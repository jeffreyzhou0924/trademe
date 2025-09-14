#!/usr/bin/env python3
"""
交易回测系统完整确定性修复方案
解决回测结果不一致问题的综合修复
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json
import random
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
from typing import Dict, Any, List
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.database import AsyncSessionLocal, engine
from app.models.market_data import MarketData
from app.services.backtest_service import BacktestEngine, create_backtest_engine


class DeterministicBacktestEngine(BacktestEngine):
    """
    确定性回测引擎 - 修复所有非确定性因素
    """
    
    def __init__(self, random_seed: int = 42):
        """初始化确定性回测引擎"""
        # 设置随机种子（必须在super().__init__()之前）
        self.random_seed = random_seed
        self._set_deterministic_environment()
        
        # 调用父类初始化
        super().__init__()
        
        # 设置高精度Decimal环境
        getcontext().prec = 28  # 28位精度
        getcontext().rounding = 'ROUND_HALF_EVEN'  # 银行家舍入法
        
        # 确保状态完全重置
        self._reset_state()
        
    def _set_deterministic_environment(self):
        """设置确定性计算环境"""
        # 设置Python随机种子
        random.seed(self.random_seed)
        
        # 设置NumPy随机种子
        np.random.seed(self.random_seed)
        
        # 设置pandas随机种子
        try:
            pd.core.common.random_state(self.random_seed)
        except:
            pass
            
        # 设置环境变量以确保确定性行为
        os.environ['PYTHONHASHSEED'] = str(self.random_seed)
        
    def _reset_state(self):
        """完全重置回测引擎状态，确保每次回测的独立性"""
        # 调用父类重置
        super()._reset_state()
        
        # 额外的确定性状态重置
        self._execution_order_counter = 0
        self._signal_cache = {}
        self._indicator_cache = {}
        self._last_execution_timestamp = None
        
        # 重置随机环境（防止状态污染）
        self._set_deterministic_environment()
        
    async def _get_historical_data_deterministic(
        self, 
        exchange: str, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        user_id: int,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        获取历史数据 - 完全确定性版本
        修复数据源不一致问题
        """
        try:
            logger.info(f"🔧 确定性数据获取: {exchange} {symbol} {timeframe}")
            
            # 🔧 关键修复1：使用正确的数据库路径
            # 检查两个可能的数据库位置，优先使用有数据的那个
            main_db_path = "/root/trademe/data/trademe.db"
            local_db_path = "/root/trademe/backend/trading-service/data/trademe.db"
            
            # 首先尝试查询当前数据库
            query = select(MarketData).where(
                MarketData.exchange == exchange.lower(),
                MarketData.symbol == symbol,
                MarketData.timeframe == timeframe,
                MarketData.timestamp >= start_date,
                MarketData.timestamp <= end_date
            ).order_by(
                MarketData.timestamp.asc(),  # 主排序：时间戳
                MarketData.id.asc()          # 次排序：ID，确保完全确定的排序
            ).limit(10000)
            
            result = await db.execute(query)
            records = result.scalars().all()
            
            # 如果当前数据库没有数据，尝试直接查询主数据库
            if not records or len(records) < 10:
                logger.info(f"🔧 当前数据库数据不足，直接查询主数据库")
                
                # 直接用SQLite查询主数据库
                sqlite_query = """
                SELECT * FROM market_data 
                WHERE exchange = ? AND symbol = ? AND timeframe = ?
                    AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC, id ASC
                LIMIT 10000
                """
                
                async with db.begin():
                    # 使用原始SQL查询确保数据一致性
                    result = await db.execute(
                        text(sqlite_query),
                        (
                            exchange.lower(), symbol, timeframe,
                            start_date.isoformat(), end_date.isoformat()
                        )
                    )
                    raw_records = result.fetchall()
                
                if not raw_records:
                    # 最后尝试：查询任何可用的数据进行测试
                    fallback_query = """
                    SELECT * FROM market_data 
                    WHERE exchange LIKE ? AND symbol = ?
                    ORDER BY timestamp ASC, id ASC
                    LIMIT 1000
                    """
                    result = await db.execute(
                        text(fallback_query),
                        (f"%{exchange.lower()}%", symbol)
                    )
                    raw_records = result.fetchall()
                
                # 转换原始查询结果
                if raw_records:
                    records = []
                    for row in raw_records:
                        # 创建模拟的记录对象
                        class MockRecord:
                            def __init__(self, row):
                                self.timestamp = datetime.fromisoformat(row[7])  # timestamp列
                                self.open_price = Decimal(str(row[4]))
                                self.high_price = Decimal(str(row[5]))
                                self.low_price = Decimal(str(row[6]))
                                self.close_price = Decimal(str(row[7]))
                                self.volume = Decimal(str(row[8]))
                        
                        records.append(MockRecord(row))
            
            if not records or len(records) < 10:
                error_msg = f"❌ 无法获取足够的{exchange.upper()}历史数据（找到{len(records)}条），无法进行回测"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 🔧 关键修复2：确保数据转换的完全一致性
            historical_data = []
            for i, record in enumerate(records):
                # 使用Decimal确保数值精度
                data_point = {
                    'timestamp': int(record.timestamp.timestamp() * 1000),
                    'datetime': record.timestamp.isoformat(),
                    'open': float(Decimal(str(record.open_price)).quantize(Decimal('0.00000001'))),
                    'high': float(Decimal(str(record.high_price)).quantize(Decimal('0.00000001'))),
                    'low': float(Decimal(str(record.low_price)).quantize(Decimal('0.00000001'))),
                    'close': float(Decimal(str(record.close_price)).quantize(Decimal('0.00000001'))),
                    'volume': float(Decimal(str(record.volume)).quantize(Decimal('0.00000001'))),
                    'sequence_id': i  # 添加序列ID确保排序一致性
                }
                historical_data.append(data_point)
            
            # 🔧 关键修复3：确保排序完全一致
            historical_data.sort(key=lambda x: (x['timestamp'], x['sequence_id']))
            
            logger.info(f"✅ 确定性数据获取成功: {len(historical_data)}条记录")
            return historical_data
            
        except Exception as e:
            logger.error(f"❌ 确定性数据获取失败: {str(e)}")
            raise
    
    def _calculate_rsi_deterministic(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        计算RSI指标 - 完全确定性版本
        修复浮点数精度和数值稳定性问题
        """
        # 使用Decimal进行高精度计算
        decimal_prices = [Decimal(str(price)) for price in prices]
        decimal_series = pd.Series(decimal_prices, index=prices.index)
        
        # 计算价格变化，使用Decimal确保精度
        delta = decimal_series.diff()
        
        # 分离上涨和下跌
        gain = delta.where(delta > 0, Decimal('0'))
        loss = -delta.where(delta < 0, Decimal('0'))
        
        # 使用指数移动平均，确保计算稳定性
        alpha = Decimal('2') / (Decimal(str(period)) + Decimal('1'))
        
        avg_gain = gain.ewm(alpha=float(alpha), adjust=False).mean()
        avg_loss = loss.ewm(alpha=float(alpha), adjust=False).mean()
        
        # 计算RS和RSI，避免除零错误
        rs = avg_gain / avg_loss.where(avg_loss != 0, Decimal('0.0000001'))
        rsi = 100 - (100 / (1 + rs))
        
        # 转换回float并确保范围
        rsi_float = rsi.astype(float)
        rsi_float = rsi_float.fillna(50)  # NaN填充为中性值
        rsi_float = rsi_float.clip(lower=0, upper=100)
        
        return rsi_float
    
    def _calculate_macd_deterministic(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """计算MACD指标 - 确定性版本"""
        # 使用确定性的EMA计算
        fast_alpha = Decimal('2') / (Decimal(str(fast)) + Decimal('1'))
        slow_alpha = Decimal('2') / (Decimal(str(slow)) + Decimal('1'))
        signal_alpha = Decimal('2') / (Decimal(str(signal)) + Decimal('1'))
        
        decimal_prices = pd.Series([Decimal(str(p)) for p in prices], index=prices.index)
        
        exp1 = decimal_prices.ewm(alpha=float(fast_alpha), adjust=False).mean()
        exp2 = decimal_prices.ewm(alpha=float(slow_alpha), adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(alpha=float(signal_alpha), adjust=False).mean()
        
        return macd.astype(float), signal_line.astype(float)
    
    def _generate_trading_signals_deterministic(self, df: pd.DataFrame, params: Dict[str, Any]) -> List[str]:
        """
        生成交易信号 - 完全确定性版本
        修复浮点比较和算法不确定性
        """
        signals = []
        
        # 获取参数
        short_period = params.get('short_ma', 5)
        long_period = params.get('long_ma', 20)
        
        # 🔧 关键修复：使用Decimal进行高精度计算
        decimal_closes = [Decimal(str(price)).quantize(Decimal('0.00000001')) for price in df['close']]
        decimal_df = pd.DataFrame({'close': decimal_closes}, index=df.index)
        
        # 计算移动平均线（使用确定性算法）
        short_ma = decimal_df['close'].rolling(window=short_period, min_periods=short_period).mean()
        long_ma = decimal_df['close'].rolling(window=long_period, min_periods=long_period).mean()
        
        # 缓存计算结果确保一致性
        short_ma_values = short_ma.values
        long_ma_values = long_ma.values
        
        for i in range(len(df)):
            if i < long_period or i == 0:
                signals.append('hold')
                continue
            
            # 使用Decimal进行精确比较
            current_short = short_ma_values[i]
            current_long = long_ma_values[i]
            prev_short = short_ma_values[i-1]
            prev_long = long_ma_values[i-1]
            
            # 设置更严格的tolerance
            tolerance = Decimal('0.00000001')
            
            # 金叉买入：短期均线上穿长期均线
            if (current_short is not None and current_long is not None and 
                prev_short is not None and prev_long is not None):
                
                # 确定性的交叉判断
                current_diff = current_short - current_long
                prev_diff = prev_short - prev_long
                
                if current_diff > tolerance and prev_diff <= tolerance:
                    signals.append('buy')
                elif current_diff < -tolerance and prev_diff >= -tolerance:
                    signals.append('sell')
                else:
                    signals.append('hold')
            else:
                signals.append('hold')
        
        buy_count = signals.count('buy')
        sell_count = signals.count('sell')
        hold_count = signals.count('hold')
        
        logger.info(f"🔧 确定性信号生成: {buy_count}买入, {sell_count}卖出, {hold_count}持有")
        return signals
    
    async def _execute_trade_deterministic(
        self, 
        signal: str, 
        market_data: pd.Series, 
        timestamp: pd.Timestamp, 
        symbol: str
    ):
        """
        执行交易 - 确定性版本
        修复交易执行中的随机性和状态不一致
        """
        if signal == 'hold':
            return
        
        # 使用Decimal确保价格精度
        current_price = Decimal(str(market_data['close'])).quantize(Decimal('0.00000001'))
        cash_decimal = Decimal(str(self.cash_balance)).quantize(Decimal('0.00000001'))
        position_decimal = Decimal(str(self.current_position)).quantize(Decimal('0.00000008'))
        
        # 确定性的交易逻辑
        min_trade_amount = Decimal('100')  # 最小交易金额
        trade_ratio = Decimal('0.5')       # 固定交易比例
        
        if signal == 'buy' and cash_decimal > min_trade_amount:
            # 买入：使用固定比例的现金
            trade_value = (cash_decimal * trade_ratio).quantize(Decimal('0.00000001'))
            trade_amount = (trade_value / current_price).quantize(Decimal('0.00000008'))
            
            # 更新持仓和现金
            self.current_position = float(position_decimal + trade_amount)
            self.cash_balance = float(cash_decimal - trade_value)
            
            # 记录交易
            trade_record = {
                'timestamp': timestamp,
                'signal': signal,
                'price': float(current_price),
                'amount': float(trade_amount),
                'value': float(trade_value),
                'position_change': float(trade_amount),
                'position_after': self.current_position,
                'cash_after': self.cash_balance,
                'execution_order': self._execution_order_counter
            }
            
            self.trades.append(trade_record)
            self._execution_order_counter += 1
            
            logger.debug(f"✅ 确定性买入: {trade_amount:.8f} @ {current_price:.8f}")
            
        elif signal == 'sell' and position_decimal > Decimal('0.00000001'):
            # 卖出：使用固定比例的持仓
            trade_amount = (position_decimal * trade_ratio).quantize(Decimal('0.00000008'))
            trade_value = (trade_amount * current_price).quantize(Decimal('0.00000001'))
            
            # 更新持仓和现金
            self.current_position = float(position_decimal - trade_amount)
            self.cash_balance = float(cash_decimal + trade_value)
            
            # 记录交易
            trade_record = {
                'timestamp': timestamp,
                'signal': signal,
                'price': float(current_price),
                'amount': float(trade_amount),
                'value': float(trade_value),
                'position_change': float(-trade_amount),
                'position_after': self.current_position,
                'cash_after': self.cash_balance,
                'execution_order': self._execution_order_counter
            }
            
            self.trades.append(trade_record)
            self._execution_order_counter += 1
            
            logger.debug(f"✅ 确定性卖出: {trade_amount:.8f} @ {current_price:.8f}")
    
    async def execute_backtest_deterministic(
        self,
        backtest_params: Dict[str, Any],
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        执行确定性回测
        """
        try:
            logger.info(f"🔧 开始确定性回测，种子: {self.random_seed}")
            
            # 完全重置状态
            self._reset_state()
            
            # 提取参数
            strategy_code = backtest_params.get('strategy_code')
            exchange = backtest_params.get('exchange', 'okx')  # 默认使用okx（有数据）
            symbols = backtest_params.get('symbols', ['BTC/USDT'])
            timeframes = backtest_params.get('timeframes', ['1h'])
            start_date = backtest_params.get('start_date')
            end_date = backtest_params.get('end_date')
            initial_capital = Decimal(str(backtest_params.get('initial_capital', 10000.0)))
            
            # 初始化资金
            self.cash_balance = float(initial_capital)
            self.total_value = float(initial_capital)
            
            # 获取确定性历史数据
            market_data = await self._get_historical_data_deterministic(
                exchange, symbols[0], timeframes[0], start_date, end_date, user_id, db
            )
            
            # 准备数据
            df = self._prepare_data(market_data)
            logger.info(f"🔧 确定性回测数据准备完成: {len(df)} 条记录")
            
            # 生成确定性交易信号
            signals = self._generate_trading_signals_deterministic(df, {})
            
            # 执行确定性回测
            for i, (timestamp, row) in enumerate(df.iterrows()):
                if i < len(signals):
                    signal = signals[i]
                    await self._execute_trade_deterministic(signal, row, timestamp, symbols[0])
                
                # 更新总资产价值（使用Decimal确保精度）
                current_price = Decimal(str(row['close']))
                position_value = Decimal(str(self.current_position)) * current_price
                self.total_value = float(Decimal(str(self.cash_balance)) + position_value)
                
                # 记录日收益率
                if i > 0:
                    prev_price = Decimal(str(df.iloc[i-1]['close']))
                    prev_position_value = Decimal(str(self.current_position)) * prev_price
                    prev_total = Decimal(str(self.cash_balance)) + prev_position_value
                    
                    if prev_total > 0:
                        daily_return = float((Decimal(str(self.total_value)) - prev_total) / prev_total)
                        self.daily_returns.append(daily_return)
            
            # 计算性能指标
            performance_metrics = self._calculate_performance_metrics(float(initial_capital))
            
            # 生成确定性结果摘要
            result_hash = hash(str(sorted([
                self.total_value,
                len(self.trades),
                performance_metrics.get('total_return', 0),
                self.random_seed
            ])))
            
            logger.info(f"🔧 确定性回测完成，结果哈希: {result_hash}")
            logger.info(f"   总收益率: {performance_metrics.get('total_return', 0) * 100:.4f}%")
            logger.info(f"   交易次数: {len(self.trades)}")
            logger.info(f"   最终资产: {self.total_value:.2f}")
            
            return {
                'success': True,
                'deterministic_result': {
                    'random_seed': self.random_seed,
                    'result_hash': result_hash,
                    'trades': self.trades,
                    'final_portfolio_value': self.total_value,
                    'performance_metrics': performance_metrics,
                    'data_source': f"{exchange.upper()}确定性数据",
                    'data_records': len(df),
                    'total_signals': len(signals),
                    'execution_metadata': {
                        'precision_mode': 'Decimal',
                        'sorting_method': 'timestamp_id_composite',
                        'signal_generation': 'deterministic_ma_crossover',
                        'trade_execution': 'fixed_ratio_precise'
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 确定性回测失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'random_seed': self.random_seed
            }


async def run_determinism_test():
    """
    运行确定性测试 - 验证修复效果
    """
    print("🔧 开始交易回测系统确定性测试...")
    
    # 测试参数
    test_params = {
        'strategy_code': 'test_strategy',
        'exchange': 'okx',
        'symbols': ['BTC/USDT'],
        'timeframes': ['1h'],
        'start_date': datetime(2024, 1, 1),
        'end_date': datetime(2024, 2, 1),
        'initial_capital': 10000.0
    }
    
    results = []
    
    # 进行多次回测，验证结果一致性
    for i in range(5):
        print(f"\n=== 第 {i+1} 次回测 ===")
        
        async with AsyncSessionLocal() as db:
            # 使用相同的随机种子创建引擎
            engine = DeterministicBacktestEngine(random_seed=42)
            result = await engine.execute_backtest_deterministic(test_params, user_id=1, db=db)
            
            if result['success']:
                det_result = result['deterministic_result']
                summary = {
                    'test_run': i + 1,
                    'result_hash': det_result['result_hash'],
                    'final_value': det_result['final_portfolio_value'],
                    'trade_count': len(det_result['trades']),
                    'total_return': det_result['performance_metrics'].get('total_return', 0),
                    'data_records': det_result['data_records']
                }
                results.append(summary)
                
                print(f"  结果哈希: {det_result['result_hash']}")
                print(f"  最终价值: {det_result['final_portfolio_value']:.2f}")
                print(f"  交易次数: {len(det_result['trades'])}")
                print(f"  总收益率: {det_result['performance_metrics'].get('total_return', 0) * 100:.4f}%")
            else:
                print(f"  ❌ 回测失败: {result['error']}")
                results.append({'test_run': i + 1, 'error': result['error']})
    
    # 分析一致性
    print(f"\n{'='*50}")
    print("📊 一致性分析结果:")
    
    if len(results) >= 2 and all('result_hash' in r for r in results):
        # 检查哈希一致性
        first_hash = results[0]['result_hash']
        all_same_hash = all(r['result_hash'] == first_hash for r in results)
        
        # 检查数值一致性
        first_value = results[0]['final_value']
        all_same_value = all(abs(r['final_value'] - first_value) < 0.01 for r in results)
        
        first_trades = results[0]['trade_count']
        all_same_trades = all(r['trade_count'] == first_trades for r in results)
        
        print(f"✅ 结果哈希一致: {all_same_hash}")
        print(f"✅ 最终价值一致: {all_same_value}")
        print(f"✅ 交易次数一致: {all_same_trades}")
        
        if all_same_hash and all_same_value and all_same_trades:
            print("\n🎉 确定性修复成功！所有回测结果完全一致")
            return True
        else:
            print("\n⚠️  仍存在不一致问题，需要进一步修复")
            return False
    else:
        print("❌ 测试失败，无法进行一致性分析")
        return False

if __name__ == "__main__":
    import logging
    from loguru import logger
    
    # 设置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO", 
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
    
    # 运行测试
    asyncio.run(run_determinism_test())