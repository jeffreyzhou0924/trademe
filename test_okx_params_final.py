#!/usr/bin/env python3
"""
最终测试OKX API参数的正确使用方式
基于之前的测试，找出正确的时间参数组合
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_correct_time_params():
    """测试正确的时间参数使用方式"""
    print("🔍 测试正确的OKX API时间参数使用...")
    
    # 最近3天的时间范围
    end_time = datetime(2025, 8, 31, 23, 59, 59)
    start_time = datetime(2025, 8, 29, 0, 0, 0)
    
    end_timestamp = int(end_time.timestamp() * 1000)
    start_timestamp = int(start_time.timestamp() * 1000)
    
    print(f"📅 目标时间范围: {start_time} 到 {end_time}")
    print(f"📅 时间戳: {start_timestamp} - {end_timestamp}")
    
    # 测试不同的参数组合
    test_cases = [
        {
            "name": "只使用after参数",
            "params": {"after": str(start_timestamp)},
            "description": "获取晚于开始时间的数据"
        },
        {
            "name": "只使用before参数", 
            "params": {"before": str(end_timestamp)},
            "description": "获取早于结束时间的数据"
        },
        {
            "name": "同时使用after和before",
            "params": {"after": str(start_timestamp), "before": str(end_timestamp)},
            "description": "获取时间范围内的数据"
        },
        {
            "name": "不使用时间参数",
            "params": {},
            "description": "获取最新数据"
        }
    ]
    
    success_cases = []
    
    for case in test_cases:
        print(f"\n🔍 测试: {case['name']}")
        print(f"📋 描述: {case['description']}")
        
        base_params = {
            "instId": "BTC-USDT-SWAP",
            "bar": "1H", 
            "limit": "20"
        }
        base_params.update(case['params'])
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://www.okx.com/api/v5/market/candles"
                
                async with session.get(url, params=base_params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("code") == "0":
                            candles = data.get("data", [])
                            
                            if candles:
                                print(f"✅ 成功获取 {len(candles)} 条数据")
                                
                                # 分析时间范围
                                timestamps = [int(c[0]) for c in candles]
                                earliest_time = datetime.fromtimestamp(min(timestamps) / 1000)
                                latest_time = datetime.fromtimestamp(max(timestamps) / 1000)
                                
                                print(f"📅 实际数据时间范围: {earliest_time} 到 {latest_time}")
                                
                                # 检查是否在目标时间范围内
                                in_range_count = sum(1 for ts in timestamps 
                                                   if start_timestamp <= ts <= end_timestamp)
                                
                                print(f"📊 目标范围内数据: {in_range_count}/{len(candles)} 条")
                                
                                if in_range_count > 0:
                                    success_cases.append(case['name'])
                                    print(f"🎯 此参数组合有效!")
                            else:
                                print(f"⚠️ 返回0条数据")
                        else:
                            print(f"❌ API错误: {data.get('msg')}")
                    else:
                        print(f"❌ HTTP错误: {response.status}")
                        
        except Exception as e:
            print(f"❌ 请求异常: {e}")
    
    print(f"\n📊 测试总结:")
    print(f"有效的参数组合: {success_cases}")
    
    return success_cases

async def test_pagination_strategy():
    """测试分页策略"""
    print(f"\n🔍 测试分页策略...")
    
    # 获取最新数据作为起点
    async with aiohttp.ClientSession() as session:
        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": "BTC-USDT-SWAP", "bar": "1H", "limit": "10"}
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0" and data.get("data"):
                    latest_candles = data["data"]
                    oldest_timestamp = int(latest_candles[-1][0])  # 最早的时间戳
                    
                    print(f"📊 最新10条数据的时间范围:")
                    for i, candle in enumerate(latest_candles):
                        ts = int(candle[0])
                        dt = datetime.fromtimestamp(ts / 1000)
                        print(f"  {i+1:2d}. {dt}")
                    
                    # 使用after参数获取更早的数据
                    print(f"\n🔍 使用after参数获取更早的数据...")
                    params2 = {
                        "instId": "BTC-USDT-SWAP",
                        "bar": "1H",
                        "after": str(oldest_timestamp),  # 获取早于此时间的数据
                        "limit": "10"
                    }
                    
                    async with session.get(url, params=params2) as response2:
                        if response2.status == 200:
                            data2 = await response2.json()
                            if data2.get("code") == "0" and data2.get("data"):
                                earlier_candles = data2["data"]
                                
                                print(f"✅ 成功获取 {len(earlier_candles)} 条更早数据:")
                                for i, candle in enumerate(earlier_candles):
                                    ts = int(candle[0])
                                    dt = datetime.fromtimestamp(ts / 1000)
                                    print(f"  {i+1:2d}. {dt}")
                                
                                # 验证时间连续性
                                latest_earliest = int(earlier_candles[0][0])  # 新数据中最新的
                                original_oldest = oldest_timestamp
                                
                                print(f"\n📊 时间连续性检查:")
                                print(f"原始数据最早时间: {datetime.fromtimestamp(original_oldest/1000)}")
                                print(f"新数据最新时间: {datetime.fromtimestamp(latest_earliest/1000)}")
                                print(f"时间差: {(original_oldest - latest_earliest) / 1000 / 3600:.1f} 小时")
                                
                                return True
                            else:
                                print(f"❌ 第二次请求失败")
                        else:
                            print(f"❌ 第二次请求HTTP错误: {response2.status}")
    
    return False

async def main():
    """主测试函数"""
    print("🚀 最终测试OKX API参数使用")
    print("=" * 50)
    
    # 测试1: 时间参数组合
    success_cases = await test_correct_time_params()
    
    if success_cases:
        # 测试2: 分页策略
        pagination_ok = await test_pagination_strategy()
        
        print(f"\n" + "=" * 50)
        print(f"🎯 关键发现:")
        print(f"✅ 有效参数组合: {success_cases}")
        print(f"✅ 分页策略: {'可行' if pagination_ok else '需要调整'}")
        
        print(f"\n📝 建议的实现策略:")
        if "只使用after参数" in success_cases:
            print(f"  - 使用after参数实现时间范围分页")
            print(f"  - 从最新时间开始，逐步向历史推进")
            print(f"  - 每次用上一批的最早时间作为下一次的after参数")
    else:
        print(f"\n❌ 未找到有效的参数组合")

if __name__ == "__main__":
    asyncio.run(main())