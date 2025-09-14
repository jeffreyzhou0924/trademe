#!/usr/bin/env python3
"""
完整WebSocket认证测试
测试真实的JWT token认证流程
"""

import asyncio
import json
import websockets
import logging
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试配置
WEBSOCKET_URL = "ws://localhost:8001/api/v1/realtime-backtest/ws/test-task-12345"
LOGIN_URL = "http://localhost:3001/api/v1/auth/login"
LOGIN_CREDENTIALS = {
    "email": "admin@trademe.com",
    "password": "admin123456"
}

async def get_valid_jwt_token():
    """获取有效的JWT token"""
    try:
        response = requests.post(LOGIN_URL, json=LOGIN_CREDENTIALS)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("access_token"):
                return data["data"]["access_token"]
        return None
    except Exception as e:
        logger.error(f"获取JWT token失败: {e}")
        return None

async def test_websocket_with_valid_token():
    """使用有效token测试WebSocket连接"""
    logger.info("🔑 获取有效JWT token...")
    token = await get_valid_jwt_token()
    
    if not token:
        logger.error("❌ 无法获取有效JWT token")
        return False
    
    logger.info(f"✅ JWT token获取成功: {token[:50]}...")
    
    try:
        # 使用查询参数传递token
        url_with_token = f"{WEBSOCKET_URL}?token={token}"
        logger.info("🔌 尝试建立WebSocket连接...")
        
        async with websockets.connect(url_with_token) as websocket:
            logger.info("✅ WebSocket连接已建立")
            
            # 等待认证响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(response)
                logger.info(f"📨 收到响应: {data}")
                
                if data.get("type") == "auth_success":
                    logger.info("🎉 WebSocket认证成功！")
                    logger.info(f"   用户ID: {data.get('user_id')}")
                    logger.info(f"   消息: {data.get('message')}")
                    
                    # 等待任务不存在的响应
                    try:
                        next_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        next_data = json.loads(next_response)
                        logger.info(f"📨 下一个响应: {next_data}")
                        
                        if next_data.get("error") and "不存在" in next_data.get("error", ""):
                            logger.info("✅ 任务不存在检查正常工作")
                    except asyncio.TimeoutError:
                        logger.info("⏱️ 等待任务状态响应超时（正常）")
                    
                    return True
                    
                elif data.get("error"):
                    logger.warning(f"⚠️ 认证失败: {data['error']}")
                    return False
                else:
                    logger.warning(f"⚠️ 未知响应格式: {data}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error("⏱️ 等待认证响应超时")
                return False
                
    except Exception as e:
        logger.error(f"❌ WebSocket连接异常: {e}")
        return False

async def test_websocket_with_message_auth():
    """测试通过消息进行认证"""
    logger.info("📨 测试通过消息进行WebSocket认证...")
    token = await get_valid_jwt_token()
    
    if not token:
        logger.error("❌ 无法获取有效JWT token")
        return False
    
    try:
        # 不带token的URL
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            logger.info("✅ WebSocket连接已建立（无token）")
            
            # 发送认证消息
            auth_message = {
                "type": "auth",
                "token": token
            }
            await websocket.send(json.dumps(auth_message))
            logger.info("📤 已发送认证消息")
            
            # 等待认证响应
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(response)
            logger.info(f"📨 认证响应: {data}")
            
            if data.get("type") == "auth_success":
                logger.info("🎉 消息认证成功！")
                return True
            else:
                logger.warning(f"⚠️ 消息认证失败: {data}")
                return False
                
    except Exception as e:
        logger.error(f"❌ 消息认证异常: {e}")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("🔧 完整WebSocket认证功能测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    success_count = 0
    total_tests = 2
    
    try:
        # 测试1: 查询参数认证
        logger.info("\n📋 测试1: 通过查询参数进行JWT认证")
        if asyncio.run(test_websocket_with_valid_token()):
            success_count += 1
            logger.info("✅ 查询参数认证测试通过")
        else:
            logger.error("❌ 查询参数认证测试失败")
        
        print("\n" + "-" * 50)
        
        # 测试2: 消息认证
        logger.info("📋 测试2: 通过消息进行JWT认证")
        if asyncio.run(test_websocket_with_message_auth()):
            success_count += 1
            logger.info("✅ 消息认证测试通过")
        else:
            logger.error("❌ 消息认证测试失败")
        
        print("\n" + "=" * 70)
        print(f"📊 测试结果: {success_count}/{total_tests} 通过")
        
        if success_count == total_tests:
            print("🎉 所有WebSocket认证测试通过！修复成功！")
            print("💡 WebSocket认证403错误已完全解决")
        else:
            print("⚠️ 部分测试失败，需要进一步调试")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ 测试运行异常: {e}")

if __name__ == "__main__":
    main()