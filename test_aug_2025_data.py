#!/usr/bin/env python3
"""
测试2025年8月数据的OKX API调用
这是用户要求的时间范围 20250801-20250831
"""

import asyncio
import aiohttp
from datetime import datetime

async def test_aug_2025_data():
    """测试2025年8月1日到31日的数据"""
    print("🔍 测试2025年8月数据 (用户要求的时间范围)...")
    
    # 用户要求的时间范围: 20250801-20250831
    start_time = datetime(2025, 8, 1, 0, 0, 0)
    end_time = datetime(2025, 8, 31, 23, 59, 59)
    
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
            print(f"📅 查询时间范围: {start_time} 到 {end_time}")
            print(f"📅 时间戳: {start_timestamp} - {end_timestamp}")
            print(f"📡 请求参数: {params}")
            
            async with session.get(url, params=params, timeout=15) as response:
                print(f"📊 响应状态: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 成功获取 {len(candles)} 条2025年8月的K线数据!")
                        
                        if candles:
                            # OKX返回数据是降序的
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            print(f"📅 实际数据时间范围: {first_time} 到 {last_time}")
                            
                            # 显示样例数据
                            sample = candles[0]  # 最新的K线
                            sample_time = datetime.fromtimestamp(int(sample[0]) / 1000)
                            print(f"📈 样例K线数据:")
                            print(f"  时间: {sample_time}")
                            print(f"  开盘价: {sample[1]}")
                            print(f"  最高价: {sample[2]}")
                            print(f"  最低价: {sample[3]}")
                            print(f"  收盘价: {sample[4]}")
                            print(f"  成交量: {sample[5]}")
                            
                            # 计算预期的总数据量
                            total_hours = int((end_timestamp - start_timestamp) / 1000 / 3600)
                            print(f"📊 时间范围总小时数: {total_hours}")
                            print(f"📊 如果分页下载，预计总数据量: ~{total_hours}条 (每小时1条)")
                        
                        return True, len(candles)
                    else:
                        print(f"❌ API返回错误: {data.get('msg')}")
                        print(f"📄 完整响应: {data}")
                        return False, 0
                else:
                    text = await response.text()
                    print(f"❌ HTTP请求失败: {response.status}")
                    print(f"📄 响应内容: {text}")
                    return False, 0
                    
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False, 0

async def test_different_timeframes():
    """测试不同时间框架的数据量"""
    print("\n🔍 测试不同时间框架的预期数据量...")
    
    # 2025年8月1日到31日
    start_time = datetime(2025, 8, 1)
    end_time = datetime(2025, 8, 31, 23, 59, 59)
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)
    
    # 不同时间框架及其预期数据量
    timeframes = {
        "1m": 44640,    # 31天 * 24小时 * 60分钟
        "5m": 8928,     # 44640 / 5
        "15m": 2976,    # 44640 / 15
        "30m": 1488,    # 44640 / 30
        "1H": 744,      # 31天 * 24小时
        "2H": 372,      # 744 / 2
        "4H": 186,      # 744 / 4
        "1D": 31        # 31天
    }
    
    print(f"📅 时间范围: 2025年8月1日 到 2025年8月31日 (31天)")
    print("📊 不同时间框架的预期数据量:")
    
    for tf, expected in timeframes.items():
        print(f"  {tf:>4}: 预期 ~{expected:>5} 条数据")
    
    # 实际测试1小时框架
    print(f"\n🔍 实际测试1小时框架数据获取...")
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "after": str(start_timestamp - 1),
        "before": str(end_timestamp),
        "limit": "100"  # 先获取100条看看
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.okx.com/api/v5/market/candles"
            
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 1H框架获取到 {len(candles)} 条数据 (预期744条，需要分页)")
                        
                        if candles:
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            print(f"📅 实际时间范围: {first_time} 到 {last_time}")
                        
                        return True
                    else:
                        print(f"❌ 1H框架API错误: {data.get('msg')}")
                        return False
                else:
                    print(f"❌ 1H框架HTTP错误: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ 1H框架测试异常: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试2025年8月数据 (用户要求的时间范围)")
    print("=" * 60)
    
    # 测试1: 2025年8月数据
    success, count = await test_aug_2025_data()
    
    if success:
        # 测试2: 不同时间框架分析
        await test_different_timeframes()
        
        print("\n" + "=" * 60)
        print("📊 关键发现:")
        print(f"✅ OKX API可以获取2025年8月数据")
        print(f"✅ 单次API调用限制100条，需要分页下载完整数据")
        print(f"✅ 不同时间框架应该有不同的数据量")
        print("⚠️ 系统需要实现分页下载以获取完整的744条1小时数据")
    else:
        print("\n❌ 2025年8月数据获取失败")

if __name__ == "__main__":
    asyncio.run(main())