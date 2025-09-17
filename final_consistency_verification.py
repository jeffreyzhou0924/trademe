#!/usr/bin/env python3
"""
最终一致性验证测试 - 多次运行相同策略确保结果一致
"""

import subprocess
import json
import time
from datetime import datetime

def generate_jwt_token():
    """生成JWT令牌"""
    jwt_command = '''JWT_SECRET="trademe_super_secret_jwt_key_for_development_only_32_chars" node -e "
const jwt = require('jsonwebtoken');
const newToken = jwt.sign(
  { userId: '6', email: 'admin@trademe.com', membershipLevel: 'professional', type: 'access' },
  process.env.JWT_SECRET,
  { expiresIn: '7d', audience: 'trademe-app', issuer: 'trademe-user-service' }
);
console.log(newToken);
"'''

    result = subprocess.run(
        ['bash', '-c', jwt_command],
        capture_output=True,
        text=True,
        cwd='/root/trademe/backend/user-service'
    )

    return result.stdout.strip() if result.returncode == 0 else None

def run_single_backtest(test_id: int, token: str):
    """运行单次回测"""
    # 更复杂的策略，应该产生一些交易
    strategy_code = '''
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any

class UserStrategy(EnhancedBaseStrategy):
    def __init__(self, context=None):
        super().__init__()
        self.position_status = None  # None, 'long'
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

        # 计算移动平均线
        sma5 = self.calculate_sma(df['close'], 5)
        sma10 = self.calculate_sma(df['close'], 10)

        if len(sma5) < 2 or len(sma10) < 2:
            return None

        current_sma5 = sma5[-1]
        current_sma10 = sma10[-1]
        prev_sma5 = sma5[-2]
        prev_sma10 = sma10[-2]

        current_price = df['close'].iloc[-1]

        # 金叉信号
        if prev_sma5 <= prev_sma10 and current_sma5 > current_sma10 and self.position_status != 'long':
            self.position_status = 'long'
            self.entry_price = current_price
            return TradingSignal(
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                quantity=0.05,
                reason="MA金叉开多"
            )

        # 死叉信号
        elif prev_sma5 >= prev_sma10 and current_sma5 < current_sma10 and self.position_status == 'long':
            self.position_status = None
            self.entry_price = None
            return TradingSignal(
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=current_price,
                quantity=0.05,
                reason="MA死叉平多"
            )

        return None
'''

    config = {
        "strategy_code": strategy_code,
        "exchange": "okx",
        "product_type": "futures",
        "symbols": ["BTC-USDT-SWAP"],
        "timeframes": ["1h"],
        "initial_capital": 10000,
        "start_date": "2025-07-01",
        "end_date": "2025-08-31",
        "deterministic": True,
        "random_seed": 42  # 相同种子确保一致性
    }

    print(f"🔄 开始第{test_id}次回测...")

    # 启动回测
    curl_command = f'''curl -s -X POST "http://localhost:8001/api/v1/realtime-backtest/start" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {token}" \
-d '{json.dumps(config)}' '''

    result = subprocess.run(['bash', '-c', curl_command], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ 第{test_id}次回测启动失败: {result.stderr}")
        return None

    try:
        response = json.loads(result.stdout)
        task_id = response.get('task_id')

        if not task_id:
            print(f"❌ 第{test_id}次回测未获取到task_id: {response}")
            return None

        print(f"✅ 第{test_id}次回测任务 {task_id} 已启动")

        # 等待完成
        for i in range(30):  # 最多等待90秒
            time.sleep(3)

            progress_cmd = f'curl -s "http://localhost:8001/api/v1/realtime-backtest/progress/{task_id}" -H "Authorization: Bearer {token}"'
            progress_result = subprocess.run(['bash', '-c', progress_cmd], capture_output=True, text=True)

            if progress_result.returncode == 0:
                progress = json.loads(progress_result.stdout)
                status = progress.get('status')

                if status == 'completed':
                    # 获取结果
                    result_cmd = f'curl -s "http://localhost:8001/api/v1/realtime-backtest/results/{task_id}" -H "Authorization: Bearer {token}"'
                    result_response = subprocess.run(['bash', '-c', result_cmd], capture_output=True, text=True)

                    if result_response.returncode == 0:
                        final_result = json.loads(result_response.stdout)
                        results = final_result.get('results', {})

                        print(f"✅ 第{test_id}次回测完成")
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
                elif status == 'failed':
                    print(f"❌ 第{test_id}次回测失败: {progress.get('error_message', '未知错误')}")
                    return None

        print(f"⏰ 第{test_id}次回测超时")
        return None

    except json.JSONDecodeError:
        print(f"❌ 第{test_id}次结果解析失败: {result.stdout}")
        return None

def analyze_consistency(results):
    """分析一致性"""
    if len(results) < 2:
        print("❌ 有效结果不足2个，无法比较")
        return False

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

    return all_consistent

def main():
    print("🧪 最终一致性验证测试")
    print("=" * 40)

    # 生成令牌
    token = generate_jwt_token()
    if not token:
        print("❌ 无法生成JWT令牌")
        return

    # 运行3次回测
    test_count = 3
    results = []

    for i in range(test_count):
        result = run_single_backtest(i + 1, token)
        if result:
            results.append(result)

        # 间隔避免并发
        if i < test_count - 1:
            time.sleep(2)

    # 分析结果
    if results:
        is_consistent = analyze_consistency(results)

        # 保存结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/final_consistency_test_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({
                "test_timestamp": datetime.now().isoformat(),
                "consistency_check": is_consistent,
                "total_tests": len(results),
                "results": results
            }, f, indent=2)

        print(f"\n📝 结果保存到: {filename}")

        if is_consistent:
            print("\n🎉 一致性测试通过！回测引擎架构清理成功，结果完全一致！")
        else:
            print("\n⚠️ 一致性测试失败，存在不一致性问题。")
    else:
        print("\n❌ 没有有效的回测结果")

if __name__ == "__main__":
    main()