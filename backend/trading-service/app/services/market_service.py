"""
市场数据服务 - 市场数据管理业务逻辑
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func, desc, asc
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

from app.models.market_data import MarketData
from app.core.market_data_collector import (
    MarketDataManager, KlineData, TickData, DataType, 
    market_data_manager
)
from app.core.websocket_manager import (
    OKXWebSocketManager, Subscription, ChannelType,
    websocket_manager
)
from app.core.strategy_engine import strategy_engine


class MarketService:
    """市场数据服务类"""
    
    def __init__(self):
        self.data_manager = market_data_manager
        self.ws_manager = websocket_manager
        self.active_subscriptions: Dict[str, bool] = {}
        
        # 注册数据处理回调
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """设置数据处理回调"""
        # 注册市场数据回调
        self.data_manager.register_storage_callback(self._on_market_data)
        
        # 注册WebSocket回调
        self.ws_manager.register_callback(ChannelType.KLINE, self._on_kline_data)
        self.ws_manager.register_callback(ChannelType.TICKER, self._on_tick_data)
        self.ws_manager.register_error_callback(self._on_websocket_error)
    
    async def _on_market_data(self, data):
        """市场数据回调处理"""
        try:
            if isinstance(data, KlineData):
                # 将K线数据发送给策略引擎
                bar_data = data.to_dict()
                await strategy_engine.process_bar_data(bar_data)
            elif isinstance(data, TickData):
                # 将tick数据发送给策略引擎
                tick_data = data.to_dict()
                await strategy_engine.process_tick_data(tick_data)
        except Exception as e:
            logger.error(f"市场数据回调处理失败: {str(e)}")
    
    async def _on_kline_data(self, kline_data: KlineData):
        """K线数据回调"""
        try:
            # 发送给策略引擎
            bar_data = kline_data.to_dict()
            await strategy_engine.process_bar_data(bar_data)
        except Exception as e:
            logger.error(f"K线数据处理失败: {str(e)}")
    
    async def _on_tick_data(self, tick_data: TickData):
        """Tick数据回调"""
        try:
            # 发送给策略引擎
            tick_data_dict = tick_data.to_dict()
            await strategy_engine.process_tick_data(tick_data_dict)
        except Exception as e:
            logger.error(f"Tick数据处理失败: {str(e)}")
    
    async def _on_websocket_error(self, error_message: str):
        """WebSocket错误回调"""
        logger.error(f"WebSocket错误: {error_message}")
    
    async def start_real_time_data(
        self, 
        symbols: List[str], 
        data_types: List[str] = ["kline", "tick"],
        timeframes: List[str] = ["1m"]
    ) -> bool:
        """启动实时数据采集"""
        try:
            # 转换数据类型
            converted_types = []
            for dt in data_types:
                if dt.lower() == "kline":
                    converted_types.append(DataType.KLINE)
                elif dt.lower() == "tick":
                    converted_types.append(DataType.TICK)
            
            # 启动数据采集
            await self.data_manager.start_data_collection(
                symbols=symbols,
                data_types=converted_types,
                exchange="okx"
            )
            
            # 启动WebSocket连接
            if not self.ws_manager.is_connected:
                await self.ws_manager.connect()
            
            # 订阅数据
            for symbol in symbols:
                # 订阅ticker数据
                if DataType.TICK in converted_types:
                    ticker_sub = Subscription(
                        channel=ChannelType.TICKER,
                        symbol=symbol
                    )
                    await self.ws_manager.subscribe(ticker_sub)
                
                # 订阅K线数据
                if DataType.KLINE in converted_types:
                    for timeframe in timeframes:
                        kline_sub = Subscription(
                            channel=ChannelType.KLINE,
                            symbol=symbol,
                            timeframe=timeframe
                        )
                        await self.ws_manager.subscribe(kline_sub)
            
            # 记录活跃订阅
            for symbol in symbols:
                self.active_subscriptions[symbol] = True
            
            logger.info(f"实时数据采集启动成功: {symbols}")
            return True
            
        except Exception as e:
            logger.error(f"启动实时数据采集失败: {str(e)}")
            return False
    
    async def stop_real_time_data(self, symbols: Optional[List[str]] = None) -> bool:
        """停止实时数据采集"""
        try:
            if symbols is None:
                # 停止所有订阅
                await self.ws_manager.disconnect()
                self.active_subscriptions.clear()
            else:
                # 停止指定交易对的订阅
                for symbol in symbols:
                    # 取消ticker订阅
                    ticker_sub = Subscription(
                        channel=ChannelType.TICKER,
                        symbol=symbol
                    )
                    await self.ws_manager.unsubscribe(ticker_sub)
                    
                    # 取消K线订阅
                    kline_sub = Subscription(
                        channel=ChannelType.KLINE,
                        symbol=symbol,
                        timeframe="1m"  # 这里应该记录实际的timeframe
                    )
                    await self.ws_manager.unsubscribe(kline_sub)
                    
                    if symbol in self.active_subscriptions:
                        del self.active_subscriptions[symbol]
            
            logger.info("实时数据采集已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止实时数据采集失败: {str(e)}")
            return False
    
    @staticmethod
    async def get_historical_klines(
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[KlineData]:
        """获取历史K线数据"""
        try:
            collector = market_data_manager.get_collector(exchange)
            await collector.initialize()
            
            since = start_time
            if not since and end_time:
                since = end_time - timedelta(days=limit // 1440)  # 估算开始时间
            
            klines = await collector.get_historical_klines(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                since=since
            )
            
            # 如果指定了结束时间，过滤数据
            if end_time:
                klines = [k for k in klines if k.timestamp <= end_time]
            
            return klines
            
        except Exception as e:
            logger.error(f"获取历史K线失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_market_data(
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[MarketData]:
        """从数据库获取市场数据"""
        query = select(MarketData).where(
            and_(
                MarketData.exchange == exchange,
                MarketData.symbol == symbol,
                MarketData.timeframe == timeframe
            )
        )
        
        if start_time:
            query = query.where(MarketData.timestamp >= start_time)
        
        if end_time:
            query = query.where(MarketData.timestamp <= end_time)
        
        query = query.order_by(MarketData.timestamp.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_latest_price(
        db: AsyncSession,
        exchange: str,
        symbol: str
    ) -> Optional[float]:
        """获取最新价格"""
        query = select(MarketData.close_price).where(
            and_(
                MarketData.exchange == exchange,
                MarketData.symbol == symbol
            )
        ).order_by(MarketData.timestamp.desc()).limit(1)
        
        result = await db.execute(query)
        latest_price = result.scalar()
        return latest_price
    
    @staticmethod
    async def get_supported_symbols(exchange: str = "okx") -> List[str]:
        """获取支持的交易对"""
        try:
            collector = market_data_manager.get_collector(exchange)
            await collector.initialize()
            
            symbols = await collector.get_supported_symbols()
            
            # 过滤出主要交易对
            major_symbols = [
                s for s in symbols 
                if any(quote in s for quote in ['/USDT', '/BTC', '/ETH', '/USD'])
            ]
            
            return major_symbols[:100]  # 返回前100个主要交易对
            
        except Exception as e:
            logger.error(f"获取支持的交易对失败: {str(e)}")
            return []
    
    @staticmethod
    async def get_supported_exchanges() -> List[Dict[str, Any]]:
        """获取支持的交易所"""
        return [
            {
                "id": "okx",
                "name": "OKX",
                "type": "spot",
                "status": "active",
                "features": ["spot", "websocket", "klines", "tickers"]
            }
        ]
    
    @staticmethod
    async def get_ticker(exchange: str, symbol: str) -> Dict[str, Any]:
        """获取ticker数据"""
        try:
            collector = market_data_manager.get_collector(exchange)
            await collector.initialize()
            
            tick_data = await collector.get_current_ticker(symbol)
            
            return {
                "symbol": symbol,
                "price": tick_data.price,
                "bid": tick_data.bid,
                "ask": tick_data.ask,
                "volume": tick_data.volume,
                "timestamp": tick_data.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取ticker数据失败: {str(e)}")
            return {"symbol": symbol, "price": 0.0, "error": str(e)}
    
    @staticmethod
    async def get_klines(
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[int] = None
    ) -> List[List]:
        """获取K线数据"""
        try:
            start_time = None
            if since:
                start_time = datetime.fromtimestamp(since / 1000)
            
            # 直接获取真实数据
            klines = await MarketService.get_historical_klines(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                start_time=start_time
            )
            
            if klines:
                # 转换为标准格式 [timestamp, open, high, low, close, volume]
                result = []
                for kline in klines:
                    result.append([
                        int(kline.timestamp.timestamp() * 1000),
                        kline.open,
                        kline.high,
                        kline.low,
                        kline.close,
                        kline.volume
                    ])
                logger.info(f"成功获取{symbol}真实K线数据: {len(result)}条")
                return result
            else:
                logger.warning(f"未获取到K线数据: {symbol}")
                return []
            
        except Exception as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            raise
    
    @staticmethod
    def _generate_mock_klines(symbol: str, timeframe: str, limit: int) -> List[List]:
        """生成模拟K线数据"""
        import random
        import math
        
        # 基础价格根据交易对确定
        base_prices = {
            'BTCUSDT': 43250.0,
            'ETHUSDT': 2650.0,
            'BNBUSDT': 315.0,
            'SOLUSDT': 98.0,
            'ADAUSDT': 0.52,
            'BTC/USDT': 43250.0,
            'ETH/USDT': 2650.0,
            'BNB/USDT': 315.0,
            'SOL/USDT': 98.0,
            'ADA/USDT': 0.52,
        }
        
        base_price = base_prices.get(symbol.upper().replace('/', ''), 100.0)
        
        # 时间间隔映射
        timeframe_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '4h': 240, '1d': 1440
        }
        
        interval = timeframe_minutes.get(timeframe, 15)
        
        result = []
        current_time = datetime.now()
        current_price = base_price
        
        for i in range(limit):
            # 计算时间戳（倒序，最新的在后面）
            timestamp = current_time - timedelta(minutes=(limit - 1 - i) * interval)
            timestamp_ms = int(timestamp.timestamp() * 1000)
            
            # 生成价格波动
            volatility = 0.02  # 2%波动率
            price_change = (random.random() - 0.5) * 2 * volatility
            new_price = current_price * (1 + price_change)
            
            # 生成OHLCV数据
            open_price = current_price
            close_price = new_price
            high_price = max(open_price, close_price) * (1 + random.random() * 0.01)
            low_price = min(open_price, close_price) * (1 - random.random() * 0.01)
            volume = random.uniform(50, 200)
            
            # 添加一些趋势性
            if i > 20:
                trend = math.sin(i / 20) * 0.001
                close_price *= (1 + trend)
                high_price *= (1 + trend)
                low_price *= (1 + trend)
            
            result.append([
                timestamp_ms,
                round(open_price, 2),
                round(high_price, 2),
                round(low_price, 2),
                round(close_price, 2),
                round(volume, 2)
            ])
            
            current_price = close_price
        
        logger.info(f"生成了 {len(result)} 条模拟K线数据 for {symbol}")
        return result
    
    @staticmethod
    async def get_order_book(exchange: str, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """获取订单簿"""
        # TODO: 实现订单簿获取
        return {
            "symbol": symbol,
            "bids": [],
            "asks": [],
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    async def calculate_indicators(
        exchange: str,
        symbol: str,
        timeframe: str,
        indicators: List[str],
        limit: int = 100
    ) -> Dict[str, Any]:
        """计算技术指标"""
        try:
            # 获取K线数据
            klines = await MarketService.get_historical_klines(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            if not klines:
                return {}
            
            # 转换为DataFrame
            data = []
            for kline in klines:
                data.append({
                    'timestamp': kline.timestamp,
                    'open': kline.open,
                    'high': kline.high,
                    'low': kline.low,
                    'close': kline.close,
                    'volume': kline.volume
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            
            result = {}
            
            # 计算指标
            for indicator in indicators:
                if indicator.lower() == 'sma':
                    result['sma_20'] = df['close'].rolling(window=20).mean().tolist()
                elif indicator.lower() == 'ema':
                    result['ema_20'] = df['close'].ewm(span=20).mean().tolist()
                elif indicator.lower() == 'rsi':
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    result['rsi'] = (100 - (100 / (1 + rs))).tolist()
                elif indicator.lower() == 'macd':
                    ema_12 = df['close'].ewm(span=12).mean()
                    ema_26 = df['close'].ewm(span=26).mean()
                    macd = ema_12 - ema_26
                    signal = macd.ewm(span=9).mean()
                    result['macd'] = macd.tolist()
                    result['macd_signal'] = signal.tolist()
                    result['macd_histogram'] = (macd - signal).tolist()
            
            return result
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {str(e)}")
            return {}
    
    async def subscribe_realtime_data(
        self,
        exchange: str,
        symbol: str,
        data_types: List[str] = ["ticker"]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """订阅实时数据"""
        try:
            # 启动实时数据采集
            await self.start_real_time_data(
                symbols=[symbol],
                data_types=data_types
            )
            
            # 创建数据队列
            data_queue = asyncio.Queue()
            
            # 注册回调来接收数据
            async def data_callback(data):
                await data_queue.put(data)
            
            if "ticker" in data_types:
                self.ws_manager.register_callback(ChannelType.TICKER, data_callback)
            if "kline" in data_types:
                self.ws_manager.register_callback(ChannelType.KLINE, data_callback)
            
            # 生成数据流
            while True:
                try:
                    data = await asyncio.wait_for(data_queue.get(), timeout=30)
                    
                    if isinstance(data, TickData):
                        yield {
                            "type": "ticker",
                            "symbol": data.symbol,
                            "price": data.price,
                            "bid": data.bid,
                            "ask": data.ask,
                            "volume": data.volume,
                            "timestamp": data.timestamp.isoformat()
                        }
                    elif isinstance(data, KlineData):
                        yield {
                            "type": "kline",
                            "symbol": data.symbol,
                            "timeframe": data.timeframe,
                            "open": data.open,
                            "high": data.high,
                            "low": data.low,
                            "close": data.close,
                            "volume": data.volume,
                            "timestamp": data.timestamp.isoformat()
                        }
                        
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield {"type": "heartbeat", "timestamp": datetime.now().isoformat()}
                    
        except Exception as e:
            logger.error(f"实时数据订阅失败: {str(e)}")
            yield {"type": "error", "message": str(e)}
    
    @staticmethod
    async def get_market_summary(
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str = "1d"
    ) -> Dict[str, Any]:
        """获取市场摘要"""
        # 获取最近的数据用于计算统计信息
        query = select(MarketData).where(
            and_(
                MarketData.exchange == exchange,
                MarketData.symbol == symbol,
                MarketData.timeframe == timeframe
            )
        ).order_by(MarketData.timestamp.desc()).limit(30)
        
        result = await db.execute(query)
        data = result.scalars().all()
        
        if not data:
            return {}
        
        # 计算统计信息
        latest = data[0]
        prices = [item.close_price for item in data]
        volumes = [item.volume for item in data]
        
        return {
            "symbol": symbol,
            "exchange": exchange,
            "latest_price": latest.close_price,
            "timestamp": latest.timestamp,
            "change_24h": (prices[0] - prices[-1]) / prices[-1] * 100 if len(prices) > 1 else 0,
            "volume_24h": sum(volumes[:24]) if len(volumes) >= 24 else sum(volumes),
            "high_24h": max(item.high_price for item in data[:24]) if len(data) >= 24 else max(item.high_price for item in data),
            "low_24h": min(item.low_price for item in data[:24]) if len(data) >= 24 else min(item.low_price for item in data),
        }
    
    @staticmethod
    async def get_market_stats(exchange: str, symbol: str, period: int = 24) -> Dict[str, Any]:
        """获取市场统计"""
        try:
            # 获取真实的24小时数据
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=period)
            
            klines = await MarketService.get_historical_klines(
                exchange=exchange,
                symbol=symbol,
                timeframe="1h",
                limit=period,
                start_time=start_time,
                end_time=end_time
            )
            
            if klines:
                prices = [k.close for k in klines]
                volumes = [k.volume for k in klines]
                highs = [k.high for k in klines]
                lows = [k.low for k in klines]
                
                # 计算成交额
                volume_usd = sum(volumes) * (prices[-1] if prices else 0)
                volume_usd_str = f"{volume_usd / 1000000:.1f}M" if volume_usd > 1000000 else f"{volume_usd / 1000:.1f}K"
                
                result = {
                    "symbol": symbol,
                    "exchange": exchange,
                    "period_hours": period,
                    "current_price": prices[-1] if prices else 0,
                    "price_change": prices[-1] - prices[0] if len(prices) > 1 else 0,
                    "price_change_percent": ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) > 1 and prices[0] > 0 else 0,
                    "high_24h": max(highs) if highs else 0,
                    "low_24h": min(lows) if lows else 0,
                    "volume_24h": sum(volumes) if volumes else 0,
                    "volume_usd_24h": volume_usd_str,
                    "average_price": sum(prices) / len(prices) if prices else 0,
                    "timestamp": datetime.now().isoformat()
                }
                logger.info(f"成功获取{symbol}真实市场统计数据")
                return result
            else:
                logger.warning(f"未获取到市场统计数据: {symbol}")
                return {"error": "No market data available"}
            
        except Exception as e:
            logger.error(f"获取市场统计失败: {str(e)}")
            raise
    
    @staticmethod
    def _generate_mock_stats(symbol: str) -> Dict[str, Any]:
        """生成模拟市场统计数据"""
        import random
        
        # 基础价格根据交易对确定
        base_prices = {
            'BTCUSDT': 43250.0,
            'ETHUSDT': 2650.0,
            'BNBUSDT': 315.0,
            'SOLUSDT': 98.0,
            'ADAUSDT': 0.52,
            'BTC/USDT': 43250.0,
            'ETH/USDT': 2650.0,
            'BNB/USDT': 315.0,
            'SOL/USDT': 98.0,
            'ADA/USDT': 0.52,
        }
        
        base_price = base_prices.get(symbol.upper().replace('/', ''), 100.0)
        
        # 生成24小时统计数据
        current_price = base_price * (1 + (random.random() - 0.5) * 0.05)  # ±5%
        high_24h = current_price * (1 + random.random() * 0.03)  # 最高价
        low_24h = current_price * (1 - random.random() * 0.03)  # 最低价
        volume_24h = random.uniform(1000, 5000)  # 24h成交量
        
        # 格式化24小时成交额
        volume_usd = volume_24h * current_price
        if volume_usd > 1000000:
            volume_usd_str = f"{volume_usd / 1000000:.1f}M"
        else:
            volume_usd_str = f"{volume_usd / 1000:.1f}K"
        
        return {
            "symbol": symbol,
            "exchange": "okx",
            "period_hours": 24,
            "current_price": round(current_price, 2),
            "high_24h": round(high_24h, 2),
            "low_24h": round(low_24h, 2),
            "volume_24h": round(volume_24h, 2),
            "volume_usd_24h": volume_usd_str,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    async def get_symbol_info(symbol: str, exchange: str = "okx") -> Optional[Dict[str, Any]]:
        """获取交易对信息"""
        try:
            collector = market_data_manager.get_collector(exchange)
            await collector.initialize()
            
            return await collector.get_symbol_info(symbol)
            
        except Exception as e:
            logger.error(f"获取交易对信息失败: {str(e)}")
            return None
    
    @staticmethod
    async def add_to_watchlist(
        db: AsyncSession,
        user_id: int,
        symbols: List[str]
    ) -> Dict[str, Any]:
        """添加到自选"""
        # TODO: 实现自选列表功能，需要创建watchlist表
        return {"added": len(symbols), "message": "自选功能开发中"}
    
    @staticmethod
    async def get_user_watchlist(db: AsyncSession, user_id: int) -> List[str]:
        """获取用户自选"""
        # TODO: 实现自选列表查询
        return []
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "websocket": self.ws_manager.get_stats(),
            "active_subscriptions": list(self.active_subscriptions.keys()),
            "subscription_count": len(self.active_subscriptions)
        }
    
    @staticmethod
    async def cleanup_old_data(
        db: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """清理旧数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # 删除旧数据
            delete_query = delete(MarketData).where(
                MarketData.timestamp < cutoff_date
            )
            
            result = await db.execute(delete_query)
            await db.commit()
            
            deleted_count = result.rowcount
            logger.info(f"清理了{deleted_count}条旧的市场数据")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理旧数据失败: {str(e)}")
            return 0


# 全局市场服务实例
market_service = MarketService()