#!/usr/bin/env python3
"""
测试回测数据源修复
验证交易所过滤是否正常工作
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# 测试JWT token (用于admin@trademe.com)
TEST_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc3NTI4NTksImV4cCI6MTc1ODM1NzY1OSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.zVBuYEGVhSuvk7N_DdFe1LLKpEO0J4LLIj_BF-2UrlM"

BASE_URL = "http://localhost:8001"

async def test_binance_backtest_should_fail():
    """
    测试1: 币安回测应该失败
    因为数据库中只有OKX数据，没有币安数据
    """
    print("🧪 测试1: 币安回测数据验证（应该失败）")
    
    config = {
        "strategy_code": """
# 简单测试策略
def on_data(data):
    return {"signal": "hold"}
        """,
        "exchange": "binance",  # 使用币安交易所
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "initial_capital": 10000.0,
        "start_date": "2025-07-01",
        "end_date": "2025-07-31",
        "data_type": "kline"
    }
    
    headers = {
        "Authorization": f"Bearer {TEST_JWT}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/v1/realtime-backtest/start-ai-strategy",
                json=config,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 400 or response.status == 422:
                    print("✅ 币安回测正确被拒绝")
                    print(f"📋 错误信息: {result.get('detail', 'Unknown error')}")
                    return True
                elif response.status == 200:
                    task_id = result.get("task_id")
                    print(f"⚠️  币安回测意外成功，任务ID: {task_id}")
                    
                    # 检查任务状态
                    await asyncio.sleep(3)
                    async with session.get(
                        f"{BASE_URL}/api/v1/realtime-backtest/status/{task_id}",
                        headers=headers
                    ) as status_response:
                        status_result = await status_response.json()
                        if status_result.get("status") == "failed":
                            print("✅ 币安回测在执行过程中正确失败")
                            print(f"📋 失败信息: {status_result.get('error_message')}")
                            return True
                        else:
                            print("❌ 币安回测不应该成功！这是bug")
                            print(f"📊 状态: {status_result.get('status')}")
                            return False
                else:
                    print(f"❌ 意外的响应状态: {response.status}")
                    print(f"📋 响应内容: {result}")
                    return False
                    
        except Exception as e:
            print(f"❌ 测试请求失败: {e}")
            return False

async def test_okx_backtest_should_work():
    """
    测试2: OKX回测应该成功
    因为数据库中有OKX数据
    """
    print("\n🧪 测试2: OKX回测数据验证（应该成功）")
    
    config = {
        "strategy_code": """
# 简单测试策略
def on_data(data):
    return {"signal": "hold"}
        """,
        "exchange": "okx",  # 使用OKX交易所
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "initial_capital": 10000.0,
        "start_date": "2025-07-01",
        "end_date": "2025-07-31",
        "data_type": "kline"
    }
    
    headers = {
        "Authorization": f"Bearer {TEST_JWT}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/v1/realtime-backtest/start-ai-strategy",
                json=config,
                headers=headers
            ) as response:
                result = await response.json()
                
                if response.status == 200:
                    task_id = result.get("task_id")
                    print(f"✅ OKX回测成功启动，任务ID: {task_id}")
                    
                    # 检查任务状态
                    print("⏳ 等待回测完成...")
                    for i in range(30):  # 最多等待30秒
                        await asyncio.sleep(1)
                        async with session.get(
                            f"{BASE_URL}/api/v1/realtime-backtest/status/{task_id}",
                            headers=headers
                        ) as status_response:
                            status_result = await status_response.json()
                            status = status_result.get("status")
                            progress = status_result.get("progress", 0)
                            
                            print(f"📊 进度: {progress}% - {status_result.get('current_step', '未知步骤')}")
                            
                            if status == "completed":
                                print("✅ OKX回测成功完成")
                                results = status_result.get("results", {})
                                print(f"📈 总收益率: {results.get('total_return', 0):.2f}%")
                                return True
                            elif status == "failed":
                                print("❌ OKX回测失败")
                                print(f"📋 失败信息: {status_result.get('error_message')}")
                                return False
                    
                    print("⏰ 回测超时")
                    return False
                else:
                    print(f"❌ OKX回测启动失败: {response.status}")
                    print(f"📋 响应内容: {result}")
                    return False
                    
        except Exception as e:
            print(f"❌ 测试请求失败: {e}")
            return False

async def main():
    """运行所有测试"""
    print("🚀 开始测试回测数据源修复...")
    print(f"⏰ 测试时间: {datetime.now()}")
    
    # 测试币安回测（应该失败）
    binance_test_passed = await test_binance_backtest_should_fail()
    
    # 测试OKX回测（应该成功）
    okx_test_passed = await test_okx_backtest_should_work()
    
    # 输出测试结果
    print("\n" + "="*60)
    print("📋 测试结果汇总:")
    print(f"   币安回测验证: {'✅ 通过' if binance_test_passed else '❌ 失败'}")
    print(f"   OKX回测验证:  {'✅ 通过' if okx_test_passed else '❌ 失败'}")
    
    if binance_test_passed and okx_test_passed:
        print("\n🎉 所有测试通过！回测数据源修复成功！")
        print("💡 现在系统会：")
        print("   - 正确验证交易所数据可用性")
        print("   - 只使用匹配的交易所数据进行回测")
        print("   - 在数据不足时提供清晰的错误信息")
    else:
        print("\n⚠️  部分测试失败，需要进一步检查")
    
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())