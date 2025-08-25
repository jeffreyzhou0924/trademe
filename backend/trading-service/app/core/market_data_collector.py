"""
市场数据采集器 - OKX交易所数据采集

支持K线数据、实时tick数据采集，使用CCXT库和WebSocket
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
import ccxt.pro as ccxt
import pandas as pd
from loguru import logger
import aiohttp
import websockets
from dataclasses import dataclass

from app.config import settings
from app.models.market_data import MarketData
from app.database import AsyncSessionLocal


class DataType(Enum):
    """数据类型枚举"""
    KLINE = "kline"
    TICK = "tick"
    ORDER_BOOK = "orderbook"
    TRADES = "trades"


@dataclass
class KlineData:
    """K线数据结构"""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    exchange: str = "okx"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "exchange": self.exchange
        }


@dataclass
class TickData:
    """Tick数据结构"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    price: float  # 最新成交价
    volume: float  # 成交量
    exchange: str = "okx"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "bid": self.bid,
            "ask": self.ask,
            "price": self.price,
            "volume": self.volume,
            "exchange": self.exchange
        }


class OKXDataCollector:
    """OKX数据采集器"""
    
    def __init__(self):
        self.exchange = None
        self.websocket_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.rest_url = "https://www.okx.com"
        
        # 数据回调
        self.kline_callbacks: List[Callable] = []
        self.tick_callbacks: List[Callable] = []
        
        # WebSocket连接
        self.ws_connections: Dict[str, Any] = {}
        self.subscribed_symbols: Dict[str, List[str]] = {}
        
        # 历史数据缓存
        self.kline_cache: Dict[str, pd.DataFrame] = {}
        
        # 运行状态
        self.is_running = False
        
    async def initialize(self):
        """初始化交易所连接"""
        try:
            # 初始化CCXT交易所对象
            self.exchange = ccxt.okx({
                'sandbox': False,  # 设置为True使用测试环境
                'timeout': settings.ccxt_timeout,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',  # 现货交易
                }
            })
            
            # 测试连接
            await self.exchange.load_markets()
            logger.info("OKX交易所连接成功")
            
            return True
            
        except Exception as e:
            logger.error(f"OKX交易所连接失败: {str(e)}")
            raise
    
    def register_kline_callback(self, callback: Callable[[KlineData], None]):
        """注册K线数据回调"""
        self.kline_callbacks.append(callback)
    
    def register_tick_callback(self, callback: Callable[[TickData], None]):
        """注册tick数据回调"""
        self.tick_callbacks.append(callback)
    
    async def get_historical_klines(
        self, 
        symbol: str, 
        timeframe: str = "1m", 
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[KlineData]:
        """获取历史K线数据"""
        try:
            if not self.exchange:
                await self.initialize()
            
            # 转换时间戳
            since_timestamp = None
            if since:
                since_timestamp = int(since.timestamp() * 1000)
            
            # 获取K线数据
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol, 
                timeframe, 
                since=since_timestamp, 
                limit=limit
            )
            
            klines = []
            for candle in ohlcv:
                timestamp, open_price, high, low, close, volume = candle
                
                kline = KlineData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(timestamp / 1000),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume
                )
                klines.append(kline)
            
            # 缓存数据
            cache_key = f"{symbol}_{timeframe}"
            df = pd.DataFrame([k.to_dict() for k in klines])
            self.kline_cache[cache_key] = df
            
            logger.info(f"获取{symbol} {timeframe} K线数据成功: {len(klines)}条")
            return klines
            
        except Exception as e:
            logger.error(f"获取历史K线失败: {str(e)}")
            raise
    
    async def get_current_ticker(self, symbol: str) -> TickData:
        """获取当前ticker数据"""
        try:
            if not self.exchange:
                await self.initialize()
            
            ticker = await self.exchange.fetch_ticker(symbol)
            
            tick_data = TickData(
                symbol=symbol,
                timestamp=datetime.now(),
                bid=ticker.get('bid', 0),
                ask=ticker.get('ask', 0),
                price=ticker.get('last', 0),
                volume=ticker.get('baseVolume', 0)
            )
            
            return tick_data
            
        except Exception as e:
            logger.error(f"获取ticker数据失败: {str(e)}")
            raise
    
    async def start_websocket_stream(self, symbols: List[str], data_types: List[DataType]):
        """启动WebSocket数据流"""
        try:
            self.is_running = True
            
            # 为每种数据类型创建订阅
            for data_type in data_types:
                if data_type == DataType.KLINE:
                    await self._subscribe_klines(symbols)
                elif data_type == DataType.TICK:
                    await self._subscribe_tickers(symbols)
            
            logger.info(f"WebSocket数据流启动成功: {symbols}")
            
        except Exception as e:
            logger.error(f"WebSocket数据流启动失败: {str(e)}")
            self.is_running = False
            raise
    
    async def stop_websocket_stream(self):
        """停止WebSocket数据流"""
        self.is_running = False
        
        # 关闭所有WebSocket连接
        for ws_id, ws in self.ws_connections.items():
            try:
                await ws.close()
                logger.info(f"WebSocket连接已关闭: {ws_id}")
            except Exception as e:
                logger.error(f"关闭WebSocket连接失败: {str(e)}")
        
        self.ws_connections.clear()
        self.subscribed_symbols.clear()
    
    async def _subscribe_klines(self, symbols: List[str], timeframes: List[str] = ["1m"]):
        """订阅K线数据"""
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    # 使用CCXT Pro的WebSocket功能
                    if not self.exchange:
                        await self.initialize()
                    
                    # 创建订阅任务
                    asyncio.create_task(self._kline_subscription_loop(symbol, timeframe))
                    
                    logger.info(f"订阅K线数据: {symbol} {timeframe}")
                    
                except Exception as e:
                    logger.error(f"订阅K线失败 {symbol} {timeframe}: {str(e)}")
    
    async def _subscribe_tickers(self, symbols: List[str]):
        """订阅ticker数据"""
        for symbol in symbols:
            try:
                # 创建ticker订阅任务
                asyncio.create_task(self._ticker_subscription_loop(symbol))
                
                logger.info(f"订阅ticker数据: {symbol}")
                
            except Exception as e:
                logger.error(f"订阅ticker失败 {symbol}: {str(e)}")
    
    async def _kline_subscription_loop(self, symbol: str, timeframe: str):
        """K线数据订阅循环"""
        while self.is_running:
            try:
                # 使用CCXT Pro监听K线数据
                kline = await self.exchange.watch_ohlcv(symbol, timeframe)
                
                if kline and len(kline) > 0:
                    # 获取最新K线
                    latest_kline = kline[-1]
                    timestamp, open_price, high, low, close, volume = latest_kline
                    
                    kline_data = KlineData(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=datetime.fromtimestamp(timestamp / 1000),
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume
                    )
                    
                    # 触发回调
                    for callback in self.kline_callbacks:
                        try:
                            await callback(kline_data)
                        except Exception as e:
                            logger.error(f"K线回调失败: {str(e)}")
                
                await asyncio.sleep(1)  # 避免过于频繁的请求
                
            except Exception as e:
                logger.error(f"K线订阅循环错误 {symbol} {timeframe}: {str(e)}")
                await asyncio.sleep(5)  # 错误后等待5秒重试
    
    async def _ticker_subscription_loop(self, symbol: str):
        """Ticker数据订阅循环"""
        while self.is_running:
            try:
                # 使用CCXT Pro监听ticker数据
                ticker = await self.exchange.watch_ticker(symbol)
                
                if ticker:
                    tick_data = TickData(
                        symbol=symbol,
                        timestamp=datetime.now(),
                        bid=ticker.get('bid', 0),
                        ask=ticker.get('ask', 0),
                        price=ticker.get('last', 0),
                        volume=ticker.get('baseVolume', 0)
                    )
                    
                    # 触发回调
                    for callback in self.tick_callbacks:
                        try:
                            await callback(tick_data)
                        except Exception as e:
                            logger.error(f"Tick回调失败: {str(e)}")
                
                await asyncio.sleep(0.1)  # Tick数据更新更频繁
                
            except Exception as e:
                logger.error(f"Ticker订阅循环错误 {symbol}: {str(e)}")
                await asyncio.sleep(2)  # 错误后等待2秒重试
    
    async def get_supported_symbols(self) -> List[str]:
        """获取支持的交易对列表"""
        try:
            if not self.exchange:
                await self.initialize()
            
            markets = self.exchange.markets
            symbols = list(markets.keys())
            
            # 过滤出现货交易对
            spot_symbols = [
                symbol for symbol in symbols 
                if markets[symbol]['type'] == 'spot' and markets[symbol]['active']
            ]
            
            logger.info(f"获取到{len(spot_symbols)}个支持的交易对")
            return spot_symbols
            
        except Exception as e:
            logger.error(f"获取交易对失败: {str(e)}")
            return []
    
    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取交易对信息"""
        try:
            if not self.exchange:
                await self.initialize()
            
            if symbol in self.exchange.markets:
                market = self.exchange.markets[symbol]
                return {
                    "symbol": symbol,
                    "base": market['base'],
                    "quote": market['quote'],
                    "active": market['active'],
                    "type": market['type'],
                    "precision": market['precision'],
                    "limits": market['limits'],
                    "fees": market.get('fees', {}),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"获取交易对信息失败: {str(e)}")
            return None
    
    async def cleanup(self):
        """清理资源"""
        await self.stop_websocket_stream()
        
        if self.exchange:
            try:
                await self.exchange.close()
                logger.info("CCXT交易所连接已关闭")
            except Exception as e:
                logger.error(f"关闭CCXT连接失败: {str(e)}")


class MarketDataManager:
    """市场数据管理器"""
    
    def __init__(self):
        self.collectors: Dict[str, OKXDataCollector] = {}
        self.data_storage_callbacks: List[Callable] = []
        
    def get_collector(self, exchange: str = "okx") -> OKXDataCollector:
        """获取数据采集器"""
        if exchange not in self.collectors:
            if exchange.lower() == "okx":
                self.collectors[exchange] = OKXDataCollector()
            else:
                raise ValueError(f"不支持的交易所: {exchange}")
        
        return self.collectors[exchange]
    
    def register_storage_callback(self, callback: Callable):
        """注册数据存储回调"""
        self.data_storage_callbacks.append(callback)
    
    async def start_data_collection(
        self, 
        symbols: List[str], 
        data_types: List[DataType],
        exchange: str = "okx"
    ):
        """开始数据采集"""
        try:
            collector = self.get_collector(exchange)
            
            # 注册数据存储回调
            collector.register_kline_callback(self._on_kline_data)
            collector.register_tick_callback(self._on_tick_data)
            
            # 初始化并启动采集
            await collector.initialize()
            await collector.start_websocket_stream(symbols, data_types)
            
            logger.info(f"开始数据采集: {exchange} {symbols}")
            
        except Exception as e:
            logger.error(f"启动数据采集失败: {str(e)}")
            raise
    
    async def _on_kline_data(self, kline_data: KlineData):
        """K线数据处理"""
        try:
            # 存储到数据库
            await self._store_kline_data(kline_data)
            
            # 触发其他回调
            for callback in self.data_storage_callbacks:
                try:
                    await callback(kline_data)
                except Exception as e:
                    logger.error(f"数据存储回调失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"K线数据处理失败: {str(e)}")
    
    async def _on_tick_data(self, tick_data: TickData):
        """Tick数据处理"""
        try:
            # Tick数据一般不持久化存储，只触发回调
            for callback in self.data_storage_callbacks:
                try:
                    await callback(tick_data)
                except Exception as e:
                    logger.error(f"Tick数据回调失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Tick数据处理失败: {str(e)}")
    
    async def _store_kline_data(self, kline_data: KlineData):
        """存储K线数据到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                # 检查是否已存在
                existing = await db.execute(
                    "SELECT id FROM market_data WHERE exchange = ? AND symbol = ? AND timeframe = ? AND timestamp = ?",
                    (kline_data.exchange, kline_data.symbol, kline_data.timeframe, kline_data.timestamp)
                )
                
                if existing.fetchone():
                    return  # 数据已存在，跳过
                
                # 插入新数据
                market_data = MarketData(
                    exchange=kline_data.exchange,
                    symbol=kline_data.symbol,
                    timeframe=kline_data.timeframe,
                    open_price=kline_data.open,
                    high_price=kline_data.high,
                    low_price=kline_data.low,
                    close_price=kline_data.close,
                    volume=kline_data.volume,
                    timestamp=kline_data.timestamp
                )
                
                db.add(market_data)
                await db.commit()
                
        except Exception as e:
            logger.error(f"存储K线数据失败: {str(e)}")


# 全局市场数据管理器实例
market_data_manager = MarketDataManager()