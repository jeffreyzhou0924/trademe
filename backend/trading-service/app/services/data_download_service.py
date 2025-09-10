"""
数据下载服务
负责从各个交易所下载K线数据和Tick数据，支持批量下载、增量更新、数据验证等功能
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import numpy as np

import ccxt
import ccxt.async_support as ccxt_async
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.data_collection import ExchangeAPIConfig
from app.models.data_management import TickData, DataExportTask
from app.models.market_data import MarketData


# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class DownloadRequest:
    """数据下载请求"""
    exchange: str
    symbol: str
    data_type: str  # 'kline' or 'tick'
    timeframe: Optional[str] = None  # 仅用于K线数据
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 1000
    save_to_db: bool = True
    export_format: Optional[str] = None  # 'csv', 'json', 'parquet'


@dataclass
class DownloadResult:
    """数据下载结果"""
    success: bool
    records_count: int
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    data_size_mb: float = 0.0


@dataclass
class DataValidationResult:
    """数据验证结果"""
    is_valid: bool
    issues: List[str]
    quality_score: float
    completeness: float
    duplicates_count: int
    outliers_count: int


class DataDownloadService:
    """数据下载服务"""
    
    # 支持的交易所配置
    SUPPORTED_EXCHANGES = {
        'binance': {
            'has_ohlcv': True,
            'has_trades': True,
            'timeframes': ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'],
            'rate_limit': 1200,  # 每分钟请求数
            'max_candles': 1000
        },
        'okx': {
            'has_ohlcv': True,
            'has_trades': True, 
            'timeframes': ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M'],
            'rate_limit': 600,
            'max_candles': 300
        },
        'huobi': {
            'has_ohlcv': True,
            'has_trades': True,
            'timeframes': ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'],
            'rate_limit': 600,
            'max_candles': 2000
        },
        'bybit': {
            'has_ohlcv': True,
            'has_trades': True,
            'timeframes': ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M'],
            'rate_limit': 600,
            'max_candles': 1000
        }
    }
    
    def __init__(self, export_directory: str = "/tmp/data_exports"):
        self.exchange_clients: Dict[str, ccxt_async.Exchange] = {}
        self.export_directory = Path(export_directory)
        self.export_directory.mkdir(parents=True, exist_ok=True)
        
    async def download_kline_data(self, request: DownloadRequest) -> DownloadResult:
        """下载K线数据"""
        start_time = datetime.now()
        
        try:
            # 验证请求参数
            validation_error = self._validate_kline_request(request)
            if validation_error:
                return DownloadResult(
                    success=False,
                    records_count=0,
                    error_message=validation_error
                )
            
            # 获取交易所客户端
            client = await self._get_exchange_client(request.exchange)
            
            # 计算时间范围
            start_timestamp = int(request.start_time.timestamp() * 1000) if request.start_time else None
            end_timestamp = int(request.end_time.timestamp() * 1000) if request.end_time else None
            
            # 分批下载数据
            all_ohlcv_data = []
            current_timestamp = start_timestamp
            
            exchange_config = self.SUPPORTED_EXCHANGES.get(request.exchange, {})
            max_candles = exchange_config.get('max_candles', 1000)
            
            while True:
                # 下载一批数据
                ohlcv_batch = await client.fetch_ohlcv(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    since=current_timestamp,
                    limit=min(request.limit, max_candles)
                )
                
                if not ohlcv_batch:
                    break
                
                # 过滤时间范围内的数据
                if end_timestamp:
                    ohlcv_batch = [candle for candle in ohlcv_batch if candle[0] <= end_timestamp]
                
                all_ohlcv_data.extend(ohlcv_batch)
                
                # 检查是否达到结束时间或请求限制
                if (end_timestamp and ohlcv_batch[-1][0] >= end_timestamp) or len(all_ohlcv_data) >= request.limit:
                    break
                
                # 更新下次请求的起始时间
                current_timestamp = ohlcv_batch[-1][0] + 1
                
                # 避免请求频率过高
                await asyncio.sleep(0.1)
            
            # 限制返回数据量
            if len(all_ohlcv_data) > request.limit:
                all_ohlcv_data = all_ohlcv_data[:request.limit]
            
            # 数据验证
            validation_result = self._validate_ohlcv_data(all_ohlcv_data)
            if not validation_result.is_valid:
                logger.warning(f"K线数据质量问题: {validation_result.issues}")
            
            # 保存到数据库
            saved_records = 0
            if request.save_to_db:
                saved_records = await self._save_kline_to_db(
                    request.exchange, request.symbol, request.timeframe, all_ohlcv_data
                )
            
            # 导出文件
            file_path = None
            if request.export_format:
                file_path = await self._export_kline_data(request, all_ohlcv_data)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return DownloadResult(
                success=True,
                records_count=saved_records if request.save_to_db else len(all_ohlcv_data),
                file_path=file_path,
                processing_time=processing_time,
                data_size_mb=self._calculate_data_size(all_ohlcv_data)
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"下载K线数据失败: {e}")
            
            return DownloadResult(
                success=False,
                records_count=0,
                error_message=str(e),
                processing_time=processing_time
            )
    
    async def download_tick_data(self, request: DownloadRequest) -> DownloadResult:
        """下载Tick数据（基于交易数据）"""
        start_time = datetime.now()
        
        try:
            # 验证请求参数
            validation_error = self._validate_tick_request(request)
            if validation_error:
                return DownloadResult(
                    success=False,
                    records_count=0,
                    error_message=validation_error
                )
            
            # 获取交易所客户端
            client = await self._get_exchange_client(request.exchange)
            
            # 计算时间范围（Tick数据通常只能获取最近的数据）
            since = int(request.start_time.timestamp() * 1000) if request.start_time else None
            
            # 下载交易数据（作为Tick数据）
            trades_data = await client.fetch_trades(
                symbol=request.symbol,
                since=since,
                limit=min(request.limit, 1000)  # 限制单次请求数量
            )
            
            # 数据验证
            validation_result = self._validate_trades_data(trades_data)
            if not validation_result.is_valid:
                logger.warning(f"Tick数据质量问题: {validation_result.issues}")
            
            # 保存到数据库
            saved_records = 0
            if request.save_to_db:
                saved_records = await self._save_tick_to_db(request.exchange, request.symbol, trades_data)
            
            # 导出文件
            file_path = None
            if request.export_format:
                file_path = await self._export_tick_data(request, trades_data)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return DownloadResult(
                success=True,
                records_count=saved_records if request.save_to_db else len(trades_data),
                file_path=file_path,
                processing_time=processing_time,
                data_size_mb=self._calculate_trades_data_size(trades_data)
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"下载Tick数据失败: {e}")
            
            return DownloadResult(
                success=False,
                records_count=0,
                error_message=str(e),
                processing_time=processing_time
            )
    
    async def batch_download(self, requests: List[DownloadRequest]) -> List[DownloadResult]:
        """批量下载数据"""
        results = []
        
        # 按交易所分组以优化连接重用
        requests_by_exchange = {}
        for request in requests:
            if request.exchange not in requests_by_exchange:
                requests_by_exchange[request.exchange] = []
            requests_by_exchange[request.exchange].append(request)
        
        # 并发下载（限制并发数以避免超过API限制）
        semaphore = asyncio.Semaphore(5)  # 最多5个并发请求
        
        async def download_with_semaphore(request):
            async with semaphore:
                if request.data_type == 'kline':
                    return await self.download_kline_data(request)
                elif request.data_type == 'tick':
                    return await self.download_tick_data(request)
                else:
                    return DownloadResult(
                        success=False,
                        records_count=0,
                        error_message=f"不支持的数据类型: {request.data_type}"
                    )
        
        # 执行所有下载任务
        download_tasks = [download_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(DownloadResult(
                    success=False,
                    records_count=0,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def get_available_symbols(self, exchange: str) -> List[str]:
        """获取交易所可用的交易对"""
        try:
            client = await self._get_exchange_client(exchange)
            markets = await client.load_markets()
            return list(markets.keys())
        except Exception as e:
            logger.error(f"获取交易对列表失败: {e}")
            return []
    
    async def get_exchange_info(self, exchange: str) -> Dict[str, Any]:
        """获取交易所信息"""
        config = self.SUPPORTED_EXCHANGES.get(exchange, {})
        
        try:
            client = await self._get_exchange_client(exchange)
            markets = await client.load_markets()
            
            return {
                'exchange_id': exchange,
                'name': client.name if hasattr(client, 'name') else exchange,
                'supported_timeframes': config.get('timeframes', []),
                'has_ohlcv': config.get('has_ohlcv', False),
                'has_trades': config.get('has_trades', False),
                'rate_limit': config.get('rate_limit', 1000),
                'max_candles_per_request': config.get('max_candles', 1000),
                'total_symbols': len(markets),
                'status': 'active'
            }
        except Exception as e:
            logger.error(f"获取交易所信息失败: {e}")
            return {
                'exchange_id': exchange,
                'status': 'error',
                'error_message': str(e)
            }
    
    async def _get_exchange_client(self, exchange_id: str) -> ccxt_async.Exchange:
        """获取交易所客户端"""
        if exchange_id not in self.exchange_clients:
            if exchange_id not in self.SUPPORTED_EXCHANGES:
                raise ValueError(f"不支持的交易所: {exchange_id}")
            
            # 创建客户端
            exchange_class = getattr(ccxt_async, exchange_id.lower())
            config = self.SUPPORTED_EXCHANGES[exchange_id]
            
            client = exchange_class({
                'apiKey': '',  # 使用公开API
                'secret': '',
                'timeout': 30000,
                'sandbox': False,  # 使用生产环境获取真实数据
                'enableRateLimit': True,
                'rateLimit': 60000 // config.get('rate_limit', 10)  # 转换为毫秒间隔
            })
            
            self.exchange_clients[exchange_id] = client
        
        return self.exchange_clients[exchange_id]
    
    def _validate_kline_request(self, request: DownloadRequest) -> Optional[str]:
        """验证K线数据请求"""
        if request.exchange not in self.SUPPORTED_EXCHANGES:
            return f"不支持的交易所: {request.exchange}"
        
        if not request.timeframe:
            return "K线数据请求必须指定时间周期"
        
        exchange_config = self.SUPPORTED_EXCHANGES[request.exchange]
        if request.timeframe not in exchange_config.get('timeframes', []):
            return f"交易所 {request.exchange} 不支持时间周期 {request.timeframe}"
        
        if not exchange_config.get('has_ohlcv', False):
            return f"交易所 {request.exchange} 不支持K线数据"
        
        return None
    
    def _validate_tick_request(self, request: DownloadRequest) -> Optional[str]:
        """验证Tick数据请求"""
        if request.exchange not in self.SUPPORTED_EXCHANGES:
            return f"不支持的交易所: {request.exchange}"
        
        exchange_config = self.SUPPORTED_EXCHANGES[request.exchange]
        if not exchange_config.get('has_trades', False):
            return f"交易所 {request.exchange} 不支持交易数据"
        
        return None
    
    def _validate_ohlcv_data(self, ohlcv_data: List) -> DataValidationResult:
        """验证K线数据质量"""
        issues = []
        quality_score = 100.0
        duplicates_count = 0
        outliers_count = 0
        
        if not ohlcv_data:
            return DataValidationResult(
                is_valid=False,
                issues=["无数据"],
                quality_score=0.0,
                completeness=0.0,
                duplicates_count=0,
                outliers_count=0
            )
        
        # 检查数据完整性
        none_count = 0
        for candle in ohlcv_data:
            if len(candle) < 6 or None in candle[:6]:
                none_count += 1
        
        if none_count > 0:
            completeness = (len(ohlcv_data) - none_count) / len(ohlcv_data) * 100
            issues.append(f"缺失数据: {none_count} 条")
            quality_score -= min(none_count / len(ohlcv_data) * 50, 30)
        else:
            completeness = 100.0
        
        # 检查重复数据
        timestamps = [candle[0] for candle in ohlcv_data]
        unique_timestamps = set(timestamps)
        duplicates_count = len(timestamps) - len(unique_timestamps)
        
        if duplicates_count > 0:
            issues.append(f"重复数据: {duplicates_count} 条")
            quality_score -= min(duplicates_count / len(ohlcv_data) * 30, 20)
        
        # 检查价格异常值
        if len(ohlcv_data) > 1:
            prices = [candle[4] for candle in ohlcv_data if candle[4]]  # 收盘价
            if prices:
                median_price = np.median(prices)
                for price in prices:
                    if abs(price - median_price) > median_price * 0.5:  # 超过中位数50%
                        outliers_count += 1
                
                if outliers_count > 0:
                    issues.append(f"价格异常值: {outliers_count} 条")
                    quality_score -= min(outliers_count / len(prices) * 20, 15)
        
        is_valid = quality_score >= 70  # 质量分数低于70认为无效
        
        return DataValidationResult(
            is_valid=is_valid,
            issues=issues,
            quality_score=max(quality_score, 0.0),
            completeness=completeness,
            duplicates_count=duplicates_count,
            outliers_count=outliers_count
        )
    
    def _validate_trades_data(self, trades_data: List) -> DataValidationResult:
        """验证交易数据质量"""
        issues = []
        quality_score = 100.0
        duplicates_count = 0
        outliers_count = 0
        
        if not trades_data:
            return DataValidationResult(
                is_valid=False,
                issues=["无数据"],
                quality_score=0.0,
                completeness=0.0,
                duplicates_count=0,
                outliers_count=0
            )
        
        # 检查数据完整性
        incomplete_count = 0
        for trade in trades_data:
            required_fields = ['id', 'timestamp', 'price', 'amount', 'side']
            if not all(trade.get(field) for field in required_fields):
                incomplete_count += 1
        
        completeness = (len(trades_data) - incomplete_count) / len(trades_data) * 100
        
        if incomplete_count > 0:
            issues.append(f"不完整数据: {incomplete_count} 条")
            quality_score -= min(incomplete_count / len(trades_data) * 50, 30)
        
        # 检查重复交易ID
        trade_ids = [trade.get('id') for trade in trades_data if trade.get('id')]
        unique_ids = set(trade_ids)
        duplicates_count = len(trade_ids) - len(unique_ids)
        
        if duplicates_count > 0:
            issues.append(f"重复交易ID: {duplicates_count} 条")
            quality_score -= min(duplicates_count / len(trades_data) * 30, 20)
        
        # 检查价格异常值
        prices = [float(trade['price']) for trade in trades_data if trade.get('price')]
        if prices:
            median_price = np.median(prices)
            for price in prices:
                if abs(price - median_price) > median_price * 0.3:  # 超过中位数30%
                    outliers_count += 1
            
            if outliers_count > 0:
                issues.append(f"价格异常值: {outliers_count} 条")
                quality_score -= min(outliers_count / len(prices) * 20, 15)
        
        is_valid = quality_score >= 70
        
        return DataValidationResult(
            is_valid=is_valid,
            issues=issues,
            quality_score=max(quality_score, 0.0),
            completeness=completeness,
            duplicates_count=duplicates_count,
            outliers_count=outliers_count
        )
    
    async def _save_kline_to_db(
        self, 
        exchange: str, 
        symbol: str, 
        timeframe: str, 
        ohlcv_data: List
    ) -> int:
        """保存K线数据到数据库"""
        saved_count = 0
        
        async with AsyncSessionLocal() as db:
            for ohlcv in ohlcv_data:
                timestamp, open_price, high, low, close, volume = ohlcv
                
                # 检查数据是否已存在
                existing = await db.execute(
                    select(MarketData).where(
                        and_(
                            MarketData.exchange == exchange,
                            MarketData.symbol == symbol,
                            MarketData.timeframe == timeframe,
                            MarketData.timestamp == datetime.fromtimestamp(timestamp / 1000)
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    continue
                
                # 创建新记录
                market_data = MarketData(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    open_price=open_price,
                    high_price=high,
                    low_price=low,
                    close_price=close,
                    volume=volume,
                    timestamp=datetime.fromtimestamp(timestamp / 1000)
                )
                
                db.add(market_data)
                saved_count += 1
            
            await db.commit()
        
        return saved_count
    
    async def _save_tick_to_db(self, exchange: str, symbol: str, trades_data: List) -> int:
        """保存Tick数据到数据库"""
        saved_count = 0
        
        async with AsyncSessionLocal() as db:
            for trade in trades_data:
                # 检查数据是否已存在
                existing = await db.execute(
                    select(TickData).where(
                        and_(
                            TickData.exchange == exchange,
                            TickData.symbol == symbol,
                            TickData.trade_id == str(trade['id'])
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    continue
                
                # 创建新的tick数据记录
                tick_data = TickData(
                    exchange=exchange,
                    symbol=symbol,
                    price=float(trade['price']),
                    volume=float(trade['amount']),
                    side=trade['side'],
                    trade_id=str(trade['id']),
                    timestamp=int(trade['timestamp'] * 1000),  # 微秒级时间戳
                    data_source='rest_api',
                    is_validated=True
                )
                
                db.add(tick_data)
                saved_count += 1
            
            await db.commit()
        
        return saved_count
    
    async def _export_kline_data(self, request: DownloadRequest, ohlcv_data: List) -> str:
        """导出K线数据到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.exchange}_{request.symbol}_{request.timeframe}_kline_{timestamp}"
        
        if request.export_format == 'csv':
            file_path = self.export_directory / f"{filename}.csv"
            
            # 转换为DataFrame
            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 保存CSV文件
            df.to_csv(file_path, index=False)
            
        elif request.export_format == 'json':
            file_path = self.export_directory / f"{filename}.json"
            
            # 转换为JSON格式
            json_data = []
            for ohlcv in ohlcv_data:
                json_data.append({
                    'timestamp': ohlcv[0],
                    'datetime': datetime.fromtimestamp(ohlcv[0] / 1000).isoformat(),
                    'open': ohlcv[1],
                    'high': ohlcv[2],
                    'low': ohlcv[3],
                    'close': ohlcv[4],
                    'volume': ohlcv[5]
                })
            
            with open(file_path, 'w') as f:
                json.dump(json_data, f, indent=2)
        
        elif request.export_format == 'parquet':
            file_path = self.export_directory / f"{filename}.parquet"
            
            # 转换为DataFrame并保存为Parquet
            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.to_parquet(file_path, index=False)
        
        else:
            raise ValueError(f"不支持的导出格式: {request.export_format}")
        
        return str(file_path)
    
    async def _export_tick_data(self, request: DownloadRequest, trades_data: List) -> str:
        """导出Tick数据到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.exchange}_{request.symbol}_tick_{timestamp}"
        
        if request.export_format == 'csv':
            file_path = self.export_directory / f"{filename}.csv"
            
            # 转换为DataFrame
            df = pd.DataFrame(trades_data)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 保存CSV文件
            df.to_csv(file_path, index=False)
            
        elif request.export_format == 'json':
            file_path = self.export_directory / f"{filename}.json"
            
            with open(file_path, 'w') as f:
                json.dump(trades_data, f, indent=2, default=str)
        
        elif request.export_format == 'parquet':
            file_path = self.export_directory / f"{filename}.parquet"
            
            # 转换为DataFrame并保存为Parquet
            df = pd.DataFrame(trades_data)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.to_parquet(file_path, index=False)
        
        else:
            raise ValueError(f"不支持的导出格式: {request.export_format}")
        
        return str(file_path)
    
    def _calculate_data_size(self, ohlcv_data: List) -> float:
        """计算K线数据大小（MB）"""
        # 简单估算：每条记录约50字节
        return len(ohlcv_data) * 50 / (1024 * 1024)
    
    def _calculate_trades_data_size(self, trades_data: List) -> float:
        """计算交易数据大小（MB）"""
        # 简单估算：每条记录约100字节
        return len(trades_data) * 100 / (1024 * 1024)
    
    async def close(self):
        """关闭所有交易所连接"""
        for client in self.exchange_clients.values():
            if hasattr(client, 'close'):
                await client.close()
        
        self.exchange_clients.clear()


# 全局实例
data_download_service = DataDownloadService()