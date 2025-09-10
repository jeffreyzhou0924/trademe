#!/usr/bin/env python3
"""
增强版WebSocket AI调试测试脚本
用于调试"AI调用失败: 未知错误"问题
"""

import asyncio
import json
import websockets
import logging
import traceback
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# JWT Token (刚刚生成的7天有效期token)
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNTk3MjksImV4cCI6MTc1NzY2NDUyOSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.85COJYi2V57j4x93-1jkSX4Kd2VgvfODn9Q26BaGRxk"

# WebSocket连接URL
WEBSOCKET_URL = "ws://43.167.252.120:8001/ws/realtime"

class WebSocketAITester:
    def __init__(self):
        self.websocket = None
        self.connected = False
        
    async def connect(self):
        """连接WebSocket"""
        try:
            logger.info(f"🔗 连接WebSocket: {WEBSOCKET_URL}")
            headers = {
                "Authorization": f"Bearer {JWT_TOKEN}"
            }
            
            self.websocket = await websockets.connect(
                WEBSOCKET_URL,
                additional_headers=headers,
                ping_interval=60,
                ping_timeout=30
            )
            self.connected = True
            logger.info("✅ WebSocket连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def listen_messages(self):
        """监听WebSocket消息"""
        logger.info("👂 开始监听WebSocket消息...")
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type', 'unknown')
                    
                    if msg_type == 'authenticated':
                        logger.info(f"🔐 认证成功: {data}")
                    elif msg_type == 'ai_start':
                        logger.info(f"🚀 AI开始: {data}")
                    elif msg_type == 'ai_progress_update':
                        logger.info(f"⏳ 进度更新: 步骤 {data.get('step', '?')}/{data.get('total_steps', '?')} - {data.get('message', '')}")
                    elif msg_type == 'ai_stream_start':
                        logger.info(f"🌊 流式开始: Request ID = {data.get('request_id', 'unknown')}")
                    elif msg_type == 'ai_stream_chunk':
                        chunk = data.get('chunk', '')
                        logger.info(f"📦 数据块: '{chunk}' (长度: {len(chunk)})")
                    elif msg_type == 'ai_stream_end':
                        logger.info(f"✅ 流式结束: 完整响应长度 = {len(data.get('full_response', ''))}")
                        logger.info(f"   💰 Token使用: {data.get('tokens_used', 0)}")
                        logger.info(f"   💵 成本: ${data.get('cost_usd', 0.0)}")
                    elif msg_type == 'ai_stream_error':
                        logger.error(f"❌ 流式错误: {data}")
                        logger.error(f"   🔍 错误类型: {data.get('error_type', 'unknown')}")
                        logger.error(f"   📝 错误信息: {data.get('error', 'no message')}")
                    elif msg_type == 'heartbeat':
                        pass  # 忽略心跳消息
                    else:
                        logger.info(f"📨 收到消息: {data}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON解析错误: {e}")
                    logger.error(f"   原始消息: {message}")
                except Exception as e:
                    logger.error(f"❌ 消息处理异常: {e}")
                    logger.error(traceback.format_exc())
                    
        except websockets.exceptions.ConnectionClosedError:
            logger.info("📤 WebSocket连接关闭")
        except Exception as e:
            logger.error(f"❌ 监听消息异常: {e}")
            logger.error(traceback.format_exc())

    async def send_ai_chat(self, content: str, session_id: str = None):
        """发送AI聊天消息"""
        if not self.connected or not self.websocket:
            logger.error("❌ WebSocket未连接")
            return False
            
        try:
            # 生成请求ID
            request_id = f"debug_test_{int(datetime.now().timestamp() * 1000)}"
            
            message = {
                "type": "ai_chat",
                "request_id": request_id,
                "content": content,
                "ai_mode": "trader",
                "session_type": "general",
                "session_id": session_id or request_id
            }
            
            logger.info(f"📤 发送AI聊天消息:")
            logger.info(f"   📝 内容: {content}")
            logger.info(f"   🆔 请求ID: {request_id}")
            logger.info(f"   🗂️ 会话ID: {message['session_id']}")
            
            await self.websocket.send(json.dumps(message))
            logger.info("✅ AI聊天消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 发送AI聊天消息失败: {e}")
            logger.error(traceback.format_exc())
            return False

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 WebSocket连接已关闭")

async def main():
    """主测试函数"""
    tester = WebSocketAITester()
    
    try:
        # 1. 连接WebSocket
        connected = await tester.connect()
        if not connected:
            logger.error("❌ 无法连接WebSocket，退出测试")
            return
        
        # 2. 启动消息监听任务
        listen_task = asyncio.create_task(tester.listen_messages())
        
        # 3. 发送认证消息
        logger.info("🔐 发送认证消息")
        auth_message = {
            "type": "authenticate",
            "token": JWT_TOKEN
        }
        await tester.websocket.send(json.dumps(auth_message))
        await asyncio.sleep(3)  # 等待认证完成
        
        # 4. 发送简单测试消息
        logger.info("🧪 测试1: 发送简单问题")
        await tester.send_ai_chat("什么是RSI指标？")
        
        # 等待响应
        await asyncio.sleep(30)  # 等待30秒看响应
        
        # 5. 创建新会话并发送第二条消息（复现用户报告的问题）
        logger.info("🧪 测试2: 新会话中发送第二条消息")
        test_session_id = f"debug_session_{int(datetime.now().timestamp() * 1000)}"
        
        await tester.send_ai_chat("hello", test_session_id)
        await asyncio.sleep(15)  # 等待15秒
        
        await tester.send_ai_chat("什么是MACD指标？", test_session_id)
        await asyncio.sleep(120)  # 等待2分钟看结果
        
        # 6. 取消监听任务并关闭连接
        listen_task.cancel()
        
    except KeyboardInterrupt:
        logger.info("⌨️ 用户中断测试")
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        logger.error(traceback.format_exc())
    finally:
        await tester.disconnect()

if __name__ == "__main__":
    logger.info("🚀 开始WebSocket AI增强调试测试")
    logger.info(f"🕐 测试时间: {datetime.now()}")
    asyncio.run(main())