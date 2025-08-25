"""
交易心得数据模型
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class NoteCategory(str, enum.Enum):
    """心得分类枚举"""
    TECHNICAL_ANALYSIS = "technical_analysis"  # 技术分析
    FUNDAMENTAL = "fundamental"  # 基本面
    STRATEGY_SUMMARY = "strategy_summary"  # 策略总结
    ERROR_REVIEW = "error_review"  # 错误复盘
    MARKET_VIEW = "market_view"  # 市场观点


class TradingNote(Base):
    """交易心得模型"""
    __tablename__ = "trading_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 基本信息
    title = Column(String(200), nullable=False, comment="心得标题")
    content = Column(Text, nullable=False, comment="心得内容")
    category = Column(Enum(NoteCategory), nullable=False, comment="分类")
    
    # 交易相关信息
    symbol = Column(String(20), comment="交易对 如BTC/USDT")
    entry_price = Column(String(50), comment="入场价格")
    exit_price = Column(String(50), comment="出场价格")
    stop_loss = Column(String(50), comment="止损价格")
    take_profit = Column(String(50), comment="止盈价格")
    position_size = Column(String(50), comment="仓位大小")
    result = Column(String(100), comment="交易结果")
    
    # 标签和元数据
    tags = Column(Text, comment="标签，JSON格式存储")
    
    # 社交功能
    likes_count = Column(Integer, default=0, comment="点赞数")
    comments_count = Column(Integer, default=0, comment="评论数")
    is_public = Column(Boolean, default=False, comment="是否公开")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<TradingNote(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class TradingNoteLike(Base):
    """交易心得点赞模型"""
    __tablename__ = "trading_note_likes"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("trading_notes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 联合唯一索引，防止重复点赞
    __table_args__ = (
        {'mysql_charset': 'utf8mb4'},
    )


class TradingNoteComment(Base):
    """交易心得评论模型"""
    __tablename__ = "trading_note_comments"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("trading_notes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False, comment="评论内容")
    parent_id = Column(Integer, ForeignKey("trading_note_comments.id"), comment="父评论ID，用于回复")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TradingNoteComment(id={self.id}, note_id={self.note_id}, user_id={self.user_id})>"