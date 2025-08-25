#!/usr/bin/env python3
"""
速率限制中间件测试脚本
验证API速率限制功能
"""

import asyncio
import httpx
import time
from typing import List

# 测试配置
TEST_CONFIG = {
    "base_url": "http://localhost:8001",
    "timeout": 30
}

async def test_basic_rate_limit():
    """测试基础速率限制"""
    print("🚦 测试基础速率限制...")
    
    endpoint = "/auth/login"  # 限制10次/分钟
    test_data = {"email": "test@example.com", "password": "password123"}
    
    success_count = 0
    rate_limited_count = 0
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 快速发送15个请求
        for i in range(15):
            try:
                response = await client.post(f"{TEST_CONFIG['base_url']}{endpoint}", json=test_data)
                
                if response.status_code == 200:
                    success_count += 1
                    print(f"  请求 {i+1}: ✅ 成功 (状态码: {response.status_code})")
                elif response.status_code == 429:
                    rate_limited_count += 1
                    data = response.json()
                    print(f"  请求 {i+1}: 🚫 速率限制 (剩余: {response.headers.get('X-RateLimit-Remaining', 'N/A')})")
                    if i >= 10:  # 前10个可能成功，后面应该被限制
                        print(f"    ✅ 正确触发速率限制")
                else:
                    print(f"  请求 {i+1}: ⚠️ 其他状态码: {response.status_code}")
                
                # 检查速率限制头
                headers = response.headers
                if 'X-RateLimit-Limit' in headers:
                    print(f"    限制: {headers['X-RateLimit-Limit']}, 剩余: {headers.get('X-RateLimit-Remaining', 'N/A')}")
                    
            except Exception as e:
                print(f"  请求 {i+1}: ❌ 异常: {str(e)}")
            
            # 避免请求过快
            await asyncio.sleep(0.1)
    
    print(f"\n📊 结果统计:")
    print(f"  成功请求: {success_count}")
    print(f"  被限制请求: {rate_limited_count}")
    print(f"  总请求: {success_count + rate_limited_count}")

async def test_different_endpoints():
    """测试不同端点的速率限制"""
    print(f"\n🎯 测试不同端点的速率限制...")
    
    endpoints_tests = [
        ("/health", "GET", None, "健康检查 (应该不被限制)"),
        ("/", "GET", None, "根路径 (应该不被限制)"),
        ("/auth/test", "GET", None, "认证测试端点"),
    ]
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        for endpoint, method, data, description in endpoints_tests:
            print(f"\n  测试: {description}")
            print(f"  端点: {method} {endpoint}")
            
            # 发送几个请求看限制情况
            for i in range(5):
                try:
                    if method == "GET":
                        response = await client.get(f"{TEST_CONFIG['base_url']}{endpoint}")
                    else:
                        response = await client.post(f"{TEST_CONFIG['base_url']}{endpoint}", json=data)
                    
                    print(f"    请求 {i+1}: 状态码 {response.status_code}")
                    
                    # 显示速率限制信息
                    if 'X-RateLimit-Limit' in response.headers:
                        print(f"      限制: {response.headers['X-RateLimit-Limit']}")
                        print(f"      剩余: {response.headers.get('X-RateLimit-Remaining', 'N/A')}")
                        
                except Exception as e:
                    print(f"    请求 {i+1}: 异常 - {str(e)}")
                
                await asyncio.sleep(0.2)

async def test_authenticated_vs_anonymous():
    """测试认证用户与匿名用户的速率限制差异"""
    print(f"\n🔐 测试认证用户与匿名用户的速率限制...")
    
    # 先登录获取Token
    login_data = {"email": "test@example.com", "password": "password123"}
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 登录获取Token
        print("  获取认证Token...")
        login_response = await client.post(f"{TEST_CONFIG['base_url']}/auth/login", json=login_data)
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("  ✅ 获取Token成功")
        else:
            print("  ❌ 登录失败，跳过认证用户测试")
            return
        
        # 测试认证用户的速率限制
        print(f"\n  测试认证用户访问 /auth/test...")
        auth_success = 0
        for i in range(8):
            response = await client.get(f"{TEST_CONFIG['base_url']}/auth/test", headers=headers)
            if response.status_code == 200:
                auth_success += 1
            print(f"    认证请求 {i+1}: {response.status_code} (剩余: {response.headers.get('X-RateLimit-Remaining', 'N/A')})")
            await asyncio.sleep(0.1)
        
        # 测试匿名用户的速率限制
        print(f"\n  测试匿名用户访问 /auth/test...")
        anon_success = 0
        for i in range(8):
            response = await client.get(f"{TEST_CONFIG['base_url']}/auth/test")
            if response.status_code in [401, 403]:  # 匿名用户会被认证拦截
                anon_success += 1
            print(f"    匿名请求 {i+1}: {response.status_code} (剩余: {response.headers.get('X-RateLimit-Remaining', 'N/A')})")
            await asyncio.sleep(0.1)
        
        print(f"\n  📊 对比结果:")
        print(f"    认证用户成功访问: {auth_success}/8")
        print(f"    匿名用户到达认证层: {anon_success}/8")

async def test_rate_limit_headers():
    """测试速率限制响应头"""
    print(f"\n📋 测试速率限制响应头...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        response = await client.get(f"{TEST_CONFIG['base_url']}/health")
        
        print(f"  响应状态: {response.status_code}")
        print(f"  响应头信息:")
        
        rate_limit_headers = {
            "X-RateLimit-Limit": "速率限制",
            "X-RateLimit-Remaining": "剩余请求数",
            "X-RateLimit-Reset": "重置时间",
            "X-Process-Time": "处理时间",
        }
        
        for header, description in rate_limit_headers.items():
            if header in response.headers:
                print(f"    {header}: {response.headers[header]} ({description})")
            else:
                print(f"    {header}: 未设置 ({description})")

async def test_burst_requests():
    """测试突发请求处理"""
    print(f"\n💨 测试突发请求处理...")
    
    endpoint = "/health"  # 使用不被限制的端点进行压力测试
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        print("  发送50个并发请求...")
        
        # 创建50个并发请求
        tasks = []
        for i in range(50):
            task = client.get(f"{TEST_CONFIG['base_url']}{endpoint}")
            tasks.append(task)
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        success_count = 0
        error_count = 0
        
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                error_count += 1
                if i < 5:  # 只显示前5个错误
                    print(f"    请求 {i+1}: ❌ 异常: {str(response)}")
            else:
                if response.status_code == 200:
                    success_count += 1
                if i < 5:  # 只显示前5个结果
                    print(f"    请求 {i+1}: 状态码 {response.status_code}")
        
        print(f"\n  📊 突发请求结果:")
        print(f"    总请求数: 50")
        print(f"    成功请求: {success_count}")
        print(f"    失败请求: {error_count}")
        print(f"    总耗时: {end_time - start_time:.2f}秒")
        print(f"    平均响应时间: {(end_time - start_time) / 50:.3f}秒")

async def run_rate_limit_tests():
    """运行所有速率限制测试"""
    print("🎯 开始速率限制中间件测试")
    print("=" * 60)
    
    try:
        # 1. 基础速率限制测试
        await test_basic_rate_limit()
        
        # 等待一段时间让速率限制重置
        print(f"\n⏳ 等待5秒让速率限制重置...")
        await asyncio.sleep(5)
        
        # 2. 不同端点测试
        await test_different_endpoints()
        
        # 3. 认证用户vs匿名用户测试
        await test_authenticated_vs_anonymous()
        
        # 4. 响应头测试
        await test_rate_limit_headers()
        
        # 5. 突发请求测试
        await test_burst_requests()
        
        print("\n" + "=" * 60)
        print("🎉 速率限制中间件测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_rate_limit_tests())