"""
OKX数据下载器
基于/root/Tradebot脚本设计的企业级OKX数据下载系统

功能特性：
1. Tick数据下载 - 基于OKX官方CDN的历史交易数据
2. K线数据下载 - 基于OKX REST API的多周期K线数据  
3. 智能任务调度 - 后台异步任务管理
4. 数据质量控制 - 自动去重、格式验证、缺失检测
5. 进度监控 - 实时下载进度和状态追踪
"""

import asyncio
import aiohttp
import aiofiles
import zipfile
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging
import gc
import psutil
import csv
import sys
from contextlib import asynccontextmanager

from app.database import AsyncSessionLocal
from app.services.okx_market_data_service import okx_market_service
from app.models.data_management import TickData
from app.models.data_collection import DataCollectionTask
from app.models.market_data import MarketData
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime as dt

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """系统资源监控器"""
    
    def __init__(self, max_memory_percent: float = 80.0, max_cpu_percent: float = 85.0):
        self.max_memory_percent = max_memory_percent
        self.max_cpu_percent = max_cpu_percent
        self.process = psutil.Process()
    
    def get_memory_usage(self) -> float:
        """获取内存使用率"""
        return psutil.virtual_memory().percent
    
    def get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        return psutil.cpu_percent(interval=1)
    
    def get_process_memory_mb(self) -> float:
        """获取当前进程内存使用（MB）"""
        return self.process.memory_info().rss / 1024 / 1024
    
    def is_resource_available(self) -> tuple[bool, str]:
        """检查资源是否可用"""
        memory_usage = self.get_memory_usage()
        cpu_usage = self.get_cpu_usage()
        
        if memory_usage > self.max_memory_percent:
            return False, f"内存使用率过高: {memory_usage:.1f}% > {self.max_memory_percent}%"
        
        if cpu_usage > self.max_cpu_percent:
            return False, f"CPU使用率过高: {cpu_usage:.1f}% > {self.max_cpu_percent}%"
        
        return True, "资源充足"
    
    async def wait_for_resources(self, max_wait_seconds: int = 300):
        """等待资源可用"""
        start_time = datetime.now()
        
        while True:
            available, message = self.is_resource_available()
            if available:
                return
            
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait_seconds:
                raise RuntimeError(f"等待资源超时: {message}")
            
            logger.warning(f"资源不足，等待中... {message}")
            await asyncio.sleep(5)  # 等待5秒后重新检查
    
    def force_cleanup(self):
        """强制清理内存"""
        gc.collect()
        logger.info(f"内存清理完成，当前进程内存: {self.get_process_memory_mb():.1f}MB")


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataType(Enum):
    """数据类型"""
    TICK = "tick"
    KLINE = "kline"


@dataclass
class DownloadTask:
    """下载任务"""
    task_id: str
    data_type: DataType
    exchange: str
    symbols: List[str]
    start_date: str
    end_date: str
    timeframes: List[str] = None  # K线专用
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error_message: str = ""
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    total_files: int = 0
    processed_files: int = 0
    downloaded_records: int = 0


class OKXDataDownloader:
    """OKX数据下载器 - 优化版本，支持资源监控和内存管理"""
    
    def __init__(self):
        self.base_data_dir = Path("/root/trademe/backend/trading-service/data")
        self.okx_tick_dir = self.base_data_dir / "okx_tick_data"
        self.okx_kline_dir = self.base_data_dir / "okx_kline_data"
        self.temp_dir = self.base_data_dir / "temp"
        
        # 创建目录
        for dir_path in [self.okx_tick_dir, self.okx_kline_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 任务管理
        self.active_tasks: Dict[str, DownloadTask] = {}
        
        # 资源监控器 - 新增
        self.resource_monitor = ResourceMonitor(max_memory_percent=75.0, max_cpu_percent=80.0)
        
        # 优化配置
        self.max_concurrent_downloads = 1  # 降低并发数，避免资源过载
        self.chunk_size = 500  # CSV处理分块大小
        self.batch_size = 50  # 减少批量插入大小，降低内存压力
        self.max_files_per_task = 10  # 限制单个任务最大文件数
        self.download_timeout = 30  # 下载超时时间（秒）
        self.retry_attempts = 2  # 重试次数
        
        # OKX配置 - 基于正确的链接格式
        self.okx_tick_base_url = "https://www.okx.com/cdn/okex/traderecords/trades/daily"
        
        # 支持的交易对 - 基于现有脚本配置
        self.supported_tick_symbols = [
            'BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'SOL', 'BSV', 'TRB', 'AIDOGE', 'STARL',
            '1INCH', 'AAVE', 'ADA', 'AGLD', 'ALGO', 'ALPHA', 'ANT', 'APE', 'API3', 'APT',
            'AR', 'ARB', 'ATOM', 'AVAX', 'AXS', 'BADGER', 'BAL', 'BAND', 'BAT', 'BICO',
            'BIGTIME', 'BLUR', 'BNB', 'BNT', 'CELO', 'CEL', 'CETUS', 'CFX', 'CHZ', 'COMP',
            'CORE', 'CRO', 'CRV'
        ]
        
        self.supported_kline_symbols = [
            # 现货交易对
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT',
            'LINK/USDT', 'MATIC/USDT', 'AVAX/USDT', 'XRP/USDT', 'DOGE/USDT',
            # 合约交易对 (永续合约)
            'BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 'ADA-USDT-SWAP', 
            'DOT-USDT-SWAP', 'LINK-USDT-SWAP', 'MATIC-USDT-SWAP', 'AVAX-USDT-SWAP',
            'XRP-USDT-SWAP', 'DOGE-USDT-SWAP', 'LTC-USDT-SWAP', 'BCH-USDT-SWAP'
        ]
        
        self.supported_timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w']
        
        logger.info("🚀 OKX数据下载器初始化完成")
    
    async def create_tick_download_task(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        task_id: Optional[str] = None
    ) -> DownloadTask:
        """创建Tick数据下载任务 - 改进版本，支持任务持久化"""
        if not task_id:
            task_id = f"tick_{int(datetime.now().timestamp())}"
        
        # 验证交易对
        invalid_symbols = [s for s in symbols if s not in self.supported_tick_symbols]
        if invalid_symbols:
            raise ValueError(f"不支持的交易对: {invalid_symbols}")
        
        # 计算日期范围
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        date_range = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_range.append(current_dt.strftime('%Y%m%d'))
            current_dt += timedelta(days=1)
        
        total_files = len(symbols) * len(date_range)
        
        # 检查文件数量，超过限制则分割任务
        if total_files > self.max_files_per_task:
            # 限制日期范围到最近的天数
            max_days = self.max_files_per_task // len(symbols)
            if max_days < 1:
                max_days = 1
            
            # 重新计算截止日期
            limited_end_dt = start_dt + timedelta(days=max_days-1)
            if limited_end_dt > end_dt:
                limited_end_dt = end_dt
            
            # 更新日期范围和文件总数
            date_range = []
            current_dt = start_dt
            while current_dt <= limited_end_dt:
                date_range.append(current_dt.strftime('%Y%m%d'))
                current_dt += timedelta(days=1)
            
            total_files = len(symbols) * len(date_range)
            
            logger.info(f"⚠️ 任务文件数量过多，限制为 {total_files} 个文件 ({start_date}-{limited_end_dt.strftime('%Y%m%d')})")
        
        task = DownloadTask(
            task_id=task_id,
            data_type=DataType.TICK,
            exchange="okx",
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            total_files=total_files
        )
        
        self.active_tasks[task_id] = task
        
        # 保存任务到数据库
        await self._save_task_to_database(task)
        
        logger.info(f"📝 创建Tick数据下载任务: {task_id}, 交易对: {len(symbols)}, 日期: {start_date}-{end_date}")
        
        return task
    
    async def create_kline_download_task(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: str,
        end_date: str,
        task_id: Optional[str] = None
    ) -> DownloadTask:
        """创建K线数据下载任务 - 改进版本，支持任务持久化"""
        if not task_id:
            task_id = f"kline_{int(datetime.now().timestamp())}"
        
        # 验证交易对
        invalid_symbols = [s for s in symbols if s not in self.supported_kline_symbols]
        if invalid_symbols:
            raise ValueError(f"不支持的交易对: {invalid_symbols}")
        
        # 验证时间周期
        invalid_timeframes = [tf for tf in timeframes if tf not in self.supported_timeframes]
        if invalid_timeframes:
            raise ValueError(f"不支持的时间周期: {invalid_timeframes}")
        
        total_files = len(symbols) * len(timeframes)
        
        task = DownloadTask(
            task_id=task_id,
            data_type=DataType.KLINE,
            exchange="okx",
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            total_files=total_files
        )
        
        self.active_tasks[task_id] = task
        
        # 保存任务到数据库
        await self._save_task_to_database(task)
        
        logger.info(f"📝 创建K线数据下载任务: {task_id}, 交易对: {len(symbols)}, 时间周期: {timeframes}")
        
        return task
    
    async def execute_tick_download_task(self, task_id: str):
        """执行Tick数据下载任务 - 改进版本"""
        if task_id not in self.active_tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        task = self.active_tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        # 更新数据库中的任务状态
        await self._update_task_in_database(task)
        
        try:
            logger.info(f"🚀 开始执行Tick下载任务: {task_id}")
            
            # 计算日期范围
            start_dt = datetime.strptime(task.start_date, '%Y%m%d')
            end_dt = datetime.strptime(task.end_date, '%Y%m%d')
            
            total_downloaded = 0
            
            # 按日期循环下载
            current_dt = start_dt
            while current_dt <= end_dt:
                date_str = current_dt.strftime('%Y%m%d')
                formatted_date = current_dt.strftime('%Y-%m-%d')
                
                logger.info(f"📅 处理日期: {formatted_date}")
                
                # 顺序下载，避免资源过载 - 优化：改为串行处理
                results = []
                for symbol in task.symbols:
                    try:
                        # 资源检查：等待资源可用
                        await self.resource_monitor.wait_for_resources()
                        
                        logger.info(f"🔍 开始下载: {symbol} (内存: {self.resource_monitor.get_process_memory_mb():.1f}MB)")
                        
                        # 串行下载，避免并发过载
                        result = await self._download_tick_file(symbol, date_str, formatted_date, task)
                        results.append(result)
                        
                        # 强制内存清理
                        self.resource_monitor.force_cleanup()
                        
                        # 适当延迟，让系统喘息
                        await asyncio.sleep(1)  # 减少延迟时间
                        
                    except Exception as e:
                        logger.error(f"❌ 下载失败 {symbol}: {e}")
                        results.append(e)
                
                # 统计结果
                day_downloaded = 0
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"❌ 下载出错: {result}")
                        task.processed_files += 1  # 计算失败的文件
                    else:
                        day_downloaded += result
                        total_downloaded += result
                        task.processed_files += 1
                    
                    task.progress = (task.processed_files / task.total_files) * 100
                
                logger.info(f"📊 {formatted_date} 完成，当日下载: {day_downloaded} 条记录 (总计: {total_downloaded}), 进度: {task.progress:.1f}%")
                
                # 更新任务状态到数据库
                task.downloaded_records = total_downloaded
                await self._update_task_in_database(task)
                
                current_dt += timedelta(days=1)
                
                # 避免请求过于频繁
                await asyncio.sleep(2)
            
            task.downloaded_records = total_downloaded
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # 最终更新状态
            await self._update_task_in_database(task)
            
            logger.info(f"✅ Tick下载任务完成: {task_id}, 下载记录数: {total_downloaded}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            await self._update_task_in_database(task)
            logger.error(f"❌ Tick下载任务失败: {task_id}, 错误: {e}")
    
    async def _download_tick_file(self, symbol: str, date_str: str, formatted_date: str, task: DownloadTask) -> int:
        """下载单个Tick文件"""
        # 构造OKX下载URL - 基于正确的链接格式
        # 现货格式: BTC-USDT-trades-2025-08-29.zip
        # 永续合约格式: BTC-USDT-SWAP-trades-2025-08-29.zip  
        # 优先尝试永续合约数据，因为现在OKX主要提供永续合约的tick数据
        zip_filename = f"{symbol}-USDT-SWAP-trades-{formatted_date}.zip"  # 永续合约格式
        download_url = f"{self.okx_tick_base_url}/{date_str}/{zip_filename}"
        
        temp_zip_path = self.temp_dir / zip_filename
        csv_filename = f"{symbol}-USDT-SWAP-trades-{formatted_date}.csv"
        temp_csv_path = self.temp_dir / csv_filename
        
        try:
            # 注意：现在我们不再保存CSV文件到最终位置，直接处理临时文件
            # 这样可以避免重复存储，数据已经在数据库中了
            
            # 下载ZIP文件
            async with aiohttp.ClientSession() as session:
                logger.info(f"📥 下载: {download_url}")
                
                async with session.get(download_url, timeout=300) as response:
                    if response.status == 200:
                        # 保存ZIP文件
                        async with aiofiles.open(temp_zip_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        
                        # 解压文件
                        try:
                            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                                zip_ref.extractall(self.temp_dir)
                        except zipfile.BadZipFile:
                            logger.error(f"❌ 无效的ZIP文件: {temp_zip_path}")
                            return 0
                        
                        # 处理CSV数据 - 基于现有脚本的数据处理逻辑
                        processed_records = await self._process_tick_csv(temp_csv_path, symbol)
                        
                        # 清理临时文件
                        if temp_zip_path.exists():
                            temp_zip_path.unlink()
                        if temp_csv_path.exists():
                            temp_csv_path.unlink()
                        
                        logger.info(f"✅ {symbol} {formatted_date} 处理完成，记录数: {processed_records}")
                        return processed_records
                    
                    elif response.status == 404:
                        logger.warning(f"⚠️ 文件不存在: {download_url}")
                        return 0
                    else:
                        logger.error(f"❌ 下载失败: {download_url}, 状态码: {response.status}")
                        return 0
            
        except Exception as e:
            logger.error(f"❌ 下载处理失败: {zip_filename}, 错误: {e}")
            # 清理可能的临时文件
            for temp_file in [temp_zip_path, temp_csv_path]:
                if temp_file.exists():
                    temp_file.unlink()
            return 0
    
    async def _process_tick_csv(self, csv_path: Path, symbol: str) -> int:
        """处理Tick CSV文件并插入数据库 - 优化版本，使用分块处理避免内存过载"""
        try:
            if not csv_path.exists():
                return 0
            
            logger.info(f"📊 开始处理tick数据文件: {csv_path} (文件大小: {csv_path.stat().st_size / 1024 / 1024:.1f}MB)")
            
            # 使用原生CSV读取器替代pandas，避免整个文件加载到内存
            inserted_count = 0
            
            async with AsyncSessionLocal() as db:
                try:
                    # 分块处理CSV文件，避免内存过载
                    with open(csv_path, 'r', encoding='gbk', errors='ignore') as csvfile:
                        # 尝试检测文件编码
                        try:
                            reader = csv.DictReader(csvfile)
                            headers = reader.fieldnames
                        except UnicodeDecodeError:
                            csvfile.close()
                            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as csvfile:
                                reader = csv.DictReader(csvfile)
                                headers = reader.fieldnames
                    
                    # 重新打开文件进行分块处理
                    with open(csv_path, 'r', encoding='gbk', errors='ignore') as csvfile:
                        reader = csv.DictReader(csvfile)
                        
                        tick_records = []
                        processed_rows = 0
                        
                        for row in reader:
                            try:
                                # 每处理一定数量检查资源
                                if processed_rows % 1000 == 0:
                                    available, _ = self.resource_monitor.is_resource_available()
                                    if not available:
                                        logger.warning("⚠️ 资源不足，暂停处理...")
                                        await asyncio.sleep(5)
                                
                                # 创建TickData记录
                                tick_data = TickData(
                                    exchange="okx",
                                    symbol=f"{symbol}/USDT",
                                    price=float(row.get('price/价格', 0) or row.get('price', 0)),
                                    volume=float(row.get('size/数量', 0) or row.get('size', 0)),
                                    side=(row.get('side/交易方向', '') or row.get('side', '')).lower(),
                                    trade_id=str(row.get('trade_id/撮合id', '') or row.get('trade_id', '')),
                                    timestamp=int(row.get('created_time/成交时间', 0) or row.get('timestamp', 0)),
                                    data_source="okx_historical",
                                    created_at=datetime.now()
                                )
                                tick_records.append(tick_data)
                                processed_rows += 1
                                
                                # 分批插入数据库，避免单次事务过大
                                if len(tick_records) >= self.batch_size:
                                    # 去重检查：查询数据库中已存在的记录
                                    duplicates_removed = await self._remove_duplicates_tick(db, tick_records)
                                    if duplicates_removed:
                                        db.add_all(duplicates_removed)
                                        await db.commit()
                                        inserted_count += len(duplicates_removed)
                                        skipped_count = len(tick_records) - len(duplicates_removed)
                                        if skipped_count > 0:
                                            logger.info(f"⚠️ 跳过重复记录: {skipped_count} 条")
                                    
                                    logger.debug(f"🔄 已插入 {inserted_count} 条记录 (内存: {self.resource_monitor.get_process_memory_mb():.1f}MB)")
                                    
                                    tick_records.clear()  # 清空列表释放内存
                                    
                                    # 强制垃圾回收
                                    if inserted_count % (self.batch_size * 10) == 0:
                                        gc.collect()
                                
                            except Exception as row_error:
                                logger.warning(f"⚠️ 跳过无效行 {processed_rows}: {row_error}")
                                continue
                        
                        # 处理剩余的记录
                        if tick_records:
                            duplicates_removed = await self._remove_duplicates_tick(db, tick_records)
                            if duplicates_removed:
                                db.add_all(duplicates_removed)
                                await db.commit()
                                inserted_count += len(duplicates_removed)
                                skipped_count = len(tick_records) - len(duplicates_removed)
                                if skipped_count > 0:
                                    logger.info(f"⚠️ 最终批次跳过重复记录: {skipped_count} 条")
                    
                    logger.info(f"✅ 成功插入 {inserted_count} 条tick数据到数据库")
                    
                    # 数据已成功插入数据库，删除CSV文件以节省存储空间
                    if csv_path.exists():
                        csv_path.unlink()
                        logger.info(f"🗑️ 已删除处理完成的CSV文件: {csv_path.name}")
                    
                    return inserted_count
                    
                except Exception as db_error:
                    await db.rollback()
                    logger.error(f"❌ 数据库操作失败: {db_error}")
                    # 数据库操作失败，删除CSV文件，避免占用存储空间
                    if csv_path.exists():
                        csv_path.unlink()
                        logger.warning(f"⚠️ 数据库操作失败，已删除CSV文件: {csv_path.name}")
                    return 0
            
        except Exception as e:
            logger.error(f"❌ 处理tick CSV失败: {csv_path}, 错误: {e}")
            return 0
    
    async def execute_kline_download_task(self, task_id: str):
        """执行K线数据下载任务 - 改进版本"""
        if task_id not in self.active_tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        task = self.active_tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        # 更新数据库中的任务状态
        await self._update_task_in_database(task)
        
        try:
            logger.info(f"🚀 开始执行K线下载任务: {task_id}")
            
            start_dt = datetime.strptime(task.start_date, '%Y%m%d')
            end_dt = datetime.strptime(task.end_date, '%Y%m%d')
            
            total_downloaded = 0
            
            # 按交易对和时间周期循环下载
            for symbol in task.symbols:
                for timeframe in task.timeframes:
                    try:
                        logger.info(f"📈 开始下载: {symbol} {timeframe}")
                        
                        # 使用改进的K线下载方法
                        records = await self._download_kline_data(
                            symbol, timeframe, start_dt, end_dt
                        )
                        
                        total_downloaded += records
                        task.processed_files += 1
                        task.progress = (task.processed_files / task.total_files) * 100
                        
                        logger.info(f"✅ {symbol} {timeframe} 下载完成，记录数: {records}, 进度: {task.progress:.1f}%")
                        
                        # 更新任务状态
                        task.downloaded_records = total_downloaded
                        await self._update_task_in_database(task)
                        
                        # 避免API限流
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"❌ {symbol} {timeframe} 下载失败: {e}")
                        task.processed_files += 1
                        task.progress = (task.processed_files / task.total_files) * 100
                        await self._update_task_in_database(task)
            
            task.downloaded_records = total_downloaded
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # 最终更新状态
            await self._update_task_in_database(task)
            
            logger.info(f"✅ K线下载任务完成: {task_id}, 下载记录数: {total_downloaded}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            await self._update_task_in_database(task)
            logger.error(f"❌ K线下载任务失败: {task_id}, 错误: {e}")
    
    async def _download_kline_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_dt: datetime, 
        end_dt: datetime
    ) -> int:
        """下载K线数据 - 修复版本，确保数据实际插入数据库"""
        try:
            logger.info(f"🚀 开始下载K线数据: {symbol} {timeframe} ({start_dt.date()} 到 {end_dt.date()})")
            
            total_records = 0
            saved_records = 0
            current_end = int(end_dt.timestamp() * 1000)
            start_timestamp = int(start_dt.timestamp() * 1000)
            
            async with AsyncSessionLocal() as db:
                # 计算合适的每次请求数量 - 基于时间框架
                # 1分钟: 300条约等于5小时, 1小时: 300条约等于12.5天
                request_limit = 300  # OKX API单次最大限制
                
                # 分批请求历史数据 - 使用时间范围分页
                request_count = 0
                while current_end > start_timestamp and request_count < 50:  # 减少最大请求次数，依靠时间范围控制
                    try:
                        # 🆕 使用时间范围参数获取K线数据
                        kline_data = await okx_market_service.get_klines(
                            symbol=symbol,
                            timeframe=timeframe,
                            limit=request_limit,
                            start_time=start_timestamp,  # 🆕 开始时间
                            end_time=current_end,        # 🆕 结束时间
                            use_cache=False
                        )
                        
                        if not kline_data.get('klines') or len(kline_data['klines']) == 0:
                            logger.warning(f"⚠️ 没有更多K线数据: {symbol} {timeframe}")
                            break
                        
                        new_records = len(kline_data['klines'])
                        total_records += new_records
                        request_count += 1
                        
                        # 🆕 将K线数据转换为MarketData对象并保存到数据库
                        market_data_records = []
                        for kline in kline_data['klines']:
                            # kline格式: [timestamp, open, high, low, close, volume, ...]
                            try:
                                timestamp_ms = int(kline[0])
                                dt_obj = dt.fromtimestamp(timestamp_ms / 1000)
                                
                                product_type = 'futures' if symbol.upper().endswith('-USDT-SWAP') or symbol.upper().endswith('-SWAP') else 'spot'
                                market_record = MarketData(
                                    exchange="okx",
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    product_type=product_type,
                                    open_price=float(kline[1]),
                                    high_price=float(kline[2]), 
                                    low_price=float(kline[3]),
                                    close_price=float(kline[4]),
                                    volume=float(kline[5]),
                                    timestamp=dt_obj
                                )
                                market_data_records.append(market_record)
                            except (ValueError, IndexError) as parse_error:
                                logger.warning(f"⚠️ 解析K线数据失败: {kline}, 错误: {parse_error}")
                                continue
                        
                        # 去重逻辑：检查现有记录避免重复
                        if market_data_records:
                            # 检查重复记录
                            existing_timestamps = []
                            for record in market_data_records:
                                existing_query = await db.execute(
                                    select(MarketData.timestamp).where(
                                        and_(
                                            MarketData.exchange == "okx",
                                            MarketData.symbol == symbol,
                                            MarketData.timeframe == timeframe,
                                            MarketData.timestamp == record.timestamp
                                        )
                                    )
                                )
                                if existing_query.scalar_one_or_none():
                                    existing_timestamps.append(record.timestamp)
                            
                            # 过滤掉重复记录
                            unique_records = [record for record in market_data_records 
                                            if record.timestamp not in existing_timestamps]
                            
                            if unique_records:
                                db.add_all(unique_records)
                                await db.commit()
                                saved_records += len(unique_records)
                                logger.info(f"💾 已保存 {len(unique_records)} 条K线数据到数据库 (跳过重复: {len(market_data_records) - len(unique_records)} 条)")
                            else:
                                logger.info(f"⚠️ 本批次所有 {len(market_data_records)} 条记录都是重复数据")
                        
                        logger.info(f"📊 获取 {new_records} 条K线数据 (总计: {total_records}, 已保存: {saved_records}, 请求次数: {request_count})")
                        
                        # 更新时间范围用于下一次请求
                        if kline_data['klines']:
                            earliest_timestamp = kline_data['klines'][0][0]  # 最早的时间戳
                            latest_timestamp = kline_data['klines'][-1][0]   # 最新的时间戳
                            
                            # 检查时间边界
                            if earliest_timestamp <= start_timestamp:
                                logger.info(f"✅ 已到达起始时间: {datetime.fromtimestamp(start_timestamp/1000)} (获得: {datetime.fromtimestamp(earliest_timestamp/1000)})")
                                break
                            
                            # 下次请求更早的数据 - 从最早的时间戳之前开始
                            current_end = earliest_timestamp - 1
                            logger.debug(f"🔄 下一次请求时间范围: {datetime.fromtimestamp(start_timestamp/1000)} 到 {datetime.fromtimestamp(current_end/1000)}")
                        else:
                            logger.warning(f"⚠️ 没有K线数据返回")
                            break
                        
                        # 如果获取的记录少于300条，说明已经到达历史数据边界
                        if new_records < 300:
                            logger.info(f"✅ 已到达历史数据边界，记录数: {new_records}")
                            break
                        
                        # 避免API限流
                        await asyncio.sleep(0.3)
                        
                    except Exception as request_error:
                        logger.error(f"❌ 单次请求失败: {request_error}")
                        await asyncio.sleep(1)  # 出错时等待更久
                        request_count += 1
                        continue
            
            logger.info(f"✅ K线下载完成: {symbol} {timeframe}, 总下载记录数: {total_records}, 实际保存到数据库: {saved_records}, 请求次数: {request_count}")
            return saved_records  # 返回实际保存的记录数
            
        except Exception as e:
            logger.error(f"❌ 下载K线数据失败: {symbol} {timeframe}, 错误: {e}")
            return 0
    
    async def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务状态"""
        return self.active_tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                logger.info(f"⏹️ 任务已取消: {task_id}")
                return True
        return False
    
    async def list_active_tasks(self) -> List[DownloadTask]:
        """列出所有活跃任务"""
        return list(self.active_tasks.values())
    
    async def clean_completed_tasks(self, days_old: int = 7):
        """清理完成的任务"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        tasks_to_remove = []
        
        for task_id, task in self.active_tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 
                and task.completed_at 
                and task.completed_at < cutoff_date):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.active_tasks[task_id]
        
        logger.info(f"🧹 清理完成任务: {len(tasks_to_remove)} 个")
    
    async def _save_task_to_database(self, task: DownloadTask):
        """保存任务到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                # 检查任务是否已存在
                existing_task = await db.execute(
                    select(DataCollectionTask).where(
                        DataCollectionTask.task_name == task.task_id
                    )
                )
                
                if existing_task.scalar_one_or_none():
                    logger.warning(f"⚠️ 任务已存在在数据库中: {task.task_id}")
                    return
                
                # 创建新任务记录
                db_task = DataCollectionTask(
                    task_name=task.task_id,
                    exchange=task.exchange,
                    data_type=task.data_type.value,
                    symbols=','.join(task.symbols),
                    timeframes=','.join(task.timeframes) if task.timeframes else None,
                    status=task.status.value,
                    schedule_type="manual",
                    success_count=0,
                    error_count=0,
                    total_records=0,
                    created_at=task.created_at,
                    config=f"{{\"start_date\": \"{task.start_date}\", \"end_date\": \"{task.end_date}\", \"total_files\": {task.total_files}}}"
                )
                
                db.add(db_task)
                await db.commit()
                logger.info(f"💾 任务已保存到数据库: {task.task_id}")
                
        except Exception as e:
            logger.error(f"❌ 保存任务到数据库失败: {e}")
    
    async def _update_task_in_database(self, task: DownloadTask):
        """更新数据库中的任务状态"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(DataCollectionTask).where(
                        DataCollectionTask.task_name == task.task_id
                    )
                )
                
                db_task = result.scalar_one_or_none()
                if db_task:
                    db_task.status = task.status.value
                    db_task.success_count = task.processed_files
                    db_task.total_records = task.downloaded_records
                    db_task.last_run_at = task.started_at
                    if task.completed_at:
                        db_task.next_run_at = task.completed_at
                    if task.error_message:
                        db_task.last_error_message = task.error_message
                        db_task.last_error_at = datetime.now()
                    
                    await db.commit()
                    logger.debug(f"🔄 任务状态已更新: {task.task_id} -> {task.status.value}")
                
        except Exception as e:
            logger.error(f"❌ 更新任务状态失败: {e}")
    
    async def get_download_statistics(self) -> Dict[str, Any]:
        """获取下载统计信息"""
        stats = {
            "total_tasks": len(self.active_tasks),
            "running_tasks": len([t for t in self.active_tasks.values() if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in self.active_tasks.values() if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.active_tasks.values() if t.status == TaskStatus.FAILED]),
            "total_downloaded_records": sum(t.downloaded_records for t in self.active_tasks.values() if t.downloaded_records),
            "tick_data_db_records": "check database for current count",
            "supported_tick_symbols": len(self.supported_tick_symbols),
            "supported_kline_symbols": len(self.supported_kline_symbols)
        }
        
        # 从数据库获取更准确的统计
        try:
            async with AsyncSessionLocal() as db:
                # 查询数据库中的任务
                db_tasks_result = await db.execute(select(DataCollectionTask))
                db_tasks = db_tasks_result.scalars().all()
                
                stats["database_tasks"] = len(db_tasks)
                stats["database_completed"] = len([t for t in db_tasks if t.status == "completed"])
                stats["database_failed"] = len([t for t in db_tasks if t.status == "failed"])
                
                # 查询tick数据总数
                from app.models.data_management import TickData
                tick_count_result = await db.execute(select(TickData))
                tick_count = len(tick_count_result.scalars().all())
                stats["tick_records_in_db"] = tick_count
                
        except Exception as e:
            logger.warning(f"⚠️ 获取数据库统计失败: {e}")
        
        return stats

    async def _remove_duplicates_tick(self, db: AsyncSession, tick_records: List[TickData]) -> List[TickData]:
        """移除重复的Tick数据记录"""
        if not tick_records:
            return []
        
        try:
            # 构建查询条件：使用symbol, timestamp, trade_id作为唯一性判断
            unique_keys = [(record.symbol, record.timestamp, record.trade_id) for record in tick_records]
            
            # 查询数据库中已存在的记录
            existing_query = select(TickData.symbol, TickData.timestamp, TickData.trade_id).where(
                or_(*[
                    and_(
                        TickData.symbol == symbol,
                        TickData.timestamp == timestamp,
                        TickData.trade_id == trade_id
                    ) for symbol, timestamp, trade_id in unique_keys
                ])
            )
            
            result = await db.execute(existing_query)
            existing_keys = set(result.fetchall())
            
            # 过滤掉重复记录
            unique_records = []
            for record in tick_records:
                key = (record.symbol, record.timestamp, record.trade_id)
                if key not in existing_keys:
                    unique_records.append(record)
            
            return unique_records
            
        except Exception as e:
            logger.error(f"❌ 去重检查失败: {e}")
            return tick_records  # 如果去重失败，返回原记录
    
    async def _remove_duplicates_kline(self, db: AsyncSession, market_records: List) -> List:
        """移除重复的K线数据记录"""
        if not market_records:
            return []
        
        try:
            from app.models.market_data import MarketData
            
            # 构建查询条件：使用exchange, symbol, timeframe, timestamp作为唯一性判断
            unique_keys = [(record.exchange, record.symbol, record.timeframe, record.timestamp) 
                          for record in market_records if hasattr(record, 'exchange')]
            
            if not unique_keys:
                return market_records
            
            # 查询数据库中已存在的记录
            existing_query = select(MarketData.exchange, MarketData.symbol, MarketData.timeframe, MarketData.timestamp).where(
                or_(*[
                    and_(
                        MarketData.exchange == exchange,
                        MarketData.symbol == symbol,
                        MarketData.timeframe == timeframe,
                        MarketData.timestamp == timestamp
                    ) for exchange, symbol, timeframe, timestamp in unique_keys
                ])
            )
            
            result = await db.execute(existing_query)
            existing_keys = set(result.fetchall())
            
            # 过滤掉重复记录
            unique_records = []
            for record in market_records:
                if hasattr(record, 'exchange'):
                    key = (record.exchange, record.symbol, record.timeframe, record.timestamp)
                    if key not in existing_keys:
                        unique_records.append(record)
                else:
                    unique_records.append(record)
            
            return unique_records
            
        except Exception as e:
            logger.error(f"❌ K线去重检查失败: {e}")
            return market_records  # 如果去重失败，返回原记录




# 全局实例
okx_data_downloader = OKXDataDownloader()
