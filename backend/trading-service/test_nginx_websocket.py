#!/usr/bin/env python3
"""
测试通过Nginx代理的WebSocket连接
验证前端可以正常连接
"""

import asyncio
import json
import websockets
import sys

# 添加项目路径
sys.path.insert(0, '/root/trademe/backend/trading-service')

from generate_jwt_token import generate_jwt_token


async def test_nginx_websocket():
    """测试通过Nginx代理的WebSocket连接"""
    
    # 生成测试JWT token（使用admin用户）
    token = generate_jwt_token(user_id=6, email="admin@trademe.com")
    if not token:
        print("❌ 无法生成测试token")
        return False
    print(f"✅ 生成测试token: {token[:50]}...")
    
    # 通过Nginx的WebSocket URL（模拟前端连接）
    ws_url = "ws://43.167.252.120/ws/realtime"
    print(f"🔗 连接到: {ws_url} (通过Nginx代理)")
    
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
                
                # 发送心跳消息
                ping_message = {
                    "type": "ping"
                }
                await websocket.send(json.dumps(ping_message))
                print("📤 发送心跳消息")
                
                # 接收响应
                response = await websocket.recv()
                ping_response = json.loads(response)
                print(f"📥 收到心跳响应: {ping_response}")
                
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
    print("🧪 Nginx WebSocket代理测试")
    print("=" * 60)
    
    success = await test_nginx_websocket()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ WebSocket通过Nginx代理测试成功!")
        print("\n说明:")
        print("1. Nginx WebSocket代理配置正确")
        print("2. 前端可以通过 ws://43.167.252.120/ws/realtime 连接")
        print("3. 认证流程正常工作")
        print("\n前端应该可以正常使用WebSocket连接了")
    else:
        print("❌ WebSocket测试失败")
        print("\n可能的问题:")
        print("1. Nginx配置未生效")
        print("2. 后端服务未运行")
        print("3. 防火墙阻止连接")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())