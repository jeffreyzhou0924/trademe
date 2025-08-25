"""
回测相关数据模式
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from decimal import Decimal


class BacktestCreate(BaseModel):
    strategy_id: int = Field(..., gt=0, description="策略ID")
    start_date: date = Field(..., description="回测开始日期")
    end_date: date = Field(..., description="回测结束日期")
    initial_capital: Decimal = Field(..., gt=0, description="初始资金")


class BacktestResponse(BaseModel):
    id: int
    strategy_id: int
    user_id: int
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_capital: Optional[Decimal]
    total_return: Optional[Decimal]
    max_drawdown: Optional[Decimal]
    sharpe_ratio: Optional[Decimal]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class BacktestList(BaseModel):
    backtests: List[BacktestResponse]
    total: int
    skip: int
    limit: int


class BacktestAnalysis(BaseModel):
    backtest_id: int
    performance_metrics: Dict[str, Any]
    trade_statistics: Dict[str, Any]
    risk_metrics: Dict[str, Any]


class BacktestCompare(BaseModel):
    comparison_metrics: Dict[str, Any]
    best_performer: int
    summary: str