#!/usr/bin/env python3
"""
测试钱包生成和管理功能
"""

import asyncio
import sys
import os
from decimal import Decimal

# 添加应用路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.wallet_pool_service import WalletPoolService
from app.models.payment import USDTWallet
from sqlalchemy import select


async def test_wallet_generation():
    """测试钱包生成功能"""
    
    print("🚀 开始测试USDT钱包池管理功能...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 创建钱包池服务
            wallet_service = WalletPoolService(db)
            
            print("\n📊 当前钱包池状态:")
            stats = await wallet_service.get_pool_statistics()
            print(f"  总钱包数: {stats['total_wallets']}")
            print(f"  网络分布: {stats['network_distribution']}")
            print(f"  状态分布: {stats['status_distribution']}")
            
            # 生成测试钱包
            print("\n🔧 生成测试钱包...")
            
            # 生成5个TRC20钱包
            trc20_wallets = await wallet_service.generate_wallets(
                network="TRC20",
                count=5,
                name_prefix="test_trc20",
                admin_id=1  # 假设管理员ID为1
            )
            print(f"✅ 成功生成 {len(trc20_wallets)} 个TRC20钱包")
            
            # 生成3个ERC20钱包
            erc20_wallets = await wallet_service.generate_wallets(
                network="ERC20", 
                count=3,
                name_prefix="test_erc20",
                admin_id=1
            )
            print(f"✅ 成功生成 {len(erc20_wallets)} 个ERC20钱包")
            
            # 生成2个BEP20钱包
            bep20_wallets = await wallet_service.generate_wallets(
                network="BEP20",
                count=2, 
                name_prefix="test_bep20",
                admin_id=1
            )
            print(f"✅ 成功生成 {len(bep20_wallets)} 个BEP20钱包")
            
            print(f"\n📈 总计生成 {len(trc20_wallets) + len(erc20_wallets) + len(bep20_wallets)} 个钱包")
            
            # 显示生成的钱包
            print("\n💰 生成的钱包详情:")
            all_wallets = trc20_wallets + erc20_wallets + bep20_wallets
            for i, wallet in enumerate(all_wallets, 1):
                print(f"  {i}. {wallet.name} ({wallet.network})")
                print(f"     地址: {wallet.address}")
                print(f"     状态: {wallet.status}")
                print(f"     余额: {wallet.balance} USDT")
            
            # 测试钱包分配功能
            print("\n🎯 测试钱包分配功能...")
            
            # 模拟分配TRC20钱包给订单
            test_order_id = "TEST_ORDER_001"
            allocated_wallet = await wallet_service.allocate_wallet(test_order_id, "TRC20")
            
            if allocated_wallet:
                print(f"✅ 成功为订单 {test_order_id} 分配钱包:")
                print(f"   钱包名称: {allocated_wallet.name}")
                print(f"   地址: {allocated_wallet.address}")
                print(f"   网络: {allocated_wallet.network}")
                print(f"   状态: {allocated_wallet.status}")
                
                # 测试释放钱包
                print(f"\n🔄 释放钱包 {allocated_wallet.id}...")
                release_success = await wallet_service.release_wallet(allocated_wallet.id, admin_id=1)
                if release_success:
                    print("✅ 钱包释放成功")
                else:
                    print("❌ 钱包释放失败")
            else:
                print("❌ 钱包分配失败 - 没有可用钱包")
            
            # 测试状态更新
            print("\n🔧 测试钱包状态更新...")
            if all_wallets:
                test_wallet_id = all_wallets[0].id
                update_success = await wallet_service.update_wallet_status(
                    test_wallet_id, "maintenance", admin_id=1
                )
                if update_success:
                    print(f"✅ 钱包 {test_wallet_id} 状态更新为 'maintenance'")
                    
                    # 恢复状态
                    await wallet_service.update_wallet_status(
                        test_wallet_id, "available", admin_id=1
                    )
                    print(f"✅ 钱包 {test_wallet_id} 状态恢复为 'available'")
                else:
                    print("❌ 钱包状态更新失败")
            
            # 最终统计
            print("\n📊 最终钱包池统计:")
            final_stats = await wallet_service.get_pool_statistics()
            print(f"  总钱包数: {final_stats['total_wallets']}")
            print(f"  网络分布: {final_stats['network_distribution']}")
            print(f"  状态分布: {final_stats['status_distribution']}")
            print(f"  总余额: {final_stats['total_balance']:.8f} USDT")
            print(f"  利用率: {final_stats['utilization_rate']:.2f}%")
            
            # 验证数据库中的数据
            print("\n🗄️  数据库验证:")
            wallet_query = select(USDTWallet)
            result = await db.execute(wallet_query)
            wallets_in_db = result.scalars().all()
            
            print(f"  数据库中的钱包总数: {len(wallets_in_db)}")
            for wallet in wallets_in_db:
                print(f"    {wallet.wallet_name} ({wallet.network}): {wallet.address} - {wallet.status}")
            
            print("\n🎉 所有测试完成！钱包池管理功能正常工作。")
            
        except Exception as e:
            print(f"❌ 测试过程中发生错误: {e}")
            import traceback
            traceback.print_exc()


async def cleanup_test_data():
    """清理测试数据"""
    print("\n🧹 清理测试数据...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 删除所有测试钱包
            from sqlalchemy import delete
            
            delete_stmt = delete(USDTWallet).where(
                USDTWallet.wallet_name.like('test_%')
            )
            
            result = await db.execute(delete_stmt)
            await db.commit()
            
            print(f"✅ 清理完成，删除了 {result.rowcount} 个测试钱包")
            
        except Exception as e:
            print(f"❌ 清理数据时发生错误: {e}")


async def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        await cleanup_test_data()
    else:
        await test_wallet_generation()


if __name__ == "__main__":
    asyncio.run(main())