"""
增强版交易所服务 - 完整实盘交易功能
包含市价单、限价单、持仓管理、批量操作等高级功能
"""

import ccxt
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import pandas as pd

from app.config import settings
from app.models.api_key import ApiKey
from app.models.trade import Trade
from app.core.risk_manager import risk_manager
from app.core.error_handler import error_handler, RetryConfig
from loguru import logger


class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: str  # long/short
    quantity: float
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float
    liquidation_price: Optional[float]
    timestamp: datetime


@dataclass
class OrderRequest:
    """订单请求参数"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"  # GTC, IOC, FOK
    reduce_only: bool = False
    post_only: bool = False


class EnhancedExchangeService:
    """增强版交易所服务类"""
    
    # 支持的交易所
    SUPPORTED_EXCHANGES = {
        'binance': ccxt.binance,
        'okx': ccxt.okx,
        'bybit': ccxt.bybit,
        'huobi': ccxt.huobi,
        'bitget': ccxt.bitget,
        'coinbase': ccxt.coinbase,
        'kucoin': ccxt.kucoin,
        'mexc': ccxt.mexc,
    }
    
    def __init__(self):
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._positions: Dict[str, List[Position]] = {}  # {user_id: [positions]}
        self._order_monitors: Dict[str, asyncio.Task] = {}  # 订单监控任务
        self._retry_config = RetryConfig(max_attempts=3, backoff_factor=2.0)
        
    async def initialize(self):
        """初始化服务"""
        logger.info("初始化增强版交易所服务...")
        # 启动定期任务
        asyncio.create_task(self._periodic_position_sync())
        asyncio.create_task(self._periodic_order_check())
        
    # ==================== 核心下单功能 ====================
    
    async def place_market_order(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        side: str,
        quantity: float,
        db: AsyncSession,
        strategy_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行市价单
        
        Args:
            user_id: 用户ID
            exchange_name: 交易所名称
            symbol: 交易对 (e.g., 'BTC/USDT')
            side: 买卖方向 ('buy' or 'sell')
            quantity: 数量
            db: 数据库会话
            strategy_id: 策略ID（可选）
            
        Returns:
            订单执行结果
        """
        try:
            logger.info(f"执行市价单: 用户{user_id}, {exchange_name}, {symbol}, {side}, 数量{quantity}")
            
            # 1. 参数验证
            if quantity <= 0:
                raise ValueError(f"无效的数量: {quantity}")
            if side not in ['buy', 'sell']:
                raise ValueError(f"无效的方向: {side}")
            
            # 2. 获取交易所连接
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return self._create_error_response("无法连接到交易所", "EXCHANGE_CONNECTION_ERROR")
            
            # 3. 获取市场信息（最小交易量、精度等）
            market_info = await self._get_market_info(exchange, symbol)
            if not market_info:
                return self._create_error_response(f"无法获取{symbol}市场信息", "MARKET_INFO_ERROR")
            
            # 4. 调整数量精度
            adjusted_quantity = self._adjust_quantity_precision(quantity, market_info)
            
            # 5. 检查最小交易量
            if adjusted_quantity < market_info.get('limits', {}).get('amount', {}).get('min', 0):
                min_amount = market_info.get('limits', {}).get('amount', {}).get('min', 0)
                return self._create_error_response(
                    f"数量低于最小交易量: {min_amount}",
                    "AMOUNT_TOO_SMALL"
                )
            
            # 6. 风险检查
            risk_check = await self._perform_risk_check(
                user_id, exchange_name, symbol, side, 'market', 
                adjusted_quantity, None, db
            )
            if not risk_check['approved']:
                return self._create_error_response(
                    f"风险检查未通过: {risk_check.get('reason')}",
                    "RISK_CHECK_FAILED",
                    risk_assessment=risk_check
                )
            
            # 7. 执行市价单（带重试机制）
            order = await self._execute_with_retry(
                exchange.create_market_order,
                symbol, side, adjusted_quantity
            )
            
            # 8. 格式化订单响应
            formatted_order = self._format_order_response(order, exchange_name)
            
            # 9. 保存订单到数据库
            await self._save_order_to_db(
                formatted_order, user_id, strategy_id, db
            )
            
            # 10. 启动订单监控
            await self._start_order_monitoring(
                user_id, exchange_name, formatted_order['id'], symbol
            )
            
            # 11. 更新持仓信息
            await self._update_position_after_order(
                user_id, exchange_name, symbol, side, 
                adjusted_quantity, formatted_order.get('average_price'), db
            )
            
            logger.info(f"市价单执行成功: 订单ID={formatted_order['id']}")
            return formatted_order
            
        except Exception as e:
            logger.error(f"市价单执行失败: {str(e)}")
            return self._create_error_response(str(e), "MARKET_ORDER_ERROR")
    
    async def place_limit_order(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        db: AsyncSession,
        strategy_id: Optional[int] = None,
        time_in_force: str = "GTC",
        post_only: bool = False
    ) -> Dict[str, Any]:
        """
        执行限价单
        
        Args:
            user_id: 用户ID
            exchange_name: 交易所名称
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            price: 限价
            db: 数据库会话
            strategy_id: 策略ID（可选）
            time_in_force: 订单有效期 (GTC/IOC/FOK)
            post_only: 是否只做Maker
            
        Returns:
            订单执行结果
        """
        try:
            logger.info(f"执行限价单: 用户{user_id}, {symbol}, {side}, 数量{quantity}@{price}")
            
            # 1. 参数验证
            if quantity <= 0 or price <= 0:
                raise ValueError(f"无效的参数: 数量={quantity}, 价格={price}")
            
            # 2. 获取交易所连接
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return self._create_error_response("无法连接到交易所", "EXCHANGE_CONNECTION_ERROR")
            
            # 3. 获取市场信息
            market_info = await self._get_market_info(exchange, symbol)
            
            # 4. 调整价格和数量精度
            adjusted_quantity = self._adjust_quantity_precision(quantity, market_info)
            adjusted_price = self._adjust_price_precision(price, market_info)
            
            # 5. 风险检查
            risk_check = await self._perform_risk_check(
                user_id, exchange_name, symbol, side, 'limit',
                adjusted_quantity, adjusted_price, db
            )
            if not risk_check['approved']:
                return self._create_error_response(
                    f"风险检查未通过: {risk_check.get('reason')}",
                    "RISK_CHECK_FAILED",
                    risk_assessment=risk_check
                )
            
            # 6. 构建订单参数
            order_params = {
                'symbol': symbol,
                'type': 'limit',
                'side': side,
                'amount': adjusted_quantity,
                'price': adjusted_price,
                'params': {}
            }
            
            # 添加高级参数
            if time_in_force != "GTC":
                order_params['params']['timeInForce'] = time_in_force
            if post_only:
                order_params['params']['postOnly'] = True
            
            # 7. 执行限价单
            order = await self._execute_with_retry(
                lambda: exchange.create_order(**order_params)
            )
            
            # 8. 格式化订单响应
            formatted_order = self._format_order_response(order, exchange_name)
            formatted_order['time_in_force'] = time_in_force
            formatted_order['post_only'] = post_only
            
            # 9. 保存订单到数据库
            await self._save_order_to_db(
                formatted_order, user_id, strategy_id, db
            )
            
            # 10. 启动订单监控
            await self._start_order_monitoring(
                user_id, exchange_name, formatted_order['id'], symbol
            )
            
            logger.info(f"限价单执行成功: 订单ID={formatted_order['id']}")
            return formatted_order
            
        except Exception as e:
            logger.error(f"限价单执行失败: {str(e)}")
            return self._create_error_response(str(e), "LIMIT_ORDER_ERROR")
    
    async def place_stop_order(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        db: AsyncSession,
        limit_price: Optional[float] = None,
        strategy_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行止损单
        
        Args:
            user_id: 用户ID
            exchange_name: 交易所名称
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            stop_price: 触发价格
            limit_price: 限价（可选，用于止损限价单）
            db: 数据库会话
            strategy_id: 策略ID（可选）
            
        Returns:
            订单执行结果
        """
        try:
            logger.info(f"执行止损单: {symbol}, {side}, 触发价={stop_price}")
            
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return self._create_error_response("无法连接到交易所", "EXCHANGE_CONNECTION_ERROR")
            
            # 检查交易所是否支持止损单
            if not exchange.has['createStopOrder']:
                return self._create_error_response(
                    f"{exchange_name}不支持止损单",
                    "FEATURE_NOT_SUPPORTED"
                )
            
            market_info = await self._get_market_info(exchange, symbol)
            adjusted_quantity = self._adjust_quantity_precision(quantity, market_info)
            adjusted_stop_price = self._adjust_price_precision(stop_price, market_info)
            
            # 执行止损单
            if limit_price:
                # 止损限价单
                adjusted_limit_price = self._adjust_price_precision(limit_price, market_info)
                order = await self._execute_with_retry(
                    exchange.create_stop_limit_order,
                    symbol, side, adjusted_quantity,
                    adjusted_stop_price, adjusted_limit_price
                )
            else:
                # 止损市价单
                order = await self._execute_with_retry(
                    exchange.create_stop_order,
                    symbol, side, adjusted_quantity, adjusted_stop_price
                )
            
            formatted_order = self._format_order_response(order, exchange_name)
            formatted_order['stop_price'] = adjusted_stop_price
            if limit_price:
                formatted_order['limit_price'] = adjusted_limit_price
            
            await self._save_order_to_db(formatted_order, user_id, strategy_id, db)
            
            logger.info(f"止损单执行成功: 订单ID={formatted_order['id']}")
            return formatted_order
            
        except Exception as e:
            logger.error(f"止损单执行失败: {str(e)}")
            return self._create_error_response(str(e), "STOP_ORDER_ERROR")
    
    # ==================== 订单管理功能 ====================
    
    async def cancel_order(
        self,
        user_id: int,
        exchange_name: str,
        order_id: str,
        symbol: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """取消订单"""
        try:
            logger.info(f"取消订单: {order_id}, {symbol}")
            
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return self._create_error_response("无法连接到交易所", "EXCHANGE_CONNECTION_ERROR")
            
            # 执行取消操作
            result = await self._execute_with_retry(
                exchange.cancel_order,
                order_id, symbol
            )
            
            # 更新数据库中的订单状态
            await self._update_order_status_in_db(order_id, OrderStatus.CANCELED, db)
            
            logger.info(f"订单取消成功: {order_id}")
            return {
                'success': True,
                'order_id': order_id,
                'status': 'canceled',
                'message': '订单已成功取消'
            }
            
        except Exception as e:
            logger.error(f"取消订单失败: {str(e)}")
            return self._create_error_response(str(e), "CANCEL_ORDER_ERROR")
    
    async def cancel_all_orders(
        self,
        user_id: int,
        exchange_name: str,
        db: AsyncSession,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """取消所有订单"""
        try:
            logger.info(f"取消所有订单: 用户{user_id}, {exchange_name}, 交易对={symbol}")
            
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return self._create_error_response("无法连接到交易所", "EXCHANGE_CONNECTION_ERROR")
            
            # 获取所有开放订单
            open_orders = await self._execute_with_retry(
                exchange.fetch_open_orders,
                symbol
            )
            
            # 批量取消
            canceled_orders = []
            failed_orders = []
            
            for order in open_orders:
                try:
                    await self._execute_with_retry(
                        exchange.cancel_order,
                        order['id'], order['symbol']
                    )
                    canceled_orders.append(order['id'])
                    await self._update_order_status_in_db(order['id'], OrderStatus.CANCELED, db)
                except Exception as e:
                    logger.error(f"取消订单{order['id']}失败: {str(e)}")
                    failed_orders.append({'id': order['id'], 'error': str(e)})
            
            return {
                'success': True,
                'canceled_count': len(canceled_orders),
                'failed_count': len(failed_orders),
                'canceled_orders': canceled_orders,
                'failed_orders': failed_orders
            }
            
        except Exception as e:
            logger.error(f"批量取消订单失败: {str(e)}")
            return self._create_error_response(str(e), "CANCEL_ALL_ORDERS_ERROR")
    
    async def get_order_status(
        self,
        user_id: int,
        exchange_name: str,
        order_id: str,
        symbol: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """查询订单状态"""
        try:
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return self._create_error_response("无法连接到交易所", "EXCHANGE_CONNECTION_ERROR")
            
            order = await self._execute_with_retry(
                exchange.fetch_order,
                order_id, symbol
            )
            
            return self._format_order_response(order, exchange_name)
            
        except Exception as e:
            logger.error(f"查询订单状态失败: {str(e)}")
            return self._create_error_response(str(e), "GET_ORDER_ERROR")
    
    async def get_open_orders(
        self,
        user_id: int,
        exchange_name: str,
        db: AsyncSession,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取所有开放订单"""
        try:
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return []
            
            orders = await self._execute_with_retry(
                exchange.fetch_open_orders,
                symbol
            )
            
            return [self._format_order_response(order, exchange_name) for order in orders]
            
        except Exception as e:
            logger.error(f"获取开放订单失败: {str(e)}")
            return []
    
    async def get_order_history(
        self,
        user_id: int,
        exchange_name: str,
        db: AsyncSession,
        symbol: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取历史订单"""
        try:
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return []
            
            since_timestamp = int(since.timestamp() * 1000) if since else None
            
            orders = await self._execute_with_retry(
                exchange.fetch_closed_orders,
                symbol, since_timestamp, limit
            )
            
            return [self._format_order_response(order, exchange_name) for order in orders]
            
        except Exception as e:
            logger.error(f"获取历史订单失败: {str(e)}")
            return []
    
    # ==================== 持仓管理功能 ====================
    
    async def sync_positions(
        self,
        user_id: int,
        exchange_name: str,
        db: AsyncSession
    ) -> List[Position]:
        """
        同步持仓信息
        
        Returns:
            持仓列表
        """
        try:
            logger.info(f"同步持仓: 用户{user_id}, {exchange_name}")
            
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return []
            
            # 检查交易所是否支持持仓查询
            if not exchange.has['fetchPositions']:
                logger.warning(f"{exchange_name}不支持持仓查询，尝试从余额计算")
                return await self._calculate_positions_from_balance(
                    user_id, exchange_name, exchange
                )
            
            # 获取持仓信息
            raw_positions = await self._execute_with_retry(
                exchange.fetch_positions
            )
            
            # 转换为Position对象
            positions = []
            for pos in raw_positions:
                if pos.get('contracts', 0) > 0:  # 只处理有持仓的
                    position = Position(
                        symbol=pos.get('symbol'),
                        side=pos.get('side', 'long'),
                        quantity=float(pos.get('contracts', 0)),
                        average_price=float(pos.get('markPrice', 0)),
                        current_price=float(pos.get('markPrice', 0)),
                        unrealized_pnl=float(pos.get('unrealizedPnl', 0)),
                        realized_pnl=float(pos.get('realizedPnl', 0)),
                        margin_used=float(pos.get('initialMargin', 0)),
                        liquidation_price=float(pos.get('liquidationPrice')) if pos.get('liquidationPrice') else None,
                        timestamp=datetime.utcnow()
                    )
                    positions.append(position)
            
            # 缓存持仓信息
            cache_key = f"{user_id}_{exchange_name}"
            self._positions[cache_key] = positions
            
            # 保存到数据库
            await self._save_positions_to_db(user_id, exchange_name, positions, db)
            
            logger.info(f"持仓同步完成: 找到{len(positions)}个持仓")
            return positions
            
        except Exception as e:
            logger.error(f"同步持仓失败: {str(e)}")
            return []
    
    async def get_position(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        db: AsyncSession
    ) -> Optional[Position]:
        """获取特定交易对的持仓"""
        positions = await self.sync_positions(user_id, exchange_name, db)
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    async def close_position(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """平仓"""
        try:
            logger.info(f"平仓: 用户{user_id}, {symbol}")
            
            # 获取当前持仓
            position = await self.get_position(user_id, exchange_name, symbol, db)
            if not position:
                return self._create_error_response(f"没有找到{symbol}的持仓", "NO_POSITION")
            
            # 执行反向市价单平仓
            side = 'sell' if position.side == 'long' else 'buy'
            
            result = await self.place_market_order(
                user_id, exchange_name, symbol,
                side, position.quantity, db
            )
            
            if result.get('success'):
                # 更新持仓状态
                await self._remove_position_from_cache(user_id, exchange_name, symbol)
                logger.info(f"平仓成功: {symbol}")
            
            return result
            
        except Exception as e:
            logger.error(f"平仓失败: {str(e)}")
            return self._create_error_response(str(e), "CLOSE_POSITION_ERROR")
    
    async def get_account_info(
        self,
        user_id: int,
        exchange_name: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        获取账户综合信息
        包括余额、持仓、盈亏等
        """
        try:
            exchange = await self._get_or_create_exchange(user_id, exchange_name, db)
            if not exchange:
                return {}
            
            # 获取余额
            balance = await self._execute_with_retry(exchange.fetch_balance)
            
            # 获取持仓
            positions = await self.sync_positions(user_id, exchange_name, db)
            
            # 计算总资产和盈亏
            total_balance = sum(
                bal.get('total', 0) * self._get_usd_price(currency)
                for currency, bal in balance.get('info', {}).items()
                if bal.get('total', 0) > 0
            )
            
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_realized_pnl = sum(pos.realized_pnl for pos in positions)
            
            return {
                'exchange': exchange_name,
                'total_balance_usd': total_balance,
                'available_balance': balance.get('free', {}),
                'used_balance': balance.get('used', {}),
                'positions_count': len(positions),
                'total_unrealized_pnl': total_unrealized_pnl,
                'total_realized_pnl': total_realized_pnl,
                'positions': [self._position_to_dict(pos) for pos in positions],
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取账户信息失败: {str(e)}")
            return {}
    
    # ==================== 辅助功能 ====================
    
    async def _get_or_create_exchange(
        self,
        user_id: int,
        exchange_name: str,
        db: AsyncSession
    ) -> Optional[ccxt.Exchange]:
        """获取或创建交易所实例"""
        from app.services.exchange_service import exchange_service
        return await exchange_service.get_exchange(user_id, exchange_name, db)
    
    async def _get_market_info(
        self,
        exchange: ccxt.Exchange,
        symbol: str
    ) -> Dict[str, Any]:
        """获取市场信息"""
        try:
            loop = asyncio.get_event_loop()
            markets = await loop.run_in_executor(None, exchange.load_markets)
            return markets.get(symbol, {})
        except Exception as e:
            logger.error(f"获取市场信息失败: {str(e)}")
            return {}
    
    def _adjust_quantity_precision(
        self,
        quantity: float,
        market_info: Dict[str, Any]
    ) -> float:
        """调整数量精度"""
        precision = market_info.get('precision', {}).get('amount', 8)
        return round(quantity, precision)
    
    def _adjust_price_precision(
        self,
        price: float,
        market_info: Dict[str, Any]
    ) -> float:
        """调整价格精度"""
        precision = market_info.get('precision', {}).get('price', 8)
        return round(price, precision)
    
    async def _perform_risk_check(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """执行风险检查"""
        try:
            # 获取账户余额
            from app.services.exchange_service import exchange_service
            balance_info = await exchange_service.get_account_balance(
                user_id, exchange_name, db
            )
            
            account_balance = {}
            if balance_info:
                account_balance = {
                    currency: bal.get('free', 0)
                    for currency, bal in balance_info.get('balances', {}).items()
                }
            
            # 调用风险管理器
            assessment = await risk_manager.validate_order(
                user_id=user_id,
                exchange=exchange_name,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                account_balance=account_balance,
                db=db
            )
            
            return {
                'approved': assessment.approved,
                'risk_level': assessment.risk_level.value,
                'risk_score': assessment.risk_score,
                'reason': ', '.join(assessment.violations) if assessment.violations else None,
                'warnings': assessment.warnings,
                'suggested_position_size': assessment.suggested_position_size
            }
            
        except Exception as e:
            logger.error(f"风险检查失败: {str(e)}")
            # 风险检查失败时，保守处理
            return {
                'approved': False,
                'reason': f'风险检查系统错误: {str(e)}'
            }
    
    async def _execute_with_retry(self, func, *args, **kwargs):
        """带重试机制的执行"""
        return await error_handler.retry(self._retry_config)(func)(*args, **kwargs)
    
    def _format_order_response(
        self,
        order: Dict[str, Any],
        exchange_name: str
    ) -> Dict[str, Any]:
        """格式化订单响应"""
        return {
            'success': True,
            'id': order.get('id'),
            'client_order_id': order.get('clientOrderId'),
            'symbol': order.get('symbol'),
            'type': order.get('type'),
            'side': order.get('side'),
            'status': order.get('status'),
            'price': float(order.get('price', 0)) if order.get('price') else None,
            'average_price': float(order.get('average', 0)) if order.get('average') else None,
            'quantity': float(order.get('amount', 0)),
            'filled': float(order.get('filled', 0)),
            'remaining': float(order.get('remaining', 0)),
            'cost': float(order.get('cost', 0)),
            'fee': order.get('fee'),
            'trades': order.get('trades', []),
            'timestamp': order.get('timestamp'),
            'datetime': order.get('datetime'),
            'exchange': exchange_name
        }
    
    def _create_error_response(
        self,
        message: str,
        error_code: str,
        **kwargs
    ) -> Dict[str, Any]:
        """创建错误响应"""
        response = {
            'success': False,
            'error': message,
            'error_code': error_code
        }
        response.update(kwargs)
        return response
    
    async def _save_order_to_db(
        self,
        order_info: Dict[str, Any],
        user_id: int,
        strategy_id: Optional[int],
        db: AsyncSession
    ):
        """保存订单到数据库"""
        try:
            trade = Trade(
                user_id=user_id,
                strategy_id=strategy_id,
                exchange=order_info.get('exchange'),
                symbol=order_info.get('symbol'),
                side=order_info.get('side', '').upper(),
                quantity=Decimal(str(order_info.get('quantity', 0))),
                price=Decimal(str(order_info.get('price', 0))) if order_info.get('price') else None,
                total_amount=Decimal(str(order_info.get('cost', 0))),
                fee=Decimal(str(order_info.get('fee', {}).get('cost', 0))) if order_info.get('fee') else Decimal('0'),
                order_id=order_info.get('id'),
                trade_type='LIVE',
                executed_at=datetime.fromtimestamp(order_info.get('timestamp', 0) / 1000) if order_info.get('timestamp') else datetime.utcnow()
            )
            
            db.add(trade)
            await db.commit()
            logger.info(f"订单已保存到数据库: {trade.order_id}")
            
        except Exception as e:
            logger.error(f"保存订单到数据库失败: {str(e)}")
            await db.rollback()
    
    async def _update_order_status_in_db(
        self,
        order_id: str,
        status: OrderStatus,
        db: AsyncSession
    ):
        """更新数据库中的订单状态"""
        try:
            # 这里需要根据实际的数据库模型来更新
            # 示例代码，实际需要根据Trade模型调整
            stmt = update(Trade).where(
                Trade.order_id == order_id
            ).values(
                status=status.value,
                updated_at=datetime.utcnow()
            )
            await db.execute(stmt)
            await db.commit()
        except Exception as e:
            logger.error(f"更新订单状态失败: {str(e)}")
            await db.rollback()
    
    async def _start_order_monitoring(
        self,
        user_id: int,
        exchange_name: str,
        order_id: str,
        symbol: str
    ):
        """启动订单监控"""
        monitor_key = f"{user_id}_{order_id}"
        if monitor_key not in self._order_monitors:
            task = asyncio.create_task(
                self._monitor_order(user_id, exchange_name, order_id, symbol)
            )
            self._order_monitors[monitor_key] = task
    
    async def _monitor_order(
        self,
        user_id: int,
        exchange_name: str,
        order_id: str,
        symbol: str
    ):
        """监控订单状态"""
        try:
            while True:
                await asyncio.sleep(5)  # 每5秒检查一次
                
                # 获取订单状态
                # 这里需要实现具体的监控逻辑
                pass
                
        except asyncio.CancelledError:
            logger.info(f"订单监控已取消: {order_id}")
        except Exception as e:
            logger.error(f"订单监控错误: {str(e)}")
    
    async def _update_position_after_order(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float],
        db: AsyncSession
    ):
        """订单执行后更新持仓"""
        # 触发持仓同步
        await self.sync_positions(user_id, exchange_name, db)
    
    async def _calculate_positions_from_balance(
        self,
        user_id: int,
        exchange_name: str,
        exchange: ccxt.Exchange
    ) -> List[Position]:
        """从余额计算持仓（现货交易所）"""
        try:
            balance = await self._execute_with_retry(exchange.fetch_balance)
            positions = []
            
            for currency, bal in balance.get('total', {}).items():
                if bal > 0 and currency != 'USDT':  # 排除稳定币
                    # 获取当前价格
                    symbol = f"{currency}/USDT"
                    ticker = await self._execute_with_retry(
                        exchange.fetch_ticker, symbol
                    )
                    
                    position = Position(
                        symbol=symbol,
                        side='long',
                        quantity=float(bal),
                        average_price=0,  # 现货没有平均价格
                        current_price=float(ticker.get('last', 0)),
                        unrealized_pnl=0,  # 需要计算
                        realized_pnl=0,
                        margin_used=0,  # 现货不使用保证金
                        liquidation_price=None,
                        timestamp=datetime.utcnow()
                    )
                    positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"从余额计算持仓失败: {str(e)}")
            return []
    
    async def _save_positions_to_db(
        self,
        user_id: int,
        exchange_name: str,
        positions: List[Position],
        db: AsyncSession
    ):
        """保存持仓到数据库"""
        # 这里需要根据实际的数据库模型来实现
        pass
    
    async def _remove_position_from_cache(
        self,
        user_id: int,
        exchange_name: str,
        symbol: str
    ):
        """从缓存中移除持仓"""
        cache_key = f"{user_id}_{exchange_name}"
        if cache_key in self._positions:
            self._positions[cache_key] = [
                pos for pos in self._positions[cache_key]
                if pos.symbol != symbol
            ]
    
    def _position_to_dict(self, position: Position) -> Dict[str, Any]:
        """将Position对象转换为字典"""
        return {
            'symbol': position.symbol,
            'side': position.side,
            'quantity': position.quantity,
            'average_price': position.average_price,
            'current_price': position.current_price,
            'unrealized_pnl': position.unrealized_pnl,
            'realized_pnl': position.realized_pnl,
            'margin_used': position.margin_used,
            'liquidation_price': position.liquidation_price,
            'timestamp': position.timestamp.isoformat()
        }
    
    def _get_usd_price(self, currency: str) -> float:
        """获取币种的USD价格（简化版）"""
        # 实际应该从市场数据获取
        prices = {
            'USDT': 1.0,
            'BTC': 45000,
            'ETH': 2500,
            'BNB': 300,
            # ... 其他币种
        }
        return prices.get(currency, 0)
    
    async def _periodic_position_sync(self):
        """定期同步持仓"""
        while True:
            await asyncio.sleep(60)  # 每分钟同步一次
            # 实现定期同步逻辑
            pass
    
    async def _periodic_order_check(self):
        """定期检查订单状态"""
        while True:
            await asyncio.sleep(30)  # 每30秒检查一次
            # 实现订单状态检查逻辑
            pass


# 全局增强版交易所服务实例
enhanced_exchange_service = EnhancedExchangeService()