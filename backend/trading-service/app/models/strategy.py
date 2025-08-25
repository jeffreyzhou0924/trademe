"""
策略模型
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Strategy(Base):
    """策略模型"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    code = Column(Text, nullable=False)
    parameters = Column(Text, nullable=True)  # JSON string
    strategy_type = Column(String(20), default="strategy")  # strategy, indicator
    ai_session_id = Column(String(100), nullable=True)  # 关联的AI会话ID
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # 是否公开分享
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())