#!/usr/bin/env python3
"""
WebSocket 流式AI测试客户端 - 验证完整功能
测试WebSocket连接、认证和流式AI回复
"""

import asyncio
import websockets
import json
import time

# 使用新生成的JWT token
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTY5OTQ2NDIsImV4cCI6MTc1NzU5OTQ0MiwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.Wzj3pXgX3Ez3Nt7d5YyVBTLVk6PfswB3JujtkGVxhIg"

async def test_websocket_ai():
    """测试WebSocket流式AI功能"""
    uri = "ws://43.167.252.120:8001/ws/realtime"
    
    print(f"🔌 正在连接WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接建立成功")
            
            # 第1步: 发送认证消息
            print("\n🔐 第1步: 发送认证消息...")
            auth_message = {
                "type": "auth", 
                "token": JWT_TOKEN
            }
            await websocket.send(json.dumps(auth_message))
            print(f"📤 已发送认证消息")
            
            # 接收认证响应
            auth_response = await asyncio.wait_for(websocket.recv(), timeout=10)
            auth_data = json.loads(auth_response)
            print(f"📨 认证响应: {auth_data}")
            
            if auth_data.get("type") != "auth_success":
                print("❌ 认证失败!")
                return False
                
            print("✅ 认证成功!")
            
            # 第2步: 发送AI对话请求
            print("\n🤖 第2步: 发送AI对话请求...")
            ai_message = {
                "type": "ai_chat",
                "content": "请用流式方式回复：介绍一个简单的MACD策略，包含参数设置和风险控制",
                "ai_mode": "trader",
                "session_type": "strategy",
                "session_id": f"test_session_{int(time.time())}",
                "request_id": f"req_{int(time.time())}"
            }
            await websocket.send(json.dumps(ai_message))
            print(f"📤 已发送AI对话请求")
            
            # 第3步: 接收流式响应
            print("\n🌊 第3步: 接收流式AI响应...")
            full_response = ""
            response_chunks = 0
            
            # 设置总超时时间（2分钟）
            start_time = time.time()
            timeout_seconds = 120
            
            while True:
                # 检查总超时
                if time.time() - start_time > timeout_seconds:
                    print(f"⏰ 总超时 ({timeout_seconds}秒)，停止接收")
                    break
                
                try:
                    # 等待消息，10秒超时
                    response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    data = json.loads(response)
                    message_type = data.get("type", "unknown")
                    
                    print(f"📨 收到消息类型: {message_type}")
                    
                    if message_type == "ai_stream_start":
                        print("🌊 AI流式回复开始")
                        
                    elif message_type == "ai_stream_chunk":
                        chunk_content = data.get("content", "")
                        full_response += chunk_content
                        response_chunks += 1
                        print(f"📝 数据块 {response_chunks}: {len(chunk_content)} 字符")
                        
                    elif message_type == "ai_stream_end":
                        print("✅ AI流式回复完成")
                        print(f"📊 统计: 总共接收 {response_chunks} 个数据块")
                        print(f"📝 完整回复长度: {len(full_response)} 字符")
                        print(f"💰 成本: ${data.get('cost_usd', 0)}")
                        print(f"🔢 Token使用: {data.get('tokens_used', 0)}")
                        break
                        
                    elif message_type == "ai_stream_error":
                        error = data.get("error", "未知错误")
                        print(f"❌ AI流式错误: {error}")
                        return False
                        
                    elif message_type == "ai_progress_update":
                        step = data.get("step", 0)
                        total = data.get("total_steps", 0)
                        status = data.get("status", "")
                        message = data.get("message", "")
                        print(f"📊 进度更新: {step}/{total} - {status} - {message}")
                        
                    elif message_type == "error":
                        error = data.get("message", "未知错误")
                        print(f"❌ 系统错误: {error}")
                        return False
                        
                    else:
                        print(f"📨 其他消息: {data}")
                
                except asyncio.TimeoutError:
                    print("⏰ 10秒内未收到消息，继续等待...")
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析错误: {e}")
                    continue
                    
            # 显示完整响应（前500字符）
            if full_response:
                print(f"\n📄 AI完整回复预览 (前500字符):")
                print("-" * 60)
                print(full_response[:500])
                if len(full_response) > 500:
                    print(f"... (还有 {len(full_response) - 500} 字符)")
                print("-" * 60)
                
            print(f"\n🎉 WebSocket流式AI测试完成!")
            return True
                
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"❌ WebSocket连接被关闭: {e}")
        return False
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket异常: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("=" * 60)
    print("🚀 WebSocket 流式AI测试开始")
    print("=" * 60)
    
    success = await test_websocket_ai()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试成功! WebSocket流式AI功能正常")
    else:
        print("❌ 测试失败! WebSocket流式AI功能异常")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())