"""
交易所服务 - CCXT集成

支持多个主流交易所的统一API接口
"""

import ccxt
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_key import ApiKey
from app.models.market_data import MarketData
from app.models.trade import Trade
from app.core.risk_manager import risk_manager, OrderRiskAssessment, RiskLevel
from app.utils.data_validation import DataValidator
from loguru import logger


class ExchangeService:
    """交易所服务类"""
    
    # 支持的交易所
    SUPPORTED_EXCHANGES = {
        'binance': ccxt.binance,
        'okx': ccxt.okx,
        'bybit': ccxt.bybit,
        'huobi': ccxt.huobi,
        'bitget': ccxt.bitget,
        'coinbase': ccxt.coinbase,
    }
    
    def __init__(self):
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._connections: Dict[str, bool] = {}
    
    def _create_exchange_instance(self, exchange_name: str, api_key: str, 
                                secret: str, passphrase: Optional[str] = None,
                                sandbox: bool = False) -> ccxt.Exchange:
        """创建交易所实例"""
        try:
            if exchange_name not in self.SUPPORTED_EXCHANGES:
                raise ValueError(f"不支持的交易所: {exchange_name}")
            
            exchange_class = self.SUPPORTED_EXCHANGES[exchange_name]
            config = {
                'apiKey': api_key,
                'secret': secret,
                'timeout': 30000,
                'enableRateLimit': True,
                'sandbox': sandbox,
            }
            
            # OKX等交易所需要passphrase
            if passphrase and exchange_name in ['okx', 'bitget']:
                config['password'] = passphrase
            
            exchange = exchange_class(config)
            return exchange
            
        except Exception as e:
            logger.error(f"创建交易所实例失败: {exchange_name}, 错误: {str(e)}")
            raise
    
    def _create_public_exchange_instance(self, exchange_name: str) -> ccxt.Exchange:
        """创建公共API交易所实例（无需API密钥）"""
        try:
            if exchange_name not in self.SUPPORTED_EXCHANGES:
                raise ValueError(f"不支持的交易所: {exchange_name}")
            
            exchange_class = self.SUPPORTED_EXCHANGES[exchange_name]
            config = {
                'timeout': 30000,
                'enableRateLimit': True,
                'sandbox': settings.environment != "production",
            }
            # 注意：不设置apiKey和secret，用于公共API调用
            
            exchange = exchange_class(config)
            logger.info(f"创建公共API交易所实例: {exchange_name}")
            return exchange
            
        except Exception as e:
            logger.error(f"创建公共API交易所实例失败: {exchange_name}, 错误: {str(e)}")
            raise
    
    async def get_exchange(self, user_id: int, exchange_name: str, 
                          db: AsyncSession) -> Optional[ccxt.Exchange]:
        """获取用户的交易所实例"""
        try:
            cache_key = f"{user_id}_{exchange_name}"
            
            # 检查缓存
            if cache_key in self._exchanges:
                return self._exchanges[cache_key]
            
            # 从数据库获取API密钥
            api_key_record = await self._get_user_api_key(db, user_id, exchange_name)
            if not api_key_record:
                logger.warning(f"用户 {user_id} 没有配置 {exchange_name} 的API密钥")
                return None
            
            # 创建交易所实例
            exchange = self._create_exchange_instance(
                exchange_name=exchange_name,
                api_key=api_key_record.api_key,
                secret=api_key_record.secret_key,
                passphrase=api_key_record.passphrase,
                sandbox=settings.environment != "production"
            )
            
            # 测试连接
            if await self._test_connection(exchange):
                self._exchanges[cache_key] = exchange
                self._connections[cache_key] = True
                logger.info(f"交易所 {exchange_name} 连接成功: 用户 {user_id}")
                return exchange
            else:
                logger.error(f"交易所 {exchange_name} 连接测试失败: 用户 {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"获取交易所实例失败: {exchange_name}, 用户: {user_id}, 错误: {str(e)}")
            return None
    
    async def _get_user_api_key(self, db: AsyncSession, user_id: int, 
                               exchange: str) -> Optional[ApiKey]:
        """获取用户的API密钥"""
        from sqlalchemy import select
        
        try:
            query = select(ApiKey).where(
                ApiKey.user_id == user_id,
                ApiKey.exchange == exchange,
                ApiKey.is_active == True
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"查询API密钥失败: {str(e)}")
            return None
    
    async def _test_connection(self, exchange: ccxt.Exchange) -> bool:
        """测试交易所连接"""
        try:
            # 异步调用API
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, exchange.fetch_balance)
            return True
        except Exception as e:
            logger.error(f"交易所连接测试失败: {str(e)}")
            return False
    
    async def get_account_balance(self, user_id: int, exchange_name: str,
                                db: AsyncSession) -> Optional[Dict[str, Any]]:
        """获取账户余额"""
        try:
            exchange = await self.get_exchange(user_id, exchange_name, db)
            if not exchange:
                return None
            
            loop = asyncio.get_event_loop()
            balance = await loop.run_in_executor(None, exchange.fetch_balance)
            
            # 格式化余额信息
            formatted_balance = {
                'exchange': exchange_name,
                'timestamp': datetime.utcnow().isoformat(),
                'balances': {}
            }
            
            for currency, amount in balance.get('total', {}).items():
                if amount and float(amount) > 0:
                    formatted_balance['balances'][currency] = {
                        'total': float(amount),
                        'free': float(balance.get('free', {}).get(currency, 0)),
                        'used': float(balance.get('used', {}).get(currency, 0))
                    }
            
            return formatted_balance
            
        except Exception as e:
            logger.error(f"获取账户余额失败: {exchange_name}, 用户: {user_id}, 错误: {str(e)}")
            return None
    
    async def get_symbols(self, exchange_name: str) -> List[str]:
        """获取交易所支持的交易对"""
        try:
            # 创建临时实例获取市场信息
            exchange_class = self.SUPPORTED_EXCHANGES.get(exchange_name)
            if not exchange_class:
                return []
            
            exchange = exchange_class({'enableRateLimit': True})
            loop = asyncio.get_event_loop()
            markets = await loop.run_in_executor(None, exchange.load_markets)
            
            # 过滤出活跃的交易对
            symbols = [symbol for symbol, market in markets.items() 
                      if market.get('active', True) and '/' in symbol]
            
            return sorted(symbols)
            
        except Exception as e:
            logger.error(f"获取交易对列表失败: {exchange_name}, 错误: {str(e)}")
            return []
    
    async def get_market_data(self, user_id: int, exchange_name: str, symbol: str,
                            timeframe: str, limit: int,
                            db: AsyncSession) -> Optional[List[Dict[str, Any]]]:
        """获取市场数据（K线）"""
        try:
            exchange = await self.get_exchange(user_id, exchange_name, db)
            if not exchange:
                # 如果用户没有配置API，使用公开接口
                logger.info(f"用户 {user_id} 无可用API密钥，使用公共API获取数据: {exchange_name}")
                exchange = self._create_public_exchange_instance(exchange_name)
            
            logger.info(f"获取市场数据: {symbol} {timeframe} limit={limit} exchange={exchange_name}")
            loop = asyncio.get_event_loop()
            ohlcv_data = await loop.run_in_executor(
                None, 
                exchange.fetch_ohlcv, 
                symbol, 
                timeframe, 
                None, 
                limit
            )
            
            logger.info(f"成功获取 {len(ohlcv_data) if ohlcv_data else 0} 条市场数据")
            
            # 转换数据格式
            formatted_data = []
            for ohlcv in ohlcv_data:
                formatted_data.append({
                    'timestamp': ohlcv[0],
                    'datetime': datetime.fromtimestamp(ohlcv[0] / 1000).isoformat(),
                    'open': float(ohlcv[1]),
                    'high': float(ohlcv[2]),
                    'low': float(ohlcv[3]),
                    'close': float(ohlcv[4]),
                    'volume': float(ohlcv[5]) if ohlcv[5] else 0
                })
            
            logger.info(f"格式化完成，返回 {len(formatted_data)} 条数据")
            return formatted_data
            
        except Exception as e:
            logger.error(f"获取市场数据失败: {exchange_name}, {symbol}, 错误: {str(e)}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None
    
    async def place_order(self, user_id: int, exchange_name: str, symbol: str,
                         order_type: str, side: str, amount: float, 
                         price: Optional[float],
                         db: AsyncSession,
                         skip_risk_check: bool = False) -> Optional[Dict[str, Any]]:
        """
        智能下单 - 集成风险管理的安全下单
        
        Args:
            user_id: 用户ID
            exchange_name: 交易所名称
            symbol: 交易对
            order_type: 订单类型 (market/limit)  
            side: 买卖方向 (buy/sell)
            amount: 数量
            price: 价格 (限价单必需)
            db: 数据库会话
            skip_risk_check: 是否跳过风险检查 (仅测试用)
            
        Returns:
            订单结果或None (如果风险检查失败)
        """
        try:
            logger.info(f"开始智能下单: 用户{user_id}, {exchange_name}, {symbol}, {side}, 数量{amount}")
            
            # 1. 获取交易所实例
            exchange = await self.get_exchange(user_id, exchange_name, db)
            if not exchange:
                logger.error(f"无法获取交易所实例: {exchange_name}, 用户: {user_id}")
                return {
                    'success': False,
                    'error': f'无法连接到交易所 {exchange_name}',
                    'error_code': 'EXCHANGE_CONNECTION_ERROR'
                }
            
            # 2. 获取账户余额 (风险检查需要)
            account_balance = {}
            if not skip_risk_check:
                balance_info = await self.get_account_balance(user_id, exchange_name, db)
                if balance_info:
                    account_balance = balance_info.get('balances', {})
                    # 转换为简单的字典格式
                    account_balance = {
                        currency: balance_data.get('free', 0) 
                        for currency, balance_data in account_balance.items()
                    }
                else:
                    logger.warning(f"无法获取账户余额，使用风险检查")
                    # 即使无法获取余额也继续风险检查，使用保守估计
                    account_balance = {'USDT': 0, symbol.split('/')[0]: 0}
            
            # 3. 风险管理验证
            if not skip_risk_check:
                logger.info("开始风险验证...")
                
                risk_assessment = await risk_manager.validate_order(
                    user_id=user_id,
                    exchange=exchange_name,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=amount,
                    price=price,
                    account_balance=account_balance,
                    db=db
                )
                
                # 风险检查结果处理
                if not risk_assessment.approved:
                    logger.warning(f"订单被风险管理拒绝: {risk_assessment.violations}")
                    return {
                        'success': False,
                        'error': '订单风险过高，已被安全系统拒绝',
                        'error_code': 'RISK_MANAGEMENT_REJECTION',
                        'risk_assessment': {
                            'approved': False,
                            'risk_level': risk_assessment.risk_level.value,
                            'risk_score': risk_assessment.risk_score,
                            'violations': risk_assessment.violations,
                            'warnings': risk_assessment.warnings
                        }
                    }
                
                # 风险等级为HIGH时给出警告但允许执行
                if risk_assessment.risk_level == RiskLevel.HIGH:
                    logger.warning(f"高风险订单，但允许执行: {risk_assessment.warnings}")
                
                # 如果建议调整仓位大小，使用建议值
                if risk_assessment.suggested_position_size and risk_assessment.suggested_position_size < amount:
                    logger.info(f"根据风险建议调整仓位: {amount} -> {risk_assessment.suggested_position_size}")
                    amount = risk_assessment.suggested_position_size
                
                logger.info(f"风险验证通过: 等级={risk_assessment.risk_level.value}, 评分={DataValidator.safe_format_decimal(risk_assessment.risk_score, decimals=2)}")
            
            # 4. 执行实际下单
            loop = asyncio.get_event_loop()
            order = None
            
            # 根据订单类型调用不同的方法
            if order_type.lower() == 'market':
                logger.info(f"执行市价单: {symbol}, {side}, {amount}")
                order = await loop.run_in_executor(
                    None,
                    exchange.create_market_order,
                    symbol, side, amount
                )
            elif order_type.lower() == 'limit':
                if not price:
                    raise ValueError("限价单必须指定价格")
                logger.info(f"执行限价单: {symbol}, {side}, {amount} @ {price}")
                order = await loop.run_in_executor(
                    None,
                    exchange.create_limit_order,
                    symbol, side, amount, price
                )
            else:
                raise ValueError(f"不支持的订单类型: {order_type}")
            
            # 5. 格式化订单响应
            formatted_order = {
                'success': True,
                'id': order.get('id'),
                'symbol': symbol,
                'type': order_type,
                'side': side,
                'amount': float(order.get('amount', amount)),
                'price': float(order.get('price', price)) if price else None,
                'filled': float(order.get('filled', 0)),
                'remaining': float(order.get('remaining', amount)),
                'status': order.get('status'),
                'timestamp': order.get('timestamp'),
                'datetime': datetime.fromtimestamp(order.get('timestamp', 0) / 1000).isoformat() if order.get('timestamp') else datetime.utcnow().isoformat(),
                'exchange': exchange_name,
                'fee': order.get('fee'),
                'cost': float(order.get('cost', 0))
            }
            
            # 6. 记录交易到数据库
            await self._record_trade_to_db(formatted_order, user_id, db)
            
            logger.info(f"订单执行成功: ID={formatted_order.get('id')}, 状态={formatted_order.get('status')}")
            return formatted_order
            
        except ccxt.NetworkError as e:
            error_msg = f"网络错误: {str(e)}"
            logger.error(f"下单网络错误: {exchange_name}, {symbol}, 错误: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'error_code': 'NETWORK_ERROR'
            }
        except ccxt.ExchangeError as e:
            error_msg = f"交易所错误: {str(e)}"
            logger.error(f"下单交易所错误: {exchange_name}, {symbol}, 错误: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'error_code': 'EXCHANGE_ERROR'
            }
        except Exception as e:
            error_msg = f"下单系统错误: {str(e)}"
            logger.error(f"下单失败: {exchange_name}, {symbol}, 错误: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'error_code': 'SYSTEM_ERROR'
            }
    
    async def _record_trade_to_db(self, order_info: Dict[str, Any], user_id: int, db: AsyncSession):
        """将成功的交易记录到数据库"""
        try:
            if order_info.get('status') in ['closed', 'filled']:
                trade = Trade(
                    user_id=user_id,
                    strategy_id=None,  # 手动交易暂时为空
                    exchange=order_info.get('exchange'),
                    symbol=order_info.get('symbol'),
                    side=order_info.get('side', '').upper(),
                    quantity=Decimal(str(order_info.get('amount', 0))),
                    price=Decimal(str(order_info.get('price', 0))),
                    total_amount=Decimal(str(order_info.get('cost', 0))),
                    fee=Decimal(str(order_info.get('fee', {}).get('cost', 0))),
                    order_id=order_info.get('id'),
                    trade_type='LIVE',
                    executed_at=datetime.fromtimestamp(order_info.get('timestamp', 0) / 1000) if order_info.get('timestamp') else datetime.utcnow()
                )
                
                db.add(trade)
                await db.commit()
                logger.info(f"交易记录已保存: {trade.symbol}, {trade.side}, {trade.quantity}")
                
        except Exception as e:
            logger.error(f"保存交易记录失败: {str(e)}")
            # 不要因为数据库错误影响交易成功
            await db.rollback()
    
    async def get_order_status(self, user_id: int, exchange_name: str,
                             order_id: str, symbol: str,
                             db: AsyncSession) -> Optional[Dict[str, Any]]:
        """查询订单状态"""
        try:
            exchange = await self.get_exchange(user_id, exchange_name, db)
            if not exchange:
                return None
            
            loop = asyncio.get_event_loop()
            order = await loop.run_in_executor(
                None,
                exchange.fetch_order,
                order_id, symbol
            )
            
            return {
                'id': order.get('id'),
                'symbol': order.get('symbol'),
                'status': order.get('status'),
                'filled': float(order.get('filled', 0)),
                'remaining': float(order.get('remaining', 0)),
                'average': float(order.get('average', 0)) if order.get('average') else None,
                'cost': float(order.get('cost', 0)),
                'fee': order.get('fee'),
                'timestamp': order.get('timestamp')
            }
            
        except Exception as e:
            logger.error(f"查询订单状态失败: {exchange_name}, {order_id}, 错误: {str(e)}")
            return None
    
    async def cancel_order(self, user_id: int, exchange_name: str,
                          order_id: str, symbol: str,
                          db: AsyncSession) -> bool:
        """取消订单"""
        try:
            exchange = await self.get_exchange(user_id, exchange_name, db)
            if not exchange:
                return False
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                exchange.cancel_order,
                order_id, symbol
            )
            
            logger.info(f"订单取消成功: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消订单失败: {exchange_name}, {order_id}, 错误: {str(e)}")
            return False
    
    async def get_trading_fees(self, user_id: int, exchange_name: str,
                             db: AsyncSession) -> Optional[Dict[str, Any]]:
        """获取交易手续费"""
        try:
            exchange = await self.get_exchange(user_id, exchange_name, db)
            if not exchange:
                return None
            
            loop = asyncio.get_event_loop()
            fees = await loop.run_in_executor(None, exchange.fetch_trading_fees)
            
            return {
                'exchange': exchange_name,
                'maker': float(fees.get('maker', 0)),
                'taker': float(fees.get('taker', 0)),
                'percentage': fees.get('percentage', True),
                'tierBased': fees.get('tierBased', False)
            }
            
        except Exception as e:
            logger.error(f"获取交易手续费失败: {exchange_name}, 错误: {str(e)}")
            return None
    
    def close_exchange(self, user_id: int, exchange_name: str):
        """关闭交易所连接"""
        cache_key = f"{user_id}_{exchange_name}"
        if cache_key in self._exchanges:
            try:
                exchange = self._exchanges[cache_key]
                if hasattr(exchange, 'close'):
                    exchange.close()
                del self._exchanges[cache_key]
                if cache_key in self._connections:
                    del self._connections[cache_key]
                logger.info(f"交易所连接已关闭: {exchange_name}, 用户: {user_id}")
            except Exception as e:
                logger.error(f"关闭交易所连接失败: {str(e)}")
    
    def close_all_exchanges(self):
        """关闭所有交易所连接"""
        for cache_key in list(self._exchanges.keys()):
            try:
                exchange = self._exchanges[cache_key]
                if hasattr(exchange, 'close'):
                    exchange.close()
            except Exception as e:
                logger.error(f"关闭交易所连接失败: {cache_key}, 错误: {str(e)}")
        
        self._exchanges.clear()
        self._connections.clear()
        logger.info("所有交易所连接已关闭")


# 全局交易所服务实例
exchange_service = ExchangeService()