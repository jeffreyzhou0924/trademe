#!/usr/bin/env python3
"""
测试策略需求提取器的效果
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.strategy_requirements_extractor import StrategyRequirementsExtractor


async def test_requirements_extraction():
    """测试策略需求提取功能"""
    
    print("=" * 80)
    print("测试策略需求提取器")
    print("=" * 80)
    
    # 模拟对话历史
    conversation_history = []
    
    # 用户描述MACD顶背离策略
    user_message_1 = """
    我想创建一个MACD顶背离策略，具体要求如下：
    1. 使用MACD指标，参数为12,26,9
    2. 检测顶背离：当价格创新高但MACD柱状图不创新高时
    3. 入场条件：出现顶背离信号，且RSI(14)大于70表示超买
    4. 出场条件：止损3%，止盈5%，或者MACD金叉时平仓
    5. 时间框架：1小时
    6. 交易对：BTC/USDT
    """
    
    # 创建模拟的对话历史记录
    msg1 = type('obj', (object,), {
        'message_type': 'user',
        'content': user_message_1,
        'created_at': datetime.now()
    })()
    conversation_history.append(msg1)
    
    # AI的回复（模拟）
    ai_response_1 = """
    好的，我理解您的需求。您想创建一个基于MACD顶背离的策略，主要特点包括：

    1. **MACD顶背离检测**：使用MACD(12,26,9)参数，当价格创新高但MACD柱状图不创新高时识别顶背离
    2. **超买确认**：配合RSI(14)>70确认超买状态
    3. **风险管理**：3%止损，5%止盈
    4. **备选出场**：MACD金叉时也可以平仓
    
    这是一个经典的逆势交易策略，利用技术指标背离来捕捉潜在的趋势反转点。
    
    策略已经比较成熟，包含了完整的入场条件、出场条件和风险管理。
    
    您是否确认生成这个策略的代码？
    """
    
    msg2 = type('obj', (object,), {
        'message_type': 'assistant', 
        'content': ai_response_1,
        'created_at': datetime.now()
    })()
    conversation_history.append(msg2)
    
    # 用户确认
    user_message_2 = "确认生成代码"
    msg3 = type('obj', (object,), {
        'message_type': 'user',
        'content': user_message_2,
        'created_at': datetime.now()
    })()
    conversation_history.append(msg3)
    
    print(f"\n📝 模拟对话历史：")
    print(f"   - 用户描述了MACD顶背离策略的详细需求")
    print(f"   - AI分析并确认了策略要点")
    print(f"   - 用户确认生成代码")
    print(f"   - 对话历史共{len(conversation_history)}条消息")
    
    # 测试策略需求提取器
    print(f"\n🔍 测试策略需求提取器...")
    requirements = await StrategyRequirementsExtractor.extract_requirements(conversation_history)
    
    print(f"\n📋 提取的策略需求：")
    print(f"   - 指标: {list(requirements.get('indicators', {}).keys())}")
    print(f"   - 入场条件数: {len(requirements.get('entry_conditions', []))}")
    print(f"   - 出场条件数: {len(requirements.get('exit_conditions', []))}")
    print(f"   - 特殊逻辑: {requirements.get('special_logic', [])}")
    print(f"   - 风险管理: {requirements.get('risk_management', {})}")
    print(f"   - 时间框架: {requirements.get('timeframe')}")
    print(f"   - 交易对: {requirements.get('trading_pair')}")
    
    # 详细打印提取的内容
    print(f"\n📄 详细提取结果：")
    
    if requirements.get('indicators'):
        print(f"\n   📊 技术指标详情：")
        for indicator, params in requirements['indicators'].items():
            print(f"      - {indicator}: {params}")
    
    if requirements.get('entry_conditions'):
        print(f"\n   📈 入场条件：")
        for i, condition in enumerate(requirements['entry_conditions'], 1):
            print(f"      {i}. {condition[:100]}...")
    
    if requirements.get('exit_conditions'):
        print(f"\n   📉 出场条件：")
        for i, condition in enumerate(requirements['exit_conditions'], 1):
            print(f"      {i}. {condition[:100]}...")
    
    # 格式化需求提示
    formatted_prompt = StrategyRequirementsExtractor.format_requirements_prompt(requirements)
    print(f"\n📝 格式化的策略生成提示：")
    print("-" * 60)
    print(formatted_prompt)
    print("-" * 60)
    
    # 验证修复效果
    print(f"\n✅ 验证结果：")
    
    # 检查是否包含关键需求
    checks = {
        "MACD指标提取": "MACD" in requirements.get('indicators', {}),
        "RSI指标提取": "RSI" in requirements.get('indicators', {}),
        "MACD参数识别": requirements.get('indicators', {}).get('MACD', {}).get('fast_period') == 12,
        "RSI参数识别": requirements.get('indicators', {}).get('RSI', {}).get('period') == 14,
        "背离逻辑识别": any('divergence' in logic for logic in requirements.get('special_logic', [])),
        "止损参数提取": requirements.get('risk_management', {}).get('stop_loss') == 3.0,
        "止盈参数提取": requirements.get('risk_management', {}).get('take_profit') == 5.0,
        "时间框架识别": requirements.get('timeframe') == '1h',
        "交易对识别": requirements.get('trading_pair') == 'BTC/USDT',
        "金叉逻辑识别": 'golden_cross' in requirements.get('special_logic', [])
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}: {'通过' if passed else '失败'}")
        if not passed:
            all_passed = False
    
    print(f"\n{'🎉 所有测试通过！需求提取器工作正常！' if all_passed else '⚠️ 部分测试失败，需要优化提取逻辑'}")
    
    # 测试边界情况
    print(f"\n🔧 测试边界情况...")
    
    # 测试只有确认消息的情况
    simple_history = [
        type('obj', (object,), {
            'message_type': 'user',
            'content': '确认生成代码',
            'created_at': datetime.now()
        })()
    ]
    
    simple_requirements = await StrategyRequirementsExtractor.extract_requirements(simple_history)
    print(f"   - 仅确认消息: 提取指标数={len(simple_requirements.get('indicators', {}))}, 预期=0")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_requirements_extraction())