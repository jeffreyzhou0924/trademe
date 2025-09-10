"""
代理重试管理器 - 智能代理轮换和重试机制
支持多代理端点、指数退避、健康检查、故障转移
"""

import asyncio
import aiohttp
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProxyStatus(Enum):
    """代理状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ProxyEndpoint:
    """代理端点配置"""
    url: str
    name: str
    priority: int = 100  # 优先级，越高越优先
    max_retries: int = 3
    timeout: int = 30  # 秒
    health_check_interval: int = 300  # 健康检查间隔（秒）
    last_health_check: Optional[datetime] = None
    status: ProxyStatus = ProxyStatus.UNKNOWN
    success_count: int = 0
    failure_count: int = 0
    avg_response_time: float = 0.0
    last_error: Optional[str] = None


class ProxyRetryManager:
    """智能代理重试管理器"""
    
    def __init__(self):
        self.proxies: List[ProxyEndpoint] = []
        self.current_proxy_index = 0
        self.health_check_task = None
        self._lock = asyncio.Lock()
        
        # 重试配置
        self.base_retry_delay = 1.0  # 基础重试延迟（秒）
        self.max_retry_delay = 60.0  # 最大重试延迟（秒）
        self.jitter_factor = 0.2  # 抖动因子，避免雷群效应
        
        # 统计信息
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
    def add_proxy(self, proxy: ProxyEndpoint):
        """添加代理端点"""
        self.proxies.append(proxy)
        logger.info(f"✅ Added proxy: {proxy.name} ({proxy.url})")
        
    def configure_default_proxies(self):
        """配置默认的第三方代理端点"""
        # 这里可以配置多个备用代理
        default_proxies = [
            ProxyEndpoint(
                url="https://api.anthropic.com/v1",
                name="Direct API",
                priority=100,
                timeout=30
            ),
            # 可以添加更多第三方代理端点
            # ProxyEndpoint(
            #     url="https://proxy1.example.com/v1",
            #     name="Proxy 1",
            #     priority=90,
            #     timeout=200
            # ),
        ]
        
        for proxy in default_proxies:
            self.add_proxy(proxy)
            
    async def start_health_monitoring(self):
        """启动健康监控任务"""
        if self.health_check_task is None:
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("🏥 Started proxy health monitoring")
            
    async def stop_health_monitoring(self):
        """停止健康监控任务"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None
            logger.info("🛑 Stopped proxy health monitoring")
            
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await self._check_all_proxies_health()
                await asyncio.sleep(60)  # 每分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)
                
    async def _check_all_proxies_health(self):
        """检查所有代理的健康状态"""
        tasks = []
        for proxy in self.proxies:
            # 如果距离上次检查超过间隔时间，则进行健康检查
            if (proxy.last_health_check is None or 
                datetime.utcnow() - proxy.last_health_check > timedelta(seconds=proxy.health_check_interval)):
                tasks.append(self._check_proxy_health(proxy))
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _check_proxy_health(self, proxy: ProxyEndpoint) -> bool:
        """检查单个代理的健康状态"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)  # 健康检查用短超时
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 简单的健康检查请求
                start_time = datetime.utcnow()
                
                # 如果是Anthropic API，使用特定的健康检查端点
                if "anthropic" in proxy.url.lower():
                    check_url = proxy.url.rstrip('/') + "/v1/models"
                else:
                    check_url = proxy.url.rstrip('/') + "/health"
                    
                async with session.get(check_url) as response:
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    if response.status < 500:  # 2xx, 3xx, 4xx都认为服务可用
                        proxy.status = ProxyStatus.HEALTHY
                        proxy.avg_response_time = (proxy.avg_response_time * 0.7 + response_time * 0.3)  # 指数移动平均
                        proxy.last_health_check = datetime.utcnow()
                        proxy.last_error = None
                        return True
                    else:
                        proxy.status = ProxyStatus.DEGRADED
                        proxy.last_error = f"HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            proxy.status = ProxyStatus.DEGRADED
            proxy.last_error = "Health check timeout"
        except Exception as e:
            proxy.status = ProxyStatus.FAILED
            proxy.last_error = str(e)
            
        proxy.last_health_check = datetime.utcnow()
        return False
        
    def get_next_proxy(self) -> Optional[ProxyEndpoint]:
        """获取下一个可用的代理（基于优先级和健康状态）"""
        # 过滤出健康或未知状态的代理
        available_proxies = [
            p for p in self.proxies 
            if p.status in [ProxyStatus.HEALTHY, ProxyStatus.UNKNOWN, ProxyStatus.DEGRADED]
        ]
        
        if not available_proxies:
            # 如果没有健康的代理，尝试所有代理
            available_proxies = self.proxies
            
        if not available_proxies:
            return None
            
        # 按优先级和成功率排序
        available_proxies.sort(key=lambda p: (
            -p.priority,  # 优先级高的优先
            -self._calculate_success_rate(p),  # 成功率高的优先
            p.avg_response_time  # 响应时间短的优先
        ))
        
        return available_proxies[0]
        
    def _calculate_success_rate(self, proxy: ProxyEndpoint) -> float:
        """计算代理的成功率"""
        total = proxy.success_count + proxy.failure_count
        if total == 0:
            return 0.5  # 新代理给予中等成功率
        return proxy.success_count / total
        
    def calculate_retry_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避 + 抖动）"""
        # 指数退避
        delay = min(self.base_retry_delay * (2 ** attempt), self.max_retry_delay)
        
        # 添加抖动
        jitter = delay * self.jitter_factor * (2 * random.random() - 1)
        delay = max(0.1, delay + jitter)
        
        return delay
        
    async def execute_with_retry(
        self,
        request_func: Callable,
        max_retries: Optional[int] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行请求并自动重试
        
        Args:
            request_func: 异步请求函数
            max_retries: 最大重试次数（覆盖默认值）
            timeout: 超时时间（覆盖默认值）
            **kwargs: 传递给请求函数的额外参数
            
        Returns:
            Dict containing success status and response/error
        """
        self.total_requests += 1
        last_error = None
        attempts_log = []
        
        # 尝试所有可用的代理
        for proxy_attempt in range(len(self.proxies)):
            proxy = self.get_next_proxy()
            if not proxy:
                break
                
            retries = max_retries or proxy.max_retries
            request_timeout = timeout or proxy.timeout
            
            # 对每个代理进行重试
            for attempt in range(retries):
                try:
                    start_time = datetime.utcnow()
                    
                    # 执行请求
                    result = await asyncio.wait_for(
                        request_func(proxy_url=proxy.url, **kwargs),
                        timeout=request_timeout
                    )
                    
                    # 记录成功
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    proxy.success_count += 1
                    proxy.avg_response_time = (proxy.avg_response_time * 0.9 + response_time * 0.1)
                    proxy.status = ProxyStatus.HEALTHY
                    self.successful_requests += 1
                    
                    logger.info(f"✅ Request successful via {proxy.name} (attempt {attempt + 1}/{retries})")
                    
                    return {
                        "success": True,
                        "response": result,
                        "proxy_used": proxy.name,
                        "attempts": attempt + 1,
                        "response_time": response_time
                    }
                    
                except asyncio.TimeoutError:
                    last_error = f"Timeout after {request_timeout}s"
                    proxy.failure_count += 1
                    
                    attempts_log.append({
                        "proxy": proxy.name,
                        "attempt": attempt + 1,
                        "error": "Timeout",
                        "duration": request_timeout
                    })
                    
                    logger.warning(f"⏱️ Timeout on {proxy.name} (attempt {attempt + 1}/{retries})")
                    
                except Exception as e:
                    last_error = str(e)
                    proxy.failure_count += 1
                    proxy.last_error = last_error
                    
                    attempts_log.append({
                        "proxy": proxy.name,
                        "attempt": attempt + 1,
                        "error": str(e)
                    })
                    
                    logger.warning(f"❌ Error on {proxy.name} (attempt {attempt + 1}/{retries}): {e}")
                    
                # 如果不是最后一次尝试，等待后重试
                if attempt < retries - 1:
                    delay = self.calculate_retry_delay(attempt)
                    logger.info(f"⏳ Waiting {delay:.1f}s before retry...")
                    await asyncio.sleep(delay)
                    
            # 标记代理为降级状态
            if proxy.failure_count > proxy.success_count:
                proxy.status = ProxyStatus.DEGRADED
                
        # 所有尝试都失败
        self.failed_requests += 1
        
        return {
            "success": False,
            "error": last_error or "All retry attempts failed",
            "attempts_log": attempts_log,
            "total_attempts": sum(len(log) for log in attempts_log)
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        proxy_stats = []
        for proxy in self.proxies:
            success_rate = self._calculate_success_rate(proxy)
            proxy_stats.append({
                "name": proxy.name,
                "status": proxy.status.value,
                "success_rate": f"{success_rate:.1%}",
                "avg_response_time": f"{proxy.avg_response_time:.2f}s",
                "success_count": proxy.success_count,
                "failure_count": proxy.failure_count,
                "last_error": proxy.last_error
            })
            
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "overall_success_rate": f"{self.successful_requests / max(1, self.total_requests):.1%}",
            "proxy_stats": proxy_stats
        }
        

# 创建全局实例
proxy_retry_manager = ProxyRetryManager()

# 配置默认代理
proxy_retry_manager.configure_default_proxies()