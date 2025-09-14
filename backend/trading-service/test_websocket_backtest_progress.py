#!/usr/bin/env python3
"""
WebSocket回测进度监控测试
验证WebSocket实时进度功能是否正常工作
"""

import asyncio
import websockets
import json
import requests
import time
from typing import Optional

class WebSocketBacktestTester:
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.ws_url = "ws://localhost:8001"
        self.user_service_url = "http://localhost:3001"
        
        # 测试用户凭证
        self.test_user = {
            "email": "publictest@example.com", 
            "password": "PublicTest123!"
        }
        
        self.jwt_token: Optional[str] = None
    
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def authenticate_user(self) -> bool:
        """获取JWT token"""
        try:
            self.log("🔐 获取JWT token...")
            
            login_url = f"{self.user_service_url}/api/v1/auth/login"
            response = requests.post(login_url, json=self.test_user, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'data' in data:
                    self.jwt_token = data['data'].get('access_token')
                    self.log(f"✅ 获取token成功: {self.jwt_token[:20]}...")
                    return True
            
            self.log("❌ 获取token失败", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"❌ 认证异常: {str(e)}", "ERROR")
            return False
    
    def start_backtest_task(self) -> Optional[str]:
        """启动回测任务获取task_id"""
        try:
            self.log("🚀 启动回测任务...")
            
            # 准备测试策略
            test_strategy = """
class TestStrategy:
    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
    def on_data_update(self, data):
        # 简单的买入持有策略
        return {'action': 'buy', 'quantity': 0.1}
"""
            
            # 回测配置
            config = {
                "strategy_code": test_strategy.strip(),
                "exchange": "binance",
                "symbols": ["BTC/USDT"],
                "timeframes": ["1h"],
                "initial_capital": 10000,
                "start_date": "2024-01-01", 
                "end_date": "2024-01-31",
                "fee_rate": "vip0"
            }
            
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            url = f"{self.base_url}/api/v1/realtime-backtest/start"
            
            response = requests.post(url, json=config, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get('task_id')
                self.log(f"✅ 回测任务启动成功，task_id: {task_id}")
                return task_id
            else:
                self.log(f"❌ 启动回测失败: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ 启动回测异常: {str(e)}", "ERROR") 
            return None
    
    async def test_websocket_progress(self, task_id: str) -> bool:
        """测试WebSocket进度监控"""
        try:
            self.log("🌐 测试WebSocket进度监控...")
            
            # WebSocket连接URL
            ws_progress_url = f"{self.ws_url}/api/v1/realtime-backtest/ws/{task_id}"
            self.log(f"📡 连接WebSocket: {ws_progress_url}")
            
            # 连接WebSocket（不使用extra_headers，改为在URL中传递token）
            ws_url_with_auth = f"{ws_progress_url}?token={self.jwt_token}"
            self.log(f"📡 使用认证URL连接WebSocket")
            
            async with websockets.connect(ws_url_with_auth) as websocket:
                self.log("✅ WebSocket连接成功")
                
                message_count = 0
                max_messages = 20  # 最多接收20条消息
                timeout_seconds = 60  # 超时60秒
                
                try:
                    while message_count < max_messages:
                        # 等待消息，设置超时
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(), 
                                timeout=timeout_seconds
                            )
                            message_count += 1
                            
                            # 解析消息
                            try:
                                data = json.loads(message)
                                status = data.get('status', 'unknown')
                                progress = data.get('progress', 0)
                                step = data.get('current_step', '')
                                
                                self.log(f"📊 进度更新: {status} - {progress}% - {step}")
                                
                                # 如果回测完成，退出循环
                                if status in ['completed', 'failed']:
                                    if status == 'completed':
                                        self.log("🎉 回测完成！WebSocket监控正常")
                                        return True
                                    else:
                                        error = data.get('error', '未知错误')
                                        self.log(f"❌ 回测失败: {error}", "ERROR")
                                        return False
                                        
                            except json.JSONDecodeError:
                                self.log(f"⚠️ 无法解析WebSocket消息: {message}", "WARN")
                                continue
                                
                        except asyncio.TimeoutError:
                            self.log("⏰ WebSocket消息接收超时", "WARN")
                            break
                            
                    self.log("⚠️ 达到最大消息数量或超时，但回测未完成", "WARN")
                    return False
                    
                except websockets.exceptions.ConnectionClosed:
                    self.log("🔌 WebSocket连接关闭", "WARN")
                    return False
                    
        except Exception as e:
            self.log(f"❌ WebSocket测试异常: {str(e)}", "ERROR")
            return False
    
    async def run_complete_test(self) -> bool:
        """运行完整的WebSocket测试"""
        self.log("🚀 开始WebSocket回测进度监控测试")
        self.log("=" * 60)
        
        try:
            # 1. 认证
            if not self.authenticate_user():
                return False
            
            # 2. 启动回测任务
            task_id = self.start_backtest_task()
            if not task_id:
                return False
            
            # 3. 测试WebSocket进度监控
            success = await self.test_websocket_progress(task_id)
            
            self.log("\n" + "=" * 60)
            if success:
                self.log("🎉 WebSocket回测进度监控测试成功！", "SUCCESS")
            else:
                self.log("❌ WebSocket回测进度监控测试失败", "ERROR")
            
            return success
            
        except Exception as e:
            self.log(f"❌ 测试执行异常: {str(e)}", "ERROR")
            return False

async def main():
    """主函数"""
    tester = WebSocketBacktestTester()
    success = await tester.run_complete_test()
    
    if success:
        print("\n🎊 WebSocket测试完成 - 功能正常")
        exit(0)
    else:
        print("\n⚠️ WebSocket测试失败 - 需要检查")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())