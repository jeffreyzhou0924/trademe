"""
支付自动化管理API - 管理员支付自动化控制接口
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Dict, Any
from decimal import Decimal

from app.database import get_db
from app.middleware.admin_auth import get_current_admin, AdminUser
from app.services.payment_automation import payment_automation
from app.models.admin import AdminOperationLog
from app.core.rbac import require_permission
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/payment-automation", tags=["支付自动化管理"])


# Pydantic模型
class ManualPaymentRequest(BaseModel):
    """手动处理支付请求"""
    order_id: int = Field(..., description="订单ID")
    tx_hash: str = Field(..., description="交易哈希", min_length=32)
    amount: Decimal = Field(..., description="支付金额", gt=0)


class TransactionConfirmRequest(BaseModel):
    """交易确认请求"""
    tx_hash: str = Field(..., description="交易哈希", min_length=32)
    network: str = Field(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$")
    from_address: str = Field(..., description="发送地址")
    to_address: str = Field(..., description="接收地址")
    amount: Decimal = Field(..., description="转账金额", gt=0)
    confirmations: int = Field(..., description="确认数", ge=0)


class AutomationStatusResponse(BaseModel):
    """自动化状态响应"""
    running: bool
    active_tasks: int
    blockchain_monitor_active: bool
    payment_processor_active: bool
    timestamp: str


@router.get("/status", response_model=AutomationStatusResponse)
@require_permission("payment:monitor")
async def get_automation_status(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """获取支付自动化系统状态"""
    try:
        status_info = payment_automation.get_automation_status()
        
        return AutomationStatusResponse(
            running=status_info["running"],
            active_tasks=status_info["active_tasks"],
            blockchain_monitor_active=status_info["blockchain_monitor_active"],
            payment_processor_active=status_info["payment_processor_active"],
            timestamp=status_info["timestamp"]
        )
        
    except Exception as e:
        logger.error(f"获取自动化状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}"
        )


@router.post("/start")
@require_permission("payment:admin")
async def start_automation(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """启动支付自动化系统"""
    try:
        if payment_automation.running:
            return {"message": "支付自动化系统已在运行", "status": "already_running"}
        
        # 重新初始化（如果需要）
        if not payment_automation.blockchain_monitor:
            await payment_automation.initialize(db)
        
        await payment_automation.start_automation()
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="START_PAYMENT_AUTOMATION",
            resource_type="payment_automation",
            details='{"action": "start_automation"}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        logger.info(f"管理员 {current_admin.id} 启动了支付自动化系统")
        
        return {"message": "支付自动化系统启动成功", "status": "started"}
        
    except Exception as e:
        logger.error(f"启动支付自动化失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动失败: {str(e)}"
        )


@router.post("/stop")
@require_permission("payment:admin")
async def stop_automation(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """停止支付自动化系统"""
    try:
        if not payment_automation.running:
            return {"message": "支付自动化系统未在运行", "status": "not_running"}
        
        await payment_automation.stop_automation()
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="STOP_PAYMENT_AUTOMATION",
            resource_type="payment_automation",
            details='{"action": "stop_automation"}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        logger.info(f"管理员 {current_admin.id} 停止了支付自动化系统")
        
        return {"message": "支付自动化系统停止成功", "status": "stopped"}
        
    except Exception as e:
        logger.error(f"停止支付自动化失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止失败: {str(e)}"
        )


@router.post("/restart")
@require_permission("payment:admin")
async def restart_automation(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """重启支付自动化系统"""
    try:
        # 先停止
        if payment_automation.running:
            await payment_automation.stop_automation()
            logger.info("支付自动化系统已停止，准备重启")
        
        # 重新初始化
        await payment_automation.initialize(db)
        
        # 启动
        await payment_automation.start_automation()
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="RESTART_PAYMENT_AUTOMATION",
            resource_type="payment_automation",
            details='{"action": "restart_automation"}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        logger.info(f"管理员 {current_admin.id} 重启了支付自动化系统")
        
        return {"message": "支付自动化系统重启成功", "status": "restarted"}
        
    except Exception as e:
        logger.error(f"重启支付自动化失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重启失败: {str(e)}"
        )


@router.post("/manual-payment")
@require_permission("payment:admin")
async def process_manual_payment(
    request: ManualPaymentRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """手动处理支付（用于异常情况处理）"""
    try:
        success = await payment_automation.manual_process_payment(
            order_id=request.order_id,
            tx_hash=request.tx_hash,
            amount=float(request.amount),
            admin_id=current_admin.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手动支付处理失败"
            )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="MANUAL_PAYMENT_PROCESS",
            resource_type="payment_order",
            resource_id=request.order_id,
            details=f'{{"tx_hash": "{request.tx_hash}", "amount": {request.amount}}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "message": "手动支付处理成功",
            "order_id": request.order_id,
            "tx_hash": request.tx_hash,
            "amount": float(request.amount)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动处理支付失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"手动支付处理失败: {str(e)}"
        )


@router.post("/confirm-transaction")
@require_permission("payment:admin")
async def confirm_transaction(
    request: TransactionConfirmRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """手动确认交易（用于处理区块链API异常情况）"""
    try:
        success = await payment_automation.process_transaction_confirmation(
            tx_hash=request.tx_hash,
            network=request.network,
            from_address=request.from_address,
            to_address=request.to_address,
            amount=float(request.amount),
            confirmations=request.confirmations
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="交易确认处理失败"
            )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="MANUAL_CONFIRM_TRANSACTION",
            resource_type="blockchain_transaction",
            details=f'{{"tx_hash": "{request.tx_hash}", "network": "{request.network}", "amount": {request.amount}}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "message": "交易确认处理成功",
            "tx_hash": request.tx_hash,
            "network": request.network,
            "confirmations": request.confirmations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动确认交易失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"交易确认失败: {str(e)}"
        )


@router.get("/health-check")
@require_permission("payment:monitor")
async def automation_health_check(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """支付自动化系统健康检查"""
    try:
        status_info = payment_automation.get_automation_status()
        
        # 检查系统健康状态
        health_issues = []
        
        if not status_info["running"]:
            health_issues.append("支付自动化系统未运行")
        
        if not status_info["blockchain_monitor_active"]:
            health_issues.append("区块链监控服务未激活")
        
        if not status_info["payment_processor_active"]:
            health_issues.append("支付处理器未激活")
        
        if status_info["active_tasks"] == 0 and status_info["running"]:
            health_issues.append("自动化系统运行中但没有活跃任务")
        
        # 确定健康状态
        if not health_issues:
            health_status = "healthy"
            message = "支付自动化系统运行正常"
        elif len(health_issues) <= 2:
            health_status = "warning"
            message = f"支付自动化系统有轻微问题: {'; '.join(health_issues)}"
        else:
            health_status = "critical"
            message = f"支付自动化系统有严重问题: {'; '.join(health_issues)}"
        
        return {
            "health_status": health_status,
            "message": message,
            "issues": health_issues,
            "system_status": status_info,
            "timestamp": status_info["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "health_status": "error",
            "message": f"健康检查失败: {str(e)}",
            "issues": ["健康检查系统异常"],
            "timestamp": None
        }