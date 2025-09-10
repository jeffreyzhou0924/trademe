"""
用户行为分析服务 - 深度用户行为模式分析和画像生成
分析用户使用习惯、交易模式、偏好特征，生成个性化用户画像和商业洞察
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from decimal import Decimal
from dataclasses import dataclass
from collections import defaultdict, Counter
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, text, distinct
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_management import (
    UserActivityLog, UserStatisticsSnapshot, UserBehaviorProfile, ActivityType
)
from app.models.strategy import Strategy
from app.models.trade import Trade
from app.models.backtest import Backtest
from app.models.api_key import ApiKey
from app.models.claude_conversation import ClaudeUsage
from app.core.exceptions import UserManagementError
from app.utils.data_validation import DataValidator

logger = logging.getLogger(__name__)


@dataclass
class UsagePattern:
    """使用模式数据类"""
    peak_hours: List[int]          # 活跃时间段
    weekly_pattern: Dict[str, int]  # 一周使用模式
    session_duration: float        # 平均会话时长
    feature_frequency: Dict[str, int]  # 功能使用频率


@dataclass
class TradingBehaviorProfile:
    """交易行为画像"""
    trading_style: str             # 交易风格
    risk_level: str                # 风险水平
    preferred_instruments: List[str]  # 偏好品种
    avg_position_size: float       # 平均仓位大小
    win_rate: float               # 胜率
    profit_factor: float          # 盈利因子
    max_drawdown: float           # 最大回撤


@dataclass
class AIUsageBehavior:
    """AI使用行为"""
    usage_frequency: str          # 使用频率
    preferred_features: List[str]  # 偏好功能
    interaction_style: str        # 交互风格
    avg_session_length: int       # 平均对话长度
    cost_awareness: str           # 成本意识


@dataclass
class UserBehaviorInsight:
    """用户行为洞察"""
    user_id: int
    user_type: str               # 用户类型
    activity_level: str          # 活跃程度
    engagement_score: float      # 参与度评分
    usage_patterns: UsagePattern
    trading_profile: Optional[TradingBehaviorProfile]
    ai_behavior: Optional[AIUsageBehavior]
    lifecycle_stage: str         # 生命周期阶段
    churn_risk_score: float      # 流失风险评分
    ltv_score: float            # 生命周期价值评分
    personalization_tags: List[str]  # 个性化标签
    recommendations: List[str]   # 个性化推荐


class UserBehaviorAnalysisService:
    """用户行为分析服务"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def analyze_user_behavior(self, user_id: int, days_back: int = 30) -> UserBehaviorInsight:
        """全面分析用户行为模式"""
        try:
            logger.info(f"开始分析用户 {user_id} 的行为模式 (最近{days_back}天)")
            
            # 并行获取各种行为数据
            analysis_tasks = [
                self._analyze_usage_patterns(user_id, days_back),
                self._analyze_trading_behavior(user_id, days_back),
                self._analyze_ai_usage_behavior(user_id, days_back),
                self._calculate_engagement_metrics(user_id, days_back),
                self._assess_user_lifecycle_stage(user_id),
                self._calculate_churn_risk(user_id, days_back),
                self._estimate_lifetime_value(user_id)
            ]
            
            results = await asyncio.gather(*analysis_tasks)
            
            usage_patterns = results[0]
            trading_profile = results[1]
            ai_behavior = results[2]
            engagement_metrics = results[3]
            lifecycle_stage = results[4]
            churn_risk = results[5]
            ltv_score = results[6]
            
            # 推导用户类型和活动水平
            user_type = await self._classify_user_type(user_id, engagement_metrics, trading_profile)
            activity_level = self._classify_activity_level(engagement_metrics)
            
            # 生成个性化标签和推荐
            personalization_tags = await self._generate_personalization_tags(
                user_id, usage_patterns, trading_profile, ai_behavior, engagement_metrics
            )
            recommendations = await self._generate_personalized_recommendations(
                user_id, user_type, usage_patterns, trading_profile, ai_behavior
            )
            
            insight = UserBehaviorInsight(
                user_id=user_id,
                user_type=user_type,
                activity_level=activity_level,
                engagement_score=engagement_metrics['engagement_score'],
                usage_patterns=usage_patterns,
                trading_profile=trading_profile,
                ai_behavior=ai_behavior,
                lifecycle_stage=lifecycle_stage,
                churn_risk_score=churn_risk,
                ltv_score=ltv_score,
                personalization_tags=personalization_tags,
                recommendations=recommendations
            )
            
            # 保存或更新行为画像
            await self._save_behavior_profile(insight)
            
            logger.info(f"用户 {user_id} 行为分析完成: {user_type}, 参与度 {DataValidator.safe_format_decimal(engagement_metrics['engagement_score'], decimals=2)}")
            
            return insight
            
        except Exception as e:
            logger.error(f"用户行为分析失败 (user_id: {user_id}): {e}")
            raise UserManagementError(f"行为分析失败: {str(e)}")
    
    async def _analyze_usage_patterns(self, user_id: int, days_back: int) -> UsagePattern:
        """分析使用模式"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # 获取活动日志
        activity_query = select(UserActivityLog).where(
            and_(
                UserActivityLog.user_id == user_id,
                UserActivityLog.created_at >= start_date,
                UserActivityLog.created_at <= end_date
            )
        ).order_by(UserActivityLog.created_at)
        
        result = await self.db.execute(activity_query)
        activities = result.scalars().all()
        
        if not activities:
            return UsagePattern(
                peak_hours=[],
                weekly_pattern={},
                session_duration=0.0,
                feature_frequency={}
            )
        
        # 分析活跃时间段
        hour_counts = Counter()
        weekday_counts = Counter()
        activity_types = Counter()
        
        for activity in activities:
            hour_counts[activity.created_at.hour] += 1
            weekday_counts[activity.created_at.strftime('%A')] += 1
            activity_types[activity.activity_type.value] += 1
        
        # 找出活跃时间段 (出现频率最高的前3个小时)
        peak_hours = [hour for hour, _ in hour_counts.most_common(3)]
        
        # 计算平均会话时长 (简化版本)
        login_activities = [a for a in activities if a.activity_type == ActivityType.LOGIN]
        avg_session_duration = len(activities) / max(len(login_activities), 1) * 10  # 粗略估算
        
        return UsagePattern(
            peak_hours=sorted(peak_hours),
            weekly_pattern=dict(weekday_counts),
            session_duration=round(avg_session_duration, 1),
            feature_frequency=dict(activity_types)
        )
    
    async def _analyze_trading_behavior(self, user_id: int, days_back: int) -> Optional[TradingBehaviorProfile]:
        """分析交易行为"""
        try:
            # 获取交易数据
            trades_query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.executed_at >= datetime.utcnow() - timedelta(days=days_back)
                )
            )
            trades_result = await self.db.execute(trades_query)
            trades = trades_result.scalars().all()
            
            if not trades:
                return None
            
            # 分析交易品种偏好
            symbols = Counter([trade.symbol for trade in trades])
            preferred_instruments = [symbol for symbol, _ in symbols.most_common(3)]
            
            # 计算基本交易指标
            total_trades = len(trades)
            avg_position_size = sum(trade.total_amount for trade in trades) / total_trades
            
            # 计算盈亏 (简化版本，假设有盈亏字段)
            profitable_trades = sum(1 for trade in trades if hasattr(trade, 'pnl') and trade.pnl > 0)
            win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
            
            # 推断交易风格
            if avg_position_size > 10000:
                risk_level = "高风险"
            elif avg_position_size > 5000:
                risk_level = "中等风险"
            else:
                risk_level = "低风险"
            
            # 推断交易风格
            if total_trades > 100:
                trading_style = "高频交易"
            elif total_trades > 20:
                trading_style = "活跃交易"
            else:
                trading_style = "长期持有"
            
            return TradingBehaviorProfile(
                trading_style=trading_style,
                risk_level=risk_level,
                preferred_instruments=preferred_instruments,
                avg_position_size=float(avg_position_size),
                win_rate=win_rate,
                profit_factor=1.0,  # 简化版本
                max_drawdown=0.0    # 简化版本
            )
            
        except Exception as e:
            logger.warning(f"交易行为分析失败 (user_id: {user_id}): {e}")
            return None
    
    async def _analyze_ai_usage_behavior(self, user_id: int, days_back: int) -> Optional[AIUsageBehavior]:
        """分析AI使用行为"""
        try:
            # 获取AI使用数据
            ai_query = select(ClaudeUsage).where(
                and_(
                    ClaudeUsage.user_id == user_id,
                    ClaudeUsage.created_at >= datetime.utcnow() - timedelta(days=days_back)
                )
            )
            ai_result = await self.db.execute(ai_query)
            ai_usages = ai_result.scalars().all()
            
            if not ai_usages:
                return None
            
            total_usages = len(ai_usages)
            avg_daily_usage = total_usages / days_back
            
            # 分析使用频率
            if avg_daily_usage >= 3:
                usage_frequency = "高频使用"
            elif avg_daily_usage >= 1:
                usage_frequency = "中等使用"
            else:
                usage_frequency = "低频使用"
            
            # 分析功能偏好 (基于请求类型)
            feature_counter = Counter()
            total_tokens = 0
            total_cost = Decimal('0')
            
            for usage in ai_usages:
                if hasattr(usage, 'request_type') and usage.request_type:
                    feature_counter[usage.request_type] += 1
                if hasattr(usage, 'input_tokens'):
                    total_tokens += usage.input_tokens or 0
                if hasattr(usage, 'total_cost'):
                    total_cost += usage.total_cost or Decimal('0')
            
            preferred_features = [feature for feature, _ in feature_counter.most_common(3)]
            
            # 分析交互风格
            avg_session_length = total_tokens / max(total_usages, 1)
            if avg_session_length > 1000:
                interaction_style = "深度对话"
            elif avg_session_length > 500:
                interaction_style = "标准交互"
            else:
                interaction_style = "简短询问"
            
            # 分析成本意识
            daily_cost = float(total_cost) / days_back
            if daily_cost > 10:
                cost_awareness = "成本不敏感"
            elif daily_cost > 2:
                cost_awareness = "成本适中"
            else:
                cost_awareness = "成本敏感"
            
            return AIUsageBehavior(
                usage_frequency=usage_frequency,
                preferred_features=preferred_features,
                interaction_style=interaction_style,
                avg_session_length=int(avg_session_length),
                cost_awareness=cost_awareness
            )
            
        except Exception as e:
            logger.warning(f"AI使用行为分析失败 (user_id: {user_id}): {e}")
            return None
    
    async def _calculate_engagement_metrics(self, user_id: int, days_back: int) -> Dict[str, Any]:
        """计算参与度指标"""
        try:
            # 获取基础数据
            stats_queries = [
                # 登录次数
                select(func.count(UserActivityLog.id)).where(
                    and_(
                        UserActivityLog.user_id == user_id,
                        UserActivityLog.activity_type == ActivityType.LOGIN,
                        UserActivityLog.created_at >= datetime.utcnow() - timedelta(days=days_back)
                    )
                ),
                # 策略创建数
                select(func.count(Strategy.id)).where(
                    and_(
                        Strategy.user_id == user_id,
                        Strategy.created_at >= datetime.utcnow() - timedelta(days=days_back)
                    )
                ),
                # 回测执行数
                select(func.count(Backtest.id)).where(
                    and_(
                        Backtest.user_id == user_id,
                        Backtest.created_at >= datetime.utcnow() - timedelta(days=days_back)
                    )
                ),
                # 活跃天数
                select(func.count(func.distinct(func.date(UserActivityLog.created_at)))).where(
                    and_(
                        UserActivityLog.user_id == user_id,
                        UserActivityLog.created_at >= datetime.utcnow() - timedelta(days=days_back)
                    )
                )
            ]
            
            results = await asyncio.gather(*[self.db.execute(query) for query in stats_queries])
            
            login_count = results[0].scalar() or 0
            strategy_count = results[1].scalar() or 0
            backtest_count = results[2].scalar() or 0
            active_days = results[3].scalar() or 0
            
            # 计算参与度评分
            login_score = min(login_count / days_back, 1.0)  # 每天1次登录为满分
            strategy_score = min(strategy_count / 5, 1.0)    # 期间内5个策略为满分
            backtest_score = min(backtest_count / 10, 1.0)   # 期间内10次回测为满分
            retention_score = active_days / days_back         # 留存率
            
            # 加权计算总参与度
            engagement_score = (
                login_score * 0.3 +
                strategy_score * 0.25 +
                backtest_score * 0.25 +
                retention_score * 0.2
            )
            
            return {
                'engagement_score': round(engagement_score, 3),
                'login_count': login_count,
                'strategy_count': strategy_count,
                'backtest_count': backtest_count,
                'active_days': active_days,
                'retention_rate': round(retention_score, 3)
            }
            
        except Exception as e:
            logger.error(f"参与度计算失败 (user_id: {user_id}): {e}")
            return {
                'engagement_score': 0.0,
                'login_count': 0,
                'strategy_count': 0,
                'backtest_count': 0,
                'active_days': 0,
                'retention_rate': 0.0
            }
    
    async def _assess_user_lifecycle_stage(self, user_id: int) -> str:
        """评估用户生命周期阶段"""
        try:
            # 获取用户基础信息
            user_query = select(User).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return "unknown"
            
            registration_days = (datetime.utcnow() - user.created_at).days
            last_login_days = (datetime.utcnow() - user.last_login_at).days if user.last_login_at else 999
            
            # 获取活动总数
            activity_count_query = select(func.count(UserActivityLog.id)).where(
                UserActivityLog.user_id == user_id
            )
            activity_result = await self.db.execute(activity_count_query)
            total_activities = activity_result.scalar() or 0
            
            # 判断生命周期阶段
            if registration_days <= 7:
                return "新用户"
            elif registration_days <= 30 and total_activities >= 10:
                return "成长期"
            elif last_login_days <= 7 and total_activities >= 50:
                return "成熟期"
            elif last_login_days <= 30:
                return "维持期"
            elif last_login_days <= 60:
                return "衰退期"
            else:
                return "流失期"
                
        except Exception as e:
            logger.error(f"生命周期评估失败 (user_id: {user_id}): {e}")
            return "unknown"
    
    async def _calculate_churn_risk(self, user_id: int, days_back: int) -> float:
        """计算流失风险评分"""
        try:
            # 获取用户信息
            user_query = select(User).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return 1.0  # 最高风险
            
            # 计算风险因子
            last_login_days = (datetime.utcnow() - user.last_login_at).days if user.last_login_at else 999
            
            # 获取最近活动
            recent_activity_query = select(func.count(UserActivityLog.id)).where(
                and_(
                    UserActivityLog.user_id == user_id,
                    UserActivityLog.created_at >= datetime.utcnow() - timedelta(days=7)
                )
            )
            recent_result = await self.db.execute(recent_activity_query)
            recent_activities = recent_result.scalar() or 0
            
            # 风险评分计算 (0-1, 越高越危险)
            login_risk = min(last_login_days / 30.0, 1.0)  # 30天未登录为最高风险
            activity_risk = max(0, 1.0 - recent_activities / 10.0)  # 7天内少于10次活动为高风险
            
            churn_risk = (login_risk * 0.6 + activity_risk * 0.4)
            
            return round(min(churn_risk, 1.0), 3)
            
        except Exception as e:
            logger.error(f"流失风险计算失败 (user_id: {user_id}): {e}")
            return 0.5  # 中等风险
    
    async def _estimate_lifetime_value(self, user_id: int) -> float:
        """估算用户生命周期价值"""
        try:
            # 获取用户信息
            user_query = select(User).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return 0.0
            
            # 基础价值计算因素
            membership_value = {
                'basic': 19,
                'premium': 99,
                'professional': 199
            }.get(user.membership_level, 0)
            
            # 获取用户活跃度
            registration_days = (datetime.utcnow() - user.created_at).days
            activity_query = select(func.count(UserActivityLog.id)).where(
                UserActivityLog.user_id == user_id
            )
            activity_result = await self.db.execute(activity_query)
            total_activities = activity_result.scalar() or 0
            
            # 活跃度因子
            activity_factor = min(total_activities / 100, 2.0)  # 最高2倍
            
            # 留存因子
            retention_factor = min(registration_days / 365, 2.0)  # 使用时间越长价值越高
            
            # LTV计算 (简化版本)
            ltv = membership_value * activity_factor * retention_factor
            
            return round(ltv, 2)
            
        except Exception as e:
            logger.error(f"LTV计算失败 (user_id: {user_id}): {e}")
            return 0.0
    
    async def _classify_user_type(self, user_id: int, engagement_metrics: Dict, 
                                trading_profile: Optional[TradingBehaviorProfile]) -> str:
        """分类用户类型"""
        engagement_score = engagement_metrics.get('engagement_score', 0)
        
        if engagement_score >= 0.8:
            return "专家用户"
        elif engagement_score >= 0.6:
            return "进阶用户"
        elif engagement_score >= 0.3:
            return "普通用户"
        else:
            return "新手用户"
    
    def _classify_activity_level(self, engagement_metrics: Dict) -> str:
        """分类活动水平"""
        engagement_score = engagement_metrics.get('engagement_score', 0)
        
        if engagement_score >= 0.7:
            return "高活跃"
        elif engagement_score >= 0.4:
            return "中等活跃"
        elif engagement_score >= 0.1:
            return "低活跃"
        else:
            return "不活跃"
    
    async def _generate_personalization_tags(self, user_id: int, usage_patterns: UsagePattern,
                                           trading_profile: Optional[TradingBehaviorProfile],
                                           ai_behavior: Optional[AIUsageBehavior],
                                           engagement_metrics: Dict) -> List[str]:
        """生成个性化标签"""
        tags = []
        
        # 基于参与度的标签
        engagement_score = engagement_metrics.get('engagement_score', 0)
        if engagement_score >= 0.8:
            tags.append("高参与度")
        elif engagement_score >= 0.5:
            tags.append("中等参与度")
        
        # 基于使用模式的标签
        if usage_patterns.peak_hours:
            if any(hour < 9 or hour > 18 for hour in usage_patterns.peak_hours):
                tags.append("非工作时间用户")
            else:
                tags.append("工作时间用户")
        
        # 基于交易行为的标签
        if trading_profile:
            tags.append(f"交易风格:{trading_profile.trading_style}")
            tags.append(f"风险偏好:{trading_profile.risk_level}")
        
        # 基于AI使用的标签
        if ai_behavior:
            tags.append(f"AI使用:{ai_behavior.usage_frequency}")
            tags.append(f"交互风格:{ai_behavior.interaction_style}")
        
        return tags
    
    async def _generate_personalized_recommendations(self, user_id: int, user_type: str,
                                                   usage_patterns: UsagePattern,
                                                   trading_profile: Optional[TradingBehaviorProfile],
                                                   ai_behavior: Optional[AIUsageBehavior]) -> List[str]:
        """生成个性化推荐"""
        recommendations = []
        
        # 基于用户类型的推荐
        if user_type == "新手用户":
            recommendations.extend([
                "建议查看新手教程",
                "尝试使用策略模板",
                "参加在线培训课程"
            ])
        elif user_type == "进阶用户":
            recommendations.extend([
                "探索高级策略功能",
                "尝试组合策略",
                "参与社区讨论"
            ])
        elif user_type == "专家用户":
            recommendations.extend([
                "考虑升级到专业版",
                "分享策略到社区",
                "申请成为策略导师"
            ])
        
        # 基于AI使用行为的推荐
        if ai_behavior:
            if ai_behavior.usage_frequency == "低频使用":
                recommendations.append("尝试更多AI功能提升效率")
            elif ai_behavior.cost_awareness == "成本敏感":
                recommendations.append("了解AI使用优化技巧")
        
        # 基于交易行为的推荐
        if trading_profile:
            if trading_profile.risk_level == "高风险":
                recommendations.append("建议加强风险管理")
            elif trading_profile.win_rate < 0.4:
                recommendations.append("考虑优化交易策略")
        
        return recommendations
    
    async def _save_behavior_profile(self, insight: UserBehaviorInsight) -> None:
        """保存或更新用户行为画像"""
        try:
            # 查找现有画像
            profile_query = select(UserBehaviorProfile).where(
                UserBehaviorProfile.user_id == insight.user_id
            )
            result = await self.db.execute(profile_query)
            existing_profile = result.scalar_one_or_none()
            
            # 准备数据
            profile_data = {
                'user_type': insight.user_type,
                'activity_level': insight.activity_level,
                'engagement_score': Decimal(str(insight.engagement_score)),
                'trading_style': insight.trading_profile.trading_style if insight.trading_profile else None,
                'risk_preference': insight.trading_profile.risk_level if insight.trading_profile else None,
                'preferred_instruments': json.dumps(insight.trading_profile.preferred_instruments) if insight.trading_profile else None,
                'preferred_features': json.dumps(insight.usage_patterns.feature_frequency),
                'usage_patterns': json.dumps({
                    'peak_hours': insight.usage_patterns.peak_hours,
                    'weekly_pattern': insight.usage_patterns.weekly_pattern,
                    'session_duration': insight.usage_patterns.session_duration
                }),
                'peak_activity_hours': json.dumps(insight.usage_patterns.peak_hours),
                'ai_usage_frequency': insight.ai_behavior.usage_frequency if insight.ai_behavior else None,
                'preferred_ai_features': json.dumps(insight.ai_behavior.preferred_features) if insight.ai_behavior else None,
                'ai_interaction_style': insight.ai_behavior.interaction_style if insight.ai_behavior else None,
                'lifetime_value_score': Decimal(str(insight.ltv_score)),
                'churn_risk_score': Decimal(str(insight.churn_risk_score)),
                'last_analyzed_at': datetime.utcnow(),
                'analysis_version': '2.0'
            }
            
            if existing_profile:
                # 更新现有画像
                for key, value in profile_data.items():
                    setattr(existing_profile, key, value)
                existing_profile.updated_at = datetime.utcnow()
            else:
                # 创建新画像
                new_profile = UserBehaviorProfile(
                    user_id=insight.user_id,
                    **profile_data
                )
                self.db.add(new_profile)
            
            await self.db.commit()
            logger.info(f"用户 {insight.user_id} 行为画像已保存")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"保存行为画像失败 (user_id: {insight.user_id}): {e}")
            raise UserManagementError(f"保存行为画像失败: {str(e)}")
    
    async def batch_analyze_user_behavior(self, user_ids: Optional[List[int]] = None,
                                        days_back: int = 30) -> Dict[str, Any]:
        """批量分析用户行为"""
        try:
            # 如果没有指定用户，分析所有活跃用户
            if not user_ids:
                user_query = select(User.id).where(User.is_active == True)
                result = await self.db.execute(user_query)
                user_ids = [row[0] for row in result.fetchall()]
            
            logger.info(f"开始批量用户行为分析，用户数量: {len(user_ids)}")
            
            successful_analyses = []
            failed_analyses = []
            
            # 批量处理用户 (每批10个用户)
            batch_size = 10
            for i in range(0, len(user_ids), batch_size):
                batch_user_ids = user_ids[i:i + batch_size]
                
                batch_tasks = [
                    self.analyze_user_behavior(user_id, days_back)
                    for user_id in batch_user_ids
                ]
                
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for user_id, result in zip(batch_user_ids, batch_results):
                    if isinstance(result, Exception):
                        failed_analyses.append({
                            "user_id": user_id,
                            "error": str(result)
                        })
                    else:
                        successful_analyses.append({
                            "user_id": user_id,
                            "user_type": result.user_type,
                            "activity_level": result.activity_level,
                            "engagement_score": result.engagement_score,
                            "churn_risk": result.churn_risk_score,
                            "ltv_score": result.ltv_score
                        })
            
            summary = {
                "total_users": len(user_ids),
                "successful_count": len(successful_analyses),
                "failed_count": len(failed_analyses),
                "success_rate": round(len(successful_analyses) / len(user_ids) * 100, 2),
                "successful_analyses": successful_analyses,
                "failed_analyses": failed_analyses,
                "analysis_summary": self._generate_batch_summary(successful_analyses),
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"批量用户行为分析完成: 成功 {len(successful_analyses)}, 失败 {len(failed_analyses)}")
            
            return summary
            
        except Exception as e:
            logger.error(f"批量用户行为分析失败: {e}")
            raise UserManagementError(f"批量分析失败: {str(e)}")
    
    def _generate_batch_summary(self, analyses: List[Dict]) -> Dict[str, Any]:
        """生成批量分析摘要"""
        if not analyses:
            return {}
        
        # 用户类型分布
        user_types = Counter([a['user_type'] for a in analyses])
        
        # 活动水平分布
        activity_levels = Counter([a['activity_level'] for a in analyses])
        
        # 平均指标
        avg_engagement = sum(a['engagement_score'] for a in analyses) / len(analyses)
        avg_churn_risk = sum(a['churn_risk'] for a in analyses) / len(analyses)
        avg_ltv = sum(a['ltv_score'] for a in analyses) / len(analyses)
        
        # 高风险用户
        high_churn_risk_users = [a for a in analyses if a['churn_risk'] >= 0.7]
        
        return {
            "user_type_distribution": dict(user_types),
            "activity_level_distribution": dict(activity_levels),
            "average_metrics": {
                "engagement_score": round(avg_engagement, 3),
                "churn_risk_score": round(avg_churn_risk, 3),
                "ltv_score": round(avg_ltv, 2)
            },
            "high_churn_risk_users": len(high_churn_risk_users),
            "high_value_users": len([a for a in analyses if a['ltv_score'] >= 100])
        }