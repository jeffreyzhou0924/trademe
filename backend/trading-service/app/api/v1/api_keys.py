"""
API密钥管理

用户交易所API密钥的安全管理
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import hashlib
import os

from app.database import get_db
from app.schemas.exchange import ApiKeyCreate, ApiKeyResponse, ApiKeyUpdate
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.api_key import ApiKey
from loguru import logger

router = APIRouter()


def encrypt_sensitive_data(data: str) -> str:
    """加密敏感数据（简单示例，生产环境应使用更强的加密）"""
    salt = os.environ.get('ENCRYPTION_SALT', 'trademe_salt_2023')
    return hashlib.sha256((data + salt).encode()).hexdigest()


def mask_api_key(api_key: str) -> str:
    """掩码API密钥显示"""
    if len(api_key) <= 8:
        return '*' * len(api_key)
    return api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]


@router.get("/")
async def get_user_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的API密钥列表"""
    try:
        from sqlalchemy import select
        
        query = select(ApiKey).where(ApiKey.user_id == current_user.id)
        result = await db.execute(query)
        api_keys = result.scalars().all()
        
        api_keys_list = []
        for key in api_keys:
            api_keys_list.append({
                "id": key.id,
                "name": f"{key.exchange.upper()}账户",  # 如果模型中没有name字段，用默认值
                "exchange": key.exchange,
                "api_key": key.api_key,  # 前端会处理显示掩码
                "permissions": "交易权限",
                "status": "active" if key.is_active else "inactive",
                "created_at": key.created_at.isoformat()
            })
        
        return {"api_keys": api_keys_list}
    except Exception as e:
        logger.error(f"获取API密钥列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取API密钥列表失败")


@router.post("/", response_model=ApiKeyResponse)
async def create_api_key(
    api_key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建API密钥"""
    try:
        from sqlalchemy import select
        
        # 检查是否已存在该交易所的API密钥
        existing_query = select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            ApiKey.exchange == api_key_data.exchange,
            ApiKey.is_active == True
        )
        existing_result = await db.execute(existing_query)
        existing_key = existing_result.scalar_one_or_none()
        
        if existing_key:
            raise HTTPException(
                status_code=409, 
                detail=f"已存在 {api_key_data.exchange} 的活跃API密钥"
            )
        
        # 创建新的API密钥记录
        new_api_key = ApiKey(
            user_id=current_user.id,
            name=api_key_data.name,
            exchange=api_key_data.exchange,
            api_key=api_key_data.api_key,  # 生产环境应该加密存储
            secret_key=api_key_data.secret_key,  # 生产环境应该加密存储
            passphrase=api_key_data.passphrase,
            is_active=True
        )
        
        db.add(new_api_key)
        await db.commit()
        await db.refresh(new_api_key)
        
        logger.info(f"用户 {current_user.id} 创建了 {api_key_data.exchange} API密钥")
        
        return ApiKeyResponse(
            id=new_api_key.id,
            exchange=new_api_key.exchange,
            api_key_masked=mask_api_key(new_api_key.api_key),
            is_active=new_api_key.is_active,
            created_at=new_api_key.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"创建API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建API密钥失败")


@router.put("/{api_key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    api_key_id: int,
    api_key_data: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新API密钥"""
    try:
        from sqlalchemy import select
        
        # 查找API密钥
        query = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.user_id == current_user.id
        )
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API密钥不存在")
        
        # 更新字段
        if api_key_data.api_key is not None:
            api_key.api_key = api_key_data.api_key
        if api_key_data.secret_key is not None:
            api_key.secret_key = api_key_data.secret_key
        if api_key_data.passphrase is not None:
            api_key.passphrase = api_key_data.passphrase
        if api_key_data.is_active is not None:
            api_key.is_active = api_key_data.is_active
        
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(f"用户 {current_user.id} 更新了API密钥 {api_key_id}")
        
        return ApiKeyResponse(
            id=api_key.id,
            exchange=api_key.exchange,
            api_key_masked=mask_api_key(api_key.api_key),
            is_active=api_key.is_active,
            created_at=api_key.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新API密钥失败")


@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除API密钥"""
    try:
        from sqlalchemy import select
        
        # 查找API密钥
        query = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.user_id == current_user.id
        )
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API密钥不存在")
        
        await db.delete(api_key)
        await db.commit()
        
        logger.info(f"用户 {current_user.id} 删除了API密钥 {api_key_id}")
        
        return {"message": "API密钥删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除API密钥失败")


@router.post("/{api_key_id}/test")
async def test_api_key(
    api_key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试API密钥连接"""
    try:
        from sqlalchemy import select
        from app.services.exchange_service import exchange_service
        
        # 查找API密钥
        query = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.user_id == current_user.id
        )
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API密钥不存在")
        
        # 测试连接
        exchange = await exchange_service.get_exchange(
            current_user.id, api_key.exchange, db
        )
        
        if exchange:
            return {
                "success": True,
                "message": f"{api_key.exchange} 连接测试成功",
                "exchange": api_key.exchange
            }
        else:
            return {
                "success": False,
                "message": f"{api_key.exchange} 连接测试失败",
                "exchange": api_key.exchange
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试API密钥失败: {str(e)}")
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "exchange": "unknown"
        }