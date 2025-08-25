"""
交易模型
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from app.database import Base


class Trade(Base):
    """交易模型"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Numeric(18, 8), nullable=False)
    price = Column(Numeric(18, 8), nullable=False)
    total_amount = Column(Numeric(18, 8), nullable=False)
    fee = Column(Numeric(18, 8), nullable=False)
    order_id = Column(String(100), nullable=True)
    trade_type = Column(String(20), nullable=False)  # BACKTEST, LIVE
    executed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())