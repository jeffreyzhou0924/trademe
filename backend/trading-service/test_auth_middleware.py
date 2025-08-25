#!/usr/bin/env python3
"""
认证中间件测试脚本
验证JWT认证功能和受保护端点
"""

import asyncio
import httpx
import json
from typing import Dict, Any

# 测试配置
TEST_CONFIG = {
    "base_url": "http://localhost:8001",
    "timeout": 30
}

# 测试用户
TEST_USER = {
    "email": "test@example.com",
    "password": "password123"
}

async def test_login():
    """测试用户登录"""
    print("🔐 测试用户登录...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        response = await client.post(
            f"{TEST_CONFIG['base_url']}/auth/login",
            json=TEST_USER
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 登录成功")
            print(f"   用户: {data['user']['username']}")
            print(f"   邮箱: {data['user']['email']}")
            print(f"   会员等级: {data['user']['membership_level']}")
            print(f"   Token类型: {data['token_type']}")
            print(f"   有效期: {data['expires_in']}秒")
            return data["access_token"]
        else:
            print(f"❌ 登录失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return None

async def test_protected_endpoint_without_token():
    """测试无Token访问受保护端点"""
    print("\n🚫 测试无Token访问受保护端点...")
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        response = await client.get(f"{TEST_CONFIG['base_url']}/auth/me")
        
        if response.status_code == 401:
            print("✅ 正确拒绝无Token访问")
        else:
            print(f"❌ 应该返回401，实际返回: {response.status_code}")

async def test_protected_endpoint_with_token(token: str):
    """测试有Token访问受保护端点"""
    print(f"\n🛡️ 测试有Token访问受保护端点...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        # 测试 /auth/me
        response = await client.get(
            f"{TEST_CONFIG['base_url']}/auth/me",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ /auth/me 访问成功")
            print(f"   用户ID: {data['id']}")
            print(f"   用户名: {data['username']}")
            print(f"   会员等级: {data['membership_level']}")
        else:
            print(f"❌ /auth/me 访问失败: {response.status_code}")
        
        # 测试 /auth/test
        response = await client.get(
            f"{TEST_CONFIG['base_url']}/auth/test",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ /auth/test 访问成功")
            print(f"   消息: {data['message']}")
            print(f"   用户信息: {data['user']}")
        else:
            print(f"❌ /auth/test 访问失败: {response.status_code}")

async def test_invalid_token():
    """测试无效Token"""
    print(f"\n🚫 测试无效Token...")
    
    headers = {"Authorization": "Bearer invalid_token_here"}
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        response = await client.get(
            f"{TEST_CONFIG['base_url']}/auth/me",
            headers=headers
        )
        
        if response.status_code == 401:
            print("✅ 正确拒绝无效Token")
        else:
            print(f"❌ 应该返回401，实际返回: {response.status_code}")

async def test_login_validation():
    """测试登录参数验证"""
    print(f"\n📝 测试登录参数验证...")
    
    # 测试无效邮箱
    invalid_cases = [
        {"email": "invalid", "password": "password123"},
        {"email": "test@example.com", "password": "123"},  # 密码太短
    ]
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        for i, case in enumerate(invalid_cases, 1):
            response = await client.post(
                f"{TEST_CONFIG['base_url']}/auth/login",
                json=case
            )
            
            if response.status_code == 400:
                print(f"✅ 测试用例{i} - 正确拒绝无效数据")
            else:
                print(f"❌ 测试用例{i} - 应该返回400，实际返回: {response.status_code}")

async def run_auth_tests():
    """运行所有认证测试"""
    print("🎯 开始认证中间件测试")
    print("=" * 60)
    
    # 1. 测试登录参数验证
    await test_login_validation()
    
    # 2. 测试登录
    token = await test_login()
    if not token:
        print("❌ 登录失败，无法继续测试")
        return
    
    # 3. 测试无Token访问
    await test_protected_endpoint_without_token()
    
    # 4. 测试无效Token
    await test_invalid_token()
    
    # 5. 测试有效Token访问
    await test_protected_endpoint_with_token(token)
    
    print("\n" + "=" * 60)
    print("🎉 认证中间件测试完成")

if __name__ == "__main__":
    asyncio.run(run_auth_tests())