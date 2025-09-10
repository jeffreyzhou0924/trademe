#!/usr/bin/env python3
"""
测试现有OKX数据下载系统的实际API调用
验证时间戳和API参数是否正确
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import sys
import os

# 添加路径以导入项目模块
sys.path.append('/root/trademe/backend/trading-service')

from app.services.okx_market_data_service import OKXMarketDataService

async def test_current_system():
    """测试当前系统的OKX API调用"""
    print("🔍 测试当前OKX市场数据服务...")
    
    # 创建服务实例
    service = OKXMarketDataService()
    
    # 测试正确的历史时间戳 (2024年8月)
    start_time = int(datetime(2024, 8, 1).timestamp() * 1000)
    end_time = int(datetime(2024, 8, 31, 23, 59, 59).timestamp() * 1000)
    
    print(f"📅 测试时间范围: {datetime.fromtimestamp(start_time/1000)} 到 {datetime.fromtimestamp(end_time/1000)}")
    
    try:
        # 调用服务获取数据
        result = await service.get_klines(
            symbol="BTC-USDT-SWAP",
            timeframe="1h", 
            limit=100,
            start_time=start_time,
            end_time=end_time,
            use_cache=False
        )
        
        print("✅ 系统调用成功!")
        print(f"📊 获取数据统计:")
        print(f"  - 交易对: {result.get('symbol')}")
        print(f"  - 时间框架: {result.get('timeframe')}")
        print(f"  - 数据条数: {result.get('count')}")
        print(f"  - 数据源: {result.get('source')}")
        
        # 显示时间范围
        klines = result.get('klines', [])
        if klines:
            first_time = datetime.fromtimestamp(klines[0][0] / 1000)
            last_time = datetime.fromtimestamp(klines[-1][0] / 1000)
            print(f"📅 实际数据时间范围: {first_time} 到 {last_time}")
            
            # 显示样例数据
            print(f"📈 首条K线数据: 时间={first_time}, 开盘={klines[0][1]}, 收盘={klines[0][4]}")
            print(f"📈 末条K线数据: 时间={last_time}, 开盘={klines[-1][1]}, 收盘={klines[-1][4]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统调用失败: {e}")
        return False

async def test_direct_api_with_correct_time():
    """直接测试OKX API，使用正确的历史时间戳"""
    print("\n🔍 直接测试OKX API (正确历史时间)...")
    
    # 使用2024年的历史时间戳
    start_time = int(datetime(2024, 8, 1).timestamp() * 1000)  
    end_time = int(datetime(2024, 8, 31, 23, 59, 59).timestamp() * 1000)
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "after": str(start_time - 1),
        "before": str(end_time),
        "limit": "100"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/candles"
            print(f"📡 请求URL: {url}")
            print(f"📋 请求参数: {params}")
            print(f"📅 时间范围: {datetime.fromtimestamp(start_time/1000)} 到 {datetime.fromtimestamp(end_time/1000)}")
            
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 直接API调用成功! 获取到 {len(candles)} 条数据")
                        
                        if candles:
                            # OKX返回数据是降序的
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)  # 最早时间
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)   # 最晚时间
                            print(f"📅 实际数据时间范围: {first_time} 到 {last_time}")
                        
                        return True
                    else:
                        print(f"❌ API返回错误: {data.get('msg')}")
                        return False
                else:
                    print(f"❌ HTTP请求失败: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ 直接API调用异常: {e}")
        return False

async def test_okx_data_downloader():
    """测试OKX数据下载器的时间戳处理"""
    print("\n🔍 测试OKX数据下载器的时间戳处理...")
    
    # 模拟用户输入的时间范围 20240801-20240831
    user_start_date = "20240801"
    user_end_date = "20240831"
    
    # 转换为时间戳 (这是下载器应该做的)
    start_dt = datetime.strptime(user_start_date, "%Y%m%d")
    end_dt = datetime.strptime(user_end_date, "%Y%m%d").replace(hour=23, minute=59, second=59)
    
    start_timestamp = int(start_dt.timestamp() * 1000)
    end_timestamp = int(end_dt.timestamp() * 1000)
    
    print(f"📅 用户输入: {user_start_date} - {user_end_date}")
    print(f"📅 转换时间: {start_dt} - {end_dt}")
    print(f"📅 时间戳: {start_timestamp} - {end_timestamp}")
    
    # 验证时间戳是否合理
    now_timestamp = int(datetime.now().timestamp() * 1000)
    if start_timestamp > now_timestamp or end_timestamp > now_timestamp:
        print("❌ 错误: 时间戳是未来时间!")
        return False
    else:
        print("✅ 时间戳验证通过，是历史时间")
        return True

async def main():
    """主测试函数"""
    print("🚀 开始测试OKX数据下载系统")
    print("=" * 60)
    
    # 测试1: 时间戳处理验证
    time_ok = await test_okx_data_downloader()
    
    if time_ok:
        # 测试2: 直接API调用
        direct_ok = await test_direct_api_with_correct_time()
        
        if direct_ok:
            # 测试3: 系统服务调用
            system_ok = await test_current_system()
            
            print("\n" + "=" * 60)
            print("📊 测试结果汇总:")
            print(f"✅ 时间戳处理: {'通过' if time_ok else '失败'}")
            print(f"✅ 直接API调用: {'通过' if direct_ok else '失败'}")
            print(f"✅ 系统服务调用: {'通过' if system_ok else '失败'}")
            
            if time_ok and direct_ok and system_ok:
                print("\n🎉 所有测试通过! OKX数据下载系统正常")
            else:
                print("\n⚠️ 部分测试失败，需要修复相关问题")
        else:
            print("\n❌ 直接API调用失败")
    else:
        print("\n❌ 时间戳处理有问题")

if __name__ == "__main__":
    asyncio.run(main())