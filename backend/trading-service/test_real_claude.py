#!/usr/bin/env python3
"""
真实Claude API测试脚本

测试真实Claude API的连接和功能
"""

import asyncio
import json
from datetime import datetime

from app.ai.core.claude_client import claude_client
from app.services.ai_service import AIService


async def test_real_claude_connection():
    """测试真实Claude API连接"""
    print("\n🔗 测试真实Claude API连接")
    print("=" * 50)
    
    print(f"🤖 Claude客户端状态:")
    print(f"启用状态: {'✅ 已启用' if claude_client.enabled else '❌ 未启用'}")
    print(f"API密钥: {'✅ 已配置' if claude_client.api_key else '❌ 未配置'}")
    print(f"Base URL: {claude_client.base_url or '默认'}")
    print(f"配置模型: {claude_client.model}")
    
    if not claude_client.enabled:
        print("❌ Claude API未启用，请检查配置")
        return False
    
    try:
        # 测试简单对话
        messages = [
            {"role": "user", "content": "你好，请用中文简单介绍一下你自己"}
        ]
        
        response = await claude_client.chat_completion(
            messages=messages,
            temperature=0.7
        )
        
        print(f"✅ API连接成功: {response['success']}")
        if response['success']:
            print(f"📝 响应内容: {response['content'][:200]}...")
            print(f"🔢 输入Token: {response['usage']['input_tokens']}")
            print(f"🔢 输出Token: {response['usage']['output_tokens']}")
            print(f"🔢 总Token: {response['usage']['total_tokens']}")
            print(f"⏱️ 响应时间: {response['usage']['response_time_ms']:.2f}ms")
            print(f"🤖 使用模型: {response['model']}")
        else:
            print(f"❌ API调用失败: {response.get('error', '未知错误')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Claude API连接测试失败: {str(e)}")
        return False


async def test_strategy_generation_real():
    """测试真实的策略生成"""
    print("\n🧪 测试真实策略生成")
    print("=" * 50)
    
    try:
        response = await claude_client.generate_strategy_code(
            description="创建一个基于RSI和MACD指标的趋势跟踪策略，当RSI超买超卖时结合MACD信号进行交易",
            indicators=["RSI", "MACD", "SMA"],
            timeframe="1h",
            risk_level="medium"
        )
        
        print(f"✅ 策略生成成功: {response['success']}")
        if response['success']:
            content = response['content']
            print(f"📝 策略内容长度: {len(content)} 字符")
            print(f"🔢 Token使用: {response['usage']['total_tokens']}")
            
            # 检查是否包含策略要素
            if "```python" in content:
                print("✅ 包含Python代码块")
            if "RSI" in content and "MACD" in content:
                print("✅ 包含要求的技术指标")
            if "class" in content or "def" in content:
                print("✅ 包含函数或类定义")
            
            # 输出部分内容
            print(f"\n📄 策略内容预览:")
            print("-" * 30)
            print(content[:500] + "..." if len(content) > 500 else content)
        
        return response['success']
        
    except Exception as e:
        print(f"❌ 策略生成测试失败: {str(e)}")
        return False


async def test_market_analysis_real():
    """测试真实的市场分析"""
    print("\n📊 测试真实市场分析")
    print("=" * 50)
    
    try:
        market_data = {
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "timestamp": datetime.now().isoformat(),
            "current_prices": {
                "BTC/USDT": {"price": 65000, "change_24h": 3.2, "volume": 28000000000},
                "ETH/USDT": {"price": 3200, "change_24h": -1.8, "volume": 15000000000}
            },
            "technical_indicators": {
                "BTC/USDT": {"rsi": 68, "macd": 1250, "sma_20": 64500},
                "ETH/USDT": {"rsi": 45, "macd": -85, "sma_20": 3150}
            }
        }
        
        response = await claude_client.analyze_market_data(
            market_data=market_data,
            symbols=["BTC/USDT", "ETH/USDT"],
            analysis_type="technical"
        )
        
        print(f"✅ 市场分析成功: {response['success']}")
        if response['success']:
            content = response['content']
            print(f"📝 分析内容长度: {len(content)} 字符")
            print(f"🔢 Token使用: {response['usage']['total_tokens']}")
            
            # 检查分析质量
            content_lower = content.lower()
            analysis_keywords = ["趋势", "支撑", "阻力", "建议", "风险", "btc", "eth"]
            found_keywords = [kw for kw in analysis_keywords if kw in content_lower]
            print(f"✅ 包含分析要素: {', '.join(found_keywords)}")
            
            # 输出分析内容
            print(f"\n📄 市场分析内容:")
            print("-" * 30)
            print(content)
        
        return response['success']
        
    except Exception as e:
        print(f"❌ 市场分析测试失败: {str(e)}")
        return False


async def test_ai_service_real():
    """测试AI服务的真实功能"""
    print("\n🤖 测试AI服务真实功能")
    print("=" * 50)
    
    try:
        # 测试对话功能
        response = await AIService.chat_completion(
            message="请分析一下当前加密货币市场的整体趋势，并给出一些交易建议",
            user_id=1,
            context={"test_mode": False},
            session_id="real_test_session"
        )
        
        print(f"✅ AI对话成功: {response['success']}")
        if response['success']:
            print(f"📝 会话ID: {response['session_id']}")
            print(f"🔢 Token使用: {response['tokens_used']}")
            print(f"🤖 使用模型: {response['model']}")
            print(f"\n📄 AI回复内容:")
            print("-" * 30)
            print(response['content'])
        
        return response['success']
        
    except Exception as e:
        print(f"❌ AI服务测试失败: {str(e)}")
        return False


async def test_claude_features():
    """测试Claude特有功能"""
    print("\n🌟 测试Claude特有功能")
    print("=" * 50)
    
    try:
        # 测试长上下文对话
        long_message = """
        我是一个加密货币交易的新手，希望你能帮我：
        
        1. 解释什么是量化交易？
        2. 推荐一些适合新手的交易策略
        3. 如何控制风险？
        4. 有什么好的学习资源？
        5. 如何评估一个交易策略的好坏？
        
        请详细回答每个问题，并给出具体的建议。
        """
        
        messages = [{"role": "user", "content": long_message}]
        
        response = await claude_client.chat_completion(
            messages=messages,
            temperature=0.6
        )
        
        print(f"✅ 长文本处理成功: {response['success']}")
        if response['success']:
            print(f"📝 输入长度: {len(long_message)} 字符")
            print(f"📝 输出长度: {len(response['content'])} 字符")
            print(f"🔢 Token使用: {response['usage']['total_tokens']}")
            
            # 检查回答质量
            content = response['content']
            if len(content) > 1000:
                print("✅ 生成详细回答")
            if "量化交易" in content and "风险" in content:
                print("✅ 回答涵盖关键概念")
            
            print(f"\n📄 详细回答预览:")
            print("-" * 30)
            print(content[:800] + "..." if len(content) > 800 else content)
        
        return response['success']
        
    except Exception as e:
        print(f"❌ Claude特有功能测试失败: {str(e)}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始真实Claude API功能测试")
    print("=" * 60)
    
    tests = [
        ("真实Claude API连接", test_real_claude_connection),
        ("真实策略生成", test_strategy_generation_real),
        ("真实市场分析", test_market_analysis_real),
        ("AI服务真实功能", test_ai_service_real),
        ("Claude特有功能", test_claude_features)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}执行异常: {str(e)}")
            results.append((test_name, False))
    
    # 测试总结
    print("\n" + "=" * 60)
    print("📊 真实Claude API测试结果")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} {test_name}")
    
    print(f"\n📈 总体结果: {passed}/{total} 测试通过 ({passed/total:.1%})")
    
    # 最终统计
    if claude_client.enabled:
        stats = claude_client.get_usage_stats()
        print(f"\n💰 本次测试费用统计:")
        print(f"总请求数: {stats['total_requests']}")
        print(f"总Token数: {stats['total_tokens']}")
        print(f"预估费用: ${stats['total_cost_usd']:.6f}")
    
    if passed == total:
        print("\n🎉 所有真实Claude API测试通过！系统已就绪！")
    else:
        print("\n⚠️ 部分测试失败，请检查API配置和网络连接")


if __name__ == "__main__":
    asyncio.run(main())