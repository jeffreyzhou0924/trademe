"""
AI相关数据模式
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum


class AIMode(str, Enum):
    """AI模式枚举"""
    DEVELOPER = "developer"  # 开发者模式
    TRADER = "trader"       # 交易员模式


class SessionType(str, Enum):
    """会话类型枚举"""
    STRATEGY = "strategy"    # 策略开发
    INDICATOR = "indicator"  # 指标开发
    GENERAL = "general"      # 通用对话


class SessionStatus(str, Enum):
    """会话状态枚举"""
    ACTIVE = "active"        # 活跃
    COMPLETED = "completed"  # 已完成
    ARCHIVED = "archived"    # 已归档


class ChatMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="消息内容")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文信息")
    session_id: Optional[str] = Field(None, description="会话ID")
    ai_mode: Optional[AIMode] = Field(AIMode.DEVELOPER, description="AI模式")
    session_type: Optional[SessionType] = Field(SessionType.GENERAL, description="会话类型")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tokens_used: int
    model: str
    cost_usd: float = Field(0.0, description="本次对话消耗金额")


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    name: str = Field(..., min_length=1, max_length=100, description="会话名称")
    ai_mode: AIMode = Field(..., description="AI模式")
    session_type: SessionType = Field(..., description="会话类型")
    description: Optional[str] = Field(None, max_length=500, description="会话描述")


class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    name: str
    ai_mode: str
    session_type: str
    status: str
    created_at: str


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    name: str
    ai_mode: str
    session_type: str
    status: str
    progress: int = Field(0, description="完成进度百分比")
    message_count: int = Field(0, description="消息数量")
    last_message: Optional[str] = Field(None, description="最后一条消息")
    cost_total: float = Field(0.0, description="总消耗金额")
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: List[SessionInfo]
    total_count: int
    ai_mode: str


class UsageStatsResponse(BaseModel):
    """AI使用统计响应"""
    period_days: int
    total_requests: int
    total_cost_usd: float
    daily_cost_usd: float
    monthly_cost_usd: float
    remaining_daily_quota: float
    remaining_monthly_quota: float
    by_feature: Dict[str, Any]
    by_session: Dict[str, Any]


class StrategyGenerateRequest(BaseModel):
    description: str = Field(..., min_length=10, description="策略描述")
    indicators: List[str] = Field(default_factory=list, description="使用的技术指标")
    timeframe: str = Field(default="1h", description="时间周期")
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$", description="风险级别")


class StrategyGenerateResponse(BaseModel):
    code: str
    explanation: str
    parameters: Dict[str, Any]
    warnings: List[str]


class MarketAnalysisRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=1, description="分析的交易对")
    timeframe: str = Field(default="1d", description="分析时间周期")
    analysis_type: str = Field(default="technical", description="分析类型")


class MarketAnalysisResponse(BaseModel):
    summary: str
    signals: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    recommendations: List[str]