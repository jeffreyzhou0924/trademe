"""
通用响应模式 - API标准响应格式
"""

from typing import Generic, TypeVar, Optional, Dict, Any
from pydantic import BaseModel

T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """成功响应模式"""
    success: bool = True
    data: T
    message: str
    code: int = 200


class ErrorResponse(BaseModel):
    """错误响应模式"""
    success: bool = False
    error: str
    message: str
    code: int = 400
    details: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模式"""
    success: bool = True
    data: T
    pagination: Dict[str, Any]
    message: str = "查询成功"
    code: int = 200