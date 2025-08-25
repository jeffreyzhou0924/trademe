#!/usr/bin/env python3
"""
Claude AI功能测试脚本

测试Claude AI集成的各项功能：
- Claude客户端连接
- 基础对话功能
- 策略生成功能
- 市场分析功能
- 使用统计功能
"""

import asyncio
import json
from datetime import datetime

from app.ai.core.claude_client import claude_client
from app.services.ai_service import AIService
from app.ai.prompts.system_prompts import SystemPrompts
from app.ai.prompts.trading_prompts import TradingPrompts


async def test_claude_client_basic():
    """测试Claude客户端基础功能"""
    print("\n🧪 测试1: Claude客户端基础功能")
    print("=" * 50)
    
    # 测试基础对话
    messages = [
        {"role": "user", "content": "你好，请简单介绍一下你的功能"}
    ]
    
    try:
        response = await claude_client.chat_completion(
            messages=messages,
            system_prompt=SystemPrompts.TRADING_ASSISTANT_SYSTEM,
            temperature=0.7
        )
        
        print(f"✅ 对话响应成功: {response['success']}")
        print(f"📝 响应内容: {response['content'][:200]}...")
        print(f"🔢 Token使用: {response['usage']['total_tokens'] if response['success'] else 0}")
        print(f"🤖 使用模型: {response['model']}")
        
        return response['success']
        
    except Exception as e:
        print(f"❌ Claude客户端测试失败: {str(e)}")
        return False


async def test_strategy_generation():
    """测试策略生成功能"""
    print("\n🧪 测试2: 策略生成功能")
    print("=" * 50)
    
    try:
        response = await claude_client.generate_strategy_code(
            description="创建一个基于双移动平均线交叉的简单策略",
            indicators=["SMA", "EMA"],
            timeframe="1h",
            risk_level="medium"
        )
        
        print(f"✅ 策略生成成功: {response['success']}")
        if response['success']:
            content = response['content']
            if "```python" in content:
                print("✅ 包含Python代码块")
            if "class" in content or "def" in content:
                print("✅ 包含函数或类定义")
            print(f"📝 策略内容长度: {len(content)} 字符")
            print(f"🔢 Token使用: {response['usage']['total_tokens']}")
        
        return response['success']
        
    except Exception as e:
        print(f"❌ 策略生成测试失败: {str(e)}")
        return False


async def test_market_analysis():
    """测试市场分析功能"""
    print("\n🧪 测试3: 市场分析功能")
    print("=" * 50)
    
    try:
        market_data = {
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "timestamp": datetime.utcnow().isoformat(),
            "prices": {
                "BTC/USDT": {"price": 45000, "change_24h": 2.5},
                "ETH/USDT": {"price": 3000, "change_24h": -1.2}
            }
        }
        
        response = await claude_client.analyze_market_data(
            market_data=market_data,
            symbols=["BTC/USDT", "ETH/USDT"],
            analysis_type="technical"
        )
        
        print(f"✅ 市场分析成功: {response['success']}")
        if response['success']:
            print(f"📝 分析内容长度: {len(response['content'])} 字符")
            print(f"🔢 Token使用: {response['usage']['total_tokens']}")
            
            # 检查是否包含分析要素
            content = response['content'].lower()
            if any(keyword in content for keyword in ["趋势", "支撑", "阻力", "建议"]):
                print("✅ 包含技术分析要素")
        
        return response['success']
        
    except Exception as e:
        print(f"❌ 市场分析测试失败: {str(e)}")
        return False


async def test_ai_service():
    """测试AI服务功能"""
    print("\n🧪 测试4: AI服务集成")
    print("=" * 50)
    
    try:
        # 测试对话完成（不使用数据库）
        response = await AIService.chat_completion(
            message="请介绍一下量化交易的基本概念",
            user_id=1,
            context={"test_mode": True},
            session_id="test_session_001"
        )
        
        print(f"✅ AI服务对话成功: {response['success']}")
        print(f"📝 会话ID: {response['session_id']}")
        print(f"🔢 Token使用: {response['tokens_used']}")
        print(f"📄 响应内容: {response['content'][:150]}...")
        
        # 测试策略生成
        strategy_response = await AIService.generate_strategy(
            description="创建一个RSI指标策略",
            indicators=["RSI"],
            timeframe="4h",
            risk_level="low",
            user_id=1
        )
        
        print(f"✅ AI策略生成成功")
        print(f"📝 生成代码长度: {len(strategy_response['code'])} 字符")
        print(f"⚠️ 警告数量: {len(strategy_response['warnings'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ AI服务测试失败: {str(e)}")
        return False


async def test_usage_stats():
    """测试使用统计功能"""
    print("\n🧪 测试5: 使用统计功能")
    print("=" * 50)
    
    try:
        # 获取Claude客户端统计
        stats = claude_client.get_usage_stats()
        
        print(f"✅ 获取使用统计成功")
        print(f"📊 总请求数: {stats['total_requests']}")
        print(f"📈 成功率: {stats['success_rate']:.2%}")
        print(f"🔢 总Token数: {stats['total_tokens']}")
        print(f"💰 总成本: ${stats['total_cost_usd']:.6f}")
        print(f"⏱️ 平均响应时间: {stats['average_response_time_ms']:.2f}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ 使用统计测试失败: {str(e)}")
        return False


async def test_prompt_templates():
    """测试提示词模板"""
    print("\n🧪 测试6: 提示词模板")
    print("=" * 50)
    
    try:
        # 测试策略生成提示词
        strategy_prompts = TradingPrompts.format_strategy_prompt(
            description="测试策略",
            indicators=["MACD", "RSI"],
            timeframe="1d",
            risk_level="high"
        )
        
        print("✅ 策略提示词模板格式化成功")
        print(f"📝 系统提示词长度: {len(strategy_prompts['system'])} 字符")
        print(f"📝 用户提示词长度: {len(strategy_prompts['user'])} 字符")
        
        # 测试市场分析提示词
        analysis_prompts = TradingPrompts.format_analysis_prompt(
            analysis_type="technical",
            symbols=["BTC/USDT"],
            market_data="test market data",
            timeframe="1h"
        )
        
        print("✅ 分析提示词模板格式化成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 提示词模板测试失败: {str(e)}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始Claude AI功能集成测试")
    print("=" * 60)
    
    test_results = []
    
    # 执行各项测试
    tests = [
        ("Claude客户端基础功能", test_claude_client_basic),
        ("策略生成功能", test_strategy_generation),
        ("市场分析功能", test_market_analysis),
        ("AI服务集成", test_ai_service),
        ("使用统计功能", test_usage_stats),
        ("提示词模板", test_prompt_templates)
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}执行异常: {str(e)}")
            test_results.append((test_name, False))
    
    # 输出测试总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 总体结果: {passed}/{total} 测试通过 ({passed/total:.1%})")
    
    if passed == total:
        print("🎉 所有测试通过！Claude AI功能集成成功！")
    elif passed > 0:
        print("⚠️ 部分测试通过，请检查失败的功能")
    else:
        print("❌ 所有测试失败，请检查配置和连接")
    
    # 输出Claude客户端状态
    print(f"\n🤖 Claude客户端状态:")
    print(f"启用状态: {'✅ 已启用' if claude_client.enabled else '❌ 未启用 (模拟模式)'}")
    print(f"配置模型: {claude_client.model}")
    print(f"最大Token: {claude_client.max_tokens}")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())