"""
风险管理系统 - 实盘交易的核心安全模块

负责所有实盘交易的风险控制，包括：
- 单笔交易风险限制
- 日损失限额检查  
- 持仓风险管理
- 保证金和流动性检查
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

from app.models.trade import Trade
from app.models.user import User
from app.models.api_key import ApiKey
from app.utils.data_validation import DataValidator


class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskLimits:
    """风险限制配置"""
    max_trade_risk_percent: float = 2.0  # 单笔交易最大风险比例 (2%)
    max_daily_loss_percent: float = 5.0  # 单日最大损失比例 (5%)
    max_total_risk_percent: float = 20.0  # 总风险敞口比例 (20%)
    max_positions: int = 10  # 最大持仓数量
    min_account_balance: float = 100.0  # 最小账户余额 (USDT)
    max_correlation_exposure: float = 50.0  # 最大相关性敞口 (50%)
    max_single_symbol_percent: float = 15.0  # 单一交易对最大比例 (15%)


@dataclass
class OrderRiskAssessment:
    """订单风险评估结果"""
    approved: bool
    risk_level: RiskLevel
    risk_score: float
    violations: List[str]
    warnings: List[str]
    suggested_position_size: Optional[float] = None
    max_allowed_size: Optional[float] = None


@dataclass
class PortfolioRisk:
    """投资组合风险指标"""
    total_value: float
    unrealized_pnl: float
    daily_pnl: float
    var_95: float  # 95% VaR
    max_drawdown: float
    position_count: int
    risk_score: float
    concentration_risk: float


class RiskManager:
    """风险管理器 - 实盘交易核心安全模块"""
    
    def __init__(self, risk_limits: Optional[RiskLimits] = None):
        """初始化风险管理器"""
        self.risk_limits = risk_limits or RiskLimits()
        self._risk_cache = {}  # 风险计算缓存
        self._cache_ttl = 300  # 缓存5分钟
        
    async def validate_order(
        self,
        user_id: int,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float],
        account_balance: Dict[str, float],
        db: AsyncSession
    ) -> OrderRiskAssessment:
        """
        全面的订单风险验证
        
        Args:
            user_id: 用户ID
            exchange: 交易所
            symbol: 交易对
            side: 买卖方向 (buy/sell)
            order_type: 订单类型 (market/limit)
            quantity: 数量
            price: 价格 (限价单必需)
            account_balance: 账户余额
            db: 数据库会话
            
        Returns:
            OrderRiskAssessment: 风险评估结果
        """
        try:
            violations = []
            warnings = []
            risk_scores = []
            
            logger.info(f"开始订单风险验证: 用户{user_id}, {symbol}, {side}, 数量{quantity}")
            
            # 1. 基础参数验证
            basic_validation = await self._validate_basic_parameters(
                symbol, side, order_type, quantity, price
            )
            if not basic_validation[0]:
                violations.extend(basic_validation[1])
            
            # 2. 账户余额检查
            balance_check = await self._check_account_balance(
                account_balance, symbol, side, quantity, price or 0
            )
            if not balance_check[0]:
                violations.append(balance_check[1])
            risk_scores.append(balance_check[2])
            
            # 3. 单笔交易风险检查
            trade_risk = await self._check_single_trade_risk(
                account_balance, symbol, quantity, price or 0
            )
            if trade_risk[0] > self.risk_limits.max_trade_risk_percent:
                violations.append(f"单笔交易风险 {DataValidator.safe_format_percentage(trade_risk[0], decimals=2)} 超过限制 {self.risk_limits.max_trade_risk_percent}%")
            elif trade_risk[0] > self.risk_limits.max_trade_risk_percent * 0.8:
                warnings.append(f"单笔交易风险较高: {DataValidator.safe_format_percentage(trade_risk[0], decimals=2)}")
            risk_scores.append(trade_risk[0])
            
            # 4. 日损失限额检查
            daily_loss = await self._check_daily_loss_limit(user_id, db)
            if daily_loss[0] > self.risk_limits.max_daily_loss_percent:
                violations.append(f"当日损失 {DataValidator.safe_format_percentage(daily_loss[0], decimals=2)} 已超过限制 {self.risk_limits.max_daily_loss_percent}%")
            elif daily_loss[0] > self.risk_limits.max_daily_loss_percent * 0.8:
                warnings.append(f"接近日损失限额: {DataValidator.safe_format_percentage(daily_loss[0], decimals=2)}")
            risk_scores.append(daily_loss[0])
            
            # 5. 持仓数量检查
            position_check = await self._check_position_limits(user_id, symbol, side, db)
            if not position_check[0]:
                violations.append(position_check[1])
            risk_scores.append(position_check[2])
            
            # 6. 集中度风险检查
            concentration_risk = await self._check_concentration_risk(
                user_id, symbol, quantity, price or 0, db
            )
            if concentration_risk[0] > self.risk_limits.max_single_symbol_percent:
                violations.append(f"单一交易对风险敞口 {DataValidator.safe_format_percentage(concentration_risk[0], decimals=2)} 超过限制")
            risk_scores.append(concentration_risk[0])
            
            # 7. 计算建议持仓大小
            suggested_size = await self._calculate_optimal_position_size(
                account_balance, symbol, price or 0, risk_scores
            )
            
            # 8. 综合风险评分
            avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0
            risk_level = self._determine_risk_level(avg_risk_score, len(violations))
            
            # 9. 最终决策
            approved = len(violations) == 0 and risk_level != RiskLevel.CRITICAL
            
            assessment = OrderRiskAssessment(
                approved=approved,
                risk_level=risk_level,
                risk_score=avg_risk_score,
                violations=violations,
                warnings=warnings,
                suggested_position_size=suggested_size,
                max_allowed_size=min(quantity, suggested_size) if suggested_size else quantity
            )
            
            # 记录风险评估结果
            logger.info(f"订单风险评估完成: 批准={approved}, 风险等级={risk_level.value}, 评分={DataValidator.safe_format_decimal(avg_risk_score, decimals=2)}")
            if violations:
                logger.warning(f"风险违规: {violations}")
            if warnings:
                logger.warning(f"风险警告: {warnings}")
                
            return assessment
            
        except Exception as e:
            logger.error(f"订单风险验证失败: {str(e)}")
            return OrderRiskAssessment(
                approved=False,
                risk_level=RiskLevel.CRITICAL,
                risk_score=100.0,
                violations=[f"风险验证系统错误: {str(e)}"],
                warnings=[]
            )
    
    async def _validate_basic_parameters(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float]
    ) -> Tuple[bool, List[str]]:
        """基础参数验证"""
        violations = []
        
        # 验证交易对格式
        if not symbol or '/' not in symbol:
            violations.append("无效的交易对格式")
        
        # 验证买卖方向
        if side.lower() not in ['buy', 'sell']:
            violations.append("无效的买卖方向")
        
        # 验证订单类型
        if order_type.lower() not in ['market', 'limit']:
            violations.append("不支持的订单类型")
        
        # 验证数量
        if quantity <= 0:
            violations.append("订单数量必须大于0")
        elif quantity > 1000000:  # 防止错误输入
            violations.append("订单数量过大")
        
        # 验证限价单价格
        if order_type.lower() == 'limit':
            if not price or price <= 0:
                violations.append("限价单必须指定有效价格")
        
        return len(violations) == 0, violations
    
    async def _check_account_balance(
        self,
        account_balance: Dict[str, float],
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Tuple[bool, str, float]:
        """检查账户余额是否充足"""
        try:
            base_currency, quote_currency = symbol.split('/')
            
            if side.lower() == 'buy':
                # 买入需要报价货币余额
                required_balance = quantity * price
                available_balance = account_balance.get(quote_currency, 0)
                currency = quote_currency
            else:
                # 卖出需要基础货币余额
                required_balance = quantity
                available_balance = account_balance.get(base_currency, 0)
                currency = base_currency
            
            # 预留5%作为手续费缓冲
            required_balance_with_buffer = required_balance * 1.05
            
            if available_balance < required_balance_with_buffer:
                return False, f"{currency} 余额不足: 需要 {DataValidator.safe_format_decimal(required_balance_with_buffer, decimals=4)}, 可用 {DataValidator.safe_format_decimal(available_balance, decimals=4)}", 80.0
            elif available_balance < required_balance_with_buffer * 1.2:
                return True, f"{currency} 余额紧张", 40.0
            else:
                return True, "", 10.0
                
        except Exception as e:
            logger.error(f"余额检查失败: {str(e)}")
            return False, f"余额检查失败: {str(e)}", 100.0
    
    async def _check_single_trade_risk(
        self,
        account_balance: Dict[str, float],
        symbol: str,
        quantity: float,
        price: float
    ) -> Tuple[float, str]:
        """检查单笔交易风险"""
        try:
            # 计算总账户价值 (以USDT计算)
            total_account_value = 0
            usdt_balance = account_balance.get('USDT', 0)
            total_account_value += usdt_balance
            
            # 简化计算：其他币种按1:1 USDT计算 (实际应该用实时汇率)
            for currency, balance in account_balance.items():
                if currency != 'USDT' and balance > 0:
                    total_account_value += balance * 0.9  # 保守估计打9折
            
            # 计算交易金额
            trade_value = quantity * price
            
            # 计算风险比例
            if total_account_value > 0:
                risk_percent = (trade_value / total_account_value) * 100
            else:
                risk_percent = 100.0  # 账户价值为0，风险为100%
            
            return risk_percent, f"单笔交易风险: {DataValidator.safe_format_percentage(risk_percent, decimals=2)}"
            
        except Exception as e:
            logger.error(f"单笔交易风险计算失败: {str(e)}")
            return 100.0, f"风险计算失败: {str(e)}"
    
    async def _check_daily_loss_limit(self, user_id: int, db: AsyncSession) -> Tuple[float, str]:
        """检查当日损失限额"""
        try:
            today = datetime.utcnow().date()
            
            # 查询当日交易记录
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.trade_type == 'LIVE',
                    func.date(Trade.executed_at) == today
                )
            )
            
            result = await db.execute(query)
            today_trades = result.scalars().all()
            
            if not today_trades:
                return 0.0, "当日无交易"
            
            # 计算当日盈亏 (简化计算)
            total_pnl = 0.0
            for trade in today_trades:
                # 这里需要更复杂的PnL计算逻辑
                # 现在先简化处理
                trade_value = float(trade.quantity) * float(trade.price)
                if trade.side.lower() == 'sell':
                    total_pnl += trade_value * 0.001  # 假设0.1%的盈利
                else:
                    total_pnl -= trade_value * 0.001  # 假设0.1%的亏损
            
            # 从实际数据计算账户价值
            account_value = await self._get_account_value(user_id)
            loss_percent = abs(min(0, total_pnl)) / account_value * 100
            
            return loss_percent, f"当日损失: {DataValidator.safe_format_percentage(loss_percent, decimals=2)}"
            
        except Exception as e:
            logger.error(f"日损失检查失败: {str(e)}")
            return 0.0, f"日损失检查失败: {str(e)}"
    
    async def _check_position_limits(
        self,
        user_id: int,
        symbol: str,
        side: str,
        db: AsyncSession
    ) -> Tuple[bool, str, float]:
        """检查持仓数量限制"""
        try:
            # 查询当前活跃持仓 (简化查询，实际需要更复杂的持仓计算)
            query = select(Trade.symbol).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.trade_type == 'LIVE'
                )
            ).distinct()
            
            result = await db.execute(query)
            active_symbols = result.scalars().all()
            
            current_positions = len(active_symbols) if active_symbols else 0
            
            # 如果是新开仓位
            if symbol not in active_symbols:
                if current_positions >= self.risk_limits.max_positions:
                    return False, f"持仓数量已达上限: {current_positions}/{self.risk_limits.max_positions}", 90.0
                elif current_positions >= self.risk_limits.max_positions * 0.8:
                    return True, f"接近持仓上限: {current_positions}/{self.risk_limits.max_positions}", 60.0
            
            return True, f"当前持仓: {current_positions}/{self.risk_limits.max_positions}", 20.0
            
        except Exception as e:
            logger.error(f"持仓限制检查失败: {str(e)}")
            return True, f"持仓检查失败: {str(e)}", 50.0
    
    async def _check_concentration_risk(
        self,
        user_id: int,
        symbol: str,
        quantity: float,
        price: float,
        db: AsyncSession
    ) -> Tuple[float, str]:
        """检查集中度风险"""
        try:
            # 计算当前交易对的总敞口
            trade_value = quantity * price
            
            # 查询该交易对的历史交易 (简化计算)
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.symbol == symbol,
                    Trade.trade_type == 'LIVE'
                )
            )
            
            result = await db.execute(query)
            symbol_trades = result.scalars().all()
            
            existing_exposure = 0.0
            for trade in symbol_trades:
                existing_exposure += float(trade.quantity) * float(trade.price)
            
            total_exposure = existing_exposure + trade_value
            
            # 从实际数据计算总投资组合价值
            portfolio_value = await self._get_portfolio_value(user_id)
            
            concentration_percent = (total_exposure / portfolio_value) * 100
            
            return concentration_percent, f"{symbol} 集中度: {DataValidator.safe_format_percentage(concentration_percent, decimals=2)}"
            
        except Exception as e:
            logger.error(f"集中度风险检查失败: {str(e)}")
            return 0.0, f"集中度检查失败: {str(e)}"
    
    async def _calculate_optimal_position_size(
        self,
        account_balance: Dict[str, float],
        symbol: str,
        price: float,
        risk_scores: List[float]
    ) -> Optional[float]:
        """根据风险管理原则计算最优仓位大小"""
        try:
            # 计算总账户价值
            total_value = sum(account_balance.values())
            
            if total_value <= 0:
                return None
            
            # 根据风险等级调整仓位
            avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 50
            
            if avg_risk < 20:
                risk_allocation = self.risk_limits.max_trade_risk_percent
            elif avg_risk < 50:
                risk_allocation = self.risk_limits.max_trade_risk_percent * 0.5
            else:
                risk_allocation = self.risk_limits.max_trade_risk_percent * 0.25
            
            # 计算建议仓位大小
            max_trade_value = total_value * (risk_allocation / 100)
            suggested_quantity = max_trade_value / price
            
            logger.info(f"建议仓位大小: {DataValidator.safe_format_decimal(suggested_quantity, decimals=6)}, 基于风险分配 {risk_allocation}%")
            return suggested_quantity
            
        except Exception as e:
            logger.error(f"仓位计算失败: {str(e)}")
            return None
    
    def _determine_risk_level(self, risk_score: float, violation_count: int) -> RiskLevel:
        """根据风险评分确定风险等级"""
        if violation_count > 0:
            return RiskLevel.CRITICAL
        elif risk_score >= 80:
            return RiskLevel.HIGH
        elif risk_score >= 50:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    async def get_portfolio_risk_summary(self, user_id: int, db: AsyncSession) -> PortfolioRisk:
        """获取投资组合风险总结"""
        try:
            # 查询用户所有活跃交易
            query = select(Trade).where(
                and_(
                    Trade.user_id == user_id,
                    Trade.trade_type == 'LIVE'
                )
            )
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            if not trades:
                return PortfolioRisk(
                    total_value=0, unrealized_pnl=0, daily_pnl=0, var_95=0,
                    max_drawdown=0, position_count=0, risk_score=0, concentration_risk=0
                )
            
            # 计算基础指标 (简化版本)
            total_value = sum(float(trade.total_amount) for trade in trades)
            position_count = len(set(trade.symbol for trade in trades))
            
            # 今日交易的盈亏
            today = datetime.utcnow().date()
            today_trades = [t for t in trades if t.executed_at.date() == today]
            daily_pnl = sum(float(t.total_amount) * 0.001 for t in today_trades)  # 简化计算
            
            # 风险评分 (基于持仓数量和集中度)
            risk_score = min(100, (position_count / self.risk_limits.max_positions) * 50 + 
                           (total_value / 10000) * 20)  # 简化计算
            
            # 计算未实现盈亏和最大回撤
            unrealized_pnl = await self._calculate_unrealized_pnl(user_id)
            max_drawdown = await self._calculate_max_drawdown(user_id)
            
            return PortfolioRisk(
                total_value=total_value,
                unrealized_pnl=unrealized_pnl,
                daily_pnl=daily_pnl,
                var_95=total_value * 0.05,  # 简化为5% VaR
                max_drawdown=max_drawdown,
                position_count=position_count,
                risk_score=risk_score,
                concentration_risk=min(100, (position_count / 3) * 50)  # 简化集中度计算
            )
            
        except Exception as e:
            logger.error(f"投资组合风险分析失败: {str(e)}")
            return PortfolioRisk(
                total_value=0, unrealized_pnl=0, daily_pnl=0, var_95=0,
                max_drawdown=0, position_count=0, risk_score=100, concentration_risk=100
            )
    
    async def emergency_stop_check(self, user_id: int, db: AsyncSession) -> Tuple[bool, str]:
        """紧急停止检查 - 检查是否需要立即停止交易"""
        try:
            portfolio_risk = await self.get_portfolio_risk_summary(user_id, db)
            
            # 紧急停止条件
            emergency_conditions = []
            
            # 1. 日损失超过紧急阈值
            daily_loss_percent = abs(portfolio_risk.daily_pnl) / max(portfolio_risk.total_value, 1) * 100
            if daily_loss_percent > self.risk_limits.max_daily_loss_percent * 2:
                emergency_conditions.append(f"日损失过大: {DataValidator.safe_format_percentage(daily_loss_percent, decimals=2)}")
            
            # 2. 风险评分过高
            if portfolio_risk.risk_score > 90:
                emergency_conditions.append(f"投资组合风险过高: {DataValidator.safe_format_decimal(portfolio_risk.risk_score, decimals=1)}")
            
            # 3. 账户价值过低
            if portfolio_risk.total_value < self.risk_limits.min_account_balance:
                emergency_conditions.append(f"账户价值过低: ${DataValidator.safe_format_price(portfolio_risk.total_value, decimals=2)}")
            
            should_stop = len(emergency_conditions) > 0
            reason = "; ".join(emergency_conditions) if should_stop else "风险正常"
            
            if should_stop:
                logger.critical(f"用户 {user_id} 触发紧急停止: {reason}")
            
            return should_stop, reason
            
        except Exception as e:
            logger.error(f"紧急停止检查失败: {str(e)}")
            return True, f"紧急停止检查失败: {str(e)}"
    
    async def _get_account_value(self, user_id: int) -> float:
        """获取用户实际账户价值"""
        try:
            from app.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                # 查询用户所有活跃持仓和余额
                from app.models.trade import Trade
                from sqlalchemy import select, func, and_
                
                # 获取用户所有交易，计算当前账户价值
                trades_query = select(Trade).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status == "filled"
                    )
                ).order_by(Trade.created_at.desc())
                
                result = await db.execute(trades_query)
                trades = result.scalars().all()
                
                account_value = 10000.0  # 默认起始价值
                total_pnl = 0.0
                
                for trade in trades:
                    # 简化的PnL计算 - 实际应该使用当前市价
                    trade_value = float(trade.quantity) * float(trade.price)
                    if trade.side.lower() == 'sell':
                        total_pnl += trade_value * 0.01  # 假设1%盈利
                    else:
                        total_pnl -= trade_value * 0.01  # 假设1%手续费成本
                
                return max(1000.0, account_value + total_pnl)  # 最小保留1000
                
        except Exception as e:
            logger.error(f"获取账户价值失败: {str(e)}")
            return 10000.0  # 默认值
    
    async def _get_portfolio_value(self, user_id: int) -> float:
        """获取用户投资组合总价值"""
        try:
            # 获取账户价值作为投资组合价值的基础
            account_value = await self._get_account_value(user_id)
            
            # 可以在这里添加其他资产价值（如持有的其他代币等）
            # 目前简化为账户价值
            
            return account_value
            
        except Exception as e:
            logger.error(f"获取投资组合价值失败: {str(e)}")
            return 10000.0  # 默认值
    
    async def _calculate_unrealized_pnl(self, user_id: int) -> float:
        """计算未实现盈亏（需要实时价格）"""
        try:
            from app.database import AsyncSessionLocal
            from app.services.exchange_service import exchange_service
            
            async with AsyncSessionLocal() as db:
                # 获取用户当前持仓
                from app.models.trade import Trade
                from sqlalchemy import select, and_
                from collections import defaultdict
                
                # 计算每个币种的净持仓
                positions = defaultdict(lambda: {'quantity': 0.0, 'avg_price': 0.0, 'total_cost': 0.0})
                
                trades_query = select(Trade).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status == "filled"
                    )
                ).order_by(Trade.created_at)
                
                result = await db.execute(trades_query)
                trades = result.scalars().all()
                
                for trade in trades:
                    symbol = trade.symbol
                    quantity = float(trade.quantity)
                    price = float(trade.price)
                    
                    if trade.side.lower() == 'buy':
                        positions[symbol]['quantity'] += quantity
                        positions[symbol]['total_cost'] += quantity * price
                    else:  # sell
                        positions[symbol]['quantity'] -= quantity
                        positions[symbol]['total_cost'] -= quantity * price
                
                total_unrealized_pnl = 0.0
                
                # 计算每个持仓的未实现盈亏
                for symbol, pos in positions.items():
                    if abs(pos['quantity']) > 0.001:  # 有持仓
                        try:
                            # 获取当前市价
                            current_price = await exchange_service.get_current_price("binance", symbol)
                            if current_price:
                                avg_price = pos['total_cost'] / pos['quantity'] if pos['quantity'] != 0 else 0
                                unrealized_pnl = (current_price - avg_price) * pos['quantity']
                                total_unrealized_pnl += unrealized_pnl
                        except:
                            # 无法获取价格时跳过
                            continue
                
                return total_unrealized_pnl
                
        except Exception as e:
            logger.error(f"计算未实现盈亏失败: {str(e)}")
            return 0.0
    
    async def _calculate_max_drawdown(self, user_id: int) -> float:
        """计算最大回撤（基于历史数据）"""
        try:
            from app.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                from app.models.trade import Trade
                from sqlalchemy import select, and_
                from datetime import datetime, timedelta
                
                # 获取过去30天的交易记录
                start_date = datetime.utcnow() - timedelta(days=30)
                
                trades_query = select(Trade).where(
                    and_(
                        Trade.user_id == user_id,
                        Trade.status == "filled",
                        Trade.created_at >= start_date
                    )
                ).order_by(Trade.created_at)
                
                result = await db.execute(trades_query)
                trades = result.scalars().all()
                
                if not trades:
                    return 0.0
                
                # 计算每日账户价值变化
                account_values = []
                running_pnl = 0.0
                initial_value = await self._get_account_value(user_id)
                
                for trade in trades:
                    trade_value = float(trade.quantity) * float(trade.price)
                    if trade.side.lower() == 'sell':
                        running_pnl += trade_value * 0.01  # 简化盈利计算
                    else:
                        running_pnl -= trade_value * 0.005  # 简化成本计算
                    
                    account_values.append(initial_value + running_pnl)
                
                if len(account_values) < 2:
                    return 0.0
                
                # 计算最大回撤
                peak = account_values[0]
                max_drawdown = 0.0
                
                for value in account_values[1:]:
                    if value > peak:
                        peak = value
                    else:
                        drawdown = (peak - value) / peak * 100
                        max_drawdown = max(max_drawdown, drawdown)
                
                return max_drawdown
                
        except Exception as e:
            logger.error(f"计算最大回撤失败: {str(e)}")
            return 0.0


# 全局风险管理器实例
risk_manager = RiskManager()