#!/usr/bin/env python3
"""
区块链转账服务测试脚本
测试TRC20和ERC20 USDT转账功能
"""

import asyncio
import sys
import os
from decimal import Decimal

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.blockchain_transfer_service import blockchain_transfer_service
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_balance_query():
    """测试余额查询功能"""
    print("\n=== 测试余额查询功能 ===")
    
    # 测试地址（可以使用实际的测试网地址）
    test_addresses = {
        'TRC20': 'TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE',  # 示例TRON地址
        'ERC20': '0x742d35cc6c6c60a7a2eae8cb3b7e2b30f9e01f78'   # 示例以太坊地址
    }
    
    for network, address in test_addresses.items():
        try:
            balance = await blockchain_transfer_service.get_balance(network, address)
            print(f"{network} 地址 {address} 余额: {balance} USDT")
        except Exception as e:
            print(f"查询 {network} 余额失败: {e}")


async def test_transaction_verification():
    """测试交易验证功能"""
    print("\n=== 测试交易验证功能 ===")
    
    # 测试交易哈希（需要使用实际的交易哈希）
    test_transactions = {
        # 'TRC20': 'some_real_tron_tx_hash',
        # 'ERC20': 'some_real_ethereum_tx_hash'
    }
    
    for network, tx_hash in test_transactions.items():
        try:
            result = await blockchain_transfer_service.verify_transaction(network, tx_hash)
            print(f"{network} 交易 {tx_hash} 验证结果: {result}")
        except Exception as e:
            print(f"验证 {network} 交易失败: {e}")


async def test_service_initialization():
    """测试服务初始化"""
    print("\n=== 测试服务初始化 ===")
    
    try:
        # 测试TRON客户端
        print(f"TRON网络: {blockchain_transfer_service.tron_network}")
        print(f"TRON USDT合约: {blockchain_transfer_service.tron_usdt_contract}")
        
        # 测试Ethereum连接
        if blockchain_transfer_service.web3.is_connected():
            print("✅ Ethereum网络连接正常")
            chain_id = await blockchain_transfer_service._get_chain_id()
            print(f"以太坊链ID: {chain_id}")
        else:
            print("❌ Ethereum网络连接失败")
            
        print(f"Ethereum USDT合约: {blockchain_transfer_service.ethereum_usdt_contract}")
        
    except Exception as e:
        print(f"服务初始化测试失败: {e}")


async def demonstrate_transfer_preparation():
    """演示转账准备过程（不执行实际转账）"""
    print("\n=== 演示转账准备过程 ===")
    
    # 示例转账参数
    demo_params = {
        'network': 'TRC20',
        'from_address': 'TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE',
        'to_address': 'TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9',
        'amount': Decimal('1.0'),
        'private_key': '0x' + '0' * 64  # 示例私钥，不要用于实际转账
    }
    
    print(f"转账网络: {demo_params['network']}")
    print(f"发送地址: {demo_params['from_address']}")
    print(f"接收地址: {demo_params['to_address']}")
    print(f"转账金额: {demo_params['amount']} USDT")
    
    # 检查余额（如果网络可用）
    try:
        balance = await blockchain_transfer_service.get_balance(
            demo_params['network'], 
            demo_params['from_address']
        )
        print(f"发送地址余额: {balance} USDT")
        
        if balance >= demo_params['amount']:
            print("✅ 余额充足，可以执行转账")
        else:
            print("❌ 余额不足，无法执行转账")
            
    except Exception as e:
        print(f"余额检查失败: {e}")
    
    print("\n注意: 这只是演示，没有执行实际的转账操作")
    print("实际转账需要有效的私钥和充足的余额")


async def main():
    """主测试函数"""
    print("🚀 开始区块链转账服务测试")
    
    try:
        await test_service_initialization()
        await test_balance_query()
        await test_transaction_verification()
        await demonstrate_transfer_preparation()
        
        print("\n✅ 区块链转账服务测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
    
    finally:
        # 关闭HTTP会话
        if hasattr(blockchain_transfer_service, '_http_session') and blockchain_transfer_service._http_session:
            await blockchain_transfer_service._http_session.close()


if __name__ == "__main__":
    asyncio.run(main())