"""
支付处理服务 - USDT支付订单处理和确认
"""

import asyncio
import uuid
from typing import Optional, Dict, List, Any
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_

from app.models.payment import USDTPaymentOrder, USDTWallet, PaymentNotification
from app.models.user import User
from app.models.membership import MembershipPlan
from app.services.wallet_pool_service import WalletPoolService
from app.services.blockchain_monitor import BlockchainMonitorService, TransactionStatus
from app.core.exceptions import PaymentError, ValidationError, WalletError
import logging

logger = logging.getLogger(__name__)


class PaymentOrder:
    """支付订单数据类"""
    
    def __init__(
        self, 
        id: int, 
        order_no: str,
        user_id: int,
        wallet_id: int,
        network: str,
        payment_address: str,
        expected_amount: Decimal,
        status: str,
        expires_at: datetime,
        created_at: datetime
    ):
        self.id = id
        self.order_no = order_no
        self.user_id = user_id
        self.wallet_id = wallet_id
        self.network = network
        self.payment_address = payment_address
        self.expected_amount = expected_amount
        self.status = status
        self.expires_at = expires_at
        self.created_at = created_at


class PaymentProcessorService:
    """支付处理核心服务"""
    
    # 订单状态常量
    STATUS_PENDING = "pending"          # 待支付
    STATUS_CONFIRMING = "confirming"    # 确认中
    STATUS_CONFIRMED = "confirmed"      # 已确认
    STATUS_EXPIRED = "expired"          # 已过期
    STATUS_FAILED = "failed"           # 失败
    STATUS_CANCELLED = "cancelled"     # 已取消
    
    # 支付超时时间（分钟）
    PAYMENT_TIMEOUT_MINUTES = 30
    
    # 金额容差（允许的差额）
    AMOUNT_TOLERANCE = Decimal('0.1')  # 0.1 USDT
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_service = WalletPoolService(db)
        self.blockchain_monitor = BlockchainMonitorService(db)
        
    async def create_payment_order(
        self,
        user_id: int,
        membership_plan_id: int,
        network: str,
        amount: Decimal,
        admin_id: Optional[int] = None
    ) -> PaymentOrder:
        """
        创建支付订单
        
        Args:
            user_id: 用户ID
            membership_plan_id: 会员计划ID
            network: 网络类型
            amount: 支付金额
            admin_id: 管理员ID（如果是管理员创建）
            
        Returns:
            支付订单信息
        """
        if amount <= 0:
            raise ValidationError("支付金额必须大于0")
            
        if network not in ["TRC20", "ERC20", "BEP20"]:
            raise ValidationError(f"不支持的网络类型: {network}")
            
        try:
            # 验证用户是否存在
            user_query = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise ValidationError(f"用户不存在: {user_id}")
            
            # 验证会员计划
            plan_query = select(MembershipPlan).where(MembershipPlan.id == membership_plan_id)
            plan_result = await self.db.execute(plan_query)
            plan = plan_result.scalar_one_or_none()
            
            if not plan:
                raise ValidationError(f"会员计划不存在: {membership_plan_id}")
            
            # 检查用户是否有未完成的订单
            existing_order = await self.db.execute(
                select(USDTPaymentOrder).where(
                    and_(
                        USDTPaymentOrder.user_id == user_id,
                        USDTPaymentOrder.status.in_([self.STATUS_PENDING, self.STATUS_CONFIRMING]),
                        USDTPaymentOrder.expires_at > datetime.utcnow()
                    )
                )
            )
            
            if existing_order.scalar_one_or_none():
                raise PaymentError("用户有未完成的支付订单")
            
            # 分配钱包地址
            wallet_info = await self.wallet_service.allocate_wallet(
                order_id=f"temp_{user_id}_{int(datetime.utcnow().timestamp())}",
                network=network
            )
            
            if not wallet_info:
                raise PaymentError(f"没有可用的{network}钱包地址")
            
            # 生成订单号
            order_no = self._generate_order_number()
            
            # 计算过期时间
            expires_at = datetime.utcnow() + timedelta(minutes=self.PAYMENT_TIMEOUT_MINUTES)
            
            # 创建支付订单
            payment_order = USDTPaymentOrder(
                order_no=order_no,
                user_id=user_id,
                wallet_id=wallet_info.id,
                membership_plan_id=membership_plan_id,
                network=network,
                usdt_amount=amount,
                expected_amount=amount,
                to_address=wallet_info.address,
                status=self.STATUS_PENDING,
                required_confirmations=1 if network == "TRC20" else (12 if network == "ERC20" else 3),
                expires_at=expires_at
            )
            
            self.db.add(payment_order)
            await self.db.flush()  # 获取生成的ID
            
            # 更新钱包的订单关联
            await self.db.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_info.id)
                .values(current_order_id=order_no)
            )
            
            await self.db.commit()
            
            # 创建支付通知
            await self._create_payment_notification(
                user_id=user_id,
                order_id=payment_order.id,
                notification_type="payment_created",
                title="支付订单已创建",
                message=f"请在{self.PAYMENT_TIMEOUT_MINUTES}分钟内完成{amount} USDT支付"
            )
            
            logger.info(f"创建支付订单成功: {order_no}, 用户: {user_id}, 金额: {amount}, 地址: {wallet_info.address}")
            
            return PaymentOrder(
                id=payment_order.id,
                order_no=order_no,
                user_id=user_id,
                wallet_id=wallet_info.id,
                network=network,
                payment_address=wallet_info.address,
                expected_amount=amount,
                status=self.STATUS_PENDING,
                expires_at=expires_at,
                created_at=payment_order.created_at
            )
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建支付订单失败: {e}")
            raise PaymentError(f"支付订单创建失败: {str(e)}")
    
    async def process_payment_confirmation(
        self,
        tx_hash: str,
        network: str,
        from_address: str,
        to_address: str,
        amount: Decimal,
        confirmations: int = 1
    ) -> bool:
        """
        处理支付确认
        
        Args:
            tx_hash: 交易哈希
            network: 网络类型
            from_address: 付款地址
            to_address: 收款地址
            amount: 转账金额
            confirmations: 确认数
            
        Returns:
            是否处理成功
        """
        try:
            # 查找对应的支付订单
            order_query = select(USDTPaymentOrder).join(
                USDTWallet,
                USDTPaymentOrder.wallet_id == USDTWallet.id
            ).where(
                and_(
                    USDTWallet.address == to_address,
                    USDTWallet.network == network,
                    USDTPaymentOrder.status.in_([self.STATUS_PENDING, self.STATUS_CONFIRMING]),
                    USDTPaymentOrder.expires_at > datetime.utcnow()
                )
            )
            
            order_result = await self.db.execute(order_query)
            order = order_result.scalar_one_or_none()
            
            if not order:
                logger.warning(f"未找到匹配的支付订单: {to_address}, {network}, {amount}")
                return False
            
            # 验证金额是否匹配
            amount_diff = abs(amount - order.expected_amount)
            if amount_diff > self.AMOUNT_TOLERANCE:
                logger.warning(f"支付金额不匹配: 期望 {order.expected_amount}, 实际 {amount}")
                await self._handle_amount_mismatch(order, amount, tx_hash)
                return False
            
            # 更新订单信息
            update_data = {
                "transaction_hash": tx_hash,
                "actual_amount": amount,
                "from_address": from_address,
                "confirmations": confirmations,
                "updated_at": datetime.utcnow()
            }
            
            # 根据确认数决定状态
            if confirmations >= order.required_confirmations:
                update_data["status"] = self.STATUS_CONFIRMED
                update_data["confirmed_at"] = datetime.utcnow()
            else:
                update_data["status"] = self.STATUS_CONFIRMING
            
            await self.db.execute(
                update(USDTPaymentOrder)
                .where(USDTPaymentOrder.id == order.id)
                .values(**update_data)
            )
            
            # 如果支付已确认，处理会员升级
            if confirmations >= order.required_confirmations:
                await self._process_membership_upgrade(order)
                
                # 释放钱包
                await self.wallet_service.release_wallet(order.wallet_id)
                
                # 创建成功通知
                await self._create_payment_notification(
                    user_id=order.user_id,
                    order_id=order.id,
                    notification_type="payment_success",
                    title="支付成功",
                    message=f"USDT支付已确认，金额: {amount}"
                )
                
                logger.info(f"支付确认成功: 订单 {order.order_no}, 交易 {tx_hash}")
            else:
                # 创建确认中通知
                await self._create_payment_notification(
                    user_id=order.user_id,
                    order_id=order.id,
                    notification_type="payment_confirming",
                    title="支付确认中",
                    message=f"交易已检测到，等待确认 ({confirmations}/{order.required_confirmations})"
                )
                
                logger.info(f"支付确认中: 订单 {order.order_no}, 确认数 {confirmations}/{order.required_confirmations}")
            
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"处理支付确认失败: {e}")
            return False
    
    async def handle_payment_timeout(self, order_id: int) -> bool:
        """
        处理支付超时
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否处理成功
        """
        try:
            # 获取订单信息
            order_query = select(USDTPaymentOrder).where(USDTPaymentOrder.id == order_id)
            order_result = await self.db.execute(order_query)
            order = order_result.scalar_one_or_none()
            
            if not order:
                return False
                
            # 检查是否已过期且仍为pending状态
            if order.expires_at <= datetime.utcnow() and order.status == self.STATUS_PENDING:
                # 更新订单状态为过期
                await self.db.execute(
                    update(USDTPaymentOrder)
                    .where(USDTPaymentOrder.id == order_id)
                    .values(
                        status=self.STATUS_EXPIRED,
                        updated_at=datetime.utcnow()
                    )
                )
                
                # 释放钱包
                await self.wallet_service.release_wallet(order.wallet_id)
                
                # 创建过期通知
                await self._create_payment_notification(
                    user_id=order.user_id,
                    order_id=order.id,
                    notification_type="payment_expired",
                    title="支付已过期",
                    message=f"订单 {order.order_no} 已过期，请重新创建支付"
                )
                
                await self.db.commit()
                
                logger.info(f"支付订单超时处理: {order.order_no}")
                return True
                
        except Exception as e:
            await self.db.rollback()
            logger.error(f"处理支付超时失败: {e}")
            
        return False
    
    async def cancel_payment_order(self, order_id: int, admin_id: Optional[int] = None) -> bool:
        """
        取消支付订单
        
        Args:
            order_id: 订单ID
            admin_id: 管理员ID
            
        Returns:
            是否取消成功
        """
        try:
            # 获取订单信息
            order_query = select(USDTPaymentOrder).where(USDTPaymentOrder.id == order_id)
            order_result = await self.db.execute(order_query)
            order = order_result.scalar_one_or_none()
            
            if not order:
                return False
            
            # 只能取消pending或confirming状态的订单
            if order.status not in [self.STATUS_PENDING, self.STATUS_CONFIRMING]:
                raise PaymentError(f"无法取消状态为 {order.status} 的订单")
            
            # 更新订单状态
            await self.db.execute(
                update(USDTPaymentOrder)
                .where(USDTPaymentOrder.id == order_id)
                .values(
                    status=self.STATUS_CANCELLED,
                    cancelled_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            
            # 释放钱包
            await self.wallet_service.release_wallet(order.wallet_id, admin_id)
            
            # 创建取消通知
            await self._create_payment_notification(
                user_id=order.user_id,
                order_id=order.id,
                notification_type="payment_cancelled",
                title="支付已取消",
                message=f"订单 {order.order_no} 已被取消"
            )
            
            await self.db.commit()
            
            logger.info(f"支付订单取消: {order.order_no}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"取消支付订单失败: {e}")
            return False
    
    async def get_order_status(self, order_no: str) -> Optional[Dict]:
        """
        获取订单状态
        
        Args:
            order_no: 订单号
            
        Returns:
            订单状态信息
        """
        try:
            order_query = select(USDTPaymentOrder).where(USDTPaymentOrder.order_no == order_no)
            order_result = await self.db.execute(order_query)
            order = order_result.scalar_one_or_none()
            
            if not order:
                return None
            
            # 如果有交易哈希，检查最新确认状态
            latest_confirmations = order.confirmations
            if order.transaction_hash and order.status == self.STATUS_CONFIRMING:
                try:
                    tx_status = await self.blockchain_monitor.check_transaction(
                        order.transaction_hash, 
                        order.network
                    )
                    latest_confirmations = tx_status.confirmations
                    
                    # 如果确认数足够，更新状态
                    if tx_status.is_confirmed and latest_confirmations >= order.required_confirmations:
                        await self.process_payment_confirmation(
                            order.transaction_hash,
                            order.network,
                            order.from_address or '',
                            order.to_address,
                            order.actual_amount or order.expected_amount,
                            latest_confirmations
                        )
                except Exception as e:
                    logger.error(f"检查交易状态失败: {e}")
            
            return {
                "order_no": order.order_no,
                "status": order.status,
                "network": order.network,
                "payment_address": order.to_address,
                "expected_amount": float(order.expected_amount),
                "actual_amount": float(order.actual_amount) if order.actual_amount else None,
                "transaction_hash": order.transaction_hash,
                "confirmations": latest_confirmations,
                "required_confirmations": order.required_confirmations,
                "expires_at": order.expires_at.isoformat(),
                "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None,
                "created_at": order.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取订单状态失败: {e}")
            return None
    
    async def cleanup_expired_orders(self) -> int:
        """
        清理过期订单
        
        Returns:
            清理的订单数量
        """
        try:
            # 查找过期的pending订单
            expired_orders_query = select(USDTPaymentOrder).where(
                and_(
                    USDTPaymentOrder.status == self.STATUS_PENDING,
                    USDTPaymentOrder.expires_at <= datetime.utcnow()
                )
            )
            
            expired_orders_result = await self.db.execute(expired_orders_query)
            expired_orders = expired_orders_result.scalars().all()
            
            cleaned_count = 0
            
            for order in expired_orders:
                if await self.handle_payment_timeout(order.id):
                    cleaned_count += 1
            
            logger.info(f"清理过期订单完成: {cleaned_count} 个")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理过期订单失败: {e}")
            return 0
    
    def _generate_order_number(self) -> str:
        """生成订单号"""
        timestamp = int(datetime.utcnow().timestamp())
        random_suffix = uuid.uuid4().hex[:8]
        return f"USDT{timestamp}{random_suffix}".upper()
    
    async def _process_membership_upgrade(self, order: USDTPaymentOrder):
        """处理会员升级"""
        try:
            # 获取会员计划信息
            plan_query = select(MembershipPlan).where(MembershipPlan.id == order.membership_plan_id)
            plan_result = await self.db.execute(plan_query)
            plan = plan_result.scalar_one_or_none()
            
            if not plan:
                logger.error(f"会员计划不存在: {order.membership_plan_id}")
                return
            
            # 计算新的过期时间
            current_time = datetime.utcnow()
            new_expires_at = current_time + timedelta(days=plan.duration_months * 30)
            
            # 更新用户会员信息
            await self.db.execute(
                update(User)
                .where(User.id == order.user_id)
                .values(
                    membership_level=plan.level,
                    membership_expires_at=new_expires_at,
                    updated_at=current_time
                )
            )
            
            logger.info(f"用户会员升级成功: 用户 {order.user_id}, 等级 {plan.level}")
            
        except Exception as e:
            logger.error(f"处理会员升级失败: {e}")
    
    async def _handle_amount_mismatch(self, order: USDTPaymentOrder, actual_amount: Decimal, tx_hash: str):
        """处理金额不匹配"""
        try:
            # 更新订单状态为失败
            await self.db.execute(
                update(USDTPaymentOrder)
                .where(USDTPaymentOrder.id == order.id)
                .values(
                    status=self.STATUS_FAILED,
                    transaction_hash=tx_hash,
                    actual_amount=actual_amount,
                    updated_at=datetime.utcnow()
                )
            )
            
            # 释放钱包
            await self.wallet_service.release_wallet(order.wallet_id)
            
            # 创建失败通知
            await self._create_payment_notification(
                user_id=order.user_id,
                order_id=order.id,
                notification_type="payment_failed",
                title="支付金额错误",
                message=f"支付金额 {actual_amount} 与订单金额 {order.expected_amount} 不匹配"
            )
            
            logger.warning(f"支付金额不匹配: 订单 {order.order_no}, 期望 {order.expected_amount}, 实际 {actual_amount}")
            
        except Exception as e:
            logger.error(f"处理金额不匹配失败: {e}")
    
    async def _create_payment_notification(
        self,
        user_id: int,
        order_id: int,
        notification_type: str,
        title: str,
        message: str
    ):
        """创建支付通知"""
        try:
            notification = PaymentNotification(
                user_id=user_id,
                order_id=order_id,
                notification_type=notification_type,
                title=title,
                message=message,
                is_read=False,
                send_email=True,
                email_sent=False
            )
            
            self.db.add(notification)
            await self.db.flush()
            
        except Exception as e:
            logger.error(f"创建支付通知失败: {e}")
    
    async def start_background_tasks(self):
        """启动后台任务"""
        # 启动过期订单清理任务
        asyncio.create_task(self._cleanup_expired_orders_task())
        
        # 启动区块链监控
        for network in ["TRC20", "ERC20", "BEP20"]:
            await self.blockchain_monitor.start_monitoring(network)
    
    async def _cleanup_expired_orders_task(self):
        """过期订单清理后台任务"""
        while True:
            try:
                await self.cleanup_expired_orders()
                await asyncio.sleep(300)  # 每5分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理过期订单任务出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试