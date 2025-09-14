#!/usr/bin/env python3
"""
诊断前端和后端回测结果差异的专项测试
重点分析实际前端请求与后端处理的差异
"""

import sys
import os
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import get_db
from app.models.market_data import MarketData
from app.services.backtest_service import create_backtest_engine
from app.api.v1.realtime_backtest import RealtimeBacktestManager, RealtimeBacktestConfig
from sqlalchemy import select, and_

class FrontendBackendDiscrepancyAnalyzer:
    """前端后端差异分析器"""
    
    def __init__(self):
        self.results = {}
        
    async def analyze_discrepancy(self) -> Dict[str, Any]:
        """分析前端和后端的回测差异"""
        print("🔍 开始诊断前端和后端回测差异")
        print("=" * 60)
        
        # 模拟前端请求的完整流程
        await self._test_frontend_simulation()
        
        # 分析实际回测服务的核心问题
        await self._test_direct_backtest_service()
        
        # 分析实时回测管理器的处理流程
        await self._test_realtime_backtest_manager()
        
        return self._generate_analysis_report()
    
    async def _test_frontend_simulation(self):
        """模拟前端完整请求流程"""
        print("\n🌐 测试1：模拟前端完整请求流程")
        print("-" * 40)
        
        # 来自前端日志的真实请求参数
        frontend_config = {
            "strategy_code": """from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
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
        position_size = self.context.parameters.get('position_size', 10.0) / 100.0
        stop_loss_pct = self.context.parameters.get('stop_loss', 5.0) / 100.0
        take_profit_pct = self.context.parameters.get('take_profit', 5.0) / 100.0
        
        # 检测均线交叉信号
        golden_cross = self._detect_golden_cross(sma5, sma10)
        death_cross = self._detect_death_cross(sma5, sma10)
        
        # 优化的信号生成逻辑
        signal = None
        
        # 金叉信号 - 开多仓
        if golden_cross:
            if kdj_k[-1] < 80 and kdj_k[-1] > kdj_d[-1]:
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
            if kdj_k[-1] > 20 and kdj_k[-1] < kdj_d[-1]:
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
        
        # 动态止盈止损调整
        if current_position and signal is None:
            signal = self._check_dynamic_exit(df, current_position, current_price, 
                                            sma5, sma10, kdj_k, kdj_d)
        
        return signal
    
    def _detect_golden_cross(self, sma5: pd.Series, sma10: pd.Series) -> bool:
        if len(sma5) < 2 or len(sma10) < 2:
            return False
        current_cross = sma5.iloc[-1] > sma10.iloc[-1]
        previous_cross = sma5.iloc[-2] <= sma10.iloc[-2]
        return current_cross and previous_cross
    
    def _detect_death_cross(self, sma5: pd.Series, sma10: pd.Series) -> bool:
        if len(sma5) < 2 or len(sma10) < 2:
            return False
        current_cross = sma5.iloc[-1] < sma10.iloc[-1]
        previous_cross = sma5.iloc[-2] >= sma10.iloc[-2]
        return current_cross and previous_cross
    
    def _check_dynamic_exit(self, df, position, current_price, sma5, sma10, kdj_k, kdj_d):
        return None  # 简化实现
    
    def calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                     k_period: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> tuple:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        rsv = 100 * (close - lowest_low) / (highest_high - lowest_low)
        rsv = rsv.fillna(50)
        k = rsv.ewm(span=k_smooth).mean()
        d = k.ewm(span=d_smooth).mean()
        j = 3 * k - 2 * d
        return k, d, j""",
            "exchange": "okx",
            "product_type": "perpetual",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "fee_rate": "vip0_perp",
            "initial_capital": 10000,
            "start_date": "2025-07-01",
            "end_date": "2025-08-31",
            "data_type": "kline"
        }
        
        try:
            # 测试RealtimeBacktestConfig的解析
            config = RealtimeBacktestConfig(**frontend_config)
            print(f"✅ 前端配置解析成功")
            print(f"   - 交易所: {config.exchange}")
            print(f"   - 交易对: {config.symbols}")
            print(f"   - 时间框架: {config.timeframes}")
            print(f"   - 开始日期: {config.start_date}")
            print(f"   - 结束日期: {config.end_date}")
            print(f"   - 初始资金: {config.initial_capital}")
            print(f"   - 策略代码长度: {len(config.strategy_code)} 字符")
            
            # 测试使用RealtimeBacktestManager
            manager = RealtimeBacktestManager()
            
            # 直接调用内部的回测逻辑
            async for db in get_db():
                try:
                    manager.db_session = db
                    
                    # 测试数据准备
                    print(f"\n🔄 测试数据准备...")
                    data_result = await manager._prepare_data(config, {})
                    market_data = data_result.get("market_data", {})
                    
                    print(f"✅ 数据准备完成:")
                    for symbol, df in market_data.items():
                        print(f"   - {symbol}: {len(df)} 条记录")
                        if len(df) > 0:
                            print(f"     时间范围: {df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
                    
                    # 测试回测逻辑执行
                    print(f"\n🔄 测试回测逻辑执行...")
                    backtest_result = await manager._run_backtest_logic(config, data_result)
                    
                    print(f"✅ 回测执行完成:")
                    trades = backtest_result.get("trades", [])
                    final_value = backtest_result.get("final_portfolio_value", config.initial_capital)
                    print(f"   - 交易数量: {len(trades)}")
                    print(f"   - 最终价值: {final_value:.2f}")
                    print(f"   - 收益率: {(final_value - config.initial_capital) / config.initial_capital * 100:.2f}%")
                    
                    # 存储结果
                    self.results['frontend_simulation'] = {
                        'trades': len(trades),
                        'final_value': final_value,
                        'success': True
                    }
                    
                    break
                finally:
                    await db.close()
                    
        except Exception as e:
            print(f"❌ 前端模拟测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.results['frontend_simulation'] = {'success': False, 'error': str(e)}
    
    async def _test_direct_backtest_service(self):
        """测试直接使用BacktestService"""
        print("\n🔧 测试2：直接测试BacktestService")
        print("-" * 40)
        
        try:
            engine = create_backtest_engine()
            
            backtest_params = {
                'strategy_code': self._get_test_strategy_code(),
                'exchange': 'okx',
                'symbols': ['BTC/USDT'],
                'timeframes': ['1h'],
                'start_date': '2025-07-01',
                'end_date': '2025-08-31',
                'initial_capital': 10000.0,
                'fee_rate': 'vip0_perp',
                'data_type': 'kline'
            }
            
            async for db in get_db():
                try:
                    result = await engine.execute_backtest(backtest_params, user_id=1, db=db)
                    
                    if result.get('success'):
                        backtest_result = result.get('backtest_result', {})
                        trades = backtest_result.get('trades', [])
                        final_value = backtest_result.get('final_portfolio_value', 10000.0)
                        
                        print(f"✅ 直接BacktestService测试成功:")
                        print(f"   - 交易数量: {len(trades)}")
                        print(f"   - 最终价值: {final_value:.2f}")
                        print(f"   - 收益率: {(final_value - 10000.0) / 10000.0 * 100:.2f}%")
                        
                        # 分析交易详情
                        if trades:
                            entry_trades = [t for t in trades if t.get('type') == 'entry']
                            exit_trades = [t for t in trades if t.get('type') == 'exit']
                            print(f"   - 开仓交易: {len(entry_trades)}")
                            print(f"   - 平仓交易: {len(exit_trades)}")
                        
                        self.results['direct_service'] = {
                            'trades': len(trades),
                            'final_value': final_value,
                            'entry_trades': len([t for t in trades if t.get('type') == 'entry']),
                            'exit_trades': len([t for t in trades if t.get('type') == 'exit']),
                            'success': True
                        }
                    else:
                        error = result.get('error', '未知错误')
                        print(f"❌ 直接BacktestService测试失败: {error}")
                        self.results['direct_service'] = {'success': False, 'error': error}
                    
                    break
                finally:
                    await db.close()
                    
        except Exception as e:
            print(f"❌ 直接服务测试异常: {e}")
            self.results['direct_service'] = {'success': False, 'error': str(e)}
    
    async def _test_realtime_backtest_manager(self):
        """测试RealtimeBacktestManager的数据处理逻辑"""
        print("\n⚡ 测试3：RealtimeBacktestManager数据处理")
        print("-" * 40)
        
        try:
            manager = RealtimeBacktestManager()
            
            # 检查数据可用性
            async for db in get_db():
                try:
                    # 查询实际可用的数据
                    query = select(MarketData).where(
                        MarketData.exchange == 'okx',
                        MarketData.symbol == 'BTC/USDT',
                        MarketData.timeframe == '1h',
                        MarketData.timestamp >= '2025-07-01',
                        MarketData.timestamp <= '2025-08-31'
                    ).order_by(MarketData.timestamp.asc())
                    
                    result = await db.execute(query)
                    records = result.scalars().all()
                    
                    print(f"📊 数据库数据检查:")
                    print(f"   - 匹配记录数: {len(records)}")
                    if records:
                        print(f"   - 时间范围: {records[0].timestamp} ~ {records[-1].timestamp}")
                        print(f"   - 价格范围: ${records[0].close_price:.2f} ~ ${max(r.close_price for r in records):.2f}")
                        
                        # 检查数据连续性
                        timestamps = [r.timestamp for r in records]
                        gaps = []
                        for i in range(1, len(timestamps)):
                            expected = timestamps[i-1] + timedelta(hours=1)
                            if timestamps[i] != expected:
                                gaps.append((timestamps[i-1], timestamps[i]))
                        
                        if gaps:
                            print(f"   - 发现 {len(gaps)} 个数据缺口")
                            if len(gaps) <= 5:  # 只显示前5个
                                for gap in gaps:
                                    print(f"     缺口: {gap[0]} -> {gap[1]}")
                        else:
                            print(f"   - 数据连续性良好")
                    
                    self.results['data_analysis'] = {
                        'total_records': len(records),
                        'has_data': len(records) > 0,
                        'data_gaps': len(gaps) if records else 0,
                        'time_range': f"{records[0].timestamp} ~ {records[-1].timestamp}" if records else "无数据"
                    }
                    
                    break
                finally:
                    await db.close()
                    
        except Exception as e:
            print(f"❌ 数据分析失败: {e}")
            self.results['data_analysis'] = {'success': False, 'error': str(e)}
    
    def _get_test_strategy_code(self) -> str:
        """获取测试用的简化策略代码"""
        return """
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
import pandas as pd

class UserStrategy(EnhancedBaseStrategy):
    def get_data_requirements(self) -> List[DataRequest]:
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
        if data_type != "kline":
            return None
            
        df = self.get_kline_data()
        if df is None or len(df) < 20:
            return None
        
        # 简单的移动平均策略
        sma_short = df['close'].rolling(5).mean()
        sma_long = df['close'].rolling(10).mean()
        
        current_price = df['close'].iloc[-1]
        
        # 金叉买入信号
        if (sma_short.iloc[-1] > sma_long.iloc[-1] and 
            sma_short.iloc[-2] <= sma_long.iloc[-2]):
            return TradingSignal(
                signal_type=SignalType.BUY,
                symbol="BTC-USDT-SWAP",
                price=current_price,
                quantity=0.1,
                metadata={'strategy': 'simple_ma_cross'}
            )
        
        # 死叉卖出信号  
        if (sma_short.iloc[-1] < sma_long.iloc[-1] and 
            sma_short.iloc[-2] >= sma_long.iloc[-2]):
            return TradingSignal(
                signal_type=SignalType.SELL,
                symbol="BTC-USDT-SWAP",
                price=current_price,
                quantity=0.1,
                metadata={'strategy': 'simple_ma_cross'}
            )
            
        return None
"""
    
    def _generate_analysis_report(self) -> Dict[str, Any]:
        """生成分析报告"""
        print("\n" + "=" * 60)
        print("📋 差异分析报告")
        print("=" * 60)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'tests_performed': len(self.results),
            'results': self.results,
            'diagnosis': [],
            'recommendations': []
        }
        
        # 分析结果
        frontend_sim = self.results.get('frontend_simulation', {})
        direct_service = self.results.get('direct_service', {})
        data_analysis = self.results.get('data_analysis', {})
        
        print(f"🧪 测试结果总结:")
        print(f"   - 前端模拟: {'✅ 成功' if frontend_sim.get('success') else '❌ 失败'}")
        print(f"   - 直接服务: {'✅ 成功' if direct_service.get('success') else '❌ 失败'}")
        print(f"   - 数据分析: {'✅ 完成' if data_analysis.get('has_data') else '❌ 无数据'}")
        
        # 诊断分析
        if not frontend_sim.get('success') or not direct_service.get('success'):
            report['diagnosis'].append("回测服务存在基础功能问题")
        
        if frontend_sim.get('success') and direct_service.get('success'):
            fs_trades = frontend_sim.get('trades', 0)
            ds_trades = direct_service.get('trades', 0)
            
            if fs_trades == 0 and ds_trades == 0:
                report['diagnosis'].append("策略没有产生任何交易信号 - 可能是策略逻辑问题或数据问题")
            elif fs_trades != ds_trades:
                report['diagnosis'].append(f"前端模拟与直接服务交易数量不一致: {fs_trades} vs {ds_trades}")
            else:
                report['diagnosis'].append("前端和后端处理逻辑一致，问题可能在其他层面")
        
        if data_analysis.get('data_gaps', 0) > 0:
            report['diagnosis'].append(f"数据存在 {data_analysis['data_gaps']} 个缺口，可能影响回测结果")
        
        # 建议
        if all(result.get('success', False) for result in [frontend_sim, direct_service]):
            if all(result.get('trades', 0) == 0 for result in [frontend_sim, direct_service]):
                report['recommendations'].extend([
                    "检查策略逻辑，确保能在给定数据上产生交易信号",
                    "验证技术指标计算是否正确",
                    "确认交叉条件是否在数据中实际发生",
                    "考虑降低策略触发条件的严格程度"
                ])
            else:
                report['recommendations'].extend([
                    "后端逻辑一致，问题可能在前端状态管理",
                    "检查前端参数传递和状态更新",
                    "验证WebSocket消息处理逻辑",
                    "确认前端缓存或会话状态影响"
                ])
        
        print(f"\n💡 诊断结论:")
        for diag in report['diagnosis']:
            print(f"   - {diag}")
            
        print(f"\n🔧 修复建议:")
        for rec in report['recommendations']:
            print(f"   - {rec}")
        
        return report

async def main():
    """主分析函数"""
    print("🚀 启动前端后端差异深度诊断")
    
    analyzer = FrontendBackendDiscrepancyAnalyzer()
    
    try:
        report = await analyzer.analyze_discrepancy()
        
        # 保存详细报告
        with open('frontend_backend_discrepancy_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📄 详细报告已保存到 frontend_backend_discrepancy_report.json")
        
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())