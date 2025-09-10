#!/usr/bin/env python3
"""
直接测试策略成熟度分析功能
"""

import sys
import os
import asyncio
sys.path.append('/root/trademe/backend/trading-service')

from app.services.strategy_maturity_analyzer import StrategyMaturityAnalyzer

async def test_macd_strategy_maturity():
    """测试MACD策略成熟度分析"""
    
    print("🧪 测试MACD策略成熟度分析系统")
    print("="*50)
    
    # 模拟对话历史
    conversation_history = [
        {"message_type": "user", "content": "我想开发一个MACD策略"},
        {"message_type": "assistant", "content": "MACD是一个很好的技术指标。你想如何使用MACD信号？"},
        {"message_type": "user", "content": """我想使用MACD指标来做交易策略。具体想法是：
        1. 当MACD线向上穿越信号线时买入
        2. 当MACD线向下穿越信号线时卖出  
        3. 设置止损为2%，止盈为5%
        4. 使用12日和26日EMA计算MACD
        5. 信号线使用9日EMA
        你觉得这个策略怎么样？需要优化哪些地方？"""},
        {"message_type": "assistant", "content": "这是一个经典的MACD交叉策略。你的参数设置很合理，12-26-9是标准参数。2%止损和5%止盈的风险收益比是1:2.5，比较合理。"}
    ]
    
    # 创建分析器
    analyzer = StrategyMaturityAnalyzer()
    
    # 分析成熟度
    print("🔍 分析对话成熟度...")
    current_message = conversation_history[-1]["content"]
    result = await StrategyMaturityAnalyzer.analyze_conversation_maturity(conversation_history[:-1], current_message)
    
    print("\n📊 分析结果:")
    print(f"   成熟度评分: {result.get('maturity_score', 0):.2f}")
    print(f"   是否成熟: {'✅ 是' if result.get('is_mature', False) else '❌ 否'}")
    print(f"   准备生成代码: {'✅ 是' if result.get('ready_for_generation', False) else '❌ 否'}")
    
    if result.get('missing_elements'):
        print(f"\n⚠️ 缺失要素:")
        for element in result['missing_elements']:
            print(f"   - {element}")
    
    if result.get('is_mature'):
        print(f"\n✅ 策略讨论已成熟，可生成确认提示")
        if result.get('confirmation_prompt'):
            print(f"\n💬 确认提示:")
            print(f"   {result['confirmation_prompt']}")
        return True
    else:
        print(f"\n❌ 策略讨论未成熟，需要更多讨论")
        return False

async def test_simple_strategy_maturity():
    """测试简单策略的成熟度分析"""
    
    print("\n\n🧪 测试简单策略对话成熟度")
    print("="*50)
    
    simple_conversation = [
        {"message_type": "user", "content": "我想开发一个移动平均策略"},
        {"message_type": "assistant", "content": "移动平均策略是量化交易中最基础的策略之一。你想用哪种类型的移动平均？"}
    ]
    
    current_message = simple_conversation[-1]["content"]
    result = await StrategyMaturityAnalyzer.analyze_conversation_maturity(simple_conversation[:-1], current_message)
    
    print(f"   成熟度评分: {result.get('maturity_score', 0):.2f}")
    print(f"   是否成熟: {'✅ 是' if result.get('is_mature', False) else '❌ 否'}")
    print(f"   这应该显示为不成熟，因为缺乏详细信息")
    
    return not result.get('is_mature', False)  # 应该返回True(不成熟)

async def main():
    """主测试函数"""
    
    print("🚀 开始策略成熟度分析直接测试")
    print("="*60)
    
    # 测试1: MACD详细策略
    macd_mature = await test_macd_strategy_maturity()
    
    # 测试2: 简单策略
    simple_immature = await test_simple_strategy_maturity()
    
    print("\n📊 测试结果总结:")
    print(f"   MACD详细策略成熟度测试: {'✅' if macd_mature else '❌'}")
    print(f"   简单策略不成熟测试: {'✅' if simple_immature else '❌'}")
    
    if macd_mature and simple_immature:
        print("\n🎉 策略成熟度分析系统工作正常！")
        print("✅ 系统能够正确区分成熟和不成熟的策略讨论")
        return True
    else:
        print("\n❌ 策略成熟度分析系统存在问题")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)