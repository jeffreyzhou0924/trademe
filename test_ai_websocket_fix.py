#!/usr/bin/env python3
"""
测试WebSocket AI聊天功能修复
验证前端到后端的完整连接流程
"""

import asyncio
import websockets
import json
import time
import sys

async def test_websocket_ai_connection():
    """测试WebSocket AI连接和聊天功能"""
    
    # 使用预设的测试JWT token (7天有效期)
    print("🔐 使用预设测试JWT token...")
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNDk1MTQsImV4cCI6MTc1NzY1NDMxNCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.a4t9vtj3_gtv-yOHFsRRq97oew8-KZqRM5izbKBnrAk"
    print(f"✅ JWT token准备完成: {token[:20]}...")
    
    # WebSocket连接测试
    uri = "ws://localhost:8001/ws/realtime"
    print(f"🔗 尝试连接WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接已建立")
            
            # 1. 发送认证消息
            auth_message = {
                "type": "auth",
                "token": token
            }
            
            print("🔐 发送认证消息...")
            await websocket.send(json.dumps(auth_message))
            
            # 等待认证响应
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)
            
            if auth_data.get("type") == "auth_success":
                print("✅ WebSocket认证成功")
                print(f"   用户ID: {auth_data.get('user_id')}")
            else:
                print(f"❌ WebSocket认证失败: {auth_data}")
                return False
            
            # 2. 发送AI聊天消息
            ai_message = {
                "type": "ai_chat",
                "request_id": f"test_{int(time.time())}",
                "content": "请简单说明什么是量化交易",
                "ai_mode": "trader",
                "session_type": "general"
            }
            
            print("🤖 发送AI聊天消息...")
            await websocket.send(json.dumps(ai_message))
            
            # 3. 监听AI响应 (流式或一次性)
            print("📡 等待AI响应...")
            response_count = 0
            max_responses = 20  # 最多等待20个响应
            
            while response_count < max_responses:
                try:
                    # 设置超时防止无限等待
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    response_count += 1
                    
                    msg_type = data.get("type")
                    
                    if msg_type == "ai_chat_start":
                        print("🚀 AI开始处理请求")
                        
                    elif msg_type == "ai_complexity_analysis":
                        print(f"🧠 AI复杂性分析: {data.get('complexity')} ({data.get('estimated_time_seconds')}秒)")
                        
                    elif msg_type == "ai_progress_update":
                        print(f"📈 AI进度更新: {data.get('step')}/{data.get('total_steps')} - {data.get('message')}")
                        
                    elif msg_type == "ai_stream_start":
                        print("🌊 开始流式响应")
                        
                    elif msg_type == "ai_stream_chunk":
                        chunk = data.get("chunk", "")
                        print(f"📝 流式数据块: {chunk[:50]}{'...' if len(chunk) > 50 else ''}")
                        
                    elif msg_type == "ai_stream_end":
                        print("✅ 流式响应完成")
                        print(f"   总tokens: {data.get('tokens_used', 0)}")
                        print(f"   成本: ${data.get('cost_usd', 0):.4f}")
                        full_response = data.get('full_response', '')
                        if full_response:
                            print(f"   完整响应: {full_response[:100]}{'...' if len(full_response) > 100 else ''}")
                        break
                        
                    elif msg_type == "ai_chat_success":
                        print("✅ AI聊天成功")
                        print(f"   响应: {data.get('response', '')[:100]}...")
                        print(f"   tokens: {data.get('tokens_used', 0)}")
                        print(f"   成本: ${data.get('cost_usd', 0):.4f}")
                        break
                        
                    elif msg_type == "ai_chat_error":
                        print(f"❌ AI聊天错误: {data.get('error')}")
                        break
                        
                    elif msg_type == "ai_stream_error":
                        print(f"❌ 流式响应错误: {data.get('error')}")
                        break
                        
                    elif msg_type in ["heartbeat", "pong"]:
                        # 忽略心跳消息
                        pass
                        
                    else:
                        print(f"📨 其他消息: {msg_type} - {data}")
                        
                except asyncio.TimeoutError:
                    print("⏰ 响应超时，测试结束")
                    break
                except Exception as e:
                    print(f"❌ 接收消息错误: {e}")
                    break
            
            print(f"📊 总共接收到 {response_count} 个响应")
            return True
            
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"❌ WebSocket连接被关闭: {e}")
        return False
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🧪 开始WebSocket AI聊天功能测试")
    print("=" * 50)
    
    # 检查后端服务是否运行
    try:
        import requests
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            print("✅ 后端服务运行正常")
        else:
            print(f"⚠️ 后端服务状态异常: {response.status_code}")
    except Exception as e:
        print(f"❌ 无法连接到后端服务: {e}")
        print("请确保后端服务正在运行 (python app/main.py)")
        return False
    
    # 执行WebSocket测试
    success = await test_websocket_ai_connection()
    
    print("=" * 50)
    if success:
        print("🎉 WebSocket AI聊天功能测试成功！")
        return True
    else:
        print("❌ WebSocket AI聊天功能测试失败！")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        sys.exit(1)