"""
USDT支付订单管理API - 完整的支付订单生命周期管理
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, validator

from app.middleware.auth import get_current_user, verify_admin_user
from app.services.payment_order_processor import (
    payment_order_processor,
    PaymentOrderRequest,
    PaymentOrderResponse,
    OrderStatus,
    PaymentType,
    create_payment_order,
    get_payment_order_status
)
from app.services.balance_synchronizer import balance_synchronizer
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic模型定义
class CreatePaymentOrderRequest(BaseModel):
    """创建支付订单请求模型"""
    payment_type: PaymentType = Field(..., description="支付类型")
    amount: Decimal = Field(..., gt=0, description="支付金额(USDT)")
    network: str = Field(..., pattern="^(TRC20|ERC20|BEP20)$", description="区块链网络")
    description: str = Field(..., min_length=1, max_length=200, description="订单描述")
    callback_url: Optional[str] = Field(None, description="回调URL")
    expire_minutes: int = Field(30, ge=5, le=1440, description="过期时间(分钟)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="扩展元数据")

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("金额必须大于0")
        if v > Decimal("100000"):
            raise ValueError("单次支付金额不能超过100,000 USDT")
        return v

    @validator('callback_url')
    def validate_callback_url(cls, v):
        if v:
            if not (v.startswith('http://') or v.startswith('https://')):
                raise ValueError("回调URL必须以http://或https://开头")
        return v


class PaymentOrderStatusResponse(BaseModel):
    """订单状态响应模型"""
    order_no: str
    user_id: int
    payment_type: str
    network: str
    to_address: str
    expected_amount: float
    actual_amount: Optional[float]
    status: str
    description: str
    transaction_hash: Optional[str]
    confirmations: Optional[int]
    created_at: str
    expires_at: Optional[str]
    confirmed_at: Optional[str]
    metadata: Optional[Dict[str, Any]]


class OrderListQuery(BaseModel):
    """订单列表查询模型"""
    status: Optional[OrderStatus] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


# API端点定义
@router.post("/create", response_model=Dict[str, Any], summary="创建支付订单")
async def create_payment_order_api(
    request: CreatePaymentOrderRequest,
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    创建新的USDT支付订单
    
    - **payment_type**: 支付类型 (membership/deposit/withdrawal/service)
    - **amount**: 支付金额 (USDT)
    - **network**: 区块链网络 (TRC20/ERC20/BEP20)
    - **description**: 订单描述
    - **callback_url**: 可选的状态回调URL
    - **expire_minutes**: 订单过期时间 (5-1440分钟)
    - **metadata**: 可选的扩展数据
    
    **返回**: 包含支付地址和订单信息的响应
    """
    try:
        # 构建订单请求
        order_request = PaymentOrderRequest(
            user_id=current_user['user_id'],
            payment_type=request.payment_type,
            amount=request.amount,
            network=request.network,
            description=request.description,
            callback_url=request.callback_url,
            expire_minutes=request.expire_minutes,
            metadata=request.metadata
        )
        
        # 创建订单
        response = await create_payment_order(order_request)
        
        logger.info(f"用户 {current_user['user_id']} 创建支付订单: {response.order_no}")
        
        return {
            "success": True,
            "message": "支付订单创建成功",
            "data": {
                "order_no": response.order_no,
                "payment_address": response.payment_address,
                "amount": float(response.amount),
                "network": response.network,
                "expires_at": response.expires_at.isoformat(),
                "status": response.status.value,
                "qr_code": response.qr_code  # TODO: 实现二维码生成
            }
        }
        
    except ValueError as e:
        logger.warning(f"创建订单参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建支付订单失败: {e}")
        raise HTTPException(status_code=500, detail="创建订单失败，请稍后重试")


@router.get("/status/{order_no}", response_model=Dict[str, Any], summary="查询订单状态")
async def get_order_status_api(
    order_no: str,
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    查询支付订单状态
    
    - **order_no**: 订单号
    
    **返回**: 详细的订单状态信息
    """
    try:
        # 获取订单状态
        order_status = await get_payment_order_status(order_no)
        
        if not order_status:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        # 权限检查 - 只能查看自己的订单或管理员可查看所有订单
        if (order_status['user_id'] != current_user['user_id'] and 
            current_user.get('role') != 'admin'):
            raise HTTPException(status_code=403, detail="无权访问该订单")
        
        return {
            "success": True,
            "data": order_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询订单状态失败 {order_no}: {e}")
        raise HTTPException(status_code=500, detail="查询订单失败")


@router.get("/list", response_model=Dict[str, Any], summary="获取用户订单列表")
async def get_user_orders_api(
    status: Optional[str] = Query(None, description="订单状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    获取当前用户的订单列表
    
    - **status**: 可选的状态过滤 (pending/processing/confirmed/expired/failed/cancelled)
    - **limit**: 返回数量限制 (1-100)
    - **offset**: 偏移量 (用于分页)
    
    **返回**: 订单列表和分页信息
    """
    try:
        # 转换状态参数
        status_filter = None
        if status:
            try:
                status_filter = OrderStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的订单状态: {status}")
        
        # 获取用户订单
        orders = await payment_order_processor.get_user_orders(
            user_id=current_user['user_id'],
            status=status_filter,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "data": {
                "orders": orders,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(orders),
                    "has_more": len(orders) == limit
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户订单列表失败 {current_user['user_id']}: {e}")
        raise HTTPException(status_code=500, detail="获取订单列表失败")


@router.post("/cancel/{order_no}", response_model=Dict[str, Any], summary="取消订单")
async def cancel_order_api(
    order_no: str,
    reason: str = Body(..., embed=True, min_length=1, max_length=100),
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    取消支付订单 (仅限pending状态)
    
    - **order_no**: 订单号
    - **reason**: 取消原因
    
    **返回**: 取消操作结果
    """
    try:
        # 检查订单是否属于当前用户
        order_status = await get_payment_order_status(order_no)
        
        if not order_status:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        if (order_status['user_id'] != current_user['user_id'] and 
            current_user.get('role') != 'admin'):
            raise HTTPException(status_code=403, detail="无权操作该订单")
        
        if order_status['status'] != OrderStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="只能取消待支付状态的订单")
        
        # 取消订单
        success = await payment_order_processor.cancel_order(order_no, reason)
        
        if not success:
            raise HTTPException(status_code=400, detail="取消订单失败")
        
        logger.info(f"用户 {current_user['user_id']} 取消订单: {order_no}, 原因: {reason}")
        
        return {
            "success": True,
            "message": "订单已成功取消",
            "data": {
                "order_no": order_no,
                "cancelled_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消订单失败 {order_no}: {e}")
        raise HTTPException(status_code=500, detail="取消订单失败")


# 管理员专用接口
@router.get("/admin/statistics", response_model=Dict[str, Any], summary="获取订单统计信息 (管理员)")
@require_auth(roles=['admin'])
async def get_payment_statistics(
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    获取支付订单统计信息 (管理员专用)
    
    **返回**: 详细的订单统计数据
    """
    try:
        # 获取订单处理器统计
        processor_stats = await payment_order_processor.get_processor_statistics()
        
        # 获取余额同步统计  
        balance_stats = await balance_synchronizer.get_sync_statistics()
        
        return {
            "success": True,
            "data": {
                "payment_processor": processor_stats,
                "balance_synchronizer": balance_stats,
                "system_status": {
                    "processor_running": processor_stats["is_running"],
                    "synchronizer_running": balance_stats["is_running"]
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取订单统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@router.post("/admin/process-transaction", response_model=Dict[str, Any], summary="手动处理区块链交易 (管理员)")
@require_auth(roles=['admin'])
async def process_blockchain_transaction_api(
    transaction_hash: str = Body(..., embed=True),
    to_address: str = Body(..., embed=True),
    amount: Decimal = Body(..., embed=True, gt=0),
    network: str = Body(..., embed=True, pattern="^(TRC20|ERC20|BEP20)$"),
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    手动处理区块链交易 (管理员专用)
    
    用于手动匹配和确认区块链交易
    
    - **transaction_hash**: 交易哈希
    - **to_address**: 接收地址
    - **amount**: 交易金额
    - **network**: 区块链网络
    """
    try:
        success = await payment_order_processor.process_blockchain_transaction(
            transaction_hash=transaction_hash,
            to_address=to_address,
            amount=amount,
            network=network
        )
        
        if success:
            logger.info(f"管理员 {current_user['user_id']} 手动处理交易: {transaction_hash}")
            return {
                "success": True,
                "message": "交易处理成功",
                "data": {
                    "transaction_hash": transaction_hash,
                    "processed_at": datetime.utcnow().isoformat()
                }
            }
        else:
            return {
                "success": False,
                "message": "未找到匹配的订单或处理失败",
                "data": None
            }
            
    except Exception as e:
        logger.error(f"手动处理交易失败: {e}")
        raise HTTPException(status_code=500, detail="处理交易失败")


@router.post("/admin/sync-wallet-balance/{wallet_id}", response_model=Dict[str, Any], summary="同步钱包余额 (管理员)")
@require_auth(roles=['admin'])
async def sync_wallet_balance_api(
    wallet_id: int,
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    手动同步指定钱包余额 (管理员专用)
    
    - **wallet_id**: 钱包ID
    """
    try:
        from app.services.balance_synchronizer import sync_wallet_balance_now
        
        result = await sync_wallet_balance_now(wallet_id)
        
        logger.info(f"管理员 {current_user['user_id']} 手动同步钱包余额: {wallet_id}")
        
        return {
            "success": True,
            "message": "钱包余额同步完成",
            "data": {
                "wallet_id": result.wallet_id,
                "address": result.address,
                "network": result.network,
                "blockchain_balance": float(result.blockchain_balance),
                "db_balance": float(result.db_balance),
                "difference": float(result.difference),
                "sync_success": result.sync_success,
                "sync_time": result.sync_time.isoformat(),
                "error_message": result.error_message
            }
        }
        
    except Exception as e:
        logger.error(f"同步钱包余额失败 {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="同步余额失败")


# 健康检查和状态接口
@router.get("/health", response_model=Dict[str, Any], summary="支付系统健康检查")
async def payment_system_health():
    """
    支付系统健康检查
    
    **返回**: 各个组件的运行状态
    """
    try:
        processor_stats = await payment_order_processor.get_processor_statistics()
        balance_stats = await balance_synchronizer.get_sync_statistics()
        
        # 简单的健康检查逻辑
        is_healthy = (
            processor_stats.get("is_running", False) and
            balance_stats.get("is_running", False)
        )
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "payment_processor": {
                    "status": "running" if processor_stats.get("is_running") else "stopped",
                    "pending_orders": processor_stats.get("pending_orders_count", 0),
                    "processing_orders": processor_stats.get("processing_orders_count", 0)
                },
                "balance_synchronizer": {
                    "status": "running" if balance_stats.get("is_running") else "stopped",
                    "total_tasks": balance_stats.get("total_tasks", 0),
                    "success_rate": balance_stats.get("success_rate", "0%")
                }
            }
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }