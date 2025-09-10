#!/usr/bin/env python3
"""
OKX API连接性测试脚本
测试OKX REST API是否可以正常访问
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

async def test_okx_api_basic():
    """测试OKX API基础连接性"""
    print("🔍 测试OKX API基础连接性...")
    
    # OKX REST API基础URL
    base_url = "https://www.okx.com"
    
    # 测试公开接口 - 获取交易所状态
    status_url = f"{base_url}/api/v5/system/status"
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"📡 请求URL: {status_url}")
            
            async with session.get(status_url, timeout=10) as response:
                print(f"📊 响应状态码: {response.status}")
                print(f"📊 响应头: {dict(response.headers)}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ OKX API连接成功!")
                    print(f"📄 响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                    return True
                else:
                    text = await response.text()
                    print(f"❌ OKX API连接失败: HTTP {response.status}")
                    print(f"📄 响应内容: {text}")
                    return False
                    
    except asyncio.TimeoutError:
        print("❌ OKX API请求超时")
        return False
    except Exception as e:
        print(f"❌ OKX API请求异常: {e}")
        return False

async def test_okx_kline_api():
    """测试OKX K线数据API"""
    print("\n🔍 测试OKX K线数据API...")
    
    # OKX K线API端点
    base_url = "https://www.okx.com"
    kline_url = f"{base_url}/api/v5/market/candles"
    
    # 测试参数
    params = {
        "instId": "BTC-USDT-SWAP",  # 合约交易对
        "bar": "1H",               # 1小时K线
        "limit": "10"              # 限制10条数据
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"📡 请求URL: {kline_url}")
            print(f"📋 请求参数: {params}")
            
            async with session.get(kline_url, params=params, timeout=10) as response:
                print(f"📊 响应状态码: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ OKX K线API调用成功!")
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"📊 获取到 {len(candles)} 条K线数据")
                        
                        if candles:
                            print("📈 最新K线数据样例:")
                            latest = candles[0]
                            timestamp = int(latest[0])
                            dt = datetime.fromtimestamp(timestamp / 1000)
                            print(f"  时间: {dt}")
                            print(f"  开盘价: {latest[1]}")
                            print(f"  最高价: {latest[2]}")
                            print(f"  最低价: {latest[3]}")
                            print(f"  收盘价: {latest[4]}")
                            print(f"  成交量: {latest[5]}")
                    else:
                        print(f"❌ OKX API返回错误: {data.get('msg', 'Unknown error')}")
                        return False
                    
                    return True
                else:
                    text = await response.text()
                    print(f"❌ OKX K线API请求失败: HTTP {response.status}")
                    print(f"📄 响应内容: {text}")
                    return False
                    
    except asyncio.TimeoutError:
        print("❌ OKX K线API请求超时")
        return False
    except Exception as e:
        print(f"❌ OKX K线API请求异常: {e}")
        return False

async def test_with_time_params():
    """测试带时间参数的OKX API调用"""
    print("\n🔍 测试带时间参数的OKX K线API...")
    
    base_url = "https://www.okx.com"
    kline_url = f"{base_url}/api/v5/market/candles"
    
    # 测试时间范围: 2025-08-01 到 2025-08-31
    start_time = int(datetime(2025, 8, 1).timestamp() * 1000)
    end_time = int(datetime(2025, 8, 31, 23, 59, 59).timestamp() * 1000)
    
    params = {
        "instId": "BTC-USDT-SWAP",
        "bar": "1H",
        "after": str(start_time - 1),  # OKX要求after要小于指定时间
        "before": str(end_time),        # before参数指定结束时间
        "limit": "100"                  # 每次最多100条
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"📡 请求URL: {kline_url}")
            print(f"📋 请求参数: {params}")
            print(f"⏰ 时间范围: {datetime.fromtimestamp(start_time/1000)} 到 {datetime.fromtimestamp(end_time/1000)}")
            
            async with session.get(kline_url, params=params, timeout=15) as response:
                print(f"📊 响应状态码: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        print(f"✅ 获取到 {len(candles)} 条时间范围内的K线数据")
                        
                        if candles:
                            # 显示第一条和最后一条的时间
                            first_time = datetime.fromtimestamp(int(candles[-1][0]) / 1000)
                            last_time = datetime.fromtimestamp(int(candles[0][0]) / 1000)
                            print(f"📅 数据时间范围: {first_time} 到 {last_time}")
                            
                        return True
                    else:
                        print(f"❌ OKX API返回错误: {data.get('msg', 'Unknown error')}")
                        print(f"📄 完整响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
                        return False
                else:
                    text = await response.text()
                    print(f"❌ 带时间参数的API请求失败: HTTP {response.status}")
                    print(f"📄 响应内容: {text}")
                    return False
                    
    except Exception as e:
        print(f"❌ 带时间参数的API请求异常: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始OKX API连接性测试")
    print("=" * 50)
    
    # 测试1: 基础连接性
    basic_ok = await test_okx_api_basic()
    
    if basic_ok:
        # 测试2: K线API
        kline_ok = await test_okx_kline_api()
        
        if kline_ok:
            # 测试3: 带时间参数的API
            time_ok = await test_with_time_params()
            
            print("\n" + "=" * 50)
            print("📊 测试结果汇总:")
            print(f"✅ 基础连接性: {'通过' if basic_ok else '失败'}")
            print(f"✅ K线API: {'通过' if kline_ok else '失败'}")
            print(f"✅ 时间参数API: {'通过' if time_ok else '失败'}")
            
            if basic_ok and kline_ok and time_ok:
                print("\n🎉 所有测试通过! OKX API连接正常")
            else:
                print("\n⚠️ 部分测试失败，需要进一步排查")
        else:
            print("\n❌ K线API测试失败，停止后续测试")
    else:
        print("\n❌ 基础连接性测试失败，请检查网络连接")

if __name__ == "__main__":
    asyncio.run(main())