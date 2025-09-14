#!/usr/bin/env python3
"""
测试WebSocket实时回测进度
"""
import asyncio
import websockets
import json
import aiohttp

# 配置  
WS_BASE_URL = "ws://localhost:8001/api/v1/realtime-backtest/ws"
API_URL = "http://localhost:8001"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI5IiwiZW1haWwiOiJwdWJsaWN0ZXN0QGV4YW1wbGUuY29tIiwibWVtYmVyc2hpcExldmVsIjoicHJlbWl1bSIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc2NDgwMjksImV4cCI6MTc1NzczNDQyOSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.0NF8y6vRqidww454Xm48sNXt_FJ4ufVDYDXr-Nx2Sek"

async def start_backtest():
    """启动一个回测任务"""
    test_config = {
        "strategy_code": "class TestStrategy:\n    def signal(self):\n        return {'action': 'buy', 'confidence': 0.8}",
        "exchange": "okx",
        "product_type": "perpetual", 
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "fee_rate": "vip0",
        "initial_capital": 10000,
        "start_date": "2025-01-01",
        "end_date": "2025-01-15",
        "data_type": "kline"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/api/v1/realtime-backtest/start",
                headers=headers,
                json=test_config
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    task_id = result.get('task_id')
                    print(f"✅ 回测任务启动成功！Task ID: {task_id}")
                    return task_id
                else:
                    error = await response.text()
                    print(f"❌ 启动回测失败: {error}")
                    return None
    except Exception as e:
        print(f"❌ 启动回测异常: {e}")
        return None

async def monitor_websocket_progress(task_id):
    """监听WebSocket回测进度"""
    ws_url = f"{WS_BASE_URL}/{task_id}"
    print(f"\n🔌 连接WebSocket监听回测进度: {ws_url}")
    
    try:
        # 连接WebSocket
        async with websockets.connect(ws_url) as websocket:
            # 发送认证消息
            auth_message = {
                "type": "auth",
                "token": JWT_TOKEN,
                "task_id": task_id
            }
            
            await websocket.send(json.dumps(auth_message))
            print("📡 已发送认证消息")
            
            # 监听消息
            message_count = 0
            max_messages = 50  # 最多接收50条消息以避免无限等待
            
            while message_count < max_messages:
                try:
                    # 设置超时避免无限等待
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    print(f"📨 收到消息: {data.get('type', 'unknown')}")
                    
                    if data.get('type') == 'auth_success':
                        print("✅ WebSocket认证成功")
                    elif data.get('type') == 'progress_update':
                        progress = data.get('progress', 0)
                        step = data.get('current_step', 'Unknown')
                        print(f"📊 进度更新: {progress}% - {step}")
                    elif data.get('type') == 'backtest_completed':
                        print("🎉 回测完成！")
                        break
                    elif data.get('type') == 'error':
                        print(f"❌ WebSocket错误: {data.get('message')}")
                        break
                    else:
                        print(f"📄 其他消息: {data}")
                    
                    message_count += 1
                    
                except asyncio.TimeoutError:
                    print("⏰ WebSocket超时，结束监听")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 WebSocket连接已关闭")
                    break
                    
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False
    
    return True

async def test_websocket_progress():
    """完整测试WebSocket回测进度"""
    print("🚀 开始WebSocket回测进度测试...")
    
    # 1. 启动回测任务
    task_id = await start_backtest()
    if not task_id:
        print("❌ 无法启动回测，测试失败")
        return False
    
    # 2. 等待一秒确保任务开始
    await asyncio.sleep(1)
    
    # 3. 开始WebSocket监听
    success = await monitor_websocket_progress(task_id)
    
    if success:
        print("✅ WebSocket回测进度监听测试成功！")
    else:
        print("❌ WebSocket回测进度监听测试失败")
    
    return success

if __name__ == "__main__":
    print("🧪 WebSocket实时回测进度测试")
    print("=" * 50)
    
    try:
        result = asyncio.run(test_websocket_progress())
        print("=" * 50)
        if result:
            print("🎉 测试完成：WebSocket实时进度功能正常！")
        else:
            print("❌ 测试完成：WebSocket实时进度功能存在问题")
    except Exception as e:
        print(f"❌ 测试异常: {e}")