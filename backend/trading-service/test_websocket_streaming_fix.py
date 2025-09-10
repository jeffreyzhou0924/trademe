#!/usr/bin/env python3
"""
WebSocket流式响应修复验证测试
验证前端消息处理修复后的完整流程
"""

import asyncio
import websockets
import json
from datetime import datetime

# 测试用JWT Token
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNzE3OTEsImV4cCI6MTc1NzY3NjU5MSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.FTG0V4rJ3iGj43jZFDBWzoerg99XahrkWoC9J4YHDP4"

async def test_websocket_streaming_fix():
    """测试WebSocket流式响应修复效果"""
    
    uri = "ws://43.167.252.120:8001/ws/realtime"
    
    print("🔧 WebSocket流式响应修复验证测试")
    print("=" * 60)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功")
            
            # 步骤1: 认证
            print("\n📋 步骤1: 发送认证信息")
            await websocket.send(JWT_TOKEN)
            
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)
            print(f"  📥 认证响应: {auth_data}")
            
            if auth_data.get("status") == "authenticated":
                print("  ✅ 认证成功")
                
                # 步骤2: 发送AI聊天请求
                print("\n📋 步骤2: 发送AI聊天请求")
                
                ai_message = {
                    "type": "ai_chat",
                    "content": "请简单回复'Hello World，我是Claude AI助手'",
                    "ai_mode": "trader",
                    "session_type": "general",
                    "request_id": "streaming_fix_test"
                }
                
                await websocket.send(json.dumps(ai_message))
                print("  📤 AI聊天请求已发送")
                print("  🤖 等待AI响应...")
                
                # 步骤3: 验证流式响应
                print("\n📋 步骤3: 验证流式响应处理")
                
                response_count = 0
                stream_chunks = []
                full_response = ""
                start_time = datetime.now()
                
                # 期望的消息类型
                expected_types = ['ai_stream_start', 'ai_stream_chunk', 'ai_stream_end']
                received_types = []
                
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30)
                        response_data = json.loads(response)
                        response_count += 1
                        
                        response_type = response_data.get("type")
                        elapsed = (datetime.now() - start_time).total_seconds()
                        
                        print(f"  📥 [{elapsed:.1f}s] 消息{response_count}: {response_type}")
                        
                        if response_type == "ai_stream_start":
                            print("     🌊 流式响应开始 - 前端应该处理此消息")
                            received_types.append('ai_stream_start')
                            
                        elif response_type == "ai_stream_chunk":
                            chunk = response_data.get("chunk", "")
                            stream_chunks.append(chunk)
                            full_response += chunk
                            print(f"     📦 数据块{len(stream_chunks)}: {chunk[:20]}{'...' if len(chunk) > 20 else ''}")
                            received_types.append('ai_stream_chunk')
                            
                        elif response_type == "ai_stream_end":
                            print("     🎯 流式响应完成")
                            print(f"     📊 统计信息:")
                            print(f"        - 总数据块数: {len(stream_chunks)}")
                            print(f"        - 完整响应长度: {len(full_response)} 字符")
                            print(f"        - Token使用: {response_data.get('tokens_used', 0)}")
                            print(f"        - 成本: ${response_data.get('cost_usd', 0.0):.6f}")
                            received_types.append('ai_stream_end')
                            break
                            
                        elif response_type in ["ai_stream_error", "ai_chat_error"]:
                            print(f"     ❌ AI错误: {response_data.get('error', 'Unknown error')}")
                            break
                            
                        elif response_type in ["ai_progress_update", "ai_complexity_analysis"]:
                            print(f"     ⏳ 进度消息: {response_data.get('message', '')}")
                            # 这些消息前端不应该显示给用户
                            
                        else:
                            print(f"     ❓ 未知消息类型: {response_data}")
                        
                        # 超时检查
                        if elapsed > 60:
                            print(f"     ⏰ 等待超时 (60秒)")
                            break
                            
                    except asyncio.TimeoutError:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        print(f"  ⏰ 等待响应超时 ({elapsed:.1f}秒)")
                        break
                    except json.JSONDecodeError as e:
                        print(f"  ❌ JSON解析错误: {e}")
                        break
                
                # 验证结果
                total_time = (datetime.now() - start_time).total_seconds()
                print(f"\n📊 修复验证结果:")
                print(f"   总响应时间: {total_time:.2f}秒")
                print(f"   接收消息数: {response_count}")
                print(f"   流式数据块数: {len(stream_chunks)}")
                print(f"   完整响应长度: {len(full_response)} 字符")
                
                # 验证消息类型完整性
                print(f"\n🔍 消息类型完整性验证:")
                for expected in expected_types:
                    if expected in received_types:
                        print(f"   ✅ {expected}: 已接收")
                    else:
                        print(f"   ❌ {expected}: 未接收")
                
                # 前端处理建议
                print(f"\n💡 前端处理建议:")
                print(f"   1. 接收到 ai_stream_start 后，清空显示区域")
                print(f"   2. 每个 ai_stream_chunk 都应该累积显示")
                print(f"   3. ai_stream_end 完成最终消息保存")
                print(f"   4. 忽略 ai_progress_update 等进度消息")
                
                if full_response and len(stream_chunks) > 0:
                    print("\n✅ WebSocket流式响应修复验证成功!")
                    print(f"   📝 AI完整回复: {full_response}")
                else:
                    print("\n❌ WebSocket流式响应修复验证失败")
            else:
                print(f"  ❌ 认证失败: {auth_data}")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket连接意外关闭: {e}")
    except Exception as e:
        print(f"❌ WebSocket测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket_streaming_fix())