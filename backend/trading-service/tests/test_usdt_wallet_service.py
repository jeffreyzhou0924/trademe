"""
USDT钱包服务单元测试
测试智能钱包分配逻辑、风险评级、加密存储等核心功能
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.usdt_wallet_service import usdt_wallet_service
from app.models.payment import USDTWallet
from app.services.wallet_encryption import encrypt_private_key, decrypt_private_key


class TestUSDTWalletService:
    """USDT钱包服务测试类"""
    
    @pytest.mark.asyncio
    async def test_wallet_creation(self, test_db_session: AsyncSession, test_config, sample_wallet_data):
        """测试钱包创建功能"""
        # 准备测试数据
        network = sample_wallet_data["network"]
        address = sample_wallet_data["address"]
        private_key = "test_private_key_for_encryption"
        
        # 模拟钱包生成
        with patch('app.services.usdt_wallet_service.generate_wallet_keypair') as mock_generate:
            mock_generate.return_value = (address, private_key)
            
            # 执行钱包创建
            wallet = await usdt_wallet_service.create_wallet(
                network=network,
                session=test_db_session
            )
            
            # 验证结果
            assert wallet is not None
            assert wallet.network == network
            assert wallet.address == address
            assert wallet.private_key_encrypted is not None
            assert wallet.is_active == True
            assert wallet.balance == Decimal('0')
            
            # 验证私钥加密
            decrypted_key = decrypt_private_key(wallet.private_key_encrypted)
            assert decrypted_key == private_key
    
    @pytest.mark.asyncio
    async def test_wallet_allocation_algorithm(self, test_db_session: AsyncSession, sample_wallet_data):
        """测试智能钱包分配算法"""
        # 创建多个测试钱包，不同风险等级和性能指标
        wallets = []
        for i in range(3):
            wallet_data = sample_wallet_data.copy()
            wallet_data.update({
                "address": f"TTestAddress{i:030d}",
                "balance": Decimal(str(100 + i * 50)),  # 100, 150, 200
                "success_rate": 0.95 + i * 0.01,  # 0.95, 0.96, 0.97
                "avg_response_time": 2.0 - i * 0.2,  # 2.0, 1.8, 1.6
                "total_transactions": 100 + i * 50,
                "risk_level": ["LOW", "MEDIUM", "LOW"][i]
            })
            
            wallet = USDTWallet(**wallet_data)
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # 测试分配算法
        order_no = "TEST_ORDER_001"
        amount = Decimal('10.0')
        user_risk_level = "LOW"
        
        allocated_wallet = await usdt_wallet_service.allocate_wallet_for_payment(
            order_no=order_no,
            network="TRC20",
            amount=amount,
            user_risk_level=user_risk_level,
            session=test_db_session
        )
        
        # 验证分配结果 - 应该选择最优钱包（高成功率、低响应时间、匹配风险等级）
        assert allocated_wallet is not None
        assert allocated_wallet.network == "TRC20"
        assert allocated_wallet.current_order_id == order_no
        assert allocated_wallet.balance >= amount
        
        # 验证智能评分逻辑 - 风险匹配、性能优先
        assert allocated_wallet.risk_level == "LOW"  # 风险等级匹配
        assert allocated_wallet.success_rate >= 0.95  # 高成功率
    
    @pytest.mark.asyncio 
    async def test_wallet_scoring_algorithm(self, test_db_session: AsyncSession):
        """测试钱包评分算法准确性"""
        # 创建具有不同特征的钱包
        test_cases = [
            {  # 高分钱包：高成功率、低延迟、充足余额
                "success_rate": 0.99,
                "avg_response_time": 0.5,
                "balance": Decimal('1000'),
                "total_transactions": 1000,
                "expected_score_range": (0.8, 1.0)
            },
            {  # 中等钱包：中等指标
                "success_rate": 0.90,
                "avg_response_time": 2.0, 
                "balance": Decimal('100'),
                "total_transactions": 100,
                "expected_score_range": (0.4, 0.8)
            },
            {  # 低分钱包：低成功率、高延迟
                "success_rate": 0.70,
                "avg_response_time": 5.0,
                "balance": Decimal('10'),
                "total_transactions": 10,
                "expected_score_range": (0.0, 0.4)
            }
        ]
        
        for case in test_cases:
            wallet = USDTWallet(
                network="TRC20",
                address=f"TTestScoring{case['total_transactions']:030d}",
                private_key_encrypted="encrypted_key",
                balance=case["balance"],
                success_rate=case["success_rate"],
                avg_response_time=case["avg_response_time"],
                total_transactions=case["total_transactions"],
                risk_level="LOW",
                is_active=True
            )
            
            # 计算评分
            score = usdt_wallet_service._calculate_wallet_score(
                wallet=wallet,
                required_amount=Decimal('10'),
                user_risk_level="LOW"
            )
            
            # 验证评分在预期范围内
            min_score, max_score = case["expected_score_range"] 
            assert min_score <= score <= max_score, f"Score {score} not in range {case['expected_score_range']}"
    
    @pytest.mark.asyncio
    async def test_wallet_release_mechanism(self, test_db_session: AsyncSession, sample_wallet_data):
        """测试钱包释放机制"""
        # 创建已分配的钱包
        wallet = USDTWallet(**sample_wallet_data)
        wallet.current_order_id = "TEST_ORDER_123"
        wallet.status = "ALLOCATED"
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # 执行钱包释放
        success = await usdt_wallet_service.release_wallet(
            order_no="TEST_ORDER_123",
            session=test_db_session
        )
        
        # 验证释放结果
        assert success == True
        
        # 刷新钱包状态
        await test_db_session.refresh(wallet)
        assert wallet.current_order_id is None
        assert wallet.status == "AVAILABLE"
    
    @pytest.mark.asyncio
    async def test_encrypted_private_key_storage(self, test_config):
        """测试私钥加密存储"""
        original_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        
        # 测试加密
        encrypted_key = encrypt_private_key(original_private_key)
        assert encrypted_key != original_private_key
        assert len(encrypted_key) > len(original_private_key)
        
        # 测试解密
        decrypted_key = decrypt_private_key(encrypted_key)
        assert decrypted_key == original_private_key
        
        # 测试加密的唯一性（相同输入产生不同密文）
        encrypted_key2 = encrypt_private_key(original_private_key)
        assert encrypted_key != encrypted_key2
        
        # 但解密结果应该相同
        decrypted_key2 = decrypt_private_key(encrypted_key2)
        assert decrypted_key2 == original_private_key
    
    @pytest.mark.asyncio
    async def test_wallet_pool_health_monitoring(self, test_db_session: AsyncSession):
        """测试钱包池健康状态监控"""
        # 创建各种状态的钱包
        wallets_data = [
            {"address": "THealthy001", "is_active": True, "success_rate": 0.95, "status": "AVAILABLE"},
            {"address": "THealthy002", "is_active": True, "success_rate": 0.90, "status": "ALLOCATED"},
            {"address": "TUnhealthy001", "is_active": False, "success_rate": 0.70, "status": "ERROR"},
            {"address": "TUnhealthy002", "is_active": True, "success_rate": 0.50, "status": "MAINTENANCE"}
        ]
        
        for data in wallets_data:
            wallet = USDTWallet(
                network="TRC20",
                private_key_encrypted="encrypted_key",
                balance=Decimal('100'),
                risk_level="LOW",
                **data
            )
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # 获取健康状态统计
        health_stats = await usdt_wallet_service.get_wallet_pool_health(
            network="TRC20",
            session=test_db_session
        )
        
        # 验证统计结果
        assert health_stats["total_wallets"] == 4
        assert health_stats["active_wallets"] == 3  # is_active=True的钱包
        assert health_stats["available_wallets"] == 1  # AVAILABLE状态
        assert health_stats["allocated_wallets"] == 1  # ALLOCATED状态
        assert health_stats["error_wallets"] == 1  # ERROR状态
        assert health_stats["avg_success_rate"] > 0.75  # 平均成功率
        assert 0 <= health_stats["health_score"] <= 1.0  # 健康评分
    
    @pytest.mark.asyncio
    async def test_risk_level_filtering(self, test_db_session: AsyncSession):
        """测试风险等级筛选功能"""
        # 创建不同风险等级的钱包
        risk_levels = ["LOW", "MEDIUM", "HIGH"]
        for i, risk in enumerate(risk_levels):
            wallet = USDTWallet(
                network="TRC20",
                address=f"TRisk{risk}{i:030d}",
                private_key_encrypted="encrypted_key",
                balance=Decimal('100'),
                risk_level=risk,
                is_active=True,
                status="AVAILABLE",
                success_rate=0.95
            )
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # 测试不同风险等级的筛选
        for user_risk in risk_levels:
            allocated_wallet = await usdt_wallet_service.allocate_wallet_for_payment(
                order_no=f"TEST_RISK_{user_risk}",
                network="TRC20",
                amount=Decimal('10'),
                user_risk_level=user_risk,
                session=test_db_session
            )
            
            # 验证分配的钱包风险等级匹配或更低
            if allocated_wallet:
                wallet_risk_level = allocated_wallet.risk_level
                risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
                assert risk_order[wallet_risk_level] <= risk_order[user_risk]
    
    @pytest.mark.asyncio
    async def test_concurrent_wallet_allocation(self, test_db_session: AsyncSession):
        """测试并发钱包分配处理"""
        # 创建有限数量的钱包
        for i in range(3):
            wallet = USDTWallet(
                network="TRC20",
                address=f"TConcurrent{i:030d}",
                private_key_encrypted="encrypted_key",
                balance=Decimal('100'),
                risk_level="LOW",
                is_active=True,
                status="AVAILABLE",
                success_rate=0.95
            )
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # 模拟并发分配请求
        import asyncio
        
        async def allocate_wallet(order_suffix):
            return await usdt_wallet_service.allocate_wallet_for_payment(
                order_no=f"CONCURRENT_ORDER_{order_suffix}",
                network="TRC20", 
                amount=Decimal('10'),
                user_risk_level="LOW",
                session=test_db_session
            )
        
        # 并发执行多个分配请求
        tasks = [allocate_wallet(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证并发处理结果
        successful_allocations = [r for r in results if not isinstance(r, Exception) and r is not None]
        assert len(successful_allocations) <= 3  # 不能超过可用钱包数量
        
        # 验证没有重复分配同一个钱包
        allocated_addresses = [wallet.address for wallet in successful_allocations]
        assert len(allocated_addresses) == len(set(allocated_addresses))  # 无重复
    
    @pytest.mark.asyncio
    async def test_wallet_performance_metrics_update(self, test_db_session: AsyncSession, sample_wallet_data):
        """测试钱包性能指标更新"""
        # 创建钱包
        wallet = USDTWallet(**sample_wallet_data)
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # 模拟交易完成，更新性能指标
        await usdt_wallet_service.update_wallet_performance(
            wallet_id=wallet.id,
            transaction_success=True,
            response_time=1.2,
            session=test_db_session
        )
        
        # 验证性能指标更新
        await test_db_session.refresh(wallet)
        assert wallet.total_transactions > sample_wallet_data.get("total_transactions", 0)
        assert wallet.successful_transactions > 0
        
        # 测试失败交易的处理
        await usdt_wallet_service.update_wallet_performance(
            wallet_id=wallet.id,
            transaction_success=False,
            response_time=5.0,
            session=test_db_session
        )
        
        await test_db_session.refresh(wallet)
        # 成功率应该有所下降
        updated_success_rate = wallet.successful_transactions / wallet.total_transactions
        assert updated_success_rate < 1.0