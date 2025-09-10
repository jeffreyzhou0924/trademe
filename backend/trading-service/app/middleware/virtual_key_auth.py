"""
虚拟API密钥认证中间件
- 兼容claude-relay-service的ck-格式密钥认证
- 支持标准Authorization: Bearer ck-xxx格式
- 集成用户限制检查和账户路由
"""

from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple

from app.database import get_db
from app.services.user_claude_key_service import UserClaudeKeyService
from app.models.claude_proxy import UserClaudeKey
from app.models.user import User

# 创建HTTP Bearer认证器
security = HTTPBearer()

class VirtualKeyAuth:
    """虚拟密钥认证类"""
    
    @staticmethod
    async def authenticate_virtual_key(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Tuple[UserClaudeKey, User]:
        """
        认证虚拟API密钥
        
        Args:
            credentials: HTTP Bearer认证凭据
            db: 数据库会话
            
        Returns:
            Tuple[UserClaudeKey, User]: 用户密钥和用户信息
            
        Raises:
            HTTPException: 认证失败时抛出
        """
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        virtual_key = credentials.credentials
        
        # 验证密钥格式 (ck-开头)
        if not virtual_key.startswith('ck-'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format. Expected format: ck-xxx",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 查询虚拟密钥
        user_key = await UserClaudeKeyService.get_user_key_by_virtual_key(db, virtual_key)
        if not user_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 检查密钥状态
        if user_key.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key is {user_key.status}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 获取用户信息
        from sqlalchemy import select
        user_stmt = select(User).where(User.id == user_key.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user_key, user

    @staticmethod
    async def get_virtual_key_from_request(request: Request) -> Optional[str]:
        """
        从请求中提取虚拟API密钥
        支持多种格式：Authorization Bearer、Query参数等
        """
        # 1. 从Authorization Header提取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # 移除 "Bearer " 前缀
            if token.startswith("ck-"):
                return token
        
        # 2. 从Query参数提取 (兼容某些客户端)
        api_key_query = request.query_params.get("api_key")
        if api_key_query and api_key_query.startswith("ck-"):
            return api_key_query
        
        # 3. 从Header直接提取 (兼容模式)
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header and api_key_header.startswith("ck-"):
            return api_key_header
        
        return None

# 依赖注入函数，可以在路由中直接使用
async def get_authenticated_virtual_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Tuple[UserClaudeKey, User]:
    """获取已认证的虚拟密钥和用户信息"""
    return await VirtualKeyAuth.authenticate_virtual_key(credentials, db)

# 兼容claude-relay-service的认证装饰器风格
def require_virtual_key_auth(func):
    """
    装饰器：要求虚拟密钥认证
    类似claude-relay-service的authenticateApiKey中间件
    """
    async def wrapper(*args, **kwargs):
        # 这个装饰器主要用于文档说明
        # 实际认证逻辑通过Depends(get_authenticated_virtual_key)实现
        return await func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper