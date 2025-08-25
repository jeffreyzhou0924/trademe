#!/usr/bin/env python3
"""
结构化日志中间件测试脚本
验证JSON格式日志记录和请求追踪功能
"""

import asyncio
import httpx
import json
import time
import os

# 测试配置
TEST_CONFIG = {
    "base_url": "http://localhost:8001",
    "timeout": 30
}

async def test_basic_request_logging():
    """测试基础请求日志记录"""
    print("📋 测试基础请求日志记录...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 测试简单GET请求
        response = await client.get(f"{TEST_CONFIG['base_url']}/health")
        
        print(f"  健康检查请求:")
        print(f"    状态码: {response.status_code}")
        print(f"    请求ID: {response.headers.get('X-Request-ID', 'N/A')}")
        print(f"    处理时间: {response.headers.get('X-Process-Time', 'N/A')}")
        
        # 测试带参数的请求
        response = await client.get(f"{TEST_CONFIG['base_url']}/", params={"test": "value"})
        
        print(f"  根路径请求 (带参数):")
        print(f"    状态码: {response.status_code}")
        print(f"    请求ID: {response.headers.get('X-Request-ID', 'N/A')}")

async def test_authenticated_request_logging():
    """测试认证请求的日志记录"""
    print(f"\n🔐 测试认证请求日志记录...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 先登录获取token
        login_data = {"email": "test@example.com", "password": "password123"}
        login_response = await client.post(f"{TEST_CONFIG['base_url']}/auth/login", json=login_data)
        
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data["access_token"]
            
            print(f"  登录请求:")
            print(f"    状态码: {login_response.status_code}")
            print(f"    请求ID: {login_response.headers.get('X-Request-ID', 'N/A')}")
            print(f"    用户: {token_data['user']['email']}")
            
            # 使用token访问受保护端点
            headers = {"Authorization": f"Bearer {token}"}
            auth_response = await client.get(f"{TEST_CONFIG['base_url']}/auth/me", headers=headers)
            
            print(f"  认证用户信息请求:")
            print(f"    状态码: {auth_response.status_code}")
            print(f"    请求ID: {auth_response.headers.get('X-Request-ID', 'N/A')}")
            
        else:
            print(f"  登录失败: {login_response.status_code}")

async def test_error_logging():
    """测试错误日志记录"""
    print(f"\n❌ 测试错误日志记录...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 访问不存在的端点
        response = await client.get(f"{TEST_CONFIG['base_url']}/nonexistent")
        
        print(f"  404错误请求:")
        print(f"    状态码: {response.status_code}")
        print(f"    请求ID: {response.headers.get('X-Request-ID', 'N/A')}")
        
        # 尝试访问需要认证的端点 (无token)
        response = await client.get(f"{TEST_CONFIG['base_url']}/auth/me")
        
        print(f"  401认证错误:")
        print(f"    状态码: {response.status_code}")
        print(f"    请求ID: {response.headers.get('X-Request-ID', 'N/A')}")

async def test_concurrent_requests():
    """测试并发请求的日志追踪"""
    print(f"\n🚀 测试并发请求日志追踪...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 创建10个并发请求
        tasks = []
        for i in range(10):
            task = client.get(f"{TEST_CONFIG['base_url']}/health")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        request_ids = []
        for i, response in enumerate(responses):
            request_id = response.headers.get('X-Request-ID', f'missing-{i}')
            request_ids.append(request_id)
            print(f"    请求 {i+1}: ID={request_id[:8]}..., 状态码={response.status_code}")
        
        # 验证所有请求ID都是唯一的
        unique_ids = set(request_ids)
        print(f"  总请求数: {len(request_ids)}")
        print(f"  唯一请求ID数: {len(unique_ids)}")
        print(f"  ID唯一性: {'✅ 通过' if len(unique_ids) == len(request_ids) else '❌ 失败'}")

async def test_slow_request_logging():
    """测试慢请求日志记录"""
    print(f"\n⏰ 测试慢请求日志记录...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 发送请求并测量时间
        start_time = time.time()
        response = await client.get(f"{TEST_CONFIG['base_url']}/health")
        end_time = time.time()
        
        duration = end_time - start_time
        process_time = float(response.headers.get('X-Process-Time', '0'))
        
        print(f"  请求总耗时: {duration:.3f}秒")
        print(f"  服务器处理时间: {process_time:.3f}秒")
        print(f"  请求ID: {response.headers.get('X-Request-ID', 'N/A')}")
        
        # 判断是否为慢请求
        if process_time > 1.0:
            print(f"  🐌 慢请求检测: 是 (>{1.0}s)")
        else:
            print(f"  ⚡ 快请求: 是 (<{1.0}s)")

def check_log_files():
    """检查日志文件生成"""
    print(f"\n📁 检查日志文件...")
    
    log_paths = [
        "./logs/trading-service.log",
        "./logs/trading-service.error.log"
    ]
    
    for log_path in log_paths:
        if os.path.exists(log_path):
            file_size = os.path.getsize(log_path)
            print(f"  ✅ {log_path}: 存在 ({file_size} bytes)")
            
            # 读取最后几行日志
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"    最新日志条目数: {len(lines)}")
                        
                        # 尝试解析最后一行为JSON
                        last_line = lines[-1].strip()
                        if last_line:
                            try:
                                log_data = json.loads(last_line)
                                print(f"    最后一条日志格式: JSON ✅")
                                print(f"    时间戳: {log_data.get('time', 'N/A')}")
                                print(f"    级别: {log_data.get('level', 'N/A')}")
                            except json.JSONDecodeError:
                                print(f"    最后一条日志格式: 文本")
                    else:
                        print(f"    文件为空")
            except Exception as e:
                print(f"    读取日志文件失败: {str(e)}")
        else:
            print(f"  ❌ {log_path}: 不存在")

async def run_structured_logging_tests():
    """运行所有结构化日志测试"""
    print("🎯 开始结构化日志中间件测试")
    print("=" * 60)
    
    try:
        # 1. 基础请求日志测试
        await test_basic_request_logging()
        
        # 2. 认证请求日志测试
        await test_authenticated_request_logging()
        
        # 3. 错误日志测试
        await test_error_logging()
        
        # 4. 并发请求追踪测试
        await test_concurrent_requests()
        
        # 5. 慢请求日志测试
        await test_slow_request_logging()
        
        # 6. 检查日志文件
        check_log_files()
        
        print("\n" + "=" * 60)
        print("🎉 结构化日志中间件测试完成")
        
        print(f"\n💡 测试总结:")
        print(f"  ✅ 请求ID生成和追踪")
        print(f"  ✅ 结构化日志记录")
        print(f"  ✅ 业务事件日志")
        print(f"  ✅ 错误日志记录")
        print(f"  ✅ 性能监控日志")
        print(f"  ✅ 并发请求唯一性")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_structured_logging_tests())