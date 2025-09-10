#!/usr/bin/env python3
"""
WebSocket AI错误修复验证测试脚本
验证修复后的错误消息传递机制
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

# JWT Token (刚刚生成的新token)
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNjEwNzUsImV4cCI6MTc1NzY2NTg3NSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.9kgBXHQwh5bB1rBLs3QvFkFVnz2cxBXN3OItKv2ohwM"

# WebSocket连接URL
WEBSOCKET_URL = "ws://43.167.252.120:8001/ws/realtime"

class WebSocketErrorFixTester:
    def __init__(self):
        self.websocket = None
        self.connected = False
        self.error_messages_received = []
        
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
        """监听WebSocket消息，专注于错误消息"""
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
                    elif msg_type == 'ai_stream_start':
                        logger.info(f"🌊 流式开始: Request ID = {data.get('request_id', 'unknown')}")
                    elif msg_type == 'ai_stream_chunk':
                        chunk = data.get('chunk', '')
                        logger.info(f"📦 数据块: '{chunk}' (长度: {len(chunk)})")
                    elif msg_type == 'ai_stream_end':
                        logger.info(f"✅ 流式结束: 完整响应长度 = {len(data.get('full_response', ''))}")
                    elif msg_type == 'ai_stream_error':
                        error_msg = data.get('error', '未找到错误信息')
                        logger.error(f"❌ 流式错误捕获到: {data}")
                        logger.error(f"   🎯 具体错误信息: '{error_msg}'")
                        
                        # 验证错误修复：检查是否还是"未知错误"
                        if error_msg == "未知错误":
                            logger.error(f"⚠️  BUG未修复：仍然显示'未知错误'")
                            self.error_messages_received.append("未知错误 - 修复失败")
                        elif error_msg.startswith("AI调用失败: 未知错误"):
                            logger.error(f"⚠️  BUG部分修复：错误消息 = '{error_msg}'")
                            self.error_messages_received.append(f"部分修复 - {error_msg}")
                        else:
                            logger.info(f"✅ BUG修复成功：获得具体错误信息 = '{error_msg}'")
                            self.error_messages_received.append(f"修复成功 - {error_msg}")
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
            request_id = f"error_fix_test_{int(datetime.now().timestamp() * 1000)}"
            
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

    def print_error_fix_summary(self):
        """打印错误修复验证结果"""
        logger.info("\n" + "="*80)
        logger.info("🔍 WebSocket AI错误修复验证结果:")
        logger.info("="*80)
        
        if not self.error_messages_received:
            logger.warning("⚠️  未捕获到任何错误消息 - 测试可能不完整")
        else:
            for i, error_msg in enumerate(self.error_messages_received, 1):
                if "修复成功" in error_msg:
                    logger.info(f"✅ 错误 #{i}: {error_msg}")
                elif "部分修复" in error_msg:
                    logger.warning(f"🔄 错误 #{i}: {error_msg}")
                else:
                    logger.error(f"❌ 错误 #{i}: {error_msg}")
        
        logger.info("="*80)

async def main():
    """主测试函数 - 触发错误场景验证修复"""
    tester = WebSocketErrorFixTester()
    
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
        
        # 4. 发送测试消息以触发错误（根据之前的观察，继续对话会触发超时）
        logger.info("🧪 错误修复测试: 发送第一条消息")
        test_session_id = f"error_fix_test_session_{int(datetime.now().timestamp() * 1000)}"
        await tester.send_ai_chat("测试消息1", test_session_id)
        
        # 等待第一条消息处理
        await asyncio.sleep(15)
        
        # 5. 发送第二条消息以触发上下文长度超时错误
        logger.info("🧪 错误修复测试: 发送第二条消息（预期触发超时错误）")
        await tester.send_ai_chat("测试消息2，这应该触发上下文长度相关的超时错误", test_session_id)
        
        # 等待足够时间让错误发生和传播
        logger.info("⏳ 等待错误发生和传播...")
        await asyncio.sleep(180)  # 等待3分钟观察错误传播
        
        # 6. 打印错误修复验证结果
        tester.print_error_fix_summary()
        
        # 7. 取消监听任务
        listen_task.cancel()
        
    except KeyboardInterrupt:
        logger.info("⌨️ 用户中断测试")
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        logger.error(traceback.format_exc())
    finally:
        await tester.disconnect()

if __name__ == "__main__":
    logger.info("🚀 开始WebSocket AI错误修复验证测试")
    logger.info(f"🕐 测试时间: {datetime.now()}")
    logger.info("🎯 测试目标: 验证'未知错误'修复为具体错误信息")
    asyncio.run(main())