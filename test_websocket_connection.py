#!/usr/bin/env python3
"""
WebSocket连接测试脚本
测试http://43.167.252.120:8001/ws/realtime端点
"""

import asyncio
import websockets
import json
import time

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNDY4OTksImV4cCI6MTc1NzY1MTY5OSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.Yt0HL40DHX8_--Ua_lEi-3HBZp3SKRoVR120hn9g-dM"

async def test_websocket_connection():
    """测试WebSocket连接和AI对话"""
    uri = "ws://43.167.252.120:8001/ws/realtime"
    
    print(f"🔌 正在连接到: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功建立")
            
            # 步骤1：发送认证消息
            auth_message = {
                "type": "auth",
                "token": JWT_TOKEN
            }
            
            print("🔐 发送认证消息...")
            await websocket.send(json.dumps(auth_message))
            
            # 等待认证响应
            response = await websocket.recv()
            auth_response = json.loads(response)
            print(f"📨 收到认证响应: {auth_response}")
            
            if auth_response.get("type") == "auth_success":
                print("✅ 认证成功！")
                
                # 步骤2：发送AI聊天请求
                ai_message = {
                    "type": "ai_chat",
                    "content": "请简单介绍一下MACD指标",
                    "ai_mode": "trader", 
                    "session_type": "strategy",
                    "session_id": f"test_{int(time.time())}",
                    "complexity": "simple",
                    "request_id": f"req_{int(time.time())}"
                }
                
                print("🤖 发送AI聊天请求...")
                await websocket.send(json.dumps(ai_message))
                
                # 步骤3：监听AI响应
                print("👂 等待AI响应...")
                response_count = 0
                full_response = ""
                
                while response_count < 20:  # 最多等待20条消息
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        data = json.loads(response)
                        response_count += 1
                        
                        print(f"📨 [{response_count}] 收到消息类型: {data.get('type')}")
                        
                        if data.get("type") == "ai_stream_start":
                            print("🌊 AI流式回复开始")
                        elif data.get("type") == "ai_stream_chunk":
                            chunk = data.get("content", "")
                            full_response += chunk
                            print(f"📝 收到数据块: {len(chunk)} 字符")
                        elif data.get("type") == "ai_stream_end":
                            print("✅ AI流式回复完成")
                            print(f"完整回复内容: {full_response}")
                            break
                        elif data.get("type") == "ai_stream_error":
                            print(f"❌ AI流式错误: {data.get('error')}")
                            break
                        elif data.get("type") == "error":
                            print(f"❌ 系统错误: {data.get('message')}")
                            break
                            
                    except asyncio.TimeoutError:
                        print("⏰ 等待响应超时")
                        break
                    except Exception as e:
                        print(f"❌ 处理响应错误: {e}")
                        break
                        
            else:
                print(f"❌ 认证失败: {auth_response}")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket连接关闭: {e}")
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket异常: {e}")
    except Exception as e:
        print(f"❌ 连接错误: {e}")

if __name__ == "__main__":
    print("🚀 开始WebSocket连接测试...")
    asyncio.run(test_websocket_connection())
    print("📝 测试完成")