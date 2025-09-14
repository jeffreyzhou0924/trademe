#!/usr/bin/env python3
"""
AI策略回测调试测试脚本
完整测试从AI对话中的均线策略生成到回测执行的流程
"""

import asyncio
import json
import sys
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any

import aiohttp
from loguru import logger

# 测试配置
BASE_URL = "http://localhost:8001"
TEST_USER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI5IiwiZW1haWwiOiJwdWJsaWN0ZXN0QGV4YW1wbGUuY29tIiwibWVtYmVyc2hpcExldmVsIjoicHJlbWl1bSIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc2NTA2NjcsImV4cCI6MTc1NzczNzA2NywiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.ZjprHZZvjsmyubWp2crsvC8FzSfYIaZPCeTAYLtVLUc"

# 测试用的均线策略代码
SAMPLE_MA_STRATEGY = """
# 简单移动平均线交叉策略
class SimpleMAStrategy:
    def __init__(self):
        self.position = 0  # 当前持仓
        self.fast_period = 10  # 快速移动平均线周期
        self.slow_period = 20  # 慢速移动平均线周期
        
    def signal(self, data):
        # 模拟信号生成
        import random
        signal_strength = random.uniform(0.5, 0.9)
        
        if signal_strength > 0.7:
            return {
                'action': 'buy',
                'confidence': signal_strength,
                'strategy': 'ma_cross'
            }
        elif signal_strength < 0.6:
            return {
                'action': 'sell', 
                'confidence': 1 - signal_strength,
                'strategy': 'ma_cross'
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'strategy': 'ma_cross'
            }
            
    def generate_signal(self):
        # 兼容接口
        return self.signal(None)
"""

class AIBacktestDebugger:
    """AI回测调试器"""
    
    def __init__(self):
        self.session = None
        self.headers = {
            "Authorization": f"Bearer {TEST_USER_TOKEN}",
            "Content-Type": "application/json"
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_strategy_validation(self) -> Dict[str, Any]:
        """测试策略验证API"""
        logger.info("🔍 测试策略验证API")
        
        # 直接调用策略验证服务
        try:
            from app.services.strategy_service import StrategyService
            
            # 测试详细验证
            result_detailed = await StrategyService.validate_strategy_code(
                SAMPLE_MA_STRATEGY, detailed=True
            )
            logger.info(f"详细验证结果: {result_detailed}")
            logger.info(f"结果类型: {type(result_detailed)}, 长度: {len(result_detailed)}")
            
            # 测试简单验证
            result_simple = await StrategyService.validate_strategy_code(
                SAMPLE_MA_STRATEGY, detailed=False
            )
            logger.info(f"简单验证结果: {result_simple}")
            logger.info(f"结果类型: {type(result_simple)}, 长度: {len(result_simple)}")
            
            return {
                "detailed_validation": result_detailed,
                "simple_validation": result_simple,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"策略验证失败: {e}")
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def test_backtest_start_api(self) -> Dict[str, Any]:
        """测试回测启动API"""
        logger.info("🚀 测试回测启动API")
        
        config = {
            "strategy_code": SAMPLE_MA_STRATEGY,
            "exchange": "okx",
            "product_type": "perpetual",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "fee_rate": "vip0",
            "initial_capital": 10000,
            "start_date": "2025-01-01",
            "end_date": "2025-01-15",
            "data_type": "kline"
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/api/v1/realtime-backtest/start",
                headers=self.headers,
                json=config
            ) as response:
                result = await response.json()
                logger.info(f"回测启动API响应: {result}")
                
                if response.status == 200:
                    return {
                        "task_id": result.get("task_id"),
                        "status": "success",
                        "response": result
                    }
                else:
                    return {
                        "status": "error",
                        "status_code": response.status,
                        "response": result
                    }
                    
        except Exception as e:
            logger.error(f"回测启动API测试失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def test_websocket_connection(self, task_id: str) -> Dict[str, Any]:
        """测试WebSocket连接"""
        logger.info(f"🌐 测试WebSocket连接: {task_id}")
        
        try:
            import websockets
            from websockets.exceptions import ConnectionClosed
            
            uri = f"ws://localhost:8001/api/v1/realtime-backtest/ws/{task_id}"
            
            async with websockets.connect(uri) as websocket:
                logger.info("WebSocket连接成功")
                
                # 接收消息
                messages = []
                try:
                    for i in range(10):  # 最多接收10条消息
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(message)
                        messages.append(data)
                        logger.info(f"收到WebSocket消息: {data}")
                        
                        if data.get("status") in ["completed", "failed"]:
                            break
                            
                except asyncio.TimeoutError:
                    logger.info("WebSocket接收超时")
                
                return {
                    "status": "success",
                    "messages": messages
                }
                
        except Exception as e:
            logger.error(f"WebSocket测试失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def test_status_polling(self, task_id: str) -> Dict[str, Any]:
        """测试状态轮询"""
        logger.info(f"📊 测试状态轮询: {task_id}")
        
        try:
            status_history = []
            
            for i in range(15):  # 轮询15次
                async with self.session.get(
                    f"{BASE_URL}/api/v1/realtime-backtest/status/{task_id}",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        status = await response.json()
                        status_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "progress": status.get("progress"),
                            "current_step": status.get("current_step"),
                            "status": status.get("status")
                        })
                        
                        logger.info(f"状态更新 {i+1}/15: {status.get('progress', 0)}% - {status.get('current_step')}")
                        
                        if status.get("status") in ["completed", "failed"]:
                            logger.info(f"任务完成，状态: {status.get('status')}")
                            break
                    else:
                        error_msg = await response.text()
                        logger.error(f"状态查询失败: {response.status}, {error_msg}")
                        
                await asyncio.sleep(2)  # 2秒轮询间隔
            
            return {
                "status": "success",
                "status_history": status_history
            }
            
        except Exception as e:
            logger.error(f"状态轮询测试失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_complete_test(self):
        """运行完整的测试流程"""
        logger.info("🎯 开始AI策略回测完整流程测试")
        
        results = {}
        
        # 1. 测试策略验证
        logger.info("\n" + "="*60)
        logger.info("第1步: 策略验证测试")
        logger.info("="*60)
        results["validation"] = await self.test_strategy_validation()
        
        # 2. 测试回测启动
        logger.info("\n" + "="*60)
        logger.info("第2步: 回测启动测试")
        logger.info("="*60)
        backtest_result = await self.test_backtest_start_api()
        results["backtest_start"] = backtest_result
        
        task_id = None
        if backtest_result.get("status") == "success":
            task_id = backtest_result.get("task_id")
            logger.info(f"✅ 回测任务创建成功: {task_id}")
        else:
            logger.error("❌ 回测任务创建失败")
            results["final_status"] = "failed_at_start"
            return results
        
        # 3. 测试状态轮询
        logger.info("\n" + "="*60)
        logger.info("第3步: 状态轮询测试")
        logger.info("="*60)
        results["status_polling"] = await self.test_status_polling(task_id)
        
        # 4. 测试WebSocket连接
        logger.info("\n" + "="*60)
        logger.info("第4步: WebSocket连接测试")
        logger.info("="*60)
        # 创建新的回测任务用于WebSocket测试
        new_backtest = await self.test_backtest_start_api()
        if new_backtest.get("status") == "success":
            ws_task_id = new_backtest.get("task_id")
            results["websocket"] = await self.test_websocket_connection(ws_task_id)
        else:
            results["websocket"] = {"status": "skipped", "reason": "无法创建测试任务"}
        
        # 5. 生成测试报告
        logger.info("\n" + "="*60)
        logger.info("🎊 测试完成，生成报告")
        logger.info("="*60)
        
        success_count = sum(1 for result in results.values() if isinstance(result, dict) and result.get("status") == "success")
        total_count = len(results)
        
        results["final_status"] = {
            "overall": "success" if success_count == total_count else "partial",
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_count/total_count*100:.1f}%"
        }
        
        return results


async def main():
    """主函数"""
    logger.info("🚀 AI策略回测系统调试工具启动")
    
    async with AIBacktestDebugger() as debugger:
        results = await debugger.run_complete_test()
        
        # 输出最终结果
        print("\n" + "="*80)
        print("🎊 AI策略回测系统调试结果")
        print("="*80)
        
        for test_name, result in results.items():
            if test_name == "final_status":
                continue
                
            status = "✅ 成功" if result.get("status") == "success" else "❌ 失败"
            print(f"{test_name.upper()}: {status}")
            
            if result.get("status") == "error":
                print(f"  错误信息: {result.get('error', '未知错误')}")
        
        final = results.get("final_status", {})
        if isinstance(final, dict):
            print(f"\n总体结果: {final.get('overall', 'unknown').upper()}")
            print(f"成功率: {final.get('success_rate', 'N/A')}")
            print(f"成功测试: {final.get('success_count', 0)}/{final.get('total_count', 0)}")
        else:
            print(f"\n总体结果: {str(final).upper()}")
            print("成功率: N/A")
            print("成功测试: N/A")
        
        # 保存详细结果到文件
        import json
        with open("/root/trademe/backend/trading-service/ai_backtest_debug_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        print("\n📋 详细结果已保存到: ai_backtest_debug_results.json")


if __name__ == "__main__":
    asyncio.run(main())