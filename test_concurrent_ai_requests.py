#!/usr/bin/env python3
"""
测试多用户并发AI对话
验证单个Claude账号的并发处理能力
"""

import asyncio
import json
import time
import websockets
from datetime import datetime
import concurrent.futures

# 测试配置
WEBSOCKET_URL = "ws://localhost:8001/ws/realtime"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTcwODY4ODcsImV4cCI6MTc1NzY5MTY4NywiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.8qJjqk_YePONXyJL3jbXceddVE-eqZ79juF1rKQY8zg"

class ConcurrentTestResult:
    def __init__(self, user_id):
        self.user_id = user_id
        self.start_time = None
        self.end_time = None
        self.success = False
        self.error = None
        self.response_time = 0
        self.messages_received = 0
        
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

def generate_request_id(user_id):
    """生成请求ID"""
    return f"user_{user_id}_{int(time.time() * 1000)}"

async def single_user_ai_request(user_id: int, message: str) -> ConcurrentTestResult:
    """单个用户的AI请求测试"""
    result = ConcurrentTestResult(user_id)
    result.start_time = time.time()
    
    try:
        print(f"👤 用户{user_id}: 开始连接...")
        
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            # 1. 认证
            auth_message = {
                "type": "auth",
                "token": TEST_TOKEN
            }
            await websocket.send(json.dumps(auth_message))
            
            auth_response = await websocket.recv()
            auth_data = json.loads(auth_response)
            
            if auth_data.get("type") != "auth_success":
                result.error = f"认证失败: {auth_data}"
                return result
            
            print(f"👤 用户{user_id}: 认证成功，发送AI消息...")
            
            # 2. 发送AI消息
            request_id = generate_request_id(user_id)
            ai_message = {
                "type": "ai_chat",
                "request_id": request_id,
                "content": f"用户{user_id}的问题: {message}",
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            await websocket.send(json.dumps(ai_message))
            
            # 3. 等待完整响应
            timeout_count = 0
            max_timeout = 60  # 60秒超时
            
            while timeout_count < max_timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    response_data = json.loads(response)
                    
                    # 计数所有消息
                    result.messages_received += 1
                    
                    # 检查是否是目标用户的响应
                    if response_data.get('request_id') == request_id:
                        
                        # 检查是否完成
                        if response_data.get('type') in ['ai_stream_end', 'ai_chat_success']:
                            result.success = True
                            result.end_time = time.time()
                            result.response_time = result.duration()
                            print(f"✅ 用户{user_id}: 成功完成 ({result.response_time:.1f}s, {result.messages_received}条消息)")
                            return result
                        elif response_data.get('type') in ['ai_stream_error', 'ai_chat_error']:
                            result.error = response_data.get('error', '未知错误')
                            result.end_time = time.time()
                            print(f"❌ 用户{user_id}: AI错误 - {result.error}")
                            return result
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    
                    # 每10秒显示一次进度
                    if timeout_count % 10 == 0:
                        print(f"⏱️ 用户{user_id}: 等待中... ({timeout_count}s)")
                    continue
            
            # 超时
            result.error = "响应超时"
            result.end_time = time.time()
            print(f"⏰ 用户{user_id}: 超时 ({max_timeout}s)")
            
    except Exception as e:
        result.error = str(e)
        result.end_time = time.time()
        print(f"💥 用户{user_id}: 异常 - {e}")
    
    return result

async def test_concurrent_users(user_count: int = 5):
    """测试多用户并发请求"""
    print(f"🧪 开始{user_count}用户并发AI对话测试")
    print("=" * 60)
    
    # 准备测试消息
    test_messages = [
        "什么是量化交易？",
        "请解释RSI指标",
        "如何制定交易策略？", 
        "什么是支撑阻力位？",
        "请介绍MACD指标",
        "如何进行风险管理？",
        "什么是趋势分析？",
        "请解释K线图",
        "如何选择交易时机？",
        "什么是止损止盈？"
    ]
    
    start_time = time.time()
    
    # 创建并发任务
    tasks = []
    for i in range(user_count):
        message = test_messages[i % len(test_messages)]
        task = asyncio.create_task(single_user_ai_request(i + 1, message))
        tasks.append(task)
        
        # 稍微错开启动时间，避免完全同时连接
        await asyncio.sleep(0.1)
    
    print(f"🚀 {user_count}个用户已启动，等待完成...")
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_time = time.time() - start_time
    
    # 分析结果
    print("\\n" + "=" * 60)
    print("📊 测试结果分析:")
    
    success_count = 0
    error_count = 0
    total_response_time = 0
    total_messages = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ 用户{i+1}: 任务异常 - {result}")
            error_count += 1
            continue
            
        if result.success:
            success_count += 1
            total_response_time += result.response_time
            total_messages += result.messages_received
            print(f"✅ 用户{result.user_id}: 成功 ({result.response_time:.1f}s, {result.messages_received}消息)")
        else:
            error_count += 1
            print(f"❌ 用户{result.user_id}: 失败 - {result.error}")
    
    # 统计摘要
    print(f"\\n📈 统计摘要:")
    print(f"   总测试时间: {total_time:.1f}秒")
    print(f"   成功用户: {success_count}/{user_count} ({success_count/user_count*100:.1f}%)")
    print(f"   失败用户: {error_count}/{user_count}")
    
    if success_count > 0:
        avg_response_time = total_response_time / success_count
        avg_messages = total_messages / success_count
        print(f"   平均响应时间: {avg_response_time:.1f}秒")
        print(f"   平均收到消息数: {avg_messages:.1f}条")
        
        # 性能评估
        if success_count == user_count and avg_response_time < 30:
            print("\\n🎉 性能评估: 优秀 - 所有用户都成功，响应时间合理")
        elif success_count >= user_count * 0.8 and avg_response_time < 60:
            print("\\n✅ 性能评估: 良好 - 大部分用户成功，响应时间可接受")  
        elif success_count >= user_count * 0.5:
            print("\\n⚠️ 性能评估: 一般 - 部分用户失败，可能需要优化")
        else:
            print("\\n❌ 性能评估: 较差 - 大量用户失败，需要增加资源")
    
    return success_count == user_count

async def main():
    """主测试函数"""
    print("🧪 Claude账号并发能力测试")
    print("=" * 60)
    
    # 先测试5个用户
    print("\\n🔸 第一轮: 5用户并发测试")
    success_5 = await test_concurrent_users(5)
    
    await asyncio.sleep(5)  # 短暂等待
    
    # 如果5用户成功，测试10用户
    if success_5:
        print("\\n🔸 第二轮: 10用户并发测试")
        success_10 = await test_concurrent_users(10)
        
        if success_10:
            print("\\n🎯 结论: 单个Claude账号可以支持10用户并发 ✅")
        else:
            print("\\n🎯 结论: 单个Claude账号在10用户并发时有压力，建议增加账号 ⚠️")
    else:
        print("\\n🎯 结论: 单个Claude账号在5用户并发时就有问题，需要立即增加账号 ❌")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n⏹️ 测试被用户中断")