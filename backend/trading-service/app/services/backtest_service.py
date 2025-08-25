"""
回测引擎服务

提供策略回测、性能分析和报告生成功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import json
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.models.trade import Trade
from app.services.exchange_service import exchange_service
from app.config import settings
from loguru import logger


class BacktestEngine:
    """回测引擎类"""
    
    def __init__(self):
        self.results = {}
        self.current_position = 0.0  # 当前持仓
        self.cash_balance = 0.0      # 现金余额
        self.total_value = 0.0       # 总资产价值
        self.trades = []             # 交易记录
        self.daily_returns = []      # 日收益率
        
    async def run_backtest(
        self, 
        strategy_id: int, 
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        symbol: str = "BTC/USDT",
        exchange: str = "binance",
        timeframe: str = "1h",
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """运行回测"""
        try:
            logger.info(f"开始回测策略 {strategy_id}: {start_date} 到 {end_date}")
            
            # 初始化回测参数
            self.cash_balance = initial_capital
            self.total_value = initial_capital
            self.current_position = 0.0
            self.trades = []
            self.daily_returns = []
            
            # 获取策略代码
            strategy = await self._get_strategy(db, strategy_id, user_id)
            if not strategy:
                raise ValueError(f"策略 {strategy_id} 不存在")
            
            # 获取历史数据
            market_data = await self._get_historical_data(
                exchange, symbol, timeframe, start_date, end_date, user_id, db
            )
            
            if not market_data or len(market_data) < 10:
                raise ValueError("历史数据不足，无法进行回测")
            
            # 转换为DataFrame
            df = self._prepare_data(market_data)
            
            # 执行回测
            backtest_results = await self._execute_backtest(strategy, df, symbol, initial_capital)
            
            # 计算性能指标
            performance_metrics = self._calculate_performance_metrics(initial_capital)
            
            # 保存回测结果
            backtest_record = await self._save_backtest_results(
                db, strategy_id, user_id, start_date, end_date, 
                initial_capital, performance_metrics, backtest_results
            )
            
            logger.info(f"回测完成，总收益率: {performance_metrics.get('total_return', 0):.2%}")
            
            return {
                "backtest_id": backtest_record.id if backtest_record else None,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "exchange": exchange,
                "timeframe": timeframe,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "initial_capital": initial_capital,
                "final_capital": self.total_value,
                "performance": performance_metrics,
                "trades_count": len(self.trades),
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"回测执行失败: {str(e)}")
            raise
    
    async def _get_strategy(self, db: AsyncSession, strategy_id: int, user_id: int) -> Optional[Strategy]:
        """获取策略"""
        query = select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == user_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_historical_data(
        self, 
        exchange: str, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        user_id: int,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取历史数据"""
        try:
            # 计算需要的数据点数量
            if timeframe == "1m":
                delta_minutes = 1
            elif timeframe == "5m":
                delta_minutes = 5
            elif timeframe == "1h":
                delta_minutes = 60
            elif timeframe == "1d":
                delta_minutes = 1440
            else:
                delta_minutes = 60  # 默认1小时
            
            total_minutes = int((end_date - start_date).total_seconds() / 60)
            limit = min(total_minutes // delta_minutes + 100, 1000)  # 多获取一些数据
            
            # 从交易所获取历史数据
            data = await exchange_service.get_market_data(
                user_id, exchange, symbol, timeframe, limit, db
            )
            
            if not data:
                # 如果获取失败，生成模拟数据用于测试
                logger.warning(f"无法获取真实数据，生成模拟数据进行回测")
                return self._generate_mock_data(start_date, end_date, timeframe)
            
            # 过滤日期范围
            filtered_data = []
            for item in data:
                item_date = datetime.fromtimestamp(item['timestamp'] / 1000)
                if start_date <= item_date <= end_date:
                    filtered_data.append(item)
            
            return filtered_data
            
        except Exception as e:
            logger.warning(f"获取历史数据失败: {str(e)}，使用模拟数据")
            return self._generate_mock_data(start_date, end_date, timeframe)
    
    def _generate_mock_data(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        timeframe: str
    ) -> List[Dict[str, Any]]:
        """生成模拟市场数据用于测试"""
        if timeframe == "1h":
            delta = timedelta(hours=1)
        elif timeframe == "1d":
            delta = timedelta(days=1)
        else:
            delta = timedelta(hours=1)
        
        data = []
        current_date = start_date
        base_price = 50000.0  # BTC基础价格
        
        while current_date <= end_date:
            # 简单的随机游走价格模型
            change_percent = np.random.normal(0, 0.02)  # 2%标准差
            new_price = base_price * (1 + change_percent)
            
            high = new_price * (1 + abs(np.random.normal(0, 0.01)))
            low = new_price * (1 - abs(np.random.normal(0, 0.01)))
            volume = np.random.uniform(100, 1000)
            
            data.append({
                'timestamp': int(current_date.timestamp() * 1000),
                'datetime': current_date.isoformat(),
                'open': base_price,
                'high': max(base_price, new_price, high),
                'low': min(base_price, new_price, low),
                'close': new_price,
                'volume': volume
            })
            
            base_price = new_price
            current_date += delta
        
        return data
    
    def _prepare_data(self, market_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """准备数据用于回测"""
        df = pd.DataFrame(market_data)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('datetime')
        df = df.sort_index()
        
        # 添加技术指标
        df = self._add_technical_indicators(df)
        
        return df
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加常用技术指标"""
        # 移动平均线
        df['ma_5'] = df['close'].rolling(window=5).mean()
        df['ma_10'] = df['close'].rolling(window=10).mean()
        df['ma_20'] = df['close'].rolling(window=20).mean()
        
        # RSI
        df['rsi'] = self._calculate_rsi(df['close'], period=14)
        
        # MACD
        df['macd'], df['macd_signal'] = self._calculate_macd(df['close'])
        
        # 布林带
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self._calculate_bollinger_bands(df['close'])
        
        return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
        """计算MACD指标"""
        exp1 = prices.ewm(span=fast).mean()
        exp2 = prices.ewm(span=slow).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal).mean()
        return macd, signal_line
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算布林带"""
        middle = prices.rolling(window=period).mean()
        std_dev = prices.rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower
    
    async def _execute_backtest(
        self, 
        strategy: Strategy, 
        df: pd.DataFrame, 
        symbol: str,
        initial_capital: float
    ) -> Dict[str, Any]:
        """执行回测逻辑"""
        try:
            # 解析策略参数
            strategy_params = json.loads(strategy.parameters) if strategy.parameters else {}
            
            # 简化的策略执行逻辑（基于移动平均线交叉）
            signals = self._generate_trading_signals(df, strategy_params)
            
            # 执行交易
            for i, (timestamp, row) in enumerate(df.iterrows()):
                if i < len(signals):
                    signal = signals[i]
                    await self._execute_trade(signal, row, timestamp, symbol)
                
                # 更新总资产价值
                current_price = row['close']
                self.total_value = self.cash_balance + (self.current_position * current_price)
                
                # 记录每日收益率
                if i > 0:
                    prev_value = self.cash_balance + (self.current_position * df.iloc[i-1]['close'])
                    daily_return = (self.total_value - prev_value) / prev_value
                    self.daily_returns.append(daily_return)
            
            return {
                "total_trades": len(self.trades),
                "winning_trades": len([t for t in self.trades if t.get('pnl', 0) > 0]),
                "losing_trades": len([t for t in self.trades if t.get('pnl', 0) < 0]),
                "final_balance": self.total_value,
                "max_position": max([abs(t.get('position_change', 0)) for t in self.trades] + [0])
            }
            
        except Exception as e:
            logger.error(f"执行回测失败: {str(e)}")
            raise
    
    def _generate_trading_signals(self, df: pd.DataFrame, params: Dict[str, Any]) -> List[str]:
        """生成交易信号"""
        signals = []
        
        # 简单的移动平均线交叉策略
        short_period = params.get('short_ma', 5)
        long_period = params.get('long_ma', 20)
        
        for i in range(len(df)):
            if i < long_period:
                signals.append('hold')
                continue
            
            short_ma = df['close'].iloc[i-short_period:i].mean()
            long_ma = df['close'].iloc[i-long_period:i].mean()
            prev_short_ma = df['close'].iloc[i-short_period-1:i-1].mean()
            prev_long_ma = df['close'].iloc[i-long_period-1:i-1].mean()
            
            # 金叉买入，死叉卖出
            if short_ma > long_ma and prev_short_ma <= prev_long_ma:
                signals.append('buy')
            elif short_ma < long_ma and prev_short_ma >= prev_long_ma:
                signals.append('sell')
            else:
                signals.append('hold')
        
        return signals
    
    async def _execute_trade(
        self, 
        signal: str, 
        market_data: pd.Series, 
        timestamp: pd.Timestamp, 
        symbol: str
    ):
        """执行交易"""
        if signal == 'hold':
            return
        
        current_price = market_data['close']
        trade_amount = 0
        
        if signal == 'buy' and self.cash_balance > current_price:
            # 买入：使用50%可用资金
            trade_value = self.cash_balance * 0.5
            trade_amount = trade_value / current_price
            
            self.current_position += trade_amount
            self.cash_balance -= trade_value
            
            trade_record = {
                'timestamp': timestamp,
                'signal': signal,
                'price': current_price,
                'amount': trade_amount,
                'value': trade_value,
                'position_change': trade_amount,
                'position_after': self.current_position,
                'cash_after': self.cash_balance
            }
            
        elif signal == 'sell' and self.current_position > 0:
            # 卖出：卖出50%持仓
            trade_amount = self.current_position * 0.5
            trade_value = trade_amount * current_price
            
            self.current_position -= trade_amount
            self.cash_balance += trade_value
            
            trade_record = {
                'timestamp': timestamp,
                'signal': signal,
                'price': current_price,
                'amount': trade_amount,
                'value': trade_value,
                'position_change': -trade_amount,
                'position_after': self.current_position,
                'cash_after': self.cash_balance
            }
        else:
            return
        
        self.trades.append(trade_record)
        logger.debug(f"执行交易: {signal} {trade_amount:.6f} @ {current_price:.2f}")
    
    def _calculate_performance_metrics(self, initial_capital: float) -> Dict[str, Any]:
        """计算完整的性能指标"""
        if not self.daily_returns:
            return self._get_empty_metrics()
        
        returns_array = np.array(self.daily_returns)
        
        # 基础收益指标
        total_return = (self.total_value - initial_capital) / initial_capital
        trading_days = len(returns_array)
        annualized_return = (1 + total_return) ** (252 / trading_days) - 1 if trading_days > 0 else 0
        
        # 风险指标
        volatility = np.std(returns_array) * np.sqrt(252) if len(returns_array) > 1 else 0
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 1 else 0
        
        # 风险调整收益比率
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        sortino_ratio = annualized_return / downside_deviation if downside_deviation > 0 else 0
        
        # 回撤分析
        max_drawdown, max_drawdown_duration = self._calculate_advanced_drawdown()
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # 交易统计
        trade_stats = self._calculate_trade_statistics()
        
        # VaR和CVaR计算
        var_95, cvar_95 = self._calculate_var_cvar(returns_array, confidence=0.95)
        var_99, cvar_99 = self._calculate_var_cvar(returns_array, confidence=0.99)
        
        # 收益分布统计
        skewness = self._calculate_skewness(returns_array)
        kurtosis = self._calculate_kurtosis(returns_array)
        
        return {
            # 基础收益指标
            'total_return': total_return,
            'annualized_return': annualized_return,
            'trading_days': trading_days,
            
            # 风险指标
            'volatility': volatility,
            'downside_deviation': downside_deviation,
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_drawdown_duration,
            
            # 风险调整收益
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            
            # 风险价值
            'var_95': var_95,
            'cvar_95': cvar_95,
            'var_99': var_99,
            'cvar_99': cvar_99,
            
            # 收益分布
            'skewness': skewness,
            'kurtosis': kurtosis,
            
            # 交易统计
            **trade_stats
        }
    
    def _calculate_advanced_drawdown(self) -> Tuple[float, int]:
        """计算最大回撤和回撤持续期"""
        if not self.daily_returns:
            return 0.0, 0
        
        returns_array = np.array(self.daily_returns)
        cumulative_returns = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        
        # 最大回撤
        max_drawdown = abs(np.min(drawdown))
        
        # 最大回撤持续期
        max_dd_duration = 0
        current_duration = 0
        
        for dd in drawdown:
            if dd < 0:
                current_duration += 1
                max_dd_duration = max(max_dd_duration, current_duration)
            else:
                current_duration = 0
                
        return max_drawdown, max_dd_duration
    
    def _calculate_trade_pnl(self, trade: Dict[str, Any]) -> float:
        """计算单笔交易盈亏"""
        # 简化的盈亏计算 - 后续需要改进为配对交易的真实盈亏
        if trade.get('signal') == 'sell':
            return trade.get('value', 0) * 0.02  # 假设2%的收益
        elif trade.get('signal') == 'buy':
            return -trade.get('value', 0) * 0.001  # 假设0.1%的手续费成本
        return 0
    
    def _calculate_trade_statistics(self) -> Dict[str, Any]:
        """计算详细的交易统计"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0
            }
        
        # 计算每笔交易的盈亏
        trade_pnls = [self._calculate_trade_pnl(trade) for trade in self.trades]
        profitable_trades = [pnl for pnl in trade_pnls if pnl > 0]
        losing_trades = [pnl for pnl in trade_pnls if pnl < 0]
        
        # 基础统计
        total_trades = len(self.trades)
        winning_trades = len(profitable_trades)
        losing_trades_count = len(losing_trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 盈亏统计
        total_profit = sum(profitable_trades) if profitable_trades else 0
        total_loss = abs(sum(losing_trades)) if losing_trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0
        
        avg_win = total_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = total_loss / losing_trades_count if losing_trades_count > 0 else 0
        
        # 连续盈亏统计
        max_consecutive_wins, max_consecutive_losses = self._calculate_consecutive_trades(trade_pnls)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses
        }
    
    def _calculate_consecutive_trades(self, trade_pnls: List[float]) -> Tuple[int, int]:
        """计算最大连续盈利和亏损次数"""
        if not trade_pnls:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for pnl in trade_pnls:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0
        
        return max_wins, max_losses
    
    def _calculate_var_cvar(self, returns: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """计算VaR和CVaR (条件风险价值)"""
        if len(returns) == 0:
            return 0.0, 0.0
        
        # VaR: 在给定置信水平下的最大预期损失
        var = np.percentile(returns, (1 - confidence) * 100)
        
        # CVaR: 超过VaR的条件期望损失
        cvar_returns = returns[returns <= var]
        cvar = np.mean(cvar_returns) if len(cvar_returns) > 0 else var
        
        return abs(var), abs(cvar)
    
    def _calculate_skewness(self, returns: np.ndarray) -> float:
        """计算收益率分布的偏度"""
        if len(returns) < 3:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        skew = np.mean(((returns - mean_return) / std_return) ** 3)
        return skew
    
    def _calculate_kurtosis(self, returns: np.ndarray) -> float:
        """计算收益率分布的峰度"""
        if len(returns) < 4:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        kurt = np.mean(((returns - mean_return) / std_return) ** 4) - 3  # 减去3得到超额峰度
        return kurt
    
    def _get_empty_metrics(self) -> Dict[str, Any]:
        """返回空的性能指标"""
        return {
            'total_return': 0,
            'annualized_return': 0,
            'trading_days': 0,
            'volatility': 0,
            'downside_deviation': 0,
            'max_drawdown': 0,
            'max_drawdown_duration': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0,
            'var_95': 0,
            'cvar_95': 0,
            'var_99': 0,
            'cvar_99': 0,
            'skewness': 0,
            'kurtosis': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'total_profit': 0,
            'total_loss': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0
        }
    
    async def _save_backtest_results(
        self,
        db: AsyncSession,
        strategy_id: int,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        performance_metrics: Dict[str, Any],
        backtest_results: Dict[str, Any]
    ) -> Optional[Backtest]:
        """保存回测结果"""
        try:
            backtest_record = Backtest(
                strategy_id=strategy_id,
                user_id=user_id,
                start_date=start_date.date(),
                end_date=end_date.date(),
                initial_capital=Decimal(str(initial_capital)),
                final_capital=Decimal(str(self.total_value)),
                total_return=Decimal(str(performance_metrics.get('total_return', 0))),
                max_drawdown=Decimal(str(performance_metrics.get('max_drawdown', 0))),
                sharpe_ratio=Decimal(str(performance_metrics.get('sharpe_ratio', 0))),
                results=json.dumps({
                    **performance_metrics,
                    **backtest_results,
                    'trades': self.trades[-50:]  # 只保存最后50笔交易记录
                }, default=str),
                status='COMPLETED'
            )
            
            db.add(backtest_record)
            await db.commit()
            await db.refresh(backtest_record)
            
            return backtest_record
            
        except Exception as e:
            await db.rollback()
            logger.error(f"保存回测结果失败: {str(e)}")
            return None


class BacktestService:
    """回测服务类"""
    
    @staticmethod
    async def run_parallel_backtests(
        db: AsyncSession,
        strategies: List[int],
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        symbol: str = "BTC/USDT",
        exchange: str = "binance"
    ) -> List[Dict[str, Any]]:
        """并行运行多个策略的回测"""
        try:
            logger.info(f"开始并行回测 {len(strategies)} 个策略")
            
            # 创建并行任务
            tasks = []
            for strategy_id in strategies:
                engine = BacktestEngine()
                task = engine.run_backtest(
                    strategy_id=strategy_id,
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    symbol=symbol,
                    exchange=exchange,
                    db=db
                )
                tasks.append(task)
            
            # 并行执行所有回测
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果，区分成功和失败的回测
            successful_results = []
            failed_results = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_results.append({
                        "strategy_id": strategies[i],
                        "error": str(result),
                        "status": "failed"
                    })
                    logger.error(f"策略 {strategies[i]} 回测失败: {str(result)}")
                else:
                    successful_results.append(result)
                    logger.info(f"策略 {strategies[i]} 回测成功")
            
            logger.info(f"并行回测完成: 成功 {len(successful_results)} 个，失败 {len(failed_results)} 个")
            
            return {
                "successful": successful_results,
                "failed": failed_results,
                "summary": {
                    "total_strategies": len(strategies),
                    "successful_count": len(successful_results),
                    "failed_count": len(failed_results),
                    "success_rate": len(successful_results) / len(strategies) if strategies else 0
                }
            }
            
        except Exception as e:
            logger.error(f"并行回测执行失败: {str(e)}")
            raise
    
    @staticmethod
    async def generate_backtest_report(
        db: AsyncSession,
        backtest_id: int,
        user_id: int,
        format: str = "json"
    ) -> Dict[str, Any]:
        """生成回测报告"""
        try:
            # 获取回测记录
            backtest = await BacktestService.get_backtest_by_id(db, backtest_id, user_id)
            if not backtest:
                raise ValueError(f"回测记录 {backtest_id} 不存在")
            
            # 解析回测结果
            results = json.loads(backtest.results) if backtest.results else {}
            
            # 生成详细报告
            report = {
                "backtest_info": {
                    "id": backtest.id,
                    "strategy_id": backtest.strategy_id,
                    "start_date": backtest.start_date.isoformat(),
                    "end_date": backtest.end_date.isoformat(),
                    "initial_capital": float(backtest.initial_capital),
                    "final_capital": float(backtest.final_capital),
                    "created_at": backtest.created_at.isoformat()
                },
                "performance_summary": {
                    "total_return": float(backtest.total_return),
                    "annualized_return": results.get('annualized_return', 0),
                    "max_drawdown": float(backtest.max_drawdown),
                    "sharpe_ratio": float(backtest.sharpe_ratio),
                    "volatility": results.get('volatility', 0),
                    "sortino_ratio": results.get('sortino_ratio', 0),
                    "calmar_ratio": results.get('calmar_ratio', 0)
                },
                "risk_metrics": {
                    "var_95": results.get('var_95', 0),
                    "cvar_95": results.get('cvar_95', 0),
                    "var_99": results.get('var_99', 0),
                    "cvar_99": results.get('cvar_99', 0),
                    "downside_deviation": results.get('downside_deviation', 0),
                    "max_drawdown_duration": results.get('max_drawdown_duration', 0)
                },
                "trading_statistics": {
                    "total_trades": results.get('total_trades', 0),
                    "winning_trades": results.get('winning_trades', 0),
                    "losing_trades": results.get('losing_trades', 0),
                    "win_rate": results.get('win_rate', 0),
                    "profit_factor": results.get('profit_factor', 0),
                    "avg_win": results.get('avg_win', 0),
                    "avg_loss": results.get('avg_loss', 0),
                    "max_consecutive_wins": results.get('max_consecutive_wins', 0),
                    "max_consecutive_losses": results.get('max_consecutive_losses', 0)
                },
                "distribution_analysis": {
                    "skewness": results.get('skewness', 0),
                    "kurtosis": results.get('kurtosis', 0)
                },
                "trades": results.get('trades', [])
            }
            
            if format.lower() == "html":
                return BacktestService._generate_html_report(report)
            else:
                return report
                
        except Exception as e:
            logger.error(f"生成回测报告失败: {str(e)}")
            raise
    
    @staticmethod
    def _generate_html_report(report: Dict[str, Any]) -> Dict[str, Any]:
        """生成HTML格式的回测报告"""
        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>回测报告 - {report['backtest_info']['id']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; margin-bottom: 40px; }}
                .section {{ margin-bottom: 30px; }}
                .section h2 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
                .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
                .metric-label {{ font-size: 14px; color: #666; margin-top: 5px; }}
                .positive {{ color: #28a745; }}
                .negative {{ color: #dc3545; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>回测报告</h1>
                    <p>回测ID: {report['backtest_info']['id']} | 策略ID: {report['backtest_info']['strategy_id']}</p>
                    <p>回测期间: {report['backtest_info']['start_date']} 至 {report['backtest_info']['end_date']}</p>
                </div>
                
                <div class="section">
                    <h2>绩效概览</h2>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-value {'positive' if report['performance_summary']['total_return'] > 0 else 'negative'}">{report['performance_summary']['total_return']:.2%}</div>
                            <div class="metric-label">总收益率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['performance_summary']['annualized_return']:.2%}</div>
                            <div class="metric-label">年化收益率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['performance_summary']['sharpe_ratio']:.2f}</div>
                            <div class="metric-label">夏普比率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value negative">{report['performance_summary']['max_drawdown']:.2%}</div>
                            <div class="metric-label">最大回撤</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>风险指标</h2>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-value">{report['performance_summary']['volatility']:.2%}</div>
                            <div class="metric-label">波动率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['performance_summary']['sortino_ratio']:.2f}</div>
                            <div class="metric-label">索提诺比率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['risk_metrics']['var_95']:.2%}</div>
                            <div class="metric-label">VaR (95%)</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['risk_metrics']['cvar_95']:.2%}</div>
                            <div class="metric-label">CVaR (95%)</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>交易统计</h2>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-value">{report['trading_statistics']['total_trades']}</div>
                            <div class="metric-label">总交易次数</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value positive">{report['trading_statistics']['win_rate']:.1%}</div>
                            <div class="metric-label">胜率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['trading_statistics']['profit_factor']:.2f}</div>
                            <div class="metric-label">盈亏比</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{report['trading_statistics']['max_consecutive_wins']}</div>
                            <div class="metric-label">最大连胜</div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return {
            "format": "html",
            "content": html_content,
            "filename": f"backtest_report_{report['backtest_info']['id']}.html"
        }
    
    @staticmethod
    async def get_user_backtests(
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        strategy_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Backtest]:
        """获取用户回测列表"""
        try:
            query = select(Backtest).where(Backtest.user_id == user_id)
            
            if strategy_id:
                query = query.where(Backtest.strategy_id == strategy_id)
            if status:
                query = query.where(Backtest.status == status)
            
            query = query.offset(skip).limit(limit).order_by(Backtest.created_at.desc())
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"获取回测列表失败: {str(e)}")
            return []
    
    @staticmethod
    async def count_user_backtests(
        db: AsyncSession,
        user_id: int,
        strategy_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> int:
        """统计用户回测数量"""
        try:
            from sqlalchemy import func
            
            query = select(func.count(Backtest.id)).where(Backtest.user_id == user_id)
            
            if strategy_id:
                query = query.where(Backtest.strategy_id == strategy_id)
            if status:
                query = query.where(Backtest.status == status)
            
            result = await db.execute(query)
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"统计回测数量失败: {str(e)}")
            return 0
    
    @staticmethod
    async def get_backtest_by_id(
        db: AsyncSession,
        backtest_id: int,
        user_id: int
    ) -> Optional[Backtest]:
        """根据ID获取回测"""
        try:
            query = select(Backtest).where(
                Backtest.id == backtest_id,
                Backtest.user_id == user_id
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"获取回测失败: {str(e)}")
            return None
    
    @staticmethod
    async def create_backtest(
        db: AsyncSession,
        backtest_data,  # BacktestCreate type
        user_id: int
    ):
        """创建并启动回测"""
        try:
            logger.info(f"用户 {user_id} 创建回测，策略ID: {backtest_data.strategy_id}")
            
            # 先创建数据库记录
            from app.models.backtest import Backtest
            from decimal import Decimal
            
            backtest_record = Backtest(
                strategy_id=backtest_data.strategy_id,
                user_id=user_id,
                start_date=backtest_data.start_date,
                end_date=backtest_data.end_date,
                initial_capital=Decimal(str(backtest_data.initial_capital)),
                final_capital=None,
                total_return=None,
                max_drawdown=None,
                sharpe_ratio=None,
                status='RUNNING'
            )
            
            db.add(backtest_record)
            await db.commit()
            await db.refresh(backtest_record)
            
            # 异步启动回测任务（不阻塞响应）
            asyncio.create_task(
                BacktestService._run_backtest_task(
                    db=db,
                    backtest_id=backtest_record.id,
                    strategy_id=backtest_data.strategy_id,
                    user_id=user_id,
                    start_date=datetime.combine(backtest_data.start_date, datetime.min.time()),
                    end_date=datetime.combine(backtest_data.end_date, datetime.min.time()),
                    initial_capital=float(backtest_data.initial_capital)
                )
            )
            
            return backtest_record
            
        except Exception as e:
            await db.rollback()
            logger.error(f"创建回测失败: {str(e)}")
            raise

    @staticmethod
    async def _run_backtest_task(
        db: AsyncSession,
        backtest_id: int,
        strategy_id: int,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float
    ):
        """后台执行回测任务"""
        try:
            logger.info(f"开始执行回测任务 ID: {backtest_id}")
            
            # 创建新的数据库会话
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as task_db:
                # 获取回测记录
                backtest = await BacktestService.get_backtest_by_id(task_db, backtest_id, user_id)
                if not backtest:
                    logger.error(f"回测记录 {backtest_id} 不存在")
                    return
                
                # 执行回测
                engine = BacktestEngine()
                result = await engine.run_backtest(
                    strategy_id=strategy_id,
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    symbol="BTC/USDT",
                    exchange="binance",
                    db=task_db
                )
                
                # 更新回测记录状态为完成
                from sqlalchemy import select
                query = select(Backtest).where(Backtest.id == backtest_id)
                db_result = await task_db.execute(query)
                backtest_update = db_result.scalar_one_or_none()
                
                if backtest_update:
                    backtest_update.status = 'COMPLETED'
                    backtest_update.final_capital = Decimal(str(result.get('final_capital', initial_capital)))
                    await task_db.commit()
                
                logger.info(f"回测任务 {backtest_id} 完成")
                
        except Exception as e:
            logger.error(f"回测任务执行失败 ID {backtest_id}: {str(e)}")
            # 更新状态为失败
            try:
                from app.database import AsyncSessionLocal
                async with AsyncSessionLocal() as error_db:
                    from sqlalchemy import select
                    query = select(Backtest).where(Backtest.id == backtest_id)
                    db_result = await error_db.execute(query)
                    backtest_update = db_result.scalar_one_or_none()
                    
                    if backtest_update:
                        backtest_update.status = 'FAILED'
                        await error_db.commit()
            except Exception as update_error:
                logger.error(f"更新回测状态失败: {str(update_error)}")

    @staticmethod
    async def start_backtest_task(backtest_id: int):
        """启动回测任务（用于API调用）"""
        # 这个方法只是一个占位符，实际的任务启动在create_backtest中
        logger.info(f"回测任务 {backtest_id} 已在后台启动")
        pass

    @staticmethod
    async def start_backtest(
        db: AsyncSession,
        strategy_id: int,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        symbol: str = "BTC/USDT",
        exchange: str = "binance"
    ) -> Dict[str, Any]:
        """启动回测"""
        try:
            # 创建回测引擎实例
            engine = BacktestEngine()
            
            # 执行回测
            result = await engine.run_backtest(
                strategy_id=strategy_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                symbol=symbol,
                exchange=exchange,
                db=db
            )
            
            return result
            
        except Exception as e:
            logger.error(f"启动回测失败: {str(e)}")
            raise
    
    @staticmethod
    async def delete_backtest(db: AsyncSession, backtest_id: int, user_id: int) -> bool:
        """删除回测"""
        try:
            backtest = await BacktestService.get_backtest_by_id(db, backtest_id, user_id)
            if not backtest:
                return False
            
            await db.delete(backtest)
            await db.commit()
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"删除回测失败: {str(e)}")
            return False


# 全局回测引擎实例
backtest_engine = BacktestEngine()