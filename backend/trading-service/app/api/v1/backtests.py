"""
Trademe Trading Service - 回测API

提供策略回测的创建、查询、分析等功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, date

from app.database import get_db
from app.schemas.backtest import (
    BacktestCreate, BacktestResponse, BacktestList, 
    BacktestAnalysis, BacktestCompare
)
from app.services.backtest_service import BacktestService
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=BacktestList)
async def get_backtests(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    strategy_id: Optional[int] = Query(None, description="策略ID筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的回测列表"""
    try:
        backtests = await BacktestService.get_user_backtests(
            db, current_user.id, skip=skip, limit=limit, 
            strategy_id=strategy_id, status=status
        )
        total = await BacktestService.count_user_backtests(
            db, current_user.id, strategy_id=strategy_id, status=status
        )
        
        return BacktestList(
            backtests=backtests,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取回测列表失败: {str(e)}")


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个回测详情"""
    try:
        backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        
        return backtest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取回测失败: {str(e)}")


@router.post("/", response_model=BacktestResponse)
async def create_backtest(
    backtest_data: BacktestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新回测"""
    try:
        # 验证日期范围
        if backtest_data.start_date >= backtest_data.end_date:
            raise HTTPException(status_code=422, detail="开始日期必须早于结束日期")
        
        # 验证策略存在且属于当前用户
        from app.services.strategy_service import StrategyService
        strategy = await StrategyService.get_strategy_by_id(
            db, backtest_data.strategy_id, current_user.id
        )
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        backtest = await BacktestService.create_backtest(db, backtest_data, current_user.id)
        
        # 异步启动回测任务（传递用户配置的交易所/交易对/周期）
        # 旧实现中 start_backtest_task 只是占位；实际任务在 create_backtest 中启动
        # 这里保持调用以兼容日志，但无需再次创建任务
        await BacktestService.start_backtest_task(backtest.id)
        
        return backtest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建回测失败: {str(e)}")


@router.post("/{backtest_id}/stop")
async def stop_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止回测"""
    try:
        backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        
        if backtest.status != "RUNNING":
            raise HTTPException(status_code=422, detail="回测未在运行中")
        
        result = await BacktestService.stop_backtest(db, backtest_id)
        return {"message": "回测已停止", "details": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止回测失败: {str(e)}")


@router.get("/{backtest_id}/analysis", response_model=BacktestAnalysis)
async def get_backtest_analysis(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取回测分析报告"""
    try:
        backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        
        if backtest.status != "COMPLETED":
            raise HTTPException(status_code=422, detail="回测尚未完成")
        
        analysis = await BacktestService.get_detailed_analysis(db, backtest_id)
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取回测分析失败: {str(e)}")


@router.get("/{backtest_id}/trades")
async def get_backtest_trades(
    backtest_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取回测交易记录"""
    try:
        backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        
        trades = await BacktestService.get_backtest_trades(
            db, backtest_id, skip=skip, limit=limit
        )
        return trades
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取回测交易记录失败: {str(e)}")


@router.post("/compare", response_model=BacktestCompare)
async def compare_backtests(
    backtest_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """比较多个回测结果"""
    try:
        if len(backtest_ids) < 2:
            raise HTTPException(status_code=422, detail="至少需要2个回测进行比较")
        
        if len(backtest_ids) > 5:
            raise HTTPException(status_code=422, detail="最多只能比较5个回测")
        
        # 验证所有回测都属于当前用户
        for backtest_id in backtest_ids:
            backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
            if not backtest:
                raise HTTPException(status_code=404, detail=f"回测 {backtest_id} 不存在")
        
        comparison = await BacktestService.compare_backtests(db, backtest_ids)
        return comparison
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"比较回测失败: {str(e)}")


@router.delete("/{backtest_id}")
async def delete_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除回测"""
    try:
        backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        
        if backtest.status == "RUNNING":
            raise HTTPException(status_code=409, detail="正在运行的回测无法删除")
        
        await BacktestService.delete_backtest(db, backtest_id)
        return {"message": "回测删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除回测失败: {str(e)}")
