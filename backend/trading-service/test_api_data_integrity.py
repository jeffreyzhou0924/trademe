#!/usr/bin/env python3
"""
API数据完整性端点测试
测试新增的数据验证API功能
"""

import requests
import json
import time
from datetime import datetime, timedelta


# 测试配置
BASE_URL = "http://localhost:8001/api/v1"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2IiwiZXhwIjoxNzI2NTg0NTg4fQ.0VRRa8"  # 测试用token

HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "Content-Type": "application/json"
}

# 问题策略代码（与实际问题相同）
PROBLEM_STRATEGY_CODE = '''from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    """MA5和MA10金叉死叉策略"""
    
    def __init__(self):
        super().__init__()
        self.last_signal = None
        
    def get_data_requirements(self) -> List[DataRequest]:
        """定义策略所需的数据源"""
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP",  # 问题：硬编码为合约
                timeframe="1h",
                required=True
            )
        ]
        
    async def on_data_update(self, data_type: str, data: Dict[str, Any]):
        """策略逻辑"""
        return None
'''

def test_check_backtest_config():
    """测试回测配置检查API"""
    print("🔍 测试回测配置检查API...")
    
    # 测试数据不匹配的情况
    payload = {
        "strategy_code": PROBLEM_STRATEGY_CODE,
        "exchange": "okx",
        "product_type": "spot",  # 现货配置
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "start_date": "2025-08-15",
        "end_date": "2025-09-14"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/data-integrity/check-backtest-config",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API响应成功")
            print(f"   状态: {result.get('status')}")
            print(f"   消息: {result.get('message')}")
            print(f"   可以继续: {result.get('can_proceed')}")
            print(f"   建议数量: {len(result.get('suggestions', []))}")
            
            if result.get('strategy_fixes'):
                print(f"   策略修复: 可用")
                print(f"   修复更改: {result['strategy_fixes'].get('changes', [])}")
            
        else:
            print(f"❌ API响应失败: {response.status_code}")
            print(f"   错误: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")


def test_get_available_data():
    """测试获取可用数据API"""
    print("\n📊 测试获取可用数据API...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/data-integrity/available-data",
            headers=HEADERS,
            params={"exchange": "okx"},
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 获取可用数据成功")
            print(f"   交易所: {result.get('exchange')}")
            print(f"   总交易对数: {result.get('total_symbols')}")
            print(f"   消息: {result.get('message')}")
            
            # 显示前3个交易对详情
            symbols = result.get('symbols', [])
            for i, symbol_info in enumerate(symbols[:3]):
                print(f"   交易对{i+1}: {symbol_info['symbol']} ({symbol_info['data_count']}条数据)")
                
        else:
            print(f"❌ 获取可用数据失败: {response.status_code}")
            print(f"   错误: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")


def test_apply_strategy_fix():
    """测试应用策略修复API"""
    print("\n🔧 测试应用策略修复API...")
    
    payload = {
        "strategy_code": PROBLEM_STRATEGY_CODE,
        "exchange": "okx", 
        "product_type": "spot",
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "start_date": "2025-08-15",
        "end_date": "2025-09-14"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/data-integrity/apply-strategy-fix",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 策略修复成功")
            print(f"   成功: {result.get('success')}")
            print(f"   消息: {result.get('message')}")
            print(f"   可以继续回测: {result.get('can_proceed_with_backtest')}")
            print(f"   修复更改: {result.get('changes_made', [])}")
            
            # 显示修复后的代码片段
            fixed_code = result.get('fixed_strategy_code', '')
            if fixed_code:
                lines = fixed_code.split('\n')
                print("   修复后的关键代码:")
                for i, line in enumerate(lines[18:25], 19):  # 显示关键部分
                    if 'symbol' in line:
                        print(f"     {i:2d}: {line.strip()}")
                        
        else:
            print(f"❌ 策略修复失败: {response.status_code}")
            print(f"   错误: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")


def test_integration_with_realtime_backtest():
    """测试与实时回测的集成"""
    print("\n🚀 测试与实时回测API的集成...")
    
    # 首先检查配置
    check_payload = {
        "strategy_code": PROBLEM_STRATEGY_CODE,
        "exchange": "okx",
        "product_type": "spot",
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"], 
        "start_date": "2025-08-15",
        "end_date": "2025-09-14"
    }
    
    try:
        # 1. 检查配置
        check_response = requests.post(
            f"{BASE_URL}/data-integrity/check-backtest-config",
            headers=HEADERS,
            json=check_payload,
            timeout=30
        )
        
        if check_response.status_code != 200:
            print(f"❌ 配置检查失败: {check_response.status_code}")
            return
        
        check_result = check_response.json()
        print(f"配置检查结果: {check_result.get('status')}")
        
        # 2. 如果需要修复，先修复策略
        fixed_strategy_code = PROBLEM_STRATEGY_CODE
        if check_result.get('strategy_fixes') and check_result['strategy_fixes'].get('can_auto_fix'):
            fix_response = requests.post(
                f"{BASE_URL}/data-integrity/apply-strategy-fix", 
                headers=HEADERS,
                json=check_payload,
                timeout=30
            )
            
            if fix_response.status_code == 200:
                fix_result = fix_response.json()
                fixed_strategy_code = fix_result.get('fixed_strategy_code', PROBLEM_STRATEGY_CODE)
                print(f"✅ 策略已自动修复")
            else:
                print(f"⚠️ 策略修复失败，使用原始代码")
        
        # 3. 使用修复后的代码进行回测
        backtest_payload = {
            "strategy_code": fixed_strategy_code,
            "exchange": "okx",
            "product_type": "spot",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "fee_rate": "vip0",
            "initial_capital": 10000,
            "start_date": "2025-08-15",
            "end_date": "2025-09-14",
            "data_type": "kline"
        }
        
        print("📈 开始实时回测...")
        backtest_response = requests.post(
            f"{BASE_URL}/realtime-backtest/start",
            headers=HEADERS,
            json=backtest_payload,
            timeout=30
        )
        
        if backtest_response.status_code == 200:
            backtest_result = backtest_response.json()
            print(f"✅ 回测已启动: {backtest_result.get('task_id')}")
            print(f"   WebSocket URL: {backtest_result.get('websocket_url')}")
        else:
            print(f"❌ 回测启动失败: {backtest_response.status_code}")
            print(f"   错误: {backtest_response.text}")
            
    except Exception as e:
        print(f"❌ 集成测试失败: {str(e)}")


def main():
    """运行所有API测试"""
    print("🚀 开始API数据完整性端点测试")
    print(f"基础URL: {BASE_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    test_check_backtest_config()
    test_get_available_data()
    test_apply_strategy_fix()
    test_integration_with_realtime_backtest()
    
    print("\n" + "=" * 50)
    print("✅ 所有API测试完成！")


if __name__ == "__main__":
    main()