"""
用户管理服务 - 核心用户管理系统业务逻辑
提供360度用户管理、智能标签、行为分析、批量操作等企业级功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload, joinedload

from app.models.user import User
from app.models.user_management import (
    UserTag, UserTagAssignment, UserActivityLog, UserStatisticsSnapshot,
    UserNotification, UserBehaviorProfile, TagType, ActivityType,
    NotificationType, NotificationChannel, NotificationStatus
)
from app.models.strategy import Strategy
from app.models.trade import Trade
from app.models.backtest import Backtest
from app.models.api_key import ApiKey
from app.models.claude_proxy import ClaudeUsageLog
from app.core.exceptions import UserManagementError

logger = logging.getLogger(__name__)


class UserManagementService:
    """用户管理服务 - 企业级用户生命周期管理"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    # ========== 核心用户管理 ==========
    
    async def get_user_comprehensive_info(self, user_id: int) -> Dict[str, Any]:
        """获取用户360度全息信息"""
        try:
            # 基础用户信息
            user_query = select(User).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                raise UserManagementError(f"用户 {user_id} 不存在")
            
            # 并行查询相关信息
            user_info_tasks = [
                self._get_user_basic_stats(user_id),
                self._get_user_tags(user_id),
                self._get_user_recent_activity(user_id, limit=20),
                self._get_user_behavior_profile(user_id),
                self._get_user_latest_stats_snapshot(user_id)
            ]
            
            basic_stats, tags, recent_activity, behavior_profile, latest_snapshot = await asyncio.gather(*user_info_tasks)
            
            # 构建完整用户信息
            comprehensive_info = {
                # 基础信息
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "phone": user.phone,
                    "avatar_url": user.avatar_url,
                    "membership_level": user.membership_level,
                    "membership_expires_at": user.membership_expires_at.isoformat() if user.membership_expires_at else None,
                    "email_verified": user.email_verified,
                    "is_active": user.is_active,
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                },
                
                # 统计信息
                "statistics": basic_stats,
                
                # 最新快照
                "latest_snapshot": latest_snapshot,
                
                # 用户标签
                "tags": tags,
                
                # 最近活动
                "recent_activity": recent_activity,
                
                # 行为画像
                "behavior_profile": behavior_profile
            }
            
            return comprehensive_info
            
        except Exception as e:
            logger.error(f"获取用户 {user_id} 360度信息失败: {e}")
            raise UserManagementError(f"获取用户信息失败: {str(e)}")
    
    async def _get_user_basic_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户基础统计信息"""
        stats = {}
        
        # 策略统计
        strategy_query = select(func.count(Strategy.id)).where(Strategy.user_id == user_id)
        active_strategy_query = select(func.count(Strategy.id)).where(
            and_(Strategy.user_id == user_id, Strategy.is_active == True)
        )
        
        # 交易统计
        trade_query = select(func.count(Trade.id)).where(Trade.user_id == user_id)
        
        # 回测统计
        backtest_query = select(func.count(Backtest.id)).where(Backtest.user_id == user_id)
        
        # API密钥统计
        api_key_query = select(func.count(ApiKey.id)).where(ApiKey.user_id == user_id)
        active_api_key_query = select(func.count(ApiKey.id)).where(
            and_(ApiKey.user_id == user_id, ApiKey.is_active == True)
        )
        
        # AI使用统计
        ai_usage_query = select(func.count(ClaudeUsageLog.id)).where(ClaudeUsageLog.user_id == user_id)
        
        # 执行查询
        results = await asyncio.gather(
            self.db.execute(strategy_query),
            self.db.execute(active_strategy_query), 
            self.db.execute(trade_query),
            self.db.execute(backtest_query),
            self.db.execute(api_key_query),
            self.db.execute(active_api_key_query),
            self.db.execute(ai_usage_query)
        )
        
        stats = {
            "total_strategies": results[0].scalar() or 0,
            "active_strategies": results[1].scalar() or 0,
            "total_trades": results[2].scalar() or 0,
            "total_backtests": results[3].scalar() or 0,
            "total_api_keys": results[4].scalar() or 0,
            "active_api_keys": results[5].scalar() or 0,
            "total_ai_usages": results[6].scalar() or 0
        }
        
        return stats
    
    async def _get_user_tags(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户标签信息"""
        query = select(UserTag).join(UserTagAssignment).where(
            UserTagAssignment.user_id == user_id
        ).options(selectinload(UserTag.tag_assignments))
        
        result = await self.db.execute(query)
        tags = result.scalars().all()
        
        tag_list = []
        for tag in tags:
            # 获取该用户的标签分配信息
            assignment_query = select(UserTagAssignment).where(
                and_(
                    UserTagAssignment.user_id == user_id,
                    UserTagAssignment.tag_id == tag.id
                )
            )
            assignment_result = await self.db.execute(assignment_query)
            assignment = assignment_result.scalar_one()
            
            tag_list.append({
                "id": tag.id,
                "name": tag.name,
                "display_name": tag.display_name,
                "description": tag.description,
                "color": tag.color,
                "tag_type": tag.tag_type.value,
                "assigned_at": assignment.assigned_at.isoformat(),
                "assigned_reason": assignment.assigned_reason,
                "auto_assigned": assignment.auto_assigned,
                "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None
            })
            
        return tag_list
    
    async def _get_user_recent_activity(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户最近活动"""
        query = select(UserActivityLog).where(
            UserActivityLog.user_id == user_id
        ).order_by(desc(UserActivityLog.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        activities = result.scalars().all()
        
        activity_list = []
        for activity in activities:
            activity_list.append({
                "id": activity.id,
                "activity_type": activity.activity_type.value,
                "activity_description": activity.activity_description,
                "ip_address": activity.ip_address,
                "resource_type": activity.resource_type,
                "resource_id": activity.resource_id,
                "is_successful": activity.is_successful,
                "error_message": activity.error_message,
                "created_at": activity.created_at.isoformat(),
                "additional_data": activity.additional_data
            })
            
        return activity_list
    
    async def _get_user_behavior_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户行为画像"""
        query = select(UserBehaviorProfile).where(UserBehaviorProfile.user_id == user_id)
        result = await self.db.execute(query)
        profile = result.scalar_one_or_none()
        
        if not profile:
            return None
            
        return {
            "id": profile.id,
            "user_type": profile.user_type,
            "activity_level": profile.activity_level,
            "engagement_score": float(profile.engagement_score) if profile.engagement_score else 0,
            "trading_style": profile.trading_style,
            "risk_preference": profile.risk_preference,
            "preferred_timeframe": profile.preferred_timeframe,
            "preferred_instruments": profile.preferred_instruments,
            "preferred_features": profile.preferred_features,
            "usage_patterns": profile.usage_patterns,
            "peak_activity_hours": profile.peak_activity_hours,
            "ai_usage_frequency": profile.ai_usage_frequency,
            "preferred_ai_features": profile.preferred_ai_features,
            "ai_interaction_style": profile.ai_interaction_style,
            "lifetime_value_score": float(profile.lifetime_value_score) if profile.lifetime_value_score else 0,
            "churn_risk_score": float(profile.churn_risk_score) if profile.churn_risk_score else 0,
            "upsell_potential_score": float(profile.upsell_potential_score) if profile.upsell_potential_score else 0,
            "last_analyzed_at": profile.last_analyzed_at.isoformat() if profile.last_analyzed_at else None,
            "analysis_version": profile.analysis_version,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
        }
    
    async def _get_user_latest_stats_snapshot(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户最新统计快照"""
        query = select(UserStatisticsSnapshot).where(
            UserStatisticsSnapshot.user_id == user_id
        ).order_by(desc(UserStatisticsSnapshot.snapshot_date)).limit(1)
        
        result = await self.db.execute(query)
        snapshot = result.scalar_one_or_none()
        
        if not snapshot:
            return None
            
        return {
            "id": snapshot.id,
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "total_strategies": snapshot.total_strategies,
            "active_strategies": snapshot.active_strategies,
            "total_backtests": snapshot.total_backtests,
            "total_trades": snapshot.total_trades,
            "login_count_30d": snapshot.login_count_30d,
            "last_login_days_ago": snapshot.last_login_days_ago,
            "active_days_30d": snapshot.active_days_30d,
            "ai_chat_count_30d": snapshot.ai_chat_count_30d,
            "ai_cost_30d": float(snapshot.ai_cost_30d) if snapshot.ai_cost_30d else 0,
            "feature_usage": snapshot.feature_usage,
            "total_pnl": float(snapshot.total_pnl) if snapshot.total_pnl else 0,
            "win_rate": float(snapshot.win_rate) if snapshot.win_rate else None,
            "avg_trade_amount": float(snapshot.avg_trade_amount) if snapshot.avg_trade_amount else 0,
            "membership_level": snapshot.membership_level,
            "membership_days_left": snapshot.membership_days_left,
            "risk_score": float(snapshot.risk_score) if snapshot.risk_score else 0,
            "account_health_score": float(snapshot.account_health_score) if snapshot.account_health_score else 100,
            "created_at": snapshot.created_at.isoformat()
        }
    
    # ========== 用户列表和搜索 ==========
    
    async def get_users_with_advanced_filtering(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        membership_levels: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        email_verified: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        last_login_after: Optional[datetime] = None,
        last_login_before: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """高级用户筛选和搜索"""
        
        try:
            # 构建基础查询
            base_query = select(User)
            count_query = select(func.count(User.id))
            
            # 构建WHERE条件
            conditions = []
            
            # 文本搜索
            if search:
                search_condition = or_(
                    User.username.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.phone.ilike(f"%{search}%")
                )
                conditions.append(search_condition)
            
            # 会员级别筛选
            if membership_levels:
                conditions.append(User.membership_level.in_(membership_levels))
            
            # 活跃状态筛选
            if is_active is not None:
                conditions.append(User.is_active == is_active)
            
            # 邮箱验证状态筛选
            if email_verified is not None:
                conditions.append(User.email_verified == email_verified)
            
            # 创建时间筛选
            if created_after:
                conditions.append(User.created_at >= created_after)
            if created_before:
                conditions.append(User.created_at <= created_before)
                
            # 最后登录时间筛选
            if last_login_after:
                conditions.append(User.last_login_at >= last_login_after)
            if last_login_before:
                conditions.append(User.last_login_at <= last_login_before)
            
            # 标签筛选
            if tags:
                # 子查询：拥有指定标签的用户
                tag_subquery = select(UserTagAssignment.user_id).join(UserTag).where(
                    UserTag.name.in_(tags)
                )
                conditions.append(User.id.in_(tag_subquery))
            
            # 应用所有条件
            if conditions:
                base_query = base_query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))
            
            # 排序
            sort_column = getattr(User, sort_by, User.created_at)
            if sort_order.lower() == "asc":
                base_query = base_query.order_by(asc(sort_column))
            else:
                base_query = base_query.order_by(desc(sort_column))
            
            # 分页
            offset = (page - 1) * page_size
            base_query = base_query.offset(offset).limit(page_size)
            
            # 执行查询
            users_result = await self.db.execute(base_query)
            count_result = await self.db.execute(count_query)
            
            users = users_result.scalars().all()
            total_count = count_result.scalar()
            
            # 获取用户的标签信息
            user_data = []
            for user in users:
                tags_info = await self._get_user_tags(user.id)
                user_data.append({
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "phone": user.phone,
                    "avatar_url": user.avatar_url,
                    "membership_level": user.membership_level,
                    "membership_expires_at": user.membership_expires_at.isoformat() if user.membership_expires_at else None,
                    "email_verified": user.email_verified,
                    "is_active": user.is_active,
                    "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                    "tags": tags_info
                })
            
            return {
                "users": user_data,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": page * page_size < total_count,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"高级用户搜索失败: {e}")
            raise UserManagementError(f"用户搜索失败: {str(e)}")
    
    # ========== 用户标签管理 ==========
    
    async def create_user_tag(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        color: str = "#3B82F6",
        tag_type: TagType = TagType.MANUAL,
        auto_assign_rule: Optional[Dict[str, Any]] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """创建用户标签"""
        
        try:
            # 检查标签名称是否已存在
            existing_query = select(UserTag).where(UserTag.name == name)
            existing_result = await self.db.execute(existing_query)
            existing_tag = existing_result.scalar_one_or_none()
            
            if existing_tag:
                raise UserManagementError(f"标签名称 '{name}' 已存在")
            
            # 创建新标签
            new_tag = UserTag(
                name=name,
                display_name=display_name,
                description=description,
                color=color,
                tag_type=tag_type,
                auto_assign_rule=auto_assign_rule,
                created_by=created_by
            )
            
            self.db.add(new_tag)
            await self.db.flush()  # 获取ID
            await self.db.commit()
            
            logger.info(f"创建用户标签成功: {name} (ID: {new_tag.id})")
            
            return {
                "id": new_tag.id,
                "name": new_tag.name,
                "display_name": new_tag.display_name,
                "description": new_tag.description,
                "color": new_tag.color,
                "tag_type": new_tag.tag_type.value,
                "auto_assign_rule": new_tag.auto_assign_rule,
                "user_count": 0,
                "created_by": new_tag.created_by,
                "created_at": new_tag.created_at.isoformat()
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建用户标签失败: {e}")
            raise UserManagementError(f"创建标签失败: {str(e)}")
    
    async def assign_tag_to_user(
        self,
        user_id: int,
        tag_id: int,
        assigned_by: Optional[int] = None,
        assigned_reason: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """为用户分配标签"""
        
        try:
            # 验证用户存在
            user_query = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise UserManagementError(f"用户 {user_id} 不存在")
            
            # 验证标签存在
            tag_query = select(UserTag).where(UserTag.id == tag_id)
            tag_result = await self.db.execute(tag_query)
            tag = tag_result.scalar_one_or_none()
            
            if not tag:
                raise UserManagementError(f"标签 {tag_id} 不存在")
            
            # 检查是否已分配
            existing_query = select(UserTagAssignment).where(
                and_(
                    UserTagAssignment.user_id == user_id,
                    UserTagAssignment.tag_id == tag_id
                )
            )
            existing_result = await self.db.execute(existing_query)
            existing_assignment = existing_result.scalar_one_or_none()
            
            if existing_assignment:
                logger.warning(f"用户 {user_id} 已拥有标签 {tag_id}")
                return False
            
            # 创建新的标签分配
            new_assignment = UserTagAssignment(
                user_id=user_id,
                tag_id=tag_id,
                assigned_by=assigned_by,
                assigned_reason=assigned_reason,
                expires_at=expires_at
            )
            
            self.db.add(new_assignment)
            
            # 更新标签用户数量
            await self.db.execute(
                update(UserTag)
                .where(UserTag.id == tag_id)
                .values(user_count=UserTag.user_count + 1)
            )
            
            await self.db.commit()
            
            logger.info(f"为用户 {user_id} 分配标签 {tag_id} 成功")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"分配标签失败: {e}")
            raise UserManagementError(f"分配标签失败: {str(e)}")
    
    async def remove_tag_from_user(self, user_id: int, tag_id: int) -> bool:
        """移除用户标签"""
        
        try:
            # 查找现有分配
            assignment_query = select(UserTagAssignment).where(
                and_(
                    UserTagAssignment.user_id == user_id,
                    UserTagAssignment.tag_id == tag_id
                )
            )
            assignment_result = await self.db.execute(assignment_query)
            assignment = assignment_result.scalar_one_or_none()
            
            if not assignment:
                logger.warning(f"用户 {user_id} 没有标签 {tag_id}")
                return False
            
            # 删除标签分配
            await self.db.execute(
                delete(UserTagAssignment).where(UserTagAssignment.id == assignment.id)
            )
            
            # 更新标签用户数量
            await self.db.execute(
                update(UserTag)
                .where(UserTag.id == tag_id)
                .values(user_count=UserTag.user_count - 1)
            )
            
            await self.db.commit()
            
            logger.info(f"移除用户 {user_id} 的标签 {tag_id} 成功")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"移除用户标签失败: {e}")
            raise UserManagementError(f"移除标签失败: {str(e)}")
    
    # ========== 用户行为记录 ==========
    
    async def log_user_activity(
        self,
        user_id: int,
        activity_type: ActivityType,
        activity_description: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referer: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        is_successful: bool = True,
        error_message: Optional[str] = None
    ) -> bool:
        """记录用户活动日志"""
        
        try:
            activity_log = UserActivityLog(
                user_id=user_id,
                activity_type=activity_type,
                activity_description=activity_description,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
                resource_type=resource_type,
                resource_id=resource_id,
                additional_data=additional_data,
                is_successful=is_successful,
                error_message=error_message
            )
            
            self.db.add(activity_log)
            await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"记录用户活动日志失败: {e}")
            return False
    
    # ========== 用户批量操作 ==========
    
    async def batch_update_users(
        self,
        user_ids: List[int],
        updates: Dict[str, Any],
        updated_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """批量更新用户信息"""
        
        try:
            successful_updates = []
            failed_updates = []
            
            # 验证更新字段
            allowed_fields = {
                'membership_level', 'membership_expires_at', 'is_active',
                'email_verified', 'phone'
            }
            invalid_fields = set(updates.keys()) - allowed_fields
            if invalid_fields:
                raise UserManagementError(f"不允许更新的字段: {invalid_fields}")
            
            # 批量更新
            for user_id in user_ids:
                try:
                    # 验证用户存在
                    user_query = select(User).where(User.id == user_id)
                    user_result = await self.db.execute(user_query)
                    user = user_result.scalar_one_or_none()
                    
                    if not user:
                        failed_updates.append({
                            "user_id": user_id,
                            "error": "用户不存在"
                        })
                        continue
                    
                    # 执行更新
                    await self.db.execute(
                        update(User).where(User.id == user_id).values(**updates)
                    )
                    
                    successful_updates.append(user_id)
                    
                    # 记录活动日志
                    await self.log_user_activity(
                        user_id=user_id,
                        activity_type=ActivityType.PROFILE_UPDATE,
                        activity_description=f"管理员批量更新用户信息: {list(updates.keys())}",
                        additional_data={
                            "updated_fields": list(updates.keys()),
                            "updated_by": updated_by
                        }
                    )
                    
                except Exception as e:
                    failed_updates.append({
                        "user_id": user_id,
                        "error": str(e)
                    })
            
            await self.db.commit()
            
            result = {
                "total_requested": len(user_ids),
                "successful_count": len(successful_updates),
                "failed_count": len(failed_updates),
                "successful_user_ids": successful_updates,
                "failed_updates": failed_updates
            }
            
            logger.info(f"批量更新用户完成: 成功 {len(successful_updates)}, 失败 {len(failed_updates)}")
            return result
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"批量更新用户失败: {e}")
            raise UserManagementError(f"批量更新失败: {str(e)}")
    
    async def batch_assign_tags(
        self,
        user_ids: List[int],
        tag_ids: List[int],
        assigned_by: Optional[int] = None,
        assigned_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """批量为用户分配标签"""
        
        try:
            successful_assignments = []
            failed_assignments = []
            
            for user_id in user_ids:
                for tag_id in tag_ids:
                    try:
                        success = await self.assign_tag_to_user(
                            user_id=user_id,
                            tag_id=tag_id,
                            assigned_by=assigned_by,
                            assigned_reason=assigned_reason
                        )
                        
                        if success:
                            successful_assignments.append({
                                "user_id": user_id,
                                "tag_id": tag_id
                            })
                        else:
                            failed_assignments.append({
                                "user_id": user_id,
                                "tag_id": tag_id,
                                "error": "标签已存在或其他原因"
                            })
                            
                    except Exception as e:
                        failed_assignments.append({
                            "user_id": user_id,
                            "tag_id": tag_id,
                            "error": str(e)
                        })
            
            result = {
                "total_requested": len(user_ids) * len(tag_ids),
                "successful_count": len(successful_assignments),
                "failed_count": len(failed_assignments),
                "successful_assignments": successful_assignments,
                "failed_assignments": failed_assignments
            }
            
            logger.info(f"批量分配标签完成: 成功 {len(successful_assignments)}, 失败 {len(failed_assignments)}")
            return result
            
        except Exception as e:
            logger.error(f"批量分配标签失败: {e}")
            raise UserManagementError(f"批量分配标签失败: {str(e)}")
    
    # ========== 用户统计与分析 ==========
    
    async def generate_user_statistics_snapshot(self, user_id: int) -> Dict[str, Any]:
        """生成用户统计快照"""
        
        try:
            current_time = datetime.utcnow()
            thirty_days_ago = current_time - timedelta(days=30)
            
            # 获取基础统计
            basic_stats = await self._get_user_basic_stats(user_id)
            
            # 获取用户信息
            user_query = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                raise UserManagementError(f"用户 {user_id} 不存在")
            
            # 30天活动统计
            login_count_query = select(func.count(UserActivityLog.id)).where(
                and_(
                    UserActivityLog.user_id == user_id,
                    UserActivityLog.activity_type == ActivityType.LOGIN,
                    UserActivityLog.created_at >= thirty_days_ago
                )
            )
            login_count_result = await self.db.execute(login_count_query)
            login_count_30d = login_count_result.scalar() or 0
            
            # AI对话统计
            ai_chat_query = select(func.count(UserActivityLog.id)).where(
                and_(
                    UserActivityLog.user_id == user_id,
                    UserActivityLog.activity_type == ActivityType.AI_CHAT,
                    UserActivityLog.created_at >= thirty_days_ago
                )
            )
            ai_chat_result = await self.db.execute(ai_chat_query)
            ai_chat_count_30d = ai_chat_result.scalar() or 0
            
            # AI成本统计
            ai_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
                and_(
                    ClaudeUsageLog.user_id == user_id,
                    ClaudeUsageLog.request_date >= thirty_days_ago
                )
            )
            ai_cost_result = await self.db.execute(ai_cost_query)
            ai_cost_30d = ai_cost_result.scalar() or Decimal('0')
            
            # 计算活跃天数（简化实现）
            active_days_query = select(func.count(func.distinct(func.date(UserActivityLog.created_at)))).where(
                and_(
                    UserActivityLog.user_id == user_id,
                    UserActivityLog.created_at >= thirty_days_ago
                )
            )
            active_days_result = await self.db.execute(active_days_query)
            active_days_30d = active_days_result.scalar() or 0
            
            # 最后登录距今天数
            last_login_days_ago = None
            if user.last_login_at:
                last_login_days_ago = (current_time - user.last_login_at).days
            
            # 会员剩余天数
            membership_days_left = None
            if user.membership_expires_at:
                membership_days_left = max(0, (user.membership_expires_at - current_time).days)
            
            # 创建统计快照
            snapshot = UserStatisticsSnapshot(
                user_id=user_id,
                snapshot_date=current_time,
                total_strategies=basic_stats['total_strategies'],
                active_strategies=basic_stats['active_strategies'],
                total_backtests=basic_stats['total_backtests'],
                total_trades=basic_stats['total_trades'],
                login_count_30d=login_count_30d,
                last_login_days_ago=last_login_days_ago,
                active_days_30d=active_days_30d,
                ai_chat_count_30d=ai_chat_count_30d,
                ai_cost_30d=ai_cost_30d,
                membership_level=user.membership_level,
                membership_days_left=membership_days_left,
                # 默认评分
                risk_score=Decimal('0'),
                account_health_score=Decimal('100')
            )
            
            self.db.add(snapshot)
            await self.db.commit()
            
            logger.info(f"生成用户 {user_id} 统计快照成功")
            
            return {
                "id": snapshot.id,
                "user_id": user_id,
                "snapshot_date": snapshot.snapshot_date.isoformat(),
                "statistics": {
                    "total_strategies": snapshot.total_strategies,
                    "active_strategies": snapshot.active_strategies,
                    "total_backtests": snapshot.total_backtests,
                    "total_trades": snapshot.total_trades,
                    "login_count_30d": snapshot.login_count_30d,
                    "active_days_30d": snapshot.active_days_30d,
                    "ai_chat_count_30d": snapshot.ai_chat_count_30d,
                    "ai_cost_30d": float(snapshot.ai_cost_30d),
                    "membership_level": snapshot.membership_level,
                    "membership_days_left": snapshot.membership_days_left,
                    "risk_score": float(snapshot.risk_score),
                    "account_health_score": float(snapshot.account_health_score)
                }
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"生成用户统计快照失败: {e}")
            raise UserManagementError(f"生成统计快照失败: {str(e)}")
    
    async def get_user_management_dashboard_stats(self) -> Dict[str, Any]:
        """获取用户管理仪表板统计信息"""
        
        try:
            current_time = datetime.utcnow()
            thirty_days_ago = current_time - timedelta(days=30)
            seven_days_ago = current_time - timedelta(days=7)
            
            # 并行查询各种统计信息
            stats_queries = [
                # 用户总数
                select(func.count(User.id)),
                # 活跃用户数
                select(func.count(User.id)).where(User.is_active == True),
                # 已验证邮箱用户数
                select(func.count(User.id)).where(User.email_verified == True),
                # 30天新用户数
                select(func.count(User.id)).where(User.created_at >= thirty_days_ago),
                # 7天新用户数
                select(func.count(User.id)).where(User.created_at >= seven_days_ago),
                # 30天活跃用户数（有登录记录）
                select(func.count(func.distinct(UserActivityLog.user_id))).where(
                    and_(
                        UserActivityLog.activity_type == ActivityType.LOGIN,
                        UserActivityLog.created_at >= thirty_days_ago
                    )
                ),
                # 各会员等级分布
                select(User.membership_level, func.count(User.id)).group_by(User.membership_level)
            ]
            
            results = await asyncio.gather(*[self.db.execute(query) for query in stats_queries[:-1]])
            membership_result = await self.db.execute(stats_queries[-1])
            
            # 处理会员等级分布
            membership_distribution = {}
            for level, count in membership_result.all():
                membership_distribution[level] = count
            
            # 标签统计
            tag_stats_query = select(func.count(UserTag.id))
            tag_result = await self.db.execute(tag_stats_query)
            total_tags = tag_result.scalar()
            
            return {
                "user_statistics": {
                    "total_users": results[0].scalar() or 0,
                    "active_users": results[1].scalar() or 0,
                    "verified_users": results[2].scalar() or 0,
                    "new_users_30d": results[3].scalar() or 0,
                    "new_users_7d": results[4].scalar() or 0,
                    "active_users_30d": results[5].scalar() or 0,
                    "membership_distribution": membership_distribution,
                    "total_tags": total_tags
                },
                "growth_metrics": {
                    "user_growth_rate_30d": self._calculate_growth_rate(results[3].scalar() or 0, results[0].scalar() or 0),
                    "active_rate": self._calculate_percentage(results[1].scalar() or 0, results[0].scalar() or 0),
                    "verification_rate": self._calculate_percentage(results[2].scalar() or 0, results[0].scalar() or 0)
                },
                "generated_at": current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取用户管理仪表板统计失败: {e}")
            raise UserManagementError(f"获取仪表板统计失败: {str(e)}")
    
    def _calculate_growth_rate(self, new_count: int, total_count: int) -> float:
        """计算增长率"""
        if total_count == 0:
            return 0.0
        return round((new_count / total_count) * 100, 2)
    
    def _calculate_percentage(self, part: int, total: int) -> float:
        """计算百分比"""
        if total == 0:
            return 0.0
        return round((part / total) * 100, 2)