"""
Trademe Trading Service - 交易管理API

提供交易记录查询、实盘交易管理等功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, date

from app.database import get_db
from app.schemas.trade import TradeResponse, TradeList, TradingPosition
from app.services.trade_service import TradeService
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=TradeList)
async def get_trades(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(50, ge=1, le=500, description="返回记录数"),
    strategy_id: Optional[int] = Query(None, description="策略ID筛选"),
    exchange: Optional[str] = Query(None, description="交易所筛选"),
    symbol: Optional[str] = Query(None, description="交易对筛选"),
    trade_type: Optional[str] = Query(None, description="交易类型筛选"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取交易记录"""
    try:
        trades = await TradeService.get_user_trades(
            db, current_user.id, skip=skip, limit=limit,
            strategy_id=strategy_id, exchange=exchange, symbol=symbol,
            trade_type=trade_type, start_date=start_date, end_date=end_date
        )
        total = await TradeService.count_user_trades(
            db, current_user.id, strategy_id=strategy_id, exchange=exchange,
            symbol=symbol, trade_type=trade_type, start_date=start_date, end_date=end_date
        )
        
        return TradeList(
            trades=trades,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易记录失败: {str(e)}")


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个交易详情"""
    try:
        trade = await TradeService.get_trade_by_id(db, trade_id, current_user.id)
        if not trade:
            raise HTTPException(status_code=404, detail="交易记录不存在")
        
        return trade
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易详情失败: {str(e)}")


@router.get("/positions/current")
async def get_current_positions(
    exchange: Optional[str] = Query(None, description="交易所筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前持仓"""
    try:
        positions = await TradeService.get_current_positions(
            db, current_user.id, exchange=exchange
        )
        return {"positions": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓失败: {str(e)}")


@router.get("/statistics/summary")
async def get_trading_summary(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取交易统计摘要"""
    try:
        summary = await TradeService.get_trading_summary(db, current_user.id, days)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易统计失败: {str(e)}")


@router.get("/pnl/daily")
async def get_daily_pnl(
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取每日盈亏"""
    try:
        pnl_data = await TradeService.get_daily_pnl(db, current_user.id, days)
        return {"daily_pnl": pnl_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取每日盈亏失败: {str(e)}")


@router.post("/manual")
async def create_manual_trade(
    trade_data: dict,  # 手动交易数据
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建手动交易记录"""
    try:
        # TODO: 实现手动交易记录创建
        return {"message": "手动交易记录创建功能待实现"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建手动交易失败: {str(e)}")