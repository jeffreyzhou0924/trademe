"""
服务间集成测试
测试USDT支付系统各服务模块间的协调工作
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.usdt_wallet_service import usdt_wallet_service
from app.services.payment_order_service import payment_order_service
from app.services.blockchain_monitor_service import blockchain_monitor_service
from app.models.payment import USDTWallet, USDTPaymentOrder


class TestServiceIntegration:
    """服务集成测试类"""
    
    @pytest.mark.asyncio
    async def test_wallet_allocation_flow(self, test_db_session: AsyncSession, clean_database):
        """测试钱包分配完整流程"""
        # 1. 创建可用钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TIntegrationFlow123456789012345678",
            private_key_encrypted="encrypted_test_key",
            balance=Decimal('1000'),
            risk_level="LOW",
            is_active=True,
            status="AVAILABLE",
            success_rate=0.95,
            avg_response_time=1.5
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # 2. Mock区块链监控服务
        with patch('app.services.payment_order_service.blockchain_monitor_service') as mock_blockchain:
            mock_blockchain.add_wallet_monitoring.return_value = True
            
            # 3. 执行完整的订单创建流程（会调用钱包分配）
            order_data = await payment_order_service.create_payment_order(
                user_id=1,
                usdt_amount=Decimal('10.0'),
                network="TRC20"
            )
            
            # 4. 验证订单创建成功
            assert order_data is not None
            assert order_data["order_no"] is not None
            assert order_data["to_address"] == wallet.address
            assert order_data["status"] == "pending"
            
            # 5. 验证钱包被正确分配
            await test_db_session.refresh(wallet)
            assert wallet.status == "ALLOCATED"
            assert wallet.current_order_id == order_data["order_no"]
            
            # 6. 验证区块链监控被启动
            mock_blockchain.add_wallet_monitoring.assert_called_once_with(
                wallet.id, wallet.address, "TRC20"
            )
    
    @pytest.mark.asyncio
    async def test_payment_monitoring_flow(self, test_db_session: AsyncSession, clean_database):
        """测试支付监控完整流程"""
        # 1. 创建待监控的订单
        wallet = USDTWallet(
            network="TRC20",
            address="TMonitoringFlow123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True,
            status="ALLOCATED",
            current_order_id="MONITOR_ORDER_001"
        )
        test_db_session.add(wallet)
        
        order = USDTPaymentOrder(
            order_no="MONITOR_ORDER_001",
            user_id=1,
            wallet_id=1,  # 将在commit后更新
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address=wallet.address,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(order)
        await test_db_session.commit()
        
        # 更新wallet_id
        order.wallet_id = wallet.id
        await test_db_session.commit()
        
        # 2. Mock区块链监控发现交易
        incoming_transaction = {
            "hash": "tx_monitoring_flow_001",
            "to_address": wallet.address,
            "from_address": "TSenderAddress123456789012345678901234",
            "amount": Decimal('10.05'),
            "confirmations": 1,
            "block_height": 12345,
            "timestamp": datetime.utcnow(),
            "status": "SUCCESS"
        }
        
        # 3. 执行支付匹配流程
        match_result = await blockchain_monitor_service.match_payment_transaction(
            transaction=incoming_transaction,
            session=test_db_session
        )
        
        # 4. 验证匹配成功
        assert match_result is not None
        assert match_result["matched"] == True
        assert match_result["order_no"] == order.order_no
        
        # 5. Mock钱包服务释放
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.release_wallet.return_value = True
            
            # 6. 执行订单确认流程
            confirm_success = await payment_order_service.confirm_payment_order(
                order_no=order.order_no,
                transaction_hash=incoming_transaction["hash"],
                actual_amount=incoming_transaction["amount"],
                confirmations=incoming_transaction["confirmations"]
            )
            
            # 7. 验证确认成功
            assert confirm_success == True
            
            # 8. 验证订单状态更新
            confirmed_order = await payment_order_service.get_payment_order(order.order_no)
            assert confirmed_order["status"] == "confirmed"
            assert confirmed_order["transaction_hash"] == incoming_transaction["hash"]
            
            # 9. 验证钱包释放被调用
            mock_wallet_service.release_wallet.assert_called_once_with(order.order_no)
    
    @pytest.mark.asyncio
    async def test_order_confirmation_flow(self, test_db_session: AsyncSession, clean_database):
        """测试订单确认完整流程"""
        # 创建测试订单和钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TConfirmationFlow123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True,
            status="ALLOCATED"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        order = USDTPaymentOrder(
            order_no="CONFIRM_FLOW_001",
            user_id=1,
            wallet_id=wallet.id,
            usdt_amount=Decimal('15.0'),
            expected_amount=Decimal('15.08'),
            network="TRC20",
            to_address=wallet.address,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(order)
        await test_db_session.commit()
        
        # Mock所有相关服务
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service, \
             patch('app.services.payment_order_service.notification_service') as mock_notification:
            
            mock_wallet_service.release_wallet.return_value = True
            mock_notification.send_notification.return_value = True
            
            # 执行订单确认
            success = await payment_order_service.confirm_payment_order(
                order_no=order.order_no,
                transaction_hash="tx_confirm_integration_test",
                actual_amount=Decimal('15.08'),
                confirmations=12
            )
            
            # 验证确认流程
            assert success == True
            
            # 验证订单状态
            await test_db_session.refresh(order)
            assert order.status == "confirmed"
            assert order.transaction_hash == "tx_confirm_integration_test"
            assert order.actual_amount == Decimal('15.08')
            assert order.confirmations == 12
            assert order.confirmed_at is not None
            
            # 验证钱包释放
            mock_wallet_service.release_wallet.assert_called_once_with(order.order_no)
    
    @pytest.mark.asyncio
    async def test_error_propagation(self, test_db_session: AsyncSession, clean_database):
        """测试错误传播机制"""
        # 测试钱包分配失败时的错误处理
        with patch('app.services.usdt_wallet_service.USDTWallet') as mock_wallet_model:
            # Mock数据库错误
            mock_wallet_model.side_effect = Exception("Database connection failed")
            
            # 尝试创建订单（应该失败）
            with pytest.raises(Exception) as exc_info:
                await payment_order_service.create_payment_order(
                    user_id=1,
                    usdt_amount=Decimal('10.0'),
                    network="TRC20"
                )
            
            # 验证错误信息
            assert "Database connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, test_db_session: AsyncSession, clean_database):
        """测试事务回滚处理"""
        # 创建钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TRollbackTest123456789012345678901",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        initial_wallet_count = len((await test_db_session.execute(
            "SELECT * FROM usdt_wallets"
        )).fetchall())
        
        # Mock订单创建中途失败
        with patch('app.services.payment_order_service.USDTPaymentOrder') as mock_order_model:
            # 第一次调用成功（创建订单），第二次调用失败（更新钱包）
            mock_order_model.side_effect = [
                MagicMock(),  # 订单创建成功
                Exception("Wallet update failed")  # 钱包更新失败
            ]
            
            # Mock钱包分配成功
            with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
                mock_wallet_service.allocate_wallet_for_payment.return_value = wallet
                
                # 尝试创建订单（应该失败并回滚）
                with pytest.raises(Exception):
                    await payment_order_service.create_payment_order(
                        user_id=1,
                        usdt_amount=Decimal('10.0'),
                        network="TRC20"
                    )
                
                # 验证钱包状态没有被改变（事务回滚）
                await test_db_session.refresh(wallet)
                assert wallet.status == "AVAILABLE"
                assert wallet.current_order_id is None
                
                # 验证没有创建新的订单记录
                orders = (await test_db_session.execute(
                    "SELECT * FROM usdt_payment_orders"
                )).fetchall()
                assert len(orders) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_coordination(self, test_db_session: AsyncSession, clean_database):
        """测试并发操作协调"""
        # 创建有限的钱包资源
        wallets = []
        for i in range(2):
            wallet = USDTWallet(
                network="TRC20",
                address=f"TConcurrent{i:030d}",
                private_key_encrypted="encrypted_key",
                balance=Decimal('100'),
                is_active=True,
                status="AVAILABLE"
            )
            wallets.append(wallet)
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # Mock区块链监控服务
        with patch('app.services.payment_order_service.blockchain_monitor_service') as mock_blockchain:
            mock_blockchain.add_wallet_monitoring.return_value = True
            
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
            
            # 启动并发任务
            tasks = [create_order(i) for i in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证结果
            successful_orders = [r for r in results if isinstance(r, dict) and "order_no" in r]
            assert len(successful_orders) <= 2  # 不能超过可用钱包数
            
            # 验证没有钱包被重复分配
            allocated_addresses = []
            for wallet in wallets:
                await test_db_session.refresh(wallet)
                if wallet.status == "ALLOCATED":
                    allocated_addresses.append(wallet.address)
            
            assert len(allocated_addresses) == len(set(allocated_addresses))  # 无重复
    
    @pytest.mark.asyncio 
    async def test_cross_service_data_consistency(self, test_db_session: AsyncSession, clean_database):
        """测试跨服务数据一致性"""
        # 创建初始数据
        wallet = USDTWallet(
            network="TRC20",
            address="TDataConsistency123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # Mock区块链服务
        with patch('app.services.payment_order_service.blockchain_monitor_service') as mock_blockchain:
            mock_blockchain.add_wallet_monitoring.return_value = True
            
            # 1. 创建订单
            order_data = await payment_order_service.create_payment_order(
                user_id=1,
                usdt_amount=Decimal('25.0'),
                network="TRC20"
            )
            
            # 2. 验证数据一致性
            # 钱包状态应该更新
            await test_db_session.refresh(wallet)
            assert wallet.status == "ALLOCATED"
            assert wallet.current_order_id == order_data["order_no"]
            
            # 3. 查询订单，验证关联正确
            order_details = await payment_order_service.get_payment_order(order_data["order_no"])
            assert order_details["to_address"] == wallet.address
            assert order_details["network"] == wallet.network
            
            # 4. Mock钱包服务
            with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
                mock_wallet_service.release_wallet.return_value = True
                
                # 5. 确认支付
                confirm_success = await payment_order_service.confirm_payment_order(
                    order_no=order_data["order_no"],
                    transaction_hash="tx_consistency_test",
                    actual_amount=Decimal('25.0'),
                    confirmations=6
                )
                
                # 6. 验证数据一致性保持
                assert confirm_success == True
                
                # 订单状态应该更新
                confirmed_order = await payment_order_service.get_payment_order(order_data["order_no"])
                assert confirmed_order["status"] == "confirmed"
                assert confirmed_order["transaction_hash"] == "tx_consistency_test"
                
                # 钱包释放应该被调用
                mock_wallet_service.release_wallet.assert_called_once_with(order_data["order_no"])
    
    @pytest.mark.asyncio
    async def test_service_timeout_handling(self, test_db_session: AsyncSession, clean_database):
        """测试服务超时处理"""
        # 创建过期订单
        wallet = USDTWallet(
            network="TRC20",
            address="TTimeoutTest123456789012345678901",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True,
            status="ALLOCATED",
            current_order_id="TIMEOUT_ORDER_001"
        )
        test_db_session.add(wallet)
        
        expired_order = USDTPaymentOrder(
            order_no="TIMEOUT_ORDER_001",
            user_id=1,
            wallet_id=1,  # 将在commit后更新
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address=wallet.address,
            status="pending",
            expires_at=datetime.utcnow() - timedelta(minutes=10)  # 已过期
        )
        test_db_session.add(expired_order)
        await test_db_session.commit()
        
        # 更新wallet_id
        expired_order.wallet_id = wallet.id
        await test_db_session.commit()
        
        # Mock钱包释放服务
        with patch('app.services.payment_order_service.usdt_wallet_service') as mock_wallet_service:
            mock_wallet_service.release_wallet.return_value = True
            
            # 执行过期订单清理
            cleaned_count = await payment_order_service.cleanup_expired_orders()
            
            # 验证清理结果
            assert cleaned_count == 1
            
            # 验证订单状态更新
            await test_db_session.refresh(expired_order)
            assert expired_order.status == "expired"
            
            # 验证钱包释放被调用
            mock_wallet_service.release_wallet.assert_called_once_with("TIMEOUT_ORDER_001")