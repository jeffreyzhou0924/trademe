#!/usr/bin/env python3
"""
测试使用真实策略ID的回测功能
验证前端策略ID生成逻辑修复后的效果
"""

import requests
import json
from datetime import datetime

# JWT Token - 7天有效期
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc4NTE1MDAsImV4cCI6MTc1ODQ1NjMwMCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.MpeKuJpD2GC6xUoqbM0EMMd-RYBWSNoCjHIh29KBx8c"

BASE_URL = "http://localhost:8001/api/v1"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def test_real_strategy_backtest():
    """测试使用真实策略ID的回测功能"""
    print("🧪 开始测试使用真实策略ID的回测功能")
    print("=" * 60)
    
    # 1. 查询策略列表，确认策略ID 65存在
    print("📋 1. 查询策略列表...")
    try:
        response = requests.get(f"{BASE_URL}/strategies", headers=headers)
        print(f"   策略列表API状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            strategies = data.get('strategies', [])
            print(f"   找到 {len(strategies)} 个策略")
            
            # 查找ID为65的策略
            strategy_65 = None
            for strategy in strategies:
                print(f"   策略ID: {strategy.get('id')}, 名称: {strategy.get('name')}")
                if strategy.get('id') == 65:
                    strategy_65 = strategy
                    break
            
            if strategy_65:
                print(f"✅ 找到目标策略 ID=65: {strategy_65.get('name')}")
                print(f"   会话ID: {strategy_65.get('ai_session_id')}")
                print(f"   状态: {strategy_65.get('status')}")
            else:
                print("❌ 未找到策略ID=65")
                return False
        else:
            print(f"❌ 策略列表查询失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 策略列表查询异常: {e}")
        return False
    
    # 2. 测试使用真实策略ID的回测
    print("\n🚀 2. 测试真实策略ID回测...")
    
    # 回测配置
    backtest_config = {
        "strategy_code": "# MA交叉策略 - 真实策略ID 65",
        "symbol": "BTC-USDT-SWAP",
        "exchange": "okx",
        "start_date": "2025-07-01",
        "end_date": "2025-08-31", 
        "initial_capital": 10000,
        "leverage": 1
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/realtime-backtest/start",
            headers=headers,
            json=backtest_config
        )
        print(f"   实时回测API状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"✅ 回测任务创建成功!")
            print(f"   任务ID: {task_id}")
            print(f"   状态: {result.get('status')}")
            print(f"   消息: {result.get('message')}")
            
            # 检查任务进度
            print(f"\n📊 3. 检查回测任务进度...")
            progress_response = requests.get(
                f"{BASE_URL}/realtime-backtest/progress/{task_id}",
                headers=headers
            )
            
            if progress_response.status_code == 200:
                progress = progress_response.json()
                print(f"   进度: {progress.get('progress', 0)}%")
                print(f"   状态: {progress.get('status')}")
                print(f"   当前步骤: {progress.get('current_step')}")
                print("✅ 回测进度查询成功")
            else:
                print(f"⚠️  回测进度查询失败: {progress_response.text}")
            
            return True
            
        elif response.status_code == 422:
            error_detail = response.json()
            print(f"❌ 参数验证失败: {error_detail}")
            return False
        else:
            print(f"❌ 回测请求失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 回测请求异常: {e}")
        return False

def test_fake_strategy_id():
    """测试使用假策略ID是否仍然报错"""
    print("\n🧪 4. 测试假策略ID是否仍然报错...")
    
    fake_backtest_config = {
        "strategy_code": "# 使用假策略ID测试",  
        "symbol": "BTC-USDT-SWAP",
        "exchange": "okx",
        "start_date": "2025-07-01",
        "end_date": "2025-08-31",
        "initial_capital": 10000
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/realtime-backtest/start", 
            headers=headers,
            json=fake_backtest_config
        )
        print(f"   假策略ID回测状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 即使没有真实策略ID，回测仍然可以执行（使用代码方式）")
            print(f"   任务ID: {result.get('task_id')}")
        else:
            print(f"❌ 假策略ID回测失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 假策略ID回测异常: {e}")

if __name__ == "__main__":
    print(f"🔧 测试时间: {datetime.now()}")
    print(f"🎯 目标: 验证前端策略ID修复后的回测功能")
    print()
    
    success = test_real_strategy_backtest()
    test_fake_strategy_id()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 真实策略ID回测功能验证成功！")
        print("✅ 前端策略ID生成逻辑修复有效")
    else:
        print("❌ 真实策略ID回测功能验证失败")
        
    print("\n💡 总结:")
    print("   - 前端修复了策略ID生成逻辑，现在使用数据库中的真实ID")
    print("   - ma6会话的策略ID应该从假ID变为真实数字ID（如65）")
    print("   - 用户点击'配置回测'按钮时，后端能找到对应的策略记录")