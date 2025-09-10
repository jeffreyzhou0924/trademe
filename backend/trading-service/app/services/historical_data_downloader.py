"""
历史数据下载器
支持多交易所K线和Tick数据的批量下载、存储和管理
"""

import asyncio
import ccxt.pro as ccxt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import select, insert, update, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import time
from decimal import Decimal

from app.database import AsyncSessionLocal
from app.database import Base

logger = logging.getLogger(__name__)

class HistoricalDataDownloader:
    """历史数据下载器"""
    
    def __init__(self):
        self.supported_exchanges = {
            'binance': ccxt.binance,
            'okx': ccxt.okx, 
            'huobi': ccxt.huobi,
            'bybit': ccxt.bybit,
            'coinbase': ccxt.coinbase
        }
        
        self.supported_timeframes = {
            '1m': 60 * 1000,      # 1分钟 = 60秒 * 1000毫秒
            '5m': 5 * 60 * 1000,  # 5分钟
            '15m': 15 * 60 * 1000, # 15分钟
            '1h': 60 * 60 * 1000,  # 1小时
            '4h': 4 * 60 * 60 * 1000, # 4小时
            '1d': 24 * 60 * 60 * 1000  # 1天
        }
        
        # 主要交易对列表
        self.major_symbols = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT',
            'XRP/USDT', 'DOT/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT'
        ]
    
    async def download_historical_klines(
        self,
        exchange_name: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """下载历史K线数据"""
        
        logger.info(f"开始下载历史数据: {exchange_name} {symbol} {timeframe} {start_date}-{end_date}")
        
        # 创建下载任务记录
        task_id = await self._create_download_task(
            db, exchange_name, symbol, timeframe, start_date, end_date
        )
        
        try:
            # 初始化交易所实例
            exchange_class = self.supported_exchanges.get(exchange_name.lower())
            if not exchange_class:
                raise ValueError(f"不支持的交易所: {exchange_name}")
            
            exchange = exchange_class({
                'apiKey': '',  # 使用公开API
                'secret': '',
                'timeout': 30000,
                'enableRateLimit': True,
                'sandbox': False,
            })
            
            # 计算时间范围和批次
            timeframe_ms = self.supported_timeframes[timeframe]
            start_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)
            
            total_expected = (end_ts - start_ts) // timeframe_ms
            await self._update_task_progress(db, task_id, 0, total_expected, 0)
            
            downloaded_count = 0
            current_ts = start_ts
            all_data = []
            
            while current_ts < end_ts:
                batch_start = current_ts
                batch_end = min(current_ts + (batch_size * timeframe_ms), end_ts)
                
                try:
                    # 下载批次数据
                    ohlcv_data = await exchange.fetch_ohlcv(
                        symbol, timeframe, since=batch_start, limit=batch_size
                    )
                    
                    if not ohlcv_data:
                        logger.warning(f"未获取到数据: {symbol} {timeframe} {batch_start}")
                        current_ts = batch_end
                        continue
                    
                    # 处理和保存数据
                    batch_records = []
                    for ohlcv in ohlcv_data:
                        timestamp, open_p, high_p, low_p, close_p, volume = ohlcv
                        
                        # 跳过重复数据
                        if timestamp < batch_start or timestamp >= batch_end:
                            continue
                            
                        record = {
                            'exchange': exchange_name.lower(),
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'open_time': timestamp,
                            'close_time': timestamp + timeframe_ms - 1,
                            'open_price': Decimal(str(open_p)),
                            'high_price': Decimal(str(high_p)),
                            'low_price': Decimal(str(low_p)),
                            'close_price': Decimal(str(close_p)),
                            'volume': Decimal(str(volume)),
                            'data_source': 'api'
                        }
                        batch_records.append(record)
                    
                    # 批量插入数据库
                    if batch_records:
                        await self._batch_insert_klines(db, batch_records)
                        downloaded_count += len(batch_records)
                        all_data.extend(batch_records)
                    
                    # 更新进度
                    progress = min((current_ts - start_ts) / (end_ts - start_ts) * 100, 100)
                    await self._update_task_progress(db, task_id, progress, total_expected, downloaded_count)
                    
                    logger.info(f"已下载 {downloaded_count} 条记录, 进度: {progress:.1f}%")
                    
                    # 防止API限流
                    await asyncio.sleep(exchange.rateLimit / 1000)
                    
                except Exception as e:
                    logger.error(f"下载批次失败 {batch_start}-{batch_end}: {str(e)}")
                    # 继续下一批次
                    pass
                
                finally:
                    current_ts = batch_end
            
            # 完成任务
            await self._complete_download_task(db, task_id, 'completed', downloaded_count)
            await exchange.close()
            
            # 更新缓存元信息
            await self._update_cache_metadata(db, exchange_name, symbol, timeframe, all_data)
            
            logger.info(f"历史数据下载完成: {downloaded_count} 条记录")
            
            return {
                'success': True,
                'task_id': task_id,
                'downloaded_count': downloaded_count,
                'total_expected': total_expected,
                'data_range': f"{start_date} - {end_date}"
            }
            
        except Exception as e:
            await self._complete_download_task(db, task_id, 'failed', downloaded_count, str(e))
            logger.error(f"历史数据下载失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'task_id': task_id
            }
    
    async def download_major_symbols_data(
        self,
        exchange_name: str,
        timeframes: List[str] = ['1h', '1d'],
        days_back: int = 365,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """批量下载主要交易对历史数据"""
        
        should_close_db = False
        if not db:
            db = AsyncSessionLocal()
            should_close_db = True
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            results = []
            total_tasks = len(self.major_symbols) * len(timeframes)
            completed_tasks = 0
            
            logger.info(f"开始批量下载 {total_tasks} 个数据集")
            
            for symbol in self.major_symbols:
                for timeframe in timeframes:
                    try:
                        result = await self.download_historical_klines(
                            exchange_name, symbol, timeframe, start_date, end_date, db
                        )
                        results.append({
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'result': result
                        })
                        completed_tasks += 1
                        
                        logger.info(f"进度: {completed_tasks}/{total_tasks} ({completed_tasks/total_tasks*100:.1f}%)")
                        
                        # 防止过载
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"下载失败 {symbol} {timeframe}: {str(e)}")
                        results.append({
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'result': {'success': False, 'error': str(e)}
                        })
            
            # 统计结果
            successful = sum(1 for r in results if r['result'].get('success'))
            total_records = sum(r['result'].get('downloaded_count', 0) for r in results if r['result'].get('success'))
            
            return {
                'success': True,
                'total_tasks': total_tasks,
                'successful_tasks': successful,
                'total_records': total_records,
                'results': results
            }
            
        finally:
            if should_close_db:
                await db.close()
    
    async def get_local_kline_data(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """从本地数据库获取K线数据"""
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        # 构建查询(使用原生SQL确保性能)
        query = text("""
        SELECT timestamp, open_price, high_price, low_price, close_price, volume
        FROM market_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND timestamp >= :start_ts 
          AND timestamp <= :end_ts
        ORDER BY timestamp ASC
        """)
        
        result = await db.execute(
            query,
            {
                'exchange': exchange.lower(),
                'symbol': symbol,
                'timeframe': timeframe,
                'start_ts': start_ts,
                'end_ts': end_ts
            }
        )
        
        rows = result.fetchall()
        
        # 转换为标准格式
        kline_data = []
        for row in rows:
            kline_data.append({
                'timestamp': row[0],
                'open': float(row[1]),
                'high': float(row[2]),
                'low': float(row[3]),
                'close': float(row[4]),
                'volume': float(row[5])
            })
        
        logger.info(f"从本地获取K线数据: {len(kline_data)} 条记录")
        return kline_data
    
    async def check_data_availability(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """检查数据可用性"""
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        # 查询数据覆盖范围
        query = text("""
        SELECT 
            MIN(timestamp) as first_timestamp,
            MAX(timestamp) as last_timestamp,
            COUNT(*) as total_records
        FROM market_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
        """)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe
        })
        
        row = result.fetchone()
        
        if not row or not row[0]:
            return {
                'available': False,
                'coverage': 0.0,
                'missing_ranges': [(start_date, end_date)],
                'total_records': 0
            }
        
        first_ts, last_ts, total_records = row
        
        # 计算覆盖范围
        data_start = max(start_ts, first_ts)
        data_end = min(end_ts, last_ts)
        
        if data_start >= data_end:
            coverage = 0.0
            missing_ranges = [(start_date, end_date)]
        else:
            coverage = (data_end - data_start) / (end_ts - start_ts) * 100
            missing_ranges = []
            
            # 检查缺失范围
            if start_ts < first_ts:
                missing_ranges.append((
                    start_date,
                    datetime.fromtimestamp(first_ts / 1000)
                ))
            
            if last_ts < end_ts:
                missing_ranges.append((
                    datetime.fromtimestamp(last_ts / 1000),
                    end_date
                ))
        
        return {
            'available': coverage > 80,  # 80%以上认为可用
            'coverage': coverage,
            'missing_ranges': missing_ranges,
            'total_records': total_records,
            'first_date': datetime.fromtimestamp(first_ts / 1000) if first_ts else None,
            'last_date': datetime.fromtimestamp(last_ts / 1000) if last_ts else None
        }
    
    async def _create_download_task(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """创建下载任务记录"""
        
        query = text("""
        INSERT INTO data_download_tasks 
        (exchange, symbol, timeframe, start_date, end_date, status, started_at)
        VALUES (:exchange, :symbol, :timeframe, :start_date, :end_date, 'running', :started_at)
        """)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_date': start_date,
            'end_date': end_date,
            'started_at': datetime.now()
        })
        
        await db.commit()
        return result.lastrowid
    
    async def _update_task_progress(
        self,
        db: AsyncSession,
        task_id: int,
        progress: float,
        total_expected: int,
        downloaded_records: int
    ):
        """更新任务进度"""
        
        query = text("""
        UPDATE data_download_tasks 
        SET progress = :progress, 
            total_records = :total_expected,
            downloaded_records = :downloaded_records
        WHERE id = :task_id
        """)
        
        await db.execute(query, {
            'task_id': task_id,
            'progress': progress,
            'total_expected': total_expected,
            'downloaded_records': downloaded_records
        })
        await db.commit()
    
    async def _complete_download_task(
        self,
        db: AsyncSession,
        task_id: int,
        status: str,
        downloaded_records: int,
        error_message: Optional[str] = None
    ):
        """完成下载任务"""
        
        query = text("""
        UPDATE data_download_tasks 
        SET status = :status,
            downloaded_records = :downloaded_records,
            error_message = :error_message,
            completed_at = :completed_at
        WHERE id = :task_id
        """)
        
        await db.execute(query, {
            'task_id': task_id,
            'status': status,
            'downloaded_records': downloaded_records,
            'error_message': error_message,
            'completed_at': datetime.now()
        })
        await db.commit()
    
    async def _batch_insert_klines(
        self,
        db: AsyncSession,
        records: List[Dict[str, Any]]
    ):
        """批量插入K线数据"""
        
        if not records:
            return
        
        # 使用INSERT OR IGNORE避免重复数据
        query_str = """
        INSERT OR IGNORE INTO kline_data 
        (exchange, symbol, timeframe, open_time, close_time, open_price, 
         high_price, low_price, close_price, volume, quote_volume, data_source)
        VALUES 
        """ + ",".join([
            f"(:{i}_exchange, :{i}_symbol, :{i}_timeframe, :{i}_open_time, :{i}_close_time, "
            f":{i}_open_price, :{i}_high_price, :{i}_low_price, :{i}_close_price, "
            f":{i}_volume, :{i}_quote_volume, :{i}_data_source)"
            for i in range(len(records))
        ])
        query = text(query_str)
        
        # 构建参数字典
        params = {}
        for i, record in enumerate(records):
            for key, value in record.items():
                params[f"{i}_{key}"] = value
        
        await db.execute(query, params)
        await db.commit()
    
    async def _update_cache_metadata(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        data: List[Dict[str, Any]]
    ):
        """更新缓存元信息"""
        
        if not data:
            return
        
        first_ts = min(d['open_time'] for d in data)
        last_ts = max(d['open_time'] for d in data)
        storage_size = len(json.dumps(data).encode('utf-8')) / 1024 / 1024  # MB
        
        # 查询是否已存在记录
        query_check = """
        SELECT id FROM data_cache_metadata 
        WHERE exchange = :exchange AND symbol = :symbol AND timeframe = :timeframe
        """
        
        result = await db.execute(query_check, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe
        })
        
        existing = result.fetchone()
        
        if existing:
            # 更新现有记录
            query_update = """
            UPDATE data_cache_metadata 
            SET first_timestamp = COALESCE(MIN(:first_ts, first_timestamp), :first_ts),
                last_timestamp = COALESCE(MAX(:last_ts, last_timestamp), :last_ts),
                total_records = total_records + :new_records,
                storage_size_mb = storage_size_mb + :storage_size,
                last_sync_at = :last_sync_at,
                sync_status = 'active',
                updated_at = :updated_at
            WHERE id = :id
            """
            
            await db.execute(query_update, {
                'id': existing[0],
                'first_ts': first_ts,
                'last_ts': last_ts,
                'new_records': len(data),
                'storage_size': storage_size,
                'last_sync_at': datetime.now(),
                'updated_at': datetime.now()
            })
        else:
            # 创建新记录
            query_insert = """
            INSERT INTO data_cache_metadata 
            (exchange, symbol, timeframe, first_timestamp, last_timestamp, 
             total_records, storage_size_mb, last_sync_at, sync_status)
            VALUES 
            (:exchange, :symbol, :timeframe, :first_ts, :last_ts, 
             :total_records, :storage_size, :last_sync_at, 'active')
            """
            
            await db.execute(query_insert, {
                'exchange': exchange.lower(),
                'symbol': symbol,
                'timeframe': timeframe,
                'first_ts': first_ts,
                'last_ts': last_ts,
                'total_records': len(data),
                'storage_size': storage_size,
                'last_sync_at': datetime.now()
            })
        
        await db.commit()

# 单例实例
historical_data_downloader = HistoricalDataDownloader()


class DataSyncScheduler:
    """数据同步调度器"""
    
    def __init__(self):
        self.downloader = historical_data_downloader
        self.is_running = False
    
    async def start_continuous_sync(
        self,
        exchanges: List[str] = ['binance', 'okx'],
        symbols: List[str] = None,
        timeframes: List[str] = ['1h', '1d'],
        sync_interval_hours: int = 6
    ):
        """启动持续同步服务"""
        
        if self.is_running:
            logger.warning("数据同步服务已在运行")
            return
        
        self.is_running = True
        symbols = symbols or self.downloader.major_symbols
        
        logger.info(f"启动数据同步服务: {len(exchanges)}个交易所, {len(symbols)}个交易对")
        
        while self.is_running:
            try:
                async with AsyncSessionLocal() as db:
                    for exchange in exchanges:
                        for symbol in symbols:
                            for timeframe in timeframes:
                                await self._sync_latest_data(db, exchange, symbol, timeframe)
                                await asyncio.sleep(1)  # 防止过载
                
                logger.info(f"数据同步完成，等待 {sync_interval_hours} 小时...")
                await asyncio.sleep(sync_interval_hours * 3600)
                
            except Exception as e:
                logger.error(f"数据同步失败: {str(e)}")
                await asyncio.sleep(300)  # 失败后等待5分钟重试
    
    async def _sync_latest_data(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str
    ):
        """同步最新数据"""
        
        # 查询最新数据时间戳
        query = text("""
        SELECT MAX(open_time) FROM kline_data 
        WHERE exchange = :exchange AND symbol = :symbol AND timeframe = :timeframe
        """)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe
        })
        
        last_timestamp = result.scalar()
        
        if last_timestamp:
            start_date = datetime.fromtimestamp(last_timestamp / 1000)
        else:
            start_date = datetime.now() - timedelta(days=7)  # 默认获取一周数据
        
        end_date = datetime.now()
        
        # 下载增量数据
        await self.downloader.download_historical_klines(
            exchange, symbol, timeframe, start_date, end_date, db, batch_size=500
        )
    
    def stop_sync(self):
        """停止同步服务"""
        self.is_running = False
        logger.info("数据同步服务已停止")

# 全局调度器实例
data_sync_scheduler = DataSyncScheduler()