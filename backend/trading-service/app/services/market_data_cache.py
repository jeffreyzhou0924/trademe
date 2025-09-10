"""
市场数据缓存服务
专门处理实时行情、K线数据、历史数据等高频更新的市场数据缓存
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from decimal import Decimal

from .redis_cache_service import RedisCacheService, cached

logger = logging.getLogger(__name__)

@dataclass
class MarketDataPoint:
    """市场数据点"""
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    change_24h: Optional[float] = None

@dataclass
class KlineData:
    """K线数据"""
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime
    interval: str  # 1m, 5m, 15m, 1h, 4h, 1d

class MarketDataCacheService:
    """市场数据缓存服务"""
    
    def __init__(self, cache_service: RedisCacheService):
        self.cache = cache_service
        self.price_update_frequency = 1  # 价格更新频率（秒）
        self.kline_update_frequency = 60  # K线更新频率（秒）
        
        # 预设缓存配置
        self._setup_cache_configs()
        
    def _setup_cache_configs(self):
        """设置缓存配置"""
        from .redis_cache_service import CacheConfig, CompressionType
        
        self.cache.cache_configs.update({
            "real_time_prices": CacheConfig(
                ttl=5,  # 实时价格5秒过期
                namespace="market_price",
                compression=CompressionType.JSON
            ),
            "kline_data": CacheConfig(
                ttl=300,  # K线数据5分钟过期
                namespace="market_kline",
                compression=CompressionType.GZIP
            ),
            "volume_data": CacheConfig(
                ttl=60,  # 成交量数据1分钟过期
                namespace="market_volume"
            ),
            "symbol_list": CacheConfig(
                ttl=3600,  # 交易对列表1小时过期
                namespace="market_symbols"
            ),
            "market_depth": CacheConfig(
                ttl=10,  # 市场深度10秒过期
                namespace="market_depth",
                compression=CompressionType.JSON
            ),
            "price_history": CacheConfig(
                ttl=1800,  # 价格历史30分钟过期
                namespace="market_history",
                compression=CompressionType.GZIP
            )
        })
    
    async def cache_real_time_price(self, symbol: str, price_data: MarketDataPoint) -> bool:
        """缓存实时价格数据"""
        try:
            key = f"price:{symbol}"
            data = asdict(price_data)
            # 转换datetime为字符串
            data['timestamp'] = price_data.timestamp.isoformat()
            
            success = await self.cache.set(key, data, "real_time_prices")
            
            if success:
                # 同时更新价格历史记录
                await self._update_price_history(symbol, price_data)
                logger.debug(f"成功缓存 {symbol} 实时价格: {price_data.price}")
            
            return success
            
        except Exception as e:
            logger.error(f"缓存实时价格失败 {symbol}: {e}")
            return False
    
    async def get_real_time_price(self, symbol: str) -> Optional[MarketDataPoint]:
        """获取实时价格数据"""
        try:
            key = f"price:{symbol}"
            data = await self.cache.get(key, "real_time_prices")
            
            if data:
                # 转换时间戳
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                return MarketDataPoint(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"获取实时价格失败 {symbol}: {e}")
            return None
    
    async def cache_multiple_prices(self, prices: Dict[str, MarketDataPoint]) -> Dict[str, bool]:
        """批量缓存价格数据"""
        results = {}
        
        # 使用asyncio.gather并发处理
        tasks = []
        symbols = []
        
        for symbol, price_data in prices.items():
            task = self.cache_real_time_price(symbol, price_data)
            tasks.append(task)
            symbols.append(symbol)
        
        try:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, result in zip(symbols, results_list):
                if isinstance(result, Exception):
                    results[symbol] = False
                    logger.error(f"批量缓存价格失败 {symbol}: {result}")
                else:
                    results[symbol] = result
                    
        except Exception as e:
            logger.error(f"批量缓存价格出错: {e}")
            
        return results
    
    async def cache_kline_data(self, symbol: str, interval: str, 
                              klines: List[KlineData]) -> bool:
        """缓存K线数据"""
        try:
            key = f"kline:{symbol}:{interval}"
            
            # 转换K线数据
            serialized_klines = []
            for kline in klines:
                data = asdict(kline)
                data['timestamp'] = kline.timestamp.isoformat()
                serialized_klines.append(data)
            
            success = await self.cache.set(key, serialized_klines, "kline_data")
            
            if success:
                logger.debug(f"成功缓存 {symbol} {interval} K线数据, 条数: {len(klines)}")
            
            return success
            
        except Exception as e:
            logger.error(f"缓存K线数据失败 {symbol}_{interval}: {e}")
            return False
    
    async def get_kline_data(self, symbol: str, interval: str, 
                            limit: int = 100) -> List[KlineData]:
        """获取K线数据"""
        try:
            key = f"kline:{symbol}:{interval}"
            data = await self.cache.get(key, "kline_data")
            
            if not data:
                return []
            
            # 转换数据
            klines = []
            for item in data[-limit:]:  # 只返回最新的limit条
                item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                klines.append(KlineData(**item))
            
            return klines
            
        except Exception as e:
            logger.error(f"获取K线数据失败 {symbol}_{interval}: {e}")
            return []
    
    async def cache_market_depth(self, symbol: str, depth_data: Dict) -> bool:
        """缓存市场深度数据"""
        try:
            key = f"depth:{symbol}"
            depth_data['timestamp'] = datetime.utcnow().isoformat()
            
            return await self.cache.set(key, depth_data, "market_depth")
            
        except Exception as e:
            logger.error(f"缓存市场深度失败 {symbol}: {e}")
            return False
    
    async def get_market_depth(self, symbol: str) -> Optional[Dict]:
        """获取市场深度数据"""
        try:
            key = f"depth:{symbol}"
            return await self.cache.get(key, "market_depth")
            
        except Exception as e:
            logger.error(f"获取市场深度失败 {symbol}: {e}")
            return None
    
    async def cache_symbol_list(self, exchange: str, symbols: List[str]) -> bool:
        """缓存交易对列表"""
        try:
            key = f"symbols:{exchange}"
            data = {
                'symbols': symbols,
                'timestamp': datetime.utcnow().isoformat(),
                'count': len(symbols)
            }
            
            return await self.cache.set(key, data, "symbol_list")
            
        except Exception as e:
            logger.error(f"缓存交易对列表失败 {exchange}: {e}")
            return False
    
    async def get_symbol_list(self, exchange: str) -> List[str]:
        """获取交易对列表"""
        try:
            key = f"symbols:{exchange}"
            data = await self.cache.get(key, "symbol_list")
            
            if data and 'symbols' in data:
                return data['symbols']
            
            return []
            
        except Exception as e:
            logger.error(f"获取交易对列表失败 {exchange}: {e}")
            return []
    
    async def _update_price_history(self, symbol: str, price_data: MarketDataPoint):
        """更新价格历史记录"""
        try:
            key = f"history:{symbol}"
            
            # 获取现有历史记录
            history = await self.cache.get(key, "price_history") or []
            
            # 添加新的价格点
            price_point = {
                'price': price_data.price,
                'volume': price_data.volume,
                'timestamp': price_data.timestamp.isoformat()
            }
            
            history.append(price_point)
            
            # 限制历史记录长度（最多保留1000个点）
            if len(history) > 1000:
                history = history[-1000:]
            
            await self.cache.set(key, history, "price_history")
            
        except Exception as e:
            logger.error(f"更新价格历史失败 {symbol}: {e}")
    
    async def get_price_history(self, symbol: str, 
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> List[Dict]:
        """获取价格历史数据"""
        try:
            key = f"history:{symbol}"
            history = await self.cache.get(key, "price_history") or []
            
            if not history:
                return []
            
            # 时间筛选
            if start_time or end_time:
                filtered_history = []
                for point in history:
                    point_time = datetime.fromisoformat(point['timestamp'])
                    
                    if start_time and point_time < start_time:
                        continue
                    if end_time and point_time > end_time:
                        continue
                        
                    filtered_history.append(point)
                
                return filtered_history
            
            return history
            
        except Exception as e:
            logger.error(f"获取价格历史失败 {symbol}: {e}")
            return []
    
    @cached(cache_type="real_time_prices", ttl=5)
    async def get_multi_symbol_prices(self, symbols: List[str]) -> Dict[str, Optional[MarketDataPoint]]:
        """获取多个交易对的价格（带缓存装饰器示例）"""
        prices = {}
        
        tasks = []
        for symbol in symbols:
            task = self.get_real_time_price(symbol)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                prices[symbol] = None
            else:
                prices[symbol] = result
        
        return prices
    
    async def clear_expired_data(self):
        """清理过期数据"""
        try:
            current_time = datetime.utcnow()
            
            # 清理过期的价格历史（超过24小时的数据）
            cutoff_time = current_time - timedelta(hours=24)
            
            # 这里可以实现更复杂的清理逻辑
            logger.info("开始清理过期市场数据")
            
            # 清理过期的实时价格数据
            await self.cache.clear_namespace("market_price")
            
            logger.info("过期市场数据清理完成")
            
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            stats = {
                "market_data_types": [
                    "real_time_prices",
                    "kline_data", 
                    "volume_data",
                    "symbol_list",
                    "market_depth",
                    "price_history"
                ],
                "cache_metrics": self.cache.get_metrics(),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # 添加各类型数据计数
            for cache_type in stats["market_data_types"]:
                metrics = self.cache.get_metrics(cache_type)
                if metrics:
                    stats[f"{cache_type}_hit_rate"] = metrics.get("hit_rate", 0.0)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}

# 工具函数
def create_market_data_point(symbol: str, price: float, volume: float, 
                            **kwargs) -> MarketDataPoint:
    """创建市场数据点"""
    return MarketDataPoint(
        symbol=symbol,
        price=price,
        volume=volume,
        timestamp=datetime.utcnow(),
        **kwargs
    )

def create_kline_data(symbol: str, ohlcv: Tuple[float, float, float, float, float],
                     interval: str, timestamp: Optional[datetime] = None) -> KlineData:
    """创建K线数据"""
    open_price, high, low, close, volume = ohlcv
    
    return KlineData(
        symbol=symbol,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        timestamp=timestamp or datetime.utcnow(),
        interval=interval
    )