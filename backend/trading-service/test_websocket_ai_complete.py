#!/usr/bin/env python3
"""
WebSocket AI 完整功能测试
测试流式AI对话是否完全正常工作
"""

import asyncio
import json
import websockets
import uuid
from datetime import datetime

# 配置
WS_URL = "ws://43.167.252.120:8001/api/v1/ai/ws/chat"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI5IiwiZW1haWwiOiJwdWJsaWN0ZXN0QGV4YW1wbGUuY29tIiwibWVtYmVyc2hpcExldmVsIjoicHJlbWl1bSIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc1MTE5OTUsImV4cCI6MTc1NzU5ODM5NSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.InQZhmMBEohYISWARCeeD5tPHWjOJ3dKuLhPxsLYRAM"

async def test_websocket_ai_stream():
    """测试WebSocket AI流式对话"""
    
    print("🚀 开始WebSocket AI流式对话测试...")
    print(f"🔗 连接地址: {WS_URL}")
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✅ WebSocket连接成功")
            
            # 步骤1: 发送认证消息
            auth_message = {
                "type": "authenticate",
                "token": JWT_TOKEN,
                "session_id": str(uuid.uuid4())
            }
            
            await websocket.send(json.dumps(auth_message))
            print("📤 发送认证消息")
            
            # 接收认证响应
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)
            print(f"📨 认证响应: {auth_data}")
            
            # 检查是否是认证成功或连接建立消息
            if auth_data.get("type") == "auth_success":
                print("✅ 认证成功 (auth_success)")
                user_id = auth_data.get("user_id")
                connection_id = auth_data.get("connection_id")
            elif auth_data.get("type") == "connection_established":
                print("✅ 连接已建立，等待认证结果...")
                # 等待真正的认证结果
                try:
                    actual_auth_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    actual_auth_data = json.loads(actual_auth_response)
                    print(f"📨 实际认证响应: {actual_auth_data}")
                    
                    if actual_auth_data.get("type") == "auth_success":
                        print("✅ 认证成功")
                        user_id = actual_auth_data.get("user_id") 
                        connection_id = actual_auth_data.get("connection_id")
                    else:
                        print("❌ 认证失败")
                        return
                except asyncio.TimeoutError:
                    # 如果没有收到进一步的认证消息，使用连接建立的信息
                    print("✅ 使用连接建立信息继续 (可能是直接认证模式)")
                    user_id = auth_data.get("user_id")
                    connection_id = auth_data.get("connection_id")
            else:
                print("❌ 认证失败")
                return
                
            print(f"👤 用户ID: {user_id}")
            print(f"🔌 连接ID: {connection_id}")
            
            # 步骤2: 发送AI对话请求
            request_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            
            ai_message = {
                "type": "ai_chat",
                "content": "请简单介绍一下MACD指标的基本原理",
                "ai_mode": "trader",
                "session_type": "strategy", 
                "session_id": session_id,
                "request_id": request_id
            }
            
            print(f"\n📤 发送AI对话请求:")
            print(f"   💬 内容: {ai_message['content']}")
            print(f"   🔍 请求ID: {request_id}")
            print(f"   📝 会话ID: {session_id}")
            
            await websocket.send(json.dumps(ai_message))
            
            # 步骤3: 接收流式响应
            print(f"\n🌊 开始接收AI流式响应...")
            start_time = datetime.now()
            
            total_chunks = 0
            total_content = ""
            stream_started = False
            stream_ended = False
            
            try:
                while True:
                    # 设置接收超时为60秒
                    response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    data = json.loads(response)
                    
                    message_type = data.get("type")
                    print(f"📦 [{datetime.now().strftime('%H:%M:%S')}] 收到消息: {message_type}")
                    
                    if message_type == "ai_stream_start":
                        stream_started = True
                        model = data.get("model", "unknown")
                        input_tokens = data.get("input_tokens", 0)
                        print(f"   ✨ 流式开始 - 模型: {model}, 输入tokens: {input_tokens}")
                        
                    elif message_type == "ai_stream_chunk":
                        total_chunks += 1
                        chunk_text = data.get("chunk", "")
                        total_content += chunk_text
                        content_length = len(data.get("content_so_far", ""))
                        print(f"   📝 数据块 #{total_chunks} - 长度: {len(chunk_text)}, 总长度: {content_length}")
                        
                    elif message_type == "ai_stream_end":
                        stream_ended = True
                        final_content = data.get("content", "")
                        tokens_used = data.get("tokens_used", 0)
                        cost_usd = data.get("cost_usd", 0.0)
                        model = data.get("model", "unknown")
                        
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        print(f"\n✅ 流式响应完成!")
                        print(f"   ⏱️  总耗时: {elapsed_time:.2f}秒")
                        print(f"   📊 数据块数量: {total_chunks}")
                        print(f"   🔤 内容长度: {len(final_content)}字符")
                        print(f"   🧠 模型: {model}")
                        print(f"   📈 Token使用: {tokens_used}")
                        print(f"   💰 成本: ${cost_usd:.6f}")
                        print(f"\n📄 AI响应内容预览 (前500字符):")
                        print("-" * 60)
                        print(final_content[:500] + ("..." if len(final_content) > 500 else ""))
                        print("-" * 60)
                        break
                        
                    elif message_type == "ai_stream_error":
                        error_msg = data.get("error", "未知错误")
                        print(f"❌ 流式错误: {error_msg}")
                        break
                        
                    elif message_type in ["ai_chat_start", "ai_complexity_analysis", "ai_progress_update"]:
                        # 处理进度消息
                        message = data.get("message", "")
                        print(f"   ℹ️  {message}")
                        
                    else:
                        print(f"   ⚠️  未知消息类型: {message_type}")
                        print(f"      数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    
            except asyncio.TimeoutError:
                elapsed_time = (datetime.now() - start_time).total_seconds()
                print(f"⏰ WebSocket响应超时 (等待{elapsed_time:.2f}秒)")
                
                # 分析当前状态
                print(f"📊 当前状态分析:")
                print(f"   🌊 流式是否开始: {stream_started}")
                print(f"   🏁 流式是否结束: {stream_ended}")
                print(f"   📦 接收数据块数: {total_chunks}")
                print(f"   📝 累积内容长度: {len(total_content)}")
                
                if not stream_started:
                    print("❌ 问题: 流式响应未开始，可能是AI服务初始化问题")
                elif not stream_ended:
                    print("⚠️  问题: 流式响应开始但未完成，可能是中途中断")
                else:
                    print("✅ 流式响应正常完成")
                
            print(f"\n🎯 WebSocket AI流式对话测试完成")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket连接意外关闭: {e}")
    except Exception as e:
        print(f"❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("=" * 80)
    print("🧪 WebSocket AI 流式对话完整测试")
    print("=" * 80)
    
    await test_websocket_ai_stream()
    
    print("\n" + "=" * 80)
    print("📋 测试总结:")
    print("✅ 如果看到 '流式响应完成'，说明WebSocket AI系统完全正常")
    print("❌ 如果出现错误或超时，说明还有问题需要修复")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())