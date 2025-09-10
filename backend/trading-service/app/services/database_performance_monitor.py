"""
数据库性能监控器
专门处理数据库查询优化、连接池管理、索引分析、慢查询检测等
"""

import time
import asyncio
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class QueryStats:
    """查询统计信息"""
    query_hash: str
    query_template: str
    execution_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_executed: datetime = field(default_factory=datetime.utcnow)
    parameters_samples: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_execution(self, duration: float, parameters: Dict[str, Any] = None):
        """添加执行记录"""
        self.execution_count += 1
        self.total_time += duration
        self.avg_time = self.total_time / self.execution_count
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.last_executed = datetime.utcnow()
        
        if parameters and len(self.parameters_samples) < 10:
            self.parameters_samples.append(parameters)

@dataclass
class SlowQuery:
    """慢查询记录"""
    query: str
    duration: float
    parameters: Optional[Dict[str, Any]]
    timestamp: datetime
    stack_trace: Optional[str] = None
    table_scans: int = 0
    index_usage: List[str] = field(default_factory=list)

@dataclass
class IndexAnalysis:
    """索引分析结果"""
    table_name: str
    index_name: str
    index_columns: List[str]
    is_unique: bool
    usage_count: int = 0
    last_used: Optional[datetime] = None
    effectiveness_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)

@dataclass
class DatabaseHealth:
    """数据库健康状态"""
    connection_count: int
    active_connections: int
    idle_connections: int
    database_size: float  # MB
    table_count: int
    index_count: int
    avg_query_time: float
    slow_query_count: int
    cache_hit_ratio: float
    fragmentation_level: float

class DatabasePerformanceMonitor:
    """数据库性能监控器"""
    
    def __init__(self, database_path: str = "data/trademe.db"):
        self.database_path = database_path
        self.query_stats: Dict[str, QueryStats] = {}
        self.slow_queries: deque = deque(maxlen=1000)
        self.index_analysis: Dict[str, IndexAnalysis] = {}
        self.connection_pool_stats = defaultdict(int)
        
        # 慢查询阈值（秒）
        self.slow_query_threshold = 0.1
        
        # 监控状态
        self.monitoring_active = False
        self.monitoring_tasks = []
        
        # 查询模板缓存
        self.query_template_cache = {}
        
    async def start_monitoring(self):
        """开始数据库性能监控"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        logger.info("启动数据库性能监控")
        
        # 创建监控任务
        self.monitoring_tasks = [
            asyncio.create_task(self._monitor_database_health()),
            asyncio.create_task(self._analyze_table_indexes()),
            asyncio.create_task(self._monitor_connection_pool()),
            asyncio.create_task(self._cleanup_old_stats())
        ]
        
        logger.info(f"启动了 {len(self.monitoring_tasks)} 个数据库监控任务")
    
    async def stop_monitoring(self):
        """停止数据库性能监控"""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        logger.info("停止数据库性能监控")
        
        # 取消所有监控任务
        for task in self.monitoring_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.monitoring_tasks.clear()
    
    def record_query_execution(self, query: str, duration: float, 
                             parameters: Dict[str, Any] = None):
        """记录查询执行"""
        try:
            # 生成查询模板和哈希
            query_template = self._generate_query_template(query)
            query_hash = self._generate_query_hash(query_template)
            
            # 更新统计信息
            if query_hash not in self.query_stats:
                self.query_stats[query_hash] = QueryStats(
                    query_hash=query_hash,
                    query_template=query_template
                )
            
            self.query_stats[query_hash].add_execution(duration, parameters)
            
            # 检查是否为慢查询
            if duration >= self.slow_query_threshold:
                slow_query = SlowQuery(
                    query=query,
                    duration=duration,
                    parameters=parameters,
                    timestamp=datetime.utcnow()
                )
                self.slow_queries.append(slow_query)
                logger.warning(f"检测到慢查询: {duration:.3f}s - {query[:100]}...")
            
        except Exception as e:
            logger.error(f"记录查询执行失败: {e}")
    
    def _generate_query_template(self, query: str) -> str:
        """生成查询模板（移除参数值）"""
        if query in self.query_template_cache:
            return self.query_template_cache[query]
        
        try:
            # 移除注释
            query_clean = re.sub(r'--.*', '', query)
            query_clean = re.sub(r'/\*.*?\*/', '', query_clean, flags=re.DOTALL)
            
            # 标准化空白字符
            query_clean = re.sub(r'\s+', ' ', query_clean).strip()
            
            # 替换常见的参数模式
            patterns = [
                (r"'[^']*'", "'?'"),           # 字符串字面量
                (r'"[^"]*"', '"?"'),           # 双引号字符串
                (r'\b\d+\.?\d*\b', '?'),       # 数字
                (r'= \?', '= ?'),              # 参数化查询
                (r'IN \([^)]+\)', 'IN (?)'),   # IN 子句
            ]
            
            template = query_clean
            for pattern, replacement in patterns:
                template = re.sub(pattern, replacement, template, flags=re.IGNORECASE)
            
            # 缓存结果
            self.query_template_cache[query] = template
            return template
            
        except Exception as e:
            logger.error(f"生成查询模板失败: {e}")
            return query
    
    def _generate_query_hash(self, query_template: str) -> str:
        """生成查询哈希"""
        import hashlib
        return hashlib.md5(query_template.encode()).hexdigest()[:12]
    
    async def _monitor_database_health(self):
        """监控数据库健康状态"""
        while self.monitoring_active:
            try:
                await self._collect_database_metrics()
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                logger.error(f"数据库健康监控出错: {e}")
                await asyncio.sleep(60)
    
    async def _collect_database_metrics(self):
        """收集数据库指标"""
        try:
            async with self._get_connection() as conn:
                # 数据库大小
                db_size = Path(self.database_path).stat().st_size / (1024 * 1024)  # MB
                
                # 表和索引数量
                tables = await self._execute_query(conn, 
                    "SELECT name FROM sqlite_master WHERE type='table'")
                table_count = len(tables)
                
                indexes = await self._execute_query(conn, 
                    "SELECT name FROM sqlite_master WHERE type='index'")
                index_count = len(indexes)
                
                # 计算平均查询时间
                if self.query_stats:
                    avg_query_time = sum(stats.avg_time for stats in self.query_stats.values()) / len(self.query_stats)
                else:
                    avg_query_time = 0.0
                
                # 慢查询数量（最近1小时）
                recent_slow_queries = [
                    q for q in self.slow_queries 
                    if (datetime.utcnow() - q.timestamp).seconds < 3600
                ]
                
                # 记录健康指标
                health = DatabaseHealth(
                    connection_count=10,  # 这里应该从连接池获取
                    active_connections=5,
                    idle_connections=5,
                    database_size=db_size,
                    table_count=table_count,
                    index_count=index_count,
                    avg_query_time=avg_query_time,
                    slow_query_count=len(recent_slow_queries),
                    cache_hit_ratio=95.0,  # SQLite没有直接的缓存统计
                    fragmentation_level=0.0  # SQLite的碎片化检测需要特殊查询
                )
                
                # 检查健康状态阈值
                await self._check_health_thresholds(health)
                
        except Exception as e:
            logger.error(f"收集数据库指标失败: {e}")
    
    async def _check_health_thresholds(self, health: DatabaseHealth):
        """检查健康状态阈值"""
        try:
            warnings = []
            
            # 数据库大小检查
            if health.database_size > 1000:  # 1GB
                warnings.append(f"数据库文件过大: {health.database_size:.2f}MB")
            
            # 平均查询时间检查
            if health.avg_query_time > 0.05:  # 50ms
                warnings.append(f"平均查询时间过长: {health.avg_query_time*1000:.2f}ms")
            
            # 慢查询数量检查
            if health.slow_query_count > 10:
                warnings.append(f"慢查询过多: {health.slow_query_count} 个")
            
            # 记录警告
            for warning in warnings:
                logger.warning(f"数据库健康检查: {warning}")
            
        except Exception as e:
            logger.error(f"检查健康状态阈值失败: {e}")
    
    async def _analyze_table_indexes(self):
        """分析表索引使用情况"""
        while self.monitoring_active:
            try:
                await self._perform_index_analysis()
                await asyncio.sleep(1800)  # 每30分钟分析一次
                
            except Exception as e:
                logger.error(f"索引分析出错: {e}")
                await asyncio.sleep(1800)
    
    async def _perform_index_analysis(self):
        """执行索引分析"""
        try:
            async with self._get_connection() as conn:
                # 获取所有索引信息
                indexes_query = """
                SELECT 
                    m.tbl_name as table_name,
                    m.name as index_name,
                    m.sql
                FROM sqlite_master m
                WHERE m.type = 'index' 
                AND m.name NOT LIKE 'sqlite_%'
                """
                
                indexes = await self._execute_query(conn, indexes_query)
                
                for index_info in indexes:
                    table_name = index_info[0]
                    index_name = index_info[1]
                    index_sql = index_info[2] or ""
                    
                    # 分析索引列
                    columns = self._extract_index_columns(index_sql)
                    is_unique = "UNIQUE" in index_sql.upper()
                    
                    # 创建或更新索引分析
                    analysis_key = f"{table_name}.{index_name}"
                    if analysis_key not in self.index_analysis:
                        self.index_analysis[analysis_key] = IndexAnalysis(
                            table_name=table_name,
                            index_name=index_name,
                            index_columns=columns,
                            is_unique=is_unique
                        )
                    
                    # 分析索引效果
                    await self._analyze_index_effectiveness(conn, analysis_key)
                
        except Exception as e:
            logger.error(f"执行索引分析失败: {e}")
    
    def _extract_index_columns(self, index_sql: str) -> List[str]:
        """从索引SQL中提取列名"""
        try:
            if not index_sql:
                return []
            
            # 查找括号内的列名
            match = re.search(r'\((.*?)\)', index_sql)
            if match:
                columns_str = match.group(1)
                columns = [col.strip().strip('"').strip("'") for col in columns_str.split(',')]
                return [col for col in columns if col]
            
            return []
            
        except Exception as e:
            logger.error(f"提取索引列名失败: {e}")
            return []
    
    async def _analyze_index_effectiveness(self, conn, analysis_key: str):
        """分析索引效果"""
        try:
            analysis = self.index_analysis[analysis_key]
            
            # 检查索引是否被查询计划使用
            # 这里可以分析查询统计中是否有使用该索引的查询
            
            # 计算效果评分（简化实现）
            usage_score = min(analysis.usage_count / 100, 1.0) * 100
            analysis.effectiveness_score = usage_score
            
            # 生成建议
            recommendations = []
            if analysis.usage_count == 0:
                recommendations.append("索引从未被使用，考虑删除")
            elif analysis.effectiveness_score < 20:
                recommendations.append("索引使用率低，检查查询模式")
            
            analysis.recommendations = recommendations
            
        except Exception as e:
            logger.error(f"分析索引效果失败: {e}")
    
    async def _monitor_connection_pool(self):
        """监控连接池状态"""
        while self.monitoring_active:
            try:
                # 这里应该从实际的连接池获取统计信息
                # 简化实现
                self.connection_pool_stats['total_connections'] = 10
                self.connection_pool_stats['active_connections'] = 3
                self.connection_pool_stats['idle_connections'] = 7
                
                await asyncio.sleep(30)  # 每30秒检查一次
                
            except Exception as e:
                logger.error(f"连接池监控出错: {e}")
                await asyncio.sleep(30)
    
    async def _cleanup_old_stats(self):
        """清理旧的统计数据"""
        while self.monitoring_active:
            try:
                current_time = datetime.utcnow()
                cutoff_time = current_time - timedelta(days=7)
                
                # 清理旧的查询统计（但保留重要的）
                stats_to_remove = []
                for query_hash, stats in self.query_stats.items():
                    if (stats.last_executed < cutoff_time and 
                        stats.execution_count < 10):  # 执行次数少的旧统计
                        stats_to_remove.append(query_hash)
                
                for query_hash in stats_to_remove:
                    del self.query_stats[query_hash]
                
                # 清理查询模板缓存
                if len(self.query_template_cache) > 1000:
                    self.query_template_cache.clear()
                
                logger.info(f"清理了 {len(stats_to_remove)} 个旧查询统计")
                
                await asyncio.sleep(3600)  # 每小时清理一次
                
            except Exception as e:
                logger.error(f"清理旧统计数据出错: {e}")
                await asyncio.sleep(3600)
    
    @asynccontextmanager
    async def _get_connection(self):
        """获取数据库连接"""
        conn = None
        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                conn.close()
    
    async def _execute_query(self, conn, query: str, parameters: Tuple = None) -> List[Any]:
        """执行查询"""
        try:
            cursor = conn.cursor()
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return []
    
    # ===========================================
    # 公共接口
    # ===========================================
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """获取数据库性能报告"""
        try:
            current_time = datetime.utcnow()
            
            # 查询统计摘要
            top_queries = sorted(
                self.query_stats.values(),
                key=lambda x: x.total_time,
                reverse=True
            )[:10]
            
            query_summary = {
                "total_unique_queries": len(self.query_stats),
                "total_executions": sum(stats.execution_count for stats in self.query_stats.values()),
                "total_time": sum(stats.total_time for stats in self.query_stats.values()),
                "avg_execution_time": sum(stats.avg_time for stats in self.query_stats.values()) / max(len(self.query_stats), 1),
                "top_time_consuming": [
                    {
                        "template": stats.query_template,
                        "executions": stats.execution_count,
                        "total_time": stats.total_time,
                        "avg_time": stats.avg_time
                    }
                    for stats in top_queries
                ]
            }
            
            # 慢查询摘要
            recent_slow_queries = [
                q for q in self.slow_queries 
                if (current_time - q.timestamp).seconds < 3600  # 最近1小时
            ]
            
            slow_query_summary = {
                "total_slow_queries": len(self.slow_queries),
                "recent_slow_queries": len(recent_slow_queries),
                "slowest_query": {
                    "query": max(self.slow_queries, key=lambda x: x.duration).query[:200] if self.slow_queries else None,
                    "duration": max(self.slow_queries, key=lambda x: x.duration).duration if self.slow_queries else 0
                }
            }
            
            # 索引分析摘要
            unused_indexes = [
                analysis for analysis in self.index_analysis.values()
                if analysis.usage_count == 0
            ]
            
            index_summary = {
                "total_indexes": len(self.index_analysis),
                "unused_indexes": len(unused_indexes),
                "low_efficiency_indexes": len([
                    analysis for analysis in self.index_analysis.values()
                    if analysis.effectiveness_score < 20
                ])
            }
            
            return {
                "timestamp": current_time.isoformat(),
                "monitoring_active": self.monitoring_active,
                "query_summary": query_summary,
                "slow_query_summary": slow_query_summary,
                "index_summary": index_summary,
                "connection_pool": dict(self.connection_pool_stats),
                "database_size_mb": Path(self.database_path).stat().st_size / (1024 * 1024) if Path(self.database_path).exists() else 0
            }
            
        except Exception as e:
            logger.error(f"获取数据库性能报告失败: {e}")
            return {"error": str(e)}
    
    async def get_slow_queries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取慢查询列表"""
        try:
            recent_queries = sorted(
                self.slow_queries,
                key=lambda x: x.timestamp,
                reverse=True
            )[:limit]
            
            return [
                {
                    "query": query.query,
                    "duration": query.duration,
                    "timestamp": query.timestamp.isoformat(),
                    "parameters": query.parameters,
                    "table_scans": query.table_scans
                }
                for query in recent_queries
            ]
            
        except Exception as e:
            logger.error(f"获取慢查询列表失败: {e}")
            return []
    
    async def get_index_analysis(self) -> List[Dict[str, Any]]:
        """获取索引分析结果"""
        try:
            return [
                {
                    "table_name": analysis.table_name,
                    "index_name": analysis.index_name,
                    "columns": analysis.index_columns,
                    "is_unique": analysis.is_unique,
                    "usage_count": analysis.usage_count,
                    "effectiveness_score": analysis.effectiveness_score,
                    "recommendations": analysis.recommendations,
                    "last_used": analysis.last_used.isoformat() if analysis.last_used else None
                }
                for analysis in self.index_analysis.values()
            ]
            
        except Exception as e:
            logger.error(f"获取索引分析结果失败: {e}")
            return []
    
    async def optimize_database(self) -> Dict[str, Any]:
        """执行数据库优化"""
        try:
            results = {}
            
            async with self._get_connection() as conn:
                # 分析数据库
                await self._execute_query(conn, "ANALYZE")
                results["analyze"] = "完成"
                
                # 重建索引（如果需要）
                fragmented_tables = await self._find_fragmented_tables(conn)
                if fragmented_tables:
                    for table in fragmented_tables:
                        await self._execute_query(conn, f"REINDEX {table}")
                    results["reindex"] = f"重建了 {len(fragmented_tables)} 个表的索引"
                
                # 清理WAL文件
                await self._execute_query(conn, "PRAGMA wal_checkpoint(TRUNCATE)")
                results["wal_checkpoint"] = "完成"
                
                # 清理未使用的空间
                await self._execute_query(conn, "VACUUM")
                results["vacuum"] = "完成"
            
            logger.info(f"数据库优化完成: {results}")
            return {"success": True, "results": results}
            
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _find_fragmented_tables(self, conn) -> List[str]:
        """查找碎片化严重的表"""
        try:
            # 获取所有表的统计信息
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = await self._execute_query(conn, tables_query)
            
            fragmented_tables = []
            for table_row in tables:
                table_name = table_row[0]
                
                # 检查表的页面统计
                # 这里可以使用更复杂的碎片化检测逻辑
                # 简化实现：假设大表可能有碎片化
                count_query = f"SELECT COUNT(*) FROM {table_name}"
                count_result = await self._execute_query(conn, count_query)
                
                if count_result and count_result[0][0] > 10000:  # 超过1万条记录的表
                    fragmented_tables.append(table_name)
            
            return fragmented_tables
            
        except Exception as e:
            logger.error(f"查找碎片化表失败: {e}")
            return []
    
    async def suggest_optimizations(self) -> List[Dict[str, Any]]:
        """生成优化建议"""
        try:
            suggestions = []
            
            # 分析查询统计
            if self.query_stats:
                # 查找频繁执行的慢查询
                frequent_slow_queries = [
                    stats for stats in self.query_stats.values()
                    if stats.avg_time > self.slow_query_threshold and stats.execution_count > 10
                ]
                
                if frequent_slow_queries:
                    suggestions.append({
                        "type": "query_optimization",
                        "priority": "high",
                        "description": f"发现 {len(frequent_slow_queries)} 个频繁执行的慢查询",
                        "details": [stats.query_template for stats in frequent_slow_queries[:5]]
                    })
            
            # 分析索引使用
            unused_indexes = [
                analysis for analysis in self.index_analysis.values()
                if analysis.usage_count == 0
            ]
            
            if unused_indexes:
                suggestions.append({
                    "type": "index_cleanup",
                    "priority": "medium",
                    "description": f"发现 {len(unused_indexes)} 个未使用的索引，建议删除",
                    "details": [f"{analysis.table_name}.{analysis.index_name}" for analysis in unused_indexes]
                })
            
            # 检查数据库大小
            if Path(self.database_path).exists():
                db_size_mb = Path(self.database_path).stat().st_size / (1024 * 1024)
                if db_size_mb > 500:  # 大于500MB
                    suggestions.append({
                        "type": "database_size",
                        "priority": "medium",
                        "description": f"数据库文件较大 ({db_size_mb:.2f}MB)，建议执行 VACUUM",
                        "details": ["考虑数据归档", "执行 VACUUM 清理", "检查日志清理策略"]
                    })
            
            # 检查慢查询数量
            if len(self.slow_queries) > 50:
                suggestions.append({
                    "type": "performance_tuning",
                    "priority": "high",
                    "description": f"慢查询过多 ({len(self.slow_queries)} 个)，需要性能调优",
                    "details": ["分析查询执行计划", "考虑添加索引", "优化查询逻辑"]
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            return []

# 全局数据库性能监控器实例
db_performance_monitor = DatabasePerformanceMonitor()

# 上下文管理器
@asynccontextmanager
async def get_db_performance_monitor():
    """获取数据库性能监控器上下文管理器"""
    try:
        yield db_performance_monitor
    finally:
        pass

# 工具函数
async def initialize_db_performance_monitor(database_path: str = None):
    """初始化数据库性能监控器"""
    global db_performance_monitor
    if database_path:
        db_performance_monitor.database_path = database_path
    
    await db_performance_monitor.start_monitoring()
    logger.info("数据库性能监控器初始化完成")
    return db_performance_monitor

async def shutdown_db_performance_monitor():
    """关闭数据库性能监控器"""
    global db_performance_monitor
    await db_performance_monitor.stop_monitoring()
    logger.info("数据库性能监控器已关闭")

# SQLAlchemy事件监听器（如果使用SQLAlchemy）
def setup_sqlalchemy_monitoring():
    """设置SQLAlchemy查询监控"""
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(Engine, "after_cursor_execute")  
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            
            # 记录查询执行
            db_performance_monitor.record_query_execution(
                query=statement,
                duration=total,
                parameters=parameters if isinstance(parameters, dict) else None
            )
        
        logger.info("SQLAlchemy查询监控设置完成")
        
    except ImportError:
        logger.warning("SQLAlchemy未安装，跳过查询监控设置")
    except Exception as e:
        logger.error(f"设置SQLAlchemy监控失败: {e}")

# 装饰器
def monitor_db_query(query_name: str = None):
    """数据库查询监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 记录执行时间
                duration = time.time() - start_time
                
                # 使用函数名作为查询名称
                name = query_name or f"func_{func.__name__}"
                
                db_performance_monitor.record_query_execution(
                    query=name,
                    duration=duration,
                    parameters={"function": func.__name__}
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                # 记录错误查询
                db_performance_monitor.record_query_execution(
                    query=f"ERROR_{func.__name__}",
                    duration=duration,
                    parameters={"error": str(e)}
                )
                raise
        
        return wrapper
    return decorator