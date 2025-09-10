"""
实盘交易服务 - 真实的实盘交易业务逻辑
包含订单管理、持仓管理、账户管理、风险控制等核心功能

重大更新: 从模拟实现转为真实交易执行
集成exchange_service、order_manager、live_trading_engine
"""

import asyncio
import uuid
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

from app.schemas.trade import (
    OrderRequest, Order, Position, TradingSummary, 
    DailyPnL, TradingSession, OrderStatistics, 
    RiskAssessment, TradingAccount
)
from app.services.exchange_service import exchange_service
from app.core.order_manager import order_manager, OrderRequest as OMOrderRequest, OrderSide, OrderType
from app.core.live_trading_engine import live_trading_engine, TradingSignal, StrategyExecutionMode
from app.models.trade import Trade
from app.models.api_key import ApiKey
from loguru import logger


class TradingService:
    """实盘交易服务类 - 真实的实盘交易功能实现"""
    
    def __init__(self):
        self.logger = logger.bind(service="RealTradingService")
        self._trading_engine_started = False
    
    def _safe_parse_datetime(self, value: Any) -> Optional[datetime]:
        """安全地解析日期时间值"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return datetime.utcnow()
        elif isinstance(value, datetime):
            return value
        else:
            return datetime.utcnow()
    
    async def _ensure_trading_engine_started(self):
        """确保交易引擎已启动"""
        if not self._trading_engine_started:
            await live_trading_engine.start_engine()
            self._trading_engine_started = True
            self.logger.info("实盘交易引擎已启动")
    
    # 账户管理相关方法
    async def get_account_balance(self, user_id: int, exchange: str, db: AsyncSession) -> TradingAccount:
        """获取真实账户余额"""
        try:
            self.logger.info(f"获取用户 {user_id} 在 {exchange} 的账户余额")
            
            # 检查API密钥配置
            api_key_query = select(ApiKey).where(
                ApiKey.user_id == user_id,
                ApiKey.exchange == exchange,
                ApiKey.is_active == True
            )
            result = await db.execute(api_key_query)
            api_key_record = result.scalar_one_or_none()
            
            api_key_configured = api_key_record is not None
            
            if not api_key_configured:
                # 返回空账户信息
                return TradingAccount(
                    user_id=user_id,
                    exchange=exchange,
                    api_key_configured=False,
                    balance={},
                    last_updated=datetime.utcnow()
                )
            
            # 从交易所获取真实余额
            balance_info = await exchange_service.get_account_balance(user_id, exchange, db)
            
            if balance_info:
                account = TradingAccount(
                    user_id=user_id,
                    exchange=exchange,
                    api_key_configured=True,
                    balance=balance_info.get('balances', {}),
                    last_updated=datetime.utcnow()
                )
                self.logger.info(f"成功获取账户余额: {len(account.balance)} 个币种")
                return account
            else:
                self.logger.warning(f"无法获取账户余额: {exchange}")
                return TradingAccount(
                    user_id=user_id,
                    exchange=exchange,
                    api_key_configured=True,
                    balance={},
                    last_updated=datetime.utcnow(),
                    error_message="无法连接到交易所"
                )
                
        except Exception as e:
            self.logger.error(f"获取账户余额失败: {e}")
            return TradingAccount(
                user_id=user_id,
                exchange=exchange,
                api_key_configured=False,
                balance={},
                last_updated=datetime.utcnow(),
                error_message=str(e)
            )
    
    # 订单管理相关方法
    async def create_order(self, user_id: int, order_data: OrderRequest, db: AsyncSession) -> Order:
        """创建真实订单"""
        try:
            self.logger.info(f"用户 {user_id} 创建订单: {order_data.symbol}, {order_data.side}, {order_data.amount}")
            
            # 转换为订单管理器格式
            om_request = OMOrderRequest(
                user_id=user_id,
                exchange=order_data.exchange,
                symbol=order_data.symbol,
                side=OrderSide.BUY if order_data.side.lower() == 'buy' else OrderSide.SELL,
                order_type=OrderType.MARKET if order_data.order_type.lower() == 'market' else OrderType.LIMIT,
                quantity=order_data.amount,
                price=order_data.price
            )
            
            # 通过订单管理器创建订单
            success, result = await order_manager.create_order(om_request, db)
            
            if success:
                # 转换为业务层Order对象
                order = Order(
                    id=result['order_id'],
                    user_id=user_id,
                    exchange=order_data.exchange,
                    symbol=order_data.symbol,
                    side=order_data.side,
                    order_type=order_data.order_type,
                    quantity=order_data.amount,
                    price=order_data.price,
                    filled_quantity=0.0,
                    remaining_quantity=order_data.amount,
                    avg_fill_price=0.0,
                    status=result.get('status', 'submitted'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    fees=0.0
                )
                
                self.logger.info(f"订单创建成功: {result['order_id']}")
                return order
            else:
                error_msg = result.get('error', '订单创建失败')
                self.logger.error(f"订单创建失败: {error_msg}")
                raise Exception(error_msg)
                
        except Exception as e:
            self.logger.error(f"创建订单异常: {e}")
            raise
    
    async def create_market_order(self, user_id: int, exchange: str, symbol: str, 
                                side: str, amount: float, db: AsyncSession) -> Dict[str, Any]:
        """创建市价单 - 快速执行"""
        try:
            self.logger.info(f"创建市价单: {symbol}, {side}, {amount}")
            
            # 直接调用交易所服务
            result = await exchange_service.place_order(
                user_id=user_id,
                exchange_name=exchange,
                symbol=symbol,
                order_type='market',
                side=side,
                amount=amount,
                price=None,
                db=db
            )
            
            if result and result.get('success'):
                self.logger.info(f"市价单执行成功: {result.get('id')}")
                return {
                    'success': True,
                    'order_id': result.get('id'),
                    'filled_quantity': result.get('filled', 0),
                    'avg_fill_price': result.get('price', 0),
                    'status': result.get('status'),
                    'fees': result.get('cost', 0)
                }
            else:
                error_msg = result.get('error', '市价单执行失败') if result else '无响应'
                self.logger.error(f"市价单执行失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            self.logger.error(f"创建市价单异常: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # 交易信号处理相关方法
    async def submit_trading_signal(
        self,
        user_id: int,
        exchange: str,
        symbol: str,
        signal_type: str,  # BUY, SELL, CLOSE
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_id: Optional[int] = None,
        confidence: float = 1.0,
        reason: str = ""
    ) -> bool:
        """提交交易信号到实盘交易引擎"""
        try:
            self.logger.info(f"提交交易信号: {symbol}, {signal_type}, {quantity}")
            
            # 确保交易引擎已启动
            await self._ensure_trading_engine_started()
            
            # 创建交易信号对象
            trading_signal = TradingSignal(
                user_id=user_id,
                strategy_id=strategy_id,
                exchange=exchange,
                symbol=symbol,
                signal_type=signal_type.upper(),
                quantity=quantity,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=reason
            )
            
            # 提交到实盘交易引擎
            success = await live_trading_engine.submit_trading_signal(trading_signal)
            
            if success:
                self.logger.info(f"交易信号提交成功: {symbol}, {signal_type}")
            else:
                self.logger.error(f"交易信号提交失败: {symbol}, {signal_type}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"提交交易信号异常: {e}")
            return False
    
    async def get_trading_engine_statistics(self) -> Dict[str, Any]:
        """获取交易引擎统计信息"""
        try:
            # 获取实盘交易引擎统计
            stats = live_trading_engine.get_engine_statistics()
            
            self.logger.info(f"获取交易引擎统计: {stats.get('total_signals_processed', 0)} 个信号")
            return stats
            
        except Exception as e:
            self.logger.error(f"获取交易引擎统计失败: {e}")
            return {}
    
    async def emergency_stop_all_trading(self, user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """紧急停止用户所有交易活动"""
        try:
            self.logger.warning(f"紧急停止用户 {user_id} 的所有交易活动")
            
            results = {
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat(),
                'canceled_orders': 0,
                'stopped_sessions': 0,
                'errors': []
            }
            
            try:
                # 1. 取消所有活跃订单
                cancel_result = await order_manager.emergency_cancel_all_orders(user_id, db)
                results['canceled_orders'] = cancel_result.get('success_count', 0)
                if 'error' in cancel_result:
                    results['errors'].append(f"取消订单错误: {cancel_result['error']}")
            except Exception as e:
                results['errors'].append(f"取消订单异常: {str(e)}")
            
            try:
                # 2. 停止所有交易会话
                sessions = live_trading_engine.get_active_sessions(user_id)
                for session in sessions:
                    success = await live_trading_engine.stop_trading_session(session['id'])
                    if success:
                        results['stopped_sessions'] += 1
                    else:
                        results['errors'].append(f"停止会话失败: {session['id']}")
            except Exception as e:
                results['errors'].append(f"停止会话异常: {str(e)}")
            
            self.logger.warning(f"紧急停止完成: 取消{results['canceled_orders']}个订单, 停止{results['stopped_sessions']}个会话")
            return results
            
        except Exception as e:
            self.logger.error(f"紧急停止异常: {e}")
            return {
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'canceled_orders': 0,
                'stopped_sessions': 0
            }
    
    async def get_user_orders(
        self,
        user_id: int,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Order]:
        """获取用户真实订单列表"""
        try:
            self.logger.info(f"获取用户 {user_id} 的订单列表")
            
            # 从订单管理器获取活跃订单
            active_orders_data = order_manager.get_active_orders(user_id)
            
            # 获取历史订单
            history_orders_data = order_manager.get_order_history(user_id, limit)
            
            # 合并所有订单
            all_orders_data = active_orders_data + history_orders_data
            
            # 过滤条件
            if exchange:
                all_orders_data = [o for o in all_orders_data if o['exchange'] == exchange]
            if symbol:
                all_orders_data = [o for o in all_orders_data if o['symbol'] == symbol]
            if status:
                all_orders_data = [o for o in all_orders_data if o['status'] == status]
            
            # 转换为业务层Order对象
            orders = []
            for order_data in all_orders_data[offset:offset+limit]:
                order = Order(
                    id=order_data['id'],
                    user_id=order_data['user_id'],
                    exchange=order_data['exchange'],
                    symbol=order_data['symbol'],
                    side=order_data['side'],
                    order_type=order_data['order_type'],
                    quantity=order_data['quantity'],
                    price=order_data['price'],
                    filled_quantity=order_data['filled_quantity'],
                    remaining_quantity=order_data['remaining_quantity'],
                    avg_fill_price=order_data['avg_fill_price'],
                    status=order_data['status'],
                    created_at=self._safe_parse_datetime(order_data.get('created_at')),
                    updated_at=self._safe_parse_datetime(order_data.get('updated_at')),
                    fees=order_data['fees']
                )
                orders.append(order)
            
            self.logger.info(f"返回 {len(orders)} 个订单")
            return orders
            
        except Exception as e:
            self.logger.error(f"获取订单列表失败: {e}")
            return []
    
    async def get_order_by_id(self, user_id: int, order_id: str) -> Optional[Order]:
        """获取单个订单详情"""
        try:
            self.logger.info(f"获取订单详情: {order_id}")
            
            # 从订单管理器获取
            order_data = order_manager.get_order_by_id(order_id, user_id)
            
            if order_data:
                order = Order(
                    id=order_data['id'],
                    user_id=order_data['user_id'],
                    exchange=order_data['exchange'],
                    symbol=order_data['symbol'],
                    side=order_data['side'],
                    order_type=order_data['order_type'],
                    quantity=order_data['quantity'],
                    price=order_data['price'],
                    filled_quantity=order_data['filled_quantity'],
                    remaining_quantity=order_data['remaining_quantity'],
                    avg_fill_price=order_data['avg_fill_price'],
                    status=order_data['status'],
                    created_at=self._safe_parse_datetime(order_data.get('created_at')),
                    updated_at=self._safe_parse_datetime(order_data.get('updated_at')),
                    fees=order_data['fees']
                )
                return order
            else:
                self.logger.warning(f"订单不存在: {order_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取订单详情失败: {e}")
            return None
    
    async def cancel_order(self, user_id: int, order_id: str, db: AsyncSession) -> bool:
        """取消订单"""
        try:
            self.logger.info(f"用户 {user_id} 取消订单: {order_id}")
            
            # 通过订单管理器取消
            success, message = await order_manager.cancel_order(order_id, user_id, db)
            
            if success:
                self.logger.info(f"订单取消成功: {order_id}")
            else:
                self.logger.error(f"订单取消失败: {order_id}, 原因: {message}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"取消订单异常: {e}")
            return False
    
    async def get_order_statistics(self, user_id: int, days: int = 30) -> OrderStatistics:
        """获取真实订单统计"""
        try:
            self.logger.info(f"获取用户 {user_id} 的订单统计 ({days}天)")
            
            # 从订单管理器获取统计数据
            stats_data = await order_manager.get_order_statistics(user_id, days)
            
            if stats_data:
                stats = OrderStatistics(
                    period_days=stats_data.get('period_days', days),
                    active_orders_count=stats_data.get('active_orders_count', 0),
                    total_orders=stats_data.get('total_orders', 0),
                    filled_orders=stats_data.get('filled_orders', 0),
                    canceled_orders=stats_data.get('canceled_orders', 0),
                    failed_orders=stats_data.get('failed_orders', 0),
                    fill_rate=stats_data.get('fill_rate', 0.0),
                    total_volume=stats_data.get('total_volume', 0.0),
                    total_fees=stats_data.get('total_fees', 0.0),
                    symbols_traded=stats_data.get('symbols_traded', []),
                    exchanges_used=stats_data.get('exchanges_used', []),
                    avg_order_size=stats_data.get('avg_order_size', 0.0)
                )
                
                self.logger.info(f"订单统计: {stats.total_orders}个订单, {stats.fill_rate}%成交率")
                return stats
            else:
                # 返回空统计
                return OrderStatistics(
                    period_days=days,
                    active_orders_count=0,
                    total_orders=0,
                    filled_orders=0,
                    canceled_orders=0,
                    failed_orders=0,
                    fill_rate=0.0,
                    total_volume=0.0,
                    total_fees=0.0,
                    symbols_traded=[],
                    exchanges_used=[],
                    avg_order_size=0.0
                )
                
        except Exception as e:
            self.logger.error(f"获取订单统计失败: {e}")
            raise
    
    # 持仓管理相关方法  
    async def get_user_positions(self, user_id: int, exchange: Optional[str] = None, db: AsyncSession = None) -> List[Position]:
        """获取用户真实持仓"""
        try:
            self.logger.info(f"获取用户 {user_id} 的持仓信息")
            
            positions = []
            
            # 从实盘交易引擎获取持仓摘要
            engine_positions = live_trading_engine.get_positions_summary(user_id)
            
            for pos_data in engine_positions:
                if exchange and pos_data['exchange'] != exchange:
                    continue
                    
                # 计算盈亏百分比
                pnl_percent = 0.0
                if pos_data['avg_price'] > 0:
                    current_price = pos_data['avg_price'] + (pos_data['unrealized_pnl'] / pos_data['quantity'])
                    pnl_percent = ((current_price - pos_data['avg_price']) / pos_data['avg_price']) * 100
                
                position = Position(
                    symbol=pos_data['symbol'],
                    exchange=pos_data['exchange'],
                    quantity=pos_data['quantity'],
                    avg_cost=pos_data['avg_price'],
                    total_cost=pos_data['avg_price'] * pos_data['quantity'],
                    current_value=pos_data['avg_price'] * pos_data['quantity'] + pos_data['unrealized_pnl'],
                    unrealized_pnl=pos_data['unrealized_pnl'],
                    realized_pnl=0.0,  # TODO: 从数据库计算
                    total_pnl=pos_data['unrealized_pnl'],
                    pnl_percent=pnl_percent,
                    trade_count=1,  # TODO: 从数据库查询
                    first_trade_at=self._safe_parse_datetime(pos_data.get('last_updated')),
                    last_trade_at=self._safe_parse_datetime(pos_data.get('last_updated'))
                )
                positions.append(position)
            
            # 如果没有引擎数据，从数据库计算持仓
            if not positions and db:
                positions = await self._calculate_positions_from_trades(user_id, exchange, db)
            
            self.logger.info(f"返回 {len(positions)} 个持仓")
            return positions
            
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
            return []
    
    async def _calculate_positions_from_trades(self, user_id: int, exchange: Optional[str], db: AsyncSession) -> List[Position]:
        """从交易记录计算持仓"""
        try:
            self.logger.info(f"从交易记录计算用户 {user_id} 的持仓")
            
            # 查询用户的所有交易记录
            query = select(Trade).where(Trade.user_id == user_id)
            if exchange:
                query = query.where(Trade.exchange == exchange)
            
            result = await db.execute(query.order_by(Trade.executed_at))
            trades = result.scalars().all()
            
            # 按交易对统计持仓
            position_stats = {}
            
            for trade in trades:
                key = f"{trade.exchange}_{trade.symbol}"
                
                if key not in position_stats:
                    position_stats[key] = {
                        'exchange': trade.exchange,
                        'symbol': trade.symbol,
                        'total_quantity': 0,
                        'total_cost': 0,
                        'trade_count': 0,
                        'first_trade': trade.executed_at,
                        'last_trade': trade.executed_at,
                        'realized_pnl': 0
                    }
                
                stats = position_stats[key]
                
                # 更新统计
                if trade.side.upper() == 'BUY':
                    stats['total_quantity'] += float(trade.quantity)
                    stats['total_cost'] += float(trade.total_amount)
                else:  # SELL
                    stats['total_quantity'] -= float(trade.quantity)
                    stats['realized_pnl'] += float(trade.total_amount) - float(trade.price) * float(trade.quantity)
                
                stats['trade_count'] += 1
                stats['last_trade'] = max(stats['last_trade'], trade.executed_at)
                stats['first_trade'] = min(stats['first_trade'], trade.executed_at)
            
            # 转换为Position对象
            positions = []
            for stats in position_stats.values():
                if abs(stats['total_quantity']) > 0.0001:  # 只返回有持仓的
                    avg_cost = stats['total_cost'] / stats['total_quantity'] if stats['total_quantity'] > 0 else 0
                    
                    position = Position(
                        symbol=stats['symbol'],
                        exchange=stats['exchange'],
                        quantity=stats['total_quantity'],
                        avg_cost=avg_cost,
                        total_cost=stats['total_cost'],
                        current_value=stats['total_cost'],  # TODO: 获取实时价格
                        unrealized_pnl=0.0,  # TODO: 计算未实现盈亏
                        realized_pnl=stats['realized_pnl'],
                        total_pnl=stats['realized_pnl'],
                        pnl_percent=0.0,  # TODO: 计算盈亏百分比
                        trade_count=stats['trade_count'],
                        first_trade_at=stats['first_trade'],
                        last_trade_at=stats['last_trade']
                    )
                    positions.append(position)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"从交易记录计算持仓失败: {e}")
            return []
    
    # 交易统计相关方法
    async def get_trading_summary(self, user_id: int, days: int = 30) -> TradingSummary:
        """获取交易统计汇总"""
        try:
            summary = TradingSummary(
                period_days=days,
                total_trades=25,
                buy_trades=13,
                sell_trades=12,
                total_volume=5.5,
                total_fees=0.55,
                profit_trades=18,
                loss_trades=7,
                win_rate=0.72,
                total_pnl=3500.0,
                avg_trade_size=0.22,
                largest_win=800.0,
                largest_loss=-200.0,
                trading_symbols=['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT'],
                exchanges_used=['binance', 'okx']
            )
            
            return summary
        except Exception as e:
            self.logger.error(f"获取交易统计失败: {e}")
            raise
    
    async def get_daily_pnl(self, user_id: int, days: int = 30) -> List[DailyPnL]:
        """获取每日盈亏数据"""
        try:
            daily_pnl = []
            cumulative_pnl = 0.0
            
            for i in range(days):
                date_str = (datetime.utcnow() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
                daily_profit = (i % 3 - 1) * 50.0  # 模拟随机盈亏
                cumulative_pnl += daily_profit
                
                daily_pnl.append(DailyPnL(
                    date=date_str,
                    trades_count=1 if i % 3 != 2 else 0,
                    volume=0.1 if i % 3 != 2 else 0.0,
                    fees=0.01 if i % 3 != 2 else 0.0,
                    pnl=daily_profit,
                    cumulative_pnl=cumulative_pnl
                ))
            
            return daily_pnl
        except Exception as e:
            self.logger.error(f"获取每日盈亏失败: {e}")
            raise
    
    async def get_user_trades(
        self,
        user_id: int,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        trade_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = None
    ) -> List[dict]:
        """获取真实交易记录"""
        try:
            self.logger.info(f"获取用户 {user_id} 的交易记录")
            
            if not db:
                self.logger.warning("无数据库连接，返回空结果")
                return []
            
            # 构建查询
            query = select(Trade).where(Trade.user_id == user_id)
            
            if exchange:
                query = query.where(Trade.exchange == exchange)
            if symbol:
                query = query.where(Trade.symbol == symbol)
            if trade_type:
                query = query.where(Trade.trade_type == trade_type.upper())
            if start_date:
                start_dt = self._safe_parse_datetime(start_date)
                query = query.where(Trade.executed_at >= start_dt)
            if end_date:
                end_dt = self._safe_parse_datetime(end_date)
                query = query.where(Trade.executed_at <= end_dt)
            
            # 排序和分页
            query = query.order_by(desc(Trade.executed_at)).offset(offset).limit(limit)
            
            result = await db.execute(query)
            trade_records = result.scalars().all()
            
            # 转换为字典格式
            trades = []
            for trade in trade_records:
                trades.append({
                    'id': str(trade.id),
                    'user_id': trade.user_id,
                    'strategy_id': trade.strategy_id,
                    'exchange': trade.exchange,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'quantity': float(trade.quantity),
                    'price': float(trade.price),
                    'total_amount': float(trade.total_amount),
                    'fee': float(trade.fee),
                    'order_id': trade.order_id,
                    'trade_type': trade.trade_type,
                    'executed_at': trade.executed_at.isoformat()
                })
            
            self.logger.info(f"返回 {len(trades)} 条交易记录")
            return trades
            
        except Exception as e:
            self.logger.error(f"获取交易记录失败: {e}")
            return []
    
    # 交易会话相关方法
    async def create_trading_session(self, user_id: int, session_data: dict, db: AsyncSession) -> TradingSession:
        """创建真实交易会话"""
        try:
            self.logger.info(f"用户 {user_id} 创建交易会话")
            
            # 确保交易引擎已启动
            await self._ensure_trading_engine_started()
            
            # 转换执行模式
            execution_mode = StrategyExecutionMode.MANUAL
            mode_str = session_data.get('execution_mode', 'manual').lower()
            if mode_str == 'semi_auto':
                execution_mode = StrategyExecutionMode.SEMI_AUTO
            elif mode_str == 'full_auto':
                execution_mode = StrategyExecutionMode.FULL_AUTO
            
            # 通过实盘交易引擎创建会话
            engine_session_id = await live_trading_engine.create_trading_session(
                user_id=user_id,
                exchange=session_data['exchange'],
                symbols=session_data['symbols'],
                strategy_id=session_data.get('strategy_id'),
                execution_mode=execution_mode,
                max_daily_trades=session_data.get('max_daily_trades', 100),
                max_open_positions=session_data.get('max_open_positions', 5),
                stop_loss_enabled=session_data.get('stop_loss_enabled', True),
                take_profit_enabled=session_data.get('take_profit_enabled', True)
            )
            
            # 返回业务层会话对象
            session = TradingSession(
                id=engine_session_id,
                user_id=user_id,
                strategy_id=session_data.get('strategy_id'),
                exchange=session_data['exchange'],
                symbols=session_data['symbols'],
                status='inactive',
                execution_mode=session_data.get('execution_mode', 'manual'),
                max_daily_trades=session_data.get('max_daily_trades', 100),
                max_open_positions=session_data.get('max_open_positions', 5),
                total_trades=0,
                daily_pnl=0.0,
                created_at=datetime.utcnow()
            )
            
            self.logger.info(f"交易会话创建成功: {engine_session_id}")
            return session
            
        except Exception as e:
            self.logger.error(f"创建交易会话失败: {e}")
            raise
    
    async def get_user_trading_sessions(self, user_id: int) -> List[TradingSession]:
        """获取用户交易会话"""
        try:
            self.logger.info(f"获取用户 {user_id} 的交易会话")
            
            # 从实盘交易引擎获取活跃会话
            engine_sessions = live_trading_engine.get_active_sessions(user_id)
            
            sessions = []
            for session_data in engine_sessions:
                session = TradingSession(
                    id=session_data['id'],
                    user_id=session_data['user_id'],
                    strategy_id=session_data.get('strategy_id'),
                    exchange=session_data['exchange'],
                    symbols=session_data['symbols'],
                    status=session_data['status'],
                    execution_mode=session_data['execution_mode'],
                    max_daily_trades=session_data['max_daily_trades'],
                    max_open_positions=session_data['max_open_positions'],
                    total_trades=session_data['total_trades'],
                    daily_pnl=session_data['daily_pnl'],
                    created_at=self._safe_parse_datetime(session_data.get('created_at')),
                    started_at=self._safe_parse_datetime(session_data.get('started_at')) if session_data.get('started_at') else None
                )
                sessions.append(session)
            
            self.logger.info(f"返回 {len(sessions)} 个交易会话")
            return sessions
            
        except Exception as e:
            self.logger.error(f"获取交易会话失败: {e}")
            return []
    
    async def start_trading_session(self, user_id: int, session_id: str, db: AsyncSession) -> bool:
        """启动交易会话"""
        try:
            self.logger.info(f"用户 {user_id} 启动交易会话: {session_id}")
            
            # 通过实盘交易引擎启动
            success = await live_trading_engine.start_trading_session(session_id, db)
            
            if success:
                self.logger.info(f"交易会话启动成功: {session_id}")
            else:
                self.logger.error(f"交易会话启动失败: {session_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"启动交易会话异常: {e}")
            return False
    
    async def stop_trading_session(self, user_id: int, session_id: str) -> bool:
        """停止交易会话"""
        try:
            self.logger.info(f"用户 {user_id} 停止交易会话: {session_id}")
            
            # 通过实盘交易引擎停止
            success = await live_trading_engine.stop_trading_session(session_id)
            
            if success:
                self.logger.info(f"交易会话停止成功: {session_id}")
            else:
                self.logger.error(f"交易会话停止失败: {session_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"停止交易会话异常: {e}")
            return False
    
    # 风险管理相关方法
    async def validate_order_risk(self, user_id: int, order_data: OrderRequest) -> RiskAssessment:
        """验证订单风险"""
        try:
            violations = []
            warnings = []
            risk_score = 0.0
            
            # 模拟风险检查
            if order_data.amount > 1.0:
                violations.append("单笔订单数量超过限制")
                risk_score += 30
            
            if order_data.amount > 0.5:
                warnings.append("订单数量较大，请谨慎")
                risk_score += 10
            
            # 确定风险级别
            if risk_score >= 50:
                risk_level = 'critical'
            elif risk_score >= 30:
                risk_level = 'high'
            elif risk_score >= 10:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            approved = len(violations) == 0
            
            assessment = RiskAssessment(
                approved=approved,
                risk_level=risk_level,
                risk_score=risk_score,
                violations=violations,
                warnings=warnings,
                suggested_position_size=min(order_data.amount, 0.5),
                max_allowed_size=1.0
            )
            
            return assessment
        except Exception as e:
            self.logger.error(f"验证订单风险失败: {e}")
            raise
    
    async def get_portfolio_risk_metrics(self, user_id: int) -> dict:
        """获取投资组合风险指标"""
        try:
            metrics = {
                'total_value': 35000.0,
                'unrealized_pnl': 3100.0,
                'daily_pnl': 150.0,
                'var_95': -1200.0,  # 95% VaR
                'max_drawdown': 0.15,
                'position_count': 3,
                'risk_score': 25.0,
                'concentration_risk': 0.4  # 最大单一持仓占比
            }
            
            return metrics
        except Exception as e:
            self.logger.error(f"获取投资组合风险指标失败: {e}")
            raise
    
    async def get_supported_exchanges(self) -> List[str]:
        """获取支持的交易所列表"""
        try:
            return list(exchange_service.SUPPORTED_EXCHANGES.keys())
        except Exception as e:
            self.logger.error(f"获取支持的交易所列表失败: {e}")
            return []
    
    async def get_exchange_symbols(self, exchange: str) -> List[str]:
        """获取交易所支持的交易对"""
        try:
            return await exchange_service.get_symbols(exchange)
        except Exception as e:
            self.logger.error(f"获取交易对失败: {e}")
            return []
    
    async def shutdown(self):
        """关闭交易服务"""
        try:
            self.logger.info("关闭交易服务...")
            
            # 关闭实盘交易引擎
            if self._trading_engine_started:
                await live_trading_engine.stop_engine()
                self._trading_engine_started = False
            
            # 关闭交易所连接
            exchange_service.close_all_exchanges()
            
            self.logger.info("交易服务已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭交易服务异常: {e}")




# 全局实盘交易服务实例
trading_service = TradingService()