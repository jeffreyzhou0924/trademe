"""
统一的服务结果处理系统

解决错误处理不一致的问题，提供标准化的服务响应格式
"""

from typing import Generic, TypeVar, Optional, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

T = TypeVar('T')


class ErrorCode(Enum):
    """标准错误代码"""
    # 通用错误 (1000-1999)
    SUCCESS = 1000
    UNKNOWN_ERROR = 1001
    VALIDATION_ERROR = 1002
    NOT_FOUND = 1003
    ALREADY_EXISTS = 1004
    PERMISSION_DENIED = 1005
    
    # 认证错误 (2000-2999)
    AUTHENTICATION_FAILED = 2001
    TOKEN_EXPIRED = 2002
    INVALID_TOKEN = 2003
    INSUFFICIENT_PERMISSIONS = 2004
    
    # 业务错误 (3000-3999)
    QUOTA_EXCEEDED = 3001
    INVALID_STRATEGY = 3002
    BACKTEST_FAILED = 3003
    AI_SERVICE_ERROR = 3004
    MARKET_DATA_ERROR = 3005
    
    # 外部服务错误 (4000-4999)
    CLAUDE_API_ERROR = 4001
    EXCHANGE_API_ERROR = 4002
    DATABASE_ERROR = 4003
    WEBSOCKET_ERROR = 4004
    
    # 系统错误 (5000-5999)
    SYSTEM_OVERLOAD = 5001
    SERVICE_UNAVAILABLE = 5002
    TIMEOUT = 5003
    CIRCUIT_BREAKER_OPEN = 5004


@dataclass
class ErrorDetail:
    """错误详情"""
    code: ErrorCode
    message: str
    field: Optional[str] = None  # 针对特定字段的错误
    context: Dict[str, Any] = field(default_factory=dict)  # 额外的错误上下文
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code.value,
            'code_name': self.code.name,
            'message': self.message,
            'field': self.field,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ServiceResult(Generic[T]):
    """
    统一的服务结果类
    
    使用示例:
    ```python
    # 成功情况
    result = ServiceResult.success(data={'strategy_id': 123})
    
    # 失败情况
    result = ServiceResult.failure(
        error=ErrorDetail(
            code=ErrorCode.VALIDATION_ERROR,
            message="策略代码格式错误",
            field="strategy_code"
        )
    )
    
    # 检查结果
    if result.is_success():
        print(result.data)
    else:
        print(result.error.message)
    ```
    """
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, data: T = None, warnings: List[str] = None, metadata: Dict[str, Any] = None) -> 'ServiceResult[T]':
        """创建成功结果"""
        return cls(
            success=True,
            data=data,
            error=None,
            warnings=warnings or [],
            metadata=metadata or {}
        )
    
    @classmethod
    def failure(cls, error: ErrorDetail, warnings: List[str] = None, metadata: Dict[str, Any] = None) -> 'ServiceResult[T]':
        """创建失败结果"""
        return cls(
            success=False,
            data=None,
            error=error,
            warnings=warnings or [],
            metadata=metadata or {}
        )
    
    @classmethod
    def from_exception(cls, exception: Exception, code: ErrorCode = ErrorCode.UNKNOWN_ERROR) -> 'ServiceResult[T]':
        """从异常创建失败结果"""
        return cls.failure(
            error=ErrorDetail(
                code=code,
                message=str(exception),
                context={'exception_type': type(exception).__name__}
            )
        )
    
    def is_success(self) -> bool:
        """是否成功"""
        return self.success
    
    def is_failure(self) -> bool:
        """是否失败"""
        return not self.success
    
    def get_data_or_raise(self) -> T:
        """获取数据或抛出异常"""
        if self.is_failure():
            raise ServiceException(self.error)
        return self.data
    
    def map(self, func) -> 'ServiceResult':
        """映射成功结果"""
        if self.is_success():
            try:
                new_data = func(self.data)
                return ServiceResult.success(new_data, self.warnings, self.metadata)
            except Exception as e:
                return ServiceResult.from_exception(e)
        return self
    
    def flat_map(self, func) -> 'ServiceResult':
        """扁平映射（用于链式调用）"""
        if self.is_success():
            return func(self.data)
        return self
    
    def or_else(self, default: T) -> T:
        """获取数据或返回默认值"""
        return self.data if self.is_success() else default
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        result = {
            'success': self.success,
            'warnings': self.warnings,
            'metadata': self.metadata
        }
        
        if self.is_success():
            result['data'] = self.data
        else:
            result['error'] = self.error.to_dict() if self.error else None
        
        return result
    
    def to_response(self, status_code: int = None) -> tuple:
        """转换为FastAPI响应格式"""
        if status_code is None:
            status_code = 200 if self.is_success() else 400
        
        return self.to_dict(), status_code


class ServiceException(Exception):
    """服务异常"""
    def __init__(self, error: ErrorDetail):
        self.error = error
        super().__init__(error.message)


class ValidationResult:
    """验证结果辅助类"""
    
    def __init__(self):
        self.errors: List[ErrorDetail] = []
        self.warnings: List[str] = []
    
    def add_error(self, field: str, message: str, code: ErrorCode = ErrorCode.VALIDATION_ERROR):
        """添加错误"""
        self.errors.append(ErrorDetail(
            code=code,
            message=message,
            field=field
        ))
    
    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)
    
    def is_valid(self) -> bool:
        """是否验证通过"""
        return len(self.errors) == 0
    
    def to_service_result(self, data: Any = None) -> ServiceResult:
        """转换为服务结果"""
        if self.is_valid():
            return ServiceResult.success(data=data, warnings=self.warnings)
        else:
            # 合并所有错误信息
            combined_message = "; ".join([e.message for e in self.errors])
            return ServiceResult.failure(
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=combined_message,
                    context={'errors': [e.to_dict() for e in self.errors]}
                ),
                warnings=self.warnings
            )


class ServiceResultBuilder:
    """服务结果构建器 - 用于复杂的结果构建"""
    
    def __init__(self):
        self._data = None
        self._error = None
        self._warnings = []
        self._metadata = {}
    
    def with_data(self, data: Any) -> 'ServiceResultBuilder':
        """设置数据"""
        self._data = data
        return self
    
    def with_error(self, code: ErrorCode, message: str, **kwargs) -> 'ServiceResultBuilder':
        """设置错误"""
        self._error = ErrorDetail(code=code, message=message, **kwargs)
        return self
    
    def add_warning(self, warning: str) -> 'ServiceResultBuilder':
        """添加警告"""
        self._warnings.append(warning)
        return self
    
    def add_metadata(self, key: str, value: Any) -> 'ServiceResultBuilder':
        """添加元数据"""
        self._metadata[key] = value
        return self
    
    def build(self) -> ServiceResult:
        """构建结果"""
        if self._error:
            return ServiceResult.failure(
                error=self._error,
                warnings=self._warnings,
                metadata=self._metadata
            )
        else:
            return ServiceResult.success(
                data=self._data,
                warnings=self._warnings,
                metadata=self._metadata
            )


# 便捷函数
def success(data: Any = None, **kwargs) -> ServiceResult:
    """快速创建成功结果"""
    return ServiceResult.success(data, **kwargs)


def failure(message: str, code: ErrorCode = ErrorCode.UNKNOWN_ERROR, **kwargs) -> ServiceResult:
    """快速创建失败结果"""
    return ServiceResult.failure(
        ErrorDetail(code=code, message=message),
        **kwargs
    )


def validate_and_return(validation_func, data: Any) -> ServiceResult:
    """验证并返回结果"""
    try:
        validation_func(data)
        return ServiceResult.success(data)
    except ValueError as e:
        return ServiceResult.failure(
            ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message=str(e)
            )
        )
    except Exception as e:
        return ServiceResult.from_exception(e)