"""
用户Claude Key管理API
- 创建和管理虚拟Claude密钥
- 查看使用统计
- 配置使用限制
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from decimal import Decimal

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services.user_claude_key_service import UserClaudeKeyService
from app.schemas.user_claude_key import (
    UserClaudeKeyCreate, UserClaudeKeyResponse, 
    UserClaudeKeyUpdate, UsageStatisticsResponse
)

router = APIRouter()


@router.post("/", response_model=UserClaudeKeyResponse)
async def create_user_claude_key(
    key_data: UserClaudeKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建用户虚拟Claude密钥"""
    try:
        user_key = await UserClaudeKeyService.create_user_claude_key(
            db=db,
            user_id=current_user.id,
            key_name=key_data.key_name,
            description=key_data.description
        )
        
        return UserClaudeKeyResponse(
            id=user_key.id,
            key_name=user_key.key_name,
            virtual_key=user_key.virtual_key,
            status=user_key.status,
            description=user_key.description,
            total_requests=user_key.total_requests,
            total_tokens=user_key.total_tokens,
            total_cost_usd=float(user_key.total_cost_usd),
            today_requests=user_key.today_requests,
            today_tokens=user_key.today_tokens,
            today_cost_usd=float(user_key.today_cost_usd),
            daily_request_limit=user_key.daily_request_limit,
            daily_token_limit=user_key.daily_token_limit,
            daily_cost_limit=float(user_key.daily_cost_limit) if user_key.daily_cost_limit else None,
            last_used_at=user_key.last_used_at.isoformat() if user_key.last_used_at else None,
            created_at=user_key.created_at.isoformat(),
            expires_at=user_key.expires_at.isoformat() if user_key.expires_at else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建密钥失败: {str(e)}")


@router.get("/", response_model=List[UserClaudeKeyResponse])
async def get_user_claude_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的所有虚拟Claude密钥"""
    try:
        user_keys = await UserClaudeKeyService.get_user_keys(db, current_user.id)
        
        return [
            UserClaudeKeyResponse(
                id=key.id,
                key_name=key.key_name,
                virtual_key=key.virtual_key,
                status=key.status,
                description=key.description,
                total_requests=key.total_requests,
                total_tokens=key.total_tokens,
                total_cost_usd=float(key.total_cost_usd),
                today_requests=key.today_requests,
                today_tokens=key.today_tokens,
                today_cost_usd=float(key.today_cost_usd),
                daily_request_limit=key.daily_request_limit,
                daily_token_limit=key.daily_token_limit,
                daily_cost_limit=float(key.daily_cost_limit) if key.daily_cost_limit else None,
                last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
                created_at=key.created_at.isoformat(),
                expires_at=key.expires_at.isoformat() if key.expires_at else None
            )
            for key in user_keys
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取密钥列表失败: {str(e)}")


@router.get("/usage/statistics", response_model=UsageStatisticsResponse)
async def get_usage_statistics(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户Claude使用统计"""
    try:
        stats = await UserClaudeKeyService.get_usage_statistics(db, current_user.id, days)
        
        return UsageStatisticsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取使用统计失败: {str(e)}")


@router.put("/{key_id}", response_model=UserClaudeKeyResponse)
async def update_user_claude_key(
    key_id: int,
    key_update: UserClaudeKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户虚拟Claude密钥"""
    try:
        # 获取用户密钥
        user_keys = await UserClaudeKeyService.get_user_keys(db, current_user.id)
        user_key = next((key for key in user_keys if key.id == key_id), None)
        
        if not user_key:
            raise HTTPException(status_code=404, detail="密钥不存在")
        
        # 更新字段
        if key_update.key_name is not None:
            user_key.key_name = key_update.key_name
        if key_update.description is not None:
            user_key.description = key_update.description
        if key_update.daily_request_limit is not None:
            user_key.daily_request_limit = key_update.daily_request_limit
        if key_update.daily_token_limit is not None:
            user_key.daily_token_limit = key_update.daily_token_limit
        if key_update.daily_cost_limit is not None:
            user_key.daily_cost_limit = Decimal(str(key_update.daily_cost_limit))
        
        await db.commit()
        await db.refresh(user_key)
        
        return UserClaudeKeyResponse(
            id=user_key.id,
            key_name=user_key.key_name,
            virtual_key=user_key.virtual_key,
            status=user_key.status,
            description=user_key.description,
            total_requests=user_key.total_requests,
            total_tokens=user_key.total_tokens,
            total_cost_usd=float(user_key.total_cost_usd),
            today_requests=user_key.today_requests,
            today_tokens=user_key.today_tokens,
            today_cost_usd=float(user_key.today_cost_usd),
            daily_request_limit=user_key.daily_request_limit,
            daily_token_limit=user_key.daily_token_limit,
            daily_cost_limit=float(user_key.daily_cost_limit) if user_key.daily_cost_limit else None,
            last_used_at=user_key.last_used_at.isoformat() if user_key.last_used_at else None,
            created_at=user_key.created_at.isoformat(),
            expires_at=user_key.expires_at.isoformat() if user_key.expires_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新密钥失败: {str(e)}")


@router.delete("/{key_id}")
async def deactivate_user_claude_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停用用户虚拟Claude密钥"""
    try:
        success = await UserClaudeKeyService.deactivate_user_key(db, key_id, current_user.id)
        
        if not success:
            raise HTTPException(status_code=404, detail="密钥不存在")
        
        return {"message": "密钥已停用", "key_id": key_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停用密钥失败: {str(e)}")


@router.post("/auto-allocate", response_model=UserClaudeKeyResponse)
async def auto_allocate_claude_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """为当前用户自动分配Claude密钥（如果没有的话）"""
    try:
        user_key = await UserClaudeKeyService.auto_allocate_key_for_new_user(db, current_user.id)
        
        return UserClaudeKeyResponse(
            id=user_key.id,
            key_name=user_key.key_name,
            virtual_key=user_key.virtual_key,
            status=user_key.status,
            description=user_key.description,
            total_requests=user_key.total_requests,
            total_tokens=user_key.total_tokens,
            total_cost_usd=float(user_key.total_cost_usd),
            today_requests=user_key.today_requests,
            today_tokens=user_key.today_tokens,
            today_cost_usd=float(user_key.today_cost_usd),
            daily_request_limit=user_key.daily_request_limit,
            daily_token_limit=user_key.daily_token_limit,
            daily_cost_limit=float(user_key.daily_cost_limit) if user_key.daily_cost_limit else None,
            last_used_at=user_key.last_used_at.isoformat() if user_key.last_used_at else None,
            created_at=user_key.created_at.isoformat(),
            expires_at=user_key.expires_at.isoformat() if user_key.expires_at else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动分配密钥失败: {str(e)}")


@router.get("/{key_id}/limits/check")
async def check_usage_limits(
    key_id: int,
    estimated_tokens: int = Query(0, ge=0, description="预估token使用量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检查密钥使用限制"""
    try:
        # 获取用户密钥
        user_keys = await UserClaudeKeyService.get_user_keys(db, current_user.id)
        user_key = next((key for key in user_keys if key.id == key_id), None)
        
        if not user_key:
            raise HTTPException(status_code=404, detail="密钥不存在")
        
        # 检查使用限制
        estimated_cost = Decimal(str(estimated_tokens * 0.00009))  # 粗略估算
        limits_check = await UserClaudeKeyService.check_usage_limits(
            db, user_key, estimated_tokens, estimated_cost
        )
        
        return limits_check
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查使用限制失败: {str(e)}")


@router.post("/{key_id}/reset-daily-usage")
async def reset_daily_usage(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重置每日使用统计（管理员功能）"""
    try:
        # 检查用户权限（这里简化处理，实际应该检查管理员权限）
        if current_user.membership_level not in ["professional", "admin"]:
            raise HTTPException(status_code=403, detail="权限不足")
        
        # 获取用户密钥
        user_keys = await UserClaudeKeyService.get_user_keys(db, current_user.id)
        user_key = next((key for key in user_keys if key.id == key_id), None)
        
        if not user_key:
            raise HTTPException(status_code=404, detail="密钥不存在")
        
        # 重置每日统计
        user_key.today_requests = 0
        user_key.today_tokens = 0
        user_key.today_cost_usd = Decimal('0')
        user_key.usage_reset_date = None
        
        await db.commit()
        
        return {"message": "每日使用统计已重置", "key_id": key_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置统计失败: {str(e)}")