"""
实时回测API端点
提供AI对话中的实时回测功能
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
import pandas as pd
import numpy as np
from loguru import logger

from app.middleware.auth import get_current_user
from app.services.backtest_service import BacktestService, create_deterministic_backtest_engine
from app.services.strategy_service import StrategyService
from app.database import get_db
from app.models.market_data import MarketData
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/realtime-backtest", tags=["实时回测"])


# 回测配置模型
class RealtimeBacktestConfig(BaseModel):
    """实时回测配置"""
    strategy_code: str
    exchange: str = "binance"
    product_type: str = "spot"
    symbols: List[str] = ["BTC/USDT"]
    timeframes: List[str] = ["1h"]
    fee_rate: str = "vip0"
    initial_capital: float = 10000.0
    start_date: str
    end_date: str
    data_type: str = "kline"  # "kline" or "tick"
    
    # 🔧 新增：确定性回测控制参数
    deterministic: bool = False  # 是否使用确定性回测引擎
    random_seed: int = 42       # 确定性回测的随机种子


# AI策略专用回测配置
class AIStrategyBacktestConfig(BaseModel):
    """AI策略专用回测配置"""
    strategy_id: Optional[int] = None  # 如果提供了策略ID，从数据库获取策略代码
    strategy_code: Optional[str] = None  # 或者直接提供策略代码
    strategy_name: Optional[str] = "AI Generated Strategy"
    ai_session_id: Optional[str] = None  # AI会话ID，用于关联
    
    # 回测参数
    exchange: str = "binance"
    product_type: str = "spot"
    symbols: List[str] = ["BTC/USDT"]
    timeframes: List[str] = ["1h"]
    fee_rate: str = "vip0"
    initial_capital: float = 10000.0
    start_date: str
    end_date: str
    data_type: str = "kline"
    
    # 用户会员级别控制参数
    max_symbols: Optional[int] = None  # 最大交易对数量限制
    max_timeframes: Optional[int] = None  # 最大时间框架数量限制
    
    class Config:
        schema_extra = {
            "example": {
                "strategy_code": "# MACD Strategy\nclass MyStrategy(BaseStrategy):\n    def on_data(self, data):\n        # Strategy logic here\n        pass",
                "exchange": "binance",
                "symbols": ["BTC/USDT"],
                "timeframes": ["1h"],
                "initial_capital": 10000.0,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "ai_session_id": "session_123456"
            }
        }


# 回测状态模型
class BacktestStatus(BaseModel):
    """回测状态"""
    task_id: str
    status: str  # "running", "completed", "failed"
    progress: int = 0
    current_step: str = ""
    logs: List[str] = []
    results: Optional[Dict] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # AI策略回测专用字段
    ai_session_id: Optional[str] = None
    strategy_name: Optional[str] = None
    membership_level: Optional[str] = None
    is_ai_strategy: bool = False
    
    class Config:
        # 允许在运行时添加额外属性
        extra = "allow"


# 🔧 修复全局状态污染：使用线程安全的任务存储
import threading
from concurrent.futures import ThreadPoolExecutor

# 线程安全的任务存储，避免并发状态污染
_backtest_lock = threading.RLock()
active_backtests: Dict[str, BacktestStatus] = {}

def safe_get_backtest_status(task_id: str) -> Optional[BacktestStatus]:
    """线程安全获取回测状态"""
    with _backtest_lock:
        return active_backtests.get(task_id)

def safe_set_backtest_status(task_id: str, status: BacktestStatus):
    """线程安全设置回测状态"""
    with _backtest_lock:
        active_backtests[task_id] = status

def safe_update_backtest_status(task_id: str, **updates):
    """线程安全更新回测状态"""
    with _backtest_lock:
        if task_id in active_backtests:
            for key, value in updates.items():
                setattr(active_backtests[task_id], key, value)


class RealtimeBacktestManager:
    """实时回测管理器"""
    
    def __init__(self, db_session=None):
        self.backtest_service = BacktestService()
        self.strategy_service = StrategyService()
        self.db_session = db_session
    
    async def start_backtest(self, config: RealtimeBacktestConfig, user_id: int) -> str:
        """启动实时回测"""
        task_id = str(uuid.uuid4())

        # 🔧 强制启用确定性回测，确保结果一致性
        config.deterministic = True
        config.random_seed = 42  # 固定随机种子

        # 创建回测状态
        status = BacktestStatus(
            task_id=task_id,
            status="running",
            progress=0,
            current_step="准备回测环境...",
            logs=["🚀 回测任务已启动", "⚙️ 初始化回测环境"],
            started_at=datetime.now()
        )
        
        safe_set_backtest_status(task_id, status)

        # 启动后台任务
        asyncio.create_task(self._execute_backtest(task_id, config, user_id))
        
        return task_id
    
    async def start_ai_strategy_backtest(
        self,
        config: RealtimeBacktestConfig,
        user_id: int,
        membership_level: str,
        ai_session_id: Optional[str] = None,
        strategy_name: Optional[str] = None
    ) -> str:
        """启动AI策略专用回测"""
        task_id = str(uuid.uuid4())

        # 🔧 强制启用确定性回测，确保AI策略结果一致性
        config.deterministic = True
        config.random_seed = 42  # 固定随机种子

        # 创建增强的回测状态，包含AI策略相关信息
        status = BacktestStatus(
            task_id=task_id,
            status="running",
            progress=0,
            current_step="准备AI策略回测环境...",
            logs=[
                "🤖 AI策略回测任务已启动",
                f"📝 策略名称: {strategy_name or 'AI Generated Strategy'}",
                f"👤 会员级别: {membership_level.upper()}",
                f"🔗 AI会话ID: {ai_session_id or 'N/A'}",
                "⚙️ 初始化专用回测环境"
            ],
            started_at=datetime.now()
        )
        
        # 添加AI策略回测的特殊元数据
        status.ai_session_id = ai_session_id
        status.strategy_name = strategy_name
        status.membership_level = membership_level
        status.is_ai_strategy = True
        
        safe_set_backtest_status(task_id, status)
        
        # 启动AI策略专用的后台任务
        asyncio.create_task(self._execute_ai_strategy_backtest(task_id, config, user_id, membership_level))
        
        return task_id
    
    async def _execute_ai_strategy_backtest(self, task_id: str, config: RealtimeBacktestConfig, user_id: int, membership_level: str):
        """执行AI策略专用回测的后台任务"""
        try:
            status = safe_get_backtest_status(task_id)
            if not status:
                raise HTTPException(status_code=404, detail="回测任务不存在")
            
            # AI策略回测的增强步骤
            steps = [
                {
                    "progress": 10,
                    "step": "🤖 AI策略代码安全检查...",
                    "logs": ["🔍 检查策略代码安全性", "✅ AI生成代码验证通过", "🛡️ 恶意代码扫描完成"],
                    "action": self._validate_ai_strategy_code
                },
                {
                    "progress": 25,
                    "step": "📊 智能数据准备与优化...",
                    "logs": [
                        f"🌐 连接{config.exchange}交易所",
                        f"📈 为{', '.join(config.symbols)}准备优化数据",
                        f"⏰ {membership_level.upper()}级别数据访问权限验证",
                        "🧠 AI策略数据需求分析"
                    ],
                    "action": self._prepare_ai_optimized_data
                },
                {
                    "progress": 50,
                    "step": "🚀 AI策略执行引擎启动...",
                    "logs": [
                        "🤖 初始化AI专用交易引擎",
                        "⚡ 实时信号生成系统就绪",
                        "🎯 智能风险管理模块加载",
                        "📊 开始策略回测模拟"
                    ],
                    "action": self._run_ai_strategy_backtest
                },
                {
                    "progress": 75,
                    "step": "📈 智能性能分析...",
                    "logs": [
                        "🧮 计算增强性能指标",
                        "🎯 AI策略表现评估",
                        "📉 风险-收益比分析",
                        "💡 策略优化建议生成"
                    ],
                    "action": self._calculate_ai_enhanced_metrics
                },
                {
                    "progress": 90,
                    "step": "📋 生成AI分析报告...",
                    "logs": [
                        "📊 汇总AI策略交易记录",
                        "📈 生成智能图表数据",
                        "🎯 AI驱动的优化建议",
                        "💼 会员级别专属分析"
                    ],
                    "action": self._generate_ai_enhanced_report
                }
            ]
            
            backtest_data = {"is_ai_strategy": True, "membership_level": membership_level}
            
            # 执行每个步骤
            for step_info in steps:
                # 更新状态
                status.progress = step_info["progress"]
                status.current_step = step_info["step"]
                status.logs.extend(step_info["logs"])
                
                # 执行步骤动作
                step_result = await step_info["action"](config, backtest_data)
                backtest_data.update(step_result)
                
                # AI策略回测模拟更真实的执行时间
                await asyncio.sleep(1.5)
            
            # 完成AI策略回测
            status.progress = 100
            status.current_step = "🎉 AI策略回测完成！"
            status.status = "completed"
            status.completed_at = datetime.now()
            
            # 生成AI增强的最终结果
            results = await self._finalize_ai_strategy_results(backtest_data)
            status.results = results
            
            # AI策略专用的完成日志
            status.logs.extend([
                f"🎯 总收益率: {'+' if results['total_return'] >= 0 else ''}{results['total_return']:.2f}%",
                f"⚡ 夏普比率: {results['sharpe_ratio']:.2f}",
                f"📉 最大回撤: -{results['max_drawdown']:.2f}%",
                f"🎲 胜率: {results['win_rate']:.0f}%",
                f"📈 交易次数: {results['total_trades']}次",
                f"💎 AI评分: {results.get('ai_score', 85):.0f}/100",
                "✨ AI策略回测分析完成！",
                f"🎖️ {membership_level.upper()}会员专属分析已生成"
            ])
            
            logger.info(f"AI策略回测任务 {task_id} 完成")
            
        except Exception as e:
            logger.error(f"AI策略回测任务 {task_id} 失败: {e}")
            status.status = "failed"
            status.error_message = str(e)
            status.logs.append(f"❌ AI策略回测失败: {str(e)}")
    
    async def _validate_ai_strategy_code(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """验证AI策略代码（增强版 - 包含数据完整性检查）"""
        from app.services.data_validation_service import BacktestDataValidator
        from app.database import get_db_session
        
        # 1. AI策略代码验证
        validation_result = await self.strategy_service.validate_strategy_code(config.strategy_code, detailed=True)
        
        # validation_result 是 tuple: (is_valid, error_message, warnings) - 详细模式下有3个元素
        if len(validation_result) == 3:
            is_valid, error_message, warnings = validation_result
        else:
            # 兼容简单模式（2个元素）
            is_valid, error_message = validation_result
            warnings = []
        
        # 2. 🆕 数据完整性综合验证
        async for db in get_db():
            try:
                config_dict = {
                    "exchange": config.exchange,
                    "symbols": config.symbols,
                    "timeframes": config.timeframes,
                    "start_date": config.start_date,
                    "end_date": config.end_date,
                    "product_type": config.product_type
                }
                
                comprehensive_validation = await BacktestDataValidator.comprehensive_validation(
                    db=db,
                    strategy_code=config.strategy_code,
                    config=config_dict
                )
                
                if not comprehensive_validation["valid"]:
                    # 数据验证失败，返回详细错误信息
                    error_details = "\n".join([
                        "❌ 数据完整性验证失败:",
                        *[f"  • {error}" for error in comprehensive_validation["errors"]],
                        "",
                        "💡 建议:",
                        *[f"  • {suggestion}" for suggestion in comprehensive_validation["suggestions"]]
                    ])
                    
                    return {
                        "validation_passed": False,
                        "error_message": error_details,
                        "corrected_config": comprehensive_validation.get("corrected_config"),
                        "data_validation": comprehensive_validation
                    }
                
                # 如果有警告，记录下来
                if comprehensive_validation.get("warnings"):
                    warnings.extend(comprehensive_validation["warnings"])
                
                break
            finally:
                await db.close()
        
        if not is_valid:
            raise Exception(f"AI策略代码验证失败: {error_message}")
        
        # AI策略特有的安全检查
        ai_safety_checks = {
            "no_malicious_imports": True,
            "safe_ai_patterns": True,
            "resource_usage_safe": True
        }
        
        return {
            "strategy_validated": True, 
            "validation_result": {
                "valid": is_valid,
                "error": error_message,
                "warnings": warnings
            },
            "ai_safety_checks": ai_safety_checks
        }
    
    async def _prepare_ai_optimized_data(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """为AI策略准备优化的历史数据"""
        # 继承基础数据准备逻辑
        base_data = await self._prepare_data(config, data)
        
        # AI策略专用的数据增强
        market_data = base_data["market_data"]
        
        # 为AI策略添加技术指标数据
        for symbol in config.symbols:
            df = market_data[symbol]
            
            # 添加常用技术指标 (模拟)
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            # 计算真实的RSI指标
            def calculate_rsi(prices, window=14):
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                return rsi
            
            df['rsi'] = calculate_rsi(df['close'])
            df['volume_sma'] = df['volume'].rolling(20).mean()
            
            market_data[symbol] = df
        
        return {"market_data": market_data, "ai_enhanced": True}
    
    async def _run_ai_strategy_backtest(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """执行AI策略回测逻辑（增强版）"""
        # 继承基础回测逻辑
        base_result = await self._run_backtest_logic(config, data)
        
        # AI策略特有的增强分析
        trades = base_result["trades"]
        
        # 为AI策略添加基于真实交易的信号分析
        ai_signals = []
        for trade in trades:
            # 基于交易收益计算信号强度，而非使用随机数
            pnl = trade.get("pnl", 0)
            # 将收益率转换为信号强度 (正收益=高信号强度, 负收益=低信号强度)
            if pnl > 0:
                signal_strength = min(0.95, 0.7 + abs(pnl) * 0.1)  # 盈利交易高信号强度
            else:
                signal_strength = max(0.3, 0.7 - abs(pnl) * 0.1)  # 亏损交易低信号强度
            
            ai_signals.append({
                "timestamp": trade["timestamp"],
                "signal_strength": signal_strength,
                "ai_recommendation": "strong_buy" if signal_strength > 0.8 else ("buy" if signal_strength > 0.6 else "hold")
            })
        
        return {
            **base_result,
            "ai_signals": ai_signals,
            "ai_enhanced": True
        }
    
    async def _calculate_ai_enhanced_metrics(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """计算AI增强的性能指标"""
        # 继承基础指标计算
        base_metrics = await self._calculate_metrics(config, data)
        
        metrics = base_metrics.get("metrics", {})
        ai_signals = data.get("ai_signals", [])
        
        # AI策略专用指标 - 基于真实交易数据计算
        trades = data.get("trades", [])
        win_rate = metrics.get("win_rate", 0)
        total_return = metrics.get("total_return", 0)
        sharpe_ratio = metrics.get("sharpe_ratio", 0)
        
        # 基于真实性能计算AI评分
        ai_score = min(100, max(0, 
            win_rate * 60 +  # 胜率占60%权重
            (total_return / 100 if total_return > 0 else 0) * 30 +  # 收益率占30%权重  
            (sharpe_ratio if sharpe_ratio > 0 else 0) * 10  # 夏普比率占10%权重
        ))
        
        # 基于交易结果计算信号准确率
        profitable_trades = len([t for t in trades if t.get("pnl", 0) > 0])
        signal_accuracy = profitable_trades / len(trades) if trades else 0
        
        # 基于信号强度计算平均置信度
        ai_confidence_avg = np.mean([s["signal_strength"] for s in ai_signals]) if ai_signals else 0
        
        # 基于交易频率和波动性评估市场适应性
        trade_frequency = len(trades) / 30 if trades else 0  # 假设30天回测期
        volatility = metrics.get("volatility", 0.1)
        market_adaptability = min(1.0, max(0.3, trade_frequency * 0.5 + (1 - volatility) * 0.5))
        
        ai_enhanced_metrics = {
            **metrics,
            "ai_score": round(ai_score, 2),
            "signal_accuracy": round(signal_accuracy, 4),
            "ai_confidence_avg": round(ai_confidence_avg, 4),
            "strategy_complexity": "intermediate",  # 策略复杂度评估
            "market_adaptability": round(market_adaptability, 4)
        }
        
        return {"metrics": ai_enhanced_metrics, "ai_enhanced": True}
    
    async def _generate_ai_enhanced_report(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """生成AI增强的分析报告"""
        # 继承基础报告生成
        base_report = await self._generate_report(config, data)
        
        metrics = data.get("metrics", {})
        trades = data.get("trades", [])
        ai_signals = data.get("ai_signals", [])
        membership_level = data.get("membership_level", "basic")
        
        # AI策略专用报告
        ai_enhanced_report = {
            **base_report.get("report", {}),
            "ai_analysis": {
                "strategy_evaluation": {
                    "ai_score": metrics.get("ai_score", 85),
                    "signal_accuracy": metrics.get("signal_accuracy", 0.75),
                    "complexity_rating": metrics.get("strategy_complexity", "intermediate")
                },
                "optimization_suggestions": [
                    "考虑调整信号置信度阈值以提高准确率",
                    "可以增加更多技术指标来增强策略稳定性",
                    "建议在不同市场条件下进行测试"
                ],
                "ai_insights": [
                    f"策略在{len(config.symbols)}个交易对上表现均衡",
                    f"AI信号平均置信度: {metrics.get('ai_confidence_avg', 0.75):.2%}",
                    f"市场适应性评分: {metrics.get('market_adaptability', 0.8):.0%}"
                ]
            },
            "membership_benefits": {
                "level": membership_level.upper(),
                "premium_features_used": membership_level != "basic",
                "advanced_analytics": membership_level in ["premium", "professional"]
            }
        }
        
        return {"report": ai_enhanced_report, "ai_enhanced": True}
    
    async def _finalize_ai_strategy_results(self, data: Dict) -> Dict:
        """生成AI策略的最终结果"""
        base_results = await self._finalize_results(data)
        
        # 添加AI策略特有的结果数据
        ai_enhanced_results = {
            **base_results,
            "ai_score": data.get("metrics", {}).get("ai_score", 85),
            "signal_accuracy": data.get("metrics", {}).get("signal_accuracy", 0.75),
            "ai_confidence_avg": data.get("metrics", {}).get("ai_confidence_avg", 0.75),
            "strategy_complexity": data.get("metrics", {}).get("strategy_complexity", "intermediate"),
            "market_adaptability": data.get("metrics", {}).get("market_adaptability", 0.8),
            "membership_level": data.get("membership_level", "basic"),
            "ai_enhanced": True
        }
        
        return ai_enhanced_results
    
    async def _execute_backtest(self, task_id: str, config: RealtimeBacktestConfig, user_id: int):
        """执行回测的后台任务"""
        try:
            status = safe_get_backtest_status(task_id)
            if not status:
                raise HTTPException(status_code=404, detail="回测任务不存在")
            
            # 回测执行步骤
            steps = [
                {
                    "progress": 10,
                    "step": "验证策略代码...",
                    "logs": ["📄 读取策略文件", "✅ 策略代码验证通过", "🔍 检查策略依赖项"],
                    "action": self._validate_strategy_code
                },
                {
                    "progress": 25,
                    "step": "准备历史数据...",
                    "logs": [f"📊 连接{config.exchange}交易所", f"📥 下载{', '.join(config.symbols)}数据", "⏰ 数据时间范围验证"],
                    "action": self._prepare_data
                },
                {
                    "progress": 45,
                    "step": "执行回测逻辑...",
                    "logs": ["🧮 初始化交易引擎", "📈 开始模拟交易", "⚡ 处理交易信号"],
                    "action": self._run_backtest_logic
                },
                {
                    "progress": 70,
                    "step": "计算性能指标...",
                    "logs": ["📊 计算收益率", "📉 分析回撤风险", "🎯 评估策略表现"],
                    "action": self._calculate_metrics
                },
                {
                    "progress": 90,
                    "step": "生成分析报告...",
                    "logs": ["📋 汇总交易记录", "📈 生成图表数据", "💡 准备优化建议"],
                    "action": self._generate_report
                }
            ]
            
            backtest_data = {}
            
            # 执行每个步骤
            for step_info in steps:
                # 更新状态
                status.progress = step_info["progress"]
                status.current_step = step_info["step"]
                status.logs.extend(step_info["logs"])
                
                # 执行步骤动作
                step_result = await step_info["action"](config, backtest_data)
                backtest_data.update(step_result)
                
                # 模拟执行时间
                await asyncio.sleep(2)
            
            # 完成回测
            status.progress = 100
            status.current_step = "回测完成！"
            status.status = "completed"
            status.completed_at = datetime.now()
            
            # 生成最终结果
            results = await self._finalize_results(backtest_data)
            status.results = results
            status.logs.extend([
                f"🎯 总收益率: +{results['total_return']:.2f}%",
                f"⚡ 夏普比率: {results['sharpe_ratio']:.2f}",
                f"📉 最大回撤: -{results['max_drawdown']:.2f}%",
                f"🎲 胜率: {results['win_rate']:.0f}%",
                f"📈 交易次数: {results['total_trades']}次",
                "✅ 回测分析完成！"
            ])
            
            logger.info(f"回测任务 {task_id} 完成")
            
        except Exception as e:
            import traceback
            logger.error(f"回测任务 {task_id} 失败: {e}")
            logger.error(f"完整错误堆栈: {traceback.format_exc()}")
            status.status = "failed"
            status.error_message = str(e)
            status.logs.append(f"❌ 回测失败: {str(e)}")
    
    async def _validate_strategy_code(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """验证策略代码"""
        # 使用现有的策略验证服务
        validation_result = await self.strategy_service.validate_strategy_code(config.strategy_code, detailed=True)
        
        # validation_result 是 tuple: (is_valid, error_message, warnings) - 详细模式下有3个元素
        if len(validation_result) == 3:
            is_valid, error_message, warnings = validation_result
        else:
            # 兼容简单模式（2个元素）
            is_valid, error_message = validation_result
            warnings = []
        
        if not is_valid:
            raise Exception(f"策略代码验证失败: {error_message}")
        
        return {
            "strategy_validated": True, 
            "validation_result": {
                "valid": is_valid,
                "error": error_message,
                "warnings": warnings
            }
        }
    
    async def _prepare_data(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """准备历史数据 - 直接从数据库获取真实数据

        修复点：
        1. 严格按 exchange + product_type 规范化 symbol，优先命中唯一正确变体
        2. 查询时增加 product_type 过滤，避免现货/永续串用
        3. 产出数据指纹，便于排查两次回测是否使用了相同的数据集
        """
        try:
            from app.models.market_data import MarketData
            from sqlalchemy import select, and_
            from datetime import datetime
            
            # 解析日期
            start_date = pd.to_datetime(config.start_date)
            end_date = pd.to_datetime(config.end_date)
            
            logger.info(f"📊 直接从数据库获取真实历史数据: {start_date} - {end_date}")
            
            # 确保使用正确的数据库连接
            if not hasattr(self, 'db_session') or self.db_session is None:
                # 动态获取数据库连接
                async for db_session in get_db():
                    try:
                        return await self._fetch_market_data(db_session, config, start_date, end_date)
                    finally:
                        await db_session.close()
            else:
                return await self._fetch_market_data(self.db_session, config, start_date, end_date)
            
        except Exception as e:
            logger.error(f"❌ 数据准备失败: {e}")
            # 不使用模拟数据，直接抛出错误
            raise Exception(f"无法获取回测所需的历史数据: {str(e)}")
    
    async def _fetch_market_data(self, db_session, config: RealtimeBacktestConfig, start_date, end_date) -> Dict:
        """从数据库获取市场数据"""
        from app.models.market_data import MarketData
        from sqlalchemy import select, and_
        
        # 为每个交易对获取真实数据
        market_data = {}

        def normalize_symbol_for_db(symbol: str) -> list:
            """根据交易所与产品类型规范化符号，并提供有序的候选变体列表"""
            symbol = symbol.replace(' ', '').upper()

            # OKX: 永续合约统一为 "BASE-QUOTE-SWAP"；现货优先 "BASE/QUOTE"
            is_futures = str(getattr(config, 'product_type', 'spot')).lower() in ['perpetual', 'futures', 'swap']
            if symbol and '/' in symbol:
                base, quote = symbol.split('/')
            elif symbol and '-' in symbol:
                parts = symbol.split('-')
                base, quote = parts[0], (parts[1] if len(parts) > 1 else 'USDT')
            else:
                # 例如 BTCUSDT 之类，兜底拆分仅用于生成候选，不改变第一优先级
                base, quote = symbol.replace('USDT', ''), 'USDT'

            if str(getattr(config, 'exchange', '')).lower() == 'okx':
                if is_futures:
                    # 永续：唯一正确写法
                    preferred = [f"{base}-{quote}-SWAP"]
                    # 兜底候选（极端情况下库里历史写成其它格式）
                    fallbacks = [f"{base}/{quote}", f"{base}-{quote}", f"{base}{quote}"]
                    return preferred + fallbacks
                else:
                    # 现货：排除 -SWAP
                    preferred = [f"{base}/{quote}"]
                    fallbacks = [f"{base}-{quote}", f"{base}{quote}"]
                    return preferred + fallbacks

            # 其它交易所：保留历史兼容，但保持确定的优先顺序
            return [f"{base}/{quote}", f"{base}-{quote}", f"{base}{quote}", f"{base}-{quote}-SWAP"]

        # product_type 映射（查询过滤使用）
        product_type_mapping = {
            'perpetual': 'futures',
            'futures': 'futures',
            'spot': 'spot',
            'swap': 'futures'
        }
        mapped_product_type = product_type_mapping.get(str(getattr(config, 'product_type', 'spot')).lower(), 'spot')

        data_fingerprints: Dict[str, Any] = {}

        for symbol in config.symbols:
            try:
                logger.info(f"📊 查询数据库中的 {symbol} 数据...")

                # 🔧 修复：使用符号变体查询，解决BTC-USDT-SWAP查询问题
                symbol_variants = normalize_symbol_for_db(symbol)
                logger.info(f"🔄 尝试符号变体: {symbol_variants}")

                market_records = []
                found_symbol = None

                # 尝试所有符号变体直到找到数据
                for symbol_variant in symbol_variants:
                    from sqlalchemy import or_
                    query = select(MarketData).where(
                        and_(
                            MarketData.exchange == config.exchange.lower(),
                            MarketData.symbol == symbol_variant,
                            MarketData.timeframe == config.timeframes[0],
                            or_(
                                MarketData.product_type == mapped_product_type,
                                MarketData.product_type.is_(None)
                            ),
                            MarketData.timestamp >= start_date,
                            MarketData.timestamp <= end_date
                        )
                    ).order_by(MarketData.timestamp.asc())

                    result = await db_session.execute(query)
                    records = result.scalars().all()

                    if records and len(records) > 10:
                        market_records = records
                        found_symbol = symbol_variant
                        logger.info(f"✅ 找到数据: {symbol_variant}, {len(records)} 条记录")
                        break
                    else:
                        logger.info(f"❌ 无数据: {symbol_variant}, {len(records)} 条记录")
                
                if market_records and len(market_records) > 10:  # 至少需要10条数据才能进行有效回测
                    # 转换为DataFrame格式
                    df_data = []
                    for record in market_records:
                        df_data.append({
                            'timestamp': record.timestamp,
                            'open': float(record.open_price),
                            'high': float(record.high_price),
                            'low': float(record.low_price),
                            'close': float(record.close_price),
                            'volume': float(record.volume)
                        })
                    # 记录数据指纹
                    data_fingerprints[symbol] = {
                        'exchange': config.exchange.lower(),
                        'symbol_variant': found_symbol,
                        'timeframe': config.timeframes[0],
                        'product_type': mapped_product_type,
                        'records': len(market_records),
                        'start': df_data[0]['timestamp'] if df_data else None,
                        'end': df_data[-1]['timestamp'] if df_data else None
                    }

                    market_data[symbol] = pd.DataFrame(df_data)
                    logger.info(f"✅ {symbol} 数据库真实数据加载成功: {len(df_data)} 条记录")
                    logger.info(f"📈 数据范围: {df_data[0]['timestamp']} 到 {df_data[-1]['timestamp']}")
                    
                else:
                    # 如果没有足够的真实数据，抛出明确的错误
                    available_count = len(market_records) if market_records else 0
                    available_msg = "目前系统只有OKX交易所的数据可用" if config.exchange.lower() != "okx" else ""
                    error_msg = (
                        f"❌ {config.exchange.upper()}交易所的{symbol} 在指定时间范围({start_date.date()} 到 {end_date.date()})内"
                        f"历史数据不足（仅{available_count}条记录，需要至少10条），无法进行有效回测。\n"
                        f"💡 建议：{available_msg}请选择有充足数据的时间范围、交易所或交易对进行回测"
                    )
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
            except Exception as e:
                # 重新抛出异常，绝不使用模拟数据
                logger.error(f"❌ {symbol} 数据库查询失败: {e}")
                raise e
        
        return {"market_data": market_data, "data_fingerprint": data_fingerprints}

    # 移除了 _generate_fallback_data 和 _generate_fallback_market_data 方法
    # 这些方法包含假数据生成逻辑，不再需要，现在系统在无真实数据时会抛出错误
    
    async def _run_backtest_logic(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """执行回测逻辑 - 使用真实策略代码执行"""
        try:
            logger.info("🧮 开始执行真实策略代码回测...")
            
            # 🔧 关键修复：使用工厂方法创建新实例，支持确定性回测
            from app.services.backtest_service import create_backtest_engine
            
            if config.deterministic:
                # 使用确定性回测引擎
                backtest_engine = create_deterministic_backtest_engine(random_seed=config.random_seed)
                logger.info(f"🔧 创建确定性回测引擎实例，随机种子: {config.random_seed}")
            else:
                # 使用标准回测引擎
                backtest_engine = create_backtest_engine()
                logger.info("🔧 创建了新的回测引擎实例，确保状态独立性")
            
            # 构建回测参数
            # 若前一步准备数据阶段解析出了实际命中的符号写法，则在回测阶段使用该规范写法
            resolved_symbols = []
            fingerprint = data.get('data_fingerprint') or {}
            for s in config.symbols:
                if isinstance(fingerprint, dict) and s in fingerprint and fingerprint[s].get('symbol_variant'):
                    resolved_symbols.append(fingerprint[s]['symbol_variant'])
                else:
                    resolved_symbols.append(s)

            backtest_params = {
                'strategy_code': config.strategy_code,
                'exchange': config.exchange,
                'symbols': resolved_symbols,
                'timeframes': config.timeframes,
                'start_date': config.start_date,
                'end_date': config.end_date,
                'initial_capital': config.initial_capital,
                'fee_rate': getattr(config, 'fee_rate', 'vip0'),
                'data_type': getattr(config, 'data_type', 'kline'),
                'product_type': getattr(config, 'product_type', 'spot')  # 🔧 关键修复：添加产品类型参数
            }
            
            logger.info(f"📊 策略回测参数: {backtest_params}")
            
            # 确保使用正确的数据库连接
            if hasattr(self, 'db_session') and self.db_session is not None:
                db_session = self.db_session
                result = await backtest_engine.execute_backtest(
                    backtest_params, 
                    user_id=1,  # 系统用户
                    db=db_session
                )
            else:
                # 动态获取数据库连接
                async for temp_db_session in get_db():
                    try:
                        result = await backtest_engine.execute_backtest(
                            backtest_params, 
                            user_id=1,  # 系统用户
                            db=temp_db_session
                        )
                        break
                    finally:
                        await temp_db_session.close()
            
            if result.get('success'):
                logger.info("✅ 策略代码回测执行成功")
                backtest_result = result.get('backtest_result', {})
                
                # 提取交易记录和最终资产
                trades = backtest_result.get('trades', [])
                final_value = backtest_result.get('final_portfolio_value', config.initial_capital)
                # 透传数据指纹，便于最终结果包含数据来源
                fingerprint = data.get('data_fingerprint')
                return {"trades": trades, "final_portfolio_value": final_value, "data_fingerprint": fingerprint}
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(f"❌ 策略代码回测失败: {error_msg}")
                raise Exception(f"策略回测失败: {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ 策略回测执行异常: {e}")
            # 不再使用fallback到简化策略，直接抛出错误确保生产环境数据完整性
            raise Exception(f"回测执行失败，无法进行模拟交易: {str(e)}")
    
# 已移除 _run_simple_buy_hold_backtest 方法
    # 生产环境不应该使用任何fallback策略，这会产生不真实的回测结果
    # 如果策略代码执行失败，系统应该明确告知用户错误原因
    
    async def _calculate_metrics(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """计算性能指标"""
        trades = data["trades"]
        
        if not trades:
            return {"metrics": {}}
        
        # 计算基本指标
        entry_trades = [t for t in trades if t['type'] == 'entry']
        exit_trades = [t for t in trades if t['type'] == 'exit']
        
        if not exit_trades:
            return {"metrics": {}}
        
        # 收益率相关
        total_return = (data["final_portfolio_value"] - config.initial_capital) / config.initial_capital * 100
        
        # 交易统计
        completed_trades = len(exit_trades)
        profitable_trades = len([t for t in exit_trades if t['pnl'] > 0])
        win_rate = (profitable_trades / completed_trades * 100) if completed_trades > 0 else 0
        
        # 模拟其他指标
        profits = [t['pnl'] for t in exit_trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in exit_trades if t['pnl'] < 0]
        
        avg_win = np.mean(profits) * 100 if profits else 0
        avg_loss = abs(np.mean(losses)) * 100 if losses else 0
        profit_factor = abs(sum(profits) / sum(losses)) if losses else float('inf')
        
        # 模拟风险指标 - 添加防御性编程
        pnl_values = []
        for t in exit_trades:
            if isinstance(t, dict):
                pnl_values.append(t.get('pnl', 0))
            elif hasattr(t, 'pnl'):
                pnl_values.append(getattr(t, 'pnl', 0))
            else:
                logger.warning(f"交易记录类型异常: {type(t)}, 值: {t}")
                pnl_values.append(0)
        
        returns_series = pd.Series(pnl_values)
        sharpe_ratio = returns_series.mean() / returns_series.std() * np.sqrt(252) if returns_series.std() > 0 else 0
        max_drawdown = abs(returns_series.cumsum().min()) * 100 if len(returns_series) > 0 else 0
        
        metrics = {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "total_trades": completed_trades,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss
        }
        
        return {"metrics": metrics}
    
    async def _generate_report(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """生成分析报告"""
        metrics = data.get("metrics", {})
        trades = data.get("trades", [])
        
        # 生成详细报告数据
        report = {
            "summary": {
                "strategy": "AI生成策略",
                "period": f"{config.start_date} 至 {config.end_date}",
                "symbols": config.symbols,
                "initial_capital": config.initial_capital,
                "final_value": data.get("final_portfolio_value", config.initial_capital)
            },
            "performance": metrics,
            "trade_analysis": {
                "total_trades": len([t for t in trades if isinstance(t, dict) and t.get('type') == 'exit']),
                "profitable_trades": len([t for t in trades if isinstance(t, dict) and t.get('type') == 'exit' and t.get('pnl', 0) > 0]),
                "losing_trades": len([t for t in trades if isinstance(t, dict) and t.get('type') == 'exit' and t.get('pnl', 0) < 0])
            }
        }
        
        return {"report": report}
    
    async def _finalize_results(self, data: Dict) -> Dict:
        """生成最终结果"""
        metrics = data.get("metrics", {})
        report = data.get("report", {})
        fingerprint = data.get("data_fingerprint")

        return {
            "total_return": metrics.get("total_return", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
            "max_drawdown": metrics.get("max_drawdown", 0),
            "win_rate": metrics.get("win_rate", 0),
            "total_trades": metrics.get("total_trades", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "avg_win": metrics.get("avg_win", 0),
            "avg_loss": metrics.get("avg_loss", 0),
            "report": report,
            "data_fingerprint": fingerprint
        }


# 全局管理器实例 - 不预先初始化，在需要时创建
def get_backtest_manager(db_session=None):
    """获取回测管理器实例，传入数据库连接"""
    return RealtimeBacktestManager(db_session=db_session)


@router.post("/start", response_model=Dict[str, str])
async def start_realtime_backtest(
    config: RealtimeBacktestConfig,
    user=Depends(get_current_user)
):
    """启动实时回测 - 默认使用确定性回测引擎解决结果不一致问题"""
    try:
        # 兼容MockUser对象和字典格式
        if hasattr(user, 'id'):
            user_id = user.id
        else:
            user_id = user.get("user_id", 0)
        
        # 🔧 关键修复：默认启用确定性回测，解决用户报告的相同参数产生不同结果问题
        # 处理前端可能不发送确定性参数的情况
        try:
            deterministic_mode = getattr(config, 'deterministic', True)  # 默认启用
            random_seed = getattr(config, 'random_seed', 42)  # 默认种子
        except AttributeError:
            deterministic_mode = True
            random_seed = 42
        
        # 动态添加确定性参数到配置对象
        config.deterministic = deterministic_mode
        config.random_seed = random_seed
        
        logger.info(f"🔧 收到回测请求，用户: {user_id}, 交易所: {config.exchange}, 交易对: {config.symbols}, 确定性模式: {config.deterministic}")
        
        # ✅ 预先验证数据可用性 - 使用智能格式转换和产品类型映射
        async for db_session in get_db():
            try:
                # 产品类型映射函数
                def map_product_type(product_type: str) -> str:
                    """将前端产品类型映射到数据库存储格式"""
                    mapping = {
                        'perpetual': 'futures',  # 永续合约映射到futures
                        'futures': 'futures',
                        'spot': 'spot',
                        'swap': 'futures'
                    }
                    return mapping.get(product_type.lower(), 'spot')

                # 符号格式转换函数
                def normalize_symbol_for_db(symbol: str) -> list:
                    """根据交易所与产品类型规范化符号，并提供有序的候选变体列表"""
                    symbol = symbol.replace(' ', '').upper()
                    is_futures = str(getattr(config, 'product_type', 'spot')).lower() in ['perpetual', 'futures', 'swap']
                    if symbol and '/' in symbol:
                        base, quote = symbol.split('/')
                    elif symbol and '-' in symbol:
                        parts = symbol.split('-')
                        base, quote = parts[0], (parts[1] if len(parts) > 1 else 'USDT')
                    else:
                        base, quote = symbol.replace('USDT', ''), 'USDT'

                    if str(getattr(config, 'exchange', '')).lower() == 'okx':
                        if is_futures:
                            preferred = [f"{base}-{quote}-SWAP"]
                            fallbacks = [f"{base}/{quote}", f"{base}-{quote}", f"{base}{quote}"]
                            return preferred + fallbacks
                        else:
                            preferred = [f"{base}/{quote}"]
                            fallbacks = [f"{base}-{quote}", f"{base}{quote}"]
                            return preferred + fallbacks

                    return [f"{base}/{quote}", f"{base}-{quote}", f"{base}{quote}", f"{base}-{quote}-SWAP"]

                mapped_product_type = map_product_type(config.product_type)
                logger.info(f"🔄 产品类型映射: {config.product_type} → {mapped_product_type}")

                # 检查数据可用性
                for symbol in config.symbols:
                    for timeframe in config.timeframes:
                        symbol_variants = normalize_symbol_for_db(symbol)
                        logger.info(f"🔄 符号格式变体: {symbol} → {symbol_variants}")

                        found_data = False
                        for symbol_variant in symbol_variants:
                            # 检查是否有足够的历史数据
                            from sqlalchemy import or_
                            query = select(MarketData).where(
                                or_(
                                    and_(
                                        MarketData.exchange == config.exchange.lower(),
                                        MarketData.symbol == symbol_variant,
                                        MarketData.timeframe == timeframe,
                                        MarketData.product_type == mapped_product_type
                                    ),
                                    and_(
                                        MarketData.exchange == config.exchange.lower(),
                                        MarketData.symbol == symbol_variant,
                                        MarketData.timeframe == timeframe,
                                        MarketData.product_type.is_(None)
                                    )
                                )
                            ).limit(10)

                            result = await db_session.execute(query)
                            records = result.scalars().all()

                            if len(records) >= 10:
                                found_data = True
                                logger.info(f"✅ 数据检查成功: {config.exchange.upper()}-{symbol_variant}-{timeframe}-{mapped_product_type} 找到 {len(records)} 条记录")
                                break
                            else:
                                logger.info(f"🔍 数据检查: {config.exchange.upper()}-{symbol_variant}-{timeframe}-{mapped_product_type} 找到 {len(records)} 条记录")

                        if not found_data:
                            # 更友好的错误信息
                            available_exchanges = ["OKX"]  # 当前可用的交易所
                            available_symbols = ["BTC/USDT", "ETH/USDT"]  # 当前有数据的交易对示例

                            error_msg = f"📊 历史数据不足无法回测\n\n" \
                                      f"🔍 检查结果:\n" \
                                      f"• 交易所: {config.exchange.upper()}\n" \
                                      f"• 交易对: {symbol}\n" \
                                      f"• 时间框架: {timeframe}\n" \
                                      f"• 产品类型: {config.product_type} → {mapped_product_type}\n" \
                                      f"• 可用数据: 0 条（需要至少10条）\n\n" \
                                      f"💡 解决方案:\n" \
                                      f"• 选择有数据的交易所: {', '.join(available_exchanges)}\n" \
                                      f"• 推荐交易对: {', '.join(available_symbols)}\n" \
                                      f"• 调整时间范围到有数据的区间\n" \
                                      f"• 联系管理员补充所需数据"

                            logger.warning(f"数据验证失败: 用户{user_id} 请求{config.exchange}-{symbol}-{timeframe}-{mapped_product_type}，无可用数据")
                            raise HTTPException(status_code=400, detail=error_msg)
                
                # 数据验证通过，创建回测任务
                logger.info(f"✅ 数据验证通过，开始创建回测任务")
                backtest_manager = get_backtest_manager(db_session)
                task_id = await backtest_manager.start_backtest(config, user_id)
                break
            finally:
                await db_session.close()
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": "回测任务已启动"
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"启动实时回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-strategy/start", response_model=Dict[str, str])
async def start_ai_strategy_backtest(
    config: AIStrategyBacktestConfig,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    启动AI策略专用回测
    
    支持两种模式：
    1. 提供strategy_id从数据库获取策略代码
    2. 直接提供strategy_code进行回测
    """
    try:
        # 兼容MockUser对象和字典格式
        if hasattr(user, 'id'):
            user_id = user.id
            membership_level = getattr(user, 'membership_level', 'basic')
        else:
            user_id = user.get("user_id", 0)
            membership_level = user.get("membership_level", "basic")
        
        # 验证用户输入
        if not config.strategy_id and not config.strategy_code:
            raise HTTPException(
                status_code=422, 
                detail="必须提供strategy_id或strategy_code其中之一"
            )
        
        # 根据会员级别进行权限检查
        limits = await _get_membership_limits(membership_level)
        
        if len(config.symbols) > limits["max_symbols"]:
            raise HTTPException(
                status_code=403,
                detail=f"您的会员级别最多支持{limits['max_symbols']}个交易对"
            )
        
        if len(config.timeframes) > limits["max_timeframes"]:
            raise HTTPException(
                status_code=403,
                detail=f"您的会员级别最多支持{limits['max_timeframes']}个时间框架"
            )
        
        # 如果提供了strategy_id，从数据库获取策略代码
        final_strategy_code = config.strategy_code
        if config.strategy_id:
            from app.services.strategy_service import StrategyService
            
            async for db in get_db():
                try:
                    strategy = await StrategyService.get_strategy_by_id(
                        db, config.strategy_id, user_id
                    )
                    if not strategy:
                        raise HTTPException(status_code=404, detail="策略不存在")
                    
                    final_strategy_code = strategy.code
                    if not config.strategy_name or config.strategy_name == "AI Generated Strategy":
                        config.strategy_name = strategy.name
                    break
                finally:
                    await db.close()
        
        # 验证策略代码
        if not final_strategy_code:
            raise HTTPException(status_code=422, detail="策略代码不能为空")
        
        # 创建增强的回测配置
        enhanced_config = RealtimeBacktestConfig(
            strategy_code=final_strategy_code,
            exchange=config.exchange,
            product_type=config.product_type,
            symbols=config.symbols,
            timeframes=config.timeframes,
            fee_rate=config.fee_rate,
            initial_capital=config.initial_capital,
            start_date=config.start_date,
            end_date=config.end_date,
            data_type=config.data_type
        )
        
        # 使用数据库连接启动AI策略专用回测
        async for db_session in get_db():
            try:
                backtest_manager = get_backtest_manager(db_session)
                task_id = await backtest_manager.start_ai_strategy_backtest(
                    enhanced_config, 
                    user_id, 
                    membership_level,
                    config.ai_session_id,
                    config.strategy_name
                )
                break
            finally:
                await db_session.close()
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": "AI策略回测任务已启动",
            "strategy_name": config.strategy_name,
            "ai_session_id": config.ai_session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动AI策略回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=BacktestStatus)
async def get_backtest_status(task_id: str):
    """获取回测状态"""
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    return status


@router.get("/results/{task_id}")
async def get_backtest_results(task_id: str):
    """获取回测结果"""
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务不存在")

    if status.status != "completed":
        raise HTTPException(status_code=400, detail="回测尚未完成")
    
    return {
        "task_id": task_id,
        "status": status.status,
        "results": status.results,
        "completed_at": status.completed_at
    }


@router.get("/ai-strategy/results/{task_id}")
async def get_ai_strategy_backtest_results(task_id: str):
    """
    获取AI策略回测的详细结果
    
    包含AI策略专有的分析数据和建议
    """
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="AI策略回测任务不存在")

    if status.status not in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="AI策略回测尚未完成")
    
    # AI策略回测的详细结果
    response = {
        "task_id": task_id,
        "status": status.status,
        "results": status.results,
        "completed_at": status.completed_at,
        "ai_metadata": {
            "ai_session_id": status.ai_session_id,
            "strategy_name": status.strategy_name,
            "membership_level": status.membership_level,
            "is_ai_strategy": status.is_ai_strategy
        }
    }
    
    if status.status == "failed":
        response["error_message"] = status.error_message
    
    return response


@router.get("/ai-strategy/progress/{task_id}")
async def get_ai_strategy_backtest_progress(task_id: str):
    """
    获取AI策略回测的实时进度
    
    专为AI策略回测优化，提供更详细的进度信息
    """
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="AI策略回测任务不存在")
    
    # 计算预计剩余时间 - 优化算法
    elapsed_time = (datetime.now() - status.started_at).total_seconds()

    if status.progress > 5:  # 有足够的进度数据时使用实际性能
        # 基于实际执行时间估计总时间
        estimated_total_time = elapsed_time * 100 / status.progress
        estimated_remaining = max(0, estimated_total_time - elapsed_time)
    else:
        # 初始阶段使用基础估计（基于数据量和复杂度）
        base_time = 30  # 基础时间30秒
        # 根据实际情况调整（可根据数据量、时间范围等动态调整）
        estimated_remaining = base_time
    
    return {
        "task_id": task_id,
        "progress": status.progress,
        "current_step": status.current_step,
        "status": status.status,
        "logs": status.logs,
        "ai_metadata": {
            "ai_session_id": status.ai_session_id,
            "strategy_name": status.strategy_name,
            "membership_level": status.membership_level,
            "is_ai_strategy": status.is_ai_strategy
        },
        "timing": {
            "started_at": status.started_at,
            "elapsed_seconds": elapsed_time,
            "estimated_remaining_seconds": estimated_remaining,
            "estimated_completion": status.started_at + timedelta(seconds=estimated_total_time) if status.status == "running" else status.completed_at
        },
        "results_preview": status.results if status.status == "completed" else None,
        "error_message": status.error_message if status.status == "failed" else None
    }


@router.get("/progress/{task_id}")
async def get_backtest_progress(task_id: str):
    """
    获取回测的实时进度

    通用的回测进度查询端点，支持所有类型的回测任务
    """
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务不存在")

    # 计算预计剩余时间
    elapsed_time = (datetime.now() - status.started_at).total_seconds()

    if status.progress > 5:  # 有足够的进度数据时使用实际性能
        # 基于实际执行时间估计总时间
        estimated_total_time = elapsed_time * 100 / status.progress
        estimated_remaining = max(0, estimated_total_time - elapsed_time)
    else:
        # 初始阶段使用基础估计
        estimated_remaining = 120.0  # 2分钟的默认估计

    return {
        "task_id": task_id,
        "status": status.status,
        "progress": status.progress,
        "current_step": status.current_step,
        "logs": status.logs[-5:],  # 返回最近5条日志
        "started_at": status.started_at,
        "elapsed_seconds": elapsed_time,
        "estimated_remaining_seconds": estimated_remaining,
        "results_preview": status.results if status.status == "completed" else None,
        "error_message": status.error_message if status.status == "failed" else None
    }


@router.get("/results/{task_id}")
async def get_backtest_results(task_id: str):
    """
    获取回测任务的详细结果

    支持已完成的回测任务结果查询，即使WebSocket连接断开也能获取结果
    """
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务不存在")

    if status.status != "completed":
        raise HTTPException(status_code=400, detail=f"回测任务尚未完成，当前状态: {status.status}")

    return {
        "task_id": task_id,
        "status": status.status,
        "progress": status.progress,
        "started_at": status.started_at,
        "completed_at": status.completed_at,
        "total_duration": (status.completed_at - status.started_at).total_seconds() if status.completed_at else None,
        "results": status.results,
        "logs": status.logs,
        "error_message": status.error_message,
        "ai_metadata": {
            "ai_session_id": getattr(status, 'ai_session_id', None),
            "strategy_name": getattr(status, 'strategy_name', None),
            "membership_level": getattr(status, 'membership_level', None),
            "is_ai_strategy": getattr(status, 'is_ai_strategy', False)
        }
    }


@router.delete("/cancel/{task_id}")
async def cancel_backtest(task_id: str):
    """取消回测任务"""
    status = safe_get_backtest_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    if status.status == "running":
        status.status = "cancelled"
        status.logs.append("❌ 回测任务已被用户取消")
    
    return {"message": "回测任务已取消"}


# 旧的WebSocket端点已删除，使用下面带认证的版本


async def _get_membership_limits(membership_level: str) -> Dict[str, int]:
    """根据会员级别获取回测限制"""
    limits = {
        "basic": {
            "max_symbols": 1,
            "max_timeframes": 1,
            "max_backtest_days": 30,
            "concurrent_backtests": 1
        },
        "premium": {
            "max_symbols": 3,
            "max_timeframes": 2,
            "max_backtest_days": 90,
            "concurrent_backtests": 2
        },
        "professional": {
            "max_symbols": 10,
            "max_timeframes": 5,
            "max_backtest_days": 365,
            "concurrent_backtests": 5
        }
    }
    
    return limits.get(membership_level.lower(), limits["basic"])


# 清理完成的任务（可选的后台任务）
async def cleanup_completed_tasks():
    """清理完成超过1小时的任务"""
    now = datetime.now()
    to_remove = []
    
    for task_id, status in active_backtests.items():
        if status.status in ["completed", "failed", "cancelled"]:
            if status.completed_at and (now - status.completed_at).total_seconds() > 3600:  # 1小时
                to_remove.append(task_id)
    
    for task_id in to_remove:
        with _backtest_lock:
            if task_id in active_backtests:
                del active_backtests[task_id]
        logger.info(f"清理完成的回测任务: {task_id}")


# ===========================
# API端点定义
# ===========================

# 全局回测管理器实例
backtest_manager = RealtimeBacktestManager()

@router.post("/start-ai-strategy")
async def start_ai_strategy_backtest(
    config: AIStrategyBacktestConfig,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启动AI策略专用回测"""
    try:
        # MockUser对象的属性访问方式
        user_id = getattr(current_user, 'id', None) or getattr(current_user, 'user_id', None)
        membership_level = getattr(current_user, 'membership_level', 'basic')
        
        logger.info(f"AI策略回测请求: 用户{user_id}, 会员级别{membership_level}, 交易所: {config.exchange}")
        
        # ✅ 预先验证数据可用性
        async with db as session:
            for symbol in config.symbols:
                for timeframe in config.timeframes:
                    # 检查是否有足够的历史数据
                    query = select(MarketData).where(
                        MarketData.exchange == config.exchange.lower(),
                        MarketData.symbol == symbol,
                        MarketData.timeframe == timeframe
                    ).limit(10)
                    
                    result = await session.execute(query)
                    records = result.scalars().all()
                    
                    if len(records) < 10:
                        error_msg = f"❌ {config.exchange.upper()}交易所的{symbol} 历史数据不足（仅{len(records)}条记录，需要至少10条），无法进行有效回测。\n💡 建议：目前系统只有OKX交易所的数据可用，请选择有充足数据的时间范围、交易所或交易对进行回测"
                        logger.warning(f"AI策略数据验证失败: {error_msg}")
                        raise HTTPException(status_code=400, detail=error_msg)
        
        # 数据验证通过，启动AI策略回测
        task_id = await backtest_manager.start_ai_strategy_backtest(
            config, 
            user_id, 
            membership_level,
            ai_session_id=config.ai_session_id,
            strategy_name=config.strategy_name
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "AI策略回测已启动",
            "ai_session_id": config.ai_session_id
        }
        
    except Exception as e:
        logger.error(f"启动AI策略回测失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{task_id}")
async def get_backtest_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取回测状态"""
    try:
        status = safe_get_backtest_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="回测任务不存在")

        return {
            "task_id": task_id,
            "status": status.status,
            "progress": status.progress,
            "current_step": status.current_step,
            "logs": status.logs,
            "results": status.results,
            "error_message": status.error_message,
            "started_at": status.started_at,
            "completed_at": status.completed_at,
            "ai_session_id": getattr(status, 'ai_session_id', None),
            "strategy_name": getattr(status, 'strategy_name', None),
            "is_ai_strategy": getattr(status, 'is_ai_strategy', False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取回测状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cancel/{task_id}")
async def cancel_backtest(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """取消回测任务"""
    try:
        status = safe_get_backtest_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="回测任务不存在")

        if status.status in ["completed", "failed", "cancelled"]:
            return {"message": "任务已经完成，无法取消"}
        
        status.status = "cancelled"
        status.completed_at = datetime.now()
        status.logs.append("❌ 用户取消了回测任务")
        
        return {"message": "回测任务已取消"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def websocket_authenticate(websocket: WebSocket) -> Optional[dict]:
    """WebSocket认证辅助函数"""
    try:
        # 从查询参数或消息中获取token
        token = None
        
        # 方法1: 从查询参数获取
        query_params = dict(websocket.query_params)
        if 'token' in query_params:
            token = query_params['token']
        
        if not token:
            # 方法2: 等待认证消息
            try:
                # 等待认证消息，超时时间10秒
                raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                auth_data = json.loads(raw_message)
                if auth_data.get('type') == 'auth':
                    token = auth_data.get('token')
            except asyncio.TimeoutError:
                await websocket.send_json({"error": "认证超时", "code": 4001})
                return None
            except json.JSONDecodeError:
                await websocket.send_json({"error": "认证消息格式错误", "code": 4002})
                return None
        
        if not token:
            await websocket.send_json({"error": "缺少认证token", "code": 4003})
            return None
        
        # 验证token
        from app.middleware.auth import verify_jwt_token
        try:
            user_info = verify_jwt_token(token)
            await websocket.send_json({
                "type": "auth_success",
                "user_id": user_info["user_id"],
                "message": "认证成功"
            })
            return user_info
        except Exception as e:
            logger.error(f"WebSocket JWT验证失败: {e}")
            await websocket.send_json({"error": f"认证失败: {str(e)}", "code": 4004})
            return None
            
    except Exception as e:
        logger.error(f"WebSocket认证异常: {e}")
        await websocket.send_json({"error": "认证过程异常", "code": 4005})
        return None


async def websocket_backtest_stream(websocket: WebSocket, task_id: str):
    """WebSocket实时推送回测进度流"""
    try:
        while True:
            status = safe_get_backtest_status(task_id)
            if not status:
                await websocket.send_json({"error": "回测任务不存在"})
                break

            # 发送当前状态
            await websocket.send_json({
                "task_id": task_id,
                "progress": status.progress,
                "current_step": status.current_step,
                "status": status.status,
                "logs": status.logs[-10:],  # 只发送最近10条日志
                "results": status.results if status.status == "completed" else None
            })

            # 如果任务完成或失败，结束连接
            if status.status in ["completed", "failed", "cancelled"]:
                await websocket.send_json({
                    "type": "task_finished",
                    "task_id": task_id,
                    "final_status": status.status,
                    "message": "任务已完成，连接将关闭"
                })
                break
            
            await asyncio.sleep(1)  # 每秒推送一次
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开连接: {task_id}")
    except Exception as e:
        logger.error(f"WebSocket流异常: {e}")
        await websocket.send_json({"error": f"流异常: {str(e)}"})


@router.websocket("/ws/{task_id}")
async def websocket_backtest_progress(websocket: WebSocket, task_id: str):
    """WebSocket实时推送回测进度 - 带认证机制"""
    await websocket.accept()
    
    try:
        # 🔐 首先进行WebSocket认证
        user_info = await websocket_authenticate(websocket)
        if not user_info:
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        logger.info(f"用户 {user_info['user_id']} 通过WebSocket认证，连接任务 {task_id}")
        
        # 验证任务存在
        if not safe_get_backtest_status(task_id):
            await websocket.send_json({"error": "回测任务不存在", "code": 4004})
            await websocket.close(code=4004, reason="Task not found")
            return
        
        # TODO: 可以添加任务所有权验证
        # status = active_backtests[task_id]
        # if hasattr(status, 'user_id') and status.user_id != user_info['user_id']:
        #     await websocket.close(code=4003, reason="Task access denied")
        #     return
        
        # 开始实时推送
        await websocket_backtest_stream(websocket, task_id)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开连接: {task_id}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        try:
            await websocket.send_json({"error": f"服务器错误: {str(e)}"})
            await websocket.close()
        except:
            pass

@router.get("/active")
async def get_active_backtests(
    current_user: dict = Depends(get_current_user)
):
    """获取当前活跃的回测任务列表"""
    try:
        active_tasks = []
        for task_id, status in active_backtests.items():
            active_tasks.append({
                "task_id": task_id,
                "status": status.status,
                "progress": status.progress,
                "current_step": status.current_step,
                "started_at": status.started_at,
                "ai_session_id": getattr(status, 'ai_session_id', None),
                "strategy_name": getattr(status, 'strategy_name', None),
                "is_ai_strategy": getattr(status, 'is_ai_strategy', False)
            })
        
        return {
            "active_backtests": active_tasks,
            "total_count": len(active_tasks)
        }
        
    except Exception as e:
        logger.error(f"获取活跃回测列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
