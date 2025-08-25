#!/usr/bin/env python3
"""
测试智能钱包分配算法功能
"""

import asyncio
import sys
import os
from decimal import Decimal
from datetime import datetime, timedelta

# 添加应用路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.smart_wallet_allocator import (
    SmartWalletAllocator, 
    AllocationRequest, 
    AllocationStrategy
)
from app.services.wallet_pool_service import WalletPoolService
from app.models.payment import USDTWallet


async def setup_test_wallets():
    """设置测试钱包数据"""
    
    async with AsyncSessionLocal() as db:
        try:
            wallet_service = WalletPoolService(db)
            
            print("🔧 创建测试钱包...")
            
            # 创建不同风险等级的测试钱包
            test_wallets_config = [
                # 低风险TRC20钱包
                {"network": "TRC20", "count": 3, "prefix": "low_risk_trc20", "risk": "LOW"},
                # 中风险ERC20钱包
                {"network": "ERC20", "count": 2, "prefix": "med_risk_erc20", "risk": "MEDIUM"}, 
                # 高风险BEP20钱包
                {"network": "BEP20", "count": 2, "prefix": "high_risk_bep20", "risk": "HIGH"},
            ]
            
            total_created = 0
            
            for config in test_wallets_config:
                wallets = await wallet_service.generate_wallets(
                    network=config["network"],
                    count=config["count"], 
                    name_prefix=config["prefix"],
                    admin_id=1
                )
                
                # 更新风险等级
                for wallet in wallets:
                    from sqlalchemy import update
                    await db.execute(
                        update(USDTWallet)
                        .where(USDTWallet.id == wallet.id)
                        .values(risk_level=config["risk"])
                    )
                
                total_created += len(wallets)
                print(f"✅ 创建了 {len(wallets)} 个 {config['network']} {config['risk']} 风险钱包")
            
            await db.commit()
            
            print(f"📈 总共创建了 {total_created} 个测试钱包")
            return total_created
            
        except Exception as e:
            print(f"❌ 创建测试钱包失败: {e}")
            await db.rollback()
            return 0


async def test_allocation_strategies():
    """测试不同分配策略"""
    
    async with AsyncSessionLocal() as db:
        try:
            allocator = SmartWalletAllocator(db)
            
            print("\n🎯 测试智能分配策略...")
            
            # 测试不同的分配策略
            test_strategies = [
                (AllocationStrategy.BALANCED, "均衡分配"),
                (AllocationStrategy.RISK_MINIMIZED, "风险最小化"),
                (AllocationStrategy.PERFORMANCE_OPTIMIZED, "性能优化"),
                (AllocationStrategy.COST_OPTIMIZED, "成本优化"),
                (AllocationStrategy.HIGH_AVAILABILITY, "高可用性")
            ]
            
            for strategy, description in test_strategies:
                print(f"\n--- 测试策略: {description} ---")
                
                # 创建分配请求
                request = AllocationRequest(
                    order_id=f"TEST_ORDER_{strategy.value}_{int(datetime.now().timestamp())}",
                    network="TRC20",
                    amount=Decimal("100.0"),
                    priority=7,
                    risk_tolerance="MEDIUM",
                    strategy=strategy
                )
                
                # 执行分配
                allocated_wallet = await allocator.allocate_optimal_wallet(request)
                
                if allocated_wallet:
                    print(f"✅ 分配成功:")
                    print(f"   钱包ID: {allocated_wallet.id}")
                    print(f"   地址: {allocated_wallet.address}")
                    print(f"   网络: {allocated_wallet.network}")
                    print(f"   状态: {allocated_wallet.status}")
                    
                    # 释放钱包以便下次测试
                    wallet_service = WalletPoolService(db)
                    await wallet_service.release_wallet(allocated_wallet.id, admin_id=1)
                    print(f"   已释放钱包供下次测试")
                else:
                    print(f"❌ 分配失败: 没有找到合适的钱包")
            
            print("\n🎉 分配策略测试完成!")
            
        except Exception as e:
            print(f"❌ 分配策略测试失败: {e}")
            import traceback
            traceback.print_exc()


async def test_risk_tolerance():
    """测试风险容忍度"""
    
    async with AsyncSessionLocal() as db:
        try:
            allocator = SmartWalletAllocator(db)
            
            print("\n🔒 测试风险容忍度...")
            
            risk_levels = ["LOW", "MEDIUM", "HIGH"]
            
            for risk_level in risk_levels:
                print(f"\n--- 测试风险等级: {risk_level} ---")
                
                request = AllocationRequest(
                    order_id=f"RISK_TEST_{risk_level}_{int(datetime.now().timestamp())}",
                    network="TRC20",
                    amount=Decimal("50.0"),
                    risk_tolerance=risk_level,
                    strategy=AllocationStrategy.RISK_MINIMIZED
                )
                
                allocated_wallet = await allocator.allocate_optimal_wallet(request)
                
                if allocated_wallet:
                    # 查询分配的钱包风险等级
                    from sqlalchemy import select
                    wallet_query = select(USDTWallet).where(USDTWallet.id == allocated_wallet.id)
                    result = await db.execute(wallet_query)
                    wallet = result.scalar_one()
                    
                    print(f"✅ 分配成功: 钱包风险等级 = {wallet.risk_level}")
                    
                    # 释放钱包
                    wallet_service = WalletPoolService(db)
                    await wallet_service.release_wallet(allocated_wallet.id, admin_id=1)
                else:
                    print(f"⚠️ 未找到符合 {risk_level} 风险等级的钱包")
                    
            print("\n🎉 风险容忍度测试完成!")
            
        except Exception as e:
            print(f"❌ 风险容忍度测试失败: {e}")
            import traceback
            traceback.print_exc()


async def test_preferred_wallets():
    """测试优选钱包功能"""
    
    async with AsyncSessionLocal() as db:
        try:
            allocator = SmartWalletAllocator(db)
            
            print("\n⭐ 测试优选钱包功能...")
            
            # 获取前3个可用钱包ID
            from sqlalchemy import select
            wallet_query = select(USDTWallet.id).where(
                USDTWallet.status == "available"
            ).limit(3)
            
            result = await db.execute(wallet_query)
            preferred_ids = [row[0] for row in result]
            
            if len(preferred_ids) >= 2:
                print(f"设置优选钱包: {preferred_ids[:2]}")
                
                request = AllocationRequest(
                    order_id=f"PREFERRED_TEST_{int(datetime.now().timestamp())}",
                    network="TRC20", 
                    amount=Decimal("75.0"),
                    preferred_wallets=preferred_ids[:2]
                )
                
                allocated_wallet = await allocator.allocate_optimal_wallet(request)
                
                if allocated_wallet:
                    if allocated_wallet.id in preferred_ids[:2]:
                        print(f"✅ 优选钱包分配成功: ID={allocated_wallet.id}")
                    else:
                        print(f"⚠️ 分配了非优选钱包: ID={allocated_wallet.id}")
                    
                    # 释放钱包
                    wallet_service = WalletPoolService(db)
                    await wallet_service.release_wallet(allocated_wallet.id, admin_id=1)
                else:
                    print("❌ 优选钱包分配失败")
            else:
                print("❌ 可用钱包不足，无法测试优选功能")
            
            print("\n🎉 优选钱包测试完成!")
            
        except Exception as e:
            print(f"❌ 优选钱包测试失败: {e}")
            import traceback
            traceback.print_exc()


async def test_allocation_statistics():
    """测试分配统计功能"""
    
    async with AsyncSessionLocal() as db:
        try:
            allocator = SmartWalletAllocator(db)
            
            print("\n📊 测试分配统计功能...")
            
            # 获取整体统计
            stats = await allocator.get_allocation_statistics()
            
            print("整体钱包池统计:")
            print(f"  总钱包数: {stats['total_wallets']}")
            print(f"  可用钱包: {stats['available_wallets']}")  
            print(f"  已占用钱包: {stats['occupied_wallets']}")
            print(f"  利用率: {stats['utilization_rate']:.2f}%")
            
            print(f"\n状态分布:")
            for status, count in stats['status_distribution'].items():
                print(f"  {status}: {count} 个")
            
            print(f"\n风险分布:")
            for risk, count in stats['risk_distribution'].items():
                print(f"  {risk}: {count} 个")
            
            # 按网络统计
            for network in ["TRC20", "ERC20", "BEP20"]:
                network_stats = await allocator.get_allocation_statistics(network)
                if network_stats['total_wallets'] > 0:
                    print(f"\n{network} 网络统计:")
                    print(f"  总数: {network_stats['total_wallets']}")
                    print(f"  利用率: {network_stats['utilization_rate']:.2f}%")
            
            print("\n🎉 统计功能测试完成!")
            
        except Exception as e:
            print(f"❌ 统计功能测试失败: {e}")
            import traceback
            traceback.print_exc()


async def cleanup_test_data():
    """清理测试数据"""
    print("\n🧹 清理测试数据...")
    
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import delete
            
            # 删除所有测试钱包
            delete_stmt = delete(USDTWallet).where(
                USDTWallet.wallet_name.like('%risk%')
            )
            
            result = await db.execute(delete_stmt)
            await db.commit()
            
            print(f"✅ 清理完成，删除了 {result.rowcount} 个测试钱包")
            
        except Exception as e:
            print(f"❌ 清理数据时发生错误: {e}")


async def main():
    """主测试函数"""
    
    print("🚀 开始智能钱包分配算法测试...")
    
    # 设置测试数据
    wallet_count = await setup_test_wallets()
    
    if wallet_count == 0:
        print("❌ 无法创建测试钱包，退出测试")
        return
    
    try:
        # 执行各项测试
        await test_allocation_strategies()
        await test_risk_tolerance()
        await test_preferred_wallets() 
        await test_allocation_statistics()
        
        print("\n🎉 所有智能分配测试完成!")
        
    finally:
        # 清理测试数据
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())