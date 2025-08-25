"""
Trademe Trading Service - AI功能API

提供AI对话、策略生成、市场分析等AI集成功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import asyncio

from app.database import get_db
from app.schemas.ai import (
    ChatMessage, ChatResponse, StrategyGenerateRequest, 
    StrategyGenerateResponse, MarketAnalysisRequest, MarketAnalysisResponse,
    CreateSessionRequest, CreateSessionResponse, SessionListResponse, UsageStatsResponse,
    AIMode, SessionType, SessionStatus
)
from app.services.ai_service import AIService
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    message: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """与AI进行对话"""
    try:
        # 添加用户会员等级到上下文
        context = message.context or {}
        context.update({
            'membership_level': current_user.membership_level,
            'ai_mode': message.ai_mode.value if message.ai_mode else 'developer',
            'session_type': message.session_type.value if message.session_type else 'general'
        })
        
        response = await AIService.chat_completion(
            message.content, 
            user_id=current_user.id,
            context=context,
            session_id=message.session_id,
            db=db
        )
        
        # 计算本次对话成本（已在AIService中按2倍计算）
        cost_usd = response.get("tokens_used", 0) * 0.00002  # 简化计算，实际在AIService中精确计算
        
        return ChatResponse(
            response=response["content"],
            session_id=response["session_id"],
            tokens_used=response.get("tokens_used", 0),
            model=response.get("model", "claude-sonnet-4"),
            cost_usd=cost_usd
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI对话失败: {str(e)}")


@router.post("/strategy/generate", response_model=StrategyGenerateResponse)
async def generate_strategy(
    request: StrategyGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI生成交易策略"""
    try:
        strategy_code = await AIService.generate_strategy(
            description=request.description,
            indicators=request.indicators,
            timeframe=request.timeframe,
            risk_level=request.risk_level,
            user_id=current_user.id,
            db=db
        )
        
        return StrategyGenerateResponse(
            code=strategy_code["code"],
            explanation=strategy_code["explanation"],
            parameters=strategy_code.get("parameters", {}),
            warnings=strategy_code.get("warnings", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略生成失败: {str(e)}")


@router.post("/strategy/optimize")
async def optimize_strategy(
    strategy_id: int,
    optimization_target: str = Query("sharpe_ratio", description="优化目标"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI优化策略参数"""
    try:
        # 验证策略所有权
        from app.services.strategy_service import StrategyService
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        optimized_params = await AIService.optimize_strategy_parameters(
            strategy.code,
            strategy.parameters,
            optimization_target,
            user_id=current_user.id
        )
        
        return {
            "original_parameters": strategy.parameters,
            "optimized_parameters": optimized_params["parameters"],
            "expected_improvement": optimized_params.get("improvement", {}),
            "optimization_summary": optimized_params.get("summary", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略优化失败: {str(e)}")


@router.post("/market/analyze", response_model=MarketAnalysisResponse)
async def analyze_market(
    request: MarketAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI市场分析"""
    try:
        analysis = await AIService.analyze_market_conditions(
            symbols=request.symbols,
            timeframe=request.timeframe,
            analysis_type=request.analysis_type,
            user_id=current_user.id,
            db=db
        )
        
        return MarketAnalysisResponse(
            summary=analysis["summary"],
            signals=analysis.get("signals", []),
            risk_assessment=analysis.get("risk_assessment", {}),
            recommendations=analysis.get("recommendations", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"市场分析失败: {str(e)}")


@router.post("/backtest/analyze")
async def analyze_backtest_results(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI分析回测结果"""
    try:
        # 验证回测所有权
        from app.services.backtest_service import BacktestService
        backtest = await BacktestService.get_backtest_by_id(db, backtest_id, current_user.id)
        if not backtest:
            raise HTTPException(status_code=404, detail="回测不存在")
        
        if backtest.status != "COMPLETED":
            raise HTTPException(status_code=422, detail="回测尚未完成")
        
        analysis = await AIService.analyze_backtest_performance(
            backtest.results,
            user_id=current_user.id,
            db=db
        )
        
        return {
            "performance_summary": analysis["summary"],
            "strengths": analysis.get("strengths", []),
            "weaknesses": analysis.get("weaknesses", []),
            "improvement_suggestions": analysis.get("suggestions", []),
            "risk_analysis": analysis.get("risk_analysis", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测分析失败: {str(e)}")


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_chat_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建AI聊天会话"""
    try:
        # 检查用户会员等级限制
        from app.services.membership_service import MembershipService
        limits = MembershipService.get_membership_limits(current_user.membership_level)
        
        # 只对策略和指标会话检查数量限制，通用对话不限制
        if request.session_type in [SessionType.STRATEGY, SessionType.INDICATOR]:
            current_sessions = await AIService.get_user_sessions_count(
                db, current_user.id, request.ai_mode.value, request.session_type.value
            )
            
            max_sessions = limits.strategies_limit if request.session_type == SessionType.STRATEGY else limits.indicators_limit
            if current_sessions >= max_sessions:
                raise HTTPException(
                    status_code=422, 
                    detail=f"{request.session_type.value}会话数量已达上限 ({max_sessions}个)"
                )
        
        session = await AIService.create_chat_session(
            db=db,
            user_id=current_user.id,
            name=request.name,
            ai_mode=request.ai_mode.value,
            session_type=request.session_type.value,
            description=request.description
        )
        
        return CreateSessionResponse(
            session_id=session["session_id"],
            name=session["name"],
            ai_mode=session["ai_mode"],
            session_type=session["session_type"],
            status=session["status"],
            created_at=session["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/sessions", response_model=SessionListResponse)
async def get_chat_sessions(
    ai_mode: AIMode = Query(..., description="AI模式"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的聊天会话列表"""
    try:
        sessions = await AIService.get_user_chat_sessions(
            db=db,
            user_id=current_user.id,
            ai_mode=ai_mode.value
        )
        
        return SessionListResponse(
            sessions=sessions,
            total_count=len(sessions),
            ai_mode=ai_mode.value
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.put("/sessions/{session_id}/status")
async def update_session_status(
    session_id: str,
    status: SessionStatus,
    progress: Optional[int] = Query(None, ge=0, le=100, description="完成进度"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新会话状态"""
    try:
        updated = await AIService.update_session_status(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
            status=status.value,
            progress=progress
        )
        
        if not updated:
            raise HTTPException(status_code=404, detail="会话不存在或无权限访问")
        
        return {"message": "会话状态更新成功", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新会话状态失败: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除聊天会话"""
    try:
        deleted = await AIService.delete_chat_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id
        )
        
        if not deleted:
            raise HTTPException(status_code=404, detail="会话不存在或无权限访问")
        
        return {"message": "会话删除成功", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@router.get("/chat/history")
async def get_chat_history(
    session_id: Optional[str] = Query(None, description="会话ID"),
    limit: int = Query(50, ge=1, le=200, description="消息数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取聊天历史"""
    try:
        history = await AIService.get_chat_history(
            user_id=current_user.id,
            session_id=session_id,
            limit=limit,
            db=db
        )
        return {"messages": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取聊天历史失败: {str(e)}")


@router.delete("/chat/{session_id}")
async def clear_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清除聊天会话"""
    try:
        result = await AIService.clear_chat_session(current_user.id, session_id, db)
        return {"message": "会话已清除", "cleared": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除会话失败: {str(e)}")


@router.get("/usage/stats", response_model=UsageStatsResponse)
async def get_ai_usage_stats(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取AI使用统计"""
    try:
        # 获取基础统计数据
        basic_stats = await AIService.get_usage_statistics(current_user.id, days, db)
        
        # 获取每日和每月使用成本
        daily_cost = await AIService.get_daily_usage_cost(db, current_user.id)
        
        # 计算月度成本 (简化为30天内的总成本)
        monthly_cost = basic_stats.get("total_cost_usd", 0)
        
        # 获取会员限制
        from app.services.membership_service import MembershipService
        limits = MembershipService.get_membership_limits(current_user.membership_level)
        
        # 计算剩余额度
        remaining_daily = max(0, limits.ai_daily_limit - daily_cost)
        remaining_monthly = max(0, limits.ai_monthly_limit - monthly_cost) if hasattr(limits, 'ai_monthly_limit') else 0
        
        # 获取按会话的统计
        session_stats = await AIService.get_session_usage_stats(db, current_user.id, days)
        
        return UsageStatsResponse(
            period_days=days,
            total_requests=basic_stats.get("total_requests", 0),
            total_cost_usd=basic_stats.get("total_cost_usd", 0),
            daily_cost_usd=daily_cost,
            monthly_cost_usd=monthly_cost,
            remaining_daily_quota=remaining_daily,
            remaining_monthly_quota=remaining_monthly,
            by_feature=basic_stats.get("by_feature", {}),
            by_session=session_stats
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取使用统计失败: {str(e)}")


@router.post("/insights/generate")
async def generate_trading_insights(
    symbol: str,
    timeframe: str = Query("1d", description="时间周期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成交易洞察"""
    try:
        insights = await AIService.generate_trading_insights(
            symbol=symbol,
            timeframe=timeframe,
            user_id=current_user.id,
            db=db
        )
        
        return {
            "symbol": symbol,
            "insights": insights["content"],
            "confidence": insights.get("confidence", 0),
            "key_factors": insights.get("factors", []),
            "timestamp": insights.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成交易洞察失败: {str(e)}")