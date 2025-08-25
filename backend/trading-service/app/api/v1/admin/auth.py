"""
管理员认证API - 登录、权限验证、会话管理
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.admin import Admin, AdminOperationLog
from app.models.user import User
from app.middleware.admin_auth import (
    get_current_admin, AdminUser, create_admin_token, 
    record_admin_login, revoke_admin_session
)
from app.core.rbac import RBACService, Permission
from app.core.security import verify_password

router = APIRouter(prefix="/admin/auth", tags=["管理员认证"])


class AdminLoginRequest(BaseModel):
    """管理员登录请求"""
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    """管理员登录响应"""
    access_token: str
    token_type: str
    admin_info: dict
    permissions: List[str]
    session_token: str


class AdminPermissionsResponse(BaseModel):
    """管理员权限响应"""
    permissions: List[str]
    role: str
    admin_id: int


class OperationLogResponse(BaseModel):
    """操作日志响应"""
    id: int
    operation: str
    resource_type: str
    resource_id: Optional[int]
    result: str
    ip_address: Optional[str]
    created_at: datetime


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: Request,
    login_data: AdminLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """管理员登录"""
    try:
        # 查询用户
        user_query = select(User).where(User.email == login_data.email)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱或密码错误"
            )
        
        # 检查是否为管理员
        admin_query = select(Admin).where(
            Admin.user_id == user.id,
            Admin.is_active == True
        )
        admin_result = await db.execute(admin_query)
        admin = admin_result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="非管理员用户"
            )
        
        # 获取管理员权限
        rbac_service = RBACService(db)
        permissions = await rbac_service.get_admin_permissions(admin.id)
        
        # 创建访问token
        access_token = await create_admin_token(
            user_id=user.id,
            admin_id=admin.id,
            role=admin.role
        )
        
        # 记录登录会话
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        session_token = await record_admin_login(
            admin_id=admin.id,
            ip_address=client_ip,
            user_agent=user_agent,
            db=db
        )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=admin.id,
            operation="login",
            resource_type="admin",
            resource_id=admin.id,
            ip_address=client_ip,
            user_agent=user_agent,
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return AdminLoginResponse(
            access_token=access_token,
            token_type="bearer",
            admin_info={
                "id": admin.id,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": admin.role,
                "department": admin.department
            },
            permissions=list(permissions),
            session_token=session_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )


@router.post("/logout")
async def admin_logout(
    request: Request,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """管理员登出"""
    try:
        # 获取会话token
        session_token = request.headers.get("x-session-token")
        if session_token:
            await revoke_admin_session(session_token, db)
        
        # 记录操作日志
        client_ip = request.client.host if request.client else "unknown"
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="logout",
            resource_type="admin",
            resource_id=current_admin.id,
            ip_address=client_ip,
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {"message": "登出成功"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登出失败: {str(e)}"
        )


@router.get("/permissions", response_model=AdminPermissionsResponse)
async def get_admin_permissions(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取当前管理员权限"""
    try:
        # 获取最新权限（防止权限变更后缓存问题）
        rbac_service = RBACService(db)
        permissions = await rbac_service.get_admin_permissions(current_admin.id)
        
        return AdminPermissionsResponse(
            permissions=list(permissions),
            role=current_admin.role,
            admin_id=current_admin.id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取权限失败: {str(e)}"
        )


@router.get("/me")
async def get_admin_info(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取当前管理员信息"""
    try:
        # 查询详细管理员信息
        admin_query = select(Admin).where(Admin.id == current_admin.id)
        admin_result = await db.execute(admin_query)
        admin = admin_result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="管理员信息不存在"
            )
        
        # 查询用户基本信息
        user_query = select(User).where(User.id == admin.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        return {
            "id": admin.id,
            "user_id": admin.user_id,
            "username": user.username if user else None,
            "email": user.email if user else None,
            "role": admin.role,
            "department": admin.department,
            "permissions": current_admin.permissions,
            "created_at": admin.created_at,
            "last_login": user.last_login_at if user else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取管理员信息失败: {str(e)}"
        )


@router.get("/operation-logs", response_model=List[OperationLogResponse])
async def get_operation_logs(
    current_admin: AdminUser = Depends(get_current_admin),
    page: int = 1,
    page_size: int = 20,
    operation: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取操作日志"""
    try:
        # 构建查询
        query = select(AdminOperationLog).where(
            AdminOperationLog.admin_id == current_admin.id
        )
        
        if operation:
            query = query.where(AdminOperationLog.operation.like(f"%{operation}%"))
        
        if resource_type:
            query = query.where(AdminOperationLog.resource_type == resource_type)
        
        # 分页和排序
        offset = (page - 1) * page_size
        query = query.order_by(AdminOperationLog.created_at.desc())
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return [
            OperationLogResponse(
                id=log.id,
                operation=log.operation,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                result=log.result,
                ip_address=log.ip_address,
                created_at=log.created_at
            )
            for log in logs
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取操作日志失败: {str(e)}"
        )


@router.post("/check-permission")
async def check_permission(
    permission: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """检查特定权限"""
    try:
        rbac_service = RBACService(db)
        has_permission = await rbac_service.check_permission(
            current_admin.id, permission
        )
        
        return {
            "permission": permission,
            "has_permission": has_permission,
            "admin_id": current_admin.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"权限检查失败: {str(e)}"
        )


@router.get("/available-permissions")
async def get_available_permissions():
    """获取所有可用权限列表"""
    try:
        permissions = [permission.value for permission in Permission]
        
        return {
            "permissions": permissions,
            "categories": {
                "user": [p for p in permissions if p.startswith("user:")],
                "claude": [p for p in permissions if p.startswith("claude:")],
                "payment": [p for p in permissions if p.startswith("payment:")],
                "data": [p for p in permissions if p.startswith("data:")],
                "strategy": [p for p in permissions if p.startswith("strategy:")],
                "trading": [p for p in permissions if p.startswith("trading:")],
                "system": [p for p in permissions if p.startswith("system:")],
                "content": [p for p in permissions if p.startswith("content:")],
                "special": [p for p in permissions if p == "*"]
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取权限列表失败: {str(e)}"
        )