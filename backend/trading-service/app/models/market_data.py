"""
市场数据模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Index
from sqlalchemy.sql import func
from app.database import Base


class MarketData(Base):
    """市场数据模型 - 增强版，支持产品类型区分"""
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 1h, 1d
    product_type = Column(String(20), nullable=False, default='spot')  # spot, futures, swap
    open_price = Column(Numeric(18, 8), nullable=False)
    high_price = Column(Numeric(18, 8), nullable=False)
    low_price = Column(Numeric(18, 8), nullable=False)
    close_price = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(18, 8), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 创建复合索引以优化查询性能
    __table_args__ = (
        Index('idx_market_data_symbol_time', 'exchange', 'symbol', 'timeframe', 'timestamp'),
        Index('idx_market_data_product_type', 'exchange', 'symbol', 'product_type', 'timeframe'),
    )