#!/usr/bin/env python3
"""
WebSocket AI客户端测试
直接连接WebSocket端点，测试AI流式对话功能
"""

import asyncio
import websockets
import json
from datetime import datetime

# 测试用JWT Token
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNjI2MjQsImV4cCI6MTc1NzY2NzQyNCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.RIWjmnuDazOp2csma62CQ_3OJJ47LQQI_KnQJ9mcylk"

async def test_websocket_ai_chat():
    """测试WebSocket AI对话功能"""
    
    uri = "ws://43.167.252.120:8001/ws/realtime"
    
    print("🔌 WebSocket AI聊天测试开始")
    print("=" * 50)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功")
            
            # 步骤1: 发送认证消息 (直接发送JWT token字符串)
            print("\n📋 步骤1: 发送认证信息")
            
            await websocket.send(JWT_TOKEN)
            print("  📤 认证消息已发送")
            
            # 接收认证响应
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)
            print(f"  📥 认证响应: {auth_data}")
            
            if auth_data.get("status") == "authenticated":
                print("  ✅ 认证成功")
                
                # 步骤2: 发送AI聊天请求
                print("\n📋 步骤2: 发送AI聊天请求")
                
                ai_message = {
                    "type": "ai_chat",
                    "content": "你好，请简单说一句hello world",
                    "ai_mode": "trader",
                    "session_type": "general",
                    "request_id": "test_001"
                }
                
                await websocket.send(json.dumps(ai_message))
                print("  📤 AI聊天请求已发送")
                print("  🤖 等待AI响应...")
                
                # 步骤3: 接收流式响应
                print("\n📋 步骤3: 接收流式响应")
                
                response_count = 0
                full_response = ""
                start_time = datetime.now()
                
                # 设置超时，最多等待60秒
                timeout = 60
                
                while True:
                    try:
                        # 等待消息，设置超时
                        response = await asyncio.wait_for(websocket.recv(), timeout=10)
                        response_data = json.loads(response)
                        response_count += 1
                        
                        response_type = response_data.get("type")
                        elapsed = (datetime.now() - start_time).total_seconds()
                        
                        print(f"  📥 [{elapsed:.1f}s] 消息{response_count}: {response_type}")
                        
                        if response_type == "ai_stream_start":
                            print("     🌊 流式响应开始")
                            
                        elif response_type == "ai_stream_chunk":
                            chunk = response_data.get("chunk", "")
                            full_response += chunk
                            print(f"     📦 数据块: {chunk[:30]}{'...' if len(chunk) > 30 else ''}")
                            
                        elif response_type == "ai_stream_end":
                            print("     🎯 流式响应完成")
                            print(f"     📊 完整响应长度: {len(full_response)} 字符")
                            print(f"     💰 Token使用: {response_data.get('tokens_used', 0)}")
                            print(f"     💸 成本: ${response_data.get('cost_usd', 0.0):.6f}")
                            break
                            
                        elif response_type in ["ai_stream_error", "ai_chat_error"]:
                            print(f"     ❌ AI错误: {response_data.get('error', 'Unknown error')}")
                            break
                            
                        elif response_type in ["ai_progress_update", "ai_complexity_analysis"]:
                            print(f"     ⏳ 进度: {response_data.get('message', '')}")
                            
                        else:
                            print(f"     📋 其他消息: {response_data}")
                        
                        # 超时检查
                        if elapsed > timeout:
                            print(f"     ⏰ 等待超时 ({timeout}秒)")
                            break
                            
                    except asyncio.TimeoutError:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        print(f"  ⏰ 等待响应超时 ({elapsed:.1f}秒)")
                        break
                    except json.JSONDecodeError as e:
                        print(f"  ❌ JSON解析错误: {e}")
                        break
                
                # 结果总结
                total_time = (datetime.now() - start_time).total_seconds()
                print(f"\n📊 测试结果总结:")
                print(f"   总响应时间: {total_time:.2f}秒")
                print(f"   接收消息数: {response_count}")
                print(f"   完整响应长度: {len(full_response)} 字符")
                
                if full_response:
                    print("   ✅ WebSocket AI聊天测试成功!")
                    print(f"   📝 AI回复预览: {full_response[:100]}...")
                else:
                    print("   ❌ WebSocket AI聊天测试失败 - 未收到有效响应")
            else:
                print(f"  ❌ 认证失败: {auth_data}")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket连接意外关闭: {e}")
    except Exception as e:
        print(f"❌ WebSocket测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket_ai_chat())