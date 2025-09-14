#!/usr/bin/env python3
"""
WebSocket连接管理竞态条件修复方案

解决的关键问题:
1. 字典并发修改竞态条件
2. 任务管理并发竞争
3. 连接映射同步问题
4. 清理过程中的迭代冲突
5. 全局状态初始化竞争

技术方案:
- 使用asyncio.Lock保护关键区域
- 实现原子性操作
- 线程安全的迭代模式
- 初始化同步机制
"""

import asyncio
import uuid
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ConcurrencySafeWebSocketManager:
    """并发安全的WebSocket管理器"""
    
    def __init__(self):
        # 数据结构保持不变
        self.active_connections: Dict[str, Any] = {}
        self.user_connections: Dict[int, List[str]] = defaultdict(list)
        self.session_connections: Dict[str, str] = {}
        self.pool_stats = {
            'total_connections_created': 0,
            'total_connections_closed': 0,
            'peak_concurrent_connections': 0,
        }
        
        # 🔒 添加关键的并发控制锁
        self._connections_lock = asyncio.Lock()  # 保护连接相关操作
        self._stats_lock = asyncio.Lock()        # 保护统计信息
        self._cleanup_lock = asyncio.Lock()      # 保护清理操作
        
        # 监控任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 配置参数
        self.config = {
            'heartbeat_interval': 30,
            'cleanup_interval': 60,
            'connection_timeout': 300,
            'max_connections_per_user': 5,
            'max_total_connections': 1000,
        }

    async def connect(self, websocket, user_id: int, session_id: Optional[str] = None, 
                      client_info: Optional[Dict[str, Any]] = None) -> str:
        """并发安全的连接建立"""
        
        async with self._connections_lock:  # 🔒 锁保护整个连接建立过程
            # 检查系统总连接数限制
            if len(self.active_connections) >= self.config['max_total_connections']:
                raise ValueError(f"系统连接数已达到限制: {self.config['max_total_connections']}")
            
            # 检查用户连接数限制 - 原子性操作
            user_current_connections = len(self.user_connections.get(user_id, []))
            if user_current_connections >= self.config['max_connections_per_user']:
                # 在锁保护下安全地断开最旧连接
                oldest_connection_id = self.user_connections[user_id][0]
                await self._disconnect_unsafe(oldest_connection_id, "用户连接数达到限制，断开最旧连接")
                logger.warning(f"用户 {user_id} 连接数达到限制，自动断开最旧连接")
            
            connection_id = str(uuid.uuid4())
            
            # 创建连接实例 (假设WebSocketConnection类存在)
            from app.services.websocket_manager import WebSocketConnection
            connection = WebSocketConnection(websocket, user_id, connection_id)
            
            # 设置客户端信息
            if client_info:
                connection.client_info = client_info
            
            # 原子性地添加到所有映射
            self.active_connections[connection_id] = connection
            self.user_connections[user_id].append(connection_id)
            
            # 如果有会话ID，添加到会话映射
            if session_id:
                self.session_connections[session_id] = connection_id
                connection.session_data["session_id"] = session_id
            
            # 更新统计 - 使用统计锁
            async with self._stats_lock:
                self.pool_stats['total_connections_created'] += 1
                current_count = len(self.active_connections)
                if current_count > self.pool_stats['peak_concurrent_connections']:
                    self.pool_stats['peak_concurrent_connections'] = current_count
            
            logger.info(f"🔗 用户 {user_id} 建立WebSocket连接: {connection_id} (总连接数: {len(self.active_connections)})")
            return connection_id

    async def disconnect(self, connection_id: str, reason: str = "正常断开"):
        """并发安全的连接断开"""
        async with self._connections_lock:  # 🔒 锁保护整个断开过程
            await self._disconnect_unsafe(connection_id, reason)
    
    async def _disconnect_unsafe(self, connection_id: str, reason: str = "正常断开"):
        """内部不安全的断开方法，需要在锁保护下调用"""
        if connection_id not in self.active_connections:
            return
        
        connection = self.active_connections[connection_id]
        user_id = connection.user_id
        
        # 从活跃连接池移除
        del self.active_connections[connection_id]
        
        # 从用户连接映射移除
        if user_id in self.user_connections:
            if connection_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(connection_id)
            
            # 如果用户没有其他连接，移除用户映射
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # 从会话映射移除
        session_id = connection.session_data.get("session_id")
        if session_id and session_id in self.session_connections:
            del self.session_connections[session_id]
        
        # 标记连接为非活跃
        connection.is_active = False
        
        # 更新统计
        async with self._stats_lock:
            self.pool_stats['total_connections_closed'] += 1
        
        logger.info(f"❌ 用户 {user_id} 断开WebSocket连接: {connection_id} (原因: {reason})")

    async def send_to_user(self, user_id: int, message: dict) -> bool:
        """并发安全的用户消息发送"""
        # 创建用户连接列表的快照以避免迭代时修改
        async with self._connections_lock:
            if user_id not in self.user_connections:
                logger.warning(f"用户 {user_id} 没有活跃的WebSocket连接")
                return False
            
            # 创建连接ID列表的副本
            connection_ids = self.user_connections[user_id].copy()
            # 创建活跃连接的副本引用
            connections_snapshot = {
                conn_id: self.active_connections[conn_id] 
                for conn_id in connection_ids 
                if conn_id in self.active_connections
            }
        
        # 在锁外进行消息发送，避免长时间持有锁
        message["timestamp"] = datetime.utcnow().isoformat()
        sent_count = 0
        
        for connection_id, connection in connections_snapshot.items():
            try:
                await connection.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"发送消息到连接 {connection_id} 失败: {e}")
                # 可以选择在这里标记连接为需要清理
        
        logger.info(f"📤 向用户 {user_id} 的 {sent_count} 个连接发送消息")
        return sent_count > 0

    async def cleanup_dead_connections(self):
        """并发安全的死连接清理"""
        async with self._cleanup_lock:  # 🔒 防止多个清理任务同时运行
            dead_connections = []
            
            # 在锁保护下创建死连接列表快照
            async with self._connections_lock:
                for connection_id, connection in self.active_connections.items():
                    if not connection.is_alive(self.config['connection_timeout']):
                        dead_connections.append((connection_id, connection))
            
            # 在锁外记录统计，在锁内执行清理
            for connection_id, connection in dead_connections:
                # 确定断开原因
                if connection.consecutive_errors >= 3:
                    reason = f"连续错误过多({connection.consecutive_errors})"
                elif not connection.is_active:
                    reason = "连接已标记为非活跃"
                else:
                    reason = "心跳超时"
                
                await self.disconnect(connection_id, reason)
            
            if dead_connections:
                logger.info(f"🧹 清理了 {len(dead_connections)} 个死连接")


class ConcurrencySafeAIWebSocketHandler:
    """并发安全的AI WebSocket处理器"""
    
    def __init__(self, websocket_manager):
        self.websocket_manager = websocket_manager
        # 现有组件保持不变
        from app.services.ai_service import AIService
        from app.services.claude_account_service import ClaudeAccountService
        self.ai_service = AIService()
        self.claude_service = ClaudeAccountService()
        
        # 活跃的AI对话任务: {request_id: task}
        self.active_ai_tasks: Dict[str, asyncio.Task] = {}
        # 连接ID到请求ID的映射: {connection_id: set(request_ids)}  
        self.connection_requests: Dict[str, Set[str]] = {}
        
        # 🔒 添加任务管理锁
        self._tasks_lock = asyncio.Lock()  # 保护任务管理操作

    async def handle_ai_chat_request(self, connection_id: str, user_id: int, 
                                   message_data: dict, db):
        """并发安全的AI对话请求处理"""
        request_id = message_data.get("request_id")
        if not request_id:
            request_id = str(uuid.uuid4())
            message_data["request_id"] = request_id
        
        async with self._tasks_lock:  # 🔒 锁保护任务管理
            # 检查并取消重复任务 - 原子性操作
            if request_id in self.active_ai_tasks:
                logger.warning(f"取消重复的AI任务: {request_id}")
                old_task = self.active_ai_tasks[request_id]
                old_task.cancel()
                # 不立即删除，让任务自己在finally中清理
            
            # 创建新的AI对话任务
            ai_task = asyncio.create_task(
                self._process_streaming_ai_chat(
                    connection_id=connection_id,
                    user_id=user_id,
                    content=message_data.get("content", ""),
                    ai_mode=message_data.get("ai_mode", "trader"),
                    session_type=message_data.get("session_type", "strategy"),
                    session_id=message_data.get("session_id"),
                    request_id=request_id,
                    complexity="medium",  # 简化复杂度分析
                    db=db
                )
            )
            
            # 原子性地更新任务映射
            self.active_ai_tasks[request_id] = ai_task
            
            # 维护连接到请求的映射
            if connection_id not in self.connection_requests:
                self.connection_requests[connection_id] = set()
            self.connection_requests[connection_id].add(request_id)

    async def _process_streaming_ai_chat(self, connection_id: str, user_id: int,
                                       content: str, ai_mode: str, session_type: str,
                                       session_id: Optional[str], request_id: Optional[str],
                                       complexity: str, db):
        """流式AI对话处理 - 改进的错误处理和资源清理"""
        try:
            logger.info(f"🌊 开始真流式AI对话处理 - 用户: {user_id}, 请求ID: {request_id}")
            
            # 发送开始通知
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_stream_start",
                "request_id": request_id,
                "message": "AI正在思考中..."
            })
            
            # 调用AI服务（这里保持原有逻辑）
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
                chunk_type = stream_chunk.get("type")
                
                if chunk_type == "ai_stream_chunk":
                    # 实时转发数据块
                    await self.websocket_manager.send_to_user(user_id, {
                        "type": "ai_stream_chunk",
                        "request_id": request_id,
                        "chunk": stream_chunk.get("chunk", ""),
                        "content_so_far": stream_chunk.get("content_so_far", ""),
                        "session_id": stream_chunk.get("session_id")
                    })
                
                elif chunk_type == "ai_stream_end":
                    # 流式结束
                    await self.websocket_manager.send_to_user(user_id, {
                        "type": "ai_stream_end",
                        "request_id": request_id,
                        "session_id": stream_chunk.get("session_id"),
                        "content": stream_chunk.get("content", ""),
                        "tokens_used": stream_chunk.get("tokens_used", 0),
                        "cost_usd": stream_chunk.get("cost_usd", 0.0),
                        "message": "✅ AI回复生成完成！"
                    })
                    break
                    
                elif chunk_type == "ai_stream_error":
                    # 流式错误
                    await self.websocket_manager.send_to_user(user_id, {
                        "type": "ai_stream_error",
                        "request_id": request_id,
                        "error": str(stream_chunk.get("error", "未知错误")),
                        "retry_suggested": True
                    })
                    break
            
        except Exception as e:
            logger.error(f"❌ 流式AI对话处理失败: {e}")
            await self.websocket_manager.send_to_user(user_id, {
                "type": "ai_stream_error",
                "request_id": request_id,
                "error": str(e),
                "retry_suggested": True
            })
        finally:
            # 🔒 并发安全的任务清理
            await self._cleanup_task(request_id, connection_id)

    async def _cleanup_task(self, request_id: Optional[str], connection_id: str):
        """并发安全的任务清理"""
        if not request_id:
            return
            
        async with self._tasks_lock:
            # 清理任务引用
            if request_id in self.active_ai_tasks:
                del self.active_ai_tasks[request_id]
            
            # 清理连接映射
            if connection_id in self.connection_requests:
                self.connection_requests[connection_id].discard(request_id)
                if not self.connection_requests[connection_id]:
                    del self.connection_requests[connection_id]

    async def handle_cancel_request(self, connection_id: str, user_id: int, request_id: str):
        """并发安全的取消请求处理"""
        async with self._tasks_lock:
            if request_id in self.active_ai_tasks:
                task = self.active_ai_tasks[request_id]
                task.cancel()
                # 任务会在finally中自行清理
                
                await self.websocket_manager.send_to_user(user_id, {
                    "type": "ai_chat_cancelled", 
                    "request_id": request_id,
                    "message": "AI对话已取消"
                })
                
                logger.info(f"用户 {user_id} 取消了AI对话任务: {request_id}")

    async def cleanup_connection(self, connection_id: str):
        """并发安全的连接清理"""
        async with self._tasks_lock:
            if connection_id in self.connection_requests:
                # 创建副本避免迭代时修改
                request_ids = self.connection_requests[connection_id].copy()
                
                for request_id in request_ids:
                    if request_id in self.active_ai_tasks:
                        task = self.active_ai_tasks[request_id]
                        task.cancel()
                        # 任务会在finally中自行清理
                
                # 清理连接映射
                del self.connection_requests[connection_id]
                logger.info(f"清理连接 {connection_id} 的 {len(request_ids)} 个AI任务")


# 工厂函数，确保单例模式的线程安全
_websocket_manager_lock = asyncio.Lock()
_websocket_manager_instance = None


async def get_concurrent_safe_websocket_manager():
    """获取并发安全的WebSocket管理器单例"""
    global _websocket_manager_instance
    
    if _websocket_manager_instance is None:
        async with _websocket_manager_lock:
            # 双重检查锁定模式
            if _websocket_manager_instance is None:
                _websocket_manager_instance = ConcurrencySafeWebSocketManager()
                logger.info("🔒 创建并发安全的WebSocket管理器实例")
    
    return _websocket_manager_instance


def create_concurrent_safe_ai_handler(websocket_manager):
    """创建并发安全的AI处理器"""
    return ConcurrencySafeAIWebSocketHandler(websocket_manager)


# 测试和验证功能
async def test_concurrency_safety():
    """测试并发安全性"""
    logger.info("🧪 开始并发安全性测试...")
    
    manager = await get_concurrent_safe_websocket_manager()
    
    # 模拟并发连接建立
    async def create_connection(user_id: int, connection_num: int):
        try:
            # 模拟WebSocket对象
            class MockWebSocket:
                async def send_text(self, text): pass
                async def close(self, code=None, reason=None): pass
            
            websocket = MockWebSocket()
            connection_id = await manager.connect(websocket, user_id, f"session_{user_id}_{connection_num}")
            logger.info(f"✅ 用户 {user_id} 连接 {connection_num} 创建成功: {connection_id}")
            
            # 模拟短暂使用后断开
            await asyncio.sleep(0.1)
            await manager.disconnect(connection_id, "测试完成")
            
        except Exception as e:
            logger.error(f"❌ 用户 {user_id} 连接 {connection_num} 创建失败: {e}")
    
    # 并发创建多个连接
    tasks = []
    for user_id in range(1, 6):  # 5个用户
        for conn_num in range(1, 4):  # 每用户3个连接
            task = asyncio.create_task(create_connection(user_id, conn_num))
            tasks.append(task)
    
    # 等待所有任务完成
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # 验证最终状态
    stats = manager.pool_stats
    logger.info(f"🎯 测试结果: 创建连接={stats['total_connections_created']}, 关闭连接={stats['total_connections_closed']}")
    
    return stats['total_connections_created'] > 0 and len(manager.active_connections) == 0


if __name__ == "__main__":
    # 运行并发安全性测试
    async def main():
        logging.basicConfig(level=logging.INFO)
        success = await test_concurrency_safety()
        if success:
            print("✅ 并发安全性测试通过！")
        else:
            print("❌ 并发安全性测试失败！")
    
    asyncio.run(main())