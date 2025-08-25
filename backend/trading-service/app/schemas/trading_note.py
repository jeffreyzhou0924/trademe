"""
交易心得API请求和响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.trading_note import NoteCategory


class TradingNoteCreate(BaseModel):
    """创建交易心得请求模型"""
    title: str = Field(..., min_length=1, max_length=200, description="心得标题")
    content: str = Field(..., min_length=1, description="心得内容")
    category: NoteCategory = Field(..., description="分类")
    
    # 交易相关信息（可选）
    symbol: Optional[str] = Field(None, max_length=20, description="交易对")
    entry_price: Optional[str] = Field(None, max_length=50, description="入场价格")
    exit_price: Optional[str] = Field(None, max_length=50, description="出场价格")
    stop_loss: Optional[str] = Field(None, max_length=50, description="止损价格")
    take_profit: Optional[str] = Field(None, max_length=50, description="止盈价格")
    position_size: Optional[str] = Field(None, max_length=50, description="仓位大小")
    result: Optional[str] = Field(None, max_length=100, description="交易结果")
    
    # 标签
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    is_public: Optional[bool] = Field(False, description="是否公开")


class TradingNoteUpdate(BaseModel):
    """更新交易心得请求模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="心得标题")
    content: Optional[str] = Field(None, min_length=1, description="心得内容")
    category: Optional[NoteCategory] = Field(None, description="分类")
    
    # 交易相关信息（可选）
    symbol: Optional[str] = Field(None, max_length=20, description="交易对")
    entry_price: Optional[str] = Field(None, max_length=50, description="入场价格")
    exit_price: Optional[str] = Field(None, max_length=50, description="出场价格")
    stop_loss: Optional[str] = Field(None, max_length=50, description="止损价格")
    take_profit: Optional[str] = Field(None, max_length=50, description="止盈价格")
    position_size: Optional[str] = Field(None, max_length=50, description="仓位大小")
    result: Optional[str] = Field(None, max_length=100, description="交易结果")
    
    # 标签
    tags: Optional[List[str]] = Field(None, description="标签列表")
    is_public: Optional[bool] = Field(None, description="是否公开")


class TradingNoteResponse(BaseModel):
    """交易心得响应模型"""
    id: int
    title: str
    content: str
    category: NoteCategory
    
    # 交易相关信息
    symbol: Optional[str] = None
    entry_price: Optional[str] = None
    exit_price: Optional[str] = None
    stop_loss: Optional[str] = None
    take_profit: Optional[str] = None
    position_size: Optional[str] = None
    result: Optional[str] = None
    
    # 标签和元数据
    tags: List[str] = []
    
    # 社交功能
    likes_count: int = 0
    comments_count: int = 0
    is_public: bool = False
    is_liked: Optional[bool] = None  # 当前用户是否已点赞
    
    # 时间戳
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradingNoteListResponse(BaseModel):
    """交易心得列表响应模型"""
    notes: List[TradingNoteResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TradingNoteFilters(BaseModel):
    """交易心得筛选参数"""
    category: Optional[NoteCategory] = None
    symbol: Optional[str] = None
    search: Optional[str] = None  # 搜索关键词
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class CommentCreate(BaseModel):
    """创建评论请求模型"""
    content: str = Field(..., min_length=1, max_length=500, description="评论内容")
    parent_id: Optional[int] = Field(None, description="父评论ID")


class CommentResponse(BaseModel):
    """评论响应模型"""
    id: int
    content: str
    user_id: int
    parent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradingNoteStats(BaseModel):
    """交易心得统计信息"""
    total_notes: int
    notes_by_category: dict
    storage_used: float  # GB
    storage_limit: float  # GB