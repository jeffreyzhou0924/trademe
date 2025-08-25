"""
数据库集成测试
测试数据一致性、事务处理、并发访问、外键约束等
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text, select, update, delete
from sqlalchemy.orm import selectinload

from app.models.payment import (
    USDTWallet, USDTPaymentOrder, PaymentNotification, 
    PaymentWebhook, ClaudeAccount, Proxy
)
from app.database import AsyncSessionLocal


class TestDatabaseIntegration:
    """数据库集成测试类"""
    
    @pytest.mark.asyncio
    async def test_data_consistency_across_tables(self, test_db_session: AsyncSession, clean_database):
        """测试表间数据一致性"""
        # 创建关联数据
        wallet = USDTWallet(
            network="TRC20",
            address="TConsistencyTest123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('500.0'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.flush()  # 获取wallet.id
        
        order = USDTPaymentOrder(
            order_no="CONSISTENCY_ORDER_001",
            user_id=1,
            wallet_id=wallet.id,
            usdt_amount=Decimal('50.0'),
            expected_amount=Decimal('50.05'),
            network="TRC20",
            to_address=wallet.address,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(order)
        await test_db_session.commit()
        
        # 验证关联数据一致性
        # 1. 通过wallet查询关联的orders
        wallet_with_orders = await test_db_session.execute(
            select(USDTWallet).options(selectinload(USDTWallet.payment_orders)).where(USDTWallet.id == wallet.id)
        )
        wallet_result = wallet_with_orders.scalar_one()
        assert len(wallet_result.payment_orders) == 1
        assert wallet_result.payment_orders[0].order_no == order.order_no
        
        # 2. 通过order查询关联的wallet
        order_with_wallet = await test_db_session.execute(
            select(USDTPaymentOrder).options(selectinload(USDTPaymentOrder.wallet)).where(USDTPaymentOrder.id == order.id)
        )
        order_result = order_with_wallet.scalar_one()
        assert order_result.wallet.address == wallet.address
        
        # 3. 验证地址一致性
        assert order_result.to_address == order_result.wallet.address
    
    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, test_db_session: AsyncSession, clean_database):
        """测试外键约束检查"""
        # 测试插入不存在的wallet_id
        invalid_order = USDTPaymentOrder(
            order_no="INVALID_WALLET_ORDER",
            user_id=1,
            wallet_id=99999,  # 不存在的wallet_id
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address="TInvalidTest123456789012345678901",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        
        test_db_session.add(invalid_order)
        
        # 应该抛出外键约束错误
        with pytest.raises(IntegrityError):
            await test_db_session.commit()
        
        await test_db_session.rollback()
        
        # 测试删除被引用的钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TForeignKeyTest123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True
        )
        test_db_session.add(wallet)
        await test_db_session.flush()
        
        order = USDTPaymentOrder(
            order_no="FK_TEST_ORDER",
            user_id=1,
            wallet_id=wallet.id,
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),
            network="TRC20",
            to_address=wallet.address,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(order)
        await test_db_session.commit()
        
        # 尝试删除被引用的钱包
        with pytest.raises(IntegrityError):
            await test_db_session.execute(
                delete(USDTWallet).where(USDTWallet.id == wallet.id)
            )
            await test_db_session.commit()
        
        await test_db_session.rollback()
    
    @pytest.mark.asyncio
    async def test_transaction_atomicity(self, test_db_session: AsyncSession, clean_database):
        """测试事务原子性"""
        # 创建测试钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TAtomicityTest123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('1000'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # 开始事务：更新钱包状态 + 创建订单
        initial_balance = wallet.balance
        
        try:
            async with test_db_session.begin():
                # 1. 更新钱包状态
                await test_db_session.execute(
                    update(USDTWallet)
                    .where(USDTWallet.id == wallet.id)
                    .values(status="ALLOCATED", balance=Decimal('900'))
                )
                
                # 2. 创建订单
                order = USDTPaymentOrder(
                    order_no="ATOMIC_ORDER_001",
                    user_id=1,
                    wallet_id=wallet.id,
                    usdt_amount=Decimal('100'),
                    expected_amount=Decimal('100.05'),
                    network="TRC20",
                    to_address=wallet.address,
                    status="pending",
                    expires_at=datetime.utcnow() + timedelta(minutes=30)
                )
                test_db_session.add(order)
                
                # 3. 故意制造错误（违反唯一约束）
                duplicate_order = USDTPaymentOrder(
                    order_no="ATOMIC_ORDER_001",  # 重复订单号
                    user_id=2,
                    wallet_id=wallet.id,
                    usdt_amount=Decimal('50'),
                    expected_amount=Decimal('50.05'),
                    network="TRC20",
                    to_address=wallet.address,
                    status="pending",
                    expires_at=datetime.utcnow() + timedelta(minutes=30)
                )
                test_db_session.add(duplicate_order)
                
                # 这里应该失败，导致整个事务回滚
                
        except IntegrityError:
            # 预期的错误
            pass
        
        # 验证事务回滚：钱包状态应该保持不变
        await test_db_session.refresh(wallet)
        assert wallet.status == "AVAILABLE"
        assert wallet.balance == initial_balance
        
        # 验证订单没有被创建
        orders = await test_db_session.execute(
            select(USDTPaymentOrder).where(USDTPaymentOrder.order_no == "ATOMIC_ORDER_001")
        )
        assert orders.scalar_one_or_none() is None
    
    @pytest.mark.asyncio
    async def test_concurrent_write_safety(self, test_db_session: AsyncSession, clean_database):
        """测试并发写入安全性"""
        # 创建测试钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TConcurrentWrite123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('1000'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # 并发更新钱包余额
        async def update_wallet_balance(session: AsyncSession, wallet_id: int, amount: Decimal):
            try:
                # 模拟读-修改-写操作
                result = await session.execute(
                    select(USDTWallet).where(USDTWallet.id == wallet_id)
                )
                wallet_obj = result.scalar_one()
                
                # 模拟一些处理时间
                await asyncio.sleep(0.1)
                
                # 更新余额
                new_balance = wallet_obj.balance - amount
                await session.execute(
                    update(USDTWallet)
                    .where(USDTWallet.id == wallet_id)
                    .values(balance=new_balance)
                )
                await session.commit()
                return {"success": True, "new_balance": new_balance}
                
            except Exception as e:
                await session.rollback()
                return {"success": False, "error": str(e)}
        
        # 启动多个并发会话
        async def create_concurrent_session():
            async with AsyncSessionLocal() as session:
                return await update_wallet_balance(session, wallet.id, Decimal('100'))
        
        # 并发执行5个余额更新任务
        tasks = [create_concurrent_session() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # 验证结果
        successful_updates = sum(1 for r in results if r["success"])
        
        # 由于并发控制，不是所有更新都会成功
        # 但至少应该有一个成功
        assert successful_updates >= 1
        
        # 验证最终余额的一致性
        await test_db_session.refresh(wallet)
        expected_final_balance = Decimal('1000') - (Decimal('100') * successful_updates)
        assert wallet.balance == expected_final_balance
    
    @pytest.mark.asyncio
    async def test_deadlock_prevention(self, test_db_session: AsyncSession, clean_database):
        """测试死锁预防机制"""
        # 创建两个钱包
        wallet1 = USDTWallet(
            network="TRC20",
            address="TDeadlock1123456789012345678901234",
            private_key_encrypted="encrypted_key",
            balance=Decimal('500'),
            is_active=True
        )
        
        wallet2 = USDTWallet(
            network="TRC20", 
            address="TDeadlock2123456789012345678901234",
            private_key_encrypted="encrypted_key",
            balance=Decimal('500'),
            is_active=True
        )
        
        test_db_session.add_all([wallet1, wallet2])
        await test_db_session.commit()
        
        # 定义可能导致死锁的并发操作
        async def operation_a():
            async with AsyncSessionLocal() as session:
                try:
                    # 按ID顺序锁定资源（防死锁策略）
                    min_id = min(wallet1.id, wallet2.id)
                    max_id = max(wallet1.id, wallet2.id)
                    
                    # 先锁定ID较小的钱包
                    await session.execute(
                        select(USDTWallet).where(USDTWallet.id == min_id).with_for_update()
                    )
                    
                    await asyncio.sleep(0.1)  # 模拟处理时间
                    
                    # 再锁定ID较大的钱包
                    await session.execute(
                        select(USDTWallet).where(USDTWallet.id == max_id).with_for_update()
                    )
                    
                    # 执行转账操作
                    await session.execute(
                        update(USDTWallet)
                        .where(USDTWallet.id == wallet1.id)
                        .values(balance=USDTWallet.balance - Decimal('50'))
                    )
                    await session.execute(
                        update(USDTWallet)
                        .where(USDTWallet.id == wallet2.id)
                        .values(balance=USDTWallet.balance + Decimal('50'))
                    )
                    
                    await session.commit()
                    return {"success": True}
                    
                except Exception as e:
                    await session.rollback()
                    return {"success": False, "error": str(e)}
        
        async def operation_b():
            # 相同的锁定顺序，防止死锁
            return await operation_a()
        
        # 并发执行可能导致死锁的操作
        task1 = asyncio.create_task(operation_a())
        task2 = asyncio.create_task(operation_b())
        
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        
        # 验证没有发生死锁，操作成功完成
        successful_operations = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        assert successful_operations >= 1  # 至少一个操作成功
    
    @pytest.mark.asyncio
    async def test_connection_pool_management(self, clean_database):
        """测试连接池管理"""
        # 创建多个并发数据库连接
        async def database_operation(operation_id: int):
            async with AsyncSessionLocal() as session:
                try:
                    # 执行数据库操作
                    wallet = USDTWallet(
                        network="TRC20",
                        address=f"TConnPool{operation_id:030d}",
                        private_key_encrypted="encrypted_key",
                        balance=Decimal('100'),
                        is_active=True
                    )
                    session.add(wallet)
                    await session.commit()
                    
                    # 模拟一些查询操作
                    result = await session.execute(
                        select(USDTWallet).where(USDTWallet.address == wallet.address)
                    )
                    found_wallet = result.scalar_one()
                    
                    return {
                        "operation_id": operation_id,
                        "success": True,
                        "wallet_id": found_wallet.id
                    }
                    
                except Exception as e:
                    return {
                        "operation_id": operation_id,
                        "success": False,
                        "error": str(e)
                    }
        
        # 创建大量并发数据库操作（测试连接池限制）
        concurrent_operations = 20
        tasks = [database_operation(i) for i in range(concurrent_operations)]
        
        # 并发执行所有操作
        results = await asyncio.gather(*tasks)
        
        # 验证所有操作都成功完成
        successful_operations = [r for r in results if r["success"]]
        failed_operations = [r for r in results if not r["success"]]
        
        assert len(successful_operations) == concurrent_operations
        assert len(failed_operations) == 0
        
        # 验证所有钱包都被正确创建
        async with AsyncSessionLocal() as session:
            all_wallets = await session.execute(
                select(USDTWallet).where(USDTWallet.address.like("TConnPool%"))
            )
            wallet_count = len(all_wallets.scalars().all())
            assert wallet_count == concurrent_operations
    
    @pytest.mark.asyncio
    async def test_complex_query_performance(self, test_db_session: AsyncSession, clean_database):
        """测试复杂查询性能"""
        # 创建大量测试数据
        wallets = []
        orders = []
        
        for i in range(100):
            wallet = USDTWallet(
                network="TRC20" if i % 2 == 0 else "ERC20",
                address=f"TPerformance{i:030d}",
                private_key_encrypted="encrypted_key",
                balance=Decimal(str(100 + i)),
                is_active=True,
                status="AVAILABLE" if i % 3 == 0 else "ALLOCATED"
            )
            wallets.append(wallet)
            
            if i % 3 != 0:  # 为ALLOCATED的钱包创建订单
                order = USDTPaymentOrder(
                    order_no=f"PERF_ORDER_{i:05d}",
                    user_id=(i % 10) + 1,  # 10个不同用户
                    wallet_id=None,  # 将在flush后设置
                    usdt_amount=Decimal(str(10 + (i % 50))),
                    expected_amount=Decimal(str(10.05 + (i % 50))),
                    network=wallet.network,
                    to_address=wallet.address,
                    status="pending" if i % 4 != 0 else "confirmed",
                    expires_at=datetime.utcnow() + timedelta(minutes=30)
                )
                orders.append((order, i))
        
        # 批量插入钱包
        test_db_session.add_all(wallets)
        await test_db_session.flush()
        
        # 设置订单的wallet_id并插入
        for order, wallet_index in orders:
            order.wallet_id = wallets[wallet_index].id
            test_db_session.add(order)
        
        await test_db_session.commit()
        
        # 执行复杂查询并测量性能
        start_time = datetime.now()
        
        # 复杂查询：联合查询钱包和订单，按多个条件筛选和排序
        complex_query = await test_db_session.execute(
            select(USDTWallet, USDTPaymentOrder)
            .join(USDTPaymentOrder, USDTWallet.id == USDTPaymentOrder.wallet_id, isouter=True)
            .where(
                (USDTWallet.network == "TRC20") &
                (USDTWallet.balance > Decimal('120')) &
                ((USDTPaymentOrder.status == "pending") | (USDTPaymentOrder.status.is_(None)))
            )
            .order_by(USDTWallet.balance.desc(), USDTPaymentOrder.created_at.desc())
        )
        
        results = complex_query.fetchall()
        query_duration = (datetime.now() - start_time).total_seconds()
        
        # 验证查询结果正确性
        assert len(results) > 0
        
        # 验证性能（查询应该在合理时间内完成）
        assert query_duration < 1.0  # 1秒内完成
        
        print(f"复杂查询性能: {len(results)} 条结果，耗时 {query_duration:.3f} 秒")
    
    @pytest.mark.asyncio
    async def test_data_migration_simulation(self, test_db_session: AsyncSession, clean_database):
        """测试数据迁移模拟"""
        # 创建旧格式数据
        old_wallets = []
        for i in range(10):
            wallet = USDTWallet(
                network="TRC20",
                address=f"TOldFormat{i:030d}",
                private_key_encrypted="old_encrypted_key",
                balance=Decimal('100'),
                is_active=True,
                # 缺少新字段，模拟数据迁移场景
                success_rate=None,
                avg_response_time=None,
                total_transactions=None
            )
            old_wallets.append(wallet)
        
        test_db_session.add_all(old_wallets)
        await test_db_session.commit()
        
        # 模拟数据迁移：为旧数据填充新字段
        migration_start = datetime.now()
        
        await test_db_session.execute(
            update(USDTWallet)
            .where(USDTWallet.success_rate.is_(None))
            .values(
                success_rate=0.95,
                avg_response_time=2.0,
                total_transactions=0,
                successful_transactions=0
            )
        )
        await test_db_session.commit()
        
        migration_duration = (datetime.now() - migration_start).total_seconds()
        
        # 验证迁移结果
        migrated_wallets = await test_db_session.execute(
            select(USDTWallet).where(USDTWallet.address.like("TOldFormat%"))
        )
        
        for wallet in migrated_wallets.scalars():
            assert wallet.success_rate is not None
            assert wallet.avg_response_time is not None
            assert wallet.total_transactions is not None
        
        print(f"数据迁移性能: 10条记录，耗时 {migration_duration:.3f} 秒")