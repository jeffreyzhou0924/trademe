#!/usr/bin/env python3
"""
WebSocket流式AI修复验证测试
测试WebSocket AI对话是否能正常工作，不再报错"Object"
"""

import asyncio
import json
import websockets
import uuid
from datetime import datetime

# 使用生成的JWT Token
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc0ODM3MTAsImV4cCI6MTc1ODA4ODUxMCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.aIXxonFx-GLwzSNeO9XFIlqf-E-_G864xKFRIZtJikA"

async def test_websocket_ai_chat():
    """测试WebSocket AI流式对话功能"""
    
    try:
        # 连接WebSocket (带认证)
        uri = f"ws://127.0.0.1:8001/ws/realtime?token={JWT_TOKEN}"
        
        print("🌊 正在连接WebSocket...")
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功！")
            
            # 发送AI对话请求
            request_id = str(uuid.uuid4())[:8]
            message = {
                "type": "ai_stream_chat",
                "request_id": request_id,
                "data": {
                    "content": "请简单介绍一下MACD指标",
                    "ai_mode": "trader",
                    "session_type": "discussion",
                    "session_id": str(uuid.uuid4())
                }
            }
            
            print(f"📤 发送AI对话请求: {message['data']['content']}")
            await websocket.send(json.dumps(message))
            
            # 接收流式响应
            response_content = ""
            start_time = datetime.now()
            timeout_seconds = 30
            
            while True:
                try:
                    # 设置超时
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    
                    print(f"📥 收到响应: {data.get('type', 'unknown')}")
                    
                    if data.get("type") == "ai_stream_chunk":
                        # 流式数据块
                        content = data.get("content", "")
                        response_content += content
                        print(f"💬 AI回复片段: {content}")
                        
                    elif data.get("type") == "ai_stream_complete":
                        # 流式完成
                        print("✅ AI流式响应完成！")
                        print(f"📄 完整回复内容: {response_content}")
                        return True
                        
                    elif data.get("type") == "ai_stream_error":
                        # 流式错误
                        error_msg = data.get("error", "未知错误")
                        print(f"❌ AI流式错误: {error_msg}")
                        return False
                        
                except asyncio.TimeoutError:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed > timeout_seconds:
                        print(f"⏰ 测试超时 ({timeout_seconds}秒)")
                        return False
                    print("⏳ 等待响应中...")
                    continue
                    
                except Exception as e:
                    print(f"❌ 接收响应错误: {e}")
                    return False
                    
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始WebSocket流式AI修复验证测试")
    print("=" * 50)
    
    success = await test_websocket_ai_chat()
    
    print("=" * 50)
    if success:
        print("🎉 WebSocket流式AI功能修复成功！")
        print("✅ 不再出现'流式AI错误: Object'问题")
    else:
        print("⚠️  WebSocket流式AI功能仍有问题")
        print("❌ 需要进一步调试")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)