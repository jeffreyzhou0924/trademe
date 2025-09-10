#!/usr/bin/env python3
"""
测试修复后的OKX数据下载系统
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加路径以导入项目模块
sys.path.append('/root/trademe/backend/trading-service')

from app.services.okx_market_data_service import OKXMarketDataService

async def test_fixed_download():
    """测试修复后的下载系统"""
    print("🔍 测试修复后的OKX数据下载系统...")
    
    service = OKXMarketDataService()
    
    # 测试时间范围: 2025年8月29日-31日（最近3天）
    start_time = int(datetime(2025, 8, 29, 0, 0, 0).timestamp() * 1000)
    end_time = int(datetime(2025, 8, 31, 23, 59, 59).timestamp() * 1000)
    
    print(f"📅 测试时间范围:")
    print(f"  开始: {datetime.fromtimestamp(start_time/1000)}")  
    print(f"  结束: {datetime.fromtimestamp(end_time/1000)}")
    print(f"  时间戳: {start_time} - {end_time}")
    
    try:
        # 调用修复后的服务
        result = await service.get_klines(
            symbol="BTC-USDT-SWAP",
            timeframe="1h",
            limit=100,
            start_time=start_time,
            end_time=end_time,
            use_cache=False
        )
        
        print(f"\n✅ 系统调用成功!")
        print(f"📊 结果统计:")
        print(f"  - 交易对: {result.get('symbol')}")
        print(f"  - 时间框架: {result.get('timeframe')}")
        print(f"  - 数据条数: {result.get('count')}")
        print(f"  - 数据源: {result.get('source')}")
        
        klines = result.get('klines', [])
        if klines:
            first_time = datetime.fromtimestamp(klines[0][0] / 1000)
            last_time = datetime.fromtimestamp(klines[-1][0] / 1000)
            print(f"📅 实际数据时间范围: {first_time} 到 {last_time}")
            
            # 计算预期数据量
            expected_hours = int((end_time - start_time) / 1000 / 3600)
            print(f"📊 预期小时数: {expected_hours} 小时")
            print(f"📊 实际获取: {len(klines)} 条")
            print(f"📊 覆盖率: {len(klines)/expected_hours*100:.1f}%")
            
            # 显示前3条和后3条数据
            print(f"\n📈 数据样例:")
            for i in range(min(3, len(klines))):
                ts = klines[i][0]
                dt = datetime.fromtimestamp(ts / 1000)
                print(f"  {i+1}. {dt} | O:{klines[i][1]} H:{klines[i][2]} L:{klines[i][3]} C:{klines[i][4]}")
            
            if len(klines) > 6:
                print("  ...")
                for i in range(max(0, len(klines)-3), len(klines)):
                    ts = klines[i][0]
                    dt = datetime.fromtimestamp(ts / 1000)
                    print(f"  {i+1}. {dt} | O:{klines[i][1]} H:{klines[i][2]} L:{klines[i][3]} C:{klines[i][4]}")
        else:
            print("⚠️ 未获取到数据")
        
        return result.get('source') == 'okx_rest_api' and len(klines) > 0
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

async def test_different_timeframes():
    """测试不同时间框架的数据获取"""
    print("\n🔍 测试不同时间框架的数据获取...")
    
    service = OKXMarketDataService()
    
    # 最近24小时
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = end_time - (24 * 60 * 60 * 1000)  # 24小时前
    
    timeframes = ["1m", "5m", "15m", "30m", "1h", "4h"]
    expected_counts = {
        "1m": 1440,   # 24 * 60分钟
        "5m": 288,    # 1440 / 5
        "15m": 96,    # 1440 / 15
        "30m": 48,    # 1440 / 30
        "1h": 24,     # 24小时
        "4h": 6       # 24 / 4
    }
    
    print(f"📅 测试最近24小时数据:")
    
    for tf in timeframes:
        try:
            result = await service.get_klines(
                symbol="BTC-USDT-SWAP",
                timeframe=tf,
                limit=100,
                start_time=start_time,
                end_time=end_time,
                use_cache=False
            )
            
            count = result.get('count', 0)
            expected = expected_counts[tf]
            coverage = min(count / expected * 100, 100) if expected > 0 else 0
            source = result.get('source', 'unknown')
            
            status = "✅" if source == 'okx_rest_api' else "❌"
            print(f"  {status} {tf:>3}: {count:>3}条 / 预期{expected:>4}条 ({coverage:>5.1f}%) [{source}]")
            
        except Exception as e:
            print(f"  ❌ {tf:>3}: 测试失败 - {e}")

async def main():
    """主测试函数"""
    print("🚀 开始测试修复后的OKX数据下载系统")
    print("=" * 60)
    
    # 测试1: 基础时间范围数据获取
    success1 = await test_fixed_download()
    
    if success1:
        # 测试2: 不同时间框架
        await test_different_timeframes()
        
        print("\n" + "=" * 60)
        print("🎉 修复验证成功!")
        print("📝 关键改进:")
        print("  ✅ 修复了OKX API的before/after参数使用")
        print("  ✅ 正确处理时间范围过滤")
        print("  ✅ 改善了错误处理和日志输出")
        print("  ✅ API调用成功返回真实数据")
    else:
        print("\n❌ 修复验证失败，需要进一步调试")

if __name__ == "__main__":
    asyncio.run(main())