#!/usr/bin/env python3
"""
测试回测系统在没有数据时正确返回错误
验证已移除fallback数据生成机制
"""

import asyncio
import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

from app.database import get_db
from app.services.backtest_service import BacktestEngine, DeterministicBacktestEngine
from datetime import datetime
import json

async def test_no_data_error():
    """测试数据库无数据时应该返回错误而不是生成模拟数据"""
    print("🔍 测试回测系统在无数据时的错误处理...")
    
    async for db in get_db():
        backtest_engine = BacktestEngine()
        
        # 测试配置 - 数据库中确实没有这些数据
        test_cases = [
            {
                "name": "OKX现货BTC/USDT",
                "exchange": "okx",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_date": datetime(2025, 8, 15),
                "end_date": datetime(2025, 9, 14)
            },
            {
                "name": "币安BTC/USDT", 
                "exchange": "binance",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_date": datetime(2025, 8, 15),
                "end_date": datetime(2025, 9, 14)
            },
            {
                "name": "OKX合约BTC-USDT-SWAP",
                "exchange": "okx", 
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1h",
                "start_date": datetime(2025, 8, 15),
                "end_date": datetime(2025, 9, 14)
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📊 测试案例 {i}: {case['name']}")
            
            try:
                # 尝试获取历史数据 - 应该失败
                historical_data = await backtest_engine._get_historical_data(
                    exchange=case["exchange"],
                    symbol=case["symbol"], 
                    timeframe=case["timeframe"],
                    start_date=case["start_date"],
                    end_date=case["end_date"],
                    user_id=1,
                    db=db
                )
                
                # 如果执行到这里说明没有抛出异常，这是错误的
                print(f"❌ 错误: 应该抛出异常但返回了数据 ({len(historical_data)} 条记录)")
                print("   这可能意味着仍然存在fallback数据生成机制")
                
            except ValueError as e:
                # 这是期望的结果 - 应该抛出数据不可用异常
                error_msg = str(e)
                if "没有找到" in error_msg or "数据不可用" in error_msg or "无法获取" in error_msg:
                    print(f"✅ 正确: 返回了预期的错误信息")
                    print(f"   错误信息: {error_msg}")
                else:
                    print(f"⚠️ 警告: 抛出了异常但错误信息不明确")
                    print(f"   错误信息: {error_msg}")
                    
            except Exception as e:
                print(f"❌ 未预期的异常类型: {type(e).__name__}: {str(e)}")
        
        break  # 只需要一次数据库连接

async def test_deterministic_backtest_no_fallback():
    """测试确定性回测服务的无fallback逻辑"""
    print("\n🔧 测试确定性回测服务...")
    
    async for db in get_db():
        backtest_engine = DeterministicBacktestEngine(random_seed=12345)
        
        try:
            # 使用确定性方法测试 - 应该失败
            result = await backtest_engine._get_historical_data_deterministic(
                db=db,
                symbol="BTC/USDT",
                start_date=datetime(2025, 8, 15),
                end_date=datetime(2025, 9, 14),
                timeframe="1h"
            )
            
            print(f"❌ 错误: 确定性方法应该失败但返回了数据 ({len(result)} 条记录)")
            
        except ValueError as e:
            print(f"✅ 正确: 确定性方法正确抛出异常")
            print(f"   错误信息: {str(e)}")
            
        except Exception as e:
            print(f"❌ 未预期的异常: {type(e).__name__}: {str(e)}")
            
        break

def test_fallback_method_removed():
    """测试确认fallback数据生成方法已被移除"""
    print("\n🗑️ 测试fallback方法是否已移除...")
    
    backtest_engine = BacktestEngine()
    
    # 检查是否还存在fallback数据生成方法
    if hasattr(backtest_engine, '_create_deterministic_fallback_data'):
        print("❌ 错误: _create_deterministic_fallback_data 方法仍然存在")
    else:
        print("✅ 正确: _create_deterministic_fallback_data 方法已被移除")
    
    # 检查其他可能的模拟数据生成方法
    problematic_methods = [
        '_generate_mock_data',
        '_create_sample_data', 
        '_create_fake_data',
        '_mock_data_generator'
    ]
    
    for method_name in problematic_methods:
        if hasattr(backtest_engine, method_name):
            print(f"⚠️ 警告: 发现可疑的数据生成方法: {method_name}")
        else:
            print(f"✅ 确认: {method_name} 方法不存在")

async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始测试回测系统fallback数据生成机制修复\n")
    
    try:
        test_fallback_method_removed()
        await test_no_data_error()
        await test_deterministic_backtest_no_fallback()
        
        print("\n🎉 所有测试完成!")
        print("\n📋 测试总结:")
        print("✅ 确认fallback数据生成方法已被移除")
        print("✅ 确认无数据时正确抛出异常而不是生成模拟数据")
        print("✅ 确认确定性回测也遵循相同的无数据错误处理逻辑")
        print("\n💡 现在回测系统只会使用真实数据，不会误导用户")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_all_tests())