#!/usr/bin/env python3
"""
测试改进的代理重试系统
验证超时问题是否得到解决
"""

import asyncio
import sys
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/root/trademe/backend/trading-service')

from app.ai.core.claude_client import claude_client
from app.services.proxy_retry_manager import proxy_retry_manager, ProxyEndpoint
from app.config import settings


async def test_basic_chat():
    """测试基础聊天功能"""
    print("\n🧪 测试基础聊天功能...")
    
    messages = [
        {"role": "user", "content": "你好，请简单介绍一下自己"}
    ]
    
    start_time = time.time()
    
    try:
        result = await claude_client.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=100
        )
        
        elapsed = time.time() - start_time
        
        if result["success"]:
            print(f"✅ 聊天成功！")
            print(f"   响应时间: {elapsed:.2f}秒")
            print(f"   使用模型: {result.get('model')}")
            print(f"   Token使用: {result['usage'].get('total_tokens', 0)}")
            print(f"   响应内容: {result['content'][:100]}...")
            return True
        else:
            print(f"❌ 聊天失败: {result.get('error')}")
            return False
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ 测试失败 ({elapsed:.2f}秒): {e}")
        return False


async def test_timeout_handling():
    """测试超时处理机制"""
    print("\n🧪 测试超时处理机制...")
    
    # 添加一个可能超时的代理进行测试
    test_proxy = ProxyEndpoint(
        url=settings.claude_base_url or "https://api.anthropic.com/v1",
        name="Test Proxy",
        priority=100,
        timeout=10,  # 短超时用于测试
        max_retries=2
    )
    
    proxy_retry_manager.add_proxy(test_proxy)
    
    messages = [
        {"role": "user", "content": "生成一个复杂的量化交易策略，包含多个技术指标"}
    ]
    
    start_time = time.time()
    
    try:
        result = await claude_client.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        elapsed = time.time() - start_time
        
        if result["success"]:
            print(f"✅ 请求成功处理！")
            print(f"   总耗时: {elapsed:.2f}秒")
            
            # 获取代理统计信息
            stats = proxy_retry_manager.get_statistics()
            print(f"\n📊 代理统计:")
            print(f"   总请求数: {stats['total_requests']}")
            print(f"   成功请求: {stats['successful_requests']}")
            print(f"   失败请求: {stats['failed_requests']}")
            print(f"   成功率: {stats['overall_success_rate']}")
            
            for proxy_stat in stats['proxy_stats']:
                print(f"\n   {proxy_stat['name']}:")
                print(f"     状态: {proxy_stat['status']}")
                print(f"     成功率: {proxy_stat['success_rate']}")
                print(f"     平均响应时间: {proxy_stat['avg_response_time']}")
                
            return True
        else:
            print(f"❌ 请求失败: {result.get('error')}")
            return False
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ 超时测试失败 ({elapsed:.2f}秒): {e}")
        return False


async def test_proxy_rotation():
    """测试代理轮换功能"""
    print("\n🧪 测试代理轮换功能...")
    
    # 添加多个代理进行测试
    proxies = [
        ProxyEndpoint(
            url="https://api.anthropic.com/v1",
            name="Primary API",
            priority=100,
            timeout=180
        ),
        ProxyEndpoint(
            url=settings.claude_base_url or "https://api.anthropic.com/v1",
            name="Backup Proxy",
            priority=90,
            timeout=200
        )
    ]
    
    for proxy in proxies:
        proxy_retry_manager.add_proxy(proxy)
    
    # 进行多次请求测试轮换
    success_count = 0
    for i in range(3):
        print(f"\n   请求 {i+1}/3...")
        
        messages = [
            {"role": "user", "content": f"测试请求 {i+1}: 生成一个简单的移动平均策略"}
        ]
        
        try:
            result = await claude_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            
            if result["success"]:
                print(f"   ✅ 请求 {i+1} 成功")
                if 'proxy_used' in result.get('usage', {}):
                    print(f"      使用代理: {result['usage']['proxy_used']}")
                success_count += 1
            else:
                print(f"   ❌ 请求 {i+1} 失败")
                
        except Exception as e:
            print(f"   ❌ 请求 {i+1} 异常: {e}")
            
        await asyncio.sleep(1)  # 避免过快请求
    
    print(f"\n📊 轮换测试结果: {success_count}/3 成功")
    return success_count >= 2  # 至少2个成功


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🚀 代理重试系统测试")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查配置
    print("\n📋 当前配置:")
    print(f"   Claude超时设置: {settings.claude_timeout}秒")
    print(f"   Claude基础URL: {settings.claude_base_url or '默认'}")
    print(f"   Claude API密钥: {'已配置' if settings.claude_api_key else '未配置'}")
    
    # 启动健康监控
    await proxy_retry_manager.start_health_monitoring()
    
    # 运行测试
    tests = [
        ("基础聊天", test_basic_chat),
        ("超时处理", test_timeout_handling),
        ("代理轮换", test_proxy_rotation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"运行测试: {test_name}")
        print('='*40)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((test_name, False))
    
    # 停止健康监控
    await proxy_retry_manager.stop_health_monitoring()
    
    # 输出总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    # 输出最终统计
    final_stats = proxy_retry_manager.get_statistics()
    print(f"\n📈 最终统计:")
    print(f"   总请求数: {final_stats['total_requests']}")
    print(f"   成功率: {final_stats['overall_success_rate']}")
    
    success_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    print(f"\n🎯 总体结果: {success_count}/{total_count} 测试通过")
    
    if success_count == total_count:
        print("🎉 所有测试通过！代理重试系统工作正常。")
    elif success_count > 0:
        print("⚠️ 部分测试通过，系统可能需要进一步优化。")
    else:
        print("❌ 所有测试失败，请检查系统配置。")


if __name__ == "__main__":
    asyncio.run(main())