"""
流式响应处理器
- 处理Claude API的流式响应
- 与WebSocket连接管理器集成
- 提供实时AI对话体验
- 支持错误处理和连接管理
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
import logging
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.websocket_manager import WebSocketManager, get_websocket_manager
from app.middleware.claude_proxy import ClaudeProxyMiddleware
from app.services.user_claude_key_service import UserClaudeKeyService
from app.services.claude_account_service import ClaudeAccountService
from app.database import get_db

logger = logging.getLogger(__name__)


class StreamErrorType(str, Enum):
    """流式错误类型枚举"""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "auth_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    API_ERROR = "api_error"
    WEBSOCKET_ERROR = "websocket_error"
    CLAUDE_ACCOUNT_ERROR = "claude_account_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy:
    """重试策略配置 - 增强版本"""
    
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt_count = 0
    
    def should_retry(self, error_type: StreamErrorType) -> bool:
        """判断是否应该重试"""
        if self.attempt_count >= self.max_retries:
            return False
            
        # 根据错误类型决定是否重试
        retryable_errors = {
            StreamErrorType.NETWORK_ERROR,
            StreamErrorType.TIMEOUT_ERROR,
            StreamErrorType.RATE_LIMIT_ERROR,
            StreamErrorType.API_ERROR
        }
        return error_type in retryable_errors
    
    def get_delay(self) -> float:
        """获取重试延迟时间（指数退避）"""
        delay = self.base_delay * (2 ** self.attempt_count)
        return min(delay, self.max_delay)
    
    def increment(self):
        """增加重试计数"""
        self.attempt_count += 1


class StreamingRecoveryManager:
    """流式响应恢复管理器"""
    
    def __init__(self):
        self.failed_accounts: Dict[int, datetime] = {}  # 失败账号及其恢复时间
        self.recovery_timeout = timedelta(minutes=5)  # 账号恢复超时
    
    def mark_account_failed(self, account_id: int):
        """标记账号失败"""
        self.failed_accounts[account_id] = datetime.utcnow() + self.recovery_timeout
        logger.warning(f"🚫 Claude账号 {account_id} 被标记为失败，将在 {self.recovery_timeout} 后重试")
    
    def is_account_available(self, account_id: int) -> bool:
        """检查账号是否可用"""
        if account_id not in self.failed_accounts:
            return True
            
        recovery_time = self.failed_accounts[account_id]
        if datetime.utcnow() > recovery_time:
            # 超过恢复时间，移除失败标记
            del self.failed_accounts[account_id]
            logger.info(f"✅ Claude账号 {account_id} 恢复可用状态")
            return True
            
        return False
    
    def get_failed_accounts(self) -> List[int]:
        """获取当前失败的账号列表"""
        return list(self.failed_accounts.keys())


class StreamingMessage:
    """流式消息数据结构"""
    
    def __init__(self, message_type: str, content: Any, session_id: str = None):
        self.type = message_type
        self.content = content
        self.session_id = session_id
        self.timestamp = datetime.utcnow().isoformat()
        self.message_id = str(uuid.uuid4())
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "content": self.content,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "message_id": self.message_id
        }


class StreamingResponseHandler:
    """流式响应处理器 - 增强版本，包含完整的错误恢复机制"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.active_streams: Dict[str, bool] = {}  # 追踪活跃的流式会话
        self.claude_proxy = ClaudeProxyMiddleware()
        self.recovery_manager = StreamingRecoveryManager()  # 恢复管理器
        self.connection_health: Dict[str, datetime] = {}  # 连接健康状态
        self.stream_heartbeat: Dict[str, datetime] = {}  # 流式连接心跳
        self.connection_stats: Dict[str, int] = {}  # 连接统计
        
    async def start_ai_stream(
        self, 
        user_id: int, 
        session_id: str, 
        message: str,
        ai_mode: str = "trader",
        session_type: str = "chat",
        db: AsyncSession = None
    ):
        """
        启动AI流式对话 - 增强版本，包含完整的错误恢复机制
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 用户消息内容
            ai_mode: AI模式 (trader, developer, analyst)
            session_type: 会话类型 (chat, strategy, indicator)
            db: 数据库会话
        """
        stream_id = f"{user_id}_{session_id}_{int(time.time())}"
        self.active_streams[stream_id] = True
        retry_strategy = RetryStrategy(max_retries=3)
        
        # 更新连接健康状态
        self.connection_health[session_id] = datetime.utcnow()
        
        try:
            # 发送开始消息
            start_msg = StreamingMessage(
                "stream_start",
                {
                    "stream_id": stream_id,
                    "user_message": message,
                    "ai_mode": ai_mode,
                    "session_type": session_type,
                    "retry_enabled": True
                },
                session_id
            )
            await self._safe_send_message(session_id, start_msg.to_dict())
            
            # 获取用户虚拟密钥
            user_key_service = UserClaudeKeyService(db)
            virtual_key = await user_key_service.get_user_virtual_key(user_id)
            
            if not virtual_key:
                await self._send_error_message(
                    session_id, 
                    "未找到用户虚拟API密钥", 
                    StreamErrorType.AUTHENTICATION_ERROR
                )
                return
            
            # 创建流式请求
            request_data = {
                "content": message,
                "ai_mode": ai_mode,
                "session_type": session_type,
                "stream": True
            }
            
            # 带重试机制的流式处理
            success = await self._process_stream_with_retry(
                stream_id, session_id, virtual_key, request_data, db, retry_strategy
            )
            
            # 发送结束消息
            if self.active_streams.get(stream_id, False) and success:
                end_msg = StreamingMessage(
                    "stream_end",
                    {"stream_id": stream_id, "status": "completed"},
                    session_id
                )
                await self._safe_send_message(session_id, end_msg.to_dict())
            elif not success:
                # 流式失败，尝试降级到非流式
                await self._fallback_to_non_streaming(
                    session_id, virtual_key, request_data, db
                )
                
        except Exception as e:
            error_type = self._classify_error(e)
            logger.error(f"❌ 流式响应处理异常: {e}, 错误类型: {error_type}")
            await self._send_error_message(session_id, str(e), error_type)
            
        finally:
            # 清理流式会话
            self.active_streams.pop(stream_id, None)
            self.connection_health.pop(session_id, None)
            self.stream_heartbeat.pop(stream_id, None)
            logger.info(f"🧹 已清理流式会话: {stream_id}")

    async def _process_stream_with_retry(
        self,
        stream_id: str,
        session_id: str,
        virtual_key: str,
        request_data: dict,
        db: AsyncSession,
        retry_strategy: RetryStrategy
    ) -> bool:
        """带重试机制的流式处理"""
        
        while retry_strategy.should_retry(StreamErrorType.UNKNOWN_ERROR):
            try:
                # 处理流式请求
                async for chunk in self._process_streaming_request(
                    stream_id, session_id, virtual_key, request_data, db
                ):
                    if not self.active_streams.get(stream_id, False):
                        logger.info(f"🛑 流式会话 {stream_id} 已停止")
                        return False
                    
                    # 安全发送流式数据块
                    chunk_msg = StreamingMessage("stream_chunk", chunk, session_id)
                    await self._safe_send_message(session_id, chunk_msg.to_dict())
                    
                    # 更新流式连接心跳
                    self.stream_heartbeat[stream_id] = datetime.utcnow()
                    self.connection_health[session_id] = datetime.utcnow()
                    
                    # 短暂延时避免过快发送
                    await asyncio.sleep(0.01)
                
                # 成功完成，返回True
                return True
                
            except Exception as e:
                error_type = self._classify_error(e)
                logger.warning(f"⚠️ 流式处理失败 (尝试 {retry_strategy.attempt_count + 1}): {e}")
                
                if retry_strategy.should_retry(error_type):
                    retry_strategy.increment()
                    delay = retry_strategy.get_delay()
                    
                    # 发送重试通知
                    retry_msg = StreamingMessage(
                        "stream_retry",
                        {
                            "attempt": retry_strategy.attempt_count,
                            "max_retries": retry_strategy.max_retries,
                            "delay": delay,
                            "error_type": error_type
                        },
                        session_id
                    )
                    await self._safe_send_message(session_id, retry_msg.to_dict())
                    
                    # 等待重试延迟
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"❌ 流式处理最终失败: {e}")
                    return False
        
        return False

    async def _safe_send_message(self, session_id: str, message: dict, timeout: float = 15.0):
        """安全发送消息，包含超时和错误处理 - 增加到15秒超时"""
        try:
            await asyncio.wait_for(
                self.websocket_manager.send_to_session(session_id, message),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"⏰ WebSocket发送超时({timeout}s): {session_id}, 消息类型: {message.get('type', 'unknown')}")
        except WebSocketDisconnect:
            logger.warning(f"🔌 WebSocket连接断开: {session_id}")
        except Exception as e:
            logger.error(f"❌ WebSocket发送失败: {e}")
            # 增加错误详情用于调试
            import traceback
            logger.debug(f"WebSocket发送错误详情: {traceback.format_exc()}")

    async def _send_error_message(
        self, 
        session_id: str, 
        error: str, 
        error_type: StreamErrorType
    ):
        """发送错误消息"""
        error_msg = StreamingMessage(
            "stream_error",
            {
                "error": error,
                "error_type": error_type,
                "code": error_type.upper(),
                "recoverable": error_type in {
                    StreamErrorType.NETWORK_ERROR,
                    StreamErrorType.TIMEOUT_ERROR,
                    StreamErrorType.RATE_LIMIT_ERROR
                }
            },
            session_id
        )
        await self._safe_send_message(session_id, error_msg.to_dict())

    def _classify_error(self, error: Exception) -> StreamErrorType:
        """错误分类 - 增强版本"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # 更精确的超时检测
        if ("timeout" in error_str or 
            "timed out" in error_str or 
            error_type == "timeouterror" or
            "read timeout" in error_str or
            "connection timeout" in error_str):
            logger.debug(f"检测到超时错误: {error_str}")
            return StreamErrorType.TIMEOUT_ERROR
        elif ("network" in error_str or 
              "connection" in error_str or
              "connectionerror" in error_type or
              "connection reset" in error_str or
              "connection refused" in error_str):
            logger.debug(f"检测到网络错误: {error_str}")
            return StreamErrorType.NETWORK_ERROR
        elif "auth" in error_str or "unauthorized" in error_str or "401" in error_str:
            return StreamErrorType.AUTHENTICATION_ERROR
        elif "rate limit" in error_str or "too many requests" in error_str or "429" in error_str:
            return StreamErrorType.RATE_LIMIT_ERROR
        elif "websocket" in error_str:
            return StreamErrorType.WEBSOCKET_ERROR
        elif ("claude" in error_str or 
              "api" in error_str or
              "service unavailable" in error_str or
              "internal server error" in error_str):
            return StreamErrorType.API_ERROR
        else:
            logger.debug(f"未分类错误: {error_str} (类型: {error_type})")
            return StreamErrorType.UNKNOWN_ERROR

    async def _fallback_to_non_streaming(
        self, 
        session_id: str, 
        virtual_key: str, 
        request_data: dict, 
        db: AsyncSession
    ):
        """降级到非流式响应"""
        try:
            logger.info(f"🔄 流式失败，降级到非流式响应: {session_id}")
            
            # 发送降级通知
            fallback_msg = StreamingMessage(
                "stream_fallback",
                {
                    "message": "流式响应不可用，切换到标准响应模式",
                    "fallback_type": "non_streaming"
                },
                session_id
            )
            await self._safe_send_message(session_id, fallback_msg.to_dict())
            
            # 这里可以调用非流式的AI服务
            # 例如：直接调用unified_proxy_ai_service
            from app.services.simplified_ai_service import unified_proxy_ai_service
            
            response = await unified_proxy_ai_service(
                virtual_api_key=virtual_key,
                message=request_data["content"],
                ai_mode=request_data.get("ai_mode", "trader"),
                session_type=request_data.get("session_type", "general"),
                session_id=session_id,
                db=db
            )
            
            # 发送非流式响应
            response_msg = StreamingMessage(
                "stream_fallback_response",
                {
                    "response": response.get("response", ""),
                    "session_id": response.get("session_id"),
                    "tokens_used": response.get("tokens_used", 0),
                    "cost_usd": response.get("cost_usd", 0.0)
                },
                session_id
            )
            await self._safe_send_message(session_id, response_msg.to_dict())
            
        except Exception as e:
            logger.error(f"❌ 降级到非流式响应失败: {e}")
            await self._send_error_message(
                session_id, 
                "系统暂时不可用，请稍后重试", 
                StreamErrorType.UNKNOWN_ERROR
            )
    
    async def _get_healthy_account(self, claude_account_service: ClaudeAccountService):
        """
        获取健康的Claude账号（排除失败的账号）
        
        Args:
            claude_account_service: Claude账号服务
            
        Returns:
            可用的Claude账号对象，如果没有则返回None
        """
        try:
            # 获取所有可用的Claude账号
            accounts = await claude_account_service.get_available_accounts()
            
            if not accounts:
                logger.warning("⚠️ 没有找到可用的Claude账号")
                return None
            
            # 过滤出健康的账号（排除恢复管理器中标记为失败的账号）
            healthy_accounts = [
                account for account in accounts
                if self.recovery_manager.is_account_available(account.id)
            ]
            
            if not healthy_accounts:
                logger.warning("⚠️ 所有Claude账号都处于失败状态，等待恢复")
                # 如果所有账号都失败了，可以选择返回一个账号进行重试
                # 或者返回None让系统进行错误处理
                failed_accounts = self.recovery_manager.get_failed_accounts()
                logger.info(f"失败账号列表: {failed_accounts}")
                return None
            
            # 选择第一个健康的账号（可以在这里实现负载均衡算法）
            selected_account = healthy_accounts[0]
            logger.info(f"✅ 选择健康的Claude账号: {selected_account.account_name} (ID: {selected_account.id})")
            
            return selected_account
            
        except Exception as e:
            logger.error(f"❌ 获取健康Claude账号失败: {e}")
            return None

    async def _process_streaming_request(
        self, 
        stream_id: str, 
        session_id: str,
        virtual_key: str, 
        request_data: dict,
        db: AsyncSession
    ) -> AsyncGenerator[dict, None]:
        """
        处理流式Claude API请求
        
        Args:
            stream_id: 流式会话ID
            session_id: WebSocket会话ID
            virtual_key: 用户虚拟API密钥
            request_data: 请求数据
            db: 数据库会话
            
        Yields:
            流式响应数据块
        """
        try:
            # 通过Claude代理中间件处理流式请求
            claude_account_service = ClaudeAccountService(db)
            
            # 获取可用的Claude账号（排除失败账号）
            account = await self._get_healthy_account(claude_account_service)
            if not account:
                yield {"error": "没有可用的Claude账号", "code": "NO_ACCOUNT"}
                return
            
            logger.info(f"🎯 流式请求使用Claude账号: {account.account_name} (ID: {account.id})")
            
            # 构造流式请求参数
            messages = [{"role": "user", "content": request_data["content"]}]
            
            # 根据AI模式调整系统提示
            system_prompt = self._get_system_prompt(
                request_data.get("ai_mode", "trader"),
                request_data.get("session_type", "chat")
            )
            
            try:
                # 通过Claude代理中间件处理流式请求
                # 这里应该实际调用Claude API的流式接口
                # 目前使用模拟数据进行演示
                
                # 构造请求数据
                proxy_request = {
                    "virtual_api_key": virtual_key,
                    "messages": messages,
                    "system": system_prompt,
                    "stream": True,
                    "claude_account_id": account.id
                }
                
                # 实际项目中应该调用: 
                # async for chunk in self.claude_proxy.stream_claude_request(proxy_request):
                #     yield chunk
                
                # 模拟流式响应处理 (演示用)
                response_text = f"正在为您分析「{request_data['content']}」的{request_data.get('session_type', '策略')}建议..."
                
                # 分块发送响应
                words = response_text.split()
                current_text = ""
                
                for i, word in enumerate(words):
                    if not self.active_streams.get(stream_id, False):
                        break
                        
                    current_text += word + " "
                    
                    chunk_data = {
                        "text": word + " ",
                        "full_text": current_text.strip(),
                        "chunk_index": i,
                        "total_chunks": len(words),
                        "is_final": i == len(words) - 1,
                        "account_id": account.id  # 包含使用的账号信息
                    }
                    
                    yield chunk_data
                    
                    # 模拟真实的响应延迟
                    await asyncio.sleep(0.05)
                    
            except Exception as claude_error:
                # Claude账号相关错误，标记账号为失败状态
                error_type = self._classify_error(claude_error)
                if error_type in {StreamErrorType.API_ERROR, StreamErrorType.CLAUDE_ACCOUNT_ERROR, 
                                StreamErrorType.AUTHENTICATION_ERROR, StreamErrorType.RATE_LIMIT_ERROR}:
                    self.recovery_manager.mark_account_failed(account.id)
                    logger.error(f"❌ Claude账号 {account.id} 失败，已标记为不可用: {claude_error}")
                
                # 重新抛出异常让上层处理重试逻辑
                raise claude_error
            
            # 最终响应数据
            yield {
                "text": "",
                "full_text": current_text.strip(),
                "chunk_index": len(words),
                "total_chunks": len(words),
                "is_final": True,
                "metadata": {
                    "ai_mode": request_data.get("ai_mode"),
                    "session_type": request_data.get("session_type"),
                    "tokens_used": len(current_text.split()),
                    "response_time_ms": int(len(words) * 50)  # 模拟响应时间
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 流式请求处理异常: {e}")
            yield {"error": str(e), "code": "PROCESSING_ERROR"}
    
    def _get_system_prompt(self, ai_mode: str, session_type: str) -> str:
        """
        根据AI模式和会话类型获取系统提示
        
        Args:
            ai_mode: AI模式
            session_type: 会话类型
            
        Returns:
            系统提示文本
        """
        base_prompts = {
            "trader": "你是一个专业的数字货币交易员，专注于技术分析和交易策略。",
            "developer": "你是一个专业的量化开发工程师，擅长编写交易算法和策略代码。",
            "analyst": "你是一个专业的市场分析师，专注于基本面和技术面分析。"
        }
        
        session_prompts = {
            "strategy": "请专注于生成可执行的交易策略，包含明确的买卖规则。",
            "indicator": "请专注于创建技术指标，提供清晰的计算公式和使用方法。",
            "chat": "请提供友好且专业的对话体验。"
        }
        
        base = base_prompts.get(ai_mode, base_prompts["trader"])
        session = session_prompts.get(session_type, session_prompts["chat"])
        
        return f"{base} {session}"
    
    async def stop_stream(self, stream_id: str):
        """
        停止指定的流式会话
        
        Args:
            stream_id: 流式会话ID
        """
        if stream_id in self.active_streams:
            self.active_streams[stream_id] = False
            logger.info(f"🛑 已停止流式会话: {stream_id}")
    
    async def stop_user_streams(self, user_id: int):
        """
        停止指定用户的所有流式会话
        
        Args:
            user_id: 用户ID
        """
        user_streams = [
            stream_id for stream_id in self.active_streams.keys()
            if stream_id.startswith(f"{user_id}_")
        ]
        
        for stream_id in user_streams:
            self.active_streams[stream_id] = False
            
        if user_streams:
            logger.info(f"🛑 已停止用户 {user_id} 的 {len(user_streams)} 个流式会话")
    
    def get_active_streams_stats(self) -> dict:
        """
        获取活跃流式会话统计
        
        Returns:
            统计信息字典
        """
        active_count = sum(1 for active in self.active_streams.values() if active)
        total_count = len(self.active_streams)
        
        # 获取连接健康状态
        healthy_connections = sum(
            1 for session_id, last_active in self.connection_health.items()
            if (datetime.utcnow() - last_active).total_seconds() < 300  # 5分钟内活跃
        )
        
        # 获取恢复管理器统计
        failed_accounts = self.recovery_manager.get_failed_accounts()
        
        return {
            "active_streams": active_count,
            "total_streams": total_count,
            "stream_ids": list(self.active_streams.keys()),
            "healthy_connections": healthy_connections,
            "total_connections": len(self.connection_health),
            "failed_accounts": failed_accounts,
            "failed_account_count": len(failed_accounts)
        }

    async def cleanup_stale_connections(self):
        """
        清理过期的连接和流式会话
        """
        current_time = datetime.utcnow()
        cleanup_timeout = timedelta(minutes=10)  # 10分钟超时
        
        # 清理过期的连接健康记录
        stale_sessions = [
            session_id for session_id, last_active in self.connection_health.items()
            if current_time - last_active > cleanup_timeout
        ]
        
        for session_id in stale_sessions:
            self.connection_health.pop(session_id, None)
            logger.info(f"🧹 清理过期连接: {session_id}")
        
        # 清理不活跃的流式会话
        stale_streams = [
            stream_id for stream_id, active in self.active_streams.items()
            if not active
        ]
        
        for stream_id in stale_streams:
            self.active_streams.pop(stream_id, None)
            self.stream_heartbeat.pop(stream_id, None)
            logger.info(f"🧹 清理非活跃流式会话: {stream_id}")
        
        # 清理过期的心跳记录
        stale_heartbeats = [
            stream_id for stream_id, last_heartbeat in self.stream_heartbeat.items()
            if current_time - last_heartbeat > cleanup_timeout
        ]
        
        for stream_id in stale_heartbeats:
            self.stream_heartbeat.pop(stream_id, None)
            logger.info(f"🧹 清理过期心跳记录: {stream_id}")
        
        if stale_sessions or stale_streams or stale_heartbeats:
            logger.info(f"🧹 清理完成: {len(stale_sessions)}个过期连接, {len(stale_streams)}个非活跃流")

    async def get_recovery_status(self) -> dict:
        """
        获取错误恢复状态
        
        Returns:
            恢复状态统计
        """
        failed_accounts = self.recovery_manager.failed_accounts
        current_time = datetime.utcnow()
        
        recovery_info = []
        for account_id, recovery_time in failed_accounts.items():
            remaining_time = (recovery_time - current_time).total_seconds()
            recovery_info.append({
                "account_id": account_id,
                "recovery_time": recovery_time.isoformat(),
                "remaining_seconds": max(0, remaining_time),
                "can_recover": remaining_time <= 0
            })
        
        return {
            "failed_account_count": len(failed_accounts),
            "recovery_timeout_minutes": self.recovery_manager.recovery_timeout.total_seconds() / 60,
            "accounts_detail": recovery_info
        }


# 全局流式响应处理器实例
_streaming_handler: Optional[StreamingResponseHandler] = None


async def get_streaming_handler() -> StreamingResponseHandler:
    """获取流式响应处理器实例"""
    global _streaming_handler
    
    if _streaming_handler is None:
        websocket_manager = await get_websocket_manager()
        _streaming_handler = StreamingResponseHandler(websocket_manager)
        logger.info("🚀 流式响应处理器已初始化")
    
    return _streaming_handler


class StreamingContext:
    """流式会话上下文管理器"""
    
    def __init__(self, user_id: int, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.handler: Optional[StreamingResponseHandler] = None
    
    async def __aenter__(self):
        self.handler = await get_streaming_handler()
        return self.handler
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.handler and exc_type is not None:
            # 如果发生异常，停止用户的所有流式会话
            await self.handler.stop_user_streams(self.user_id)


@asynccontextmanager
async def streaming_context(user_id: int, session_id: str):
    """流式会话上下文管理器的便捷函数"""
    ctx = StreamingContext(user_id, session_id)
    async with ctx as handler:
        yield handler