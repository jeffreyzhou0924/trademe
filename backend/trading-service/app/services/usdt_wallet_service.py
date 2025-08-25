"""
USDT钱包池管理服务 - 中心化钱包池核心实现
实现智能钱包分配、余额管理、安全控制等功能
"""

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from cryptography.fernet import Fernet
from sqlalchemy import select, update, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import AsyncSessionLocal
from app.models.payment import USDTWallet, USDTPaymentOrder, WalletBalance
from app.core.config import settings


class USDTWalletService:
    """USDT钱包池管理服务 - 中心化架构实现"""
    
    def __init__(self):
        # 加密管理
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # 钱包池配置
        self.max_wallets_per_network = 10  # 每个网络最大钱包数
        self.wallet_allocation_timeout = 1800  # 钱包分配超时时间(30分钟)
        self.min_available_wallets = 2  # 最少可用钱包数
        
        # 风险控制配置
        self.daily_limit_default = Decimal("1000.0")  # 默认日限额
        self.monthly_limit_default = Decimal("10000.0")  # 默认月限额
        self.high_risk_threshold = Decimal("500.0")  # 高风险阈值
        
    def _get_or_create_encryption_key(self) -> bytes:
        """获取或创建加密密钥"""
        key_file = settings.DATA_DIR / "usdt_wallet_encryption.key"
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(key)
            return key
    
    def _encrypt_private_key(self, private_key: str) -> str:
        """加密私钥"""
        if not private_key:
            return ""
        return self.cipher.encrypt(private_key.encode()).decode()
    
    def _decrypt_private_key(self, encrypted_key: str) -> str:
        """解密私钥"""
        if not encrypted_key:
            return ""
        try:
            return self.cipher.decrypt(encrypted_key.encode()).decode()
        except Exception as e:
            logger.error(f"私钥解密失败: {e}")
            return ""
    
    async def create_wallet(
        self,
        wallet_name: str,
        network: str,
        address: str,
        private_key: str,
        daily_limit: Optional[Decimal] = None,
        monthly_limit: Optional[Decimal] = None
    ) -> USDTWallet:
        """创建新钱包到钱包池"""
        
        async with AsyncSessionLocal() as session:
            # 检查地址是否已存在
            existing = await session.execute(
                select(USDTWallet).where(USDTWallet.address == address)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"钱包地址已存在: {address}")
            
            # 加密私钥
            encrypted_private_key = self._encrypt_private_key(private_key)
            
            # 创建钱包
            wallet = USDTWallet(
                wallet_name=wallet_name,
                network=network.upper(),
                address=address,
                private_key=encrypted_private_key,
                status="available",
                daily_limit=daily_limit or self.daily_limit_default,
                monthly_limit=monthly_limit or self.monthly_limit_default,
                risk_level="LOW"
            )
            
            session.add(wallet)
            await session.commit()
            await session.refresh(wallet)
            
            logger.info(f"创建新钱包 - 名称: {wallet_name}, 网络: {network}, 地址: {address[:10]}...")
            return wallet
    
    async def get_available_wallets(
        self, 
        network: Optional[str] = None,
        min_daily_remaining: Optional[Decimal] = None
    ) -> List[USDTWallet]:
        """获取可用钱包列表"""
        
        async with AsyncSessionLocal() as session:
            conditions = [USDTWallet.status == "available"]
            
            if network:
                conditions.append(USDTWallet.network == network.upper())
                
            if min_daily_remaining:
                conditions.append(
                    USDTWallet.daily_limit - USDTWallet.current_daily_received >= min_daily_remaining
                )
            
            query = select(USDTWallet).where(and_(*conditions)).order_by(
                USDTWallet.current_daily_received.asc(),  # 优先选择使用较少的钱包
                USDTWallet.last_sync_at.asc().nulls_first()  # 然后按最后同步时间
            )
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def allocate_wallet_for_payment(
        self,
        order_no: str,
        network: str,
        amount: Decimal,
        user_risk_level: str = "LOW"
    ) -> Optional[USDTWallet]:
        """为支付订单分配钱包 - 核心业务逻辑"""
        
        async with AsyncSessionLocal() as session:
            # 1. 获取适合的钱包
            suitable_wallets = await self._find_suitable_wallets(
                session, network, amount, user_risk_level
            )
            
            if not suitable_wallets:
                logger.warning(f"没有找到适合的钱包 - 网络: {network}, 金额: {amount}")
                return None
            
            # 2. 智能选择最优钱包
            selected_wallet = await self._select_optimal_wallet(suitable_wallets, amount)
            
            # 3. 分配钱包
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == selected_wallet.id)
                .values(
                    status="occupied",
                    current_order_id=order_no,
                    allocated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            logger.info(f"钱包分配成功 - 订单: {order_no}, 钱包: {selected_wallet.wallet_name}")
            
            # 4. 检查钱包池状态，必要时触发补充
            await self._check_wallet_pool_health(session, network)
            
            return selected_wallet
    
    async def _find_suitable_wallets(
        self,
        session: AsyncSession,
        network: str,
        amount: Decimal,
        user_risk_level: str
    ) -> List[USDTWallet]:
        """查找适合的钱包"""
        
        conditions = [
            USDTWallet.status == "available",
            USDTWallet.network == network.upper(),
            # 检查日限额
            USDTWallet.daily_limit - USDTWallet.current_daily_received >= amount,
            # 检查月限额  
            USDTWallet.monthly_limit - USDTWallet.current_monthly_received >= amount
        ]
        
        # 根据用户风险等级筛选钱包
        if user_risk_level == "HIGH":
            conditions.append(USDTWallet.risk_level.in_(["LOW", "MEDIUM", "HIGH"]))
        elif user_risk_level == "MEDIUM":
            conditions.append(USDTWallet.risk_level.in_(["LOW", "MEDIUM"]))
        else:  # LOW
            conditions.append(USDTWallet.risk_level == "LOW")
        
        query = select(USDTWallet).where(and_(*conditions))
        result = await session.execute(query)
        return result.scalars().all()
    
    async def _select_optimal_wallet(
        self, 
        wallets: List[USDTWallet], 
        amount: Decimal
    ) -> USDTWallet:
        """智能选择最优钱包"""
        
        def calculate_wallet_score(wallet: USDTWallet) -> float:
            """计算钱包评分"""
            # 1. 使用率得分 (40%) - 优先选择使用率低的
            daily_usage_rate = float(wallet.current_daily_received) / float(wallet.daily_limit)
            usage_score = (1.0 - daily_usage_rate) * 0.4
            
            # 2. 余额分散性得分 (30%) - 避免单个钱包集中过多资金
            balance_score = min(1.0, float(wallet.balance) / 1000.0) * 0.3
            
            # 3. 风险等级得分 (20%)
            risk_scores = {"LOW": 1.0, "MEDIUM": 0.7, "HIGH": 0.4}
            risk_score = risk_scores.get(wallet.risk_level, 0.5) * 0.2
            
            # 4. 活跃度得分 (10%) - 最近使用的钱包优先
            if wallet.last_sync_at:
                hours_since_sync = (datetime.utcnow() - wallet.last_sync_at).total_seconds() / 3600
                activity_score = max(0, (24 - hours_since_sync) / 24) * 0.1
            else:
                activity_score = 0.05  # 新钱包默认分数
            
            return usage_score + balance_score + risk_score + activity_score
        
        # 计算每个钱包的得分并选择最优的
        wallet_scores = [(wallet, calculate_wallet_score(wallet)) for wallet in wallets]
        wallet_scores.sort(key=lambda x: x[1], reverse=True)
        
        best_wallet = wallet_scores[0][0]
        best_score = wallet_scores[0][1]
        
        logger.debug(f"选择最优钱包: {best_wallet.wallet_name}, 得分: {best_score:.3f}")
        return best_wallet
    
    async def release_wallet(self, order_no: str, update_statistics: bool = True) -> bool:
        """释放钱包分配"""
        
        async with AsyncSessionLocal() as session:
            # 查找分配的钱包
            query = select(USDTWallet).where(USDTWallet.current_order_id == order_no)
            result = await session.execute(query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                logger.warning(f"未找到分配给订单 {order_no} 的钱包")
                return False
            
            # 释放钱包
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet.id)
                .values(
                    status="available",
                    current_order_id=None,
                    allocated_at=None
                )
            )
            
            # 如果需要，更新统计信息
            if update_statistics:
                # 这里可以添加统计更新逻辑
                pass
            
            await session.commit()
            logger.info(f"释放钱包: {wallet.wallet_name}, 订单: {order_no}")
            return True
    
    async def update_wallet_balance(
        self,
        wallet_id: int,
        new_balance: Decimal,
        block_height: Optional[int] = None,
        sync_source: str = "api"
    ) -> bool:
        """更新钱包余额"""
        
        async with AsyncSessionLocal() as session:
            # 更新钱包余额
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(
                    balance=new_balance,
                    last_sync_at=datetime.utcnow(),
                    sync_block_height=block_height
                )
            )
            
            # 创建余额快照
            balance_snapshot = WalletBalance(
                wallet_id=wallet_id,
                balance=new_balance,
                block_height=block_height,
                sync_source=sync_source
            )
            session.add(balance_snapshot)
            
            await session.commit()
            logger.debug(f"更新钱包余额: ID={wallet_id}, 余额={new_balance}")
            return True
    
    async def record_payment_received(
        self,
        wallet_id: int,
        amount: Decimal,
        transaction_hash: str
    ) -> bool:
        """记录钱包收到支付"""
        
        async with AsyncSessionLocal() as session:
            # 更新钱包统计
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(
                    total_received=USDTWallet.total_received + amount,
                    current_daily_received=USDTWallet.current_daily_received + amount,
                    current_monthly_received=USDTWallet.current_monthly_received + amount,
                    transaction_count=USDTWallet.transaction_count + 1
                )
            )
            
            await session.commit()
            logger.info(f"记录支付收到: 钱包ID={wallet_id}, 金额={amount}, 交易={transaction_hash[:10]}...")
            return True
    
    async def _check_wallet_pool_health(self, session: AsyncSession, network: str):
        """检查钱包池健康状态"""
        
        # 检查可用钱包数量
        available_query = select(func.count(USDTWallet.id)).where(
            and_(
                USDTWallet.network == network.upper(),
                USDTWallet.status == "available"
            )
        )
        result = await session.execute(available_query)
        available_count = result.scalar()
        
        if available_count < self.min_available_wallets:
            logger.warning(f"钱包池警告: {network} 网络可用钱包不足 ({available_count}/{self.min_available_wallets})")
            # 这里可以触发告警或自动补充钱包的逻辑
    
    async def cleanup_expired_allocations(self) -> int:
        """清理超时的钱包分配"""
        
        expired_time = datetime.utcnow() - timedelta(seconds=self.wallet_allocation_timeout)
        
        async with AsyncSessionLocal() as session:
            # 查找超时分配
            query = select(USDTWallet).where(
                and_(
                    USDTWallet.status == "occupied",
                    USDTWallet.allocated_at < expired_time
                )
            )
            result = await session.execute(query)
            expired_wallets = result.scalars().all()
            
            # 释放超时钱包
            if expired_wallets:
                await session.execute(
                    update(USDTWallet)
                    .where(USDTWallet.id.in_([w.id for w in expired_wallets]))
                    .values(
                        status="available",
                        current_order_id=None,
                        allocated_at=None
                    )
                )
                await session.commit()
                
                logger.info(f"清理超时钱包分配: {len(expired_wallets)} 个钱包")
            
            return len(expired_wallets)
    
    async def get_wallet_pool_statistics(self) -> Dict[str, Any]:
        """获取钱包池统计信息"""
        
        async with AsyncSessionLocal() as session:
            # 按网络和状态统计
            stats_query = select(
                USDTWallet.network,
                USDTWallet.status,
                func.count(USDTWallet.id).label('count'),
                func.sum(USDTWallet.balance).label('total_balance'),
                func.sum(USDTWallet.current_daily_received).label('daily_received'),
                func.avg(USDTWallet.current_daily_received / USDTWallet.daily_limit * 100).label('avg_usage_rate')
            ).group_by(USDTWallet.network, USDTWallet.status)
            
            result = await session.execute(stats_query)
            raw_stats = result.all()
            
            # 整理统计数据
            stats = {}
            for row in raw_stats:
                network = row.network
                if network not in stats:
                    stats[network] = {
                        'total_wallets': 0,
                        'available_wallets': 0,
                        'occupied_wallets': 0,
                        'total_balance': Decimal('0'),
                        'daily_received': Decimal('0'),
                        'average_usage_rate': 0.0
                    }
                
                stats[network]['total_wallets'] += row.count
                if row.status == 'available':
                    stats[network]['available_wallets'] = row.count
                elif row.status == 'occupied':
                    stats[network]['occupied_wallets'] = row.count
                
                stats[network]['total_balance'] += row.total_balance or Decimal('0')
                stats[network]['daily_received'] += row.daily_received or Decimal('0')
                if row.avg_usage_rate:
                    stats[network]['average_usage_rate'] = float(row.avg_usage_rate)
            
            return stats
    
    async def reset_daily_statistics(self) -> int:
        """重置每日统计（定时任务调用）"""
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(USDTWallet).values(current_daily_received=Decimal('0'))
            )
            await session.commit()
            
            updated_count = result.rowcount
            logger.info(f"重置每日统计完成: {updated_count} 个钱包")
            return updated_count


# 全局实例
usdt_wallet_service = USDTWalletService()