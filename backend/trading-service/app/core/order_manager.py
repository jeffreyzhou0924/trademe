"""
订单管理和执行引擎 - 实盘交易订单生命周期管理

核心功能:
- 订单创建和验证
- 订单状态实时跟踪
- 执行监控和异常处理
- 批量订单管理
- 订单历史和分析
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

from app.models.trade import Trade
from app.services.exchange_service import exchange_service
from app.core.risk_manager import risk_manager


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"          # 待创建
    SUBMITTED = "submitted"      # 已提交
    OPEN = "open"               # 开放（部分成交）
    FILLED = "filled"           # 完全成交
    CANCELED = "canceled"       # 已取消
    REJECTED = "rejected"       # 被拒绝
    EXPIRED = "expired"         # 已过期
    FAILED = "failed"           # 失败


class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"           # 市价单
    LIMIT = "limit"            # 限价单
    STOP = "stop"              # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderRequest:
    """订单创建请求"""
    user_id: int
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"  # GTC, IOC, FOK
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None


@dataclass 
class OrderInfo:
    """订单信息"""
    id: str
    user_id: int
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    stop_price: Optional[float]
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    exchange_order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    fees: float = 0.0
    fills: List[Dict] = field(default_factory=list)


class OrderManager:
    """订单管理和执行引擎"""
    
    def __init__(self):
        """初始化订单管理器"""
        self._active_orders: Dict[str, OrderInfo] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._order_history: List[OrderInfo] = []
        self._max_history_size = 10000
        
    async def create_order(
        self,
        request: OrderRequest,
        db: AsyncSession,
        skip_risk_check: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        创建新订单
        
        Args:
            request: 订单请求
            db: 数据库会话
            skip_risk_check: 是否跳过风险检查
            
        Returns:
            (success: bool, result: dict)
        """
        try:
            logger.info(f"创建订单: 用户{request.user_id}, {request.exchange}, {request.symbol}, {request.side.value}, 数量{request.quantity}")
            
            # 1. 生成订单ID
            order_id = str(uuid.uuid4())
            client_order_id = request.client_order_id or f"tm_{order_id[:8]}"
            
            # 2. 基础验证
            validation_result = await self._validate_order_request(request)
            if not validation_result[0]:
                return False, {
                    'error': validation_result[1],
                    'error_code': 'VALIDATION_ERROR',
                    'order_id': order_id
                }
            
            # 3. 创建订单对象
            order = OrderInfo(
                id=order_id,
                user_id=request.user_id,
                exchange=request.exchange,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                price=request.price,
                stop_price=request.stop_price,
                remaining_quantity=request.quantity,
                client_order_id=client_order_id,
                status=OrderStatus.PENDING
            )
            
            # 4. 执行订单
            execution_result = await self._execute_order(order, db, skip_risk_check)
            
            if execution_result['success']:
                # 订单提交成功，开始监控
                self._active_orders[order_id] = order
                await self._start_order_monitoring(order_id, db)
                
                logger.info(f"订单创建成功: {order_id}, 交易所订单ID: {order.exchange_order_id}")
                return True, {
                    'success': True,
                    'order_id': order_id,
                    'exchange_order_id': order.exchange_order_id,
                    'status': order.status.value,
                    'message': '订单已成功提交'
                }
            else:
                # 订单提交失败
                order.status = OrderStatus.FAILED
                order.error_message = execution_result.get('error', '未知错误')
                self._add_to_history(order)
                
                logger.error(f"订单创建失败: {order_id}, 错误: {order.error_message}")
                return False, {
                    'success': False,
                    'order_id': order_id,
                    'error': order.error_message,
                    'error_code': execution_result.get('error_code', 'EXECUTION_ERROR')
                }
                
        except Exception as e:
            logger.error(f"创建订单异常: {str(e)}")
            return False, {
                'success': False,
                'error': f'系统错误: {str(e)}',
                'error_code': 'SYSTEM_ERROR'
            }
    
    async def _validate_order_request(self, request: OrderRequest) -> Tuple[bool, str]:
        """验证订单请求参数"""
        try:
            # 基础参数验证
            if request.quantity <= 0:
                return False, "订单数量必须大于0"
            
            if request.quantity > 1000000:  # 防止错误输入
                return False, "订单数量过大"
            
            # 价格验证
            if request.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if not request.price or request.price <= 0:
                    return False, "限价单必须指定有效价格"
            
            if request.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if not request.stop_price or request.stop_price <= 0:
                    return False, "止损单必须指定有效止损价格"
            
            # 交易对格式验证
            if not request.symbol or '/' not in request.symbol:
                return False, "无效的交易对格式"
                
            return True, ""
            
        except Exception as e:
            logger.error(f"订单验证异常: {str(e)}")
            return False, f"验证失败: {str(e)}"
    
    async def _execute_order(
        self,
        order: OrderInfo,
        db: AsyncSession,
        skip_risk_check: bool = False
    ) -> Dict[str, Any]:
        """执行订单"""
        try:
            order.status = OrderStatus.SUBMITTED
            order.updated_at = datetime.utcnow()
            
            # 调用交易所服务执行订单
            result = await exchange_service.place_order(
                user_id=order.user_id,
                exchange_name=order.exchange,
                symbol=order.symbol,
                order_type=order.order_type.value,
                side=order.side.value,
                amount=order.quantity,
                price=order.price,
                db=db,
                skip_risk_check=skip_risk_check
            )
            
            if result and result.get('success'):
                # 更新订单信息
                order.exchange_order_id = result.get('id')
                order.status = self._map_exchange_status(result.get('status', 'open'))
                order.filled_quantity = result.get('filled', 0)
                order.remaining_quantity = order.quantity - order.filled_quantity
                order.avg_fill_price = result.get('price', 0) if result.get('filled', 0) > 0 else 0
                order.fees = result.get('fee', {}).get('cost', 0) if result.get('fee') else 0
                order.updated_at = datetime.utcnow()
                
                logger.info(f"订单执行成功: {order.id}, 交易所返回: {result.get('status')}")
                return {'success': True, 'result': result}
            else:
                error_msg = result.get('error', '执行失败') if result else '无响应'
                logger.error(f"订单执行失败: {order.id}, 错误: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'error_code': result.get('error_code', 'EXECUTION_ERROR') if result else 'NO_RESPONSE'
                }
                
        except Exception as e:
            logger.error(f"订单执行异常: {str(e)}")
            return {
                'success': False,
                'error': f'执行异常: {str(e)}',
                'error_code': 'EXECUTION_EXCEPTION'
            }
    
    def _map_exchange_status(self, exchange_status: str) -> OrderStatus:
        """映射交易所状态到内部状态"""
        status_mapping = {
            'open': OrderStatus.OPEN,
            'closed': OrderStatus.FILLED,
            'filled': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELED,
            'cancelled': OrderStatus.CANCELED,
            'rejected': OrderStatus.REJECTED,
            'expired': OrderStatus.EXPIRED
        }
        return status_mapping.get(exchange_status.lower(), OrderStatus.OPEN)
    
    async def _start_order_monitoring(self, order_id: str, db: AsyncSession):
        """开始监控订单状态"""
        if order_id in self._monitoring_tasks:
            return  # 已在监控中
            
        task = asyncio.create_task(self._monitor_order(order_id, db))
        self._monitoring_tasks[order_id] = task
        logger.debug(f"开始监控订单: {order_id}")
    
    async def _monitor_order(self, order_id: str, db: AsyncSession):
        """监控单个订单状态"""
        try:
            while order_id in self._active_orders:
                order = self._active_orders[order_id]
                
                # 检查是否为最终状态
                if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, 
                                  OrderStatus.REJECTED, OrderStatus.EXPIRED, OrderStatus.FAILED]:
                    break
                
                # 查询最新状态
                try:
                    status_result = await exchange_service.get_order_status(
                        user_id=order.user_id,
                        exchange_name=order.exchange,
                        order_id=order.exchange_order_id,
                        symbol=order.symbol,
                        db=db
                    )
                    
                    if status_result:
                        # 更新订单状态
                        old_status = order.status
                        order.status = self._map_exchange_status(status_result.get('status', 'open'))
                        order.filled_quantity = status_result.get('filled', 0)
                        order.remaining_quantity = order.quantity - order.filled_quantity
                        order.avg_fill_price = status_result.get('average', 0) if order.filled_quantity > 0 else 0
                        order.fees += status_result.get('fee', {}).get('cost', 0) if status_result.get('fee') else 0
                        order.updated_at = datetime.utcnow()
                        
                        # 记录状态变化
                        if old_status != order.status:
                            logger.info(f"订单状态变化: {order_id}, {old_status.value} -> {order.status.value}")
                        
                        # 检查是否已完成
                        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, 
                                          OrderStatus.REJECTED, OrderStatus.EXPIRED]:
                            break
                    
                except Exception as e:
                    logger.error(f"查询订单状态异常: {order_id}, 错误: {str(e)}")
                
                # 等待后继续监控
                await asyncio.sleep(5)  # 每5秒检查一次
            
            # 订单完成，移到历史记录
            if order_id in self._active_orders:
                order = self._active_orders.pop(order_id)
                self._add_to_history(order)
                logger.info(f"订单监控完成: {order_id}, 最终状态: {order.status.value}")
            
        except asyncio.CancelledError:
            logger.debug(f"订单监控任务被取消: {order_id}")
        except Exception as e:
            logger.error(f"订单监控异常: {order_id}, 错误: {str(e)}")
        finally:
            # 清理监控任务
            if order_id in self._monitoring_tasks:
                del self._monitoring_tasks[order_id]
    
    def _add_to_history(self, order: OrderInfo):
        """添加订单到历史记录"""
        self._order_history.append(order)
        
        # 限制历史记录大小
        if len(self._order_history) > self._max_history_size:
            self._order_history = self._order_history[-self._max_history_size:]
    
    async def cancel_order(
        self,
        order_id: str,
        user_id: int,
        db: AsyncSession
    ) -> Tuple[bool, str]:
        """取消订单"""
        try:
            if order_id not in self._active_orders:
                return False, "订单不存在或已完成"
            
            order = self._active_orders[order_id]
            
            # 验证用户权限
            if order.user_id != user_id:
                return False, "无权限取消此订单"
            
            # 检查订单状态
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, 
                              OrderStatus.REJECTED, OrderStatus.EXPIRED]:
                return False, f"订单状态为 {order.status.value}，无法取消"
            
            # 调用交易所取消订单
            cancel_result = await exchange_service.cancel_order(
                user_id=user_id,
                exchange_name=order.exchange,
                order_id=order.exchange_order_id,
                symbol=order.symbol,
                db=db
            )
            
            if cancel_result:
                order.status = OrderStatus.CANCELED
                order.updated_at = datetime.utcnow()
                logger.info(f"订单取消成功: {order_id}")
                return True, "订单已取消"
            else:
                return False, "取消订单失败"
                
        except Exception as e:
            logger.error(f"取消订单异常: {str(e)}")
            return False, f"取消失败: {str(e)}"
    
    def get_active_orders(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取活跃订单列表"""
        try:
            orders = []
            for order in self._active_orders.values():
                if user_id is None or order.user_id == user_id:
                    orders.append(self._order_to_dict(order))
            
            # 按创建时间倒序排序
            orders.sort(key=lambda x: x['created_at'], reverse=True)
            return orders
            
        except Exception as e:
            logger.error(f"获取活跃订单失败: {str(e)}")
            return []
    
    def get_order_history(
        self,
        user_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取订单历史"""
        try:
            orders = []
            for order in reversed(self._order_history[-limit:]):  # 最近的订单
                if user_id is None or order.user_id == user_id:
                    orders.append(self._order_to_dict(order))
            
            return orders[:limit]
            
        except Exception as e:
            logger.error(f"获取订单历史失败: {str(e)}")
            return []
    
    def get_order_by_id(self, order_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取订单"""
        try:
            # 先查找活跃订单
            if order_id in self._active_orders:
                order = self._active_orders[order_id]
                if order.user_id == user_id:
                    return self._order_to_dict(order)
            
            # 再查找历史订单
            for order in self._order_history:
                if order.id == order_id and order.user_id == user_id:
                    return self._order_to_dict(order)
            
            return None
            
        except Exception as e:
            logger.error(f"获取订单详情失败: {str(e)}")
            return None
    
    def _order_to_dict(self, order: OrderInfo) -> Dict[str, Any]:
        """将订单对象转换为字典"""
        return {
            'id': order.id,
            'user_id': order.user_id,
            'exchange': order.exchange,
            'symbol': order.symbol,
            'side': order.side.value,
            'order_type': order.order_type.value,
            'quantity': order.quantity,
            'price': order.price,
            'stop_price': order.stop_price,
            'filled_quantity': order.filled_quantity,
            'remaining_quantity': order.remaining_quantity,
            'avg_fill_price': order.avg_fill_price,
            'status': order.status.value,
            'exchange_order_id': order.exchange_order_id,
            'client_order_id': order.client_order_id,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat(),
            'error_message': order.error_message,
            'fees': order.fees,
            'fills': order.fills
        }
    
    async def get_order_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取订单统计信息"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # 统计活跃订单
            active_orders = [o for o in self._active_orders.values() 
                           if o.user_id == user_id]
            
            # 统计历史订单
            period_orders = [o for o in self._order_history 
                           if o.user_id == user_id and o.created_at >= start_time]
            
            # 计算统计指标
            total_orders = len(period_orders)
            filled_orders = sum(1 for o in period_orders if o.status == OrderStatus.FILLED)
            canceled_orders = sum(1 for o in period_orders if o.status == OrderStatus.CANCELED)
            failed_orders = sum(1 for o in period_orders if o.status in [OrderStatus.REJECTED, OrderStatus.FAILED])
            
            fill_rate = (filled_orders / total_orders * 100) if total_orders > 0 else 0
            total_volume = sum(o.filled_quantity * (o.avg_fill_price or 0) for o in period_orders)
            total_fees = sum(o.fees for o in period_orders)
            
            # 按交易对和交易所统计
            symbols = set(o.symbol for o in period_orders)
            exchanges = set(o.exchange for o in period_orders)
            
            return {
                'period_days': days,
                'active_orders_count': len(active_orders),
                'total_orders': total_orders,
                'filled_orders': filled_orders,
                'canceled_orders': canceled_orders,
                'failed_orders': failed_orders,
                'fill_rate': round(fill_rate, 2),
                'total_volume': round(total_volume, 2),
                'total_fees': round(total_fees, 6),
                'symbols_traded': list(symbols),
                'exchanges_used': list(exchanges),
                'avg_order_size': round(total_volume / filled_orders, 2) if filled_orders > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取订单统计失败: {str(e)}")
            return {}
    
    async def cleanup_completed_orders(self, max_age_hours: int = 24):
        """清理已完成的老订单"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            # 移动到历史记录
            to_remove = []
            for order_id, order in self._active_orders.items():
                if (order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, 
                                   OrderStatus.REJECTED, OrderStatus.EXPIRED, OrderStatus.FAILED] 
                    and order.updated_at < cutoff_time):
                    to_remove.append(order_id)
            
            for order_id in to_remove:
                order = self._active_orders.pop(order_id)
                self._add_to_history(order)
                
                # 取消监控任务
                if order_id in self._monitoring_tasks:
                    self._monitoring_tasks[order_id].cancel()
                    del self._monitoring_tasks[order_id]
            
            logger.info(f"清理了 {len(to_remove)} 个已完成订单")
            
        except Exception as e:
            logger.error(f"清理订单异常: {str(e)}")
    
    async def emergency_cancel_all_orders(self, user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """紧急取消用户所有订单"""
        try:
            user_orders = [oid for oid, order in self._active_orders.items() 
                          if order.user_id == user_id]
            
            results = []
            for order_id in user_orders:
                cancel_result = await self.cancel_order(order_id, user_id, db)
                results.append({
                    'order_id': order_id,
                    'success': cancel_result[0],
                    'message': cancel_result[1]
                })
            
            success_count = sum(1 for r in results if r['success'])
            logger.warning(f"紧急取消用户 {user_id} 的订单: {success_count}/{len(results)} 成功")
            
            return {
                'total_orders': len(results),
                'success_count': success_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"紧急取消订单异常: {str(e)}")
            return {'error': f'紧急取消失败: {str(e)}'}


# 全局订单管理器实例
order_manager = OrderManager()