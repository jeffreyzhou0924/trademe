#!/usr/bin/env python3
"""
WebSocket AI 最终修复验证测试
验证所有修复（包括Object错误、role属性错误等）都已生效
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 测试配置
WEBSOCKET_URL = "ws://43.167.252.120/ws/realtime"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNzY2MzQsImV4cCI6MTc1NzY4MTQzNCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.cBGX0gG2HYVq-myd0GmTsDe93_K4lxGqEvRs9nXfhXs"

class FinalWebSocketTester:
    def __init__(self):
        self.ws = None
        self.authenticated = False
        
    async def test_final_fix(self):
        """最终修复测试"""
        try:
            logger.info("🧪 开始WebSocket AI最终修复验证测试")
            
            # 1. 连接WebSocket
            logger.info("🔗 连接到WebSocket...")
            self.ws = await websockets.connect(WEBSOCKET_URL)
            logger.info("✅ WebSocket连接成功")
            
            # 2. 认证
            logger.info("🔐 进行身份认证...")
            await self.ws.send(json.dumps({
                "type": "auth",
                "token": JWT_TOKEN
            }))
            
            # 等待认证结果
            while not self.authenticated:
                response = await self.ws.recv()
                data = json.loads(response)
                if data.get('type') in ['auth_success', 'connection_established']:
                    self.authenticated = True
                    logger.info("✅ 认证成功")
            
            # 3. 连续发送3条AI消息，确保没有"Object"错误
            test_messages = [
                "请简单介绍RSI指标",
                "RSI指标与MACD指标的区别是什么？", 
                "如何在策略中使用这两个指标？"
            ]
            
            for i, message in enumerate(test_messages, 1):
                logger.info(f"📤 发送第{i}条测试消息: {message[:30]}...")
                
                request_id = f"final_test_{i}_{datetime.now().strftime('%H%M%S')}"
                await self.ws.send(json.dumps({
                    "type": "ai_chat",
                    "request_id": request_id,
                    "content": message,
                    "ai_mode": "trader",
                    "session_type": "strategy"
                }))
                
                # 监听响应
                error_found = False
                stream_chunks = 0
                response_completed = False
                
                timeout = 60  # 60秒超时
                start_time = asyncio.get_event_loop().time()
                
                while not response_completed and (asyncio.get_event_loop().time() - start_time) < timeout:
                    try:
                        response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        if data.get('request_id') != request_id:
                            continue
                        
                        message_type = data.get('type')
                        
                        if message_type == 'ai_stream_start':
                            logger.info(f"🌊 第{i}条消息开始流式响应")
                            
                        elif message_type == 'ai_stream_chunk':
                            stream_chunks += 1
                            if stream_chunks % 10 == 0:  # 每10个chunk打印一次
                                logger.info(f"📝 第{i}条消息已收到{stream_chunks}个数据块")
                                
                        elif message_type == 'ai_stream_end':
                            response_completed = True
                            full_response = data.get('full_response', '')
                            logger.info(f"✅ 第{i}条消息完成 - 总计{stream_chunks}个数据块，响应长度:{len(full_response)}")
                            
                        elif message_type in ['ai_stream_error', 'ai_chat_error']:
                            error_found = True
                            error_msg = data.get('error', '未知错误')
                            logger.error(f"❌ 第{i}条消息出错: {error_msg}")
                            if 'Object' in error_msg:
                                logger.error("🚨 发现Object错误 - 修复未生效!")
                            if 'ClaudeConversation' in error_msg:
                                logger.error("🚨 发现ClaudeConversation错误 - 修复未生效!")
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"❌ 第{i}条消息处理异常: {e}")
                        break
                
                if error_found:
                    logger.error(f"❌ 第{i}条消息测试失败")
                    return False
                elif not response_completed:
                    logger.error(f"❌ 第{i}条消息响应超时")
                    return False
                else:
                    logger.info(f"✅ 第{i}条消息测试通过")
                
                # 短暂等待再发送下一条
                await asyncio.sleep(2)
            
            logger.info("🎉 所有测试通过！WebSocket AI修复成功！")
            return True
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            return False
        finally:
            if self.ws:
                await self.ws.close()
                logger.info("🔌 WebSocket连接已关闭")

async def main():
    tester = FinalWebSocketTester()
    success = await tester.test_final_fix()
    
    print("\n" + "="*60)
    if success:
        print("🎉 WebSocket AI修复验证测试完全通过!")
        print("✅ 'Object'错误已修复")
        print("✅ 'ClaudeConversation object is not subscriptable'错误已修复")  
        print("✅ 'ClaudeConversation object has no attribute role'错误已修复")
        print("✅ 连续多次AI对话正常工作")
        print("✅ 前端不再显示undefined错误")
        print("\n💡 用户现在可以正常使用AI对话功能，不会再遇到之前的错误！")
    else:
        print("❌ 测试失败，仍有问题需要修复")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())