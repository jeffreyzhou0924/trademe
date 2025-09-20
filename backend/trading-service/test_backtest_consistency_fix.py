#!/usr/bin/env python3
"""
回测一致性修复验证测试
测试修复后的回测引擎是否能产生100%一致的结果
"""

import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from loguru import logger

# 配置简洁的日志输出
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

class BacktestConsistencyValidator:
    """回测一致性验证器"""

    def __init__(self):
        self.test_results = []

    async def run_consistency_test(self, iterations: int = 3) -> Dict[str, Any]:
        """运行一致性测试"""
        logger.info(f"🚀 开始回测一致性验证测试 ({iterations}次迭代)")

        # 准备测试策略代码 - 简单的MA策略确保可重现性
        test_strategy_code = '''
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
import pandas as pd

class UserStrategy(EnhancedBaseStrategy):
    """确定性MA策略 - 用于一致性测试"""

    def __init__(self, context):
        super().__init__(context)
        self.position_status = None
        self.entry_price = None

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

        # 计算MA - 使用确定性计算
        sma5 = self.calculate_sma(df['close'], 5)
        sma10 = self.calculate_sma(df['close'], 10)

        if len(sma5) < 2 or len(sma10) < 2:
            return None

        current_sma5 = sma5[-1]
        current_sma10 = sma10[-1]
        prev_sma5 = sma5[-2]
        prev_sma10 = sma10[-2]

        current_price = df['close'].iloc[-1]

        # 检测金叉和死叉 - 确定性逻辑
        golden_cross = prev_sma5 <= prev_sma10 and current_sma5 > current_sma10
        death_cross = prev_sma5 >= prev_sma10 and current_sma5 < current_sma10

        position_size_pct = 0.05

        # 金叉信号处理
        if golden_cross and self.position_status != 'long':
            self.position_status = 'long'
            self.entry_price = current_price
            return TradingSignal(
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                quantity=position_size_pct,
                reason="金叉开多"
            )

        # 死叉信号处理
        elif death_cross and self.position_status == 'long':
            self.position_status = None
            self.entry_price = None
            return TradingSignal(
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=current_price,
                quantity=position_size_pct,
                reason="死叉平多"
            )

        return None

    def get_strategy_info(self) -> Dict[str, Any]:
        return {
            "name": "一致性测试MA策略",
            "description": "确定性MA金叉死叉策略，用于测试回测一致性",
            "parameters": {"ma_short": 5, "ma_long": 10}
        }
'''

        # 回测配置
        test_params = {
            'strategy_code': test_strategy_code,
            'exchange': 'okx',
            'product_type': 'perpetual',
            'symbols': ['BTC-USDT-SWAP'],
            'timeframes': ['1h'],
            'fee_rate': 'vip0_perp',
            'initial_capital': 10000,
            'start_date': '2025-07-01',
            'end_date': '2025-08-31',
            'data_type': 'kline',
            'deterministic': True,
            'random_seed': 42
        }

        results = []

        try:
            # 导入必要的模块
            from app.services.stateless_backtest_adapter import StatelessBacktestAdapter
            from app.database import get_db

            # 执行多次回测并比较结果
            for i in range(iterations):
                logger.info(f"🔄 执行第 {i+1} 次确定性回测...")

                # 获取数据库会话
                db_generator = get_db()
                db_session = await db_generator.__anext__()

                try:
                    # 创建无状态回测引擎
                    engine = StatelessBacktestAdapter()

                    # 执行回测
                    result = await engine.execute_backtest(
                        params=test_params,
                        user_id=1,
                        db=db_session
                    )

                    if result['success']:
                        backtest_result = result['backtest_result']
                        performance = backtest_result['performance_metrics']

                        results.append({
                            'iteration': i + 1,
                            'final_capital': performance.get('final_capital', 0),
                            'total_return': performance.get('total_return', 0),
                            'max_drawdown': performance.get('max_drawdown', 0),
                            'sharpe_ratio': performance.get('sharpe_ratio', 0),
                            'total_trades': performance.get('total_trades', 0),
                            'win_rate': performance.get('win_rate', 0),
                            'volatility': performance.get('volatility', 0),
                            'profit_factor': performance.get('profit_factor', 0)
                        })

                        logger.info(f"✅ 第 {i+1} 次回测完成 - 收益率: {performance.get('total_return', 0):.4f}, 交易数: {performance.get('total_trades', 0)}")
                    else:
                        logger.error(f"❌ 第 {i+1} 次回测失败: {result.get('error', '未知错误')}")
                        return {"success": False, "error": f"回测执行失败: {result.get('error')}"}

                finally:
                    await db_session.close()

        except Exception as e:
            logger.error(f"❌ 一致性测试执行失败: {e}")
            return {"success": False, "error": str(e)}

        # 分析一致性
        consistency_analysis = self._analyze_consistency(results)

        return {
            "success": True,
            "iterations": iterations,
            "results": results,
            "consistency_analysis": consistency_analysis
        }

    def _analyze_consistency(self, results: List[Dict]) -> Dict[str, Any]:
        """分析结果一致性"""
        if len(results) < 2:
            return {"consistent": True, "message": "样本不足，无法判断一致性"}

        # 检查关键指标的一致性
        metrics_to_check = [
            'final_capital', 'total_return', 'max_drawdown',
            'sharpe_ratio', 'total_trades', 'win_rate'
        ]

        inconsistencies = []

        for metric in metrics_to_check:
            values = [result[metric] for result in results]
            unique_values = set([round(v, 8) for v in values])  # 8位小数精度

            if len(unique_values) > 1:
                inconsistencies.append({
                    'metric': metric,
                    'values': values,
                    'variance': max(values) - min(values)
                })

        is_consistent = len(inconsistencies) == 0

        analysis = {
            "consistent": is_consistent,
            "inconsistencies": inconsistencies,
            "message": "回测结果100%一致 ✅" if is_consistent else f"发现 {len(inconsistencies)} 个不一致指标 ❌"
        }

        return analysis

async def main():
    """主测试函数"""
    validator = BacktestConsistencyValidator()

    logger.info("🔧 开始验证回测一致性修复效果...")

    # 测试5次迭代确保一致性
    result = await validator.run_consistency_test(iterations=5)

    if result['success']:
        logger.info("\n" + "="*60)
        logger.info("📊 回测一致性验证结果")
        logger.info("="*60)

        consistency = result['consistency_analysis']
        logger.info(f"一致性状态: {consistency['message']}")

        if consistency['consistent']:
            logger.info("🎉 回测一致性修复成功！所有迭代结果完全一致")

            # 显示基准结果
            if result['results']:
                base_result = result['results'][0]
                logger.info(f"📈 基准回测结果:")
                logger.info(f"   总收益率: {base_result['total_return']:.4f}")
                logger.info(f"   最终资金: {base_result['final_capital']:.2f}")
                logger.info(f"   最大回撤: {base_result['max_drawdown']:.4f}")
                logger.info(f"   夏普比率: {base_result['sharpe_ratio']:.4f}")
                logger.info(f"   总交易数: {base_result['total_trades']}")
                logger.info(f"   胜率: {base_result['win_rate']:.4f}")
        else:
            logger.error("❌ 一致性验证失败，发现不一致指标:")
            for inconsistency in consistency['inconsistencies']:
                logger.error(f"   {inconsistency['metric']}: {inconsistency['values']} (方差: {inconsistency['variance']:.8f})")
    else:
        logger.error(f"❌ 一致性测试失败: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())