"""
用户Claude Key相关的Pydantic schemas
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal


class UserClaudeKeyCreate(BaseModel):
    """创建用户Claude Key请求"""
    key_name: str
    description: Optional[str] = None
    daily_request_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None  
    daily_cost_limit: Optional[float] = None


class UserClaudeKeyUpdate(BaseModel):
    """更新用户Claude Key请求"""
    key_name: Optional[str] = None
    description: Optional[str] = None
    daily_request_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None
    daily_cost_limit: Optional[float] = None


class UserClaudeKeyResponse(BaseModel):
    """用户Claude Key响应"""
    id: int
    key_name: str
    virtual_key: str
    status: str
    description: Optional[str] = None
    
    # 使用统计
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    
    # 当日统计
    today_requests: int
    today_tokens: int
    today_cost_usd: float
    
    # 限制配置
    daily_request_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None
    daily_cost_limit: Optional[float] = None
    
    # 时间信息
    last_used_at: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None

    class Config:
        from_attributes = True


class UsageRecord(BaseModel):
    """使用记录"""
    timestamp: str
    request_type: str
    ai_mode: Optional[str] = None
    tokens: int
    cost_usd: float
    success: bool
    response_time_ms: Optional[int] = None


class KeyUsageStats(BaseModel):
    """单个密钥使用统计"""
    key_id: int
    key_name: str
    virtual_key: str
    status: str
    requests: int
    tokens: int
    cost_usd: float
    today_requests: int
    today_tokens: int
    today_cost_usd: float
    last_used_at: Optional[str] = None


class TodayUsage(BaseModel):
    """今日使用统计"""
    requests: int
    tokens: int
    cost_usd: float


class UsageStatisticsResponse(BaseModel):
    """用户Claude使用统计响应"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    total_cost_usd: float
    today_usage: TodayUsage
    keys_count: int
    by_key: List[KeyUsageStats]
    recent_usage: List[UsageRecord]


class LimitsCheckResponse(BaseModel):
    """使用限制检查响应"""
    can_proceed: bool
    limit_exceeded: List[str]
    remaining: Dict[str, Any]
    warnings: List[str]


class ClaudeRequestRoute(BaseModel):
    """Claude请求路由信息"""
    user_key_id: int
    claude_account_id: int
    account_name: str
    proxy_used: bool
    estimated_cost: float