"""
用户模型 - 基础用户信息
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """用户模型（简化版本，主要用于类型提示）"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    google_id = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(Text, nullable=True)
    membership_level = Column(String(20), default="basic")
    membership_expires_at = Column(DateTime, nullable=True)
    email_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())