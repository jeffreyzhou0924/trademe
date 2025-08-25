"""
管理员认证中间件 - 管理后台专用认证
"""

import json
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt

from app.database import get_db
from app.models.admin import Admin, AdminSession
from app.models.user import User
from app.config import settings
from app.core.exceptions import AuthenticationError
from app.core.rbac import RBACService

security = HTTPBearer()


class AdminUser:
    """管理员用户模型（简化版）"""
    def __init__(self, admin_id: int, user_id: int, role: str, permissions: list):
        self.id = admin_id
        self.user_id = user_id
        self.role = role
        self.permissions = permissions
        self.username = None
        self.email = None


async def verify_admin_token(token: str, db: AsyncSession) -> Optional[AdminUser]:
    """验证管理员token"""
    try:
        # 解码JWT token
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id: int = payload.get("user_id")
        token_type: str = payload.get("type")
        
        if not user_id or token_type != "admin_access":
            return None
        
        # 查询管理员信息
        query = select(Admin).where(Admin.user_id == user_id, Admin.is_active == True)
        result = await db.execute(query)
        admin = result.scalar_one_or_none()
        
        if not admin:
            return None
        
        # 查询用户基本信息
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            return None
        
        # 获取管理员权限
        rbac_service = RBACService(db)
        permissions = await rbac_service.get_admin_permissions(admin.id)
        
        # 创建管理员用户对象
        admin_user = AdminUser(
            admin_id=admin.id,
            user_id=user_id,
            role=admin.role,
            permissions=list(permissions)
        )
        admin_user.username = user.username
        admin_user.email = user.email
        
        return admin_user
        
    except JWTError as e:
        print(f"JWT验证失败: {e}")
        return None
    except Exception as e:
        print(f"管理员token验证失败: {e}")
        return None


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> AdminUser:
    """获取当前管理员用户（依赖注入）"""
    
    token = None
    
    # 首先尝试从HTTP Bearer token获取
    if credentials:
        token = credentials.credentials
    else:
        # 备用方案：从请求头手动提取
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少管理员认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证token
    admin_user = await verify_admin_token(token, db)
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的管理员认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return admin_user


async def create_admin_token(user_id: int, admin_id: int, role: str) -> str:
    """创建管理员访问token"""
    try:
        expire = datetime.utcnow() + timedelta(hours=8)  # 8小时有效期
        payload = {
            "user_id": user_id,
            "admin_id": admin_id,
            "role": role,
            "type": "admin_access",
            "exp": expire.timestamp(),
            "iat": datetime.utcnow().timestamp()
        }
        
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
        return token
        
    except Exception as e:
        raise AuthenticationError(f"创建管理员token失败: {e}")


async def record_admin_login(
    admin_id: int, 
    ip_address: str, 
    user_agent: str, 
    db: AsyncSession
) -> str:
    """记录管理员登录并创建会话"""
    try:
        # 创建会话token
        import secrets
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)  # 24小时会话
        
        # 创建会话记录
        session = AdminSession(
            admin_id=admin_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            last_activity=datetime.utcnow()
        )
        
        db.add(session)
        await db.commit()
        
        return session_token
        
    except Exception as e:
        await db.rollback()
        raise AuthenticationError(f"记录管理员登录失败: {e}")


async def update_admin_activity(session_token: str, db: AsyncSession):
    """更新管理员活动时间"""
    try:
        query = select(AdminSession).where(
            AdminSession.session_token == session_token,
            AdminSession.is_active == True
        )
        result = await db.execute(query)
        session = result.scalar_one_or_none()
        
        if session:
            session.last_activity = datetime.utcnow()
            await db.commit()
            
    except Exception as e:
        print(f"更新管理员活动时间失败: {e}")


async def revoke_admin_session(session_token: str, db: AsyncSession):
    """撤销管理员会话"""
    try:
        query = select(AdminSession).where(
            AdminSession.session_token == session_token
        )
        result = await db.execute(query)
        session = result.scalar_one_or_none()
        
        if session:
            session.is_active = False
            await db.commit()
            
    except Exception as e:
        await db.rollback()
        raise AuthenticationError(f"撤销管理员会话失败: {e}")


async def cleanup_expired_sessions(db: AsyncSession):
    """清理过期会话"""
    try:
        from sqlalchemy import update
        
        # 标记过期会话为非活跃状态
        query = update(AdminSession).where(
            AdminSession.expires_at < datetime.utcnow(),
            AdminSession.is_active == True
        ).values(is_active=False)
        
        await db.execute(query)
        await db.commit()
        
        print("✅ 管理员过期会话清理完成")
        
    except Exception as e:
        await db.rollback()
        print(f"❌ 清理管理员过期会话失败: {e}")


class AdminAuthMiddleware:
    """管理员认证中间件类"""
    
    def __init__(self):
        self.rbac_service = None
    
    async def authenticate_admin(
        self, 
        request: Request, 
        db: AsyncSession
    ) -> Optional[AdminUser]:
        """管理员身份验证"""
        try:
            # 提取token
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            
            token = auth_header[7:]
            admin_user = await verify_admin_token(token, db)
            
            if admin_user:
                # 更新活动时间（如果有会话token）
                session_token = request.headers.get("x-session-token")
                if session_token:
                    await update_admin_activity(session_token, db)
            
            return admin_user
            
        except Exception as e:
            print(f"管理员身份验证失败: {e}")
            return None
    
    async def check_permission(
        self, 
        admin_user: AdminUser, 
        required_permission: str,
        db: AsyncSession
    ) -> bool:
        """检查管理员权限"""
        try:
            if not self.rbac_service:
                self.rbac_service = RBACService(db)
            
            return await self.rbac_service.check_permission(
                admin_user.id, required_permission
            )
            
        except Exception as e:
            print(f"权限检查失败: {e}")
            return False


# 全局管理员认证中间件实例
admin_auth_middleware = AdminAuthMiddleware()