#!/usr/bin/env python3
"""
测试WebSocket连接
验证WebSocket端点是否正常工作
"""

import asyncio
import json
import websockets
import sys

# 添加项目路径
sys.path.insert(0, '/root/trademe/backend/trading-service')

from generate_jwt_token import generate_jwt_token


async def test_websocket_connection():
    """测试WebSocket连接"""
    
    # 生成测试JWT token（使用admin用户）
    token = generate_jwt_token(user_id=6, email="admin@trademe.com")
    if not token:
        print("❌ 无法生成测试token")
        return False
    print(f"✅ 生成测试token: {token[:50]}...")
    
    # WebSocket URL
    ws_url = "ws://localhost:8001/ws/realtime"
    print(f"🔗 连接到: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket连接建立")
            
            # 发送认证消息
            auth_message = {
                "type": "auth",
                "token": token
            }
            await websocket.send(json.dumps(auth_message))
            print("📤 发送认证消息")
            
            # 接收认证响应
            response = await websocket.recv()
            auth_response = json.loads(response)
            print(f"📥 收到响应: {auth_response}")
            
            if auth_response.get("type") == "auth_success":
                print(f"✅ 认证成功! User ID: {auth_response.get('user_id')}")
                
                # 发送测试消息
                test_message = {
                    "type": "message",
                    "content": "Hello WebSocket!"
                }
                await websocket.send(json.dumps(test_message))
                print("📤 发送测试消息")
                
                # 接收响应
                response = await websocket.recv()
                test_response = json.loads(response)
                print(f"📥 收到响应: {test_response}")
                
                # 正常关闭连接
                await websocket.close()
                print("✅ WebSocket连接正常关闭")
                return True
                
            else:
                print(f"❌ 认证失败: {auth_response}")
                return False
                
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("🧪 WebSocket连接测试")
    print("=" * 60)
    
    success = await test_websocket_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ WebSocket测试通过!")
        print("\n前端WebSocket连接修复说明:")
        print("1. WebSocket端点已修正为: /ws/realtime")
        print("2. 认证消息类型已修正为: auth")
        print("3. 前端已重新构建，WebSocket连接应该正常工作")
    else:
        print("❌ WebSocket测试失败，请检查后端服务")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())