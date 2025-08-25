"""
回测模型
"""

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from app.database import Base


class Backtest(Base):
    """回测模型"""
    __tablename__ = "backtests"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Numeric(15, 2), nullable=False)
    final_capital = Column(Numeric(15, 2), nullable=True)
    total_return = Column(Numeric(8, 4), nullable=True)
    max_drawdown = Column(Numeric(8, 4), nullable=True)
    sharpe_ratio = Column(Numeric(6, 4), nullable=True)
    results = Column(Text, nullable=True)  # JSON string
    status = Column(String(20), default="RUNNING")
    created_at = Column(DateTime(timezone=True), server_default=func.now())