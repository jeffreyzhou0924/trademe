"""
策略引擎核心模块

提供策略执行、市场数据处理、信号生成等核心功能
"""

import asyncio
import json
import traceback
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from loguru import logger

from app.models.strategy import Strategy
from app.models.market_data import MarketData
from app.models.trade import Trade


class StrategyStatus(Enum):
    """策略状态枚举"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class SignalType(Enum):
    """信号类型枚举"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class TradingSignal:
    """交易信号数据类"""
    signal_type: SignalType
    symbol: str
    price: float
    quantity: float
    strategy_id: int = 0
    timestamp: datetime = None
    reason: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['signal_type'] = self.signal_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class StrategyContext:
    """策略执行上下文"""
    strategy_id: int
    user_id: int
    symbol: str
    timeframe: str
    current_price: float = 0.0
    balance: float = 10000.0  # 默认余额
    position: float = 0.0  # 当前持仓
    portfolio_value: float = 10000.0
    
    # 历史数据
    bars: pd.DataFrame = None
    ticks: List[Dict] = None
    
    # 技术指标缓存
    indicators: Dict[str, Any] = None
    
    # 自定义参数
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.bars is None:
            self.bars = pd.DataFrame()
        if self.ticks is None:
            self.ticks = []
        if self.indicators is None:
            self.indicators = {}
        if self.parameters is None:
            self.parameters = {}


class BaseStrategy:
    """基础策略类"""
    
    def __init__(self, context: StrategyContext):
        self.context = context
        self.signals: List[TradingSignal] = []
        self.last_signal_time = None
        
    def on_tick(self, tick_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """处理tick数据 - 需要子类实现"""
        pass
    
    def on_bar(self, bar_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """处理K线数据 - 需要子类实现"""
        pass
    
    def on_signal(self, signal: TradingSignal) -> bool:
        """处理交易信号 - 可以在子类中重写"""
        self.signals.append(signal)
        self.last_signal_time = datetime.now()
        return True
    
    def get_indicator(self, name: str, period: int = 14) -> np.ndarray:
        """获取技术指标"""
        cache_key = f"{name}_{period}"
        if cache_key in self.context.indicators:
            return self.context.indicators[cache_key]
        
        # 计算技术指标
        if name.lower() == "sma":
            result = self._calculate_sma(period)
        elif name.lower() == "ema":
            result = self._calculate_ema(period)
        elif name.lower() == "rsi":
            result = self._calculate_rsi(period)
        elif name.lower() == "macd":
            result = self._calculate_macd()
        else:
            raise ValueError(f"不支持的技术指标: {name}")
        
        # 缓存结果
        self.context.indicators[cache_key] = result
        return result
    
    def _calculate_sma(self, period: int) -> np.ndarray:
        """计算简单移动平均线"""
        if len(self.context.bars) < period:
            return np.array([])
        
        return self.context.bars['close'].rolling(window=period).mean().values
    
    def _calculate_ema(self, period: int) -> np.ndarray:
        """计算指数移动平均线"""
        if len(self.context.bars) < period:
            return np.array([])
        
        return self.context.bars['close'].ewm(span=period).mean().values
    
    def _calculate_rsi(self, period: int = 14) -> np.ndarray:
        """计算相对强弱指数"""
        if len(self.context.bars) < period + 1:
            return np.array([])
        
        closes = self.context.bars['close']
        delta = closes.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.values
    
    def _calculate_macd(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, np.ndarray]:
        """计算MACD指标"""
        if len(self.context.bars) < slow_period:
            return {"macd": np.array([]), "signal": np.array([]), "histogram": np.array([])}
        
        closes = self.context.bars['close']
        
        ema_fast = closes.ewm(span=fast_period).mean()
        ema_slow = closes.ewm(span=slow_period).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line.values,
            "signal": signal_line.values,
            "histogram": histogram.values
        }


class StrategyEngine:
    """策略引擎主类"""
    
    def __init__(self):
        self.running_strategies: Dict[str, Dict] = {}
        self.strategy_instances: Dict[str, BaseStrategy] = {}
        self.signal_callbacks: List[Callable] = []
        
    def register_signal_callback(self, callback: Callable[[TradingSignal], None]):
        """注册信号回调函数"""
        self.signal_callbacks.append(callback)
    
    async def load_strategy(self, strategy: Strategy, context: StrategyContext) -> str:
        """加载策略到引擎"""
        try:
            execution_id = f"strategy_{strategy.id}_{uuid.uuid4().hex[:8]}"
            
            # 编译策略代码
            strategy_class = await self._compile_strategy_code(strategy.code)
            
            # 创建策略实例
            strategy_instance = strategy_class(context)
            
            # 存储策略信息
            self.running_strategies[execution_id] = {
                "strategy_id": strategy.id,
                "user_id": context.user_id,
                "status": StrategyStatus.STOPPED,
                "start_time": None,
                "last_update": datetime.now(),
                "signal_count": 0,
                "error_message": None
            }
            
            self.strategy_instances[execution_id] = strategy_instance
            
            logger.info(f"策略加载成功: {strategy.name} (ID: {execution_id})")
            return execution_id
            
        except Exception as e:
            logger.error(f"策略加载失败: {str(e)}")
            raise ValueError(f"策略加载失败: {str(e)}")
    
    async def start_strategy(self, execution_id: str) -> bool:
        """启动策略"""
        if execution_id not in self.running_strategies:
            raise ValueError("策略不存在")
        
        try:
            self.running_strategies[execution_id]["status"] = StrategyStatus.RUNNING
            self.running_strategies[execution_id]["start_time"] = datetime.now()
            
            logger.info(f"策略已启动: {execution_id}")
            return True
            
        except Exception as e:
            self.running_strategies[execution_id]["status"] = StrategyStatus.ERROR
            self.running_strategies[execution_id]["error_message"] = str(e)
            logger.error(f"策略启动失败: {str(e)}")
            return False
    
    async def stop_strategy(self, execution_id: str) -> bool:
        """停止策略"""
        if execution_id not in self.running_strategies:
            return False
        
        try:
            self.running_strategies[execution_id]["status"] = StrategyStatus.STOPPED
            logger.info(f"策略已停止: {execution_id}")
            return True
            
        except Exception as e:
            logger.error(f"策略停止失败: {str(e)}")
            return False
    
    async def process_tick_data(self, tick_data: Dict[str, Any]) -> List[TradingSignal]:
        """处理tick数据"""
        signals = []
        
        for execution_id, strategy_info in self.running_strategies.items():
            if strategy_info["status"] != StrategyStatus.RUNNING:
                continue
            
            try:
                strategy_instance = self.strategy_instances[execution_id]
                
                # 更新策略上下文
                strategy_instance.context.current_price = tick_data.get("price", 0)
                strategy_instance.context.ticks.append(tick_data)
                
                # 限制tick历史数量
                if len(strategy_instance.context.ticks) > 1000:
                    strategy_instance.context.ticks = strategy_instance.context.ticks[-500:]
                
                # 处理tick数据
                signal = strategy_instance.on_tick(tick_data)
                
                if signal:
                    signals.append(signal)
                    strategy_info["signal_count"] += 1
                    
                    # 触发信号回调
                    for callback in self.signal_callbacks:
                        try:
                            await callback(signal)
                        except Exception as e:
                            logger.error(f"信号回调失败: {str(e)}")
                
                strategy_info["last_update"] = datetime.now()
                
            except Exception as e:
                strategy_info["status"] = StrategyStatus.ERROR
                strategy_info["error_message"] = str(e)
                logger.error(f"策略执行错误 {execution_id}: {str(e)}")
        
        return signals
    
    async def process_bar_data(self, bar_data: Dict[str, Any]) -> List[TradingSignal]:
        """处理K线数据"""
        signals = []
        
        for execution_id, strategy_info in self.running_strategies.items():
            if strategy_info["status"] != StrategyStatus.RUNNING:
                continue
            
            try:
                strategy_instance = self.strategy_instances[execution_id]
                
                # 更新K线数据
                new_bar = pd.DataFrame([bar_data])
                if strategy_instance.context.bars.empty:
                    strategy_instance.context.bars = new_bar
                else:
                    strategy_instance.context.bars = pd.concat([
                        strategy_instance.context.bars, new_bar
                    ], ignore_index=True)
                
                # 限制K线历史数量
                if len(strategy_instance.context.bars) > 1000:
                    strategy_instance.context.bars = strategy_instance.context.bars.tail(500)
                
                # 清除技术指标缓存
                strategy_instance.context.indicators.clear()
                
                # 处理K线数据
                signal = strategy_instance.on_bar(bar_data)
                
                if signal:
                    signals.append(signal)
                    strategy_info["signal_count"] += 1
                    
                    # 触发信号回调
                    for callback in self.signal_callbacks:
                        try:
                            await callback(signal)
                        except Exception as e:
                            logger.error(f"信号回调失败: {str(e)}")
                
                strategy_info["last_update"] = datetime.now()
                
            except Exception as e:
                strategy_info["status"] = StrategyStatus.ERROR
                strategy_info["error_message"] = str(e)
                logger.error(f"策略执行错误 {execution_id}: {str(e)}")
        
        return signals
    
    async def get_strategy_status(self, execution_id: str) -> Optional[Dict]:
        """获取策略状态"""
        if execution_id not in self.running_strategies:
            return None
        
        strategy_info = self.running_strategies[execution_id].copy()
        strategy_info["status"] = strategy_info["status"].value
        
        # 添加策略实例信息
        if execution_id in self.strategy_instances:
            instance = self.strategy_instances[execution_id]
            strategy_info.update({
                "signal_count_today": len(instance.signals),
                "last_signal_time": instance.last_signal_time.isoformat() if instance.last_signal_time else None,
                "current_price": instance.context.current_price,
                "position": instance.context.position,
                "balance": instance.context.balance
            })
        
        return strategy_info
    
    def get_all_strategy_status(self) -> Dict[str, Dict]:
        """获取所有策略状态"""
        result = {}
        for execution_id in self.running_strategies.keys():
            result[execution_id] = asyncio.run(self.get_strategy_status(execution_id))
        return result
    
    async def _compile_strategy_code(self, code: str) -> type:
        """编译策略代码"""
        try:
            # 创建执行环境
            namespace = {
                'BaseStrategy': BaseStrategy,
                'TradingSignal': TradingSignal,
                'SignalType': SignalType,
                'np': np,
                'pd': pd,
                'datetime': datetime,
                'timedelta': timedelta,
            }
            
            # 执行代码
            exec(code, namespace)
            
            # 查找策略类
            strategy_class = None
            for name, obj in namespace.items():
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseStrategy) and 
                    obj is not BaseStrategy):
                    strategy_class = obj
                    break
            
            if strategy_class is None:
                raise ValueError("策略代码中未找到有效的策略类")
            
            return strategy_class
            
        except Exception as e:
            logger.error(f"策略代码编译失败: {str(e)}")
            raise ValueError(f"策略代码编译失败: {str(e)}")
    
    async def cleanup_strategy(self, execution_id: str):
        """清理策略资源"""
        if execution_id in self.running_strategies:
            del self.running_strategies[execution_id]
        
        if execution_id in self.strategy_instances:
            del self.strategy_instances[execution_id]
        
        logger.info(f"策略资源已清理: {execution_id}")


# 全局策略引擎实例
strategy_engine = StrategyEngine()


# 示例策略类
class SimpleEMAStrategy(BaseStrategy):
    """简单EMA策略示例"""
    
    def __init__(self, context: StrategyContext):
        super().__init__(context)
        self.short_period = context.parameters.get("short_period", 5)
        self.long_period = context.parameters.get("long_period", 20)
    
    def on_bar(self, bar_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """K线数据处理"""
        if len(self.context.bars) < self.long_period:
            return None
        
        try:
            short_ema = self.get_indicator("ema", self.short_period)
            long_ema = self.get_indicator("ema", self.long_period)
            
            if len(short_ema) < 2 or len(long_ema) < 2:
                return None
            
            current_price = bar_data["close"]
            
            # 金叉信号
            if (short_ema[-1] > long_ema[-1] and 
                short_ema[-2] <= long_ema[-2] and 
                self.context.position == 0):
                
                return TradingSignal(
                    strategy_id=self.context.strategy_id,
                    symbol=self.context.symbol,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    quantity=0.1,  # 10%仓位
                    timestamp=datetime.now(),
                    reason=f"EMA金叉: 短期EMA({self.short_period})上穿长期EMA({self.long_period})"
                )
            
            # 死叉信号
            elif (short_ema[-1] < long_ema[-1] and 
                  short_ema[-2] >= long_ema[-2] and 
                  self.context.position > 0):
                
                return TradingSignal(
                    strategy_id=self.context.strategy_id,
                    symbol=self.context.symbol,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    quantity=self.context.position,
                    timestamp=datetime.now(),
                    reason=f"EMA死叉: 短期EMA({self.short_period})下穿长期EMA({self.long_period})"
                )
            
        except Exception as e:
            logger.error(f"EMA策略计算错误: {str(e)}")
            
        return None