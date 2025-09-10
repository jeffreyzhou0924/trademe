"""
智能订单路由系统 - Smart Order Router (SOR)

功能特性:
- 多交易所流动性聚合
- 最佳价格发现
- 订单拆分和执行优化
- 滑点最小化
- 市场影响分析
- 实时路由决策
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
import numpy as np

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.exchange_service import exchange_service
from app.core.risk_manager import risk_manager


class OrderRoutingStrategy(Enum):
    """订单路由策略"""
    BEST_PRICE = "best_price"           # 最佳价格
    MINIMAL_IMPACT = "minimal_impact"   # 最小市场影响
    FASTEST_FILL = "fastest_fill"       # 最快成交
    BALANCED = "balanced"               # 平衡策略
    ICEBERG = "iceberg"                 # 冰山策略
    TWAP = "twap"                      # 时间加权平均价格
    VWAP = "vwap"                      # 成交量加权平均价格


class ExecutionUrgency(Enum):
    """执行紧急程度"""
    LOW = "low"           # 低紧急度，注重成本
    MEDIUM = "medium"     # 中等紧急度
    HIGH = "high"         # 高紧急度，注重速度
    CRITICAL = "critical" # 关键紧急度，立即执行


@dataclass
class MarketLiquidity:
    """市场流动性信息"""
    exchange: str
    symbol: str
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    spread: float
    depth_5_bid: float  # 5档买单深度
    depth_5_ask: float  # 5档卖单深度
    last_trade_price: float
    volume_24h: float
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass 
class OrderFragment:
    """订单片段"""
    fragment_id: str
    parent_order_id: str
    exchange: str
    symbol: str
    side: str
    quantity: float
    price: Optional[float] = None
    order_type: str = "market"
    expected_fill_time: Optional[datetime] = None
    estimated_cost: float = 0.0
    estimated_slippage: float = 0.0
    priority: int = 1  # 执行优先级


@dataclass
class RoutingDecision:
    """路由决策"""
    decision_id: str
    original_order_id: str
    strategy: OrderRoutingStrategy
    fragments: List[OrderFragment] = field(default_factory=list)
    total_estimated_cost: float = 0.0
    total_estimated_slippage: float = 0.0
    expected_completion_time: Optional[datetime] = None
    confidence_score: float = 0.0
    reasoning: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrderExecutionResult:
    """订单执行结果"""
    fragment_id: str
    success: bool
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    actual_cost: float = 0.0
    actual_slippage: float = 0.0
    execution_time: float = 0.0  # 秒
    exchange_order_id: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.utcnow)


class SmartOrderRouter:
    """智能订单路由器"""
    
    def __init__(self):
        self.logger = logger.bind(service="SmartOrderRouter")
        
        # 流动性信息缓存
        self.liquidity_cache: Dict[str, Dict[str, MarketLiquidity]] = {}
        
        # 路由决策历史
        self.routing_history: Dict[str, RoutingDecision] = {}
        
        # 执行结果历史
        self.execution_history: List[OrderExecutionResult] = []
        
        # 交易所性能统计
        self.exchange_stats: Dict[str, Dict[str, float]] = {}
        
        # 配置参数
        self.config = {
            'max_order_fragments': 10,       # 最大订单分片数
            'min_fragment_size': 0.001,      # 最小分片大小
            'max_slippage_tolerance': 0.005, # 最大滑点容忍度
            'liquidity_update_interval': 5,   # 流动性更新间隔(秒)
            'execution_timeout': 30,         # 执行超时时间(秒)
            'price_impact_threshold': 0.002,  # 价格影响阈值
        }
        
        # 监控任务
        self._liquidity_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start_router(self):
        """启动智能路由器"""
        if self._running:
            return
            
        self._running = True
        self.logger.info("启动智能订单路由器")
        
        # 启动流动性监控任务
        self._liquidity_task = asyncio.create_task(self._liquidity_monitoring_loop())
        
        # 初始化交易所统计
        await self._initialize_exchange_stats()
        
        self.logger.info("智能订单路由器启动完成")
    
    async def stop_router(self):
        """停止智能路由器"""
        if not self._running:
            return
            
        self.logger.info("停止智能订单路由器")
        self._running = False
        
        # 停止监控任务
        if self._liquidity_task and not self._liquidity_task.done():
            self._liquidity_task.cancel()
            try:
                await self._liquidity_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("智能订单路由器已停止")
    
    async def route_order(
        self,
        order_id: str,
        user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        target_price: Optional[float] = None,
        strategy: OrderRoutingStrategy = OrderRoutingStrategy.BALANCED,
        urgency: ExecutionUrgency = ExecutionUrgency.MEDIUM,
        max_slippage: Optional[float] = None,
        db: Optional[AsyncSession] = None
    ) -> RoutingDecision:
        """
        路由订单到最优执行路径
        
        Args:
            order_id: 订单ID
            user_id: 用户ID
            symbol: 交易对
            side: 方向 (buy/sell)
            quantity: 数量
            order_type: 订单类型
            target_price: 目标价格
            strategy: 路由策略
            urgency: 执行紧急程度
            max_slippage: 最大滑点
            db: 数据库会话
        """
        try:
            self.logger.info(f"开始路由订单: {order_id}, {symbol}, {side}, {quantity}")
            
            # 获取当前市场流动性
            liquidity_data = await self._gather_market_liquidity(symbol)
            
            if not liquidity_data:
                raise ValueError("无法获取市场流动性数据")
            
            # 执行风险检查
            risk_check = await self._perform_risk_assessment(
                user_id, symbol, side, quantity, target_price, db
            )
            
            if not risk_check['approved']:
                raise ValueError(f"风险检查失败: {risk_check['reason']}")
            
            # 根据策略生成路由决策
            decision = await self._generate_routing_decision(
                order_id, symbol, side, quantity, order_type,
                target_price, strategy, urgency, max_slippage, liquidity_data
            )
            
            # 保存决策历史
            self.routing_history[decision.decision_id] = decision
            
            self.logger.info(f"订单路由决策生成: {decision.decision_id}, {len(decision.fragments)}个片段")
            return decision
            
        except Exception as e:
            self.logger.error(f"订单路由失败: {order_id}, 错误: {str(e)}")
            raise
    
    async def execute_routing_decision(
        self,
        decision: RoutingDecision,
        user_id: int,
        db: AsyncSession
    ) -> List[OrderExecutionResult]:
        """执行路由决策"""
        try:
            self.logger.info(f"开始执行路由决策: {decision.decision_id}")
            
            results = []
            
            # 按优先级排序片段
            sorted_fragments = sorted(decision.fragments, key=lambda x: x.priority)
            
            # 根据策略决定执行方式
            if decision.strategy in [OrderRoutingStrategy.FASTEST_FILL, OrderRoutingStrategy.CRITICAL]:
                # 并行执行
                tasks = [
                    self._execute_order_fragment(fragment, user_id, db)
                    for fragment in sorted_fragments
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理异常结果
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        error_result = OrderExecutionResult(
                            fragment_id=sorted_fragments[i].fragment_id,
                            success=False,
                            error_message=str(result)
                        )
                        results[i] = error_result
                        
            else:
                # 顺序执行
                for fragment in sorted_fragments:
                    result = await self._execute_order_fragment(fragment, user_id, db)
                    results.append(result)
                    
                    # 根据执行结果调整后续片段
                    if not result.success:
                        self.logger.warning(f"片段执行失败: {fragment.fragment_id}")
                        # 可以选择停止执行或调整剩余片段
            
            # 保存执行结果
            self.execution_history.extend(results)
            
            # 更新交易所性能统计
            await self._update_exchange_performance_stats(results)
            
            self.logger.info(f"路由决策执行完成: {decision.decision_id}, {len(results)}个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"执行路由决策失败: {decision.decision_id}, 错误: {str(e)}")
            raise
    
    async def _gather_market_liquidity(self, symbol: str) -> Dict[str, MarketLiquidity]:
        """收集市场流动性数据"""
        liquidity_data = {}
        
        try:
            # 获取所有支持该交易对的交易所
            supported_exchanges = await self._get_supported_exchanges_for_symbol(symbol)
            
            for exchange in supported_exchanges:
                try:
                    # 获取订单簿数据
                    orderbook = await exchange_service.get_orderbook(exchange, symbol, depth=10)
                    
                    if orderbook and 'bids' in orderbook and 'asks' in orderbook:
                        bids = orderbook['bids']
                        asks = orderbook['asks']
                        
                        if bids and asks:
                            bid_price = float(bids[0][0])
                            bid_size = float(bids[0][1])
                            ask_price = float(asks[0][0])
                            ask_size = float(asks[0][1])
                            
                            # 计算深度
                            depth_5_bid = sum(float(bid[1]) for bid in bids[:5])
                            depth_5_ask = sum(float(ask[1]) for ask in asks[:5])
                            
                            # 获取24小时成交量
                            ticker = await exchange_service.get_ticker(exchange, symbol)
                            volume_24h = float(ticker.get('volume', 0)) if ticker else 0
                            
                            liquidity = MarketLiquidity(
                                exchange=exchange,
                                symbol=symbol,
                                bid_price=bid_price,
                                ask_price=ask_price,
                                bid_size=bid_size,
                                ask_size=ask_size,
                                spread=(ask_price - bid_price) / bid_price,
                                depth_5_bid=depth_5_bid,
                                depth_5_ask=depth_5_ask,
                                last_trade_price=(bid_price + ask_price) / 2,
                                volume_24h=volume_24h
                            )
                            
                            liquidity_data[exchange] = liquidity
                            
                except Exception as e:
                    self.logger.warning(f"获取 {exchange} 流动性数据失败: {str(e)}")
                    continue
            
            # 更新缓存
            if symbol not in self.liquidity_cache:
                self.liquidity_cache[symbol] = {}
            self.liquidity_cache[symbol].update(liquidity_data)
            
        except Exception as e:
            self.logger.error(f"收集市场流动性失败: {symbol}, 错误: {str(e)}")
        
        return liquidity_data
    
    async def _generate_routing_decision(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        target_price: Optional[float],
        strategy: OrderRoutingStrategy,
        urgency: ExecutionUrgency,
        max_slippage: Optional[float],
        liquidity_data: Dict[str, MarketLiquidity]
    ) -> RoutingDecision:
        """生成路由决策"""
        try:
            decision_id = str(uuid.uuid4())
            fragments = []
            
            # 根据策略选择路由算法
            if strategy == OrderRoutingStrategy.BEST_PRICE:
                fragments = await self._route_by_best_price(
                    order_id, symbol, side, quantity, order_type, liquidity_data
                )
            elif strategy == OrderRoutingStrategy.MINIMAL_IMPACT:
                fragments = await self._route_by_minimal_impact(
                    order_id, symbol, side, quantity, order_type, liquidity_data
                )
            elif strategy == OrderRoutingStrategy.FASTEST_FILL:
                fragments = await self._route_by_fastest_fill(
                    order_id, symbol, side, quantity, order_type, liquidity_data
                )
            elif strategy == OrderRoutingStrategy.BALANCED:
                fragments = await self._route_by_balanced_strategy(
                    order_id, symbol, side, quantity, order_type, liquidity_data, urgency
                )
            elif strategy == OrderRoutingStrategy.ICEBERG:
                fragments = await self._route_by_iceberg_strategy(
                    order_id, symbol, side, quantity, order_type, liquidity_data
                )
            elif strategy in [OrderRoutingStrategy.TWAP, OrderRoutingStrategy.VWAP]:
                fragments = await self._route_by_time_weighted_strategy(
                    order_id, symbol, side, quantity, order_type, liquidity_data, strategy
                )
            else:
                # 默认策略：最佳价格
                fragments = await self._route_by_best_price(
                    order_id, symbol, side, quantity, order_type, liquidity_data
                )
            
            # 计算总体估算成本和滑点
            total_cost = sum(f.estimated_cost for f in fragments)
            total_slippage = sum(f.estimated_slippage * f.quantity for f in fragments) / quantity
            
            # 生成执行时间估算
            if urgency == ExecutionUrgency.CRITICAL:
                completion_time = datetime.utcnow() + timedelta(seconds=5)
            elif urgency == ExecutionUrgency.HIGH:
                completion_time = datetime.utcnow() + timedelta(seconds=15)
            elif urgency == ExecutionUrgency.MEDIUM:
                completion_time = datetime.utcnow() + timedelta(seconds=30)
            else:
                completion_time = datetime.utcnow() + timedelta(minutes=5)
            
            # 计算置信度分数
            confidence = self._calculate_confidence_score(fragments, liquidity_data, strategy)
            
            decision = RoutingDecision(
                decision_id=decision_id,
                original_order_id=order_id,
                strategy=strategy,
                fragments=fragments,
                total_estimated_cost=total_cost,
                total_estimated_slippage=total_slippage,
                expected_completion_time=completion_time,
                confidence_score=confidence,
                reasoning=self._generate_routing_reasoning(strategy, fragments, liquidity_data)
            )
            
            return decision
            
        except Exception as e:
            self.logger.error(f"生成路由决策失败: {str(e)}")
            raise
    
    async def _route_by_best_price(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        liquidity_data: Dict[str, MarketLiquidity]
    ) -> List[OrderFragment]:
        """按最佳价格路由"""
        fragments = []
        remaining_quantity = quantity
        
        # 按价格排序（买单按ask升序，卖单按bid降序）
        if side.lower() == 'buy':
            sorted_liquidity = sorted(
                liquidity_data.items(),
                key=lambda x: x[1].ask_price
            )
        else:
            sorted_liquidity = sorted(
                liquidity_data.items(),
                key=lambda x: x[1].bid_price,
                reverse=True
            )
        
        for i, (exchange, liquidity) in enumerate(sorted_liquidity):
            if remaining_quantity <= 0:
                break
            
            # 确定可执行数量
            if side.lower() == 'buy':
                available_size = liquidity.ask_size
                price = liquidity.ask_price
            else:
                available_size = liquidity.bid_size
                price = liquidity.bid_price
            
            # 考虑流动性深度
            max_size = min(available_size * 0.8, remaining_quantity)  # 只使用80%的可用流动性
            
            if max_size >= self.config['min_fragment_size']:
                fragment = OrderFragment(
                    fragment_id=str(uuid.uuid4()),
                    parent_order_id=order_id,
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    quantity=max_size,
                    price=price if order_type == 'limit' else None,
                    order_type=order_type,
                    estimated_cost=max_size * price,
                    estimated_slippage=self._calculate_estimated_slippage(liquidity, max_size, side),
                    priority=i + 1
                )
                
                fragments.append(fragment)
                remaining_quantity -= max_size
        
        return fragments
    
    async def _route_by_minimal_impact(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        liquidity_data: Dict[str, MarketLiquidity]
    ) -> List[OrderFragment]:
        """按最小市场影响路由"""
        fragments = []
        
        # 计算每个交易所的价格影响
        impact_scores = {}
        for exchange, liquidity in liquidity_data.items():
            depth = liquidity.depth_5_bid if side.lower() == 'sell' else liquidity.depth_5_ask
            impact = quantity / depth if depth > 0 else float('inf')
            impact_scores[exchange] = impact
        
        # 按影响程度排序
        sorted_by_impact = sorted(impact_scores.items(), key=lambda x: x[1])
        
        remaining_quantity = quantity
        for i, (exchange, impact) in enumerate(sorted_by_impact):
            if remaining_quantity <= 0:
                break
            
            liquidity = liquidity_data[exchange]
            
            # 计算合适的分片大小（基于流动性和影响）
            if side.lower() == 'buy':
                available_size = liquidity.depth_5_ask
                price = liquidity.ask_price
            else:
                available_size = liquidity.depth_5_bid
                price = liquidity.bid_price
            
            # 限制单笔订单对流动性的影响
            max_impact_ratio = 0.1  # 最多影响10%的深度
            max_size = min(available_size * max_impact_ratio, remaining_quantity)
            
            if max_size >= self.config['min_fragment_size']:
                fragment = OrderFragment(
                    fragment_id=str(uuid.uuid4()),
                    parent_order_id=order_id,
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    quantity=max_size,
                    price=price if order_type == 'limit' else None,
                    order_type=order_type,
                    estimated_cost=max_size * price,
                    estimated_slippage=self._calculate_estimated_slippage(liquidity, max_size, side),
                    priority=i + 1
                )
                
                fragments.append(fragment)
                remaining_quantity -= max_size
        
        return fragments
    
    async def _route_by_fastest_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        liquidity_data: Dict[str, MarketLiquidity]
    ) -> List[OrderFragment]:
        """按最快成交路由"""
        fragments = []
        
        # 按交易所性能排序
        sorted_exchanges = await self._sort_exchanges_by_performance(liquidity_data.keys())
        
        # 将订单分散到多个表现最佳的交易所
        num_exchanges = min(3, len(sorted_exchanges))  # 最多使用3个交易所
        quantity_per_exchange = quantity / num_exchanges
        
        for i, exchange in enumerate(sorted_exchanges[:num_exchanges]):
            liquidity = liquidity_data[exchange]
            
            if side.lower() == 'buy':
                price = liquidity.ask_price
                available_size = liquidity.ask_size
            else:
                price = liquidity.bid_price
                available_size = liquidity.bid_size
            
            # 确保不超过可用流动性
            fragment_size = min(quantity_per_exchange, available_size * 0.9)
            
            if fragment_size >= self.config['min_fragment_size']:
                fragment = OrderFragment(
                    fragment_id=str(uuid.uuid4()),
                    parent_order_id=order_id,
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    quantity=fragment_size,
                    price=price if order_type == 'limit' else None,
                    order_type='market',  # 使用市价单以确保快速成交
                    estimated_cost=fragment_size * price,
                    estimated_slippage=self._calculate_estimated_slippage(liquidity, fragment_size, side),
                    priority=1  # 所有片段同等优先级，并行执行
                )
                
                fragments.append(fragment)
        
        return fragments
    
    async def _route_by_balanced_strategy(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        liquidity_data: Dict[str, MarketLiquidity],
        urgency: ExecutionUrgency
    ) -> List[OrderFragment]:
        """平衡策略路由"""
        fragments = []
        
        # 综合评分：价格(40%) + 流动性(30%) + 性能(20%) + 费用(10%)
        exchange_scores = {}
        
        for exchange, liquidity in liquidity_data.items():
            # 价格分数
            if side.lower() == 'buy':
                price_score = 1.0 / liquidity.ask_price  # 价格越低分数越高
            else:
                price_score = liquidity.bid_price  # 价格越高分数越高
            
            # 流动性分数
            depth = liquidity.depth_5_bid if side.lower() == 'sell' else liquidity.depth_5_ask
            liquidity_score = min(depth / quantity, 1.0)  # 流动性充足度
            
            # 性能分数
            perf_stats = self.exchange_stats.get(exchange, {})
            performance_score = perf_stats.get('success_rate', 0.5)
            
            # 费用分数 (简化，实际应该从交易所获取)
            fee_score = 0.999  # 假设0.1%手续费
            
            # 综合分数
            total_score = (
                price_score * 0.4 +
                liquidity_score * 0.3 +
                performance_score * 0.2 +
                fee_score * 0.1
            )
            
            exchange_scores[exchange] = total_score
        
        # 按综合分数排序
        sorted_exchanges = sorted(
            exchange_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 根据紧急程度决定分配策略
        if urgency in [ExecutionUrgency.HIGH, ExecutionUrgency.CRITICAL]:
            # 高优先级：使用前2个最佳交易所
            selected_exchanges = sorted_exchanges[:2]
        else:
            # 低优先级：使用前3个交易所以获得更好的价格
            selected_exchanges = sorted_exchanges[:3]
        
        # 按分数比例分配数量
        total_score = sum(score for _, score in selected_exchanges)
        
        for i, (exchange, score) in enumerate(selected_exchanges):
            liquidity = liquidity_data[exchange]
            
            # 按分数比例分配
            allocation_ratio = score / total_score
            fragment_size = quantity * allocation_ratio
            
            # 检查流动性限制
            if side.lower() == 'buy':
                price = liquidity.ask_price
                max_size = liquidity.ask_size * 0.7
            else:
                price = liquidity.bid_price
                max_size = liquidity.bid_size * 0.7
            
            fragment_size = min(fragment_size, max_size)
            
            if fragment_size >= self.config['min_fragment_size']:
                fragment = OrderFragment(
                    fragment_id=str(uuid.uuid4()),
                    parent_order_id=order_id,
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    quantity=fragment_size,
                    price=price if order_type == 'limit' else None,
                    order_type=order_type,
                    estimated_cost=fragment_size * price,
                    estimated_slippage=self._calculate_estimated_slippage(liquidity, fragment_size, side),
                    priority=i + 1
                )
                
                fragments.append(fragment)
        
        return fragments
    
    async def _execute_order_fragment(
        self,
        fragment: OrderFragment,
        user_id: int,
        db: AsyncSession
    ) -> OrderExecutionResult:
        """执行订单片段"""
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"执行订单片段: {fragment.fragment_id} 在 {fragment.exchange}")
            
            # 通过交易所服务执行订单
            result = await exchange_service.place_order(
                user_id=user_id,
                exchange_name=fragment.exchange,
                symbol=fragment.symbol,
                order_type=fragment.order_type,
                side=fragment.side,
                amount=fragment.quantity,
                price=fragment.price,
                db=db,
                skip_risk_check=True  # 已在路由阶段进行风险检查
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            if result and result.get('success'):
                # 执行成功
                executed_price = float(result.get('price', fragment.price or 0))
                executed_quantity = float(result.get('filled', fragment.quantity))
                actual_cost = float(result.get('cost', executed_price * executed_quantity))
                
                # 计算实际滑点
                if fragment.order_type == 'market':
                    expected_price = fragment.estimated_cost / fragment.quantity
                    actual_slippage = abs(executed_price - expected_price) / expected_price
                else:
                    actual_slippage = 0.0
                
                return OrderExecutionResult(
                    fragment_id=fragment.fragment_id,
                    success=True,
                    executed_quantity=executed_quantity,
                    executed_price=executed_price,
                    actual_cost=actual_cost,
                    actual_slippage=actual_slippage,
                    execution_time=execution_time,
                    exchange_order_id=str(result.get('id', ''))
                )
            else:
                # 执行失败
                error_msg = result.get('error', '未知错误') if result else '无响应'
                return OrderExecutionResult(
                    fragment_id=fragment.fragment_id,
                    success=False,
                    execution_time=execution_time,
                    error_message=error_msg
                )
                
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(f"执行订单片段异常: {fragment.fragment_id}, 错误: {str(e)}")
            
            return OrderExecutionResult(
                fragment_id=fragment.fragment_id,
                success=False,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    # 辅助方法
    def _calculate_estimated_slippage(
        self,
        liquidity: MarketLiquidity,
        quantity: float,
        side: str
    ) -> float:
        """计算预估滑点"""
        try:
            if side.lower() == 'buy':
                depth = liquidity.depth_5_ask
                reference_price = liquidity.ask_price
            else:
                depth = liquidity.depth_5_bid  
                reference_price = liquidity.bid_price
            
            if depth <= 0:
                return 0.01  # 默认1%滑点
            
            # 简单的线性滑点模型
            impact_ratio = quantity / depth
            base_slippage = liquidity.spread / 2  # 基础滑点为点差的一半
            impact_slippage = impact_ratio * 0.005  # 市场影响滑点
            
            return min(base_slippage + impact_slippage, 0.02)  # 最大2%滑点
            
        except Exception:
            return 0.005  # 默认0.5%滑点
    
    def _calculate_confidence_score(
        self,
        fragments: List[OrderFragment],
        liquidity_data: Dict[str, MarketLiquidity],
        strategy: OrderRoutingStrategy
    ) -> float:
        """计算路由决策的置信度分数"""
        try:
            if not fragments:
                return 0.0
            
            # 基础分数
            base_score = 0.7
            
            # 流动性充足度加分
            total_available_liquidity = 0
            total_required_liquidity = sum(f.quantity for f in fragments)
            
            for fragment in fragments:
                if fragment.exchange in liquidity_data:
                    liquidity = liquidity_data[fragment.exchange]
                    if fragment.side.lower() == 'buy':
                        total_available_liquidity += liquidity.depth_5_ask
                    else:
                        total_available_liquidity += liquidity.depth_5_bid
            
            if total_available_liquidity > 0:
                liquidity_ratio = min(total_available_liquidity / total_required_liquidity, 2.0)
                liquidity_bonus = (liquidity_ratio - 1.0) * 0.1  # 流动性充足时加分
            else:
                liquidity_bonus = -0.2
            
            # 分散度加分
            diversification_bonus = min(len(fragments) / 3, 1.0) * 0.1
            
            # 交易所性能加分
            performance_bonus = 0.0
            for fragment in fragments:
                exchange_stats = self.exchange_stats.get(fragment.exchange, {})
                success_rate = exchange_stats.get('success_rate', 0.5)
                performance_bonus += (success_rate - 0.5) * 0.1
            
            performance_bonus /= len(fragments)
            
            final_score = base_score + liquidity_bonus + diversification_bonus + performance_bonus
            return min(max(final_score, 0.0), 1.0)
            
        except Exception:
            return 0.5  # 默认中等置信度
    
    async def _get_supported_exchanges_for_symbol(self, symbol: str) -> List[str]:
        """获取支持指定交易对的交易所列表"""
        try:
            # 这里应该从exchange_service获取实际支持的交易所列表
            # 暂时返回硬编码的列表
            all_exchanges = ["binance", "okx", "huobi", "bybit"]
            
            # 可以添加逻辑检查哪些交易所实际支持该交易对
            supported = []
            for exchange in all_exchanges:
                try:
                    # 尝试获取ticker来验证支持
                    ticker = await exchange_service.get_ticker(exchange, symbol)
                    if ticker:
                        supported.append(exchange)
                except:
                    continue
            
            return supported if supported else ["binance"]  # 至少返回一个交易所
            
        except Exception as e:
            self.logger.error(f"获取支持的交易所失败: {symbol}, 错误: {str(e)}")
            return ["binance"]  # 默认返回Binance
    
    async def _sort_exchanges_by_performance(self, exchanges: List[str]) -> List[str]:
        """按性能排序交易所"""
        try:
            exchange_performance = []
            
            for exchange in exchanges:
                stats = self.exchange_stats.get(exchange, {})
                score = (
                    stats.get('success_rate', 0.5) * 0.4 +
                    (1.0 / max(stats.get('avg_execution_time', 1.0), 0.1)) * 0.3 +
                    stats.get('uptime_ratio', 0.9) * 0.3
                )
                exchange_performance.append((exchange, score))
            
            # 按性能分数排序
            sorted_exchanges = sorted(exchange_performance, key=lambda x: x[1], reverse=True)
            return [exchange for exchange, _ in sorted_exchanges]
            
        except Exception:
            return list(exchanges)
    
    async def _perform_risk_assessment(
        self,
        user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        target_price: Optional[float],
        db: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """执行风险评估"""
        try:
            if db:
                # 使用风险管理器进行检查
                assessment = await risk_manager.assess_order_risk(
                    user_id, symbol, side, quantity, target_price, db
                )
                
                return {
                    'approved': assessment.approved,
                    'reason': assessment.violations[0] if assessment.violations else None,
                    'risk_score': assessment.risk_score
                }
            else:
                # 简化风险检查
                return {
                    'approved': True,
                    'reason': None,
                    'risk_score': 0.1
                }
                
        except Exception as e:
            self.logger.error(f"风险评估失败: {str(e)}")
            return {
                'approved': False,
                'reason': f"风险评估异常: {str(e)}",
                'risk_score': 1.0
            }
    
    def _generate_routing_reasoning(
        self,
        strategy: OrderRoutingStrategy,
        fragments: List[OrderFragment],
        liquidity_data: Dict[str, MarketLiquidity]
    ) -> str:
        """生成路由决策的理由说明"""
        try:
            reasoning = f"使用{strategy.value}策略，"
            
            if len(fragments) == 1:
                fragment = fragments[0]
                reasoning += f"单一路由到{fragment.exchange}，"
                reasoning += f"预估成本{fragment.estimated_cost:.4f}，"
                reasoning += f"预估滑点{fragment.estimated_slippage:.2%}"
            else:
                exchanges = [f.exchange for f in fragments]
                reasoning += f"分散到{len(fragments)}个交易所: {', '.join(set(exchanges))}，"
                
                total_cost = sum(f.estimated_cost for f in fragments)
                avg_slippage = sum(f.estimated_slippage for f in fragments) / len(fragments)
                reasoning += f"总预估成本{total_cost:.4f}，"
                reasoning += f"平均预估滑点{avg_slippage:.2%}"
            
            # 添加市场条件描述
            avg_spread = sum(l.spread for l in liquidity_data.values()) / len(liquidity_data)
            reasoning += f"，当前市场平均点差{avg_spread:.2%}"
            
            return reasoning
            
        except Exception:
            return f"使用{strategy.value}策略进行路由"
    
    async def _initialize_exchange_stats(self):
        """初始化交易所统计信息"""
        exchanges = ["binance", "okx", "huobi", "bybit"]
        
        for exchange in exchanges:
            self.exchange_stats[exchange] = {
                'success_rate': 0.95,      # 95%成功率
                'avg_execution_time': 1.5,  # 1.5秒平均执行时间
                'uptime_ratio': 0.999,      # 99.9%在线时间
                'total_orders': 0,
                'successful_orders': 0,
                'failed_orders': 0
            }
    
    async def _update_exchange_performance_stats(self, results: List[OrderExecutionResult]):
        """更新交易所性能统计"""
        try:
            # 按交易所分组结果
            exchange_results = {}
            for result in results:
                # 从fragment_id或其他方式获取交易所信息
                # 这里需要根据实际实现调整
                exchange = "unknown"  # TODO: 获取实际交易所名称
                
                if exchange not in exchange_results:
                    exchange_results[exchange] = []
                exchange_results[exchange].append(result)
            
            # 更新统计信息
            for exchange, exchange_result_list in exchange_results.items():
                if exchange in self.exchange_stats:
                    stats = self.exchange_stats[exchange]
                    
                    for result in exchange_result_list:
                        stats['total_orders'] += 1
                        
                        if result.success:
                            stats['successful_orders'] += 1
                        else:
                            stats['failed_orders'] += 1
                        
                        # 更新平均执行时间
                        if result.execution_time > 0:
                            current_avg = stats['avg_execution_time']
                            total_orders = stats['total_orders']
                            stats['avg_execution_time'] = (
                                (current_avg * (total_orders - 1) + result.execution_time) / total_orders
                            )
                    
                    # 更新成功率
                    if stats['total_orders'] > 0:
                        stats['success_rate'] = stats['successful_orders'] / stats['total_orders']
                        
        except Exception as e:
            self.logger.error(f"更新交易所性能统计失败: {str(e)}")
    
    async def _liquidity_monitoring_loop(self):
        """流动性监控循环"""
        try:
            self.logger.info("流动性监控循环开始")
            
            while self._running:
                try:
                    # 更新活跃交易对的流动性数据
                    active_symbols = list(self.liquidity_cache.keys())
                    
                    for symbol in active_symbols:
                        await self._gather_market_liquidity(symbol)
                    
                    await asyncio.sleep(self.config['liquidity_update_interval'])
                    
                except Exception as e:
                    self.logger.error(f"流动性监控异常: {str(e)}")
                    await asyncio.sleep(10)
                    
        except asyncio.CancelledError:
            self.logger.info("流动性监控循环被取消")
        except Exception as e:
            self.logger.error(f"流动性监控循环异常: {str(e)}")
    
    # 其他路由策略实现（简化版本）
    async def _route_by_iceberg_strategy(self, *args) -> List[OrderFragment]:
        """冰山策略路由（简化实现）"""
        return await self._route_by_minimal_impact(*args)
    
    async def _route_by_time_weighted_strategy(self, *args) -> List[OrderFragment]:
        """时间加权策略路由（简化实现）"""
        return await self._route_by_balanced_strategy(*args[:6], ExecutionUrgency.LOW)
    
    # 查询接口
    def get_liquidity_snapshot(self, symbol: str) -> Dict[str, Any]:
        """获取流动性快照"""
        return self.liquidity_cache.get(symbol, {})
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        total_decisions = len(self.routing_history)
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for r in self.execution_history if r.success)
        
        return {
            'total_routing_decisions': total_decisions,
            'total_order_executions': total_executions,
            'successful_execution_rate': successful_executions / total_executions if total_executions > 0 else 0,
            'exchange_stats': self.exchange_stats,
            'avg_fragments_per_decision': (
                sum(len(d.fragments) for d in self.routing_history.values()) / total_decisions
                if total_decisions > 0 else 0
            )
        }


# 全局智能订单路由器实例
smart_order_router = SmartOrderRouter()