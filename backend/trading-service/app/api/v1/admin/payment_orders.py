"""
USDT支付订单管理API - 管理员支付订单管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from app.database import get_db
from app.middleware.admin_auth import get_current_admin, AdminUser
from app.services.payment_processor import PaymentProcessorService, PaymentOrder
from app.models.payment import USDTPaymentOrder, USDTWallet
from app.models.user import User
from app.models.membership import MembershipPlan
from app.models.admin import AdminOperationLog
from app.core.rbac import require_permission
from app.core.exceptions import PaymentError, ValidationError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/usdt/orders", tags=["USDT支付订单管理"])


# Pydantic模型
class PaymentOrderCreateRequest(BaseModel):
    """创建支付订单请求"""
    user_id: int = Field(..., description="用户ID")
    membership_plan_id: int = Field(..., description="会员计划ID")
    network: str = Field(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$")
    amount: Decimal = Field(..., description="支付金额", gt=0)


class PaymentOrderResponse(BaseModel):
    """支付订单响应"""
    id: int
    order_no: str
    user_id: int
    user_email: str
    wallet_id: int
    wallet_address: str
    membership_plan_id: int
    plan_name: str
    network: str
    usdt_amount: Decimal
    expected_amount: Decimal
    actual_amount: Optional[Decimal]
    status: str
    transaction_hash: Optional[str]
    from_address: Optional[str]
    to_address: str
    confirmations: int
    required_confirmations: int
    expires_at: datetime
    confirmed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]


class PaymentOrderListResponse(BaseModel):
    """支付订单列表响应"""
    orders: List[PaymentOrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaymentOrderStatisticsResponse(BaseModel):
    """支付订单统计响应"""
    total_orders: int
    pending_orders: int
    confirmed_orders: int
    expired_orders: int
    cancelled_orders: int
    failed_orders: int
    total_amount: Decimal
    confirmed_amount: Decimal
    success_rate: float
    avg_processing_time: float
    network_distribution: Dict[str, int]
    status_distribution: Dict[str, int]


@router.get("/", response_model=PaymentOrderListResponse)
@require_permission("order:view")
async def get_payment_orders(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    user_id: Optional[int] = Query(None, description="用户ID筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    network: Optional[str] = Query(None, description="网络类型筛选"),
    search: Optional[str] = Query(None, description="搜索关键词(订单号/邮箱)"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序")
):
    """获取支付订单列表"""
    try:
        # 构建基础查询 - 关联用户和会员计划表
        query = select(
            USDTPaymentOrder,
            User.email.label('user_email'),
            MembershipPlan.name.label('plan_name'),
            USDTWallet.address.label('wallet_address')
        ).join(
            User, USDTPaymentOrder.user_id == User.id
        ).join(
            MembershipPlan, USDTPaymentOrder.membership_plan_id == MembershipPlan.id
        ).join(
            USDTWallet, USDTPaymentOrder.wallet_id == USDTWallet.id
        )
        
        count_query = select(func.count(USDTPaymentOrder.id)).join(
            User, USDTPaymentOrder.user_id == User.id
        ).join(
            MembershipPlan, USDTPaymentOrder.membership_plan_id == MembershipPlan.id
        )
        
        # 添加筛选条件
        filters = []
        
        if user_id:
            filters.append(USDTPaymentOrder.user_id == user_id)
        
        if status:
            filters.append(USDTPaymentOrder.status == status)
        
        if network:
            filters.append(USDTPaymentOrder.network == network)
        
        if search:
            search_filter = or_(
                USDTPaymentOrder.order_no.like(f"%{search}%"),
                User.email.like(f"%{search}%")
            )
            filters.append(search_filter)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 添加排序
        if sort_by in ['created_at', 'updated_at', 'expires_at', 'confirmed_at', 'usdt_amount']:
            sort_column = getattr(USDTPaymentOrder, sort_by)
            if sort_order.lower() == 'asc':
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(USDTPaymentOrder.created_at.desc())
        
        # 添加分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # 执行查询
        result = await db.execute(query)
        rows = result.fetchall()
        
        # 转换为响应格式
        order_responses = [
            PaymentOrderResponse(
                id=row.USDTPaymentOrder.id,
                order_no=row.USDTPaymentOrder.order_no,
                user_id=row.USDTPaymentOrder.user_id,
                user_email=row.user_email,
                wallet_id=row.USDTPaymentOrder.wallet_id,
                wallet_address=row.wallet_address,
                membership_plan_id=row.USDTPaymentOrder.membership_plan_id,
                plan_name=row.plan_name,
                network=row.USDTPaymentOrder.network,
                usdt_amount=row.USDTPaymentOrder.usdt_amount,
                expected_amount=row.USDTPaymentOrder.expected_amount,
                actual_amount=row.USDTPaymentOrder.actual_amount,
                status=row.USDTPaymentOrder.status,
                transaction_hash=row.USDTPaymentOrder.transaction_hash,
                from_address=row.USDTPaymentOrder.from_address,
                to_address=row.USDTPaymentOrder.to_address,
                confirmations=row.USDTPaymentOrder.confirmations,
                required_confirmations=row.USDTPaymentOrder.required_confirmations,
                expires_at=row.USDTPaymentOrder.expires_at,
                confirmed_at=row.USDTPaymentOrder.confirmed_at,
                cancelled_at=row.USDTPaymentOrder.cancelled_at,
                created_at=row.USDTPaymentOrder.created_at,
                updated_at=row.USDTPaymentOrder.updated_at
            )
            for row in rows
        ]
        
        total_pages = (total + page_size - 1) // page_size
        
        return PaymentOrderListResponse(
            orders=order_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"获取支付订单列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订单列表失败: {str(e)}"
        )


@router.post("/", response_model=PaymentOrderResponse)
@require_permission("order:create")
async def create_payment_order(
    request: PaymentOrderCreateRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """创建支付订单（管理员操作）"""
    try:
        payment_processor = PaymentProcessorService(db)
        
        # 创建支付订单
        payment_order = await payment_processor.create_payment_order(
            user_id=request.user_id,
            membership_plan_id=request.membership_plan_id,
            network=request.network,
            amount=request.amount,
            admin_id=current_admin.id
        )
        
        # 获取关联信息用于响应
        order_query = select(
            USDTPaymentOrder,
            User.email.label('user_email'),
            MembershipPlan.name.label('plan_name'),
            USDTWallet.address.label('wallet_address')
        ).join(
            User, USDTPaymentOrder.user_id == User.id
        ).join(
            MembershipPlan, USDTPaymentOrder.membership_plan_id == MembershipPlan.id
        ).join(
            USDTWallet, USDTPaymentOrder.wallet_id == USDTWallet.id
        ).where(USDTPaymentOrder.id == payment_order.id)
        
        result = await db.execute(order_query)
        row = result.first()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="创建的订单未找到"
            )
        
        return PaymentOrderResponse(
            id=row.USDTPaymentOrder.id,
            order_no=row.USDTPaymentOrder.order_no,
            user_id=row.USDTPaymentOrder.user_id,
            user_email=row.user_email,
            wallet_id=row.USDTPaymentOrder.wallet_id,
            wallet_address=row.wallet_address,
            membership_plan_id=row.USDTPaymentOrder.membership_plan_id,
            plan_name=row.plan_name,
            network=row.USDTPaymentOrder.network,
            usdt_amount=row.USDTPaymentOrder.usdt_amount,
            expected_amount=row.USDTPaymentOrder.expected_amount,
            actual_amount=row.USDTPaymentOrder.actual_amount,
            status=row.USDTPaymentOrder.status,
            transaction_hash=row.USDTPaymentOrder.transaction_hash,
            from_address=row.USDTPaymentOrder.from_address,
            to_address=row.USDTPaymentOrder.to_address,
            confirmations=row.USDTPaymentOrder.confirmations,
            required_confirmations=row.USDTPaymentOrder.required_confirmations,
            expires_at=row.USDTPaymentOrder.expires_at,
            confirmed_at=row.USDTPaymentOrder.confirmed_at,
            cancelled_at=row.USDTPaymentOrder.cancelled_at,
            created_at=row.USDTPaymentOrder.created_at,
            updated_at=row.USDTPaymentOrder.updated_at
        )
        
    except Exception as e:
        logger.error(f"创建支付订单失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"订单创建失败: {str(e)}"
        )


@router.get("/{order_id}", response_model=PaymentOrderResponse)
@require_permission("order:view")
async def get_payment_order(
    order_id: int,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取支付订单详情"""
    try:
        # 查询订单详情
        order_query = select(
            USDTPaymentOrder,
            User.email.label('user_email'),
            MembershipPlan.name.label('plan_name'),
            USDTWallet.address.label('wallet_address')
        ).join(
            User, USDTPaymentOrder.user_id == User.id
        ).join(
            MembershipPlan, USDTPaymentOrder.membership_plan_id == MembershipPlan.id
        ).join(
            USDTWallet, USDTPaymentOrder.wallet_id == USDTWallet.id
        ).where(USDTPaymentOrder.id == order_id)
        
        result = await db.execute(order_query)
        row = result.first()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="支付订单不存在"
            )
        
        return PaymentOrderResponse(
            id=row.USDTPaymentOrder.id,
            order_no=row.USDTPaymentOrder.order_no,
            user_id=row.USDTPaymentOrder.user_id,
            user_email=row.user_email,
            wallet_id=row.USDTPaymentOrder.wallet_id,
            wallet_address=row.wallet_address,
            membership_plan_id=row.USDTPaymentOrder.membership_plan_id,
            plan_name=row.plan_name,
            network=row.USDTPaymentOrder.network,
            usdt_amount=row.USDTPaymentOrder.usdt_amount,
            expected_amount=row.USDTPaymentOrder.expected_amount,
            actual_amount=row.USDTPaymentOrder.actual_amount,
            status=row.USDTPaymentOrder.status,
            transaction_hash=row.USDTPaymentOrder.transaction_hash,
            from_address=row.USDTPaymentOrder.from_address,
            to_address=row.USDTPaymentOrder.to_address,
            confirmations=row.USDTPaymentOrder.confirmations,
            required_confirmations=row.USDTPaymentOrder.required_confirmations,
            expires_at=row.USDTPaymentOrder.expires_at,
            confirmed_at=row.USDTPaymentOrder.confirmed_at,
            cancelled_at=row.USDTPaymentOrder.cancelled_at,
            created_at=row.USDTPaymentOrder.created_at,
            updated_at=row.USDTPaymentOrder.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订单详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订单详情失败: {str(e)}"
        )


@router.post("/{order_id}/cancel")
@require_permission("order:manage")
async def cancel_payment_order(
    order_id: int,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """取消支付订单"""
    try:
        payment_processor = PaymentProcessorService(db)
        success = await payment_processor.cancel_payment_order(order_id, current_admin.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="订单取消失败"
            )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="CANCEL_ORDER",
            resource_type="payment_order",
            resource_id=order_id,
            details=f'{{"action": "manual_cancel"}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {"message": "订单取消成功", "order_id": order_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消订单失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"订单取消失败: {str(e)}"
        )


@router.post("/{order_id}/manual-confirm")
@require_permission("order:manage")
async def manual_confirm_payment(
    order_id: int,
    tx_hash: str = Query(..., description="交易哈希"),
    amount: Decimal = Query(..., description="实际金额", gt=0),
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """手动确认支付（用于特殊情况处理）"""
    try:
        # 获取订单信息
        order_query = select(USDTPaymentOrder).where(USDTPaymentOrder.id == order_id)
        result = await db.execute(order_query)
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订单不存在"
            )
        
        if order.status not in ["pending", "confirming"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"订单状态 {order.status} 不允许手动确认"
            )
        
        # 使用支付处理服务进行确认
        payment_processor = PaymentProcessorService(db)
        success = await payment_processor.process_payment_confirmation(
            tx_hash=tx_hash,
            network=order.network,
            from_address="",  # 手动确认时可能没有
            to_address=order.to_address,
            amount=amount,
            confirmations=order.required_confirmations  # 直接设为所需确认数
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="支付确认处理失败"
            )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="MANUAL_CONFIRM_PAYMENT",
            resource_type="payment_order",
            resource_id=order_id,
            details=f'{{"tx_hash": "{tx_hash}", "amount": {amount}, "action": "manual_confirm"}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "message": "支付确认成功",
            "order_id": order_id,
            "tx_hash": tx_hash,
            "amount": float(amount)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"手动确认支付失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"支付确认失败: {str(e)}"
        )


@router.get("/statistics/overview", response_model=PaymentOrderStatisticsResponse)
@require_permission("order:view")
async def get_payment_order_statistics(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="统计天数")
):
    """获取支付订单统计信息"""
    try:
        # 计算时间范围
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 基础统计查询
        base_query = select(USDTPaymentOrder).where(USDTPaymentOrder.created_at >= start_date)
        
        # 状态分布统计
        status_query = select(
            USDTPaymentOrder.status,
            func.count().label('count')
        ).where(
            USDTPaymentOrder.created_at >= start_date
        ).group_by(USDTPaymentOrder.status)
        
        status_result = await db.execute(status_query)
        status_stats = {row.status: row.count for row in status_result}
        
        # 网络分布统计
        network_query = select(
            USDTPaymentOrder.network,
            func.count().label('count')
        ).where(
            USDTPaymentOrder.created_at >= start_date
        ).group_by(USDTPaymentOrder.network)
        
        network_result = await db.execute(network_query)
        network_stats = {row.network: row.count for row in network_result}
        
        # 金额统计
        amount_query = select(
            func.count().label('total_orders'),
            func.sum(USDTPaymentOrder.usdt_amount).label('total_amount'),
            func.sum(
                func.case(
                    (USDTPaymentOrder.status == 'confirmed', USDTPaymentOrder.actual_amount),
                    else_=0
                )
            ).label('confirmed_amount'),
            func.avg(
                func.case(
                    (USDTPaymentOrder.confirmed_at.isnot(None),
                     func.extract('epoch', USDTPaymentOrder.confirmed_at - USDTPaymentOrder.created_at)),
                    else_=None
                )
            ).label('avg_processing_time')
        ).where(USDTPaymentOrder.created_at >= start_date)
        
        amount_result = await db.execute(amount_query)
        amount_row = amount_result.first()
        
        # 计算成功率
        total_orders = amount_row.total_orders or 0
        confirmed_orders = status_stats.get('confirmed', 0)
        success_rate = (confirmed_orders / max(total_orders, 1)) * 100
        
        return PaymentOrderStatisticsResponse(
            total_orders=total_orders,
            pending_orders=status_stats.get('pending', 0),
            confirmed_orders=confirmed_orders,
            expired_orders=status_stats.get('expired', 0),
            cancelled_orders=status_stats.get('cancelled', 0),
            failed_orders=status_stats.get('failed', 0),
            total_amount=Decimal(str(amount_row.total_amount or 0)),
            confirmed_amount=Decimal(str(amount_row.confirmed_amount or 0)),
            success_rate=success_rate,
            avg_processing_time=float(amount_row.avg_processing_time or 0),
            network_distribution=network_stats,
            status_distribution=status_stats
        )
        
    except Exception as e:
        logger.error(f"获取订单统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )


@router.post("/cleanup/expired")
@require_permission("order:manage")
async def cleanup_expired_orders(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """清理过期订单"""
    try:
        payment_processor = PaymentProcessorService(db)
        cleaned_count = await payment_processor.cleanup_expired_orders()
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="CLEANUP_EXPIRED_ORDERS",
            resource_type="payment_order",
            details=f'{{"cleaned_count": {cleaned_count}}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "message": "过期订单清理完成",
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"清理过期订单失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理操作失败: {str(e)}"
        )