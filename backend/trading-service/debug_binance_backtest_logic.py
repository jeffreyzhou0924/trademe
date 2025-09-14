#!/usr/bin/env python3
"""
调试币安回测逻辑矛盾问题
验证为什么使用币安参数的回测会产生结果，而数据库中只有OKX数据
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.backtest_service import BacktestEngine
from sqlalchemy import select, distinct
from app.models.market_data import MarketData
from loguru import logger

async def debug_binance_backtest_issue():
    """调试币安回测逻辑问题"""
    
    async with AsyncSessionLocal() as db:
        try:
            print("🔍 开始调试币安回测逻辑问题...")
            
            # 1. 验证数据库实际状态
            print("\n1️⃣ 验证数据库实际状态")
            query = select(distinct(MarketData.exchange)).where(
                MarketData.symbol == "BTC/USDT"
            )
            result = await db.execute(query)
            available_exchanges = [ex for ex in result.scalars().all() if ex]
            print(f"📊 BTC/USDT可用交易所: {available_exchanges}")
            
            # 2. 测试 _check_data_availability 方法的模糊匹配
            print("\n2️⃣ 测试数据可用性检查方法")
            engine = BacktestEngine()
            
            # 模拟币安数据可用性检查
            binance_availability = await engine._check_data_availability(
                "binance", "BTC/USDT", 
                datetime.now() - timedelta(days=30), 
                datetime.now(), 
                db
            )
            print(f"💰 币安数据可用性检查结果: {binance_availability}")
            
            # 模拟OKX数据可用性检查
            okx_availability = await engine._check_data_availability(
                "okx", "BTC/USDT", 
                datetime.now() - timedelta(days=30), 
                datetime.now(), 
                db
            )
            print(f"🏢 OKX数据可用性检查结果: {okx_availability}")
            
            # 3. 测试实际的历史数据获取
            print("\n3️⃣ 测试实际历史数据获取")
            
            try:
                binance_data = await engine._get_historical_data(
                    "binance", "BTC/USDT", "1h",
                    datetime.now() - timedelta(days=7),
                    datetime.now(),
                    1, db
                )
                print(f"💰 币安历史数据获取成功: {len(binance_data)}条记录")
            except Exception as e:
                print(f"💰 币安历史数据获取失败: {str(e)}")
            
            try:
                okx_data = await engine._get_historical_data(
                    "okx", "BTC/USDT", "1h",
                    datetime.now() - timedelta(days=7),
                    datetime.now(),
                    1, db
                )
                print(f"🏢 OKX历史数据获取成功: {len(okx_data)}条记录")
            except Exception as e:
                print(f"🏢 OKX历史数据获取失败: {str(e)}")
            
            # 4. 测试完整的execute_backtest方法
            print("\n4️⃣ 测试完整回测执行流程")
            
            backtest_params = {
                'strategy_code': '''
class TestStrategy:
    def __init__(self):
        self.position = 0
    
    def on_data(self, data):
        return "hold"
                ''',
                'exchange': 'binance',
                'symbols': ['BTC/USDT'],
                'timeframes': ['1h'],
                'start_date': '2024-01-01',
                'end_date': '2024-01-07',
                'initial_capital': 10000.0
            }
            
            try:
                result = await engine.execute_backtest(backtest_params, 1, db)
                print(f"💰 币安完整回测结果: {result.get('success')}")
                if result.get('success'):
                    print(f"   📈 回测数据记录数: {result.get('backtest_result', {}).get('data_records', 0)}")
                    print(f"   📊 数据源: {result.get('backtest_result', {}).get('data_source', 'Unknown')}")
                else:
                    print(f"   ❌ 回测失败原因: {result.get('error', 'Unknown')}")
            except Exception as e:
                print(f"💰 币安完整回测异常: {str(e)}")
            
            # 5. 检查是否存在fallback机制
            print("\n5️⃣ 检查可能的绕过机制")
            
            # 检查数据库中是否有任何包含"binance"的记录
            fuzzy_query = select(MarketData).where(
                MarketData.exchange.ilike("%binance%"),
                MarketData.symbol == "BTC/USDT"
            ).limit(10)
            
            fuzzy_result = await db.execute(fuzzy_query)
            fuzzy_records = fuzzy_result.scalars().all()
            print(f"🔍 模糊匹配binance的记录数: {len(fuzzy_records)}")
            
            if fuzzy_records:
                for record in fuzzy_records[:3]:
                    print(f"   📄 记录: 交易所={record.exchange}, 符号={record.symbol}, 时间={record.timestamp}")
            
            print("\n✅ 调试完成")
            
        except Exception as e:
            print(f"❌ 调试过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_binance_backtest_issue())