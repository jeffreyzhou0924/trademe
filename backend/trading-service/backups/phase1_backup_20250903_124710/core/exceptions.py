"""
自定义异常类 - 用于系统错误处理
"""

from typing import Optional, Any


class TrademeException(Exception):
    """Trademe系统基础异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)


class SecurityError(TrademeException):
    """安全相关异常"""
    pass


class PermissionError(TrademeException):
    """权限相关异常"""
    pass


class AuthenticationError(TrademeException):
    """认证相关异常"""
    pass


class TokenBlacklistError(TrademeException):
    """Token黑名单相关异常"""
    pass


class WalletError(TrademeException):
    """钱包相关异常"""
    pass


class BlockchainError(TrademeException):
    """区块链相关异常"""
    pass


class PaymentError(TrademeException):
    """支付相关异常"""
    pass


class ValidationError(TrademeException):
    """数据验证异常"""
    pass


class NetworkError(TrademeException):
    """网络连接异常"""
    pass


class UserManagementError(TrademeException):
    """用户管理相关异常"""
    pass


class TradingError(TrademeException):
    """交易相关异常"""
    pass


class ExchangeError(TrademeException):
    """交易所相关异常"""
    pass


class DataCollectionError(TrademeException):
    """数据采集相关异常"""
    pass


class APIError(TrademeException):
    """API相关异常"""
    pass


class APIException(Exception):
    """API异常，包含HTTP状态码"""
    
    def __init__(self, status_code: int, message: str, details: Optional[Any] = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(self.message)