#!/usr/bin/env python3
"""
分析AI策略生成请求与普通chat请求的内容差异
找出导致30秒超时的根本原因
"""

import asyncio
import sys
import os
import time
import httpx
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.simplified_ai_service import UnifiedProxyAIService


def analyze_system_prompt():
    """分析系统提示的差异"""
    
    print("=== 系统提示分析 ===")
    
    # 创建AI服务实例
    ai_service = UnifiedProxyAIService()
    
    # 生成不同类型的系统提示
    general_prompt = ai_service._build_system_prompt("developer", 9, "general")
    strategy_prompt = ai_service._build_system_prompt("developer", 9, "strategy")
    indicator_prompt = ai_service._build_system_prompt("developer", 9, "indicator")
    
    print(f"🔍 普通对话系统提示长度: {len(general_prompt)} 字符")
    print(f"📊 策略生成系统提示长度: {len(strategy_prompt)} 字符")
    print(f"📈 指标生成系统提示长度: {len(indicator_prompt)} 字符")
    
    print("\n--- 普通对话系统提示 ---")
    print(general_prompt)
    
    print("\n--- 策略生成系统提示 ---")
    print(strategy_prompt)
    
    print("\n--- 指标生成系统提示 ---")
    print(indicator_prompt)
    
    return {
        "general": {"prompt": general_prompt, "length": len(general_prompt)},
        "strategy": {"prompt": strategy_prompt, "length": len(strategy_prompt)},
        "indicator": {"prompt": indicator_prompt, "length": len(indicator_prompt)}
    }


def build_test_requests():
    """构建测试请求数据"""
    
    prompts = analyze_system_prompt()
    
    # 基础用户消息
    simple_message = "你好，请简单介绍一下数字货币交易"
    complex_strategy_message = "请帮我创建一个基于MACD指标的BTC交易策略，包括买卖信号、止损止盈、风险管理等完整功能"
    
    # 构建不同类型的请求
    requests = {
        "简单聊天": {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": simple_message}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "system": prompts["general"]["prompt"]
        },
        "复杂策略生成": {
            "model": "claude-sonnet-4-20250514", 
            "messages": [{"role": "user", "content": complex_strategy_message}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "system": prompts["strategy"]["prompt"]
        },
        "简化策略生成": {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "创建简单的MACD策略代码"}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "system": prompts["strategy"]["prompt"]
        }
    }
    
    return requests


async def test_proxy_service_directly():
    """直接测试代理服务的响应时间"""
    
    print("\n=== 直接代理服务测试 ===")
    
    # 代理服务配置
    proxy_base_url = "https://claude.cloudcdn7.com/api"
    proxy_api_key = "cr_b48f228f987b3d94495498a9260fdb6032ccc4cd3dd49ea380c960ed699bab56"
    
    requests = build_test_requests()
    
    for request_name, request_data in requests.items():
        print(f"\n🧪 测试 {request_name}")
        
        # 计算请求大小
        request_json = json.dumps(request_data, ensure_ascii=False)
        request_size = len(request_json.encode('utf-8'))
        
        print(f"📦 请求大小: {request_size:,} 字节")
        print(f"📄 系统提示长度: {len(request_data['system'])} 字符")
        print(f"💬 用户消息长度: {len(request_data['messages'][0]['content'])} 字符")
        
        # 发送请求并计时
        start_time = time.time()
        
        try:
            timeout_config = httpx.Timeout(40.0)  # 40秒超时测试
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {proxy_api_key}",
                    "User-Agent": "Trademe-AI-Client/1.0"
                }
                
                response = await client.post(
                    f"{proxy_base_url}/v1/messages",
                    headers=headers,
                    json=request_data
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                print(f"⏱️  响应时间: {duration:.2f}秒")
                print(f"🌐 HTTP状态: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    usage = result.get("usage", {})
                    content = result.get("content", [])
                    
                    content_length = 0
                    if content and len(content) > 0:
                        content_length = len(content[0].get("text", ""))
                    
                    print(f"📤 输入Token: {usage.get('input_tokens', 0)}")
                    print(f"📥 输出Token: {usage.get('output_tokens', 0)}")  
                    print(f"📝 响应长度: {content_length} 字符")
                    print(f"✅ 请求成功")
                    
                else:
                    print(f"❌ 请求失败: {response.status_code}")
                    print(f"错误内容: {response.text[:200]}...")
        
        except httpx.TimeoutException as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"⏰ 请求超时: {duration:.2f}秒")
            print(f"❌ 超时错误: {str(e)}")
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"⏱️  错误发生时间: {duration:.2f}秒")
            print(f"❌ 请求异常: {str(e)}")
        
        print("-" * 60)


async def test_request_complexity_correlation():
    """测试请求复杂度与处理时间的相关性"""
    
    print("\n=== 请求复杂度与处理时间相关性测试 ===")
    
    # 代理服务配置
    proxy_base_url = "https://claude.cloudcdn7.com/api"
    proxy_api_key = "cr_b48f228f987b3d94495498a9260fdb6032ccc4cd3dd49ea380c960ed699bab56"
    
    # 基础系统提示 
    base_prompt = "你是Trademe平台的AI交易助手，专门帮助用户进行数字货币交易决策。"
    
    # 创建不同复杂度的测试用例
    test_cases = [
        {
            "name": "最简单请求",
            "system": base_prompt,
            "message": "你好"
        },
        {
            "name": "简单策略询问",
            "system": base_prompt + "请帮助用户创建交易策略。",
            "message": "什么是MACD?"
        },
        {
            "name": "中等复杂度策略请求",
            "system": base_prompt + """
请帮助用户创建交易策略，提供完整的Python代码实现，包括策略类定义、方法实现、参数配置和注释。请将Python代码包装在 ```python 代码块中。
""",
            "message": "创建一个简单的MACD策略"
        },
        {
            "name": "高复杂度策略请求",
            "system": base_prompt + """
请帮助用户创建交易策略，提供完整的Python代码实现，包括策略类定义、方法实现、参数配置和注释。请将Python代码包装在 ```python 代码块中。
""",
            "message": "请帮我创建一个完整的多因子量化交易策略，结合MACD、RSI、布林带指标，包含完整的风险管理、仓位管理、止损止盈逻辑，支持多种交易对，具备回测功能和实盘交易接口"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 测试用例 {i}: {test_case['name']}")
        
        request_data = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": test_case["message"]}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "system": test_case["system"]
        }
        
        # 分析请求特征
        request_json = json.dumps(request_data, ensure_ascii=False)
        request_size = len(request_json.encode('utf-8'))
        system_length = len(test_case["system"])
        message_length = len(test_case["message"])
        
        print(f"📦 请求大小: {request_size:,} 字节")
        print(f"🎯 系统提示: {system_length} 字符")
        print(f"💬 用户消息: {message_length} 字符")
        
        # 发送请求并测量时间
        start_time = time.time()
        
        try:
            timeout_config = httpx.Timeout(35.0)  # 35秒超时
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {proxy_api_key}",
                    "User-Agent": "Trademe-AI-Client/1.0"
                }
                
                response = await client.post(
                    f"{proxy_base_url}/v1/messages",
                    headers=headers,
                    json=request_data
                )
                
                end_time = time.time()
                duration = end_time - start_time
                success = response.status_code == 200
                
                # 分析响应
                output_tokens = 0
                response_length = 0
                if success:
                    result = response.json()
                    usage = result.get("usage", {})
                    output_tokens = usage.get("output_tokens", 0)
                    content = result.get("content", [])
                    if content and len(content) > 0:
                        response_length = len(content[0].get("text", ""))
                
                result_data = {
                    "name": test_case['name'],
                    "request_size": request_size,
                    "system_length": system_length,
                    "message_length": message_length,
                    "duration": duration,
                    "success": success,
                    "http_status": response.status_code,
                    "output_tokens": output_tokens,
                    "response_length": response_length
                }
                
                results.append(result_data)
                
                print(f"⏱️  处理时间: {duration:.2f}秒")
                print(f"🌐 HTTP状态: {response.status_code}")
                print(f"📥 输出Token: {output_tokens}")
                print(f"📝 响应长度: {response_length} 字符")
                print(f"{'✅ 成功' if success else '❌ 失败'}")
                
        except httpx.TimeoutException:
            end_time = time.time()
            duration = end_time - start_time
            results.append({
                "name": test_case['name'],
                "request_size": request_size,
                "system_length": system_length,
                "message_length": message_length,
                "duration": duration,
                "success": False,
                "http_status": 408,  # 超时
                "output_tokens": 0,
                "response_length": 0
            })
            
            print(f"⏰ 请求超时: {duration:.2f}秒")
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            results.append({
                "name": test_case['name'],
                "request_size": request_size,
                "system_length": system_length,
                "message_length": message_length,
                "duration": duration,
                "success": False,
                "http_status": 500,  # 服务器错误
                "output_tokens": 0,
                "response_length": 0
            })
            
            print(f"❌ 请求异常: {str(e)}")
        
        print("-" * 60)
    
    # 分析结果
    print("\n=== 分析结果 ===")
    print(f"{'测试用例':<20} {'请求大小':<10} {'系统提示':<8} {'消息长度':<8} {'处理时间':<8} {'状态'}")
    print("-" * 80)
    
    for result in results:
        status = "✅成功" if result['success'] else f"❌失败({result['http_status']})"
        print(f"{result['name']:<20} {result['request_size']:<10} {result['system_length']:<8} {result['message_length']:<8} {result['duration']:<8.1f} {status}")
    
    # 计算相关性
    successful_results = [r for r in results if r['success']]
    if len(successful_results) > 1:
        print("\n🔍 成功请求的处理时间分析:")
        for result in successful_results:
            print(f"  {result['name']}: {result['duration']:.2f}秒 (输出{result['output_tokens']}Token)")
    
    timeout_results = [r for r in results if not r['success'] and r['duration'] > 30]
    if timeout_results:
        print("\n⏰ 超时请求分析:")
        for result in timeout_results:
            print(f"  {result['name']}: 超时 {result['duration']:.2f}秒")
    
    return results


async def main():
    """主测试函数"""
    
    print("🔍 TradeMe AI策略生成超时问题深度分析")
    print("=" * 80)
    
    # 1. 分析系统提示差异
    prompt_analysis = analyze_system_prompt()
    
    # 2. 测试代理服务直接响应
    await test_proxy_service_directly()
    
    # 3. 测试请求复杂度与处理时间相关性
    correlation_results = await test_request_complexity_correlation()
    
    print("\n" + "=" * 80)
    print("📋 分析总结:")
    
    # 总结发现
    print("\n🎯 关键发现:")
    print("1. 系统提示长度差异:")
    for prompt_type, data in prompt_analysis.items():
        print(f"   - {prompt_type}: {data['length']} 字符")
    
    print("\n2. 请求复杂度影响:")
    successful = sum(1 for r in correlation_results if r['success'])
    failed = len(correlation_results) - successful
    print(f"   - 成功请求: {successful}/{len(correlation_results)}")
    print(f"   - 失败请求: {failed}/{len(correlation_results)}")
    
    if correlation_results:
        avg_success_time = sum(r['duration'] for r in correlation_results if r['success']) / max(successful, 1)
        avg_timeout_time = sum(r['duration'] for r in correlation_results if not r['success']) / max(failed, 1)
        print(f"   - 成功请求平均时间: {avg_success_time:.2f}秒")
        print(f"   - 失败请求平均时间: {avg_timeout_time:.2f}秒")
    
    print("\n💡 优化建议:")
    print("1. 简化策略生成的系统提示，减少不必要的复杂指令")
    print("2. 分段处理复杂策略请求，避免单次请求过于复杂") 
    print("3. 考虑使用更短的用户消息进行初步测试")
    print("4. 实施请求预处理，过滤可能导致超时的复杂请求")
    
    return correlation_results


if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0)