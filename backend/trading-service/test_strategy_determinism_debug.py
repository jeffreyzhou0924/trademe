#!/usr/bin/env python3
"""
深度分析复杂策略的确定性问题
专门调试双均线+KDJ策略在前端回测中的不一致性
"""

import sys
import os
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import get_db
from app.models.market_data import MarketData
from app.services.backtest_service import create_backtest_engine
from sqlalchemy import select, and_

# 从前端日志中提取的策略代码
FRONTEND_STRATEGY_CODE = """from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"优化的双均线交叉策略 - 结合KDJ指标过滤\"\"\"
    
    def get_data_requirements(self) -> List[DataRequest]:
        \"\"\"定义策略所需的数据源\"\"\"
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP", 
                timeframe="1h",
                required=True
            )
        ]
    
    async def on_data_update(self, data_type: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        \"\"\"数据更新处理 - 实现双均线交叉策略逻辑\"\"\"
        if data_type != "kline":
            return None
            
        # 获取K线数据
        df = self.get_kline_data()
        if df is None or len(df) < 50:  # 需要足够的历史数据
            return None
        
        # 计算技术指标
        sma5 = self.calculate_sma(df['close'], 5)
        sma10 = self.calculate_sma(df['close'], 10)
        
        # 计算KDJ指标用于信号过滤
        kdj_k, kdj_d, kdj_j = self.calculate_kdj(df['high'], df['low'], df['close'], 9, 3, 3)
        
        # 获取当前价格和仓位信息
        current_price = df['close'].iloc[-1]
        current_position = self.get_current_position()
        
        # 从参数中获取配置
        position_size = self.context.parameters.get('position_size', 10.0) / 100.0  # 转换为比例
        stop_loss_pct = self.context.parameters.get('stop_loss', 5.0) / 100.0
        take_profit_pct = self.context.parameters.get('take_profit', 5.0) / 100.0
        
        # 检测均线交叉信号
        golden_cross = self._detect_golden_cross(sma5, sma10)
        death_cross = self._detect_death_cross(sma5, sma10)
        
        # 优化的信号生成逻辑
        signal = None
        
        # 金叉信号 - 开多仓
        if golden_cross:
            # KDJ过滤：K值小于80且K>D时信号更可靠
            if kdj_k[-1] < 80 and kdj_k[-1] > kdj_d[-1]:
                # 如果有空仓，先平空再开多
                if current_position and current_position < 0:
                    # 系统会自动处理平仓逻辑
                    pass
                
                signal = TradingSignal(
                    signal_type=SignalType.BUY,
                    symbol="BTC-USDT-SWAP",
                    price=current_price,
                    quantity=position_size,
                    stop_loss=current_price * (1 - stop_loss_pct),
                    take_profit=current_price * (1 + take_profit_pct),
                    metadata={
                        'strategy': 'sma_cross_optimized',
                        'signal_reason': 'golden_cross_with_kdj_filter',
                        'sma5': sma5[-1],
                        'sma10': sma10[-1],
                        'kdj_k': kdj_k[-1],
                        'kdj_d': kdj_d[-1]
                    }
                )
        
        # 死叉信号 - 开空仓
        elif death_cross:
            # KDJ过滤：K值大于20且K<D时信号更可靠
            if kdj_k[-1] > 20 and kdj_k[-1] < kdj_d[-1]:
                # 如果有多仓，先平多再开空
                if current_position and current_position > 0:
                    # 系统会自动处理平仓逻辑
                    pass
                
                signal = TradingSignal(
                    signal_type=SignalType.SELL,
                    symbol="BTC-USDT-SWAP",
                    price=current_price,
                    quantity=position_size,
                    stop_loss=current_price * (1 + stop_loss_pct),
                    take_profit=current_price * (1 - take_profit_pct),
                    metadata={
                        'strategy': 'sma_cross_optimized',
                        'signal_reason': 'death_cross_with_kdj_filter',
                        'sma5': sma5[-1],
                        'sma10': sma10[-1],
                        'kdj_k': kdj_k[-1],
                        'kdj_d': kdj_d[-1]
                    }
                )
        
        # 动态止盈止损调整（趋势跟踪优化）
        if current_position and signal is None:
            signal = self._check_dynamic_exit(df, current_position, current_price, 
                                            sma5, sma10, kdj_k, kdj_d)
        
        return signal
    
    def _detect_golden_cross(self, sma5: pd.Series, sma10: pd.Series) -> bool:
        \"\"\"检测金叉信号\"\"\"
        if len(sma5) < 2 or len(sma10) < 2:
            return False
        
        # 当前SMA5 > SMA10 且 前一根SMA5 <= SMA10
        current_cross = sma5.iloc[-1] > sma10.iloc[-1]
        previous_cross = sma5.iloc[-2] <= sma10.iloc[-2]
        
        return current_cross and previous_cross
    
    def _detect_death_cross(self, sma5: pd.Series, sma10: pd.Series) -> bool:
        \"\"\"检测死叉信号\"\"\"
        if len(sma5) < 2 or len(sma10) < 2:
            return False
        
        # 当前SMA5 < SMA10 且 前一根SMA5 >= SMA10
        current_cross = sma5.iloc[-1] < sma10.iloc[-1]
        previous_cross = sma5.iloc[-2] >= sma10.iloc[-2]
        
        return current_cross and previous_cross
    
    def _check_dynamic_exit(self, df: pd.DataFrame, position: float, current_price: float,
                          sma5: pd.Series, sma10: pd.Series, kdj_k: pd.Series, kdj_d: pd.Series) -> Optional[TradingSignal]:
        \"\"\"动态出场逻辑 - 趋势跟踪优化\"\"\"
        
        # 多仓动态止盈逻辑
        if position > 0:
            # 趋势转弱信号：SMA5开始走平或KDJ超买
            if (sma5.iloc[-1] <= sma5.iloc[-2] or kdj_k[-1] > 85) and kdj_k[-1] < kdj_d[-1]:
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    symbol="BTC-USDT-SWAP",
                    price=current_price,
                    quantity=abs(position),
                    metadata={
                        'strategy': 'sma_cross_optimized',
                        'signal_reason': 'dynamic_exit_long_trend_weak'
                    }
                )
        
        # 空仓动态止盈逻辑
        elif position < 0:
            # 趋势转强信号：SMA5开始上涨或KDJ超卖反弹
            if (sma5.iloc[-1] >= sma5.iloc[-2] or kdj_k[-1] < 15) and kdj_k[-1] > kdj_d[-1]:
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    symbol="BTC-USDT-SWAP",
                    price=current_price,
                    quantity=abs(position),
                    metadata={
                        'strategy': 'sma_cross_optimized',
                        'signal_reason': 'dynamic_exit_short_trend_strong'
                    }
                )
        
        return None
    
    def calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                     k_period: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> tuple:
        \"\"\"计算KDJ指标\"\"\"
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        rsv = 100 * (close - lowest_low) / (highest_high - lowest_low)
        rsv = rsv.fillna(50)  # 填充NaN值
        
        k = rsv.ewm(span=k_smooth).mean()
        d = k.ewm(span=d_smooth).mean()
        j = 3 * k - 2 * d
        
        return k, d, j
"""

class StrategyDeterminismAnalyzer:
    """策略确定性分析器"""
    
    def __init__(self):
        self.results = []
    
    async def analyze_strategy_determinism(self, num_runs: int = 5) -> Dict[str, Any]:
        """分析策略确定性问题"""
        print(f"🔍 开始策略确定性分析 - 执行 {num_runs} 次相同回测")
        
        # 回测配置（与前端日志保持一致）
        backtest_config = {
            'strategy_code': FRONTEND_STRATEGY_CODE,
            'exchange': 'okx',
            'symbols': ['BTC/USDT'],
            'timeframes': ['1h'],
            'start_date': '2025-07-01',
            'end_date': '2025-08-31',
            'initial_capital': 10000.0,
            'fee_rate': 'vip0_perp',
            'data_type': 'kline'
        }
        
        # 执行多次回测
        results = []
        for i in range(num_runs):
            print(f"\n🔧 执行第 {i+1} 次回测...")
            
            # 使用工厂方法创建独立的回测引擎实例
            engine = create_backtest_engine()
            
            async for db in get_db():
                try:
                    result = await engine.execute_backtest(
                        backtest_config,
                        user_id=1,
                        db=db
                    )
                    
                    if result.get('success'):
                        backtest_result = result.get('backtest_result', {})
                        
                        # 提取关键结果用于比较
                        key_metrics = {
                            'final_portfolio_value': backtest_result.get('final_portfolio_value', 0),
                            'total_trades': len(backtest_result.get('trades', [])),
                            'trade_count': len([t for t in backtest_result.get('trades', []) if t.get('type') == 'exit']),
                        }
                        
                        # 计算详细的交易哈希（包含时间戳和价格）
                        trades = backtest_result.get('trades', [])
                        trade_signatures = []
                        for trade in trades:
                            if isinstance(trade, dict):
                                signature = f"{trade.get('timestamp', '')}-{trade.get('type', '')}-{trade.get('price', 0)}-{trade.get('quantity', 0)}-{trade.get('pnl', 0)}"
                                trade_signatures.append(signature)
                        
                        trade_hash = hashlib.md5('|'.join(sorted(trade_signatures)).encode()).hexdigest()
                        key_metrics['trade_hash'] = trade_hash
                        
                        results.append({
                            'run_id': i + 1,
                            'success': True,
                            'metrics': key_metrics,
                            'trades': trades,
                            'trade_signatures': trade_signatures
                        })
                        
                        print(f"✅ 第 {i+1} 次回测完成:")
                        print(f"   - 最终价值: {key_metrics['final_portfolio_value']:.2f}")
                        print(f"   - 交易数量: {key_metrics['total_trades']}")
                        print(f"   - 完整交易: {key_metrics['trade_count']}")
                        print(f"   - 交易哈希: {trade_hash[:8]}...")
                        
                    else:
                        print(f"❌ 第 {i+1} 次回测失败: {result.get('error', '未知错误')}")
                        results.append({
                            'run_id': i + 1,
                            'success': False,
                            'error': result.get('error')
                        })
                    
                    break
                finally:
                    await db.close()
        
        # 分析结果
        return self._analyze_results(results)
    
    def _analyze_results(self, results: List[Dict]) -> Dict[str, Any]:
        """分析多次回测结果的一致性"""
        print(f"\n📊 分析 {len(results)} 次回测结果的一致性...")
        
        successful_runs = [r for r in results if r.get('success')]
        failed_runs = [r for r in results if not r.get('success')]
        
        if len(successful_runs) < 2:
            return {
                'consistent': False,
                'reason': f"只有 {len(successful_runs)} 次成功回测，无法进行一致性比较",
                'successful_runs': len(successful_runs),
                'failed_runs': len(failed_runs)
            }
        
        # 检查结果一致性
        first_result = successful_runs[0]['metrics']
        inconsistencies = []
        
        for i, run in enumerate(successful_runs[1:], 2):
            metrics = run['metrics']
            
            # 检查关键指标
            if abs(metrics['final_portfolio_value'] - first_result['final_portfolio_value']) > 0.01:
                inconsistencies.append({
                    'type': 'final_value_mismatch',
                    'run': i,
                    'expected': first_result['final_portfolio_value'],
                    'actual': metrics['final_portfolio_value'],
                    'difference': abs(metrics['final_portfolio_value'] - first_result['final_portfolio_value'])
                })
            
            if metrics['total_trades'] != first_result['total_trades']:
                inconsistencies.append({
                    'type': 'trade_count_mismatch',
                    'run': i,
                    'expected': first_result['total_trades'],
                    'actual': metrics['total_trades']
                })
            
            if metrics['trade_hash'] != first_result['trade_hash']:
                inconsistencies.append({
                    'type': 'trade_sequence_mismatch',
                    'run': i,
                    'expected_hash': first_result['trade_hash'],
                    'actual_hash': metrics['trade_hash']
                })
        
        # 生成详细分析报告
        analysis_report = {
            'consistent': len(inconsistencies) == 0,
            'successful_runs': len(successful_runs),
            'failed_runs': len(failed_runs),
            'inconsistencies': inconsistencies,
            'summary': {}
        }
        
        # 统计各次运行的关键指标
        final_values = [r['metrics']['final_portfolio_value'] for r in successful_runs]
        trade_counts = [r['metrics']['total_trades'] for r in successful_runs]
        trade_hashes = [r['metrics']['trade_hash'] for r in successful_runs]
        
        analysis_report['summary'] = {
            'final_values': {
                'all_values': final_values,
                'unique_count': len(set(final_values)),
                'min': min(final_values),
                'max': max(final_values),
                'range': max(final_values) - min(final_values)
            },
            'trade_counts': {
                'all_counts': trade_counts,
                'unique_count': len(set(trade_counts)),
                'consistent': len(set(trade_counts)) == 1
            },
            'trade_sequences': {
                'unique_hashes': len(set(trade_hashes)),
                'consistent': len(set(trade_hashes)) == 1
            }
        }
        
        return analysis_report

async def main():
    """主分析函数"""
    print("🚀 启动复杂策略确定性深度分析")
    print("=" * 60)
    
    analyzer = StrategyDeterminismAnalyzer()
    
    try:
        # 执行分析
        analysis = await analyzer.analyze_strategy_determinism(num_runs=3)
        
        print("\n" + "=" * 60)
        print("📋 分析结果报告")
        print("=" * 60)
        
        print(f"✅ 成功运行: {analysis['successful_runs']} 次")
        print(f"❌ 失败运行: {analysis['failed_runs']} 次")
        print(f"🎯 结果一致性: {'✅ 一致' if analysis['consistent'] else '❌ 不一致'}")
        
        if not analysis['consistent']:
            print(f"\n⚠️ 发现 {len(analysis['inconsistencies'])} 个不一致问题:")
            for inc in analysis['inconsistencies']:
                print(f"   - 运行{inc['run']}: {inc['type']}")
                if 'expected' in inc:
                    print(f"     期望: {inc['expected']}, 实际: {inc['actual']}")
                if 'difference' in inc:
                    print(f"     差异: {inc['difference']:.6f}")
        
        # 详细统计
        summary = analysis['summary']
        if summary:
            print(f"\n📊 详细统计:")
            
            fv = summary['final_values']
            print(f"   最终价值:")
            print(f"     - 唯一值数量: {fv['unique_count']}")
            print(f"     - 取值范围: {fv['min']:.2f} ~ {fv['max']:.2f} (差异: {fv['range']:.6f})")
            print(f"     - 所有值: {[f'{v:.2f}' for v in fv['all_values']]}")
            
            tc = summary['trade_counts']
            print(f"   交易数量:")
            print(f"     - 唯一值数量: {tc['unique_count']}")
            print(f"     - 一致性: {'✅' if tc['consistent'] else '❌'}")
            print(f"     - 所有值: {tc['all_counts']}")
            
            ts = summary['trade_sequences']
            print(f"   交易序列:")
            print(f"     - 唯一哈希数量: {ts['unique_hashes']}")
            print(f"     - 一致性: {'✅' if ts['consistent'] else '❌'}")
        
        # 诊断建议
        print(f"\n💡 诊断建议:")
        if analysis['consistent']:
            print("   ✅ 策略执行完全一致，问题可能在前端或其他层面")
        else:
            inconsistency_types = set(inc['type'] for inc in analysis['inconsistencies'])
            if 'final_value_mismatch' in inconsistency_types:
                print("   🔍 最终价值不一致 - 可能存在浮点精度问题或状态污染")
            if 'trade_count_mismatch' in inconsistency_types:
                print("   🔍 交易数量不一致 - 可能存在信号生成的随机性")
            if 'trade_sequence_mismatch' in inconsistency_types:
                print("   🔍 交易序列不一致 - 策略逻辑可能包含非确定性因素")
        
        # 保存详细结果
        with open('strategy_determinism_analysis.json', 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"\n📄 详细结果已保存到 strategy_determinism_analysis.json")
        
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())