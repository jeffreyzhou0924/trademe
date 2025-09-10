"""
用户钱包管理API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from decimal import Decimal

from app.middleware.auth import get_current_active_user
from app.services.user_wallet_service import user_wallet_service

router = APIRouter()


class UserWalletResponse(BaseModel):
    user_id: int
    wallets: Dict[str, Any]
    total_balance: float
    networks_count: int


class ConsolidationRequest(BaseModel):
    min_amount: Optional[float] = 1.0


@router.post("/allocate")
async def allocate_user_wallets(current_user = Depends(get_current_active_user)):
    """为当前用户分配钱包地址"""
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else 0
        if not user_id:
            raise HTTPException(status_code=400, detail="无效的用户ID")
        
        wallets = await user_wallet_service.allocate_wallets_for_user(user_id)
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "wallets": wallets,
                "message": "钱包分配成功"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"钱包分配失败: {str(e)}")


@router.get("/my-wallets", response_model=UserWalletResponse)
async def get_my_wallets(current_user = Depends(get_current_active_user)):
    """获取当前用户的钱包信息"""
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else 0
        if not user_id:
            raise HTTPException(status_code=400, detail="无效的用户ID")
        
        wallet_info = await user_wallet_service.get_user_wallets(user_id)
        
        return UserWalletResponse(**wallet_info)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取钱包信息失败: {str(e)}")


@router.get("/balance")
async def get_user_balance(current_user = Depends(get_current_active_user)):
    """获取当前用户所有钱包余额"""
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else 0
        if not user_id:
            raise HTTPException(status_code=400, detail="无效的用户ID")
        
        balances = await user_wallet_service.check_user_balances(user_id)
        
        total_balance = sum(balances.values())
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "balances": {network: float(balance) for network, balance in balances.items()},
                "total_balance": float(total_balance)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取余额失败: {str(e)}")


@router.post("/consolidate")
async def initiate_consolidation(
    request: ConsolidationRequest,
    current_user = Depends(get_current_active_user)
):
    """发起资金归集"""
    try:
        user_id = current_user.id if hasattr(current_user, 'id') else 0
        if not user_id:
            raise HTTPException(status_code=400, detail="无效的用户ID")
        
        min_amount = Decimal(str(request.min_amount))
        consolidation_tasks = await user_wallet_service.initiate_fund_consolidation(user_id, min_amount)
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "consolidation_tasks": consolidation_tasks,
                "tasks_count": len(consolidation_tasks),
                "message": f"成功发起 {len(consolidation_tasks)} 个归集任务"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发起归集失败: {str(e)}")


# 管理员API
@router.get("/admin/overview")
async def get_user_wallets_overview(current_user = Depends(get_current_active_user)):
    """获取用户钱包系统概览（管理员）"""
    try:
        # 检查管理员权限
        user_email = current_user.email if hasattr(current_user, 'email') else ""
        if not user_email.endswith("@trademe.com") and "admin" not in user_email:
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        overview = await user_wallet_service.get_all_user_wallets()
        
        return {
            "success": True,
            "data": overview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户钱包概览失败: {str(e)}")


@router.post("/admin/user/{user_id}/allocate")
async def allocate_wallets_for_user_admin(
    user_id: int,
    current_user = Depends(get_current_active_user)
):
    """为指定用户分配钱包（管理员）"""
    try:
        # 检查管理员权限
        user_email = current_user.email if hasattr(current_user, 'email') else ""
        if not user_email.endswith("@trademe.com") and "admin" not in user_email:
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        wallets = await user_wallet_service.allocate_wallets_for_user(user_id)
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "wallets": wallets,
                "message": f"成功为用户 {user_id} 分配钱包"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分配钱包失败: {str(e)}")


@router.get("/admin/user/{user_id}/wallets")
async def get_user_wallets_admin(
    user_id: int,
    current_user = Depends(get_current_active_user)
):
    """获取指定用户的钱包信息（管理员）"""
    try:
        # 检查管理员权限
        user_email = current_user.email if hasattr(current_user, 'email') else ""
        if not user_email.endswith("@trademe.com") and "admin" not in user_email:
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        wallet_info = await user_wallet_service.get_user_wallets(user_id)
        
        return {
            "success": True,
            "data": wallet_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户钱包信息失败: {str(e)}")