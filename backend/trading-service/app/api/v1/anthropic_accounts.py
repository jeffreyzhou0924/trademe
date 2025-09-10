"""
Anthropic官方API账户管理API端点
支持Setup Token OAuth2方式，不依赖第三方代理服务
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from pydantic import BaseModel, Field
import logging

from app.database import get_db
from app.middleware.auth import verify_admin_user
from app.models.claude_proxy import ClaudeAccount
from app.services.anthropic_oauth_service import anthropic_oauth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/anthropic-accounts")

class SetupTokenRequest(BaseModel):
    """生成Setup Token授权链接的请求模型"""
    description: str = Field(default="", description="账户描述")

class SetupTokenExchange(BaseModel):
    """Setup Token授权码交换请求模型"""
    session_id: str = Field(..., description="OAuth会话ID")
    authorization_code: str = Field(..., description="授权码或包含access_token的完整回调URL")
    account_name: str = Field(..., description="账户名称")
    daily_limit: float = Field(default=50.0, description="每日限额(USD)")
    description: str = Field(default="", description="账户描述")
    priority: int = Field(default=50, description="调度优先级")

class DirectTokenImport(BaseModel):
    """直接导入access_token的请求模型（用于手动方式）"""
    access_token: str = Field(..., description="从Claude获取的访问令牌")
    account_name: str = Field(..., description="账户名称")
    daily_limit: float = Field(default=50.0, description="每日限额(USD)")
    description: str = Field(default="", description="账户描述")
    priority: int = Field(default=50, description="调度优先级")
    expires_in: int = Field(default=31536000, description="过期时间（秒）")

class AnthropicAccountUpdate(BaseModel):
    """更新Anthropic账户的请求模型"""
    account_name: Optional[str] = None
    daily_limit: Optional[float] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    is_schedulable: Optional[bool] = None
    status: Optional[str] = None


@router.post("/generate-setup-token-url", response_model=Dict[str, Any])
async def generate_setup_token_url(
    current_admin: dict = Depends(verify_admin_user),
):
    """
    生成Anthropic Setup Token授权链接
    Step 1: 生成OAuth授权URL，用户需要访问此URL完成授权
    """
    
    try:
        result = await anthropic_oauth_service.generate_setup_token_params()
        
        logger.info("🔗 Generated Setup Token authorization URL")
        
        return {
            "success": True,
            "message": "Setup Token授权链接生成成功",
            "auth_url": result["auth_url"],
            "session_id": result["session_id"],
            "expires_in": result["expires_in"],
            "instructions": [
                "1. 复制上面的授权链接，在浏览器中打开",
                "2. 登录您的Claude账户并完成授权",
                "3. 从回调页面复制授权码",
                "4. 返回此页面，粘贴授权码完成Setup Token交换"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to generate Setup Token URL: {e}")
        raise HTTPException(status_code=500, detail=f"生成Setup Token授权链接失败: {str(e)}")


@router.post("/exchange-setup-token", response_model=Dict[str, Any])
async def exchange_setup_token(
    exchange_data: SetupTokenExchange,
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """
    交换Setup Token授权码为访问令牌并创建账户
    Step 2: 使用授权码交换访问令牌，并创建Claude账户
    """
    
    try:
        # 检查账户名是否重复
        existing_account = await session.execute(
            select(ClaudeAccount).where(
                ClaudeAccount.account_name == exchange_data.account_name
            )
        )
        
        if existing_account.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="账户名已存在"
            )
        
        # 交换授权码获取token
        token_data = await anthropic_oauth_service.exchange_setup_token_code(
            session_id=exchange_data.session_id,
            authorization_code=exchange_data.authorization_code,
            session=session
        )
        
        # 创建账户
        account = await anthropic_oauth_service.create_account_with_setup_token(
            account_name=exchange_data.account_name,
            token_data=token_data,
            description=exchange_data.description,
            daily_limit=exchange_data.daily_limit,
            priority=exchange_data.priority,
            session=session
        )
        
        logger.info(f"✅ Successfully created Setup Token account: {exchange_data.account_name} (ID: {account.id})")
        
        return {
            "success": True,
            "message": "Setup Token账户创建成功",
            "account": {
                "id": account.id,
                "account_name": account.account_name,
                "proxy_type": account.proxy_type,
                "status": account.status,
                "daily_limit": float(account.daily_limit),
                "priority": account.priority,
                "scopes": account.oauth_scopes.split(',') if account.oauth_scopes else [],
                "expires_at": account.oauth_expires_at.isoformat() if account.oauth_expires_at else None,
                "created_at": account.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to exchange Setup Token: {e}")
        raise HTTPException(status_code=500, detail=f"Setup Token交换失败: {str(e)}")


@router.post("/import-direct-token", response_model=Dict[str, Any])
async def import_direct_token(
    token_data: DirectTokenImport,
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """
    直接导入access_token（手动方式）
    
    当Cloudflare阻止自动OAuth流程时，用户可以：
    1. 在浏览器中手动完成OAuth授权
    2. 从回调URL中获取access_token
    3. 使用此端点直接导入token
    
    回调URL示例:
    https://console.anthropic.com/oauth/code/callback#access_token=xxx&token_type=Bearer&expires_in=31536000
    """
    
    try:
        # 检查账户名称是否已存在
        existing_query = select(ClaudeAccount).where(
            ClaudeAccount.account_name == token_data.account_name
        )
        existing_result = await session.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"账户名称 '{token_data.account_name}' 已存在")
        
        # 构建token数据（与OAuth流程返回的格式一致）
        from datetime import datetime, timedelta
        token_info = {
            'access_token': token_data.access_token,
            'refresh_token': '',  # 手动导入通常没有refresh token
            'expires_at': (datetime.now() + timedelta(seconds=token_data.expires_in)).isoformat(),
            'scopes': ['user:inference'],  # Setup Token的默认权限
            'token_type': 'Bearer',
            'manual_import': True  # 标记为手动导入
        }
        
        # 使用相同的创建函数
        account = await anthropic_oauth_service.create_account_with_setup_token(
            account_name=token_data.account_name,
            token_data=token_info,
            description=token_data.description or f"手动导入的Setup Token - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            daily_limit=token_data.daily_limit,
            priority=token_data.priority,
            session=session
        )
        
        logger.info(f"✅ Successfully imported direct token for account: {token_data.account_name} (ID: {account.id})")
        
        # 测试连接
        test_result = await anthropic_oauth_service.test_account_connection(account)
        
        return {
            "success": True,
            "message": "访问令牌导入成功",
            "account": {
                "id": account.id,
                "account_name": account.account_name,
                "proxy_type": account.proxy_type,
                "status": account.status,
                "daily_limit": float(account.daily_limit),
                "priority": account.priority,
                "scopes": account.oauth_scopes.split(',') if account.oauth_scopes else [],
                "expires_at": account.oauth_expires_at.isoformat() if account.oauth_expires_at else None,
                "created_at": account.created_at.isoformat()
            },
            "connection_test": test_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to import direct token: {e}")
        raise HTTPException(status_code=500, detail=f"访问令牌导入失败: {str(e)}")


@router.get("/", response_model=List[Dict[str, Any]])
async def list_anthropic_accounts(
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """获取Anthropic Setup Token账户列表"""
    
    try:
        query = select(ClaudeAccount).where(
            ClaudeAccount.proxy_type == "setup_token"
        ).order_by(
            ClaudeAccount.priority.asc(),
            ClaudeAccount.success_rate.desc(),
            ClaudeAccount.created_at.desc()
        )
        
        result = await session.execute(query)
        accounts = result.scalars().all()
        
        response_accounts = []
        for account in accounts:
            usage_percentage = (
                float(account.current_usage) / float(account.daily_limit) * 100
                if account.daily_limit > 0 else 0
            )
            
            response_accounts.append({
                "id": account.id,
                "account_name": account.account_name,
                "proxy_type": account.proxy_type,
                "daily_limit": float(account.daily_limit),
                "current_usage": float(account.current_usage),
                "usage_percentage": usage_percentage,
                "status": account.status,
                "priority": account.priority,
                "is_schedulable": account.is_schedulable,
                "success_rate": float(account.success_rate),
                "total_requests": account.total_requests,
                "failed_requests": account.failed_requests,
                "avg_response_time": account.avg_response_time,
                "scopes": account.oauth_scopes.split(',') if account.oauth_scopes else [],
                "token_type": account.oauth_token_type,
                "expires_at": account.oauth_expires_at.isoformat() if account.oauth_expires_at else None,
                "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
                "last_check_at": account.last_check_at.isoformat() if account.last_check_at else None,
                "created_at": account.created_at.isoformat(),
                "updated_at": account.updated_at.isoformat() if account.updated_at else None,
                "description": account.description or "",
                "subscription_info": account.subscription_info
            })
        
        logger.info(f"📋 Listed {len(response_accounts)} Anthropic Setup Token accounts")
        return response_accounts
        
    except Exception as e:
        logger.error(f"❌ Failed to list Anthropic accounts: {e}")
        raise HTTPException(status_code=500, detail=f"获取账户列表失败: {str(e)}")


@router.get("/{account_id}", response_model=Dict[str, Any])
async def get_anthropic_account(
    account_id: int,
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """获取单个Anthropic Setup Token账户详情"""
    
    try:
        result = await session.execute(
            select(ClaudeAccount).where(
                ClaudeAccount.id == account_id,
                ClaudeAccount.proxy_type == "setup_token"
            )
        )
        
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在或不是Setup Token类型")
        
        usage_percentage = (
            float(account.current_usage) / float(account.daily_limit) * 100
            if account.daily_limit > 0 else 0
        )
        
        return {
            "id": account.id,
            "account_name": account.account_name,
            "proxy_type": account.proxy_type,
            "daily_limit": float(account.daily_limit),
            "current_usage": float(account.current_usage),
            "usage_percentage": usage_percentage,
            "status": account.status,
            "priority": account.priority,
            "is_schedulable": account.is_schedulable,
            "success_rate": float(account.success_rate),
            "total_requests": account.total_requests,
            "failed_requests": account.failed_requests,
            "avg_response_time": account.avg_response_time,
            "scopes": account.oauth_scopes.split(',') if account.oauth_scopes else [],
            "token_type": account.oauth_token_type,
            "expires_at": account.oauth_expires_at.isoformat() if account.oauth_expires_at else None,
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
            "last_check_at": account.last_check_at.isoformat() if account.last_check_at else None,
            "created_at": account.created_at.isoformat(),
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            "description": account.description or "",
            "subscription_info": account.subscription_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get Anthropic account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取账户失败: {str(e)}")


@router.put("/{account_id}", response_model=Dict[str, Any])
async def update_anthropic_account(
    account_id: int,
    account_updates: AnthropicAccountUpdate,
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """更新Anthropic Setup Token账户"""
    
    try:
        # 检查账户是否存在
        result = await session.execute(
            select(ClaudeAccount).where(
                ClaudeAccount.id == account_id,
                ClaudeAccount.proxy_type == "setup_token"
            )
        )
        
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在或不是Setup Token类型")
        
        # 构建更新字典
        update_values = {}
        
        if account_updates.account_name is not None:
            # 检查新账户名是否重复
            existing = await session.execute(
                select(ClaudeAccount).where(
                    ClaudeAccount.account_name == account_updates.account_name,
                    ClaudeAccount.id != account_id
                )
            )
            
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="账户名已存在")
            
            update_values[ClaudeAccount.account_name] = account_updates.account_name
        
        if account_updates.daily_limit is not None:
            update_values[ClaudeAccount.daily_limit] = account_updates.daily_limit
        
        if account_updates.description is not None:
            update_values[ClaudeAccount.description] = account_updates.description
        
        if account_updates.priority is not None:
            update_values[ClaudeAccount.priority] = account_updates.priority
        
        if account_updates.is_schedulable is not None:
            update_values[ClaudeAccount.is_schedulable] = account_updates.is_schedulable
        
        if account_updates.status is not None:
            update_values[ClaudeAccount.status] = account_updates.status
        
        # 执行更新
        if update_values:
            await session.execute(
                update(ClaudeAccount)
                .where(ClaudeAccount.id == account_id)
                .values(**update_values)
            )
            await session.commit()
        
        # 获取更新后的账户
        result = await session.execute(
            select(ClaudeAccount).where(ClaudeAccount.id == account_id)
        )
        updated_account = result.scalar_one()
        
        logger.info(f"✅ Updated Anthropic Setup Token account: {account_id}")
        
        return {
            "success": True,
            "message": "账户更新成功",
            "account": {
                "id": updated_account.id,
                "account_name": updated_account.account_name,
                "status": updated_account.status,
                "daily_limit": float(updated_account.daily_limit),
                "priority": updated_account.priority,
                "is_schedulable": updated_account.is_schedulable,
                "description": updated_account.description or "",
                "updated_at": updated_account.updated_at.isoformat() if updated_account.updated_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update Anthropic account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"更新账户失败: {str(e)}")


@router.delete("/{account_id}", response_model=Dict[str, Any])
async def delete_anthropic_account(
    account_id: int,
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """删除Anthropic Setup Token账户"""
    
    try:
        # 检查账户是否存在
        result = await session.execute(
            select(ClaudeAccount).where(
                ClaudeAccount.id == account_id,
                ClaudeAccount.proxy_type == "setup_token"
            )
        )
        
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在或不是Setup Token类型")
        
        # 执行删除
        await session.execute(
            delete(ClaudeAccount).where(ClaudeAccount.id == account_id)
        )
        await session.commit()
        
        logger.info(f"✅ Deleted Anthropic Setup Token account: {account_id} ({account.account_name})")
        
        return {
            "success": True,
            "message": f"账户 '{account.account_name}' 已删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete Anthropic account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"删除账户失败: {str(e)}")


@router.post("/{account_id}/test", response_model=Dict[str, Any])
async def test_anthropic_account(
    account_id: int,
    current_admin: dict = Depends(verify_admin_user),
    session: AsyncSession = Depends(get_db)
):
    """测试Anthropic Setup Token账户连接"""
    
    try:
        # 检查账户是否存在
        result = await session.execute(
            select(ClaudeAccount).where(
                ClaudeAccount.id == account_id,
                ClaudeAccount.proxy_type == "setup_token"
            )
        )
        
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在或不是Setup Token类型")
        
        # 执行连接测试
        test_result = await anthropic_oauth_service.test_account_connection(account)
        
        # 更新账户状态
        new_status = "active" if test_result["success"] else "error"
        
        await session.execute(
            update(ClaudeAccount)
            .where(ClaudeAccount.id == account_id)
            .values(
                status=new_status,
                error_message=test_result.get("error") if not test_result["success"] else None,
                last_check_at=logger.info(f"Updated account {account_id} last_check_at")
            )
        )
        await session.commit()
        
        logger.info(f"🧪 Tested Setup Token account {account_id}: {'✅ SUCCESS' if test_result['success'] else '❌ FAILED'}")
        
        return {
            "success": test_result["success"],
            "message": "连接测试成功" if test_result["success"] else f"连接测试失败: {test_result.get('error')}",
            "account_id": account_id,
            "account_name": account.account_name,
            "test_details": test_result,
            "account_status_updated": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to test Anthropic account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")