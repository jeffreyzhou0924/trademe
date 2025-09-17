#!/usr/bin/env python3
"""
回测一致性调试工具
用于深入分析回测结果不一致的根本原因
"""

import asyncio
import json
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any
import aiohttp
import pandas as pd
import numpy as np

class BacktestConsistencyTester:
    """回测一致性测试器"""

    def __init__(self):
        self.base_url = "http://localhost:8001/api/v1"
        self.results = []

    def get_auth_headers(self):
        """获取认证头"""
        # 使用有效的JWT token
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc4MzQ3MDUsImV4cCI6MTc1ODQzOTUwNSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.C3UbHbUYj5O-RFLf6y12ta1rpkscIKWrz8sAkS5XZaA"
        return {"Authorization": f"Bearer {token}"}

    async def test_consecutive_backtests(self, count: int = 5):
        """测试连续多次回测的一致性"""
        print(f"🧪 开始连续{count}次回测一致性测试...")

        # 固定的策略代码
        strategy_code = '''from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    """简化MA金叉死叉策略 - 用于一致性测试"""

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

        # 简化的MA策略
        ma5 = self.calculate_sma(df['close'], 5)
        ma10 = self.calculate_sma(df['close'], 10)

        if len(ma5) < 2 or len(ma10) < 2:
            return None

        current_price = df['close'].iloc[-1]
        current_ma5 = ma5[-1]
        current_ma10 = ma10[-1]
        prev_ma5 = ma5[-2]
        prev_ma10 = ma10[-2]

        # 金叉信号
        if prev_ma5 <= prev_ma10 and current_ma5 > current_ma10:
            if self.position_status != 'long':
                self.position_status = 'long'
                self.entry_price = current_price
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    symbol=self.symbol,
                    price=current_price,
                    quantity=0.05,
                    reason="MA金叉买入"
                )

        # 死叉信号
        elif prev_ma5 >= prev_ma10 and current_ma5 < current_ma10:
            if self.position_status == 'long':
                self.position_status = None
                self.entry_price = None
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    symbol=self.symbol,
                    price=current_price,
                    quantity=0.05,
                    reason="MA死叉卖出"
                )

        return None

    def get_strategy_info(self) -> Dict[str, Any]:
        return {
            "name": "一致性测试MA策略",
            "description": "简化的MA金叉死叉策略，用于测试回测一致性",
            "parameters": {"ma_short": 5, "ma_long": 10}
        }'''

        # 固定的回测配置
        backtest_config = {
            "strategy_code": strategy_code,
            "exchange": "okx",
            "product_type": "perpetual",
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": ["1h"],
            "fee_rate": "vip0_perp",
            "initial_capital": 10000,
            "start_date": "2025-07-01",
            "end_date": "2025-08-31",
            "data_type": "kline",
            # 启用确定性回测
            "deterministic": True,
            "random_seed": 42
        }

        results = []

        async with aiohttp.ClientSession() as session:
            for i in range(count):
                print(f"\n🔄 执行第 {i+1} 次回测...")

                try:
                    # 启动回测
                    async with session.post(
                        f"{self.base_url}/realtime-backtest/start",
                        json=backtest_config,
                        headers=self.get_auth_headers()
                    ) as response:
                        if response.status != 200:
                            print(f"❌ 回测启动失败: {response.status}")
                            continue

                        result = await response.json()
                        task_id = result["task_id"]
                        print(f"✅ 回测任务 {task_id} 已启动")

                    # 等待回测完成
                    await asyncio.sleep(2)
                    final_result = await self.wait_for_completion(session, task_id)

                    if final_result:
                        # 提取关键指标
                        metrics = final_result.get("results", {})
                        test_result = {
                            "test_id": i + 1,
                            "task_id": task_id,
                            "timestamp": datetime.now().isoformat(),
                            "total_return": metrics.get("total_return", 0),
                            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                            "max_drawdown": metrics.get("max_drawdown", 0),
                            "win_rate": metrics.get("win_rate", 0),
                            "total_trades": metrics.get("total_trades", 0),
                            "raw_result": final_result
                        }
                        results.append(test_result)
                        print(f"📊 第{i+1}次结果: 收益率={test_result['total_return']:.2f}%, 胜率={test_result['win_rate']:.1f}%")

                    # 间隔时间避免并发
                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"❌ 第{i+1}次回测失败: {e}")

        # 分析结果一致性
        await self.analyze_consistency(results)
        return results

    async def wait_for_completion(self, session: aiohttp.ClientSession, task_id: str, timeout: int = 60):
        """等待回测完成"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                async with session.get(
                    f"{self.base_url}/realtime-backtest/progress/{task_id}",
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        progress = await response.json()
                        if progress.get("status") == "completed":
                            # 获取最终结果
                            async with session.get(
                                f"{self.base_url}/realtime-backtest/results/{task_id}",
                                headers=self.get_auth_headers()
                            ) as result_response:
                                if result_response.status == 200:
                                    return await result_response.json()
                        elif progress.get("status") == "failed":
                            print(f"❌ 回测任务失败: {progress.get('error_message')}")
                            return None

                await asyncio.sleep(2)

            except Exception as e:
                print(f"⚠️ 获取进度时出错: {e}")
                await asyncio.sleep(2)

        print(f"⏰ 回测任务 {task_id} 超时")
        return None

    async def analyze_consistency(self, results: List[Dict]):
        """分析结果一致性"""
        if len(results) < 2:
            print("❌ 结果数量不足，无法进行一致性分析")
            return

        print(f"\n📈 回测一致性分析 (共{len(results)}次测试)")
        print("=" * 80)

        # 提取关键指标
        metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']

        print("📊 详细结果对比:")
        for i, result in enumerate(results):
            print(f"第{i+1}次: ", end="")
            for metric in metrics:
                value = result.get(metric, 0)
                if metric in ['total_return', 'max_drawdown', 'win_rate']:
                    print(f"{metric}={value:.2f}% ", end="")
                else:
                    print(f"{metric}={value:.2f} ", end="")
            print()

        # 计算差异
        print(f"\n🔍 一致性检查:")
        all_consistent = True

        for metric in metrics:
            values = [result.get(metric, 0) for result in results]
            unique_values = set(f"{v:.6f}" for v in values)  # 保留6位小数进行比较

            if len(unique_values) == 1:
                print(f"✅ {metric}: 完全一致 ({values[0]:.6f})")
            else:
                all_consistent = False
                min_val = min(values)
                max_val = max(values)
                diff = max_val - min_val
                print(f"❌ {metric}: 不一致! 范围={min_val:.6f}~{max_val:.6f}, 差异={diff:.6f}")
                print(f"   具体值: {[f'{v:.6f}' for v in values]}")

        if all_consistent:
            print(f"\n🎉 结论: 所有{len(results)}次回测结果完全一致!")
        else:
            print(f"\n⚠️ 结论: 发现回测结果不一致性问题!")

        # 保存详细结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/backtest_consistency_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"📝 详细结果已保存到: {filename}")

    async def test_parallel_backtests(self, count: int = 3):
        """测试并行回测的一致性"""
        print(f"🚀 开始并行{count}次回测一致性测试...")

        # 使用相同的策略和配置...
        # 但这次并发执行

        tasks = []
        for i in range(count):
            task = self.run_single_backtest(f"parallel_{i+1}")
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分析并行执行的一致性
        valid_results = [r for r in results if not isinstance(r, Exception)]
        await self.analyze_consistency(valid_results)

        return valid_results

async def main():
    """主测试函数"""
    tester = BacktestConsistencyTester()

    print("🔬 回测一致性深度调查工具")
    print("=" * 50)

    # 测试1: 连续回测一致性
    print("\n📋 测试1: 连续回测一致性")
    consecutive_results = await tester.test_consecutive_backtests(5)

    # 测试2: 并行回测一致性
    print("\n📋 测试2: 并行回测一致性")
    # parallel_results = await tester.test_parallel_backtests(3)

    print("\n🎯 调查完成!")

if __name__ == "__main__":
    asyncio.run(main())