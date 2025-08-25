"""
交易所相关数据模式
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime


class ExchangeInfo(BaseModel):
    """交易所信息"""
    name: str
    display_name: str
    supported: bool = True
    features: Dict[str, bool] = Field(default_factory=dict)


class ExchangeSymbols(BaseModel):
    """交易所交易对列表"""
    exchange: str
    symbols: List[str]
    total: int


class AccountBalance(BaseModel):
    """账户余额"""
    exchange: str
    timestamp: str
    balances: Dict[str, Dict[str, float]]


class MarketDataPoint(BaseModel):
    """市场数据点（K线）"""
    timestamp: int
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataRequest(BaseModel):
    """市场数据请求"""
    symbol: str = Field(..., description="交易对")
    timeframe: str = Field(default="1h", description="时间周期")
    limit: int = Field(default=100, ge=1, le=1000, description="数据点数量")


class MarketDataResponse(BaseModel):
    """市场数据响应"""
    exchange: str
    symbol: str
    timeframe: str
    data: List[MarketDataPoint]
    count: int


class OrderCreate(BaseModel):
    """创建订单请求"""
    symbol: str = Field(..., description="交易对，如 BTC/USDT")
    type: str = Field(..., pattern="^(market|limit)$", description="订单类型")
    side: str = Field(..., pattern="^(buy|sell)$", description="买卖方向")
    amount: float = Field(..., gt=0, description="订单数量")
    price: Optional[float] = Field(None, gt=0, description="价格（限价单必填）")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if '/' not in v:
            raise ValueError('交易对格式应为 BASE/QUOTE，如 BTC/USDT')
        return v.upper()


class OrderResponse(BaseModel):
    """订单响应"""
    id: str
    symbol: str
    type: str
    side: str
    amount: float
    price: Optional[float]
    status: str
    timestamp: Optional[int]
    exchange: str


class OrderStatus(BaseModel):
    """订单状态"""
    id: str
    symbol: str
    status: str
    filled: float
    remaining: float
    average: Optional[float]
    cost: float
    fee: Optional[Dict[str, Any]]
    timestamp: Optional[int]


class TradingFees(BaseModel):
    """交易手续费"""
    exchange: str
    maker: float
    taker: float
    percentage: bool = True
    tierBased: bool = False


class ApiKeyCreate(BaseModel):
    """API密钥创建"""
    name: str = Field(..., description="API密钥名称")
    exchange: str = Field(..., description="交易所名称")
    api_key: str = Field(..., min_length=10, description="API密钥")
    secret_key: str = Field(..., min_length=10, description="密钥")
    passphrase: Optional[str] = Field(None, description="密码短语（某些交易所需要）")
    
    @validator('exchange')
    def validate_exchange(cls, v):
        return v.lower()


class ApiKeyResponse(BaseModel):
    """API密钥响应"""
    id: int
    exchange: str
    api_key_masked: str  # 只显示前4位和后4位
    is_active: bool
    created_at: datetime
    
    @validator('api_key_masked', pre=True)
    def mask_api_key(cls, v):
        if isinstance(v, str) and len(v) > 8:
            return v[:4] + '*' * (len(v) - 8) + v[-4:]
        return v


class ApiKeyUpdate(BaseModel):
    """API密钥更新"""
    api_key: Optional[str] = Field(None, min_length=10)
    secret_key: Optional[str] = Field(None, min_length=10)
    passphrase: Optional[str] = None
    is_active: Optional[bool] = None


class ExchangeStatus(BaseModel):
    """交易所状态"""
    exchange: str
    connected: bool
    last_update: datetime
    error_message: Optional[str] = None


class TradeHistory(BaseModel):
    """交易历史"""
    id: str
    symbol: str
    side: str
    amount: float
    price: float
    cost: float
    fee: Dict[str, Any]
    timestamp: int
    exchange: str


class PositionInfo(BaseModel):
    """持仓信息（期货）"""
    symbol: str
    side: str  # long, short
    size: float
    contracts: float
    unrealized_pnl: float
    percentage: float
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float]
    margin_ratio: float


class ExchangeStatistics(BaseModel):
    """交易所统计信息"""
    exchange: str
    total_trades: int
    total_volume: float
    total_pnl: float
    win_rate: float
    avg_profit: float
    avg_loss: float
    sharpe_ratio: Optional[float]
    max_drawdown: Optional[float]