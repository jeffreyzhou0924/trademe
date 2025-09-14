#!/usr/bin/env python3
"""
完整回测参数问题诊断和修复验证
解决用户报告的OKX永续合约BTC 1小时数据参数错误问题
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from loguru import logger

# 测试用JWT Token (新生成，7天有效)
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc4NDk5MzMsImV4cCI6MTc1ODQ1NDczMywiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.Fwihr_9AG5DoEnXZQhR11OTdYcHpJIwpvQr8EB6BhOo"

BASE_URL = "http://localhost:8001/api/v1"

async def test_data_availability():
    """测试数据可用性"""
    print("🔍 1. 检查数据库中OKX永续合约BTC数据可用性")
    
    from app.database import get_db
    from app.models.market_data import MarketData
    from sqlalchemy import select, and_, func
    
    async for db in get_db():
        try:
            # 检查OKX交易所的BTC相关数据
            symbols_to_check = [
                "BTC/USDT", "BTC-USDT", "BTC-USDT-SWAP", 
                "BTCUSDT", "BTC_USDT", "btc/usdt", "btc-usdt-swap"
            ]
            
            print(f"   检查交易对: {symbols_to_check}")
            print(f"   时间范围: 2025-07-01 到 2025-08-31")
            
            total_available = 0
            available_symbols = []
            
            for symbol in symbols_to_check:
                query = select(func.count(MarketData.id)).where(
                    and_(
                        MarketData.exchange == "okx",
                        MarketData.symbol == symbol,
                        MarketData.timeframe == "1h",
                        MarketData.timestamp >= "2025-07-01",
                        MarketData.timestamp <= "2025-08-31"
                    )
                )
                
                result = await db.execute(query)
                count = result.scalar()
                
                if count > 0:
                    print(f"   ✅ {symbol}: {count:,} 条记录")
                    total_available += count
                    available_symbols.append(symbol)
                else:
                    print(f"   ❌ {symbol}: 无数据")
            
            print(f"   📊 总计可用数据: {total_available:,} 条记录")
            print(f"   📈 可用交易对: {available_symbols}")
            
            # 获取数据样本
            if available_symbols:
                sample_symbol = available_symbols[0]
                sample_query = select(MarketData).where(
                    and_(
                        MarketData.exchange == "okx",
                        MarketData.symbol == sample_symbol,
                        MarketData.timeframe == "1h",
                        MarketData.timestamp >= "2025-07-01",
                        MarketData.timestamp <= "2025-08-31"
                    )
                ).order_by(MarketData.timestamp.asc()).limit(3)
                
                sample_result = await db.execute(sample_query)
                samples = sample_result.scalars().all()
                
                print(f"   🔍 {sample_symbol} 数据样本:")
                for sample in samples:
                    print(f"     {sample.timestamp}: O:{sample.open_price} H:{sample.high_price} L:{sample.low_price} C:{sample.close_price}")
            
            break
        finally:
            await db.close()
    
    return available_symbols

async def test_api_request(config, test_name):
    """测试API请求"""
    print(f"🚀 {test_name}")
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    url = f"{BASE_URL}/realtime-backtest/start"
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"   📤 请求URL: {url}")
            print(f"   📋 请求配置:")
            for key, value in config.items():
                if key == "strategy_code":
                    print(f"     {key}: [代码长度: {len(str(value))} 字符]")
                else:
                    print(f"     {key}: {value}")
            
            async with session.post(url, json=config, headers=headers) as response:
                status_code = response.status
                response_text = await response.text()
                
                print(f"   📊 响应状态: {status_code}")
                
                if status_code == 200:
                    try:
                        response_data = json.loads(response_text)
                        print(f"   ✅ 成功响应: {response_data}")
                        return response_data
                    except json.JSONDecodeError:
                        print(f"   📄 响应内容: {response_text}")
                        return {"status": "success", "raw_response": response_text}
                else:
                    print(f"   ❌ 错误响应: {response_text}")
                    try:
                        error_data = json.loads(response_text)
                        return {"status": "error", "error": error_data}
                    except json.JSONDecodeError:
                        return {"status": "error", "error": response_text}
    
    except Exception as e:
        print(f"   💥 请求异常: {e}")
        return {"status": "exception", "error": str(e)}

async def test_various_configurations(available_symbols):
    """测试各种配置组合"""
    print("\n🔧 2. 测试各种回测配置")
    
    # 基础策略代码
    basic_strategy = """
class UserStrategy(BaseStrategy):
    def on_data(self, data):
        # 简单买卖策略
        if len(self.data) > 20:
            sma_short = self.data['close'].rolling(5).mean().iloc[-1]
            sma_long = self.data['close'].rolling(20).mean().iloc[-1]
            
            if sma_short > sma_long:
                return {"action": "buy", "quantity": 1}
            else:
                return {"action": "sell", "quantity": 1}
        return None
"""
    
    test_configs = []
    
    # 为每个可用的交易对创建测试配置
    for symbol in available_symbols[:3]:  # 测试前3个可用交易对
        test_configs.extend([
            {
                "name": f"✅ 标准配置 - {symbol}",
                "config": {
                    "strategy_code": basic_strategy,
                    "exchange": "okx",
                    "product_type": "spot",
                    "symbols": [symbol],
                    "timeframes": ["1h"],
                    "fee_rate": "vip0",
                    "initial_capital": 10000.0,
                    "start_date": "2025-07-01",
                    "end_date": "2025-08-31",
                    "data_type": "kline"
                }
            },
            {
                "name": f"🔄 永续合约配置 - {symbol}",
                "config": {
                    "strategy_code": basic_strategy,
                    "exchange": "okx",
                    "product_type": "perpetual",
                    "symbols": [symbol],
                    "timeframes": ["1h"],
                    "fee_rate": "vip0_perp",
                    "initial_capital": 10000.0,
                    "start_date": "2025-07-01",
                    "end_date": "2025-08-31",
                    "data_type": "kline"
                }
            }
        ])
    
    # 用户报告的具体配置
    if "BTC-USDT-SWAP" in available_symbols or "BTC/USDT" in available_symbols:
        user_symbol = "BTC-USDT-SWAP" if "BTC-USDT-SWAP" in available_symbols else "BTC/USDT"
        test_configs.insert(0, {
            "name": f"🎯 用户报告的配置 - {user_symbol}",
            "config": {
                "strategy_code": basic_strategy,
                "exchange": "okx",
                "product_type": "perpetual",
                "symbols": [user_symbol],
                "timeframes": ["1h"],
                "fee_rate": "vip0_perp",
                "initial_capital": 10000.0,
                "start_date": "2025-07-01",
                "end_date": "2025-08-31",
                "data_type": "kline"
            }
        })
    
    results = []
    for test_config in test_configs:
        result = await test_api_request(test_config["config"], test_config["name"])
        results.append({
            "test_name": test_config["name"],
            "result": result
        })
        
        # 添加延迟避免请求过快
        await asyncio.sleep(1)
    
    return results

async def monitor_backtest_progress(task_id):
    """监控回测进度"""
    print(f"\n📊 3. 监控回测进度 - 任务ID: {task_id}")
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    status_url = f"{BASE_URL}/realtime-backtest/status/{task_id}"
    
    for i in range(12):  # 最多监控12次 (约1分钟)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(status_url, headers=headers) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        progress = status_data.get("progress", 0)
                        current_step = status_data.get("current_step", "未知步骤")
                        status = status_data.get("status", "unknown")
                        
                        print(f"   [{i+1:2d}/12] 进度: {progress:3d}% | {status} | {current_step}")
                        
                        if status in ["completed", "failed", "cancelled"]:
                            print(f"   🎯 回测已{status}")
                            if status == "completed":
                                results = status_data.get("results", {})
                                print(f"   📈 回测结果预览:")
                                for key, value in results.items():
                                    if isinstance(value, (int, float)):
                                        print(f"     {key}: {value}")
                            elif status == "failed":
                                error_msg = status_data.get("error_message", "未知错误")
                                print(f"   ❌ 失败原因: {error_msg}")
                            break
                    else:
                        print(f"   [{i+1:2d}/12] 状态查询失败: {response.status}")
                        break
            
            await asyncio.sleep(5)  # 每5秒检查一次
        except Exception as e:
            print(f"   [{i+1:2d}/12] 监控异常: {e}")
            break

async def main():
    """主函数"""
    print("🔧 OKX永续合约BTC回测参数错误问题 - 完整诊断")
    print("=" * 70)
    print(f"🕐 测试时间: {datetime.now()}")
    print(f"🔗 API基础URL: {BASE_URL}")
    
    try:
        # 1. 检查数据可用性
        available_symbols = await test_data_availability()
        
        if not available_symbols:
            print("\n❌ 没有找到可用的OKX BTC数据，无法进行回测测试")
            return
        
        # 2. 测试各种配置
        test_results = await test_various_configurations(available_symbols)
        
        # 3. 分析测试结果
        print("\n📋 测试结果总结:")
        print("-" * 50)
        
        successful_tests = []
        failed_tests = []
        
        for result in test_results:
            test_name = result["test_name"]
            test_result = result["result"]
            
            if test_result.get("status") == "error":
                failed_tests.append(result)
                print(f"❌ {test_name}")
                error_detail = test_result.get("error", {})
                if isinstance(error_detail, dict):
                    error_msg = error_detail.get("detail", str(error_detail))
                else:
                    error_msg = str(error_detail)
                print(f"   错误: {error_msg}")
            elif test_result.get("task_id"):
                successful_tests.append(result)
                print(f"✅ {test_name}")
                print(f"   任务ID: {test_result['task_id']}")
            else:
                print(f"⚠️ {test_name} - 响应异常")
                print(f"   详情: {test_result}")
        
        print(f"\n📊 总结: {len(successful_tests)} 成功, {len(failed_tests)} 失败")
        
        # 4. 如果有成功的测试，监控第一个
        if successful_tests:
            first_success = successful_tests[0]
            task_id = first_success["result"]["task_id"]
            await monitor_backtest_progress(task_id)
        
        # 5. 问题分析和建议
        print("\n💡 问题分析和建议:")
        print("-" * 30)
        
        if successful_tests:
            print("✅ API端点工作正常")
            print("✅ 数据验证通过")
            print("✅ 回测任务可以成功启动")
            
            if failed_tests:
                print("⚠️ 部分配置存在问题：")
                for failed_test in failed_tests:
                    print(f"   - {failed_test['test_name']}")
                    error = failed_test["result"].get("error", {})
                    if isinstance(error, dict):
                        detail = error.get("detail", "未知错误")
                        print(f"     原因: {detail}")
        else:
            print("❌ 所有测试都失败了")
            print("💡 可能的原因:")
            print("   1. API端点不可用或配置错误")
            print("   2. JWT认证失败")
            print("   3. 数据库连接问题")
            print("   4. 参数验证过于严格")
        
        print(f"\n🎯 针对用户问题的结论:")
        print("   用户报告：OKX永续合约BTC 1小时数据，20250701-20250831，参数错误")
        
        if successful_tests and any("用户报告" in test["test_name"] for test in successful_tests):
            print("   ✅ 用户报告的配置现在可以正常工作")
            print("   💡 建议用户：")
            print("     - 清除浏览器缓存后重试")
            print("     - 确保使用最新的JWT token")
            print("     - 检查网络连接")
        else:
            print("   ⚠️ 用户报告的配置仍有问题")
            if available_symbols:
                print(f"   💡 建议使用以下可用交易对: {available_symbols[:3]}")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())