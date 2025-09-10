"""
策略自动化执行服务 - 完善策略执行引擎功能缺失

功能特性:
- 策略代码动态执行
- 信号自动生成
- 参数实时调整
- 执行状态监控
- 智能错误恢复
- 性能实时分析
"""

import asyncio
import json
import uuid
import traceback
import importlib.util
import types
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
import numpy as np
import pandas as pd

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

from app.models.strategy import Strategy
from app.models.trade import Trade
from app.core.live_trading_engine import live_trading_engine, TradingSignal, StrategyExecutionMode
from app.core.risk_manager import risk_manager
from app.services.exchange_service import exchange_service
from app.services.strategy_service import StrategyService


class StrategyExecutionStatus(Enum):
    """策略执行状态"""
    IDLE = "idle"                  # 空闲
    INITIALIZING = "initializing"  # 初始化中
    RUNNING = "running"            # 运行中
    PAUSED = "paused"             # 暂停
    STOPPING = "stopping"         # 停止中
    STOPPED = "stopped"           # 已停止
    ERROR = "error"               # 错误状态
    CRASHED = "crashed"           # 崩溃


class SignalStrength(Enum):
    """信号强度"""
    WEAK = "weak"         # 弱信号
    MODERATE = "moderate" # 中等信号
    STRONG = "strong"     # 强信号
    CRITICAL = "critical" # 关键信号


@dataclass
class StrategyContext:
    """策略执行上下文"""
    strategy_id: int
    user_id: int
    session_id: str
    exchange: str
    symbols: List[str]
    parameters: Dict[str, Any]
    execution_mode: StrategyExecutionMode
    
    # 运行时状态
    status: StrategyExecutionStatus = StrategyExecutionStatus.IDLE
    start_time: Optional[datetime] = None
    last_tick_time: Optional[datetime] = None
    error_count: int = 0
    signal_count: int = 0
    
    # 性能指标
    total_pnl: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    
    # 数据存储
    market_data: Dict[str, Any] = field(default_factory=dict)
    positions: Dict[str, float] = field(default_factory=dict)
    indicators: Dict[str, Any] = field(default_factory=dict)
    
    # 错误记录
    recent_errors: List[str] = field(default_factory=list)


@dataclass
class GeneratedSignal:
    """生成的交易信号"""
    signal_id: str
    strategy_id: int
    symbol: str
    signal_type: str  # BUY, SELL, CLOSE
    strength: SignalStrength
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 1.0
    reason: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class StrategyExecutorService:
    """策略自动化执行服务"""
    
    def __init__(self):
        self.logger = logger.bind(service="StrategyExecutor")
        
        # 活跃策略执行上下文
        self.active_strategies: Dict[int, StrategyContext] = {}
        
        # 编译后的策略代码缓存
        self.compiled_strategies: Dict[int, types.ModuleType] = {}
        
        # 执行任务管理
        self.execution_tasks: Dict[int, asyncio.Task] = {}
        
        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 性能统计
        self.stats = {
            'total_strategies_executed': 0,
            'total_signals_generated': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'average_execution_time_ms': 0.0,
            'uptime_start': datetime.utcnow()
        }
    
    async def start_service(self):
        """启动策略执行服务"""
        if self._running:
            return
            
        self._running = True
        self.logger.info("启动策略自动化执行服务")
        
        # 启动监控任务
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info("策略执行服务启动完成")
    
    async def stop_service(self):
        """停止策略执行服务"""
        if not self._running:
            return
            
        self.logger.info("停止策略执行服务")
        self._running = False
        
        # 停止所有活跃策略
        for strategy_id in list(self.active_strategies.keys()):
            await self.stop_strategy_execution(strategy_id)
        
        # 停止监控任务
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("策略执行服务已停止")
    
    async def start_strategy_execution(
        self,
        strategy_id: int,
        user_id: int,
        exchange: str,
        symbols: List[str],
        execution_mode: StrategyExecutionMode,
        db: AsyncSession,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """启动策略执行"""
        try:
            self.logger.info(f"启动策略执行: {strategy_id}")
            
            # 检查策略是否已在运行
            if strategy_id in self.active_strategies:
                self.logger.warning(f"策略 {strategy_id} 已在运行中")
                return False
            
            # 获取策略信息
            strategy = await StrategyService.get_strategy_by_id(db, strategy_id, user_id)
            if not strategy:
                self.logger.error(f"策略不存在: {strategy_id}")
                return False
            
            # 编译策略代码
            compiled_strategy = await self._compile_strategy_code(strategy)
            if not compiled_strategy:
                self.logger.error(f"策略代码编译失败: {strategy_id}")
                return False
            
            self.compiled_strategies[strategy_id] = compiled_strategy
            
            # 创建执行上下文
            session_id = str(uuid.uuid4())
            context = StrategyContext(
                strategy_id=strategy_id,
                user_id=user_id,
                session_id=session_id,
                exchange=exchange,
                symbols=symbols,
                parameters=parameters or json.loads(strategy.parameters or '{}'),
                execution_mode=execution_mode,
                status=StrategyExecutionStatus.INITIALIZING
            )
            
            self.active_strategies[strategy_id] = context
            
            # 在实盘交易引擎中创建会话
            engine_session_id = await live_trading_engine.create_trading_session(
                user_id=user_id,
                exchange=exchange,
                symbols=symbols,
                strategy_id=strategy_id,
                execution_mode=execution_mode
            )
            
            # 启动策略执行任务
            execution_task = asyncio.create_task(
                self._strategy_execution_loop(context, compiled_strategy, db)
            )
            self.execution_tasks[strategy_id] = execution_task
            
            context.status = StrategyExecutionStatus.RUNNING
            context.start_time = datetime.utcnow()
            
            self.stats['total_strategies_executed'] += 1
            self.logger.info(f"策略执行已启动: {strategy_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动策略执行失败: {strategy_id}, 错误: {str(e)}")
            return False
    
    async def stop_strategy_execution(self, strategy_id: int) -> bool:
        """停止策略执行"""
        try:
            if strategy_id not in self.active_strategies:
                return False
            
            context = self.active_strategies[strategy_id]
            context.status = StrategyExecutionStatus.STOPPING
            
            # 取消执行任务
            if strategy_id in self.execution_tasks:
                task = self.execution_tasks[strategy_id]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del self.execution_tasks[strategy_id]
            
            # 停止实盘交易引擎中的会话
            await live_trading_engine.stop_trading_session(context.session_id)
            
            # 清理资源
            context.status = StrategyExecutionStatus.STOPPED
            del self.active_strategies[strategy_id]
            
            if strategy_id in self.compiled_strategies:
                del self.compiled_strategies[strategy_id]
            
            self.logger.info(f"策略执行已停止: {strategy_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"停止策略执行失败: {strategy_id}, 错误: {str(e)}")
            return False
    
    async def _strategy_execution_loop(
        self,
        context: StrategyContext,
        compiled_strategy: types.ModuleType,
        db: AsyncSession
    ):
        """策略执行主循环"""
        try:
            self.logger.info(f"策略 {context.strategy_id} 开始执行循环")
            
            # 初始化策略
            await self._initialize_strategy(context, compiled_strategy)
            
            while self._running and context.status == StrategyExecutionStatus.RUNNING:
                try:
                    execution_start = datetime.utcnow()
                    
                    # 更新市场数据
                    await self._update_market_data(context)
                    
                    # 计算技术指标
                    await self._calculate_indicators(context, compiled_strategy)
                    
                    # 执行策略逻辑生成信号
                    signals = await self._execute_strategy_logic(context, compiled_strategy)
                    
                    # 处理生成的信号
                    if signals:
                        await self._process_generated_signals(context, signals, db)
                    
                    # 更新性能指标
                    await self._update_performance_metrics(context, db)
                    
                    # 记录执行时间
                    execution_time = (datetime.utcnow() - execution_start).total_seconds() * 1000
                    self._update_execution_stats(execution_time)
                    
                    context.last_tick_time = datetime.utcnow()
                    
                    # 等待下一个执行周期
                    await asyncio.sleep(1)  # 1秒周期
                    
                except Exception as e:
                    await self._handle_strategy_error(context, str(e))
                    await asyncio.sleep(5)  # 错误时等待更长时间
            
        except asyncio.CancelledError:
            self.logger.info(f"策略 {context.strategy_id} 执行循环被取消")
        except Exception as e:
            self.logger.error(f"策略 {context.strategy_id} 执行循环异常: {str(e)}")
            context.status = StrategyExecutionStatus.CRASHED
        finally:
            self.logger.info(f"策略 {context.strategy_id} 执行循环结束")
    
    async def _compile_strategy_code(self, strategy: Strategy) -> Optional[types.ModuleType]:
        """编译策略代码"""
        try:
            self.logger.info(f"编译策略代码: {strategy.id}")
            
            # 验证代码安全性
            is_valid, error_msg = await StrategyService.validate_strategy_code(strategy.code)
            if not is_valid:
                self.logger.error(f"策略代码验证失败: {error_msg}")
                return None
            
            # 动态编译代码
            spec = importlib.util.spec_from_loader(
                f"strategy_{strategy.id}",
                loader=None
            )
            module = importlib.util.module_from_spec(spec)
            
            # 添加常用的交易库和函数
            module.np = np
            module.pd = pd
            module.datetime = datetime
            module.logger = self.logger.bind(strategy_id=strategy.id)
            
            # 执行策略代码
            exec(strategy.code, module.__dict__)
            
            # 验证必需的函数
            required_functions = []
            if hasattr(module, 'on_tick'):
                required_functions.append('on_tick')
            if hasattr(module, 'on_bar'):
                required_functions.append('on_bar')
            if hasattr(module, 'generate_signal'):
                required_functions.append('generate_signal')
            
            if not required_functions:
                self.logger.warning(f"策略 {strategy.id} 缺少标准函数，将使用默认实现")
            
            self.logger.info(f"策略代码编译成功: {strategy.id}, 函数: {required_functions}")
            return module
            
        except Exception as e:
            self.logger.error(f"编译策略代码失败: {strategy.id}, 错误: {str(e)}")
            return None
    
    async def _initialize_strategy(self, context: StrategyContext, compiled_strategy: types.ModuleType):
        """初始化策略"""
        try:
            # 初始化市场数据存储
            for symbol in context.symbols:
                context.market_data[symbol] = {
                    'current_price': 0.0,
                    'bid_price': 0.0,
                    'ask_price': 0.0,
                    'volume': 0.0,
                    'bars': [],
                    'last_update': datetime.utcnow()
                }
                context.positions[symbol] = 0.0
            
            # 调用策略初始化函数（如果存在）
            if hasattr(compiled_strategy, 'initialize'):
                await self._safe_call_strategy_function(
                    compiled_strategy.initialize,
                    context,
                    "初始化"
                )
            
            self.logger.info(f"策略 {context.strategy_id} 初始化完成")
            
        except Exception as e:
            self.logger.error(f"策略初始化失败: {context.strategy_id}, 错误: {str(e)}")
            raise
    
    async def _update_market_data(self, context: StrategyContext):
        """更新市场数据"""
        try:
            for symbol in context.symbols:
                # 获取当前价格
                current_price = await exchange_service.get_current_price(
                    context.exchange, symbol
                )
                
                if current_price:
                    market_data = context.market_data[symbol]
                    market_data['current_price'] = current_price
                    market_data['last_update'] = datetime.utcnow()
                    
                    # 获取订单簿数据
                    orderbook = await exchange_service.get_orderbook(
                        context.exchange, symbol
                    )
                    if orderbook:
                        market_data['bid_price'] = orderbook.get('bid', current_price)
                        market_data['ask_price'] = orderbook.get('ask', current_price)
                    
                    # 获取最新K线数据
                    bars = await exchange_service.get_recent_klines(
                        context.exchange, symbol, limit=100
                    )
                    if bars:
                        market_data['bars'] = bars
                        
        except Exception as e:
            self.logger.error(f"更新市场数据失败: {context.strategy_id}, 错误: {str(e)}")
    
    async def _calculate_indicators(self, context: StrategyContext, compiled_strategy: types.ModuleType):
        """计算技术指标"""
        try:
            for symbol in context.symbols:
                market_data = context.market_data[symbol]
                bars = market_data.get('bars', [])
                
                if not bars or len(bars) < 20:  # 需要足够的数据
                    continue
                
                # 转换为pandas DataFrame
                df = pd.DataFrame(bars)
                if df.empty:
                    continue
                
                # 计算常用技术指标
                indicators = await self._calculate_standard_indicators(df)
                context.indicators[symbol] = indicators
                
                # 调用策略的自定义指标计算函数
                if hasattr(compiled_strategy, 'calculate_indicators'):
                    custom_indicators = await self._safe_call_strategy_function(
                        compiled_strategy.calculate_indicators,
                        df, context.parameters,
                        "计算指标"
                    )
                    if custom_indicators and isinstance(custom_indicators, dict):
                        context.indicators[symbol].update(custom_indicators)
                        
        except Exception as e:
            self.logger.error(f"计算技术指标失败: {context.strategy_id}, 错误: {str(e)}")
    
    async def _calculate_standard_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算标准技术指标"""
        indicators = {}
        
        if 'close' not in df.columns or len(df) < 20:
            return indicators
        
        try:
            prices = df['close']
            
            # 移动平均线
            indicators['ma_5'] = prices.rolling(5).mean().iloc[-1]
            indicators['ma_10'] = prices.rolling(10).mean().iloc[-1]
            indicators['ma_20'] = prices.rolling(20).mean().iloc[-1]
            
            # RSI
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1]
            
            # MACD
            exp1 = prices.ewm(span=12).mean()
            exp2 = prices.ewm(span=26).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9).mean()
            indicators['macd'] = macd.iloc[-1]
            indicators['macd_signal'] = signal.iloc[-1]
            indicators['macd_histogram'] = (macd - signal).iloc[-1]
            
            # 布林带
            bb_period = 20
            bb_std = 2
            bb_middle = prices.rolling(bb_period).mean()
            bb_std_dev = prices.rolling(bb_period).std()
            indicators['bb_upper'] = (bb_middle + bb_std_dev * bb_std).iloc[-1]
            indicators['bb_middle'] = bb_middle.iloc[-1]
            indicators['bb_lower'] = (bb_middle - bb_std_dev * bb_std).iloc[-1]
            
        except Exception as e:
            self.logger.error(f"计算标准指标失败: {str(e)}")
        
        return indicators
    
    async def _execute_strategy_logic(
        self,
        context: StrategyContext,
        compiled_strategy: types.ModuleType
    ) -> List[GeneratedSignal]:
        """执行策略逻辑生成信号"""
        signals = []
        
        try:
            for symbol in context.symbols:
                market_data = context.market_data[symbol]
                indicators = context.indicators.get(symbol, {})
                current_position = context.positions[symbol]
                
                # 准备策略输入数据
                strategy_data = {
                    'symbol': symbol,
                    'price': market_data['current_price'],
                    'bid': market_data['bid_price'],
                    'ask': market_data['ask_price'],
                    'position': current_position,
                    'indicators': indicators,
                    'parameters': context.parameters,
                    'bars': market_data.get('bars', [])
                }
                
                # 调用策略的信号生成函数
                if hasattr(compiled_strategy, 'generate_signal'):
                    signal_data = await self._safe_call_strategy_function(
                        compiled_strategy.generate_signal,
                        strategy_data,
                        "生成信号"
                    )
                    
                    if signal_data and self._is_valid_signal(signal_data):
                        signal = self._create_generated_signal(
                            context, symbol, signal_data, indicators
                        )
                        signals.append(signal)
                
                # 检查默认信号生成逻辑
                elif self._should_generate_default_signals():
                    default_signal = await self._generate_default_signal(
                        context, symbol, strategy_data
                    )
                    if default_signal:
                        signals.append(default_signal)
                        
        except Exception as e:
            self.logger.error(f"执行策略逻辑失败: {context.strategy_id}, 错误: {str(e)}")
        
        return signals
    
    async def _process_generated_signals(
        self,
        context: StrategyContext,
        signals: List[GeneratedSignal],
        db: AsyncSession
    ):
        """处理生成的交易信号"""
        for signal in signals:
            try:
                self.logger.info(
                    f"处理信号: {signal.symbol}, {signal.signal_type}, "
                    f"强度: {signal.strength.value}, 置信度: {signal.confidence}"
                )
                
                # 根据执行模式决定是否自动执行
                should_execute = self._should_auto_execute_signal(context, signal)
                
                if should_execute:
                    # 转换为实盘交易引擎信号
                    trading_signal = TradingSignal(
                        user_id=context.user_id,
                        strategy_id=context.strategy_id,
                        exchange=context.exchange,
                        symbol=signal.symbol,
                        signal_type=signal.signal_type,
                        quantity=signal.quantity,
                        price=signal.price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        confidence=signal.confidence,
                        reason=signal.reason
                    )
                    
                    # 提交到实盘交易引擎
                    success = await live_trading_engine.submit_trading_signal(trading_signal)
                    
                    if success:
                        context.signal_count += 1
                        self.stats['total_signals_generated'] += 1
                        self.stats['successful_executions'] += 1
                        self.logger.info(f"信号提交成功: {signal.signal_id}")
                    else:
                        self.stats['failed_executions'] += 1
                        self.logger.error(f"信号提交失败: {signal.signal_id}")
                else:
                    self.logger.info(f"信号需要手动确认: {signal.signal_id}")
                    # TODO: 发送给前端用户确认
                    
            except Exception as e:
                self.logger.error(f"处理信号失败: {signal.signal_id}, 错误: {str(e)}")
    
    def _should_auto_execute_signal(self, context: StrategyContext, signal: GeneratedSignal) -> bool:
        """判断是否应该自动执行信号"""
        if context.execution_mode == StrategyExecutionMode.MANUAL:
            return False
        elif context.execution_mode == StrategyExecutionMode.SEMI_AUTO:
            # 只有强信号和关键信号才自动执行
            return signal.strength in [SignalStrength.STRONG, SignalStrength.CRITICAL]
        elif context.execution_mode == StrategyExecutionMode.FULL_AUTO:
            return True
        
        return False
    
    async def _safe_call_strategy_function(
        self,
        func: Callable,
        *args,
        operation_name: str = "策略函数调用"
    ) -> Any:
        """安全调用策略函数"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args)
            else:
                return func(*args)
        except Exception as e:
            self.logger.error(f"{operation_name}失败: {str(e)}")
            return None
    
    def _is_valid_signal(self, signal_data: Any) -> bool:
        """验证信号数据有效性"""
        if not isinstance(signal_data, dict):
            return False
        
        required_fields = ['signal_type', 'quantity']
        return all(field in signal_data for field in required_fields)
    
    def _create_generated_signal(
        self,
        context: StrategyContext,
        symbol: str,
        signal_data: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> GeneratedSignal:
        """创建生成的信号对象"""
        signal_id = str(uuid.uuid4())
        
        # 确定信号强度
        strength = SignalStrength.MODERATE
        if 'strength' in signal_data:
            try:
                strength = SignalStrength(signal_data['strength'])
            except ValueError:
                pass
        
        return GeneratedSignal(
            signal_id=signal_id,
            strategy_id=context.strategy_id,
            symbol=symbol,
            signal_type=signal_data['signal_type'].upper(),
            strength=strength,
            quantity=float(signal_data['quantity']),
            price=signal_data.get('price'),
            stop_loss=signal_data.get('stop_loss'),
            take_profit=signal_data.get('take_profit'),
            confidence=float(signal_data.get('confidence', 1.0)),
            reason=signal_data.get('reason', ''),
            indicators=indicators.copy()
        )
    
    async def _monitoring_loop(self):
        """监控循环"""
        try:
            self.logger.info("策略执行监控循环开始")
            
            while self._running:
                try:
                    # 监控策略健康状况
                    await self._monitor_strategy_health()
                    
                    # 更新整体统计
                    await self._update_service_statistics()
                    
                    # 清理资源
                    await self._cleanup_resources()
                    
                    await asyncio.sleep(30)  # 30秒监控周期
                    
                except Exception as e:
                    self.logger.error(f"监控循环异常: {str(e)}")
                    await asyncio.sleep(10)
                    
        except asyncio.CancelledError:
            self.logger.info("策略执行监控循环被取消")
        except Exception as e:
            self.logger.error(f"监控循环异常: {str(e)}")
    
    async def _monitor_strategy_health(self):
        """监控策略健康状况"""
        for strategy_id, context in list(self.active_strategies.items()):
            try:
                # 检查执行任务是否还在运行
                if strategy_id in self.execution_tasks:
                    task = self.execution_tasks[strategy_id]
                    if task.done():
                        exception = task.exception()
                        if exception:
                            self.logger.error(f"策略 {strategy_id} 执行任务异常: {exception}")
                            context.status = StrategyExecutionStatus.CRASHED
                        else:
                            context.status = StrategyExecutionStatus.STOPPED
                        
                        # 清理任务
                        del self.execution_tasks[strategy_id]
                
                # 检查最后更新时间
                if context.last_tick_time:
                    time_since_last_tick = (datetime.utcnow() - context.last_tick_time).total_seconds()
                    if time_since_last_tick > 300:  # 5分钟无更新
                        self.logger.warning(f"策略 {strategy_id} 可能无响应，最后更新: {context.last_tick_time}")
                
                # 检查错误计数
                if context.error_count > 10:
                    self.logger.error(f"策略 {strategy_id} 错误过多，考虑停止执行")
                    context.status = StrategyExecutionStatus.ERROR
                    
            except Exception as e:
                self.logger.error(f"监控策略健康异常: {strategy_id}, 错误: {str(e)}")
    
    # 查询接口
    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """获取活跃策略列表"""
        strategies = []
        for strategy_id, context in self.active_strategies.items():
            strategies.append({
                'strategy_id': strategy_id,
                'user_id': context.user_id,
                'session_id': context.session_id,
                'exchange': context.exchange,
                'symbols': context.symbols,
                'status': context.status.value,
                'execution_mode': context.execution_mode.value,
                'start_time': context.start_time.isoformat() if context.start_time else None,
                'last_tick_time': context.last_tick_time.isoformat() if context.last_tick_time else None,
                'error_count': context.error_count,
                'signal_count': context.signal_count,
                'total_pnl': context.total_pnl,
                'win_rate': context.win_rate
            })
        
        return strategies
    
    def get_strategy_context(self, strategy_id: int) -> Optional[StrategyContext]:
        """获取策略执行上下文"""
        return self.active_strategies.get(strategy_id)
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        uptime = (datetime.utcnow() - self.stats['uptime_start']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'active_strategies_count': len(self.active_strategies),
            'running_tasks_count': len(self.execution_tasks)
        }
    
    async def update_strategy_parameters(
        self,
        strategy_id: int,
        new_parameters: Dict[str, Any]
    ) -> bool:
        """动态更新策略参数"""
        try:
            if strategy_id not in self.active_strategies:
                return False
            
            context = self.active_strategies[strategy_id]
            context.parameters.update(new_parameters)
            
            self.logger.info(f"策略 {strategy_id} 参数已更新: {new_parameters}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新策略参数失败: {strategy_id}, 错误: {str(e)}")
            return False
    
    # 辅助方法
    async def _handle_strategy_error(self, context: StrategyContext, error_msg: str):
        """处理策略执行错误"""
        context.error_count += 1
        context.recent_errors.append(f"{datetime.utcnow().isoformat()}: {error_msg}")
        
        # 保留最近10个错误
        if len(context.recent_errors) > 10:
            context.recent_errors.pop(0)
        
        self.logger.error(f"策略 {context.strategy_id} 执行错误: {error_msg}")
        
        # 错误过多时暂停策略
        if context.error_count > 5:
            context.status = StrategyExecutionStatus.ERROR
            self.logger.error(f"策略 {context.strategy_id} 错误过多，已暂停执行")
    
    def _should_generate_default_signals(self) -> bool:
        """是否应该生成默认信号（基于简单的技术指标）"""
        return True  # 可配置
    
    async def _generate_default_signal(
        self,
        context: StrategyContext,
        symbol: str,
        strategy_data: Dict[str, Any]
    ) -> Optional[GeneratedSignal]:
        """生成默认交易信号（简单的移动平均策略）"""
        try:
            indicators = strategy_data.get('indicators', {})
            current_price = strategy_data.get('price', 0)
            
            if not indicators or current_price <= 0:
                return None
            
            ma_5 = indicators.get('ma_5')
            ma_20 = indicators.get('ma_20')
            rsi = indicators.get('rsi')
            
            if not all([ma_5, ma_20, rsi]):
                return None
            
            signal_type = None
            strength = SignalStrength.WEAK
            reason = ""
            
            # 简单的移动平均交叉策略
            if ma_5 > ma_20 and rsi < 30:  # 金叉且超卖
                signal_type = 'BUY'
                strength = SignalStrength.MODERATE
                reason = "MA金叉且RSI超卖"
            elif ma_5 < ma_20 and rsi > 70:  # 死叉且超买
                signal_type = 'SELL'
                strength = SignalStrength.MODERATE
                reason = "MA死叉且RSI超买"
            
            if signal_type:
                return GeneratedSignal(
                    signal_id=str(uuid.uuid4()),
                    strategy_id=context.strategy_id,
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=strength,
                    quantity=0.1,  # 默认数量
                    confidence=0.6,  # 较低置信度
                    reason=reason,
                    indicators=indicators
                )
            
        except Exception as e:
            self.logger.error(f"生成默认信号失败: {str(e)}")
        
        return None
    
    def _update_execution_stats(self, execution_time_ms: float):
        """更新执行统计"""
        # 更新平均执行时间
        current_avg = self.stats['average_execution_time_ms']
        total_executions = self.stats['successful_executions'] + self.stats['failed_executions']
        
        if total_executions > 0:
            self.stats['average_execution_time_ms'] = (
                (current_avg * (total_executions - 1) + execution_time_ms) / total_executions
            )
    
    async def _update_performance_metrics(self, context: StrategyContext, db: AsyncSession):
        """更新策略性能指标"""
        try:
            # TODO: 实现详细的性能指标计算
            # 这里只是示例实现
            pass
        except Exception as e:
            self.logger.error(f"更新性能指标失败: {context.strategy_id}, 错误: {str(e)}")
    
    async def _update_service_statistics(self):
        """更新服务统计信息"""
        try:
            # 计算成功率
            total_executions = self.stats['successful_executions'] + self.stats['failed_executions']
            if total_executions > 0:
                success_rate = (self.stats['successful_executions'] / total_executions) * 100
                self.stats['success_rate'] = round(success_rate, 2)
        except Exception as e:
            self.logger.error(f"更新服务统计异常: {str(e)}")
    
    async def _cleanup_resources(self):
        """清理资源"""
        try:
            # 清理已完成的任务
            completed_tasks = [
                strategy_id for strategy_id, task in self.execution_tasks.items()
                if task.done()
            ]
            
            for strategy_id in completed_tasks:
                del self.execution_tasks[strategy_id]
            
        except Exception as e:
            self.logger.error(f"清理资源异常: {str(e)}")


# 全局策略执行服务实例
strategy_executor_service = StrategyExecutorService()