#!/usr/bin/env python3

"""
测试OKX tick数据的可用性
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_okx_data_availability():
    """测试OKX数据可用性"""
    
    base_url = "https://static.okx.com/cdn/okex/traderecords/trades/daily"
    symbol = "BTC"
    version = "240927"
    
    # 测试不同的日期范围
    test_dates = [
        # 最近的日期
        "2025-08-31",
        "2025-08-30",
        "2025-08-01",
        "2025-07-15", 
        "2025-07-01",
        # 更早的日期
        "2025-06-01",
        "2025-05-01",
        "2024-12-31",
        "2024-08-01",
        "2024-05-02",  # 我们之前成功下载的日期
    ]
    
    async with aiohttp.ClientSession() as session:
        print("=== OKX Tick数据可用性测试 ===")
        
        for date_str in test_dates:
            formatted_date = date_str  # OKX使用YYYY-MM-DD格式
            zip_filename = f"{symbol}-USDT-{version}-trades-{formatted_date}.zip"
            url = f"{base_url}/{date_str}/{zip_filename}"
            
            try:
                async with session.head(url, timeout=10) as response:
                    status = response.status
                    if status == 200:
                        content_length = response.headers.get('Content-Length', 'Unknown')
                        print(f"✅ {date_str}: 可用 (大小: {content_length} bytes)")
                    elif status == 404:
                        print(f"❌ {date_str}: 不存在 (404)")
                    else:
                        print(f"⚠️ {date_str}: 状态码 {status}")
                        
            except Exception as e:
                print(f"🔥 {date_str}: 请求失败 - {e}")
    
    print("\n=== 检查完成 ===")

if __name__ == "__main__":
    asyncio.run(test_okx_data_availability())