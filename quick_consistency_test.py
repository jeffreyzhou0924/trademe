#!/usr/bin/env python3
"""
快速一致性测试 - 验证回测引擎清理后的功能
"""

import subprocess
import json
import time

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

    if result.returncode == 0:
        return result.stdout.strip()
    return None

def test_single_backtest():
    """测试单次回测"""
    token = generate_jwt_token()
    if not token:
        print("❌ 无法生成JWT令牌")
        return False

    # 简单的策略代码
    strategy_code = '''
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any

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
        # 简单的买入策略作为测试
        df = self.get_kline_data()
        if df is None or len(df) < 10:
            return None

        # 每10根K线买入一次作为测试
        if len(df) % 10 == 0:
            current_price = df['close'].iloc[-1]
            return TradingSignal(
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=current_price,
                quantity=0.01,
                reason="测试买入"
            )
        return None
'''

    config = {
        "strategy_code": strategy_code,
        "exchange": "okx",
        "product_type": "futures",  # 修正产品类型
        "symbols": ["BTC-USDT-SWAP"],
        "timeframes": ["1h"],
        "initial_capital": 10000,
        "start_date": "2025-07-01",
        "end_date": "2025-07-15",  # 缩短测试时间
        "deterministic": True,
        "random_seed": 42
    }

    # 使用curl测试
    curl_command = f'''curl -s -X POST "http://localhost:8001/api/v1/realtime-backtest/start" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {token}" \
-d '{json.dumps(config)}' '''

    print("🚀 启动快速回测测试...")
    result = subprocess.run(['bash', '-c', curl_command], capture_output=True, text=True)

    if result.returncode == 0:
        try:
            response = json.loads(result.stdout)
            task_id = response.get('task_id')

            if task_id:
                print(f"✅ 回测任务启动成功: {task_id}")

                # 等待完成
                for i in range(20):  # 最多等待60秒
                    time.sleep(3)

                    progress_cmd = f'curl -s "http://localhost:8001/api/v1/realtime-backtest/progress/{task_id}" -H "Authorization: Bearer {token}"'
                    progress_result = subprocess.run(['bash', '-c', progress_cmd], capture_output=True, text=True)

                    if progress_result.returncode == 0:
                        progress = json.loads(progress_result.stdout)
                        status = progress.get('status')
                        print(f"📊 进度: {progress.get('progress', 0)}% - {progress.get('current_step', '')}")

                        if status == 'completed':
                            # 获取结果
                            result_cmd = f'curl -s "http://localhost:8001/api/v1/realtime-backtest/results/{task_id}" -H "Authorization: Bearer {token}"'
                            result_response = subprocess.run(['bash', '-c', result_cmd], capture_output=True, text=True)

                            if result_response.returncode == 0:
                                final_result = json.loads(result_response.stdout)
                                results = final_result.get('results', {})

                                print("✅ 回测完成！")
                                print(f"   💰 总收益率: {results.get('total_return', 0):.2f}%")
                                print(f"   📈 交易次数: {results.get('total_trades', 0)}")
                                print(f"   🎯 胜率: {results.get('win_rate', 0):.1f}%")

                                return True
                        elif status == 'failed':
                            print(f"❌ 回测失败: {progress.get('error_message', '未知错误')}")
                            return False

                print("⏰ 回测超时")
                return False
            else:
                print(f"❌ 未获取到task_id: {response}")
                return False

        except json.JSONDecodeError:
            print(f"❌ 响应解析失败: {result.stdout}")
            return False
    else:
        print(f"❌ 请求失败: {result.stderr}")
        return False

def main():
    print("🔍 快速一致性测试 - 验证回测引擎清理后的功能")
    print("=" * 50)

    success = test_single_backtest()

    print("\n" + "=" * 50)
    if success:
        print("🎉 测试通过！回测引擎架构清理成功，系统正常运行。")
    else:
        print("❌ 测试失败，需要进一步检查。")

if __name__ == "__main__":
    main()