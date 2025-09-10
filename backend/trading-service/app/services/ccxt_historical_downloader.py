"""
CCXT历史数据下载器 - 生产级实现
支持长期历史数据批量下载，优化的错误处理和进度跟踪
"""

import ccxt
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import time
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from ..database import AsyncSessionLocal
from ..models import MarketData

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CCXTHistoricalDownloader:
    """
    基于CCXT的历史数据下载器
    - 支持多交易所 (OKX, Binance, etc.)
    - 智能分页和时间切片
    - 生产级错误处理和重试
    - 进度跟踪和状态管理
    """
    
    def __init__(self, exchange_id: str = 'okx'):
        """
        初始化下载器
        
        Args:
            exchange_id: 交易所ID (okx, binance, huobi, etc.)
        """
        self.exchange_id = exchange_id
        self.exchange = self._init_exchange()
        
        # 配置参数
        self.config = {
            'rate_limit_delay': 0.11,  # 110ms间隔，符合OKX限制
            'max_retries': 5,
            'retry_delay': 2,
            'batch_size': 300,  # 每次请求最大记录数
            'max_concurrent': 3,  # 最大并发请求数
        }
        
        # 时间框架配置 
        self.timeframe_ms = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
            '1w': 7 * 24 * 60 * 60 * 1000,
        }
        
        # 状态跟踪
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_records': 0,
            'start_time': None,
        }
    
    def _init_exchange(self) -> ccxt.Exchange:
        """初始化交易所实例"""
        try:
            if self.exchange_id == 'okx':
                exchange = ccxt.okx({
                    'rateLimit': 110,  # OKX限制为100ms，设置110ms更安全
                    'enableRateLimit': True,
                    'sandbox': False,
                })
            elif self.exchange_id == 'binance':
                exchange = ccxt.binance({
                    'rateLimit': 100,
                    'enableRateLimit': True,
                    'sandbox': False,
                })
            else:
                raise ValueError(f"不支持的交易所: {self.exchange_id}")
            
            exchange.load_markets()
            logger.info(f"✅ {self.exchange_id.upper()} 交易所初始化成功")
            return exchange
            
        except Exception as e:
            logger.error(f"❌ 交易所初始化失败: {str(e)}")
            raise
    
    async def download_historical_data(
        self,
        symbols: List[str],
        timeframes: List[str], 
        start_date: datetime,
        end_date: datetime,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        下载历史数据的主方法
        
        Args:
            symbols: 交易对列表 ['BTC/USDT:USDT', 'ETH/USDT:USDT']
            timeframes: 时间框架列表 ['1m', '5m', '1h', '1d']  
            start_date: 开始日期
            end_date: 结束日期
            progress_callback: 进度回调函数
            
        Returns:
            下载结果统计
        """
        self.stats['start_time'] = datetime.now()
        
        logger.info(f"🚀 开始下载历史数据")
        logger.info(f"📊 交易所: {self.exchange_id.upper()}")
        logger.info(f"💰 交易对: {symbols}")
        logger.info(f"⏰ 时间框架: {timeframes}")
        logger.info(f"📅 时间范围: {start_date} -> {end_date}")
        
        try:
            # 创建下载任务
            tasks = []
            total_tasks = len(symbols) * len(timeframes)
            completed_tasks = 0
            
            for symbol in symbols:
                for timeframe in timeframes:
                    task_info = {
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'start_date': start_date,
                        'end_date': end_date,
                        'task_id': f"{symbol}_{timeframe}",
                    }
                    tasks.append(task_info)
            
            # 批量处理任务
            results = []
            semaphore = asyncio.Semaphore(self.config['max_concurrent'])
            
            async def process_task(task_info):
                async with semaphore:
                    result = await self._download_symbol_timeframe(
                        task_info['symbol'],
                        task_info['timeframe'], 
                        task_info['start_date'],
                        task_info['end_date']
                    )
                    
                    nonlocal completed_tasks
                    completed_tasks += 1
                    
                    if progress_callback:
                        progress = (completed_tasks / total_tasks) * 100
                        await progress_callback(progress, task_info, result)
                    
                    return result
            
            # 执行所有任务
            task_coroutines = [process_task(task) for task in tasks]
            results = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            # 统计结果
            summary = self._generate_summary(results)
            
            logger.info(f"🎉 下载完成!")
            logger.info(f"📈 总请求数: {self.stats['total_requests']}")
            logger.info(f"✅ 成功: {self.stats['successful_requests']}")
            logger.info(f"❌ 失败: {self.stats['failed_requests']}")
            logger.info(f"📊 总记录数: {self.stats['total_records']}")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ 下载过程出错: {str(e)}")
            raise
    
    async def _download_symbol_timeframe(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        下载单个交易对和时间框架的数据
        """
        logger.info(f"📥 开始下载 {symbol} {timeframe}")
        
        try:
            # 转换时间戳
            since = int(start_date.timestamp() * 1000)
            end_timestamp = int(end_date.timestamp() * 1000)
            
            all_data = []
            current_timestamp = since
            batch_count = 0
            
            while current_timestamp < end_timestamp:
                batch_count += 1
                
                try:
                    # 使用CCXT获取数据
                    ohlcv_data = await self._fetch_ohlcv_batch(
                        symbol, timeframe, current_timestamp
                    )
                    
                    if not ohlcv_data:
                        logger.warning(f"⚠️ {symbol} {timeframe} 批次 {batch_count} 返回空数据")
                        break
                    
                    # 过滤时间范围内的数据
                    filtered_data = [
                        candle for candle in ohlcv_data 
                        if candle[0] <= end_timestamp
                    ]
                    
                    all_data.extend(filtered_data)
                    
                    # 更新时间戳
                    last_timestamp = ohlcv_data[-1][0]
                    current_timestamp = last_timestamp + self.timeframe_ms[timeframe]
                    
                    # 如果最后一根K线已经超过结束时间，退出
                    if last_timestamp >= end_timestamp:
                        break
                    
                    logger.info(f"📊 {symbol} {timeframe} 批次 {batch_count}: {len(ohlcv_data)} 条数据")
                    
                    # 速率限制
                    await asyncio.sleep(self.config['rate_limit_delay'])
                    
                except Exception as e:
                    logger.error(f"❌ {symbol} {timeframe} 批次 {batch_count} 失败: {str(e)}")
                    await asyncio.sleep(self.config['retry_delay'])
                    continue
            
            # 保存到数据库
            saved_count = await self._save_to_database(symbol, timeframe, all_data)
            
            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'success': True,
                'total_records': len(all_data),
                'saved_records': saved_count,
                'batches': batch_count,
                'start_time': start_date,
                'end_time': end_date,
            }
            
            logger.info(f"✅ {symbol} {timeframe} 完成: {saved_count} 条记录")
            return result
            
        except Exception as e:
            logger.error(f"❌ {symbol} {timeframe} 下载失败: {str(e)}")
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'success': False,
                'error': str(e),
                'total_records': 0,
                'saved_records': 0,
            }
    
    async def _fetch_ohlcv_batch(
        self, 
        symbol: str, 
        timeframe: str, 
        since: int
    ) -> List[List]:
        """
        获取单批OHLCV数据，带重试机制
        """
        for attempt in range(self.config['max_retries']):
            try:
                self.stats['total_requests'] += 1
                
                # 使用CCXT的fetchOHLCV方法
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=self.config['batch_size']
                )
                
                self.stats['successful_requests'] += 1
                self.stats['total_records'] += len(ohlcv)
                
                return ohlcv
                
            except ccxt.RateLimitExceeded as e:
                wait_time = self.config['retry_delay'] * (2 ** attempt)
                logger.warning(f"⚠️ 速率限制，等待 {wait_time}s: {str(e)}")
                await asyncio.sleep(wait_time)
                
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
                wait_time = self.config['retry_delay'] * (2 ** attempt)
                logger.warning(f"⚠️ 网络错误，重试 {attempt+1}/{self.config['max_retries']}: {str(e)}")
                if attempt < self.config['max_retries'] - 1:
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"❌ 未知错误: {str(e)}")
                break
        
        self.stats['failed_requests'] += 1
        return []
    
    async def _save_to_database(
        self, 
        symbol: str, 
        timeframe: str, 
        ohlcv_data: List[List]
    ) -> int:
        """
        保存数据到数据库
        """
        if not ohlcv_data:
            return 0
        
        try:
            async with AsyncSessionLocal() as db:
                saved_count = 0
                
                for candle in ohlcv_data:
                    timestamp, open_price, high, low, close, volume = candle
                    
                    # 创建MarketData记录
                    market_data = MarketData(
                        symbol=symbol.replace('/', '').replace(':', ''),  # 格式化交易对名称
                        timeframe=timeframe,
                        timestamp=datetime.fromtimestamp(timestamp / 1000),
                        open_price=float(open_price),
                        high_price=float(high),
                        low_price=float(low),
                        close_price=float(close),
                        volume=float(volume),
                        exchange=self.exchange_id,
                    )
                    
                    db.add(market_data)
                    saved_count += 1
                
                await db.commit()
                return saved_count
                
        except Exception as e:
            logger.error(f"❌ 数据库保存失败: {str(e)}")
            return 0
    
    def _generate_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """
        生成下载结果摘要
        """
        successful = [r for r in results if isinstance(r, dict) and r.get('success', False)]
        failed = [r for r in results if isinstance(r, dict) and not r.get('success', False)]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        total_records = sum(r.get('saved_records', 0) for r in successful)
        elapsed_time = datetime.now() - self.stats['start_time']
        
        summary = {
            'success': True,
            'total_tasks': len(results),
            'successful_tasks': len(successful),
            'failed_tasks': len(failed) + len(exceptions),
            'total_records_downloaded': total_records,
            'total_api_requests': self.stats['total_requests'],
            'successful_api_requests': self.stats['successful_requests'],
            'failed_api_requests': self.stats['failed_requests'],
            'elapsed_time': str(elapsed_time),
            'download_rate': f"{total_records / elapsed_time.total_seconds():.2f} records/sec" if elapsed_time.total_seconds() > 0 else "N/A",
            'exchange': self.exchange_id,
            'timestamp': datetime.now().isoformat(),
        }
        
        return summary

# 使用示例和工厂函数
class CCXTDownloadTaskManager:
    """
    CCXT下载任务管理器
    提供简化的接口来执行批量历史数据下载
    """
    
    @staticmethod
    async def download_okx_historical_data(
        symbols: List[str],
        timeframes: List[str],
        days_back: int = 30,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        简化的OKX历史数据下载接口
        
        Args:
            symbols: 交易对列表，如 ['BTC/USDT:USDT', 'ETH/USDT:USDT']  
            timeframes: 时间框架列表，如 ['1m', '5m', '1h', '1d']
            days_back: 向前几天的数据
            progress_callback: 进度回调函数
            
        Returns:
            下载结果
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        downloader = CCXTHistoricalDownloader('okx')
        
        return await downloader.download_historical_data(
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            progress_callback=progress_callback
        )
    
    @staticmethod
    async def download_long_term_data(
        symbol: str,
        timeframe: str, 
        years_back: int = 1,
        exchange_id: str = 'okx'
    ) -> Dict[str, Any]:
        """
        下载长期历史数据（1-2年）
        
        Args:
            symbol: 交易对，如 'BTC/USDT:USDT'
            timeframe: 时间框架，如 '1h'
            years_back: 向前几年的数据
            exchange_id: 交易所ID
            
        Returns:
            下载结果
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years_back * 365)
        
        downloader = CCXTHistoricalDownloader(exchange_id)
        
        return await downloader.download_historical_data(
            symbols=[symbol],
            timeframes=[timeframe],
            start_date=start_date,
            end_date=end_date,
        )