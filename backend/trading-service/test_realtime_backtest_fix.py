#!/usr/bin/env python3
"""
测试实时回测API修复
"""
import asyncio
import aiohttp
import json
import os

# 测试配置
BASE_URL = "http://localhost:8001"
TEST_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2IiwidXNlcl9pZCI6NiwiZW1haWwiOiJwdWJsaWN0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjoxNzM0OTc2ODgzfQ.2TKSdg_8SZI3T7KKFqz3-5Gq8JD2KN4tPEuIpfAj_rw"

# 测试用简单MACD策略代码
SIMPLE_MACD_STRATEGY = '''
import pandas as pd
import numpy as np
from typing import Dict, Any, List

class MACDStrategy:
    """简单MACD策略"""
    
    def __init__(self):
        self.name = "MACD信号策略"
        self.position = 0
        self.signals = []
        
    def calculate_macd(self, prices: pd.Series, fast_period=12, slow_period=26, signal_period=9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast_period).mean()
        ema_slow = prices.ewm(span=slow_period).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
        
    def generate_signals(self, data: Dict[str, Any]) -> List[Dict]:
        """生成交易信号"""
        if 'close' not in data:
            return []
            
        closes = pd.Series(data['close'])
        macd_line, signal_line, histogram = self.calculate_macd(closes)
        
        signals = []
        for i in range(1, len(closes)):
            if (macd_line.iloc[i] > signal_line.iloc[i] and 
                macd_line.iloc[i-1] <= signal_line.iloc[i-1]):
                # 金叉买入信号
                signals.append({
                    'type': 'buy',
                    'price': closes.iloc[i],
                    'timestamp': i,
                    'confidence': 0.8
                })
            elif (macd_line.iloc[i] < signal_line.iloc[i] and 
                  macd_line.iloc[i-1] >= signal_line.iloc[i-1]):
                # 死叉卖出信号
                signals.append({
                    'type': 'sell', 
                    'price': closes.iloc[i],
                    'timestamp': i,
                    'confidence': 0.8
                })
        
        return signals

def strategy_signal(klines: List[Dict]) -> Dict:
    """策略主入口函数"""
    strategy = MACDStrategy()
    
    # 构建价格数据
    data = {
        'close': [k['close'] for k in klines],
        'high': [k['high'] for k in klines],
        'low': [k['low'] for k in klines],
        'volume': [k['volume'] for k in klines]
    }
    
    # 生成信号
    signals = strategy.generate_signals(data)
    
    return {
        'signals': signals,
        'strategy_name': strategy.name,
        'total_signals': len(signals)
    }
'''

async def test_realtime_backtest():
    """测试实时回测API"""
    
    # 测试配置
    test_config = {
        "strategy_code": SIMPLE_MACD_STRATEGY,
        "exchange": "okx",
        "product_type": "perpetual",
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "fee_rate": "vip0",
        "initial_capital": 10000,
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "data_type": "kline"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_JWT}"
    }
    
    print("🧪 开始测试实时回测API修复...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # 发起回测请求
            print(f"📡 发送回测请求到 {BASE_URL}/api/v1/realtime-backtest/start")
            
            async with session.post(
                f"{BASE_URL}/api/v1/realtime-backtest/start",
                headers=headers,
                json=test_config
            ) as response:
                
                print(f"📊 响应状态码: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 回测启动成功!")
                    print(f"📋 任务ID: {result.get('task_id', 'Unknown')}")
                    print(f"📋 状态: {result.get('status', 'Unknown')}")
                    print(f"📋 消息: {result.get('message', 'No message')}")
                    
                    task_id = result.get('task_id')
                    if task_id:
                        # 等待几秒后检查任务状态
                        await asyncio.sleep(3)
                        
                        print(f"\n📊 检查任务状态: {task_id}")
                        async with session.get(
                            f"{BASE_URL}/api/v1/realtime-backtest/status/{task_id}",
                            headers=headers
                        ) as status_response:
                            if status_response.status == 200:
                                status_data = await status_response.json()
                                print(f"📋 任务状态: {status_data.get('status', 'Unknown')}")
                                print(f"📋 进度: {status_data.get('progress', 0)}%")
                                
                                if status_data.get('logs'):
                                    print("📜 执行日志:")
                                    for log in status_data['logs'][-5:]:  # 显示最后5条日志
                                        print(f"   {log}")
                                        
                                if status_data.get('error_message'):
                                    print(f"❌ 错误信息: {status_data['error_message']}")
                            else:
                                print(f"❌ 获取状态失败: {status_response.status}")
                    
                    return True
                    
                else:
                    error_text = await response.text()
                    print(f"❌ 回测启动失败: {response.status}")
                    print(f"❌ 错误信息: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ 测试过程出错: {str(e)}")
        return False

async def test_strategy_validation():
    """测试策略代码验证"""
    print("\n🔍 测试策略代码验证...")
    
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {TEST_JWT}"
    }
    
    test_data = {
        "code": SIMPLE_MACD_STRATEGY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/v1/strategies/validate",
                headers=headers,
                json=test_data
            ) as response:
                
                print(f"📊 验证响应状态码: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 策略验证结果: {result}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ 策略验证失败: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ 验证测试出错: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 开始AI策略回测完整流程测试...")
    print(f"📡 测试目标: {BASE_URL}")
    print("=" * 60)
    
    # 运行测试
    asyncio.run(test_strategy_validation())
    asyncio.run(test_realtime_backtest())
    
    print("=" * 60)
    print("✅ 测试完成!")