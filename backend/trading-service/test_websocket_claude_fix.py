#!/usr/bin/env python3
"""
测试WebSocket流式AI修复后的功能
验证claude_client未定义错误是否已经解决
"""

import asyncio
import json
import websockets
import uuid
from datetime import datetime

# 使用新生成的JWT Token
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc0ODQ0MTcsImV4cCI6MTc1ODA4OTIxNywiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.fS7BohX-0Xd7DEkmngQ7_tYnoYpNBWOhXFvChJQjzzM"

async def test_websocket_ai_after_fix():
    """测试修复后的WebSocket AI流式对话功能"""
    
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
                    "content": "请简单介绍一下RSI指标的用法",
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
            timeout_seconds = 45
            chunks_received = 0
            
            while True:
                try:
                    # 设置超时
                    response = await asyncio.wait_for(websocket.recv(), timeout=8.0)
                    data = json.loads(response)
                    
                    print(f"📥 收到响应: {data.get('type', 'unknown')}")
                    
                    if data.get("type") == "ai_stream_chunk":
                        # 流式数据块
                        content = data.get("content", "")
                        response_content += content
                        chunks_received += 1
                        print(f"💬 第{chunks_received}个AI回复片段: {content[:50]}...")
                        
                    elif data.get("type") == "ai_stream_complete":
                        # 流式完成
                        print("✅ AI流式响应完成！")
                        print(f"📊 总共收到 {chunks_received} 个数据块")
                        print(f"📄 完整回复长度: {len(response_content)} 字符")
                        print(f"📄 回复内容预览: {response_content[:200]}...")
                        return True, "正常完成"
                        
                    elif data.get("type") == "ai_stream_error":
                        # 流式错误
                        error_msg = data.get("error", "未知错误")
                        print(f"❌ AI流式错误: {error_msg}")
                        return False, f"AI流式错误: {error_msg}"
                        
                    elif data.get("type") == "error":
                        # 一般错误
                        error_msg = data.get("error", "未知错误")
                        print(f"❌ 服务器错误: {error_msg}")
                        return False, f"服务器错误: {error_msg}"
                        
                except asyncio.TimeoutError:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed > timeout_seconds:
                        print(f"⏰ 测试超时 ({timeout_seconds}秒)")
                        return False, "超时"
                    print("⏳ 等待响应中...")
                    continue
                    
                except Exception as e:
                    print(f"❌ 接收响应错误: {e}")
                    return False, f"接收响应错误: {e}"
                    
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False, f"WebSocket连接失败: {e}"

async def main():
    """主测试函数"""
    print("🚀 开始WebSocket流式AI修复验证测试")
    print("==" * 25)
    print("🔧 测试目标: 验证'claude_client未定义'错误是否已修复")
    print("🔧 预期结果: AI对话应该正常工作，不再报错")
    print("=" * 50)
    
    success, message = await test_websocket_ai_after_fix()
    
    print("=" * 50)
    if success:
        print("🎉 WebSocket流式AI功能修复成功！")
        print("✅ 不再出现'claude_client未定义'错误")
        print("✅ AI对话流式响应正常工作")
    else:
        print("⚠️  WebSocket流式AI功能仍有问题")
        print(f"❌ 错误信息: {message}")
        
        # 给出调试建议
        if "claude_client" in message.lower():
            print("🔍 建议: 检查ai_service.py中是否还有未修复的claude_client引用")
        elif "超时" in message:
            print("🔍 建议: 检查Claude账号配置和代理连接状态")
        elif "连接失败" in message:
            print("🔍 建议: 检查WebSocket服务器是否正在运行")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)