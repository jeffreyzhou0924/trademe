"""
数据采集任务管理核心逻辑
负责数据采集任务的调度、执行、监控和管理
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
from enum import Enum

import ccxt
import ccxt.async_support as ccxt_async
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.data_collection import (
    DataCollectionTask, DataQualityMetric, ExchangeAPIConfig,
    DataCollectionLog, DataStorageUsage, DataCleanupJob
)
from app.models.data_management import (
    TickData, DataPartition, DataPipelineConfig, DataQualityRule
)
from app.models.market_data import MarketData


# 配置日志
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    RUNNING = "running"


class DataType(Enum):
    """数据类型枚举"""
    KLINE = "kline"
    TICK = "tick"
    ORDERBOOK = "orderbook" 
    TRADES = "trades"
    FUNDING_RATE = "funding_rate"


@dataclass
class CollectionResult:
    """数据采集结果"""
    success: bool
    records_count: int
    error_message: Optional[str] = None
    processing_time: float = 0.0
    data_quality_score: float = 100.0


@dataclass 
class ExchangeConfig:
    """交易所配置"""
    exchange_id: str
    api_key: Optional[str] = None
    secret: Optional[str] = None
    sandbox: bool = True
    rate_limit: int = 10
    timeout: int = 30000
    proxies: Optional[Dict] = None


class DataCollectionManager:
    """数据采集管理器"""
    
    def __init__(self):
        self.running_tasks: Dict[int, asyncio.Task] = {}
        self.exchange_clients: Dict[str, ccxt_async.Exchange] = {}
        self.task_scheduler: Optional[asyncio.Task] = None
        self.is_running = False
        
    async def start(self):
        """启动数据采集管理器"""
        if self.is_running:
            return
            
        logger.info("启动数据采集管理器...")
        self.is_running = True
        
        # 启动任务调度器
        self.task_scheduler = asyncio.create_task(self._task_scheduler_loop())
        
        # 预加载活跃任务
        await self._load_active_tasks()
        
        logger.info("数据采集管理器启动完成")
    
    async def stop(self):
        """停止数据采集管理器"""
        if not self.is_running:
            return
            
        logger.info("停止数据采集管理器...")
        self.is_running = False
        
        # 停止任务调度器
        if self.task_scheduler:
            self.task_scheduler.cancel()
            try:
                await self.task_scheduler
            except asyncio.CancelledError:
                pass
        
        # 停止所有运行中的任务
        if self.running_tasks:
            tasks_to_cancel = list(self.running_tasks.values())
            for task in tasks_to_cancel:
                task.cancel()
            
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            
        # 关闭交易所客户端
        for client in self.exchange_clients.values():
            if hasattr(client, 'close'):
                await client.close()
        
        self.running_tasks.clear()
        self.exchange_clients.clear()
        
        logger.info("数据采集管理器停止完成")
    
    async def _task_scheduler_loop(self):
        """任务调度器主循环"""
        while self.is_running:
            try:
                await self._check_and_schedule_tasks()
                await asyncio.sleep(60)  # 每分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"任务调度器异常: {e}")
                await asyncio.sleep(10)  # 异常后等待10秒
    
    async def _check_and_schedule_tasks(self):
        """检查并调度任务"""
        async with self._get_db_session() as db:
            try:
                # 查询需要执行的任务
                current_time = datetime.now()
                
                # 查询活跃且到了执行时间的任务
                stmt = select(DataCollectionTask).where(
                    and_(
                        DataCollectionTask.status == TaskStatus.ACTIVE.value,
                        or_(
                            DataCollectionTask.next_run_at.is_(None),
                            DataCollectionTask.next_run_at <= current_time
                        )
                    )
                ).order_by(DataCollectionTask.priority.desc())
                
                result = await db.execute(stmt)
                pending_tasks = result.scalars().all()
                
                for task in pending_tasks:
                    if task.id not in self.running_tasks:
                        # 创建并启动采集任务
                        collection_task = asyncio.create_task(
                            self._execute_collection_task(task.id)
                        )
                        self.running_tasks[task.id] = collection_task
                        
                        logger.info(f"启动采集任务: {task.task_name} (ID: {task.id})")
                
                # 清理已完成的任务
                completed_task_ids = []
                for task_id, task in self.running_tasks.items():
                    if task.done():
                        completed_task_ids.append(task_id)
                
                for task_id in completed_task_ids:
                    del self.running_tasks[task_id]
                    
            except Exception as e:
                logger.error(f"检查和调度任务失败: {e}")
    
    async def _execute_collection_task(self, task_id: int):
        """执行单个采集任务"""
        async with self._get_db_session() as db:
            try:
                # 获取任务配置
                stmt = select(DataCollectionTask).where(DataCollectionTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task or task.status != TaskStatus.ACTIVE.value:
                    return
                
                # 更新任务状态
                task.status = TaskStatus.RUNNING.value
                task.last_run_at = datetime.now()
                await db.commit()
                
                # 解析配置
                symbols = json.loads(task.symbols) if task.symbols else []
                timeframes = json.loads(task.timeframes) if task.timeframes else []
                
                # 执行数据采集
                results = []
                for symbol in symbols:
                    if task.data_type == DataType.KLINE.value:
                        for timeframe in timeframes:
                            result = await self._collect_kline_data(
                                task.exchange, symbol, timeframe, task
                            )
                            results.append(result)
                    elif task.data_type == DataType.TICK.value:
                        result = await self._collect_tick_data(
                            task.exchange, symbol, task
                        )
                        results.append(result)
                    # 可以添加其他数据类型的处理
                
                # 更新任务统计
                successful_results = [r for r in results if r.success]
                failed_results = [r for r in results if not r.success]
                
                task.success_count += len(successful_results)
                task.error_count += len(failed_results)
                task.total_records += sum(r.records_count for r in successful_results)
                
                # 计算下次执行时间
                task.next_run_at = self._calculate_next_run_time(task)
                task.status = TaskStatus.ACTIVE.value
                
                await db.commit()
                
                # 记录执行日志
                await self._log_task_execution(db, task, results)
                
                # 更新数据质量指标
                if successful_results:
                    await self._update_quality_metrics(db, task, successful_results)
                
            except Exception as e:
                logger.error(f"执行采集任务 {task_id} 失败: {e}")
                
                # 更新任务错误状态
                try:
                    task.status = TaskStatus.ERROR.value
                    task.last_error_at = datetime.now()
                    task.last_error_message = str(e)
                    task.error_count += 1
                    await db.commit()
                except:
                    pass
    
    async def _collect_kline_data(
        self, 
        exchange_id: str, 
        symbol: str, 
        timeframe: str, 
        task: DataCollectionTask
    ) -> CollectionResult:
        """采集K线数据"""
        start_time = datetime.now()
        
        try:
            # 获取交易所客户端
            client = await self._get_exchange_client(exchange_id)
            
            # 计算时间范围
            since = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
            
            # 获取K线数据
            ohlcv_data = await client.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=100
            )
            
            # 保存数据到数据库
            async with self._get_db_session() as db:
                records_saved = 0
                
                for ohlcv in ohlcv_data:
                    timestamp, open_price, high, low, close, volume = ohlcv
                    
                    # 检查数据是否已存在
                    existing = await db.execute(
                        select(MarketData).where(
                            and_(
                                MarketData.exchange == exchange_id,
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
                        exchange=exchange_id,
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
                    records_saved += 1
                
                await db.commit()
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return CollectionResult(
                success=True,
                records_count=records_saved,
                processing_time=processing_time,
                data_quality_score=self._calculate_data_quality_score(ohlcv_data)
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return CollectionResult(
                success=False,
                records_count=0,
                error_message=str(e),
                processing_time=processing_time
            )
    
    async def _collect_tick_data(
        self, 
        exchange_id: str, 
        symbol: str, 
        task: DataCollectionTask
    ) -> CollectionResult:
        """采集Tick数据"""
        start_time = datetime.now()
        
        try:
            # 获取交易所客户端
            client = await self._get_exchange_client(exchange_id)
            
            # 获取最近的交易数据（模拟tick数据）
            trades = await client.fetch_trades(symbol, limit=100)
            
            # 保存数据到数据库
            async with self._get_db_session() as db:
                records_saved = 0
                
                for trade in trades:
                    # 检查数据是否已存在
                    existing = await db.execute(
                        select(TickData).where(
                            and_(
                                TickData.exchange == exchange_id,
                                TickData.symbol == symbol,
                                TickData.trade_id == str(trade['id'])
                            )
                        )
                    )
                    
                    if existing.scalar_one_or_none():
                        continue
                    
                    # 创建新的tick数据记录
                    tick_data = TickData(
                        exchange=exchange_id,
                        symbol=symbol,
                        price=trade['price'],
                        volume=trade['amount'],
                        side=trade['side'],
                        trade_id=str(trade['id']),
                        timestamp=int(trade['timestamp'] * 1000),  # 微秒级时间戳
                        data_source='rest_api'
                    )
                    
                    db.add(tick_data)
                    records_saved += 1
                
                await db.commit()
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return CollectionResult(
                success=True,
                records_count=records_saved,
                processing_time=processing_time,
                data_quality_score=self._calculate_tick_quality_score(trades)
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            return CollectionResult(
                success=False,
                records_count=0,
                error_message=str(e),
                processing_time=processing_time
            )
    
    async def _get_exchange_client(self, exchange_id: str) -> ccxt_async.Exchange:
        """获取交易所客户端"""
        if exchange_id not in self.exchange_clients:
            # 从数据库获取交易所配置
            async with self._get_db_session() as db:
                stmt = select(ExchangeAPIConfig).where(
                    ExchangeAPIConfig.exchange == exchange_id
                )
                result = await db.execute(stmt)
                config = result.scalar_one_or_none()
                
                if not config:
                    raise ValueError(f"交易所 {exchange_id} 配置不存在")
            
            # 创建客户端
            exchange_class = getattr(ccxt_async, exchange_id.lower())
            client = exchange_class({
                'apiKey': '',  # 使用公开API
                'secret': '',
                'timeout': 30000,
                'sandbox': True,  # 使用测试环境
                'enableRateLimit': True,
                'rateLimit': config.rate_limit_per_second * 1000 if config else 1000
            })
            
            self.exchange_clients[exchange_id] = client
        
        return self.exchange_clients[exchange_id]
    
    def _calculate_data_quality_score(self, data: List) -> float:
        """计算数据质量评分"""
        if not data:
            return 0.0
        
        score = 100.0
        
        # 检查数据完整性
        none_count = sum(1 for item in data if None in item)
        if none_count > 0:
            score -= (none_count / len(data)) * 20
        
        # 检查数据连续性（简单检查）
        timestamps = [item[0] for item in data if item[0]]
        if len(timestamps) > 1:
            gaps = 0
            for i in range(1, len(timestamps)):
                if timestamps[i] - timestamps[i-1] > 2 * 60 * 1000:  # 超过2分钟间隙
                    gaps += 1
            
            if gaps > 0:
                score -= min(gaps * 5, 30)
        
        return max(score, 0.0)
    
    def _calculate_tick_quality_score(self, trades: List) -> float:
        """计算Tick数据质量评分"""
        if not trades:
            return 0.0
        
        score = 100.0
        
        # 检查必要字段完整性
        incomplete_count = 0
        for trade in trades:
            if not all([trade.get('price'), trade.get('amount'), trade.get('side')]):
                incomplete_count += 1
        
        if incomplete_count > 0:
            score -= (incomplete_count / len(trades)) * 30
        
        # 检查价格合理性
        prices = [float(trade['price']) for trade in trades if trade.get('price')]
        if prices:
            avg_price = sum(prices) / len(prices)
            outliers = sum(1 for p in prices if abs(p - avg_price) > avg_price * 0.1)
            
            if outliers > 0:
                score -= min((outliers / len(prices)) * 20, 20)
        
        return max(score, 0.0)
    
    def _calculate_next_run_time(self, task: DataCollectionTask) -> datetime:
        """计算下次执行时间"""
        # 解析调度配置
        config = json.loads(task.schedule_config) if task.schedule_config else {}
        interval_minutes = config.get('interval_minutes', 60)  # 默认每小时
        
        return datetime.now() + timedelta(minutes=interval_minutes)
    
    async def _log_task_execution(
        self, 
        db: AsyncSession, 
        task: DataCollectionTask, 
        results: List[CollectionResult]
    ):
        """记录任务执行日志"""
        execution_id = f"exec_{task.id}_{int(datetime.now().timestamp())}"
        
        for i, result in enumerate(results):
            log_level = "INFO" if result.success else "ERROR"
            message = f"采集完成: {result.records_count} 条记录" if result.success else f"采集失败: {result.error_message}"
            
            log_entry = DataCollectionLog(
                task_id=task.id,
                execution_id=execution_id,
                log_level=log_level,
                message=message,
                details=json.dumps(asdict(result)),
                exchange=task.exchange,
                data_type=task.data_type,
                records_processed=result.records_count,
                processing_time_ms=int(result.processing_time * 1000),
                error_message=result.error_message
            )
            
            db.add(log_entry)
        
        await db.commit()
    
    async def _update_quality_metrics(
        self, 
        db: AsyncSession, 
        task: DataCollectionTask,
        results: List[CollectionResult]
    ):
        """更新数据质量指标"""
        today = date.today()
        symbols = json.loads(task.symbols) if task.symbols else []
        
        for symbol in symbols:
            # 查询或创建质量指标记录
            stmt = select(DataQualityMetric).where(
                and_(
                    DataQualityMetric.exchange == task.exchange,
                    DataQualityMetric.symbol == symbol,
                    DataQualityMetric.data_type == task.data_type,
                    DataQualityMetric.date == today
                )
            )
            result = await db.execute(stmt)
            metric = result.scalar_one_or_none()
            
            if not metric:
                metric = DataQualityMetric(
                    task_id=task.id,
                    exchange=task.exchange,
                    symbol=symbol,
                    data_type=task.data_type,
                    date=today
                )
                db.add(metric)
            
            # 更新指标
            total_records = sum(r.records_count for r in results if r.success)
            avg_quality_score = sum(r.data_quality_score for r in results if r.success) / len(results)
            
            metric.total_records += total_records
            metric.quality_score = avg_quality_score
            metric.completeness_rate = min(avg_quality_score, 100.0)
            metric.accuracy_score = avg_quality_score
        
        await db.commit()
    
    async def _load_active_tasks(self):
        """加载活跃任务"""
        async with self._get_db_session() as db:
            stmt = select(DataCollectionTask).where(
                DataCollectionTask.status == TaskStatus.ACTIVE.value
            )
            result = await db.execute(stmt)
            active_tasks = result.scalars().all()
            
            logger.info(f"加载了 {len(active_tasks)} 个活跃任务")
    
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


class DataQualityMonitor:
    """数据质量监控器"""
    
    def __init__(self):
        self.monitoring_rules: List[DataQualityRule] = []
        self.is_running = False
    
    async def start(self):
        """启动质量监控"""
        if self.is_running:
            return
        
        self.is_running = True
        await self._load_quality_rules()
        
        # 启动监控循环
        asyncio.create_task(self._monitoring_loop())
        
        logger.info("数据质量监控启动完成")
    
    async def stop(self):
        """停止质量监控"""
        self.is_running = False
        logger.info("数据质量监控已停止")
    
    async def _monitoring_loop(self):
        """质量监控主循环"""
        while self.is_running:
            try:
                await self._run_quality_checks()
                await asyncio.sleep(3600)  # 每小时检查一次
            except Exception as e:
                logger.error(f"质量监控异常: {e}")
                await asyncio.sleep(600)  # 异常后等待10分钟
    
    async def _load_quality_rules(self):
        """加载质量检查规则"""
        async with AsyncSessionLocal() as db:
            stmt = select(DataQualityRule).where(
                DataQualityRule.is_active == True
            )
            result = await db.execute(stmt)
            self.monitoring_rules = result.scalars().all()
    
    async def _run_quality_checks(self):
        """执行质量检查"""
        for rule in self.monitoring_rules:
            try:
                await self._execute_quality_rule(rule)
            except Exception as e:
                logger.error(f"执行质量规则 {rule.rule_name} 失败: {e}")
    
    async def _execute_quality_rule(self, rule: DataQualityRule):
        """执行单个质量规则"""
        async with AsyncSessionLocal() as db:
            # 执行SQL查询规则
            result = await db.execute(text(rule.rule_sql))
            check_value = result.scalar()
            
            # 评估结果
            threshold = float(rule.threshold_value) if rule.threshold_value else 0
            operator = rule.threshold_operator
            
            passed = False
            if operator == ">=":
                passed = check_value >= threshold
            elif operator == "<=":
                passed = check_value <= threshold
            elif operator == "==":
                passed = check_value == threshold
            elif operator == "!=":
                passed = check_value != threshold
            
            # 更新规则统计
            rule.total_checks += 1
            rule.last_check_at = datetime.now()
            rule.last_check_result = "passed" if passed else "failed"
            rule.last_check_value = float(check_value) if check_value else 0
            
            if passed:
                rule.passed_checks += 1
            else:
                rule.failed_checks += 1
                
                # 如果检查失败且启用了自动修复
                if rule.auto_fix_enabled and rule.auto_fix_sql:
                    try:
                        await db.execute(text(rule.auto_fix_sql))
                        logger.info(f"自动修复规则 {rule.rule_name} 执行成功")
                    except Exception as e:
                        logger.error(f"自动修复规则 {rule.rule_name} 执行失败: {e}")
            
            await db.commit()


# 全局实例
data_collection_manager = DataCollectionManager()
data_quality_monitor = DataQualityMonitor()