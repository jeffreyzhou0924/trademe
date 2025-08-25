"""
支付订单服务单元测试  
测试订单创建、状态管理、确认处理、过期清理等核心功能
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment_order_service import payment_order_service
from app.models.payment import USDTPaymentOrder, USDTWallet, PaymentNotification


class TestPaymentOrderService:
    """支付订单服务测试类"""
    
    @pytest.mark.asyncio
    async def test_order_creation(self, test_db_session: AsyncSession, sample_order_data):
        """测试订单创建功能"""
        # 创建可用钱包
        wallet = USDTWallet(
            network=sample_order_data["network"],
            address="TOrderCreateTest123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('1000'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # Mock钱包服务分配
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.allocate_wallet_for_payment.return_value = wallet
            mock_wallet_service.release_wallet.return_value = True
            
            # 执行订单创建
            order_data = await payment_order_service.create_payment_order(
                user_id=sample_order_data["user_id"],
                usdt_amount=Decimal(str(sample_order_data["usdt_amount"])),
                network=sample_order_data["network"],
                extra_info=sample_order_data["extra_info"]
            )
            
            # 验证订单数据
            assert order_data is not None
            assert "order_no" in order_data
            assert order_data["usdt_amount"] == sample_order_data["usdt_amount"]
            assert order_data["network"] == sample_order_data["network"]
            assert order_data["to_address"] == wallet.address
            assert order_data["status"] == "pending"
            assert "expires_at" in order_data
            assert "qr_code_data" in order_data
            
            # 验证随机金额后缀
            if sample_order_data["extra_info"]["add_random_suffix"]:
                assert order_data["expected_amount"] > sample_order_data["usdt_amount"]
                difference = order_data["expected_amount"] - sample_order_data["usdt_amount"]
                assert 0.01 <= difference <= 0.99  # 随机后缀范围
    
    @pytest.mark.asyncio
    async def test_order_no_generation_uniqueness(self):
        """测试订单号生成的唯一性"""
        # 生成多个订单号
        order_nos = []
        for _ in range(100):
            order_no = payment_order_service._generate_order_no()
            order_nos.append(order_no)
        
        # 验证唯一性
        assert len(order_nos) == len(set(order_nos))
        
        # 验证格式
        for order_no in order_nos:
            assert order_no.startswith("USDT")
            assert len(order_no) > 20  # 包含时间戳和随机后缀
    
    @pytest.mark.asyncio
    async def test_amount_validation_logic(self, test_db_session: AsyncSession):
        """测试金额验证逻辑"""
        # 测试各网络的最小金额限制
        test_cases = [
            {"network": "TRC20", "amount": 0.5, "should_pass": False},   # 低于最小值
            {"network": "TRC20", "amount": 1.0, "should_pass": True},    # 刚好最小值
            {"network": "ERC20", "amount": 5.0, "should_pass": False},   # 低于最小值
            {"network": "ERC20", "amount": 10.0, "should_pass": True},   # 刚好最小值
            {"network": "BEP20", "amount": 0.9, "should_pass": False},   # 低于最小值
            {"network": "BEP20", "amount": 1.0, "should_pass": True}     # 刚好最小值
        ]
        
        for case in test_cases:
            # Mock钱包服务（对于应该通过的情况）
            with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
                if case["should_pass"]:
                    mock_wallet = USDTWallet(
                        network=case["network"],
                        address="TAmountValidTest123456789012345678",
                        private_key_encrypted="encrypted_key",
                        balance=Decimal('1000'),
                        is_active=True
                    )
                    mock_wallet_service.allocate_wallet_for_payment.return_value = mock_wallet
                else:
                    mock_wallet_service.allocate_wallet_for_payment.return_value = None
                
                if case["should_pass"]:
                    # 应该成功创建
                    order_data = await payment_order_service.create_payment_order(
                        user_id=1,
                        usdt_amount=Decimal(str(case["amount"])),
                        network=case["network"]
                    )
                    assert order_data is not None
                else:
                    # 应该抛出异常
                    with pytest.raises(ValueError):
                        await payment_order_service.create_payment_order(
                            user_id=1,
                            usdt_amount=Decimal(str(case["amount"])),
                            network=case["network"]
                        )
    
    @pytest.mark.asyncio
    async def test_order_expiration_handling(self, test_db_session: AsyncSession):
        """测试订单过期处理"""
        # 创建过期订单
        expired_order = USDTPaymentOrder(
            order_no="EXPIRED_ORDER_001",
            user_id=1,
            wallet_id=1,
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address="TExpiredOrderTest123456789012345678",
            status="pending",
            expires_at=datetime.utcnow() - timedelta(minutes=10)  # 已过期
        )
        test_db_session.add(expired_order)
        await test_db_session.commit()
        
        # 获取订单（应该自动标记为过期）
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.release_wallet.return_value = True
            
            order_data = await payment_order_service.get_payment_order(expired_order.order_no)
            
            # 验证订单被标记为过期
            assert order_data is not None
            assert order_data["status"] == "expired"
    
    @pytest.mark.asyncio
    async def test_order_confirmation_process(self, test_db_session: AsyncSession):
        """测试订单确认流程"""
        # 创建待确认订单
        pending_order = USDTPaymentOrder(
            order_no="CONFIRM_ORDER_001",
            user_id=1,
            wallet_id=1,
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address="TConfirmOrderTest123456789012345678",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(pending_order)
        await test_db_session.commit()
        
        # Mock依赖服务
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.release_wallet.return_value = True
            
            # 确认订单
            success = await payment_order_service.confirm_payment_order(
                order_no=pending_order.order_no,
                transaction_hash="tx_confirm_12345",
                actual_amount=Decimal('10.05'),
                confirmations=12
            )
            
            # 验证确认成功
            assert success == True
            
            # 验证订单状态更新
            confirmed_order = await payment_order_service.get_payment_order(pending_order.order_no)
            assert confirmed_order["status"] == "confirmed"
            assert confirmed_order["transaction_hash"] == "tx_confirm_12345"
            assert confirmed_order["actual_amount"] == 10.05
            assert confirmed_order["confirmations"] == 12
            assert confirmed_order["confirmed_at"] is not None
    
    @pytest.mark.asyncio
    async def test_order_cancellation_logic(self, test_db_session: AsyncSession):
        """测试订单取消功能"""
        # 创建可取消订单
        cancellable_order = USDTPaymentOrder(
            order_no="CANCEL_ORDER_001",
            user_id=1,
            wallet_id=1,
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address="TCancelOrderTest123456789012345678",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(cancellable_order)
        await test_db_session.commit()
        
        # Mock钱包服务
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.release_wallet.return_value = True
            
            # 执行取消
            success = await payment_order_service.cancel_payment_order(
                order_no=cancellable_order.order_no,
                reason="用户主动取消"
            )
            
            # 验证取消成功
            assert success == True
            
            # 验证订单状态
            cancelled_order = await payment_order_service.get_payment_order(cancellable_order.order_no)
            assert cancelled_order["status"] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_statistics_calculation_accuracy(self, test_db_session: AsyncSession):
        """测试统计数据计算准确性"""
        # 创建不同状态的测试订单
        orders_data = [
            {"order_no": "STAT_ORDER_001", "status": "confirmed", "usdt_amount": 10.0, "actual_amount": 10.05},
            {"order_no": "STAT_ORDER_002", "status": "confirmed", "usdt_amount": 20.0, "actual_amount": 20.08},
            {"order_no": "STAT_ORDER_003", "status": "pending", "usdt_amount": 15.0, "actual_amount": None},
            {"order_no": "STAT_ORDER_004", "status": "expired", "usdt_amount": 5.0, "actual_amount": None},
            {"order_no": "STAT_ORDER_005", "status": "cancelled", "usdt_amount": 8.0, "actual_amount": None}
        ]
        
        for order_data in orders_data:
            order = USDTPaymentOrder(
                user_id=1,
                wallet_id=1,
                network="TRC20",
                to_address="TStatOrderTest123456789012345678",
                expires_at=datetime.utcnow() + timedelta(minutes=30),
                confirmed_at=datetime.utcnow() if order_data["status"] == "confirmed" else None,
                **{k: v for k, v in order_data.items() if k != "actual_amount" or v is not None},
                actual_amount=Decimal(str(order_data["actual_amount"])) if order_data["actual_amount"] else None
            )
            test_db_session.add(order)
        
        await test_db_session.commit()
        
        # 计算统计数据
        stats = await payment_order_service.get_payment_statistics()
        
        # 验证统计准确性
        assert stats["total_orders"] == 5
        assert stats["confirmed_orders"] == 2
        assert stats["pending_orders"] == 1
        assert stats["expired_orders"] == 1
        assert stats["cancelled_orders"] == 1
        assert stats["total_amount"] == 58.0  # 10+20+15+5+8
        assert stats["confirmed_amount"] == 30.13  # 10.05+20.08
        assert stats["average_confirmation_time"] >= 0  # 应该有确认时间
    
    @pytest.mark.asyncio
    async def test_notification_sending_mechanism(self, test_db_session: AsyncSession):
        """测试通知发送机制"""
        user_id = 123
        order_no = "NOTIFICATION_TEST_001"
        
        # 测试不同类型的通知
        notification_types = ["success", "expired", "failed"]
        
        for notification_type in notification_types:
            # 发送通知
            await payment_order_service._send_payment_notification(
                user_id=user_id,
                order_no=order_no,
                notification_type=notification_type
            )
            
            # 验证通知已创建
            from sqlalchemy import select
            query = select(PaymentNotification).where(
                PaymentNotification.user_id == user_id,
                PaymentNotification.notification_type == notification_type
            )
            result = await test_db_session.execute(query)
            notification = result.scalar_one_or_none()
            
            assert notification is not None
            assert notification.user_id == user_id
            assert order_no in notification.message
            assert notification.is_read == False
    
    @pytest.mark.asyncio
    async def test_qr_code_data_generation(self):
        """测试二维码数据生成"""
        test_cases = [
            {
                "network": "TRC20",
                "address": "TQRCodeTest123456789012345678901234",
                "amount": Decimal('10.50'),
                "expected_prefix": "tron:"
            },
            {
                "network": "ERC20", 
                "address": "0x1234567890123456789012345678901234567890",
                "amount": Decimal('25.75'),
                "expected_prefix": "ethereum:"
            },
            {
                "network": "BEP20",
                "address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "amount": Decimal('5.25'),
                "expected_prefix": "bnb:"
            }
        ]
        
        for case in test_cases:
            qr_data = payment_order_service._generate_qr_code_data(
                address=case["address"],
                amount=case["amount"],
                network=case["network"]
            )
            
            # 验证QR码数据格式
            assert qr_data.startswith(case["expected_prefix"])
            assert case["address"] in qr_data
            assert str(case["amount"]) in qr_data
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_orders_batch(self, test_db_session: AsyncSession):
        """测试批量清理过期订单"""
        # 创建多个过期订单
        expired_orders = []
        for i in range(5):
            order = USDTPaymentOrder(
                order_no=f"CLEANUP_ORDER_{i:03d}",
                user_id=1,
                wallet_id=1,
                usdt_amount=Decimal('10.0'),
                expected_amount=Decimal('10.05'),
                network="TRC20",
                to_address=f"TCleanupTest{i:030d}",
                status="pending",
                expires_at=datetime.utcnow() - timedelta(minutes=i+1)  # 都已过期
            )
            expired_orders.append(order)
            test_db_session.add(order)
        
        # 创建一个未过期订单
        active_order = USDTPaymentOrder(
            order_no="ACTIVE_ORDER_001",
            user_id=1,
            wallet_id=1,
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address="TActiveTest123456789012345678901234",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)  # 未过期
        )
        test_db_session.add(active_order)
        await test_db_session.commit()
        
        # Mock钱包服务
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.release_wallet.return_value = True
            
            # 执行清理
            cleaned_count = await payment_order_service.cleanup_expired_orders()
            
            # 验证清理结果
            assert cleaned_count == 5
            
            # 验证过期订单状态被更新
            for order in expired_orders:
                updated_order = await payment_order_service.get_payment_order(order.order_no)
                assert updated_order["status"] == "expired"
            
            # 验证未过期订单不受影响
            active_order_data = await payment_order_service.get_payment_order(active_order.order_no)
            assert active_order_data["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_concurrent_order_creation(self, test_db_session: AsyncSession):
        """测试并发订单创建"""
        # 创建有限的钱包资源
        for i in range(2):
            wallet = USDTWallet(
                network="TRC20",
                address=f"TConcurrentOrder{i:030d}",
                private_key_encrypted="encrypted_key",
                balance=Decimal('1000'),
                is_active=True,
                status="AVAILABLE"
            )
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # Mock钱包分配服务（模拟有限资源）
        allocation_count = 0
        
        async def mock_allocate_wallet(*args, **kwargs):
            nonlocal allocation_count
            if allocation_count < 2:  # 只能分配2个钱包
                allocation_count += 1
                return MagicMock(
                    id=allocation_count,
                    address=f"TMockWallet{allocation_count:030d}",
                    network="TRC20"
                )
            return None
        
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.allocate_wallet_for_payment.side_effect = mock_allocate_wallet
            
            # 并发创建多个订单
            import asyncio
            
            async def create_order(user_id):
                try:
                    return await payment_order_service.create_payment_order(
                        user_id=user_id,
                        usdt_amount=Decimal('10.0'),
                        network="TRC20"
                    )
                except Exception as e:
                    return {"error": str(e)}
            
            # 启动5个并发订单创建任务
            tasks = [create_order(i) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证并发处理结果
            successful_orders = [r for r in results if isinstance(r, dict) and "order_no" in r]
            failed_orders = [r for r in results if isinstance(r, dict) and "error" in r]
            
            assert len(successful_orders) <= 2  # 不能超过可用钱包数
            assert len(failed_orders) >= 3     # 其余应该失败