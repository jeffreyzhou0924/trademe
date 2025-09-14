"""
无状态回测引擎 - 解决并发回测状态污染问题

这是架构改进的核心组件，使用无状态设计模式
每次回测创建独立的执行上下文，避免状态污染
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import asyncio
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.models.trade import Trade
from app.models.market_data import MarketData
from app.utils.data_validation import DataValidator


@dataclass
class BacktestConfig:
    """回测配置数据类"""
    strategy_id: int
    user_id: int
    start_date: datetime
    end_date: datetime
    initial_capital: float
    symbol: str = "BTC/USDT"
    exchange: str = "binance"
    timeframe: str = "1h"
    fee_rate: float = 0.001
    slippage: float = 0.001
    
    # AI策略相关配置
    ai_session_id: Optional[str] = None
    is_ai_generated: bool = False
    membership_level: str = "basic"
    
    # 确定性回测配置
    deterministic: bool = False
    random_seed: int = 42


@dataclass
class BacktestState:
    """回测状态数据类 - 封装所有回测状态"""
    current_position: float = 0.0
    cash_balance: float = 0.0
    total_value: float = 0.0
    trades: List[Dict] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    portfolio_history: List[Dict] = field(default_factory=list)
    drawdown_history: List[float] = field(default_factory=list)
    max_drawdown: float = 0.0
    peak_value: float = 0.0
    
    # 性能指标
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    
    # 时间追踪
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None


@dataclass
class BacktestResult:
    """回测结果数据类"""
    success: bool
    backtest_id: Optional[int] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    trades: List[Dict] = field(default_factory=list)
    portfolio_history: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0.0
    
    # AI增强结果
    ai_analysis: Optional[Dict] = None
    ai_score: Optional[float] = None
    optimization_suggestions: List[str] = field(default_factory=list)


class BacktestContext:
    """回测执行上下文 - 每次回测的独立执行环境"""
    
    def __init__(self, config: BacktestConfig, db: AsyncSession):
        self.config = config
        self.db = db
        self.state = BacktestState(
            cash_balance=config.initial_capital,
            total_value=config.initial_capital,
            peak_value=config.initial_capital
        )
        self.strategy_code: Optional[str] = None
        self.market_data: Optional[pd.DataFrame] = None
        
    async def execute(self) -> BacktestResult:
        """执行回测"""
        try:
            self.state.start_time = datetime.now()
            
            # 1. 加载策略
            await self._load_strategy()
            
            # 2. 获取市场数据
            await self._load_market_data()
            
            # 3. 执行回测逻辑
            await self._run_backtest_loop()
            
            # 4. 计算性能指标
            metrics = self._calculate_performance_metrics()
            
            # 5. 保存结果
            backtest_id = await self._save_results(metrics)
            
            self.state.end_time = datetime.now()
            execution_time = (self.state.end_time - self.state.start_time).total_seconds()
            
            return BacktestResult(
                success=True,
                backtest_id=backtest_id,
                performance_metrics=metrics,
                trades=self.state.trades,
                portfolio_history=self.state.portfolio_history,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"回测执行失败: {e}")
            return BacktestResult(
                success=False,
                error=str(e)
            )
    
    async def _load_strategy(self):
        """加载策略代码"""
        result = await self.db.execute(
            select(Strategy).where(
                Strategy.id == self.config.strategy_id,
                Strategy.user_id == self.config.user_id
            )
        )
        strategy = result.scalar_one_or_none()
        
        if not strategy:
            raise ValueError(f"策略 {self.config.strategy_id} 不存在")
        
        self.strategy_code = strategy.code
        logger.info(f"加载策略: {strategy.name}")
    
    async def _load_market_data(self):
        """加载市场数据"""
        # 构建查询
        query = select(MarketData).where(
            MarketData.symbol == self.config.symbol,
            MarketData.exchange == self.config.exchange,
            MarketData.timeframe == self.config.timeframe,
            MarketData.timestamp >= self.config.start_date,
            MarketData.timestamp <= self.config.end_date
        ).order_by(MarketData.timestamp)
        
        result = await self.db.execute(query)
        data = result.scalars().all()
        
        if not data:
            raise ValueError("没有找到历史数据")
        
        # 转换为DataFrame
        self.market_data = pd.DataFrame([
            {
                'timestamp': d.timestamp,
                'open': float(d.open),
                'high': float(d.high),
                'low': float(d.low),
                'close': float(d.close),
                'volume': float(d.volume)
            }
            for d in data
        ])
        
        logger.info(f"加载 {len(self.market_data)} 条市场数据")
    
    async def _run_backtest_loop(self):
        """执行回测主循环"""
        if self.market_data is None or self.market_data.empty:
            raise ValueError("市场数据未加载")
        
        # 创建策略执行环境
        strategy_env = self._create_strategy_environment()
        
        # 执行策略代码
        exec(self.strategy_code, strategy_env)
        
        # 获取策略实例
        strategy_class = strategy_env.get('Strategy')
        if not strategy_class:
            raise ValueError("策略代码中未找到Strategy类")
        
        strategy_instance = strategy_class()
        
        # 回测主循环
        for idx, row in self.market_data.iterrows():
            # 更新当前价格
            current_price = row['close']
            
            # 调用策略信号生成
            signal = strategy_instance.generate_signal(row)
            
            # 执行交易
            if signal == 'BUY' and self.state.current_position == 0:
                self._execute_buy(current_price, row['timestamp'])
            elif signal == 'SELL' and self.state.current_position > 0:
                self._execute_sell(current_price, row['timestamp'])
            
            # 更新组合价值
            self._update_portfolio_value(current_price, row['timestamp'])
    
    def _create_strategy_environment(self) -> Dict:
        """创建策略执行环境"""
        return {
            'pd': pd,
            'np': np,
            'talib': __import__('talib'),
            '__builtins__': __builtins__,
        }
    
    def _execute_buy(self, price: float, timestamp: datetime):
        """执行买入"""
        # 计算可买数量
        available_cash = self.state.cash_balance * (1 - self.config.fee_rate)
        position_size = available_cash / price
        
        # 更新状态
        self.state.current_position = position_size
        self.state.cash_balance = 0
        
        # 记录交易
        trade = {
            'timestamp': timestamp,
            'type': 'BUY',
            'price': price,
            'quantity': position_size,
            'fee': available_cash * self.config.fee_rate,
            'total': available_cash
        }
        self.state.trades.append(trade)
        self.state.total_trades += 1
        
        logger.debug(f"买入: {position_size:.8f} @ {price:.2f}")
    
    def _execute_sell(self, price: float, timestamp: datetime):
        """执行卖出"""
        # 计算卖出价值
        sell_value = self.state.current_position * price
        fee = sell_value * self.config.fee_rate
        net_value = sell_value - fee
        
        # 计算盈亏
        if len(self.state.trades) > 0:
            last_buy = next((t for t in reversed(self.state.trades) if t['type'] == 'BUY'), None)
            if last_buy:
                profit = net_value - last_buy['total']
                if profit > 0:
                    self.state.winning_trades += 1
                    self.state.total_profit += profit
                else:
                    self.state.losing_trades += 1
                    self.state.total_loss += abs(profit)
        
        # 更新状态
        self.state.cash_balance = net_value
        self.state.current_position = 0
        
        # 记录交易
        trade = {
            'timestamp': timestamp,
            'type': 'SELL',
            'price': price,
            'quantity': self.state.current_position,
            'fee': fee,
            'total': net_value
        }
        self.state.trades.append(trade)
        self.state.total_trades += 1
        
        logger.debug(f"卖出: {self.state.current_position:.8f} @ {price:.2f}")
    
    def _update_portfolio_value(self, current_price: float, timestamp: datetime):
        """更新组合价值"""
        # 计算总价值
        position_value = self.state.current_position * current_price
        self.state.total_value = self.state.cash_balance + position_value
        
        # 更新峰值
        if self.state.total_value > self.state.peak_value:
            self.state.peak_value = self.state.total_value
        
        # 计算回撤
        drawdown = (self.state.peak_value - self.state.total_value) / self.state.peak_value
        self.state.drawdown_history.append(drawdown)
        self.state.max_drawdown = max(self.state.max_drawdown, drawdown)
        
        # 记录组合历史
        self.state.portfolio_history.append({
            'timestamp': timestamp,
            'total_value': self.state.total_value,
            'cash': self.state.cash_balance,
            'position_value': position_value,
            'drawdown': drawdown
        })
        
        # 计算日收益率
        if len(self.state.portfolio_history) > 1:
            prev_value = self.state.portfolio_history[-2]['total_value']
            daily_return = (self.state.total_value - prev_value) / prev_value
            self.state.daily_returns.append(daily_return)
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """计算性能指标"""
        initial_capital = self.config.initial_capital
        final_value = self.state.total_value
        
        # 基础指标
        total_return = (final_value - initial_capital) / initial_capital
        
        # 风险调整指标
        if len(self.state.daily_returns) > 0:
            returns_array = np.array(self.state.daily_returns)
            sharpe_ratio = np.mean(returns_array) / (np.std(returns_array) + 1e-8) * np.sqrt(252)
            volatility = np.std(returns_array) * np.sqrt(252)
        else:
            sharpe_ratio = 0
            volatility = 0
        
        # 交易统计
        win_rate = self.state.winning_trades / max(self.state.total_trades, 1)
        avg_win = self.state.total_profit / max(self.state.winning_trades, 1)
        avg_loss = self.state.total_loss / max(self.state.losing_trades, 1)
        profit_factor = self.state.total_profit / max(self.state.total_loss, 1)
        
        return {
            'total_return': total_return,
            'final_capital': final_value,
            'max_drawdown': self.state.max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'volatility': volatility,
            'total_trades': self.state.total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'best_trade': max(self.state.trades, key=lambda x: x.get('profit', 0), default={}).get('profit', 0) if self.state.trades else 0,
            'worst_trade': min(self.state.trades, key=lambda x: x.get('profit', 0), default={}).get('profit', 0) if self.state.trades else 0,
        }
    
    async def _save_results(self, metrics: Dict[str, Any]) -> Optional[int]:
        """保存回测结果"""
        try:
            backtest = Backtest(
                strategy_id=self.config.strategy_id,
                user_id=self.config.user_id,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                initial_capital=Decimal(str(self.config.initial_capital)),
                final_capital=Decimal(str(metrics['final_capital'])),
                total_return=Decimal(str(metrics['total_return'])),
                max_drawdown=Decimal(str(metrics['max_drawdown'])),
                sharpe_ratio=Decimal(str(metrics['sharpe_ratio'])),
                results=DataValidator.safe_json_dumps(metrics),
                status="COMPLETED",
                ai_session_id=self.config.ai_session_id,
                is_ai_generated=self.config.is_ai_generated,
                membership_level=self.config.membership_level,
                completed_at=datetime.now()
            )
            
            self.db.add(backtest)
            await self.db.commit()
            await self.db.refresh(backtest)
            
            return backtest.id
            
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
            await self.db.rollback()
            return None


class StatelessBacktestEngine:
    """无状态回测引擎 - 主入口"""
    
    @staticmethod
    async def run_backtest(
        config: BacktestConfig,
        db: AsyncSession
    ) -> BacktestResult:
        """
        运行回测 - 完全无状态
        每次调用创建新的执行上下文
        """
        # 创建独立的执行上下文
        context = BacktestContext(config, db)
        
        # 执行回测
        result = await context.execute()
        
        # 上下文自动销毁，不保留任何状态
        return result
    
    @staticmethod
    async def run_parallel_backtests(
        configs: List[BacktestConfig],
        db: AsyncSession
    ) -> List[BacktestResult]:
        """
        并行运行多个回测
        每个回测完全独立，不会相互干扰
        """
        tasks = [
            StatelessBacktestEngine.run_backtest(config, db)
            for config in configs
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    BacktestResult(
                        success=False,
                        error=str(result)
                    )
                )
            else:
                processed_results.append(result)
        
        return processed_results


# 导出便捷函数
async def run_stateless_backtest(
    strategy_id: int,
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float,
    db: AsyncSession,
    **kwargs
) -> BacktestResult:
    """便捷函数 - 运行无状态回测"""
    config = BacktestConfig(
        strategy_id=strategy_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        **kwargs
    )
    
    return await StatelessBacktestEngine.run_backtest(config, db)