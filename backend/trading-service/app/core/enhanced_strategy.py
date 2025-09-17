"""
增强策略基类模块
提供AI生成策略的基础架构和数据请求功能
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod


class DataType(Enum):
    """数据类型枚举"""
    KLINE = "kline"
    TICK = "tick" 
    ORDER_BOOK = "order_book"


@dataclass
class DataRequest:
    """数据请求定义"""
    data_type: DataType
    exchange: str
    symbol: str
    timeframe: str
    required: bool = True


class EnhancedBaseStrategy(ABC):
    """增强策略基类"""
    
    def __init__(self, context=None):
        self.context = context
        self._kline_data = None
    
    @abstractmethod
    def get_data_requirements(self) -> List[DataRequest]:
        """获取策略数据需求"""
        pass
    
    @abstractmethod
    async def on_data_update(self, data_type: str, data: Dict[str, Any]):
        """数据更新回调"""
        pass
    
    def get_kline_data(self) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        return self._kline_data
    
    def get_current_position(self) -> float:
        """获取当前持仓"""
        return 0.0
    
    def calculate_sma(self, series: pd.Series, period: int) -> pd.Series:
        """计算简单移动平均线"""
        return series.rolling(window=period).mean()
    
    def calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """计算指数移动平均线"""
        return series.ewm(span=period).mean()
    
    def calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """计算MACD指标"""
        ema_fast = self.calculate_ema(series, fast)
        ema_slow = self.calculate_ema(series, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, series: pd.Series, period: int = 20, std_dev: float = 2) -> tuple:
        """计算布林带"""
        sma = self.calculate_sma(series, period)
        std = series.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    def calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                     k_period: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> tuple:
        """计算KDJ指标"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        rsv = 100 * (close - lowest_low) / (highest_high - lowest_low)
        rsv = rsv.fillna(50)
        
        k = rsv.ewm(span=k_smooth).mean()
        d = k.ewm(span=d_smooth).mean()
        j = 3 * k - 2 * d
        
        return k, d, j