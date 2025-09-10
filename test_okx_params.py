#!/usr/bin/env python3
"""
测试OKX API的不同参数组合，找出正确的分页方式
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_different_param_combinations():
    """测试不同的参数组合"""
    print("🔍 测试OKX API不同参数组合...")
    
    # 获取最新数据作为基准
    async with aiohttp.ClientSession() as session:
        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": "BTC-USDT-SWAP", "bar": "1H", "limit": "5"}
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0" and data.get("data"):
                    latest_candles = data["data"]
                    latest_timestamp = int(latest_candles[0][0])  # 最新时间戳
                    oldest_timestamp = int(latest_candles[-1][0])  # 最早时间戳
                    
                    print("📊 基准数据:")
                    for i, candle in enumerate(latest_candles):
                        ts = int(candle[0])
                        dt = datetime.fromtimestamp(ts / 1000)
                        print(f"  {i+1}. {dt} ({ts})")
                    
                    print(f"\n最新时间戳: {latest_timestamp}")
                    print(f"最早时间戳: {oldest_timestamp}")
                    
                    # 测试1: 使用after参数获取更早的数据
                    await test_after_param(oldest_timestamp)
                    
                    # 测试2: 使用before参数
                    await test_before_param(oldest_timestamp)
                    
                    # 测试3: 使用固定历史时间戳
                    await test_historical_timestamp()
                    
                else:
                    print("❌ 获取基准数据失败")
            else:
                print(f"❌ HTTP错误: {response.status}")

async def test_after_param(reference_timestamp):
    """测试after参数 - 应该获取比指定时间戳更早的数据"""
    print(f"\n🔍 测试after参数 (获取早于 {reference_timestamp} 的数据)...")
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "after": str(reference_timestamp),  # after表示早于此时间
        "limit": "5"
    }
    
    async with aiohttp.ClientSession() as session:
        url = "https://www.okx.com/api/v5/market/candles"
        
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0":
                    candles = data.get("data", [])
                    print(f"✅ after参数获取到 {len(candles)} 条数据")
                    
                    for i, candle in enumerate(candles):
                        ts = int(candle[0])
                        dt = datetime.fromtimestamp(ts / 1000)
                        print(f"  {i+1}. {dt} ({ts})")
                        
                    if candles:
                        newest_ts = int(candles[0][0])
                        oldest_ts = int(candles[-1][0])
                        print(f"验证: 最新={newest_ts} < 参考={reference_timestamp} ? {newest_ts < reference_timestamp}")
                        
                else:
                    print(f"❌ after参数API错误: {data.get('msg')}")
            else:
                print(f"❌ after参数HTTP错误: {response.status}")

async def test_before_param(reference_timestamp):
    """测试before参数 - 应该获取比指定时间戳更晚的数据"""
    print(f"\n🔍 测试before参数 (获取晚于 {reference_timestamp} 的数据)...")
    
    # before参数应该是获取晚于指定时间的数据
    # 但OKX可能相反，让我们测试一下
    params = {
        "instId": "BTC-USDT-SWAP", 
        "bar": "1H",
        "before": str(reference_timestamp),
        "limit": "5"
    }
    
    async with aiohttp.ClientSession() as session:
        url = "https://www.okx.com/api/v5/market/candles"
        
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0":
                    candles = data.get("data", [])
                    print(f"✅ before参数获取到 {len(candles)} 条数据")
                    
                    for i, candle in enumerate(candles):
                        ts = int(candle[0])
                        dt = datetime.fromtimestamp(ts / 1000)
                        print(f"  {i+1}. {dt} ({ts})")
                        
                else:
                    print(f"❌ before参数API错误: {data.get('msg')}")
            else:
                print(f"❌ before参数HTTP错误: {response.status}")

async def test_historical_timestamp():
    """测试固定的历史时间戳"""
    print(f"\n🔍 测试固定历史时间戳...")
    
    # 使用一个明确的历史时间：比如7天前
    seven_days_ago = datetime.now() - timedelta(days=7)
    historical_timestamp = int(seven_days_ago.timestamp() * 1000)
    
    print(f"📅 7天前时间: {seven_days_ago} ({historical_timestamp})")
    
    # 测试用after参数获取7天前之后的数据
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "after": str(historical_timestamp - 1),
        "limit": "10"
    }
    
    async with aiohttp.ClientSession() as session:
        url = "https://www.okx.com/api/v5/market/candles"
        
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0":
                    candles = data.get("data", [])
                    print(f"✅ 历史时间戳获取到 {len(candles)} 条数据")
                    
                    if candles:
                        first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                        last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000) 
                        print(f"📅 数据时间范围: {first_time} 到 {last_time}")
                        
                else:
                    print(f"❌ 历史时间戳API错误: {data.get('msg')}")
            else:
                print(f"❌ 历史时间戳HTTP错误: {response.status}")

async def main():
    """主测试函数"""
    print("🚀 开始测试OKX API参数组合")
    print("=" * 50)
    
    await test_different_param_combinations()
    
    print("\n" + "=" * 50)
    print("📝 参数使用总结:")
    print("- limit: 限制返回条数，最大100")
    print("- after: 获取早于指定时间戳的数据 (历史数据)")
    print("- before: 获取晚于指定时间戳的数据 (还是历史数据?)")
    print("- 默认返回最新数据，按时间降序排列")

if __name__ == "__main__":
    asyncio.run(main())