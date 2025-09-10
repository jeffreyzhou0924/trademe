"""
统一性能管理器
整合所有性能优化组件，提供统一的性能监控、分析和优化服务
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from .performance_optimizer import (
    PerformanceOptimizer, performance_optimizer, 
    OptimizationType, PerformanceLevel
)
from .database_performance_monitor import (
    DatabasePerformanceMonitor, db_performance_monitor
)
from .integrated_cache_manager import cache_manager

logger = logging.getLogger(__name__)

class SystemComponent(Enum):
    """系统组件"""
    APPLICATION = "application"
    DATABASE = "database"
    CACHE = "cache"
    NETWORK = "network"
    STORAGE = "storage"

class PerformanceAction(Enum):
    """性能操作"""
    MONITOR = "monitor"
    ANALYZE = "analyze"
    OPTIMIZE = "optimize"
    ALERT = "alert"
    REPORT = "report"

@dataclass
class SystemPerformanceReport:
    """系统性能报告"""
    timestamp: datetime
    overall_health: str
    component_health: Dict[str, str]
    performance_metrics: Dict[str, Any]
    active_issues: List[Dict[str, Any]]
    optimization_recommendations: List[Dict[str, Any]]
    recent_optimizations: List[Dict[str, Any]]
    system_resources: Dict[str, Any]

@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_id: str
    severity: PerformanceLevel
    component: SystemComponent
    message: str
    detected_at: datetime
    metrics: Dict[str, Any]
    auto_resolved: bool = False
    resolved_at: Optional[datetime] = None

class UnifiedPerformanceManager:
    """统一性能管理器"""
    
    def __init__(self):
        self.app_optimizer = performance_optimizer
        self.db_monitor = db_performance_monitor
        self.cache_manager = cache_manager
        
        # 性能告警
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = []
        
        # 管理状态
        self.is_running = False
        self.management_tasks: List[asyncio.Task] = []
        
        # 性能阈值
        self.alert_thresholds = self._init_alert_thresholds()
        
        # 优化历史
        self.optimization_history: List[Dict[str, Any]] = []
    
    def _init_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """初始化告警阈值"""
        return {
            "system_cpu": {"warning": 80.0, "critical": 95.0},
            "system_memory": {"warning": 85.0, "critical": 95.0},
            "database_size": {"warning": 1000.0, "critical": 2000.0},  # MB
            "slow_queries": {"warning": 10, "critical": 50},  # 数量
            "api_response_time": {"warning": 1000.0, "critical": 3000.0},  # ms
            "cache_hit_rate": {"warning": 70.0, "critical": 50.0},  # %
            "connection_pool": {"warning": 80, "critical": 95},  # %使用率
            "disk_usage": {"warning": 85.0, "critical": 95.0}
        }
    
    async def start(self):
        """启动统一性能管理器"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("启动统一性能管理器")
        
        try:
            # 启动各个组件的监控
            await self.app_optimizer.start_monitoring()
            await self.db_monitor.start_monitoring()
            
            # 初始化缓存管理器（如果还未初始化）
            if not self.cache_manager.is_initialized:
                await self.cache_manager.initialize()
            
            # 启动管理任务
            self.management_tasks = [
                asyncio.create_task(self._performance_coordination_task()),
                asyncio.create_task(self._alert_management_task()),
                asyncio.create_task(self._auto_optimization_coordination()),
                asyncio.create_task(self._system_health_monitoring()),
                asyncio.create_task(self._performance_reporting_task())
            ]
            
            logger.info(f"启动了 {len(self.management_tasks)} 个性能管理任务")
            
        except Exception as e:
            logger.error(f"启动统一性能管理器失败: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """停止统一性能管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("停止统一性能管理器")
        
        try:
            # 取消管理任务
            for task in self.management_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            self.management_tasks.clear()
            
            # 停止各个组件的监控
            await self.app_optimizer.stop_monitoring()
            await self.db_monitor.stop_monitoring()
            
        except Exception as e:
            logger.error(f"停止统一性能管理器失败: {e}")
    
    async def _performance_coordination_task(self):
        """性能协调任务"""
        while self.is_running:
            try:
                # 协调各个组件的性能监控
                await self._coordinate_performance_monitoring()
                
                # 每2分钟执行一次
                await asyncio.sleep(120)
                
            except Exception as e:
                logger.error(f"性能协调任务出错: {e}")
                await asyncio.sleep(120)
    
    async def _coordinate_performance_monitoring(self):
        """协调性能监控"""
        try:
            # 获取各组件的性能数据
            app_report = await self.app_optimizer.get_performance_report()
            db_report = await self.db_monitor.get_performance_report()
            cache_health = await self.cache_manager.get_cache_health()
            
            # 分析性能数据的关联性
            await self._analyze_cross_component_performance(app_report, db_report, cache_health)
            
        except Exception as e:
            logger.error(f"协调性能监控失败: {e}")
    
    async def _analyze_cross_component_performance(self, app_report: Dict, db_report: Dict, cache_health: Dict):
        """分析跨组件性能关联"""
        try:
            # 分析数据库性能与应用性能的关联
            if (db_report.get("slow_query_summary", {}).get("recent_slow_queries", 0) > 5 and
                app_report.get("system_health") in ["poor", "critical"]):
                
                await self._create_correlation_alert(
                    "database_app_correlation",
                    "数据库慢查询可能导致应用性能下降",
                    PerformanceLevel.POOR,
                    SystemComponent.DATABASE
                )
            
            # 分析缓存性能与应用性能的关联
            if (cache_health.get("status") != "healthy" and
                app_report.get("latest_metrics", {}).get("api_response_time", {}).get("level") == "poor"):
                
                await self._create_correlation_alert(
                    "cache_app_correlation",
                    "缓存问题可能导致API响应时间过长",
                    PerformanceLevel.POOR,
                    SystemComponent.CACHE
                )
            
        except Exception as e:
            logger.error(f"分析跨组件性能关联失败: {e}")
    
    async def _alert_management_task(self):
        """告警管理任务"""
        while self.is_running:
            try:
                # 处理告警
                await self._process_alerts()
                
                # 清理旧告警
                await self._cleanup_old_alerts()
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"告警管理任务出错: {e}")
                await asyncio.sleep(60)
    
    async def _process_alerts(self):
        """处理告警"""
        try:
            current_time = datetime.utcnow()
            
            # 检查是否有告警需要升级
            for alert_id, alert in list(self.active_alerts.items()):
                if (current_time - alert.detected_at).seconds > 1800:  # 30分钟未解决
                    if alert.severity == PerformanceLevel.POOR:
                        alert.severity = PerformanceLevel.CRITICAL
                        logger.warning(f"告警升级为严重: {alert.message}")
            
            # 检查是否有告警可以自动解决
            await self._check_auto_resolve_alerts()
            
        except Exception as e:
            logger.error(f"处理告警失败: {e}")
    
    async def _check_auto_resolve_alerts(self):
        """检查自动解决的告警"""
        try:
            current_time = datetime.utcnow()
            resolved_alerts = []
            
            for alert_id, alert in self.active_alerts.items():
                # 检查告警条件是否已解决
                if await self._is_alert_resolved(alert):
                    alert.auto_resolved = True
                    alert.resolved_at = current_time
                    resolved_alerts.append(alert_id)
                    
                    # 移到历史记录
                    self.alert_history.append(alert)
                    logger.info(f"告警自动解决: {alert.message}")
            
            # 清理已解决的告警
            for alert_id in resolved_alerts:
                del self.active_alerts[alert_id]
            
        except Exception as e:
            logger.error(f"检查自动解决告警失败: {e}")
    
    async def _is_alert_resolved(self, alert: PerformanceAlert) -> bool:
        """检查告警是否已解决"""
        try:
            # 根据告警类型检查是否已解决
            # 这里需要根据具体的告警类型实现检查逻辑
            return False  # 简化实现
            
        except Exception as e:
            logger.error(f"检查告警解决状态失败: {e}")
            return False
    
    async def _auto_optimization_coordination(self):
        """自动优化协调"""
        while self.is_running:
            try:
                # 协调自动优化
                await self._coordinate_optimizations()
                
                # 每5分钟执行一次
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"自动优化协调出错: {e}")
                await asyncio.sleep(300)
    
    async def _coordinate_optimizations(self):
        """协调优化操作"""
        try:
            # 检查是否需要协调优化
            active_issues = await self.app_optimizer.get_performance_issues()
            db_suggestions = await self.db_monitor.suggest_optimizations()
            
            # 按优先级排序优化建议
            all_suggestions = []
            
            # 添加应用层优化建议
            for issue in active_issues:
                if issue.get("severity") == "critical":
                    all_suggestions.append({
                        "priority": 1,
                        "type": "application",
                        "action": f"fix_issue_{issue['issue_id']}",
                        "description": issue["description"]
                    })
            
            # 添加数据库优化建议
            for suggestion in db_suggestions:
                priority = 1 if suggestion.get("priority") == "high" else 2
                all_suggestions.append({
                    "priority": priority,
                    "type": "database",
                    "action": suggestion["type"],
                    "description": suggestion["description"]
                })
            
            # 执行高优先级优化
            high_priority_suggestions = [s for s in all_suggestions if s["priority"] == 1]
            if high_priority_suggestions:
                await self._execute_coordinated_optimization(high_priority_suggestions[:3])  # 最多3个
            
        except Exception as e:
            logger.error(f"协调优化操作失败: {e}")
    
    async def _execute_coordinated_optimization(self, suggestions: List[Dict[str, Any]]):
        """执行协调优化"""
        try:
            results = []
            
            for suggestion in suggestions:
                start_time = time.time()
                success = False
                error = None
                
                try:
                    if suggestion["type"] == "application":
                        # 执行应用层优化
                        opt_type = OptimizationType.MEMORY  # 根据建议确定类型
                        result = await self.app_optimizer.force_optimization(opt_type)
                        success = result.success
                        
                    elif suggestion["type"] == "database":
                        # 执行数据库优化
                        result = await self.db_monitor.optimize_database()
                        success = result.get("success", False)
                    
                except Exception as e:
                    error = str(e)
                
                results.append({
                    "suggestion": suggestion,
                    "success": success,
                    "error": error,
                    "duration": time.time() - start_time,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # 记录优化历史
            self.optimization_history.append({
                "type": "coordinated",
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"协调优化完成: {len([r for r in results if r['success']])}/{len(results)} 成功")
            
        except Exception as e:
            logger.error(f"执行协调优化失败: {e}")
    
    async def _system_health_monitoring(self):
        """系统健康监控"""
        while self.is_running:
            try:
                # 监控系统整体健康状态
                health_status = await self._calculate_system_health()
                
                # 如果健康状态不佳，创建告警
                if health_status["overall_score"] < 70:
                    await self._create_health_alert(health_status)
                
                # 每3分钟检查一次
                await asyncio.sleep(180)
                
            except Exception as e:
                logger.error(f"系统健康监控出错: {e}")
                await asyncio.sleep(180)
    
    async def _calculate_system_health(self) -> Dict[str, Any]:
        """计算系统健康状态"""
        try:
            # 获取各组件健康状态
            app_report = await self.app_optimizer.get_performance_report()
            db_report = await self.db_monitor.get_performance_report()
            cache_health = await self.cache_manager.get_cache_health()
            
            # 计算健康分数（0-100）
            scores = {
                "application": self._calculate_app_health_score(app_report),
                "database": self._calculate_db_health_score(db_report),
                "cache": self._calculate_cache_health_score(cache_health)
            }
            
            # 总体健康分数
            overall_score = sum(scores.values()) / len(scores)
            
            return {
                "overall_score": overall_score,
                "component_scores": scores,
                "health_level": self._get_health_level(overall_score),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"计算系统健康状态失败: {e}")
            return {"overall_score": 50, "error": str(e)}
    
    def _calculate_app_health_score(self, app_report: Dict[str, Any]) -> float:
        """计算应用健康分数"""
        try:
            base_score = 100.0
            
            # 根据系统健康状态扣分
            health_status = app_report.get("system_health", "good")
            if health_status == "critical":
                base_score -= 50
            elif health_status == "poor":
                base_score -= 30
            elif health_status == "average":
                base_score -= 15
            
            # 根据活跃问题数量扣分
            active_issues = app_report.get("active_issues", {})
            critical_count = active_issues.get("critical", 0)
            poor_count = active_issues.get("poor", 0)
            
            base_score -= critical_count * 10
            base_score -= poor_count * 5
            
            return max(0.0, base_score)
            
        except Exception as e:
            logger.error(f"计算应用健康分数失败: {e}")
            return 50.0
    
    def _calculate_db_health_score(self, db_report: Dict[str, Any]) -> float:
        """计算数据库健康分数"""
        try:
            base_score = 100.0
            
            # 根据慢查询数量扣分
            slow_queries = db_report.get("slow_query_summary", {}).get("recent_slow_queries", 0)
            if slow_queries > 20:
                base_score -= 40
            elif slow_queries > 10:
                base_score -= 20
            elif slow_queries > 5:
                base_score -= 10
            
            # 根据数据库大小扣分
            db_size = db_report.get("database_size_mb", 0)
            if db_size > 2000:  # 2GB
                base_score -= 20
            elif db_size > 1000:  # 1GB
                base_score -= 10
            
            return max(0.0, base_score)
            
        except Exception as e:
            logger.error(f"计算数据库健康分数失败: {e}")
            return 50.0
    
    def _calculate_cache_health_score(self, cache_health: Dict[str, Any]) -> float:
        """计算缓存健康分数"""
        try:
            if cache_health.get("status") == "healthy":
                return 100.0
            elif cache_health.get("status") == "not_initialized":
                return 70.0
            else:
                return 30.0
                
        except Exception as e:
            logger.error(f"计算缓存健康分数失败: {e}")
            return 50.0
    
    def _get_health_level(self, score: float) -> str:
        """获取健康等级"""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "average"
        elif score >= 40:
            return "poor"
        else:
            return "critical"
    
    async def _performance_reporting_task(self):
        """性能报告任务"""
        while self.is_running:
            try:
                # 生成定期性能报告
                report = await self.generate_comprehensive_report()
                
                # 记录报告（这里可以发送到监控系统）
                logger.info(f"生成性能报告: 总体健康 {report.overall_health}")
                
                # 每小时生成一次报告
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"性能报告任务出错: {e}")
                await asyncio.sleep(3600)
    
    async def _create_correlation_alert(self, alert_id: str, message: str, 
                                      severity: PerformanceLevel, component: SystemComponent):
        """创建关联告警"""
        try:
            if alert_id in self.active_alerts:
                return  # 告警已存在
            
            alert = PerformanceAlert(
                alert_id=alert_id,
                severity=severity,
                component=component,
                message=message,
                detected_at=datetime.utcnow(),
                metrics={}
            )
            
            self.active_alerts[alert_id] = alert
            logger.warning(f"创建关联告警: {message}")
            
        except Exception as e:
            logger.error(f"创建关联告警失败: {e}")
    
    async def _create_health_alert(self, health_status: Dict[str, Any]):
        """创建健康告警"""
        try:
            score = health_status["overall_score"]
            alert_id = f"system_health_{int(datetime.utcnow().timestamp())}"
            
            if alert_id.split('_')[0:2] in [alert.alert_id.split('_')[0:2] for alert in self.active_alerts.values()]:
                return  # 避免重复告警
            
            severity = PerformanceLevel.CRITICAL if score < 40 else PerformanceLevel.POOR
            
            alert = PerformanceAlert(
                alert_id=alert_id,
                severity=severity,
                component=SystemComponent.APPLICATION,
                message=f"系统健康状态不佳，评分: {score:.1f}",
                detected_at=datetime.utcnow(),
                metrics=health_status
            )
            
            self.active_alerts[alert_id] = alert
            logger.warning(f"创建健康告警: 系统健康评分 {score:.1f}")
            
        except Exception as e:
            logger.error(f"创建健康告警失败: {e}")
    
    async def _cleanup_old_alerts(self):
        """清理旧告警"""
        try:
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(hours=24)
            
            # 清理历史告警
            self.alert_history = [
                alert for alert in self.alert_history
                if alert.detected_at > cutoff_time
            ]
            
            # 限制历史告警数量
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-500:]
            
        except Exception as e:
            logger.error(f"清理旧告警失败: {e}")
    
    # ===========================================
    # 公共接口
    # ===========================================
    
    async def generate_comprehensive_report(self) -> SystemPerformanceReport:
        """生成综合性能报告"""
        try:
            current_time = datetime.utcnow()
            
            # 获取各组件报告
            app_report = await self.app_optimizer.get_performance_report()
            db_report = await self.db_monitor.get_performance_report()
            cache_health = await self.cache_manager.get_cache_health()
            cache_stats = await self.cache_manager.get_cache_statistics()
            
            # 计算整体健康状态
            health_status = await self._calculate_system_health()
            
            # 组合性能指标
            performance_metrics = {
                "application": app_report.get("latest_metrics", {}),
                "database": {
                    "query_summary": db_report.get("query_summary", {}),
                    "slow_queries": db_report.get("slow_query_summary", {}),
                    "size_mb": db_report.get("database_size_mb", 0)
                },
                "cache": {
                    "health": cache_health,
                    "statistics": cache_stats
                }
            }
            
            # 活跃问题
            app_issues = await self.app_optimizer.get_performance_issues()
            db_suggestions = await self.db_monitor.suggest_optimizations()
            
            active_issues = []
            active_issues.extend([
                {
                    "component": "application",
                    "type": issue.get("type", "unknown"),
                    "severity": issue.get("severity", "unknown"),
                    "description": issue.get("description", "")
                }
                for issue in app_issues
            ])
            
            # 优化建议
            optimization_recommendations = []
            optimization_recommendations.extend([
                {
                    "component": "database",
                    "type": suggestion.get("type", ""),
                    "priority": suggestion.get("priority", "medium"),
                    "description": suggestion.get("description", "")
                }
                for suggestion in db_suggestions
            ])
            
            # 最近的优化操作
            recent_optimizations = self.optimization_history[-10:] if self.optimization_history else []
            
            # 系统资源（从应用报告中获取）
            system_resources = app_report.get("latest_metrics", {})
            
            return SystemPerformanceReport(
                timestamp=current_time,
                overall_health=health_status.get("health_level", "unknown"),
                component_health={
                    "application": app_report.get("system_health", "unknown"),
                    "database": "good" if db_report.get("monitoring_active", False) else "unknown",
                    "cache": cache_health.get("status", "unknown")
                },
                performance_metrics=performance_metrics,
                active_issues=active_issues,
                optimization_recommendations=optimization_recommendations,
                recent_optimizations=recent_optimizations,
                system_resources=system_resources
            )
            
        except Exception as e:
            logger.error(f"生成综合性能报告失败: {e}")
            return SystemPerformanceReport(
                timestamp=datetime.utcnow(),
                overall_health="unknown",
                component_health={},
                performance_metrics={"error": str(e)},
                active_issues=[],
                optimization_recommendations=[],
                recent_optimizations=[],
                system_resources={}
            )
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        try:
            return [
                {
                    "alert_id": alert.alert_id,
                    "severity": alert.severity.value,
                    "component": alert.component.value,
                    "message": alert.message,
                    "detected_at": alert.detected_at.isoformat(),
                    "metrics": alert.metrics,
                    "auto_resolved": alert.auto_resolved
                }
                for alert in self.active_alerts.values()
            ]
            
        except Exception as e:
            logger.error(f"获取活跃告警失败: {e}")
            return []
    
    async def force_system_optimization(self) -> Dict[str, Any]:
        """强制系统优化"""
        try:
            logger.info("开始强制系统优化")
            results = {}
            
            # 应用层优化
            app_result = await self.app_optimizer.force_optimization(OptimizationType.MEMORY)
            results["application"] = {
                "success": app_result.success,
                "improvements": app_result.improvements,
                "errors": app_result.errors
            }
            
            # 数据库优化
            db_result = await self.db_monitor.optimize_database()
            results["database"] = db_result
            
            # 缓存优化
            if self.cache_manager.is_initialized:
                cache_result = {"success": True, "message": "缓存系统运行正常"}
            else:
                cache_result = {"success": False, "message": "缓存系统未初始化"}
            results["cache"] = cache_result
            
            # 记录优化历史
            optimization_record = {
                "type": "manual_system_optimization",
                "results": results,
                "timestamp": datetime.utcnow().isoformat(),
                "triggered_by": "manual"
            }
            self.optimization_history.append(optimization_record)
            
            logger.info("强制系统优化完成")
            return {"success": True, "results": results}
            
        except Exception as e:
            logger.error(f"强制系统优化失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_optimization_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取优化历史"""
        try:
            return self.optimization_history[-limit:] if self.optimization_history else []
            
        except Exception as e:
            logger.error(f"获取优化历史失败: {e}")
            return []
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            return {
                "unified_manager": {
                    "running": self.is_running,
                    "active_alerts": len(self.active_alerts),
                    "optimization_history": len(self.optimization_history)
                },
                "components": {
                    "app_optimizer": self.app_optimizer.monitoring_active,
                    "db_monitor": self.db_monitor.monitoring_active,
                    "cache_manager": self.cache_manager.is_initialized
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {"error": str(e)}

# 全局统一性能管理器实例
unified_performance_manager = UnifiedPerformanceManager()

# 上下文管理器
@asynccontextmanager
async def get_unified_performance_manager():
    """获取统一性能管理器上下文管理器"""
    try:
        yield unified_performance_manager
    finally:
        pass

# 工具函数
async def initialize_unified_performance_manager():
    """初始化统一性能管理器"""
    global unified_performance_manager
    await unified_performance_manager.start()
    logger.info("统一性能管理器初始化完成")
    return unified_performance_manager

async def shutdown_unified_performance_manager():
    """关闭统一性能管理器"""
    global unified_performance_manager
    await unified_performance_manager.stop()
    logger.info("统一性能管理器已关闭")