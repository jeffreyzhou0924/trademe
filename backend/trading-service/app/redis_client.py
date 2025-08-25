"""
Trademe Trading Service - Redis客户端

用于缓存、会话存储、实时数据缓存等
"""

import redis.asyncio as redis
import json
import pickle
from typing import Any, Optional, Union, Dict
from datetime import timedelta
import asyncio

from app.config import settings


class RedisClient:
    """Redis异步客户端封装"""
    
    def __init__(self):
        self.redis_pool = None
        self.redis_client = None
    
    async def connect(self):
        """连接到Redis"""
        try:
            # 创建连接池
            self.redis_pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                password=settings.redis_password if settings.redis_password else None,
                db=settings.redis_db,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            
            # 创建客户端
            self.redis_client = redis.Redis(connection_pool=self.redis_pool)
            
            # 测试连接
            await self.redis_client.ping()
            print("✅ Redis连接成功")
            return True
            
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            raise
    
    async def close(self):
        """关闭Redis连接"""
        try:
            if self.redis_client:
                await self.redis_client.aclose()
            if self.redis_pool:
                await self.redis_pool.aclose()
            print("✅ Redis连接已关闭")
        except Exception as e:
            print(f"❌ 关闭Redis连接失败: {e}")
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None,
        serialize: bool = True
    ) -> bool:
        """设置缓存"""
        try:
            if serialize:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                elif not isinstance(value, str):
                    value = pickle.dumps(value)
            
            result = await self.redis_client.set(key, value, ex=ttl)
            return result
        except Exception as e:
            print(f"Redis设置失败 {key}: {e}")
            return False
    
    async def get(
        self, 
        key: str, 
        deserialize: bool = True
    ) -> Optional[Any]:
        """获取缓存"""
        try:
            value = await self.redis_client.get(key)
            if value is None:
                return None
            
            if deserialize:
                try:
                    # 尝试JSON反序列化
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    try:
                        # 尝试pickle反序列化
                        return pickle.loads(value)
                    except:
                        # 返回原始字符串
                        return value
            return value
            
        except Exception as e:
            print(f"Redis获取失败 {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            print(f"Redis删除失败 {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            result = await self.redis_client.exists(key)
            return result > 0
        except Exception as e:
            print(f"Redis检查存在失败 {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """设置过期时间"""
        try:
            result = await self.redis_client.expire(key, ttl)
            return result
        except Exception as e:
            print(f"Redis设置过期失败 {key}: {e}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """递增计数器"""
        try:
            result = await self.redis_client.incrby(key, amount)
            return result
        except Exception as e:
            print(f"Redis递增失败 {key}: {e}")
            return None
    
    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """递减计数器"""
        try:
            result = await self.redis_client.decrby(key, amount)
            return result
        except Exception as e:
            print(f"Redis递减失败 {key}: {e}")
            return None
    
    async def hset(self, name: str, mapping: Dict[str, Any]) -> bool:
        """设置哈希表"""
        try:
            result = await self.redis_client.hset(name, mapping=mapping)
            return result > 0
        except Exception as e:
            print(f"Redis哈希设置失败 {name}: {e}")
            return False
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """获取哈希表字段"""
        try:
            result = await self.redis_client.hget(name, key)
            return result
        except Exception as e:
            print(f"Redis哈希获取失败 {name}.{key}: {e}")
            return None
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """获取整个哈希表"""
        try:
            result = await self.redis_client.hgetall(name)
            return result
        except Exception as e:
            print(f"Redis哈希获取全部失败 {name}: {e}")
            return {}
    
    async def lpush(self, name: str, *values) -> Optional[int]:
        """向列表左侧推入元素"""
        try:
            result = await self.redis_client.lpush(name, *values)
            return result
        except Exception as e:
            print(f"Redis列表推入失败 {name}: {e}")
            return None
    
    async def rpop(self, name: str) -> Optional[str]:
        """从列表右侧弹出元素"""
        try:
            result = await self.redis_client.rpop(name)
            return result
        except Exception as e:
            print(f"Redis列表弹出失败 {name}: {e}")
            return None
    
    async def llen(self, name: str) -> int:
        """获取列表长度"""
        try:
            result = await self.redis_client.llen(name)
            return result
        except Exception as e:
            print(f"Redis列表长度获取失败 {name}: {e}")
            return 0
    
    async def flushdb(self) -> bool:
        """清空当前数据库"""
        try:
            result = await self.redis_client.flushdb()
            return result
        except Exception as e:
            print(f"Redis清空数据库失败: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            latency = await self.redis_client.ping()
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "latency": f"{latency}ms",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# 全局Redis客户端实例
redis_client = RedisClient()


# 初始化和关闭函数
async def init_redis():
    """初始化Redis连接"""
    await redis_client.connect()


async def close_redis():
    """关闭Redis连接"""
    await redis_client.close()


# 缓存装饰器
def cache_result(ttl: int = 3600, key_prefix: str = "cache"):
    """缓存函数结果装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 尝试从缓存获取
            cached_result = await redis_client.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            await redis_client.set(cache_key, result, ttl=ttl)
            return result
        
        return wrapper
    return decorator


# 专用缓存类
class MarketDataCache:
    """市场数据缓存"""
    
    @staticmethod
    async def set_price(symbol: str, price: float, ttl: int = 30):
        """缓存价格数据"""
        key = f"price:{symbol}"
        await redis_client.set(key, price, ttl=ttl)
    
    @staticmethod
    async def get_price(symbol: str) -> Optional[float]:
        """获取价格数据"""
        key = f"price:{symbol}"
        price = await redis_client.get(key, deserialize=False)
        return float(price) if price else None
    
    @staticmethod
    async def set_kline(symbol: str, timeframe: str, data: Dict, ttl: int = 3600):
        """缓存K线数据"""
        key = f"kline:{symbol}:{timeframe}"
        await redis_client.set(key, data, ttl=ttl)
    
    @staticmethod
    async def get_kline(symbol: str, timeframe: str) -> Optional[Dict]:
        """获取K线数据"""
        key = f"kline:{symbol}:{timeframe}"
        return await redis_client.get(key)


class SessionCache:
    """会话缓存"""
    
    @staticmethod
    async def set_user_session(user_id: int, session_data: Dict, ttl: int = 86400):
        """设置用户会话"""
        key = f"session:user:{user_id}"
        await redis_client.set(key, session_data, ttl=ttl)
    
    @staticmethod
    async def get_user_session(user_id: int) -> Optional[Dict]:
        """获取用户会话"""
        key = f"session:user:{user_id}"
        return await redis_client.get(key)
    
    @staticmethod
    async def delete_user_session(user_id: int):
        """删除用户会话"""
        key = f"session:user:{user_id}"
        await redis_client.delete(key)


class RateLimitCache:
    """限流缓存"""
    
    @staticmethod
    async def check_rate_limit(identifier: str, limit: int, window: int = 60) -> bool:
        """检查是否超过限流"""
        key = f"rate_limit:{identifier}"
        current = await redis_client.incr(key)
        
        if current == 1:
            await redis_client.expire(key, window)
        
        return current <= limit
    
    @staticmethod
    async def get_rate_limit_info(identifier: str) -> Dict[str, int]:
        """获取限流信息"""
        key = f"rate_limit:{identifier}"
        current = await redis_client.get(key, deserialize=False)
        ttl = await redis_client.redis_client.ttl(key)
        
        return {
            "current": int(current) if current else 0,
            "remaining_seconds": ttl if ttl > 0 else 0
        }