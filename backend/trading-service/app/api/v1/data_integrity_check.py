"""
数据完整性检查API端点
为前端提供回测前的数据验证接口
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import get_current_user
from app.database import get_db
from app.services.data_validation_service import BacktestDataValidator
from app.services.strategy_symbol_fix_service import SmartStrategyRepairer
from app.models.market_data import MarketData
from sqlalchemy import select, distinct
from loguru import logger


router = APIRouter(prefix="/data-integrity", tags=["数据完整性检查"])


class BacktestConfigCheckRequest(BaseModel):
    """回测配置检查请求"""
    strategy_code: str
    exchange: str = "okx"
    product_type: str = "spot"
    symbols: List[str] = ["BTC/USDT"]
    timeframes: List[str] = ["1h"]
    start_date: str
    end_date: str


class DataAvailabilityResponse(BaseModel):
    """数据可用性响应"""
    status: str  # "valid", "warning", "error"
    message: str
    details: Dict[str, Any]
    suggestions: List[str] = []
    can_proceed: bool = False
    corrected_config: Optional[Dict[str, Any]] = None
    strategy_fixes: Optional[Dict[str, Any]] = None


@router.post("/check-backtest-config", response_model=DataAvailabilityResponse)
async def check_backtest_config(
    request: BacktestConfigCheckRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    检查回测配置的数据完整性
    在用户开始回测前进行预验证，提供友好的错误提示和修复建议
    """
    try:
        logger.info(f"用户 {current_user.id} 请求数据完整性检查")
        
        # 1. 获取数据库中可用的数据
        available_data_query = select(
            distinct(MarketData.symbol),
            MarketData.exchange,
            MarketData.timeframe
        ).where(
            MarketData.exchange == request.exchange.lower()
        )
        
        result = await db.execute(available_data_query)
        available_data = [
            {
                "symbol": row[0],
                "exchange": row[1], 
                "timeframe": row[2]
            }
            for row in result.all()
        ]
        
        # 2. 进行综合验证
        config_dict = {
            "exchange": request.exchange,
            "symbols": request.symbols,
            "timeframes": request.timeframes,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "product_type": request.product_type
        }
        
        validation_result = await BacktestDataValidator.comprehensive_validation(
            db=db,
            strategy_code=request.strategy_code,
            config=config_dict
        )
        
        # 3. 如果验证失败，尝试智能修复
        strategy_fixes = None
        if not validation_result["valid"]:
            repair_result = await SmartStrategyRepairer.auto_repair_strategy_for_backtest(
                strategy_code=request.strategy_code,
                user_config=config_dict,
                available_data=available_data
            )
            
            if repair_result["success"]:
                strategy_fixes = {
                    "can_auto_fix": repair_result["can_proceed"],
                    "changes": repair_result["changes_made"],
                    "fixed_code": repair_result["fixed_code"],
                    "validation_results": repair_result["validation_results"]
                }
        
        # 4. 根据验证结果生成响应
        if validation_result["valid"]:
            return DataAvailabilityResponse(
                status="valid",
                message="✅ 配置验证通过，可以开始回测",
                details={
                    "available_symbols": [data["symbol"] for data in available_data],
                    "config_symbols": request.symbols,
                    "data_count": len(available_data)
                },
                can_proceed=True,
                corrected_config=validation_result.get("corrected_config")
            )
        
        elif strategy_fixes and strategy_fixes["can_auto_fix"]:
            return DataAvailabilityResponse(
                status="warning",
                message="⚠️ 发现配置问题，但可以自动修复",
                details={
                    "errors": validation_result["errors"],
                    "available_symbols": [data["symbol"] for data in available_data]
                },
                suggestions=[
                    "系统已自动修复策略代码中的交易对不匹配问题",
                    "点击'应用修复'使用修正后的配置",
                    *validation_result.get("suggestions", [])
                ],
                can_proceed=True,
                corrected_config=validation_result.get("corrected_config"),
                strategy_fixes=strategy_fixes
            )
        
        else:
            return DataAvailabilityResponse(
                status="error", 
                message="❌ 数据完整性验证失败",
                details={
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", []),
                    "available_symbols": [data["symbol"] for data in available_data]
                },
                suggestions=validation_result.get("suggestions", []),
                can_proceed=False
            )
    
    except Exception as e:
        logger.error(f"数据完整性检查失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"数据完整性检查过程出错: {str(e)}"
        )


@router.get("/available-data")
async def get_available_data(
    exchange: str = "okx",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取数据库中可用的市场数据概览
    帮助用户了解可以回测的交易对和时间框架
    """
    try:
        query = select(
            MarketData.symbol,
            MarketData.timeframe,
            MarketData.exchange
        ).where(
            MarketData.exchange == exchange.lower()
        ).distinct()
        
        result = await db.execute(query)
        data = result.all()
        
        # 按交易对分组
        symbols_data = {}
        for row in data:
            symbol, timeframe, exchange = row
            if symbol not in symbols_data:
                symbols_data[symbol] = {
                    "symbol": symbol,
                    "exchange": exchange,
                    "timeframes": [],
                    "data_count": 0
                }
            symbols_data[symbol]["timeframes"].append(timeframe)
        
        # 获取每个交易对的数据量
        for symbol in symbols_data:
            count_query = select(MarketData).where(
                MarketData.exchange == exchange.lower(),
                MarketData.symbol == symbol
            )
            count_result = await db.execute(count_query)
            symbols_data[symbol]["data_count"] = len(count_result.scalars().all())
        
        return {
            "exchange": exchange.upper(),
            "total_symbols": len(symbols_data),
            "symbols": list(symbols_data.values()),
            "message": f"找到 {len(symbols_data)} 个可用交易对"
        }
        
    except Exception as e:
        logger.error(f"获取可用数据失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取可用数据失败: {str(e)}"
        )


@router.post("/apply-strategy-fix")
async def apply_strategy_fix(
    request: BacktestConfigCheckRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    应用策略代码的自动修复
    返回修复后的策略代码和配置
    """
    try:
        # 获取可用数据
        available_data_query = select(
            distinct(MarketData.symbol),
            MarketData.exchange,
            MarketData.timeframe
        ).where(
            MarketData.exchange == request.exchange.lower()
        )
        
        result = await db.execute(available_data_query)
        available_data = [
            {
                "symbol": row[0],
                "exchange": row[1],
                "timeframe": row[2]
            }
            for row in result.all()
        ]
        
        config_dict = {
            "exchange": request.exchange,
            "symbols": request.symbols,
            "timeframes": request.timeframes,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "product_type": request.product_type
        }
        
        # 应用智能修复
        repair_result = await SmartStrategyRepairer.auto_repair_strategy_for_backtest(
            strategy_code=request.strategy_code,
            user_config=config_dict,
            available_data=available_data
        )
        
        if not repair_result["success"]:
            raise HTTPException(
                status_code=400,
                detail="策略修复失败"
            )
        
        return {
            "success": True,
            "fixed_strategy_code": repair_result["fixed_code"],
            "changes_made": repair_result["changes_made"],
            "validation_results": repair_result["validation_results"],
            "message": "策略代码已成功修复",
            "can_proceed_with_backtest": repair_result["can_proceed"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用策略修复失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"应用策略修复失败: {str(e)}"
        )