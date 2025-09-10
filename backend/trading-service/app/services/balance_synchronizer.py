"""
余额同步器 - 实时同步区块链钱包余额
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.config import settings
from app.models.payment import USDTWallet, WalletBalance, BlockchainTransaction
from app.services.blockchain_monitor_service import blockchain_monitor_service
from app.services.usdt_wallet_service import usdt_wallet_service
from app.utils.data_validation import DataValidator
import logging

logger = logging.getLogger(__name__)


@dataclass
class BalanceSyncTask:
    """余额同步任务"""
    wallet_id: int
    network: str
    address: str
    last_sync_at: Optional[datetime] = None
    sync_interval: int = 300  # 默认5分钟同步一次
    priority: int = 1  # 1-低, 2-中, 3-高
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class BalanceSyncResult:
    """余额同步结果"""
    wallet_id: int
    address: str
    network: str
    blockchain_balance: Decimal
    db_balance: Decimal
    difference: Decimal
    sync_success: bool
    sync_time: datetime
    error_message: Optional[str] = None


class BalanceSynchronizer:
    """余额同步器 - 实时同步区块链余额到数据库"""
    
    def __init__(self):
        self.sync_tasks: Dict[int, BalanceSyncTask] = {}
        self.is_running = False
        self.sync_interval = settings.blockchain_monitor_interval  # 从配置获取间隔
        self.max_concurrent_syncs = 5  # 最大并发同步数量
        self.tolerance = Decimal('0.000001')  # 余额差异容忍度 (1微USDT)
        
        # 同步统计
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0
        self.last_sync_time = None
        
        logger.info("余额同步器初始化完成")
    
    async def start_synchronizer(self):
        """启动余额同步器"""
        if self.is_running:
            logger.warning("余额同步器已在运行中")
            return
        
        self.is_running = True
        logger.info("启动余额同步器")
        
        # 加载现有钱包的同步任务
        await self._load_sync_tasks()
        
        # 启动同步循环
        asyncio.create_task(self._sync_loop())
    
    async def stop_synchronizer(self):
        """停止余额同步器"""
        self.is_running = False
        logger.info("余额同步器已停止")
    
    async def add_wallet_sync(
        self, 
        wallet_id: int, 
        network: str, 
        address: str,
        priority: int = 1,
        sync_interval: int = None
    ):
        """添加钱包余额同步任务"""
        if wallet_id in self.sync_tasks:
            logger.warning(f"钱包 {wallet_id} 已在同步列表中")
            return
        
        task = BalanceSyncTask(
            wallet_id=wallet_id,
            network=network,
            address=address,
            priority=priority,
            sync_interval=sync_interval or self.sync_interval
        )
        
        self.sync_tasks[wallet_id] = task
        logger.info(f"添加钱包同步任务: {address} ({network})")
    
    async def remove_wallet_sync(self, wallet_id: int):
        """移除钱包余额同步任务"""
        if wallet_id in self.sync_tasks:
            del self.sync_tasks[wallet_id]
            logger.info(f"移除钱包同步任务: {wallet_id}")
    
    async def sync_wallet_balance(self, wallet_id: int, force: bool = False) -> BalanceSyncResult:
        """同步单个钱包余额"""
        if wallet_id not in self.sync_tasks:
            raise ValueError(f"钱包 {wallet_id} 不在同步任务列表中")
        
        task = self.sync_tasks[wallet_id]
        
        try:
            # 检查是否需要同步
            if not force and not self._should_sync(task):
                return BalanceSyncResult(
                    wallet_id=wallet_id,
                    address=task.address,
                    network=task.network,
                    blockchain_balance=Decimal('0'),
                    db_balance=Decimal('0'),
                    difference=Decimal('0'),
                    sync_success=True,
                    sync_time=datetime.utcnow(),
                    error_message="跳过同步 - 未达到同步间隔"
                )
            
            # 更新任务状态
            task.status = "running"
            
            # 从区块链获取余额
            blockchain_balance = await blockchain_monitor_service.get_address_balance(
                task.address, 
                task.network
            )
            
            # 从数据库获取当前余额
            async with AsyncSessionLocal() as session:
                wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
                result = await session.execute(wallet_query)
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    raise ValueError(f"钱包 {wallet_id} 不存在")
                
                db_balance = wallet.balance
            
            # 计算差异
            difference = blockchain_balance - db_balance
            
            # 记录同步结果
            sync_result = BalanceSyncResult(
                wallet_id=wallet_id,
                address=task.address,
                network=task.network,
                blockchain_balance=blockchain_balance,
                db_balance=db_balance,
                difference=difference,
                sync_success=True,
                sync_time=datetime.utcnow()
            )
            
            # 如果差异超过容忍度，更新数据库余额
            if abs(difference) > self.tolerance:
                await self._update_wallet_balance(
                    wallet_id, 
                    blockchain_balance, 
                    difference,
                    f"余额同步 - 区块链:{blockchain_balance}, 数据库:{db_balance}"
                )
                logger.info(f"钱包 {wallet_id} 余额已同步: {DataValidator.safe_format_decimal(db_balance, decimals=6)} -> {DataValidator.safe_format_decimal(blockchain_balance, decimals=6)}")
            
            # 更新任务状态
            task.status = "completed"
            task.last_sync_at = datetime.utcnow()
            
            # 更新统计
            self.total_syncs += 1
            self.successful_syncs += 1
            self.last_sync_time = datetime.utcnow()
            
            return sync_result
            
        except Exception as e:
            # 更新任务状态
            task.status = "failed"
            
            # 记录失败结果
            sync_result = BalanceSyncResult(
                wallet_id=wallet_id,
                address=task.address,
                network=task.network,
                blockchain_balance=Decimal('0'),
                db_balance=Decimal('0'),
                difference=Decimal('0'),
                sync_success=False,
                sync_time=datetime.utcnow(),
                error_message=str(e)
            )
            
            # 更新统计
            self.total_syncs += 1
            self.failed_syncs += 1
            
            logger.error(f"钱包 {wallet_id} 余额同步失败: {e}")
            return sync_result
    
    async def sync_all_wallets(self, force: bool = False) -> List[BalanceSyncResult]:
        """同步所有钱包余额"""
        results = []
        
        # 按优先级排序任务
        sorted_tasks = sorted(
            self.sync_tasks.items(), 
            key=lambda x: (-x[1].priority, x[0])
        )
        
        # 限制并发数量
        semaphore = asyncio.Semaphore(self.max_concurrent_syncs)
        
        async def sync_with_semaphore(wallet_id: int):
            async with semaphore:
                return await self.sync_wallet_balance(wallet_id, force)
        
        # 并发执行同步任务
        tasks = [
            sync_with_semaphore(wallet_id) 
            for wallet_id, _ in sorted_tasks
        ]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常结果
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    wallet_id = sorted_tasks[i][0]
                    task = sorted_tasks[i][1]
                    processed_results.append(
                        BalanceSyncResult(
                            wallet_id=wallet_id,
                            address=task.address,
                            network=task.network,
                            blockchain_balance=Decimal('0'),
                            db_balance=Decimal('0'),
                            difference=Decimal('0'),
                            sync_success=False,
                            sync_time=datetime.utcnow(),
                            error_message=str(result)
                        )
                    )
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"批量余额同步失败: {e}")
            return []
    
    async def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        success_rate = 0
        if self.total_syncs > 0:
            success_rate = (self.successful_syncs / self.total_syncs) * 100
        
        return {
            "total_tasks": len(self.sync_tasks),
            "active_tasks": len([t for t in self.sync_tasks.values() if t.status == "running"]),
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
            "success_rate": DataValidator.safe_format_percentage(success_rate, decimals=2),
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "is_running": self.is_running
        }
    
    async def get_wallet_sync_status(self, wallet_id: int) -> Optional[Dict[str, Any]]:
        """获取钱包同步状态"""
        if wallet_id not in self.sync_tasks:
            return None
        
        task = self.sync_tasks[wallet_id]
        return {
            "wallet_id": task.wallet_id,
            "network": task.network,
            "address": task.address,
            "status": task.status,
            "priority": task.priority,
            "sync_interval": task.sync_interval,
            "last_sync_at": task.last_sync_at.isoformat() if task.last_sync_at else None,
            "next_sync_at": (
                task.last_sync_at + timedelta(seconds=task.sync_interval)
            ).isoformat() if task.last_sync_at else None
        }
    
    async def force_sync_wallet(self, wallet_id: int) -> BalanceSyncResult:
        """强制同步指定钱包"""
        return await self.sync_wallet_balance(wallet_id, force=True)
    
    async def _load_sync_tasks(self):
        """从数据库加载同步任务"""
        try:
            async with AsyncSessionLocal() as session:
                # 查询所有活跃钱包
                wallet_query = select(USDTWallet).where(
                    USDTWallet.status.in_(['available', 'occupied'])
                )
                result = await session.execute(wallet_query)
                wallets = result.scalars().all()
                
                for wallet in wallets:
                    await self.add_wallet_sync(
                        wallet.id,
                        wallet.network,
                        wallet.address,
                        priority=2 if wallet.status == 'occupied' else 1
                    )
                
                logger.info(f"已加载 {len(wallets)} 个钱包同步任务")
                
        except Exception as e:
            logger.error(f"加载同步任务失败: {e}")
    
    async def _sync_loop(self):
        """同步主循环"""
        while self.is_running:
            try:
                logger.debug("执行批量余额同步")
                results = await self.sync_all_wallets()
                
                # 记录同步结果
                synced_count = len([r for r in results if r.sync_success])
                failed_count = len([r for r in results if not r.sync_success])
                
                if synced_count > 0 or failed_count > 0:
                    logger.info(f"余额同步完成 - 成功: {synced_count}, 失败: {failed_count}")
                
                # 等待下一个同步周期
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"同步循环错误: {e}")
                await asyncio.sleep(self.sync_interval)
    
    def _should_sync(self, task: BalanceSyncTask) -> bool:
        """判断是否需要同步"""
        if not task.last_sync_at:
            return True
        
        elapsed = (datetime.utcnow() - task.last_sync_at).total_seconds()
        return elapsed >= task.sync_interval
    
    async def _update_wallet_balance(
        self, 
        wallet_id: int, 
        new_balance: Decimal, 
        difference: Decimal,
        reason: str
    ):
        """更新钱包余额"""
        try:
            # 使用钱包服务更新余额
            await usdt_wallet_service.update_wallet_balance(
                wallet_id=wallet_id,
                new_balance=new_balance,
                sync_source=reason
            )
            
            # 记录余额变更历史
            async with AsyncSessionLocal() as session:
                balance_record = WalletBalance(
                    wallet_id=wallet_id,
                    balance=new_balance,
                    balance_change=difference,
                    change_reason=reason,
                    sync_source="balance_synchronizer",
                    created_at=datetime.utcnow()
                )
                
                session.add(balance_record)
                await session.commit()
                
        except Exception as e:
            logger.error(f"更新钱包 {wallet_id} 余额失败: {e}")
            raise


# 全局余额同步器实例
balance_synchronizer = BalanceSynchronizer()


# 便捷函数
async def start_balance_sync():
    """启动余额同步服务"""
    await balance_synchronizer.start_synchronizer()


async def stop_balance_sync():
    """停止余额同步服务"""
    await balance_synchronizer.stop_synchronizer()


async def sync_wallet_balance_now(wallet_id: int) -> BalanceSyncResult:
    """立即同步钱包余额"""
    return await balance_synchronizer.force_sync_wallet(wallet_id)


async def get_balance_sync_stats() -> Dict[str, Any]:
    """获取余额同步统计"""
    return await balance_synchronizer.get_sync_statistics()


if __name__ == "__main__":
    """测试代码"""
    import asyncio
    
    async def test_balance_synchronizer():
        """测试余额同步器"""
        print("=== 测试余额同步器 ===")
        
        try:
            # 创建测试实例
            sync = BalanceSynchronizer()
            
            # 添加测试钱包
            await sync.add_wallet_sync(
                wallet_id=1,
                network="TRC20",
                address="TTest1234567890123456789012345678901",
                priority=2
            )
            
            # 测试单个钱包同步
            print("\n1. 测试单钱包同步")
            result = await sync.sync_wallet_balance(1, force=True)
            print(f"同步结果: {result.sync_success}")
            print(f"区块链余额: {DataValidator.safe_format_decimal(result.blockchain_balance, decimals=6)}")
            print(f"数据库余额: {DataValidator.safe_format_decimal(result.db_balance, decimals=6)}")
            
            # 测试统计信息
            print("\n2. 测试统计信息")
            stats = await sync.get_sync_statistics()
            print(f"统计信息: {stats}")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    # 运行测试
    asyncio.run(test_balance_synchronizer())