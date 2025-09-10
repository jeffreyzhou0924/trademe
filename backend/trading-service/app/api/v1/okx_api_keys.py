"""
OKX API密钥管理专用接口
针对OKX交易所的特殊认证要求进行优化

OKX特殊要求:
- 必需的passphrase字段
- API密钥权限验证
- 连接测试和健康检查
- IP白名单验证提示
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncio
import ccxt
from datetime import datetime

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.api_key import ApiKey
from app.services.okx_service import okx_service
from loguru import logger
from app.utils.sensitive_info_masker import masker, safe_log_format


router = APIRouter()


class OKXApiKeyCreate(BaseModel):
    """OKX API密钥创建请求"""
    name: str = Field(..., description="API密钥名称")
    api_key: str = Field(..., min_length=20, description="OKX API Key")
    secret_key: str = Field(..., min_length=20, description="OKX Secret Key") 
    passphrase: str = Field(..., min_length=4, description="OKX Passphrase (必需)")
    permissions: Optional[str] = Field("trading", description="权限类型")
    ip_whitelist: Optional[List[str]] = Field(None, description="IP白名单提示")


class OKXApiKeyResponse(BaseModel):
    """OKX API密钥响应"""
    id: int
    name: str
    exchange: str
    api_key_masked: str
    passphrase_set: bool
    permissions: str
    status: str
    connection_status: str
    last_test_at: Optional[datetime]
    created_at: datetime


class OKXConnectionTest(BaseModel):
    """OKX连接测试结果"""
    success: bool
    message: str
    account_type: Optional[str] = None
    available_balance: Optional[float] = None
    permissions: Optional[List[str]] = None
    ip_restrictions: Optional[str] = None


@router.get("/", response_model=List[OKXApiKeyResponse])
async def get_okx_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的OKX API密钥列表"""
    try:
        from sqlalchemy import select
        
        # 查询用户的OKX API密钥
        query = select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            ApiKey.exchange == "okx"
        )
        result = await db.execute(query)
        api_keys = result.scalars().all()
        
        okx_keys = []
        for key in api_keys:
            # 掩码显示API密钥
            masked_key = key.api_key[:8] + '*' * (len(key.api_key) - 12) + key.api_key[-4:]
            
            okx_keys.append(OKXApiKeyResponse(
                id=key.id,
                name=key.name,
                exchange=key.exchange,
                api_key_masked=masked_key,
                passphrase_set=bool(key.passphrase),
                permissions="交易权限",
                status="active" if key.is_active else "inactive",
                connection_status="unknown",  # 需要测试才知道
                last_test_at=None,  # 可以添加last_test_at字段到模型
                created_at=key.created_at
            ))
        
        logger.info(safe_log_format("📋 获取OKX API密钥列表成功: 用户 {}, 数量: {}", current_user.id, len(okx_keys)))
        return okx_keys
        
    except Exception as e:
        logger.error(safe_log_format("❌ 获取OKX API密钥列表失败: 用户 {}, 错误: {}", current_user.id, str(e)[:100] + '...'))
        raise HTTPException(status_code=500, detail="获取OKX API密钥列表失败")


@router.post("/", response_model=OKXApiKeyResponse)
async def create_okx_api_key(
    api_key_data: OKXApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建OKX API密钥"""
    try:
        from sqlalchemy import select
        
        # 检查是否已存在OKX API密钥
        existing_query = select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            ApiKey.exchange == "okx",
            ApiKey.is_active == True
        )
        result = await db.execute(existing_query)
        existing_key = result.scalar_one_or_none()
        
        if existing_key:
            raise HTTPException(
                status_code=400, 
                detail="您已经配置了OKX API密钥，请先删除现有密钥再创建新的"
            )
        
        # 验证API密钥格式 (OKX格式验证)
        if not api_key_data.api_key.startswith(('ok', 'OK')):
            masked_key = api_key_data.api_key[:8] + '*' * 16 if len(api_key_data.api_key) > 8 else api_key_data.api_key[:4] + '***'
            logger.warning(safe_log_format("⚠️ 可能的无效OKX API Key格式: {}", masked_key))
        
        # 创建新的API密钥记录
        new_api_key = ApiKey(
            user_id=current_user.id,
            name=api_key_data.name,
            exchange="okx",
            api_key=api_key_data.api_key,
            secret_key=api_key_data.secret_key,
            passphrase=api_key_data.passphrase,  # OKX必需
            is_active=True
        )
        
        db.add(new_api_key)
        await db.commit()
        await db.refresh(new_api_key)
        
        # 返回响应
        masked_key = api_key_data.api_key[:8] + '*' * (len(api_key_data.api_key) - 12) + api_key_data.api_key[-4:]
        
        response = OKXApiKeyResponse(
            id=new_api_key.id,
            name=new_api_key.name,
            exchange=new_api_key.exchange,
            api_key_masked=masked_key,
            passphrase_set=True,
            permissions=api_key_data.permissions or "trading",
            status="active",
            connection_status="pending_test",
            last_test_at=None,
            created_at=new_api_key.created_at
        )
        
        logger.info(safe_log_format("✅ OKX API密钥创建成功: 用户 {}, 密钥ID: {}", current_user.id, new_api_key.id))
        return response
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(safe_log_format("❌ 创建OKX API密钥失败: 用户 {}, 错误: {}", current_user.id, str(e)))
        raise HTTPException(status_code=500, detail=f"创建OKX API密钥失败: {str(e)}")


@router.post("/{api_key_id}/test", response_model=OKXConnectionTest)
async def test_okx_connection(
    api_key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试OKX API密钥连接"""
    try:
        from sqlalchemy import select
        
        # 查询API密钥
        query = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.user_id == current_user.id,
            ApiKey.exchange == "okx"
        )
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="未找到指定的OKX API密钥")
        
        # 测试连接
        try:
            # 创建临时OKX连接
            exchange = ccxt.okx({
                'apiKey': api_key.api_key,
                'secret': api_key.secret_key,
                'password': api_key.passphrase,
                'timeout': 10000,
                'enableRateLimit': True,
                'sandbox': False,  # 始终测试生产环境连接
            })
            
            # 执行连接测试
            balance_data = await asyncio.get_event_loop().run_in_executor(
                None, exchange.fetch_balance
            )
            
            # 获取账户信息
            account_info = balance_data.get('info', {})
            permissions = []
            
            # 检查权限
            if 'read' in str(balance_data).lower():
                permissions.append('read')
            if 'trade' in str(account_info).lower():
                permissions.append('trade')
            
            # 获取可用余额
            usdt_balance = balance_data.get('free', {}).get('USDT', 0)
            
            test_result = OKXConnectionTest(
                success=True,
                message="✅ OKX连接测试成功！API密钥有效，可以正常交易",
                account_type="现货账户",
                available_balance=float(usdt_balance),
                permissions=permissions,
                ip_restrictions="请确保服务器IP在OKX API白名单中"
            )
            
            logger.info(safe_log_format("✅ OKX连接测试成功: 用户 {}, API密钥ID: {}", current_user.id, api_key_id))
            
        except ccxt.AuthenticationError as auth_error:
            test_result = OKXConnectionTest(
                success=False,
                message=f"❌ 认证失败: {str(auth_error)[:100]}...",
                ip_restrictions="请检查: 1) API密钥是否正确 2) Passphrase是否正确 3) IP是否在白名单中"
            )
            logger.warning(safe_log_format("⚠️ OKX认证失败: 用户 {}, 错误: {}", current_user.id, str(auth_error)[:100] + '...'))
            
        except ccxt.PermissionDenied as perm_error:
            test_result = OKXConnectionTest(
                success=False,
                message=f"❌ 权限不足: {str(perm_error)[:100]}...",
                ip_restrictions="请检查API密钥的交易权限设置"
            )
            logger.warning(safe_log_format("⚠️ OKX权限不足: 用户 {}, 错误: {}", current_user.id, str(perm_error)[:100] + '...'))
            
        except Exception as conn_error:
            test_result = OKXConnectionTest(
                success=False,
                message=f"❌ 连接失败: {str(conn_error)[:100]}...",
                ip_restrictions="可能的原因: 1) 网络问题 2) IP未加白名单 3) API配置错误"
            )
            logger.error(safe_log_format("❌ OKX连接测试失败: 用户 {}, 错误: {}", current_user.id, str(conn_error)[:100] + '...'))
        
        return test_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(safe_log_format("❌ OKX连接测试异常: 用户 {}, API密钥ID: {}, 错误: {}", current_user.id, api_key_id, str(e)[:100] + '...'))
        raise HTTPException(status_code=500, detail="OKX连接测试失败")


@router.put("/{api_key_id}")
async def update_okx_api_key(
    api_key_id: int,
    api_key_data: OKXApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新OKX API密钥"""
    try:
        from sqlalchemy import select
        
        # 查询现有API密钥
        query = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.user_id == current_user.id,
            ApiKey.exchange == "okx"
        )
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="未找到指定的OKX API密钥")
        
        # 更新API密钥信息
        api_key.name = api_key_data.name
        api_key.api_key = api_key_data.api_key
        api_key.secret_key = api_key_data.secret_key
        api_key.passphrase = api_key_data.passphrase
        
        await db.commit()
        
        logger.info(safe_log_format("✅ OKX API密钥更新成功: 用户 {}, 密钥ID: {}", current_user.id, api_key_id))
        return {"message": "OKX API密钥更新成功"}
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(safe_log_format("❌ 更新OKX API密钥失败: 用户 {}, 密钥ID: {}, 错误: {}", current_user.id, api_key_id, str(e)[:100] + '...'))
        raise HTTPException(status_code=500, detail="更新OKX API密钥失败")


@router.delete("/{api_key_id}")
async def delete_okx_api_key(
    api_key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除OKX API密钥"""
    try:
        from sqlalchemy import select
        
        # 查询API密钥
        query = select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.user_id == current_user.id,
            ApiKey.exchange == "okx"
        )
        result = await db.execute(query)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="未找到指定的OKX API密钥")
        
        # 软删除：设置为非活跃状态
        api_key.is_active = False
        await db.commit()
        
        logger.info(safe_log_format("✅ OKX API密钥删除成功: 用户 {}, 密钥ID: {}", current_user.id, api_key_id))
        return {"message": "OKX API密钥删除成功"}
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(safe_log_format("❌ 删除OKX API密钥失败: 用户 {}, 密钥ID: {}, 错误: {}", current_user.id, api_key_id, str(e)[:100] + '...'))
        raise HTTPException(status_code=500, detail="删除OKX API密钥失败")


@router.get("/validation-guide")
async def get_okx_validation_guide():
    """获取OKX API密钥配置指南"""
    return {
        "title": "OKX API密钥配置指南",
        "steps": [
            {
                "step": 1,
                "title": "登录OKX官网",
                "description": "访问 https://www.okx.com 并登录您的账户"
            },
            {
                "step": 2,
                "title": "进入API管理",
                "description": "点击右上角头像 → API管理 → 创建API Key"
            },
            {
                "step": 3,
                "title": "设置API权限",
                "description": "勾选'交易'权限，设置API名称和密码(Passphrase)"
            },
            {
                "step": 4,
                "title": "配置IP白名单",
                "description": "添加服务器IP到白名单，或选择不限制IP(不推荐)"
            },
            {
                "step": 5,
                "title": "记录API信息",
                "description": "复制API Key、Secret Key和Passphrase，妥善保管"
            }
        ],
        "security_tips": [
            "🔒 永远不要分享您的API密钥信息",
            "🌐 建议设置IP白名单限制",
            "⏰ 定期更换API密钥",
            "📱 开启双因素认证(2FA)",
            "💰 设置合理的资金密码和交易限额"
        ],
        "troubleshooting": {
            "authentication_error": "检查API Key、Secret Key和Passphrase是否正确",
            "permission_denied": "确认API密钥已开启交易权限",
            "ip_restricted": "检查服务器IP是否在OKX白名单中",
            "rate_limit": "请求频率过高，稍后再试"
        }
    }