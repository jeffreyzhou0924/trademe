"""
会员计划模型 - 与用户服务保持一致的表结构
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from sqlalchemy.sql import func
from app.database import Base


class MembershipPlan(Base):
    """会员计划模型 (与用户服务Prisma模型保持一致)"""
    __tablename__ = "membership_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    level = Column(String(50), nullable=False)
    duration_months = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    discount = Column(Integer, default=0)
    features = Column(Text, nullable=False)  # JSON string for SQLite
    is_active = Column(Boolean, default=True)
    popular = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())