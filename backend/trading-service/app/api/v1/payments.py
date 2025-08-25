"""
USDT支付订单管理API
提供支付订单的创建、查询、确认等功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime

from app.services.payment_order_service import payment_order_service
from app.services.blockchain_monitor_service import blockchain_monitor_service
from app.middleware.auth import get_current_user, admin_required
from app.schemas.response import ResponseModel, SuccessResponse, ErrorResponse

router = APIRouter(prefix="/payments", tags=["支付管理"])


# Request Models
class CreatePaymentOrderRequest(BaseModel):
    """创建支付订单请求"""
    usdt_amount: float = Field(..., gt=0, description="USDT金额")
    network: str = Field(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$")
    membership_plan_id: Optional[int] = Field(None, description="会员计划ID")
    add_random_suffix: bool = Field(True, description="是否添加随机金额后缀")
    risk_level: str = Field("LOW", description="风险等级", regex="^(LOW|MEDIUM|HIGH)$")


class ConfirmPaymentRequest(BaseModel):
    """确认支付请求"""
    transaction_hash: str = Field(..., description="交易哈希")
    actual_amount: float = Field(..., gt=0, description="实际支付金额")
    confirmations: int = Field(1, ge=0, description="确认数")


# Response Models
class PaymentOrderResponse(BaseModel):
    """支付订单响应"""
    order_no: str
    usdt_amount: float
    expected_amount: float
    actual_amount: Optional[float]
    network: str
    to_address: str
    from_address: Optional[str]
    transaction_hash: Optional[str]
    status: str
    confirmations: int
    required_confirmations: int
    expires_at: str
    confirmed_at: Optional[str]
    created_at: str
    qr_code_data: str


class PaymentStatisticsResponse(BaseModel):
    """支付统计响应"""
    total_orders: int
    confirmed_orders: int
    pending_orders: int
    expired_orders: int
    cancelled_orders: int
    total_amount: float
    confirmed_amount: float
    network_distribution: Dict[str, int]
    average_confirmation_time: float


# API Endpoints
@router.post("/orders", response_model=SuccessResponse)
async def create_payment_order(
    request: CreatePaymentOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    创建USDT支付订单
    
    - **usdt_amount**: USDT支付金额
    - **network**: 区块链网络 (TRC20/ERC20/BEP20)
    - **membership_plan_id**: 可选的会员计划ID
    - **add_random_suffix**: 是否添加随机金额后缀以区分订单
    - **risk_level**: 用户风险等级，影响钱包分配策略
    
    返回订单信息包括：
    - 订单号
    - 支付地址
    - 期望金额
    - 过期时间
    - 二维码数据
    """
    try:
        user_id = current_user["user_id"]
        
        extra_info = {
            'risk_level': request.risk_level,
            'add_random_suffix': request.add_random_suffix
        }
        
        order_data = await payment_order_service.create_payment_order(
            user_id=user_id,
            usdt_amount=Decimal(str(request.usdt_amount)),
            network=request.network,
            membership_plan_id=request.membership_plan_id,
            extra_info=extra_info
        )
        
        return SuccessResponse(
            message="支付订单创建成功",
            data=order_data
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建支付订单失败: {str(e)}")


@router.get("/orders/{order_no}", response_model=SuccessResponse)
async def get_payment_order(
    order_no: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取支付订单详情
    
    - **order_no**: 订单号
    
    返回完整的订单信息，包括状态、金额、地址等
    """
    try:
        order_data = await payment_order_service.get_payment_order(order_no)
        
        if not order_data:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        # 验证订单所有权（非管理员只能查看自己的订单）
        if order_data["user_id"] != current_user["user_id"] and not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="无权访问此订单")
        
        return SuccessResponse(
            message="获取订单信息成功",
            data=order_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取订单信息失败: {str(e)}")


@router.get("/orders", response_model=SuccessResponse)
async def get_user_payment_orders(
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="订单状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    获取当前用户的支付订单列表
    
    - **status**: 可选的状态筛选 (pending/confirmed/expired/cancelled)
    - **limit**: 返回数量限制，最大100
    - **offset**: 分页偏移量
    """
    try:
        user_id = current_user["user_id"]
        
        orders_data = await payment_order_service.get_user_payment_orders(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return SuccessResponse(
            message="获取订单列表成功",
            data={
                "orders": orders_data,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(orders_data)
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取订单列表失败: {str(e)}")


@router.post("/orders/{order_no}/confirm", response_model=SuccessResponse)
async def confirm_payment_order(
    order_no: str,
    request: ConfirmPaymentRequest,
    current_user: dict = Depends(admin_required)
):
    """
    管理员确认支付订单（手动确认）
    
    - **order_no**: 订单号
    - **transaction_hash**: 区块链交易哈希
    - **actual_amount**: 实际支付金额
    - **confirmations**: 确认数
    
    注意：通常由区块链监控服务自动确认，此接口用于特殊情况下的手动干预
    """
    try:
        success = await payment_order_service.confirm_payment_order(
            order_no=order_no,
            transaction_hash=request.transaction_hash,
            actual_amount=Decimal(str(request.actual_amount)),
            confirmations=request.confirmations
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="确认支付失败，请检查订单状态和参数")
        
        return SuccessResponse(
            message="支付订单确认成功",
            data={"order_no": order_no, "status": "confirmed"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认支付失败: {str(e)}")


@router.post("/orders/{order_no}/cancel", response_model=SuccessResponse)
async def cancel_payment_order(
    order_no: str,
    reason: str = Query("用户取消", description="取消原因"),
    current_user: dict = Depends(get_current_user)
):
    """
    取消支付订单
    
    - **order_no**: 订单号
    - **reason**: 取消原因
    
    只有订单创建者或管理员可以取消订单
    """
    try:
        # 验证订单所有权
        order_data = await payment_order_service.get_payment_order(order_no)
        if not order_data:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        if order_data["user_id"] != current_user["user_id"] and not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="无权取消此订单")
        
        success = await payment_order_service.cancel_payment_order(order_no, reason)
        
        if not success:
            raise HTTPException(status_code=400, detail="取消订单失败，请检查订单状态")
        
        return SuccessResponse(
            message="订单取消成功",
            data={"order_no": order_no, "status": "cancelled"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消订单失败: {str(e)}")


@router.get("/transactions/{tx_hash}/status", response_model=SuccessResponse)
async def get_transaction_status(
    tx_hash: str,
    network: str = Query(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    查询区块链交易状态
    
    - **tx_hash**: 交易哈希
    - **network**: 网络类型
    
    返回交易的确认状态、确认数、区块高度等信息
    """
    try:
        tx_status = await blockchain_monitor_service.get_transaction_status(tx_hash, network)
        
        return SuccessResponse(
            message="获取交易状态成功",
            data={
                "transaction_hash": tx_hash,
                "network": network,
                **tx_status
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询交易状态失败: {str(e)}")


@router.get("/wallets/{address}/balance", response_model=SuccessResponse)
async def get_wallet_balance(
    address: str,
    network: str = Query(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$"),
    current_user: dict = Depends(admin_required)
):
    """
    查询钱包地址USDT余额（管理员功能）
    
    - **address**: 钱包地址
    - **network**: 网络类型
    
    从区块链直接查询地址余额
    """
    try:
        balance = await blockchain_monitor_service.get_address_balance(address, network)
        
        return SuccessResponse(
            message="获取钱包余额成功",
            data={
                "address": address,
                "network": network,
                "balance": float(balance)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询钱包余额失败: {str(e)}")


@router.get("/statistics", response_model=SuccessResponse)
async def get_payment_statistics(
    current_user: dict = Depends(admin_required),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期")
):
    """
    获取支付统计信息（管理员功能）
    
    - **start_date**: 统计开始日期
    - **end_date**: 统计结束日期
    
    返回订单数量、金额、网络分布、平均确认时间等统计数据
    """
    try:
        stats = await payment_order_service.get_payment_statistics(start_date, end_date)
        
        return SuccessResponse(
            message="获取统计信息成功",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.post("/maintenance/cleanup-expired", response_model=SuccessResponse)
async def cleanup_expired_orders(
    current_user: dict = Depends(admin_required)
):
    """
    清理过期订单（管理员功能）
    
    手动触发过期订单清理，释放占用的钱包资源
    """
    try:
        cleaned_count = await payment_order_service.cleanup_expired_orders()
        
        return SuccessResponse(
            message="清理过期订单完成",
            data={
                "cleaned_orders": cleaned_count
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理过期订单失败: {str(e)}")


# Webhook接口（用于第三方支付回调）
@router.post("/webhook/payment-confirmation")
async def payment_confirmation_webhook(request: dict):
    """
    支付确认Webhook
    
    用于接收第三方支付服务的回调通知
    """
    try:
        # 这里可以添加webhook签名验证
        order_no = request.get("order_no")
        transaction_hash = request.get("transaction_hash")
        actual_amount = request.get("actual_amount")
        
        if not all([order_no, transaction_hash, actual_amount]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        # 记录webhook
        from app.models.payment import PaymentWebhook
        from app.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            webhook = PaymentWebhook(
                webhook_type="payment_confirmed",
                payload=str(request),
                processed=False
            )
            session.add(webhook)
            await session.commit()
        
        # 处理支付确认
        success = await payment_order_service.confirm_payment_order(
            order_no=order_no,
            transaction_hash=transaction_hash,
            actual_amount=Decimal(str(actual_amount))
        )
        
        return {"status": "success" if success else "failed"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}