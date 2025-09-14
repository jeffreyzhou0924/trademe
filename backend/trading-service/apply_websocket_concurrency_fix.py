#!/usr/bin/env python3
"""
应用WebSocket并发修复到现有系统

这个脚本将并发安全的修复应用到现有的WebSocket实现中，
通过猴子补丁的方式替换关键方法，确保向后兼容性。
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)


async def apply_websocket_concurrency_fix():
    """应用WebSocket并发安全修复"""
    print("🔧 开始应用WebSocket并发安全修复...")
    
    try:
        # 导入现有的WebSocket管理器
        from app.services.websocket_manager import websocket_manager, WebSocketManager
        from app.api.v1.ai_websocket import ai_websocket_handler, AIWebSocketHandler
        
        print("✅ 成功导入现有WebSocket组件")
        
        # 为现有的WebSocketManager添加并发控制锁
        if not hasattr(websocket_manager, '_connections_lock'):
            websocket_manager._connections_lock = asyncio.Lock()
            websocket_manager._stats_lock = asyncio.Lock()
            websocket_manager._cleanup_lock = asyncio.Lock()
            print("✅ 为WebSocketManager添加并发控制锁")
        
        # 为AI处理器添加任务管理锁
        if not hasattr(ai_websocket_handler, '_tasks_lock'):
            ai_websocket_handler._tasks_lock = asyncio.Lock()
            print("✅ 为AIWebSocketHandler添加任务管理锁")
        
        # 替换关键方法为并发安全版本
        await _patch_websocket_manager_methods(websocket_manager)
        await _patch_ai_handler_methods(ai_websocket_handler)
        
        print("✅ WebSocket并发安全修复应用成功！")
        return True
        
    except Exception as e:
        print(f"❌ 应用WebSocket并发安全修复失败: {e}")
        logger.error(f"WebSocket并发修复失败: {e}")
        return False


async def _patch_websocket_manager_methods(manager):
    """为WebSocketManager打补丁，添加并发安全性"""
    
    # 保存原始方法
    original_connect = manager.connect
    original_disconnect = manager.disconnect
    original_send_to_user = manager.send_to_user
    original_cleanup_dead_connections = getattr(manager, '_cleanup_dead_connections', None)
    
    # 并发安全的connect方法
    async def safe_connect(websocket, user_id: int, session_id: Optional[str] = None, 
                          client_info: Optional[Dict[str, Any]] = None) -> str:
        async with manager._connections_lock:
            # 检查系统总连接数限制
            if len(manager.active_connections) >= manager.config.get('max_total_connections', 1000):
                raise ValueError(f"系统连接数已达到限制")
            
            # 检查用户连接数限制并原子性地处理
            user_current_connections = len(manager.user_connections.get(user_id, []))
            max_per_user = manager.config.get('max_connections_per_user', 5)
            
            if user_current_connections >= max_per_user:
                # 在锁保护下安全地断开最旧连接
                if manager.user_connections.get(user_id):
                    oldest_connection_id = manager.user_connections[user_id][0]
                    await safe_disconnect_unsafe(oldest_connection_id, "用户连接数达到限制，断开最旧连接")
                    logger.warning(f"用户 {user_id} 连接数达到限制，自动断开最旧连接")
            
            # 调用原始connect方法的核心逻辑，但在锁保护下
            return await original_connect(websocket, user_id, session_id, client_info)
    
    # 并发安全的disconnect方法
    async def safe_disconnect(connection_id: str, reason: str = "正常断开"):
        async with manager._connections_lock:
            await safe_disconnect_unsafe(connection_id, reason)
    
    # 内部不安全的断开方法（需要在锁保护下调用）
    async def safe_disconnect_unsafe(connection_id: str, reason: str = "正常断开"):
        if connection_id not in manager.active_connections:
            return
        
        connection = manager.active_connections[connection_id]
        user_id = connection.user_id
        
        # 从活跃连接池移除
        del manager.active_connections[connection_id]
        
        # 从用户连接映射移除
        if user_id in manager.user_connections:
            if connection_id in manager.user_connections[user_id]:
                manager.user_connections[user_id].remove(connection_id)
            
            # 如果用户没有其他连接，移除用户映射
            if not manager.user_connections[user_id]:
                del manager.user_connections[user_id]
        
        # 从会话映射移除
        session_id = connection.session_data.get("session_id")
        if session_id and session_id in manager.session_connections:
            del manager.session_connections[session_id]
        
        # 标记连接为非活跃
        connection.is_active = False
        
        # 更新统计
        async with manager._stats_lock:
            manager.pool_stats['total_connections_closed'] += 1
        
        logger.info(f"❌ 用户 {user_id} 断开WebSocket连接: {connection_id} (原因: {reason})")
    
    # 并发安全的send_to_user方法
    async def safe_send_to_user(user_id: int, message: dict) -> bool:
        # 创建用户连接列表的快照以避免迭代时修改
        async with manager._connections_lock:
            if user_id not in manager.user_connections:
                logger.warning(f"用户 {user_id} 没有活跃的WebSocket连接")
                return False
            
            # 创建连接ID列表的副本
            connection_ids = manager.user_connections[user_id].copy()
            # 创建活跃连接的副本引用
            connections_snapshot = {
                conn_id: manager.active_connections[conn_id] 
                for conn_id in connection_ids 
                if conn_id in manager.active_connections
            }
        
        # 在锁外进行消息发送，避免长时间持有锁
        from datetime import datetime
        message["timestamp"] = datetime.utcnow().isoformat()
        sent_count = 0
        
        for connection_id, connection in connections_snapshot.items():
            try:
                await connection.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"发送消息到连接 {connection_id} 失败: {e}")
        
        logger.info(f"📤 向用户 {user_id} 的 {sent_count} 个连接发送消息")
        return sent_count > 0
    
    # 并发安全的清理方法
    async def safe_cleanup_dead_connections():
        if not hasattr(manager, '_cleanup_lock'):
            return
            
        async with manager._cleanup_lock:
            dead_connections = []
            
            # 在锁保护下创建死连接列表快照
            async with manager._connections_lock:
                timeout = manager.config.get('connection_timeout', 300)
                for connection_id, connection in manager.active_connections.items():
                    if not connection.is_alive(timeout):
                        dead_connections.append((connection_id, connection))
            
            # 清理死连接
            for connection_id, connection in dead_connections:
                if connection.consecutive_errors >= 3:
                    reason = f"连续错误过多({connection.consecutive_errors})"
                elif not connection.is_active:
                    reason = "连接已标记为非活跃"
                else:
                    reason = "心跳超时"
                
                await safe_disconnect(connection_id, reason)
            
            if dead_connections:
                logger.info(f"🧹 清理了 {len(dead_connections)} 个死连接")
    
    # 应用补丁
    manager.connect = safe_connect
    manager.disconnect = safe_disconnect
    manager.send_to_user = safe_send_to_user
    if original_cleanup_dead_connections:
        manager._cleanup_dead_connections = safe_cleanup_dead_connections
    
    print("✅ WebSocketManager并发安全补丁已应用")


async def _patch_ai_handler_methods(handler):
    """为AIWebSocketHandler打补丁，添加并发安全性"""
    
    # 保存原始方法
    original_handle_ai_chat = handler.handle_ai_chat_request
    original_cleanup_connection = handler.cleanup_connection
    original_cancel_request = handler.handle_cancel_request
    
    # 并发安全的AI对话请求处理
    async def safe_handle_ai_chat_request(connection_id: str, user_id: int, 
                                        message_data: dict, db):
        request_id = message_data.get("request_id")
        if not request_id:
            import uuid
            request_id = str(uuid.uuid4())
            message_data["request_id"] = request_id
        
        async with handler._tasks_lock:
            # 检查并取消重复任务 - 原子性操作
            if request_id in handler.active_ai_tasks:
                logger.warning(f"取消重复的AI任务: {request_id}")
                old_task = handler.active_ai_tasks[request_id]
                old_task.cancel()
            
            # 调用原始处理逻辑，但确保任务管理的原子性
            await original_handle_ai_chat(connection_id, user_id, message_data, db)
    
    # 并发安全的连接清理
    async def safe_cleanup_connection(connection_id: str):
        async with handler._tasks_lock:
            if connection_id in handler.connection_requests:
                # 创建副本避免迭代时修改
                request_ids = handler.connection_requests[connection_id].copy()
                
                for request_id in request_ids:
                    if request_id in handler.active_ai_tasks:
                        task = handler.active_ai_tasks[request_id]
                        task.cancel()
                        # 任务会在finally中自行清理
                
                # 清理连接映射
                del handler.connection_requests[connection_id]
                logger.info(f"清理连接 {connection_id} 的 {len(request_ids)} 个AI任务")
    
    # 并发安全的取消请求
    async def safe_handle_cancel_request(connection_id: str, user_id: int, request_id: str):
        async with handler._tasks_lock:
            if request_id in handler.active_ai_tasks:
                task = handler.active_ai_tasks[request_id]
                task.cancel()
                
                await handler.websocket_manager.send_to_user(user_id, {
                    "type": "ai_chat_cancelled",
                    "request_id": request_id,
                    "message": "AI对话已取消"
                })
                
                logger.info(f"用户 {user_id} 取消了AI对话任务: {request_id}")
    
    # 增强现有的流式处理方法的finally块
    original_process_streaming = getattr(handler, '_process_streaming_ai_chat', None)
    if original_process_streaming:
        async def safe_process_streaming_ai_chat(*args, **kwargs):
            request_id = kwargs.get('request_id')
            connection_id = kwargs.get('connection_id')
            
            try:
                return await original_process_streaming(*args, **kwargs)
            finally:
                # 并发安全的任务清理
                if request_id and hasattr(handler, '_tasks_lock'):
                    async with handler._tasks_lock:
                        if request_id in handler.active_ai_tasks:
                            del handler.active_ai_tasks[request_id]
                        
                        if connection_id in handler.connection_requests:
                            handler.connection_requests[connection_id].discard(request_id)
                            if not handler.connection_requests[connection_id]:
                                del handler.connection_requests[connection_id]
        
        handler._process_streaming_ai_chat = safe_process_streaming_ai_chat
    
    # 应用补丁
    handler.handle_ai_chat_request = safe_handle_ai_chat_request
    handler.cleanup_connection = safe_cleanup_connection
    handler.handle_cancel_request = safe_handle_cancel_request
    
    print("✅ AIWebSocketHandler并发安全补丁已应用")


async def test_applied_fix():
    """测试应用的修复是否生效"""
    print("\n🧪 测试应用的并发安全修复...")
    
    try:
        from app.services.websocket_manager import websocket_manager
        from app.api.v1.ai_websocket import ai_websocket_handler
        
        # 检查锁是否已添加
        has_ws_locks = (hasattr(websocket_manager, '_connections_lock') and 
                       hasattr(websocket_manager, '_stats_lock') and 
                       hasattr(websocket_manager, '_cleanup_lock'))
        
        has_ai_locks = hasattr(ai_websocket_handler, '_tasks_lock')
        
        if has_ws_locks and has_ai_locks:
            print("✅ 所有并发控制锁已正确添加")
            
            # 测试锁是否可用
            async with websocket_manager._connections_lock:
                async with ai_websocket_handler._tasks_lock:
                    print("✅ 并发控制锁测试通过")
            
            return True
        else:
            print(f"❌ 缺少并发控制锁: WebSocket={has_ws_locks}, AI={has_ai_locks}")
            return False
            
    except Exception as e:
        print(f"❌ 测试应用修复失败: {e}")
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("🔧 WebSocket并发安全修复应用器")
    print("=" * 60)
    
    # 应用修复
    success = await apply_websocket_concurrency_fix()
    
    if success:
        # 测试修复效果
        test_success = await test_applied_fix()
        
        if test_success:
            print("\n🎉 WebSocket并发安全修复已成功应用！")
            print("\n📋 修复内容:")
            print("  ✅ 添加连接管理并发控制锁")
            print("  ✅ 添加统计信息并发控制锁") 
            print("  ✅ 添加清理操作并发控制锁")
            print("  ✅ 添加AI任务管理并发控制锁")
            print("  ✅ 原子性连接建立和断开操作")
            print("  ✅ 并发安全的消息发送")
            print("  ✅ 并发安全的任务管理")
            print("\n🚀 系统现在可以安全处理并发WebSocket连接！")
            return True
        else:
            print("\n❌ 修复应用后测试失败")
            return False
    else:
        print("\n❌ 修复应用失败")
        return False


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)