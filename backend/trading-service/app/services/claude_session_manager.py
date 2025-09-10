"""
Claude会话窗口管理器 - 企业级持久化会话管理

基于参考项目的会话窗口概念，实现持久化存储、Redis缓存、智能窗口策略
提供跨服务的会话状态同步和高性能的会话管理功能
"""

import asyncio
import json
import logging
import redis.asyncio as aioredis
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.claude_proxy import ClaudeAccount, ClaudeUsageLog
from app.config import settings

logger = logging.getLogger(__name__)


class SessionWindow:
    """
    会话窗口数据模型
    """
    def __init__(
        self,
        account_id: int,
        window_id: str,
        start_time: datetime,
        end_time: datetime,
        total_limit: float,
        current_usage: float = 0.0,
        request_count: int = 0,
        window_type: str = "standard"
    ):
        self.account_id = account_id
        self.window_id = window_id
        self.start_time = start_time
        self.end_time = end_time
        self.total_limit = total_limit
        self.current_usage = current_usage
        self.request_count = request_count
        self.window_type = window_type  # standard, priority, burst
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "account_id": self.account_id,
            "window_id": self.window_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_limit": self.total_limit,
            "current_usage": self.current_usage,
            "request_count": self.request_count,
            "window_type": self.window_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "usage_percentage": (self.current_usage / self.total_limit * 100) if self.total_limit > 0 else 0,
            "remaining_minutes": max(0, int((self.end_time - datetime.utcnow()).total_seconds() / 60)),
            "is_expired": datetime.utcnow() >= self.end_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionWindow':
        """从字典创建实例"""
        # 安全地解析日期时间
        start_time_value = data["start_time"]
        if isinstance(start_time_value, str):
            try:
                start_time = datetime.fromisoformat(start_time_value)
            except (ValueError, TypeError):
                start_time = datetime.utcnow()
        elif isinstance(start_time_value, datetime):
            start_time = start_time_value
        else:
            start_time = datetime.utcnow()
            
        end_time_value = data["end_time"]
        if isinstance(end_time_value, str):
            try:
                end_time = datetime.fromisoformat(end_time_value)
            except (ValueError, TypeError):
                end_time = datetime.utcnow() + timedelta(hours=24)
        elif isinstance(end_time_value, datetime):
            end_time = end_time_value
        else:
            end_time = datetime.utcnow() + timedelta(hours=24)
            
        window = cls(
            account_id=data["account_id"],
            window_id=data["window_id"],
            start_time=start_time,
            end_time=end_time,
            total_limit=data["total_limit"],
            current_usage=data.get("current_usage", 0.0),
            request_count=data.get("request_count", 0),
            window_type=data.get("window_type", "standard")
        )
        # 安全地解析创建和更新时间
        created_at_value = data["created_at"]
        if isinstance(created_at_value, str):
            try:
                window.created_at = datetime.fromisoformat(created_at_value)
            except (ValueError, TypeError):
                window.created_at = datetime.utcnow()
        elif isinstance(created_at_value, datetime):
            window.created_at = created_at_value
        else:
            window.created_at = datetime.utcnow()
            
        updated_at_value = data.get("updated_at", data["created_at"])
        if isinstance(updated_at_value, str):
            try:
                window.updated_at = datetime.fromisoformat(updated_at_value)
            except (ValueError, TypeError):
                window.updated_at = window.created_at
        elif isinstance(updated_at_value, datetime):
            window.updated_at = updated_at_value
        else:
            window.updated_at = window.created_at
        return window


class ClaudeSessionManager:
    """
    Claude会话窗口管理器
    
    功能特性：
    1. 持久化会话存储（Redis + 数据库备份）
    2. 智能窗口策略（基于账号类型和使用模式）
    3. 跨服务会话同步
    4. 自动清理和优化
    5. 实时监控和统计
    """
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.redis_prefix = "claude:session:"
        
        # 窗口策略配置
        self.window_strategies = {
            "standard": {
                "duration_hours": 5,  # 标准5小时窗口
                "max_concurrent": 3,  # 最大并发窗口数
                "usage_limit_ratio": 0.2  # 每日限额的20%
            },
            "priority": {
                "duration_hours": 3,  # 优先级窗口更短但限额更高
                "max_concurrent": 2,
                "usage_limit_ratio": 0.4  # 每日限额的40%
            },
            "burst": {
                "duration_hours": 1,  # 爆发窗口短时间高限额
                "max_concurrent": 1,
                "usage_limit_ratio": 0.6  # 每日限额的60%
            }
        }
        
        # 内存缓存（作为Redis的fallback）
        self._memory_cache: Dict[str, SessionWindow] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """初始化Redis连接和清理任务"""
        try:
            # 初始化Redis连接
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379')
            self.redis_client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                encoding='utf-8'
            )
            
            # 测试连接
            await self.redis_client.ping()
            logger.info("✅ Redis connection established for session management")
            
            # 启动清理任务
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed, using memory cache only: {e}")
            self.redis_client = None
    
    async def close(self):
        """关闭连接和清理资源"""
        try:
            # 停止清理任务
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭Redis连接
            if self.redis_client:
                await self.redis_client.close()
                logger.info("✅ Redis connection closed")
            
            # 清理内存缓存
            self._memory_cache.clear()
            
        except Exception as e:
            logger.error(f"❌ Error closing session manager: {e}")
    
    async def create_session_window(
        self,
        account_id: int,
        window_type: str = "standard",
        custom_duration_hours: Optional[int] = None,
        custom_limit_ratio: Optional[float] = None
    ) -> Optional[SessionWindow]:
        """
        创建新的会话窗口
        
        Args:
            account_id: 账号ID
            window_type: 窗口类型 (standard, priority, burst)
            custom_duration_hours: 自定义持续时间
            custom_limit_ratio: 自定义限额比例
        """
        try:
            async with AsyncSessionLocal() as session:
                # 获取账号信息
                result = await session.execute(
                    select(ClaudeAccount).where(ClaudeAccount.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    logger.error(f"Account {account_id} not found")
                    return None
                
                # 检查现有窗口数量
                active_windows = await self.get_active_windows(account_id)
                strategy = self.window_strategies.get(window_type, self.window_strategies["standard"])
                
                if len(active_windows) >= strategy["max_concurrent"]:
                    logger.warning(f"Account {account_id} has reached max concurrent windows ({strategy['max_concurrent']})")
                    return None
                
                # 计算窗口参数
                now = datetime.utcnow()
                duration_hours = custom_duration_hours or strategy["duration_hours"]
                end_time = now + timedelta(hours=duration_hours)
                
                limit_ratio = custom_limit_ratio or strategy["usage_limit_ratio"]
                window_limit = float(account.daily_limit) * limit_ratio
                
                # 生成窗口ID
                window_id = f"{account_id}_{window_type}_{int(now.timestamp())}"
                
                # 创建窗口对象
                window = SessionWindow(
                    account_id=account_id,
                    window_id=window_id,
                    start_time=now,
                    end_time=end_time,
                    total_limit=window_limit,
                    window_type=window_type
                )
                
                # 存储到Redis和内存缓存
                await self._store_window(window)
                
                logger.info(
                    f"🕐 Created {window_type} session window for account {account_id}: "
                    f"{window_id}, limit: ${window_limit:.2f}, duration: {duration_hours}h"
                )
                
                return window
                
        except Exception as e:
            logger.error(f"❌ Failed to create session window for account {account_id}: {e}")
            return None
    
    async def get_session_window(
        self,
        account_id: int,
        window_id: Optional[str] = None,
        auto_create: bool = True
    ) -> Optional[SessionWindow]:
        """
        获取会话窗口（优先获取活跃窗口）
        """
        try:
            # 如果指定了window_id，直接获取
            if window_id:
                return await self._get_window_by_id(window_id)
            
            # 获取账号的活跃窗口
            active_windows = await self.get_active_windows(account_id)
            
            if active_windows:
                # 返回使用率最低的窗口（负载均衡）
                return min(active_windows, key=lambda w: w.current_usage / w.total_limit)
            
            # 如果没有活跃窗口且允许自动创建
            if auto_create:
                return await self.create_session_window(account_id, "standard")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get session window for account {account_id}: {e}")
            return None
    
    async def get_active_windows(self, account_id: int) -> List[SessionWindow]:
        """获取账号的所有活跃窗口"""
        try:
            active_windows = []
            
            # 从Redis获取
            if self.redis_client:
                pattern = f"{self.redis_prefix}{account_id}_*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    window_data = await self.redis_client.get(key)
                    if window_data:
                        try:
                            window = SessionWindow.from_dict(json.loads(window_data))
                            if not window.to_dict()["is_expired"]:
                                active_windows.append(window)
                        except Exception as parse_error:
                            logger.warning(f"Failed to parse window data: {parse_error}")
            
            # 从内存缓存获取（fallback）
            for window in self._memory_cache.values():
                if window.account_id == account_id and not window.to_dict()["is_expired"]:
                    active_windows.append(window)
            
            return active_windows
            
        except Exception as e:
            logger.error(f"❌ Failed to get active windows for account {account_id}: {e}")
            return []
    
    async def update_session_usage(
        self,
        window_id: str,
        cost_increment: float,
        request_increment: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        更新会话窗口使用量
        
        Returns:
            (success, window_info)
        """
        try:
            window = await self._get_window_by_id(window_id)
            if not window:
                return False, {"error": "Window not found"}
            
            # 检查窗口是否过期
            if window.to_dict()["is_expired"]:
                return False, {"error": "Window expired", "window_id": window_id}
            
            # 更新使用量
            window.current_usage += cost_increment
            window.request_count += request_increment
            window.updated_at = datetime.utcnow()
            
            # 检查是否超过限额
            usage_percentage = (window.current_usage / window.total_limit) * 100
            is_over_limit = window.current_usage >= window.total_limit
            
            # 存储更新
            await self._store_window(window)
            
            result = {
                "success": True,
                "window_id": window_id,
                "usage_percentage": usage_percentage,
                "is_over_limit": is_over_limit,
                "remaining_limit": window.total_limit - window.current_usage,
                **window.to_dict()
            }
            
            if is_over_limit:
                logger.warning(f"🚨 Session window {window_id} exceeded limit: {usage_percentage:.1f}%")
            
            return not is_over_limit, result
            
        except Exception as e:
            logger.error(f"❌ Failed to update session usage for window {window_id}: {e}")
            return False, {"error": str(e)}
    
    async def close_session_window(self, window_id: str, reason: str = "manual") -> bool:
        """关闭会话窗口"""
        try:
            # 从Redis删除
            if self.redis_client:
                redis_key = f"{self.redis_prefix}{window_id}"
                await self.redis_client.delete(redis_key)
            
            # 从内存缓存删除
            if window_id in self._memory_cache:
                del self._memory_cache[window_id]
            
            logger.info(f"✅ Closed session window {window_id}, reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to close session window {window_id}: {e}")
            return False
    
    async def get_session_statistics(
        self,
        account_id: Optional[int] = None,
        window_type: Optional[str] = None,
        time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_windows": 0,
                "active_windows": 0,
                "expired_windows": 0,
                "by_type": {},
                "by_account": {},
                "total_usage": 0.0,
                "total_requests": 0
            }
            
            # 收集所有窗口数据
            all_windows = []
            
            # 从Redis收集
            if self.redis_client:
                pattern = f"{self.redis_prefix}*"
                if account_id:
                    pattern = f"{self.redis_prefix}{account_id}_*"
                
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    window_data = await self.redis_client.get(key)
                    if window_data:
                        try:
                            window = SessionWindow.from_dict(json.loads(window_data))
                            all_windows.append(window)
                        except Exception:
                            continue
            
            # 从内存缓存收集
            for window in self._memory_cache.values():
                if not account_id or window.account_id == account_id:
                    all_windows.append(window)
            
            # 统计分析
            now = datetime.utcnow()
            time_cutoff = now - timedelta(hours=time_range_hours)
            
            for window in all_windows:
                if window.created_at < time_cutoff:
                    continue
                
                if window_type and window.window_type != window_type:
                    continue
                
                stats["total_windows"] += 1
                
                window_info = window.to_dict()
                if not window_info["is_expired"]:
                    stats["active_windows"] += 1
                else:
                    stats["expired_windows"] += 1
                
                # 按类型统计
                w_type = window.window_type
                if w_type not in stats["by_type"]:
                    stats["by_type"][w_type] = {
                        "count": 0, "total_usage": 0.0, "total_requests": 0
                    }
                stats["by_type"][w_type]["count"] += 1
                stats["by_type"][w_type]["total_usage"] += window.current_usage
                stats["by_type"][w_type]["total_requests"] += window.request_count
                
                # 按账号统计
                acc_id = str(window.account_id)
                if acc_id not in stats["by_account"]:
                    stats["by_account"][acc_id] = {
                        "count": 0, "total_usage": 0.0, "total_requests": 0
                    }
                stats["by_account"][acc_id]["count"] += 1
                stats["by_account"][acc_id]["total_usage"] += window.current_usage
                stats["by_account"][acc_id]["total_requests"] += window.request_count
                
                # 总计
                stats["total_usage"] += window.current_usage
                stats["total_requests"] += window.request_count
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get session statistics: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def cleanup_expired_windows(self) -> Dict[str, int]:
        """清理过期的会话窗口"""
        try:
            cleanup_stats = {
                "redis_cleaned": 0,
                "memory_cleaned": 0,
                "total_cleaned": 0
            }
            
            now = datetime.utcnow()
            
            # 清理Redis中的过期窗口
            if self.redis_client:
                pattern = f"{self.redis_prefix}*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    window_data = await self.redis_client.get(key)
                    if window_data:
                        try:
                            window = SessionWindow.from_dict(json.loads(window_data))
                            if window.end_time <= now:
                                await self.redis_client.delete(key)
                                cleanup_stats["redis_cleaned"] += 1
                        except Exception:
                            # 删除无法解析的数据
                            await self.redis_client.delete(key)
                            cleanup_stats["redis_cleaned"] += 1
            
            # 清理内存缓存中的过期窗口
            expired_keys = []
            for window_id, window in self._memory_cache.items():
                if window.end_time <= now:
                    expired_keys.append(window_id)
            
            for key in expired_keys:
                del self._memory_cache[key]
                cleanup_stats["memory_cleaned"] += 1
            
            cleanup_stats["total_cleaned"] = cleanup_stats["redis_cleaned"] + cleanup_stats["memory_cleaned"]
            
            if cleanup_stats["total_cleaned"] > 0:
                logger.info(f"🧹 Cleaned up {cleanup_stats['total_cleaned']} expired session windows")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup expired windows: {e}")
            return {"error": str(e)}
    
    async def _store_window(self, window: SessionWindow):
        """存储窗口到Redis和内存缓存"""
        window_data = json.dumps(window.to_dict(), ensure_ascii=False)
        
        # 存储到Redis
        if self.redis_client:
            redis_key = f"{self.redis_prefix}{window.window_id}"
            # 设置过期时间为窗口结束时间 + 1小时缓冲
            expire_seconds = int((window.end_time - datetime.utcnow()).total_seconds()) + 3600
            await self.redis_client.setex(redis_key, expire_seconds, window_data)
        
        # 存储到内存缓存
        self._memory_cache[window.window_id] = window
    
    async def _get_window_by_id(self, window_id: str) -> Optional[SessionWindow]:
        """根据ID获取窗口"""
        # 优先从Redis获取
        if self.redis_client:
            redis_key = f"{self.redis_prefix}{window_id}"
            window_data = await self.redis_client.get(redis_key)
            if window_data:
                try:
                    return SessionWindow.from_dict(json.loads(window_data))
                except Exception as e:
                    logger.warning(f"Failed to parse window from Redis: {e}")
        
        # 从内存缓存获取
        return self._memory_cache.get(window_id)
    
    async def _cleanup_loop(self):
        """定期清理任务循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                await self.cleanup_expired_windows()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟后重试


# 全局会话管理器实例
session_manager = ClaudeSessionManager()


# 便捷函数
async def get_or_create_session_window(account_id: int, window_type: str = "standard") -> Optional[SessionWindow]:
    """获取或创建会话窗口"""
    return await session_manager.get_session_window(account_id, auto_create=True)


async def update_session_usage(window_id: str, cost: float) -> Tuple[bool, Dict[str, Any]]:
    """更新会话使用量"""
    return await session_manager.update_session_usage(window_id, cost)


async def close_session_window(window_id: str, reason: str = "manual") -> bool:
    """关闭会话窗口"""
    return await session_manager.close_session_window(window_id, reason)