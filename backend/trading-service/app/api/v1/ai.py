"""
Trademe Trading Service - AI功能API

提供AI对话、策略生成、市场分析等AI集成功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, AsyncGenerator
import asyncio
import json
import logging

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
from app.services.user_claude_key_service import UserClaudeKeyService
from app.services.websocket_manager import get_websocket_manager, WebSocketManager
from app.services.streaming_response_handler import get_streaming_handler, streaming_context

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    message: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """与AI进行对话 - 使用统一代理服务"""
    try:
        from app.services.ai_service import AIService
        
        # 创建AI服务实例
        ai_service = AIService()
        
        # 获取会话类型，如果消息中有session_type则使用，否则默认为general
        session_type = getattr(message, 'session_type', 'general')
        if hasattr(message, 'session_type') and message.session_type:
            session_type = message.session_type.value if hasattr(message.session_type, 'value') else message.session_type
        
        # 调用AI服务
        response = await ai_service.chat_completion(
            message=message.content,
            user_id=current_user.id,
            session_id=message.session_id,
            context={
                'ai_mode': message.ai_mode.value if message.ai_mode else 'developer',
                'session_type': session_type,
                'membership_level': current_user.membership_level
            },
            db=db
        )
        
        # 构建标准响应
        return ChatResponse(
            response=response.get("content", ""),
            session_id=response.get("session_id", message.session_id),
            tokens_used=response.get("tokens_used", 0),
            model=response.get("model", "claude-sonnet-4-20250514"),
            cost_usd=response.get("cost_usd", 0.0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"AI对话失败: {error_traceback}")
        raise HTTPException(status_code=500, detail=f"AI对话失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream_with_ai(
    message: ChatMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """与AI进行流式对话 - 使用现有AI服务"""
    
    async def stream_generator() -> AsyncGenerator[str, None]:
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'session_id': message.session_id})}\n\n"
            
            # 获取会话类型
            session_type = getattr(message, 'session_type', 'general')
            if hasattr(message, 'session_type') and message.session_type:
                session_type = message.session_type.value if hasattr(message.session_type, 'value') else message.session_type
            
            # 使用现有的stream_chat_completion方法
            stream_result = await ai_service.stream_chat_completion(
                message=message.content,
                user_id=current_user.id,
                session_id=message.session_id,
                context={
                    'ai_mode': message.ai_mode.value if message.ai_mode else 'developer',
                    'session_type': session_type,
                    'membership_level': current_user.membership_level
                },
                db=db
            )
            
            # 直接迭代异步生成器
            async for chunk in stream_result:
                if chunk.get("type") == "error":
                    yield f"data: {json.dumps(chunk)}\n\n"
                    break
                elif chunk.get("type") == "content":
                    yield f"data: {json.dumps({
                        'type': 'content',
                        'content': chunk.get('content', ''),
                        'session_id': chunk.get('session_id', message.session_id),
                        'model': 'claude-sonnet-4-20250514'
                    })}\n\n"
                elif chunk.get("type") == "strategy_parsing":
                    # 发送策略解析结果
                    yield f"data: {json.dumps({
                        'type': 'strategy_parsing',
                        'data': chunk.get('data', {}),
                        'session_id': chunk.get('session_id', message.session_id)
                    })}\n\n"
                else:
                    yield f"data: {json.dumps(chunk)}\n\n"
            
            # 发送完成事件
            yield f"data: {json.dumps({
                'type': 'done',
                'finish_reason': 'stop',
                'session_id': message.session_id
            })}\n\n"
            
            # 发送结束事件
            yield f"data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({
                'type': 'error',
                'error': {
                    'code': 500,
                    'message': f'流式对话失败: {str(e)}'
                }
            })}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.post("/strategy/generate", response_model=StrategyGenerateResponse)
async def generate_strategy(
    request: StrategyGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI生成交易策略 - 使用现有AI服务"""
    try:
        # 构建策略生成描述
        full_description = f"""
策略描述: {request.description}
指标要求: {', '.join(request.indicators) if request.indicators else '自动选择'}
时间框架: {request.timeframe}
风险级别: {request.risk_level}

请生成一个完整的交易策略代码。
"""
        
        # 使用现有的chat_completion方法
        strategy_result = await ai_service.chat_completion(
            message=full_description,
            user_id=current_user.id,
            session_id=None,  # 策略生成不需要session
            context={
                'ai_mode': 'developer',
                'session_type': 'strategy',
                'membership_level': current_user.membership_level
            },
            db=db
        )
        
        # 从响应中提取策略信息
        content = strategy_result.get("content", "")
        
        # 简单的代码提取逻辑
        import re
        code_blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
        code = code_blocks[0] if code_blocks else "# 策略生成失败\npass"
        
        return StrategyGenerateResponse(
            code=code,
            explanation=content,
            parameters={},
            warnings=[]
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
    """获取AI使用统计 - 基于用户直接使用统计"""
    try:
        from sqlalchemy import text, select, func
        from datetime import datetime, timedelta
        from app.services.membership_service import MembershipService
        
        # 计算时间范围
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        
        # 获取时间段内的总统计 - 从claude_usage_logs表读取实际数据
        total_stats_query = text("""
            SELECT 
                COALESCE(COUNT(*), 0) as total_requests,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(api_cost), 0.0) as total_cost
            FROM claude_usage_logs 
            WHERE user_id = :user_id 
            AND DATE(request_date) >= :start_date 
            AND DATE(request_date) <= :end_date
            AND success = 1
        """)
        
        total_result = await db.execute(total_stats_query, {
            "user_id": current_user.id,
            "start_date": start_date,
            "end_date": end_date
        })
        total_data = total_result.fetchone()
        
        # 获取今日统计 - 从claude_usage_logs表读取
        today_stats_query = text("""
            SELECT 
                COALESCE(COUNT(*), 0) as today_requests,
                COALESCE(SUM(total_tokens), 0) as today_tokens,
                COALESCE(SUM(api_cost), 0.0) as today_cost
            FROM claude_usage_logs 
            WHERE user_id = :user_id 
            AND DATE(request_date) = :today
            AND success = 1
        """)
        
        today_result = await db.execute(today_stats_query, {
            "user_id": current_user.id,
            "today": end_date
        })
        today_data = today_result.fetchone()
        
        # 如果没有记录，设置默认值
        total_requests = total_data[0] if total_data and total_data[0] else 0
        total_cost_usd = float(total_data[2]) if total_data and total_data[2] else 0.0
        today_cost = float(today_data[2]) if today_data and today_data[2] else 0.0
        
        # 获取会员限制
        limits = MembershipService.get_membership_limits(current_user.membership_level)
        
        # 计算剩余额度
        daily_limit = float(limits.ai_daily_limit.replace('$', '')) if isinstance(limits.ai_daily_limit, str) else float(limits.ai_daily_limit)
        remaining_daily = max(0, daily_limit - today_cost)
        remaining_monthly = max(0, daily_limit * 30 - total_cost_usd)  # 简化计算
        
        return UsageStatsResponse(
            period_days=days,
            total_requests=total_requests,
            total_cost_usd=total_cost_usd,
            daily_cost_usd=today_cost,
            monthly_cost_usd=total_cost_usd,  # 简化为时间段内总成本
            remaining_daily_quota=remaining_daily,
            remaining_monthly_quota=remaining_monthly,
            by_feature={},  # 暂时为空，可以后续扩展
            by_session={}   # 暂时为空，可以后续扩展
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


# ===== 虚拟API密钥认证的公开端点 =====
# 仿照claude-relay-service的模式，用户使用虚拟API密钥调用

async def authenticate_virtual_key(
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """通过虚拟API密钥认证用户"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少API密钥")
    
    # 验证虚拟API密钥格式
    if not x_api_key.startswith('uck-'):
        raise HTTPException(status_code=401, detail="无效的API密钥格式")
    
    # 查找虚拟API密钥
    user_key = await UserClaudeKeyService.get_user_key_by_virtual_key(db, x_api_key)
    if not user_key or user_key.status != 'active':
        raise HTTPException(status_code=401, detail="API密钥无效或已停用")
    
    return user_key


@router.post("/v1/messages", response_model=dict)
async def anthropic_compatible_chat(
    request: dict,
    user_key = Depends(authenticate_virtual_key),
    db: AsyncSession = Depends(get_db)
):
    """
    兼容Anthropic API格式的聊天端点
    用户可以使用虚拟API密钥直接调用，就像使用Claude官方API一样
    """
    try:
        from app.middleware.claude_proxy import ClaudeProxyMiddleware
        
        # 验证必要的请求参数
        if "messages" not in request:
            raise HTTPException(status_code=400, detail="缺少必要参数: messages")
        
        # 构建增强请求数据
        enhanced_request_data = {
            **request,
            "user_id": user_key.user_id,
            "virtual_key": user_key.virtual_key,
            "session_id": request.get("session_id"),
            "ai_mode": request.get("ai_mode", "developer"),
            "priority": "normal"
        }
        
        # 验证并路由请求（使用智能调度）
        validated_user_key, claude_account = await ClaudeProxyMiddleware.validate_and_route_request(
            db, user_key.virtual_key, enhanced_request_data, "chat"
        )
        
        # 代理请求到Claude账号
        response = await ClaudeProxyMiddleware.proxy_claude_request(
            db, validated_user_key, claude_account, enhanced_request_data, "chat"
        )
        
        # 返回兼容Anthropic API格式的响应
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[DEBUG] Virtual Key API Error: {error_traceback}")
        raise HTTPException(status_code=500, detail=f"AI服务暂时不可用: {str(e)}")


@router.post("/proxy/chat")
async def proxy_chat_with_virtual_key(
    request: dict,
    user_key = Depends(authenticate_virtual_key),
    db: AsyncSession = Depends(get_db)
):
    """
    简化的代理聊天端点（兼容我们自己的格式）
    支持content字段的简单请求格式
    """
    try:
        from app.middleware.claude_proxy import ClaudeProxyMiddleware
        
        # 支持简化的请求格式
        content = request.get("content") or request.get("message", "")
        if not content:
            raise HTTPException(status_code=400, detail="缺少消息内容")
        
        # 构建标准的Claude API请求格式
        claude_request = {
            "model": request.get("model", "claude-sonnet-4-20250514"),
            "max_tokens": request.get("max_tokens", 4000),
            "messages": [{"role": "user", "content": content}],
            "temperature": request.get("temperature", 0.7)
        }
        
        # 构建增强请求数据
        enhanced_request_data = {
            **claude_request,
            "user_id": user_key.user_id,
            "virtual_key": user_key.virtual_key,
            "session_id": request.get("session_id"),
            "ai_mode": request.get("ai_mode", "developer"),
            "session_type": request.get("session_type", "general"),
            "priority": "normal"
        }
        
        # 验证并路由请求
        validated_user_key, claude_account = await ClaudeProxyMiddleware.validate_and_route_request(
            db, user_key.virtual_key, enhanced_request_data, "chat"
        )
        
        # 代理请求到Claude账号
        response = await ClaudeProxyMiddleware.proxy_claude_request(
            db, validated_user_key, claude_account, enhanced_request_data, "chat"
        )
        
        # 返回简化响应格式
        return {
            "success": True,
            "response": response.get("content", response.get("text", "")),
            "model": response.get("model", claude_request["model"]),
            "usage": response.get("usage", {}),
            "session_id": request.get("session_id"),
            "cost_usd": response.get("cost_usd", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[DEBUG] Proxy Chat Error: {error_traceback}")
        raise HTTPException(status_code=500, detail=f"代理聊天失败: {str(e)}")


# ===== WebSocket流式AI对话端点 =====

@router.websocket("/ws/chat/{user_id}")
async def websocket_ai_chat(
    websocket: WebSocket,
    user_id: int,
    session_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    WebSocket流式AI对话端点
    
    Args:
        websocket: WebSocket连接
        user_id: 用户ID
        session_id: 可选的会话ID
        token: 可选的JWT认证令牌
    """
    
    # 获取WebSocket管理器
    websocket_manager = await get_websocket_manager()
    
    try:
        # 接受WebSocket连接
        await websocket.accept()
        logger.info(f"🔗 WebSocket连接建立: 用户{user_id}, 会话{session_id}")
        
        # 注册连接到管理器
        connection_id = await websocket_manager.connect(websocket, user_id, session_id)
        
        # 发送欢迎消息
        await websocket.send_json({
            "type": "welcome",
            "message": "WebSocket连接已建立，开始流式AI对话",
            "connection_id": connection_id,
            "session_id": session_id
        })
        
        # 消息处理循环
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_json()
                logger.info(f"📥 收到WebSocket消息: {data.get('type', 'unknown')}")
                
                # 更新心跳
                await websocket_manager.handle_ping(connection_id)
                
                # 处理不同类型的消息
                message_type = data.get("type", "")
                
                if message_type == "ping":
                    # 心跳响应已在handle_ping中处理
                    continue
                    
                elif message_type == "chat":
                    # 处理AI对话请求
                    await handle_websocket_chat_message(
                        websocket, websocket_manager, user_id, session_id or connection_id, data
                    )
                    
                elif message_type == "stop_stream":
                    # 停止当前流式响应
                    await handle_stop_stream(user_id, session_id or connection_id, data)
                    
                else:
                    # 未知消息类型
                    await websocket.send_json({
                        "type": "error",
                        "message": f"未知的消息类型: {message_type}",
                        "code": "UNKNOWN_MESSAGE_TYPE"
                    })
                    
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket客户端主动断开: 用户{user_id}")
                break
                
            except Exception as e:
                logger.error(f"❌ WebSocket消息处理异常: {e}")
                await websocket.send_json({
                    "type": "error", 
                    "message": str(e),
                    "code": "MESSAGE_PROCESSING_ERROR"
                })
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket连接断开: 用户{user_id}")
        
    except Exception as e:
        logger.error(f"❌ WebSocket连接异常: {e}")
        
    finally:
        # 清理连接
        await websocket_manager.disconnect(connection_id, "连接关闭")
        logger.info(f"🧹 WebSocket连接已清理: 用户{user_id}")


async def handle_websocket_chat_message(
    websocket: WebSocket,
    websocket_manager: WebSocketManager, 
    user_id: int,
    session_id: str,
    data: dict
):
    """
    处理WebSocket聊天消息
    
    Args:
        websocket: WebSocket连接
        websocket_manager: WebSocket管理器
        user_id: 用户ID
        session_id: 会话ID
        data: 消息数据
    """
    try:
        # 验证消息内容
        content = data.get("content", "").strip()
        if not content:
            await websocket.send_json({
                "type": "error",
                "message": "消息内容不能为空",
                "code": "EMPTY_CONTENT"
            })
            return
        
        # 获取AI模式和会话类型
        ai_mode = data.get("ai_mode", "trader")
        session_type = data.get("session_type", "chat")
        
        logger.info(f"🤖 启动AI流式对话: 用户{user_id}, 模式{ai_mode}, 类型{session_type}")
        
        # 启动流式AI对话处理
        async with streaming_context(user_id, session_id) as streaming_handler:
            # 获取数据库会话
            async for db in get_db():
                await streaming_handler.start_ai_stream(
                    user_id=user_id,
                    session_id=session_id,
                    message=content,
                    ai_mode=ai_mode,
                    session_type=session_type,
                    db=db
                )
                break  # 只取第一个数据库会话
                
    except Exception as e:
        logger.error(f"❌ WebSocket聊天处理异常: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"处理聊天消息失败: {str(e)}",
            "code": "CHAT_PROCESSING_ERROR"
        })


async def handle_stop_stream(user_id: int, session_id: str, data: dict):
    """
    处理停止流式响应请求
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
        data: 消息数据
    """
    try:
        # 获取流式处理器
        streaming_handler = await get_streaming_handler()
        
        # 停止指定会话的流式响应
        stream_id = data.get("stream_id")
        if stream_id:
            await streaming_handler.stop_stream(stream_id)
        else:
            # 停止用户的所有流式响应
            await streaming_handler.stop_user_streams(user_id)
        
        logger.info(f"🛑 已停止流式响应: 用户{user_id}, 会话{session_id}")
        
    except Exception as e:
        logger.error(f"❌ 停止流式响应失败: {e}")


@router.get("/ws/stats")
async def get_websocket_stats():
    """获取WebSocket连接统计"""
    try:
        websocket_manager = await get_websocket_manager()
        streaming_handler = await get_streaming_handler()
        
        ws_stats = websocket_manager.get_connection_stats()
        stream_stats = streaming_handler.get_active_streams_stats()
        
        return {
            "websocket_connections": ws_stats,
            "streaming_sessions": stream_stats,
            "timestamp": json.loads(json.dumps(asyncio.get_event_loop().time()))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取WebSocket统计失败: {str(e)}")


@router.post("/ws/broadcast")
async def broadcast_message(
    message: dict,
    target_user: Optional[int] = Query(None, description="目标用户ID，不指定则广播给所有用户")
):
    """广播消息到WebSocket连接"""
    try:
        websocket_manager = await get_websocket_manager()
        
        if target_user:
            # 发送给特定用户
            success = await websocket_manager.send_to_user(target_user, message)
            return {
                "success": success,
                "target": f"user_{target_user}",
                "message": "消息已发送" if success else "用户未连接"
            }
        else:
            # 广播给所有用户
            await websocket_manager.broadcast_to_all(message)
            stats = websocket_manager.get_connection_stats()
            return {
                "success": True,
                "target": "all_users",
                "message": f"消息已广播给{stats['total_connections']}个连接"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"广播消息失败: {str(e)}")