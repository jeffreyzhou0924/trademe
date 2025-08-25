"""
策略相关数据模式
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime
import json


class StrategyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="策略名称")
    description: Optional[str] = Field(None, max_length=500, description="策略描述")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="策略参数")
    strategy_type: Literal["strategy", "indicator"] = Field(default="strategy", description="类型：策略或指标")


class StrategyCreate(StrategyBase):
    code: str = Field(..., min_length=10, description="策略代码")
    ai_session_id: Optional[str] = Field(None, description="关联的AI会话ID")


class StrategyFromAI(BaseModel):
    """从AI会话创建策略/指标"""
    name: str = Field(..., min_length=1, max_length=100, description="策略/指标名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    code: str = Field(..., min_length=10, description="代码")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="参数")
    strategy_type: Literal["strategy", "indicator"] = Field(..., description="类型：策略或指标")
    ai_session_id: str = Field(..., description="AI会话ID")


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    code: Optional[str] = Field(None, min_length=10)
    parameters: Optional[Dict[str, Any]] = None
    strategy_type: Optional[Literal["strategy", "indicator"]] = None
    is_active: Optional[bool] = None


class StrategyResponse(StrategyBase):
    id: int
    user_id: int
    code: str
    ai_session_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @field_validator('parameters', mode='before')
    @classmethod
    def parse_parameters(cls, v: Union[str, dict, None]) -> Dict[str, Any]:
        """将JSON字符串转换为字典"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return {}
    
    class Config:
        from_attributes = True


class StrategyList(BaseModel):
    strategies: List[StrategyResponse]
    total: int
    skip: int
    limit: int


class StrategyExecution(BaseModel):
    strategy_id: int
    execution_type: str
    status: str
    execution_id: Optional[str] = None
    message: str