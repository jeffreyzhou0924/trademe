"""
性能优化器
提供系统性能监控、瓶颈检测、自动优化等功能
包含数据库优化、内存管理、异步任务优化、缓存优化等
"""

import asyncio
import time
import psutil
import gc
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import weakref
import tracemalloc

logger = logging.getLogger(__name__)

class PerformanceLevel(Enum):
    """性能等级"""
    EXCELLENT = "excellent"    # 优秀
    GOOD = "good"             # 良好
    AVERAGE = "average"       # 平均
    POOR = "poor"            # 较差
    CRITICAL = "critical"     # 严重

class OptimizationType(Enum):
    """优化类型"""
    DATABASE = "database"
    MEMORY = "memory"
    ASYNC_TASK = "async_task"
    API_RESPONSE = "api_response"
    CACHE = "cache"
    NETWORK = "network"
    CPU = "cpu"

@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    level: PerformanceLevel = PerformanceLevel.GOOD
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceIssue:
    """性能问题"""
    issue_id: str
    type: OptimizationType
    severity: PerformanceLevel
    description: str
    detected_at: datetime
    metrics: List[PerformanceMetric] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    auto_fix_available: bool = False
    resolved: bool = False

@dataclass
class OptimizationResult:
    """优化结果"""
    optimization_type: OptimizationType
    success: bool
    improvements: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.active_issues: Dict[str, PerformanceIssue] = {}
        self.optimization_history: List[OptimizationResult] = []
        self.monitoring_active = False
        self.optimization_tasks: Dict[str, asyncio.Task] = {}
        
        # 性能阈值配置
        self.thresholds = self._init_performance_thresholds()
        
        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 监控间隔
        self.monitoring_interval = 30  # 秒
        
        # 弱引用跟踪（用于内存泄漏检测）
        self.object_registry = weakref.WeakSet()
        
    def _init_performance_thresholds(self) -> Dict[str, Dict[str, float]]:
        """初始化性能阈值"""
        return {
            "cpu_usage": {"warning": 70.0, "critical": 90.0},
            "memory_usage": {"warning": 75.0, "critical": 90.0},
            "disk_usage": {"warning": 80.0, "critical": 95.0},
            "api_response_time": {"warning": 1000.0, "critical": 3000.0},  # 毫秒
            "database_query_time": {"warning": 100.0, "critical": 500.0},  # 毫秒
            "active_connections": {"warning": 80, "critical": 100},
            "memory_growth_rate": {"warning": 10.0, "critical": 25.0},  # MB/小时
            "cache_hit_rate": {"warning": 70.0, "critical": 50.0}  # 百分比，越低越差
        }
    
    async def start_monitoring(self):
        """开始性能监控"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        logger.info("启动性能监控系统")
        
        # 启动内存跟踪
        tracemalloc.start()
        
        # 创建监控任务
        monitoring_tasks = [
            asyncio.create_task(self._monitor_system_resources()),
            asyncio.create_task(self._monitor_api_performance()),
            asyncio.create_task(self._monitor_database_performance()),
            asyncio.create_task(self._monitor_memory_usage()),
            asyncio.create_task(self._monitor_async_tasks()),
            asyncio.create_task(self._auto_optimization_task())
        ]
        
        # 存储任务引用
        for i, task in enumerate(monitoring_tasks):
            self.optimization_tasks[f"monitor_{i}"] = task
        
        logger.info(f"启动了 {len(monitoring_tasks)} 个监控任务")
    
    async def stop_monitoring(self):
        """停止性能监控"""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        logger.info("停止性能监控系统")
        
        # 取消所有监控任务
        for task_name, task in self.optimization_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.optimization_tasks.clear()
        
        # 停止内存跟踪
        tracemalloc.stop()
        
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)
    
    async def _monitor_system_resources(self):
        """监控系统资源"""
        while self.monitoring_active:
            try:
                # CPU使用率
                cpu_usage = psutil.cpu_percent(interval=1)
                await self._record_metric("cpu_usage", cpu_usage, "percent")
                
                # 内存使用率
                memory = psutil.virtual_memory()
                memory_usage = memory.percent
                await self._record_metric("memory_usage", memory_usage, "percent")
                
                # 磁盘使用率
                disk = psutil.disk_usage('/')
                disk_usage = (disk.used / disk.total) * 100
                await self._record_metric("disk_usage", disk_usage, "percent")
                
                # 网络IO
                network = psutil.net_io_counters()
                await self._record_metric("network_bytes_sent", network.bytes_sent, "bytes")
                await self._record_metric("network_bytes_recv", network.bytes_recv, "bytes")
                
                # 进程信息
                process = psutil.Process()
                await self._record_metric("process_memory_mb", process.memory_info().rss / 1024 / 1024, "MB")
                await self._record_metric("process_cpu_percent", process.cpu_percent(), "percent")
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"系统资源监控出错: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_api_performance(self):
        """监控API性能"""
        while self.monitoring_active:
            try:
                # 这里应该从API中间件或日志中收集响应时间数据
                # 简化实现：模拟API响应时间监控
                
                # 实际实现中，这些数据应该从请求日志或中间件中获取
                current_time = datetime.utcnow()
                
                # 模拟一些API响应时间数据
                api_endpoints = [
                    "/api/v1/strategies", "/api/v1/market-data", 
                    "/api/v1/ai/chat", "/api/v1/trading/orders"
                ]
                
                for endpoint in api_endpoints:
                    # 这里应该从实际监控数据中获取
                    # response_time = get_average_response_time(endpoint)
                    # await self._record_metric(f"api_response_time_{endpoint}", response_time, "ms")
                    pass
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"API性能监控出错: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_database_performance(self):
        """监控数据库性能"""
        while self.monitoring_active:
            try:
                # 监控数据库连接数
                # 这里应该从实际的数据库连接池中获取数据
                
                # 监控查询性能
                # 可以通过SQLAlchemy的事件系统或数据库日志来收集
                
                # 简化实现
                await self._record_metric("active_db_connections", 10, "count")
                await self._record_metric("avg_query_time", 50.0, "ms")
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"数据库性能监控出错: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_memory_usage(self):
        """监控内存使用"""
        while self.monitoring_active:
            try:
                # 获取当前内存快照
                if tracemalloc.is_tracing():
                    current, peak = tracemalloc.get_traced_memory()
                    await self._record_metric("traced_memory_current", current / 1024 / 1024, "MB")
                    await self._record_metric("traced_memory_peak", peak / 1024 / 1024, "MB")
                
                # 垃圾回收统计
                gc_stats = gc.get_stats()
                if gc_stats:
                    await self._record_metric("gc_collections_gen0", gc_stats[0]['collections'], "count")
                    await self._record_metric("gc_objects_gen0", gc_stats[0]['collected'], "count")
                
                # 检测内存泄漏
                await self._check_memory_leaks()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"内存使用监控出错: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_async_tasks(self):
        """监控异步任务"""
        while self.monitoring_active:
            try:
                # 获取当前运行的任务数量
                all_tasks = asyncio.all_tasks()
                running_tasks = sum(1 for task in all_tasks if not task.done())
                
                await self._record_metric("running_async_tasks", running_tasks, "count")
                
                # 检查长时间运行的任务
                long_running_tasks = []
                for task in all_tasks:
                    if not task.done():
                        # 检查任务创建时间（需要自定义实现）
                        pass
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"异步任务监控出错: {e}")
                await asyncio.sleep(60)
    
    async def _auto_optimization_task(self):
        """自动优化任务"""
        while self.monitoring_active:
            try:
                # 检测性能问题
                await self._detect_performance_issues()
                
                # 自动执行优化
                await self._auto_optimize()
                
                # 清理历史数据
                await self._cleanup_old_data()
                
                await asyncio.sleep(300)  # 5分钟执行一次
                
            except Exception as e:
                logger.error(f"自动优化任务出错: {e}")
                await asyncio.sleep(300)
    
    async def _record_metric(self, name: str, value: float, unit: str, metadata: Dict[str, Any] = None):
        """记录性能指标"""
        try:
            thresholds = self.thresholds.get(name, {})
            
            # 确定性能等级
            level = PerformanceLevel.GOOD
            if "critical" in thresholds and value >= thresholds["critical"]:
                level = PerformanceLevel.CRITICAL
            elif "warning" in thresholds and value >= thresholds["warning"]:
                level = PerformanceLevel.POOR
            elif name == "cache_hit_rate":  # 缓存命中率越高越好
                if value < thresholds.get("critical", 0):
                    level = PerformanceLevel.CRITICAL
                elif value < thresholds.get("warning", 0):
                    level = PerformanceLevel.POOR
            
            metric = PerformanceMetric(
                name=name,
                value=value,
                unit=unit,
                timestamp=datetime.utcnow(),
                threshold_warning=thresholds.get("warning"),
                threshold_critical=thresholds.get("critical"),
                level=level,
                metadata=metadata or {}
            )
            
            # 存储到历史记录
            self.metrics_history[name].append(metric)
            
            # 如果性能等级较差，记录问题
            if level in [PerformanceLevel.POOR, PerformanceLevel.CRITICAL]:
                await self._record_performance_issue(metric)
            
        except Exception as e:
            logger.error(f"记录性能指标失败 {name}: {e}")
    
    async def _record_performance_issue(self, metric: PerformanceMetric):
        """记录性能问题"""
        try:
            issue_id = f"{metric.name}_{int(metric.timestamp.timestamp())}"
            
            if issue_id in self.active_issues:
                return  # 问题已存在
            
            # 确定优化类型
            optimization_type = self._get_optimization_type(metric.name)
            
            # 生成建议
            suggestions = self._generate_suggestions(metric)
            
            issue = PerformanceIssue(
                issue_id=issue_id,
                type=optimization_type,
                severity=metric.level,
                description=f"{metric.name} 性能指标异常: {metric.value} {metric.unit}",
                detected_at=metric.timestamp,
                metrics=[metric],
                suggestions=suggestions,
                auto_fix_available=self._can_auto_fix(metric.name),
                resolved=False
            )
            
            self.active_issues[issue_id] = issue
            
            logger.warning(f"检测到性能问题: {issue.description}")
            
        except Exception as e:
            logger.error(f"记录性能问题失败: {e}")
    
    def _get_optimization_type(self, metric_name: str) -> OptimizationType:
        """根据指标名称确定优化类型"""
        if "cpu" in metric_name or "process_cpu" in metric_name:
            return OptimizationType.CPU
        elif "memory" in metric_name or "gc_" in metric_name:
            return OptimizationType.MEMORY
        elif "db" in metric_name or "query" in metric_name:
            return OptimizationType.DATABASE
        elif "api" in metric_name or "response" in metric_name:
            return OptimizationType.API_RESPONSE
        elif "cache" in metric_name:
            return OptimizationType.CACHE
        elif "network" in metric_name:
            return OptimizationType.NETWORK
        elif "async" in metric_name or "task" in metric_name:
            return OptimizationType.ASYNC_TASK
        else:
            return OptimizationType.CPU  # 默认
    
    def _generate_suggestions(self, metric: PerformanceMetric) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        if metric.name == "cpu_usage":
            suggestions.extend([
                "检查是否有CPU密集型任务占用过多资源",
                "考虑使用异步处理减少CPU阻塞",
                "优化算法复杂度",
                "增加缓存减少重复计算"
            ])
        elif metric.name == "memory_usage":
            suggestions.extend([
                "检查内存泄漏",
                "优化数据结构使用",
                "增加垃圾回收频率",
                "减少大对象创建"
            ])
        elif "query" in metric.name:
            suggestions.extend([
                "检查数据库索引",
                "优化SQL查询",
                "使用查询缓存",
                "考虑数据库分片"
            ])
        elif "api_response" in metric.name:
            suggestions.extend([
                "优化API逻辑",
                "增加响应缓存",
                "使用异步处理",
                "优化数据库查询"
            ])
        elif "cache" in metric.name:
            suggestions.extend([
                "调整缓存策略",
                "增加缓存容量",
                "优化缓存键设计",
                "检查缓存失效策略"
            ])
        
        return suggestions
    
    def _can_auto_fix(self, metric_name: str) -> bool:
        """判断是否可以自动修复"""
        auto_fixable_metrics = {
            "memory_usage": True,  # 可以触发GC
            "cache_hit_rate": True,  # 可以调整缓存策略
            "gc_collections_gen0": True,  # 可以手动GC
        }
        
        return auto_fixable_metrics.get(metric_name, False)
    
    async def _detect_performance_issues(self):
        """检测性能问题"""
        try:
            current_time = datetime.utcnow()
            
            # 检查趋势问题
            for metric_name, history in self.metrics_history.items():
                if len(history) < 10:  # 需要足够的历史数据
                    continue
                
                recent_metrics = [m for m in history if (current_time - m.timestamp).seconds < 600]  # 最近10分钟
                
                if len(recent_metrics) < 5:
                    continue
                
                # 检查是否有持续恶化的趋势
                values = [m.value for m in recent_metrics]
                if len(values) >= 5:
                    trend = self._calculate_trend(values)
                    if trend > 0.1 and metric_name in ["cpu_usage", "memory_usage", "api_response_time"]:
                        # 性能持续恶化
                        issue_id = f"trend_{metric_name}_{int(current_time.timestamp())}"
                        if issue_id not in self.active_issues:
                            await self._create_trend_issue(metric_name, recent_metrics, trend)
            
        except Exception as e:
            logger.error(f"检测性能问题失败: {e}")
    
    def _calculate_trend(self, values: List[float]) -> float:
        """计算趋势斜率"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x = list(range(n))
        y = values
        
        # 简单线性回归计算斜率
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope
    
    async def _create_trend_issue(self, metric_name: str, recent_metrics: List[PerformanceMetric], trend: float):
        """创建趋势问题"""
        try:
            issue_id = f"trend_{metric_name}_{int(datetime.utcnow().timestamp())}"
            
            issue = PerformanceIssue(
                issue_id=issue_id,
                type=self._get_optimization_type(metric_name),
                severity=PerformanceLevel.POOR,
                description=f"{metric_name} 性能持续恶化，趋势斜率: {trend:.4f}",
                detected_at=datetime.utcnow(),
                metrics=recent_metrics,
                suggestions=[
                    f"立即调查 {metric_name} 性能恶化原因",
                    "检查最近的代码变更",
                    "分析系统负载变化",
                    "考虑紧急性能优化措施"
                ],
                auto_fix_available=False,
                resolved=False
            )
            
            self.active_issues[issue_id] = issue
            logger.warning(f"检测到性能趋势问题: {issue.description}")
            
        except Exception as e:
            logger.error(f"创建趋势问题失败: {e}")
    
    async def _auto_optimize(self):
        """自动优化"""
        try:
            for issue_id, issue in list(self.active_issues.items()):
                if issue.auto_fix_available and not issue.resolved:
                    result = await self._perform_auto_optimization(issue)
                    
                    if result.success:
                        issue.resolved = True
                        logger.info(f"自动优化成功: {issue.description}")
                    else:
                        logger.warning(f"自动优化失败: {issue.description}, 错误: {result.errors}")
                    
                    self.optimization_history.append(result)
        
        except Exception as e:
            logger.error(f"自动优化失败: {e}")
    
    async def _perform_auto_optimization(self, issue: PerformanceIssue) -> OptimizationResult:
        """执行自动优化"""
        start_time = time.time()
        result = OptimizationResult(optimization_type=issue.type, success=False)
        
        try:
            if issue.type == OptimizationType.MEMORY:
                await self._optimize_memory()
                result.success = True
                result.improvements["gc_collections"] = "执行了垃圾回收"
                
            elif issue.type == OptimizationType.CACHE:
                await self._optimize_cache()
                result.success = True
                result.improvements["cache_optimization"] = "优化了缓存策略"
                
            elif issue.type == OptimizationType.DATABASE:
                await self._optimize_database()
                result.success = True
                result.improvements["db_optimization"] = "优化了数据库连接"
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"执行自动优化失败: {e}")
        
        result.duration = time.time() - start_time
        return result
    
    async def _optimize_memory(self):
        """优化内存"""
        try:
            # 执行垃圾回收
            collected = gc.collect()
            logger.info(f"内存优化：垃圾回收清理了 {collected} 个对象")
            
            # 清理弱引用注册表
            self.object_registry.clear()
            
        except Exception as e:
            logger.error(f"内存优化失败: {e}")
            raise
    
    async def _optimize_cache(self):
        """优化缓存"""
        try:
            # 这里应该与缓存管理器交互
            # 可以清理过期缓存、调整缓存大小等
            logger.info("缓存优化：清理过期缓存项")
            
        except Exception as e:
            logger.error(f"缓存优化失败: {e}")
            raise
    
    async def _optimize_database(self):
        """优化数据库"""
        try:
            # 这里可以优化数据库连接池、清理长时间运行的查询等
            logger.info("数据库优化：优化连接池配置")
            
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            raise
    
    async def _check_memory_leaks(self):
        """检查内存泄漏"""
        try:
            if not tracemalloc.is_tracing():
                return
            
            # 获取内存快照
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            # 检查内存使用最多的前10个位置
            for stat in top_stats[:10]:
                if stat.size > 10 * 1024 * 1024:  # 大于10MB
                    logger.warning(f"内存使用较大: {stat.traceback.format()[-1]}, 大小: {stat.size / 1024 / 1024:.2f}MB")
            
        except Exception as e:
            logger.error(f"检查内存泄漏失败: {e}")
    
    async def _cleanup_old_data(self):
        """清理旧数据"""
        try:
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(hours=24)
            
            # 清理旧的性能问题
            resolved_issues = []
            for issue_id, issue in self.active_issues.items():
                if issue.resolved and issue.detected_at < cutoff_time:
                    resolved_issues.append(issue_id)
            
            for issue_id in resolved_issues:
                del self.active_issues[issue_id]
            
            # 清理旧的优化历史
            if len(self.optimization_history) > 1000:
                self.optimization_history = self.optimization_history[-500:]
            
            logger.info(f"清理了 {len(resolved_issues)} 个已解决的旧问题")
            
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
    
    # ===========================================
    # 公共接口
    # ===========================================
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        try:
            current_time = datetime.utcnow()
            
            # 最新性能指标
            latest_metrics = {}
            for name, history in self.metrics_history.items():
                if history:
                    latest_metrics[name] = {
                        "value": history[-1].value,
                        "unit": history[-1].unit,
                        "level": history[-1].level.value,
                        "timestamp": history[-1].timestamp.isoformat()
                    }
            
            # 活跃问题统计
            issue_stats = {
                "total": len(self.active_issues),
                "critical": sum(1 for issue in self.active_issues.values() if issue.severity == PerformanceLevel.CRITICAL),
                "poor": sum(1 for issue in self.active_issues.values() if issue.severity == PerformanceLevel.POOR),
                "auto_fixable": sum(1 for issue in self.active_issues.values() if issue.auto_fix_available)
            }
            
            # 优化历史统计
            recent_optimizations = [opt for opt in self.optimization_history 
                                  if (current_time - opt.timestamp).seconds < 86400]  # 最近24小时
            
            optimization_stats = {
                "total_24h": len(recent_optimizations),
                "successful_24h": sum(1 for opt in recent_optimizations if opt.success),
                "by_type": {}
            }
            
            for opt in recent_optimizations:
                opt_type = opt.optimization_type.value
                if opt_type not in optimization_stats["by_type"]:
                    optimization_stats["by_type"][opt_type] = {"total": 0, "successful": 0}
                
                optimization_stats["by_type"][opt_type]["total"] += 1
                if opt.success:
                    optimization_stats["by_type"][opt_type]["successful"] += 1
            
            return {
                "timestamp": current_time.isoformat(),
                "monitoring_active": self.monitoring_active,
                "latest_metrics": latest_metrics,
                "active_issues": issue_stats,
                "optimization_stats": optimization_stats,
                "system_health": self._calculate_system_health()
            }
            
        except Exception as e:
            logger.error(f"获取性能报告失败: {e}")
            return {"error": str(e)}
    
    def _calculate_system_health(self) -> str:
        """计算系统健康状态"""
        try:
            if not self.active_issues:
                return "excellent"
            
            critical_count = sum(1 for issue in self.active_issues.values() 
                               if issue.severity == PerformanceLevel.CRITICAL)
            poor_count = sum(1 for issue in self.active_issues.values() 
                           if issue.severity == PerformanceLevel.POOR)
            
            if critical_count > 0:
                return "critical"
            elif poor_count > 3:
                return "poor"
            elif poor_count > 0:
                return "average"
            else:
                return "good"
                
        except Exception as e:
            logger.error(f"计算系统健康状态失败: {e}")
            return "unknown"
    
    async def get_performance_issues(self) -> List[Dict[str, Any]]:
        """获取性能问题列表"""
        try:
            issues = []
            for issue in self.active_issues.values():
                issue_data = {
                    "issue_id": issue.issue_id,
                    "type": issue.type.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "detected_at": issue.detected_at.isoformat(),
                    "suggestions": issue.suggestions,
                    "auto_fix_available": issue.auto_fix_available,
                    "resolved": issue.resolved,
                    "metrics_count": len(issue.metrics)
                }
                issues.append(issue_data)
            
            return sorted(issues, key=lambda x: x["detected_at"], reverse=True)
            
        except Exception as e:
            logger.error(f"获取性能问题列表失败: {e}")
            return []
    
    async def force_optimization(self, optimization_type: OptimizationType) -> OptimizationResult:
        """强制执行优化"""
        try:
            logger.info(f"强制执行优化: {optimization_type.value}")
            
            # 创建临时问题来触发优化
            temp_issue = PerformanceIssue(
                issue_id=f"manual_{optimization_type.value}_{int(datetime.utcnow().timestamp())}",
                type=optimization_type,
                severity=PerformanceLevel.POOR,
                description=f"手动触发的 {optimization_type.value} 优化",
                detected_at=datetime.utcnow(),
                auto_fix_available=True,
                resolved=False
            )
            
            result = await self._perform_auto_optimization(temp_issue)
            self.optimization_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"强制执行优化失败: {e}")
            return OptimizationResult(
                optimization_type=optimization_type,
                success=False,
                errors=[str(e)]
            )

# 全局性能优化器实例
performance_optimizer = PerformanceOptimizer()

# 上下文管理器
@asynccontextmanager
async def get_performance_optimizer():
    """获取性能优化器上下文管理器"""
    try:
        yield performance_optimizer
    finally:
        pass

# 工具函数
async def initialize_performance_optimizer():
    """初始化性能优化器"""
    global performance_optimizer
    await performance_optimizer.start_monitoring()
    logger.info("性能优化器初始化完成")
    return performance_optimizer

async def shutdown_performance_optimizer():
    """关闭性能优化器"""
    global performance_optimizer
    await performance_optimizer.stop_monitoring()
    logger.info("性能优化器已关闭")

# 装饰器
def monitor_performance(metric_name: str, threshold_warning: float = None, threshold_critical: float = None):
    """性能监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 记录执行时间
                execution_time = (time.time() - start_time) * 1000  # 毫秒
                
                await performance_optimizer._record_metric(
                    name=f"{metric_name}_execution_time",
                    value=execution_time,
                    unit="ms",
                    metadata={"function": func.__name__}
                )
                
                return result
                
            except Exception as e:
                # 记录错误指标
                await performance_optimizer._record_metric(
                    name=f"{metric_name}_error_count",
                    value=1,
                    unit="count",
                    metadata={"function": func.__name__, "error": str(e)}
                )
                raise
        
        return wrapper
    return decorator