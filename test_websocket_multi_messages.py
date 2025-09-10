#!/usr/bin/env python3
"""
测试WebSocket AI多条消息处理
验证第二条消息不会卡住的修复
"""

import asyncio
import json
import time
import websockets
from datetime import datetime

# 测试配置
WEBSOCKET_URL = "ws://localhost:8001/ws/realtime"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwODYxNjQsImV4cCI6MTc1NzE3MjU2NCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.zfgvJ3FVxnSCTwV-FwGA1d3daaUVAM3Cw59HbTH8TWc"

def generate_request_id():
    """生成请求ID"""
    return f"test_{int(time.time() * 1000)}"

async def test_multiple_messages():
    """测试多条消息处理"""
    print("🔗 开始测试WebSocket多条消息处理...")
    
    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            print("✅ WebSocket连接建立成功")
            
            # 1. 认证
            auth_message = {
                "type": "auth",
                "token": TEST_TOKEN
            }
            await websocket.send(json.dumps(auth_message))
            
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)
            print(f"🔐 认证响应: {auth_data}")
            
            if auth_data.get("type") != "auth_success":
                print("❌ 认证失败")
                return False
            
            print("✅ 认证成功")
            
            # 2. 发送第一条AI消息
            print("\n📤 发送第一条AI消息...")
            first_request_id = generate_request_id()
            first_message = {
                "type": "ai_chat",
                "request_id": first_request_id,
                "content": "第一条消息：简单说明一下什么是量化交易？",
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            await websocket.send(json.dumps(first_message))
            
            # 等待一些响应
            first_msg_responses = []
            timeout_count = 0
            while timeout_count < 10:  # 最多等10秒
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    first_msg_responses.append(response_data)
                    
                    print(f"📨 第一条消息响应: {response_data.get('type')} - {response_data.get('message', '')}")
                    
                    # 如果收到流式结束或成功，就停止等待
                    if response_data.get('type') in ['ai_stream_end', 'ai_chat_success']:
                        break
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    continue
                    
            # 3. 立即发送第二条AI消息（不等待第一条完全结束）
            print("\n📤 发送第二条AI消息...")
            second_request_id = generate_request_id()
            second_message = {
                "type": "ai_chat",
                "request_id": second_request_id,
                "content": "第二条消息：请简单说明什么是RSI指标？",
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            await websocket.send(json.dumps(second_message))
            
            # 等待第二条消息的响应
            second_msg_responses = []
            timeout_count = 0
            progress_stuck_count = 0
            last_progress_time = time.time()
            
            while timeout_count < 15:  # 最多等15秒
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    
                    # 检查是否是第二条消息的响应
                    if response_data.get('request_id') == second_request_id:
                        second_msg_responses.append(response_data)
                        
                        print(f"📨 第二条消息响应: {response_data.get('type')} - {response_data.get('message', '')}")
                        
                        # 检测progress_update卡住
                        if response_data.get('type') == 'ai_progress_update':
                            current_time = time.time()
                            if current_time - last_progress_time < 2:  # 2秒内多次progress update
                                progress_stuck_count += 1
                            else:
                                progress_stuck_count = 0
                            last_progress_time = current_time
                            
                            if progress_stuck_count > 5:
                                print("⚠️ 检测到可能的progress_update循环")
                        
                        # 如果收到流式结束或成功，测试通过
                        if response_data.get('type') in ['ai_stream_end', 'ai_chat_success']:
                            print("✅ 第二条消息处理成功！")
                            return True
                            
                    else:
                        # 这是第一条消息的响应，继续处理
                        if response_data.get('request_id') == first_request_id:
                            first_msg_responses.append(response_data)
                        else:
                            print(f"📨 其他响应: {response_data.get('type')}")
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    print(f"⏱️ 超时等待 ({timeout_count}/15)")
                    continue
            
            print("❌ 第二条消息处理可能卡住了")
            print(f"📊 第一条消息收到 {len(first_msg_responses)} 个响应")
            print(f"📊 第二条消息收到 {len(second_msg_responses)} 个响应")
            
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

async def main():
    """主测试函数"""
    print("🧪 WebSocket多条消息处理测试")
    print("=" * 60)
    
    success = await test_multiple_messages()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试通过！第二条消息处理正常")
        return True
    else:
        print("❌ 测试失败！第二条消息可能仍有问题")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        exit(1)