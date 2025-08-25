"""
实盘交易策略模型
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from app.database import Base


class LiveStrategy(Base):
    """实盘交易策略模型"""
    __tablename__ = "live_strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # running, paused, stopped
    start_time = Column(DateTime(timezone=True))
    stop_time = Column(DateTime(timezone=True))
    total_trades = Column(Integer, default=0)
    profit_loss = Column(Numeric(15, 4), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())