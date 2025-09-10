"""
OKX交易所专用服务
基于CCXT库的OKX交易所深度集成，提供完整的交易功能

功能特性:
- OKX API认证和连接管理
- 账户信息和余额查询  
- 订单执行和管理
- 实时数据获取
- 风险控制集成
- WebSocket实时推送
"""

import ccxt
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
import hmac
import time
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger
from app.utils.data_validation import DataValidator

from app.config import settings
from app.models.api_key import ApiKey
from app.models.trade import Trade
from app.models.user import User
from app.core.risk_manager import risk_manager, OrderRiskAssessment, RiskLevel
from app.core.exceptions import TradingError, ExchangeError, AuthenticationError
from app.services.exchange_service import ExchangeService


class OKXOrderType(Enum):
    """OKX订单类型"""
    MARKET = "market"       # 市价单
    LIMIT = "limit"         # 限价单
    POST_ONLY = "post_only" # 只做maker单
    FOK = "fok"            # 全部成交或立即取消
    IOC = "ioc"            # 立即成交或取消


class OKXOrderSide(Enum):
    """OKX订单方向"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class OKXOrderRequest:
    """OKX订单请求"""
    symbol: str
    side: OKXOrderSide
    amount: Decimal
    order_type: OKXOrderType = OKXOrderType.MARKET
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: Optional[str] = None
    client_order_id: Optional[str] = None


@dataclass
class OKXAccountInfo:
    """OKX账户信息"""
    total_equity: Decimal
    available_balance: Decimal
    frozen_balance: Decimal
    unrealized_pnl: Decimal
    margin_ratio: Optional[Decimal] = None
    positions: List[Dict] = None


@dataclass
class OKXOrderInfo:
    """OKX订单信息"""
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: str
    amount: Decimal
    price: Optional[Decimal]
    filled_amount: Decimal
    remaining_amount: Decimal
    status: str
    order_type: str
    created_at: datetime
    updated_at: datetime
    fee: Optional[Decimal] = None
    average_price: Optional[Decimal] = None


class OKXTradingService:
    """OKX交易所专用服务"""
    
    def __init__(self):
        self.exchange_name = "okx"
        self.base_url = "https://www.okx.com"
        self.sandbox_url = "https://www.okx.com"  # OKX使用相同URL，通过API密钥区分
        self._exchanges: Dict[str, ccxt.okx] = {}
        self._connections: Dict[str, bool] = {}
        self._user_configs: Dict[str, Dict] = {}
        
        # OKX特有配置
        self.supported_symbols = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT',
            'XRP/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT'
        ]
        
        logger.info("🚀 OKX交易服务初始化完成")
    
    async def authenticate_user(self, user_id: int, db: AsyncSession) -> Optional[ccxt.okx]:
        """
        认证用户并创建OKX交易所连接
        """
        try:
            cache_key = f"okx_user_{user_id}"
            
            # 检查缓存的连接
            if cache_key in self._exchanges and self._connections.get(cache_key, False):
                logger.info(f"✅ 使用缓存的OKX连接: 用户 {user_id}")
                return self._exchanges[cache_key]
            
            # 从数据库获取API密钥
            api_key_query = select(ApiKey).where(
                and_(ApiKey.user_id == user_id, ApiKey.exchange == "okx", ApiKey.is_active == True)
            )
            result = await db.execute(api_key_query)
            api_key_record = result.scalar_one_or_none()
            
            if not api_key_record:
                logger.warning(f"⚠️ 用户 {user_id} 未配置OKX API密钥")
                return None
            
            # 创建OKX交易所实例
            exchange = ccxt.okx({
                'apiKey': api_key_record.api_key,
                'secret': api_key_record.secret_key,
                'password': api_key_record.passphrase,  # OKX必需的passphrase
                'timeout': 30000,
                'enableRateLimit': True,
                'sandbox': settings.environment != "production",
                'options': {
                    'defaultType': 'spot',  # 默认现货交易
                }
            })
            
            # 测试连接
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, exchange.fetch_balance
                )
                
                # 缓存连接
                self._exchanges[cache_key] = exchange
                self._connections[cache_key] = True
                self._user_configs[cache_key] = {
                    'user_id': user_id,
                    'authenticated_at': datetime.utcnow(),
                    'api_key_id': api_key_record.id
                }
                
                logger.info(f"✅ OKX连接认证成功: 用户 {user_id}")
                return exchange
                
            except Exception as auth_error:
                logger.error(f"❌ OKX认证失败: 用户 {user_id}, 错误: {str(auth_error)}")
                raise AuthenticationError(f"OKX认证失败: {str(auth_error)}")
                
        except Exception as e:
            logger.error(f"❌ OKX用户认证异常: 用户 {user_id}, 错误: {str(e)}")
            raise TradingError(f"用户认证失败: {str(e)}")
    
    async def get_account_info(self, user_id: int, db: AsyncSession) -> OKXAccountInfo:
        """
        获取OKX账户信息
        """
        try:
            exchange = await self.authenticate_user(user_id, db)
            if not exchange:
                raise AuthenticationError("未找到有效的OKX连接")
            
            # 获取账户余额
            balance_data = await asyncio.get_event_loop().run_in_executor(
                None, exchange.fetch_balance
            )
            
            # 解析账户信息
            total_equity = Decimal(str(balance_data.get('total', 0)))
            free_balance = Decimal(str(balance_data.get('free', {}).get('USDT', 0)))
            used_balance = Decimal(str(balance_data.get('used', {}).get('USDT', 0)))
            
            account_info = OKXAccountInfo(
                total_equity=total_equity,
                available_balance=free_balance,
                frozen_balance=used_balance,
                unrealized_pnl=Decimal('0'),  # 需要额外API调用获取
            )
            
            logger.info(f"📊 OKX账户信息获取成功: 用户 {user_id}, 总资产: {total_equity}")
            return account_info
            
        except Exception as e:
            logger.error(f"❌ 获取OKX账户信息失败: 用户 {user_id}, 错误: {str(e)}")
            raise TradingError(f"获取账户信息失败: {str(e)}")
    
    async def place_order(self, user_id: int, order_request: OKXOrderRequest, 
                         db: AsyncSession) -> OKXOrderInfo:
        """
        在OKX交易所下单
        """
        try:
            exchange = await self.authenticate_user(user_id, db)
            if not exchange:
                raise AuthenticationError("未找到有效的OKX连接")
            
            # 风险检查
            risk_assessment = await self._assess_order_risk(user_id, order_request, db)
            if risk_assessment.risk_level == RiskLevel.HIGH:
                raise TradingError(f"订单风险过高: {risk_assessment.risk_message}")
            
            # 准备订单参数
            order_params = {
                'symbol': order_request.symbol,
                'type': order_request.order_type.value,
                'side': order_request.side.value,
                'amount': float(order_request.amount),
            }
            
            # 限价单需要指定价格
            if order_request.order_type in [OKXOrderType.LIMIT, OKXOrderType.POST_ONLY]:
                if not order_request.price:
                    raise ValueError("限价单必须指定价格")
                order_params['price'] = float(order_request.price)
            
            # 添加客户端订单ID
            if order_request.client_order_id:
                order_params['clientOrderId'] = order_request.client_order_id
            
            # 执行下单
            logger.info(f"📝 提交OKX订单: 用户 {user_id}, 参数: {order_params}")
            
            order_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: exchange.create_order(**order_params)
            )
            
            # 解析订单结果
            order_info = OKXOrderInfo(
                order_id=order_result['id'],
                client_order_id=order_result.get('clientOrderId'),
                symbol=order_result['symbol'],
                side=order_result['side'],
                amount=Decimal(str(order_result['amount'])),
                price=Decimal(str(order_result['price'])) if order_result.get('price') else None,
                filled_amount=Decimal(str(order_result['filled'])),
                remaining_amount=Decimal(str(order_result['remaining'])),
                status=order_result['status'],
                order_type=order_result['type'],
                created_at=datetime.fromtimestamp(order_result['timestamp'] / 1000),
                updated_at=datetime.utcnow(),
                fee=Decimal(str(order_result['fee']['cost'])) if order_result.get('fee') else None,
                average_price=Decimal(str(order_result['average'])) if order_result.get('average') else None
            )
            
            # 记录交易到数据库
            await self._save_trade_record(user_id, order_info, db)
            
            logger.info(f"✅ OKX订单创建成功: 用户 {user_id}, 订单ID: {order_info.order_id}")
            return order_info
            
        except Exception as e:
            logger.error(f"❌ OKX下单失败: 用户 {user_id}, 错误: {str(e)}")
            raise TradingError(f"下单失败: {str(e)}")
    
    async def get_order_status(self, user_id: int, order_id: str, 
                             symbol: str, db: AsyncSession) -> OKXOrderInfo:
        """
        查询OKX订单状态
        """
        try:
            exchange = await self.authenticate_user(user_id, db)
            if not exchange:
                raise AuthenticationError("未找到有效的OKX连接")
            
            # 查询订单状态
            order_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: exchange.fetch_order(order_id, symbol)
            )
            
            # 解析订单信息
            order_info = OKXOrderInfo(
                order_id=order_data['id'],
                client_order_id=order_data.get('clientOrderId'),
                symbol=order_data['symbol'],
                side=order_data['side'],
                amount=Decimal(str(order_data['amount'])),
                price=Decimal(str(order_data['price'])) if order_data.get('price') else None,
                filled_amount=Decimal(str(order_data['filled'])),
                remaining_amount=Decimal(str(order_data['remaining'])),
                status=order_data['status'],
                order_type=order_data['type'],
                created_at=datetime.fromtimestamp(order_data['timestamp'] / 1000),
                updated_at=datetime.utcnow(),
                fee=Decimal(str(order_data['fee']['cost'])) if order_data.get('fee') else None,
                average_price=Decimal(str(order_data['average'])) if order_data.get('average') else None
            )
            
            logger.info(f"📋 OKX订单状态查询成功: 用户 {user_id}, 订单ID: {order_id}, 状态: {order_info.status}")
            return order_info
            
        except Exception as e:
            logger.error(f"❌ 查询OKX订单状态失败: 用户 {user_id}, 订单ID: {order_id}, 错误: {str(e)}")
            raise TradingError(f"查询订单状态失败: {str(e)}")
    
    async def cancel_order(self, user_id: int, order_id: str, symbol: str, db: AsyncSession) -> bool:
        """
        取消OKX订单
        """
        try:
            exchange = await self.authenticate_user(user_id, db)
            if not exchange:
                raise AuthenticationError("未找到有效的OKX连接")
            
            # 取消订单
            cancel_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: exchange.cancel_order(order_id, symbol)
            )
            
            success = cancel_result.get('info', {}).get('sCode') == '0'
            
            if success:
                logger.info(f"✅ OKX订单取消成功: 用户 {user_id}, 订单ID: {order_id}")
            else:
                logger.warning(f"⚠️ OKX订单取消失败: 用户 {user_id}, 订单ID: {order_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 取消OKX订单失败: 用户 {user_id}, 订单ID: {order_id}, 错误: {str(e)}")
            return False
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取OKX交易对实时价格
        """
        try:
            # 使用公开API，不需要认证
            exchange = ccxt.okx()
            
            ticker_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: exchange.fetch_ticker(symbol)
            )
            
            return {
                'symbol': ticker_data['symbol'],
                'last': ticker_data['last'],
                'bid': ticker_data['bid'],
                'ask': ticker_data['ask'],
                'change': ticker_data['change'],
                'percentage': ticker_data['percentage'],
                'high': ticker_data['high'],
                'low': ticker_data['low'],
                'volume': ticker_data['baseVolume'],
                'timestamp': ticker_data['timestamp']
            }
            
        except Exception as e:
            logger.error(f"❌ 获取OKX价格数据失败: {symbol}, 错误: {str(e)}")
            raise TradingError(f"获取价格数据失败: {str(e)}")
    
    async def get_klines(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[List]:
        """
        获取OKX K线数据
        """
        try:
            # 使用公开API
            exchange = ccxt.okx()
            
            ohlcv_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            )
            
            logger.info(f"📈 获取OKX K线数据成功: {symbol}, 周期: {timeframe}, 数量: {len(ohlcv_data)}")
            return ohlcv_data
            
        except Exception as e:
            logger.error(f"❌ 获取OKX K线数据失败: {symbol}, 错误: {str(e)}")
            raise TradingError(f"获取K线数据失败: {str(e)}")
    
    async def get_supported_symbols(self) -> List[str]:
        """
        获取支持的交易对列表
        """
        return self.supported_symbols.copy()
    
    async def _assess_order_risk(self, user_id: int, order_request: OKXOrderRequest, 
                                db: AsyncSession) -> OrderRiskAssessment:
        """
        评估订单风险
        """
        try:
            # 获取账户信息
            account_info = await self.get_account_info(user_id, db)
            
            # 计算订单价值
            if order_request.order_type == OKXOrderType.MARKET:
                # 市价单：使用当前市价估算
                ticker = await self.get_ticker(order_request.symbol)
                estimated_price = Decimal(str(ticker['last']))
            else:
                # 限价单：使用指定价格
                estimated_price = order_request.price or Decimal('0')
            
            order_value = order_request.amount * estimated_price
            
            # 风险评估参数
            position_ratio = float(order_value / account_info.total_equity) if account_info.total_equity > 0 else 1
            available_ratio = float(order_value / account_info.available_balance) if account_info.available_balance > 0 else 1
            
            # 风险级别判断
            risk_level = RiskLevel.LOW
            risk_messages = []
            
            if position_ratio > 0.5:
                risk_level = RiskLevel.HIGH
                risk_messages.append(f"单笔订单占总资产比例过高: {DataValidator.safe_format_percentage(position_ratio * 100, decimals=1)}")
            elif position_ratio > 0.2:
                risk_level = RiskLevel.MEDIUM
                risk_messages.append(f"单笔订单占总资产比例较高: {DataValidator.safe_format_percentage(position_ratio * 100, decimals=1)}")
            
            if available_ratio > 1:
                risk_level = RiskLevel.HIGH
                risk_messages.append(f"订单价值超过可用余额: {DataValidator.safe_format_percentage(available_ratio * 100, decimals=1)}")
            elif available_ratio > 0.8:
                risk_level = max(risk_level, RiskLevel.MEDIUM)
                risk_messages.append(f"订单价值接近可用余额: {DataValidator.safe_format_percentage(available_ratio * 100, decimals=1)}")
            
            return OrderRiskAssessment(
                risk_level=risk_level,
                risk_score=max(position_ratio, available_ratio),
                risk_message=" | ".join(risk_messages) if risk_messages else "风险可控",
                suggested_amount=order_request.amount if risk_level != RiskLevel.HIGH else order_request.amount * Decimal('0.5')
            )
            
        except Exception as e:
            logger.error(f"❌ 订单风险评估失败: 用户 {user_id}, 错误: {str(e)}")
            return OrderRiskAssessment(
                risk_level=RiskLevel.HIGH,
                risk_score=1.0,
                risk_message=f"风险评估失败: {str(e)}",
                suggested_amount=Decimal('0')
            )
    
    async def _save_trade_record(self, user_id: int, order_info: OKXOrderInfo, db: AsyncSession):
        """
        保存交易记录到数据库
        """
        try:
            trade_record = Trade(
                user_id=user_id,
                exchange="okx",
                symbol=order_info.symbol,
                side=order_info.side,
                quantity=float(order_info.amount),
                price=float(order_info.price or 0),
                total_amount=float(order_info.amount * (order_info.price or Decimal('0'))),
                fee=float(order_info.fee or 0),
                order_id=order_info.order_id,
                trade_type="LIVE",
                executed_at=order_info.created_at,
            )
            
            db.add(trade_record)
            await db.commit()
            
            logger.info(f"💾 交易记录保存成功: 用户 {user_id}, 订单ID: {order_info.order_id}")
            
        except Exception as e:
            logger.error(f"❌ 保存交易记录失败: 用户 {user_id}, 错误: {str(e)}")
            await db.rollback()


# 创建全局OKX服务实例
okx_service = OKXTradingService()