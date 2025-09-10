"""
资金归集服务 - 用户充值资金自动归集到主钱包
实现多网络资金归集、手续费优化、风险控制等功能
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func, desc

from app.models.payment import USDTWallet, USDTPaymentOrder, BlockchainTransaction
from app.database import AsyncSessionLocal
# from app.services.blockchain_monitor_service import BlockchainMonitorService  # 临时禁用，避免循环依赖
from app.services.usdt_wallet_service import USDTWalletService
from app.config import settings
from app.utils.data_validation import DataValidator

logger = logging.getLogger(__name__)


class ConsolidationStrategy(Enum):
    """归集策略"""
    IMMEDIATE = "immediate"      # 立即归集 (适合高金额)
    SCHEDULED = "scheduled"      # 定时归集 (节省手续费)
    THRESHOLD = "threshold"      # 阈值归集 (平衡效率和成本)
    MANUAL = "manual"           # 手动归集


@dataclass
class ConsolidationRule:
    """归集规则配置"""
    network: str                    # 网络类型
    min_consolidation_amount: Decimal  # 最小归集金额
    consolidation_threshold: Decimal   # 归集阈值
    max_fee_ratio: Decimal             # 最大手续费比例
    consolidation_interval: int        # 归集间隔(秒)
    master_wallet_address: str         # 主钱包地址


@dataclass
class ConsolidationTask:
    """归集任务"""
    task_id: str
    source_wallet_id: int
    target_wallet_id: int
    network: str
    amount: Decimal
    estimated_fee: Decimal
    priority: int  # 1-5, 5为最高优先级
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    status: str = "pending"  # pending, processing, completed, failed


class FundConsolidationService:
    """资金归集服务"""
    
    def __init__(self):
        self.wallet_service = USDTWalletService()
        # self.blockchain_service = BlockchainMonitorService()  # 临时禁用
        
        # 归集配置
        self.consolidation_rules = self._get_consolidation_rules()
        self.max_concurrent_tasks = 5
        self.fee_estimation_cache = {}
        self.consolidation_lock = asyncio.Lock()
        
    def _get_consolidation_rules(self) -> Dict[str, ConsolidationRule]:
        """获取归集规则配置"""
        return {
            "TRC20": ConsolidationRule(
                network="TRC20",
                min_consolidation_amount=Decimal("10.0"),      # 最小10 USDT才归集
                consolidation_threshold=Decimal("100.0"),      # 达到100 USDT自动归集
                max_fee_ratio=Decimal("0.05"),                 # 手续费不超过5%
                consolidation_interval=3600,                   # 每小时检查一次
                master_wallet_address=getattr(settings, "master_wallet_trc20", "")
            ),
            "ERC20": ConsolidationRule(
                network="ERC20", 
                min_consolidation_amount=Decimal("50.0"),      # ETH网络手续费高，最小50 USDT
                consolidation_threshold=Decimal("500.0"),      # 达到500 USDT才归集
                max_fee_ratio=Decimal("0.10"),                 # 手续费可以到10%
                consolidation_interval=7200,                   # 每2小时检查一次
                master_wallet_address=getattr(settings, "master_wallet_erc20", "")
            ),
            "BEP20": ConsolidationRule(
                network="BEP20",
                min_consolidation_amount=Decimal("20.0"),      # BSC网络手续费中等
                consolidation_threshold=Decimal("200.0"),      # 达到200 USDT归集
                max_fee_ratio=Decimal("0.02"),                 # 手续费不超过2%
                consolidation_interval=1800,                   # 每30分钟检查一次
                master_wallet_address=getattr(settings, "master_wallet_bep20", "")
            )
        }
    
    async def scan_for_consolidation_opportunities(self) -> List[ConsolidationTask]:
        """扫描需要归集的钱包"""
        consolidation_tasks = []
        
        async with AsyncSessionLocal() as session:
            for network, rule in self.consolidation_rules.items():
                # 获取有资金的钱包 (排除主钱包)
                query = select(USDTWallet).where(
                    and_(
                        USDTWallet.network == network,
                        USDTWallet.balance > rule.min_consolidation_amount,
                        USDTWallet.status == "available",
                        USDTWallet.address != rule.master_wallet_address
                    )
                ).order_by(desc(USDTWallet.balance))
                
                result = await session.execute(query)
                wallets = result.scalars().all()
                
                logger.info(f"Found {len(wallets)} wallets with funds on {network}")
                
                for wallet in wallets:
                    # 检查是否需要归集
                    if await self._should_consolidate_wallet(wallet, rule):
                        task = await self._create_consolidation_task(wallet, rule)
                        if task:
                            consolidation_tasks.append(task)
        
        # 按优先级排序
        consolidation_tasks.sort(key=lambda x: x.priority, reverse=True)
        logger.info(f"Created {len(consolidation_tasks)} consolidation tasks")
        
        return consolidation_tasks
    
    async def _should_consolidate_wallet(self, wallet: USDTWallet, rule: ConsolidationRule) -> bool:
        """判断钱包是否需要归集"""
        # 1. 检查余额阈值
        if wallet.balance < rule.consolidation_threshold:
            return False
        
        # 2. 检查最近是否有归集
        last_consolidation = await self._get_last_consolidation_time(wallet.id)
        if last_consolidation:
            time_since_last = datetime.utcnow() - last_consolidation
            if time_since_last.total_seconds() < rule.consolidation_interval:
                return False
        
        # 3. 检查钱包是否正在使用中
        if wallet.current_order_id:
            return False
        
        # 4. 估算手续费
        estimated_fee = await self._estimate_consolidation_fee(wallet.network, wallet.balance)
        fee_ratio = estimated_fee / wallet.balance if wallet.balance > 0 else Decimal("1")
        
        if fee_ratio > rule.max_fee_ratio:
            logger.warning(f"Fee ratio too high for wallet {wallet.address}: {DataValidator.safe_format_percentage(fee_ratio * 100, decimals=2)}")
            return False
        
        return True
    
    async def _create_consolidation_task(self, wallet: USDTWallet, rule: ConsolidationRule) -> Optional[ConsolidationTask]:
        """创建归集任务"""
        try:
            # 获取主钱包
            master_wallet = await self._get_master_wallet(rule.network)
            if not master_wallet:
                logger.error(f"Master wallet not found for network {rule.network}")
                return None
            
            # 估算手续费
            estimated_fee = await self._estimate_consolidation_fee(rule.network, wallet.balance)
            
            # 计算实际归集金额 (扣除手续费)
            consolidation_amount = wallet.balance - estimated_fee
            
            if consolidation_amount <= 0:
                logger.warning(f"Consolidation amount too low for wallet {wallet.address}")
                return None
            
            # 计算优先级
            priority = self._calculate_priority(wallet.balance, estimated_fee, rule)
            
            task = ConsolidationTask(
                task_id=f"CONS_{wallet.network}_{wallet.id}_{int(datetime.utcnow().timestamp())}",
                source_wallet_id=wallet.id,
                target_wallet_id=master_wallet.id,
                network=wallet.network,
                amount=consolidation_amount,
                estimated_fee=estimated_fee,
                priority=priority,
                created_at=datetime.utcnow()
            )
            
            return task
            
        except Exception as e:
            logger.error(f"Failed to create consolidation task for wallet {wallet.id}: {e}")
            return None
    
    async def execute_consolidation_task(self, task: ConsolidationTask) -> bool:
        """执行归集任务"""
        try:
            logger.info(f"Executing consolidation task {task.task_id}")
            
            async with self.consolidation_lock:
                # 1. 重新检查源钱包状态
                source_wallet = await self._get_wallet_by_id(task.source_wallet_id)
                if not source_wallet or source_wallet.status != "available":
                    logger.warning(f"Source wallet {task.source_wallet_id} not available")
                    return False
                
                # 2. 标记钱包为归集中
                await self._mark_wallet_consolidating(task.source_wallet_id)
                
                try:
                    # 3. 执行区块链转账
                    tx_hash = await self._execute_blockchain_transfer(task)
                    
                    if tx_hash:
                        # 4. 记录归集交易
                        await self._record_consolidation_transaction(task, tx_hash)
                        
                        # 5. 更新钱包余额
                        await self._update_wallet_after_consolidation(task, tx_hash)
                        
                        logger.info(f"Consolidation task {task.task_id} completed successfully, tx: {tx_hash}")
                        return True
                    else:
                        logger.error(f"Blockchain transfer failed for task {task.task_id}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error executing consolidation task {task.task_id}: {e}")
                    return False
                finally:
                    # 释放钱包锁定
                    await self._release_wallet_lock(task.source_wallet_id)
                    
        except Exception as e:
            logger.error(f"Failed to execute consolidation task {task.task_id}: {e}")
            return False
    
    async def _execute_blockchain_transfer(self, task: ConsolidationTask) -> Optional[str]:
        """执行区块链转账"""
        try:
            # 获取源钱包和目标钱包
            async with AsyncSessionLocal() as session:
                source_wallet = await session.get(USDTWallet, task.source_wallet_id)
                target_wallet = await session.get(USDTWallet, task.target_wallet_id)
                
                if not source_wallet or not target_wallet:
                    return None
                
                # 解密私钥
                decrypted_private_key = self.wallet_service._decrypt_private_key(source_wallet.private_key)
                
                # 临时模拟区块链交易
                tx_hash = f"mock_tx_{task.task_id}_{int(datetime.utcnow().timestamp())}"
                logger.info(f"模拟区块链交易: {task.network} {source_wallet.address} -> {target_wallet.address} 金额: {task.amount} USDT")
                
                # TODO: 集成真实的区块链服务
                # tx_hash = await self.blockchain_service.send_usdt(
                #     network=task.network,
                #     private_key=decrypted_private_key,
                #     to_address=target_wallet.address,
                #     amount=task.amount
                # )
                
                return tx_hash
                
        except Exception as e:
            logger.error(f"Blockchain transfer error: {e}")
            return None
    
    async def get_consolidation_statistics(self) -> Dict[str, Any]:
        """获取归集统计信息"""
        async with AsyncSessionLocal() as session:
            stats = {
                "total_wallets_with_funds": 0,
                "total_consolidatable_amount": Decimal("0"),
                "pending_consolidation_tasks": 0,
                "completed_consolidations_today": 0,
                "total_fees_saved": Decimal("0"),
                "network_breakdown": {}
            }
            
            for network, rule in self.consolidation_rules.items():
                # 统计有资金的钱包
                query = select(func.count(USDTWallet.id), func.sum(USDTWallet.balance)).where(
                    and_(
                        USDTWallet.network == network,
                        USDTWallet.balance > rule.min_consolidation_amount,
                        USDTWallet.address != rule.master_wallet_address
                    )
                )
                result = await session.execute(query)
                count, total_balance = result.first()
                
                stats["network_breakdown"][network] = {
                    "wallets_count": count or 0,
                    "total_balance": float(total_balance or 0),
                    "consolidation_threshold": float(rule.consolidation_threshold),
                    "master_wallet": rule.master_wallet_address
                }
                
                stats["total_wallets_with_funds"] += count or 0
                stats["total_consolidatable_amount"] += total_balance or Decimal("0")
            
            return stats
    
    # 辅助方法
    async def _get_master_wallet(self, network: str) -> Optional[USDTWallet]:
        """获取指定网络的主钱包"""
        async with AsyncSessionLocal() as session:
            rule = self.consolidation_rules.get(network)
            if not rule or not rule.master_wallet_address:
                return None
                
            query = select(USDTWallet).where(
                and_(
                    USDTWallet.network == network,
                    USDTWallet.address == rule.master_wallet_address
                )
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def _estimate_consolidation_fee(self, network: str, amount: Decimal) -> Decimal:
        """估算归集手续费"""
        # 缓存手续费估算结果
        cache_key = f"{network}_{int(datetime.utcnow().timestamp() // 300)}"  # 5分钟缓存
        
        if cache_key in self.fee_estimation_cache:
            base_fee = self.fee_estimation_cache[cache_key]
        else:
            # 根据网络获取当前手续费
            if network == "TRC20":
                base_fee = Decimal("1.0")  # TRC20 固定手续费
            elif network == "ERC20":
                base_fee = await self._get_eth_gas_fee()
            elif network == "BEP20":
                base_fee = Decimal("0.5")  # BSC 相对较低的手续费
            else:
                base_fee = Decimal("2.0")  # 默认手续费
            
            self.fee_estimation_cache[cache_key] = base_fee
        
        return base_fee
    
    async def _get_eth_gas_fee(self) -> Decimal:
        """获取以太坊当前Gas费用"""
        # 这里应该调用真实的Gas费用API
        # 暂时返回估算值
        return Decimal("10.0")
    
    def _calculate_priority(self, balance: Decimal, fee: Decimal, rule: ConsolidationRule) -> int:
        """计算归集优先级"""
        # 金额越大，优先级越高
        amount_priority = min(5, int(balance / rule.consolidation_threshold))
        
        # 手续费比例越低，优先级越高
        fee_ratio = fee / balance if balance > 0 else Decimal("1")
        fee_priority = 5 if fee_ratio < Decimal("0.01") else (3 if fee_ratio < Decimal("0.05") else 1)
        
        return min(5, max(1, (amount_priority + fee_priority) // 2))
    
    async def _get_last_consolidation_time(self, wallet_id: int) -> Optional[datetime]:
        """获取钱包最后归集时间"""
        # 这里应该查询归集历史记录表
        # 暂时返回None
        return None
    
    async def _get_wallet_by_id(self, wallet_id: int) -> Optional[USDTWallet]:
        """根据ID获取钱包"""
        async with AsyncSessionLocal() as session:
            return await session.get(USDTWallet, wallet_id)
    
    async def _mark_wallet_consolidating(self, wallet_id: int):
        """标记钱包为归集中状态"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(status="consolidating", updated_at=datetime.utcnow())
            )
            await session.commit()
    
    async def _release_wallet_lock(self, wallet_id: int):
        """释放钱包锁定状态"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(status="available", updated_at=datetime.utcnow())
            )
            await session.commit()
    
    async def _record_consolidation_transaction(self, task: ConsolidationTask, tx_hash: str):
        """记录归集交易"""
        # 这里应该在区块链交易表中记录归集交易
        logger.info(f"Recording consolidation transaction: {tx_hash} for task {task.task_id}")
    
    async def _update_wallet_after_consolidation(self, task: ConsolidationTask, tx_hash: str):
        """归集后更新钱包余额"""
        async with AsyncSessionLocal() as session:
            # 更新源钱包余额
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == task.source_wallet_id)
                .values(
                    balance=0,  # 归集后余额为0
                    total_sent=USDTWallet.total_sent + task.amount,
                    transaction_count=USDTWallet.transaction_count + 1,
                    updated_at=datetime.utcnow()
                )
            )
            
            # 更新目标钱包余额
            await session.execute(
                update(USDTWallet)
                .where(USDTWallet.id == task.target_wallet_id)
                .values(
                    balance=USDTWallet.balance + task.amount,
                    total_received=USDTWallet.total_received + task.amount,
                    transaction_count=USDTWallet.transaction_count + 1,
                    updated_at=datetime.utcnow()
                )
            )
            
            await session.commit()


# 创建全局实例
fund_consolidation_service = FundConsolidationService()