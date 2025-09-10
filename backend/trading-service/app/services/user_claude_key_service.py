"""
用户Claude Key管理服务
- 自动分配虚拟Claude Key
- 使用量统计和限制检查
- 与Claude账号池的路由集成
"""

import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

from app.models.claude_proxy import UserClaudeKey, ClaudeAccount, ClaudeUsageLog
from app.models.user import User
from app.services.claude_account_service import ClaudeAccountService
from app.services.membership_service import MembershipService
from app.services.intelligent_claude_scheduler import (
    IntelligentClaudeScheduler, 
    SchedulingContext, 
    SchedulingStrategy
)


class UserClaudeKeyService:
    """用户Claude Key服务 - 虚拟密钥管理和使用统计"""
    
    @staticmethod
    def generate_virtual_key(user_id: int, key_name: str = "default") -> str:
        """
        生成虚拟Claude Key - 兼容claude-relay-service格式
        格式: ck-{user_id}-{random_string}
        """
        random_part = secrets.token_urlsafe(32)
        virtual_key = f"ck-{user_id}-{random_part}"
        return virtual_key
    
    @staticmethod
    async def create_user_claude_key(
        db: AsyncSession,
        user_id: int,
        key_name: str = "Default API Key",
        description: str = None
    ) -> UserClaudeKey:
        """
        为用户创建虚拟Claude Key
        """
        # 生成虚拟密钥
        virtual_key = UserClaudeKeyService.generate_virtual_key(user_id, key_name)
        
        # 获取用户会员等级限制
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"用户 {user_id} 不存在")
            
        limits = MembershipService.get_membership_limits(user.membership_level)
        
        # 创建虚拟密钥记录
        user_key = UserClaudeKey(
            user_id=user_id,
            virtual_key=virtual_key,
            key_name=key_name,
            description=description,
            status="active",
            daily_request_limit=getattr(limits, 'ai_requests_per_day', None),
            daily_token_limit=getattr(limits, 'ai_tokens_per_day', None), 
            daily_cost_limit=getattr(limits, 'ai_daily_limit', None),
            usage_reset_date=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        
        db.add(user_key)
        await db.commit()
        await db.refresh(user_key)
        
        return user_key
    
    @staticmethod
    async def auto_allocate_key_for_new_user(db: AsyncSession, user_id: int) -> UserClaudeKey:
        """
        新用户注册后自动分配Claude Key
        """
        # 检查用户是否已有虚拟密钥
        existing_key_stmt = select(UserClaudeKey).where(
            and_(
                UserClaudeKey.user_id == user_id,
                UserClaudeKey.status == "active"
            )
        )
        result = await db.execute(existing_key_stmt)
        existing_key = result.scalar_one_or_none()
        
        if existing_key:
            return existing_key
            
        # 创建默认虚拟密钥
        return await UserClaudeKeyService.create_user_claude_key(
            db=db,
            user_id=user_id,
            key_name="Default API Key", 
            description="自动分配的默认Claude API密钥"
        )
    
    @staticmethod
    async def get_user_key_by_virtual_key(
        db: AsyncSession, 
        virtual_key: str
    ) -> Optional[UserClaudeKey]:
        """
        通过虚拟密钥获取用户密钥记录
        """
        stmt = select(UserClaudeKey).where(
            and_(
                UserClaudeKey.virtual_key == virtual_key,
                UserClaudeKey.status == "active"
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_keys(db: AsyncSession, user_id: int) -> List[UserClaudeKey]:
        """
        获取用户的所有虚拟密钥
        """
        stmt = select(UserClaudeKey).where(UserClaudeKey.user_id == user_id).order_by(
            desc(UserClaudeKey.created_at)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_user_virtual_key(db: AsyncSession, user_id: int) -> Optional[str]:
        """
        获取用户的活跃虚拟密钥 - 用于AI请求路由
        如果用户没有虚拟密钥，自动创建一个
        """
        # 查找用户的活跃虚拟密钥
        stmt = select(UserClaudeKey).where(
            and_(
                UserClaudeKey.user_id == user_id,
                UserClaudeKey.status == "active"
            )
        ).order_by(desc(UserClaudeKey.created_at))
        
        result = await db.execute(stmt)
        user_key = result.scalar_one_or_none()
        
        if user_key:
            return user_key.virtual_key
        
        # 如果没有虚拟密钥，自动创建一个
        try:
            new_key = await UserClaudeKeyService.auto_allocate_key_for_new_user(db, user_id)
            return new_key.virtual_key
        except Exception as e:
            # 创建失败，返回None让上层处理
            print(f"自动创建虚拟密钥失败 - 用户ID: {user_id}, 错误: {str(e)}")
            return None
    
    @staticmethod
    async def check_usage_limits(
        db: AsyncSession,
        user_key: UserClaudeKey,
        estimated_tokens: int = 0,
        estimated_cost: Decimal = Decimal('0')
    ) -> Dict[str, Any]:
        """
        检查使用限制
        """
        # 重置每日统计(如果需要)
        await UserClaudeKeyService._reset_daily_usage_if_needed(db, user_key)
        
        # 检查各项限制
        checks = {
            "can_proceed": True,
            "limit_exceeded": [],
            "remaining": {},
            "warnings": []
        }
        
        # 检查每日请求限制
        if user_key.daily_request_limit:
            if user_key.today_requests >= user_key.daily_request_limit:
                checks["can_proceed"] = False
                checks["limit_exceeded"].append("daily_requests")
            checks["remaining"]["daily_requests"] = max(0, user_key.daily_request_limit - user_key.today_requests)
        
        # 检查每日token限制
        if user_key.daily_token_limit:
            projected_tokens = user_key.today_tokens + estimated_tokens
            if projected_tokens > user_key.daily_token_limit:
                checks["can_proceed"] = False
                checks["limit_exceeded"].append("daily_tokens")
            checks["remaining"]["daily_tokens"] = max(0, user_key.daily_token_limit - user_key.today_tokens)
        
        # 检查每日成本限制
        if user_key.daily_cost_limit:
            projected_cost = user_key.today_cost_usd + estimated_cost
            if projected_cost > user_key.daily_cost_limit:
                checks["can_proceed"] = False
                checks["limit_exceeded"].append("daily_cost")
            checks["remaining"]["daily_cost"] = float(max(Decimal('0'), user_key.daily_cost_limit - user_key.today_cost_usd))
        
        # 警告(接近限制)
        if user_key.daily_request_limit and checks.get("remaining", {}).get("daily_requests", 0) <= 5:
            checks["warnings"].append("请求次数即将达到每日限制")
            
        if user_key.daily_cost_limit:
            remaining_cost = checks.get("remaining", {}).get("daily_cost", 0)
            if remaining_cost <= 1.0:  # 少于$1
                checks["warnings"].append("每日成本即将达到限制")
        
        return checks
    
    @staticmethod
    async def log_usage(
        db: AsyncSession,
        user_key: UserClaudeKey,
        claude_account: ClaudeAccount,
        request_id: str,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        api_cost_usd: Decimal,
        charged_cost_usd: Decimal = None,
        success: bool = True,
        error_code: str = None,
        error_message: str = None,
        response_time_ms: int = None,
        session_id: str = None,
        ai_mode: str = None,
        request_content_hash: str = None,
        response_content_hash: str = None
    ) -> ClaudeUsageLog:
        """
        记录用户Claude使用情况
        """
        if charged_cost_usd is None:
            charged_cost_usd = api_cost_usd
            
        total_tokens = input_tokens + output_tokens
        
        # 创建使用记录
        usage_log = ClaudeUsageLog(
            account_id=claude_account.id,
            user_id=user_key.user_id,
            request_type=request_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            api_cost=api_cost_usd,
            response_time=response_time_ms,
            success=success,
            error_code=error_code,
            error_message=error_message,
            request_date=datetime.now()
        )
        
        db.add(usage_log)
        
        # 更新用户密钥的统计信息
        user_key.total_requests += 1
        if success:
            user_key.successful_requests += 1
        else:
            user_key.failed_requests += 1
            
        user_key.total_tokens += total_tokens
        user_key.total_cost_usd += charged_cost_usd
        user_key.last_used_at = datetime.now()
        
        # 更新当日统计
        await UserClaudeKeyService._reset_daily_usage_if_needed(db, user_key)
        user_key.today_requests += 1
        user_key.today_tokens += total_tokens
        user_key.today_cost_usd += charged_cost_usd
        
        await db.commit()
        await db.refresh(usage_log)
        
        return usage_log
    
    @staticmethod
    async def _reset_daily_usage_if_needed(db: AsyncSession, user_key: UserClaudeKey):
        """
        检查并重置每日使用统计(如果需要)
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 如果重置日期为空或者已经过了今天，重置统计
        if not user_key.usage_reset_date or user_key.usage_reset_date < today_start:
            user_key.today_requests = 0
            user_key.today_tokens = 0
            user_key.today_cost_usd = Decimal('0')
            user_key.usage_reset_date = today_start
            
            # 不在这里commit，让调用者处理
    
    @staticmethod
    async def get_usage_statistics(
        db: AsyncSession,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取用户Claude使用统计
        """
        # 获取用户的虚拟密钥
        user_keys_stmt = select(UserClaudeKey).where(UserClaudeKey.user_id == user_id)
        result = await db.execute(user_keys_stmt)
        user_keys = result.scalars().all()
        
        if not user_keys:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "today_usage": {"requests": 0, "tokens": 0, "cost_usd": 0},
                "keys_count": 0,
                "by_key": [],
                "recent_usage": []
            }
        
        key_ids = [key.id for key in user_keys]
        
        # 获取最近的使用记录 (暂时简化查询)
        since_date = datetime.now() - timedelta(days=days)
        recent_usage_stmt = select(ClaudeUsageLog).where(
            and_(
                ClaudeUsageLog.user_id == user_id,
                ClaudeUsageLog.request_date >= since_date
            )
        ).order_by(desc(ClaudeUsageLog.request_date)).limit(100)
        
        result = await db.execute(recent_usage_stmt)
        recent_usage = result.scalars().all()
        
        # 汇总统计
        total_requests = sum(key.total_requests for key in user_keys)
        successful_requests = sum(key.successful_requests for key in user_keys)
        failed_requests = sum(key.failed_requests for key in user_keys)
        total_tokens = sum(key.total_tokens for key in user_keys)
        total_cost_usd = sum(key.total_cost_usd for key in user_keys)
        
        # 今日使用统计
        today_requests = sum(key.today_requests for key in user_keys)
        today_tokens = sum(key.today_tokens for key in user_keys)
        today_cost_usd = sum(key.today_cost_usd for key in user_keys)
        
        # 按密钥分组统计
        by_key = []
        for key in user_keys:
            by_key.append({
                "key_id": key.id,
                "key_name": key.key_name,
                "virtual_key": key.virtual_key[:20] + "...",  # 隐藏完整密钥
                "status": key.status,
                "requests": key.total_requests,
                "tokens": key.total_tokens,
                "cost_usd": float(key.total_cost_usd),
                "today_requests": key.today_requests,
                "today_tokens": key.today_tokens,
                "today_cost_usd": float(key.today_cost_usd),
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None
            })
        
        # 最近使用记录
        recent_usage_list = []
        for usage in recent_usage:
            recent_usage_list.append({
                "timestamp": usage.request_timestamp.isoformat(),
                "request_type": usage.request_type,
                "ai_mode": usage.ai_mode,
                "tokens": usage.total_tokens,
                "cost_usd": float(usage.charged_cost_usd),
                "success": usage.success,
                "response_time_ms": usage.response_time_ms
            })
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests, 
            "failed_requests": failed_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": float(total_cost_usd),
            "today_usage": {
                "requests": today_requests,
                "tokens": today_tokens, 
                "cost_usd": float(today_cost_usd)
            },
            "keys_count": len(user_keys),
            "by_key": by_key,
            "recent_usage": recent_usage_list
        }
    
    @staticmethod
    async def deactivate_user_key(db: AsyncSession, user_key_id: int, user_id: int) -> bool:
        """
        停用用户的虚拟密钥
        """
        stmt = select(UserClaudeKey).where(
            and_(
                UserClaudeKey.id == user_key_id,
                UserClaudeKey.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        user_key = result.scalar_one_or_none()
        
        if not user_key:
            return False
            
        user_key.status = "inactive"
        await db.commit()
        
        return True
    
    @staticmethod
    async def route_to_claude_account(
        db: AsyncSession,
        user_key: UserClaudeKey,
        request_type: str = "chat",
        estimated_cost: Decimal = Decimal('0.01'),
        user_tier: str = "basic",
        session_id: str = None
    ) -> Optional[ClaudeAccount]:
        """
        为用户请求路由到合适的Claude账号
        使用企业级智能调度算法
        """
        claude_service = ClaudeAccountService()
        scheduler = IntelligentClaudeScheduler()
        
        # 优先使用首选账号(如果设置了粘性会话)
        if user_key.sticky_session_enabled and user_key.preferred_account_id:
            preferred_account = await claude_service.get_account(user_key.preferred_account_id)
            if preferred_account and preferred_account.status == "active":
                # 检查账号可用性
                if await claude_service._is_account_available(preferred_account):
                    return preferred_account
        
        # 获取所有可用的Claude账号
        available_accounts = await claude_service.list_accounts(
            status="active",
            active_only=True,
            with_proxy=True
        )
        
        if not available_accounts:
            return None
        
        # 构建调度上下文
        context = SchedulingContext(
            user_id=user_key.user_id,
            request_type=request_type,
            estimated_tokens=int(float(estimated_cost) * 1000),  # 粗略估算token数量
            user_tier=user_tier,
            session_id=session_id or f"user_{user_key.user_id}",
            priority="normal",
            preferred_region="auto",
            budget_limit=float(estimated_cost)
        )
        
        # 根据用户等级选择调度策略
        user_stmt = select(User).where(User.id == user_key.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if user:
            membership_level = user.membership_level
            if membership_level in ["premium", "professional"]:
                # 高级用户使用智能混合策略
                strategy = SchedulingStrategy.HYBRID_INTELLIGENT
                context.priority = "high" if membership_level == "professional" else "normal"
            elif membership_level == "basic":
                # 基础用户使用成本优化策略
                strategy = SchedulingStrategy.COST_OPTIMIZED
            else:
                # 免费用户使用负载均衡策略
                strategy = SchedulingStrategy.WEIGHTED_RESPONSE_TIME
        else:
            strategy = SchedulingStrategy.ROUND_ROBIN
        
        # 使用智能调度器选择最佳账号
        selected_account = await scheduler.select_optimal_account(
            db=db,
            available_accounts=available_accounts,
            context=context,
            strategy=strategy
        )
        
        if selected_account:
            # 记录调度决策以便后续优化
            await scheduler.record_scheduling_decision(
                db=db,
                selected_account_id=selected_account.id,
                context=context,
                strategy=strategy,
                decision_factors={
                    "user_tier": user_tier,
                    "request_type": request_type,
                    "estimated_cost": float(estimated_cost),
                    "available_accounts_count": len(available_accounts)
                }
            )
        
        return selected_account