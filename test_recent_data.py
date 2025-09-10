#!/usr/bin/env python3
"""
测试最近时间范围的OKX数据下载
验证API是否可以获取近期历史数据
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_recent_okx_data():
    """测试最近30天的OKX数据"""
    print("🔍 测试最近30天的OKX数据...")
    
    # 使用最近30天的时间范围
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    # 转换为毫秒时间戳
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "after": str(start_timestamp - 1),
        "before": str(end_timestamp),
        "limit": "100"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/candles"
            print(f"📅 测试时间范围: {start_time} 到 {end_time}")
            print(f"📡 请求参数: {params}")
            
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 获取到 {len(candles)} 条最近30天的数据")
                        
                        if candles:
                            # OKX返回数据是降序的
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            print(f"📅 实际数据时间范围: {first_time} 到 {last_time}")
                            
                            # 显示最新数据
                            latest_candle = candles[0]
                            latest_dt = datetime.fromtimestamp(int(latest_candle[0]) / 1000)
                            print(f"📈 最新K线: {latest_dt} 开盘={latest_candle[1]} 收盘={latest_candle[4]}")
                        
                        return True
                    else:
                        print(f"❌ API返回错误: {data.get('msg')}")
                        return False
                else:
                    print(f"❌ HTTP请求失败: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

async def test_no_time_params():
    """测试不带时间参数的API调用（获取最新数据）"""
    print("\n🔍 测试不带时间参数的API调用...")
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "limit": "10"  # 只获取最新10条
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/candles"
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 获取到 {len(candles)} 条最新数据")
                        
                        if candles:
                            latest_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            oldest_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            print(f"📅 数据时间范围: {oldest_time} 到 {latest_time}")
                        
                        return True
                    else:
                        print(f"❌ API返回错误: {data.get('msg')}")
                        return False
                else:
                    print(f"❌ HTTP请求失败: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试OKX最近数据获取")
    print("=" * 50)
    
    # 测试1: 不带时间参数的最新数据
    latest_ok = await test_no_time_params()
    
    if latest_ok:
        # 测试2: 最近30天数据
        recent_ok = await test_recent_okx_data()
        
        print("\n" + "=" * 50)
        print("📊 测试结果:")
        print(f"✅ 最新数据获取: {'成功' if latest_ok else '失败'}")
        print(f"✅ 最近30天数据: {'成功' if recent_ok else '失败'}")
        
        if latest_ok and recent_ok:
            print("\n🎉 OKX API连接正常，可以获取历史数据")
        else:
            print("\n⚠️ 部分测试失败")
    else:
        print("\n❌ 基础API调用失败")

if __name__ == "__main__":
    asyncio.run(main())