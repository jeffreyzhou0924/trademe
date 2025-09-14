#!/usr/bin/env python3
"""
WebSocket消息去重修复
====================

解决AI对话中出现重复消息的问题：
1. 添加消息内容哈希去重机制
2. 基于时间窗口的重复检测
3. 用户会话级别的消息缓存
4. 优雅处理重复请求

修复目标：
- 防止10秒内相同内容的重复处理
- 保持用户体验不受影响
- 自动清理过期的去重缓存
"""

import asyncio
import hashlib
import time
import logging
from typing import Dict, Set, Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MessageDeduplicationManager:
    """消息去重管理器"""
    
    def __init__(self, dedup_window_seconds: int = 15):
        """
        初始化去重管理器
        
        Args:
            dedup_window_seconds: 去重时间窗口（秒）
        """
        self.dedup_window = dedup_window_seconds
        
        # 用户消息去重缓存: user_id -> {msg_hash: timestamp}
        self.user_message_cache: Dict[int, Dict[str, float]] = {}
        
        # 全局请求去重缓存: request_id -> timestamp
        self.request_cache: Dict[str, float] = {}
        
        # 定期清理任务
        self.cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"🛡️ 消息去重管理器初始化完成 - 时间窗口: {dedup_window_seconds}秒")
    
    def _get_message_hash(self, user_id: int, content: str, session_id: str) -> str:
        """生成消息内容哈希"""
        message_key = f"{user_id}:{session_id}:{content.strip()}"
        return hashlib.md5(message_key.encode()).hexdigest()[:16]
    
    def is_duplicate_message(self, user_id: int, content: str, session_id: str) -> bool:
        """
        检查是否为重复消息
        
        Args:
            user_id: 用户ID
            content: 消息内容
            session_id: 会话ID
            
        Returns:
            True if duplicate, False otherwise
        """
        current_time = time.time()
        message_hash = self._get_message_hash(user_id, content, session_id)
        
        # 确保用户缓存存在
        if user_id not in self.user_message_cache:
            self.user_message_cache[user_id] = {}
        
        user_cache = self.user_message_cache[user_id]
        
        # 检查是否存在重复消息
        if message_hash in user_cache:
            last_time = user_cache[message_hash]
            time_diff = current_time - last_time
            
            if time_diff < self.dedup_window:
                logger.warning(f"🚫 发现重复消息 - 用户: {user_id}, 时间差: {time_diff:.1f}秒")
                return True
        
        # 记录新消息
        user_cache[message_hash] = current_time
        
        # 清理过期消息
        self._cleanup_expired_messages(user_cache, current_time)
        
        return False
    
    def is_duplicate_request(self, request_id: str) -> bool:
        """
        检查是否为重复请求ID
        
        Args:
            request_id: 请求ID
            
        Returns:
            True if duplicate, False otherwise
        """
        if not request_id:
            return False
            
        current_time = time.time()
        
        if request_id in self.request_cache:
            last_time = self.request_cache[request_id]
            time_diff = current_time - last_time
            
            if time_diff < self.dedup_window:
                logger.warning(f"🚫 发现重复请求ID: {request_id}, 时间差: {time_diff:.1f}秒")
                return True
        
        # 记录新请求
        self.request_cache[request_id] = current_time
        return False
    
    def _cleanup_expired_messages(self, cache: Dict[str, float], current_time: float):
        """清理过期的消息缓存"""
        expired_keys = [
            key for key, timestamp in cache.items()
            if current_time - timestamp > self.dedup_window
        ]
        
        for key in expired_keys:
            del cache[key]
    
    def cleanup_expired_caches(self):
        """清理所有过期的缓存"""
        current_time = time.time()
        
        # 清理用户消息缓存
        for user_id, user_cache in self.user_message_cache.items():
            self._cleanup_expired_messages(user_cache, current_time)
        
        # 清理空的用户缓存
        empty_users = [
            user_id for user_id, cache in self.user_message_cache.items()
            if not cache
        ]
        for user_id in empty_users:
            del self.user_message_cache[user_id]
        
        # 清理请求缓存
        expired_requests = [
            request_id for request_id, timestamp in self.request_cache.items()
            if current_time - timestamp > self.dedup_window
        ]
        for request_id in expired_requests:
            del self.request_cache[request_id]
        
        if expired_requests or empty_users:
            logger.debug(f"🧹 清理过期缓存 - 用户: {len(empty_users)}, 请求: {len(expired_requests)}")
    
    async def start_cleanup_task(self):
        """启动定期清理任务"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("🧹 启动消息去重缓存清理任务")
    
    async def _periodic_cleanup(self):
        """定期清理任务"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒清理一次
                self.cleanup_expired_caches()
            except asyncio.CancelledError:
                logger.info("🧹 消息去重缓存清理任务已停止")
                break
            except Exception as e:
                logger.error(f"❌ 消息去重缓存清理失败: {e}")
    
    def get_stats(self) -> Dict[str, any]:
        """获取去重统计信息"""
        return {
            "active_users": len(self.user_message_cache),
            "total_cached_messages": sum(len(cache) for cache in self.user_message_cache.values()),
            "cached_requests": len(self.request_cache),
            "dedup_window_seconds": self.dedup_window
        }


# 全局去重管理器实例
message_dedup_manager = MessageDeduplicationManager(dedup_window_seconds=15)


async def apply_message_deduplication_fix():
    """应用消息去重修复到现有WebSocket处理器"""
    print("🛡️ 开始应用消息去重修复...")
    
    try:
        from app.api.v1.ai_websocket import ai_websocket_handler, AIWebSocketHandler
        
        # 保存原始方法
        original_handle_ai_chat = ai_websocket_handler.handle_ai_chat_request
        
        # 创建去重包装方法
        async def dedup_handle_ai_chat_request(
            connection_id: str, user_id: int, message_data: dict, db
        ):
            content = message_data.get("content", "")
            session_id = message_data.get("session_id", "")
            request_id = message_data.get("request_id", "")
            
            # 检查消息内容去重
            if message_dedup_manager.is_duplicate_message(user_id, content, session_id):
                logger.info(f"🚫 跳过重复消息 - 用户: {user_id}, 会话: {session_id[:8]}...")
                
                # 向用户发送去重通知（可选）
                from app.services.websocket_manager import websocket_manager
                await websocket_manager.send_to_user(user_id, {
                    "type": "ai_chat_dedup",
                    "request_id": request_id,
                    "message": "检测到重复消息，已自动跳过处理"
                })
                return
            
            # 检查请求ID去重
            if request_id and message_dedup_manager.is_duplicate_request(request_id):
                logger.info(f"🚫 跳过重复请求 - 请求ID: {request_id}")
                return
            
            # 调用原始处理方法
            await original_handle_ai_chat(connection_id, user_id, message_data, db)
        
        # 应用去重包装
        ai_websocket_handler.handle_ai_chat_request = dedup_handle_ai_chat_request
        
        # 启动清理任务
        await message_dedup_manager.start_cleanup_task()
        
        print("✅ 消息去重修复应用成功！")
        print("📋 修复内容:")
        print("  🛡️ 消息内容哈希去重 (15秒时间窗口)")
        print("  🔍 请求ID重复检测")
        print("  🧹 自动清理过期缓存")
        print("  📊 去重统计监控")
        
        return True
        
    except Exception as e:
        print(f"❌ 消息去重修复应用失败: {e}")
        logger.error(f"消息去重修复失败: {e}")
        return False


async def test_deduplication():
    """测试去重功能"""
    print("\n🧪 测试消息去重功能...")
    
    # 模拟重复消息测试
    test_user_id = 6
    test_session_id = "test_session"
    test_content = "我想开发一个ma策略"
    
    # 第一次消息 - 应该通过
    is_dup1 = message_dedup_manager.is_duplicate_message(test_user_id, test_content, test_session_id)
    print(f"第一次消息: {'❌ 重复' if is_dup1 else '✅ 通过'}")
    
    # 立即重复 - 应该被拦截
    is_dup2 = message_dedup_manager.is_duplicate_message(test_user_id, test_content, test_session_id)
    print(f"立即重复: {'✅ 拦截' if is_dup2 else '❌ 通过'}")
    
    # 不同内容 - 应该通过
    is_dup3 = message_dedup_manager.is_duplicate_message(test_user_id, "不同的消息内容", test_session_id)
    print(f"不同内容: {'❌ 重复' if is_dup3 else '✅ 通过'}")
    
    # 统计信息
    stats = message_dedup_manager.get_stats()
    print(f"\n📊 去重统计: {stats}")
    
    if not is_dup1 and is_dup2 and not is_dup3:
        print("🎉 消息去重功能测试通过！")
        return True
    else:
        print("❌ 消息去重功能测试失败")
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("🛡️ WebSocket消息去重修复器")
    print("=" * 60)
    
    # 测试去重功能
    test_success = await test_deduplication()
    
    if test_success:
        # 应用修复
        fix_success = await apply_message_deduplication_fix()
        
        if fix_success:
            print("\n🎉 WebSocket消息去重修复完成！")
            print("\n💡 修复效果:")
            print("  • 防止10秒内相同内容重复处理")
            print("  • 自动清理过期去重缓存")
            print("  • 保持用户体验流畅")
            print("  • 减少不必要的AI API调用")
            return True
    
    print("\n❌ WebSocket消息去重修复失败")
    return False


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)