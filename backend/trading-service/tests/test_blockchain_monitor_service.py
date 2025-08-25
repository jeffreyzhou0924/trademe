"""
区块链监控服务单元测试
测试TRON和Ethereum网络集成、交易监控、支付匹配等功能
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.services.blockchain_monitor_service import blockchain_monitor_service
from app.models.payment import USDTWallet, USDTPaymentOrder


class TestBlockchainMonitorService:
    """区块链监控服务测试类"""
    
    @pytest.mark.asyncio
    async def test_tron_latest_block_fetch(self, mock_blockchain_responses):
        """测试TRON最新区块获取"""
        with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
            # 模拟TRON API响应
            mock_client = AsyncMock()
            mock_tron.return_value = mock_client
            mock_client.get_now_block.return_value = mock_blockchain_responses["tron_latest_block"]
            
            # 执行测试
            block_info = await blockchain_monitor_service.get_latest_block("TRC20")
            
            # 验证结果
            assert block_info is not None
            assert "number" in block_info
            assert "timestamp" in block_info
            assert block_info["number"] == 12345
            mock_client.get_now_block.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ethereum_latest_block_fetch(self, mock_blockchain_responses):
        """测试Ethereum最新区块获取"""
        with patch('app.services.blockchain_monitor_service.Web3') as mock_web3:
            # 模拟Web3响应
            mock_instance = MagicMock()
            mock_web3.return_value = mock_instance
            mock_instance.eth.get_block.return_value = mock_blockchain_responses["ethereum_latest_block"]
            
            # 执行测试
            block_info = await blockchain_monitor_service.get_latest_block("ERC20")
            
            # 验证结果
            assert block_info is not None
            assert "number" in block_info
            assert block_info["number"] == int("0x1234", 16)
    
    @pytest.mark.asyncio
    async def test_address_transaction_fetch(self, test_db_session: AsyncSession):
        """测试地址交易记录获取"""
        test_address = "TTestMonitorAddress123456789012345678"
        
        with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
            # 模拟交易数据
            mock_transactions = {
                "data": [
                    {
                        "txID": "tx123456",
                        "blockNumber": 12345,
                        "block_timestamp": 1640995200000,
                        "raw_data": {
                            "contract": [{
                                "parameter": {
                                    "value": {
                                        "amount": 10000000,  # 10 USDT (6 decimals)
                                        "to_address": "41" + test_address[1:],  # TRON format
                                        "from_address": "41234567890abcdef"
                                    }
                                },
                                "type_url": "type.googleapis.com/protocol.TriggerSmartContract"
                            }]
                        },
                        "ret": [{"contractRet": "SUCCESS"}]
                    }
                ]
            }
            
            mock_client = AsyncMock()
            mock_tron.return_value = mock_client
            mock_client.get_account_transactions.return_value = mock_transactions
            
            # 执行测试
            transactions = await blockchain_monitor_service.get_address_transactions(
                address=test_address,
                network="TRC20",
                limit=10
            )
            
            # 验证结果
            assert len(transactions) == 1
            tx = transactions[0]
            assert tx["hash"] == "tx123456"
            assert tx["amount"] == Decimal('10.0')  # 转换为USDT单位
            assert tx["status"] == "SUCCESS"
            assert tx["confirmations"] >= 0
    
    @pytest.mark.asyncio
    async def test_usdt_balance_query_trc20(self, mock_blockchain_responses):
        """测试TRC20 USDT余额查询"""
        test_address = "TTestBalanceQuery123456789012345678"
        
        with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
            # 模拟USDT余额响应 (6 decimals)
            mock_client = AsyncMock()
            mock_tron.return_value = mock_client
            mock_client.trigger_smart_contract.return_value = {
                "constant_result": ["00000000000000000000000000000000000000000000000000000000009896800"]  # 10 USDT
            }
            
            # 执行测试
            balance = await blockchain_monitor_service.get_address_balance(
                address=test_address,
                network="TRC20"
            )
            
            # 验证结果
            assert balance == Decimal('100.0')  # hex转decimal再除以10^6
    
    @pytest.mark.asyncio
    async def test_usdt_balance_query_erc20(self, mock_blockchain_responses):
        """测试ERC20 USDT余额查询"""
        test_address = "0x1234567890123456789012345678901234567890"
        
        with patch('app.services.blockchain_monitor_service.Web3') as mock_web3:
            # 模拟Web3和合约调用
            mock_instance = MagicMock()
            mock_contract = MagicMock()
            mock_web3.return_value = mock_instance
            mock_instance.eth.contract.return_value = mock_contract
            mock_contract.functions.balanceOf.return_value.call.return_value = 250250000  # 250.25 USDT
            
            # 执行测试
            balance = await blockchain_monitor_service.get_address_balance(
                address=test_address,
                network="ERC20"
            )
            
            # 验证结果
            assert balance == Decimal('250.25')
    
    @pytest.mark.asyncio
    async def test_transaction_status_check(self, mock_blockchain_responses):
        """测试交易状态检查"""
        tx_hash = "test_transaction_hash_123456789abcdef"
        
        with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
            # 模拟交易状态响应
            mock_client = AsyncMock()
            mock_tron.return_value = mock_client
            mock_client.get_transaction_info.return_value = {
                "id": tx_hash,
                "blockNumber": 12345,
                "blockTimeStamp": 1640995200000,
                "contractResult": ["SUCCESS"],
                "receipt": {
                    "result": "SUCCESS"
                }
            }
            
            # 模拟当前区块高度
            mock_client.get_now_block.return_value = {
                "block_header": {
                    "raw_data": {"number": 12357}  # 12个确认
                }
            }
            
            # 执行测试
            status = await blockchain_monitor_service.get_transaction_status(
                tx_hash=tx_hash,
                network="TRC20"
            )
            
            # 验证结果
            assert status["success"] == True
            assert status["confirmations"] == 12
            assert status["block_height"] == 12345
    
    @pytest.mark.asyncio
    async def test_monitoring_task_management(self, test_db_session: AsyncSession):
        """测试监控任务管理"""
        # 创建测试钱包
        wallet = USDTWallet(
            network="TRC20",
            address="TMonitorTaskTest123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('0'),
            is_active=True,
            status="AVAILABLE"
        )
        test_db_session.add(wallet)
        await test_db_session.commit()
        
        # 添加监控任务
        success = await blockchain_monitor_service.add_wallet_monitoring(
            wallet_id=wallet.id,
            address=wallet.address,
            network=wallet.network,
            session=test_db_session
        )
        
        assert success == True
        
        # 验证监控任务已创建
        monitoring_tasks = await blockchain_monitor_service.get_active_monitoring_tasks(
            session=test_db_session
        )
        
        task_addresses = [task["address"] for task in monitoring_tasks]
        assert wallet.address in task_addresses
        
        # 移除监控任务
        remove_success = await blockchain_monitor_service.remove_wallet_monitoring(
            wallet_id=wallet.id,
            session=test_db_session
        )
        
        assert remove_success == True
    
    @pytest.mark.asyncio
    async def test_payment_matching_logic(self, test_db_session: AsyncSession):
        """测试支付匹配逻辑"""
        # 创建测试订单
        order = USDTPaymentOrder(
            order_no="TEST_PAYMENT_MATCH_001",
            user_id=1,
            wallet_id=1,
            usdt_amount=Decimal('10.0'),
            expected_amount=Decimal('10.05'),  # 带随机后缀
            network="TRC20",
            to_address="TPaymentMatchTest123456789012345678",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        test_db_session.add(order)
        await test_db_session.commit()
        
        # 模拟接收到区块链交易
        incoming_transaction = {
            "hash": "tx_payment_match_123",
            "to_address": order.to_address,
            "amount": Decimal('10.05'),
            "confirmations": 1,
            "block_height": 12345,
            "timestamp": datetime.utcnow()
        }
        
        # 执行支付匹配
        match_result = await blockchain_monitor_service.match_payment_transaction(
            transaction=incoming_transaction,
            session=test_db_session
        )
        
        # 验证匹配结果
        assert match_result is not None
        assert match_result["order_no"] == order.order_no
        assert match_result["matched"] == True
        assert match_result["amount_difference"] <= 0.01  # 允许小额差异
    
    @pytest.mark.asyncio
    async def test_confirmation_counting_accuracy(self, mock_blockchain_responses):
        """测试确认数计算准确性"""
        tx_block_height = 12340
        current_block_height = 12352  # 应该有12个确认
        
        with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
            mock_client = AsyncMock()
            mock_tron.return_value = mock_client
            
            # 模拟交易信息（在指定区块）
            mock_client.get_transaction_info.return_value = {
                "blockNumber": tx_block_height
            }
            
            # 模拟当前最新区块
            mock_client.get_now_block.return_value = {
                "block_header": {
                    "raw_data": {"number": current_block_height}
                }
            }
            
            # 执行确认数计算
            confirmations = await blockchain_monitor_service.get_transaction_confirmations(
                tx_hash="test_tx_hash",
                network="TRC20"
            )
            
            # 验证确认数计算
            expected_confirmations = current_block_height - tx_block_height
            assert confirmations == expected_confirmations
    
    @pytest.mark.asyncio
    async def test_network_switching_functionality(self, mock_blockchain_responses):
        """测试网络切换功能"""
        networks = ["TRC20", "ERC20", "BEP20"]
        
        for network in networks:
            # 测试每个网络的API调用
            if network == "TRC20":
                with patch('app.services.blockchain_monitor_service.TronClient'):
                    result = await blockchain_monitor_service.get_network_status(network)
                    assert result["network"] == network
                    assert "latest_block" in result
                    
            elif network == "ERC20":
                with patch('app.services.blockchain_monitor_service.Web3'):
                    result = await blockchain_monitor_service.get_network_status(network)
                    assert result["network"] == network
                    assert "latest_block" in result
                    
            elif network == "BEP20":
                with patch('app.services.blockchain_monitor_service.Web3'):
                    result = await blockchain_monitor_service.get_network_status(network)
                    assert result["network"] == network
                    assert "latest_block" in result
    
    @pytest.mark.asyncio
    async def test_error_handling_and_retry_logic(self):
        """测试错误处理和重试逻辑"""
        with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
            # 模拟网络错误
            mock_client = AsyncMock()
            mock_tron.return_value = mock_client
            mock_client.get_now_block.side_effect = [
                Exception("Network error"),  # 第1次失败
                Exception("Timeout"),        # 第2次失败
                {"block_header": {"raw_data": {"number": 12345}}}  # 第3次成功
            ]
            
            # 执行带重试的操作
            with patch('app.services.blockchain_monitor_service.MAX_RETRIES', 3):
                result = await blockchain_monitor_service.get_latest_block_with_retry("TRC20")
                
                # 验证最终成功
                assert result is not None
                assert result["number"] == 12345
                
                # 验证重试了3次
                assert mock_client.get_now_block.call_count == 3
    
    @pytest.mark.asyncio
    async def test_real_time_monitoring_simulation(self, test_db_session: AsyncSession):
        """测试实时监控模拟"""
        # 创建监控地址
        monitored_address = "TRealTimeMonitor123456789012345678"
        
        # 启动监控任务
        with patch('app.services.blockchain_monitor_service.schedule_monitoring_task') as mock_schedule:
            await blockchain_monitor_service.start_real_time_monitoring(
                address=monitored_address,
                network="TRC20",
                callback=lambda tx: print(f"New transaction: {tx}"),
                session=test_db_session
            )
            
            # 验证监控任务已调度
            mock_schedule.assert_called_once()
            
            # 模拟监控检查周期
            with patch('app.services.blockchain_monitor_service.TronClient') as mock_tron:
                mock_client = AsyncMock()
                mock_tron.return_value = mock_client
                
                # 模拟发现新交易
                mock_client.get_account_transactions.return_value = {
                    "data": [{
                        "txID": "new_tx_12345",
                        "blockNumber": 12350,
                        "raw_data": {
                            "contract": [{
                                "parameter": {
                                    "value": {
                                        "amount": 5000000,  # 5 USDT
                                        "to_address": "41" + monitored_address[1:]
                                    }
                                }
                            }]
                        },
                        "ret": [{"contractRet": "SUCCESS"}]
                    }]
                }
                
                # 执行监控检查
                new_transactions = await blockchain_monitor_service.check_address_for_new_transactions(
                    address=monitored_address,
                    network="TRC20",
                    last_checked_block=12340
                )
                
                # 验证发现了新交易
                assert len(new_transactions) == 1
                assert new_transactions[0]["amount"] == Decimal('5.0')
                assert new_transactions[0]["to_address"] == monitored_address