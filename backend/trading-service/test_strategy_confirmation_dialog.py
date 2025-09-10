"""
策略确认对话管理器测试脚本
测试不同成熟度下的确认提示生成和用户响应解析
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.strategy_maturity_analyzer import StrategyMaturityAnalyzer
from app.services.strategy_confirmation_dialog import StrategyConfirmationDialog


async def test_confirmation_generation():
    """测试确认提示生成"""
    
    analyzer = StrategyMaturityAnalyzer()
    dialog = StrategyConfirmationDialog()
    
    print("🧪 策略确认对话管理器测试开始")
    print("=" * 80)
    
    # 测试用例：不同成熟度的策略
    test_cases = [
        # 低成熟度 - 应该生成讨论引导
        {
            "name": "初步想法 (预期: 讨论引导)",
            "conversation": [
                {"role": "user", "content": "我想做个交易策略赚钱"}
            ]
        },
        
        # 中等成熟度 - 应该生成改进建议
        {
            "name": "基础框架 (预期: 改进建议)",
            "conversation": [
                {"role": "user", "content": "用RSI指标做反转策略"},
                {"role": "user", "content": "RSI超买卖出，超卖买入"},
                {"role": "user", "content": "用1小时周期"}
            ]
        },
        
        # 高成熟度 - 应该询问用户确认
        {
            "name": "成熟策略 (预期: 用户确认)",
            "conversation": [
                {"role": "user", "content": "双均线交叉策略"},
                {"role": "user", "content": "10日均线上穿20日均线买入，下穿卖出"},
                {"role": "user", "content": "止损2%，止盈3%，1小时图"}
            ]
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📊 测试用例 {i}: {test_case['name']}")
        print("-" * 60)
        
        # 先分析策略成熟度
        conversation = test_case["conversation"]
        current_message = conversation[-1]["content"]
        history = conversation[:-1]
        
        maturity_result = await analyzer.analyze_strategy_maturity(history, current_message)
        
        print(f"📈 成熟度分数: {maturity_result['total_score']:.1f}/100")
        print(f"🎯 成熟度等级: {maturity_result['maturity_level']}")
        
        # 生成确认提示
        confirmation_result = await dialog.generate_confirmation_prompt(
            maturity_result, user_id=1, session_id=f"test_session_{i}"
        )
        
        print(f"🔄 确认类型: {confirmation_result['confirmation_type']}")
        print(f"⚡ 需要用户操作: {confirmation_result['requires_user_action']}")
        
        print(f"\n💬 生成的确认消息:")
        print("─" * 40)
        # 显示消息的前200个字符
        message = confirmation_result['message']
        preview = message[:200] + "..." if len(message) > 200 else message
        print(preview)
        
        print("\n" + "=" * 80)
    
    print("\n✅ 确认提示生成测试完成！")


async def test_user_response_parsing():
    """测试用户响应解析"""
    
    dialog = StrategyConfirmationDialog()
    
    print("\n🔍 用户响应解析测试:")
    print("-" * 60)
    
    # 测试不同的用户响应
    test_responses = [
        # 明确确认
        "确认生成",
        "好的，开始生成代码",
        "可以，我同意",
        "OK，开始吧",
        
        # 继续讨论  
        "继续讨论一下",
        "我想再完善一下参数",
        "先不生成，再聊聊",
        "等等，我还有疑问",
        
        # 模糊响应
        "我觉得还行",
        "这个策略用MACD指标会更好",
        "不太确定",
        "嗯..."
    ]
    
    for response in test_responses:
        parse_result = await dialog.parse_user_confirmation(response)
        
        intent = parse_result['intent']
        confidence = parse_result['confidence']
        action = parse_result['action']
        
        # 格式化显示
        intent_icon = {
            "confirm_generation": "✅",
            "continue_discussion": "💭", 
            "unclear": "❓",
            "error": "❌"
        }.get(intent, "⚪")
        
        print(f"{intent_icon} \"{response}\" → {intent} (置信度: {confidence:.1f}) → {action}")
    
    print("\n✅ 用户响应解析测试完成！")


async def test_integration_flow():
    """测试完整的集成流程"""
    
    analyzer = StrategyMaturityAnalyzer()
    dialog = StrategyConfirmationDialog()
    
    print("\n🔄 完整集成流程测试:")
    print("-" * 60)
    
    # 模拟一个完整的对话流程
    conversation_history = [
        {"role": "user", "content": "我想做个MACD策略"},
        {"role": "assistant", "content": "好的，请告诉我更多细节"},
        {"role": "user", "content": "MACD金叉买入，死叉卖出"},
        {"role": "assistant", "content": "不错，还有其他条件吗？"},
        {"role": "user", "content": "设置2%止损，3%止盈，用15分钟图"},
    ]
    
    current_message = "加上RSI确认，避免假信号"
    history = conversation_history[:-1]
    
    print("📊 当前对话状态:")
    for msg in conversation_history[-3:]:
        role_icon = "🧑" if msg["role"] == "user" else "🤖"
        print(f"  {role_icon} {msg['content'][:50]}...")
    print(f"  🧑 {current_message}")
    
    # 1. 分析策略成熟度
    print(f"\n🔍 分析策略成熟度...")
    maturity_result = await analyzer.analyze_strategy_maturity(history, current_message)
    print(f"  成熟度: {maturity_result['total_score']:.1f}/100 ({maturity_result['maturity_level']})")
    
    # 2. 生成确认提示
    print(f"\n💭 生成确认提示...")
    confirmation_result = await dialog.generate_confirmation_prompt(
        maturity_result, user_id=1, session_id="integration_test"
    )
    print(f"  确认类型: {confirmation_result['confirmation_type']}")
    print(f"  需要用户操作: {confirmation_result['requires_user_action']}")
    
    # 3. 模拟用户响应
    simulated_responses = ["确认生成", "继续完善一下", "不太确定"]
    
    for user_response in simulated_responses:
        print(f"\n🧑 用户响应: \"{user_response}\"")
        
        parse_result = await dialog.parse_user_confirmation(user_response)
        print(f"  解析结果: {parse_result['intent']} (置信度: {parse_result['confidence']:.1f})")
        print(f"  建议操作: {parse_result['action']}")
        
        if parse_result['intent'] == 'unclear':
            clarification = dialog.generate_clarification_request()
            print(f"  🤖 澄清请求: {clarification[:50]}...")
    
    print("\n✅ 完整集成流程测试完成！")


if __name__ == "__main__":
    asyncio.run(test_confirmation_generation())
    asyncio.run(test_user_response_parsing()) 
    asyncio.run(test_integration_flow())