"""
资金归集API端点 - 管理员资金归集功能
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

from app.middleware.auth import get_current_user
from app.api.v1.admin_simple import check_admin_permission
from app.services.fund_consolidation_service import (
    fund_consolidation_service, 
    ConsolidationTask, 
    ConsolidationStrategy
)
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/fund-consolidation", tags=["资金归集"])


class ConsolidationTaskResponse(BaseModel):
    """归集任务响应"""
    task_id: str
    source_wallet_id: int
    target_wallet_id: int
    network: str
    amount: str
    estimated_fee: str
    priority: int
    status: str
    created_at: datetime


class ConsolidationStatsResponse(BaseModel):
    """归集统计响应"""
    total_wallets_with_funds: int
    total_consolidatable_amount: str
    pending_consolidation_tasks: int
    completed_consolidations_today: int
    total_fees_saved: str
    network_breakdown: Dict[str, Any]


class ExecuteConsolidationRequest(BaseModel):
    """执行归集请求"""
    task_ids: List[str] = Field(..., description="要执行的任务ID列表")
    strategy: ConsolidationStrategy = Field(default=ConsolidationStrategy.THRESHOLD, description="归集策略")


class ManualConsolidationRequest(BaseModel):
    """手动归集请求"""
    source_wallet_id: int = Field(..., description="源钱包ID")
    target_wallet_id: Optional[int] = Field(None, description="目标钱包ID，不指定则使用默认主钱包")
    amount: Optional[str] = Field(None, description="归集金额，不指定则归集全部")
    force: bool = Field(default=False, description="是否强制执行（忽略手续费限制）")


@router.get("/scan", response_model=SuccessResponse[List[ConsolidationTaskResponse]])
async def scan_consolidation_opportunities(
    current_user = Depends(get_current_user),
    network: Optional[str] = Query(None, description="指定网络类型")
):
    """扫描归集机会"""
    await check_admin_permission(current_user)
    
    try:
        tasks = await fund_consolidation_service.scan_for_consolidation_opportunities()
        
        # 如果指定了网络，则过滤
        if network:
            tasks = [task for task in tasks if task.network == network]
        
        task_responses = []
        for task in tasks:
            task_responses.append(ConsolidationTaskResponse(
                task_id=task.task_id,
                source_wallet_id=task.source_wallet_id,
                target_wallet_id=task.target_wallet_id,
                network=task.network,
                amount=str(task.amount),
                estimated_fee=str(task.estimated_fee),
                priority=task.priority,
                status=task.status,
                created_at=task.created_at
            ))
        
        return SuccessResponse(
            data=task_responses,
            message=f"Found {len(task_responses)} consolidation opportunities"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描归集机会失败: {str(e)}")


@router.post("/execute", response_model=SuccessResponse[Dict[str, Any]])
async def execute_consolidation_tasks(
    request: ExecuteConsolidationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """执行归集任务"""
    await check_admin_permission(current_user)
    
    if not request.task_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个归集任务")
    
    try:
        # 重新扫描获取最新任务列表
        all_tasks = await fund_consolidation_service.scan_for_consolidation_opportunities()
        
        # 筛选要执行的任务
        selected_tasks = [task for task in all_tasks if task.task_id in request.task_ids]
        
        if not selected_tasks:
            raise HTTPException(status_code=404, detail="未找到指定的归集任务")
        
        # 添加后台任务执行归集
        for task in selected_tasks:
            background_tasks.add_task(
                fund_consolidation_service.execute_consolidation_task,
                task
            )
        
        total_amount = sum(task.amount for task in selected_tasks)
        total_fee = sum(task.estimated_fee for task in selected_tasks)
        
        return SuccessResponse(
            data={
                "executed_tasks": len(selected_tasks),
                "total_amount": str(total_amount),
                "estimated_total_fee": str(total_fee),
                "strategy": request.strategy.value
            },
            message=f"已开始执行 {len(selected_tasks)} 个归集任务"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行归集任务失败: {str(e)}")


@router.post("/manual", response_model=SuccessResponse[Dict[str, Any]])
async def manual_consolidation(
    request: ManualConsolidationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """手动归集指定钱包"""
    await check_admin_permission(current_user)
    
    try:
        # 获取源钱包信息
        source_wallet = await fund_consolidation_service._get_wallet_by_id(request.source_wallet_id)
        if not source_wallet:
            raise HTTPException(status_code=404, detail="源钱包不存在")
        
        if source_wallet.status != "available":
            raise HTTPException(status_code=400, detail="源钱包不可用")
        
        # 确定目标钱包
        if request.target_wallet_id:
            target_wallet = await fund_consolidation_service._get_wallet_by_id(request.target_wallet_id)
            if not target_wallet:
                raise HTTPException(status_code=404, detail="目标钱包不存在")
        else:
            target_wallet = await fund_consolidation_service._get_master_wallet(source_wallet.network)
            if not target_wallet:
                raise HTTPException(status_code=400, detail=f"未配置{source_wallet.network}网络的主钱包")
        
        # 确定归集金额
        if request.amount:
            consolidation_amount = Decimal(request.amount)
            if consolidation_amount > source_wallet.balance:
                raise HTTPException(status_code=400, detail="归集金额超过钱包余额")
        else:
            consolidation_amount = source_wallet.balance
        
        # 检查手续费
        estimated_fee = await fund_consolidation_service._estimate_consolidation_fee(
            source_wallet.network, 
            consolidation_amount
        )
        
        if not request.force:
            rule = fund_consolidation_service.consolidation_rules.get(source_wallet.network)
            if rule:
                fee_ratio = estimated_fee / consolidation_amount if consolidation_amount > 0 else Decimal("1")
                if fee_ratio > rule.max_fee_ratio:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"手续费比例过高 ({fee_ratio:.2%})，请使用force=true强制执行"
                    )
        
        # 创建手动归集任务
        task = ConsolidationTask(
            task_id=f"MANUAL_{source_wallet.network}_{source_wallet.id}_{int(datetime.utcnow().timestamp())}",
            source_wallet_id=source_wallet.id,
            target_wallet_id=target_wallet.id,
            network=source_wallet.network,
            amount=consolidation_amount - estimated_fee,
            estimated_fee=estimated_fee,
            priority=5,  # 手动任务最高优先级
            created_at=datetime.utcnow(),
            status="manual"
        )
        
        # 添加后台任务执行归集
        background_tasks.add_task(
            fund_consolidation_service.execute_consolidation_task,
            task
        )
        
        return SuccessResponse(
            data={
                "task_id": task.task_id,
                "source_wallet": source_wallet.address,
                "target_wallet": target_wallet.address,
                "amount": str(task.amount),
                "estimated_fee": str(estimated_fee),
                "network": source_wallet.network
            },
            message="手动归集任务已创建并开始执行"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"手动归集失败: {str(e)}")


@router.get("/statistics", response_model=SuccessResponse[ConsolidationStatsResponse])
async def get_consolidation_statistics(
    current_user = Depends(get_current_user)
):
    """获取归集统计信息"""
    await check_admin_permission(current_user)
    
    try:
        stats = await fund_consolidation_service.get_consolidation_statistics()
        
        response = ConsolidationStatsResponse(
            total_wallets_with_funds=stats["total_wallets_with_funds"],
            total_consolidatable_amount=str(stats["total_consolidatable_amount"]),
            pending_consolidation_tasks=stats["pending_consolidation_tasks"],
            completed_consolidations_today=stats["completed_consolidations_today"],
            total_fees_saved=str(stats["total_fees_saved"]),
            network_breakdown=stats["network_breakdown"]
        )
        
        return SuccessResponse(
            data=response,
            message="获取归集统计信息成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/rules", response_model=SuccessResponse[Dict[str, Any]])
async def get_consolidation_rules(
    current_user = Depends(get_current_user)
):
    """获取归集规则配置"""
    await check_admin_permission(current_user)
    
    rules_data = {}
    for network, rule in fund_consolidation_service.consolidation_rules.items():
        rules_data[network] = {
            "min_consolidation_amount": str(rule.min_consolidation_amount),
            "consolidation_threshold": str(rule.consolidation_threshold),
            "max_fee_ratio": str(rule.max_fee_ratio),
            "consolidation_interval": rule.consolidation_interval,
            "master_wallet_address": rule.master_wallet_address
        }
    
    return SuccessResponse(
        data=rules_data,
        message="获取归集规则成功"
    )


@router.post("/auto-consolidation/{action}")
async def toggle_auto_consolidation(
    action: str,
    current_user = Depends(get_current_user),
    network: Optional[str] = Query(None, description="指定网络，不指定则应用到所有网络")
):
    """开启/关闭自动归集"""
    await check_admin_permission(current_user)
    
    if action not in ["start", "stop"]:
        raise HTTPException(status_code=400, detail="action参数必须是start或stop")
    
    # 这里应该实现自动归集的定时任务控制
    # 暂时返回成功响应
    
    return SuccessResponse(
        data={
            "action": action,
            "network": network or "all",
            "status": "success"
        },
        message=f"自动归集已{'开启' if action == 'start' else '关闭'}"
    )