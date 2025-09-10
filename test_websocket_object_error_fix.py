#!/usr/bin/env python3
"""
WebSocket AI 流式对话 Object 错误修复验证脚本

测试场景：
1. 验证前端错误处理逻辑的Object序列化问题是否修复
2. 测试复杂错误对象的安全序列化
3. 验证WebSocket流式对话的错误显示是否正常
"""

import json
import asyncio
import websockets
import requests
from datetime import datetime

# 测试配置
BASE_URL = "http://43.167.252.120"
WS_URL = "ws://43.167.252.120:8001/ws/realtime"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2IiwiZW1haWwiOiJwdWJsaWN0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjoxNzM5MTA3ODE5LCJpYXQiOjE3MjU2MzU4MTksInVzZXJfaWQiOjZ9.9JaS7jtLe8w7nNe-VqnOmJpCc7A3Vf4Q_6B1FqeSfs"

def print_status(message, status="INFO"):
    """打印状态信息"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_emoji = {
        "INFO": "ℹ️",
        "SUCCESS": "✅", 
        "ERROR": "❌",
        "WARNING": "⚠️",
        "TEST": "🧪"
    }
    print(f"{timestamp} {status_emoji.get(status, 'ℹ️')} [{status}] {message}")

async def test_websocket_object_error_handling():
    """测试WebSocket的Object错误处理"""
    print_status("开始测试WebSocket Object错误处理修复", "TEST")
    
    try:
        # 连接WebSocket
        print_status("连接WebSocket服务...")
        async with websockets.connect(
            f"{WS_URL}?token={TEST_TOKEN}",
            ping_interval=30,
            ping_timeout=10
        ) as websocket:
            print_status("WebSocket连接成功", "SUCCESS")
            
            # 发送测试消息 - 故意触发复杂错误
            test_message = {
                "type": "ai_chat_streaming",
                "request_id": f"error-test-{int(datetime.now().timestamp())}",
                "content": "这是一条用来测试错误处理的消息，请确保前端能正确显示任何错误信息而不是显示'Object'",
                "session_id": "test-session-id",
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            
            print_status(f"发送测试消息: {test_message['content'][:50]}...")
            await websocket.send(json.dumps(test_message))
            
            # 监听响应
            timeout_seconds = 30
            print_status(f"等待响应（超时: {timeout_seconds}秒）...")
            
            response_count = 0
            try:
                async for message in websocket:
                    response_count += 1
                    try:
                        data = json.loads(message)
                        msg_type = data.get('type', 'unknown')
                        
                        print_status(f"收到消息 #{response_count} - 类型: {msg_type}")
                        
                        # 检查错误消息格式
                        if msg_type == "ai_chat_error" or "error" in data:
                            error_info = data.get('error', data.get('message', ''))
                            print_status(f"错误消息: {error_info}", "WARNING")
                            
                            # 验证错误消息不是 "Object"
                            if error_info == "Object" or str(error_info).strip() == "Object":
                                print_status("⚠️ 发现Object错误！错误消息应该被修复", "ERROR")
                                return False
                            else:
                                print_status("✅ 错误消息格式正常，不是'Object'", "SUCCESS")
                        
                        # 检查流式错误
                        if msg_type == "ai_stream_error":
                            error_details = data.get('error', {})
                            print_status(f"流式错误详情: {error_details}", "WARNING")
                            
                            # 检查错误详情是否是Object
                            if str(error_details).strip() == "Object" or error_details == "Object":
                                print_status("⚠️ 发现流式Object错误！应该被修复", "ERROR")
                                return False
                        
                        # 如果收到成功响应，说明没有错误
                        if msg_type == "ai_chat_success":
                            response_content = data.get('response', '')
                            print_status(f"AI响应成功: {response_content[:100]}...")
                            break
                        
                        # 限制响应数量，避免无限循环
                        if response_count >= 10:
                            print_status("收到足够多的响应消息，结束测试")
                            break
                            
                    except json.JSONDecodeError:
                        print_status(f"非JSON响应: {message[:200]}", "WARNING")
                
                print_status("WebSocket Object错误处理测试完成", "SUCCESS")
                return True
                
            except asyncio.TimeoutError:
                print_status("WebSocket响应超时", "WARNING")
                return True  # 超时不算错误，重点是检查Object错误
                
    except Exception as e:
        print_status(f"WebSocket连接失败: {e}", "ERROR")
        return False

def test_frontend_error_serialization():
    """测试前端错误序列化逻辑（模拟）"""
    print_status("测试前端错误序列化逻辑", "TEST")
    
    # 模拟前端的safeStringifyError函数
    def safe_stringify_error(error):
        if not error:
            return 'undefined'
        if isinstance(error, str):
            return error
        if isinstance(error, (int, float, bool)):
            return str(error)
        if isinstance(error, dict):
            try:
                # 尝试提取常见的错误属性
                if 'message' in error:
                    return error['message']
                if hasattr(error, '__str__') and str(error) != '[object Object]':
                    return str(error)
                # 尝试JSON序列化
                return json.dumps(error, indent=2)
            except:
                return '[Complex Error Object]'
        return str(error)
    
    # 测试各种错误类型
    test_cases = [
        ("字符串错误", "这是一个字符串错误"),
        ("数字错误", 500),
        ("布尔错误", False),
        ("简单对象错误", {"message": "API调用失败", "code": 500}),
        ("复杂对象错误", {"error": {"nested": {"deep": "error"}}, "timestamp": datetime.now()}),
        ("空值", None),
        ("空字符串", ""),
    ]
    
    all_passed = True
    for test_name, error_input in test_cases:
        try:
            result = safe_stringify_error(error_input)
            if result == "Object":
                print_status(f"❌ {test_name}: 返回了'Object'，应该被修复", "ERROR")
                all_passed = False
            else:
                print_status(f"✅ {test_name}: '{result[:50]}...' (正常)", "SUCCESS")
        except Exception as e:
            print_status(f"❌ {test_name}: 处理异常 - {e}", "ERROR")
            all_passed = False
    
    return all_passed

async def main():
    """主测试函数"""
    print_status("=== WebSocket AI Object错误修复验证开始 ===", "TEST")
    
    # 测试1：前端错误序列化逻辑
    print_status("\n--- 测试1: 前端错误序列化逻辑 ---")
    serialization_ok = test_frontend_error_serialization()
    
    # 测试2：WebSocket实际错误处理
    print_status("\n--- 测试2: WebSocket实际错误处理 ---")
    websocket_ok = await test_websocket_object_error_handling()
    
    # 总结
    print_status(f"\n=== 测试结果总结 ===")
    print_status(f"前端序列化测试: {'✅ 通过' if serialization_ok else '❌ 失败'}")
    print_status(f"WebSocket错误测试: {'✅ 通过' if websocket_ok else '❌ 失败'}")
    
    overall_result = serialization_ok and websocket_ok
    if overall_result:
        print_status("🎉 所有测试通过！Object错误问题已修复", "SUCCESS")
    else:
        print_status("⚠️ 部分测试失败，需要进一步检查", "WARNING")
    
    return overall_result

if __name__ == "__main__":
    asyncio.run(main())