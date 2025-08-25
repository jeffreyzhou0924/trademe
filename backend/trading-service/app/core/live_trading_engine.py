"""
实盘交易引擎 - 核心交易执行和管理系统

功能特性:
- 策略自动执行
- 实时仓位管理
- 止损止盈自动化
- 交易会话管理
- 风险控制集成
- 实时监控和告警
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple, Callable
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

from app.models.trade import Trade
from app.models.strategy import Strategy
from app.models.user import User
from app.core.risk_manager import risk_manager, OrderRiskAssessment
from app.core.order_manager import order_manager, OrderRequest, OrderSide, OrderType, OrderStatus
from app.services.trade_service import trade_service
from app.services.exchange_service import exchange_service


class TradingSessionStatus(Enum):
    """交易会话状态"""
    INACTIVE = "inactive"      # 未激活
    ACTIVE = "active"         # 激活中
    PAUSED = "paused"         # 暂停
    STOPPING = "stopping"     # 停止中
    STOPPED = "stopped"       # 已停止
    ERROR = "error"           # 错误状态


class StrategyExecutionMode(Enum):
    """策略执行模式"""
    MANUAL = "manual"         # 手动确认
    SEMI_AUTO = "semi_auto"   # 半自动
    FULL_AUTO = "full_auto"   # 全自动


@dataclass
class TradingSession:
    """交易会话"""
    id: str
    user_id: int
    strategy_id: Optional[int]
    exchange: str
    symbols: List[str]
    status: TradingSessionStatus = TradingSessionStatus.INACTIVE
    execution_mode: StrategyExecutionMode = StrategyExecutionMode.MANUAL
    max_daily_trades: int = 100
    max_open_positions: int = 5
    stop_loss_enabled: bool = True
    take_profit_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    total_trades: int = 0
    daily_pnl: float = 0.0
    error_message: Optional[str] = None


@dataclass
class PositionManager:
    """持仓管理器"""
    user_id: int
    exchange: str
    symbol: str
    current_quantity: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_order_id: Optional[str] = None
    take_profit_order_id: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradingSignal:
    """交易信号"""
    user_id: int
    strategy_id: Optional[int]
    exchange: str
    symbol: str
    signal_type: str  # BUY, SELL, CLOSE
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 1.0
    reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed: bool = False


class LiveTradingEngine:
    """实盘交易引擎"""
    
    def __init__(self):
        """初始化交易引擎"""
        self._sessions: Dict[str, TradingSession] = {}
        self._positions: Dict[str, PositionManager] = {}  # key: f"{user_id}_{exchange}_{symbol}"
        self._pending_signals: List[TradingSignal] = []
        self._engine_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 性能统计
        self._stats = {
            'total_signals_processed': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'risk_rejections': 0,
            'uptime_start': datetime.utcnow()
        }
    
    async def start_engine(self):
        """启动交易引擎"""
        if self._running:
            return
            
        try:
            self._running = True
            logger.info("启动实盘交易引擎...")
            
            # 启动主引擎任务
            self._engine_task = asyncio.create_task(self._engine_main_loop())
            
            # 启动监控任务
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            logger.info("实盘交易引擎启动成功")
            
        except Exception as e:
            logger.error(f"启动交易引擎失败: {str(e)}")
            self._running = False
            raise
    
    async def stop_engine(self):
        """停止交易引擎"""
        if not self._running:
            return
            
        try:
            logger.info("停止实盘交易引擎...")
            self._running = False
            
            # 停止所有交易会话
            for session_id in list(self._sessions.keys()):
                await self.stop_trading_session(session_id)
            
            # 取消任务
            if self._engine_task:
                self._engine_task.cancel()
                try:
                    await self._engine_task
                except asyncio.CancelledError:
                    pass
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("实盘交易引擎已停止")
            
        except Exception as e:
            logger.error(f"停止交易引擎异常: {str(e)}")
    
    async def create_trading_session(
        self,
        user_id: int,
        exchange: str,
        symbols: List[str],
        strategy_id: Optional[int] = None,
        execution_mode: StrategyExecutionMode = StrategyExecutionMode.MANUAL,
        **kwargs
    ) -> str:
        """创建交易会话"""
        try:
            session_id = str(uuid.uuid4())
            
            session = TradingSession(
                id=session_id,
                user_id=user_id,
                strategy_id=strategy_id,
                exchange=exchange,
                symbols=symbols,
                execution_mode=execution_mode,
                max_daily_trades=kwargs.get('max_daily_trades', 100),
                max_open_positions=kwargs.get('max_open_positions', 5),
                stop_loss_enabled=kwargs.get('stop_loss_enabled', True),
                take_profit_enabled=kwargs.get('take_profit_enabled', True)
            )
            
            self._sessions[session_id] = session
            
            # 初始化持仓管理器
            for symbol in symbols:
                position_key = f"{user_id}_{exchange}_{symbol}"
                self._positions[position_key] = PositionManager(
                    user_id=user_id,
                    exchange=exchange,
                    symbol=symbol
                )
            
            logger.info(f"创建交易会话: {session_id}, 用户: {user_id}, 交易所: {exchange}")
            return session_id
            
        except Exception as e:
            logger.error(f"创建交易会话失败: {str(e)}")
            raise
    
    async def start_trading_session(self, session_id: str, db: AsyncSession) -> bool:
        """启动交易会话"""
        try:
            if session_id not in self._sessions:
                logger.error(f"交易会话不存在: {session_id}")
                return False
            
            session = self._sessions[session_id]
            
            # 检查风险控制
            emergency_check = await risk_manager.emergency_stop_check(session.user_id, db)
            if emergency_check[0]:
                session.status = TradingSessionStatus.ERROR
                session.error_message = f"风险控制阻止启动: {emergency_check[1]}"
                logger.warning(f"交易会话启动被阻止: {session_id}, 原因: {emergency_check[1]}")
                return False
            
            session.status = TradingSessionStatus.ACTIVE
            session.started_at = datetime.utcnow()
            session.error_message = None
            
            # 加载当前持仓状态
            await self._load_positions(session, db)
            
            logger.info(f"交易会话已启动: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动交易会话失败: {str(e)}")
            return False
    
    async def stop_trading_session(self, session_id: str) -> bool:
        """停止交易会话"""
        try:
            if session_id not in self._sessions:
                return False
            
            session = self._sessions[session_id]
            session.status = TradingSessionStatus.STOPPING
            
            # 取消所有挂单
            # TODO: 实现取消挂单逻辑
            
            session.status = TradingSessionStatus.STOPPED
            session.stopped_at = datetime.utcnow()
            
            logger.info(f"交易会话已停止: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止交易会话失败: {str(e)}")
            return False
    
    async def submit_trading_signal(self, signal: TradingSignal) -> bool:
        """提交交易信号"""
        try:
            # 基础验证
            if not self._validate_signal(signal):
                logger.warning(f"交易信号验证失败: {signal.symbol}")
                return False
            
            # 检查会话状态
            user_sessions = [s for s in self._sessions.values() 
                           if s.user_id == signal.user_id and s.status == TradingSessionStatus.ACTIVE]
            
            if not user_sessions:
                logger.warning(f"用户 {signal.user_id} 没有活跃的交易会话")
                return False
            
            # 添加到信号队列
            self._pending_signals.append(signal)
            logger.info(f"交易信号已提交: {signal.symbol}, {signal.signal_type}, 数量: {signal.quantity}")
            return True
            
        except Exception as e:
            logger.error(f"提交交易信号失败: {str(e)}")
            return False
    
    def _validate_signal(self, signal: TradingSignal) -> bool:
        """验证交易信号"""
        if signal.quantity <= 0:
            return False
        if signal.signal_type not in ['BUY', 'SELL', 'CLOSE']:
            return False
        if not signal.symbol or '/' not in signal.symbol:
            return False
        return True
    
    async def _engine_main_loop(self):
        """引擎主循环"""
        try:
            logger.info("交易引擎主循环开始")
            
            while self._running:
                try:
                    # 处理待处理的交易信号
                    await self._process_pending_signals()
                    
                    # 管理活跃持仓
                    await self._manage_positions()
                    
                    # 检查止损止盈
                    await self._check_stop_orders()
                    
                    # 清理已完成的会话
                    await self._cleanup_sessions()
                    
                    # 等待下一个周期
                    await asyncio.sleep(1)  # 1秒周期
                    
                except Exception as e:
                    logger.error(f"引擎主循环异常: {str(e)}")
                    await asyncio.sleep(5)  # 异常时等待更长时间
                    
        except asyncio.CancelledError:
            logger.info("交易引擎主循环被取消")
        except Exception as e:
            logger.error(f"交易引擎主循环严重异常: {str(e)}")
        finally:
            logger.info("交易引擎主循环结束")
    
    async def _process_pending_signals(self):
        """处理待处理的交易信号"""
        if not self._pending_signals:
            return
            
        # 批量处理信号
        signals_to_process = self._pending_signals[:10]  # 每次最多处理10个
        self._pending_signals = self._pending_signals[10:]
        
        for signal in signals_to_process:
            try:
                # TODO: 需要从外部传入数据库会话
                # 这里暂时使用 None，实际应该从调用处传入
                await self._execute_trading_signal(signal, None)
                self._stats['total_signals_processed'] += 1
            except Exception as e:
                logger.error(f"执行交易信号异常: {str(e)}")
                self._stats['failed_executions'] += 1
    
    async def _execute_trading_signal(self, signal: TradingSignal, db: AsyncSession):
        """执行单个交易信号"""
        try:
            # 查找对应的交易会话
            session = self._find_session_for_signal(signal)
            if not session:
                logger.warning(f"未找到匹配的交易会话: {signal.symbol}")
                return
            
            # 检查会话状态和限制
            if not self._check_session_limits(session, signal):
                logger.warning(f"交易会话限制检查失败: {session.id}")
                return
            
            logger.info(f"执行交易信号: {signal.symbol}, {signal.signal_type}, {signal.quantity}")
            
            # 根据信号类型执行不同操作
            execution_result = None
            if signal.signal_type == 'BUY':
                execution_result = await self._execute_buy_signal(signal, session, db)
            elif signal.signal_type == 'SELL':
                execution_result = await self._execute_sell_signal(signal, session, db)
            elif signal.signal_type == 'CLOSE':
                execution_result = await self._execute_close_signal(signal, session, db)
            
            if execution_result and execution_result.get('success'):
                signal.executed = True
                session.total_trades += 1
                
                # 更新持仓信息
                await self._update_position_after_trade(signal, execution_result, session)
                
                self._stats['successful_executions'] += 1
                logger.info(f"交易信号执行成功: {signal.symbol}")
            else:
                error_msg = execution_result.get('error', '未知错误') if execution_result else '无执行结果'
                logger.error(f"交易信号执行失败: {signal.symbol}, 错误: {error_msg}")
                self._stats['failed_executions'] += 1
            
        except Exception as e:
            logger.error(f"执行交易信号异常: {signal.symbol}, 错误: {str(e)}")
            self._stats['failed_executions'] += 1
    
    def _find_session_for_signal(self, signal: TradingSignal) -> Optional[TradingSession]:
        """为信号查找匹配的交易会话"""
        for session in self._sessions.values():
            if (session.user_id == signal.user_id and 
                session.exchange == signal.exchange and
                signal.symbol in session.symbols and
                session.status == TradingSessionStatus.ACTIVE):
                return session
        return None
    
    def _check_session_limits(self, session: TradingSession, signal: TradingSignal) -> bool:
        """检查会话限制"""
        # 检查日交易次数
        if session.total_trades >= session.max_daily_trades:
            return False
        
        # 检查开仓数量
        user_positions = [p for p in self._positions.values() 
                         if p.user_id == session.user_id and p.current_quantity != 0]
        if len(user_positions) >= session.max_open_positions and signal.signal_type in ['BUY', 'SELL']:
            return False
        
        return True
    
    async def _execute_buy_signal(self, signal: TradingSignal, session: TradingSession, db: AsyncSession) -> Dict[str, Any]:
        """执行买入信号"""
        try:
            logger.info(f"执行买入信号: {signal.symbol}, 数量: {signal.quantity}")
            
            # 创建订单请求
            order_request = OrderRequest(
                user_id=signal.user_id,
                exchange=signal.exchange,
                symbol=signal.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET if not signal.price else OrderType.LIMIT,
                quantity=signal.quantity,
                price=signal.price
            )
            
            # 通过订单管理器执行订单
            # 注意: 这里需要数据库会话，实际部署时需要传入
            # 暂时直接调用exchange_service
            from app.services.exchange_service import exchange_service
            
            result = await exchange_service.place_order(
                user_id=signal.user_id,
                exchange_name=signal.exchange,
                symbol=signal.symbol,
                order_type='market' if not signal.price else 'limit',
                side='buy',
                amount=signal.quantity,
                price=signal.price,
                db=db,
                skip_risk_check=False
            )
            
            if result and result.get('success'):
                logger.info(f"买入订单执行成功: {result.get('id')}")
                
                # 设置止损止盈
                if signal.stop_loss or signal.take_profit:
                    await self._set_stop_orders(signal, result, session)
                
                return {
                    'success': True,
                    'order_id': result.get('id'),
                    'filled_quantity': result.get('filled', 0),
                    'avg_price': result.get('price', signal.price),
                    'total_cost': result.get('cost', 0)
                }
            else:
                error_msg = result.get('error', '买入订单执行失败') if result else '无响应'
                logger.error(f"买入订单执行失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"执行买入信号异常: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_sell_signal(self, signal: TradingSignal, session: TradingSession, db: AsyncSession) -> Dict[str, Any]:
        """执行卖出信号"""
        try:
            logger.info(f"执行卖出信号: {signal.symbol}, 数量: {signal.quantity}")
            
            # 创建订单请求
            order_request = OrderRequest(
                user_id=signal.user_id,
                exchange=signal.exchange,
                symbol=signal.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET if not signal.price else OrderType.LIMIT,
                quantity=signal.quantity,
                price=signal.price
            )
            
            # 通过exchange_service执行订单
            from app.services.exchange_service import exchange_service
            
            result = await exchange_service.place_order(
                user_id=signal.user_id,
                exchange_name=signal.exchange,
                symbol=signal.symbol,
                order_type='market' if not signal.price else 'limit',
                side='sell',
                amount=signal.quantity,
                price=signal.price,
                db=db,
                skip_risk_check=False
            )
            
            if result and result.get('success'):
                logger.info(f"卖出订单执行成功: {result.get('id')}")
                
                return {
                    'success': True,
                    'order_id': result.get('id'),
                    'filled_quantity': result.get('filled', 0),
                    'avg_price': result.get('price', signal.price),
                    'total_proceeds': result.get('cost', 0)
                }
            else:
                error_msg = result.get('error', '卖出订单执行失败') if result else '无响应'
                logger.error(f"卖出订单执行失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"执行卖出信号异常: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_close_signal(self, signal: TradingSignal, session: TradingSession, db: AsyncSession) -> Dict[str, Any]:
        """执行平仓信号"""
        try:
            logger.info(f"执行平仓信号: {signal.symbol}")
            
            # 获取当前持仓
            position_key = f"{signal.user_id}_{signal.exchange}_{signal.symbol}"
            if position_key not in self._positions:
                logger.warning(f"未找到持仓信息: {signal.symbol}")
                return {
                    'success': False,
                    'error': '未找到持仓信息'
                }
            
            position = self._positions[position_key]
            if position.current_quantity == 0:
                logger.warning(f"持仓数量为0，无需平仓: {signal.symbol}")
                return {
                    'success': False,
                    'error': '持仓数量为0'
                }
            
            # 确定平仓方向（与持仓方向相反）
            close_side = 'sell' if position.current_quantity > 0 else 'buy'
            close_quantity = abs(position.current_quantity)
            
            # 执行平仓订单
            from app.services.exchange_service import exchange_service
            
            result = await exchange_service.place_order(
                user_id=signal.user_id,
                exchange_name=signal.exchange,
                symbol=signal.symbol,
                order_type='market',  # 平仓使用市价单
                side=close_side,
                amount=close_quantity,
                price=None,
                db=db,
                skip_risk_check=False
            )
            
            if result and result.get('success'):
                logger.info(f"平仓订单执行成功: {result.get('id')}")
                
                # 取消止损止盈订单
                await self._cancel_stop_orders(position)
                
                # 清空持仓
                position.current_quantity = 0
                position.stop_loss_price = None
                position.take_profit_price = None
                position.stop_loss_order_id = None
                position.take_profit_order_id = None
                position.last_updated = datetime.utcnow()
                
                return {
                    'success': True,
                    'order_id': result.get('id'),
                    'closed_quantity': result.get('filled', 0),
                    'avg_price': result.get('price', 0),
                    'total_proceeds': result.get('cost', 0)
                }
            else:
                error_msg = result.get('error', '平仓订单执行失败') if result else '无响应'
                logger.error(f"平仓订单执行失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"执行平仓信号异常: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _manage_positions(self):
        """管理活跃持仓"""
        for position in self._positions.values():
            if position.current_quantity == 0:
                continue
                
            try:
                # TODO: 更新持仓的实时价格和PnL
                # TODO: 检查是否需要调整止损止盈
                pass
            except Exception as e:
                logger.error(f"管理持仓异常: {position.symbol}, 错误: {str(e)}")
    
    async def _check_stop_orders(self):
        """检查止损止盈订单"""
        for position in self._positions.values():
            if position.current_quantity == 0:
                continue
                
            try:
                # TODO: 检查止损条件
                # TODO: 检查止盈条件
                # TODO: 触发相应的止损止盈订单
                pass
            except Exception as e:
                logger.error(f"检查止损止盈异常: {position.symbol}, 错误: {str(e)}")
    
    async def _load_positions(self, session: TradingSession, db: AsyncSession):
        """加载当前持仓状态"""
        try:
            for symbol in session.symbols:
                position_key = f"{session.user_id}_{session.exchange}_{symbol}"
                
                # 从TradeService获取当前持仓
                positions = await trade_service.get_current_positions(
                    db, session.user_id, session.exchange
                )
                
                # 查找对应的持仓
                for pos_data in positions:
                    if pos_data['symbol'] == symbol:
                        if position_key in self._positions:
                            position = self._positions[position_key]
                            position.current_quantity = pos_data['quantity']
                            position.avg_entry_price = pos_data['avg_cost']
                            position.unrealized_pnl = pos_data['unrealized_pnl']
                            position.last_updated = datetime.utcnow()
                        break
                        
        except Exception as e:
            logger.error(f"加载持仓状态失败: {str(e)}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        try:
            logger.info("交易引擎监控循环开始")
            
            while self._running:
                try:
                    # 健康检查
                    await self._health_check()
                    
                    # 性能统计
                    await self._update_statistics()
                    
                    # 风险监控
                    await self._risk_monitoring()
                    
                    await asyncio.sleep(30)  # 30秒周期
                    
                except Exception as e:
                    logger.error(f"监控循环异常: {str(e)}")
                    await asyncio.sleep(10)
                    
        except asyncio.CancelledError:
            logger.info("交易引擎监控循环被取消")
        except Exception as e:
            logger.error(f"交易引擎监控循环异常: {str(e)}")
    
    async def _health_check(self):
        """健康检查"""
        try:
            active_sessions = len([s for s in self._sessions.values() 
                                 if s.status == TradingSessionStatus.ACTIVE])
            active_positions = len([p for p in self._positions.values() 
                                  if p.current_quantity != 0])
            pending_signals = len(self._pending_signals)
            
            logger.debug(f"引擎状态: 活跃会话={active_sessions}, 活跃持仓={active_positions}, 待处理信号={pending_signals}")
            
        except Exception as e:
            logger.error(f"健康检查异常: {str(e)}")
    
    async def _update_statistics(self):
        """更新统计信息"""
        try:
            self._stats['uptime_seconds'] = (datetime.utcnow() - self._stats['uptime_start']).total_seconds()
            
            # 计算成功率
            total_executions = self._stats['successful_executions'] + self._stats['failed_executions']
            success_rate = (self._stats['successful_executions'] / total_executions * 100) if total_executions > 0 else 0
            self._stats['success_rate'] = round(success_rate, 2)
            
        except Exception as e:
            logger.error(f"更新统计异常: {str(e)}")
    
    async def _risk_monitoring(self):
        """风险监控"""
        try:
            # TODO: 检查各个用户的风险状况
            # TODO: 检查整体系统风险
            pass
        except Exception as e:
            logger.error(f"风险监控异常: {str(e)}")
    
    async def _cleanup_sessions(self):
        """清理已完成的会话"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            to_remove = []
            for session_id, session in self._sessions.items():
                if (session.status == TradingSessionStatus.STOPPED and 
                    session.stopped_at and session.stopped_at < cutoff_time):
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                del self._sessions[session_id]
                logger.debug(f"清理已停止的交易会话: {session_id}")
                
        except Exception as e:
            logger.error(f"清理会话异常: {str(e)}")
    
    # 查询接口
    def get_active_sessions(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取活跃交易会话"""
        sessions = []
        for session in self._sessions.values():
            if user_id is None or session.user_id == user_id:
                if session.status in [TradingSessionStatus.ACTIVE, TradingSessionStatus.PAUSED]:
                    sessions.append(self._session_to_dict(session))
        return sessions
    
    def get_positions_summary(self, user_id: int) -> List[Dict[str, Any]]:
        """获取持仓摘要"""
        positions = []
        for position in self._positions.values():
            if position.user_id == user_id and position.current_quantity != 0:
                positions.append({
                    'exchange': position.exchange,
                    'symbol': position.symbol,
                    'quantity': position.current_quantity,
                    'avg_price': position.avg_entry_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'stop_loss': position.stop_loss_price,
                    'take_profit': position.take_profit_price,
                    'last_updated': position.last_updated.isoformat()
                })
        return positions
    
    def get_engine_statistics(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        return self._stats.copy()
    
    def _session_to_dict(self, session: TradingSession) -> Dict[str, Any]:
        """转换会话对象为字典"""
        return {
            'id': session.id,
            'user_id': session.user_id,
            'strategy_id': session.strategy_id,
            'exchange': session.exchange,
            'symbols': session.symbols,
            'status': session.status.value,
            'execution_mode': session.execution_mode.value,
            'max_daily_trades': session.max_daily_trades,
            'max_open_positions': session.max_open_positions,
            'total_trades': session.total_trades,
            'daily_pnl': session.daily_pnl,
            'created_at': session.created_at.isoformat(),
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'error_message': session.error_message
        }


    # 辅助方法
    async def _update_position_after_trade(self, signal: TradingSignal, execution_result: Dict[str, Any], session: TradingSession):
        """交易后更新持仓信息"""
        try:
            position_key = f"{signal.user_id}_{signal.exchange}_{signal.symbol}"
            
            if position_key not in self._positions:
                # 创建新持仓
                self._positions[position_key] = PositionManager(
                    user_id=signal.user_id,
                    exchange=signal.exchange,
                    symbol=signal.symbol
                )
            
            position = self._positions[position_key]
            filled_quantity = execution_result.get('filled_quantity', 0)
            avg_price = execution_result.get('avg_price', 0)
            
            if signal.signal_type == 'BUY':
                # 更新买入持仓
                old_quantity = position.current_quantity
                old_cost = old_quantity * position.avg_entry_price if old_quantity > 0 else 0
                new_cost = filled_quantity * avg_price
                
                position.current_quantity += filled_quantity
                position.avg_entry_price = (old_cost + new_cost) / position.current_quantity if position.current_quantity > 0 else avg_price
                
            elif signal.signal_type == 'SELL':
                # 更新卖出持仓
                position.current_quantity -= filled_quantity
                # 如果全部卖出，清零持仓
                if abs(position.current_quantity) < 0.0001:
                    position.current_quantity = 0
                    position.avg_entry_price = 0
            
            position.last_updated = datetime.utcnow()
            logger.debug(f"持仓更新: {signal.symbol}, 数量: {position.current_quantity}, 均价: {position.avg_entry_price}")
            
        except Exception as e:
            logger.error(f"更新持仓信息异常: {str(e)}")
    
    async def _set_stop_orders(self, signal: TradingSignal, execution_result: Dict[str, Any], session: TradingSession):
        """设置止损止盈订单"""
        try:
            position_key = f"{signal.user_id}_{signal.exchange}_{signal.symbol}"
            if position_key in self._positions:
                position = self._positions[position_key]
                
                if signal.stop_loss:
                    position.stop_loss_price = signal.stop_loss
                    # TODO: 实际在交易所放置止损单
                    
                if signal.take_profit:
                    position.take_profit_price = signal.take_profit
                    # TODO: 实际在交易所放置止盈单
                    
                logger.info(f"设置止损止盈: {signal.symbol}, SL: {signal.stop_loss}, TP: {signal.take_profit}")
                
        except Exception as e:
            logger.error(f"设置止损止盈异常: {str(e)}")


# 全局实盘交易引擎实例
live_trading_engine = LiveTradingEngine()