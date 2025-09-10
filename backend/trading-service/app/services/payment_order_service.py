"""
USDT支付订单管理服务
负责支付订单的创建、状态管理、确认处理等核心业务逻辑
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import AsyncSessionLocal
from app.models.payment import (
    USDTPaymentOrder, 
    USDTWallet, 
    PaymentWebhook, 
    PaymentNotification
)
from app.services.usdt_wallet_service import usdt_wallet_service
from app.services.blockchain_monitor_service import blockchain_monitor_service
from app.config import settings


class PaymentOrderService:
    """支付订单管理服务"""
    
    def __init__(self):
        self.default_timeout_minutes = settings.payment_timeout_minutes
        self.supported_networks = ['TRC20', 'ERC20', 'BEP20']
        self.min_amounts = {
            'TRC20': Decimal('1.0'),    # 最小1 USDT
            'ERC20': Decimal('10.0'),   # 最小10 USDT (考虑gas费)
            'BEP20': Decimal('1.0')     # 最小1 USDT
        }
    
    def _generate_order_no(self) -> str:
        """生成唯一订单号"""
        timestamp = int(datetime.utcnow().timestamp())
        random_suffix = secrets.token_hex(8)
        return f"USDT{timestamp}{random_suffix}"
    
    async def create_payment_order(
        self,
        user_id: int,
        usdt_amount: Decimal,
        network: str = 'TRC20',
        membership_plan_id: Optional[int] = None,
        extra_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建USDT支付订单
        
        Args:
            user_id: 用户ID
            usdt_amount: USDT金额
            network: 网络类型 (TRC20/ERC20/BEP20)
            membership_plan_id: 会员计划ID (可选)
            extra_info: 额外信息 (可选)
        
        Returns:
            订单信息字典
        """
        async with AsyncSessionLocal() as session:
            try:
                # 1. 验证参数
                if network not in self.supported_networks:
                    raise ValueError(f"不支持的网络类型: {network}")
                
                if usdt_amount < self.min_amounts.get(network, Decimal('1.0')):
                    raise ValueError(f"{network} 网络最小金额为 {self.min_amounts[network]} USDT")
                
                # 2. 分配钱包地址
                wallet = await usdt_wallet_service.allocate_wallet_for_payment(
                    order_no="temp",  # 临时订单号，后面会更新
                    network=network,
                    amount=usdt_amount,
                    user_risk_level=extra_info.get('risk_level', 'LOW') if extra_info else 'LOW'
                )
                
                if not wallet:
                    raise ValueError("暂时无可用钱包地址，请稍后重试")
                
                # 3. 创建订单
                order_no = self._generate_order_no()
                expires_at = datetime.utcnow() + timedelta(minutes=self.default_timeout_minutes)
                
                # 计算期望金额（可能包含小额随机数以区分订单）
                expected_amount = usdt_amount
                if extra_info and extra_info.get('add_random_suffix', True):
                    # 添加小额随机数 (0.01-0.99 USDT)
                    random_cents = Decimal(secrets.randbelow(99) + 1) / 100
                    expected_amount = usdt_amount + random_cents
                
                payment_order = USDTPaymentOrder(
                    order_no=order_no,
                    user_id=user_id,
                    wallet_id=wallet.id,
                    membership_plan_id=membership_plan_id,
                    usdt_amount=usdt_amount,
                    expected_amount=expected_amount,
                    network=network,
                    to_address=wallet.address,
                    status='pending',
                    expires_at=expires_at,
                    required_confirmations=1 if network == 'TRC20' else 12
                )
                
                session.add(payment_order)
                await session.commit()
                await session.refresh(payment_order)
                
                # 4. 更新钱包的当前订单ID
                await session.execute(
                    update(USDTWallet)
                    .where(USDTWallet.id == wallet.id)
                    .values(current_order_id=order_no)
                )
                await session.commit()
                
                # 5. 添加钱包到区块链监控
                await blockchain_monitor_service.add_wallet_monitoring(
                    wallet.id, wallet.address, network
                )
                
                logger.info(f"创建支付订单成功: {order_no}, 用户: {user_id}, 金额: {usdt_amount} {network}")
                
                return {
                    'order_no': order_no,
                    'usdt_amount': float(usdt_amount),
                    'expected_amount': float(expected_amount),
                    'network': network,
                    'to_address': wallet.address,
                    'expires_at': expires_at.isoformat(),
                    'status': 'pending',
                    'qr_code_data': self._generate_qr_code_data(wallet.address, expected_amount, network)
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"创建支付订单失败: {e}")
                raise
    
    def _generate_qr_code_data(self, address: str, amount: Decimal, network: str) -> str:
        """生成支付二维码数据"""
        if network == 'TRC20':
            return f"tron:{address}?amount={amount}&token=USDT"
        elif network == 'ERC20':
            return f"ethereum:{address}?value=0&token=0xdAC17F958D2ee523a2206206994597C13D831ec7&uint256={int(amount * 1000000)}"
        elif network == 'BEP20':
            return f"bnb:{address}?amount={amount}&token=USDT"
        else:
            return f"{address}"
    
    async def get_payment_order(self, order_no: str) -> Optional[Dict[str, Any]]:
        """获取支付订单详情"""
        async with AsyncSessionLocal() as session:
            query = select(USDTPaymentOrder).where(
                USDTPaymentOrder.order_no == order_no
            )
            
            result = await session.execute(query)
            order = result.scalar_one_or_none()
            
            if not order:
                return None
            
            # 检查订单是否过期
            if order.status == 'pending' and datetime.utcnow() > order.expires_at:
                await self._expire_payment_order(session, order)
                order.status = 'expired'
            
            return {
                'order_no': order.order_no,
                'user_id': order.user_id,
                'usdt_amount': float(order.usdt_amount),
                'expected_amount': float(order.expected_amount),
                'actual_amount': float(order.actual_amount) if order.actual_amount else None,
                'network': order.network,
                'to_address': order.to_address,
                'from_address': order.from_address,
                'transaction_hash': order.transaction_hash,
                'status': order.status,
                'confirmations': order.confirmations,
                'required_confirmations': order.required_confirmations,
                'expires_at': order.expires_at.isoformat(),
                'confirmed_at': order.confirmed_at.isoformat() if order.confirmed_at else None,
                'created_at': order.created_at.isoformat(),
                'qr_code_data': self._generate_qr_code_data(order.to_address, order.expected_amount, order.network)
            }
    
    async def get_user_payment_orders(
        self, 
        user_id: int, 
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取用户支付订单列表"""
        async with AsyncSessionLocal() as session:
            conditions = [USDTPaymentOrder.user_id == user_id]
            
            if status:
                conditions.append(USDTPaymentOrder.status == status)
            
            query = select(USDTPaymentOrder).where(
                and_(*conditions)
            ).order_by(
                USDTPaymentOrder.created_at.desc()
            ).limit(limit).offset(offset)
            
            result = await session.execute(query)
            orders = result.scalars().all()
            
            return [
                {
                    'order_no': order.order_no,
                    'usdt_amount': float(order.usdt_amount),
                    'expected_amount': float(order.expected_amount),
                    'actual_amount': float(order.actual_amount) if order.actual_amount else None,
                    'network': order.network,
                    'to_address': order.to_address,
                    'transaction_hash': order.transaction_hash,
                    'status': order.status,
                    'expires_at': order.expires_at.isoformat(),
                    'confirmed_at': order.confirmed_at.isoformat() if order.confirmed_at else None,
                    'created_at': order.created_at.isoformat()
                }
                for order in orders
            ]
    
    async def confirm_payment_order(
        self,
        order_no: str,
        transaction_hash: str,
        actual_amount: Decimal,
        confirmations: int = 1
    ) -> bool:
        """确认支付订单（通常由区块链监控服务调用）"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.order_no == order_no
                )
                
                result = await session.execute(query)
                order = result.scalar_one_or_none()
                
                if not order:
                    logger.error(f"订单不存在: {order_no}")
                    return False
                
                if order.status != 'pending':
                    logger.warning(f"订单状态不正确: {order_no}, 当前状态: {order.status}")
                    return False
                
                # 验证金额（允许1%误差）
                expected_amount = order.expected_amount
                tolerance = expected_amount * Decimal('0.01')
                
                if abs(actual_amount - expected_amount) > tolerance:
                    logger.error(f"订单金额不匹配: {order_no}, 期望: {expected_amount}, 实际: {actual_amount}")
                    return False
                
                # 更新订单状态
                await session.execute(
                    update(USDTPaymentOrder)
                    .where(USDTPaymentOrder.id == order.id)
                    .values(
                        status='confirmed',
                        transaction_hash=transaction_hash,
                        actual_amount=actual_amount,
                        confirmations=confirmations,
                        confirmed_at=datetime.utcnow()
                    )
                )
                
                await session.commit()
                
                # 释放钱包分配
                await usdt_wallet_service.release_wallet(order_no)
                
                # 发送支付成功通知
                await self._send_payment_notification(order.user_id, order_no, 'success')
                
                logger.info(f"支付订单确认成功: {order_no}, 交易哈希: {transaction_hash}")
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error(f"确认支付订单失败: {order_no}, 错误: {e}")
                return False
    
    async def cancel_payment_order(self, order_no: str, reason: str = "用户取消") -> bool:
        """取消支付订单"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.order_no == order_no
                )
                
                result = await session.execute(query)
                order = result.scalar_one_or_none()
                
                if not order:
                    return False
                
                if order.status not in ['pending']:
                    logger.warning(f"订单状态不允许取消: {order_no}, 状态: {order.status}")
                    return False
                
                # 更新订单状态
                await session.execute(
                    update(USDTPaymentOrder)
                    .where(USDTPaymentOrder.id == order.id)
                    .values(
                        status='cancelled',
                        cancelled_at=datetime.utcnow()
                    )
                )
                
                await session.commit()
                
                # 释放钱包分配
                await usdt_wallet_service.release_wallet(order_no)
                
                logger.info(f"支付订单已取消: {order_no}, 原因: {reason}")
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error(f"取消支付订单失败: {order_no}, 错误: {e}")
                return False
    
    async def _expire_payment_order(self, session: AsyncSession, order: USDTPaymentOrder):
        """处理订单过期"""
        try:
            await session.execute(
                update(USDTPaymentOrder)
                .where(USDTPaymentOrder.id == order.id)
                .values(status='expired')
            )
            
            await session.commit()
            
            # 释放钱包分配
            await usdt_wallet_service.release_wallet(order.order_no)
            
            # 发送过期通知
            await self._send_payment_notification(order.user_id, order.order_no, 'expired')
            
            logger.info(f"支付订单已过期: {order.order_no}")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"处理订单过期失败: {order.order_no}, 错误: {e}")
    
    async def cleanup_expired_orders(self) -> int:
        """清理过期订单（定时任务）"""
        async with AsyncSessionLocal() as session:
            current_time = datetime.utcnow()
            
            # 查找过期的待支付订单
            query = select(USDTPaymentOrder).where(
                and_(
                    USDTPaymentOrder.status == 'pending',
                    USDTPaymentOrder.expires_at < current_time
                )
            )
            
            result = await session.execute(query)
            expired_orders = result.scalars().all()
            
            cleaned_count = 0
            for order in expired_orders:
                await self._expire_payment_order(session, order)
                cleaned_count += 1
            
            logger.info(f"清理过期订单: {cleaned_count} 个")
            return cleaned_count
    
    async def _send_payment_notification(
        self, 
        user_id: int, 
        order_no: str, 
        notification_type: str
    ):
        """发送支付通知"""
        async with AsyncSessionLocal() as session:
            try:
                titles = {
                    'success': '支付成功',
                    'expired': '支付超时',
                    'failed': '支付失败'
                }
                
                messages = {
                    'success': f'您的USDT支付订单 {order_no} 已确认成功。',
                    'expired': f'您的USDT支付订单 {order_no} 已超时，请重新创建订单。',
                    'failed': f'您的USDT支付订单 {order_no} 支付失败，请联系客服。'
                }
                
                notification = PaymentNotification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=titles.get(notification_type, '支付通知'),
                    message=messages.get(notification_type, f'订单 {order_no} 状态更新'),
                    is_read=False
                )
                
                session.add(notification)
                await session.commit()
                
            except Exception as e:
                logger.error(f"发送支付通知失败: {e}")
    
    async def get_payment_statistics(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取支付统计信息"""
        async with AsyncSessionLocal() as session:
            conditions = []
            
            if start_date:
                conditions.append(USDTPaymentOrder.created_at >= start_date)
            if end_date:
                conditions.append(USDTPaymentOrder.created_at <= end_date)
            
            query = select(USDTPaymentOrder)
            if conditions:
                query = query.where(and_(*conditions))
            
            result = await session.execute(query)
            orders = result.scalars().all()
            
            # 统计数据
            stats = {
                'total_orders': len(orders),
                'confirmed_orders': 0,
                'pending_orders': 0,
                'expired_orders': 0,
                'cancelled_orders': 0,
                'total_amount': Decimal('0'),
                'confirmed_amount': Decimal('0'),
                'network_distribution': {},
                'average_confirmation_time': 0
            }
            
            confirmation_times = []
            
            for order in orders:
                stats[f"{order.status}_orders"] += 1
                stats['total_amount'] += order.usdt_amount
                
                if order.status == 'confirmed':
                    stats['confirmed_amount'] += order.actual_amount or order.usdt_amount
                    if order.confirmed_at and order.created_at:
                        confirmation_time = (order.confirmed_at - order.created_at).total_seconds() / 60
                        confirmation_times.append(confirmation_time)
                
                # 网络分布统计
                network = order.network
                if network in stats['network_distribution']:
                    stats['network_distribution'][network] += 1
                else:
                    stats['network_distribution'][network] = 1
            
            # 计算平均确认时间
            if confirmation_times:
                stats['average_confirmation_time'] = sum(confirmation_times) / len(confirmation_times)
            
            # 转换Decimal为float便于JSON序列化
            stats['total_amount'] = float(stats['total_amount'])
            stats['confirmed_amount'] = float(stats['confirmed_amount'])
            
            return stats


# 全局实例
payment_order_service = PaymentOrderService()