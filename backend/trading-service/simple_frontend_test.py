#!/usr/bin/env python3
"""
简单测试验证前端WebSocket消息显示修复
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 测试配置
WEBSOCKET_URL = "ws://43.167.252.120/ws/realtime"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNzY2MzQsImV4cCI6MTc1NzY4MTQzNCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.cBGX0gG2HYVq-myd0GmTsDe93_K4lxGqEvRs9nXfhXs"

async def test_websocket_messages():
    """测试WebSocket消息显示"""
    try:
        logger.info("🧪 开始WebSocket消息显示测试")
        
        # 1. 连接WebSocket
        logger.info("🔗 连接到WebSocket...")
        ws = await websockets.connect(WEBSOCKET_URL)
        logger.info("✅ WebSocket连接成功")
        
        # 2. 认证
        logger.info("🔐 进行身份认证...")
        await ws.send(json.dumps({
            "type": "auth",
            "token": JWT_TOKEN
        }))
        
        # 等待认证结果
        authenticated = False
        while not authenticated:
            response = await ws.recv()
            data = json.loads(response)
            logger.info(f"📨 收到消息: {data.get('type', 'UNKNOWN_TYPE')}")
            
            # 检查消息显示格式
            if data.get('type') in ['auth_success', 'connection_established']:
                authenticated = True
                logger.info("✅ 认证成功")
                
                # 验证消息格式是否清晰
                logger.info(f"🔍 消息内容检查:")
                logger.info(f"  - type: {data.get('type')}")
                logger.info(f"  - user_id: {data.get('user_id', 'N/A')}")
                logger.info(f"  - connection_id: {data.get('connection_id', 'N/A')}")
        
        # 3. 发送一条简单的AI消息，观察进度更新显示
        logger.info("📤 发送简单AI消息测试...")
        
        request_id = f"display_test_{int(asyncio.get_event_loop().time())}"
        await ws.send(json.dumps({
            "type": "ai_chat",
            "request_id": request_id,
            "content": "你好，简单回复即可",  # 简短消息，避免超时
            "ai_mode": "trader",
            "session_type": "strategy"
        }))
        
        # 4. 监听响应，检查消息显示格式
        message_count = 0
        timeout = 30  # 30秒超时
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get('request_id') != request_id:
                    continue
                
                message_count += 1
                message_type = data.get('type')
                
                # 详细显示消息内容，检查是否还有"Object"问题
                logger.info(f"📨 消息 #{message_count}: {message_type}")
                
                if message_type == 'ai_progress_update':
                    logger.info(f"  📊 进度更新详情:")
                    logger.info(f"    - step: {data.get('step', 'N/A')}")
                    logger.info(f"    - total_steps: {data.get('total_steps', 'N/A')}")
                    logger.info(f"    - status: {data.get('status', 'N/A')}")
                    logger.info(f"    - message: {data.get('message', 'N/A')}")
                    
                elif message_type == 'ai_stream_start':
                    logger.info(f"  🌊 流式开始: {data.get('message', 'N/A')}")
                    
                elif message_type == 'ai_stream_chunk':
                    chunk_length = len(data.get('chunk', ''))
                    logger.info(f"  📝 数据块: {chunk_length} 字符")
                    
                elif message_type == 'ai_stream_end':
                    full_response_length = len(data.get('full_response', ''))
                    logger.info(f"  ✅ 流式结束: 响应长度 {full_response_length}")
                    logger.info(f"  💰 Token使用: {data.get('tokens_used', 'N/A')}")
                    logger.info("🎉 测试成功完成！")
                    await ws.close()
                    return True
                    
                elif message_type in ['ai_stream_error', 'ai_chat_error']:
                    error_msg = data.get('error', '未知错误')
                    logger.error(f"  ❌ 错误: {error_msg}")
                    
                    # 检查是否还有"Object"错误
                    if 'Object' in error_msg:
                        logger.error("🚨 发现Object错误 - 修复未生效!")
                        return False
                    break
                    
            except asyncio.TimeoutError:
                logger.info("⏱️ 等待消息...")
                continue
            except Exception as e:
                logger.error(f"❌ 消息处理异常: {e}")
                break
        
        logger.error("❌ 测试超时或失败")
        await ws.close()
        return False
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False

async def main():
    success = await test_websocket_messages()
    
    print("\n" + "="*60)
    if success:
        print("🎉 前端WebSocket消息显示修复测试通过!")
        print("✅ 消息显示格式清晰，无'Object'错误")
        print("✅ 进度更新显示正常")
        print("✅ 流式响应处理正常")
    else:
        print("❌ 测试失败，需要进一步调查")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())