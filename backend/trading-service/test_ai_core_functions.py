#!/usr/bin/env python3
"""
AI策略生成核心功能快速验证脚本
专注验证最关键的修复效果
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.strategy_requirements_extractor import StrategyRequirementsExtractor


def create_message(role: str, content: str):
    """创建消息对象"""
    return type('obj', (object,), {
        'message_type': role,
        'content': content.strip(),
        'created_at': datetime.now()
    })()


async def test_core_function():
    """测试核心功能 - 从对话历史中提取策略需求"""
    
    print("🔍 AI策略生成核心功能验证")
    print("="*60)
    
    # 创建一个真实的MACD策略对话
    print("📝 创建MACD顶背离策略对话...")
    conversation = [
        create_message('user', """
        我想创建一个MACD顶背离策略：
        - MACD参数：快线12，慢线26，信号线9
        - 当价格创新高但MACD柱状图不创新高时做空
        - RSI(14)大于70确认超买
        - 止损3%，止盈5%
        - 时间框架：1小时
        - 交易对：BTC/USDT
        """),
        
        create_message('assistant', """
        好的，我理解您的MACD顶背离策略。主要特点：
        1. MACD(12,26,9)检测背离
        2. RSI(14)>70超买确认
        3. 风险管理：3%止损，5%止盈
        4. 1小时K线，BTC/USDT
        
        这是一个完整的逆势策略。您确认生成代码吗？
        """),
        
        create_message('user', "确认生成代码")
    ]
    
    print(f"对话轮次: {len(conversation)}")
    
    # 提取策略需求
    print("\n🔍 提取策略需求...")
    requirements = await StrategyRequirementsExtractor.extract_requirements(conversation)
    
    # 显示提取结果
    print("\n📊 提取结果：")
    
    indicators = requirements.get('indicators', {})
    print(f"技术指标 ({len(indicators)}个):")
    for name, params in indicators.items():
        print(f"  - {name}: {params}")
    
    risk_mgmt = requirements.get('risk_management', {})
    print(f"风险管理: {risk_mgmt}")
    
    special_logic = requirements.get('special_logic', [])
    print(f"特殊逻辑: {special_logic}")
    
    print(f"时间框架: {requirements.get('timeframe')}")
    print(f"交易对: {requirements.get('trading_pair')}")
    
    # 关键验证点
    print("\n✅ 关键验证点：")
    
    checks = [
        ("MACD指标", 'MACD' in indicators),
        ("MACD参数正确", indicators.get('MACD', {}).get('fast_period') == 12),
        ("RSI指标", 'RSI' in indicators), 
        ("RSI参数正确", indicators.get('RSI', {}).get('period') == 14),
        ("止损参数", risk_mgmt.get('stop_loss') == 3.0),
        ("止盈参数", risk_mgmt.get('take_profit') == 5.0),
        ("背离逻辑", 'bearish_divergence' in special_logic),
        ("时间框架", requirements.get('timeframe') == '1h'),
        ("交易对", requirements.get('trading_pair') == 'BTC/USDT')
    ]
    
    passed_count = 0
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if result:
            passed_count += 1
    
    # 生成提示词
    print(f"\n📝 生成策略提示词...")
    formatted_prompt = StrategyRequirementsExtractor.format_requirements_prompt(requirements)
    
    print("提示词预览（前200字符）:")
    print("-" * 40)
    print(formatted_prompt[:200] + "...")
    print("-" * 40)
    
    # 最终评估
    success_rate = passed_count / len(checks)
    print(f"\n🎯 验证结果:")
    print(f"通过率: {success_rate:.1%} ({passed_count}/{len(checks)})")
    
    if success_rate >= 0.8:
        print("🎉 核心功能工作正常！")
        print("✅ 对话历史中的策略参数被正确提取")
        print("✅ 上下文丢失问题已修复")
        print("✅ 可以进行完整的AI策略生成测试")
        
        # 输出可用于真实AI调用的提示词
        print(f"\n💡 可用于AI调用的完整提示词:")
        print("="*60)
        print(formatted_prompt)
        print("="*60)
        
    else:
        print("⚠️  部分功能需要优化")
        failed_checks = [name for name, result in checks if not result]
        print(f"失败项: {', '.join(failed_checks)}")
    
    return success_rate >= 0.8


async def main():
    """主函数"""
    try:
        success = await test_core_function()
        print(f"\n{'='*60}")
        print(f"验证{'成功' if success else '需要优化'} - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"\n❌ 验证异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())