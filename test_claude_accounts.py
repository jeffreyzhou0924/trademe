#!/usr/bin/env python3
"""
Claude账户连接测试脚本
直接测试数据库中的Claude账户是否可以正常连接
"""

import asyncio
import sqlite3
import aiohttp
import json
import time
from typing import Dict, Any, List, Optional

# Claude连接测试配置
CLAUDE_API_ENDPOINTS = {
    "proxy_service": "https://claude.cloudcdn7.com/api/v1/messages",
    "direct": "https://api.anthropic.com/v1/messages"
}

async def test_claude_account(
    account_name: str,
    api_key: str,
    proxy_base_url: str,
    proxy_type: str = "proxy_service"
) -> Dict[str, Any]:
    """测试单个Claude账户连接"""
    
    print(f"🧪 测试账户: {account_name}")
    print(f"📍 代理URL: {proxy_base_url}")
    print(f"🔑 API密钥: {api_key[:20]}...")
    
    # 构建完整API端点
    if proxy_type == "proxy_service":
        endpoint = f"{proxy_base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Trademe/1.0 (Test)"
        }
    else:
        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    
    # 测试请求数据
    test_data = {
        "model": "claude-sonnet-4-20250514",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
        "temperature": 0.0
    }
    
    start_time = time.time()
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, headers=headers, json=test_data) as response:
                response_time = int((time.time() - start_time) * 1000)
                response_text = await response.text()
                
                print(f"📊 响应状态码: {response.status}")
                print(f"⏱️ 响应时间: {response_time}ms")
                print(f"📝 响应内容: {response_text[:200]}...")
                
                result = {
                    "account_name": account_name,
                    "status_code": response.status,
                    "response_time_ms": response_time,
                    "success": response.status == 200,
                    "endpoint": endpoint,
                    "error_message": None,
                    "response_preview": response_text[:500]
                }
                
                if response.status == 200:
                    try:
                        response_json = json.loads(response_text)
                        result["model"] = response_json.get("model", "unknown")
                        print("✅ 连接成功！")
                    except json.JSONDecodeError:
                        result["success"] = False
                        result["error_message"] = "响应JSON格式错误"
                        print("❌ JSON解析失败")
                        
                elif response.status == 401:
                    result["error_message"] = "API密钥无效或已过期"
                    print("❌ 认证失败")
                elif response.status == 403:
                    result["error_message"] = "API配额已耗尽"
                    print("❌ 配额不足")
                elif response.status == 429:
                    result["error_message"] = "请求频率限制"
                    print("⚠️ 请求限流")
                else:
                    result["error_message"] = f"HTTP错误: {response.status}"
                    print(f"❌ HTTP错误: {response.status}")
                
                return result
                
    except aiohttp.ClientError as e:
        result = {
            "account_name": account_name,
            "status_code": None,
            "response_time_ms": int((time.time() - start_time) * 1000),
            "success": False,
            "endpoint": endpoint,
            "error_message": f"网络连接错误: {str(e)}",
            "response_preview": None
        }
        print(f"❌ 连接错误: {e}")
        return result
    
    except Exception as e:
        result = {
            "account_name": account_name,
            "status_code": None,
            "response_time_ms": int((time.time() - start_time) * 1000),
            "success": False,
            "endpoint": endpoint,
            "error_message": f"未知错误: {str(e)}",
            "response_preview": None
        }
        print(f"❌ 未知错误: {e}")
        return result

async def load_and_test_accounts() -> List[Dict[str, Any]]:
    """从数据库加载并测试所有Claude账户"""
    
    # 连接数据库
    conn = sqlite3.connect('/root/trademe/data/trademe.db')
    cursor = conn.cursor()
    
    # 查询Claude账户
    cursor.execute("""
        SELECT id, account_name, api_key, proxy_base_url, proxy_type, status
        FROM claude_accounts 
        WHERE status = 'active'
        ORDER BY id
    """)
    
    accounts = cursor.fetchall()
    conn.close()
    
    if not accounts:
        print("❌ 数据库中没有找到活跃的Claude账户")
        return []
    
    print(f"📋 找到 {len(accounts)} 个活跃Claude账户")
    print("=" * 80)
    
    results = []
    
    for account in accounts:
        account_id, account_name, api_key, proxy_base_url, proxy_type, status = account
        
        print(f"\n🔍 测试账户 [{account_id}] {account_name}")
        print(f"📍 状态: {status}")
        print("-" * 50)
        
        result = await test_claude_account(
            account_name=account_name,
            api_key=api_key,
            proxy_base_url=proxy_base_url or "https://claude.cloudcdn7.com/api",
            proxy_type=proxy_type or "proxy_service"
        )
        
        results.append(result)
        print("-" * 50)
        
        # 间隔1秒，避免请求过于频繁
        await asyncio.sleep(1)
    
    return results

async def main():
    """主测试流程"""
    print("🚀 Claude账户连接测试开始")
    print("=" * 80)
    
    results = await load_and_test_accounts()
    
    if not results:
        return
    
    # 汇总测试结果
    print("\n📊 测试结果汇总")
    print("=" * 80)
    
    successful = 0
    failed = 0
    
    for result in results:
        status = "✅ 成功" if result["success"] else "❌ 失败"
        error_msg = f" - {result['error_message']}" if result.get("error_message") else ""
        
        print(f"{result['account_name']:<20} {status}{error_msg}")
        
        if result["success"]:
            successful += 1
        else:
            failed += 1
    
    print("-" * 80)
    print(f"✅ 成功: {successful}个")
    print(f"❌ 失败: {failed}个")
    print(f"📊 成功率: {successful/(successful+failed)*100:.1f}%" if (successful+failed) > 0 else "N/A")
    
    # 如果有失败的账户，提供详细错误信息
    if failed > 0:
        print("\n🔍 失败账户详细信息:")
        for result in results:
            if not result["success"]:
                print(f"\n账户: {result['account_name']}")
                print(f"端点: {result['endpoint']}")
                print(f"错误: {result['error_message']}")
                if result.get("response_preview"):
                    print(f"响应: {result['response_preview'][:200]}...")

if __name__ == "__main__":
    asyncio.run(main())