#!/usr/bin/env python3
"""
Claude API端点调试工具
测试实际的Claude API调用，并调试端点配置问题
"""

import os
import sys
import asyncio
import requests
from datetime import datetime

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.config import settings
from app.ai.core.claude_client import ClaudeClient
from loguru import logger

async def test_claude_endpoint():
    """测试Claude API端点配置"""
    
    print("🔍 Claude API端点调试开始")
    print("=" * 60)
    
    # 1. 检查环境变量配置
    print("📋 环境变量配置:")
    print(f"  CLAUDE_API_KEY: {os.getenv('CLAUDE_API_KEY')}")
    print(f"  CLAUDE_BASE_URL: {os.getenv('CLAUDE_BASE_URL')}")
    print(f"  ANTHROPIC_AUTH_TOKEN: {os.getenv('ANTHROPIC_AUTH_TOKEN')}")
    print(f"  ANTHROPIC_BASE_URL: {os.getenv('ANTHROPIC_BASE_URL')}")
    print()
    
    # 2. 检查设置配置
    print("⚙️ Settings配置:")
    print(f"  claude_api_key: {getattr(settings, 'claude_api_key', 'N/A')}")
    print(f"  claude_base_url: {getattr(settings, 'claude_base_url', 'N/A')}")
    print(f"  claude_auth_token: {getattr(settings, 'claude_auth_token', 'N/A')}")  
    print(f"  claude_model: {getattr(settings, 'claude_model', 'N/A')}")
    print()
    
    # 3. 测试直接HTTP请求 - 尝试不同的端点路径
    print("🌐 直接HTTP请求测试:")
    
    # Claude CDN7服务可能的端点路径
    test_endpoints = [
        "/api/anthropic/v1/messages",  # 之前测试失败的路径
        "/anthropic/v1/messages",     # 可能的正确路径
        "/v1/messages",               # 标准Anthropic路径
        "/api/v1/messages",           # 另一种可能
        "/messages",                  # 最简路径
    ]
    
    base_url = "https://claude.cloudcdn7.com"
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': 'cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a',
        'anthropic-version': '2023-06-01'
    }
    
    test_payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "测试消息"}]
    }
    
    for endpoint_path in test_endpoints:
        full_url = f"{base_url}{endpoint_path}"
        print(f"  测试端点: {full_url}")
        
        try:
            response = requests.post(
                full_url,
                json=test_payload,
                headers=headers,
                timeout=10
            )
            
            print(f"    状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"    ✅ 成功! 响应: {response.json()}")
                break
            else:
                print(f"    ❌ 失败: {response.text[:200]}...")
                
        except requests.RequestException as e:
            print(f"    💥 异常: {str(e)}")
        print()
    
    # 4. 测试Claude客户端初始化
    print("🤖 Claude客户端测试:")
    
    client = ClaudeClient()
    print(f"  客户端启用状态: {client.enabled}")
    print(f"  API密钥: {client.api_key[:20] if client.api_key else None}...")
    print(f"  基础URL: {client.base_url}")
    print(f"  模型: {client.model}")
    print()
    
    # 5. 尝试实际的Claude API调用
    if client.enabled:
        print("🧪 实际API调用测试:")
        try:
            test_messages = [{"role": "user", "content": "你好,请简单回复测试"}]
            
            result = await client.chat_completion(
                messages=test_messages,
                max_tokens=50,
                temperature=0.7
            )
            
            print(f"  ✅ 调用成功!")
            print(f"  响应内容: {result.get('content', '')[:100]}...")
            print(f"  Token使用: {result.get('usage', {})}")
            print(f"  模型: {result.get('model', 'unknown')}")
            
        except Exception as e:
            print(f"  ❌ 调用失败: {str(e)}")
    
    print("\n🔍 Claude API端点调试完成")

if __name__ == "__main__":
    asyncio.run(test_claude_endpoint())