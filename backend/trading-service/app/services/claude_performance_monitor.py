"""
Claude性能监控服务
- 收集API响应时间、成功率等性能指标
- 检测异常模式和成本超支
- 提供性能分析和优化建议
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning" 
    CRITICAL = "critical"


class MetricType(str, Enum):
    """指标类型"""
    RESPONSE_TIME = "response_time"
    SUCCESS_RATE = "success_rate"
    COST_USAGE = "cost_usage"
    REQUEST_RATE = "request_rate"
    ERROR_RATE = "error_rate"


@dataclass
class PerformanceMetric:
    """性能指标数据"""
    timestamp: datetime
    account_id: int
    user_id: int
    metric_type: MetricType
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """告警规则"""
    metric_type: MetricType
    threshold: float
    alert_level: AlertLevel
    window_seconds: int = 300  # 5分钟窗口
    description: str = ""


@dataclass
class PerformanceAlert:
    """性能告警"""
    timestamp: datetime
    alert_level: AlertLevel
    metric_type: MetricType
    account_id: int
    current_value: float
    threshold: float
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClaudePerformanceMonitor:
    """Claude性能监控器"""
    
    def __init__(self):
        # 内存中存储最近的指标数据（最多保存1000条/账号）
        self.metrics: Dict[int, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 性能统计缓存
        self.stats_cache: Dict[str, Dict] = {}
        self.cache_ttl = 60  # 缓存60秒
        self.last_cache_update: Dict[str, datetime] = {}
        
        # 告警规则
        self.alert_rules: List[AlertRule] = [
            AlertRule(
                metric_type=MetricType.RESPONSE_TIME,
                threshold=10.0,  # 10秒
                alert_level=AlertLevel.WARNING,
                description="响应时间过长"
            ),
            AlertRule(
                metric_type=MetricType.RESPONSE_TIME,
                threshold=20.0,  # 20秒
                alert_level=AlertLevel.CRITICAL,
                description="响应时间严重过长"
            ),
            AlertRule(
                metric_type=MetricType.SUCCESS_RATE,
                threshold=0.8,  # 80%成功率
                alert_level=AlertLevel.WARNING,
                description="成功率偏低"
            ),
            AlertRule(
                metric_type=MetricType.SUCCESS_RATE,
                threshold=0.5,  # 50%成功率
                alert_level=AlertLevel.CRITICAL,
                description="成功率严重偏低"
            ),
            AlertRule(
                metric_type=MetricType.COST_USAGE,
                threshold=50.0,  # $50/天
                alert_level=AlertLevel.WARNING,
                description="日成本较高"
            ),
            AlertRule(
                metric_type=MetricType.ERROR_RATE,
                threshold=0.1,  # 10%错误率
                alert_level=AlertLevel.WARNING,
                description="错误率偏高"
            ),
        ]
        
        # 活跃告警（避免重复告警）
        self.active_alerts: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=10)  # 告警冷却期
        
    def record_api_call(self, 
                       account_id: int,
                       user_id: int, 
                       response_time_ms: int,
                       success: bool,
                       cost_usd: float,
                       error_type: Optional[str] = None):
        """
        记录API调用性能指标
        
        Args:
            account_id: Claude账号ID
            user_id: 用户ID
            response_time_ms: 响应时间(毫秒)
            success: 是否成功
            cost_usd: API成本(美元)
            error_type: 错误类型(如果失败)
        """
        current_time = datetime.utcnow()
        
        # 记录响应时间
        response_time_seconds = response_time_ms / 1000.0
        self._add_metric(
            account_id, user_id, current_time,
            MetricType.RESPONSE_TIME, response_time_seconds,
            {"success": success, "error_type": error_type}
        )
        
        # 记录成功/失败状态
        success_value = 1.0 if success else 0.0
        self._add_metric(
            account_id, user_id, current_time,
            MetricType.SUCCESS_RATE, success_value,
            {"error_type": error_type}
        )
        
        # 记录成本
        self._add_metric(
            account_id, user_id, current_time,
            MetricType.COST_USAGE, cost_usd,
            {"success": success}
        )
        
        # 记录错误率
        error_value = 0.0 if success else 1.0
        self._add_metric(
            account_id, user_id, current_time,
            MetricType.ERROR_RATE, error_value,
            {"error_type": error_type}
        )
        
        # 检查告警条件
        asyncio.create_task(self._check_alerts(account_id))
        
    def _add_metric(self, account_id: int, user_id: int, timestamp: datetime,
                   metric_type: MetricType, value: float, metadata: Dict[str, Any]):
        """添加性能指标"""
        metric = PerformanceMetric(
            timestamp=timestamp,
            account_id=account_id,
            user_id=user_id,
            metric_type=metric_type,
            value=value,
            metadata=metadata
        )
        self.metrics[account_id].append(metric)
        
        # 清理缓存
        cache_key = f"{account_id}_{metric_type.value}"
        if cache_key in self.stats_cache:
            del self.stats_cache[cache_key]
        
    async def _check_alerts(self, account_id: int):
        """检查告警条件"""
        current_time = datetime.utcnow()
        
        for rule in self.alert_rules:
            alert_key = f"{account_id}_{rule.metric_type.value}_{rule.alert_level.value}"
            
            # 检查告警冷却期
            if alert_key in self.active_alerts:
                if current_time - self.active_alerts[alert_key] < self.alert_cooldown:
                    continue
            
            # 获取指标数据
            window_start = current_time - timedelta(seconds=rule.window_seconds)
            recent_metrics = [
                m for m in self.metrics[account_id] 
                if m.metric_type == rule.metric_type and m.timestamp >= window_start
            ]
            
            if not recent_metrics:
                continue
            
            # 计算当前值
            if rule.metric_type in [MetricType.SUCCESS_RATE, MetricType.ERROR_RATE]:
                current_value = statistics.mean([m.value for m in recent_metrics])
            elif rule.metric_type == MetricType.RESPONSE_TIME:
                current_value = statistics.mean([m.value for m in recent_metrics])
            elif rule.metric_type == MetricType.COST_USAGE:
                # 计算时间窗口内的总成本
                current_value = sum([m.value for m in recent_metrics])
            else:
                current_value = statistics.mean([m.value for m in recent_metrics])
            
            # 检查阈值
            trigger_alert = False
            if rule.metric_type == MetricType.SUCCESS_RATE:
                # 成功率低于阈值
                trigger_alert = current_value < rule.threshold
            else:
                # 其他指标高于阈值
                trigger_alert = current_value > rule.threshold
            
            if trigger_alert:
                alert = PerformanceAlert(
                    timestamp=current_time,
                    alert_level=rule.alert_level,
                    metric_type=rule.metric_type,
                    account_id=account_id,
                    current_value=current_value,
                    threshold=rule.threshold,
                    description=rule.description,
                    metadata={
                        "window_seconds": rule.window_seconds,
                        "sample_count": len(recent_metrics)
                    }
                )
                
                await self._handle_alert(alert)
                self.active_alerts[alert_key] = current_time
    
    async def _handle_alert(self, alert: PerformanceAlert):
        """处理告警"""
        log_level = logging.WARNING if alert.alert_level == AlertLevel.WARNING else logging.CRITICAL
        logger.log(
            log_level,
            f"🚨 性能告警: 账号{alert.account_id} {alert.description} - "
            f"{alert.metric_type.value}={alert.current_value:.3f} (阈值: {alert.threshold})"
        )
        
        # 这里可以添加更多告警处理逻辑，如发送邮件、Webhook等
    
    def get_account_performance_stats(self, account_id: int, 
                                    hours: int = 1) -> Dict[str, Any]:
        """
        获取账号性能统计
        
        Args:
            account_id: Claude账号ID
            hours: 统计时间窗口（小时）
            
        Returns:
            包含各项性能指标的统计信息
        """
        cache_key = f"{account_id}_stats_{hours}h"
        
        # 检查缓存
        if (cache_key in self.stats_cache and 
            cache_key in self.last_cache_update and
            (datetime.utcnow() - self.last_cache_update[cache_key]).seconds < self.cache_ttl):
            return self.stats_cache[cache_key]
        
        # 计算统计信息
        window_start = datetime.utcnow() - timedelta(hours=hours)
        account_metrics = [
            m for m in self.metrics[account_id] 
            if m.timestamp >= window_start
        ]
        
        if not account_metrics:
            stats = {
                "account_id": account_id,
                "time_window_hours": hours,
                "total_requests": 0,
                "avg_response_time": 0,
                "success_rate": 0,
                "error_rate": 0,
                "total_cost": 0,
                "requests_per_hour": 0
            }
        else:
            # 分类指标
            response_times = [m.value for m in account_metrics if m.metric_type == MetricType.RESPONSE_TIME]
            success_metrics = [m.value for m in account_metrics if m.metric_type == MetricType.SUCCESS_RATE]
            error_metrics = [m.value for m in account_metrics if m.metric_type == MetricType.ERROR_RATE]
            cost_metrics = [m.value for m in account_metrics if m.metric_type == MetricType.COST_USAGE]
            
            stats = {
                "account_id": account_id,
                "time_window_hours": hours,
                "total_requests": len(response_times),
                "avg_response_time": statistics.mean(response_times) if response_times else 0,
                "median_response_time": statistics.median(response_times) if response_times else 0,
                "p95_response_time": self._percentile(response_times, 95) if response_times else 0,
                "success_rate": statistics.mean(success_metrics) if success_metrics else 0,
                "error_rate": statistics.mean(error_metrics) if error_metrics else 0,
                "total_cost": sum(cost_metrics),
                "avg_cost_per_request": statistics.mean(cost_metrics) if cost_metrics else 0,
                "requests_per_hour": len(response_times) / hours if hours > 0 else 0,
                "last_update": datetime.utcnow().isoformat()
            }
        
        # 更新缓存
        self.stats_cache[cache_key] = stats
        self.last_cache_update[cache_key] = datetime.utcnow()
        
        return stats
    
    def get_system_performance_stats(self, hours: int = 1) -> Dict[str, Any]:
        """
        获取系统整体性能统计
        
        Args:
            hours: 统计时间窗口（小时）
            
        Returns:
            系统整体性能指标
        """
        cache_key = f"system_stats_{hours}h"
        
        # 检查缓存
        if (cache_key in self.stats_cache and 
            cache_key in self.last_cache_update and
            (datetime.utcnow() - self.last_cache_update[cache_key]).seconds < self.cache_ttl):
            return self.stats_cache[cache_key]
        
        window_start = datetime.utcnow() - timedelta(hours=hours)
        
        all_response_times = []
        all_success_metrics = []
        all_error_metrics = []
        all_cost_metrics = []
        active_accounts = set()
        
        for account_id, metrics in self.metrics.items():
            account_metrics = [m for m in metrics if m.timestamp >= window_start]
            
            if account_metrics:
                active_accounts.add(account_id)
                
                for metric in account_metrics:
                    if metric.metric_type == MetricType.RESPONSE_TIME:
                        all_response_times.append(metric.value)
                    elif metric.metric_type == MetricType.SUCCESS_RATE:
                        all_success_metrics.append(metric.value)
                    elif metric.metric_type == MetricType.ERROR_RATE:
                        all_error_metrics.append(metric.value)
                    elif metric.metric_type == MetricType.COST_USAGE:
                        all_cost_metrics.append(metric.value)
        
        stats = {
            "time_window_hours": hours,
            "active_accounts": len(active_accounts),
            "total_requests": len(all_response_times),
            "avg_response_time": statistics.mean(all_response_times) if all_response_times else 0,
            "median_response_time": statistics.median(all_response_times) if all_response_times else 0,
            "p95_response_time": self._percentile(all_response_times, 95) if all_response_times else 0,
            "p99_response_time": self._percentile(all_response_times, 99) if all_response_times else 0,
            "overall_success_rate": statistics.mean(all_success_metrics) if all_success_metrics else 0,
            "overall_error_rate": statistics.mean(all_error_metrics) if all_error_metrics else 0,
            "total_cost": sum(all_cost_metrics),
            "avg_cost_per_request": statistics.mean(all_cost_metrics) if all_cost_metrics else 0,
            "requests_per_hour": len(all_response_times) / hours if hours > 0 else 0,
            "cost_per_hour": sum(all_cost_metrics) / hours if hours > 0 else 0,
            "last_update": datetime.utcnow().isoformat()
        }
        
        # 更新缓存
        self.stats_cache[cache_key] = stats
        self.last_cache_update[cache_key] = datetime.utcnow()
        
        return stats
    
    def get_performance_trends(self, account_id: int, 
                              hours: int = 24, 
                              bucket_minutes: int = 60) -> Dict[str, List]:
        """
        获取性能趋势数据
        
        Args:
            account_id: Claude账号ID
            hours: 统计时间窗口（小时）
            bucket_minutes: 时间分桶大小（分钟）
            
        Returns:
            时间序列性能数据
        """
        window_start = datetime.utcnow() - timedelta(hours=hours)
        bucket_size = timedelta(minutes=bucket_minutes)
        
        # 创建时间桶
        buckets = []
        current_bucket_start = window_start
        while current_bucket_start < datetime.utcnow():
            buckets.append(current_bucket_start)
            current_bucket_start += bucket_size
        
        # 按时间桶聚合数据
        trend_data = {
            "timestamps": [bucket.isoformat() for bucket in buckets],
            "avg_response_time": [],
            "success_rate": [],
            "error_rate": [],
            "request_count": [],
            "total_cost": []
        }
        
        account_metrics = list(self.metrics[account_id])
        
        for bucket_start in buckets:
            bucket_end = bucket_start + bucket_size
            bucket_metrics = [
                m for m in account_metrics 
                if bucket_start <= m.timestamp < bucket_end
            ]
            
            if bucket_metrics:
                # 分类指标
                response_times = [m.value for m in bucket_metrics if m.metric_type == MetricType.RESPONSE_TIME]
                success_values = [m.value for m in bucket_metrics if m.metric_type == MetricType.SUCCESS_RATE]
                error_values = [m.value for m in bucket_metrics if m.metric_type == MetricType.ERROR_RATE]
                cost_values = [m.value for m in bucket_metrics if m.metric_type == MetricType.COST_USAGE]
                
                trend_data["avg_response_time"].append(
                    statistics.mean(response_times) if response_times else 0
                )
                trend_data["success_rate"].append(
                    statistics.mean(success_values) if success_values else 0
                )
                trend_data["error_rate"].append(
                    statistics.mean(error_values) if error_values else 0
                )
                trend_data["request_count"].append(len(response_times))
                trend_data["total_cost"].append(sum(cost_values))
            else:
                # 空桶
                trend_data["avg_response_time"].append(0)
                trend_data["success_rate"].append(0)
                trend_data["error_rate"].append(0)
                trend_data["request_count"].append(0)
                trend_data["total_cost"].append(0)
        
        return trend_data
    
    def get_optimization_recommendations(self, account_id: int) -> List[Dict[str, Any]]:
        """
        获取性能优化建议
        
        Args:
            account_id: Claude账号ID
            
        Returns:
            优化建议列表
        """
        stats = self.get_account_performance_stats(account_id, hours=24)
        recommendations = []
        
        # 响应时间优化
        if stats["avg_response_time"] > 5.0:
            recommendations.append({
                "type": "performance",
                "priority": "high" if stats["avg_response_time"] > 10.0 else "medium",
                "title": "响应时间优化",
                "description": f"平均响应时间{stats['avg_response_time']:.1f}秒，建议检查网络延迟或代理配置",
                "suggestions": [
                    "检查网络连接质量",
                    "优化代理服务器配置",
                    "考虑使用更快的API端点",
                    "实施请求缓存机制"
                ]
            })
        
        # 成功率优化
        if stats["success_rate"] < 0.9:
            recommendations.append({
                "type": "reliability",
                "priority": "high" if stats["success_rate"] < 0.8 else "medium",
                "title": "可靠性改善",
                "description": f"成功率{stats['success_rate']:.1%}，低于理想水平",
                "suggestions": [
                    "检查API密钥有效性",
                    "增加重试机制",
                    "实施断路器模式",
                    "监控账号限额使用情况"
                ]
            })
        
        # 成本优化
        if stats["avg_cost_per_request"] > 0.01:  # $0.01/请求
            recommendations.append({
                "type": "cost",
                "priority": "medium",
                "title": "成本优化",
                "description": f"平均每请求成本${stats['avg_cost_per_request']:.4f}，可进一步优化",
                "suggestions": [
                    "优化请求参数（减少max_tokens）",
                    "实施智能缓存减少重复请求",
                    "使用成本更低的模型版本",
                    "批处理相似请求"
                ]
            })
        
        # 请求频率优化
        if stats["requests_per_hour"] > 1000:
            recommendations.append({
                "type": "scaling",
                "priority": "low",
                "title": "扩展性优化",
                "description": f"每小时{stats['requests_per_hour']:.0f}个请求，建议考虑负载均衡",
                "suggestions": [
                    "增加更多Claude账号",
                    "实施请求负载均衡",
                    "考虑请求队列机制",
                    "监控API限额使用"
                ]
            })
        
        return recommendations
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = k - f
        
        if f == len(sorted_data) - 1:
            return sorted_data[f]
        else:
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
    
    def clear_old_metrics(self, hours: int = 48):
        """清理旧的性能指标数据"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        cleared_count = 0
        
        for account_id in self.metrics:
            old_count = len(self.metrics[account_id])
            # 过滤掉旧数据
            self.metrics[account_id] = deque(
                [m for m in self.metrics[account_id] if m.timestamp > cutoff_time],
                maxlen=1000
            )
            cleared_count += old_count - len(self.metrics[account_id])
        
        if cleared_count > 0:
            logger.info(f"🧹 清理了{cleared_count}条旧性能指标数据")
        
        # 清理缓存
        self.stats_cache.clear()
        self.last_cache_update.clear()


# 全局性能监控器实例
claude_performance_monitor = ClaudePerformanceMonitor()