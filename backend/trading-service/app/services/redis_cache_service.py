"""
企业级Redis缓存服务
提供多层缓存架构，支持用户会话、市场数据、API响应、AI对话等场景
"""

import json
import hashlib
import asyncio
from typing import Optional, Any, Dict, List, Union, Callable, Set
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis
from contextlib import asynccontextmanager
import pickle
import gzip
import time
from functools import wraps

logger = logging.getLogger(__name__)

class CacheLevel(Enum):
    """缓存级别定义"""
    L1_MEMORY = "l1_memory"        # 内存缓存，最快访问
    L2_REDIS = "l2_redis"          # Redis缓存，中等速度
    L3_DATABASE = "l3_database"     # 数据库缓存，最慢但持久

class CacheStrategy(Enum):
    """缓存策略"""
    WRITE_THROUGH = "write_through"    # 写透缓存
    WRITE_BACK = "write_back"          # 写回缓存
    WRITE_AROUND = "write_around"      # 绕写缓存
    CACHE_ASIDE = "cache_aside"        # 旁路缓存

class CompressionType(Enum):
    """压缩类型"""
    NONE = "none"
    GZIP = "gzip"
    PICKLE = "pickle"
    JSON = "json"

@dataclass
class CacheConfig:
    """缓存配置"""
    ttl: int = 3600                          # 存活时间（秒）
    strategy: CacheStrategy = CacheStrategy.CACHE_ASIDE
    compression: CompressionType = CompressionType.JSON
    max_size: Optional[int] = None           # 最大缓存大小
    enable_metrics: bool = True              # 启用性能指标
    namespace: str = "trademe"               # 命名空间
    
@dataclass 
class CacheMetrics:
    """缓存性能指标"""
    hits: int = 0
    misses: int = 0
    writes: int = 0
    deletes: int = 0
    errors: int = 0
    total_time: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_response_time(self) -> float:
        total_ops = self.hits + self.misses + self.writes
        return self.total_time / total_ops if total_ops > 0 else 0.0

class RedisCacheService:
    """企业级Redis缓存服务"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Any] = {}
        self.cache_configs: Dict[str, CacheConfig] = {}
        self.metrics: Dict[str, CacheMetrics] = {}
        self.is_connected = False
        
        # 预设缓存配置
        self._setup_default_configs()
        
    def _setup_default_configs(self):
        """设置默认缓存配置"""
        self.cache_configs.update({
            "user_sessions": CacheConfig(ttl=1800, namespace="session"),
            "market_data": CacheConfig(ttl=30, namespace="market", compression=CompressionType.GZIP),
            "api_responses": CacheConfig(ttl=300, namespace="api"),
            "ai_conversations": CacheConfig(ttl=3600, namespace="ai", max_size=1000),
            "strategy_results": CacheConfig(ttl=1800, namespace="strategy"),
            "user_profiles": CacheConfig(ttl=7200, namespace="user"),
            "historical_data": CacheConfig(ttl=86400, namespace="history", compression=CompressionType.GZIP),
            "real_time_prices": CacheConfig(ttl=5, namespace="price"),
            "trading_signals": CacheConfig(ttl=60, namespace="signal"),
            "backtest_cache": CacheConfig(ttl=3600, namespace="backtest")
        })
    
    async def connect(self):
        """连接Redis服务器"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=20
            )
            
            # 测试连接
            await self.redis_client.ping()
            self.is_connected = True
            logger.info("Redis缓存服务连接成功")
            
            # 启动清理任务
            asyncio.create_task(self._cleanup_task())
            
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self.is_connected = False
            
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.is_connected = False
            logger.info("Redis缓存服务已断开")
    
    def _generate_key(self, namespace: str, key: str) -> str:
        """生成缓存键"""
        return f"{namespace}:{key}"
    
    def _serialize_data(self, data: Any, compression: CompressionType) -> bytes:
        """序列化数据"""
        try:
            if compression == CompressionType.JSON:
                serialized = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
            elif compression == CompressionType.PICKLE:
                serialized = pickle.dumps(data)
            else:
                serialized = str(data).encode('utf-8')
            
            if compression == CompressionType.GZIP:
                return gzip.compress(serialized)
            return serialized
            
        except Exception as e:
            logger.error(f"数据序列化失败: {e}")
            return str(data).encode('utf-8')
    
    def _deserialize_data(self, data: bytes, compression: CompressionType) -> Any:
        """反序列化数据"""
        try:
            if compression == CompressionType.GZIP:
                data = gzip.decompress(data)
            
            if compression == CompressionType.JSON:
                return json.loads(data.decode('utf-8'))
            elif compression == CompressionType.PICKLE:
                return pickle.loads(data)
            else:
                return data.decode('utf-8')
                
        except Exception as e:
            logger.error(f"数据反序列化失败: {e}")
            return None
    
    async def get(self, key: str, cache_type: str = "default", 
                  fallback_func: Optional[Callable] = None) -> Optional[Any]:
        """获取缓存数据"""
        config = self.cache_configs.get(cache_type, CacheConfig())
        full_key = self._generate_key(config.namespace, key)
        
        start_time = time.time()
        
        try:
            # L1缓存：内存缓存
            if full_key in self.memory_cache:
                self._record_metrics(cache_type, "hit", time.time() - start_time)
                return self.memory_cache[full_key]
            
            # L2缓存：Redis缓存
            if self.is_connected and self.redis_client:
                cached_data = await self.redis_client.get(full_key)
                if cached_data:
                    result = self._deserialize_data(cached_data, config.compression)
                    
                    # 存入L1缓存
                    self.memory_cache[full_key] = result
                    self._record_metrics(cache_type, "hit", time.time() - start_time)
                    return result
            
            # 缓存未命中，调用回调函数
            if fallback_func:
                result = await fallback_func() if asyncio.iscoroutinefunction(fallback_func) else fallback_func()
                if result is not None:
                    await self.set(key, result, cache_type)
                    self._record_metrics(cache_type, "miss", time.time() - start_time)
                    return result
            
            self._record_metrics(cache_type, "miss", time.time() - start_time)
            return None
            
        except Exception as e:
            logger.error(f"获取缓存数据失败 {full_key}: {e}")
            self._record_metrics(cache_type, "error", time.time() - start_time)
            return None
    
    async def set(self, key: str, value: Any, cache_type: str = "default") -> bool:
        """设置缓存数据"""
        config = self.cache_configs.get(cache_type, CacheConfig())
        full_key = self._generate_key(config.namespace, key)
        
        start_time = time.time()
        
        try:
            # L1缓存：内存缓存
            self.memory_cache[full_key] = value
            
            # L2缓存：Redis缓存
            if self.is_connected and self.redis_client:
                serialized_data = self._serialize_data(value, config.compression)
                
                if config.ttl > 0:
                    await self.redis_client.setex(full_key, config.ttl, serialized_data)
                else:
                    await self.redis_client.set(full_key, serialized_data)
            
            self._record_metrics(cache_type, "write", time.time() - start_time)
            return True
            
        except Exception as e:
            logger.error(f"设置缓存数据失败 {full_key}: {e}")
            self._record_metrics(cache_type, "error", time.time() - start_time)
            return False
    
    async def delete(self, key: str, cache_type: str = "default") -> bool:
        """删除缓存数据"""
        config = self.cache_configs.get(cache_type, CacheConfig())
        full_key = self._generate_key(config.namespace, key)
        
        try:
            # 删除L1缓存
            self.memory_cache.pop(full_key, None)
            
            # 删除L2缓存
            if self.is_connected and self.redis_client:
                await self.redis_client.delete(full_key)
            
            self._record_metrics(cache_type, "delete")
            return True
            
        except Exception as e:
            logger.error(f"删除缓存数据失败 {full_key}: {e}")
            return False
    
    async def exists(self, key: str, cache_type: str = "default") -> bool:
        """检查缓存是否存在"""
        config = self.cache_configs.get(cache_type, CacheConfig())
        full_key = self._generate_key(config.namespace, key)
        
        try:
            # 检查L1缓存
            if full_key in self.memory_cache:
                return True
            
            # 检查L2缓存
            if self.is_connected and self.redis_client:
                result = await self.redis_client.exists(full_key)
                return result > 0
                
            return False
            
        except Exception as e:
            logger.error(f"检查缓存存在失败 {full_key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int, cache_type: str = "default") -> bool:
        """设置缓存过期时间"""
        config = self.cache_configs.get(cache_type, CacheConfig())
        full_key = self._generate_key(config.namespace, key)
        
        try:
            if self.is_connected and self.redis_client:
                return await self.redis_client.expire(full_key, ttl)
            return False
            
        except Exception as e:
            logger.error(f"设置缓存过期时间失败 {full_key}: {e}")
            return False
    
    async def clear_namespace(self, namespace: str) -> int:
        """清空指定命名空间的所有缓存"""
        try:
            pattern = f"{namespace}:*"
            count = 0
            
            # 清理L1缓存
            keys_to_remove = [k for k in self.memory_cache.keys() if k.startswith(f"{namespace}:")]
            for key in keys_to_remove:
                del self.memory_cache[key]
                count += 1
            
            # 清理L2缓存
            if self.is_connected and self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    count += deleted
            
            logger.info(f"清空命名空间 {namespace}，删除 {count} 个缓存")
            return count
            
        except Exception as e:
            logger.error(f"清空命名空间失败 {namespace}: {e}")
            return 0
    
    def _record_metrics(self, cache_type: str, operation: str, response_time: float = 0.0):
        """记录性能指标"""
        if cache_type not in self.metrics:
            self.metrics[cache_type] = CacheMetrics()
        
        metrics = self.metrics[cache_type]
        
        if operation == "hit":
            metrics.hits += 1
        elif operation == "miss":
            metrics.misses += 1
        elif operation == "write":
            metrics.writes += 1
        elif operation == "delete":
            metrics.deletes += 1
        elif operation == "error":
            metrics.errors += 1
        
        metrics.total_time += response_time
    
    def get_metrics(self, cache_type: Optional[str] = None) -> Dict[str, Any]:
        """获取性能指标"""
        if cache_type:
            if cache_type in self.metrics:
                return asdict(self.metrics[cache_type])
            return {}
        
        return {
            cache_type: asdict(metrics) 
            for cache_type, metrics in self.metrics.items()
        }
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        info = {
            "connected": self.is_connected,
            "memory_cache_size": len(self.memory_cache),
            "cache_configs": len(self.cache_configs),
            "metrics": self.get_metrics()
        }
        
        if self.is_connected and self.redis_client:
            redis_info = await self.redis_client.info()
            info["redis_info"] = {
                "used_memory_human": redis_info.get("used_memory_human"),
                "connected_clients": redis_info.get("connected_clients"),
                "total_commands_processed": redis_info.get("total_commands_processed"),
                "keyspace_hits": redis_info.get("keyspace_hits"),
                "keyspace_misses": redis_info.get("keyspace_misses")
            }
        
        return info
    
    async def _cleanup_task(self):
        """定期清理任务"""
        while self.is_connected:
            try:
                # 清理L1缓存中的过期数据（简单实现）
                current_time = time.time()
                keys_to_remove = []
                
                for key in list(self.memory_cache.keys()):
                    # 这里可以实现更复杂的过期检查逻辑
                    pass
                
                # 每5分钟执行一次清理
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
                await asyncio.sleep(60)

# 缓存装饰器
def cached(cache_type: str = "default", ttl: Optional[int] = None):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            cache_service = kwargs.get('cache_service')
            if not cache_service:
                # 如果没有传入缓存服务，直接调用原函数
                return await func(*args, **kwargs)
            
            # 尝试从缓存获取
            result = await cache_service.get(cache_key, cache_type)
            if result is not None:
                return result
            
            # 缓存未命中，调用原函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            if result is not None:
                await cache_service.set(cache_key, result, cache_type)
            
            return result
        
        return wrapper
    return decorator

# 全局缓存服务实例
cache_service = RedisCacheService()

# 上下文管理器
@asynccontextmanager
async def get_cache_service():
    """获取缓存服务上下文管理器"""
    if not cache_service.is_connected:
        await cache_service.connect()
    try:
        yield cache_service
    finally:
        pass  # 保持连接，不关闭

async def initialize_cache_service(redis_url: str = "redis://localhost:6379"):
    """初始化缓存服务"""
    global cache_service
    cache_service = RedisCacheService(redis_url)
    await cache_service.connect()
    return cache_service