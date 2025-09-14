#!/usr/bin/env python3
"""
前后端回测结果差异深度分析
专门分析为什么策略生成信号但不产生实际交易的问题
"""

import sys
import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any
import pandas as pd
import numpy as np

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import get_db
from app.services.backtest_service import create_backtest_engine
from app.models.market_data import MarketData
from sqlalchemy import select, and_

class FrontendBackendDiscrepancyAnalyzer:
    """前后端回测差异分析器"""
    
    def __init__(self):
        self.results = {}
    
    async def analyze_discrepancy(self):
        """分析前后端回测差异"""
        print("🔍 开始前后端回测差异深度分析")
        print("=" * 70)
        
        # 步骤1：模拟前端配置进行回测
        await self._simulate_frontend_backtest()
        
        # 步骤2：直接调用服务端进行回测
        await self._direct_service_backtest()
        
        # 步骤3：分析数据完整性
        await self._analyze_data_integrity()
        
        # 生成分析报告
        self._generate_analysis_report()
    
    async def _simulate_frontend_backtest(self):
        """步骤1：模拟前端用户的回测配置"""
        print("\n🎯 步骤1：模拟前端用户回测配置")
        print("-" * 50)
        
        # 使用和前端完全相同的策略代码
        frontend_strategy = """from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"双均线交叉策略 + KDJ过滤\"\"\"
    
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
        if df is None or len(df) < 50:
            return None
        
        # 计算技术指标
        sma5 = self.calculate_sma(df['close'], 5)
        sma10 = self.calculate_sma(df['close'], 10)
        kdj_k, kdj_d, kdj_j = self.calculate_kdj(df['high'], df['low'], df['close'], 9, 3, 3)
        
        current_price = df['close'].iloc[-1]
        current_position = self.get_current_position()
        
        position_size = self.context.parameters.get('position_size', 10.0) / 100.0
        stop_loss_pct = self.context.parameters.get('stop_loss', 5.0) / 100.0
        take_profit_pct = self.context.parameters.get('take_profit', 10.0) / 100.0
        
        # 检测均线交叉信号
        golden_cross = self._detect_golden_cross(sma5, sma10)
        death_cross = self._detect_death_cross(sma5, sma10)
        
        signal = None
        
        # 原始严格的KDJ过滤条件
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
                        'strategy': 'sma_cross_kdj_strict',
                        'signal_reason': 'golden_cross_kdj_filter',
                        'sma5': sma5[-1],
                        'sma10': sma10[-1],
                        'kdj_k': kdj_k[-1],
                        'kdj_d': kdj_d[-1]
                    }
                )
        
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
                        'strategy': 'sma_cross_kdj_strict',
                        'signal_reason': 'death_cross_kdj_filter',
                        'sma5': sma5[-1],
                        'sma10': sma10[-1],
                        'kdj_k': kdj_k[-1],
                        'kdj_d': kdj_d[-1]
                    }
                )
        
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
    
    def calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                     k_period: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> tuple:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        rsv = 100 * (close - lowest_low) / (highest_high - lowest_low)
        rsv = rsv.fillna(50)
        k = rsv.ewm(span=k_smooth).mean()
        d = k.ewm(span=d_smooth).mean()
        j = 3 * k - 2 * d
        return k, d, j"""
        
        print("🧪 执行前端配置模拟回测...")
        try:
            engine = create_backtest_engine()
            
            frontend_params = {
                'strategy_code': frontend_strategy,
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
                    result = await engine.execute_backtest(frontend_params, user_id=1, db=db)
                    
                    if result.get('success'):
                        backtest_result = result.get('backtest_result', {})
                        trades = backtest_result.get('trades', [])
                        final_value = backtest_result.get('final_portfolio_value', 10000.0)
                        
                        print(f"✅ 前端模拟回测结果:")
                        print(f"   - 交易数量: {len(trades)}")
                        print(f"   - 最终价值: {final_value:.2f}")
                        print(f"   - 收益率: {(final_value - 10000.0) / 10000.0 * 100:.2f}%")
                        
                        self.results['frontend_simulation'] = {
                            'trades': len(trades),
                            'final_value': final_value,
                            'success': True
                        }
                    else:
                        error = result.get('error', '未知错误')
                        print(f"❌ 前端模拟回测失败: {error}")
                        self.results['frontend_simulation'] = {'success': False, 'error': error}
                    
                    break
                finally:
                    await db.close()
                    
        except Exception as e:
            print(f"❌ 前端模拟回测异常: {e}")
            self.results['frontend_simulation'] = {'success': False, 'error': str(e)}
    
    async def _direct_service_backtest(self):
        """步骤2：直接调用服务端回测"""
        print("\n🔧 步骤2：直接服务端回测测试")
        print("-" * 50)
        
        # 简化的双均线策略，不使用KDJ过滤
        simplified_strategy = """from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"纯双均线交叉策略 - 无KDJ过滤\"\"\"
    
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
        
        # 计算技术指标
        sma5 = self.calculate_sma(df['close'], 5)
        sma10 = self.calculate_sma(df['close'], 10)
        
        current_price = df['close'].iloc[-1]
        current_position = self.get_current_position()
        
        position_size = 0.1  # 10%
        stop_loss_pct = 0.05  # 5%
        take_profit_pct = 0.10  # 10%
        
        # 检测均线交叉信号
        golden_cross = self._detect_golden_cross(sma5, sma10)
        death_cross = self._detect_death_cross(sma5, sma10)
        
        signal = None
        
        # 无KDJ过滤的纯交叉信号
        if golden_cross:
            signal = TradingSignal(
                signal_type=SignalType.BUY,
                symbol="BTC-USDT-SWAP",
                price=current_price,
                quantity=position_size,
                stop_loss=current_price * (1 - stop_loss_pct),
                take_profit=current_price * (1 + take_profit_pct),
                metadata={
                    'strategy': 'pure_sma_cross',
                    'signal_reason': 'golden_cross_no_filter',
                    'sma5': sma5[-1],
                    'sma10': sma10[-1]
                }
            )
        
        elif death_cross:
            signal = TradingSignal(
                signal_type=SignalType.SELL,
                symbol="BTC-USDT-SWAP",
                price=current_price,
                quantity=position_size,
                stop_loss=current_price * (1 + stop_loss_pct),
                take_profit=current_price * (1 - take_profit_pct),
                metadata={
                    'strategy': 'pure_sma_cross',
                    'signal_reason': 'death_cross_no_filter',
                    'sma5': sma5[-1],
                    'sma10': sma10[-1]
                }
            )
        
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
        return current_cross and previous_cross"""
        
        print("🧪 执行纯双均线回测测试...")
        try:
            engine = create_backtest_engine()
            
            service_params = {
                'strategy_code': simplified_strategy,
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
                    result = await engine.execute_backtest(service_params, user_id=1, db=db)
                    
                    if result.get('success'):
                        backtest_result = result.get('backtest_result', {})
                        trades = backtest_result.get('trades', [])
                        final_value = backtest_result.get('final_portfolio_value', 10000.0)
                        
                        print(f"✅ 纯双均线回测结果:")
                        print(f"   - 交易数量: {len(trades)}")
                        print(f"   - 最终价值: {final_value:.2f}")
                        print(f"   - 收益率: {(final_value - 10000.0) / 10000.0 * 100:.2f}%")
                        
                        # 分析交易详情
                        entry_trades = [t for t in trades if t.get('type') == 'entry']
                        exit_trades = [t for t in trades if t.get('type') == 'exit']
                        
                        self.results['direct_service'] = {
                            'trades': len(trades),
                            'final_value': final_value,
                            'entry_trades': len(entry_trades),
                            'exit_trades': len(exit_trades),
                            'success': True
                        }
                        
                        if trades:
                            print(f"   - 开仓交易: {len(entry_trades)}")
                            print(f"   - 平仓交易: {len(exit_trades)}")
                    else:
                        error = result.get('error', '未知错误')
                        print(f"❌ 纯双均线回测失败: {error}")
                        self.results['direct_service'] = {'success': False, 'error': error}
                    
                    break
                finally:
                    await db.close()
                    
        except Exception as e:
            print(f"❌ 纯双均线回测异常: {e}")
            self.results['direct_service'] = {'success': False, 'error': str(e)}
    
    async def _analyze_data_integrity(self):
        """步骤3：分析数据完整性"""
        print("\n📊 步骤3：数据完整性分析")
        print("-" * 50)
        
        try:
            async for db in get_db():
                try:
                    # 查询数据完整性
                    query = select(MarketData).where(
                        and_(
                            MarketData.exchange == 'okx',
                            MarketData.symbol == 'BTC/USDT',
                            MarketData.timeframe == '1h',
                            MarketData.timestamp >= '2025-07-01',
                            MarketData.timestamp <= '2025-08-31'
                        )
                    ).order_by(MarketData.timestamp)
                    
                    result = await db.execute(query)
                    records = result.scalars().all()
                    
                    if records:
                        print(f"✅ 数据库记录:")
                        print(f"   - 总记录数: {len(records)}")
                        print(f"   - 时间范围: {records[0].timestamp} ~ {records[-1].timestamp}")
                        
                        # 检查数据缺口
                        timestamps = [r.timestamp for r in records]
                        expected_count = (datetime.strptime('2025-08-31', '%Y-%m-%d') - 
                                        datetime.strptime('2025-07-01', '%Y-%m-%d')).days * 24
                        gaps = expected_count - len(records)
                        
                        print(f"   - 预期记录: {expected_count}")
                        print(f"   - 数据缺口: {gaps}")
                        
                        self.results['data_analysis'] = {
                            'total_records': len(records),
                            'has_data': len(records) > 0,
                            'data_gaps': gaps,
                            'time_range': f"{records[0].timestamp} ~ {records[-1].timestamp}"
                        }
                    else:
                        print("❌ 未找到匹配的数据记录")
                        self.results['data_analysis'] = {
                            'total_records': 0,
                            'has_data': False,
                            'error': '未找到数据记录'
                        }
                    
                    break
                finally:
                    await db.close()
                    
        except Exception as e:
            print(f"❌ 数据完整性分析异常: {e}")
            self.results['data_analysis'] = {'error': str(e)}
    
    def _generate_analysis_report(self):
        """生成分析报告"""
        print("\n" + "=" * 70)
        print("📋 前后端回测差异分析报告")
        print("=" * 70)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'tests_performed': 3,
            'results': self.results,
            'diagnosis': [],
            'recommendations': []
        }
        
        # 诊断问题
        frontend_trades = self.results.get('frontend_simulation', {}).get('trades', 0)
        service_trades = self.results.get('direct_service', {}).get('trades', 0)
        has_data = self.results.get('data_analysis', {}).get('has_data', False)
        
        if frontend_trades == 0 and service_trades == 0:
            report['diagnosis'].append("策略没有产生任何交易信号 - 可能是策略逻辑问题或数据问题")
        elif service_trades > 0 and frontend_trades == 0:
            report['diagnosis'].append("KDJ过滤条件过于严格，阻止了交易执行")
        elif not has_data:
            report['diagnosis'].append("数据库中缺少必要的历史数据")
        
        if self.results.get('data_analysis', {}).get('data_gaps', 0) > 0:
            gaps = self.results.get('data_analysis', {}).get('data_gaps', 0)
            report['diagnosis'].append(f"数据存在 {gaps} 个缺口，可能影响回测结果")
        
        # 生成建议
        report['recommendations'] = [
            "检查策略逻辑，确保能在给定数据上产生交易信号",
            "验证技术指标计算是否正确",
            "确认交叉条件是否在数据中实际发生",
            "考虑降低策略触发条件的严格程度"
        ]
        
        print("🔍 诊断结果:")
        for i, diagnosis in enumerate(report['diagnosis'], 1):
            print(f"   {i}. {diagnosis}")
        
        print(f"\n💡 改进建议:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"   {i}. {rec}")
        
        print(f"\n📊 详细测试结果:")
        for test_name, result in self.results.items():
            if result.get('success', True):
                print(f"   ✅ {test_name}: 成功")
                if 'trades' in result:
                    print(f"      - 交易数量: {result['trades']}")
                if 'final_value' in result:
                    print(f"      - 最终价值: {result['final_value']:.2f}")
            else:
                print(f"   ❌ {test_name}: 失败")
        
        # 保存报告
        with open('frontend_backend_discrepancy_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📄 详细报告已保存到 frontend_backend_discrepancy_report.json")
        
        return report

async def main():
    """主分析函数"""
    print("🔍 启动前后端回测差异深度分析")
    
    analyzer = FrontendBackendDiscrepancyAnalyzer()
    
    try:
        await analyzer.analyze_discrepancy()
        print("\n🎉 差异分析完成")
        
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())