"""
Claude智能调度服务 - 参考claude-relay-service的UnifiedClaudeScheduler设计
实现智能账号选择、负载均衡、故障转移等功能
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
from sqlalchemy import select, update, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.claude_proxy import ClaudeAccount, Proxy, ClaudeSchedulerConfig
from app.services.claude_account_service import claude_account_service

logger = logging.getLogger(__name__)


@dataclass
class SchedulerContext:
    """调度上下文"""
    user_id: Optional[int] = None
    request_type: str = "chat"
    model_name: Optional[str] = None
    session_id: Optional[str] = None
    min_quota: Optional[Decimal] = None
    prefer_proxy: bool = False
    excluded_accounts: Optional[List[int]] = None
    priority: int = 100  # 数字越小优先级越高


@dataclass
class AccountScore:
    """账号评分"""
    account: ClaudeAccount
    score: float
    reasons: List[str]


class ClaudeSchedulerService:
    """Claude智能调度服务"""
    
    def __init__(self):
        self.config_cache = {}
        self.config_cache_expires = None
        
        # 默认调度策略
        self.default_strategy = {
            "load_balance": {
                "weight_success_rate": 0.4,
                "weight_remaining_quota": 0.3,
                "weight_response_time": 0.2,
                "weight_last_used": 0.1
            },
            "failover": {
                "max_failure_rate": 0.1,  # 10%
                "min_success_rate": 0.9,   # 90%
                "cooldown_minutes": 5
            },
            "cost_optimize": {
                "prefer_lower_cost": True,
                "quota_efficiency_threshold": 0.8
            }
        }
    
    async def select_optimal_account(
        self, 
        context: SchedulerContext
    ) -> Optional[ClaudeAccount]:
        """
        选择最优账号 - 核心调度逻辑
        
        Args:
            context: 调度上下文
            
        Returns:
            选中的Claude账号，如果没有可用账号则返回None
        """
        logger.info(f"Starting account selection with context: {context}")
        
        # 1. 检查会话粘性
        if context.session_id:
            sticky_account = await self._try_sticky_session(context)
            if sticky_account:
                logger.info(f"Using sticky session account: {sticky_account.id}")
                return sticky_account
        
        # 2. 获取候选账号列表
        candidates = await self._get_candidate_accounts(context)
        if not candidates:
            logger.warning("No candidate accounts available")
            return None
        
        # 3. 账号评分和排序
        scored_accounts = await self._score_accounts(candidates, context)
        if not scored_accounts:
            logger.warning("No accounts passed scoring criteria")
            return None
        
        # 4. 选择最高分账号
        selected_score = scored_accounts[0]
        selected_account = selected_score.account
        
        # 5. 设置会话粘性
        if context.session_id:
            await claude_account_service._set_sticky_session(
                context.session_id, 
                selected_account.id
            )
        
        # 6. 记录选择决策
        await self._log_selection_decision(selected_score, context)
        
        logger.info(f"Selected account: {selected_account.account_name} (ID: {selected_account.id}, Score: {selected_score.score:.2f})")
        
        return selected_account
    
    async def _try_sticky_session(
        self, 
        context: SchedulerContext
    ) -> Optional[ClaudeAccount]:
        """尝试使用会话粘性账号"""
        
        cached_account_id = await claude_account_service._get_sticky_session_account(
            context.session_id
        )
        
        if not cached_account_id:
            return None
            
        account = await claude_account_service.get_account(cached_account_id)
        
        # 验证账号是否仍然可用
        if account and await self._is_account_suitable(account, context):
            await claude_account_service._update_account_usage_stats(account.id)
            return account
        else:
            # 清除无效的会话粘性
            await claude_account_service._clear_sticky_session(context.session_id)
            
        return None
    
    async def _get_candidate_accounts(
        self, 
        context: SchedulerContext
    ) -> List[ClaudeAccount]:
        """获取候选账号列表"""
        
        async with AsyncSessionLocal() as session:
            # 基本条件：状态活跃
            conditions = [ClaudeAccount.status == "active"]
            
            # 排除指定账号
            if context.excluded_accounts:
                conditions.append(~ClaudeAccount.id.in_(context.excluded_accounts))
            
            # 最小配额要求
            if context.min_quota:
                conditions.append(
                    ClaudeAccount.daily_limit - ClaudeAccount.current_usage >= context.min_quota
                )
            
            query = select(ClaudeAccount).where(and_(*conditions))
            
            # 如果偏好有代理的账号
            if context.prefer_proxy:
                query = query.where(ClaudeAccount.proxy_id.isnot(None))
            
            result = await session.execute(query)
            candidates = result.scalars().all()
            
            logger.info(f"Query returned {len(candidates)} raw candidates")
            for c in candidates:
                logger.info(f"  - {c.account_name}: status={c.status}, limit={c.daily_limit}, usage={c.current_usage}, remaining={c.daily_limit - c.current_usage}")
            
            # 过滤不适合的账号
            suitable_candidates = []
            for account in candidates:
                is_suitable = await self._is_account_suitable(account, context)
                logger.info(f"Account {account.account_name} suitable check: {is_suitable}")
                if is_suitable:
                    suitable_candidates.append(account)
                else:
                    logger.info(f"  Rejected {account.account_name}: not suitable")
            
            logger.info(f"Found {len(suitable_candidates)} suitable candidate accounts after filtering")
            return suitable_candidates
    
    async def _is_account_suitable(
        self, 
        account: ClaudeAccount, 
        context: SchedulerContext
    ) -> bool:
        """检查账号是否适合当前请求"""
        
        # 基本可用性检查
        is_available = await claude_account_service._is_account_available(account)
        if not is_available:
            logger.info(f"Account {account.account_name} not available from claude_account_service")
            return False
        
        # 模型支持检查（如果需要特定模型）
        if context.model_name:
            # 这里可以添加模型支持检查逻辑
            # 例如：某些账号可能不支持Claude-3.5-Sonnet等
            pass
        
        # 成功率检查
        if account.success_rate < Decimal("85.0"):
            logger.debug(f"Account {account.id} success rate too low: {account.success_rate}%")
            return False
        
        # 配额检查
        remaining_quota = account.daily_limit - account.current_usage
        if remaining_quota < Decimal("1.0"):  # 至少保留$1配额
            logger.debug(f"Account {account.id} insufficient quota: ${remaining_quota}")
            return False
        
        return True
    
    async def _score_accounts(
        self, 
        candidates: List[ClaudeAccount], 
        context: SchedulerContext
    ) -> List[AccountScore]:
        """对候选账号进行评分排序"""
        
        scored_accounts = []
        
        for account in candidates:
            score_data = await self._calculate_account_score(account, context)
            if score_data.score > 0:
                scored_accounts.append(score_data)
        
        # 按分数降序排列
        scored_accounts.sort(key=lambda x: x.score, reverse=True)
        
        return scored_accounts
    
    async def _calculate_account_score(
        self, 
        account: ClaudeAccount, 
        context: SchedulerContext
    ) -> AccountScore:
        """计算账号得分"""
        
        reasons = []
        weights = self.default_strategy["load_balance"]
        
        # 1. 成功率得分 (0-100)
        success_score = float(account.success_rate)
        reasons.append(f"success_rate: {success_score:.1f}%")
        
        # 2. 剩余配额得分 (0-100)
        remaining_quota = account.daily_limit - account.current_usage
        quota_ratio = min(float(remaining_quota) / 10.0, 1.0)  # 假设$10为满分
        quota_score = quota_ratio * 100
        reasons.append(f"remaining_quota: ${remaining_quota:.2f} (score: {quota_score:.1f})")
        
        # 3. 响应时间得分 (0-100，响应时间越低得分越高)
        if account.avg_response_time is not None and account.avg_response_time > 0:
            # 假设5秒为最差，500ms为最佳
            time_score = max(0, 100 - (account.avg_response_time - 500) / 45)
        else:
            time_score = 100  # 新账号给满分
        reasons.append(f"response_time: {account.avg_response_time}ms (score: {time_score:.1f})")
        
        # 4. 最近使用时间得分 (0-100，越久未使用得分越高)
        if account.last_used_at:
            hours_since_last_use = (datetime.utcnow() - account.last_used_at).total_seconds() / 3600
            last_used_score = min(hours_since_last_use * 20, 100)  # 5小时未使用为满分
        else:
            last_used_score = 100  # 从未使用过给满分
        reasons.append(f"last_used_hours: {hours_since_last_use if account.last_used_at else 'never'} (score: {last_used_score:.1f})")
        
        # 加权计算总分
        total_score = (
            success_score * weights["weight_success_rate"] +
            quota_score * weights["weight_remaining_quota"] +
            time_score * weights["weight_response_time"] +
            last_used_score * weights["weight_last_used"]
        )
        
        # 优先级修正（数字越小优先级越高）
        priority_bonus = max(0, (200 - context.priority) / 20)  # 最多+10分
        total_score += priority_bonus
        
        if context.prefer_proxy and account.proxy_id:
            total_score += 5  # 代理加成
            reasons.append("proxy_bonus: +5")
        
        return AccountScore(
            account=account,
            score=total_score,
            reasons=reasons
        )
    
    async def _log_selection_decision(
        self, 
        selected_score: AccountScore, 
        context: SchedulerContext
    ):
        """记录选择决策日志"""
        
        decision_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "selected_account_id": selected_score.account.id,
            "selected_account_name": selected_score.account.account_name,
            "score": selected_score.score,
            "reasons": selected_score.reasons,
            "context": {
                "user_id": context.user_id,
                "request_type": context.request_type,
                "model_name": context.model_name,
                "session_id": context.session_id,
                "priority": context.priority
            }
        }
        
        logger.info(f"Account selection decision: {json.dumps(decision_log, indent=2)}")
    
    async def get_scheduler_config(
        self, 
        config_type: str = "load_balance"
    ) -> Dict[str, Any]:
        """获取调度器配置"""
        
        # 检查缓存
        now = datetime.utcnow()
        if (self.config_cache_expires and 
            now < self.config_cache_expires and 
            config_type in self.config_cache):
            return self.config_cache[config_type]
        
        # 从数据库获取配置
        async with AsyncSessionLocal() as session:
            query = select(ClaudeSchedulerConfig).where(
                and_(
                    ClaudeSchedulerConfig.config_type == config_type,
                    ClaudeSchedulerConfig.is_active == True
                )
            ).order_by(ClaudeSchedulerConfig.priority.asc())
            
            result = await session.execute(query)
            config_record = result.scalar_one_or_none()
            
            if config_record:
                try:
                    config_data = json.loads(config_record.config_data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in scheduler config: {config_record.id}")
                    config_data = self.default_strategy.get(config_type, {})
            else:
                config_data = self.default_strategy.get(config_type, {})
            
            # 更新缓存
            self.config_cache[config_type] = config_data
            self.config_cache_expires = now + timedelta(minutes=10)  # 10分钟缓存
            
            return config_data
    
    async def update_scheduler_config(
        self, 
        config_type: str, 
        config_data: Dict[str, Any],
        config_name: Optional[str] = None
    ) -> bool:
        """更新调度器配置"""
        
        async with AsyncSessionLocal() as session:
            # 查找现有配置
            query = select(ClaudeSchedulerConfig).where(
                ClaudeSchedulerConfig.config_type == config_type
            )
            result = await session.execute(query)
            existing_config = result.scalar_one_or_none()
            
            if existing_config:
                # 更新现有配置
                existing_config.config_data = json.dumps(config_data)
                existing_config.updated_at = datetime.utcnow()
                if config_name:
                    existing_config.config_name = config_name
            else:
                # 创建新配置
                new_config = ClaudeSchedulerConfig(
                    config_name=config_name or f"{config_type}_config",
                    config_type=config_type,
                    config_data=json.dumps(config_data),
                    is_active=True,
                    priority=100
                )
                session.add(new_config)
            
            await session.commit()
            
            # 清除缓存
            self.config_cache.pop(config_type, None)
            self.config_cache_expires = None
            
            logger.info(f"Updated scheduler config: {config_type}")
            return True
    
    async def get_account_pool_status(self) -> Dict[str, Any]:
        """获取账号池状态概览"""
        
        async with AsyncSessionLocal() as session:
            # 总体统计
            total_query = select(
                func.count(ClaudeAccount.id).label('total_accounts'),
                func.count(ClaudeAccount.id).filter(ClaudeAccount.status == 'active').label('active_accounts'),
                func.sum(ClaudeAccount.daily_limit).label('total_daily_limit'),
                func.sum(ClaudeAccount.current_usage).label('total_current_usage'),
                func.avg(ClaudeAccount.success_rate).label('avg_success_rate'),
                func.avg(ClaudeAccount.avg_response_time).label('avg_response_time')
            )
            
            result = await session.execute(total_query)
            stats = result.first()
            
            # 按状态分组统计
            status_query = select(
                ClaudeAccount.status,
                func.count(ClaudeAccount.id).label('count')
            ).group_by(ClaudeAccount.status)
            
            status_result = await session.execute(status_query)
            status_breakdown = {row.status: row.count for row in status_result}
            
            total_limit = float(stats.total_daily_limit or 0)
            total_usage = float(stats.total_current_usage or 0)
            
            return {
                'total_accounts': stats.total_accounts or 0,
                'active_accounts': stats.active_accounts or 0,
                'status_breakdown': status_breakdown,
                'total_daily_limit_usd': total_limit,
                'total_current_usage_usd': total_usage,
                'remaining_quota_usd': total_limit - total_usage,
                'quota_utilization_percent': (total_usage / total_limit * 100) if total_limit > 0 else 0,
                'avg_success_rate_percent': float(stats.avg_success_rate or 0),
                'avg_response_time_ms': float(stats.avg_response_time or 0),
                'pool_health': self._calculate_pool_health(stats, status_breakdown)
            }
    
    def _calculate_pool_health(
        self, 
        stats: Any, 
        status_breakdown: Dict[str, int]
    ) -> str:
        """计算账号池健康度"""
        
        total_accounts = stats.total_accounts or 0
        active_accounts = stats.active_accounts or 0
        avg_success_rate = float(stats.avg_success_rate or 0)
        
        if total_accounts == 0:
            return "empty"
        
        active_ratio = active_accounts / total_accounts
        
        if active_ratio >= 0.8 and avg_success_rate >= 95:
            return "excellent"
        elif active_ratio >= 0.6 and avg_success_rate >= 90:
            return "good"
        elif active_ratio >= 0.4 and avg_success_rate >= 85:
            return "fair"
        else:
            return "poor"


# 全局实例
claude_scheduler_service = ClaudeSchedulerService()