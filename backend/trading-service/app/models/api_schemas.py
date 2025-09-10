"""
API模式定义
提供所有API端点的Pydantic模型，包含完整的验证规则和文档
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
import re
from pydantic import BaseModel, Field, validator, root_validator
from fastapi import HTTPException

# ===========================================
# 基础枚举类型
# ===========================================

class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class StrategyStatus(str, Enum):
    """策略状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"

class TimeInterval(str, Enum):
    """时间间隔"""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"

class MembershipLevel(str, Enum):
    """会员级别"""
    BASIC = "basic"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"

# ===========================================
# 基础模型
# ===========================================

class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, le=1000, description="页码")
    limit: int = Field(20, ge=1, le=100, description="每页数量")
    sort_by: Optional[str] = Field(None, description="排序字段")
    sort_order: Optional[str] = Field("desc", regex="^(asc|desc)$", description="排序方向")

# ===========================================
# 用户相关模型
# ===========================================

class UserRegistration(BaseModel):
    """用户注册"""
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    confirm_password: str = Field(..., description="确认密码")
    membership_level: Optional[MembershipLevel] = Field(MembershipLevel.BASIC, description="会员级别")
    
    @validator('email')
    def validate_email(cls, v):
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('邮箱格式无效')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度不能少于8位')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('密码必须包含字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v
    
    @root_validator
    def validate_passwords_match(cls, values):
        password = values.get('password')
        confirm_password = values.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise ValueError('两次输入的密码不一致')
        return values

class UserLogin(BaseModel):
    """用户登录"""
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")
    remember_me: bool = Field(False, description="记住登录状态")
    captcha_token: Optional[str] = Field(None, description="验证码令牌")

class UserProfile(BaseModel):
    """用户资料"""
    user_id: int
    email: str
    membership_level: MembershipLevel
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    preferences: Optional[Dict[str, Any]] = None

class UpdateUserProfile(BaseModel):
    """更新用户资料"""
    preferences: Optional[Dict[str, Any]] = Field(None, description="用户偏好设置")
    notification_settings: Optional[Dict[str, bool]] = Field(None, description="通知设置")

# ===========================================
# 交易相关模型
# ===========================================

class CreateOrderRequest(BaseModel):
    """创建订单请求"""
    symbol: str = Field(..., description="交易对")
    side: OrderSide = Field(..., description="买入/卖出")
    type: OrderType = Field(..., description="订单类型")
    quantity: Decimal = Field(..., gt=0, description="数量")
    price: Optional[Decimal] = Field(None, gt=0, description="价格（限价单必填）")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="止损价格")
    time_in_force: Optional[str] = Field("GTC", description="有效期类型")
    client_order_id: Optional[str] = Field(None, description="客户端订单ID")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        symbol_pattern = r'^[A-Z]{3,10}[/-]?[A-Z]{3,10}$'
        if not re.match(symbol_pattern, v.upper()):
            raise ValueError('交易对格式无效')
        return v.upper()
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('数量必须大于0')
        # 检查小数位数
        if v.as_tuple().exponent < -8:
            raise ValueError('数量小数位数不能超过8位')
        return v
    
    @root_validator
    def validate_price_for_limit_order(cls, values):
        order_type = values.get('type')
        price = values.get('price')
        
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not price:
            raise ValueError('限价单必须指定价格')
        
        return values

class OrderResponse(BaseModel):
    """订单响应"""
    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Optional[Decimal]
    status: OrderStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal
    avg_price: Optional[Decimal] = None

class CancelOrderRequest(BaseModel):
    """取消订单请求"""
    order_id: str = Field(..., description="订单ID")
    
    @validator('order_id')
    def validate_order_id(cls, v):
        if not v or len(v) < 8:
            raise ValueError('订单ID格式无效')
        return v

# ===========================================
# 策略相关模型
# ===========================================

class CreateStrategyRequest(BaseModel):
    """创建策略请求"""
    name: str = Field(..., min_length=1, max_length=100, description="策略名称")
    description: Optional[str] = Field(None, max_length=500, description="策略描述")
    code: str = Field(..., description="策略代码")
    symbols: List[str] = Field(..., min_items=1, description="交易对列表")
    parameters: Optional[Dict[str, Any]] = Field(None, description="策略参数")
    risk_parameters: Optional[Dict[str, Any]] = Field(None, description="风险参数")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        symbol_pattern = r'^[A-Z]{3,10}[/-]?[A-Z]{3,10}$'
        for symbol in v:
            if not re.match(symbol_pattern, symbol.upper()):
                raise ValueError(f'交易对格式无效: {symbol}')
        return [s.upper() for s in v]
    
    @validator('code')
    def validate_code(cls, v):
        if len(v) > 50000:  # 50KB限制
            raise ValueError('策略代码长度超过限制')
        
        # 检查危险操作
        dangerous_patterns = [
            r'\b(exec|eval|compile|__import__)\b',
            r'\b(os\.system|subprocess)\b',
            r'\b(open|file)\b'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(f'策略代码包含不安全操作: {pattern}')
        
        return v

class UpdateStrategyRequest(BaseModel):
    """更新策略请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="策略名称")
    description: Optional[str] = Field(None, max_length=500, description="策略描述")
    code: Optional[str] = Field(None, description="策略代码")
    parameters: Optional[Dict[str, Any]] = Field(None, description="策略参数")
    risk_parameters: Optional[Dict[str, Any]] = Field(None, description="风险参数")
    status: Optional[StrategyStatus] = Field(None, description="策略状态")

class StrategyResponse(BaseModel):
    """策略响应"""
    strategy_id: int
    user_id: int
    name: str
    description: Optional[str]
    status: StrategyStatus
    symbols: List[str]
    created_at: datetime
    updated_at: Optional[datetime]
    parameters: Optional[Dict[str, Any]]
    risk_parameters: Optional[Dict[str, Any]]
    performance_metrics: Optional[Dict[str, Any]] = None

# ===========================================
# 回测相关模型
# ===========================================

class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_id: int = Field(..., description="策略ID")
    symbol: str = Field(..., description="交易对")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    initial_capital: Decimal = Field(..., gt=0, description="初始资金")
    commission_rate: Optional[Decimal] = Field(Decimal('0.001'), ge=0, description="手续费率")
    slippage_rate: Optional[Decimal] = Field(Decimal('0.0001'), ge=0, description="滑点率")
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('结束日期必须晚于开始日期')
        return v
    
    @validator('symbol')
    def validate_symbol(cls, v):
        symbol_pattern = r'^[A-Z]{3,10}[/-]?[A-Z]{3,10}$'
        if not re.match(symbol_pattern, v.upper()):
            raise ValueError('交易对格式无效')
        return v.upper()

class BacktestResult(BaseModel):
    """回测结果"""
    backtest_id: int
    strategy_id: int
    symbol: str
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_capital: Decimal
    total_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    win_rate: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    created_at: datetime

# ===========================================
# AI相关模型
# ===========================================

class AIRequestBase(BaseModel):
    """AI请求基础模型"""
    content: str = Field(..., min_length=1, max_length=5000, description="消息内容")
    session_type: str = Field("general", description="会话类型")
    session_id: Optional[str] = Field(None, description="会话ID")
    
    @validator('content')
    def validate_content(cls, v):
        # 检查内容安全性
        if re.search(r'<script|javascript:|onerror=', v, re.IGNORECASE):
            raise ValueError('消息内容包含不安全字符')
        return v.strip()

class AIChatRequest(AIRequestBase):
    """AI聊天请求"""
    ai_mode: Optional[str] = Field("general", description="AI模式")
    include_context: bool = Field(True, description="是否包含上下文")
    max_tokens: Optional[int] = Field(None, ge=1, le=4000, description="最大令牌数")

class AIChatResponse(BaseModel):
    """AI聊天响应"""
    session_id: str
    response: str
    token_usage: Dict[str, int]
    model_info: Dict[str, str]
    timestamp: datetime
    context_used: bool = True

class AISessionInfo(BaseModel):
    """AI会话信息"""
    session_id: str
    user_id: int
    session_type: str
    created_at: datetime
    last_active: datetime
    message_count: int
    total_tokens: int

# ===========================================
# 市场数据相关模型
# ===========================================

class MarketDataRequest(BaseModel):
    """市场数据请求"""
    symbol: str = Field(..., description="交易对")
    interval: TimeInterval = Field(..., description="时间间隔")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    limit: Optional[int] = Field(500, ge=1, le=1000, description="数据条数")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        symbol_pattern = r'^[A-Z]{3,10}[/-]?[A-Z]{3,10}$'
        if not re.match(symbol_pattern, v.upper()):
            raise ValueError('交易对格式无效')
        return v.upper()
    
    @root_validator
    def validate_time_range(cls, values):
        start_time = values.get('start_time')
        end_time = values.get('end_time')
        
        if start_time and end_time and end_time <= start_time:
            raise ValueError('结束时间必须晚于开始时间')
        
        return values

class KlineData(BaseModel):
    """K线数据"""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    interval: TimeInterval

class MarketTicker(BaseModel):
    """市场行情"""
    symbol: str
    price: Decimal
    volume: Decimal
    change_24h: Decimal
    change_percent_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal
    timestamp: datetime

# ===========================================
# 钱包相关模型
# ===========================================

class WalletBalance(BaseModel):
    """钱包余额"""
    asset: str
    balance: Decimal
    locked: Decimal = Decimal('0')
    available: Decimal

class TransferRequest(BaseModel):
    """转账请求"""
    to_address: str = Field(..., description="目标地址")
    amount: Decimal = Field(..., gt=0, description="转账金额")
    asset: str = Field(..., description="资产类型")
    network: Optional[str] = Field("TRC20", description="网络类型")
    memo: Optional[str] = Field(None, max_length=200, description="备注")
    
    @validator('to_address')
    def validate_address(cls, v):
        # 简化的地址格式验证
        if len(v) < 25 or len(v) > 62:
            raise ValueError('钱包地址格式无效')
        return v

class TransferResponse(BaseModel):
    """转账响应"""
    transfer_id: str
    tx_hash: Optional[str]
    status: str
    created_at: datetime

# ===========================================
# 数据管理相关模型
# ===========================================

class DataDownloadRequest(BaseModel):
    """数据下载请求"""
    exchange: str = Field(..., description="交易所")
    symbols: List[str] = Field(..., min_items=1, max_items=50, description="交易对列表")
    data_type: str = Field(..., description="数据类型")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    intervals: Optional[List[TimeInterval]] = Field(None, description="时间间隔")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        symbol_pattern = r'^[A-Z]{3,10}[/-]?[A-Z]{3,10}$'
        validated_symbols = []
        for symbol in v:
            if not re.match(symbol_pattern, symbol.upper()):
                raise ValueError(f'交易对格式无效: {symbol}')
            validated_symbols.append(symbol.upper())
        return validated_symbols
    
    @root_validator
    def validate_date_range(cls, values):
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise ValueError('结束日期必须晚于开始日期')
            
            # 限制下载时间范围（比如最多6个月）
            if (end_date - start_date).days > 180:
                raise ValueError('下载时间范围不能超过6个月')
        
        return values

class DataTaskInfo(BaseModel):
    """数据任务信息"""
    task_id: str
    status: str
    progress: float
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]

# ===========================================
# 系统管理相关模型
# ===========================================

class SystemStatus(BaseModel):
    """系统状态"""
    service_name: str
    status: str
    uptime: float
    memory_usage: Dict[str, Any]
    database_status: str
    cache_status: str
    timestamp: datetime

class UserStatsResponse(BaseModel):
    """用户统计响应"""
    total_users: int
    active_users: int
    new_users_today: int
    premium_users: int
    professional_users: int

class TradingStatsResponse(BaseModel):
    """交易统计响应"""
    total_orders: int
    active_orders: int
    completed_orders: int
    total_volume: Decimal
    success_rate: float

# ===========================================
# 错误响应模型
# ===========================================

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ValidationErrorResponse(BaseModel):
    """验证错误响应"""
    success: bool = False
    message: str = "参数验证失败"
    validation_errors: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ===========================================
# 通用查询模型
# ===========================================

class DateRangeQuery(BaseModel):
    """日期范围查询"""
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    
    @root_validator
    def validate_date_range(cls, values):
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        
        if start_date and end_date and end_date <= start_date:
            raise ValueError('结束日期必须晚于开始日期')
        
        return values

class SearchQuery(BaseModel):
    """搜索查询"""
    keyword: str = Field(..., min_length=1, max_length=100, description="搜索关键词")
    search_type: Optional[str] = Field("all", description="搜索类型")
    
    @validator('keyword')
    def validate_keyword(cls, v):
        # 检查搜索关键词安全性
        if re.search(r'[<>"\';]', v):
            raise ValueError('搜索关键词包含不安全字符')
        return v.strip()

# ===========================================
# 批量操作模型
# ===========================================

class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    action: str = Field(..., description="操作类型")
    items: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100, description="操作项目")
    options: Optional[Dict[str, Any]] = Field(None, description="操作选项")

class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    total_items: int
    successful_items: int
    failed_items: int
    results: List[Dict[str, Any]]
    errors: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)