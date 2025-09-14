#!/usr/bin/env python3
"""
AI对话回测系统集成测试 - 修复JWT认证和策略代码传递问题
测试完整的AI对话→策略生成→回测流程
"""

import asyncio
import json
import requests
import time
from typing import Dict, Any, Optional

class AIBacktestIntegrationTester:
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.user_service_url = "http://localhost:3001"
        
        # 测试用户凭证
        self.test_user = {
            "email": "publictest@example.com",
            "password": "PublicTest123!"
        }
        
        self.jwt_token: Optional[str] = None
        self.headers: Dict[str, str] = {
            "Content-Type": "application/json"
        }
    
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def authenticate_user(self) -> bool:
        """用户认证获取JWT token"""
        try:
            self.log("🔐 开始用户认证...")
            
            # 向用户服务登录
            login_url = f"{self.user_service_url}/api/v1/auth/login"
            response = requests.post(login_url, json=self.test_user, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # 用户服务返回的是data.access_token
                if data.get('success') and 'data' in data:
                    self.jwt_token = data['data'].get('access_token')
                else:
                    self.jwt_token = data.get('token')  # 备用格式
                
                if self.jwt_token:
                    # 更新请求头
                    self.headers['Authorization'] = f'Bearer {self.jwt_token}'
                    self.log(f"✅ 认证成功，Token: {self.jwt_token[:20]}...")
                    return True
                else:
                    self.log("❌ 认证响应中没有token", "ERROR")
                    return False
            else:
                self.log(f"❌ 认证失败: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ 认证异常: {str(e)}", "ERROR")
            return False
    
    def test_trading_service_connection(self) -> bool:
        """测试交易服务连接"""
        try:
            self.log("🔗 测试交易服务连接...")
            
            # 测试健康检查端点
            health_url = f"{self.base_url}/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                self.log("✅ 交易服务连接正常")
                return True
            else:
                self.log(f"❌ 交易服务连接失败: {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ 交易服务连接异常: {str(e)}", "ERROR")
            return False
    
    def test_jwt_token_validation(self) -> bool:
        """测试JWT token验证"""
        try:
            self.log("🔑 测试JWT token验证...")
            
            # 调用需要认证的端点 - 使用简单的GET端点
            test_url = f"{self.base_url}/api/v1/ai/usage/stats"
            response = requests.get(test_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                self.log("✅ JWT token验证成功")
                return True
            elif response.status_code == 401:
                self.log("❌ JWT token验证失败 - 401 Unauthorized", "ERROR")
                self.log(f"请求头: {self.headers}", "DEBUG")
                return False
            else:
                self.log(f"❌ 意外的响应状态: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ JWT token验证异常: {str(e)}", "ERROR")
            return False
    
    def test_realtime_backtest_api(self) -> bool:
        """测试实时回测API的JWT token传递"""
        try:
            self.log("📊 测试实时回测API...")
            
            # 准备测试策略代码
            test_strategy_code = """
class MACDDivergenceStrategy:
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        
    def on_data_update(self, data):
        # 简单的MACD策略逻辑
        close_price = data['close']
        
        # 模拟MACD计算
        if len(data.get('history', [])) > 26:
            # 买入信号
            if close_price > data.get('sma_20', 0):
                return {'action': 'buy', 'quantity': 0.1}
            # 卖出信号  
            elif close_price < data.get('sma_50', 0):
                return {'action': 'sell', 'quantity': 0.1}
        
        return {'action': 'hold', 'quantity': 0}
"""
            
            # 构建回测配置
            backtest_config = {
                "strategy_code": test_strategy_code.strip(),
                "exchange": "binance",
                "product_type": "spot",
                "symbols": ["BTC/USDT"],
                "timeframes": ["1h"],
                "fee_rate": "vip0",
                "initial_capital": 10000,
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "data_type": "kline"
            }
            
            # 发送回测请求
            backtest_url = f"{self.base_url}/api/v1/realtime-backtest/start"
            
            self.log(f"📤 发送回测请求到: {backtest_url}")
            self.log(f"🔑 使用认证头: Bearer {self.jwt_token[:20]}...")
            self.log(f"📝 策略代码长度: {len(test_strategy_code)} 字符")
            
            response = requests.post(
                backtest_url,
                json=backtest_config,
                headers=self.headers,
                timeout=30
            )
            
            self.log(f"📥 回测API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get('task_id')
                
                self.log("✅ 回测任务启动成功！")
                self.log(f"📋 任务ID: {task_id}")
                
                # 简单监控回测进度
                return self.monitor_backtest_progress(task_id)
                
            elif response.status_code == 401:
                self.log("❌ JWT认证失败 - 401 Unauthorized", "ERROR")
                self.log(f"响应内容: {response.text}", "DEBUG")
                return False
            else:
                self.log(f"❌ 回测API调用失败: {response.status_code}", "ERROR")
                self.log(f"响应内容: {response.text}", "DEBUG")
                return False
                
        except Exception as e:
            self.log(f"❌ 回测API测试异常: {str(e)}", "ERROR")
            return False
    
    def monitor_backtest_progress(self, task_id: str, max_wait: int = 300) -> bool:
        """监控回测进度"""
        try:
            self.log(f"⏳ 开始监控回测进度 (最多等待{max_wait}秒)...")
            
            start_time = time.time()
            
            while (time.time() - start_time) < max_wait:
                # 检查回测进度
                progress_url = f"{self.base_url}/api/v1/realtime-backtest/status/{task_id}"
                response = requests.get(progress_url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    progress = data.get('progress', 0)
                    
                    self.log(f"📊 回测状态: {status}, 进度: {progress}%")
                    
                    if status == 'completed':
                        self.log("🎉 回测完成！")
                        return True
                    elif status == 'failed':
                        error = data.get('error', '未知错误')
                        self.log(f"❌ 回测失败: {error}", "ERROR")
                        return False
                    
                else:
                    self.log(f"⚠️ 无法获取回测状态: {response.status_code}", "WARN")
                
                time.sleep(5)  # 等待5秒后重试
            
            self.log("⏰ 回测监控超时", "WARN")
            return False
            
        except Exception as e:
            self.log(f"❌ 监控回测进度异常: {str(e)}", "ERROR")
            return False
    
    def run_complete_test(self) -> bool:
        """运行完整的集成测试"""
        self.log("🚀 开始AI对话回测系统完整集成测试")
        self.log("=" * 60)
        
        test_results = {
            "authentication": False,
            "service_connection": False,
            "jwt_validation": False,
            "backtest_api": False
        }
        
        try:
            # 1. 用户认证
            test_results["authentication"] = self.authenticate_user()
            if not test_results["authentication"]:
                self.log("❌ 认证失败，终止测试", "ERROR")
                return False
            
            # 2. 测试交易服务连接
            test_results["service_connection"] = self.test_trading_service_connection()
            if not test_results["service_connection"]:
                self.log("❌ 交易服务连接失败，终止测试", "ERROR")  
                return False
            
            # 3. 测试JWT token验证
            test_results["jwt_validation"] = self.test_jwt_token_validation()
            if not test_results["jwt_validation"]:
                self.log("❌ JWT验证失败，终止测试", "ERROR")
                return False
            
            # 4. 测试实时回测API
            test_results["backtest_api"] = self.test_realtime_backtest_api()
            
            # 总结测试结果
            self.log("\n" + "=" * 60)
            self.log("📋 测试结果总结:")
            for test_name, result in test_results.items():
                status = "✅ 通过" if result else "❌ 失败"
                self.log(f"  - {test_name}: {status}")
            
            all_passed = all(test_results.values())
            if all_passed:
                self.log("\n🎉 所有测试通过！AI对话回测系统集成正常", "SUCCESS")
            else:
                self.log("\n⚠️ 部分测试失败，需要进一步检查", "WARN")
            
            return all_passed
            
        except Exception as e:
            self.log(f"❌ 集成测试异常: {str(e)}", "ERROR")
            return False

def main():
    """主函数"""
    tester = AIBacktestIntegrationTester()
    success = tester.run_complete_test()
    
    if success:
        print("\n🎊 集成测试完成 - 系统正常运行")
        exit(0)
    else:
        print("\n⚠️ 集成测试失败 - 需要修复问题")
        exit(1)

if __name__ == "__main__":
    main()