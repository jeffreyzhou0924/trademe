"""
智能钱包分配算法 - 企业级钱包选择优化系统
"""

import asyncio
import logging
from typing import List, Optional, Dict, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc

from app.models.payment import USDTWallet, USDTPaymentOrder, WalletBalance
from app.services.wallet_pool_service import WalletInfo
from app.core.exceptions import WalletError

logger = logging.getLogger(__name__)


class AllocationStrategy(Enum):
    """分配策略枚举"""
    BALANCED = "balanced"              # 均衡分配（默认）
    RISK_MINIMIZED = "risk_minimized"  # 风险最小化
    PERFORMANCE_OPTIMIZED = "performance_optimized"  # 性能优化
    COST_OPTIMIZED = "cost_optimized"  # 成本优化
    HIGH_AVAILABILITY = "high_availability"  # 高可用性


@dataclass
class WalletScore:
    """钱包评分"""
    wallet_id: int
    address: str
    network: str
    total_score: float
    risk_score: float        # 风险评分 (0-1, 越低越好)
    performance_score: float # 性能评分 (0-1, 越高越好)  
    availability_score: float # 可用性评分 (0-1, 越高越好)
    load_score: float       # 负载评分 (0-1, 越低越好)
    cost_score: float       # 成本评分 (0-1, 越低越好)


@dataclass
class AllocationRequest:
    """分配请求"""
    order_id: str
    network: str
    amount: Decimal
    priority: int = 5           # 优先级 (1-10, 10最高)
    risk_tolerance: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    strategy: AllocationStrategy = AllocationStrategy.BALANCED
    max_wait_time: int = 30     # 最大等待时间(秒)
    preferred_wallets: List[int] = None  # 优选钱包ID列表
    blacklist_wallets: List[int] = None  # 黑名单钱包ID列表


class SmartWalletAllocator:
    """智能钱包分配器 - 企业级多策略分配算法"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # 评分权重配置
        self.score_weights = {
            AllocationStrategy.BALANCED: {
                "risk": 0.25,
                "performance": 0.25,
                "availability": 0.25,
                "load": 0.15,
                "cost": 0.10
            },
            AllocationStrategy.RISK_MINIMIZED: {
                "risk": 0.50,
                "performance": 0.20,
                "availability": 0.20,
                "load": 0.05,
                "cost": 0.05
            },
            AllocationStrategy.PERFORMANCE_OPTIMIZED: {
                "risk": 0.10,
                "performance": 0.40,
                "availability": 0.30,
                "load": 0.15,
                "cost": 0.05
            },
            AllocationStrategy.COST_OPTIMIZED: {
                "risk": 0.15,
                "performance": 0.15,
                "availability": 0.15,
                "load": 0.20,
                "cost": 0.35
            },
            AllocationStrategy.HIGH_AVAILABILITY: {
                "risk": 0.20,
                "performance": 0.15,
                "availability": 0.45,
                "load": 0.15,
                "cost": 0.05
            }
        }

    async def allocate_optimal_wallet(
        self, 
        request: AllocationRequest
    ) -> Optional[WalletInfo]:
        """
        智能分配最优钱包
        
        Args:
            request: 分配请求对象
            
        Returns:
            分配的钱包信息或None
        """
        try:
            logger.info(f"开始智能钱包分配: 订单={request.order_id}, 网络={request.network}, 策略={request.strategy.value}")
            
            # 1. 获取候选钱包列表
            candidates = await self._get_candidate_wallets(request)
            if not candidates:
                logger.warning(f"没有可用的 {request.network} 钱包")
                return None
            
            # 2. 计算钱包评分
            wallet_scores = await self._calculate_wallet_scores(candidates, request)
            
            # 3. 根据策略选择最优钱包
            best_wallet = await self._select_best_wallet(wallet_scores, request)
            if not best_wallet:
                logger.warning("未找到符合条件的最优钱包")
                return None
            
            # 4. 执行原子性分配
            allocated_wallet = await self._atomic_allocate(best_wallet, request)
            
            if allocated_wallet:
                logger.info(f"智能分配成功: 钱包={allocated_wallet.address}, 评分={best_wallet.total_score:.3f}")
                
                # 记录分配决策日志
                await self._log_allocation_decision(best_wallet, request)
            
            return allocated_wallet
            
        except Exception as e:
            logger.error(f"智能钱包分配失败: {e}")
            await self.db.rollback()
            raise WalletError(f"智能分配失败: {str(e)}")

    async def _get_candidate_wallets(
        self, 
        request: AllocationRequest
    ) -> List[USDTWallet]:
        """获取候选钱包列表"""
        
        # 基础筛选条件
        conditions = [
            USDTWallet.network == request.network,
            USDTWallet.status == "available"
        ]
        
        # 应用黑名单
        if request.blacklist_wallets:
            conditions.append(~USDTWallet.id.in_(request.blacklist_wallets))
        
        # 风险等级筛选
        risk_mapping = {
            "LOW": ["LOW"],
            "MEDIUM": ["LOW", "MEDIUM"], 
            "HIGH": ["LOW", "MEDIUM", "HIGH"]
        }
        allowed_risks = risk_mapping.get(request.risk_tolerance, ["LOW", "MEDIUM"])
        conditions.append(USDTWallet.risk_level.in_(allowed_risks))
        
        # 执行查询
        query = select(USDTWallet).where(and_(*conditions))
        
        # 优选钱包优先
        if request.preferred_wallets:
            query = query.order_by(
                USDTWallet.id.in_(request.preferred_wallets).desc(),
                USDTWallet.transaction_count.asc()
            )
        else:
            query = query.order_by(USDTWallet.transaction_count.asc())
        
        # 限制候选数量提升性能
        query = query.limit(50)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _calculate_wallet_scores(
        self, 
        wallets: List[USDTWallet], 
        request: AllocationRequest
    ) -> List[WalletScore]:
        """计算钱包评分"""
        
        scores = []
        
        for wallet in wallets:
            # 1. 风险评分 (0-1, 越低越好)
            risk_score = await self._calculate_risk_score(wallet)
            
            # 2. 性能评分 (0-1, 越高越好)
            performance_score = await self._calculate_performance_score(wallet)
            
            # 3. 可用性评分 (0-1, 越高越好)
            availability_score = await self._calculate_availability_score(wallet)
            
            # 4. 负载评分 (0-1, 越低越好)
            load_score = await self._calculate_load_score(wallet)
            
            # 5. 成本评分 (0-1, 越低越好)
            cost_score = await self._calculate_cost_score(wallet)
            
            # 6. 计算加权总分
            weights = self.score_weights[request.strategy]
            total_score = (
                (1 - risk_score) * weights["risk"] +          # 风险越低越好
                performance_score * weights["performance"] +   # 性能越高越好
                availability_score * weights["availability"] + # 可用性越高越好
                (1 - load_score) * weights["load"] +          # 负载越低越好
                (1 - cost_score) * weights["cost"]            # 成本越低越好
            )
            
            score = WalletScore(
                wallet_id=wallet.id,
                address=wallet.address,
                network=wallet.network,
                total_score=total_score,
                risk_score=risk_score,
                performance_score=performance_score,
                availability_score=availability_score,
                load_score=load_score,
                cost_score=cost_score
            )
            
            scores.append(score)
        
        # 按总分降序排序
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        return scores

    async def _calculate_risk_score(self, wallet: USDTWallet) -> float:
        """计算风险评分"""
        
        # 基础风险等级
        risk_base = {
            "LOW": 0.1,
            "MEDIUM": 0.3,
            "HIGH": 0.6
        }.get(wallet.risk_level, 0.3)
        
        # 历史失败率影响 (最近30天)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # 查询最近失败订单数
        failed_orders_query = select(func.count(USDTPaymentOrder.id)).where(
            and_(
                USDTPaymentOrder.wallet_id == wallet.id,
                USDTPaymentOrder.status.in_(["failed", "expired"]),
                USDTPaymentOrder.created_at >= thirty_days_ago
            )
        )
        
        result = await self.db.execute(failed_orders_query)
        failed_count = result.scalar() or 0
        
        # 总订单数
        total_orders_query = select(func.count(USDTPaymentOrder.id)).where(
            and_(
                USDTPaymentOrder.wallet_id == wallet.id,
                USDTPaymentOrder.created_at >= thirty_days_ago
            )
        )
        
        result = await self.db.execute(total_orders_query)
        total_count = result.scalar() or 0
        
        # 计算失败率调整
        failure_rate = failed_count / max(total_count, 1)
        risk_adjustment = failure_rate * 0.3  # 最多增加0.3的风险
        
        return min(1.0, risk_base + risk_adjustment)

    async def _calculate_performance_score(self, wallet: USDTWallet) -> float:
        """计算性能评分"""
        
        # 基础性能分数
        base_score = 0.5
        
        # 交易成功率加成
        if wallet.transaction_count > 0:
            # 这里简化处理，实际应该查询成功交易比率
            success_rate = max(0, 1 - (wallet.transaction_count * 0.01))  # 交易次数越多，假设成功率略降
            base_score += success_rate * 0.3
        
        # 最后同步时间影响 (越新越好)
        if wallet.last_sync_at:
            hours_since_sync = (datetime.utcnow() - wallet.last_sync_at).total_seconds() / 3600
            sync_factor = max(0, 1 - (hours_since_sync / 24))  # 24小时内同步得满分
            base_score += sync_factor * 0.2
        
        return min(1.0, base_score)

    async def _calculate_availability_score(self, wallet: USDTWallet) -> float:
        """计算可用性评分"""
        
        # 基础可用性分数（状态为available就是满分）
        base_score = 1.0 if wallet.status == "available" else 0.0
        
        # 最近被分配的频率影响 (避免热点钱包)
        if wallet.allocated_at:
            hours_since_allocated = (datetime.utcnow() - wallet.allocated_at).total_seconds() / 3600
            cooldown_factor = min(1.0, hours_since_allocated / 6)  # 6小时冷却期
            base_score *= cooldown_factor
        
        return base_score

    async def _calculate_load_score(self, wallet: USDTWallet) -> float:
        """计算负载评分"""
        
        # 当前日收款量与限额比率
        if wallet.daily_limit and wallet.daily_limit > 0:
            daily_usage_rate = float(wallet.current_daily_received) / float(wallet.daily_limit)
        else:
            daily_usage_rate = 0
        
        # 月度收款量与限额比率
        if wallet.monthly_limit and wallet.monthly_limit > 0:
            monthly_usage_rate = float(wallet.current_monthly_received) / float(wallet.monthly_limit)
        else:
            monthly_usage_rate = 0
        
        # 综合负载评分
        load_score = max(daily_usage_rate, monthly_usage_rate)
        
        return min(1.0, load_score)

    async def _calculate_cost_score(self, wallet: USDTWallet) -> float:
        """计算成本评分"""
        
        # 网络成本基准
        network_cost = {
            "TRC20": 0.1,  # TRON网络费用较低
            "BEP20": 0.3,  # BSC网络费用中等
            "ERC20": 0.8   # Ethereum网络费用较高
        }.get(wallet.network, 0.5)
        
        # 历史交易费用（如果有记录）
        # 这里简化处理，实际应该查询历史平均手续费
        
        return network_cost

    async def _select_best_wallet(
        self, 
        wallet_scores: List[WalletScore], 
        request: AllocationRequest
    ) -> Optional[WalletScore]:
        """选择最佳钱包"""
        
        if not wallet_scores:
            return None
        
        # 优选钱包策略
        if request.preferred_wallets:
            for score in wallet_scores:
                if score.wallet_id in request.preferred_wallets:
                    logger.info(f"选择优选钱包: {score.address}")
                    return score
        
        # 选择评分最高的钱包
        best_score = wallet_scores[0]
        
        logger.info(f"选择最优钱包: 地址={best_score.address}, 评分={best_score.total_score:.3f}")
        logger.debug(f"评分详情: 风险={best_score.risk_score:.3f}, 性能={best_score.performance_score:.3f}, 可用性={best_score.availability_score:.3f}")
        
        return best_score

    async def _atomic_allocate(
        self, 
        wallet_score: WalletScore, 
        request: AllocationRequest
    ) -> Optional[WalletInfo]:
        """原子性分配钱包"""
        
        from sqlalchemy import update
        
        # 原子性更新钱包状态
        update_result = await self.db.execute(
            update(USDTWallet)
            .where(
                and_(
                    USDTWallet.id == wallet_score.wallet_id,
                    USDTWallet.status == "available"
                )
            )
            .values(
                status="occupied",
                current_order_id=request.order_id,
                allocated_at=func.now(),
                updated_at=func.now()
            )
        )
        
        if update_result.rowcount == 0:
            logger.warning(f"钱包 {wallet_score.wallet_id} 已被其他进程分配")
            return None
        
        await self.db.commit()
        
        # 返回钱包信息
        return WalletInfo(
            id=wallet_score.wallet_id,
            name=f"Smart_Wallet_{wallet_score.wallet_id}",
            network=wallet_score.network,
            address=wallet_score.address,
            balance=Decimal('0'),  # 实际应该查询余额
            status="occupied",
            created_at=datetime.utcnow()
        )

    async def _log_allocation_decision(
        self, 
        wallet_score: WalletScore, 
        request: AllocationRequest
    ):
        """记录分配决策日志"""
        
        decision_log = {
            "order_id": request.order_id,
            "selected_wallet": wallet_score.wallet_id,
            "strategy": request.strategy.value,
            "total_score": wallet_score.total_score,
            "score_breakdown": {
                "risk": wallet_score.risk_score,
                "performance": wallet_score.performance_score,
                "availability": wallet_score.availability_score,
                "load": wallet_score.load_score,
                "cost": wallet_score.cost_score
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"分配决策日志: {decision_log}")

    async def get_allocation_statistics(self, network: str = None) -> Dict[str, Any]:
        """获取分配统计信息"""
        
        stats = {}
        
        # 基础查询条件
        conditions = []
        if network:
            conditions.append(USDTWallet.network == network)
        
        base_query = select(USDTWallet)
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        # 按状态统计
        status_query = select(
            USDTWallet.status,
            func.count().label('count')
        ).group_by(USDTWallet.status)
        
        if conditions:
            status_query = status_query.where(and_(*conditions))
        
        result = await self.db.execute(status_query)
        status_stats = {row.status: row.count for row in result}
        
        # 按风险等级统计
        risk_query = select(
            USDTWallet.risk_level,
            func.count().label('count')
        ).group_by(USDTWallet.risk_level)
        
        if conditions:
            risk_query = risk_query.where(and_(*conditions))
        
        result = await self.db.execute(risk_query)
        risk_stats = {row.risk_level: row.count for row in result}
        
        # 计算利用率
        available_count = status_stats.get('available', 0)
        occupied_count = status_stats.get('occupied', 0)
        total_count = available_count + occupied_count + status_stats.get('maintenance', 0)
        
        utilization_rate = (occupied_count / max(total_count, 1)) * 100
        
        return {
            "status_distribution": status_stats,
            "risk_distribution": risk_stats,
            "utilization_rate": utilization_rate,
            "total_wallets": total_count,
            "available_wallets": available_count,
            "occupied_wallets": occupied_count
        }