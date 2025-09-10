"""
智能标签服务 - 基于用户行为的智能标签分析和推荐
通过用户活动数据、交易行为、使用模式等多维度分析，自动推荐和分配用户标签
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_management import (
    UserTag, UserTagAssignment, UserActivityLog, UserStatisticsSnapshot,
    UserBehaviorProfile, TagType, ActivityType
)
from app.models.strategy import Strategy
from app.models.trade import Trade
from app.models.backtest import Backtest
from app.models.api_key import ApiKey
from app.models.claude_conversation import ClaudeUsage
from app.services.user_management_service import UserManagementService
from app.core.exceptions import UserManagementError
from app.utils.data_validation import DataValidator

logger = logging.getLogger(__name__)


class UserSegment(Enum):
    """用户细分类型"""
    NEWBIE = "新手用户"
    INTERMEDIATE = "进阶用户"
    EXPERT = "专家用户"
    INACTIVE = "非活跃用户"
    HIGH_VALUE = "高价值用户"
    AT_RISK = "流失风险用户"
    POWER_USER = "重度用户"
    CASUAL = "轻度用户"


@dataclass
class UserCharacteristics:
    """用户特征数据类"""
    user_id: int
    registration_days: int
    total_logins: int
    login_frequency: float  # 登录频率 (次/天)
    last_login_days_ago: int
    total_strategies: int
    active_strategies: int
    total_backtests: int
    total_trades: int
    total_ai_usage: int
    ai_usage_frequency: float  # AI使用频率
    membership_level: str
    is_email_verified: bool
    is_active: bool
    # 行为模式指标
    activity_diversity: float  # 活动多样性
    engagement_level: float    # 参与度
    technical_proficiency: float  # 技术熟练度


@dataclass
class TagRecommendation:
    """标签推荐结果"""
    tag_name: str
    confidence_score: float  # 置信度评分 (0-1)
    reason: str             # 推荐原因
    auto_assign: bool       # 是否自动分配
    priority: int           # 优先级 (1-10)


class SmartTaggingService:
    """智能标签服务"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.user_management_service = UserManagementService(db_session)
        
        # 预定义标签规则
        self.tag_rules = self._initialize_tag_rules()
    
    def _initialize_tag_rules(self) -> Dict[str, Dict[str, Any]]:
        """初始化标签规则配置"""
        return {
            "新用户": {
                "criteria": {
                    "registration_days": {"max": 7},
                    "total_logins": {"max": 5}
                },
                "confidence_base": 0.9,
                "auto_assign": True,
                "priority": 9
            },
            "活跃用户": {
                "criteria": {
                    "login_frequency": {"min": 0.5},  # 每天至少登录0.5次
                    "last_login_days_ago": {"max": 3}
                },
                "confidence_base": 0.8,
                "auto_assign": True,
                "priority": 8
            },
            "策略达人": {
                "criteria": {
                    "total_strategies": {"min": 5},
                    "active_strategies": {"min": 2}
                },
                "confidence_base": 0.85,
                "auto_assign": True,
                "priority": 7
            },
            "回测专家": {
                "criteria": {
                    "total_backtests": {"min": 10}
                },
                "confidence_base": 0.8,
                "auto_assign": True,
                "priority": 6
            },
            "交易高手": {
                "criteria": {
                    "total_trades": {"min": 50}
                },
                "confidence_base": 0.85,
                "auto_assign": True,
                "priority": 8
            },
            "AI用户": {
                "criteria": {
                    "total_ai_usage": {"min": 20},
                    "ai_usage_frequency": {"min": 0.2}
                },
                "confidence_base": 0.8,
                "auto_assign": True,
                "priority": 7
            },
            "高级会员": {
                "criteria": {
                    "membership_level": {"in": ["premium", "professional"]}
                },
                "confidence_base": 1.0,
                "auto_assign": True,
                "priority": 9
            },
            "沉睡用户": {
                "criteria": {
                    "last_login_days_ago": {"min": 30},
                    "registration_days": {"min": 30}
                },
                "confidence_base": 0.9,
                "auto_assign": True,
                "priority": 8
            },
            "流失风险": {
                "criteria": {
                    "last_login_days_ago": {"min": 14, "max": 30},
                    "total_logins": {"min": 5}
                },
                "confidence_base": 0.7,
                "auto_assign": False,
                "priority": 9
            },
            "重度用户": {
                "criteria": {
                    "login_frequency": {"min": 2.0},
                    "activity_diversity": {"min": 0.6}
                },
                "confidence_base": 0.8,
                "auto_assign": True,
                "priority": 7
            }
        }
    
    async def analyze_user_for_tagging(self, user_id: int) -> Tuple[UserCharacteristics, List[TagRecommendation]]:
        """分析用户并生成标签推荐"""
        try:
            # 获取用户特征
            characteristics = await self._extract_user_characteristics(user_id)
            
            # 基于规则生成标签推荐
            recommendations = self._generate_tag_recommendations(characteristics)
            
            # 基于机器学习模型增强推荐 (简化版本)
            enhanced_recommendations = await self._enhance_recommendations_with_ml(characteristics, recommendations)
            
            # 过滤已存在的标签
            filtered_recommendations = await self._filter_existing_tags(user_id, enhanced_recommendations)
            
            return characteristics, filtered_recommendations
            
        except Exception as e:
            logger.error(f"分析用户标签失败 (user_id: {user_id}): {e}")
            raise UserManagementError(f"用户标签分析失败: {str(e)}")
    
    async def _extract_user_characteristics(self, user_id: int) -> UserCharacteristics:
        """提取用户特征数据"""
        
        # 获取用户基础信息
        user_query = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise UserManagementError(f"用户 {user_id} 不存在")
        
        current_time = datetime.utcnow()
        registration_days = (current_time - user.created_at).days
        last_login_days_ago = (current_time - user.last_login_at).days if user.last_login_at else 999
        
        # 并行查询各种统计数据
        stats_queries = [
            # 登录统计
            select(func.count(UserActivityLog.id)).where(
                and_(UserActivityLog.user_id == user_id, UserActivityLog.activity_type == ActivityType.LOGIN)
            ),
            # 策略统计
            select(func.count(Strategy.id)).where(Strategy.user_id == user_id),
            select(func.count(Strategy.id)).where(and_(Strategy.user_id == user_id, Strategy.is_active == True)),
            # 回测统计
            select(func.count(Backtest.id)).where(Backtest.user_id == user_id),
            # 交易统计
            select(func.count(Trade.id)).where(Trade.user_id == user_id),
            # AI使用统计
            select(func.count(ClaudeUsage.id)).where(ClaudeUsage.user_id == user_id)
        ]
        
        results = await asyncio.gather(*[self.db.execute(query) for query in stats_queries])
        
        total_logins = results[0].scalar() or 0
        total_strategies = results[1].scalar() or 0
        active_strategies = results[2].scalar() or 0
        total_backtests = results[3].scalar() or 0
        total_trades = results[4].scalar() or 0
        total_ai_usage = results[5].scalar() or 0
        
        # 计算频率和模式指标
        login_frequency = total_logins / max(registration_days, 1)
        ai_usage_frequency = total_ai_usage / max(registration_days, 1)
        
        # 计算活动多样性 (用户使用了多少种不同功能)
        activity_diversity = await self._calculate_activity_diversity(user_id)
        
        # 计算参与度 (综合多个指标)
        engagement_level = self._calculate_engagement_level(
            login_frequency, total_strategies, total_backtests, total_ai_usage
        )
        
        # 计算技术熟练度
        technical_proficiency = self._calculate_technical_proficiency(
            total_strategies, active_strategies, total_backtests, total_trades
        )
        
        return UserCharacteristics(
            user_id=user_id,
            registration_days=registration_days,
            total_logins=total_logins,
            login_frequency=login_frequency,
            last_login_days_ago=last_login_days_ago,
            total_strategies=total_strategies,
            active_strategies=active_strategies,
            total_backtests=total_backtests,
            total_trades=total_trades,
            total_ai_usage=total_ai_usage,
            ai_usage_frequency=ai_usage_frequency,
            membership_level=user.membership_level,
            is_email_verified=user.email_verified,
            is_active=user.is_active,
            activity_diversity=activity_diversity,
            engagement_level=engagement_level,
            technical_proficiency=technical_proficiency
        )
    
    async def _calculate_activity_diversity(self, user_id: int) -> float:
        """计算用户活动多样性"""
        try:
            # 查询用户使用过的不同活动类型数量
            activity_types_query = select(func.count(func.distinct(UserActivityLog.activity_type))).where(
                UserActivityLog.user_id == user_id
            )
            result = await self.db.execute(activity_types_query)
            unique_activities = result.scalar() or 0
            
            # 总共有多少种活动类型
            total_activity_types = len(ActivityType)
            
            return min(unique_activities / total_activity_types, 1.0)
            
        except Exception:
            return 0.0
    
    def _calculate_engagement_level(self, login_freq: float, strategies: int, backtests: int, ai_usage: int) -> float:
        """计算用户参与度"""
        # 加权计算参与度
        weights = {
            'login': 0.3,
            'strategy': 0.25,
            'backtest': 0.25,
            'ai': 0.2
        }
        
        # 标准化各项指标 (0-1)
        login_score = min(login_freq / 2.0, 1.0)  # 每天2次登录为满分
        strategy_score = min(strategies / 10.0, 1.0)  # 10个策略为满分
        backtest_score = min(backtests / 20.0, 1.0)  # 20次回测为满分
        ai_score = min(ai_usage / 50.0, 1.0)  # 50次AI使用为满分
        
        engagement = (
            login_score * weights['login'] +
            strategy_score * weights['strategy'] +
            backtest_score * weights['backtest'] +
            ai_score * weights['ai']
        )
        
        return round(engagement, 3)
    
    def _calculate_technical_proficiency(self, total_strategies: int, active_strategies: int, 
                                       backtests: int, trades: int) -> float:
        """计算技术熟练度"""
        # 基于策略数量、活跃度、回测和交易数量计算技术熟练度
        strategy_score = min(total_strategies / 15.0, 1.0)
        activity_score = (active_strategies / max(total_strategies, 1)) if total_strategies > 0 else 0
        backtest_score = min(backtests / 30.0, 1.0)
        trading_score = min(trades / 100.0, 1.0)
        
        proficiency = (strategy_score * 0.3 + activity_score * 0.2 + 
                      backtest_score * 0.3 + trading_score * 0.2)
        
        return round(proficiency, 3)
    
    def _generate_tag_recommendations(self, characteristics: UserCharacteristics) -> List[TagRecommendation]:
        """基于规则生成标签推荐"""
        recommendations = []
        
        for tag_name, rule in self.tag_rules.items():
            # 检查是否满足标签条件
            if self._check_tag_criteria(characteristics, rule["criteria"]):
                # 计算置信度
                confidence = self._calculate_confidence_score(characteristics, rule)
                
                # 生成推荐原因
                reason = self._generate_recommendation_reason(tag_name, characteristics, rule["criteria"])
                
                recommendation = TagRecommendation(
                    tag_name=tag_name,
                    confidence_score=confidence,
                    reason=reason,
                    auto_assign=rule["auto_assign"],
                    priority=rule["priority"]
                )
                
                recommendations.append(recommendation)
        
        # 按置信度和优先级排序
        recommendations.sort(key=lambda x: (x.confidence_score, x.priority), reverse=True)
        
        return recommendations
    
    def _check_tag_criteria(self, characteristics: UserCharacteristics, criteria: Dict[str, Any]) -> bool:
        """检查用户是否满足标签条件"""
        for field, conditions in criteria.items():
            value = getattr(characteristics, field, None)
            if value is None:
                continue
                
            # 检查最小值条件
            if "min" in conditions and value < conditions["min"]:
                return False
            
            # 检查最大值条件
            if "max" in conditions and value > conditions["max"]:
                return False
            
            # 检查包含条件
            if "in" in conditions and value not in conditions["in"]:
                return False
            
            # 检查等于条件
            if "eq" in conditions and value != conditions["eq"]:
                return False
        
        return True
    
    def _calculate_confidence_score(self, characteristics: UserCharacteristics, rule: Dict[str, Any]) -> float:
        """计算标签推荐置信度"""
        base_confidence = rule["confidence_base"]
        
        # 根据用户活跃度调整置信度
        activity_bonus = characteristics.engagement_level * 0.1
        
        # 根据数据完整性调整置信度
        data_completeness = 1.0  # 简化版本，假设数据完整
        
        confidence = min(base_confidence + activity_bonus, 1.0) * data_completeness
        
        return round(confidence, 3)
    
    def _generate_recommendation_reason(self, tag_name: str, characteristics: UserCharacteristics, 
                                      criteria: Dict[str, Any]) -> str:
        """生成推荐理由"""
        reasons = []
        
        # 根据具体的标签生成个性化理由
        if tag_name == "新用户":
            reasons.append(f"注册 {characteristics.registration_days} 天")
            reasons.append(f"总登录 {characteristics.total_logins} 次")
        elif tag_name == "活跃用户":
            reasons.append(f"平均每天登录 {characteristics.login_frequency:.1f} 次")
            reasons.append(f"最后登录 {characteristics.last_login_days_ago} 天前")
        elif tag_name == "策略达人":
            reasons.append(f"创建了 {characteristics.total_strategies} 个策略")
            reasons.append(f"其中 {characteristics.active_strategies} 个处于活跃状态")
        elif tag_name == "回测专家":
            reasons.append(f"执行了 {characteristics.total_backtests} 次回测")
        elif tag_name == "交易高手":
            reasons.append(f"执行了 {characteristics.total_trades} 笔交易")
        elif tag_name == "AI用户":
            reasons.append(f"使用AI功能 {characteristics.total_ai_usage} 次")
            reasons.append(f"AI使用频率 {DataValidator.safe_format_decimal(characteristics.ai_usage_frequency, decimals=2)} 次/天")
        elif tag_name == "高级会员":
            reasons.append(f"会员等级: {characteristics.membership_level}")
        elif tag_name == "沉睡用户":
            reasons.append(f"最后登录 {characteristics.last_login_days_ago} 天前")
        elif tag_name == "重度用户":
            reasons.append(f"参与度评分: {DataValidator.safe_format_decimal(characteristics.engagement_level, decimals=2)}")
            reasons.append(f"活动多样性: {DataValidator.safe_format_decimal(characteristics.activity_diversity, decimals=2)}")
        
        return "; ".join(reasons)
    
    async def _enhance_recommendations_with_ml(self, characteristics: UserCharacteristics, 
                                             recommendations: List[TagRecommendation]) -> List[TagRecommendation]:
        """使用机器学习模型增强推荐 (简化版本)"""
        # 这里是一个简化版本的ML增强
        # 在实际生产环境中，可以集成真正的ML模型
        
        enhanced = []
        for rec in recommendations:
            # 基于用户参与度调整置信度
            engagement_factor = 1.0 + (characteristics.engagement_level - 0.5) * 0.2
            enhanced_confidence = min(rec.confidence_score * engagement_factor, 1.0)
            
            enhanced_rec = TagRecommendation(
                tag_name=rec.tag_name,
                confidence_score=enhanced_confidence,
                reason=rec.reason,
                auto_assign=rec.auto_assign,
                priority=rec.priority
            )
            enhanced.append(enhanced_rec)
        
        return enhanced
    
    async def _filter_existing_tags(self, user_id: int, recommendations: List[TagRecommendation]) -> List[TagRecommendation]:
        """过滤用户已拥有的标签"""
        # 获取用户现有标签
        existing_tags_query = select(UserTag.name).join(UserTagAssignment).where(
            UserTagAssignment.user_id == user_id
        )
        result = await self.db.execute(existing_tags_query)
        existing_tag_names = {row[0] for row in result.fetchall()}
        
        # 过滤已存在的标签
        filtered_recommendations = [
            rec for rec in recommendations 
            if rec.tag_name not in existing_tag_names
        ]
        
        return filtered_recommendations
    
    async def auto_assign_recommended_tags(self, user_id: int, admin_id: Optional[int] = None) -> Dict[str, Any]:
        """自动分配推荐的标签"""
        try:
            characteristics, recommendations = await self.analyze_user_for_tagging(user_id)
            
            auto_assign_tags = [rec for rec in recommendations if rec.auto_assign and rec.confidence_score >= 0.7]
            
            successful_assignments = []
            failed_assignments = []
            
            for rec in auto_assign_tags:
                try:
                    # 查找或创建标签
                    tag = await self._get_or_create_system_tag(rec.tag_name)
                    
                    # 分配标签
                    success = await self.user_management_service.assign_tag_to_user(
                        user_id=user_id,
                        tag_id=tag.id,
                        assigned_by=admin_id,
                        assigned_reason=f"智能分析自动分配 (置信度: {DataValidator.safe_format_decimal(rec.confidence_score, decimals=2)}): {rec.reason}"
                    )
                    
                    if success:
                        successful_assignments.append({
                            "tag_name": rec.tag_name,
                            "confidence_score": rec.confidence_score,
                            "reason": rec.reason
                        })
                    else:
                        failed_assignments.append({
                            "tag_name": rec.tag_name,
                            "error": "分配失败，可能已存在"
                        })
                        
                except Exception as e:
                    failed_assignments.append({
                        "tag_name": rec.tag_name,
                        "error": str(e)
                    })
            
            result = {
                "user_id": user_id,
                "user_characteristics": {
                    "registration_days": characteristics.registration_days,
                    "engagement_level": characteristics.engagement_level,
                    "technical_proficiency": characteristics.technical_proficiency,
                    "activity_diversity": characteristics.activity_diversity
                },
                "total_recommendations": len(recommendations),
                "auto_assign_candidates": len(auto_assign_tags),
                "successful_assignments": successful_assignments,
                "failed_assignments": failed_assignments,
                "success_count": len(successful_assignments),
                "fail_count": len(failed_assignments)
            }
            
            logger.info(f"用户 {user_id} 智能标签分配完成: 成功 {len(successful_assignments)}, 失败 {len(failed_assignments)}")
            
            return result
            
        except Exception as e:
            logger.error(f"自动分配标签失败 (user_id: {user_id}): {e}")
            raise UserManagementError(f"自动分配标签失败: {str(e)}")
    
    async def _get_or_create_system_tag(self, tag_name: str) -> UserTag:
        """获取或创建系统标签"""
        # 查找现有标签
        tag_query = select(UserTag).where(UserTag.name == tag_name)
        result = await self.db.execute(tag_query)
        existing_tag = result.scalar_one_or_none()
        
        if existing_tag:
            return existing_tag
        
        # 创建新的系统标签
        tag_colors = {
            "新用户": "#10B981",      # 绿色
            "活跃用户": "#3B82F6",    # 蓝色  
            "策略达人": "#8B5CF6",    # 紫色
            "回测专家": "#F59E0B",    # 黄色
            "交易高手": "#EF4444",    # 红色
            "AI用户": "#06B6D4",      # 青色
            "高级会员": "#F97316",    # 橙色
            "沉睡用户": "#6B7280",    # 灰色
            "流失风险": "#DC2626",    # 深红色
            "重度用户": "#7C3AED"     # 深紫色
        }
        
        new_tag = UserTag(
            name=tag_name,
            display_name=tag_name,
            description=f"系统自动生成的 {tag_name} 标签",
            color=tag_colors.get(tag_name, "#6B7280"),
            tag_type=TagType.SYSTEM,
            is_active=True,
            user_count=0
        )
        
        self.db.add(new_tag)
        await self.db.flush()  # 获取ID
        
        return new_tag
    
    async def batch_auto_tag_users(self, user_ids: Optional[List[int]] = None, 
                                 admin_id: Optional[int] = None) -> Dict[str, Any]:
        """批量自动标签分配"""
        try:
            # 如果没有指定用户ID，则分析所有活跃用户
            if not user_ids:
                user_query = select(User.id).where(User.is_active == True)
                result = await self.db.execute(user_query)
                user_ids = [row[0] for row in result.fetchall()]
            
            logger.info(f"开始批量智能标签分析，用户数量: {len(user_ids)}")
            
            all_results = []
            total_successful = 0
            total_failed = 0
            
            # 批量处理用户
            batch_size = 10  # 每批处理10个用户
            for i in range(0, len(user_ids), batch_size):
                batch_user_ids = user_ids[i:i + batch_size]
                
                batch_tasks = [
                    self.auto_assign_recommended_tags(user_id, admin_id)
                    for user_id in batch_user_ids
                ]
                
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for user_id, result in zip(batch_user_ids, batch_results):
                    if isinstance(result, Exception):
                        all_results.append({
                            "user_id": user_id,
                            "success": False,
                            "error": str(result)
                        })
                        total_failed += 1
                    else:
                        all_results.append({
                            "user_id": user_id,
                            "success": True,
                            "data": result
                        })
                        total_successful += result["success_count"]
                        total_failed += result["fail_count"]
            
            summary = {
                "total_users_processed": len(user_ids),
                "total_tag_assignments": total_successful,
                "total_failures": total_failed,
                "success_rate": round(total_successful / max(total_successful + total_failed, 1) * 100, 2),
                "detailed_results": all_results,
                "processed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"批量智能标签分析完成: 处理 {len(user_ids)} 用户, 成功分配 {total_successful} 个标签")
            
            return summary
            
        except Exception as e:
            logger.error(f"批量自动标签分配失败: {e}")
            raise UserManagementError(f"批量标签分配失败: {str(e)}")