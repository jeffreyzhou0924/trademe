#!/usr/bin/env python3
"""
分步测试OKX API，从最简单的开始
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_latest_data_only():
    """测试1: 只获取最新数据，不带任何时间参数"""
    print("🔍 测试1: 获取最新K线数据 (不带时间参数)...")
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "limit": "10"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/candles"
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 成功获取 {len(candles)} 条最新K线数据")
                        
                        if candles:
                            for i, candle in enumerate(candles):
                                timestamp = int(candle[0])
                                dt = datetime.fromtimestamp(timestamp / 1000)
                                print(f"  {i+1:2d}. {dt} | 收盘价: {candle[4]}")
                        
                        return True, candles
                    else:
                        print(f"❌ API错误: {data.get('msg')}")
                        return False, []
                else:
                    print(f"❌ HTTP错误: {response.status}")
                    return False, []
                    
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, []

async def test_recent_with_before():
    """测试2: 使用before参数获取最近数据"""
    print("\n🔍 测试2: 使用before参数获取最近一周数据...")
    
    # 最近一周
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    
    end_timestamp = int(end_time.timestamp() * 1000)
    
    params = {
        "instId": "BTC-USDT-SWAP", 
        "bar": "1H",
        "before": str(end_timestamp),
        "limit": "100"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/candles"
            print(f"📅 查询时间: 截至 {end_time}")
            
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 成功获取 {len(candles)} 条数据 (使用before参数)")
                        
                        if candles:
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            print(f"📅 数据时间范围: {first_time} 到 {last_time}")
                        
                        return True, candles
                    else:
                        print(f"❌ API错误: {data.get('msg')}")
                        return False, []
                else:
                    print(f"❌ HTTP错误: {response.status}")
                    return False, []
                    
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, []

async def test_pagination_download():
    """测试3: 分页下载历史数据"""
    print("\n🔍 测试3: 分页下载历史数据...")
    
    all_candles = []
    end_time = datetime.now()
    
    # 从现在开始往前获取数据
    current_before = int(end_time.timestamp() * 1000)
    
    for page in range(1, 4):  # 测试前3页
        params = {
            "instId": "BTC-USDT-SWAP",
            "bar": "1H", 
            "before": str(current_before),
            "limit": "100"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://www.okx.com/api/v5/market/candles"
                
                print(f"📄 获取第 {page} 页数据...")
                
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("code") == "0":
                            candles = data.get("data", [])
                            
                            if not candles:
                                print(f"⚠️  第 {page} 页无数据，停止分页")
                                break
                            
                            print(f"✅ 第 {page} 页获取 {len(candles)} 条数据")
                            
                            # 添加到总数据中
                            all_candles.extend(candles)
                            
                            # 更新下一页的before参数为当前页最早的时间
                            oldest_timestamp = int(candles[-1][0])
                            current_before = oldest_timestamp
                            
                            # 显示时间范围
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            print(f"    时间范围: {first_time} 到 {last_time}")
                            
                        else:
                            print(f"❌ 第 {page} 页API错误: {data.get('msg')}")
                            break
                    else:
                        print(f"❌ 第 {page} 页HTTP错误: {response.status}")
                        break
                        
        except Exception as e:
            print(f"❌ 第 {page} 页异常: {e}")
            break
    
    print(f"\n📊 分页下载结果: 总共获取 {len(all_candles)} 条K线数据")
    
    if all_candles:
        earliest = datetime.fromtimestamp(int(all_candles[-1][0]) / 1000) 
        latest = datetime.fromtimestamp(int(all_candles[0][0]) / 1000)
        print(f"📅 数据时间跨度: {earliest} 到 {latest}")
        
        return True, all_candles
    
    return False, []

async def main():
    """主测试函数"""
    print("🚀 分步测试OKX API功能")
    print("=" * 50)
    
    # 测试1: 基础功能
    success1, data1 = await test_latest_data_only()
    
    if success1:
        # 测试2: before参数
        success2, data2 = await test_recent_with_before()
        
        if success2:
            # 测试3: 分页下载
            success3, data3 = await test_pagination_download()
            
            print("\n" + "=" * 50)
            print("📊 测试总结:")
            print(f"✅ 基础API调用: {'成功' if success1 else '失败'}")
            print(f"✅ before参数: {'成功' if success2 else '失败'}")
            print(f"✅ 分页下载: {'成功' if success3 else '失败'}")
            
            if success1 and success2 and success3:
                print("\n🎉 OKX API完全正常，可以实现历史数据分页下载!")
                print("📝 下一步: 修复系统的分页下载逻辑")
            else:
                print("\n⚠️  部分功能有问题")

if __name__ == "__main__":
    asyncio.run(main())