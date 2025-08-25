"""
分层回测API端点
为不同等级用户提供差异化的回测服务
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.strategy import Strategy
from app.schemas.user import UserResponse
from app.schemas.strategy import StrategyResponse
from app.services.tiered_backtest_service import (
    tiered_backtest_service, 
    UserTier, 
    DataPrecision
)
from app.middleware.auth import get_current_user
from loguru import logger

router = APIRouter(prefix="/tiered-backtests", tags=["分层回测"])


# Pydantic 模型定义
class TieredBacktestRequest(BaseModel):
    """分层回测请求模型"""
    strategy_id: int = Field(..., description="策略ID")
    symbol: str = Field("BTC/USDT", description="交易对")
    exchange: str = Field("binance", description="交易所")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    initial_capital: float = Field(10000.0, gt=0, description="初始资金")
    timeframe: Optional[str] = Field("1h", description="时间框架(Basic用户)")
    force_precision: Optional[str] = Field(None, description="强制精度(测试用)")


class TierInfoResponse(BaseModel):
    """用户等级信息响应"""
    tier: str = Field(..., description="用户等级")
    data_precision: str = Field(..., description="数据精度")
    features: List[str] = Field(..., description="可用功能")
    limits: Dict[str, Any] = Field(..., description="使用限制")


class BacktestResultResponse(BaseModel):
    """回测结果响应"""
    user_tier: str = Field(..., description="用户等级")
    data_precision: str = Field(..., description="数据精度")
    strategy_id: int = Field(..., description="策略ID")
    symbol: str = Field(..., description="交易对")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    initial_capital: float = Field(..., description="初始资金")
    final_capital: float = Field(..., description="最终资金")
    performance: Dict[str, Any] = Field(..., description="性能指标")
    features_used: List[str] = Field(..., description="使用的功能")
    backtest_timestamp: str = Field(..., description="回测时间戳")


@router.get("/tier-info", response_model=TierInfoResponse)
async def get_user_tier_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的等级信息"""
    try:
        # 确定用户等级
        user_tier = tiered_backtest_service._determine_user_tier(current_user)
        
        # 获取等级信息
        tier_info = tiered_backtest_service.get_tier_info(user_tier)
        
        return TierInfoResponse(
            tier=tier_info["tier"],
            data_precision=tier_info["data_precision"],
            features=tier_info["features"],
            limits=tier_info["limits"]
        )
        
    except Exception as e:
        logger.error(f"获取用户等级信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取等级信息失败: {str(e)}"
        )


@router.post("/run", response_model=BacktestResultResponse)
async def run_tiered_backtest(
    request: TieredBacktestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """运行分层回测"""
    try:
        logger.info(f"用户{current_user.id}请求分层回测: 策略{request.strategy_id}")
        
        # 1. 验证策略所有权
        strategy = await _get_user_strategy(db, request.strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="策略不存在或无权访问"
            )
        
        # 2. 准备回测参数
        backtest_params = {
            "strategy_id": request.strategy_id,
            "symbol": request.symbol,
            "exchange": request.exchange,
            "start_date": datetime.combine(request.start_date, datetime.min.time()),
            "end_date": datetime.combine(request.end_date, datetime.min.time()),
            "initial_capital": request.initial_capital,
            "timeframe": request.timeframe,
            "db": db
        }
        
        # 3. 执行分层回测
        result = await tiered_backtest_service.run_tiered_backtest(
            user=current_user,
            strategy=strategy,
            params=backtest_params
        )
        
        # 4. 格式化响应
        return BacktestResultResponse(
            user_tier=result["user_tier"],
            data_precision=result["data_precision"],
            strategy_id=result["strategy_id"],
            symbol=result["symbol"],
            start_date=result["start_date"],
            end_date=result["end_date"],
            initial_capital=result["initial_capital"],
            final_capital=result["final_capital"],
            performance=result["performance"],
            features_used=result["features_used"],
            backtest_timestamp=result["backtest_timestamp"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分层回测失败: 用户{current_user.id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回测执行失败: {str(e)}"
        )


@router.get("/supported-precisions")
async def get_supported_precisions(
    current_user: User = Depends(get_current_user)
):
    """获取用户支持的数据精度"""
    try:
        user_tier = tiered_backtest_service._determine_user_tier(current_user)
        tier_info = tiered_backtest_service.get_tier_info(user_tier)
        
        precision_details = {
            "kline": {
                "name": "K线级",
                "description": "基于OHLCV数据的标准回测",
                "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "accuracy": "中等",
                "cost": "低"
            },
            "second": {
                "name": "秒级聚合",
                "description": "基于秒级聚合数据的高精度回测",
                "timeframes": ["1s", "5s", "15s", "30s"] + ["1m", "5m", "15m", "1h", "4h", "1d"],
                "accuracy": "高",
                "cost": "中等"
            },
            "tick_sim": {
                "name": "Tick模拟",
                "description": "基于高频数据模拟的超高精度回测",
                "timeframes": ["tick模拟"] + ["1s", "5s", "15s", "30s", "1m", "5m", "15m", "1h", "4h", "1d"],
                "accuracy": "很高",
                "cost": "中等"
            },
            "tick_real": {
                "name": "真实Tick",
                "description": "基于真实tick数据的极致精度回测",
                "timeframes": ["真实tick"] + ["1s", "5s", "15s", "30s", "1m", "5m", "15m", "1h", "4h", "1d"],
                "accuracy": "极高",
                "cost": "高"
            }
        }
        
        current_precision = tier_info["data_precision"]
        supported_timeframes = tier_info["limits"]["supported_timeframes"]
        
        return {
            "user_tier": user_tier.value,
            "current_precision": current_precision,
            "precision_details": precision_details[current_precision],
            "supported_timeframes": supported_timeframes,
            "upgrade_benefits": _get_upgrade_benefits(user_tier)
        }
        
    except Exception as e:
        logger.error(f"获取支持精度失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取精度信息失败: {str(e)}"
        )


@router.get("/precision-comparison")
async def get_precision_comparison():
    """获取不同精度的对比信息"""
    try:
        comparison = {
            "precisions": [
                {
                    "level": "basic",
                    "name": "K线级回测",
                    "data_type": "OHLCV K线",
                    "min_timeframe": "1分钟",
                    "accuracy": "★★★☆☆",
                    "speed": "★★★★★",
                    "cost": "★☆☆☆☆",
                    "suitable_for": ["长线策略", "日内策略", "初学者"],
                    "limitations": ["无法捕捉分钟内价格变化", "滑点模拟简化"]
                },
                {
                    "level": "pro",
                    "name": "混合精度回测",
                    "data_type": "自适应秒级+Tick模拟",
                    "min_timeframe": "1秒",
                    "accuracy": "★★★★☆",
                    "speed": "★★★☆☆",
                    "cost": "★★☆☆☆",
                    "suitable_for": ["中高频策略", "套利策略", "进阶用户"],
                    "limitations": ["部分时段使用模拟数据", "计算资源消耗较大"]
                },
                {
                    "level": "elite",
                    "name": "真实Tick回测",
                    "data_type": "真实逐笔成交+L2订单簿",
                    "min_timeframe": "毫秒级",
                    "accuracy": "★★★★★",
                    "speed": "★★☆☆☆",
                    "cost": "★★★★☆",
                    "suitable_for": ["高频策略", "做市策略", "专业交易员"],
                    "limitations": ["计算密集", "存储需求大", "成本较高"]
                }
            ],
            "use_cases": {
                "趋势跟踪策略": "basic",
                "均值回归策略": "basic",
                "动量策略": "pro",
                "套利策略": "pro",
                "做市策略": "elite",
                "高频统计套利": "elite"
            },
            "upgrade_guide": {
                "basic_to_pro": {
                    "benefits": ["精度提升50%", "支持秒级策略", "智能精度切换"],
                    "cost_increase": "$60/月",
                    "recommended_if": "策略频率 > 1次/小时"
                },
                "pro_to_elite": {
                    "benefits": ["最高精度", "真实滑点", "订单簿分析"],
                    "cost_increase": "$220/月", 
                    "recommended_if": "策略频率 > 1次/分钟"
                }
            }
        }
        
        return comparison
        
    except Exception as e:
        logger.error(f"获取精度对比失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取对比信息失败: {str(e)}"
        )


@router.post("/demo-comparison")
async def run_demo_comparison(
    request: TieredBacktestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """运行演示对比 - 同时展示不同精度的回测结果"""
    try:
        logger.info(f"用户{current_user.id}请求演示对比")
        
        # 验证策略
        strategy = await _get_user_strategy(db, request.strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="策略不存在或无权访问"
            )
        
        # 准备基础参数
        base_params = {
            "strategy_id": request.strategy_id,
            "symbol": request.symbol,
            "exchange": request.exchange,
            "start_date": datetime.combine(request.start_date, datetime.min.time()),
            "end_date": datetime.combine(request.end_date, datetime.min.time()),
            "initial_capital": request.initial_capital,
            "timeframe": request.timeframe,
            "db": db
        }
        
        # 运行不同精度的回测对比
        results = {}
        
        # Basic回测
        basic_engine = tiered_backtest_service.engines[UserTier.BASIC]
        basic_result = await basic_engine.run_backtest(strategy, base_params)
        results["basic"] = {
            "precision": "kline",
            "performance": basic_result.get("performance", {}),
            "features": basic_result.get("features_used", [])
        }
        
        # Pro回测 (如果用户是Pro或Elite)
        current_tier = tiered_backtest_service._determine_user_tier(current_user)
        if current_tier in [UserTier.PRO, UserTier.ELITE]:
            pro_engine = tiered_backtest_service.engines[UserTier.PRO]
            pro_result = await pro_engine.run_backtest(strategy, base_params)
            results["pro"] = {
                "precision": "hybrid",
                "performance": pro_result.get("performance", {}),
                "features": pro_result.get("features_used", []),
                "precision_breakdown": pro_result.get("precision_breakdown", {})
            }
        
        # Elite回测 (如果用户是Elite)
        if current_tier == UserTier.ELITE:
            elite_engine = tiered_backtest_service.engines[UserTier.ELITE]
            elite_result = await elite_engine.run_backtest(strategy, base_params)
            results["elite"] = {
                "precision": "tick_real",
                "performance": elite_result.get("performance", {}),
                "features": elite_result.get("features_used", []),
                "execution_analytics": elite_result.get("execution_analytics", {})
            }
        
        # 生成对比分析
        comparison_analysis = _analyze_precision_differences(results)
        
        return {
            "user_tier": current_tier.value,
            "comparison_results": results,
            "analysis": comparison_analysis,
            "recommendations": _get_upgrade_recommendations(current_tier, comparison_analysis)
        }
        
    except Exception as e:
        logger.error(f"演示对比失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对比分析失败: {str(e)}"
        )


# 辅助函数
async def _get_user_strategy(db: AsyncSession, strategy_id: int, user_id: int) -> Optional[Strategy]:
    """获取用户策略"""
    from sqlalchemy import select
    
    query = select(Strategy).where(
        Strategy.id == strategy_id,
        Strategy.user_id == user_id
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _get_upgrade_benefits(current_tier: UserTier) -> Dict[str, Any]:
    """获取升级收益"""
    benefits = {
        UserTier.BASIC: {
            "next_tier": "pro",
            "benefits": [
                "精度提升50%以上",
                "支持秒级策略",
                "智能精度切换",
                "更长历史数据",
                "更多并发回测"
            ],
            "cost": "+$60/月"
        },
        UserTier.PRO: {
            "next_tier": "elite", 
            "benefits": [
                "真实tick级精度",
                "订单簿深度分析",
                "精确滑点计算",
                "市场冲击分析",
                "无限策略复杂度"
            ],
            "cost": "+$220/月"
        },
        UserTier.ELITE: {
            "next_tier": None,
            "benefits": ["您已享受最高等级服务"],
            "cost": "无需升级"
        }
    }
    return benefits.get(current_tier, {})


def _analyze_precision_differences(results: Dict[str, Any]) -> Dict[str, Any]:
    """分析不同精度的差异"""
    analysis = {
        "return_improvement": {},
        "risk_reduction": {},
        "execution_quality": {}
    }
    
    if "basic" in results and "pro" in results:
        basic_perf = results["basic"]["performance"]
        pro_perf = results["pro"]["performance"]
        
        return_diff = pro_perf.get("total_return", 0) - basic_perf.get("total_return", 0)
        analysis["return_improvement"]["pro_vs_basic"] = {
            "absolute": return_diff,
            "relative": return_diff / max(basic_perf.get("total_return", 0.01), 0.01),
            "significance": "显著" if abs(return_diff) > 0.01 else "一般"
        }
    
    return analysis


def _get_upgrade_recommendations(current_tier: UserTier, analysis: Dict[str, Any]) -> List[str]:
    """获取升级建议"""
    recommendations = []
    
    if current_tier == UserTier.BASIC:
        recommendations = [
            "如果您的策略交易频率较高(>1次/小时)，建议升级至Pro版本",
            "Pro版本的混合精度可显著提升回测准确性",
            "2年历史数据支持更全面的策略验证"
        ]
    elif current_tier == UserTier.PRO:
        recommendations = [
            "如果您从事高频交易(>1次/分钟)，建议升级至Elite版本",
            "Elite版本提供真实tick数据，精度最高",
            "订单簿分析和滑点计算对高频策略至关重要"
        ]
    
    return recommendations