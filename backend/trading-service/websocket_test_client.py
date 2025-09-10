#!/usr/bin/env python3
"""
WebSocket AI对话测试客户端
演示如何使用WebSocket进行AI对话，解决HTTP超时问题
"""

import asyncio
import json
import websockets
import uuid
from typing import Optional
import time

class AIWebSocketClient:
    """AI WebSocket客户端"""
    
    def __init__(self, uri: str, token: str):
        self.uri = uri
        self.token = token
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connection_id: Optional[str] = None
        self.user_id: Optional[int] = None
        
    async def connect(self):
        """连接到WebSocket服务器"""
        print(f"🔗 正在连接到: {self.uri}")
        self.websocket = await websockets.connect(self.uri)
        print("✅ WebSocket连接已建立")
        
        # 发送认证消息
        auth_message = {
            "type": "authenticate",
            "token": self.token
        }
        
        await self.websocket.send(json.dumps(auth_message))
        print("🔐 已发送认证消息")
        
        # 等待认证响应
        response = await self.websocket.recv()
        auth_result = json.loads(response)
        
        print(f"🔍 收到认证响应: {auth_result}")
        
        if auth_result.get("type") == "auth_success":
            self.connection_id = auth_result.get("connection_id")
            self.user_id = auth_result.get("user_id")
            print(f"✅ 认证成功! 连接ID: {self.connection_id}, 用户ID: {self.user_id}")
        elif auth_result.get("type") == "connection_established":
            # 可能是连接建立消息，再等待一个认证响应
            self.connection_id = auth_result.get("connection_id") 
            self.user_id = auth_result.get("user_id")
            print(f"✅ 连接已建立! 连接ID: {self.connection_id}, 用户ID: {self.user_id}")
        else:
            print(f"❌ 认证失败: {auth_result.get('message', '未知错误')}")
            return False
        
        return True
    
    async def send_ai_chat(self, content: str, ai_mode: str = "trader", session_type: str = "strategy"):
        """发送AI对话请求"""
        if not self.websocket:
            print("❌ WebSocket未连接")
            return
        
        request_id = str(uuid.uuid4())
        message = {
            "type": "ai_chat",
            "request_id": request_id,
            "content": content,
            "ai_mode": ai_mode,
            "session_type": session_type
        }
        
        await self.websocket.send(json.dumps(message))
        print(f"📤 已发送AI对话请求 (ID: {request_id[:8]}...)")
        print(f"💭 内容: {content}")
        
        return request_id
    
    async def listen_for_messages(self):
        """监听来自服务器的消息"""
        if not self.websocket:
            print("❌ WebSocket未连接")
            return
            
        print("👂 开始监听服务器消息...")
        
        try:
            async for message in self.websocket:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "heartbeat":
                    print("💓 收到心跳包")
                    
                elif message_type == "ai_chat_start":
                    print(f"🤖 AI开始处理: {data.get('message')}")
                    
                elif message_type == "ai_complexity_analysis":
                    complexity = data.get('complexity')
                    estimated_time = data.get('estimated_time_seconds')
                    print(f"📊 复杂度分析: {complexity} (预估时间: {estimated_time}秒)")
                    
                elif message_type == "ai_progress_update":
                    step = data.get('step')
                    total_steps = data.get('total_steps')
                    status = data.get('status')
                    message = data.get('message')
                    print(f"⏳ 进度更新 [{step}/{total_steps}]: {message}")
                    
                elif message_type == "ai_chat_success":
                    print("✅ AI回复生成完成!")
                    print(f"📝 回复内容: {data.get('response')[:200]}...")
                    print(f"🔢 Token使用: {data.get('tokens_used')}")
                    print(f"🤖 模型: {data.get('model')}")
                    print(f"💰 成本: ${data.get('cost_usd', 0):.4f}")
                    
                elif message_type == "ai_chat_error":
                    print(f"❌ AI对话错误: {data.get('message')}")
                    print(f"🔍 错误详情: {data.get('error')}")
                    
                elif message_type == "ai_chat_cancelled":
                    print(f"🚫 AI对话已取消: {data.get('message')}")
                    
                else:
                    print(f"📨 收到消息: {data}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket连接已关闭")
        except Exception as e:
            print(f"❌ 监听消息时发生错误: {e}")
    
    async def disconnect(self):
        """断开WebSocket连接"""
        if self.websocket:
            await self.websocket.close()
            print("👋 WebSocket连接已断开")


async def main():
    """主函数"""
    print("🚀 WebSocket AI对话测试客户端")
    print("=" * 50)
    
    # 配置参数
    WS_URI = "ws://localhost:8001/api/v1/ai/ws/chat"
    JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTY3Mzg3NTAsImV4cCI6MTc1NjgyNTE1MCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.ZnHws7F0BgSQEgFoHDZYTeU1hvb8v0hnwH-wTSqImMI"
    
    # 创建客户端
    client = AIWebSocketClient(WS_URI, JWT_TOKEN)
    
    try:
        # 连接到服务器
        if not await client.connect():
            return
        
        # 创建消息监听任务
        listen_task = asyncio.create_task(client.listen_for_messages())
        
        print("\n🎯 测试场景：")
        
        # 测试: 简单请求
        print("\n📝 测试: 简单AI请求")
        await client.send_ai_chat("你好，这是一个WebSocket测试")
        
        # 等待响应
        print("\n⏱️  等待AI响应 (最多20秒)...")
        await asyncio.sleep(20)
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断测试")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        
    finally:
        await client.disconnect()
        print("\n🏁 测试完成")


if __name__ == "__main__":
    # 安装依赖提示
    try:
        import websockets
    except ImportError:
        print("❌ 请先安装websockets库: pip install websockets")
        exit(1)
    
    # 运行测试
    asyncio.run(main())