"""
智能Claude调度器 - 高级负载均衡和成本优化
使用机器学习算法和预测模型优化Claude账号选择
"""

import asyncio
import json
import math
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, case
from sqlalchemy.orm import selectinload

from app.models.claude_proxy import ClaudeAccount, ClaudeUsageLog
from app.models.user import User


class SchedulingStrategy(str, Enum):
    """调度策略枚举"""
    ROUND_ROBIN = "round_robin"           # 轮询
    LEAST_USED = "least_used"            # 最少使用
    WEIGHTED_RESPONSE_TIME = "weighted_response_time"  # 加权响应时间
    COST_OPTIMIZED = "cost_optimized"    # 成本优化
    PREDICTIVE_LOAD = "predictive_load"  # 预测性负载均衡
    HYBRID_INTELLIGENT = "hybrid_intelligent"  # 混合智能调度


@dataclass
class AccountScore:
    """账号评分"""
    account_id: int
    total_score: float
    availability_score: float
    performance_score: float
    cost_score: float
    load_score: float
    reliability_score: float
    predicted_response_time: float
    confidence: float


@dataclass
class SchedulingContext:
    """调度上下文"""
    user_id: int
    request_type: str
    estimated_tokens: int
    priority: str = "normal"  # low, normal, high, critical
    user_tier: str = "basic"  # basic, premium, professional
    session_id: Optional[str] = None
    preferred_region: Optional[str] = None
    max_latency_ms: Optional[int] = None
    budget_limit: Optional[float] = None


class IntelligentClaudeScheduler:
    """智能Claude调度器 - 企业级负载均衡系统"""
    
    def __init__(self):
        self.scheduling_history: Dict[int, List[float]] = {}  # 账号ID -> 响应时间历史
        self.load_predictions: Dict[int, float] = {}          # 账号ID -> 预测负载
        self.cost_efficiency: Dict[int, float] = {}           # 账号ID -> 成本效率
        self.reliability_metrics: Dict[int, Dict] = {}        # 账号ID -> 可靠性指标
        
        # 算法配置
        self.config = {
            "history_window_hours": 24,
            "prediction_weight": 0.3,
            "performance_weight": 0.25,
            "cost_weight": 0.2,
            "availability_weight": 0.15,
            "reliability_weight": 0.1,
            "response_time_threshold_ms": 5000,
            "success_rate_threshold": 0.95,
            "load_balance_factor": 0.8
        }
    
    async def select_optimal_account(
        self,
        db: AsyncSession,
        available_accounts: List[ClaudeAccount],
        context: SchedulingContext,
        strategy: SchedulingStrategy = SchedulingStrategy.HYBRID_INTELLIGENT
    ) -> Optional[ClaudeAccount]:
        """
        选择最优Claude账号 - 智能调度核心算法
        
        Args:
            db: 数据库会话
            available_accounts: 可用账号列表
            context: 调度上下文
            strategy: 调度策略
            
        Returns:
            最优账号或None
        """
        if not available_accounts:
            return None
        
        # 更新账号指标
        await self._update_account_metrics(db, available_accounts)
        
        # 根据策略选择账号
        if strategy == SchedulingStrategy.ROUND_ROBIN:
            return await self._round_robin_selection(available_accounts)
        elif strategy == SchedulingStrategy.LEAST_USED:
            return await self._least_used_selection(available_accounts)
        elif strategy == SchedulingStrategy.WEIGHTED_RESPONSE_TIME:
            return await self._weighted_response_time_selection(db, available_accounts)
        elif strategy == SchedulingStrategy.COST_OPTIMIZED:
            return await self._cost_optimized_selection(db, available_accounts, context)
        elif strategy == SchedulingStrategy.PREDICTIVE_LOAD:
            return await self._predictive_load_selection(db, available_accounts, context)
        elif strategy == SchedulingStrategy.HYBRID_INTELLIGENT:
            return await self._hybrid_intelligent_selection(db, available_accounts, context)
        else:
            # 默认使用混合智能调度
            return await self._hybrid_intelligent_selection(db, available_accounts, context)
    
    async def _hybrid_intelligent_selection(
        self,
        db: AsyncSession,
        accounts: List[ClaudeAccount],
        context: SchedulingContext
    ) -> Optional[ClaudeAccount]:
        """
        混合智能选择 - 综合考虑多个因素的高级算法
        """
        scored_accounts = []
        
        for account in accounts:
            score = await self._calculate_comprehensive_score(db, account, context)
            scored_accounts.append((account, score))
        
        # 按总分排序
        scored_accounts.sort(key=lambda x: x[1].total_score, reverse=True)
        
        # 应用随机化避免总是选择同一个账号
        if len(scored_accounts) > 1:
            top_accounts = scored_accounts[:min(3, len(scored_accounts))]  # 取前3名
            weights = [acc[1].total_score for acc in top_accounts]
            
            # 使用加权随机选择
            selected_account = self._weighted_random_choice(top_accounts, weights)
            return selected_account[0]
        
        return scored_accounts[0][0] if scored_accounts else None
    
    async def _calculate_comprehensive_score(
        self,
        db: AsyncSession,
        account: ClaudeAccount,
        context: SchedulingContext
    ) -> AccountScore:
        """
        计算账号综合评分
        """
        # 1. 可用性评分 (0-1)
        availability_score = await self._calculate_availability_score(account)
        
        # 2. 性能评分 (0-1)
        performance_score = await self._calculate_performance_score(db, account)
        
        # 3. 成本评分 (0-1)
        cost_score = await self._calculate_cost_score(account, context)
        
        # 4. 负载评分 (0-1)
        load_score = await self._calculate_load_score(account)
        
        # 5. 可靠性评分 (0-1)
        reliability_score = await self._calculate_reliability_score(db, account)
        
        # 6. 预测响应时间
        predicted_response_time = await self._predict_response_time(db, account, context)
        
        # 加权计算总分
        total_score = (
            availability_score * self.config["availability_weight"] +
            performance_score * self.config["performance_weight"] +
            cost_score * self.config["cost_weight"] +
            load_score * (1 - self.config["load_balance_factor"]) +
            reliability_score * self.config["reliability_weight"]
        )
        
        # 应用用户等级权重
        tier_multiplier = self._get_tier_multiplier(context.user_tier)
        total_score *= tier_multiplier
        
        # 计算置信度
        confidence = self._calculate_confidence(account, context)
        
        return AccountScore(
            account_id=account.id,
            total_score=total_score,
            availability_score=availability_score,
            performance_score=performance_score,
            cost_score=cost_score,
            load_score=load_score,
            reliability_score=reliability_score,
            predicted_response_time=predicted_response_time,
            confidence=confidence
        )
    
    async def _calculate_availability_score(self, account: ClaudeAccount) -> float:
        """计算可用性评分"""
        # 基于剩余配额和状态
        if account.status != "active":
            return 0.0
            
        # 配额比例
        if account.daily_limit <= 0:
            return 0.0
            
        quota_ratio = float((account.daily_limit - account.current_usage) / account.daily_limit)
        quota_ratio = max(0, min(1, quota_ratio))
        
        # 考虑最近的可用性
        availability_penalty = 0
        if account.last_check_at:
            hours_since_check = (datetime.utcnow() - account.last_check_at).total_seconds() / 3600
            if hours_since_check > 1:  # 超过1小时未检查，降低评分
                availability_penalty = min(0.3, hours_since_check * 0.05)
        
        return max(0, quota_ratio - availability_penalty)
    
    async def _calculate_performance_score(self, db: AsyncSession, account: ClaudeAccount) -> float:
        """计算性能评分"""
        # 基于历史响应时间和成功率
        success_rate = float(account.success_rate or 95.0) / 100.0  # 默认95%成功率
        response_time_score = 1.0
        
        if account.avg_response_time is not None and account.avg_response_time > 0:
            # 响应时间越低评分越高
            max_acceptable_time = self.config["response_time_threshold_ms"]
            response_time_score = max(0, 1 - (account.avg_response_time / max_acceptable_time))
        
        # 获取最近性能数据
        recent_performance = await self._get_recent_performance(db, account.id)
        recent_score = recent_performance.get("avg_score", 0.8)
        
        # 综合评分
        performance_score = (success_rate * 0.4 + response_time_score * 0.3 + recent_score * 0.3)
        return min(1.0, performance_score)
    
    async def _calculate_cost_score(self, account: ClaudeAccount, context: SchedulingContext) -> float:
        """计算成本评分"""
        # 基于账号的成本效率和用户预算
        
        # 获取账号的历史成本效率
        efficiency = self.cost_efficiency.get(account.id, 0.8)
        
        # 考虑用户预算限制
        budget_factor = 1.0
        if context.budget_limit:
            estimated_cost = context.estimated_tokens * 0.00009  # 粗略估算
            if estimated_cost > context.budget_limit:
                budget_factor = context.budget_limit / estimated_cost
        
        return efficiency * budget_factor
    
    async def _calculate_load_score(self, account: ClaudeAccount) -> float:
        """计算负载评分"""
        # 基于当前负载和预测负载
        current_load = float(account.current_usage) / float(account.daily_limit) if account.daily_limit > 0 else 1.0
        
        # 预测负载
        predicted_load = self.load_predictions.get(account.id, current_load)
        
        # 负载越低评分越高
        load_score = 1.0 - ((current_load * 0.6) + (predicted_load * 0.4))
        return max(0, load_score)
    
    async def _calculate_reliability_score(self, db: AsyncSession, account: ClaudeAccount) -> float:
        """计算可靠性评分"""
        # 基于历史稳定性和错误率
        reliability_data = self.reliability_metrics.get(account.id, {})
        
        # 默认可靠性指标
        uptime_score = reliability_data.get("uptime_score", 0.95)
        error_rate = reliability_data.get("error_rate", 0.05)
        consistency_score = reliability_data.get("consistency_score", 0.9)
        
        # 综合可靠性评分
        reliability_score = (uptime_score * 0.4 + (1 - error_rate) * 0.3 + consistency_score * 0.3)
        return min(1.0, reliability_score)
    
    async def _predict_response_time(
        self, 
        db: AsyncSession, 
        account: ClaudeAccount, 
        context: SchedulingContext
    ) -> float:
        """预测响应时间"""
        # 基于历史数据和当前负载预测
        
        base_time = account.avg_response_time if account.avg_response_time is not None and account.avg_response_time > 0 else 2000
        
        # 负载因子
        load_ratio = float(account.current_usage) / float(account.daily_limit) if account.daily_limit > 0 else 0
        load_factor = 1 + (load_ratio * 0.5)  # 负载越高响应时间越长
        
        # 请求类型因子
        type_factor = self._get_request_type_factor(context.request_type)
        
        # Token数量因子
        token_factor = 1 + (context.estimated_tokens / 4000) * 0.3  # 基于平均4000token的基准
        
        predicted_time = base_time * load_factor * type_factor * token_factor
        
        return min(predicted_time, 30000)  # 最大30秒
    
    def _get_request_type_factor(self, request_type: str) -> float:
        """获取请求类型的时间因子"""
        factors = {
            "chat": 1.0,
            "analysis": 1.3,
            "generation": 1.5,
            "strategy": 2.0,
            "complex": 2.5
        }
        return factors.get(request_type, 1.0)
    
    def _get_tier_multiplier(self, user_tier: str) -> float:
        """获取用户等级的调度权重倍数"""
        multipliers = {
            "basic": 1.0,
            "premium": 1.2,
            "professional": 1.5
        }
        return multipliers.get(user_tier, 1.0)
    
    def _calculate_confidence(self, account: ClaudeAccount, context: SchedulingContext) -> float:
        """计算预测置信度"""
        # 基于历史数据量和账号稳定性
        
        data_points = account.total_requests or 0  # 处理None值
        if data_points == 0:
            return 0.3  # 新账号低置信度
        elif data_points < 100:
            return 0.5 + (data_points / 100) * 0.3
        else:
            return 0.8 + min(0.2, (data_points / 1000) * 0.2)
    
    def _weighted_random_choice(self, items: List[Tuple], weights: List[float]) -> Tuple:
        """加权随机选择"""
        if not items or not weights:
            return items[0] if items else None
            
        total_weight = sum(weights)
        if total_weight <= 0:
            return items[0]
            
        # 归一化权重
        normalized_weights = [w / total_weight for w in weights]
        
        # 随机选择
        import random
        rand_val = random.random()
        cumulative = 0
        
        for i, weight in enumerate(normalized_weights):
            cumulative += weight
            if rand_val <= cumulative:
                return items[i]
                
        return items[-1]  # 兜底返回最后一个
    
    async def _update_account_metrics(self, db: AsyncSession, accounts: List[ClaudeAccount]):
        """更新账号指标缓存"""
        for account in accounts:
            # 更新历史性能数据
            await self._update_performance_history(db, account.id)
            
            # 更新负载预测
            await self._update_load_prediction(db, account.id)
            
            # 更新成本效率
            await self._update_cost_efficiency(db, account.id)
            
            # 更新可靠性指标
            await self._update_reliability_metrics(db, account.id)
    
    async def _update_performance_history(self, db: AsyncSession, account_id: int):
        """更新性能历史"""
        # 获取最近24小时的性能数据
        since_time = datetime.utcnow() - timedelta(hours=self.config["history_window_hours"])
        
        stmt = select(ClaudeUsageLog.response_time).where(
            and_(
                ClaudeUsageLog.account_id == account_id,
                ClaudeUsageLog.request_date >= since_time,
                ClaudeUsageLog.success == True
            )
        ).order_by(desc(ClaudeUsageLog.request_date)).limit(100)
        
        result = await db.execute(stmt)
        response_times = [row[0] for row in result.fetchall() if row[0] is not None]
        
        if response_times:
            self.scheduling_history[account_id] = response_times
    
    async def _update_load_prediction(self, db: AsyncSession, account_id: int):
        """更新负载预测"""
        # 简单的线性预测，基于最近使用趋势
        # 在实际应用中可以使用更复杂的机器学习模型
        
        current_hour = datetime.utcnow().hour
        
        # 基于时间模式预测负载
        peak_hours = [9, 10, 11, 14, 15, 16]  # 工作时间高峰
        if current_hour in peak_hours:
            predicted_load = 0.7  # 高负载
        elif current_hour in [8, 12, 13, 17, 18]:
            predicted_load = 0.5  # 中等负载
        else:
            predicted_load = 0.3  # 低负载
        
        self.load_predictions[account_id] = predicted_load
    
    async def _update_cost_efficiency(self, db: AsyncSession, account_id: int):
        """更新成本效率"""
        # 计算成本效率指标
        since_time = datetime.utcnow() - timedelta(days=7)
        
        stmt = select(
            func.avg(ClaudeUsageLog.total_tokens / ClaudeUsageLog.api_cost).label("efficiency")
        ).where(
            and_(
                ClaudeUsageLog.account_id == account_id,
                ClaudeUsageLog.request_date >= since_time,
                ClaudeUsageLog.api_cost > 0,
                ClaudeUsageLog.success == True
            )
        )
        
        result = await db.execute(stmt)
        efficiency = result.scalar()
        
        if efficiency:
            # 归一化效率值
            normalized_efficiency = min(1.0, float(efficiency) / 10000)  # 假设10000是高效率基准
            self.cost_efficiency[account_id] = normalized_efficiency
        else:
            self.cost_efficiency[account_id] = 0.8  # 默认效率
    
    async def _update_reliability_metrics(self, db: AsyncSession, account_id: int):
        """更新可靠性指标"""
        since_time = datetime.utcnow() - timedelta(days=7)
        
        # 计算错误率和一致性（SQLite兼容版本）
        stmt = select(
            func.count().label("total_requests"),
            func.sum(case((ClaudeUsageLog.success == False, 1), else_=0)).label("failed_requests"),
            func.avg(ClaudeUsageLog.response_time).label("avg_response_time"),
            func.max(ClaudeUsageLog.response_time).label("max_response_time"),
            func.min(ClaudeUsageLog.response_time).label("min_response_time")
        ).where(
            and_(
                ClaudeUsageLog.account_id == account_id,
                ClaudeUsageLog.request_date >= since_time
            )
        )
        
        result = await db.execute(stmt)
        row = result.fetchone()
        
        if row and row.total_requests > 0:
            error_rate = float(row.failed_requests or 0) / float(row.total_requests)
            
            # 一致性评分（基于响应时间范围而不是标准差，SQLite兼容）
            avg_time = float(row.avg_response_time or 1000)
            max_time = float(row.max_response_time or 1000)
            min_time = float(row.min_response_time or 1000)
            time_range = max_time - min_time
            consistency_score = max(0, 1 - (time_range / 10000))  # 时间范围越小越一致
            
            self.reliability_metrics[account_id] = {
                "uptime_score": 0.98,  # 简化为固定值，实际应该基于监控数据
                "error_rate": error_rate,
                "consistency_score": consistency_score
            }
        else:
            # 默认可靠性指标
            self.reliability_metrics[account_id] = {
                "uptime_score": 0.95,
                "error_rate": 0.05,
                "consistency_score": 0.9
            }
    
    async def _get_recent_performance(self, db: AsyncSession, account_id: int) -> Dict[str, float]:
        """获取最近性能数据"""
        # 获取最近1小时的性能指标
        since_time = datetime.utcnow() - timedelta(hours=1)
        
        stmt = select(
            func.avg(ClaudeUsageLog.response_time).label("avg_response_time"),
            func.count().label("total_requests"),
            func.sum(case((ClaudeUsageLog.success == True, 1), else_=0)).label("success_requests")
        ).where(
            and_(
                ClaudeUsageLog.account_id == account_id,
                ClaudeUsageLog.request_date >= since_time
            )
        )
        
        result = await db.execute(stmt)
        row = result.fetchone()
        
        if row and row.total_requests > 0:
            success_rate = float(row.success_requests) / float(row.total_requests)
            avg_time = float(row.avg_response_time or 2000)
            
            # 性能评分
            success_score = success_rate
            time_score = max(0, 1 - (avg_time / 5000))
            avg_score = (success_score + time_score) / 2
            
            return {
                "avg_score": avg_score,
                "success_rate": success_rate,
                "avg_response_time": avg_time
            }
        
        return {
            "avg_score": 0.8,
            "success_rate": 0.95,
            "avg_response_time": 2000
        }
    
    async def _round_robin_selection(self, accounts: List[ClaudeAccount]) -> ClaudeAccount:
        """轮询选择"""
        # 简单轮询实现
        current_time = int(time.time())
        index = current_time % len(accounts)
        return accounts[index]
    
    async def _least_used_selection(self, accounts: List[ClaudeAccount]) -> ClaudeAccount:
        """最少使用选择"""
        return min(accounts, key=lambda x: x.current_usage)
    
    async def _weighted_response_time_selection(self, db: AsyncSession, accounts: List[ClaudeAccount]) -> ClaudeAccount:
        """加权响应时间选择"""
        # 基于响应时间的反向权重选择
        weights = []
        for account in accounts:
            if account.avg_response_time is not None and account.avg_response_time > 0:
                weight = 1.0 / account.avg_response_time  # 响应时间越短权重越大
            else:
                weight = 1.0
            weights.append(weight)
        
        account_weight_pairs = list(zip(accounts, weights))
        selected = self._weighted_random_choice(account_weight_pairs, weights)
        return selected[0]
    
    async def _cost_optimized_selection(
        self, 
        db: AsyncSession, 
        accounts: List[ClaudeAccount], 
        context: SchedulingContext
    ) -> ClaudeAccount:
        """成本优化选择"""
        # 选择成本效率最高的账号
        best_account = accounts[0]
        best_efficiency = self.cost_efficiency.get(best_account.id, 0.5)
        
        for account in accounts[1:]:
            efficiency = self.cost_efficiency.get(account.id, 0.5)
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_account = account
        
        return best_account
    
    async def _predictive_load_selection(
        self, 
        db: AsyncSession, 
        accounts: List[ClaudeAccount], 
        context: SchedulingContext
    ) -> ClaudeAccount:
        """预测性负载选择"""
        # 基于负载预测选择最佳账号
        best_account = accounts[0]
        lowest_predicted_load = self.load_predictions.get(best_account.id, 0.8)
        
        for account in accounts[1:]:
            predicted_load = self.load_predictions.get(account.id, 0.8)
            if predicted_load < lowest_predicted_load:
                lowest_predicted_load = predicted_load
                best_account = account
        
        return best_account
    
    async def record_scheduling_decision(
        self,
        db: AsyncSession,
        selected_account_id: int,
        context: SchedulingContext,
        strategy: SchedulingStrategy,
        decision_factors: Dict[str, Any]
    ) -> None:
        """记录调度决策以便后续优化和分析"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # 记录调度决策日志
            decision_log = {
                "timestamp": datetime.utcnow().isoformat(),
                "selected_account_id": selected_account_id,
                "user_id": context.user_id,
                "strategy": strategy.value if hasattr(strategy, 'value') else str(strategy),
                "session_id": getattr(context, 'session_id', None),
                "request_type": getattr(context, 'request_type', 'chat'),
                "decision_factors": decision_factors
            }
            
            logger.info(f"Claude调度决策记录: {json.dumps(decision_log, ensure_ascii=False, indent=2)}")
            
            # 更新调度历史（用于机器学习优化）
            if selected_account_id not in self.scheduling_history:
                self.scheduling_history[selected_account_id] = []
                
            # 记录本次调度的响应时间预测
            predicted_response_time = decision_factors.get('predicted_response_time', 2000)
            self.scheduling_history[selected_account_id].append(predicted_response_time)
            
            # 保持历史记录在合理范围内（最多保留100条记录）
            if len(self.scheduling_history[selected_account_id]) > 100:
                self.scheduling_history[selected_account_id] = self.scheduling_history[selected_account_id][-100:]
                
        except Exception as e:
            logger.error(f"记录调度决策失败: {str(e)}")
            # 不抛出异常，避免影响主要功能