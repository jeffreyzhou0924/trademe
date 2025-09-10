#!/usr/bin/env python3
"""
用户钱包系统初始化脚本
- 创建主钱包（归集目标）
- 为现有用户分配钱包
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from app.database import get_db
from app.services.user_wallet_service import user_wallet_service
from app.services.wallet_generator import MultiChainWalletGenerator
from sqlalchemy import text


async def create_master_wallets():
    """创建主钱包"""
    print("📦 创建主钱包...")
    
    wallet_generator = MultiChainWalletGenerator()
    networks = ['TRC20', 'ERC20']  # BEP20支持待后续添加
    
    async for db in get_db():
        for network in networks:
            # 检查是否已存在主钱包
            result = await db.execute(
                text("SELECT id FROM master_wallets WHERE network = :network"),
                {"network": network}
            )
            existing = result.fetchone()
            
            if existing:
                print(f"✅ {network} 主钱包已存在")
                continue
            
            # 生成主钱包
            wallet_info = wallet_generator.generate_wallet(network, f"master_{network.lower()}")
            
            # 保存主钱包
            await db.execute(
                text("""
                    INSERT INTO master_wallets (network, address, private_key, description, is_active)
                    VALUES (:network, :address, :private_key, :description, 1)
                """),
                {
                    "network": network,
                    "address": wallet_info.address,
                    "private_key": wallet_info.private_key,
                    "description": f"{network} 网络主归集钱包"
                }
            )
            
            print(f"✅ 创建 {network} 主钱包: {wallet_info.address}")
        
        await db.commit()
        break  # 只处理一个数据库会话
    
    print("📦 主钱包创建完成")


async def allocate_wallets_for_existing_users():
    """为现有用户分配钱包"""
    print("👥 为现有用户分配钱包...")
    
    async for db in get_db():
        # 获取所有用户
        result = await db.execute(
            text("SELECT id, email, username FROM users WHERE id > 0")
        )
        users = result.fetchall()
        
        print(f"📊 找到 {len(users)} 个用户")
        
        for user in users:
            user_id, email, username = user
            
            try:
                print(f"🔄 为用户 {user_id} ({email}) 分配钱包...")
                
                # 分配钱包
                wallets = await user_wallet_service.allocate_wallets_for_user(user_id)
                
                print(f"✅ 用户 {user_id} 钱包分配完成:")
                for network, address in wallets.items():
                    print(f"   {network}: {address}")
                
            except Exception as e:
                print(f"❌ 用户 {user_id} 钱包分配失败: {e}")
        
        break  # 只处理一个数据库会话
    
    print("👥 用户钱包分配完成")


async def display_system_overview():
    """显示系统概览"""
    print("\n📊 用户钱包系统概览")
    print("=" * 50)
    
    overview = await user_wallet_service.get_all_user_wallets()
    
    summary = overview['summary']
    print(f"总用户数: {summary['total_users']}")
    print(f"用户钱包数: {summary['total_user_wallets']}")
    print(f"有资金钱包: {summary['funded_wallets']}")
    print(f"总用户余额: {summary['total_user_balance']:.8f} USDT")
    print(f"网络数量: {summary['networks_count']}")
    
    print("\n📈 网络分布:")
    for network_info in overview['network_distribution']:
        print(f"  {network_info['network']}: {network_info['wallet_count']} 个钱包, "
              f"{network_info['total_balance']:.8f} USDT")
    
    print(f"\n👤 用户详情 (前10名):")
    for i, user in enumerate(overview['users'][:10], 1):
        print(f"  {i:2d}. {user['email']} - {user['wallet_count']} 钱包, "
              f"{user['total_balance']:.8f} USDT")


async def check_master_wallets():
    """检查主钱包状态"""
    print("\n💰 主钱包状态:")
    print("=" * 50)
    
    async for db in get_db():
        result = await db.execute(
            text("SELECT network, address, description, is_active FROM master_wallets ORDER BY network")
        )
        master_wallets = result.fetchall()
        
        if not master_wallets:
            print("❌ 未找到主钱包")
            return
        
        for wallet in master_wallets:
            network, address, description, is_active = wallet
            status = "🟢 活跃" if is_active else "🔴 停用"
            print(f"  {network}: {address} {status}")
            print(f"    描述: {description}")
        
        break  # 只处理一个数据库会话


async def main():
    """主函数"""
    print("🚀 用户钱包系统初始化")
    print("=" * 50)
    
    try:
        # 1. 创建主钱包
        await create_master_wallets()
        
        # 2. 为现有用户分配钱包
        await allocate_wallets_for_existing_users()
        
        # 3. 检查主钱包状态
        await check_master_wallets()
        
        # 4. 显示系统概览
        await display_system_overview()
        
        print("\n🎉 用户钱包系统初始化完成！")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())