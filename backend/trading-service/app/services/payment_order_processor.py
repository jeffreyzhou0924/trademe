"""
支付订单处理器 - 处理USDT支付订单的完整生命周期
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from enum import Enum

from app.database import AsyncSessionLocal
from app.config import settings
from app.models.payment import USDTPaymentOrder, USDTWallet, BlockchainTransaction
from app.services.blockchain_monitor_service import blockchain_monitor_service
from app.services.usdt_wallet_service import usdt_wallet_service
from app.services.balance_synchronizer import balance_synchronizer
import logging

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    """订单状态枚举"""
    PENDING = "pending"          # 待支付
    PROCESSING = "processing"    # 处理中
    CONFIRMED = "confirmed"      # 已确认
    EXPIRED = "expired"          # 已过期
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"      # 已取消
    REFUNDED = "refunded"       # 已退款


class PaymentType(str, Enum):
    """支付类型枚举"""
    MEMBERSHIP = "membership"    # 会员充值
    DEPOSIT = "deposit"         # 资金充值
    WITHDRAWAL = "withdrawal"   # 资金提现
    SERVICE = "service"         # 服务付费


@dataclass
class PaymentOrderRequest:
    """支付订单创建请求"""
    user_id: int
    payment_type: PaymentType
    amount: Decimal
    network: str
    description: str
    callback_url: Optional[str] = None
    expire_minutes: int = 30
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PaymentOrderResponse:
    """支付订单响应"""
    order_no: str
    payment_address: str
    amount: Decimal
    network: str
    qr_code: Optional[str] = None
    expires_at: datetime = None
    status: OrderStatus = OrderStatus.PENDING


class PaymentOrderProcessor:
    """支付订单处理器 - 管理支付订单完整生命周期"""
    
    def __init__(self):
        self.is_running = False
        self.processing_interval = 10  # 处理间隔(秒)
        self.order_timeout = settings.payment_timeout_minutes * 60  # 订单超时时间(秒)
        self.confirmation_blocks = settings.blockchain_confirmation_blocks  # 确认块数
        
        # 处理统计
        self.total_orders = 0
        self.processed_orders = 0
        self.confirmed_orders = 0
        self.expired_orders = 0
        self.failed_orders = 0
        
        # 订单缓存
        self.pending_orders: Dict[str, USDTPaymentOrder] = {}
        self.processing_orders: Dict[str, USDTPaymentOrder] = {}
        
        logger.info("支付订单处理器初始化完成")
    
    async def start_processor(self):
        """启动订单处理器"""
        if self.is_running:
            logger.warning("支付订单处理器已在运行中")
            return
        
        self.is_running = True
        logger.info("启动支付订单处理器")
        
        # 加载待处理订单
        await self._load_pending_orders()
        
        # 启动处理循环
        asyncio.create_task(self._processing_loop())
    
    async def stop_processor(self):
        """停止订单处理器"""
        self.is_running = False
        logger.info("支付订单处理器已停止")
    
    async def create_payment_order(
        self, 
        request: PaymentOrderRequest
    ) -> PaymentOrderResponse:
        """创建支付订单"""
        try:
            # 生成订单号
            order_no = self._generate_order_no(request.payment_type)
            
            # 分配钱包
            wallet = await usdt_wallet_service.allocate_wallet(order_no, request.network)
            if not wallet:
                raise ValueError(f"无法分配 {request.network} 网络钱包")
            
            # 计算过期时间
            expires_at = datetime.utcnow() + timedelta(minutes=request.expire_minutes)
            
            # 创建订单记录
            async with AsyncSessionLocal() as session:
                payment_order = USDTPaymentOrder(
                    order_no=order_no,
                    user_id=request.user_id,
                    payment_type=request.payment_type.value,
                    network=request.network,
                    wallet_id=wallet['id'],
                    to_address=wallet['address'],
                    expected_amount=request.amount,
                    status=OrderStatus.PENDING.value,
                    description=request.description,
                    callback_url=request.callback_url,
                    expires_at=expires_at,
                    metadata=json.dumps(request.metadata) if request.metadata else None
                )
                
                session.add(payment_order)
                await session.commit()
                
                # 添加到待处理订单缓存
                self.pending_orders[order_no] = payment_order
                
                logger.info(f"创建支付订单: {order_no}, 金额: {request.amount} USDT")
                
                return PaymentOrderResponse(
                    order_no=order_no,
                    payment_address=wallet['address'],
                    amount=request.amount,
                    network=request.network,
                    expires_at=expires_at,
                    status=OrderStatus.PENDING
                )
                
        except Exception as e:
            logger.error(f"创建支付订单失败: {e}")
            raise
    
    async def get_order_status(self, order_no: str) -> Optional[Dict[str, Any]]:
        """获取订单状态"""
        try:
            async with AsyncSessionLocal() as session:
                query = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.order_no == order_no
                )
                result = await session.execute(query)
                order = result.scalar_one_or_none()
                
                if not order:
                    return None
                
                return {
                    "order_no": order.order_no,
                    "user_id": order.user_id,
                    "payment_type": order.payment_type,
                    "network": order.network,
                    "to_address": order.to_address,
                    "expected_amount": float(order.expected_amount),
                    "actual_amount": float(order.actual_amount) if order.actual_amount else None,
                    "status": order.status,
                    "description": order.description,
                    "transaction_hash": order.transaction_hash,
                    "confirmations": order.confirmations,
                    "created_at": order.created_at.isoformat(),
                    "expires_at": order.expires_at.isoformat() if order.expires_at else None,
                    "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None,
                    "metadata": json.loads(order.metadata) if order.metadata else None
                }
                
        except Exception as e:
            logger.error(f"获取订单状态失败 {order_no}: {e}")
            return None
    
    async def cancel_order(self, order_no: str, reason: str = "用户取消") -> bool:
        """取消订单"""
        try:
            async with AsyncSessionLocal() as session:
                # 更新订单状态
                update_result = await session.execute(
                    update(USDTPaymentOrder)
                    .where(
                        and_(
                            USDTPaymentOrder.order_no == order_no,
                            USDTPaymentOrder.status.in_([OrderStatus.PENDING.value])
                        )
                    )
                    .values(
                        status=OrderStatus.CANCELLED.value,
                        description=f"{reason}",
                        updated_at=datetime.utcnow()
                    )
                )
                
                if update_result.rowcount == 0:
                    logger.warning(f"无法取消订单 {order_no} - 订单不存在或状态不允许取消")
                    return False
                
                await session.commit()
                
                # 释放钱包
                await usdt_wallet_service.release_wallet(order_no)
                
                # 从缓存中移除
                self.pending_orders.pop(order_no, None)
                self.processing_orders.pop(order_no, None)
                
                logger.info(f"订单 {order_no} 已取消: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"取消订单失败 {order_no}: {e}")
            return False
    
    async def process_blockchain_transaction(
        self, 
        transaction_hash: str, 
        to_address: str, 
        amount: Decimal,
        network: str
    ) -> bool:
        """处理区块链交易 - 匹配订单并确认支付"""
        try:
            # 查找匹配的订单
            async with AsyncSessionLocal() as session:
                query = select(USDTPaymentOrder).where(
                    and_(
                        USDTPaymentOrder.to_address == to_address,
                        USDTPaymentOrder.network == network,
                        USDTPaymentOrder.status == OrderStatus.PENDING.value
                    )
                )
                result = await session.execute(query)
                orders = result.scalars().all()
                
                if not orders:
                    logger.warning(f"未找到匹配的订单: {to_address} ({network})")
                    return False
                
                # 找到最佳匹配订单
                best_match = self._find_best_matching_order(orders, amount)
                if not best_match:
                    logger.warning(f"未找到金额匹配的订单: {amount} USDT")
                    return False
                
                # 获取交易确认状态
                tx_status = await blockchain_monitor_service.get_transaction_status(
                    transaction_hash, 
                    network
                )
                
                # 更新订单状态
                await session.execute(
                    update(USDTPaymentOrder)
                    .where(USDTPaymentOrder.id == best_match.id)
                    .values(
                        status=OrderStatus.PROCESSING.value,
                        actual_amount=amount,
                        transaction_hash=transaction_hash,
                        confirmations=tx_status.get('confirmations', 0),
                        updated_at=datetime.utcnow()
                    )
                )
                
                await session.commit()
                
                # 移动到处理中订单缓存
                self.pending_orders.pop(best_match.order_no, None)
                self.processing_orders[best_match.order_no] = best_match
                
                logger.info(f"订单 {best_match.order_no} 开始处理交易: {transaction_hash}")
                
                # 如果确认数足够，直接确认订单
                if tx_status.get('confirmations', 0) >= self.confirmation_blocks:
                    await self._confirm_order(best_match.order_no, tx_status)
                
                return True
                
        except Exception as e:
            logger.error(f"处理区块链交易失败: {e}")
            return False
    
    async def get_user_orders(
        self, 
        user_id: int, 
        status: Optional[OrderStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取用户订单列表"""
        try:
            async with AsyncSessionLocal() as session:
                query = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.user_id == user_id
                )
                
                if status:
                    query = query.where(USDTPaymentOrder.status == status.value)
                
                query = query.order_by(USDTPaymentOrder.created_at.desc())
                query = query.limit(limit).offset(offset)
                
                result = await session.execute(query)
                orders = result.scalars().all()
                
                return [
                    {
                        "order_no": order.order_no,
                        "payment_type": order.payment_type,
                        "network": order.network,
                        "expected_amount": float(order.expected_amount),
                        "actual_amount": float(order.actual_amount) if order.actual_amount else None,
                        "status": order.status,
                        "description": order.description,
                        "created_at": order.created_at.isoformat(),
                        "expires_at": order.expires_at.isoformat() if order.expires_at else None,
                        "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None
                    }
                    for order in orders
                ]
                
        except Exception as e:
            logger.error(f"获取用户订单失败 {user_id}: {e}")
            return []
    
    async def get_processor_statistics(self) -> Dict[str, Any]:
        """获取处理器统计信息"""
        async with AsyncSessionLocal() as session:
            # 统计不同状态的订单数量
            status_stats = {}
            for status in OrderStatus:
                query = select(func.count(USDTPaymentOrder.id)).where(
                    USDTPaymentOrder.status == status.value
                )
                result = await session.execute(query)
                count = result.scalar()
                status_stats[status.value] = count
            
            # 统计今日订单
            today = datetime.utcnow().date()
            today_query = select(func.count(USDTPaymentOrder.id)).where(
                func.date(USDTPaymentOrder.created_at) == today
            )
            today_result = await session.execute(today_query)
            today_orders = today_result.scalar()
            
            # 统计今日金额
            amount_query = select(func.sum(USDTPaymentOrder.actual_amount)).where(
                and_(
                    func.date(USDTPaymentOrder.created_at) == today,
                    USDTPaymentOrder.status == OrderStatus.CONFIRMED.value
                )
            )
            amount_result = await session.execute(amount_query)
            today_amount = amount_result.scalar() or Decimal('0')
        
        return {
            "status_distribution": status_stats,
            "pending_orders_count": len(self.pending_orders),
            "processing_orders_count": len(self.processing_orders),
            "today_orders": today_orders,
            "today_confirmed_amount": float(today_amount),
            "total_processed": self.processed_orders,
            "total_confirmed": self.confirmed_orders,
            "total_expired": self.expired_orders,
            "total_failed": self.failed_orders,
            "is_running": self.is_running
        }
    
    async def _load_pending_orders(self):
        """加载待处理订单"""
        try:
            async with AsyncSessionLocal() as session:
                # 加载待支付订单
                pending_query = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.status == OrderStatus.PENDING.value
                )
                pending_result = await session.execute(pending_query)
                pending_orders = pending_result.scalars().all()
                
                for order in pending_orders:
                    self.pending_orders[order.order_no] = order
                
                # 加载处理中订单
                processing_query = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.status == OrderStatus.PROCESSING.value
                )
                processing_result = await session.execute(processing_query)
                processing_orders = processing_result.scalars().all()
                
                for order in processing_orders:
                    self.processing_orders[order.order_no] = order
                
                logger.info(
                    f"已加载订单 - 待支付: {len(self.pending_orders)}, "
                    f"处理中: {len(self.processing_orders)}"
                )
                
        except Exception as e:
            logger.error(f"加载待处理订单失败: {e}")
    
    async def _processing_loop(self):
        """处理主循环"""
        while self.is_running:
            try:
                # 检查过期订单
                await self._check_expired_orders()
                
                # 检查处理中订单的确认状态
                await self._check_processing_orders()
                
                # 等待下一个处理周期
                await asyncio.sleep(self.processing_interval)
                
            except Exception as e:
                logger.error(f"处理循环错误: {e}")
                await asyncio.sleep(self.processing_interval)
    
    async def _check_expired_orders(self):
        """检查并处理过期订单"""
        current_time = datetime.utcnow()
        expired_orders = []
        
        for order_no, order in self.pending_orders.items():
            if order.expires_at and current_time > order.expires_at:
                expired_orders.append(order_no)
        
        for order_no in expired_orders:
            await self._expire_order(order_no)
    
    async def _check_processing_orders(self):
        """检查处理中订单的确认状态"""
        for order_no, order in list(self.processing_orders.items()):
            try:
                if not order.transaction_hash:
                    continue
                
                # 获取最新交易状态
                tx_status = await blockchain_monitor_service.get_transaction_status(
                    order.transaction_hash,
                    order.network
                )
                
                confirmations = tx_status.get('confirmations', 0)
                
                # 更新确认数
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(USDTPaymentOrder)
                        .where(USDTPaymentOrder.order_no == order_no)
                        .values(
                            confirmations=confirmations,
                            updated_at=datetime.utcnow()
                        )
                    )
                    await session.commit()
                
                # 检查是否达到确认要求
                if confirmations >= self.confirmation_blocks:
                    await self._confirm_order(order_no, tx_status)
                
            except Exception as e:
                logger.error(f"检查处理中订单 {order_no} 失败: {e}")
    
    async def _confirm_order(self, order_no: str, tx_status: Dict[str, Any]):
        """确认订单"""
        try:
            async with AsyncSessionLocal() as session:
                # 更新订单为已确认
                await session.execute(
                    update(USDTPaymentOrder)
                    .where(USDTPaymentOrder.order_no == order_no)
                    .values(
                        status=OrderStatus.CONFIRMED.value,
                        confirmations=tx_status.get('confirmations', 0),
                        confirmed_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
                
                await session.commit()
                
                # 从处理中缓存移除
                order = self.processing_orders.pop(order_no, None)
                
                if order:
                    # 释放钱包
                    await usdt_wallet_service.release_wallet(order_no)
                    
                    # 触发回调
                    if order.callback_url:
                        asyncio.create_task(self._send_callback(order, OrderStatus.CONFIRMED))
                    
                    # 更新统计
                    self.confirmed_orders += 1
                    
                    logger.info(f"订单 {order_no} 已确认")
                
        except Exception as e:
            logger.error(f"确认订单 {order_no} 失败: {e}")
    
    async def _expire_order(self, order_no: str):
        """过期订单"""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(USDTPaymentOrder)
                    .where(USDTPaymentOrder.order_no == order_no)
                    .values(
                        status=OrderStatus.EXPIRED.value,
                        updated_at=datetime.utcnow()
                    )
                )
                
                await session.commit()
                
                # 从缓存移除
                order = self.pending_orders.pop(order_no, None)
                
                if order:
                    # 释放钱包
                    await usdt_wallet_service.release_wallet(order_no)
                    
                    # 触发回调
                    if order.callback_url:
                        asyncio.create_task(self._send_callback(order, OrderStatus.EXPIRED))
                    
                    # 更新统计
                    self.expired_orders += 1
                    
                    logger.info(f"订单 {order_no} 已过期")
                
        except Exception as e:
            logger.error(f"处理过期订单 {order_no} 失败: {e}")
    
    async def _send_callback(self, order: USDTPaymentOrder, status: OrderStatus):
        """发送回调通知"""
        try:
            import aiohttp
            
            callback_data = {
                "order_no": order.order_no,
                "user_id": order.user_id,
                "status": status.value,
                "amount": float(order.actual_amount) if order.actual_amount else float(order.expected_amount),
                "transaction_hash": order.transaction_hash,
                "confirmations": order.confirmations,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    order.callback_url,
                    json=callback_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"回调通知发送成功: {order.order_no}")
                    else:
                        logger.warning(f"回调通知失败: {order.order_no}, 状态码: {response.status}")
                        
        except Exception as e:
            logger.error(f"发送回调通知失败 {order.order_no}: {e}")
    
    def _generate_order_no(self, payment_type: PaymentType) -> str:
        """生成订单号"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        type_prefix = {
            PaymentType.MEMBERSHIP: "MEM",
            PaymentType.DEPOSIT: "DEP", 
            PaymentType.WITHDRAWAL: "WDR",
            PaymentType.SERVICE: "SVC"
        }.get(payment_type, "PAY")
        
        random_suffix = str(uuid.uuid4().hex)[:6].upper()
        return f"{type_prefix}{timestamp}{random_suffix}"
    
    def _find_best_matching_order(
        self, 
        orders: List[USDTPaymentOrder], 
        amount: Decimal
    ) -> Optional[USDTPaymentOrder]:
        """找到最佳匹配的订单"""
        # 精确匹配
        for order in orders:
            if order.expected_amount == amount:
                return order
        
        # 容差匹配 (±1%)
        tolerance = Decimal('0.01')
        for order in orders:
            diff = abs(order.expected_amount - amount)
            if diff <= order.expected_amount * tolerance:
                return order
        
        return None


# 全局订单处理器实例
payment_order_processor = PaymentOrderProcessor()


# 便捷函数
async def start_payment_processor():
    """启动支付订单处理器"""
    await payment_order_processor.start_processor()


async def stop_payment_processor():
    """停止支付订单处理器"""
    await payment_order_processor.stop_processor()


async def create_payment_order(request: PaymentOrderRequest) -> PaymentOrderResponse:
    """创建支付订单"""
    return await payment_order_processor.create_payment_order(request)


async def get_payment_order_status(order_no: str) -> Optional[Dict[str, Any]]:
    """获取订单状态"""
    return await payment_order_processor.get_order_status(order_no)


if __name__ == "__main__":
    """测试代码"""
    import asyncio
    
    async def test_payment_processor():
        """测试支付处理器"""
        print("=== 测试支付订单处理器 ===")
        
        try:
            # 创建测试请求
            request = PaymentOrderRequest(
                user_id=1,
                payment_type=PaymentType.MEMBERSHIP,
                amount=Decimal("99.99"),
                network="TRC20",
                description="高级会员充值",
                expire_minutes=30
            )
            
            # 测试创建订单
            print("\n1. 测试创建订单")
            response = await create_payment_order(request)
            print(f"订单号: {response.order_no}")
            print(f"支付地址: {response.payment_address}")
            print(f"金额: {response.amount}")
            
            # 测试获取订单状态
            print("\n2. 测试获取订单状态")
            status = await get_payment_order_status(response.order_no)
            print(f"订单状态: {status}")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    # 运行测试
    asyncio.run(test_payment_processor())