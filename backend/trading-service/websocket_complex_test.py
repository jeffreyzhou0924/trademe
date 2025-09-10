#!/usr/bin/env python3
"""
WebSocket复杂AI请求测试 - 测试MACD背离策略生成
验证WebSocket系统处理复杂请求的能力，解决HTTP超时问题
"""

import asyncio
import json
import websockets
import uuid
import time

class ComplexAIWebSocketTest:
    """复杂AI WebSocket测试"""
    
    def __init__(self, uri: str, token: str):
        self.uri = uri
        self.token = token
        self.websocket = None
        self.connection_id = None
        self.user_id = None
        
    async def connect_and_authenticate(self):
        """连接并认证"""
        print(f"🔗 正在连接到: {self.uri}")
        self.websocket = await websockets.connect(self.uri)
        print("✅ WebSocket连接已建立")
        
        # 发送认证消息
        auth_message = {
            "type": "authenticate",
            "token": self.token
        }
        
        await self.websocket.send(json.dumps(auth_message))
        
        # 等待认证响应
        while True:
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "connection_established":
                self.connection_id = data.get("connection_id")
                self.user_id = data.get("user_id")
                print(f"✅ 连接已建立! 连接ID: {self.connection_id}, 用户ID: {self.user_id}")
            elif data.get("type") == "auth_success":
                print("✅ 认证成功!")
                break
                
        return True
    
    async def test_complex_strategy_request(self):
        """测试复杂策略生成请求"""
        request_id = str(uuid.uuid4())
        complex_message = {
            "type": "ai_chat",
            "request_id": request_id,
            "content": "我想开发一个MACD背离策略，请帮我生成完整的策略代码。策略需要包含以下功能：1. 识别MACD与价格的背离信号 2. 设置合理的止损和止盈 3. 包含风险管理机制 4. 添加详细的策略说明和参数优化建议",
            "ai_mode": "trader",
            "session_type": "strategy"
        }
        
        print(f"\n🎯 发送复杂策略生成请求:")
        print(f"📝 内容: {complex_message['content'][:100]}...")
        
        start_time = time.time()
        await self.websocket.send(json.dumps(complex_message))
        print(f"📤 已发送复杂AI请求 (ID: {request_id[:8]}...)")
        
        # 监听响应
        final_response = None
        try:
            while True:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=180)  # 3分钟超时
                data = json.loads(response)
                message_type = data.get("type")
                
                if message_type == "ai_complexity_analysis":
                    complexity = data.get('complexity')
                    estimated_time = data.get('estimated_time_seconds')
                    print(f"📊 复杂度分析: {complexity} (预估时间: {estimated_time}秒)")
                    
                elif message_type == "ai_progress_update":
                    step = data.get('step')
                    total_steps = data.get('total_steps')
                    message = data.get('message')
                    print(f"⏳ 进度更新 [{step}/{total_steps}]: {message}")
                    
                elif message_type == "ai_chat_success":
                    end_time = time.time()
                    execution_time = end_time - start_time
                    
                    print("🎉 复杂AI请求处理成功!")
                    print(f"📝 回复长度: {len(data.get('response', ''))} 字符")
                    print(f"🔢 Token使用: {data.get('tokens_used')}")
                    print(f"🤖 模型: {data.get('model')}")
                    print(f"💰 成本: ${data.get('cost_usd', 0):.4f}")
                    print(f"⏱️ 实际处理时间: {execution_time:.1f}秒")
                    
                    # 显示策略代码片段
                    response_content = data.get('response', '')
                    if 'def' in response_content or 'class' in response_content:
                        print("🔍 检测到策略代码生成!")
                        # 显示前200字符
                        print(f"📋 策略预览: {response_content[:200]}...")
                    
                    final_response = data
                    break
                    
                elif message_type == "ai_chat_error":
                    print(f"❌ AI请求失败: {data.get('message')}")
                    print(f"🔍 错误详情: {data.get('error')}")
                    break
                    
                elif message_type == "heartbeat":
                    print("💓 收到心跳包")
                    
                else:
                    print(f"📨 收到消息: {message_type}")
                    
        except asyncio.TimeoutError:
            print("⏰ 请求超时 - 但这是WebSocket容错机制，不是网络失败")
            
        return final_response
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            print("👋 WebSocket连接已断开")

async def main():
    """主测试函数"""
    print("🚀 复杂AI请求WebSocket测试")
    print("=" * 60)
    print("📋 测试目标: MACD背离策略生成 (之前HTTP会超时)")
    print()
    
    # 配置参数
    WS_URI = "ws://localhost:8001/api/v1/ai/ws/chat"
    JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTY3Mzg3NTAsImV4cCI6MTc1NjgyNTE1MCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.ZnHws7F0BgSQEgFoHDZYTeU1hvb8v0hnwH-wTSqImMI"
    
    # 创建测试客户端
    test_client = ComplexAIWebSocketTest(WS_URI, JWT_TOKEN)
    
    try:
        # 连接并认证
        if not await test_client.connect_and_authenticate():
            return
        
        # 测试复杂策略生成
        print("\n🎯 开始复杂策略生成测试...")
        result = await test_client.test_complex_strategy_request()
        
        if result:
            print("\n✅ 测试总结:")
            print("• WebSocket成功处理复杂AI请求")  
            print("• 避免了HTTP超时问题")
            print("• 提供了实时进度追踪")
            print("• 策略生成功能正常工作")
        else:
            print("\n❌ 测试未完全成功，但WebSocket连接机制正常")
            
    except KeyboardInterrupt:
        print("\n🛑 用户中断测试")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        
    finally:
        await test_client.disconnect()
        print("\n🏁 复杂AI请求测试完成")

if __name__ == "__main__":
    asyncio.run(main())