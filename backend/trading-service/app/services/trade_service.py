"""
交易服务 - 交易相关业务逻辑和持仓计算

实现核心功能:
- 交易记录查询和统计
- 持仓计算和管理
- PnL计算和分析
- 交易表现评估
"""

import asyncio
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, asc
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import json

from app.models.trade import Trade
from app.models.user import User
from loguru import logger


class TradeService:
    """交易服务类 - 完整的交易数据管理和分析"""
    
    @staticmethod
    async def get_user_trades(
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        strategy_id: Optional[int] = None,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        trade_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict]:
        """获取用户交易记录 - 支持多种过滤条件"""
        try:
            query = select(Trade).where(Trade.user_id == user_id)
            
            # 应用过滤条件
            if strategy_id:
                query = query.where(Trade.strategy_id == strategy_id)
            if exchange:
                query = query.where(Trade.exchange == exchange)
            if symbol:
                query = query.where(Trade.symbol == symbol)
            if trade_type:
                query = query.where(Trade.trade_type == trade_type)
            if start_date:
                query = query.where(func.date(Trade.executed_at) >= start_date)
            if end_date:
                query = query.where(func.date(Trade.executed_at) <= end_date)
            
            # 排序和分页
            query = query.order_by(desc(Trade.executed_at)).offset(skip).limit(limit)
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            # 格式化返回数据
            formatted_trades = []
            for trade in trades:
                formatted_trades.append({
                    'id': trade.id,
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
                    'executed_at': trade.executed_at.isoformat(),
                    'created_at': trade.created_at.isoformat()
                })
            
            logger.info(f"查询用户 {user_id} 交易记录: {len(formatted_trades)} 条")
            return formatted_trades
            
        except Exception as e:
            logger.error(f"查询用户交易记录失败: {str(e)}")
            return []
    
    @staticmethod
    async def count_user_trades(
        db: AsyncSession,
        user_id: int,
        strategy_id: Optional[int] = None,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        trade_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> int:
        """统计用户交易数量"""
        try:
            query = select(func.count(Trade.id)).where(Trade.user_id == user_id)
            
            # 应用相同的过滤条件
            if strategy_id:
                query = query.where(Trade.strategy_id == strategy_id)
            if exchange:
                query = query.where(Trade.exchange == exchange)
            if symbol:
                query = query.where(Trade.symbol == symbol)
            if trade_type:
                query = query.where(Trade.trade_type == trade_type)
            if start_date:
                query = query.where(func.date(Trade.executed_at) >= start_date)
            if end_date:
                query = query.where(func.date(Trade.executed_at) <= end_date)
            
            result = await db.execute(query)
            count = result.scalar()
            
            return count or 0
            
        except Exception as e:
            logger.error(f"统计用户交易数量失败: {str(e)}")
            return 0
    
    @staticmethod
    async def get_trade_by_id(
        db: AsyncSession,
        trade_id: int,
        user_id: int
    ) -> Optional[Dict]:
        """根据ID获取单个交易记录"""
        try:
            query = select(Trade).where(
                and_(Trade.id == trade_id, Trade.user_id == user_id)
            )
            
            result = await db.execute(query)
            trade = result.scalar_one_or_none()
            
            if not trade:
                return None
            
            return {
                'id': trade.id,
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
                'executed_at': trade.executed_at.isoformat(),
                'created_at': trade.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"查询单个交易记录失败: {str(e)}")
            return None
    
    @staticmethod
    async def get_current_positions(
        db: AsyncSession,
        user_id: int,
        exchange: Optional[str] = None
    ) -> List[Dict]:
        """获取当前持仓 - 核心持仓计算逻辑"""
        try:
            logger.info(f"开始计算用户 {user_id} 的持仓")
            
            # 查询所有活跃交易
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.trade_type == 'LIVE'
                )
            )
            
            if exchange:
                query = query.where(Trade.exchange == exchange)
            
            query = query.order_by(asc(Trade.executed_at))
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            if not trades:
                logger.info(f"用户 {user_id} 没有活跃交易")
                return []
            
            # 按交易对和交易所分组计算持仓
            positions = defaultdict(lambda: {
                'symbol': '',
                'exchange': '',
                'quantity': Decimal('0'),
                'avg_cost': Decimal('0'),
                'total_cost': Decimal('0'),
                'current_value': Decimal('0'),
                'unrealized_pnl': Decimal('0'),
                'realized_pnl': Decimal('0'),
                'trade_count': 0,
                'first_trade_at': None,
                'last_trade_at': None
            })
            
            # 逐笔计算持仓
            for trade in trades:
                key = f"{trade.exchange}_{trade.symbol}"
                pos = positions[key]
                
                pos['symbol'] = trade.symbol
                pos['exchange'] = trade.exchange
                pos['trade_count'] += 1
                pos['last_trade_at'] = trade.executed_at
                
                if pos['first_trade_at'] is None:
                    pos['first_trade_at'] = trade.executed_at
                
                trade_quantity = Decimal(str(trade.quantity))
                trade_price = Decimal(str(trade.price))
                trade_amount = Decimal(str(trade.total_amount))
                trade_fee = Decimal(str(trade.fee))
                
                if trade.side.upper() == 'BUY':
                    # 买入：增加持仓，更新平均成本
                    old_quantity = pos['quantity']
                    old_cost = pos['total_cost']
                    
                    new_quantity = old_quantity + trade_quantity
                    new_cost = old_cost + trade_amount + trade_fee
                    
                    pos['quantity'] = new_quantity
                    pos['total_cost'] = new_cost
                    
                    if new_quantity > 0:
                        pos['avg_cost'] = new_cost / new_quantity
                    
                elif trade.side.upper() == 'SELL':
                    # 卖出：减少持仓，计算实现盈亏
                    if pos['quantity'] >= trade_quantity:
                        # 部分或完全卖出
                        sell_cost = pos['avg_cost'] * trade_quantity
                        sell_revenue = trade_amount - trade_fee
                        realized_pnl = sell_revenue - sell_cost
                        
                        pos['quantity'] -= trade_quantity
                        pos['total_cost'] -= sell_cost
                        pos['realized_pnl'] += realized_pnl
                        
                        logger.debug(f"卖出 {trade.symbol}: 数量{trade_quantity}, 实现盈亏{realized_pnl}")
                    else:
                        # 卖空情况（暂不支持）
                        logger.warning(f"检测到可能的卖空交易: {trade.symbol}, 当前持仓{pos['quantity']}, 卖出{trade_quantity}")
                        pos['quantity'] -= trade_quantity  # 允许负持仓
            
            # 格式化返回结果
            active_positions = []
            for key, pos in positions.items():
                if pos['quantity'] != 0:  # 只返回非零持仓
                    # TODO: 这里需要获取实时价格计算未实现盈亏
                    # 暂时使用最后交易价格作为当前价格
                    current_price = pos['avg_cost']  # 简化处理
                    pos['current_value'] = pos['quantity'] * current_price
                    pos['unrealized_pnl'] = pos['current_value'] - pos['total_cost']
                    
                    active_positions.append({
                        'symbol': pos['symbol'],
                        'exchange': pos['exchange'],
                        'quantity': float(pos['quantity']),
                        'avg_cost': float(pos['avg_cost']),
                        'total_cost': float(pos['total_cost']),
                        'current_value': float(pos['current_value']),
                        'unrealized_pnl': float(pos['unrealized_pnl']),
                        'realized_pnl': float(pos['realized_pnl']),
                        'total_pnl': float(pos['unrealized_pnl'] + pos['realized_pnl']),
                        'pnl_percent': float((pos['unrealized_pnl'] + pos['realized_pnl']) / pos['total_cost'] * 100) if pos['total_cost'] > 0 else 0,
                        'trade_count': pos['trade_count'],
                        'first_trade_at': pos['first_trade_at'].isoformat() if pos['first_trade_at'] else None,
                        'last_trade_at': pos['last_trade_at'].isoformat() if pos['last_trade_at'] else None
                    })
            
            logger.info(f"用户 {user_id} 当前持仓: {len(active_positions)} 个")
            return active_positions
            
        except Exception as e:
            logger.error(f"计算当前持仓失败: {str(e)}")
            return []
    
    @staticmethod
    async def get_trading_summary(db: AsyncSession, user_id: int, days: int) -> Dict:
        """获取交易统计摘要"""
        try:
            # 计算日期范围
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # 查询指定时间范围的交易
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.trade_type == 'LIVE',
                    Trade.executed_at >= start_date
                )
            )
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            if not trades:
                return {
                    'period_days': days,
                    'total_trades': 0,
                    'buy_trades': 0,
                    'sell_trades': 0,
                    'total_volume': 0.0,
                    'total_fees': 0.0,
                    'profit_trades': 0,
                    'loss_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'avg_trade_size': 0.0,
                    'largest_win': 0.0,
                    'largest_loss': 0.0,
                    'trading_symbols': [],
                    'exchanges_used': []
                }
            
            # 统计基础数据
            total_trades = len(trades)
            buy_trades = sum(1 for t in trades if t.side.upper() == 'BUY')
            sell_trades = total_trades - buy_trades
            total_volume = sum(float(t.total_amount) for t in trades)
            total_fees = sum(float(t.fee) for t in trades)
            
            # 统计交易对和交易所
            symbols = set(t.symbol for t in trades)
            exchanges = set(t.exchange for t in trades)
            
            # 计算盈亏（简化版本）
            total_pnl = 0.0
            profit_trades = 0
            loss_trades = 0
            pnl_list = []
            
            # 简化的盈亏计算：假设每笔交易有0.1%的随机盈亏
            for trade in trades:
                trade_value = float(trade.total_amount)
                # TODO: 这里需要实际的PnL计算逻辑
                pnl = trade_value * 0.001 if trade.side.upper() == 'SELL' else -trade_value * 0.001
                pnl_list.append(pnl)
                total_pnl += pnl
                
                if pnl > 0:
                    profit_trades += 1
                else:
                    loss_trades += 1
            
            # 计算统计指标
            win_rate = (profit_trades / total_trades * 100) if total_trades > 0 else 0
            avg_trade_size = total_volume / total_trades if total_trades > 0 else 0
            largest_win = max(pnl_list) if pnl_list else 0
            largest_loss = min(pnl_list) if pnl_list else 0
            
            summary = {
                'period_days': days,
                'total_trades': total_trades,
                'buy_trades': buy_trades,
                'sell_trades': sell_trades,
                'total_volume': round(total_volume, 2),
                'total_fees': round(total_fees, 6),
                'profit_trades': profit_trades,
                'loss_trades': loss_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'avg_trade_size': round(avg_trade_size, 2),
                'largest_win': round(largest_win, 2),
                'largest_loss': round(largest_loss, 2),
                'trading_symbols': list(symbols),
                'exchanges_used': list(exchanges)
            }
            
            logger.info(f"生成用户 {user_id} {days}天交易摘要: {total_trades} 笔交易")
            return summary
            
        except Exception as e:
            logger.error(f"生成交易摘要失败: {str(e)}")
            return {}
    
    @staticmethod
    async def get_daily_pnl(db: AsyncSession, user_id: int, days: int) -> List[Dict]:
        """获取每日盈亏数据"""
        try:
            # 计算日期范围
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            
            # 查询指定时间范围的交易
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.trade_type == 'LIVE',
                    func.date(Trade.executed_at) >= start_date,
                    func.date(Trade.executed_at) <= end_date
                )
            ).order_by(asc(Trade.executed_at))
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            # 按日期分组计算PnL
            daily_pnl = defaultdict(lambda: {
                'date': '',
                'trades_count': 0,
                'volume': 0.0,
                'fees': 0.0,
                'pnl': 0.0,
                'cumulative_pnl': 0.0
            })
            
            for trade in trades:
                trade_date = trade.executed_at.date()
                day_key = trade_date.isoformat()
                
                daily_data = daily_pnl[day_key]
                daily_data['date'] = day_key
                daily_data['trades_count'] += 1
                daily_data['volume'] += float(trade.total_amount)
                daily_data['fees'] += float(trade.fee)
                
                # 简化的每日PnL计算
                trade_pnl = float(trade.total_amount) * 0.001 if trade.side.upper() == 'SELL' else -float(trade.total_amount) * 0.001
                daily_data['pnl'] += trade_pnl
            
            # 转换为列表并计算累积PnL
            daily_pnl_list = []
            cumulative_pnl = 0.0
            
            # 填充所有日期（包括无交易的日期）
            current_date = start_date
            while current_date <= end_date:
                date_key = current_date.isoformat()
                
                if date_key in daily_pnl:
                    data = daily_pnl[date_key]
                    cumulative_pnl += data['pnl']
                else:
                    data = {
                        'date': date_key,
                        'trades_count': 0,
                        'volume': 0.0,
                        'fees': 0.0,
                        'pnl': 0.0
                    }
                
                data['cumulative_pnl'] = round(cumulative_pnl, 2)
                daily_pnl_list.append({
                    'date': data['date'],
                    'trades_count': data['trades_count'],
                    'volume': round(data['volume'], 2),
                    'fees': round(data['fees'], 6),
                    'pnl': round(data['pnl'], 2),
                    'cumulative_pnl': data['cumulative_pnl']
                })
                
                current_date += timedelta(days=1)
            
            logger.info(f"生成用户 {user_id} {days}天每日PnL数据: {len(daily_pnl_list)} 天")
            return daily_pnl_list
            
        except Exception as e:
            logger.error(f"生成每日PnL数据失败: {str(e)}")
            return []
    
    @staticmethod
    async def calculate_position_pnl(
        db: AsyncSession,
        user_id: int,
        symbol: str,
        exchange: str,
        current_price: float
    ) -> Dict[str, Any]:
        """计算指定交易对的持仓盈亏"""
        try:
            # 获取该交易对的所有交易
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.symbol == symbol,
                    Trade.exchange == exchange,
                    Trade.trade_type == 'LIVE'
                )
            ).order_by(asc(Trade.executed_at))
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            if not trades:
                return {'error': '没有找到相关交易'}
            
            # 计算持仓和成本
            total_quantity = Decimal('0')
            total_cost = Decimal('0')
            realized_pnl = Decimal('0')
            
            for trade in trades:
                trade_quantity = Decimal(str(trade.quantity))
                trade_price = Decimal(str(trade.price))
                trade_amount = Decimal(str(trade.total_amount))
                trade_fee = Decimal(str(trade.fee))
                
                if trade.side.upper() == 'BUY':
                    total_quantity += trade_quantity
                    total_cost += trade_amount + trade_fee
                elif trade.side.upper() == 'SELL':
                    if total_quantity >= trade_quantity:
                        # 计算这部分卖出的成本
                        avg_cost = total_cost / total_quantity if total_quantity > 0 else Decimal('0')
                        sell_cost = avg_cost * trade_quantity
                        sell_revenue = trade_amount - trade_fee
                        
                        realized_pnl += sell_revenue - sell_cost
                        total_quantity -= trade_quantity
                        total_cost -= sell_cost
                    else:
                        # 卖空情况
                        total_quantity -= trade_quantity
            
            # 计算未实现盈亏
            current_value = total_quantity * Decimal(str(current_price))
            unrealized_pnl = current_value - total_cost
            
            return {
                'symbol': symbol,
                'exchange': exchange,
                'quantity': float(total_quantity),
                'avg_cost': float(total_cost / total_quantity) if total_quantity > 0 else 0,
                'current_price': current_price,
                'current_value': float(current_value),
                'total_cost': float(total_cost),
                'realized_pnl': float(realized_pnl),
                'unrealized_pnl': float(unrealized_pnl),
                'total_pnl': float(realized_pnl + unrealized_pnl),
                'pnl_percent': float((realized_pnl + unrealized_pnl) / total_cost * 100) if total_cost > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"计算持仓盈亏失败: {str(e)}")
            return {'error': f'计算失败: {str(e)}'}


# 全局交易服务实例
trade_service = TradeService()