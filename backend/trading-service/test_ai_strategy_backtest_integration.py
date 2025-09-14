#!/usr/bin/env python3
"""
AI策略生成后立即回测功能的完整测试脚本

测试从AI策略生成到回测完成的完整流程
"""

import asyncio
import json
import time
import aiohttp
from typing import Dict, Any

# 测试配置
BASE_URL = "http://localhost:8001"
USER_EMAIL = "admin@trademe.com"  # 使用管理员账户测试
USER_PASSWORD = "admin123456"

class AIStrategyBacktestTester:
    """AI策略回测集成测试器"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.session = None
        self.jwt_token = None
        self.user_info = None
    
    async def setup(self):
        """初始化测试环境"""
        self.session = aiohttp.ClientSession()
        await self.login()
    
    async def cleanup(self):
        """清理测试环境"""
        if self.session:
            await self.session.close()
    
    async def login(self) -> Dict[str, Any]:
        """用户登录获取JWT token"""
        print("🔐 正在登录用户...")
        
        login_data = {
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        }
        
        # 调用用户服务登录
        user_service_url = "http://localhost:3001/api/v1/auth/login"
        
        try:
            async with self.session.post(user_service_url, json=login_data) as response:
                if response.status == 200:
                    result = await response.json()
                    # 用户服务返回的数据结构
                    data = result.get("data", {})
                    self.jwt_token = data.get("access_token")
                    self.user_info = data.get("user", {})
                    print(f"✅ 登录成功: {self.user_info.get('email')}")
                    print(f"👤 会员级别: {self.user_info.get('membership_level', 'basic')}")
                    return result
                else:
                    error_text = await response.text()
                    print(f"❌ 登录失败: {response.status} - {error_text}")
                    return None
        except Exception as e:
            print(f"❌ 登录请求异常: {e}")
            return None
    
    async def test_strategy_detail_api(self) -> Dict[str, Any]:
        """测试AI策略详情获取API"""
        print("\n📋 测试AI策略详情获取API...")
        
        # 首先创建一个测试策略
        strategy_data = {
            "name": "测试MACD策略",
            "description": "AI生成的MACD策略测试",
            "code": """
# MACD交易策略
class MACDStrategy:
    def __init__(self):
        self.fast_period = 12
        self.slow_period = 26
        self.signal_period = 9
    
    def on_data(self, data):
        # 计算MACD指标
        ema_fast = self.calculate_ema(data['close'], self.fast_period)
        ema_slow = self.calculate_ema(data['close'], self.slow_period)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, self.signal_period)
        
        # 生成交易信号
        if macd_line > signal_line:
            return "BUY"
        elif macd_line < signal_line:
            return "SELL"
        else:
            return "HOLD"
    
    def calculate_ema(self, prices, period):
        # 简化的EMA计算
        return sum(prices[-period:]) / period
""",
            "strategy_type": "strategy",
            "ai_session_id": "test_session_12345",
            "parameters": {}
        }
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        # 创建策略
        async with self.session.post(
            f"{self.base_url}/api/v1/strategies/",
            json=strategy_data,
            headers=headers
        ) as response:
            if response.status == 200:
                strategy_result = await response.json()
                strategy_id = strategy_result["id"]
                print(f"✅ 策略创建成功: ID={strategy_id}")
                
                # 测试获取AI策略详情
                async with self.session.get(
                    f"{self.base_url}/api/v1/strategies/ai-generated/{strategy_id}",
                    headers=headers
                ) as detail_response:
                    if detail_response.status == 200:
                        detail_result = await detail_response.json()
                        print(f"✅ AI策略详情获取成功")
                        print(f"   策略名称: {detail_result.get('name')}")
                        print(f"   建议参数: {detail_result.get('suggested_backtest_params', {})}")
                        return detail_result
                    else:
                        error_text = await detail_response.text()
                        print(f"❌ 获取策略详情失败: {detail_response.status} - {error_text}")
                        return None
            else:
                error_text = await response.text()
                print(f"❌ 策略创建失败: {response.status} - {error_text}")
                return None
    
    async def test_ai_strategy_backtest(self) -> Dict[str, Any]:
        """测试AI策略专用回测API"""
        print("\n🚀 测试AI策略专用回测API...")
        
        # AI策略回测配置
        backtest_config = {
            "strategy_code": """
# AI生成的RSI策略
class RSIStrategy:
    def __init__(self):
        self.rsi_period = 14
        self.oversold = 30
        self.overbought = 70
    
    def on_data(self, data):
        rsi = self.calculate_rsi(data['close'], self.rsi_period)
        
        if rsi < self.oversold:
            return "BUY"
        elif rsi > self.overbought:
            return "SELL"
        else:
            return "HOLD"
    
    def calculate_rsi(self, prices, period):
        # 简化的RSI计算
        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
""",
            "strategy_name": "AI生成RSI策略",
            "ai_session_id": "test_ai_session_67890",
            "exchange": "binance",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "initial_capital": 10000.0,
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "fee_rate": "vip0"
        }
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        # 启动AI策略回测
        async with self.session.post(
            f"{self.base_url}/api/v1/realtime-backtest/ai-strategy/start",
            json=backtest_config,
            headers=headers
        ) as response:
            if response.status == 200:
                result = await response.json()
                task_id = result.get("task_id")
                print(f"✅ AI策略回测启动成功: task_id={task_id}")
                print(f"   策略名称: {result.get('strategy_name')}")
                print(f"   AI会话ID: {result.get('ai_session_id')}")
                
                # 监控回测进度
                await self.monitor_backtest_progress(task_id)
                
                # 获取最终结果
                return await self.get_backtest_results(task_id)
            else:
                error_text = await response.text()
                print(f"❌ AI策略回测启动失败: {response.status} - {error_text}")
                return None
    
    async def monitor_backtest_progress(self, task_id: str):
        """监控回测进度"""
        print(f"\n📊 监控回测进度: {task_id}")
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        while True:
            async with self.session.get(
                f"{self.base_url}/api/v1/realtime-backtest/ai-strategy/progress/{task_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    progress_data = await response.json()
                    status = progress_data.get("status")
                    progress = progress_data.get("progress", 0)
                    current_step = progress_data.get("current_step", "")
                    
                    print(f"   进度: {progress}% - {current_step}")
                    
                    if status in ["completed", "failed"]:
                        if status == "completed":
                            print("✅ 回测完成!")
                        else:
                            error_msg = progress_data.get("error_message", "未知错误")
                            print(f"❌ 回测失败: {error_msg}")
                        break
                    
                    await asyncio.sleep(2)  # 每2秒检查一次进度
                else:
                    print(f"❌ 获取进度失败: {response.status}")
                    break
    
    async def get_backtest_results(self, task_id: str) -> Dict[str, Any]:
        """获取回测结果"""
        print(f"\n📈 获取回测结果: {task_id}")
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        async with self.session.get(
            f"{self.base_url}/api/v1/realtime-backtest/ai-strategy/results/{task_id}",
            headers=headers
        ) as response:
            if response.status == 200:
                results = await response.json()
                
                print("✅ 回测结果获取成功:")
                if results.get("results"):
                    result_data = results["results"]
                    print(f"   总收益率: {result_data.get('total_return', 0):.2f}%")
                    print(f"   夏普比率: {result_data.get('sharpe_ratio', 0):.2f}")
                    print(f"   最大回撤: {result_data.get('max_drawdown', 0):.2f}%")
                    print(f"   胜率: {result_data.get('win_rate', 0):.0f}%")
                    print(f"   交易次数: {result_data.get('total_trades', 0)}")
                    print(f"   AI评分: {result_data.get('ai_score', 0):.0f}/100")
                
                return results
            else:
                error_text = await response.text()
                print(f"❌ 获取回测结果失败: {response.status} - {error_text}")
                return None
    
    async def test_backtest_recommendations(self):
        """测试回测优化建议API"""
        print("\n💡 测试回测优化建议API...")
        
        recommendation_request = {
            "strategy_code": """
# 测试策略代码
class TestStrategy:
    def __init__(self):
        self.ma_period = 20
        self.rsi_period = 14
    
    def on_data(self, data):
        # 使用MA和RSI的组合策略
        ma = sum(data['close'][-self.ma_period:]) / self.ma_period
        current_price = data['close'][-1]
        
        if current_price > ma:
            return "BUY"
        else:
            return "SELL"
""",
            "previous_results": {
                "total_return": 5.2,
                "win_rate": 0.45,
                "max_drawdown": 0.18,
                "sharpe_ratio": 1.2
            }
        }
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        async with self.session.post(
            f"{self.base_url}/api/v1/ai/strategy/backtest-recommendations",
            json=recommendation_request,
            headers=headers
        ) as response:
            if response.status == 200:
                recommendations = await response.json()
                print("✅ 获取优化建议成功:")
                
                if recommendations.get("success"):
                    recs = recommendations.get("recommendations", {})
                    
                    # 显示参数建议
                    param_suggestions = recs.get("parameter_suggestions", [])
                    if param_suggestions:
                        print("   📊 参数优化建议:")
                        for suggestion in param_suggestions:
                            print(f"      - {suggestion.get('parameter')}: {suggestion.get('suggestion')}")
                    
                    # 显示优化提示
                    optimization_tips = recs.get("optimization_tips", [])
                    if optimization_tips:
                        print("   🎯 优化提示:")
                        for tip in optimization_tips:
                            print(f"      - {tip.get('tip')}: {tip.get('suggestion')}")
                
                return recommendations
            else:
                error_text = await response.text()
                print(f"❌ 获取优化建议失败: {response.status} - {error_text}")
                return None
    
    async def test_auto_trigger_integration(self):
        """测试自动触发回测集成API"""
        print("\n🔄 测试自动触发回测集成API...")
        
        integration_data = {
            "ai_session_id": "integration_test_session_123",
            "strategy_code": """
# 集成测试策略
class IntegrationTestStrategy:
    def __init__(self):
        self.sma_short = 10
        self.sma_long = 30
    
    def on_data(self, data):
        if len(data['close']) < self.sma_long:
            return "HOLD"
        
        sma_short = sum(data['close'][-self.sma_short:]) / self.sma_short
        sma_long = sum(data['close'][-self.sma_long:]) / self.sma_long
        
        if sma_short > sma_long:
            return "BUY"
        else:
            return "SELL"
""",
            "strategy_name": "集成测试双均线策略",
            "auto_config": True
        }
        
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        
        async with self.session.post(
            f"{self.base_url}/api/v1/ai/strategy/auto-backtest",
            json=integration_data,
            headers=headers
        ) as response:
            if response.status == 200:
                result = await response.json()
                
                if result.get("success"):
                    print("✅ 自动触发回测集成成功:")
                    print(f"   策略ID: {result.get('strategy_id')}")
                    print(f"   回测任务ID: {result.get('backtest_task_id')}")
                    print(f"   策略名称: {result.get('strategy_name')}")
                    print(f"   回测配置: {result.get('backtest_config', {})}")
                    
                    # 监控自动触发的回测
                    task_id = result.get('backtest_task_id')
                    if task_id:
                        await self.monitor_backtest_progress(task_id)
                        await self.get_backtest_results(task_id)
                else:
                    print(f"❌ 自动触发失败: {result.get('message')}")
                
                return result
            else:
                error_text = await response.text()
                print(f"❌ 自动触发回测集成失败: {response.status} - {error_text}")
                return None
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始AI策略回测集成功能完整测试")
        print("=" * 60)
        
        try:
            # 设置测试环境
            await self.setup()
            
            if not self.jwt_token:
                print("❌ 登录失败，无法继续测试")
                return
            
            # 运行各项测试
            test_results = {}
            
            # 1. 测试策略详情API
            test_results["strategy_detail"] = await self.test_strategy_detail_api()
            
            # 2. 测试AI策略回测
            test_results["ai_backtest"] = await self.test_ai_strategy_backtest()
            
            # 3. 测试优化建议
            test_results["recommendations"] = await self.test_backtest_recommendations()
            
            # 4. 测试自动触发集成
            test_results["auto_integration"] = await self.test_auto_trigger_integration()
            
            # 输出测试总结
            print("\n" + "=" * 60)
            print("🎯 测试总结:")
            for test_name, result in test_results.items():
                status = "✅ 通过" if result else "❌ 失败"
                print(f"   {test_name}: {status}")
            
            print("\n🎉 AI策略回测集成功能测试完成!")
            
        except Exception as e:
            print(f"❌ 测试过程中发生错误: {e}")
        finally:
            # 清理测试环境
            await self.cleanup()


async def main():
    """主函数"""
    tester = AIStrategyBacktestTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    print("AI策略生成后立即回测功能 - 完整测试")
    print("作者: Claude Code AI Backend Architect")
    print("时间: 2025-09-11")
    print()
    
    asyncio.run(main())