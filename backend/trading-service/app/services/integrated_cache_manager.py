"""
集成缓存管理器
统一管理Redis缓存、市场数据缓存、用户会话缓存、AI对话缓存等
提供统一的缓存接口和监控功能
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from contextlib import asynccontextmanager

from .redis_cache_service import RedisCacheService
from .market_data_cache import MarketDataCacheService
from .user_session_cache import UserSessionCacheService
from .ai_conversation_cache import AIConversationCacheService

logger = logging.getLogger(__name__)

class IntegratedCacheManager:
    """集成缓存管理器"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_service: Optional[RedisCacheService] = None
        self.market_cache: Optional[MarketDataCacheService] = None
        self.session_cache: Optional[UserSessionCacheService] = None
        self.ai_cache: Optional[AIConversationCacheService] = None
        
        self.is_initialized = False
        self.health_status = {}
        
    async def initialize(self) -> bool:
        """初始化所有缓存服务"""
        try:
            # 初始化Redis服务
            self.redis_service = RedisCacheService(self.redis_url)
            await self.redis_service.connect()
            
            if not self.redis_service.is_connected:
                logger.error("Redis服务连接失败")
                return False
            
            # 初始化各专业缓存服务
            self.market_cache = MarketDataCacheService(self.redis_service)
            self.session_cache = UserSessionCacheService(self.redis_service)
            self.ai_cache = AIConversationCacheService(self.redis_service)
            
            self.is_initialized = True
            
            # 启动健康检查任务
            asyncio.create_task(self._health_check_task())
            
            # 启动清理任务
            asyncio.create_task(self._cleanup_task())
            
            logger.info("集成缓存管理器初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"集成缓存管理器初始化失败: {e}")
            self.is_initialized = False
            return False
    
    async def shutdown(self):
        """关闭所有缓存服务"""
        try:
            if self.redis_service:
                await self.redis_service.disconnect()
            
            self.is_initialized = False
            logger.info("集成缓存管理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭缓存服务失败: {e}")
    
    # ===========================================
    # 市场数据缓存接口
    # ===========================================
    
    async def cache_real_time_price(self, symbol: str, price_data: Dict[str, Any]) -> bool:
        """缓存实时价格"""
        if not self._check_initialized():
            return False
            
        try:
            from .market_data_cache import MarketDataPoint
            
            # 转换数据格式
            market_data = MarketDataPoint(
                symbol=symbol,
                price=price_data.get('price', 0.0),
                volume=price_data.get('volume', 0.0),
                timestamp=datetime.utcnow(),
                bid=price_data.get('bid'),
                ask=price_data.get('ask'),
                high_24h=price_data.get('high_24h'),
                low_24h=price_data.get('low_24h'),
                change_24h=price_data.get('change_24h')
            )
            
            return await self.market_cache.cache_real_time_price(symbol, market_data)
            
        except Exception as e:
            logger.error(f"缓存实时价格失败: {e}")
            return False
    
    async def get_real_time_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时价格"""
        if not self._check_initialized():
            return None
            
        try:
            price_data = await self.market_cache.get_real_time_price(symbol)
            if price_data:
                return {
                    'symbol': price_data.symbol,
                    'price': price_data.price,
                    'volume': price_data.volume,
                    'timestamp': price_data.timestamp.isoformat(),
                    'bid': price_data.bid,
                    'ask': price_data.ask,
                    'high_24h': price_data.high_24h,
                    'low_24h': price_data.low_24h,
                    'change_24h': price_data.change_24h
                }
            return None
            
        except Exception as e:
            logger.error(f"获取实时价格失败: {e}")
            return None
    
    async def cache_kline_data(self, symbol: str, interval: str, 
                              klines: List[Dict[str, Any]]) -> bool:
        """缓存K线数据"""
        if not self._check_initialized():
            return False
            
        try:
            from .market_data_cache import KlineData
            
            # 转换数据格式
            kline_objects = []
            for kline in klines:
                kline_obj = KlineData(
                    symbol=symbol,
                    open=kline.get('open', 0.0),
                    high=kline.get('high', 0.0),
                    low=kline.get('low', 0.0),
                    close=kline.get('close', 0.0),
                    volume=kline.get('volume', 0.0),
                    timestamp=datetime.fromisoformat(kline.get('timestamp')) if isinstance(kline.get('timestamp'), str) else kline.get('timestamp', datetime.utcnow()),
                    interval=interval
                )
                kline_objects.append(kline_obj)
            
            return await self.market_cache.cache_kline_data(symbol, interval, kline_objects)
            
        except Exception as e:
            logger.error(f"缓存K线数据失败: {e}")
            return False
    
    async def get_kline_data(self, symbol: str, interval: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取K线数据"""
        if not self._check_initialized():
            return []
            
        try:
            klines = await self.market_cache.get_kline_data(symbol, interval, limit)
            
            return [
                {
                    'symbol': k.symbol,
                    'open': k.open,
                    'high': k.high,
                    'low': k.low,
                    'close': k.close,
                    'volume': k.volume,
                    'timestamp': k.timestamp.isoformat(),
                    'interval': k.interval
                }
                for k in klines
            ]
            
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []
    
    # ===========================================
    # 用户会话缓存接口
    # ===========================================
    
    async def create_user_session(self, user_id: int, email: str, role: str,
                                jwt_token: str, ip_address: str, user_agent: str,
                                remember_me: bool = False) -> Optional[str]:
        """创建用户会话"""
        if not self._check_initialized():
            return None
            
        try:
            session = await self.session_cache.create_session(
                user_id, email, role, jwt_token, ip_address, user_agent, remember_me
            )
            return session.session_id
            
        except Exception as e:
            logger.error(f"创建用户会话失败: {e}")
            return None
    
    async def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取用户会话"""
        if not self._check_initialized():
            return None
            
        try:
            session = await self.session_cache.get_session(session_id)
            if session:
                return {
                    'user_id': session.user_id,
                    'email': session.email,
                    'role': session.role,
                    'session_id': session.session_id,
                    'created_at': session.created_at.isoformat(),
                    'last_active': session.last_active.isoformat(),
                    'expires_at': session.expires_at.isoformat(),
                    'ip_address': session.ip_address,
                    'user_agent': session.user_agent,
                    'status': session.status.value,
                    'permissions': session.permissions
                }
            return None
            
        except Exception as e:
            logger.error(f"获取用户会话失败: {e}")
            return None
    
    async def update_session_activity(self, session_id: str, activity_data: Dict[str, Any] = None) -> bool:
        """更新会话活动"""
        if not self._check_initialized():
            return False
            
        return await self.session_cache.update_session_activity(session_id, activity_data)
    
    async def terminate_user_session(self, session_id: str, reason: str = "logout") -> bool:
        """终止用户会话"""
        if not self._check_initialized():
            return False
            
        return await self.session_cache.terminate_session(session_id, reason)
    
    async def check_api_rate_limit(self, user_id: int, endpoint: str) -> Dict[str, Any]:
        """检查API访问限制"""
        if not self._check_initialized():
            return {"allowed": True, "error": "缓存服务未初始化"}
            
        try:
            allowed, limit_info = await self.session_cache.check_rate_limit(user_id, endpoint)
            return {"allowed": allowed, **limit_info}
            
        except Exception as e:
            logger.error(f"检查API限制失败: {e}")
            return {"allowed": True, "error": str(e)}
    
    async def is_jwt_blacklisted(self, jwt_token: str) -> bool:
        """检查JWT是否在黑名单"""
        if not self._check_initialized():
            return False
            
        return await self.session_cache.is_jwt_blacklisted(jwt_token)
    
    # ===========================================
    # AI对话缓存接口
    # ===========================================
    
    async def create_ai_conversation(self, user_id: int, session_type: str,
                                   initial_message: Optional[str] = None) -> Optional[str]:
        """创建AI对话"""
        if not self._check_initialized():
            return None
            
        try:
            from .ai_conversation_cache import SessionType
            
            session_type_enum = SessionType(session_type)
            context = await self.ai_cache.create_conversation(
                user_id, session_type_enum, initial_message
            )
            return context.session_id
            
        except Exception as e:
            logger.error(f"创建AI对话失败: {e}")
            return None
    
    async def add_ai_message(self, session_id: str, role: str, content: str,
                           metadata: Optional[Dict[str, Any]] = None,
                           token_count: Optional[int] = None) -> bool:
        """添加AI消息"""
        if not self._check_initialized():
            return False
            
        try:
            from .ai_conversation_cache import MessageRole
            
            role_enum = MessageRole(role)
            return await self.ai_cache.add_message_to_conversation(
                session_id, role_enum, content, metadata, token_count
            )
            
        except Exception as e:
            logger.error(f"添加AI消息失败: {e}")
            return False
    
    async def get_ai_context(self, session_id: str, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """获取AI上下文"""
        if not self._check_initialized():
            return []
            
        try:
            return await self.ai_cache.get_context_for_ai_request(session_id, max_messages)
            
        except Exception as e:
            logger.error(f"获取AI上下文失败: {e}")
            return []
    
    async def cache_ai_response(self, session_id: str, user_query: str, ai_response: str,
                              model_info: Dict[str, Any], token_usage: Dict[str, int]) -> bool:
        """缓存AI响应"""
        if not self._check_initialized():
            return False
            
        return await self.ai_cache.cache_ai_response(
            session_id, user_query, ai_response, model_info, token_usage
        )
    
    async def get_user_ai_sessions(self, user_id: int, session_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取用户AI会话列表"""
        if not self._check_initialized():
            return []
            
        try:
            from .ai_conversation_cache import SessionType
            
            session_type_enum = SessionType(session_type) if session_type else None
            return await self.ai_cache.get_user_ai_sessions(user_id, session_type_enum)
            
        except Exception as e:
            logger.error(f"获取用户AI会话列表失败: {e}")
            return []
    
    # ===========================================
    # 通用缓存接口
    # ===========================================
    
    async def get_cache_value(self, key: str, cache_type: str = "default") -> Optional[Any]:
        """获取缓存值"""
        if not self._check_initialized():
            return None
            
        return await self.redis_service.get(key, cache_type)
    
    async def set_cache_value(self, key: str, value: Any, cache_type: str = "default") -> bool:
        """设置缓存值"""
        if not self._check_initialized():
            return False
            
        return await self.redis_service.set(key, value, cache_type)
    
    async def delete_cache_value(self, key: str, cache_type: str = "default") -> bool:
        """删除缓存值"""
        if not self._check_initialized():
            return False
            
        return await self.redis_service.delete(key, cache_type)
    
    async def clear_cache_namespace(self, namespace: str) -> int:
        """清空命名空间缓存"""
        if not self._check_initialized():
            return 0
            
        return await self.redis_service.clear_namespace(namespace)
    
    # ===========================================
    # 监控和统计接口
    # ===========================================
    
    async def get_cache_health(self) -> Dict[str, Any]:
        """获取缓存健康状态"""
        if not self.is_initialized:
            return {"status": "not_initialized", "services": {}}
        
        health_info = {
            "status": "healthy" if self.redis_service.is_connected else "unhealthy",
            "services": {
                "redis": {
                    "connected": self.redis_service.is_connected,
                    "url": self.redis_url
                },
                "market_cache": {
                    "available": self.market_cache is not None
                },
                "session_cache": {
                    "available": self.session_cache is not None
                },
                "ai_cache": {
                    "available": self.ai_cache is not None
                }
            },
            "health_checks": self.health_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return health_info
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self._check_initialized():
            return {}
        
        try:
            stats = {
                "redis_info": await self.redis_service.get_cache_info(),
                "general_metrics": self.redis_service.get_metrics(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 添加专业缓存服务统计
            if self.market_cache:
                stats["market_cache"] = await self.market_cache.get_cache_statistics()
                
            if self.session_cache:
                stats["session_cache"] = await self.session_cache.get_session_statistics()
                
            if self.ai_cache:
                stats["ai_cache"] = await self.ai_cache.get_ai_cache_statistics()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        if not self._check_initialized():
            return {}
        
        try:
            redis_info = await self.redis_service.get_cache_info()
            
            memory_info = {
                "redis_memory": redis_info.get("redis_info", {}).get("used_memory_human", "N/A"),
                "local_memory_cache_size": redis_info.get("memory_cache_size", 0),
                "total_cache_configs": redis_info.get("cache_configs", 0),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return memory_info
            
        except Exception as e:
            logger.error(f"获取内存使用失败: {e}")
            return {"error": str(e)}
    
    # ===========================================
    # 私有方法
    # ===========================================
    
    def _check_initialized(self) -> bool:
        """检查是否已初始化"""
        if not self.is_initialized:
            logger.warning("缓存管理器尚未初始化")
            return False
        return True
    
    async def _health_check_task(self):
        """健康检查任务"""
        while self.is_initialized:
            try:
                # 检查Redis连接
                if self.redis_service:
                    self.health_status["redis"] = {
                        "connected": self.redis_service.is_connected,
                        "last_check": datetime.utcnow().isoformat()
                    }
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"健康检查任务出错: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_task(self):
        """定期清理任务"""
        while self.is_initialized:
            try:
                # 每小时执行一次清理
                await asyncio.sleep(3600)
                
                # 清理过期的市场数据
                if self.market_cache:
                    await self.market_cache.clear_expired_data()
                
                # 清理过期的AI对话（7天以上）
                if self.ai_cache:
                    await self.ai_cache.cleanup_expired_conversations(days=7)
                
                logger.info("定期清理任务完成")
                
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
                await asyncio.sleep(1800)  # 出错时30分钟后重试


# 全局缓存管理器实例
cache_manager = IntegratedCacheManager()

# 上下文管理器
@asynccontextmanager
async def get_cache_manager():
    """获取缓存管理器上下文"""
    if not cache_manager.is_initialized:
        await cache_manager.initialize()
    try:
        yield cache_manager
    finally:
        pass  # 保持连接，不关闭

# 初始化函数
async def initialize_cache_manager(redis_url: str = "redis://localhost:6379") -> IntegratedCacheManager:
    """初始化全局缓存管理器"""
    global cache_manager
    cache_manager = IntegratedCacheManager(redis_url)
    success = await cache_manager.initialize()
    
    if success:
        logger.info("全局缓存管理器初始化成功")
    else:
        logger.error("全局缓存管理器初始化失败")
    
    return cache_manager

# 装饰器函数
def cache_result(cache_type: str = "default", ttl: int = 300, key_func: Optional[callable] = None):
    """结果缓存装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 尝试从缓存获取
            cached_result = await cache_manager.get_cache_value(cache_key, cache_type)
            if cached_result is not None:
                return cached_result
            
            # 调用原函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            if result is not None:
                await cache_manager.set_cache_value(cache_key, result, cache_type)
            
            return result
        
        return wrapper
    return decorator