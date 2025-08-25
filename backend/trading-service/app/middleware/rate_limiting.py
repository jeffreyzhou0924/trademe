"""
速率限制中间件
实现API速率限制以防止滥用和DDoS攻击
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import hashlib
from datetime import datetime, timedelta

from app.config import settings
from app.redis_client import redis_client


class RateLimiter:
    """速率限制器"""
    
    def __init__(self):
        """初始化速率限制器"""
        self.default_limit = settings.api_rate_limit  # 默认每分钟1000次
        self.redis_client = None
        
        # 不同端点的特定限制 (requests_per_minute)
        self.endpoint_limits = {
            "/auth/login": 10,           # 登录限制更严格
            "/auth/logout": 20,          
            "/api/v1/ai/chat": 30,       # AI聊天限制
            "/api/v1/strategies": 100,   # 策略管理
            "/api/v1/backtests": 50,     # 回测限制
            "/api/v1/trades": 200,       # 交易数据
            "/api/v1/market": 500,       # 市场数据限制相对宽松
        }
        
        # 特权用户限制倍数
        self.membership_multipliers = {
            "basic": 1.0,
            "pro": 2.0,
            "elite": 5.0,
            "admin": 10.0
        }
        
        # 内存缓存 (Redis不可用时使用)
        self.memory_cache = {}
        self.cache_cleanup_interval = 300  # 5分钟清理一次
        self.last_cleanup = time.time()
    
    async def get_redis(self):
        """获取Redis客户端"""
        return redis_client
    
    def get_client_identifier(self, request: Request) -> str:
        """获取客户端唯一标识"""
        # 优先使用认证用户ID
        if hasattr(request.state, 'user') and request.state.user:
            return f"user:{request.state.user.id}"
        
        # 获取真实IP (考虑代理)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # 结合IP和User-Agent创建指纹
        user_agent = request.headers.get("User-Agent", "")
        fingerprint = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
        
        return f"ip:{client_ip}:{fingerprint[:8]}"
    
    def get_rate_limit_for_endpoint(self, path: str, user_membership: str = "basic") -> int:
        """获取特定端点的速率限制"""
        # 获取基础限制
        base_limit = self.endpoint_limits.get(path, self.default_limit)
        
        # 应用会员等级倍数
        multiplier = self.membership_multipliers.get(user_membership, 1.0)
        
        return int(base_limit * multiplier)
    
    async def is_rate_limited_redis(self, key: str, limit: int, window: int = 60) -> Tuple[bool, Dict]:
        """使用Redis检查速率限制"""
        try:
            redis_instance = await self.get_redis()
            if not redis_instance or not redis_instance.redis_client:
                return await self.is_rate_limited_memory(key, limit, window)
            
            # 滑动窗口算法
            now = time.time()
            redis_conn = redis_instance.redis_client
            pipeline = redis_conn.pipeline()
            
            # 清理过期的请求记录
            pipeline.zremrangebyscore(key, 0, now - window)
            
            # 添加当前请求
            pipeline.zadd(key, {str(now): now})
            
            # 获取当前窗口内的请求数量
            pipeline.zcard(key)
            
            # 设置key的过期时间
            pipeline.expire(key, window + 10)
            
            results = await pipeline.execute()
            current_requests = results[2]  # zcard的结果
            
            is_limited = current_requests > limit
            
            # 计算重置时间
            oldest_requests = await redis_conn.zrange(key, 0, 0, withscores=True)
            if oldest_requests:
                reset_time = oldest_requests[0][1] + window
            else:
                reset_time = now + window
            
            return is_limited, {
                "limit": limit,
                "remaining": max(0, limit - current_requests),
                "reset": int(reset_time),
                "retry_after": max(1, int(reset_time - now)) if is_limited else None
            }
            
        except Exception as e:
            print(f"Redis速率限制失败，回退到内存: {str(e)}")
            return await self.is_rate_limited_memory(key, limit, window)
    
    async def is_rate_limited_memory(self, key: str, limit: int, window: int = 60) -> Tuple[bool, Dict]:
        """使用内存检查速率限制 (Redis不可用时的后备方案)"""
        now = time.time()
        
        # 定期清理过期数据
        if now - self.last_cleanup > self.cache_cleanup_interval:
            await self.cleanup_memory_cache(now, window)
            self.last_cleanup = now
        
        # 获取或创建客户端记录
        if key not in self.memory_cache:
            self.memory_cache[key] = []
        
        client_requests = self.memory_cache[key]
        
        # 清理过期请求
        cutoff_time = now - window
        client_requests[:] = [req_time for req_time in client_requests if req_time > cutoff_time]
        
        # 检查是否超限
        is_limited = len(client_requests) >= limit
        
        if not is_limited:
            # 添加当前请求
            client_requests.append(now)
        
        # 计算重置时间
        if client_requests:
            reset_time = min(client_requests) + window
        else:
            reset_time = now + window
        
        return is_limited, {
            "limit": limit,
            "remaining": max(0, limit - len(client_requests)),
            "reset": int(reset_time),
            "retry_after": max(1, int(reset_time - now)) if is_limited else None
        }
    
    async def cleanup_memory_cache(self, now: float, window: int):
        """清理内存缓存中的过期数据"""
        cutoff_time = now - window
        keys_to_remove = []
        
        for key, requests in self.memory_cache.items():
            # 移除过期的请求
            requests[:] = [req_time for req_time in requests if req_time > cutoff_time]
            
            # 如果没有有效请求，标记删除
            if not requests:
                keys_to_remove.append(key)
        
        # 删除空的记录
        for key in keys_to_remove:
            del self.memory_cache[key]
    
    async def check_rate_limit(self, request: Request) -> Optional[JSONResponse]:
        """检查请求是否超过速率限制"""
        # 获取客户端标识
        client_id = self.get_client_identifier(request)
        
        # 获取用户会员等级
        user_membership = "basic"
        if hasattr(request.state, 'user') and request.state.user:
            user_membership = getattr(request.state.user, 'membership_level', 'basic')
        
        # 获取路径特定的限制
        path = request.url.path
        rate_limit = self.get_rate_limit_for_endpoint(path, user_membership)
        
        # 构建Redis key
        redis_key = f"rate_limit:{client_id}:{path}"
        
        # 检查速率限制
        is_limited, limit_info = await self.is_rate_limited_redis(redis_key, rate_limit)
        
        if is_limited:
            # 返回速率限制错误
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"超过API速率限制。每分钟最多 {rate_limit} 次请求。",
                    "limit": limit_info["limit"],
                    "remaining": limit_info["remaining"],
                    "reset": limit_info["reset"],
                    "retry_after": limit_info["retry_after"]
                },
                headers={
                    "X-RateLimit-Limit": str(limit_info["limit"]),
                    "X-RateLimit-Remaining": str(limit_info["remaining"]),
                    "X-RateLimit-Reset": str(limit_info["reset"]),
                    "Retry-After": str(limit_info["retry_after"])
                }
            )
        
        # 在响应头中添加速率限制信息
        request.state.rate_limit_info = limit_info
        return None


# 全局速率限制器实例
rate_limiter = RateLimiter()


async def rate_limiting_middleware(request: Request, call_next):
    """速率限制中间件"""
    
    # 跳过健康检查和文档端点
    skip_paths = ["/health", "/", "/docs", "/redoc", "/openapi.json"]
    if request.url.path in skip_paths:
        return await call_next(request)
    
    # 检查速率限制
    rate_limit_response = await rate_limiter.check_rate_limit(request)
    if rate_limit_response:
        return rate_limit_response
    
    # 继续处理请求
    response = await call_next(request)
    
    # 添加速率限制头信息
    if hasattr(request.state, 'rate_limit_info'):
        limit_info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(limit_info["reset"])
    
    return response