#!/usr/bin/env python3
"""
WebSocket AI对话完整流程测试
测试从认证到AI响应的完整流程
"""

import asyncio
import websockets
import json
import time

# JWT Token (新生成的有效token)
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTY4Nzg2NjEsImV4cCI6MTc1Njk2NTA2MSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.svBu2FngotJuv1TnlXlofn3bJtm5-IQqIvr1-qvb3a0"

async def test_websocket_full_flow():
    """测试完整的WebSocket AI对话流程"""
    uri = "ws://localhost:8001/ws/realtime"
    
    print(f"🔗 连接WebSocket服务器: {uri}")
    print(f"🔑 JWT Token: {JWT_TOKEN[:20]}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接已建立")
            
            # 第1步: 发送认证消息
            auth_message = {
                "type": "auth",
                "token": JWT_TOKEN
            }
            
            print("🔐 发送认证消息...")
            await websocket.send(json.dumps(auth_message))
            
            # 第2步: 等待认证响应
            print("⏳ 等待认证响应...")
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_response = json.loads(response)
            
            print(f"📨 认证响应: {auth_response}")
            
            if auth_response.get("type") != "auth_success":
                print("❌ 认证失败")
                return
                
            print("✅ 认证成功")
            user_id = auth_response.get("user_id")
            connection_id = auth_response.get("connection_id")
            
            # 第3步: 发送AI聊天消息
            request_id = str(int(time.time() * 1000))
            
            ai_message = {
                "type": "ai_chat",
                "request_id": request_id,
                "content": "测试AI响应，请简单回复确认收到",
                "ai_mode": "trader",
                "session_type": "general",
                "session_id": f"test_session_{int(time.time())}"
            }
            
            print(f"🤖 发送AI聊天消息 (request_id: {request_id})...")
            await websocket.send(json.dumps(ai_message))
            
            # 第4步: 等待AI响应 (增加超时时间)
            print("⏳ 等待AI响应 (最多30秒)...")
            
            timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    ai_response = json.loads(response)
                    
                    print(f"📨 收到响应: {ai_response}")
                    
                    # 检查响应类型
                    response_type = ai_response.get("type")
                    
                    if response_type == "ai_chat_success":
                        print("🎉 AI响应成功!")
                        print(f"📝 AI回复: {ai_response.get('response', '')[:200]}...")
                        print(f"🪙 Token使用: {ai_response.get('tokens_used', 0)}")
                        print(f"💰 成本: ${ai_response.get('cost_usd', 0):.4f}")
                        return
                    elif response_type == "ai_chat_error":
                        print(f"❌ AI响应错误: {ai_response.get('error', 'Unknown error')}")
                        return
                    elif response_type in ["ai_progress_update", "ai_complexity_analysis"]:
                        print(f"📊 处理进度: {ai_response.get('message', '')}")
                        # 继续等待最终响应
                    else:
                        print(f"🔄 其他消息类型: {response_type}")
                        
                except asyncio.TimeoutError:
                    print("⏰ 5秒内没有收到消息，继续等待...")
                    continue
                except Exception as e:
                    print(f"❌ 接收消息错误: {e}")
                    break
            
            print("❌ 等待AI响应超时")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket连接关闭: {e}")
    except Exception as e:
        print(f"❌ WebSocket测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_full_flow())