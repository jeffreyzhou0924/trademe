"""
RBAC权限控制系统 - 基于角色的访问控制
"""

from enum import Enum
from typing import Dict, List, Optional, Set
from functools import wraps
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin import Admin, AdminRole
from app.core.exceptions import PermissionError, AuthenticationError


class Permission(Enum):
    """权限枚举"""
    # 用户管理权限
    USER_READ = "user:read"
    USER_WRITE = "user:write" 
    USER_DELETE = "user:delete"
    USER_MANAGE = "user:manage"  # 包含用户状态、会员等级管理
    
    # Claude服务管理权限
    CLAUDE_READ = "claude:read"
    CLAUDE_WRITE = "claude:write"
    CLAUDE_CONFIG = "claude:config"
    CLAUDE_MANAGE = "claude:manage"
    
    # 支付管理权限
    PAYMENT_READ = "payment:read"
    PAYMENT_WRITE = "payment:write"
    PAYMENT_MANAGE = "payment:manage"
    WALLET_MANAGE = "wallet:manage"
    
    # 数据采集管理权限
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_CONFIG = "data:config"
    DATA_MANAGE = "data:manage"
    
    # 策略管理权限
    STRATEGY_READ = "strategy:read"
    STRATEGY_WRITE = "strategy:write"
    STRATEGY_AUDIT = "strategy:audit"
    STRATEGY_MANAGE = "strategy:manage"
    
    # 交易管理权限
    TRADING_READ = "trading:read"
    TRADING_WRITE = "trading:write"
    TRADING_MANAGE = "trading:manage"
    
    # 系统管理权限
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MANAGE = "system:manage"
    
    # 内容管理权限
    CONTENT_READ = "content:read"
    CONTENT_WRITE = "content:write"
    CONTENT_MANAGE = "content:manage"
    
    # 超级管理员权限
    SUPER_ADMIN = "*"


class Role(Enum):
    """预定义角色枚举"""
    SUPER_ADMIN = "super_admin"
    USER_MANAGER = "user_manager"
    AI_MANAGER = "ai_manager"
    FINANCE_MANAGER = "finance_manager"
    DATA_MANAGER = "data_manager"
    STRATEGY_MANAGER = "strategy_manager"
    SYSTEM_ADMIN = "system_admin"
    CONTENT_MANAGER = "content_manager"
    OBSERVER = "observer"


# 角色权限映射
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: {Permission.SUPER_ADMIN},
    
    Role.USER_MANAGER: {
        Permission.USER_READ, Permission.USER_WRITE, 
        Permission.USER_DELETE, Permission.USER_MANAGE
    },
    
    Role.AI_MANAGER: {
        Permission.CLAUDE_READ, Permission.CLAUDE_WRITE,
        Permission.CLAUDE_CONFIG, Permission.CLAUDE_MANAGE,
        Permission.USER_READ  # 需要查看用户AI使用情况
    },
    
    Role.FINANCE_MANAGER: {
        Permission.PAYMENT_READ, Permission.PAYMENT_WRITE,
        Permission.PAYMENT_MANAGE, Permission.WALLET_MANAGE,
        Permission.USER_READ  # 需要查看用户会员信息
    },
    
    Role.DATA_MANAGER: {
        Permission.DATA_READ, Permission.DATA_WRITE,
        Permission.DATA_CONFIG, Permission.DATA_MANAGE,
        Permission.SYSTEM_READ  # 需要查看系统性能
    },
    
    Role.STRATEGY_MANAGER: {
        Permission.STRATEGY_READ, Permission.STRATEGY_WRITE,
        Permission.STRATEGY_AUDIT, Permission.STRATEGY_MANAGE,
        Permission.TRADING_READ, Permission.USER_READ
    },
    
    Role.SYSTEM_ADMIN: {
        Permission.SYSTEM_READ, Permission.SYSTEM_WRITE,
        Permission.SYSTEM_CONFIG, Permission.SYSTEM_MANAGE,
        Permission.DATA_READ, Permission.CLAUDE_READ
    },
    
    Role.CONTENT_MANAGER: {
        Permission.CONTENT_READ, Permission.CONTENT_WRITE,
        Permission.CONTENT_MANAGE, Permission.USER_READ
    },
    
    Role.OBSERVER: {
        Permission.USER_READ, Permission.CLAUDE_READ, Permission.PAYMENT_READ,
        Permission.DATA_READ, Permission.STRATEGY_READ, Permission.TRADING_READ,
        Permission.SYSTEM_READ, Permission.CONTENT_READ
    }
}


class RBACService:
    """RBAC权限服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_admin_permissions(self, admin_id: int) -> Set[str]:
        """获取管理员权限"""
        try:
            # 查询管理员信息
            result = await self.db.execute(
                "SELECT a.permissions, ar.permissions FROM admins a "
                "LEFT JOIN admin_roles ar ON a.role = ar.name "
                "WHERE a.id = ? AND a.is_active = 1",
                (admin_id,)
            )
            row = result.fetchone()
            
            if not row:
                return set()
            
            admin_permissions, role_permissions = row
            
            # 合并管理员个人权限和角色权限
            permissions = set()
            
            if admin_permissions:
                import json
                permissions.update(json.loads(admin_permissions))
            
            if role_permissions:
                import json
                permissions.update(json.loads(role_permissions))
            
            return permissions
            
        except Exception as e:
            print(f"获取管理员权限失败: {e}")
            return set()
    
    def has_permission(self, user_permissions: Set[str], required_permission: str) -> bool:
        """检查是否有指定权限"""
        # 超级管理员拥有所有权限
        if Permission.SUPER_ADMIN.value in user_permissions:
            return True
        
        # 检查具体权限
        if required_permission in user_permissions:
            return True
        
        # 检查通配符权限
        permission_parts = required_permission.split(':')
        if len(permission_parts) == 2:
            wildcard_permission = f"{permission_parts[0]}:*"
            if wildcard_permission in user_permissions:
                return True
        
        return False
    
    async def check_permission(self, admin_id: int, required_permission: str) -> bool:
        """检查管理员是否有指定权限"""
        user_permissions = await self.get_admin_permissions(admin_id)
        return self.has_permission(user_permissions, required_permission)
    
    async def create_default_roles(self):
        """创建默认角色"""
        try:
            import json
            
            for role, permissions in ROLE_PERMISSIONS.items():
                # 检查角色是否已存在
                result = await self.db.execute(
                    "SELECT id FROM admin_roles WHERE name = ?",
                    (role.value,)
                )
                if result.fetchone():
                    continue
                
                # 创建角色
                permissions_json = json.dumps([p.value for p in permissions])
                await self.db.execute(
                    "INSERT INTO admin_roles (name, description, permissions, is_system) "
                    "VALUES (?, ?, ?, 1)",
                    (role.value, f"系统预定义角色: {role.value}", permissions_json)
                )
            
            await self.db.commit()
            print("✅ 默认角色创建成功")
            
        except Exception as e:
            await self.db.rollback()
            print(f"❌ 创建默认角色失败: {e}")
    
    async def assign_role_to_admin(self, admin_id: int, role_name: str):
        """为管理员分配角色"""
        try:
            await self.db.execute(
                "UPDATE admins SET role = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (role_name, admin_id)
            )
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            raise PermissionError(f"分配角色失败: {e}")


def require_permission(permission: str):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取数据库session和当前管理员
            db = kwargs.get('db')
            current_admin = kwargs.get('current_admin')
            
            if not db or not current_admin:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="需要管理员权限"
                )
            
            # 检查权限
            rbac_service = RBACService(db)
            has_permission = await rbac_service.check_permission(
                current_admin.id, permission
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限: {permission}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_any_permission(*permissions: str):
    """需要任意一个权限的装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            current_admin = kwargs.get('current_admin')
            
            if not db or not current_admin:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="需要管理员权限"
                )
            
            # 检查是否有任意一个权限
            rbac_service = RBACService(db)
            has_any_permission = False
            
            for permission in permissions:
                if await rbac_service.check_permission(current_admin.id, permission):
                    has_any_permission = True
                    break
            
            if not has_any_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限，需要以下权限之一: {', '.join(permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_all_permissions(*permissions: str):
    """需要所有权限的装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            current_admin = kwargs.get('current_admin')
            
            if not db or not current_admin:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="需要管理员权限"
                )
            
            # 检查是否有所有权限
            rbac_service = RBACService(db)
            missing_permissions = []
            
            for permission in permissions:
                if not await rbac_service.check_permission(current_admin.id, permission):
                    missing_permissions.append(permission)
            
            if missing_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少权限: {', '.join(missing_permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# 权限工具函数
async def get_rbac_service(db: AsyncSession = Depends(get_db)) -> RBACService:
    """获取RBAC服务依赖"""
    return RBACService(db)


async def init_rbac_system(db: AsyncSession):
    """初始化RBAC系统"""
    rbac_service = RBACService(db)
    await rbac_service.create_default_roles()
    print("✅ RBAC权限系统初始化完成")