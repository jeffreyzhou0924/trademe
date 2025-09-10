#!/usr/bin/env python3
"""
持续WebSocket连接测试 - 模拟浏览器行为
保持连接打开，等待多轮对话
"""

import asyncio
import websockets
import json
import time
import signal

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNDY4OTksImV4cCI6MTc1NzY1MTY5OSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.Yt0HL40DHX8_--Ua_lEi-3HBZp3SKRoVR120hn9g-dM"

class PersistentWebSocketTest:
    def __init__(self):
        self.websocket = None
        self.running = True
        
    async def connect_and_maintain(self):
        """建立并维护WebSocket连接"""
        uri = "ws://43.167.252.120:8001/ws/realtime"
        
        print(f"🔌 正在连接到: {uri}")
        
        try:
            async with websockets.connect(uri) as websocket:
                self.websocket = websocket
                print("✅ WebSocket连接成功建立")
                
                # 步骤1：认证
                await self.authenticate()
                
                # 步骤2：保持连接并处理消息
                await self.maintain_connection()
                    
        except websockets.exceptions.ConnectionClosed as e:
            print(f"❌ WebSocket连接关闭: {e.code} - {e.reason}")
            return e.code, e.reason
        except Exception as e:
            print(f"❌ 连接错误: {e}")
            return None, str(e)
    
    async def authenticate(self):
        """发送认证消息"""
        auth_message = {
            "type": "auth",
            "token": JWT_TOKEN
        }
        
        print("🔐 发送认证消息...")
        await self.websocket.send(json.dumps(auth_message))
        
        # 等待认证响应
        response = await self.websocket.recv()
        auth_response = json.loads(response)
        print(f"📨 收到认证响应: {auth_response}")
        
        if auth_response.get("type") != "auth_success":
            raise Exception(f"认证失败: {auth_response}")
            
        print("✅ 认证成功！")
    
    async def send_ai_request(self, content):
        """发送AI聊天请求"""
        ai_message = {
            "type": "ai_chat",
            "content": content,
            "ai_mode": "trader", 
            "session_type": "strategy",
            "session_id": f"persistent_test_{int(time.time())}",
            "complexity": "simple",
            "request_id": f"req_{int(time.time())}"
        }
        
        print(f"🤖 发送AI请求: {content}")
        await self.websocket.send(json.dumps(ai_message))
    
    async def maintain_connection(self):
        """维持连接，处理消息"""
        print("🔄 开始维持连接，等待消息...")
        
        # 发送第一个AI请求
        await self.send_ai_request("简单介绍MACD指标")
        
        message_count = 0
        ai_response_complete = False
        
        while self.running:
            try:
                # 等待消息，5分钟超时
                response = await asyncio.wait_for(self.websocket.recv(), timeout=300.0)
                data = json.loads(response)
                message_count += 1
                
                print(f"📨 [{message_count}] 收到: {data.get('type')}")
                
                # 处理不同类型的消息
                if data.get("type") == "ai_stream_start":
                    print("🌊 AI流式回复开始")
                    ai_response_complete = False
                elif data.get("type") == "ai_stream_chunk":
                    chunk = data.get("content", "")
                    print(f"📝 数据块: {len(chunk)} 字符")
                elif data.get("type") == "ai_stream_end":
                    print("✅ AI流式回复完成")
                    ai_response_complete = True
                    
                    # AI响应完成后，等待几秒钟，然后发送另一个请求测试持久性
                    print("⏰ 等待5秒后发送第二个请求...")
                    await asyncio.sleep(5)
                    await self.send_ai_request("解释什么是RSI指标")
                    
                elif data.get("type") == "ai_stream_error":
                    print(f"❌ AI错误: {data.get('error')}")
                elif data.get("type") == "error":
                    print(f"❌ 系统错误: {data.get('message')}")
                    
                # 如果收到了足够多的消息，主动关闭测试
                if message_count >= 50:
                    print("✅ 收到足够多的消息，测试完成")
                    break
                    
            except asyncio.TimeoutError:
                print("⏰ 5分钟无消息，发送心跳...")
                ping_message = {"type": "ping"}
                await self.websocket.send(json.dumps(ping_message))
            except websockets.exceptions.ConnectionClosed as e:
                print(f"🔌 连接被服务器关闭: {e.code} - {e.reason}")
                break
            except Exception as e:
                print(f"❌ 消息处理错误: {e}")
                break
        
        print("📝 连接维护结束")

def signal_handler(sig, frame):
    print("\n🛑 收到中断信号，准备关闭...")
    global test
    test.running = False

async def main():
    global test
    test = PersistentWebSocketTest()
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 开始持续WebSocket连接测试...")
    print("   测试目标：模拟浏览器行为，保持连接打开")
    print("   按 Ctrl+C 可以随时停止测试")
    
    code, reason = await test.connect_and_maintain()
    
    print("📋 测试结果:")
    if code is None:
        print("   状态: 异常结束")
        print(f"   原因: {reason}")
    else:
        print(f"   关闭代码: {code}")
        print(f"   关闭原因: {reason}")
        if code == 1000:
            print("   这是正常关闭，表示连接正常工作")
        elif code == 1006:
            print("   这是异常关闭，表示可能有服务器端问题")

if __name__ == "__main__":
    asyncio.run(main())