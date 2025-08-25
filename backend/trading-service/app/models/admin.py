"""
管理员模型 - 管理后台用户模型
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Admin(Base):
    """管理员模型"""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="admin")
    permissions = Column(Text, nullable=False)  # JSON string
    department = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关联关系
    creator = relationship("Admin", remote_side=[id])


class AdminRole(Base):
    """管理员角色模型"""
    __tablename__ = "admin_roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(Text, nullable=False)  # JSON array of permissions
    is_system = Column(Boolean, default=False)  # 系统预定义角色不可删除
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AdminOperationLog(Base):
    """管理员操作日志模型"""
    __tablename__ = "admin_operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False, index=True)
    operation = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)  # JSON details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    result = Column(String(20), nullable=False)  # success, failed, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminSession(Base):
    """管理员会话模型"""
    __tablename__ = "admin_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False, index=True)
    session_token = Column(String(255), nullable=False, unique=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())