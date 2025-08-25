"""
会员管理相关的数据模式
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserStats(BaseModel):
    """用户使用统计"""
    api_keys_count: int
    api_keys_limit: int
    ai_usage_today: float
    ai_daily_limit: float
    tick_backtest_today: int
    tick_backtest_limit: int
    storage_used: float  # MB
    storage_limit: float  # MB
    indicators_count: int
    indicators_limit: int
    strategies_count: int
    strategies_limit: int
    live_trading_count: int
    live_trading_limit: int


class MembershipLimits(BaseModel):
    """会员等级限制"""
    membership_level: str
    api_keys_limit: int
    ai_daily_limit: float
    tick_backtest_limit: int
    storage_limit: float  # MB
    indicators_limit: int
    strategies_limit: int
    live_trading_limit: int


class UsageStatsResponse(BaseModel):
    """使用统计响应"""
    success: bool
    data: UserStats
    message: str = "获取成功"


class MembershipResponse(BaseModel):
    """会员信息响应"""
    success: bool
    data: dict
    message: str = "获取成功"