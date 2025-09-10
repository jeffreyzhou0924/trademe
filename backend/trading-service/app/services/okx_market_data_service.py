"""
OKX市场数据服务
集成真实K线数据，替代前端Mock数据
基于现有okx_rest_kline.py服务优化
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import aiohttp
import requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.database import AsyncSessionLocal
from app.models.market_data import MarketData
from app.models.api_key import ApiKey
from app.utils.data_validation import DataValidator
from app.services.okx_auth_service import get_okx_auth_service

# 配置日志
logger = logging.getLogger(__name__)


class OKXMarketDataService:
    """OKX市场数据服务"""
    
    def __init__(self):
        # OKX REST API配置
        self.rest_url = "https://www.okx.com/api/v5"
        
        # 数据缓存
        self.kline_cache = {}
        self.ticker_cache = {}
        self.cache_ttl = 30  # 缓存30秒
        
        # 🆕 分页标记，用于历史数据获取
        self._pagination_marker = {}
        
        # OKX时间周期映射
        self.timeframe_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "2h": "2H", "4h": "4H", 
            "1d": "1D", "1w": "1W"
        }
        
        # 支持的交易对 - 包括现货和合约
        self.supported_symbols = [
            # 现货交易对
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT",
            "DOT/USDT", "LINK/USDT", "MATIC/USDT", "AVAX/USDT",
            # 合约交易对  
            "BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "ADA-USDT-SWAP",
            "DOT-USDT-SWAP", "LINK-USDT-SWAP", "MATIC-USDT-SWAP", "AVAX-USDT-SWAP"
        ]
        
        logger.info("🚀 OKX市场数据服务初始化完成")
    
    async def get_klines(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 100,
        start_time: int = None,
        end_time: int = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """获取K线数据 - 主要接口"""
        try:
            # 参数验证
            if symbol not in self.supported_symbols:
                error_msg = f"不支持的交易对: {symbol}，支持的交易对: {list(self.supported_symbols)}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            # 检查缓存
            if use_cache:
                cached_data = await self._get_cached_klines(symbol, timeframe, limit)
                if cached_data:
                    logger.debug(f"📊 使用缓存K线数据: {symbol} {timeframe}")
                    return cached_data
            
            # 获取真实数据
            real_data = await self._fetch_okx_klines(symbol, timeframe, limit, start_time, end_time)
            
            if real_data["klines"]:
                # 缓存数据
                await self._cache_klines(symbol, timeframe, limit, real_data)
                
                # 保存到数据库
                await self._save_to_database(real_data)
                
                return real_data
            else:
                # 🚨 不再使用备用数据，直接报错
                error_msg = f"OKX API调用成功但返回空数据: {symbol} {timeframe}"
                if start_time and end_time:
                    start_dt = datetime.fromtimestamp(start_time / 1000)
                    end_dt = datetime.fromtimestamp(end_time / 1000)
                    error_msg += f" (时间范围: {start_dt} - {end_dt})"
                
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"❌ 获取K线数据失败: {symbol} {timeframe} - {e}")
            # 🚨 不再使用备用数据，直接抛出异常
            raise e
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取实时价格数据"""
        try:
            # 检查缓存
            cached_ticker = await self._get_cached_ticker(symbol)
            if cached_ticker:
                logger.debug(f"💰 使用缓存价格数据: {symbol}")
                return cached_ticker
            
            # 获取真实数据
            real_ticker = await self._fetch_okx_ticker(symbol)
            
            if real_ticker:
                # 缓存数据
                await self._cache_ticker(symbol, real_ticker)
                return real_ticker
            else:
                error_msg = f"OKX API调用成功但返回空价格数据: {symbol}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"❌ 获取价格数据失败: {symbol} - {e}")
            raise e
    
    async def get_multiple_tickers(self, symbols: List[str]) -> Dict[str, Dict]:
        """批量获取多个交易对的价格数据"""
        results = {}
        tasks = []
        
        # 创建并发任务
        for symbol in symbols:
            if symbol in self.supported_symbols:
                task = asyncio.create_task(
                    self.get_ticker(symbol),
                    name=f"ticker_{symbol}"
                )
                tasks.append((symbol, task))
        
        # 并发执行
        for symbol, task in tasks:
            try:
                results[symbol] = await task
            except Exception as e:
                logger.error(f"❌ 批量获取 {symbol} 价格失败: {e}")
                results[symbol] = {"error": str(e)}
        
        return results
    
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """获取交易对信息"""
        try:
            okx_symbol = symbol.replace("/", "-")
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.rest_url}/public/instruments"
                params = {"instType": "SPOT", "instId": okx_symbol}
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data["code"] == "0" and data["data"]:
                            instrument = data["data"][0]
                            
                            return {
                                "symbol": symbol,
                                "base_asset": instrument["baseCcy"],
                                "quote_asset": instrument["quoteCcy"],
                                "min_qty": float(instrument["minSz"]),
                                "min_notional": float(instrument.get("minSz", "0")),
                                "tick_size": float(instrument["tickSz"]),
                                "lot_size": float(instrument["lotSz"]),
                                "status": instrument["state"],
                                "exchange": "okx"
                            }
            
            # 如果API调用失败，返回默认信息
            return self._get_default_symbol_info(symbol)
            
        except Exception as e:
            logger.error(f"❌ 获取交易对信息失败: {symbol} - {e}")
            return self._get_default_symbol_info(symbol)
    
    async def _fetch_okx_klines(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int,
        start_time: int = None,
        end_time: int = None
    ) -> Dict[str, Any]:
        """从OKX API获取K线数据 - 带认证支持的版本"""
        # 转换符号格式
        okx_symbol = symbol.replace("/", "-")
        okx_timeframe = self.timeframe_map.get(timeframe.lower(), timeframe)
        
        # 分页逻辑
        pagination_marker = None
        if hasattr(self, '_pagination_marker') and symbol in self._pagination_marker:
            pagination_marker = self._pagination_marker[symbol]
            logger.info(f"📅 使用分页标记: {pagination_marker} (继续获取历史数据)")
        else:
            logger.info(f"📅 获取最新数据 (首次请求)")
        
        # API调用结果
        data = None
        api_source = None
        
        try:
            # 🆕 优先使用认证的OKX API服务
            okx_service = get_okx_auth_service()
            
            if okx_service:
                logger.info(f"🔑 使用认证OKX API: {symbol} {timeframe}")
                api_source = "okx_auth_api"
                
                # 调用认证API
                data = await okx_service.get_market_data(
                    instrument_id=okx_symbol,
                    bar=okx_timeframe,
                    limit=min(limit, 300),
                    after=str(pagination_marker) if pagination_marker else None
                )
                
            else:
                # 回退到公开API
                logger.warning(f"⚠️ OKX认证服务未可用，使用公开API: {symbol}")
                api_source = "okx_public_api"
                
                async with aiohttp.ClientSession() as session:
                    # 🆕 对于历史数据，使用history-candles端点
                    if start_time or pagination_marker:
                        url = f"{self.rest_url}/market/history-candles"
                        logger.info(f"📈 使用历史数据端点: {symbol}")
                    else:
                        url = f"{self.rest_url}/market/candles"
                        
                    params = {
                        "instId": okx_symbol,
                        "bar": okx_timeframe,
                        "limit": min(limit, 300)
                    }
                    
                    # 🆕 添加时间范围参数
                    if start_time:
                        params["after"] = str(start_time)
                    elif pagination_marker:
                        params["after"] = str(pagination_marker)
                        
                    if end_time:
                        params["before"] = str(end_time)
                    
                    logger.info(f"📊 OKX公开API请求: {symbol} {timeframe}")
                    logger.debug(f"🔧 请求参数: {params}")
                    
                    async with session.get(url, params=params, timeout=15) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}")
                        
                        data = await response.json()
            
            # 检查API响应
            if data["code"] != "0":
                raise Exception(f"OKX API错误: {data.get('msg', 'Unknown error')}")
            
            if not data["data"]:
                logger.warning(f"⚠️ OKX API返回空数据 - 可能时间范围内无数据")
                return {
                    "klines": [],
                    "symbol": symbol,
                    "exchange": "okx", 
                    "timeframe": timeframe,
                    "count": 0,
                    "timestamp": int(time.time() * 1000),
                    "source": f"{api_source}_empty"
                }
            
            # 转换数据格式
            klines = []
            for candle in data["data"]:
                # OKX返回格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                klines.append([
                    int(candle[0]),      # timestamp (毫秒)
                    float(candle[1]),    # open
                    float(candle[2]),    # high  
                    float(candle[3]),    # low
                    float(candle[4]),    # close
                    float(candle[5])     # volume
                ])
            
            # OKX返回数据是降序的，需要反转为升序
            klines.reverse()
            
            # 🆕 保存分页标记（最早的时间戳），用于下次请求
            if klines:
                earliest_timestamp = klines[0][0]  # 反转后第一个是最早的
                self._pagination_marker[symbol] = earliest_timestamp
                logger.debug(f"🔖 保存分页标记: {symbol} -> {earliest_timestamp}")
            
            # 🆕 过滤时间范围外的数据（如果指定了时间范围）
            if start_time or end_time:
                filtered_klines = []
                for kline in klines:
                    kline_time = kline[0]
                    # 检查是否在指定时间范围内
                    if start_time and kline_time < start_time:
                        continue  # 跳过早于开始时间的数据
                    if end_time and kline_time > end_time:
                        continue  # 跳过晚于结束时间的数据
                    filtered_klines.append(kline)
                
                klines = filtered_klines
                logger.debug(f"🔍 时间过滤: 原始 {len(data['data'])} 条 -> 过滤后 {len(klines)} 条")
            
            result = {
                "klines": klines,
                "symbol": symbol,
                "exchange": "okx",
                "timeframe": timeframe,
                "count": len(klines),
                "timestamp": int(time.time() * 1000),
                "source": api_source
            }
            
            # 记录数据信息
            if klines:
                earliest_time = datetime.fromtimestamp(klines[0][0] / 1000)
                latest_time = datetime.fromtimestamp(klines[-1][0] / 1000)
                latest_price = klines[-1][4]  # 最新收盘价
                safe_price = DataValidator.safe_format_price(latest_price)
                logger.info(f"✅ 获取 {len(klines)} 条K线数据: {earliest_time} 到 {latest_time}")
                logger.info(f"💰 {symbol} 最新价格: {safe_price}")
            else:
                logger.info(f"📊 时间范围内无K线数据")
            
            return result
                    
        except Exception as e:
            logger.error(f"❌ OKX API获取失败: {e}")
            raise
    
    async def _fetch_okx_ticker(self, symbol: str) -> Dict[str, Any]:
        """从OKX API获取实时价格"""
        okx_symbol = symbol.replace("/", "-")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.rest_url}/market/ticker"
                params = {"instId": okx_symbol}
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    data = await response.json()
                    
                    if data["code"] != "0" or not data["data"]:
                        raise Exception(f"OKX API错误: {data.get('msg', 'No data')}")
                    
                    ticker = data["data"][0]
                    
                    result = {
                        "symbol": symbol,
                        "price": float(ticker["last"]),
                        "change_24h": float(ticker.get("chg24h", "0")) * 100,  # 转换为百分比
                        "high_24h": float(ticker["high24h"]),
                        "low_24h": float(ticker["low24h"]),
                        "volume_24h": float(ticker.get("vol24h", "0")),
                        "timestamp": int(ticker["ts"]),
                        "exchange": "okx",
                        "source": "okx_rest_api"
                    }
                    
                    # 使用安全的价格格式化
                    safe_price = DataValidator.safe_format_price(result['price'])
                    safe_change = DataValidator.safe_format_percentage(result['change_24h'])
                    logger.info(f"💰 {symbol}: {safe_price} ({safe_change})")
                    
                    return result
                    
        except Exception as e:
            logger.error(f"❌ OKX Ticker API获取失败: {e}")
            raise
    
    async def _save_to_database(self, kline_data: Dict[str, Any]):
        """保存K线数据到数据库"""
        try:
            async with self._get_db_session() as db:
                saved_count = 0
                
                for kline in kline_data["klines"]:
                    timestamp, open_price, high, low, close, volume = kline
                    
                    # 检查是否已存在
                    existing = await db.execute(
                        select(MarketData).where(
                            and_(
                                MarketData.exchange == kline_data["exchange"],
                                MarketData.symbol == kline_data["symbol"],
                                MarketData.timeframe == kline_data["timeframe"],
                                MarketData.timestamp == datetime.fromtimestamp(timestamp / 1000)
                            )
                        )
                    )
                    
                    if existing.scalar_one_or_none():
                        continue
                    
                    # 创建新记录
                    market_data = MarketData(
                        exchange=kline_data["exchange"],
                        symbol=kline_data["symbol"],
                        timeframe=kline_data["timeframe"],
                        open_price=open_price,
                        high_price=high,
                        low_price=low,
                        close_price=close,
                        volume=volume,
                        timestamp=datetime.fromtimestamp(timestamp / 1000)
                    )
                    
                    db.add(market_data)
                    saved_count += 1
                
                if saved_count > 0:
                    await db.commit()
                    logger.info(f"💾 保存 {saved_count} 条K线数据到数据库")
                    
        except Exception as e:
            logger.error(f"❌ 保存K线数据到数据库失败: {e}")
    
    async def _get_cached_klines(self, symbol: str, timeframe: str, limit: int) -> Optional[Dict]:
        """获取缓存的K线数据"""
        cache_key = f"{symbol}_{timeframe}_{limit}"
        
        if cache_key in self.kline_cache:
            data, timestamp = self.kline_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return data
            else:
                # 缓存过期，删除
                del self.kline_cache[cache_key]
        
        return None
    
    async def _cache_klines(self, symbol: str, timeframe: str, limit: int, data: Dict):
        """缓存K线数据"""
        cache_key = f"{symbol}_{timeframe}_{limit}"
        self.kline_cache[cache_key] = (data, time.time())
        
        # 限制缓存大小，保留最新的50个
        if len(self.kline_cache) > 50:
            oldest_key = min(self.kline_cache.keys(), 
                           key=lambda k: self.kline_cache[k][1])
            del self.kline_cache[oldest_key]
    
    async def _get_cached_ticker(self, symbol: str) -> Optional[Dict]:
        """获取缓存的价格数据"""
        cache_key = f"ticker_{symbol}"
        
        if cache_key in self.ticker_cache:
            data, timestamp = self.ticker_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return data
            else:
                del self.ticker_cache[cache_key]
        
        return None
    
    async def _cache_ticker(self, symbol: str, data: Dict):
        """缓存价格数据"""
        cache_key = f"ticker_{symbol}"
        self.ticker_cache[cache_key] = (data, time.time())
        
        # 限制缓存大小
        if len(self.ticker_cache) > 20:
            oldest_key = min(self.ticker_cache.keys(), 
                           key=lambda k: self.ticker_cache[k][1])
            del self.ticker_cache[oldest_key]
    
    async def _get_fallback_klines(self, symbol: str, timeframe: str, limit: int) -> Dict:
        """获取备用K线数据"""
        logger.warning(f"⚠️ 使用备用K线数据: {symbol}")
        
        # 首先尝试从数据库获取历史数据
        try:
            async with self._get_db_session() as db:
                stmt = select(MarketData).where(
                    and_(
                        MarketData.symbol == symbol,
                        MarketData.timeframe == timeframe
                    )
                ).order_by(desc(MarketData.timestamp)).limit(limit)
                
                result = await db.execute(stmt)
                historical_data = result.scalars().all()
                
                if historical_data:
                    klines = []
                    for data in reversed(historical_data):  # 转换为升序
                        klines.append([
                            int(data.timestamp.timestamp() * 1000),
                            data.open_price,
                            data.high_price,
                            data.low_price,
                            data.close_price,
                            data.volume
                        ])
                    
                    logger.info(f"📊 从数据库获取历史数据: {len(klines)} 条")
                    
                    return {
                        "klines": klines,
                        "symbol": symbol,
                        "exchange": "okx",
                        "timeframe": timeframe,
                        "count": len(klines),
                        "timestamp": int(time.time() * 1000),
                        "source": "database_backup"
                    }
        except Exception as e:
            logger.warning(f"⚠️ 从数据库获取历史数据失败: {e}")
        
        # 如果数据库也没有，生成基于真实价格范围的模拟数据
        base_prices = {
            "BTC/USDT": 95000,   # 接近真实价格范围
            "ETH/USDT": 3500,  
            "SOL/USDT": 200,
            "ADA/USDT": 0.9,
            "DOT/USDT": 7.5,
            "LINK/USDT": 20,
            "MATIC/USDT": 1.1,
            "AVAX/USDT": 45
        }
        
        base_price = base_prices.get(symbol, 100)
        current_time = int(time.time() * 1000)
        
        # 生成基于时间间隔的模拟数据
        interval_ms = {
            "1m": 60000, "5m": 300000, "15m": 900000, "30m": 1800000,
            "1h": 3600000, "2h": 7200000, "4h": 14400000, "1d": 86400000
        }.get(timeframe, 3600000)
        
        klines = []
        for i in range(limit):
            timestamp = current_time - interval_ms * (limit - i - 1)
            
            # 生成小幅波动的数据 (±2%)
            variation = 0.02 * (i / limit - 0.5)  
            open_price = base_price * (1 + variation)
            close_price = open_price * (1 + (variation * 0.5))
            high_price = max(open_price, close_price) * 1.01
            low_price = min(open_price, close_price) * 0.99
            volume = 100 + (i * 10)
            
            klines.append([
                timestamp,
                round(open_price, 2),
                round(high_price, 2), 
                round(low_price, 2),
                round(close_price, 2),
                round(volume, 4)
            ])
        
        return {
            "klines": klines,
            "symbol": symbol,
            "exchange": "okx",
            "timeframe": timeframe,
            "count": len(klines),
            "timestamp": current_time,
            "source": "fallback_simulation"
        }
    
    async def _get_fallback_ticker(self, symbol: str) -> Dict:
        """获取备用价格数据"""
        logger.warning(f"⚠️ 使用备用价格数据: {symbol}")
        
        base_prices = {
            "BTC/USDT": 95000,
            "ETH/USDT": 3500,
            "SOL/USDT": 200,
            "ADA/USDT": 0.9,
            "DOT/USDT": 7.5,
            "LINK/USDT": 20,
            "MATIC/USDT": 1.1,
            "AVAX/USDT": 45
        }
        
        base_price = base_prices.get(symbol, 100)
        current_price = base_price * (1 + (time.time() % 100 - 50) / 10000)  # 小幅波动
        
        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "change_24h": round((time.time() % 10 - 5), 2),  # -5% to +5%
            "high_24h": round(current_price * 1.05, 2),
            "low_24h": round(current_price * 0.95, 2),
            "volume_24h": round(1000000 + (time.time() % 5000000), 2),
            "timestamp": int(time.time() * 1000),
            "exchange": "okx",
            "source": "fallback_simulation"
        }
    
    def _get_default_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """获取默认交易对信息"""
        base, quote = symbol.split("/")
        
        return {
            "symbol": symbol,
            "base_asset": base,
            "quote_asset": quote,
            "min_qty": 0.001,
            "min_notional": 10,
            "tick_size": 0.01,
            "lot_size": 0.001,
            "status": "TRADING",
            "exchange": "okx"
        }
    
    @asynccontextmanager
    async def _get_db_session(self):
        """获取数据库会话上下文管理器"""
        async with AsyncSessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 测试获取BTC价格
            ticker = await self.get_ticker("BTC/USDT")
            
            return {
                "status": "healthy",
                "service": "okx_market_data",
                "timestamp": int(time.time() * 1000),
                "cache_size": {
                    "klines": len(self.kline_cache),
                    "tickers": len(self.ticker_cache)
                },
                "test_result": {
                    "symbol": ticker["symbol"],
                    "price": ticker["price"],
                    "source": ticker["source"]
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "okx_market_data",
                "timestamp": int(time.time() * 1000),
                "error": str(e)
            }


# 全局实例
okx_market_service = OKXMarketDataService()