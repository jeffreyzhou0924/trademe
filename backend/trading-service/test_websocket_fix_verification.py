#!/usr/bin/env python3
"""
WebSocket AI流式响应修复验证测试
测试修复后的WebSocket是否能正常处理多次连续对话
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 测试配置
WEBSOCKET_URL = "ws://43.167.252.120/ws/realtime"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwNzY2MzQsImV4cCI6MTc1NzY4MTQzNCwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.cBGX0gG2HYVq-myd0GmTsDe93_K4lxGqEvRs9nXfhXs"

class WebSocketAITester:
    def __init__(self):
        self.websocket = None
        self.authenticated = False
        self.test_results = {
            'connection': False,
            'authentication': False,
            'first_conversation': False,
            'second_conversation': False,
            'error_handling': True  # 默认通过，除非发现错误
        }
        
    async def connect(self):
        """连接WebSocket"""
        try:
            logger.info(f"🔗 连接到WebSocket: {WEBSOCKET_URL}")
            # 使用简单的连接方式，不传递headers
            self.websocket = await websockets.connect(WEBSOCKET_URL)
            self.test_results['connection'] = True
            logger.info("✅ WebSocket连接成功")
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            return False
    
    async def authenticate(self):
        """认证"""
        try:
            auth_message = {
                "type": "auth",
                "token": JWT_TOKEN
            }
            await self.websocket.send(json.dumps(auth_message))
            logger.info("📤 发送认证消息")
            
            # 等待认证响应
            timeout = 10
            start_time = asyncio.get_event_loop().time()
            
            while not self.authenticated and (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    data = json.loads(response)
                    logger.info(f"📨 收到消息: {data.get('type', 'unknown')}")
                    
                    if data.get('type') in ['auth_success', 'connection_established']:
                        self.authenticated = True
                        self.test_results['authentication'] = True
                        logger.info("✅ 认证成功")
                        return True
                except asyncio.TimeoutError:
                    continue
            
            if not self.authenticated:
                logger.error("❌ 认证超时")
                return False
                
        except Exception as e:
            logger.error(f"❌ 认证失败: {e}")
            return False
    
    async def send_ai_message(self, content: str, conversation_num: int):
        """发送AI对话消息"""
        try:
            request_id = f"test_{conversation_num}_{datetime.now().strftime('%H%M%S')}"
            message = {
                "type": "ai_chat",
                "request_id": request_id,
                "content": content,
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            
            logger.info(f"📤 发送AI消息 #{conversation_num}: {content[:50]}...")
            await self.websocket.send(json.dumps(message))
            
            # 等待AI响应
            streaming_started = False
            chunks_received = 0
            response_completed = False
            error_occurred = False
            
            timeout = 60  # 60秒超时
            start_time = asyncio.get_event_loop().time()
            
            while not response_completed and (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    
                    message_type = data.get('type', 'unknown')
                    
                    # 检查是否是我们的请求响应
                    if data.get('request_id') != request_id:
                        continue
                    
                    logger.info(f"📨 #{conversation_num} 收到: {message_type}")
                    
                    if message_type == 'ai_stream_start':
                        streaming_started = True
                        logger.info(f"🌊 #{conversation_num} 流式开始")
                        
                    elif message_type == 'ai_stream_chunk':
                        chunks_received += 1
                        chunk_content = data.get('chunk', '')
                        logger.info(f"📝 #{conversation_num} 数据块 #{chunks_received}: {chunk_content[:30]}...")
                        
                    elif message_type == 'ai_stream_end':
                        response_completed = True
                        full_response = data.get('full_response', '')
                        logger.info(f"✅ #{conversation_num} 流式结束，总计 {chunks_received} 个数据块，响应长度: {len(full_response)}")
                        
                        # 标记测试通过
                        if conversation_num == 1:
                            self.test_results['first_conversation'] = True
                        elif conversation_num == 2:
                            self.test_results['second_conversation'] = True
                        
                    elif message_type in ['ai_stream_error', 'ai_chat_error']:
                        error_occurred = True
                        error_msg = data.get('error', 'Unknown error')
                        logger.error(f"❌ #{conversation_num} AI错误: {error_msg}")
                        self.test_results['error_handling'] = False
                        break
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ #{conversation_num} 等待响应超时，继续监听...")
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"❌ #{conversation_num} JSON解析错误: {e}")
                    self.test_results['error_handling'] = False
                    continue
                except Exception as e:
                    logger.error(f"❌ #{conversation_num} 处理消息错误: {e}")
                    self.test_results['error_handling'] = False
                    continue
            
            if not response_completed and not error_occurred:
                logger.error(f"❌ #{conversation_num} AI响应超时")
                return False
                
            return response_completed and not error_occurred
            
        except Exception as e:
            logger.error(f"❌ #{conversation_num} 发送AI消息失败: {e}")
            self.test_results['error_handling'] = False
            return False
    
    async def run_test(self):
        """运行完整测试"""
        logger.info("🚀 开始WebSocket AI修复验证测试")
        
        # 1. 连接测试
        if not await self.connect():
            return self.generate_report()
        
        # 2. 认证测试
        if not await self.authenticate():
            return self.generate_report()
        
        # 3. 第一次对话测试
        logger.info("🎯 测试第一次AI对话")
        first_success = await self.send_ai_message(
            "你好，请简单介绍一下RSI指标的基本原理。", 1
        )
        
        if first_success:
            logger.info("✅ 第一次对话测试通过")
        else:
            logger.error("❌ 第一次对话测试失败")
        
        # 4. 等待一下，然后第二次对话测试
        logger.info("⏳ 等待3秒后进行第二次对话测试...")
        await asyncio.sleep(3)
        
        logger.info("🎯 测试第二次AI对话（这是关键测试）")
        second_success = await self.send_ai_message(
            "请继续解释MACD指标与RSI指标的区别。", 2
        )
        
        if second_success:
            logger.info("✅ 第二次对话测试通过")
        else:
            logger.error("❌ 第二次对话测试失败")
        
        # 关闭连接
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 WebSocket连接已关闭")
        
        return self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        logger.info("📋 生成测试报告")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_results': self.test_results,
            'overall_status': all(self.test_results.values()),
            'summary': {}
        }
        
        # 计算通过的测试数量
        passed_tests = sum(1 for result in self.test_results.values() if result)
        total_tests = len(self.test_results)
        
        report['summary'] = {
            'passed': passed_tests,
            'total': total_tests,
            'success_rate': f"{(passed_tests/total_tests)*100:.1f}%"
        }
        
        # 打印报告
        print("\n" + "="*60)
        print("🧪 WebSocket AI流式响应修复验证测试报告")
        print("="*60)
        print(f"测试时间: {report['timestamp']}")
        print(f"总体状态: {'✅ 通过' if report['overall_status'] else '❌ 失败'}")
        print(f"成功率: {report['summary']['success_rate']} ({report['summary']['passed']}/{report['summary']['total']})")
        print("\n详细结果:")
        
        test_descriptions = {
            'connection': 'WebSocket连接',
            'authentication': 'JWT认证',
            'first_conversation': '第一次AI对话',
            'second_conversation': '第二次AI对话',
            'error_handling': '错误处理'
        }
        
        for test_name, result in self.test_results.items():
            status = "✅ 通过" if result else "❌ 失败"
            description = test_descriptions.get(test_name, test_name)
            print(f"  {description}: {status}")
        
        print("\n" + "="*60)
        
        if report['overall_status']:
            print("🎉 恭喜！WebSocket AI流式响应修复成功！")
            print("✅ 现在支持多次连续AI对话，不再出现'Object'错误")
        else:
            print("⚠️  发现问题，需要进一步调试")
            
            if not self.test_results['connection']:
                print("- WebSocket连接失败，请检查服务器状态")
            if not self.test_results['authentication']:
                print("- JWT认证失败，请检查token有效性")
            if not self.test_results['first_conversation']:
                print("- 第一次对话失败，基础AI功能有问题")
            if not self.test_results['second_conversation']:
                print("- 第二次对话失败，这是修复的关键问题")
            if not self.test_results['error_handling']:
                print("- 发现错误处理问题，可能仍有'Object'错误")
        
        print("="*60)
        
        return report

async def main():
    """主函数"""
    tester = WebSocketAITester()
    report = await tester.run_test()
    
    # 保存报告到文件
    report_file = f"websocket_fix_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 测试报告已保存到: {report_file}")

if __name__ == "__main__":
    asyncio.run(main())