"""
OKX数据下载器 - 增强版本
基于现有问题的系统性优化，包含：
1. 精确的任务状态跟踪
2. 数据完整性验证
3. 智能重试机制
4. 详细的错误报告
5. 分时间段下载策略
"""

import asyncio
import aiohttp
import aiofiles
import zipfile
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import logging
import gc
import psutil
import csv
import sys
import json
from contextlib import asynccontextmanager

from app.database import AsyncSessionLocal
from app.services.okx_market_data_service import okx_market_service
from app.models.data_management import TickData
from app.models.data_collection import DataCollectionTask
from app.models.market_data import MarketData
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime as dt

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """增强的任务状态"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"  # 新增：部分成功
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataType(Enum):
    """数据类型"""
    TICK = "tick"
    KLINE = "kline"


@dataclass
class SubTaskProgress:
    """子任务进度跟踪"""
    symbol: str
    timeframe: str = ""
    total_expected_records: int = 0
    actual_records: int = 0
    status: TaskStatus = TaskStatus.PENDING
    error_message: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    data_quality_score: float = 0.0  # 数据质量评分


@dataclass 
class EnhancedDownloadTask:
    """增强的下载任务"""
    task_id: str
    data_type: DataType
    exchange: str
    symbols: List[str]
    start_date: str
    end_date: str
    timeframes: List[str] = None
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error_message: str = ""
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    total_files: int = 0
    processed_files: int = 0
    downloaded_records: int = 0
    expected_records: int = 0  # 新增：预期记录数
    
    # 新增：详细的子任务跟踪
    subtasks: List[SubTaskProgress] = field(default_factory=list)
    failed_subtasks: List[SubTaskProgress] = field(default_factory=list)
    quality_issues: List[str] = field(default_factory=list)
    
    # 新增：性能指标
    average_download_speed: float = 0.0  # records/second
    peak_memory_usage: float = 0.0  # MB
    total_api_requests: int = 0
    failed_api_requests: int = 0


class DataQualityChecker:
    """数据质量检查器"""
    
    @staticmethod
    async def check_kline_data_quality(
        db: AsyncSession, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Tuple[float, List[str]]:
        """检查K线数据质量"""
        issues = []
        quality_score = 100.0
        
        try:
            # 1. 检查数据完整性 - 计算预期记录数
            expected_records = DataQualityChecker._calculate_expected_kline_records(
                timeframe, start_date, end_date
            )
            
            # 查询实际记录数
            result = await db.execute(
                select(func.count(MarketData.id)).where(
                    and_(
                        MarketData.exchange == "okx",
                        MarketData.symbol == symbol,
                        MarketData.timeframe == timeframe,
                        MarketData.timestamp >= start_date,
                        MarketData.timestamp <= end_date
                    )
                )
            )
            actual_records = result.scalar() or 0
            
            # 计算完整性得分
            if expected_records > 0:
                completeness = min(actual_records / expected_records, 1.0)
                quality_score *= completeness
                
                if completeness < 0.95:
                    issues.append(f"数据不完整: 预期 {expected_records} 条，实际 {actual_records} 条 (完整度: {completeness:.1%})")
            
            # 2. 检查数据连续性 - 查找时间间隙
            gaps_result = await db.execute(
                text("""
                SELECT COUNT(*) as gap_count FROM (
                    SELECT 
                        timestamp,
                        LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp
                    FROM market_data 
                    WHERE exchange = :exchange AND symbol = :symbol AND timeframe = :timeframe
                        AND timestamp BETWEEN :start_date AND :end_date
                ) t
                WHERE JULIANDAY(timestamp) - JULIANDAY(prev_timestamp) > :expected_interval
                """),
                {
                    "exchange": "okx",
                    "symbol": symbol, 
                    "timeframe": timeframe,
                    "start_date": start_date,
                    "end_date": end_date,
                    "expected_interval": DataQualityChecker._get_timeframe_days(timeframe) * 2  # 允许2倍的间隔容差
                }
            )
            gap_count = gaps_result.scalar() or 0
            
            if gap_count > 0:
                quality_score *= max(0.7, 1.0 - (gap_count * 0.1))
                issues.append(f"发现 {gap_count} 个时间间隙")
            
            # 3. 检查价格数据合理性
            price_check_result = await db.execute(
                select(
                    func.count().filter(MarketData.open_price <= 0).label('invalid_price_count'),
                    func.count().filter(MarketData.high_price < MarketData.low_price).label('invalid_range_count')
                ).where(
                    and_(
                        MarketData.exchange == "okx",
                        MarketData.symbol == symbol,
                        MarketData.timeframe == timeframe,
                        MarketData.timestamp >= start_date,
                        MarketData.timestamp <= end_date
                    )
                )
            )
            
            price_issues = price_check_result.first()
            if price_issues.invalid_price_count > 0:
                quality_score *= 0.8
                issues.append(f"发现 {price_issues.invalid_price_count} 条无效价格记录")
                
            if price_issues.invalid_range_count > 0:
                quality_score *= 0.9
                issues.append(f"发现 {price_issues.invalid_range_count} 条价格范围异常记录")
            
            return quality_score, issues
            
        except Exception as e:
            logger.error(f"数据质量检查失败: {e}")
            return 50.0, [f"质量检查异常: {str(e)}"]
    
    @staticmethod
    def _calculate_expected_kline_records(timeframe: str, start_date: datetime, end_date: datetime) -> int:
        """计算预期的K线记录数"""
        total_days = (end_date - start_date).days + 1
        
        timeframe_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240,
            '1d': 1440, '1w': 10080
        }
        
        if timeframe not in timeframe_minutes:
            return 0
        
        minutes_per_record = timeframe_minutes[timeframe]
        records_per_day = 1440 / minutes_per_record  # 一天的分钟数 / 每条记录的分钟数
        
        # 考虑市场休市时间 (假设加密货币市场24小时交易)
        return int(total_days * records_per_day * 0.99)  # 99% 预期完整度，考虑维护时间
    
    @staticmethod
    def _get_timeframe_days(timeframe: str) -> float:
        """获取时间框架对应的天数"""
        timeframe_days = {
            '1m': 1/1440, '5m': 5/1440, '15m': 15/1440, '30m': 30/1440,
            '1h': 1/24, '2h': 2/24, '4h': 4/24,
            '1d': 1, '1w': 7
        }
        return timeframe_days.get(timeframe, 1/1440)


class RetryManager:
    """重试管理器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def execute_with_retry(self, coro_func, *args, **kwargs):
        """带重试的执行器"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)  # 指数退避
                    logger.warning(f"第 {attempt + 1} 次尝试失败，{delay}秒后重试: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"重试 {self.max_retries} 次后仍失败: {e}")
        
        raise last_exception


class EnhancedOKXDataDownloader:
    """增强版OKX数据下载器"""
    
    def __init__(self):
        self.base_data_dir = Path("/root/trademe/backend/trading-service/data")
        self.okx_tick_dir = self.base_data_dir / "okx_tick_data"
        self.okx_kline_dir = self.base_data_dir / "okx_kline_data"
        self.temp_dir = self.base_data_dir / "temp"
        
        # 创建目录
        for dir_path in [self.okx_tick_dir, self.okx_kline_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 任务管理
        self.active_tasks: Dict[str, EnhancedDownloadTask] = {}
        
        # 增强组件
        self.quality_checker = DataQualityChecker()
        self.retry_manager = RetryManager(max_retries=3, base_delay=2.0)
        
        # 配置
        self.max_concurrent_downloads = 1
        self.chunk_size = 500
        self.batch_size = 100
        
        # OKX配置
        self.okx_tick_base_url = "https://static.okx.com/cdn/okex/traderecords/trades/daily"
        
        self.supported_tick_symbols = [
            'BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'SOL', 'BSV', 'TRB', 'AIDOGE', 'STARL',
            '1INCH', 'AAVE', 'ADA', 'AGLD', 'ALGO', 'ALPHA', 'ANT', 'APE', 'API3', 'APT',
        ]
        
        self.supported_kline_symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT',
            'BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 'ADA-USDT-SWAP', 
            'DOT-USDT-SWAP', 'LINK-USDT-SWAP', 'MATIC-USDT-SWAP', 'AVAX-USDT-SWAP',
        ]
        
        self.supported_timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w']
        
        logger.info("🚀 增强版OKX数据下载器初始化完成")
    
    async def create_enhanced_kline_task(
        self,
        symbols: List[str],
        timeframes: List[str], 
        start_date: str,
        end_date: str,
        task_id: Optional[str] = None
    ) -> EnhancedDownloadTask:
        """创建增强的K线下载任务"""
        if not task_id:
            task_id = f"enhanced_kline_{int(datetime.now().timestamp())}"
        
        # 验证参数
        invalid_symbols = [s for s in symbols if s not in self.supported_kline_symbols]
        if invalid_symbols:
            raise ValueError(f"不支持的交易对: {invalid_symbols}")
        
        invalid_timeframes = [tf for tf in timeframes if tf not in self.supported_timeframes]
        if invalid_timeframes:
            raise ValueError(f"不支持的时间周期: {invalid_timeframes}")
        
        # 计算预期记录数和子任务
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        
        subtasks = []
        expected_total_records = 0
        
        for symbol in symbols:
            for timeframe in timeframes:
                expected_records = self.quality_checker._calculate_expected_kline_records(
                    timeframe, start_dt, end_dt
                )
                expected_total_records += expected_records
                
                subtask = SubTaskProgress(
                    symbol=symbol,
                    timeframe=timeframe,
                    total_expected_records=expected_records,
                    status=TaskStatus.PENDING
                )
                subtasks.append(subtask)
        
        task = EnhancedDownloadTask(
            task_id=task_id,
            data_type=DataType.KLINE,
            exchange="okx",
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            total_files=len(symbols) * len(timeframes),
            expected_records=expected_total_records,
            subtasks=subtasks
        )
        
        self.active_tasks[task_id] = task
        await self._save_enhanced_task_to_database(task)
        
        logger.info(f"📝 创建增强K线任务: {task_id}, 预期记录数: {expected_total_records}")
        return task
    
    async def execute_enhanced_kline_task(self, task_id: str):
        """执行增强的K线下载任务"""
        if task_id not in self.active_tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        task = self.active_tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        await self._update_enhanced_task_in_database(task)
        
        try:
            logger.info(f"🚀 开始执行增强K线任务: {task_id}")
            
            start_dt = datetime.strptime(task.start_date, '%Y%m%d')
            end_dt = datetime.strptime(task.end_date, '%Y%m%d')
            
            completed_subtasks = 0
            failed_subtasks = 0
            
            # 逐个处理子任务
            for subtask in task.subtasks:
                subtask.status = TaskStatus.RUNNING
                subtask.start_time = datetime.now()
                
                try:
                    logger.info(f"📈 开始下载子任务: {subtask.symbol} {subtask.timeframe}")
                    
                    # 使用重试管理器下载
                    records = await self.retry_manager.execute_with_retry(
                        self._download_kline_with_validation,
                        subtask.symbol, subtask.timeframe, start_dt, end_dt, subtask
                    )
                    
                    subtask.actual_records = records
                    subtask.status = TaskStatus.COMPLETED
                    subtask.end_time = datetime.now()
                    
                    # 数据质量检查
                    quality_score, quality_issues = await self.quality_checker.check_kline_data_quality(
                        await self._get_db_session(), subtask.symbol, subtask.timeframe, start_dt, end_dt
                    )
                    
                    subtask.data_quality_score = quality_score
                    if quality_issues:
                        task.quality_issues.extend([f"{subtask.symbol} {subtask.timeframe}: {issue}" for issue in quality_issues])
                    
                    completed_subtasks += 1
                    task.downloaded_records += records
                    
                    logger.info(f"✅ {subtask.symbol} {subtask.timeframe} 完成: {records} 条记录, 质量评分: {quality_score:.1f}")
                    
                except Exception as e:
                    subtask.status = TaskStatus.FAILED
                    subtask.error_message = str(e)
                    subtask.end_time = datetime.now()
                    task.failed_subtasks.append(subtask)
                    failed_subtasks += 1
                    
                    logger.error(f"❌ {subtask.symbol} {subtask.timeframe} 失败: {e}")
                
                # 更新任务进度
                task.processed_files = completed_subtasks + failed_subtasks
                task.progress = (task.processed_files / task.total_files) * 100
                
                await self._update_enhanced_task_in_database(task)
            
            # 确定最终状态
            if failed_subtasks == 0:
                task.status = TaskStatus.COMPLETED
            elif completed_subtasks > 0:
                task.status = TaskStatus.PARTIAL_SUCCESS
                task.error_message = f"部分成功: {completed_subtasks}/{len(task.subtasks)} 个子任务完成"
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "所有子任务都失败了"
            
            task.completed_at = datetime.now()
            await self._update_enhanced_task_in_database(task)
            
            logger.info(f"✅ 增强K线任务完成: {task_id}, 状态: {task.status.value}, 记录数: {task.downloaded_records}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            await self._update_enhanced_task_in_database(task)
            logger.error(f"❌ 增强K线任务失败: {task_id}, 错误: {e}")
    
    async def _download_kline_with_validation(
        self, 
        symbol: str, 
        timeframe: str, 
        start_dt: datetime, 
        end_dt: datetime,
        subtask: SubTaskProgress
    ) -> int:
        """带验证的K线数据下载"""
        try:
            # 分阶段下载，避免单次下载数据量过大
            total_saved = 0
            current_start = start_dt
            stage_days = 7  # 每次下载7天的数据
            
            async with AsyncSessionLocal() as db:
                while current_start < end_dt:
                    current_end = min(current_start + timedelta(days=stage_days), end_dt)
                    
                    logger.info(f"🔄 分阶段下载: {symbol} {timeframe} ({current_start.date()} 到 {current_end.date()})")
                    
                    # 检查这个时间段是否已有数据
                    existing_count = await db.execute(
                        select(func.count(MarketData.id)).where(
                            and_(
                                MarketData.exchange == "okx",
                                MarketData.symbol == symbol,
                                MarketData.timeframe == timeframe,
                                MarketData.timestamp >= current_start,
                                MarketData.timestamp <= current_end
                            )
                        )
                    )
                    existing = existing_count.scalar() or 0
                    
                    if existing > 0:
                        logger.info(f"⏭️ 时间段 {current_start.date()}-{current_end.date()} 已有 {existing} 条数据，跳过")
                        current_start = current_end
                        continue
                    
                    # 下载这个时间段的数据
                    stage_saved = await self._download_kline_stage(
                        symbol, timeframe, current_start, current_end, db
                    )
                    
                    total_saved += stage_saved
                    current_start = current_end
                    
                    # 避免API限流
                    await asyncio.sleep(1)
            
            return total_saved
            
        except Exception as e:
            logger.error(f"❌ 下载K线数据失败: {symbol} {timeframe}, 错误: {e}")
            subtask.error_message = str(e)
            raise e
    
    async def _download_kline_stage(
        self,
        symbol: str,
        timeframe: str, 
        start_dt: datetime,
        end_dt: datetime,
        db: AsyncSession
    ) -> int:
        """下载单个阶段的K线数据"""
        try:
            current_end = int(end_dt.timestamp() * 1000)
            start_timestamp = int(start_dt.timestamp() * 1000)
            saved_records = 0
            request_count = 0
            
            while current_end > start_timestamp and request_count < 20:
                try:
                    # 使用OKX市场服务获取K线数据
                    kline_data = await okx_market_service.get_klines(
                        symbol=symbol,
                        timeframe=timeframe,
                        limit=300,
                        start_time=start_timestamp,
                        end_time=current_end,
                        use_cache=False
                    )
                    
                    if not kline_data.get('klines') or len(kline_data['klines']) == 0:
                        logger.info(f"⚠️ 没有更多数据: {symbol} {timeframe}")
                        break
                    
                    request_count += 1
                    
                    # 转换为MarketData对象
                    market_data_records = []
                    for kline in kline_data['klines']:
                        try:
                            timestamp_ms = int(kline[0])
                            dt_obj = dt.fromtimestamp(timestamp_ms / 1000)
                            
                            # 确保时间戳在指定范围内
                            if not (start_dt <= dt_obj <= end_dt):
                                continue
                            
                            # 按符号写法自动判断产品类型：*-SWAP 视为永续(futures)，否则视为现货(spot)
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
                            logger.warning(f"⚠️ 解析K线失败: {kline}, 错误: {parse_error}")
                            continue
                    
                    # 批量插入并避免重复
                    if market_data_records:
                        unique_records = await self._remove_duplicates_kline(db, market_data_records)
                        
                        if unique_records:
                            db.add_all(unique_records)
                            await db.commit()
                            saved_records += len(unique_records)
                            
                            logger.info(f"💾 已保存 {len(unique_records)} 条K线数据 (跳过重复: {len(market_data_records) - len(unique_records)} 条)")
                    
                    # 更新时间范围
                    if kline_data['klines']:
                        earliest_timestamp = int(kline_data['klines'][0][0])
                        
                        if earliest_timestamp <= start_timestamp:
                            logger.info(f"✅ 已到达起始时间")
                            break
                        
                        current_end = earliest_timestamp - 1
                    
                    # 如果获取的数据少于300条，说明已到边界
                    if len(kline_data['klines']) < 300:
                        logger.info(f"✅ 已到达数据边界")
                        break
                    
                    await asyncio.sleep(0.2)
                    
                except Exception as request_error:
                    logger.error(f"❌ API请求失败: {request_error}")
                    await asyncio.sleep(2)
                    continue
            
            logger.info(f"✅ 阶段下载完成: {symbol} {timeframe}, 保存 {saved_records} 条记录")
            return saved_records
            
        except Exception as e:
            logger.error(f"❌ 阶段下载失败: {e}")
            return 0
    
    async def _get_db_session(self) -> AsyncSession:
        """获取数据库会话"""
        return AsyncSessionLocal()
    
    async def _save_enhanced_task_to_database(self, task: EnhancedDownloadTask):
        """保存增强任务到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                # 序列化子任务信息
                subtasks_json = json.dumps([
                    {
                        "symbol": st.symbol,
                        "timeframe": st.timeframe, 
                        "expected_records": st.total_expected_records,
                        "status": st.status.value
                    }
                    for st in task.subtasks
                ])
                
                db_task = DataCollectionTask(
                    task_name=task.task_id,
                    exchange=task.exchange,
                    data_type=task.data_type.value,
                    symbols=','.join(task.symbols),
                    timeframes=','.join(task.timeframes) if task.timeframes else None,
                    status=task.status.value,
                    schedule_type="enhanced_manual",
                    success_count=0,
                    error_count=0,
                    total_records=0,
                    created_at=task.created_at,
                    config=json.dumps({
                        "start_date": task.start_date,
                        "end_date": task.end_date,
                        "total_files": task.total_files,
                        "expected_records": task.expected_records,
                        "subtasks": subtasks_json
                    })
                )
                
                db.add(db_task)
                await db.commit()
                logger.info(f"💾 增强任务已保存: {task.task_id}")
                
        except Exception as e:
            logger.error(f"❌ 保存增强任务失败: {e}")
    
    async def _update_enhanced_task_in_database(self, task: EnhancedDownloadTask):
        """更新增强任务状态"""
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
                    
                    # 更新详细配置信息
                    config = json.loads(db_task.config or "{}")
                    config.update({
                        "progress": task.progress,
                        "quality_issues": task.quality_issues,
                        "failed_subtasks_count": len(task.failed_subtasks),
                        "completed_subtasks": [
                            {
                                "symbol": st.symbol,
                                "timeframe": st.timeframe,
                                "records": st.actual_records,
                                "quality_score": st.data_quality_score
                            }
                            for st in task.subtasks if st.status == TaskStatus.COMPLETED
                        ]
                    })
                    db_task.config = json.dumps(config)
                    
                    await db.commit()
                    logger.debug(f"🔄 增强任务状态已更新: {task.task_id}")
                
        except Exception as e:
            logger.error(f"❌ 更新增强任务状态失败: {e}")
    
    async def _remove_duplicates_kline(self, db: AsyncSession, market_records: List[MarketData]) -> List[MarketData]:
        """移除重复的K线数据"""
        if not market_records:
            return []
        
        try:
            # 构建查询条件
            unique_keys = [(record.exchange, record.symbol, record.timeframe, record.timestamp) 
                          for record in market_records]
            
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
            
            # 过滤重复记录
            unique_records = []
            for record in market_records:
                key = (record.exchange, record.symbol, record.timeframe, record.timestamp)
                if key not in existing_keys:
                    unique_records.append(record)
            
            return unique_records
            
        except Exception as e:
            logger.error(f"❌ K线去重失败: {e}")
            return market_records
    
    async def get_enhanced_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取增强任务的详细状态"""
        if task_id not in self.active_tasks:
            return None
        
        task = self.active_tasks[task_id]
        
        return {
            "task_id": task.task_id,
            "data_type": task.data_type.value,
            "status": task.status.value,
            "progress": task.progress,
            "symbols": task.symbols,
            "timeframes": task.timeframes,
            "expected_records": task.expected_records,
            "downloaded_records": task.downloaded_records,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message,
            "subtasks": [
                {
                    "symbol": st.symbol,
                    "timeframe": st.timeframe,
                    "status": st.status.value,
                    "expected_records": st.total_expected_records,
                    "actual_records": st.actual_records,
                    "quality_score": st.data_quality_score,
                    "error_message": st.error_message,
                    "retry_count": st.retry_count
                }
                for st in task.subtasks
            ],
            "quality_issues": task.quality_issues,
            "failed_subtasks_count": len(task.failed_subtasks)
        }


# 全局实例
enhanced_okx_downloader = EnhancedOKXDataDownloader()
