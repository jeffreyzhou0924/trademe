"""
Tick数据管理器
支持高频tick数据的采集、存储、聚合和查询
"""

import asyncio
import ccxt.pro as ccxt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import pandas as pd
import numpy as np
from decimal import Decimal
from collections import defaultdict
import gzip
import pickle

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class TickDataManager:
    """Tick数据管理器"""
    
    def __init__(self):
        self.supported_exchanges = {
            'binance': ccxt.binance,
            'okx': ccxt.okx,
            'huobi': ccxt.huobi,
            'bybit': ccxt.bybit
        }
        
        # 分区策略：按小时分区存储
        self.partition_interval_hours = 1
        
        # 压缩策略：超过1小时的数据自动压缩
        self.compression_threshold_hours = 1
        
        # 内存缓存：最近1小时tick数据
        self.memory_cache = {}
        self.cache_expiry_hours = 1
    
    async def start_tick_stream(
        self,
        exchange_name: str,
        symbols: List[str],
        db: AsyncSession
    ):
        """启动tick数据实时采集流"""
        
        logger.info(f"启动tick数据流: {exchange_name} {symbols}")
        
        try:
            exchange_class = self.supported_exchanges.get(exchange_name.lower())
            if not exchange_class:
                raise ValueError(f"不支持的交易所: {exchange_name}")
            
            exchange = exchange_class({
                'apiKey': '',  # 使用公开WebSocket
                'secret': '',
                'timeout': 30000,
                'enableRateLimit': True
            })
            
            # 订阅tick数据流
            while True:
                for symbol in symbols:
                    try:
                        # 获取最新tick数据
                        ticker = await exchange.watch_ticker(symbol)
                        
                        if ticker:
                            tick_record = {
                                'exchange': exchange_name.lower(),
                                'symbol': symbol,
                                'timestamp': int(ticker['timestamp']),
                                'price': Decimal(str(ticker['last'])),
                                'quantity': Decimal(str(ticker.get('baseVolume', 0))),
                                'side': 'unknown',  # WebSocket ticker通常不包含方向
                                'data_source': 'websocket'
                            }
                            
                            # 保存到数据库和缓存
                            await self._save_tick_data(db, tick_record)
                            await self._update_memory_cache(symbol, tick_record)
                        
                        await asyncio.sleep(0.1)  # 100ms间隔
                        
                    except Exception as e:
                        logger.error(f"获取tick数据失败 {symbol}: {str(e)}")
                        await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Tick数据流异常: {str(e)}")
        finally:
            await exchange.close()
    
    async def get_tick_data_range(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取指定时间范围的tick数据"""
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        # 构建查询
        query = """
        SELECT timestamp, price, quantity, side, trade_id, is_buyer_maker
        FROM tick_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timestamp >= :start_ts 
          AND timestamp <= :end_ts
        ORDER BY timestamp ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        rows = result.fetchall()
        
        tick_data = []
        for row in rows:
            tick_data.append({
                'timestamp': row[0],
                'price': float(row[1]),
                'quantity': float(row[2]),
                'side': row[3],
                'trade_id': row[4],
                'is_buyer_maker': row[5]
            })
        
        logger.info(f"获取tick数据: {len(tick_data)} 条记录")
        return tick_data
    
    async def aggregate_ticks_to_klines(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """将tick数据聚合为K线数据"""
        
        logger.info(f"聚合tick数据为K线: {symbol} {timeframe} {start_date}-{end_date}")
        
        # 获取tick数据
        tick_data = await self.get_tick_data_range(
            exchange, symbol, start_date, end_date, db
        )
        
        if not tick_data:
            logger.warning("没有tick数据可聚合")
            return []
        
        # 转换为DataFrame进行聚合
        df = pd.DataFrame(tick_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # 根据timeframe进行重采样
        timeframe_mapping = {
            '1m': '1T',   # 1分钟
            '5m': '5T',   # 5分钟
            '15m': '15T', # 15分钟
            '1h': '1H',   # 1小时
            '4h': '4H',   # 4小时
            '1d': '1D'    # 1天
        }
        
        resample_rule = timeframe_mapping.get(timeframe, '1H')
        
        # 聚合计算OHLCV
        kline_df = df['price'].resample(resample_rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        })
        
        # 计算成交量
        volume_df = df['quantity'].resample(resample_rule).agg({
            'volume': 'sum',
            'trades_count': 'count'
        })
        
        # 合并数据
        result_df = pd.concat([kline_df, volume_df], axis=1)
        result_df.dropna(inplace=True)
        
        # 转换为标准格式
        kline_data = []
        for timestamp, row in result_df.iterrows():
            open_time = int(timestamp.timestamp() * 1000)
            
            # 计算收盘时间
            timeframe_ms = {
                '1m': 60 * 1000,
                '5m': 5 * 60 * 1000,
                '15m': 15 * 60 * 1000,
                '1h': 60 * 60 * 1000,
                '4h': 4 * 60 * 60 * 1000,
                '1d': 24 * 60 * 60 * 1000
            }.get(timeframe, 60 * 60 * 1000)
            
            close_time = open_time + timeframe_ms - 1
            
            kline_record = {
                'timestamp': open_time,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'trades_count': int(row['trades_count'])
            }
            kline_data.append(kline_record)
        
        logger.info(f"tick聚合完成: {len(tick_data)} ticks → {len(kline_data)} K线")
        return kline_data
    
    async def create_custom_timeframe_klines(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        custom_minutes: int,  # 自定义分钟数 (如：3分钟，7分钟等)
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """创建自定义时间框架的K线数据"""
        
        logger.info(f"创建自定义{custom_minutes}分钟K线: {symbol}")
        
        # 获取1分钟K线数据作为基础
        base_klines = await self._get_base_klines(
            exchange, symbol, start_date, end_date, '1m', db
        )
        
        if not base_klines:
            logger.warning("没有基础K线数据")
            return []
        
        # 按自定义时间框架聚合
        df = pd.DataFrame(base_klines)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # 自定义重采样规则
        resample_rule = f'{custom_minutes}T'
        
        aggregated = df.resample(resample_rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        aggregated.dropna(inplace=True)
        
        # 转换为结果格式
        custom_klines = []
        for timestamp, row in aggregated.iterrows():
            custom_klines.append({
                'timestamp': int(timestamp.timestamp() * 1000),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            })
        
        logger.info(f"自定义K线聚合完成: {len(custom_klines)} 条记录")
        return custom_klines
    
    async def _save_tick_data(
        self,
        db: AsyncSession,
        tick_record: Dict[str, Any]
    ):
        """保存单个tick数据"""
        
        # 检查是否需要分区存储
        partition_key = self._get_partition_key(tick_record['timestamp'])
        
        query = """
        INSERT OR IGNORE INTO tick_data 
        (exchange, symbol, timestamp, price, quantity, side, data_source)
        VALUES (:exchange, :symbol, :timestamp, :price, :quantity, :side, :data_source)
        """
        
        await db.execute(query, tick_record)
        await db.commit()
        
        # 检查是否需要压缩旧数据
        await self._check_compression_needed(db, tick_record['exchange'], tick_record['symbol'])
    
    async def _get_base_klines(
        self,
        exchange: str,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取基础K线数据"""
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        query = """
        SELECT open_time as timestamp, open_price as open, high_price as high, 
               low_price as low, close_price as close, volume
        FROM kline_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND open_time >= :start_ts 
          AND open_time <= :end_ts
        ORDER BY open_time ASC
        """
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        rows = result.fetchall()
        
        return [
            {
                'timestamp': row[0],
                'open': float(row[1]),
                'high': float(row[2]),
                'low': float(row[3]),
                'close': float(row[4]),
                'volume': float(row[5])
            }
            for row in rows
        ]
    
    async def _update_memory_cache(
        self,
        symbol: str,
        tick_record: Dict[str, Any]
    ):
        """更新内存缓存"""
        
        cache_key = f"{tick_record['exchange']}_{symbol}"
        
        if cache_key not in self.memory_cache:
            self.memory_cache[cache_key] = []
        
        self.memory_cache[cache_key].append(tick_record)
        
        # 保持缓存大小(最多保留1小时数据)
        cutoff_time = int((datetime.now() - timedelta(hours=self.cache_expiry_hours)).timestamp() * 1000)
        self.memory_cache[cache_key] = [
            tick for tick in self.memory_cache[cache_key]
            if tick['timestamp'] > cutoff_time
        ]
    
    def _get_partition_key(self, timestamp_ms: int) -> str:
        """生成分区键"""
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime('%Y%m%d_%H')  # 按小时分区
    
    async def _check_compression_needed(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str
    ):
        """检查是否需要压缩历史数据"""
        
        # 查询1小时前的数据是否需要压缩
        cutoff_time = int((datetime.now() - timedelta(hours=self.compression_threshold_hours)).timestamp() * 1000)
        
        query = """
        SELECT COUNT(*) FROM tick_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timestamp < :cutoff_time
          AND compressed = 0
        """
        
        try:
            result = await db.execute(query, {
                'exchange': exchange,
                'symbol': symbol,
                'cutoff_time': cutoff_time
            })
            
            uncompressed_count = result.scalar()
            
            # 如果超过10000条记录，启动压缩
            if uncompressed_count > 10000:
                await self._compress_old_tick_data(db, exchange, symbol, cutoff_time)
                
        except Exception as e:
            logger.error(f"检查压缩需求失败: {str(e)}")
    
    async def _compress_old_tick_data(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        cutoff_time: int
    ):
        """压缩旧的tick数据"""
        
        logger.info(f"开始压缩tick数据: {exchange} {symbol}")
        
        try:
            # 查询需要压缩的数据
            query_select = """
            SELECT timestamp, price, quantity, side, trade_id, is_buyer_maker
            FROM tick_data 
            WHERE exchange = :exchange 
              AND symbol = :symbol 
              AND timestamp < :cutoff_time
              AND compressed = 0
            ORDER BY timestamp ASC
            """
            
            result = await db.execute(query_select, {
                'exchange': exchange,
                'symbol': symbol,
                'cutoff_time': cutoff_time
            })
            
            rows = result.fetchall()
            
            if not rows:
                return
            
            # 压缩数据
            raw_data = [
                {
                    'timestamp': row[0],
                    'price': float(row[1]),
                    'quantity': float(row[2]),
                    'side': row[3],
                    'trade_id': row[4],
                    'is_buyer_maker': row[5]
                }
                for row in rows
            ]
            
            # 使用gzip压缩
            compressed_data = gzip.compress(pickle.dumps(raw_data))
            
            # 保存压缩数据到专用表
            await self._save_compressed_tick_data(
                db, exchange, symbol, compressed_data, len(rows), cutoff_time
            )
            
            # 删除原始数据
            query_delete = """
            DELETE FROM tick_data 
            WHERE exchange = :exchange 
              AND symbol = :symbol 
              AND timestamp < :cutoff_time
              AND compressed = 0
            """
            
            await db.execute(query_delete, {
                'exchange': exchange,
                'symbol': symbol,
                'cutoff_time': cutoff_time
            })
            
            await db.commit()
            
            logger.info(f"tick数据压缩完成: {len(rows)} 条记录")
            
        except Exception as e:
            logger.error(f"tick数据压缩失败: {str(e)}")
            await db.rollback()
    
    async def _save_compressed_tick_data(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        compressed_data: bytes,
        original_count: int,
        cutoff_time: int
    ):
        """保存压缩的tick数据"""
        
        query = """
        INSERT INTO tick_data_compressed 
        (exchange, symbol, time_range_start, time_range_end, 
         compressed_data, original_count, compression_ratio)
        VALUES (:exchange, :symbol, :start_time, :end_time, 
                :compressed_data, :original_count, :compression_ratio)
        """
        
        # 计算压缩比
        original_size = original_count * 100  # 估算原始大小
        compressed_size = len(compressed_data)
        compression_ratio = compressed_size / original_size
        
        await db.execute(query, {
            'exchange': exchange,
            'symbol': symbol,
            'start_time': cutoff_time - 3600 * 1000,  # 1小时前
            'end_time': cutoff_time,
            'compressed_data': compressed_data,
            'original_count': original_count,
            'compression_ratio': compression_ratio
        })
        
        await db.commit()

class TickToKlineAggregator:
    """Tick到K线聚合器"""
    
    def __init__(self):
        self.tick_manager = TickDataManager()
    
    async def create_realtime_klines(
        self,
        exchange: str,
        symbol: str,
        timeframes: List[str],
        db: AsyncSession
    ) -> Dict[str, List[Dict[str, Any]]]:
        """基于实时tick数据创建多时间框架K线"""
        
        logger.info(f"创建实时K线: {symbol} {timeframes}")
        
        # 获取最近1小时的tick数据
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        tick_data = await self.tick_manager.get_tick_data_range(
            exchange, symbol, start_time, end_time, db
        )
        
        results = {}
        
        for timeframe in timeframes:
            try:
                klines = await self.tick_manager.aggregate_ticks_to_klines(
                    exchange, symbol, start_time, end_time, timeframe, db
                )
                results[timeframe] = klines
                
            except Exception as e:
                logger.error(f"聚合失败 {timeframe}: {str(e)}")
                results[timeframe] = []
        
        return results
    
    async def backfill_missing_klines(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        missing_ranges: List[Tuple[datetime, datetime]],
        db: AsyncSession
    ) -> int:
        """使用tick数据回填缺失的K线数据"""
        
        total_backfilled = 0
        
        for start_date, end_date in missing_ranges:
            try:
                logger.info(f"回填K线数据: {symbol} {timeframe} {start_date}-{end_date}")
                
                # 检查是否有对应的tick数据
                tick_data = await self.tick_manager.get_tick_data_range(
                    exchange, symbol, start_date, end_date, db
                )
                
                if len(tick_data) < 10:
                    logger.warning(f"tick数据不足，跳过回填: {len(tick_data)} 条")
                    continue
                
                # 聚合为K线
                klines = await self.tick_manager.aggregate_ticks_to_klines(
                    exchange, symbol, start_date, end_date, timeframe, db
                )
                
                if klines:
                    # 保存到K线表
                    await self._save_backfilled_klines(
                        db, exchange, symbol, timeframe, klines
                    )
                    total_backfilled += len(klines)
                
            except Exception as e:
                logger.error(f"回填失败 {start_date}-{end_date}: {str(e)}")
        
        logger.info(f"回填完成: {total_backfilled} 条K线记录")
        return total_backfilled
    
    async def _save_backfilled_klines(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        klines: List[Dict[str, Any]]
    ):
        """保存回填的K线数据"""
        
        from app.services.historical_data_downloader import historical_data_downloader
        
        # 转换为标准格式
        timeframe_ms = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }.get(timeframe, 60 * 60 * 1000)
        
        batch_records = []
        for kline in klines:
            record = {
                'exchange': exchange.lower(),
                'symbol': symbol,
                'timeframe': timeframe,
                'open_time': kline['timestamp'],
                'close_time': kline['timestamp'] + timeframe_ms - 1,
                'open_price': Decimal(str(kline['open'])),
                'high_price': Decimal(str(kline['high'])),
                'low_price': Decimal(str(kline['low'])),
                'close_price': Decimal(str(kline['close'])),
                'volume': Decimal(str(kline['volume'])),
                'trades_count': kline.get('trades_count'),
                'data_source': 'tick_aggregation'
            }
            batch_records.append(record)
        
        # 批量插入
        await historical_data_downloader._batch_insert_klines(db, batch_records)

# 全局实例
tick_data_manager = TickDataManager()
tick_to_kline_aggregator = TickToKlineAggregator()