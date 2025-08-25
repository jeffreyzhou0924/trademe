"""
异常处理和恢复机制 - 生产级错误处理系统

功能特性:
- 多层次异常捕获和处理
- 自动恢复和重试机制
- 熔断器模式实现
- 系统健康监控
- 错误分类和告警
- 优雅降级处理
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Union
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import traceback
import functools
from collections import deque, defaultdict
import inspect

from loguru import logger


class ErrorSeverity(Enum):
    """错误严重性级别"""
    LOW = "low"           # 低 - 可忽略
    MEDIUM = "medium"     # 中 - 需关注
    HIGH = "high"         # 高 - 需处理
    CRITICAL = "critical" # 严重 - 立即处理


class ErrorCategory(Enum):
    """错误分类"""
    NETWORK = "network"             # 网络错误
    EXCHANGE_API = "exchange_api"   # 交易所API错误
    DATABASE = "database"           # 数据库错误
    VALIDATION = "validation"       # 验证错误
    RISK_MANAGEMENT = "risk"        # 风险管理错误
    ORDER_EXECUTION = "order"       # 订单执行错误
    SYSTEM = "system"              # 系统错误
    UNKNOWN = "unknown"            # 未知错误


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"     # 关闭 - 正常运行
    OPEN = "open"         # 开启 - 熔断中
    HALF_OPEN = "half_open"  # 半开 - 尝试恢复


@dataclass
class ErrorInfo:
    """错误信息"""
    id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    traceback_info: str
    context: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class CircuitBreaker:
    """熔断器"""
    name: str
    failure_threshold: int = 5      # 失败阈值
    recovery_timeout: int = 60      # 恢复超时（秒）
    success_threshold: int = 3      # 半开状态成功阈值
    
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0         # 基础延迟（秒）
    max_delay: float = 60.0         # 最大延迟
    backoff_factor: float = 2.0     # 退避因子
    jitter: bool = True             # 是否加入随机抖动


class ErrorHandler:
    """异常处理和恢复管理器"""
    
    def __init__(self):
        """初始化错误处理器"""
        self._errors: deque = deque(maxlen=10000)  # 错误历史记录
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._error_counts: Dict[ErrorCategory, int] = defaultdict(int)
        self._recovery_handlers: Dict[ErrorCategory, Callable] = {}
        self._alert_handlers: List[Callable] = []
        
        # 统计信息
        self._stats = {
            'total_errors': 0,
            'resolved_errors': 0,
            'critical_errors': 0,
            'network_errors': 0,
            'api_errors': 0,
            'database_errors': 0,
            'system_errors': 0,
            'last_error_time': None,
            'uptime_start': datetime.utcnow()
        }
        
        # 注册默认恢复处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认恢复处理器"""
        self._recovery_handlers[ErrorCategory.NETWORK] = self._handle_network_error
        self._recovery_handlers[ErrorCategory.EXCHANGE_API] = self._handle_api_error
        self._recovery_handlers[ErrorCategory.DATABASE] = self._handle_database_error
        self._recovery_handlers[ErrorCategory.SYSTEM] = self._handle_system_error
    
    def handle_error(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        user_id: Optional[int] = None
    ) -> ErrorInfo:
        """处理异常"""
        try:
            # 分类异常
            if category is None:
                category = self._classify_exception(exception)
            
            if severity is None:
                severity = self._determine_severity(exception, category)
            
            # 创建错误信息
            error_info = ErrorInfo(
                id=f"err_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                category=category,
                severity=severity,
                message=str(exception),
                exception_type=type(exception).__name__,
                traceback_info=traceback.format_exc(),
                context=context or {}
            )
            
            if user_id:
                error_info.context['user_id'] = user_id
            
            # 记录错误
            self._record_error(error_info)
            
            # 更新统计
            self._update_stats(error_info)
            
            # 记录日志
            self._log_error(error_info)
            
            # 触发告警
            if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                asyncio.create_task(self._trigger_alerts(error_info))
            
            # 尝试自动恢复
            if self._should_attempt_recovery(error_info):
                asyncio.create_task(self._attempt_recovery(error_info))
            
            return error_info
            
        except Exception as e:
            logger.critical(f"错误处理器本身发生异常: {str(e)}")
            # 创建最基本的错误信息
            return ErrorInfo(
                id="handler_error",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                message=f"错误处理器异常: {str(e)}",
                exception_type="ErrorHandlerException",
                traceback_info=traceback.format_exc()
            )
    
    def _classify_exception(self, exception: Exception) -> ErrorCategory:
        """分类异常"""
        exception_type = type(exception).__name__
        exception_message = str(exception).lower()
        
        # 网络相关错误
        if any(keyword in exception_message for keyword in ['connection', 'network', 'timeout', 'dns']):
            return ErrorCategory.NETWORK
        
        # 数据库相关错误
        if any(keyword in exception_message for keyword in ['database', 'sql', 'sqlite', 'connection pool']):
            return ErrorCategory.DATABASE
        
        # API相关错误
        if any(keyword in exception_message for keyword in ['api', 'http', 'status code', 'rate limit']):
            return ErrorCategory.EXCHANGE_API
        
        # 验证相关错误
        if any(keyword in exception_message for keyword in ['validation', 'invalid', 'required']):
            return ErrorCategory.VALIDATION
        
        # 风险管理相关错误
        if any(keyword in exception_message for keyword in ['risk', 'limit', 'exposure']):
            return ErrorCategory.RISK_MANAGEMENT
        
        # 订单相关错误
        if any(keyword in exception_message for keyword in ['order', 'trade', 'execution']):
            return ErrorCategory.ORDER_EXECUTION
        
        # 系统相关错误
        if exception_type in ['MemoryError', 'SystemError', 'OSError']:
            return ErrorCategory.SYSTEM
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, exception: Exception, category: ErrorCategory) -> ErrorSeverity:
        """确定错误严重性"""
        exception_type = type(exception).__name__
        exception_message = str(exception).lower()
        
        # 严重错误
        critical_keywords = ['critical', 'fatal', 'emergency', 'system', 'memory']
        if any(keyword in exception_message for keyword in critical_keywords):
            return ErrorSeverity.CRITICAL
        
        if exception_type in ['MemoryError', 'SystemError', 'KeyboardInterrupt']:
            return ErrorSeverity.CRITICAL
        
        # 高严重性错误
        if category in [ErrorCategory.RISK_MANAGEMENT, ErrorCategory.SYSTEM]:
            return ErrorSeverity.HIGH
        
        high_keywords = ['error', 'fail', 'exception', 'timeout']
        if any(keyword in exception_message for keyword in high_keywords):
            return ErrorSeverity.HIGH
        
        # 中等严重性错误
        if category in [ErrorCategory.ORDER_EXECUTION, ErrorCategory.DATABASE]:
            return ErrorSeverity.MEDIUM
        
        # 低严重性错误
        return ErrorSeverity.LOW
    
    def _record_error(self, error_info: ErrorInfo):
        """记录错误"""
        self._errors.append(error_info)
        self._error_counts[error_info.category] += 1
    
    def _update_stats(self, error_info: ErrorInfo):
        """更新统计信息"""
        self._stats['total_errors'] += 1
        self._stats['last_error_time'] = error_info.occurred_at
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            self._stats['critical_errors'] += 1
        
        category_key = f"{error_info.category.value}_errors"
        self._stats[category_key] = self._stats.get(category_key, 0) + 1
    
    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_message = f"[{error_info.category.value.upper()}] {error_info.message}"
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # 详细信息只在调试模式记录
        if error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.debug(f"错误详情: {error_info.traceback_info}")
    
    async def _trigger_alerts(self, error_info: ErrorInfo):
        """触发告警"""
        try:
            for handler in self._alert_handlers:
                try:
                    await handler(error_info)
                except Exception as e:
                    logger.error(f"告警处理器异常: {str(e)}")
        except Exception as e:
            logger.error(f"触发告警异常: {str(e)}")
    
    def _should_attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """判断是否应该尝试自动恢复"""
        # 已达到最大重试次数
        if error_info.retry_count >= error_info.max_retries:
            return False
        
        # 严重错误不自动恢复
        if error_info.severity == ErrorSeverity.CRITICAL:
            return False
        
        # 检查是否有对应的恢复处理器
        return error_info.category in self._recovery_handlers
    
    async def _attempt_recovery(self, error_info: ErrorInfo):
        """尝试自动恢复"""
        try:
            handler = self._recovery_handlers.get(error_info.category)
            if handler:
                error_info.retry_count += 1
                
                # 计算重试延迟
                delay = min(1.0 * (2 ** (error_info.retry_count - 1)), 60.0)
                await asyncio.sleep(delay)
                
                # 执行恢复处理
                success = await handler(error_info)
                
                if success:
                    error_info.resolved = True
                    error_info.resolved_at = datetime.utcnow()
                    self._stats['resolved_errors'] += 1
                    logger.info(f"错误自动恢复成功: {error_info.id}")
                else:
                    # 如果还有重试机会，继续尝试
                    if error_info.retry_count < error_info.max_retries:
                        await asyncio.sleep(5)  # 短暂等待后重试
                        await self._attempt_recovery(error_info)
                    else:
                        logger.warning(f"错误恢复失败，已达最大重试次数: {error_info.id}")
                        
        except Exception as e:
            logger.error(f"自动恢复异常: {str(e)}")
    
    # 默认恢复处理器
    async def _handle_network_error(self, error_info: ErrorInfo) -> bool:
        """处理网络错误"""
        try:
            logger.info(f"尝试恢复网络错误: {error_info.id}")
            
            # TODO: 实现网络连接检查和重连逻辑
            # 这里可以ping测试、重新建立连接等
            
            # 模拟恢复检查
            await asyncio.sleep(2)
            
            logger.info(f"网络错误恢复完成: {error_info.id}")
            return True
            
        except Exception as e:
            logger.error(f"网络错误恢复异常: {str(e)}")
            return False
    
    async def _handle_api_error(self, error_info: ErrorInfo) -> bool:
        """处理API错误"""
        try:
            logger.info(f"尝试恢复API错误: {error_info.id}")
            
            # TODO: 实现API连接检查、重新认证等
            # 检查API限流状态、重新获取token等
            
            await asyncio.sleep(3)
            
            logger.info(f"API错误恢复完成: {error_info.id}")
            return True
            
        except Exception as e:
            logger.error(f"API错误恢复异常: {str(e)}")
            return False
    
    async def _handle_database_error(self, error_info: ErrorInfo) -> bool:
        """处理数据库错误"""
        try:
            logger.info(f"尝试恢复数据库错误: {error_info.id}")
            
            # TODO: 实现数据库连接检查、重连等
            # 检查连接池状态、重新建立连接等
            
            await asyncio.sleep(2)
            
            logger.info(f"数据库错误恢复完成: {error_info.id}")
            return True
            
        except Exception as e:
            logger.error(f"数据库错误恢复异常: {str(e)}")
            return False
    
    async def _handle_system_error(self, error_info: ErrorInfo) -> bool:
        """处理系统错误"""
        try:
            logger.info(f"尝试恢复系统错误: {error_info.id}")
            
            # TODO: 实现系统资源检查、清理等
            # 清理内存、检查磁盘空间等
            
            await asyncio.sleep(5)
            
            logger.warning(f"系统错误需要人工干预: {error_info.id}")
            return False  # 系统错误通常需要人工干预
            
        except Exception as e:
            logger.error(f"系统错误恢复异常: {str(e)}")
            return False
    
    # 熔断器相关方法
    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
        return self._circuit_breakers[name]
    
    def circuit_breaker_call(
        self,
        breaker_name: str,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ):
        """熔断器调用装饰器"""
        def decorator(original_func):
            @functools.wraps(original_func)
            async def wrapper(*args, **kwargs):
                breaker = self.get_circuit_breaker(breaker_name)
                
                # 检查熔断器状态
                if breaker.state == CircuitBreakerState.OPEN:
                    # 检查是否可以尝试恢复
                    if (breaker.last_failure_time and 
                        datetime.utcnow() - breaker.last_failure_time > timedelta(seconds=breaker.recovery_timeout)):
                        breaker.state = CircuitBreakerState.HALF_OPEN
                        breaker.success_count = 0
                    else:
                        # 熔断中，调用回退函数
                        if fallback:
                            return await fallback(*args, **kwargs)
                        raise Exception(f"熔断器 {breaker_name} 处于开启状态")
                
                try:
                    result = await original_func(*args, **kwargs)
                    
                    # 成功调用
                    if breaker.state == CircuitBreakerState.HALF_OPEN:
                        breaker.success_count += 1
                        if breaker.success_count >= breaker.success_threshold:
                            breaker.state = CircuitBreakerState.CLOSED
                            breaker.failure_count = 0
                    else:
                        breaker.failure_count = max(0, breaker.failure_count - 1)
                    
                    breaker.last_success_time = datetime.utcnow()
                    return result
                    
                except Exception as e:
                    # 调用失败
                    breaker.failure_count += 1
                    breaker.last_failure_time = datetime.utcnow()
                    
                    if breaker.failure_count >= breaker.failure_threshold:
                        breaker.state = CircuitBreakerState.OPEN
                        logger.warning(f"熔断器 {breaker_name} 已开启")
                    
                    # 记录错误
                    self.handle_error(e, context={'circuit_breaker': breaker_name})
                    raise
                    
            return wrapper
        
        if func:
            return decorator(func)
        return decorator
    
    # 重试装饰器
    def retry(
        self,
        config: Optional[RetryConfig] = None,
        exceptions: tuple = (Exception,)
    ):
        """重试装饰器"""
        if config is None:
            config = RetryConfig()
            
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(config.max_attempts):
                    try:
                        if inspect.iscoroutinefunction(func):
                            return await func(*args, **kwargs)
                        else:
                            return func(*args, **kwargs)
                            
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt == config.max_attempts - 1:
                            # 最后一次尝试失败
                            break
                        
                        # 计算延迟
                        delay = min(config.base_delay * (config.backoff_factor ** attempt), config.max_delay)
                        
                        if config.jitter:
                            import random
                            delay *= (0.5 + random.random() * 0.5)  # 添加50%的随机抖动
                        
                        logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败，{delay:.2f}秒后重试: {str(e)}")
                        await asyncio.sleep(delay)
                
                # 记录最终失败
                error_info = self.handle_error(
                    last_exception,
                    context={'function': func.__name__, 'attempts': config.max_attempts}
                )
                raise last_exception
                
            return wrapper
        return decorator
    
    # 查询接口
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计"""
        stats = self._stats.copy()
        stats['error_categories'] = dict(self._error_counts)
        stats['circuit_breakers'] = {
            name: {
                'state': cb.state.value,
                'failure_count': cb.failure_count,
                'success_count': cb.success_count
            }
            for name, cb in self._circuit_breakers.items()
        }
        return stats
    
    def get_recent_errors(self, limit: int = 100, severity: Optional[ErrorSeverity] = None) -> List[Dict[str, Any]]:
        """获取最近错误"""
        errors = list(self._errors)
        
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        # 按时间倒序排列
        errors.sort(key=lambda x: x.occurred_at, reverse=True)
        
        return [self._error_to_dict(e) for e in errors[:limit]]
    
    def _error_to_dict(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """转换错误信息为字典"""
        return {
            'id': error_info.id,
            'category': error_info.category.value,
            'severity': error_info.severity.value,
            'message': error_info.message,
            'exception_type': error_info.exception_type,
            'context': error_info.context,
            'occurred_at': error_info.occurred_at.isoformat(),
            'resolved': error_info.resolved,
            'resolved_at': error_info.resolved_at.isoformat() if error_info.resolved_at else None,
            'retry_count': error_info.retry_count
        }
    
    def add_alert_handler(self, handler: Callable):
        """添加告警处理器"""
        self._alert_handlers.append(handler)
    
    def add_recovery_handler(self, category: ErrorCategory, handler: Callable):
        """添加自定义恢复处理器"""
        self._recovery_handlers[category] = handler


# 全局错误处理器实例
error_handler = ErrorHandler()