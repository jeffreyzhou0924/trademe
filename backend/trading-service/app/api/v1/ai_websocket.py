"""
AI WebSocket 实时对话接口
- 支持长时间AI对话的实时流式响应
- 解决HTTP超时问题
- 提供进度追踪和错误处理
- 支持对话中断和恢复
"""

import asyncio
import json
import uuid
from typing import Dict, Optional, Any, Set
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import get_db
from app.middleware.auth import verify_token
from app.services.websocket_manager import get_websocket_manager, WebSocketManager
from app.services.ai_service import AIService
from app.services.claude_account_service import ClaudeAccountService
from app.services.collaborative_strategy_optimizer import collaborative_optimizer
from app.core.claude_client import ClaudeClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/ws", tags=["AI WebSocket"])


class AIWebSocketHandler:
    """AI WebSocket处理器"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.ai_service = AIService()
        self.claude_service = ClaudeAccountService()
        
        # 活跃的AI对话任务: {request_id: task}  - 改用request_id作为键以支持并发
        self.active_ai_tasks: Dict[str, asyncio.Task] = {}
        # 连接ID到请求ID的映射: {connection_id: set(request_ids)}
        self.connection_requests: Dict[str, Set[str]] = {}
    
    async def _get_streaming_claude_client(self, db: AsyncSession) -> Optional[ClaudeClient]:
        """获取流式Claude客户端实例"""
        try:
            # 从Claude账号服务获取可用账号
            account = await self.claude_service.select_best_account()
            if not account:
                logger.error("没有可用的Claude账号")
                return None
            
            # 获取解密的API密钥
            decrypted_api_key = await self.claude_service.get_decrypted_api_key(account.id)
            if not decrypted_api_key:
                logger.error("无法解密Claude API密钥")
                return None
            
            # 创建流式Claude客户端
            claude_client = ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,  # 增加超时时间支持长响应
                max_retries=2
            )
            
            logger.info(f"🤖 创建流式Claude客户端成功: {account.account_name}")
            return claude_client
            
        except Exception as e:
            logger.error(f"创建流式Claude客户端失败: {e}")
            return None
    
    async def handle_ai_chat_request(
        self,
        connection_id: str,
        user_id: int,
        message_data: dict,
        db: AsyncSession
    ):
        """
        处理AI对话请求 - 支持协作优化对话
        
        Args:
            connection_id: WebSocket连接ID
            user_id: 用户ID
            message_data: 消息数据
            db: 数据库会话
        """
        try:
            # 提取请求参数
            content = message_data.get("content", "")
            ai_mode = message_data.get("ai_mode", "trader")
            session_type = message_data.get("session_type", "strategy")
            session_id = message_data.get("session_id")
            
            # 检查是否为协作优化对话
            optimization_session_id = message_data.get("optimization_session_id")
            if optimization_session_id:
                await self._handle_collaborative_optimization(
                    connection_id=connection_id,
                    user_id=user_id,
                    optimization_session_id=optimization_session_id,
                    user_message=content,
                    request_id=message_data.get("request_id"),
                    db=db
                )
                return
            
            # 发送开始处理通知
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_chat_start",
                "request_id": message_data.get("request_id"),
                "status": "processing",
                "message": "AI正在思考中，请稍候..."
            })
            
            # 分析请求复杂度
            complexity = self._analyze_request_complexity(content)
            
            # 发送复杂度分析结果
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_complexity_analysis",
                "complexity": complexity,
                "estimated_time_seconds": self._get_estimated_time(complexity),
                "message": f"检测到{complexity}复杂度请求，预计处理时间: {self._get_estimated_time(complexity)}秒"
            })
            
            # 创建流式AI对话任务 🌊
            ai_task = asyncio.create_task(
                self._process_streaming_ai_chat(
                    connection_id=connection_id,
                    user_id=user_id,
                    content=content,
                    ai_mode=ai_mode,
                    session_type=session_type,
                    session_id=session_id,
                    request_id=message_data.get("request_id"),
                    complexity=complexity,
                    db=db
                )
            )
            
            # 保存任务引用到request_id，支持并发请求
            request_id = message_data.get("request_id")
            if request_id:
                # 如果同一个request_id已有任务在运行，取消旧任务
                if request_id in self.active_ai_tasks:
                    logger.warning(f"取消重复的AI任务: {request_id}")
                    self.active_ai_tasks[request_id].cancel()
                
                self.active_ai_tasks[request_id] = ai_task
                
                # 维护连接到请求的映射
                if connection_id not in self.connection_requests:
                    self.connection_requests[connection_id] = set()
                self.connection_requests[connection_id].add(request_id)
            
        except Exception as e:
            logger.error(f"处理AI对话请求失败: {e}")
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_chat_error",
                "request_id": message_data.get("request_id"),
                "error": str(e),
                "message": "AI对话处理失败，请稍后重试"
            })
    
    async def _process_streaming_ai_chat(
        self,
        connection_id: str,
        user_id: int,
        content: str,
        ai_mode: str,
        session_type: str,
        session_id: Optional[str],
        request_id: Optional[str],
        complexity: str,
        db: AsyncSession
    ):
        """
        真正的流式AI对话处理 - 实时推送AI响应数据块
        """
        try:
            logger.info(f"🌊 开始真流式AI对话处理 - 用户: {user_id}, 请求ID: {request_id}")
            
            # 步骤1: 初始化流式AI服务
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_progress_update",
                "request_id": request_id,
                "step": 1,
                "total_steps": 2,
                "status": "initializing",
                "message": "正在初始化真流式AI服务..."
            })
            
            # 步骤2: 开始真流式AI对话
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_progress_update",
                "request_id": request_id,
                "step": 2,
                "total_steps": 2,
                "status": "streaming",
                "message": "开始Claude AI真流式响应..."
            })
            
            # 🌊 使用真正的流式AI服务
            logger.info("🤖 调用真流式Claude AI服务...")
            
            # 使用流式AI服务
            async for stream_chunk in self.ai_service.stream_chat_completion(
                message=content,
                user_id=user_id,
                session_id=session_id,
                context={
                    'ai_mode': ai_mode,
                    'session_type': session_type,
                    'membership_level': 'professional'
                },
                db=db
            ):
                try:
                    chunk_type = stream_chunk.get("type")
                    
                    if chunk_type == "ai_stream_start":
                        # 流式开始
                        logger.info(f"🌊 AI流式响应开始 - 输入tokens: {stream_chunk.get('input_tokens', 0)}")
                        
                        await self.websocket_manager.send_to_user(user_id, {
                            "type": "ai_stream_start",
                            "request_id": request_id,
                            "session_id": stream_chunk.get("session_id"),
                            "model": stream_chunk.get("model", "claude-sonnet-4"),
                            "input_tokens": stream_chunk.get("input_tokens", 0)
                        })
                        
                    elif chunk_type == "ai_stream_chunk":
                        # 内容数据块 - 实时转发给前端
                        text_chunk = stream_chunk.get("chunk", "")
                        
                        await self.websocket_manager.send_to_user(user_id, {
                            "type": "ai_stream_chunk",
                            "request_id": request_id,
                            "chunk": text_chunk,
                            "content_so_far": stream_chunk.get("content_so_far", ""),
                            "session_id": stream_chunk.get("session_id")
                        })
                        
                        logger.debug(f"📦 实时转发数据块 - 长度: {len(text_chunk)} 字符")
                        
                    elif chunk_type == "ai_stream_end":
                        # 流式结束
                        content_full = stream_chunk.get("content", "")
                        tokens_used = stream_chunk.get("tokens_used", 0)
                        cost_usd = stream_chunk.get("cost_usd", 0.0)
                        
                        logger.info(f"✅ AI流式对话完成 - Tokens: {tokens_used}, 成本: ${cost_usd:.6f}")
                        
                        await self.websocket_manager.send_to_user(user_id, {
                            "type": "ai_stream_end",
                            "request_id": request_id,
                            "session_id": stream_chunk.get("session_id"),
                            "content": content_full,
                            "tokens_used": tokens_used,
                            "cost_usd": cost_usd,
                            "model": stream_chunk.get("model", "claude-sonnet-4"),
                            "message": "✅ 真流式AI回复生成完成！"
                        })
                        
                        logger.info(f"✅ 真流式AI对话处理完成 - Request ID: {request_id}")
                        break
                        
                    elif chunk_type == "ai_stream_error":
                        # 流式错误 - 确保错误信息是字符串格式
                        error_raw = stream_chunk.get("error", "未知流式错误")
                        error_msg = str(error_raw) if error_raw is not None else "未知流式错误"
                        logger.error(f"❌ AI流式对话错误: {error_msg}")
                        
                        await self.websocket_manager.send_to_user(user_id, {
                            "type": "ai_stream_error",
                            "request_id": request_id,
                            "error": error_msg,  # 确保是字符串
                            "error_type": "ai_stream_error",
                            "session_id": stream_chunk.get("session_id"),
                            "retry_suggested": True,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        break
                        
                except Exception as chunk_error:
                    logger.error(f"处理流式数据块错误: {chunk_error}")
                    await self.websocket_manager.send_to_user(user_id, {
                        "type": "ai_stream_error",
                        "request_id": request_id,
                        "error": f"数据块处理错误: {str(chunk_error)}",
                        "retry_suggested": True,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    break
                    
        except Exception as e:
            error_str = str(e) if str(e) else "未知异常，无错误信息"
            error_type = type(e).__name__
            
            logger.error(f"❌ 真流式AI对话处理失败 - Request ID: {request_id}")
            logger.error(f"   📋 异常类型: {error_type}")
            logger.error(f"   📝 错误信息: {error_str}")
            logger.error(f"❌ 异常堆栈跟踪:", exc_info=True)
            
            # 根据异常类型提供更具体的错误信息
            if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                error_message = "⏱️ AI请求超时，Claude服务可能繁忙，请稍后重试"
                error_type = "timeout"
            elif "empty" in error_str.lower():
                error_message = "🔍 AI响应内容为空，请重试"
                error_type = "empty_response"
            elif "connection" in error_str.lower() or "network" in error_str.lower():
                error_message = "🌐 网络连接问题，请检查网络后重试"
                error_type = "network_error"
            elif "claude api" in error_str.lower() or "claude ai" in error_str.lower():
                error_message = "🤖 Claude AI服务暂时不可用，请稍后重试"
                error_type = "api_error"
            elif "未知错误" in error_str:
                error_message = "⚠️ Claude AI服务响应异常，可能是服务过载，请稍后重试"
                error_type = "unknown_error"
            else:
                error_message = f"❌ 真流式AI对话处理失败：{error_str}"
                error_type = "general_error"
            
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_stream_error", 
                "request_id": request_id,
                "error": str(error_message),  # 确保错误消息是字符串
                "error_type": str(error_type),  # 确保错误类型是字符串
                "message": str(error_message),  # 添加message字段保持一致性
                "retry_suggested": True,
                "timestamp": datetime.utcnow().isoformat()
            })
        finally:
            # 清理任务引用
            if request_id and request_id in self.active_ai_tasks:
                del self.active_ai_tasks[request_id]
            
            # 清理连接映射
            if connection_id in self.connection_requests and request_id:
                self.connection_requests[connection_id].discard(request_id)
                if not self.connection_requests[connection_id]:
                    del self.connection_requests[connection_id]
    
    async def _handle_collaborative_optimization(
        self,
        connection_id: str,
        user_id: int,
        optimization_session_id: str,
        user_message: str,
        request_id: Optional[str],
        db: AsyncSession
    ):
        """
        处理协作优化对话
        """
        try:
            logger.info(f"📝 处理协作优化对话 - 用户: {user_id}, 优化会话: {optimization_session_id}")
            
            # 发送处理开始通知
            await self.websocket_manager.send_to_user(user_id, {
                "type": "optimization_processing",
                "request_id": request_id,
                "optimization_session_id": optimization_session_id,
                "message": "正在处理您的反馈..."
            })
            
            # 调用协作优化器处理用户消息
            result = await collaborative_optimizer.handle_user_response(
                session_id=optimization_session_id,
                user_message=user_message,
                user_id=user_id
            )
            
            if result["success"]:
                # 根据优化阶段发送不同类型的响应
                stage = result.get("stage", "unknown")
                
                response_data = {
                    "type": "optimization_response",
                    "request_id": request_id,
                    "optimization_session_id": optimization_session_id,
                    "stage": stage,
                    "message": result["message"],
                    "requires_user_input": result.get("requires_user_input", True),
                    "is_processing": result.get("is_processing", False)
                }
                
                # 特殊处理：如果需要回测或者优化完成，添加额外信息
                if stage == "awaiting_backtest":
                    response_data["awaiting_backtest"] = True
                    response_data["estimated_time"] = 30
                elif stage == "backtest_review":
                    response_data["optimization_results"] = result.get("optimization_results", {})
                elif stage == "completed":
                    response_data["optimization_completed"] = True
                    response_data["final_results"] = result.get("final_results", {})
                
                await self.websocket_manager.send_to_user(user_id, response_data)
                
            else:
                # 处理失败
                await self.websocket_manager.send_to_user(user_id, {
                    "type": "optimization_error",
                    "request_id": request_id,
                    "optimization_session_id": optimization_session_id,
                    "error": result.get("error", "协作优化处理失败"),
                    "message": "处理您的消息时出现问题，请重试或重新开始优化。"
                })
                
        except Exception as e:
            logger.error(f"协作优化对话处理失败: {e}")
            await self.websocket_manager.send_to_user(user_id, {
                "type": "optimization_error",
                "request_id": request_id,
                "optimization_session_id": optimization_session_id,
                "error": str(e),
                "message": "协作优化服务暂时不可用，请稍后重试。"
            })
    
    def _analyze_request_complexity(self, content: str) -> str:
        """分析请求复杂度"""
        total_chars = len(content)
        
        # 检测复杂关键词
        complex_keywords = ["策略", "代码", "分析", "算法", "回测", "交易", "指标", "MACD", "RSI", "背离"]
        complex_count = sum(1 for keyword in complex_keywords if keyword in content)
        
        if total_chars > 1000 or complex_count >= 2:
            return "complex"
        elif total_chars > 200 or complex_count >= 1:
            return "medium"
        else:
            return "simple"
    
    def _get_estimated_time(self, complexity: str) -> int:
        """获取预估处理时间"""
        time_map = {
            "simple": 15,
            "medium": 45, 
            "complex": 120
        }
        return time_map.get(complexity, 45)
    
    async def _process_ai_chat_with_progress(
        self,
        connection_id: str,
        user_id: int,
        content: str,
        ai_mode: str,
        session_type: str,
        session_id: Optional[str],
        request_id: Optional[str],
        complexity: str,
        db: AsyncSession
    ):
        """
        带进度追踪的AI对话处理
        """
        try:
            # 步骤1: 准备AI服务
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_progress_update",
                "request_id": request_id,
                "step": 1,
                "total_steps": 4,
                "status": "preparing",
                "message": "正在准备AI服务..."
            })
            
            await asyncio.sleep(1)  # 模拟准备时间
            
            # 步骤2: 分析用户意图
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_progress_update", 
                "request_id": request_id,
                "step": 2,
                "total_steps": 4,
                "status": "analyzing",
                "message": "正在分析您的需求..."
            })
            
            # 步骤3: 生成AI回复 (这里是真实的AI调用)
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_progress_update",
                "request_id": request_id, 
                "step": 3,
                "total_steps": 4,
                "status": "generating",
                "message": f"Claude AI正在生成回复 (复杂度: {complexity})..."
            })
            
            # 调用AI服务 - 使用优化后的错误处理机制
            try:
                response = await self.ai_service.chat_completion(
                    message=content,
                    user_id=user_id,
                    context=None,
                    session_id=session_id,
                    db=db
                )
                
                # 步骤4: 完成处理
                await self.websocket_manager.send_to_user(user_id, {
                    "type": "ai_progress_update",
                    "request_id": request_id,
                    "step": 4,
                    "total_steps": 4,
                    "status": "completing",
                    "message": "正在完成处理..."
                })
                
                await asyncio.sleep(0.5)  # 短暂延迟确保用户看到完成状态
                
                # 发送最终成功响应
                await self.websocket_manager.send_to_user(user_id, {
                    "type": "ai_chat_success",
                    "request_id": request_id,
                    "response": response.get("response", ""),
                    "session_id": response.get("session_id"),
                    "tokens_used": response.get("tokens_used", 0),
                    "model": response.get("model", ""),
                    "cost_usd": response.get("cost_usd", 0.0),
                    "message": "AI回复生成完成！"
                })
                
            except Exception as ai_error:
                logger.error(f"AI调用失败: {ai_error}")
                
                # 分析错误类型并提供友好的错误信息
                error_message = self._get_friendly_error_message(str(ai_error), complexity)
                
                await self.websocket_manager.send_to_user(user_id, {
                    "type": "ai_chat_error",
                    "request_id": request_id,
                    "error": error_message,
                    "error_code": "AI_PROCESSING_FAILED",
                    "complexity": complexity,
                    "retry_suggested": True,
                    "message": error_message
                })
                
        except asyncio.CancelledError:
            # 任务被取消（用户断开连接）
            logger.info(f"AI对话任务被取消: {connection_id}")
            
        except Exception as e:
            logger.error(f"AI对话处理异常: {e}")
            
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_chat_error",
                "request_id": request_id,
                "error": str(e),
                "error_code": "INTERNAL_ERROR",
                "message": "系统内部错误，请稍后重试"
            })
        
        finally:
            # 清理任务引用 (这是_process_ai_chat_with_progress方法，应该也用request_id)
            if request_id and request_id in self.active_ai_tasks:
                del self.active_ai_tasks[request_id]
            
            # 清理连接映射
            if connection_id in self.connection_requests and request_id:
                self.connection_requests[connection_id].discard(request_id)
                if not self.connection_requests[connection_id]:
                    del self.connection_requests[connection_id]
    
    def _get_friendly_error_message(self, error: str, complexity: str) -> str:
        """获取友好的错误信息"""
        if "504" in error or "Gateway Timeout" in error:
            if complexity == "complex":
                return "复杂请求处理超时，建议将请求拆分为多个简单问题，或稍后重试"
            elif complexity == "medium":
                return "请求处理超时，建议稍后重试或简化问题"
            else:
                return "网络超时，请检查网络连接或稍后重试"
        
        elif "RATE_LIMIT" in error:
            return "API调用频率过高，请稍后重试"
        
        elif "QUOTA_EXCEEDED" in error:
            return "AI服务配额已耗尽，请联系管理员"
        
        elif "INVALID_API_KEY" in error:
            return "AI服务配置错误，请联系管理员"
        
        else:
            return f"AI服务暂时不可用: {error[:100]}..."
    
    async def handle_cancel_request(self, connection_id: str, user_id: int, request_id: str):
        """处理取消AI对话请求"""
        if request_id and request_id in self.active_ai_tasks:
            task = self.active_ai_tasks[request_id]
            task.cancel()
            del self.active_ai_tasks[request_id]
            
            # 清理连接映射
            if connection_id in self.connection_requests:
                self.connection_requests[connection_id].discard(request_id)
                if not self.connection_requests[connection_id]:
                    del self.connection_requests[connection_id]
            
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_chat_cancelled",
                "request_id": request_id,
                "message": "AI对话已取消"
            })
            
            logger.info(f"用户 {user_id} 取消了AI对话任务: {request_id}")
        else:
            logger.warning(f"未找到可取消的AI任务: {request_id}")
    
    async def cleanup_connection(self, connection_id: str):
        """清理连接相关的AI任务"""
        if connection_id in self.connection_requests:
            request_ids = self.connection_requests[connection_id].copy()
            for request_id in request_ids:
                if request_id in self.active_ai_tasks:
                    task = self.active_ai_tasks[request_id]
                    task.cancel()
                    del self.active_ai_tasks[request_id]
            
            del self.connection_requests[connection_id]
            logger.info(f"清理连接 {connection_id} 的 {len(request_ids)} 个AI任务")


# 全局AI WebSocket处理器
ai_websocket_handler = AIWebSocketHandler(None)


@router.websocket("/chat")
async def ai_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    AI WebSocket对话端点
    
    连接参数:
        - token: JWT认证令牌 (可选，可通过消息验证)
    
    支持的消息类型:
        - ai_chat: AI对话请求
        - cancel_request: 取消当前AI请求
        - ping: 心跳检测
    """
    websocket_manager = await get_websocket_manager()
    
    # 初始化AI处理器
    if ai_websocket_handler.websocket_manager is None:
        ai_websocket_handler.websocket_manager = websocket_manager
    
    # 接受WebSocket连接
    await websocket.accept()
    
    # 连接建立时的临时状态
    connection_id = None
    user_id = None
    
    try:
        while True:
            # 接收客户端消息
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "无效的JSON格式"
                })
                continue
            
            message_type = message.get("type")
            
            # 处理认证消息
            if message_type == "authenticate":
                try:
                    token = message.get("token")
                    if not token:
                        await websocket.send_json({
                            "type": "auth_error",
                            "message": "缺少认证令牌"
                        })
                        continue
                    
                    # 验证JWT令牌
                    token_payload = verify_token(token)
                    if not token_payload:
                        await websocket.send_json({
                            "type": "auth_error",
                            "message": "无效的JWT令牌"
                        })
                        continue
                    
                    user_id = int(token_payload.user_id)
                    
                    # 建立WebSocket连接管理
                    connection_id = await websocket_manager.connect(
                        websocket=websocket,
                        user_id=user_id,
                        session_id=message.get("session_id")
                    )
                    
                    await websocket.send_json({
                        "type": "auth_success",
                        "connection_id": connection_id,
                        "user_id": user_id,
                        "message": "认证成功，AI对话已准备就绪"
                    })
                    
                    logger.info(f"用户 {user_id} 通过WebSocket认证成功")
                    
                except Exception as e:
                    await websocket.send_json({
                        "type": "auth_error",
                        "message": f"认证失败: {str(e)}"
                    })
                    continue
            
            # 需要认证的消息类型
            elif user_id is None:
                await websocket.send_json({
                    "type": "error",
                    "message": "请先发送authenticate消息进行认证"
                })
                continue
            
            # 处理AI对话请求
            elif message_type == "ai_chat":
                # 生成请求ID
                request_id = message.get("request_id") or str(uuid.uuid4())
                message["request_id"] = request_id
                
                # 异步处理AI对话
                await ai_websocket_handler.handle_ai_chat_request(
                    connection_id=connection_id,
                    user_id=user_id,
                    message_data=message,
                    db=db
                )
            
            # 处理协作优化对话请求
            elif message_type == "optimization_chat":
                request_id = message.get("request_id") or str(uuid.uuid4())
                message["request_id"] = request_id
                
                await ai_websocket_handler._handle_collaborative_optimization(
                    connection_id=connection_id,
                    user_id=user_id,
                    optimization_session_id=message.get("optimization_session_id"),
                    user_message=message.get("content", ""),
                    request_id=request_id,
                    db=db
                )
            
            # 处理取消请求
            elif message_type == "cancel_request":
                request_id = message.get("request_id")
                await ai_websocket_handler.handle_cancel_request(
                    connection_id=connection_id,
                    user_id=user_id,
                    request_id=request_id
                )
            
            # 处理心跳检测
            elif message_type == "ping":
                await websocket_manager.handle_ping(connection_id)
            
            # 未知消息类型
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {message_type}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: {connection_id}")
    
    except Exception as e:
        logger.error(f"WebSocket处理异常: {e}")
        
    finally:
        # 清理连接和任务
        if connection_id:
            await ai_websocket_handler.cleanup_connection(connection_id)
            await websocket_manager.disconnect(connection_id, "连接关闭")


@router.get("/connections/stats")
async def get_websocket_stats(
    websocket_manager: WebSocketManager = Depends(get_websocket_manager)
):
    """获取WebSocket连接统计信息"""
    stats = websocket_manager.get_connection_stats()
    
    # 添加AI任务统计
    stats["active_ai_tasks"] = len(ai_websocket_handler.active_ai_tasks)
    
    return {
        "status": "success",
        "data": stats
    }