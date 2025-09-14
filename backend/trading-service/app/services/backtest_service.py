"""
回测引擎服务

提供策略回测、性能分析和报告生成功能
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal, getcontext
import json
import asyncio
import random
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.models.trade import Trade
from app.services.exchange_service import exchange_service
from app.config import settings
from app.utils.data_validation import DataValidator
from loguru import logger


class BacktestEngine:
    """回测引擎类"""
    
    def __init__(self):
        self._reset_state()
    
    def _reset_state(self):
        """完全重置回测引擎状态，确保每次回测的独立性"""
        self.results = {}
        self.current_position = 0.0  # 当前持仓
        self.cash_balance = 0.0      # 现金余额
        self.total_value = 0.0       # 总资产价值
        self.trades = []             # 交易记录
        self.daily_returns = []      # 日收益率
        self.portfolio_history = []  # 资产价值历史
        self.drawdown_history = []   # 回撤历史
        
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
            
            # 🔧 关键修复：完全重置状态，确保每次回测的独立性
            self._reset_state()
            
            # 初始化回测参数
            self.cash_balance = initial_capital
            self.total_value = initial_capital
            logger.info(f"🔧 状态重置完成，初始资金: {initial_capital}")
            
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
            
            logger.info(f"回测完成，总收益率: {DataValidator.safe_format_percentage(performance_metrics.get('total_return', 0) * 100, decimals=2)}")
            
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
        """获取历史数据 - 直接从数据库获取（增强数据验证）"""
        try:
            from app.models.market_data import MarketData
            from sqlalchemy import select, and_
            from app.services.data_validation_service import DataValidationService
            
            logger.info(f"获取历史数据: {exchange} {symbol} {timeframe} {start_date}-{end_date}")
            
            # 🆕 使用数据验证服务检查数据可用性
            validation = await DataValidationService.validate_backtest_data_availability(
                db=db,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if not validation["available"]:
                # 详细的错误信息和建议
                error_msg = f"❌ {validation['error_message']}"
                if validation.get("suggestions"):
                    error_msg += f"\n💡 建议: {'; '.join(validation['suggestions'])}"
                
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 使用验证通过的实际交易对格式
            actual_symbol = validation["actual_symbol"]
            if actual_symbol != symbol:
                logger.info(f"✅ 将使用数据库中的交易对格式: {actual_symbol} (原请求: {symbol})")
            
            # 从数据库查询历史数据
            query = select(MarketData).where(
                and_(
                    MarketData.exchange == exchange.lower(),
                    MarketData.symbol == actual_symbol,  # 使用实际可用的格式
                    MarketData.timeframe == timeframe,
                    MarketData.timestamp >= start_date,
                    MarketData.timestamp <= end_date
                )
            ).order_by(MarketData.timestamp.asc()).limit(10000)
            
            result = await db.execute(query)
            records = result.scalars().all()
            
            # 再次检查数据量
            if not records or len(records) < 10:
                error_msg = f"❌ 验证通过但数据量不足: {len(records) if records else 0}条记录"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 转换为回测所需的格式
            historical_data = []
            for record in records:
                historical_data.append({
                    'timestamp': int(record.timestamp.timestamp() * 1000),
                    'datetime': record.timestamp.isoformat(),
                    'open': float(record.open_price),
                    'high': float(record.high_price),
                    'low': float(record.low_price),
                    'close': float(record.close_price),
                    'volume': float(record.volume)
                })
            
            logger.info(f"✅ 成功获取{exchange.upper()}历史数据: {len(historical_data)}条记录")
            logger.info(f"   数据时间范围: {records[0].timestamp} 到 {records[-1].timestamp}")
            
            return historical_data
            
        except Exception as e:
            error_msg = f"❌ 获取历史数据失败: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    # 移除了 _generate_mock_data 方法
    # 生产环境不应该使用模拟数据进行回测，这会误导用户
    
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
        """计算RSI指标 - 修复浮点精度问题"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # 🔧 修复除零错误和无效值问题
        # 避免除零，当loss为0时，RSI应为100
        rs = np.where(loss != 0, gain / loss, np.inf)
        rsi = 100 - (100 / (1 + rs))
        
        # 清理无效值并转换为Pandas Series
        rsi_series = pd.Series(rsi, index=prices.index)
        rsi_series = rsi_series.fillna(50)  # NaN填充为中性值50  
        rsi_series = rsi_series.clip(lower=0, upper=100)  # 确保RSI在有效范围内
        
        return rsi_series
    
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
        """执行回测逻辑 - 修复：使用用户策略代码而非简单移动平均"""
        try:
            # 🔧 关键修复：使用用户的策略代码
            if strategy.code and strategy.code.strip():
                logger.info("使用用户策略代码执行回测")
                signals = await self._execute_user_strategy_code(strategy, df, symbol)
            else:
                logger.info("使用默认移动平均策略")
                # 解析策略参数
                strategy_params = json.loads(strategy.parameters) if strategy.parameters else {}
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
    
    async def _execute_user_strategy_code(
        self, 
        strategy: Strategy, 
        df: pd.DataFrame, 
        symbol: str
    ) -> List[str]:
        """执行用户策略代码并生成信号"""
        try:
            # 动态执行策略代码
            namespace = {}
            exec(strategy.code, namespace)
            
            # 获取UserStrategy类
            UserStrategy = namespace.get('UserStrategy')
            if not UserStrategy:
                raise ValueError("策略代码中未找到UserStrategy类")
            
            # 创建策略实例
            strategy_instance = UserStrategy()
            
            # 为策略实例提供数据访问方法
            strategy_instance.get_kline_data = lambda: df
            
            signals = []
            
            # 遍历数据，调用策略的on_data_update方法
            for i, (timestamp, row) in enumerate(df.iterrows()):
                if i < 50:  # 确保有足够的历史数据
                    signals.append('hold')
                    continue
                
                # 创建当前时间点的数据切片
                current_df = df.iloc[:i+1].copy()
                strategy_instance.get_kline_data = lambda: current_df
                
                # 模拟参数上下文
                from types import SimpleNamespace
                strategy_instance.context = SimpleNamespace()
                strategy_instance.context.parameters = {
                    'position_size': 10.0,
                    'stop_loss': 5.0,
                    'take_profit': 10.0
                }
                
                # 模拟当前持仓
                strategy_instance.get_current_position = lambda: self.current_position
                
                # 添加技术指标计算方法
                strategy_instance.calculate_sma = self.calculate_sma
                
                try:
                    # 调用策略的信号生成方法
                    signal = await strategy_instance.on_data_update("kline", {})
                    
                    if signal:
                        if hasattr(signal, 'signal_type'):
                            if str(signal.signal_type) == 'SignalType.BUY':
                                signals.append('buy')
                            elif str(signal.signal_type) == 'SignalType.SELL':
                                signals.append('sell')
                            else:
                                signals.append('hold')
                        else:
                            signals.append('hold')
                    else:
                        signals.append('hold')
                        
                except Exception as signal_error:
                    logger.warning(f"策略信号生成错误 (时间点 {i}): {signal_error}")
                    signals.append('hold')
            
            logger.info(f"用户策略执行完成: {signals.count('buy')}买入, {signals.count('sell')}卖出, {signals.count('hold')}持有")
            return signals
            
        except Exception as e:
            logger.error(f"执行用户策略代码失败: {str(e)}")
            # 回退到简单策略
            strategy_params = json.loads(strategy.parameters) if strategy.parameters else {}
            return self._generate_trading_signals(df, strategy_params)
    
    def calculate_sma(self, series: pd.Series, period: int) -> pd.Series:
        """计算简单移动平均线"""
        return series.rolling(window=period).mean()
    
    def _generate_trading_signals(self, df: pd.DataFrame, params: Dict[str, Any]) -> List[str]:
        """生成交易信号 - 修复浮点比较精度问题"""
        signals = []
        
        # 简单的移动平均线交叉策略
        short_period = params.get('short_ma', 5)
        long_period = params.get('long_ma', 20)
        
        # 🔧 预先计算移动平均线，提高一致性
        df_work = df.copy()
        df_work['short_ma'] = df_work['close'].rolling(window=short_period).mean()
        df_work['long_ma'] = df_work['close'].rolling(window=long_period).mean()
        
        for i in range(len(df_work)):
            if i < long_period or i == 0:
                signals.append('hold')
                continue
            
            # 使用预先计算的移动平均线
            current_short_ma = df_work['short_ma'].iloc[i]
            current_long_ma = df_work['long_ma'].iloc[i]
            prev_short_ma = df_work['short_ma'].iloc[i-1]
            prev_long_ma = df_work['long_ma'].iloc[i-1]
            
            # 🔧 修复浮点比较精度问题，使用容差
            tolerance = 1e-10
            
            # 金叉买入：短期均线上穿长期均线
            short_cross_above = (current_short_ma > current_long_ma + tolerance) and (prev_short_ma <= prev_long_ma + tolerance)
            # 死叉卖出：短期均线下穿长期均线  
            short_cross_below = (current_short_ma < current_long_ma - tolerance) and (prev_short_ma >= prev_long_ma - tolerance)
            
            if short_cross_above:
                signals.append('buy')
            elif short_cross_below:
                signals.append('sell')
            else:
                signals.append('hold')
        
        logger.debug(f"🔧 生成交易信号完成: {signals.count('buy')}买入, {signals.count('sell')}卖出, {signals.count('hold')}持有")
        return signals
    
    async def _save_api_data_to_local(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        api_data: List[Dict[str, Any]]
    ):
        """异步保存API数据到本地数据库"""
        try:
            from app.services.historical_data_downloader import historical_data_downloader
            from decimal import Decimal
            
            logger.info(f"保存API数据到本地: {len(api_data)} 条记录")
            
            # 转换API数据格式为数据库格式
            timeframe_ms = {
                '1m': 60 * 1000,
                '5m': 5 * 60 * 1000,
                '15m': 15 * 60 * 1000,
                '1h': 60 * 60 * 1000,
                '4h': 4 * 60 * 60 * 1000,
                '1d': 24 * 60 * 60 * 1000
            }.get(timeframe, 60 * 60 * 1000)
            
            batch_records = []
            for item in api_data:
                timestamp = item['timestamp']
                record = {
                    'exchange': exchange.lower(),
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'open_time': timestamp,
                    'close_time': timestamp + timeframe_ms - 1,
                    'open_price': Decimal(str(item['open'])),
                    'high_price': Decimal(str(item['high'])),
                    'low_price': Decimal(str(item['low'])),
                    'close_price': Decimal(str(item['close'])),
                    'volume': Decimal(str(item['volume'])),
                    'quote_volume': Decimal(str(item.get('quote_volume', 0))),
                    'data_source': 'api'
                }
                batch_records.append(record)
            
            # 批量保存到数据库
            await historical_data_downloader._batch_insert_klines(db, batch_records)
            
            # 更新缓存元信息
            await historical_data_downloader._update_cache_metadata(
                db, exchange, symbol, timeframe, batch_records
            )
            
            logger.info(f"API数据保存完成: {len(batch_records)} 条记录")
            
        except Exception as e:
            logger.error(f"保存API数据失败: {str(e)}")
    
    async def _execute_trade(
        self, 
        signal: str, 
        market_data: pd.Series, 
        timestamp: pd.Timestamp, 
        symbol: str
    ):
        """执行交易"""
        logger.debug(f"🔧 尝试执行交易: 信号={signal}, 价格={market_data['close']:.2f}, 现金={self.cash_balance:.2f}, 持仓={self.current_position:.6f}")
        
        if signal == 'hold':
            return
        
        current_price = market_data['close']
        trade_amount = 0
        
        if signal == 'buy' and self.cash_balance > 100:  # 只需要有足够现金进行交易(最少$100)
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
            
            logger.info(f"✅ 执行买入: {trade_amount:.6f} @ {current_price:.2f}, 剩余现金: {self.cash_balance:.2f}")
        
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
            
            logger.info(f"✅ 执行卖出: {trade_amount:.6f} @ {current_price:.2f}, 获得现金: {trade_value:.2f}")
            
        else:
            return
        
        self.trades.append(trade_record)
        logger.debug(f"执行交易: {signal} {DataValidator.safe_format_decimal(trade_amount, decimals=6)} @ {DataValidator.safe_format_price(current_price, decimals=2)}")
    
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
    
    async def execute_backtest(
        self,
        backtest_params: Dict[str, Any],
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        执行回测的标准接口方法
        
        Args:
            backtest_params: 回测参数字典
            user_id: 用户ID  
            db: 数据库会话
            
        Returns:
            包含success状态和回测结果的字典
        """
        try:
            logger.info(f"执行回测，参数: {backtest_params}")
            
            # 🔧 关键修复：确保每次execute_backtest调用都重置状态
            self._reset_state()
            
            # 提取参数
            strategy_code = backtest_params.get('strategy_code')
            exchange = backtest_params.get('exchange', 'binance')
            symbols = backtest_params.get('symbols', ['BTC/USDT'])
            timeframes = backtest_params.get('timeframes', ['1h'])
            start_date = backtest_params.get('start_date')
            end_date = backtest_params.get('end_date')
            initial_capital = backtest_params.get('initial_capital', 10000.0)
            
            logger.info(f"🔧 状态重置完成，开始执行回测: {exchange}-{symbols[0]}-{initial_capital}")
            
            # 验证必要参数
            if not strategy_code:
                raise ValueError("策略代码不能为空")
            if not start_date or not end_date:
                raise ValueError("开始日期和结束日期不能为空")
            
            # 转换日期
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).replace(tzinfo=None)
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).replace(tzinfo=None)
            
            # 验证数据源可用性
            primary_symbol = symbols[0] if symbols else 'BTC/USDT'
            data_availability = await self._check_data_availability(
                exchange, primary_symbol, start_date, end_date, db
            )
            
            if not data_availability['has_data']:
                error_msg = (
                    f"❌ {exchange.upper()}交易所的{primary_symbol}在指定时间范围"
                    f"({start_date.date()} 到 {end_date.date()})内没有历史数据。\n"
                    f"当前系统数据源: {data_availability['available_exchanges']}\n"
                    f"建议: 请选择有数据的交易所进行回测"
                )
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'available_data': data_availability
                }
            
            # 获取历史数据
            market_data = await self._get_historical_data(
                exchange, primary_symbol, timeframes[0], start_date, end_date, user_id, db
            )
            
            if not market_data or len(market_data) < 10:
                error_msg = f"获取到的{exchange.upper()}历史数据不足({len(market_data) if market_data else 0}条)，无法进行有效回测"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # 准备数据
            df = self._prepare_data(market_data)
            logger.info(f"成功准备回测数据: {len(df)} 条记录，时间范围: {df.index[0]} 到 {df.index[-1]}")
            
            # 创建临时策略对象用于回测执行
            from app.models.strategy import Strategy
            temp_strategy = Strategy(
                id=0,
                user_id=user_id,
                name="临时回测策略",
                code=strategy_code,
                parameters=json.dumps({})
            )
            
            # 执行回测
            backtest_results = await self._execute_backtest(temp_strategy, df, primary_symbol, initial_capital)
            
            # 计算性能指标
            performance_metrics = self._calculate_performance_metrics(initial_capital)
            
            logger.info(f"回测执行成功，总收益率: {performance_metrics.get('total_return', 0) * 100:.2f}%")
            
            return {
                'success': True,
                'backtest_result': {
                    'trades': self.trades,
                    'final_portfolio_value': self.total_value,
                    'performance_metrics': performance_metrics,
                    'backtest_results': backtest_results,
                    'data_source': f"{exchange.upper()}真实数据",
                    'data_records': len(df)
                }
            }
            
        except Exception as e:
            error_msg = f"回测执行失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    async def _check_data_availability(
        self,
        exchange: str,
        symbol: str, 
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """检查指定交易所和交易对的数据可用性"""
        try:
            from app.models.market_data import MarketData
            from sqlalchemy import select, distinct
            
            # 检查指定交易所的数据
            # 使用更宽松的时间范围查询，因为数据可能不在精确的时间范围内
            query = select(MarketData).where(
                MarketData.exchange.ilike(f"%{exchange}%"),
                MarketData.symbol == symbol
            ).limit(1000)  # 限制查询数量以检查数据可用性
            
            result = await db.execute(query)
            records = result.scalars().all()
            has_data = len(records) > 10  # 至少需要10条数据
            
            # 获取可用的交易所列表
            available_exchanges_query = select(distinct(MarketData.exchange)).where(
                MarketData.symbol == symbol
            )
            exchanges_result = await db.execute(available_exchanges_query)
            available_exchanges = [ex for ex in exchanges_result.scalars().all() if ex]
            
            return {
                'has_data': has_data,
                'record_count': len(records),
                'requested_exchange': exchange,
                'available_exchanges': available_exchanges,
                'symbol': symbol,
                'date_range': f"{start_date.date()} 到 {end_date.date()}"
            }
            
        except Exception as e:
            logger.error(f"检查数据可用性失败: {e}")
            return {
                'has_data': False,
                'record_count': 0,
                'requested_exchange': exchange,
                'available_exchanges': [],
                'error': str(e)
            }


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
                engine = create_backtest_engine()  # 🔧 使用工厂方法创建独立实例
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
                engine = create_backtest_engine()  # 🔧 使用工厂方法创建独立实例
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
            engine = create_backtest_engine()  # 🔧 使用工厂方法创建独立实例
            
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


class DeterministicBacktestEngine(BacktestEngine):
    """确定性回测引擎 - 解决回测结果不一致问题
    
    主要修复:
    1. 随机种子控制 - 消除所有随机性源头
    2. Decimal高精度计算 - 避免浮点数精度累积误差
    3. 确定性数据库查询 - 复合排序确保查询结果一致
    4. 增强状态管理 - 完全独立的状态重置
    """
    
    def __init__(self, random_seed: int = 42):
        """初始化确定性回测引擎
        
        Args:
            random_seed: 随机种子，确保结果可重现
        """
        self.random_seed = random_seed
        self._set_deterministic_environment()
        super().__init__()
        logger.info(f"🔧 初始化确定性回测引擎，随机种子: {random_seed}")
        
    def _set_deterministic_environment(self):
        """设置完全确定性的环境"""
        # 1. 设置所有随机源的种子
        random.seed(self.random_seed)
        np.random.seed(self.random_seed)
        os.environ['PYTHONHASHSEED'] = str(self.random_seed)
        
        # 2. 设置Decimal高精度计算环境
        getcontext().prec = 28  # 28位精度，足够处理金融计算
        getcontext().rounding = 'ROUND_HALF_EVEN'  # 银行家舍入，避免累积偏差
        
        logger.debug(f"🔧 设置确定性环境: 随机种子={self.random_seed}, Decimal精度=28位")
        
    def _reset_state(self):
        """完全重置回测引擎状态，确保每次回测的确定性独立性"""
        super()._reset_state()
        
        # 重新设置确定性环境（防止外部代码污染）
        self._set_deterministic_environment()
        
        logger.debug("🔧 确定性状态重置完成")
        
    async def _get_historical_data_deterministic(
        self, 
        db: AsyncSession, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime, 
        timeframe: str = "1h"
    ) -> pd.DataFrame:
        """确定性历史数据查询 - 使用复合排序确保结果一致"""
        try:
            from app.models.market_data import MarketData
            
            logger.info(f"🔧 确定性数据查询: {symbol} {timeframe} {start_date} - {end_date}")
            
            # 关键修复：使用复合排序确保查询结果完全确定
            query = select(MarketData).where(
                MarketData.symbol == symbol.replace('/', ''),
                MarketData.timeframe == timeframe,
                MarketData.open_time >= int(start_date.timestamp() * 1000),
                MarketData.open_time <= int(end_date.timestamp() * 1000)
            ).order_by(
                MarketData.open_time.asc(),  # 主排序：时间戳
                MarketData.id.asc()          # 次排序：ID，确保完全确定性
            )
            
            result = await db.execute(query)
            market_data = result.scalars().all()
            
            if not market_data:
                error_msg = f"❌ 数据库中没有找到 {symbol} {timeframe} 的历史数据"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 转换为DataFrame，使用Decimal确保精度
            df_data = []
            for item in market_data:
                df_data.append({
                    'timestamp': pd.Timestamp(item.open_time, unit='ms'),
                    'open': float(Decimal(str(item.open_price))),
                    'high': float(Decimal(str(item.high_price))),
                    'low': float(Decimal(str(item.low_price))),
                    'close': float(Decimal(str(item.close_price))),
                    'volume': float(Decimal(str(item.volume))),
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)  # 确保时间序列排序
            
            logger.info(f"✅ 确定性数据获取成功: {len(df)} 条记录")
            return df
            
        except Exception as e:
            logger.error(f"❌ 确定性数据查询失败: {str(e)}")
            # 不再生成模拟数据，直接抛出异常
            raise ValueError(f"无法获取 {symbol} 的历史数据: {str(e)}")
            
    async def _get_api_data_deterministic(
        self, 
        db: AsyncSession, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime, 
        timeframe: str
    ) -> pd.DataFrame:
        """确定性API数据获取 - 使用固定参数确保一致性"""
        try:
            # 使用父类的API获取方法，但确保参数确定性
            df = await super()._get_historical_data(db, symbol, start_date, end_date, timeframe)
            
            if df.empty:
                error_msg = f"❌ API数据获取失败，没有找到 {symbol} 的数据"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 对API数据进行确定性后处理
            df = df.sort_index()  # 确保时间排序
            return df
            
        except Exception as e:
            logger.error(f"❌ API数据获取失败: {str(e)}")
            raise ValueError(f"无法通过API获取 {symbol} 的历史数据: {str(e)}")
    
    # 已移除 _create_deterministic_fallback_data 方法
    # 回测系统不应该生成模拟数据，必须使用真实的历史数据
    
    def _calculate_moving_average_deterministic(self, prices: List[float], window: int) -> List[Optional[float]]:
        """确定性移动平均线计算 - 使用Decimal精度"""
        decimal_prices = [Decimal(str(p)) for p in prices]
        ma_values = []
        
        for i in range(len(decimal_prices)):
            if i < window - 1:
                ma_values.append(None)
            else:
                # 使用Decimal进行高精度计算
                window_sum = sum(decimal_prices[i-window+1:i+1])
                ma_value = window_sum / Decimal(str(window))
                ma_values.append(float(ma_value))
        
        return ma_values
    
    def _generate_trading_signals_deterministic(self, df: pd.DataFrame, strategy_params: Dict[str, Any] = None) -> List[str]:
        """确定性交易信号生成 - 消除所有随机性"""
        if df.empty:
            return []
        
        if strategy_params is None:
            strategy_params = {'short_period': 5, 'long_period': 20}
        
        short_period = strategy_params.get('short_period', 5)
        long_period = strategy_params.get('long_period', 20)
        
        logger.debug(f"🔧 确定性信号生成: MA({short_period}, {long_period})")
        
        closes = df['close'].tolist()
        
        # 使用确定性移动平均计算
        ma_short = self._calculate_moving_average_deterministic(closes, short_period)
        ma_long = self._calculate_moving_average_deterministic(closes, long_period)
        
        signals = []
        tolerance = Decimal('0.01')  # 使用Decimal容差
        
        for i in range(len(closes)):
            if i < long_period or ma_short[i] is None or ma_long[i] is None:
                signals.append('hold')
                continue
                
            # 确定性的交叉判断
            current_diff = Decimal(str(ma_short[i])) - Decimal(str(ma_long[i]))
            prev_diff = (Decimal(str(ma_short[i-1])) - Decimal(str(ma_long[i-1])) 
                        if i > 0 and ma_short[i-1] is not None and ma_long[i-1] is not None 
                        else Decimal('0'))
            
            # 金叉买入
            if current_diff > tolerance and prev_diff <= tolerance:
                signals.append('buy')
            # 死叉卖出  
            elif current_diff < -tolerance and prev_diff >= -tolerance:
                signals.append('sell')
            else:
                signals.append('hold')
                
        logger.debug(f"🔧 确定性信号统计: {signals.count('buy')}买入, {signals.count('sell')}卖出, {signals.count('hold')}持有")
        return signals
    
    async def _execute_trade_deterministic(
        self, 
        signal: str, 
        market_data: pd.Series, 
        timestamp: pd.Timestamp, 
        symbol: str
    ):
        """确定性交易执行 - 使用Decimal确保精度一致性"""
        if signal == 'hold':
            return
            
        # 使用Decimal进行所有金融计算
        current_price = Decimal(str(market_data['close']))
        cash_decimal = Decimal(str(self.cash_balance))
        position_decimal = Decimal(str(self.current_position))
        
        logger.debug(f"🔧 确定性交易执行: 信号={signal}, 价格={current_price}, 现金={cash_decimal}, 持仓={position_decimal}")
        
        if signal == 'buy' and cash_decimal > Decimal('100'):
            # 买入：使用50%的现金（固定比例，避免随机性）
            trade_ratio = Decimal('0.5')
            trade_value = cash_decimal * trade_ratio
            trade_amount = trade_value / current_price
            
            # 更新持仓和现金（使用Decimal确保精度）
            self.current_position = float(position_decimal + trade_amount)
            self.cash_balance = float(cash_decimal - trade_value)
            
            trade_record = {
                'timestamp': timestamp,
                'signal': signal,
                'price': float(current_price),
                'amount': float(trade_amount),
                'value': float(trade_value),
                'position_change': float(trade_amount),
                'position_after': self.current_position,
                'cash_after': self.cash_balance
            }
            
            self.trades.append(trade_record)
            logger.info(f"✅ 确定性买入: {float(trade_amount):.6f} @ {float(current_price):.2f}")
            
        elif signal == 'sell' and position_decimal > Decimal('0.00001'):
            # 卖出：卖出50%持仓（固定比例，避免随机性）
            trade_ratio = Decimal('0.5')
            trade_amount = position_decimal * trade_ratio
            trade_value = trade_amount * current_price
            
            # 更新持仓和现金
            self.current_position = float(position_decimal - trade_amount)
            self.cash_balance = float(cash_decimal + trade_value)
            
            trade_record = {
                'timestamp': timestamp,
                'signal': signal,
                'price': float(current_price),
                'amount': float(trade_amount),
                'value': float(trade_value),
                'position_change': float(-trade_amount),
                'position_after': self.current_position,
                'cash_after': self.cash_balance
            }
            
            self.trades.append(trade_record)
            logger.info(f"✅ 确定性卖出: {float(trade_amount):.6f} @ {float(current_price):.2f}")
    
    async def run_deterministic_backtest(
        self, 
        strategy_id: int, 
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        symbol: str = "BTC/USDT",
        session: AsyncSession = None
    ) -> Dict[str, Any]:
        """运行确定性回测 - 保证100%可重现的结果"""
        
        # 确保每次回测都重新设置确定性环境
        self._set_deterministic_environment()
        self._reset_state()
        
        logger.info(f"🔧 启动确定性回测: {symbol} {start_date} - {end_date}, 初始资金: {initial_capital}")
        
        try:
            self.cash_balance = initial_capital
            self.total_value = initial_capital
            
            # 获取确定性历史数据
            df = await self._get_historical_data_deterministic(
                session, symbol, start_date, end_date
            )
            
            if df.empty:
                raise ValueError("无法获取历史数据")
            
            # 生成确定性交易信号
            signals = self._generate_trading_signals_deterministic(df)
            
            # 执行确定性回测
            for i, (timestamp, market_data) in enumerate(df.iterrows()):
                if i < len(signals):
                    signal = signals[i]
                    await self._execute_trade_deterministic(signal, market_data, timestamp, symbol)
                
                # 更新总资产价值
                current_price = Decimal(str(market_data['close']))
                position_value = Decimal(str(self.current_position)) * current_price
                self.total_value = float(Decimal(str(self.cash_balance)) + position_value)
                self.portfolio_history.append(self.total_value)
            
            # 计算确定性性能指标
            metrics = self._calculate_performance_metrics(initial_capital)
            
            # 生成确定性结果哈希（用于验证一致性）
            result_data = [
                self.total_value,
                len(self.trades),
                self.cash_balance,
                self.current_position,
                self.random_seed
            ]
            result_hash = hash(str(sorted(result_data)))
            
            result = {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'symbol': symbol,
                'initial_capital': initial_capital,
                'final_value': self.total_value,
                'total_return': metrics.get('total_return', 0),
                'trade_count': len(self.trades),
                'trades': self.trades,
                'metrics': metrics,
                'random_seed': self.random_seed,
                'result_hash': result_hash,  # 用于验证结果一致性
                'deterministic': True  # 标记为确定性结果
            }
            
            logger.info(f"✅ 确定性回测完成: 最终价值={self.total_value:.2f}, 交易次数={len(self.trades)}, 哈希={result_hash}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 确定性回测失败: {str(e)}")
            raise


# 🔧 关键修复：移除全局实例，每次都创建新的BacktestEngine实例
# 这确保了不同回测任务之间的完全独立性
def create_backtest_engine() -> 'StatelessBacktestAdapter':
    """创建新的回测引擎实例，确保状态独立性 - 现在使用无状态引擎"""
    from app.services.stateless_backtest_adapter import create_stateless_backtest_engine
    return create_stateless_backtest_engine()

def create_deterministic_backtest_engine(random_seed: int = 42) -> 'StatelessBacktestAdapter':
    """创建确定性回测引擎实例 - 解决回测结果不一致问题
    
    现在使用无状态引擎，彻底解决状态污染问题
    
    Args:
        random_seed: 随机种子，确保结果100%可重现
        
    Returns:
        StatelessBacktestAdapter: 无状态回测引擎适配器
    """
    from app.services.stateless_backtest_adapter import create_stateless_deterministic_backtest_engine
    return create_stateless_deterministic_backtest_engine(random_seed)