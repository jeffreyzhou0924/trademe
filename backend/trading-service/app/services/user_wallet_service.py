"""
用户钱包服务 - 处理用户钱包分配、管理和归集
"""

import asyncio
import logging
import secrets
from typing import List, Dict, Optional, Any
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from app.database import get_db
from app.services.wallet_generator import MultiChainWalletGenerator, WalletInfo
from app.services.blockchain_monitor_service import BlockchainMonitorService
from app.services.blockchain_transfer_service import blockchain_transfer_service

logger = logging.getLogger(__name__)


class UserWalletService:
    """用户钱包服务"""
    
    SUPPORTED_NETWORKS = ['TRC20', 'ERC20']  # BEP20支持待后续添加
    
    def __init__(self):
        self.wallet_generator = MultiChainWalletGenerator()
        self.blockchain_monitor = BlockchainMonitorService()
    
    async def allocate_wallets_for_user(self, user_id: int) -> Dict[str, str]:
        """为用户分配3个网络的钱包地址"""
        try:
            user_wallets = {}
            
            async for db in get_db():
                # 检查用户是否已经有钱包分配
                for network in self.SUPPORTED_NETWORKS:
                    result = await db.execute(
                        text("SELECT address FROM user_wallets WHERE user_id = :user_id AND network = :network"),
                        {"user_id": user_id, "network": network}
                    )
                    existing = result.fetchone()
                    
                    if existing:
                        user_wallets[network] = existing[0]
                        continue
                    
                    # 从钱包池中分配或生成新钱包
                    wallet_address = await self._allocate_wallet_for_network(db, user_id, network)
                    user_wallets[network] = wallet_address
                
                await db.commit()
                break  # 只处理一个数据库会话
                
            logger.info(f"为用户 {user_id} 分配钱包完成: {user_wallets}")
            return user_wallets
            
        except Exception as e:
            logger.error(f"为用户 {user_id} 分配钱包失败: {e}")
            raise
    
    async def _allocate_wallet_for_network(self, db, user_id: int, network: str) -> str:
        """为特定网络分配钱包"""
        # 首先尝试从钱包池中分配可用钱包
        result = await db.execute(
            text("""
                SELECT id, address FROM usdt_wallets 
                WHERE network = :network AND status = 'available' 
                AND current_order_id IS NULL 
                LIMIT 1
            """),
            {"network": network}
        )
        available_wallet = result.fetchone()
        
        if available_wallet:
            wallet_id, address = available_wallet
            
            # 更新钱包状态为用户专用
            await db.execute(
                text("UPDATE usdt_wallets SET status = 'user_allocated' WHERE id = :wallet_id"),
                {"wallet_id": wallet_id}
            )
            
            # 创建用户钱包关联
            await db.execute(
                text("""
                    INSERT INTO user_wallets (user_id, wallet_id, network, address, is_primary)
                    VALUES (:user_id, :wallet_id, :network, :address, :is_primary)
                """),
                {
                    "user_id": user_id,
                    "wallet_id": wallet_id,
                    "network": network,
                    "address": address,
                    "is_primary": True
                }
            )
            
            return address
        
        # 如果钱包池中没有可用钱包，生成新的
        return await self._generate_new_user_wallet(db, user_id, network)
    
    async def _generate_new_user_wallet(self, db, user_id: int, network: str) -> str:
        """为用户生成新钱包"""
        try:
            # 生成钱包
            wallet_info = self.wallet_generator.generate_wallet(network, f"user_{user_id}_{network.lower()}")
            
            # 保存到钱包池
            result = await db.execute(
                text("""
                    INSERT INTO usdt_wallets 
                    (wallet_name, network, address, private_key, public_key, balance, status, risk_level)
                    VALUES (:name, :network, :address, :private_key, :public_key, 0.0, 'user_allocated', 'LOW')
                """),
                {
                    "name": wallet_info.name,
                    "network": wallet_info.network,
                    "address": wallet_info.address,
                    "private_key": wallet_info.private_key,
                    "public_key": wallet_info.public_key
                }
            )
            
            wallet_id = result.lastrowid
            
            # 创建用户钱包关联
            await db.execute(
                text("""
                    INSERT INTO user_wallets (user_id, wallet_id, network, address, is_primary)
                    VALUES (:user_id, :wallet_id, :network, :address, :is_primary)
                """),
                {
                    "user_id": user_id,
                    "wallet_id": wallet_id,
                    "network": network,
                    "address": wallet_info.address,
                    "is_primary": True
                }
            )
            
            logger.info(f"为用户 {user_id} 生成新钱包 {network}: {wallet_info.address}")
            return wallet_info.address
            
        except Exception as e:
            logger.error(f"为用户 {user_id} 生成 {network} 钱包失败: {e}")
            raise
    
    async def get_user_wallets(self, user_id: int) -> Dict[str, Any]:
        """获取用户所有钱包信息"""
        try:
            async for db in get_db():
                result = await db.execute(
                    text("""
                        SELECT uw.network, uw.address, w.balance, w.status, 
                               w.transaction_count, w.total_received, uw.created_at
                        FROM user_wallets uw
                        JOIN usdt_wallets w ON uw.wallet_id = w.id
                        WHERE uw.user_id = :user_id
                        ORDER BY uw.network
                    """),
                    {"user_id": user_id}
                )
                wallets = result.fetchall()
                
                wallet_dict = {}
                total_balance = Decimal('0')
                
                for wallet in wallets:
                    network = wallet[0]
                    wallet_dict[network] = {
                        "address": wallet[1],
                        "balance": float(wallet[2] or 0),
                        "status": wallet[3],
                        "transaction_count": wallet[4] or 0,
                        "total_received": float(wallet[5] or 0),
                        "created_at": wallet[6]
                    }
                    total_balance += Decimal(str(wallet[2] or 0))
                
                result_data = {
                    "user_id": user_id,
                    "wallets": wallet_dict,
                    "total_balance": float(total_balance),
                    "networks_count": len(wallet_dict)
                }
                break  # 只处理一个数据库会话
            
            return result_data
                
        except Exception as e:
            logger.error(f"获取用户 {user_id} 钱包信息失败: {e}")
            return {"user_id": user_id, "wallets": {}, "total_balance": 0.0, "networks_count": 0}
    
    async def check_user_balances(self, user_id: int) -> Dict[str, Decimal]:
        """检查用户所有钱包余额"""
        try:
            async for db in get_db():
                balances = await db.execute(
                    text("""
                        SELECT uw.network, w.balance
                        FROM user_wallets uw
                        JOIN usdt_wallets w ON uw.wallet_id = w.id
                        WHERE uw.user_id = :user_id
                    """),
                    {"user_id": user_id}
                )
                results = balances.fetchall()
                result_dict = {network: Decimal(str(balance or 0)) for network, balance in results}
                break  # 只处理一个数据库会话
                
            return result_dict
                
        except Exception as e:
            logger.error(f"检查用户 {user_id} 余额失败: {e}")
            return {}
    
    async def initiate_fund_consolidation(self, user_id: int, min_amount: Decimal = Decimal('1.0')) -> List[Dict]:
        """发起资金归集（将用户钱包资金转移到主钱包）"""
        try:
            consolidation_tasks = []
            
            async for db in get_db():
                # 检查用户钱包余额
                result = await db.execute(
                    text("""
                        SELECT uw.id, uw.network, uw.address, w.balance, w.private_key
                        FROM user_wallets uw
                        JOIN usdt_wallets w ON uw.wallet_id = w.id
                        WHERE uw.user_id = :user_id AND w.balance >= :min_amount
                    """),
                    {"user_id": user_id, "min_amount": float(min_amount)}
                )
                user_wallets = result.fetchall()
                
                for wallet in user_wallets:
                    user_wallet_id, network, address, balance, private_key = wallet
                    
                    # 获取对应的主钱包
                    master_result = await db.execute(
                        text("SELECT id, address FROM master_wallets WHERE network = :network AND is_active = 1"),
                        {"network": network}
                    )
                    master_wallet = master_result.fetchone()
                    
                    if not master_wallet:
                        logger.warning(f"未找到 {network} 网络的主钱包")
                        continue
                    
                    master_wallet_id, master_address = master_wallet
                    
                    # 创建归集记录
                    insert_result = await db.execute(
                        text("""
                            INSERT INTO fund_consolidations 
                            (user_wallet_id, master_wallet_id, amount, status)
                            VALUES (:user_wallet_id, :master_wallet_id, :amount, 'pending')
                        """),
                        {
                            "user_wallet_id": user_wallet_id,
                            "master_wallet_id": master_wallet_id,
                            "amount": float(balance)
                        }
                    )
                    
                    consolidation_id = insert_result.lastrowid
                    
                    consolidation_tasks.append({
                        "consolidation_id": consolidation_id,
                        "network": network,
                        "from_address": address,
                        "to_address": master_address,
                        "amount": float(balance),
                        "private_key": private_key
                    })
                
                await db.commit()
                break  # 只处理一个数据库会话
                
                # 执行归集任务（这里可以异步处理）
                for task in consolidation_tasks:
                    await self._execute_consolidation_task(task)
                
                return consolidation_tasks
                
        except Exception as e:
            logger.error(f"发起用户 {user_id} 资金归集失败: {e}")
            raise
    
    async def _execute_consolidation_task(self, task: Dict):
        """执行单个归集任务 - 使用真实区块链转账"""
        consolidation_id = task['consolidation_id']
        network = task['network']
        from_address = task['from_address']
        to_address = task['to_address']
        amount = Decimal(str(task['amount']))
        private_key = task['private_key']
        
        try:
            logger.info(f"开始执行归集任务 {consolidation_id}: {network} {amount} USDT from {from_address} to {to_address}")
            
            # 检查余额是否足够
            balance = await blockchain_transfer_service.get_balance(network, from_address)
            if balance < amount:
                raise Exception(f"余额不足: 需要 {amount} USDT, 实际 {balance} USDT")
            
            # 预留一些余额用于手续费（特别是ERC20）
            if network.upper() == 'ERC20':
                # ERC20需要ETH作为gas费，这里预留0.1 USDT作为缓冲
                if balance - amount < Decimal('0.1'):
                    amount = balance - Decimal('0.1')
                    if amount <= 0:
                        raise Exception("余额不足以支付gas费用")
            
            # 执行真实的区块链转账
            tx_hash, success = await blockchain_transfer_service.transfer_usdt(
                network=network,
                from_private_key=private_key,
                to_address=to_address,
                amount=amount
            )
            
            if success and tx_hash:
                # 更新归集记录为成功
                async for db in get_db():
                    await db.execute(
                        text("""
                            UPDATE fund_consolidations 
                            SET status = 'completed', transaction_hash = :tx_hash, completed_at = :now
                            WHERE id = :consolidation_id
                        """),
                        {
                            "consolidation_id": consolidation_id,
                            "tx_hash": tx_hash,
                            "now": datetime.now()
                        }
                    )
                    await db.commit()
                    break
                
                logger.info(f"归集任务 {consolidation_id} 完成: {tx_hash}")
                
                # 可选: 同步更新钱包余额
                await self._sync_wallet_balance_after_transfer(from_address, network)
                
            else:
                raise Exception("区块链转账失败")
            
        except Exception as e:
            logger.error(f"执行归集任务 {consolidation_id} 失败: {e}")
            
            # 更新归集记录为失败
            try:
                async for db in get_db():
                    await db.execute(
                        text("""
                            UPDATE fund_consolidations 
                            SET status = 'failed', error_message = :error
                            WHERE id = :consolidation_id
                        """),
                        {
                            "consolidation_id": consolidation_id,
                            "error": str(e)
                        }
                    )
                    await db.commit()
                    break
            except Exception as db_error:
                logger.error(f"更新归集记录失败状态时出错: {db_error}")
    
    async def _sync_wallet_balance_after_transfer(self, address: str, network: str):
        """转账后同步钱包余额"""
        try:
            # 获取最新余额
            new_balance = await blockchain_transfer_service.get_balance(network, address)
            
            # 更新数据库中的余额
            async for db in get_db():
                await db.execute(
                    text("""
                        UPDATE usdt_wallets 
                        SET balance = :balance, last_sync_time = :now 
                        WHERE address = :address AND network = :network
                    """),
                    {
                        "balance": float(new_balance),
                        "address": address,
                        "network": network,
                        "now": datetime.now()
                    }
                )
                await db.commit()
                break
                
            logger.info(f"已同步钱包 {address} 余额: {new_balance} USDT")
            
        except Exception as e:
            logger.error(f"同步钱包余额失败: {e}")
    
    async def get_all_user_wallets(self) -> Dict[str, Any]:
        """获取所有用户钱包统计信息（管理后台用）"""
        try:
            async for db in get_db():
                # 用户钱包统计
                stats_result = await db.execute(
                    text("""
                        SELECT 
                            COUNT(DISTINCT uw.user_id) as total_users,
                            COUNT(*) as total_user_wallets,
                            SUM(CASE WHEN w.balance > 0 THEN 1 ELSE 0 END) as funded_wallets,
                            SUM(w.balance) as total_user_balance,
                            COUNT(DISTINCT uw.network) as networks_count
                        FROM user_wallets uw
                        JOIN usdt_wallets w ON uw.wallet_id = w.id
                    """)
                )
                stats = stats_result.fetchone()
                
                # 网络分布
                network_stats_result = await db.execute(
                    text("""
                        SELECT uw.network, COUNT(*) as count, SUM(w.balance) as total_balance
                        FROM user_wallets uw
                        JOIN usdt_wallets w ON uw.wallet_id = w.id
                        GROUP BY uw.network
                    """)
                )
                network_stats = network_stats_result.fetchall()
                
                # 用户详情
                user_details_result = await db.execute(
                    text("""
                        SELECT 
                            u.id, u.email, u.username,
                            COUNT(uw.id) as wallet_count,
                            SUM(w.balance) as total_balance,
                            MAX(uw.created_at) as last_wallet_created
                        FROM users u
                        LEFT JOIN user_wallets uw ON u.id = uw.user_id
                        LEFT JOIN usdt_wallets w ON uw.wallet_id = w.id
                        GROUP BY u.id, u.email, u.username
                        ORDER BY total_balance DESC
                    """)
                )
                user_details = user_details_result.fetchall()
                
                return {
                    "summary": {
                        "total_users": stats[0] or 0,
                        "total_user_wallets": stats[1] or 0,
                        "funded_wallets": stats[2] or 0,
                        "total_user_balance": float(stats[3] or 0),
                        "networks_count": stats[4] or 0
                    },
                    "network_distribution": [
                        {
                            "network": row[0],
                            "wallet_count": row[1],
                            "total_balance": float(row[2] or 0)
                        }
                        for row in network_stats
                    ],
                    "users": [
                        {
                            "user_id": row[0],
                            "email": row[1],
                            "username": row[2],
                            "wallet_count": row[3] or 0,
                            "total_balance": float(row[4] or 0),
                            "last_wallet_created": row[5]
                        }
                        for row in user_details
                    ]
                }
                break  # 只处理一个数据库会话
                
        except Exception as e:
            logger.error(f"获取用户钱包统计失败: {e}")
            return {
                "summary": {"total_users": 0, "total_user_wallets": 0, "funded_wallets": 0, "total_user_balance": 0.0, "networks_count": 0},
                "network_distribution": [],
                "users": []
            }


# 全局实例
user_wallet_service = UserWalletService()