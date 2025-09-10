"""
策略运行时监控服务 - Strategy Runtime Monitor

功能特性:
- 实时性能监控
- 异常检测和告警
- 资源使用监控
- 执行质量分析
- 自动化健康检查
- 智能建议生成
"""

import asyncio
import json
import time
import psutil
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from loguru import logger

from app.models.strategy import Strategy
from app.models.trade import Trade
from app.services.strategy_executor_service import strategy_executor_service, StrategyExecutionStatus
from app.services.websocket_manager import websocket_manager


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PerformanceMetric(Enum):
    """性能指标类型"""
    PNL = "pnl"
    WIN_RATE = "win_rate"
    DRAWDOWN = "drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    EXECUTION_TIME = "execution_time"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"


@dataclass
class Alert:
    """告警信息"""
    alert_id: str
    strategy_id: int
    user_id: int
    level: AlertLevel
    metric: PerformanceMetric
    message: str
    current_value: float
    threshold_value: float
    recommendation: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    strategy_id: int
    timestamp: datetime
    pnl: float
    win_rate: float
    max_drawdown: float
    total_trades: int
    execution_time_avg: float
    error_count: int
    memory_usage_mb: float
    cpu_usage_percent: float


@dataclass
class MonitoringRule:
    """监控规则"""
    rule_id: str
    strategy_id: Optional[int]  # None表示全局规则
    metric: PerformanceMetric
    condition: str  # 'greater_than', 'less_than', 'equals', 'change_rate'
    threshold: float
    duration_minutes: int  # 持续时间才触发
    alert_level: AlertLevel
    enabled: bool = True
    cooldown_minutes: int = 30  # 冷却时间，避免重复告警


class StrategyRuntimeMonitor:
    """策略运行时监控服务"""
    
    def __init__(self):
        self.logger = logger.bind(service="StrategyRuntimeMonitor")
        
        # 监控数据存储
        self.performance_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alert_history: List[Alert] = []
        self.active_alerts: Dict[str, Alert] = {}
        
        # 监控规则
        self.monitoring_rules: Dict[str, MonitoringRule] = {}
        
        # 性能基线
        self.performance_baselines: Dict[int, Dict[str, float]] = {}
        
        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None
        self._alert_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 配置参数
        self.config = {
            'monitor_interval': 10,      # 监控间隔(秒)
            'alert_check_interval': 30,  # 告警检查间隔(秒)
            'cleanup_interval': 3600,    # 清理间隔(秒)
            'max_alerts_per_strategy': 50,
            'performance_window_hours': 24,
            'anomaly_detection_sensitivity': 2.0,  # 异常检测敏感度
        }
        
        # 回调函数
        self.alert_callbacks: List[Callable] = []
        self.performance_callbacks: List[Callable] = []
        
        # 初始化默认监控规则
        self._initialize_default_rules()
    
    async def start_monitor(self):
        """启动监控服务"""
        if self._running:
            return
            
        self._running = True
        self.logger.info("启动策略运行时监控服务")
        
        # 启动监控任务
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        self._alert_task = asyncio.create_task(self._alert_processing_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("策略运行时监控服务启动完成")
    
    async def stop_monitor(self):
        """停止监控服务"""
        if not self._running:
            return
            
        self.logger.info("停止策略运行时监控服务")
        self._running = False
        
        # 停止监控任务
        tasks = [self._monitor_task, self._alert_task, self._cleanup_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.logger.info("策略运行时监控服务已停止")
    
    async def _monitoring_loop(self):
        """主监控循环"""
        try:
            self.logger.info("监控循环开始")
            
            while self._running:
                try:
                    # 获取活跃策略列表
                    active_strategies = strategy_executor_service.get_active_strategies()
                    
                    # 为每个活跃策略收集性能数据
                    for strategy_info in active_strategies:
                        strategy_id = strategy_info['strategy_id']
                        
                        try:
                            # 收集性能快照
                            snapshot = await self._collect_performance_snapshot(
                                strategy_id, strategy_info
                            )
                            
                            if snapshot:
                                # 存储性能数据
                                self.performance_history[strategy_id].append(snapshot)
                                
                                # 检查是否需要更新基线
                                await self._update_performance_baseline(strategy_id, snapshot)
                                
                                # 触发性能回调
                                await self._trigger_performance_callbacks(snapshot)
                                
                        except Exception as e:
                            self.logger.error(f"收集策略 {strategy_id} 性能数据失败: {str(e)}")
                    
                    # 等待下一个监控周期
                    await asyncio.sleep(self.config['monitor_interval'])
                    
                except Exception as e:
                    self.logger.error(f"监控循环异常: {str(e)}")
                    await asyncio.sleep(30)
                    
        except asyncio.CancelledError:
            self.logger.info("监控循环被取消")
        except Exception as e:
            self.logger.error(f"监控循环严重异常: {str(e)}")
    
    async def _collect_performance_snapshot(
        self, 
        strategy_id: int, 
        strategy_info: Dict[str, Any]
    ) -> Optional[PerformanceSnapshot]:
        """收集策略性能快照"""
        try:
            # 获取策略执行上下文
            context = strategy_executor_service.get_strategy_context(strategy_id)
            if not context:
                return None
            
            # 获取系统资源使用情况
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            
            # 计算性能指标
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                performance_metrics = await self._calculate_performance_metrics(
                    strategy_id, db
                )
            
            snapshot = PerformanceSnapshot(
                strategy_id=strategy_id,
                timestamp=datetime.utcnow(),
                pnl=performance_metrics.get('pnl', 0.0),
                win_rate=performance_metrics.get('win_rate', 0.0),
                max_drawdown=performance_metrics.get('max_drawdown', 0.0),
                total_trades=performance_metrics.get('total_trades', 0),
                execution_time_avg=performance_metrics.get('execution_time_avg', 0.0),
                error_count=context.error_count,
                memory_usage_mb=memory_info.rss / 1024 / 1024,
                cpu_usage_percent=cpu_percent
            )
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"收集性能快照失败: {strategy_id}, 错误: {str(e)}")
            return None
    
    async def _calculate_performance_metrics(
        self, 
        strategy_id: int, 
        db: AsyncSession
    ) -> Dict[str, float]:
        """计算性能指标"""
        try:
            # 查询最近24小时的交易记录
            since_time = datetime.utcnow() - timedelta(hours=self.config['performance_window_hours'])
            
            query = select(Trade).where(and_(
                Trade.strategy_id == strategy_id,
                Trade.executed_at >= since_time,
                Trade.trade_type == 'LIVE'
            )).order_by(Trade.executed_at)
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            if not trades:
                return {
                    'pnl': 0.0,
                    'win_rate': 0.0,
                    'max_drawdown': 0.0,
                    'total_trades': 0,
                    'execution_time_avg': 0.0
                }
            
            # 计算PnL
            buy_volume = sum(float(t.total_amount) for t in trades if t.side == 'BUY')
            sell_volume = sum(float(t.total_amount) for t in trades if t.side == 'SELL')
            total_fees = sum(float(t.fee) for t in trades)
            pnl = sell_volume - buy_volume - total_fees
            
            # 计算胜率（简化版本）
            profitable_trades = 0
            total_trades = len(trades)
            
            # 这里需要更复杂的逻辑来确定每笔交易的盈亏
            # 暂时使用简化计算
            if total_trades > 0:
                profitable_trades = max(int(total_trades * 0.6), 0)  # 假设60%胜率
            
            win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
            
            # 计算最大回撤（简化版本）
            max_drawdown = abs(pnl * 0.1) if pnl < 0 else 0.0  # 简化计算
            
            # 平均执行时间（模拟数据）
            execution_time_avg = 1.5  # 假设平均1.5秒
            
            return {
                'pnl': pnl,
                'win_rate': win_rate,
                'max_drawdown': max_drawdown,
                'total_trades': total_trades,
                'execution_time_avg': execution_time_avg
            }
            
        except Exception as e:
            self.logger.error(f"计算性能指标失败: {strategy_id}, 错误: {str(e)}")
            return {}
    
    async def _alert_processing_loop(self):
        """告警处理循环"""
        try:
            self.logger.info("告警处理循环开始")
            
            while self._running:
                try:
                    # 检查所有监控规则
                    for rule_id, rule in self.monitoring_rules.items():
                        if not rule.enabled:
                            continue
                            
                        await self._check_monitoring_rule(rule)
                    
                    # 处理异常检测
                    await self._detect_anomalies()
                    
                    # 等待下一个检查周期
                    await asyncio.sleep(self.config['alert_check_interval'])
                    
                except Exception as e:
                    self.logger.error(f"告警处理循环异常: {str(e)}")
                    await asyncio.sleep(60)
                    
        except asyncio.CancelledError:
            self.logger.info("告警处理循环被取消")
        except Exception as e:
            self.logger.error(f"告警处理循环异常: {str(e)}")
    
    async def _check_monitoring_rule(self, rule: MonitoringRule):
        """检查单个监控规则"""
        try:
            # 获取需要检查的策略列表
            strategy_ids = []
            if rule.strategy_id:
                strategy_ids = [rule.strategy_id]
            else:
                # 全局规则，检查所有活跃策略
                active_strategies = strategy_executor_service.get_active_strategies()
                strategy_ids = [s['strategy_id'] for s in active_strategies]
            
            for strategy_id in strategy_ids:
                # 获取最近的性能数据
                recent_data = list(self.performance_history[strategy_id])
                if not recent_data:
                    continue
                
                # 获取指标值
                current_value = self._extract_metric_value(recent_data[-1], rule.metric)
                if current_value is None:
                    continue
                
                # 检查是否满足触发条件
                should_alert = self._evaluate_condition(
                    current_value, rule.condition, rule.threshold
                )
                
                if should_alert:
                    # 检查持续时间
                    if self._check_duration_requirement(rule, recent_data):
                        # 检查冷却时间
                        if self._check_cooldown_period(rule, strategy_id):
                            # 生成告警
                            await self._generate_alert(rule, strategy_id, current_value)
                            
        except Exception as e:
            self.logger.error(f"检查监控规则失败: {rule.rule_id}, 错误: {str(e)}")
    
    async def _detect_anomalies(self):
        """异常检测"""
        try:
            for strategy_id, history in self.performance_history.items():
                if len(history) < 10:  # 需要足够的历史数据
                    continue
                
                recent_data = list(history)[-10:]  # 最近10个数据点
                
                # 检测PnL异常
                pnl_values = [d.pnl for d in recent_data]
                if len(pnl_values) >= 5:
                    mean_pnl = statistics.mean(pnl_values[:-1])  # 排除最新值
                    std_pnl = statistics.stdev(pnl_values[:-1]) if len(pnl_values) > 2 else 0
                    
                    current_pnl = pnl_values[-1]
                    
                    if std_pnl > 0:
                        z_score = abs(current_pnl - mean_pnl) / std_pnl
                        
                        if z_score > self.config['anomaly_detection_sensitivity']:
                            # 检测到PnL异常
                            await self._generate_anomaly_alert(
                                strategy_id, 
                                PerformanceMetric.PNL,
                                current_pnl,
                                mean_pnl,
                                f"PnL出现异常波动，Z-score: {z_score:.2f}"
                            )
                
                # 检测错误率异常
                error_counts = [d.error_count for d in recent_data]
                if len(error_counts) >= 3:
                    recent_errors = error_counts[-1] - error_counts[-3]  # 最近的错误增量
                    if recent_errors > 5:  # 短时间内错误数量大幅增加
                        await self._generate_anomaly_alert(
                            strategy_id,
                            PerformanceMetric.ERROR_RATE,
                            recent_errors,
                            0,
                            f"策略错误数量异常增加: {recent_errors}"
                        )
                        
        except Exception as e:
            self.logger.error(f"异常检测失败: {str(e)}")
    
    async def _generate_alert(
        self, 
        rule: MonitoringRule, 
        strategy_id: int, 
        current_value: float
    ):
        """生成告警"""
        try:
            alert_id = f"{rule.rule_id}_{strategy_id}_{int(time.time())}"
            
            # 获取用户ID
            context = strategy_executor_service.get_strategy_context(strategy_id)
            user_id = context.user_id if context else 0
            
            # 生成建议
            recommendation = self._generate_recommendation(rule.metric, current_value, rule.threshold)
            
            alert = Alert(
                alert_id=alert_id,
                strategy_id=strategy_id,
                user_id=user_id,
                level=rule.alert_level,
                metric=rule.metric,
                message=f"策略{strategy_id} {rule.metric.value}指标异常: 当前值{current_value:.4f}, 阈值{rule.threshold:.4f}",
                current_value=current_value,
                threshold_value=rule.threshold,
                recommendation=recommendation
            )
            
            # 保存告警
            self.alert_history.append(alert)
            self.active_alerts[alert_id] = alert
            
            # 触发告警回调
            await self._trigger_alert_callbacks(alert)
            
            # 发送WebSocket通知
            await self._send_websocket_alert(alert)
            
            self.logger.warning(f"生成告警: {alert.message}")
            
        except Exception as e:
            self.logger.error(f"生成告警失败: {str(e)}")
    
    async def _generate_anomaly_alert(
        self,
        strategy_id: int,
        metric: PerformanceMetric,
        current_value: float,
        baseline_value: float,
        message: str
    ):
        """生成异常告警"""
        try:
            alert_id = f"anomaly_{strategy_id}_{metric.value}_{int(time.time())}"
            
            context = strategy_executor_service.get_strategy_context(strategy_id)
            user_id = context.user_id if context else 0
            
            alert = Alert(
                alert_id=alert_id,
                strategy_id=strategy_id,
                user_id=user_id,
                level=AlertLevel.WARNING,
                metric=metric,
                message=message,
                current_value=current_value,
                threshold_value=baseline_value,
                recommendation=self._generate_anomaly_recommendation(metric, current_value, baseline_value)
            )
            
            self.alert_history.append(alert)
            self.active_alerts[alert_id] = alert
            
            await self._trigger_alert_callbacks(alert)
            await self._send_websocket_alert(alert)
            
            self.logger.warning(f"检测到异常: {message}")
            
        except Exception as e:
            self.logger.error(f"生成异常告警失败: {str(e)}")
    
    def _extract_metric_value(self, snapshot: PerformanceSnapshot, metric: PerformanceMetric) -> Optional[float]:
        """从性能快照中提取指标值"""
        metric_mapping = {
            PerformanceMetric.PNL: snapshot.pnl,
            PerformanceMetric.WIN_RATE: snapshot.win_rate,
            PerformanceMetric.DRAWDOWN: snapshot.max_drawdown,
            PerformanceMetric.EXECUTION_TIME: snapshot.execution_time_avg,
            PerformanceMetric.ERROR_RATE: snapshot.error_count,
            PerformanceMetric.RESOURCE_USAGE: snapshot.memory_usage_mb
        }
        
        return metric_mapping.get(metric)
    
    def _evaluate_condition(self, current_value: float, condition: str, threshold: float) -> bool:
        """评估条件是否满足"""
        if condition == 'greater_than':
            return current_value > threshold
        elif condition == 'less_than':
            return current_value < threshold
        elif condition == 'equals':
            return abs(current_value - threshold) < 0.001
        elif condition == 'change_rate':
            # 需要更复杂的逻辑来计算变化率
            return False
        else:
            return False
    
    def _check_duration_requirement(
        self, 
        rule: MonitoringRule, 
        recent_data: List[PerformanceSnapshot]
    ) -> bool:
        """检查持续时间要求"""
        if rule.duration_minutes <= 0:
            return True
        
        # 检查最近指定时间内是否一直满足条件
        cutoff_time = datetime.utcnow() - timedelta(minutes=rule.duration_minutes)
        relevant_data = [d for d in recent_data if d.timestamp >= cutoff_time]
        
        if len(relevant_data) < 2:
            return False
        
        # 检查是否所有数据点都满足条件
        for data in relevant_data:
            value = self._extract_metric_value(data, rule.metric)
            if value is None or not self._evaluate_condition(value, rule.condition, rule.threshold):
                return False
        
        return True
    
    def _check_cooldown_period(self, rule: MonitoringRule, strategy_id: int) -> bool:
        """检查冷却时间"""
        if rule.cooldown_minutes <= 0:
            return True
        
        # 查找最近的相同类型告警
        cutoff_time = datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes)
        
        for alert in reversed(self.alert_history):
            if (alert.strategy_id == strategy_id and 
                alert.metric == rule.metric and 
                alert.created_at >= cutoff_time):
                return False  # 在冷却时间内
        
        return True
    
    def _generate_recommendation(
        self, 
        metric: PerformanceMetric, 
        current_value: float, 
        threshold: float
    ) -> str:
        """生成优化建议"""
        recommendations = {
            PerformanceMetric.PNL: {
                'low': "考虑调整交易参数，检查市场条件是否适合当前策略",
                'high': "表现良好，考虑适度增加仓位或复制成功参数"
            },
            PerformanceMetric.WIN_RATE: {
                'low': "胜率较低，建议检查入场条件和止损设置",
                'high': "胜率良好，注意风险控制避免单笔大损失"
            },
            PerformanceMetric.DRAWDOWN: {
                'low': "回撤控制良好，可以考虑适度提高收益目标",
                'high': "回撤过大，建议降低仓位或调整止损参数"
            },
            PerformanceMetric.ERROR_RATE: {
                'low': "系统运行稳定",
                'high': "错误率过高，检查网络连接和API配置"
            },
            PerformanceMetric.RESOURCE_USAGE: {
                'low': "资源使用正常",
                'high': "内存使用过高，考虑优化策略代码或增加系统资源"
            }
        }
        
        if current_value > threshold:
            return recommendations.get(metric, {}).get('high', '建议关注此指标')
        else:
            return recommendations.get(metric, {}).get('low', '建议关注此指标')
    
    def _generate_anomaly_recommendation(
        self, 
        metric: PerformanceMetric, 
        current_value: float, 
        baseline_value: float
    ) -> str:
        """生成异常情况建议"""
        if metric == PerformanceMetric.PNL:
            if current_value < baseline_value:
                return "PnL出现异常下降，建议暂停策略执行并检查市场环境变化"
            else:
                return "PnL异常上升，注意是否存在风险累积，建议适时获利了结"
        elif metric == PerformanceMetric.ERROR_RATE:
            return "错误率异常升高，建议检查网络连接、API状态和策略代码逻辑"
        else:
            return "指标出现异常波动，建议密切关注并考虑人工干预"
    
    async def _trigger_alert_callbacks(self, alert: Alert):
        """触发告警回调"""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                self.logger.error(f"告警回调失败: {str(e)}")
    
    async def _trigger_performance_callbacks(self, snapshot: PerformanceSnapshot):
        """触发性能回调"""
        for callback in self.performance_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(snapshot)
                else:
                    callback(snapshot)
            except Exception as e:
                self.logger.error(f"性能回调失败: {str(e)}")
    
    async def _send_websocket_alert(self, alert: Alert):
        """发送WebSocket告警通知"""
        try:
            message = {
                "type": "strategy_alert",
                "alert_id": alert.alert_id,
                "strategy_id": alert.strategy_id,
                "level": alert.level.value,
                "metric": alert.metric.value,
                "message": alert.message,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "recommendation": alert.recommendation,
                "timestamp": alert.created_at.isoformat()
            }
            
            await websocket_manager.send_to_user(alert.user_id, message)
            
        except Exception as e:
            self.logger.error(f"发送WebSocket告警失败: {str(e)}")
    
    async def _update_performance_baseline(self, strategy_id: int, snapshot: PerformanceSnapshot):
        """更新性能基线"""
        try:
            if strategy_id not in self.performance_baselines:
                self.performance_baselines[strategy_id] = {}
            
            baseline = self.performance_baselines[strategy_id]
            
            # 计算移动平均作为基线
            metrics = ['pnl', 'win_rate', 'max_drawdown', 'execution_time_avg']
            for metric in metrics:
                current_value = getattr(snapshot, metric)
                
                if metric not in baseline:
                    baseline[metric] = current_value
                else:
                    # 指数移动平均
                    alpha = 0.1  # 平滑因子
                    baseline[metric] = alpha * current_value + (1 - alpha) * baseline[metric]
                    
        except Exception as e:
            self.logger.error(f"更新性能基线失败: {strategy_id}, 错误: {str(e)}")
    
    async def _cleanup_loop(self):
        """清理循环"""
        try:
            self.logger.info("清理循环开始")
            
            while self._running:
                try:
                    # 清理过期告警
                    cutoff_time = datetime.utcnow() - timedelta(hours=24)
                    
                    # 清理告警历史
                    self.alert_history = [
                        alert for alert in self.alert_history 
                        if alert.created_at >= cutoff_time
                    ]
                    
                    # 清理活跃告警中的过期项
                    expired_alerts = [
                        alert_id for alert_id, alert in self.active_alerts.items()
                        if alert.created_at < cutoff_time
                    ]
                    
                    for alert_id in expired_alerts:
                        del self.active_alerts[alert_id]
                    
                    # 清理性能历史数据（保留最近1000条）
                    for strategy_id in list(self.performance_history.keys()):
                        history = self.performance_history[strategy_id]
                        if len(history) > 1000:
                            # deque会自动限制大小，这里只是确保清理
                            pass
                    
                    self.logger.info(f"清理完成: 告警历史{len(self.alert_history)}条, 活跃告警{len(self.active_alerts)}条")
                    
                    await asyncio.sleep(self.config['cleanup_interval'])
                    
                except Exception as e:
                    self.logger.error(f"清理循环异常: {str(e)}")
                    await asyncio.sleep(3600)
                    
        except asyncio.CancelledError:
            self.logger.info("清理循环被取消")
        except Exception as e:
            self.logger.error(f"清理循环异常: {str(e)}")
    
    def _initialize_default_rules(self):
        """初始化默认监控规则"""
        default_rules = [
            # PnL监控
            MonitoringRule(
                rule_id="global_pnl_loss",
                strategy_id=None,
                metric=PerformanceMetric.PNL,
                condition="less_than",
                threshold=-1000.0,  # 损失超过1000
                duration_minutes=10,
                alert_level=AlertLevel.WARNING
            ),
            MonitoringRule(
                rule_id="global_pnl_critical_loss",
                strategy_id=None,
                metric=PerformanceMetric.PNL,
                condition="less_than",
                threshold=-5000.0,  # 损失超过5000
                duration_minutes=5,
                alert_level=AlertLevel.CRITICAL
            ),
            # 胜率监控
            MonitoringRule(
                rule_id="global_low_win_rate",
                strategy_id=None,
                metric=PerformanceMetric.WIN_RATE,
                condition="less_than",
                threshold=0.3,  # 胜率低于30%
                duration_minutes=30,
                alert_level=AlertLevel.WARNING
            ),
            # 回撤监控
            MonitoringRule(
                rule_id="global_high_drawdown",
                strategy_id=None,
                metric=PerformanceMetric.DRAWDOWN,
                condition="greater_than",
                threshold=0.2,  # 回撤超过20%
                duration_minutes=5,
                alert_level=AlertLevel.ERROR
            ),
            # 错误率监控
            MonitoringRule(
                rule_id="global_high_error_rate",
                strategy_id=None,
                metric=PerformanceMetric.ERROR_RATE,
                condition="greater_than",
                threshold=10,  # 错误数超过10
                duration_minutes=15,
                alert_level=AlertLevel.ERROR
            ),
            # 资源使用监控
            MonitoringRule(
                rule_id="global_high_memory_usage",
                strategy_id=None,
                metric=PerformanceMetric.RESOURCE_USAGE,
                condition="greater_than",
                threshold=1000.0,  # 内存超过1GB
                duration_minutes=20,
                alert_level=AlertLevel.WARNING
            )
        ]
        
        for rule in default_rules:
            self.monitoring_rules[rule.rule_id] = rule
    
    # 公共接口
    def add_monitoring_rule(self, rule: MonitoringRule):
        """添加监控规则"""
        self.monitoring_rules[rule.rule_id] = rule
        self.logger.info(f"添加监控规则: {rule.rule_id}")
    
    def remove_monitoring_rule(self, rule_id: str) -> bool:
        """移除监控规则"""
        if rule_id in self.monitoring_rules:
            del self.monitoring_rules[rule_id]
            self.logger.info(f"移除监控规则: {rule_id}")
            return True
        return False
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)
    
    def register_performance_callback(self, callback: Callable):
        """注册性能回调"""
        self.performance_callbacks.append(callback)
    
    def get_strategy_performance_history(self, strategy_id: int) -> List[PerformanceSnapshot]:
        """获取策略性能历史"""
        return list(self.performance_history.get(strategy_id, []))
    
    def get_active_alerts(self, strategy_id: Optional[int] = None) -> List[Alert]:
        """获取活跃告警"""
        if strategy_id is None:
            return list(self.active_alerts.values())
        else:
            return [alert for alert in self.active_alerts.values() if alert.strategy_id == strategy_id]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            self.logger.info(f"告警已确认: {alert_id}")
            return True
        return False
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        total_alerts = len(self.alert_history)
        active_alerts = len(self.active_alerts)
        monitored_strategies = len(self.performance_history)
        
        # 按级别统计告警
        alert_by_level = defaultdict(int)
        for alert in self.alert_history:
            alert_by_level[alert.level.value] += 1
        
        # 按指标统计告警
        alert_by_metric = defaultdict(int)
        for alert in self.alert_history:
            alert_by_metric[alert.metric.value] += 1
        
        return {
            'total_alerts_generated': total_alerts,
            'active_alerts_count': active_alerts,
            'monitored_strategies_count': monitored_strategies,
            'monitoring_rules_count': len(self.monitoring_rules),
            'alerts_by_level': dict(alert_by_level),
            'alerts_by_metric': dict(alert_by_metric),
            'enabled_rules_count': sum(1 for rule in self.monitoring_rules.values() if rule.enabled)
        }


# 全局策略运行时监控服务实例
strategy_runtime_monitor = StrategyRuntimeMonitor()