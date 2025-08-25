"""
会员管理API端点
处理用户会员信息、使用统计、升级等功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.services.membership_service import MembershipService
from app.schemas.membership import UsageStatsResponse, MembershipResponse, UserStats

router = APIRouter(prefix="/membership", tags=["会员管理"])


@router.get("/usage-stats", response_model=UsageStatsResponse, summary="获取用户使用统计")
async def get_usage_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的使用统计信息
    包括API密钥、AI使用量、存储空间、策略数量等各项指标的使用情况
    """
    try:
        # 获取用户使用统计
        stats = await MembershipService.get_user_usage_stats(
            db=db,
            user_id=current_user.id,
            membership_level=current_user.membership_level
        )
        
        return UsageStatsResponse(
            success=True,
            data=stats,
            message="获取使用统计成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取使用统计失败: {str(e)}"
        )


@router.get("/limits", response_model=MembershipResponse, summary="获取会员限制信息")
async def get_membership_limits(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前用户会员等级的限制信息
    """
    try:
        limits = MembershipService.get_membership_limits(current_user.membership_level)
        
        return MembershipResponse(
            success=True,
            data=limits.dict(),
            message="获取会员限制成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会员限制失败: {str(e)}"
        )


@router.get("/features", response_model=MembershipResponse, summary="获取会员功能特性")
async def get_membership_features(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前用户会员等级的功能特性
    """
    try:
        features = MembershipService.get_membership_features(current_user.membership_level)
        
        return MembershipResponse(
            success=True,
            data=features,
            message="获取会员功能特性成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会员功能特性失败: {str(e)}"
        )


@router.get("/all-plans", response_model=MembershipResponse, summary="获取所有会员套餐")
async def get_all_membership_plans():
    """
    获取所有可用的会员套餐信息
    用于展示升级选项
    """
    try:
        plans = []
        for level in ["basic", "premium", "professional", "enterprise"]:
            features = MembershipService.get_membership_features(level)
            limits = MembershipService.get_membership_limits(level)
            
            plan = {
                "level": level,
                "name": features["name"],
                "price": features["price"],
                "period": features["period"],
                "features": features["features"],
                "limits": limits.dict()
            }
            plans.append(plan)
        
        return MembershipResponse(
            success=True,
            data={"plans": plans},
            message="获取所有会员套餐成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会员套餐失败: {str(e)}"
        )


@router.post("/check-limit", response_model=MembershipResponse, summary="检查使用限制")
async def check_usage_limit(
    usage_type: str,
    current_usage: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    检查用户是否达到使用限制
    
    Args:
        usage_type: 使用类型 (api_keys, strategies, indicators, live_trading, tick_backtest)
        current_usage: 当前使用量
    """
    try:
        can_use = MembershipService.check_usage_limit(
            membership_level=current_user.membership_level,
            usage_type=usage_type,
            current_usage=current_usage
        )
        
        return MembershipResponse(
            success=True,
            data={"can_use": can_use, "usage_type": usage_type, "current_usage": current_usage},
            message="检查限制成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查使用限制失败: {str(e)}"
        )