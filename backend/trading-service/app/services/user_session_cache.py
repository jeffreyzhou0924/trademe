"""
用户会话缓存服务
处理用户登录状态、权限缓存、API访问限制、用户偏好设置等
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from enum import Enum

from .redis_cache_service import RedisCacheService, CacheConfig, CompressionType

logger = logging.getLogger(__name__)

class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"

class UserRole(Enum):
    """用户角色"""
    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"

@dataclass
class UserSession:
    """用户会话数据"""
    user_id: int
    email: str
    role: str
    session_id: str
    jwt_token: str
    created_at: datetime
    last_active: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str
    status: SessionStatus = SessionStatus.ACTIVE
    permissions: List[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []

@dataclass
class APIRateLimit:
    """API限制配置"""
    user_id: int
    endpoint: str
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    current_minute_count: int = 0
    current_hour_count: int = 0
    current_day_count: int = 0
    reset_minute: datetime = None
    reset_hour: datetime = None
    reset_day: datetime = None
    
    def __post_init__(self):
        if self.reset_minute is None:
            self.reset_minute = datetime.utcnow().replace(second=0, microsecond=0) + timedelta(minutes=1)
        if self.reset_hour is None:
            self.reset_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if self.reset_day is None:
            self.reset_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

@dataclass
class UserPreferences:
    """用户偏好设置"""
    user_id: int
    language: str = "zh"
    timezone: str = "UTC+8"
    theme: str = "dark"
    default_symbols: List[str] = None
    notification_settings: Dict[str, bool] = None
    trading_preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.default_symbols is None:
            self.default_symbols = ["BTC/USDT", "ETH/USDT"]
        if self.notification_settings is None:
            self.notification_settings = {
                "email_notifications": True,
                "push_notifications": True,
                "price_alerts": True,
                "trade_confirmations": True
            }
        if self.trading_preferences is None:
            self.trading_preferences = {
                "default_order_type": "limit",
                "confirm_orders": True,
                "show_advanced_features": False
            }

class UserSessionCacheService:
    """用户会话缓存服务"""
    
    def __init__(self, cache_service: RedisCacheService):
        self.cache = cache_service
        self.default_session_ttl = 1800  # 30分钟
        self.extended_session_ttl = 86400  # 24小时
        
        # 设置缓存配置
        self._setup_cache_configs()
        
    def _setup_cache_configs(self):
        """设置缓存配置"""
        self.cache.cache_configs.update({
            "user_sessions": CacheConfig(
                ttl=self.default_session_ttl,
                namespace="session",
                compression=CompressionType.JSON
            ),
            "user_permissions": CacheConfig(
                ttl=3600,  # 权限缓存1小时
                namespace="permissions"
            ),
            "rate_limits": CacheConfig(
                ttl=86400,  # 限流配置24小时
                namespace="rate_limit"
            ),
            "user_preferences": CacheConfig(
                ttl=7200,  # 用户偏好2小时
                namespace="preferences"
            ),
            "jwt_blacklist": CacheConfig(
                ttl=86400,  # JWT黑名单24小时
                namespace="jwt_blacklist"
            ),
            "login_attempts": CacheConfig(
                ttl=900,  # 登录尝试15分钟
                namespace="login_attempts"
            ),
            "user_activity": CacheConfig(
                ttl=1800,  # 用户活动30分钟
                namespace="activity"
            )
        })
    
    async def create_session(self, user_id: int, email: str, role: str, 
                           jwt_token: str, ip_address: str, user_agent: str,
                           remember_me: bool = False) -> UserSession:
        """创建用户会话"""
        try:
            session_id = self._generate_session_id(user_id, ip_address)
            current_time = datetime.utcnow()
            
            # 根据remember_me设置过期时间
            expires_at = current_time + timedelta(
                seconds=self.extended_session_ttl if remember_me else self.default_session_ttl
            )
            
            session = UserSession(
                user_id=user_id,
                email=email,
                role=role,
                session_id=session_id,
                jwt_token=jwt_token,
                created_at=current_time,
                last_active=current_time,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                status=SessionStatus.ACTIVE,
                permissions=self._get_default_permissions(role)
            )
            
            # 缓存会话数据
            await self._cache_session(session)
            
            # 记录登录活动
            await self._record_login_activity(user_id, ip_address, success=True)
            
            logger.info(f"创建用户会话成功: user_id={user_id}, session_id={session_id}")
            return session
            
        except Exception as e:
            logger.error(f"创建用户会话失败: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """获取用户会话"""
        try:
            key = f"session:{session_id}"
            data = await self.cache.get(key, "user_sessions")
            
            if not data:
                return None
            
            # 转换时间字段
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            data['last_active'] = datetime.fromisoformat(data['last_active'])
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
            data['status'] = SessionStatus(data['status'])
            
            session = UserSession(**data)
            
            # 检查会话是否过期
            if datetime.utcnow() > session.expires_at:
                session.status = SessionStatus.EXPIRED
                await self._update_session_status(session_id, SessionStatus.EXPIRED)
                return None
            
            # 更新最后活动时间
            await self._update_last_active(session_id)
            
            return session
            
        except Exception as e:
            logger.error(f"获取用户会话失败: {e}")
            return None
    
    async def get_session_by_user_id(self, user_id: int) -> List[UserSession]:
        """获取用户的所有会话"""
        try:
            # 这里简化实现，实际应该维护用户ID到会话ID的映射
            key_pattern = f"user_sessions:{user_id}:*"
            # 由于Redis的keys操作性能问题，这里应该使用更好的数据结构
            # 比如维护用户活跃会话列表
            
            sessions = []
            # 实现获取用户所有会话的逻辑
            return sessions
            
        except Exception as e:
            logger.error(f"获取用户会话列表失败: {e}")
            return []
    
    async def update_session_activity(self, session_id: str, 
                                    activity_data: Dict[str, Any] = None) -> bool:
        """更新会话活动"""
        try:
            # 更新最后活动时间
            await self._update_last_active(session_id)
            
            # 记录活动数据
            if activity_data:
                activity_key = f"activity:{session_id}"
                current_time = datetime.utcnow()
                
                activity_record = {
                    'timestamp': current_time.isoformat(),
                    'data': activity_data
                }
                
                # 获取现有活动记录
                activities = await self.cache.get(activity_key, "user_activity") or []
                activities.append(activity_record)
                
                # 保持最近50条活动记录
                if len(activities) > 50:
                    activities = activities[-50:]
                
                await self.cache.set(activity_key, activities, "user_activity")
            
            return True
            
        except Exception as e:
            logger.error(f"更新会话活动失败: {e}")
            return False
    
    async def terminate_session(self, session_id: str, reason: str = "logout") -> bool:
        """终止会话"""
        try:
            # 获取会话信息
            session = await self.get_session(session_id)
            if not session:
                return True  # 会话不存在，认为已终止
            
            # 将JWT令牌加入黑名单
            await self._add_jwt_to_blacklist(session.jwt_token, reason)
            
            # 更新会话状态
            await self._update_session_status(session_id, SessionStatus.TERMINATED)
            
            # 删除会话缓存
            key = f"session:{session_id}"
            await self.cache.delete(key, "user_sessions")
            
            logger.info(f"终止会话成功: session_id={session_id}, reason={reason}")
            return True
            
        except Exception as e:
            logger.error(f"终止会话失败: {e}")
            return False
    
    async def check_rate_limit(self, user_id: int, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """检查API访问限制"""
        try:
            key = f"rate_limit:{user_id}:{endpoint}"
            limit_data = await self.cache.get(key, "rate_limits")
            
            current_time = datetime.utcnow()
            
            if not limit_data:
                # 创建新的限制记录
                rate_limit = APIRateLimit(user_id=user_id, endpoint=endpoint)
            else:
                # 转换时间字段
                for time_field in ['reset_minute', 'reset_hour', 'reset_day']:
                    if time_field in limit_data and limit_data[time_field]:
                        limit_data[time_field] = datetime.fromisoformat(limit_data[time_field])
                
                rate_limit = APIRateLimit(**limit_data)
            
            # 重置计数器
            if current_time >= rate_limit.reset_minute:
                rate_limit.current_minute_count = 0
                rate_limit.reset_minute = current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
                
            if current_time >= rate_limit.reset_hour:
                rate_limit.current_hour_count = 0
                rate_limit.reset_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                
            if current_time >= rate_limit.reset_day:
                rate_limit.current_day_count = 0
                rate_limit.reset_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            # 检查限制
            limits_exceeded = []
            
            if rate_limit.current_minute_count >= rate_limit.requests_per_minute:
                limits_exceeded.append("minute")
                
            if rate_limit.current_hour_count >= rate_limit.requests_per_hour:
                limits_exceeded.append("hour")
                
            if rate_limit.current_day_count >= rate_limit.requests_per_day:
                limits_exceeded.append("day")
            
            allowed = len(limits_exceeded) == 0
            
            if allowed:
                # 增加计数
                rate_limit.current_minute_count += 1
                rate_limit.current_hour_count += 1
                rate_limit.current_day_count += 1
                
                # 更新缓存
                await self._cache_rate_limit(rate_limit)
            
            limit_info = {
                "allowed": allowed,
                "limits_exceeded": limits_exceeded,
                "remaining_minute": rate_limit.requests_per_minute - rate_limit.current_minute_count,
                "remaining_hour": rate_limit.requests_per_hour - rate_limit.current_hour_count,
                "remaining_day": rate_limit.requests_per_day - rate_limit.current_day_count,
                "reset_times": {
                    "minute": rate_limit.reset_minute.isoformat(),
                    "hour": rate_limit.reset_hour.isoformat(),
                    "day": rate_limit.reset_day.isoformat()
                }
            }
            
            return allowed, limit_info
            
        except Exception as e:
            logger.error(f"检查API限制失败: {e}")
            # 出错时允许访问，但记录日志
            return True, {"error": str(e)}
    
    async def is_jwt_blacklisted(self, jwt_token: str) -> bool:
        """检查JWT是否在黑名单中"""
        try:
            token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()
            key = f"jwt_blacklist:{token_hash}"
            
            result = await self.cache.exists(key, "jwt_blacklist")
            return result
            
        except Exception as e:
            logger.error(f"检查JWT黑名单失败: {e}")
            return False
    
    async def cache_user_permissions(self, user_id: int, permissions: List[str]) -> bool:
        """缓存用户权限"""
        try:
            key = f"permissions:{user_id}"
            data = {
                'user_id': user_id,
                'permissions': permissions,
                'cached_at': datetime.utcnow().isoformat()
            }
            
            return await self.cache.set(key, data, "user_permissions")
            
        except Exception as e:
            logger.error(f"缓存用户权限失败: {e}")
            return False
    
    async def get_user_permissions(self, user_id: int) -> List[str]:
        """获取用户权限"""
        try:
            key = f"permissions:{user_id}"
            data = await self.cache.get(key, "user_permissions")
            
            if data and 'permissions' in data:
                return data['permissions']
                
            return []
            
        except Exception as e:
            logger.error(f"获取用户权限失败: {e}")
            return []
    
    async def cache_user_preferences(self, preferences: UserPreferences) -> bool:
        """缓存用户偏好"""
        try:
            key = f"preferences:{preferences.user_id}"
            data = asdict(preferences)
            
            return await self.cache.set(key, data, "user_preferences")
            
        except Exception as e:
            logger.error(f"缓存用户偏好失败: {e}")
            return False
    
    async def get_user_preferences(self, user_id: int) -> Optional[UserPreferences]:
        """获取用户偏好"""
        try:
            key = f"preferences:{user_id}"
            data = await self.cache.get(key, "user_preferences")
            
            if data:
                return UserPreferences(**data)
                
            return None
            
        except Exception as e:
            logger.error(f"获取用户偏好失败: {e}")
            return None
    
    def _generate_session_id(self, user_id: int, ip_address: str) -> str:
        """生成会话ID"""
        timestamp = datetime.utcnow().timestamp()
        data = f"{user_id}:{ip_address}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _get_default_permissions(self, role: str) -> List[str]:
        """获取默认权限"""
        permission_map = {
            "admin": [
                "admin.read", "admin.write", "admin.delete",
                "user.read", "user.write",
                "trading.read", "trading.write", "trading.execute",
                "ai.use", "ai.premium",
                "data.read", "data.write"
            ],
            "professional": [
                "user.read", "user.write",
                "trading.read", "trading.write", "trading.execute",
                "ai.use", "ai.premium",
                "data.read"
            ],
            "premium": [
                "user.read", "user.write",
                "trading.read", "trading.write",
                "ai.use",
                "data.read"
            ],
            "user": [
                "user.read", "user.write",
                "trading.read",
                "ai.use"
            ]
        }
        
        return permission_map.get(role, permission_map["user"])
    
    async def _cache_session(self, session: UserSession):
        """缓存会话数据"""
        key = f"session:{session.session_id}"
        data = asdict(session)
        
        # 转换时间字段为字符串
        data['created_at'] = session.created_at.isoformat()
        data['last_active'] = session.last_active.isoformat()
        data['expires_at'] = session.expires_at.isoformat()
        data['status'] = session.status.value
        
        await self.cache.set(key, data, "user_sessions")
        
        # 维护用户会话列表
        user_sessions_key = f"user_sessions:{session.user_id}"
        user_sessions = await self.cache.get(user_sessions_key, "user_sessions") or []
        
        if session.session_id not in user_sessions:
            user_sessions.append(session.session_id)
            # 限制用户同时会话数量
            if len(user_sessions) > 5:
                user_sessions = user_sessions[-5:]
                
            await self.cache.set(user_sessions_key, user_sessions, "user_sessions")
    
    async def _update_last_active(self, session_id: str):
        """更新最后活动时间"""
        session = await self.get_session(session_id)
        if session:
            session.last_active = datetime.utcnow()
            await self._cache_session(session)
    
    async def _update_session_status(self, session_id: str, status: SessionStatus):
        """更新会话状态"""
        session = await self.get_session(session_id)
        if session:
            session.status = status
            await self._cache_session(session)
    
    async def _add_jwt_to_blacklist(self, jwt_token: str, reason: str):
        """将JWT添加到黑名单"""
        token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()
        key = f"jwt_blacklist:{token_hash}"
        
        data = {
            'reason': reason,
            'blacklisted_at': datetime.utcnow().isoformat()
        }
        
        await self.cache.set(key, data, "jwt_blacklist")
    
    async def _cache_rate_limit(self, rate_limit: APIRateLimit):
        """缓存限流数据"""
        key = f"rate_limit:{rate_limit.user_id}:{rate_limit.endpoint}"
        data = asdict(rate_limit)
        
        # 转换时间字段
        data['reset_minute'] = rate_limit.reset_minute.isoformat()
        data['reset_hour'] = rate_limit.reset_hour.isoformat()
        data['reset_day'] = rate_limit.reset_day.isoformat()
        
        await self.cache.set(key, data, "rate_limits")
    
    async def _record_login_activity(self, user_id: int, ip_address: str, success: bool):
        """记录登录活动"""
        try:
            key = f"login_attempts:{ip_address}"
            attempts = await self.cache.get(key, "login_attempts") or []
            
            attempt = {
                'user_id': user_id,
                'ip_address': ip_address,
                'success': success,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            attempts.append(attempt)
            
            # 保留最近20次尝试
            if len(attempts) > 20:
                attempts = attempts[-20:]
            
            await self.cache.set(key, attempts, "login_attempts")
            
        except Exception as e:
            logger.error(f"记录登录活动失败: {e}")
    
    async def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            stats = {
                "cache_metrics": self.cache.get_metrics(),
                "session_types": [
                    "user_sessions",
                    "user_permissions", 
                    "rate_limits",
                    "user_preferences",
                    "jwt_blacklist",
                    "login_attempts",
                    "user_activity"
                ]
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取会话统计失败: {e}")
            return {}