"""
交易相关数据模式
包含实盘交易相关的完整数据结构
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Literal
from datetime import datetime
from decimal import Decimal


class TradeResponse(BaseModel):
    id: int
    user_id: int
    strategy_id: int
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    total_amount: Decimal
    fee: Decimal
    trade_type: str
    executed_at: datetime
    
    class Config:
        from_attributes = True


class TradeList(BaseModel):
    trades: List[TradeResponse]
    total: int
    skip: int
    limit: int


class TradingPosition(BaseModel):
    symbol: str
    exchange: str
    side: str
    quantity: Decimal
    avg_price: Decimal
    unrealized_pnl: Decimal

# 实盘交易相关Schema定义
class OrderRequest(BaseModel):
    """下单请求"""
    exchange: str
    symbol: str
    order_type: Literal['market', 'limit']
    side: Literal['buy', 'sell']
    amount: float
    price: Optional[float] = None

class Order(BaseModel):
    """订单信息"""
    id: str
    user_id: int
    exchange: str
    symbol: str
    side: Literal['buy', 'sell']
    order_type: Literal['market', 'limit']
    quantity: float
    price: Optional[float] = None
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: Literal['pending', 'submitted', 'open', 'filled', 'canceled', 'rejected', 'failed']
    exchange_order_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    fees: float = 0.0
    error_message: Optional[str] = None

class Position(BaseModel):
    """持仓信息"""
    symbol: str
    exchange: str
    quantity: float
    avg_cost: float
    total_cost: float
    current_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    pnl_percent: float
    trade_count: int
    first_trade_at: datetime
    last_trade_at: datetime

class TradingAccount(BaseModel):
    """交易账户信息"""
    user_id: int
    exchange: str
    api_key_configured: bool
    balance: Dict[str, Dict[str, float]]  # {currency: {total, free, used}}
    last_updated: datetime

class TradingSummary(BaseModel):
    """交易统计汇总"""
    period_days: int
    total_trades: int
    buy_trades: int
    sell_trades: int
    total_volume: float
    total_fees: float
    profit_trades: int
    loss_trades: int
    win_rate: float
    total_pnl: float
    avg_trade_size: float
    largest_win: float
    largest_loss: float
    trading_symbols: List[str]
    exchanges_used: List[str]

class DailyPnL(BaseModel):
    """每日盈亏数据"""
    date: str
    trades_count: int
    volume: float
    fees: float
    pnl: float
    cumulative_pnl: float

class TradingSession(BaseModel):
    """交易会话"""
    id: str
    user_id: int
    strategy_id: Optional[int] = None
    exchange: str
    symbols: List[str]
    status: Literal['inactive', 'active', 'paused', 'stopping', 'stopped', 'error']
    execution_mode: Literal['manual', 'semi_auto', 'full_auto']
    max_daily_trades: int
    max_open_positions: int
    total_trades: int = 0
    daily_pnl: float = 0.0
    created_at: datetime
    started_at: Optional[datetime] = None
    error_message: Optional[str] = None

class OrderStatistics(BaseModel):
    """订单统计"""
    period_days: int
    active_orders_count: int
    total_orders: int
    filled_orders: int
    canceled_orders: int
    failed_orders: int
    fill_rate: float
    total_volume: float
    total_fees: float
    symbols_traded: List[str]
    exchanges_used: List[str]
    avg_order_size: float

class RiskAssessment(BaseModel):
    """风险评估结果"""
    approved: bool
    risk_level: Literal['low', 'medium', 'high', 'critical']
    risk_score: float
    violations: List[str]
    warnings: List[str]
    suggested_position_size: Optional[float] = None
    max_allowed_size: Optional[float] = None