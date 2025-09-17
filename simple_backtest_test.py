#!/usr/bin/env python3
"""
简单的回测一致性测试脚本
使用curl命令进行快速测试
"""

import json
import subprocess
import time
from datetime import datetime

def get_test_config():
    """获取测试配置"""
    return {
        "strategy_code": '''from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy:
    """MA金叉死叉策略 - 用于一致性测试"""

    def __init__(self):
        # 简化的策略，不依赖EnhancedBaseStrategy
        self.position_status = None
        self.entry_price = None
        self.sma5_values = []
        self.sma10_values = []

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

        sma5 = self.calculate_sma(df['close'], 5)
        sma10 = self.calculate_sma(df['close'], 10)

        if len(sma5) < 2 or len(sma10) < 2:
            return None

        current_sma5 = sma5[-1]
        current_sma10 = sma10[-1]
        prev_sma5 = sma5[-2]
        prev_sma10 = sma10[-2]

        current_price = df['close'].iloc[-1]

        # 检测金叉和死叉
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
            "description": "简化的MA金叉死叉策略，用于测试回测一致性",
            "parameters": {"ma_short": 5, "ma_long": 10}
        }''',
        "exchange": "okx",
        "product_type": "perpetual",
        "symbols": ["BTC-USDT-SWAP"],
        "timeframes": ["1h"],
        "fee_rate": "vip0_perp",
        "initial_capital": 10000,
        "start_date": "2025-07-01",
        "end_date": "2025-08-31",
        "data_type": "kline",
        "deterministic": True,
        "random_seed": 42
    }

def run_curl_backtest(test_id: int):
    """使用curl运行单次回测"""
    config = get_test_config()

    # JWT token
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTgwODk0MTksImV4cCI6MTc1ODY5NDIxOSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.w3959w5oLxxmzU79wx7NJ6pIXG25mgLBxp4sicaFq_k"

    # 创建临时配置文件
    config_file = f"/tmp/backtest_config_{test_id}.json"
    with open(config_file, 'w') as f:
        json.dump(config, f)

    print(f"🔄 开始第{test_id}次回测...")

    try:
        # 启动回测
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            'http://localhost:8001/api/v1/realtime-backtest/start',
            '-H', 'Content-Type: application/json',
            '-H', f'Authorization: Bearer {token}',
            '-d', f'@{config_file}'
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            print(f"❌ 第{test_id}次回测启动失败: {result.stderr}")
            return None

        response = json.loads(result.stdout)
        task_id = response.get('task_id')

        if not task_id:
            print(f"❌ 第{test_id}次回测未获取到task_id: {response}")
            return None

        print(f"✅ 第{test_id}次回测任务 {task_id} 已启动")

        # 等待完成并获取结果
        return wait_and_get_result(task_id, token, test_id)

    except Exception as e:
        print(f"❌ 第{test_id}次回测异常: {e}")
        return None
    finally:
        # 清理临时文件
        subprocess.run(['rm', '-f', config_file], capture_output=True)

def wait_and_get_result(task_id: str, token: str, test_id: int, max_wait: int = 60):
    """等待回测完成并获取结果"""
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            # 检查进度
            result = subprocess.run([
                'curl', '-s',
                f'http://localhost:8001/api/v1/realtime-backtest/progress/{task_id}',
                '-H', f'Authorization: Bearer {token}'
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                progress = json.loads(result.stdout)
                status = progress.get('status')

                if status == 'completed':
                    # 获取最终结果
                    result = subprocess.run([
                        'curl', '-s',
                        f'http://localhost:8001/api/v1/realtime-backtest/results/{task_id}',
                        '-H', f'Authorization: Bearer {token}'
                    ], capture_output=True, text=True, timeout=10)

                    if result.returncode == 0:
                        final_result = json.loads(result.stdout)
                        print(f"✅ 第{test_id}次回测完成")
                        return extract_metrics(final_result, test_id, task_id)

                elif status == 'failed':
                    print(f"❌ 第{test_id}次回测失败: {progress.get('error_message', '未知错误')}")
                    return None

            time.sleep(3)

        except Exception as e:
            print(f"⚠️ 第{test_id}次回测检查进度出错: {e}")
            time.sleep(3)

    print(f"⏰ 第{test_id}次回测超时")
    return None

def extract_metrics(result: dict, test_id: int, task_id: str):
    """提取关键指标"""
    try:
        results = result.get('results', {})
        return {
            'test_id': test_id,
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'total_return': results.get('total_return', 0),
            'sharpe_ratio': results.get('sharpe_ratio', 0),
            'max_drawdown': results.get('max_drawdown', 0),
            'win_rate': results.get('win_rate', 0),
            'total_trades': results.get('total_trades', 0)
        }
    except Exception as e:
        print(f"⚠️ 第{test_id}次结果解析失败: {e}")
        return None

def analyze_results(results: list):
    """分析结果一致性"""
    if len(results) < 2:
        print("❌ 有效结果不足2个，无法比较")
        return

    print(f"\n📊 回测一致性分析 (共{len(results)}个有效结果)")
    print("=" * 70)

    # 显示详细结果
    for result in results:
        print(f"第{result['test_id']}次: 收益率={result['total_return']:.4f}%, 胜率={result['win_rate']:.2f}%, 交易次数={result['total_trades']}")

    # 检查一致性
    metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']
    all_consistent = True

    print(f"\n🔍 一致性检查:")
    for metric in metrics:
        values = [r[metric] for r in results]
        unique_values = set(f"{v:.6f}" for v in values)

        if len(unique_values) == 1:
            print(f"✅ {metric}: 一致 ({values[0]:.6f})")
        else:
            all_consistent = False
            min_val, max_val = min(values), max(values)
            diff = max_val - min_val
            print(f"❌ {metric}: 不一致! 范围={min_val:.6f}~{max_val:.6f}, 差异={diff:.6f}")

    if all_consistent:
        print(f"\n🎉 结论: 所有回测结果完全一致!")
    else:
        print(f"\n⚠️ 结论: 发现不一致性!")

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"/tmp/backtest_consistency_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"📝 详细结果保存到: {filename}")

def main():
    """主函数"""
    print("🔬 简单回测一致性测试")
    print("=" * 40)

    test_count = 3
    results = []

    for i in range(test_count):
        result = run_curl_backtest(i + 1)
        if result:
            results.append(result)

        # 间隔避免并发
        if i < test_count - 1:
            time.sleep(2)

    analyze_results(results)

if __name__ == "__main__":
    main()