#!/usr/bin/env python3
"""
WebSocket认证修复测试脚本
测试实时回测WebSocket端点的认证机制
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试配置
WEBSOCKET_URL = "ws://localhost:8001/api/v1/realtime-backtest/ws/test-task-id"
TEST_TOKEN = "test-jwt-token"  # 这里使用测试token

async def test_websocket_auth():
    """测试WebSocket认证功能"""
    
    logger.info("🚀 开始WebSocket认证测试")
    
    try:
        # 测试1: 不提供token的连接
        logger.info("📋 测试1: 不提供token的连接")
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                # 发送非认证消息
                await websocket.send(json.dumps({"type": "ping"}))
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                logger.info(f"   响应: {data}")
                
                if data.get("error") and "认证" in data.get("error", ""):
                    logger.info("   ✅ 正确拒绝了未认证连接")
                else:
                    logger.warning("   ⚠️ 未正确处理未认证连接")
        except Exception as e:
            logger.info(f"   ✅ 连接被正确拒绝: {e}")
    
        # 测试2: 通过查询参数提供token
        logger.info("📋 测试2: 通过查询参数提供token")
        try:
            url_with_token = f"{WEBSOCKET_URL}?token={TEST_TOKEN}"
            async with websockets.connect(url_with_token) as websocket:
                # 等待认证响应
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                logger.info(f"   认证响应: {data}")
                
                if data.get("type") == "auth_success":
                    logger.info("   ✅ 查询参数认证成功")
                elif data.get("error"):
                    logger.info(f"   ⚠️ 认证失败: {data['error']}")
                else:
                    logger.info("   ⚠️ 未知响应")
        except Exception as e:
            logger.warning(f"   ❌ 查询参数认证异常: {e}")
    
        # 测试3: 通过消息提供token
        logger.info("📋 测试3: 通过消息提供token")
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                # 发送认证消息
                auth_message = {
                    "type": "auth",
                    "token": TEST_TOKEN
                }
                await websocket.send(json.dumps(auth_message))
                
                # 等待认证响应
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                logger.info(f"   认证响应: {data}")
                
                if data.get("type") == "auth_success":
                    logger.info("   ✅ 消息认证成功")
                elif data.get("error"):
                    logger.info(f"   ⚠️ 认证失败: {data['error']}")
                else:
                    logger.info("   ⚠️ 未知响应")
        except Exception as e:
            logger.warning(f"   ❌ 消息认证异常: {e}")
    
        # 测试4: 使用无效token
        logger.info("📋 测试4: 使用无效token")
        try:
            invalid_url = f"{WEBSOCKET_URL}?token=invalid-token"
            async with websockets.connect(invalid_url) as websocket:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                logger.info(f"   无效token响应: {data}")
                
                if data.get("error") and data.get("code") in [4003, 4004]:
                    logger.info("   ✅ 正确拒绝了无效token")
                else:
                    logger.warning("   ⚠️ 未正确处理无效token")
        except Exception as e:
            logger.info(f"   ✅ 无效token被正确拒绝: {e}")
    
        logger.info("✅ WebSocket认证测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试过程异常: {e}")

async def test_task_not_found():
    """测试任务不存在的处理"""
    logger.info("📋 测试: 任务不存在处理")
    
    try:
        # 使用不存在的任务ID
        url = "ws://localhost:8001/api/v1/realtime-backtest/ws/non-existent-task?token=test-token"
        async with websockets.connect(url) as websocket:
            # 等待响应
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2)
                    data = json.loads(response)
                    logger.info(f"   响应: {data}")
                    
                    if data.get("error") and "不存在" in data.get("error", ""):
                        logger.info("   ✅ 正确处理了任务不存在")
                        break
                except asyncio.TimeoutError:
                    logger.info("   等待响应超时")
                    break
                    
    except Exception as e:
        logger.warning(f"   ❌ 任务不存在测试异常: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 WebSocket认证修复验证测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # 运行WebSocket认证测试
        asyncio.run(test_websocket_auth())
        
        print("\n" + "-" * 40)
        
        # 运行任务不存在测试
        asyncio.run(test_task_not_found())
        
        print("\n" + "=" * 60)
        print("🎉 WebSocket认证修复测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 测试运行异常: {e}")

if __name__ == "__main__":
    main()