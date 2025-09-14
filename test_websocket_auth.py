#!/usr/bin/env python3
"""
测试WebSocket AI认证流程
"""

import asyncio
import json
import websockets
import jwt
from datetime import datetime, timedelta

# JWT配置
JWT_SECRET = "trademe_super_secret_jwt_key_for_development_only_32_chars"  # 与后端一致
JWT_ALGORITHM = "HS256"

def create_jwt_token(user_id: int = 6):
    """创建测试用的JWT token"""
    payload = {
        "userId": user_id,  # 用户服务格式
        "user_id": user_id,
        "email": "test@example.com",
        "username": f"user_{user_id}",
        "membershipLevel": "professional",
        "type": "access",  # 必需的token类型
        "aud": "trademe-app",  # audience
        "iss": "trademe-user-service",  # issuer
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def test_websocket_auth():
    """测试WebSocket认证流程"""
    uri = "ws://localhost:8001/api/v1/ai/ws/chat"
    token = create_jwt_token(6)
    
    print(f"🔗 连接到 WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket 连接建立")
            
            # 发送认证消息
            auth_message = {
                "type": "auth",
                "token": token
            }
            print(f"📤 发送认证消息: {auth_message['type']}")
            await websocket.send(json.dumps(auth_message))
            
            # 等待认证响应
            print("⏳ 等待认证响应...")
            auth_timeout = asyncio.create_task(asyncio.sleep(5))
            receive_task = asyncio.create_task(websocket.recv())
            
            done, pending = await asyncio.wait(
                [auth_timeout, receive_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if receive_task in done:
                response = json.loads(receive_task.result())
                print(f"📨 收到响应: {json.dumps(response, indent=2)}")
                
                if response.get("type") == "auth_success":
                    print("✅ 认证成功！")
                    print(f"   - Connection ID: {response.get('connection_id')}")
                    print(f"   - User ID: {response.get('user_id')}")
                    
                    # 发送测试消息
                    test_message = {
                        "type": "ai_chat",
                        "request_id": "test_123",
                        "content": "你好，这是一个测试消息",
                        "ai_mode": "trader",
                        "session_type": "strategy"
                    }
                    print(f"\n📤 发送测试AI消息...")
                    await websocket.send(json.dumps(test_message))
                    
                    # 接收几个响应
                    for i in range(3):
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=5)
                            response_data = json.loads(response)
                            print(f"📨 响应 {i+1}: {response_data.get('type')} - {response_data.get('message', '')[:50]}")
                        except asyncio.TimeoutError:
                            print(f"⏱️ 响应 {i+1} 超时")
                            break
                    
                elif response.get("type") == "auth_error":
                    print(f"❌ 认证失败: {response.get('message')}")
                else:
                    print(f"❓ 未知响应类型: {response.get('type')}")
            else:
                print("❌ 认证超时，未收到响应")
                auth_timeout.cancel()
                
    except Exception as e:
        print(f"❌ 连接错误: {e}")

if __name__ == "__main__":
    print("🚀 开始测试 WebSocket AI 认证流程")
    asyncio.run(test_websocket_auth())
    print("\n✅ 测试完成")