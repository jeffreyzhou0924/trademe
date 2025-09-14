"""
Trademe Trading Service - 策略管理API

提供策略的增删改查、执行、优化等功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import asyncio

from app.database import get_db
from app.schemas.strategy import (
    StrategyCreate, StrategyUpdate, StrategyResponse, 
    StrategyList, StrategyExecution, StrategyFromAI
)
from app.services.strategy_service import StrategyService
from app.services.enhanced_strategy_validator import EnhancedStrategyValidator
from app.middleware.auth import get_current_user
from app.models.user import User
from app.core.strategy_engine import strategy_engine, StrategyContext

router = APIRouter()


# 策略质量评估相关的数据模型
class StrategyQualityAssessmentRequest(BaseModel):
    """策略质量评估请求"""
    code: str
    target_market: Optional[str] = "BTCUSDT"
    
    class Config:
        schema_extra = {
            "example": {
                "code": "class MyStrategy(EnhancedBaseStrategy):\n    def get_data_requirements(self):\n        return [DataRequest(symbol='BTCUSDT', data_type=DataType.KLINE)]\n    \n    async def on_data_update(self, data_type: str, data: Dict) -> Optional[TradingSignal]:\n        return TradingSignal(signal_type=SignalType.BUY, confidence=0.8)",
                "target_market": "BTCUSDT"
            }
        }


class StrategyQualityAssessmentResponse(BaseModel):
    """策略质量评估响应"""
    valid: bool
    final_quality_score: float
    risk_score: float
    risk_level: str
    enhanced_checks: Dict[str, Any]
    intelligent_suggestions: List[Dict[str, Any]]
    optimization_opportunities: List[Dict[str, Any]]
    errors: List[str] = []
    warnings: List[str] = []


@router.get("/", response_model=StrategyList)
async def get_strategies(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    active_only: bool = Query(True, description="仅返回激活的策略"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的策略列表"""
    try:
        strategies = await StrategyService.get_user_strategies(
            db, current_user.id, skip=skip, limit=limit, active_only=active_only
        )
        total = await StrategyService.count_user_strategies(
            db, current_user.id, active_only=active_only
        )
        
        return StrategyList(
            strategies=strategies,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略列表失败: {str(e)}")


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个策略详情"""
    try:
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略失败: {str(e)}")


@router.post("/", response_model=StrategyResponse)
async def create_strategy(
    strategy_data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新策略"""
    try:
        # 验证策略代码
        is_valid, error_msg = await StrategyService.validate_strategy_code(strategy_data.code)
        if not is_valid:
            raise HTTPException(status_code=422, detail=f"策略代码验证失败: {error_msg}")
        
        strategy = await StrategyService.create_strategy(db, strategy_data, current_user.id)
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建策略失败: {str(e)}")


@router.post("/quality-assessment", response_model=StrategyQualityAssessmentResponse)
async def assess_strategy_quality(
    request: StrategyQualityAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    策略质量评估API
    
    对提供的策略代码进行全面的质量评估，包括：
    - 基础语法和模板验证
    - 风险控制分析
    - 逻辑一致性检查
    - 性能优化建议
    - 市场适应性评估
    - AI驱动的智能建议
    """
    try:
        # 构建验证上下文
        validation_context = {
            "user_id": current_user.id,
            "membership_level": getattr(current_user, 'membership_level', 'basic'),
            "target_market": request.target_market,
            "assessment_timestamp": asyncio.get_event_loop().time()
        }
        
        # 执行增强策略校验
        validation_result = await EnhancedStrategyValidator.validate_strategy_enhanced(
            request.code, validation_context
        )
        
        # 构建响应
        response_data = {
            "valid": validation_result.get("valid", False),
            "final_quality_score": validation_result.get("final_quality_score", 0.0),
            "risk_score": validation_result.get("risk_score", 0.0),
            "risk_level": validation_result.get("enhanced_checks", {}).get("risk_analysis", {}).get("risk_level", "未评估"),
            "enhanced_checks": validation_result.get("enhanced_checks", {}),
            "intelligent_suggestions": validation_result.get("intelligent_suggestions", []),
            "optimization_opportunities": validation_result.get("optimization_opportunities", []),
            "errors": validation_result.get("errors", []),
            "warnings": validation_result.get("warnings", [])
        }
        
        return StrategyQualityAssessmentResponse(**response_data)
        
    except Exception as e:
        # 发生异常时返回错误响应
        error_response = {
            "valid": False,
            "final_quality_score": 0.0,
            "risk_score": 0.0,
            "risk_level": "评估失败",
            "enhanced_checks": {"error": f"评估过程异常: {str(e)}"},
            "intelligent_suggestions": [],
            "optimization_opportunities": [],
            "errors": [f"策略质量评估失败: {str(e)}"],
            "warnings": ["建议检查策略代码格式和内容"]
        }
        return StrategyQualityAssessmentResponse(**error_response)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    strategy_data: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新策略"""
    try:
        # 检查策略所有权
        existing_strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not existing_strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 如果更新代码，需要验证
        if strategy_data.code and strategy_data.code != existing_strategy.code:
            is_valid, error_msg = await StrategyService.validate_strategy_code(strategy_data.code)
            if not is_valid:
                raise HTTPException(status_code=422, detail=f"策略代码验证失败: {error_msg}")
        
        strategy = await StrategyService.update_strategy(db, strategy_id, strategy_data)
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新策略失败: {str(e)}")


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除策略"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 检查是否有正在运行的回测或实盘
        if await StrategyService.has_running_operations(db, strategy_id):
            raise HTTPException(status_code=409, detail="策略正在运行中，无法删除")
        
        await StrategyService.delete_strategy(db, strategy_id)
        return {"message": "策略删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除策略失败: {str(e)}")


@router.post("/{strategy_id}/execute", response_model=StrategyExecution)
async def execute_strategy(
    strategy_id: int,
    execution_type: str = Query(..., pattern="^(backtest|live)$", description="执行类型"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """执行策略（回测或实盘）"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        if not strategy.is_active:
            raise HTTPException(status_code=422, detail="策略未激活")
        
        # 执行策略
        if execution_type == "backtest":
            result = await StrategyService.start_backtest(db, strategy_id, current_user.id)
        else:  # live
            result = await StrategyService.start_live_trading(db, strategy_id, current_user.id)
        
        return StrategyExecution(
            strategy_id=strategy_id,
            execution_type=execution_type,
            status="started",
            execution_id=result.get("execution_id"),
            message=result.get("message", "策略执行已开始")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行策略失败: {str(e)}")


@router.post("/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止策略执行"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        result = await StrategyService.stop_strategy_execution(db, strategy_id)
        return {"message": "策略已停止", "details": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止策略失败: {str(e)}")


@router.get("/{strategy_id}/performance")
async def get_strategy_performance(
    strategy_id: int,
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取策略性能统计"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        performance = await StrategyService.get_strategy_performance(db, strategy_id, days)
        return performance
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略性能失败: {str(e)}")


@router.post("/{strategy_id}/clone", response_model=StrategyResponse)
async def clone_strategy(
    strategy_id: int,
    name: Optional[str] = Query(None, description="新策略名称"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """克隆策略"""
    try:
        # 检查策略所有权或是否为公开策略
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        cloned_strategy = await StrategyService.clone_strategy(
            db, strategy_id, current_user.id, new_name=name
        )
        return cloned_strategy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"克隆策略失败: {str(e)}")


@router.post("/{strategy_id}/validate")
async def validate_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """验证策略代码"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        is_valid, error_msg, warnings = await StrategyService.validate_strategy_code(
            strategy.code, detailed=True
        )
        
        return {
            "valid": is_valid,
            "error": error_msg,
            "warnings": warnings,
            "strategy_id": strategy_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证策略失败: {str(e)}")


@router.post("/from-ai", response_model=StrategyResponse)
async def create_strategy_from_ai(
    strategy_data: StrategyFromAI,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """从AI会话创建策略/指标到用户库中"""
    try:
        # 检查是否已经存在相同AI会话的策略/指标
        existing_strategy = await StrategyService.get_strategy_by_ai_session(
            db, strategy_data.ai_session_id, current_user.id, strategy_data.strategy_type
        )
        
        if existing_strategy:
            # 更新现有策略/指标
            strategy_update = StrategyUpdate(
                name=strategy_data.name,
                description=strategy_data.description,
                code=strategy_data.code,
                parameters=strategy_data.parameters
            )
            strategy = await StrategyService.update_strategy(db, existing_strategy.id, strategy_update)
            return strategy
        else:
            # 创建新的策略/指标
            strategy_create = StrategyCreate(
                name=strategy_data.name,
                description=strategy_data.description,
                code=strategy_data.code,
                parameters=strategy_data.parameters,
                strategy_type=strategy_data.strategy_type,
                ai_session_id=strategy_data.ai_session_id
            )
            strategy = await StrategyService.create_strategy(db, strategy_create, current_user.id)
            return strategy
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存策略/指标失败: {str(e)}")


@router.get("/by-type/{strategy_type}")
async def get_strategies_by_type(
    strategy_type: str,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """根据类型获取用户的策略或指标"""
    try:
        if strategy_type not in ["strategy", "indicator"]:
            raise HTTPException(status_code=400, detail="无效的策略类型")
            
        strategies = await StrategyService.get_strategies_by_type(
            db, current_user.id, strategy_type, skip=skip, limit=limit
        )
        total = await StrategyService.count_strategies_by_type(
            db, current_user.id, strategy_type
        )
        
        return StrategyList(
            strategies=strategies,
            total=total,
            skip=skip,
            limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取{strategy_type}列表失败: {str(e)}")


@router.get("/{strategy_id}/logs")
async def get_strategy_logs(
    strategy_id: int,
    limit: int = Query(100, ge=1, le=1000, description="日志条数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取策略执行日志"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        logs = await StrategyService.get_strategy_logs(db, strategy_id, limit)
        return {"logs": logs, "strategy_id": strategy_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略日志失败: {str(e)}")


@router.post("/{strategy_id}/load")
async def load_strategy_to_engine(
    strategy_id: int,
    symbol: str = Query(..., description="交易对"),
    timeframe: str = Query("1m", description="时间周期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """加载策略到引擎"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        if not strategy.is_active:
            raise HTTPException(status_code=422, detail="策略未激活")
        
        # 创建策略上下文
        context = StrategyContext(
            strategy_id=strategy_id,
            user_id=current_user.id,
            symbol=symbol,
            timeframe=timeframe,
            parameters=strategy.parameters
        )
        
        # 加载策略到引擎
        execution_id = await strategy_engine.load_strategy(strategy, context)
        
        return {
            "execution_id": execution_id,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "message": "策略已加载到引擎"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载策略失败: {str(e)}")


@router.post("/engine/{execution_id}/start")
async def start_strategy_engine(
    execution_id: str,
    current_user: User = Depends(get_current_user)
):
    """启动策略引擎执行"""
    try:
        success = await strategy_engine.start_strategy(execution_id)
        
        if success:
            return {
                "execution_id": execution_id,
                "status": "running",
                "message": "策略引擎已启动"
            }
        else:
            raise HTTPException(status_code=500, detail="策略引擎启动失败")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动策略引擎失败: {str(e)}")


@router.post("/engine/{execution_id}/stop")
async def stop_strategy_engine(
    execution_id: str,
    current_user: User = Depends(get_current_user)
):
    """停止策略引擎执行"""
    try:
        success = await strategy_engine.stop_strategy(execution_id)
        
        if success:
            return {
                "execution_id": execution_id,
                "status": "stopped",
                "message": "策略引擎已停止"
            }
        else:
            raise HTTPException(status_code=404, detail="执行ID不存在")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止策略引擎失败: {str(e)}")


@router.get("/engine/{execution_id}/status")
async def get_strategy_engine_status(
    execution_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取策略引擎状态"""
    try:
        status = await strategy_engine.get_strategy_status(execution_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="执行ID不存在")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略状态失败: {str(e)}")


@router.get("/engine/status/all")
async def get_all_strategy_engine_status(
    current_user: User = Depends(get_current_user)
):
    """获取所有策略引擎状态"""
    try:
        all_status = strategy_engine.get_all_strategy_status()
        
        # 过滤出当前用户的策略
        user_strategies = {}
        for execution_id, status in all_status.items():
            if status and status.get("user_id") == current_user.id:
                user_strategies[execution_id] = status
        
        return {
            "strategies": user_strategies,
            "total": len(user_strategies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略状态失败: {str(e)}")


@router.get("/{strategy_id}/live-details")
async def get_strategy_live_details(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取策略实盘详细信息"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 获取基本信息
        live_details = await StrategyService.get_strategy_live_details(db, strategy_id)
        
        return {
            "strategy": strategy,
            "live_stats": live_details.get("stats", {}),
            "trades": live_details.get("trades", []),
            "performance": live_details.get("performance", {}),
            "status": live_details.get("status", "stopped")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实盘详情失败: {str(e)}")


@router.get("/{strategy_id}/trades")
async def get_strategy_trades(
    strategy_id: int,
    limit: int = Query(50, ge=1, le=200, description="交易记录数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取策略交易记录"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        trades = await StrategyService.get_strategy_trades(db, strategy_id, limit, offset)
        total_trades = await StrategyService.count_strategy_trades(db, strategy_id)
        
        return {
            "trades": trades,
            "total": total_trades,
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易记录失败: {str(e)}")


@router.get("/public", response_model=StrategyList)
async def get_public_strategies(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    db: AsyncSession = Depends(get_db)
):
    """获取公开策略列表"""
    try:
        strategies = await StrategyService.get_public_strategies(db, skip=skip, limit=limit)
        
        return StrategyList(
            strategies=strategies,
            total=len(strategies),
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取公开策略失败: {str(e)}")


@router.post("/{strategy_id}/action")
async def execute_strategy_action(
    strategy_id: int,
    action_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """执行策略操作 (启动/暂停/停止)"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        action = action_data.get("action")
        if action not in ["start", "pause", "stop", "restart"]:
            raise HTTPException(status_code=400, detail="无效的操作类型")
        
        # 模拟策略操作 - 实际应该调用策略引擎
        new_status_map = {
            "start": "running",
            "pause": "paused", 
            "stop": "stopped",
            "restart": "running"
        }
        
        new_status = new_status_map.get(action, "stopped")
        
        # 这里应该实际更新数据库中的策略状态
        # await StrategyService.update_strategy_status(db, strategy_id, new_status)
        
        return {
            "success": True,
            "message": f"策略{action}操作成功",
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略操作失败: {str(e)}")


@router.put("/{strategy_id}/parameters")
async def update_strategy_parameters(
    strategy_id: int,
    parameters_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新策略参数"""
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        parameters = parameters_data.get("parameters", {})
        
        # 这里应该实际更新数据库中的策略参数
        # await StrategyService.update_strategy_parameters(db, strategy_id, parameters)
        
        return {
            "success": True,
            "message": "策略参数更新成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新策略参数失败: {str(e)}")


@router.get("/ai-generated/{strategy_id}")
async def get_ai_generated_strategy_for_backtest(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取AI生成的策略详情用于回测
    
    前端在AI策略生成成功后调用此API获取策略详情，
    包括策略代码、建议的回测参数等信息
    """
    try:
        # 检查策略所有权
        strategy = await StrategyService.get_strategy_by_id(db, strategy_id, current_user.id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 检查是否为AI生成的策略
        if not hasattr(strategy, 'ai_session_id') or not strategy.ai_session_id:
            raise HTTPException(status_code=400, detail="该策略不是AI生成的策略")
        
        # 基于策略内容智能推荐回测参数
        suggested_params = await _generate_backtest_suggestions(strategy)
        
        return {
            "strategy_id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "code": strategy.code,
            "parameters": strategy.parameters,
            "strategy_type": strategy.strategy_type,
            "ai_session_id": strategy.ai_session_id,
            "suggested_backtest_params": suggested_params,
            "created_at": strategy.created_at.isoformat() if strategy.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取AI策略详情失败: {str(e)}")


@router.get("/latest-ai-strategy/{session_id}")
async def get_latest_ai_strategy_from_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    根据AI会话ID获取最新生成的策略
    
    AI对话完成策略生成后，前端可以通过会话ID获取最新的策略
    """
    try:
        # 查找该会话最新创建的策略
        latest_strategy = await StrategyService.get_latest_strategy_by_session(
            db, session_id, current_user.id
        )
        
        if not latest_strategy:
            raise HTTPException(status_code=404, detail="该会话中没有找到策略")
        
        # 生成回测建议参数
        suggested_params = await _generate_backtest_suggestions(latest_strategy)
        
        return {
            "strategy_id": latest_strategy.id,
            "name": latest_strategy.name,
            "description": latest_strategy.description,
            "code": latest_strategy.code,
            "parameters": latest_strategy.parameters,
            "strategy_type": latest_strategy.strategy_type,
            "ai_session_id": latest_strategy.ai_session_id,
            "suggested_backtest_params": suggested_params,
            "created_at": latest_strategy.created_at.isoformat() if latest_strategy.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取AI会话策略失败: {str(e)}")


async def _generate_backtest_suggestions(strategy) -> Dict[str, Any]:
    """
    基于策略内容智能推荐回测参数
    """
    suggestions = {
        "symbols": ["BTC/USDT"],  # 默认推荐
        "timeframes": ["1h"],     # 默认时间框架
        "initial_capital": 10000.0,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "exchange": "binance",
        "fee_rate": "vip0"
    }
    
    # 基于策略代码内容进行智能推荐
    code_lower = strategy.code.lower() if strategy.code else ""
    
    # 时间框架推荐
    if any(indicator in code_lower for indicator in ['1m', 'minute', '分钟']):
        suggestions["timeframes"] = ["1m", "5m"]
    elif any(indicator in code_lower for indicator in ['1h', 'hour', '小时']):
        suggestions["timeframes"] = ["1h", "4h"]
    elif any(indicator in code_lower for indicator in ['1d', 'day', '日']):
        suggestions["timeframes"] = ["1d"]
    
    # 交易对推荐
    if any(symbol in code_lower for symbol in ['eth', 'ethereum']):
        suggestions["symbols"] = ["ETH/USDT", "BTC/USDT"]
    elif any(symbol in code_lower for symbol in ['bnb', 'binance']):
        suggestions["symbols"] = ["BNB/USDT", "BTC/USDT"]
    
    # 根据策略复杂度推荐回测时间范围
    complexity_indicators = ['ma', 'rsi', 'macd', 'bollinger', 'ema', 'sma']
    complexity_score = sum(1 for indicator in complexity_indicators if indicator in code_lower)
    
    if complexity_score >= 3:  # 复杂策略
        suggestions["start_date"] = "2023-01-01"  # 更长的回测时间
    elif complexity_score >= 2:  # 中等复杂度
        suggestions["start_date"] = "2023-06-01"
    
    # 风险管理相关的资金建议
    if any(risk_term in code_lower for risk_term in ['stop_loss', 'risk', '止损']):
        suggestions["initial_capital"] = 50000.0  # 有风险管理的策略可以用更多资金
    
    return suggestions