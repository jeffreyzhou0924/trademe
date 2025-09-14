#!/usr/bin/env python3
"""
测试上下文丢失修复效果的脚本

模拟用户描述MACD顶背离策略，然后确认生成代码，验证生成的策略是否包含用户需求的所有细节
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_

# 导入必要的服务和模型
from app.models.claude_conversation import ClaudeConversation
from app.services.ai_service import AIService
from app.services.strategy_requirements_extractor import StrategyRequirementsExtractor
from app.core.database import DATABASE_URL

# 创建异步数据库引擎
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def simulate_conversation():
    """模拟用户与AI的策略讨论对话"""
    
    print("=" * 80)
    print("测试上下文丢失修复效果")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        # 测试参数
        user_id = 1  # 测试用户ID
        session_id = f"test_context_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
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
        
        # 格式化需求提示
        formatted_prompt = StrategyRequirementsExtractor.format_requirements_prompt(requirements)
        print(f"\n📄 格式化的策略需求提示（前500字）：")
        print(formatted_prompt[:500] + "..." if len(formatted_prompt) > 500 else formatted_prompt)
        
        # 测试策略生成（不实际调用AI，只验证流程）
        print(f"\n🚀 测试策略生成流程...")
        
        # 验证修复效果
        print(f"\n✅ 修复验证结果：")
        
        # 检查是否包含关键需求
        checks = {
            "MACD指标提取": "MACD" in requirements.get('indicators', {}),
            "RSI指标提取": "RSI" in requirements.get('indicators', {}),
            "背离逻辑识别": any('divergence' in logic for logic in requirements.get('special_logic', [])),
            "止损参数提取": 'stop_loss' in requirements.get('risk_management', {}),
            "止盈参数提取": 'take_profit' in requirements.get('risk_management', {}),
            "时间框架识别": requirements.get('timeframe') == '1h',
            "交易对识别": requirements.get('trading_pair') == 'BTC/USDT'
        }
        
        all_passed = True
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {'通过' if passed else '失败'}")
            if not passed:
                all_passed = False
        
        print(f"\n{'🎉 所有测试通过！修复成功！' if all_passed else '⚠️ 部分测试失败，需要进一步调试'}")
        
        # 测试实际的策略生成调用（可选）
        test_actual_generation = False  # 设置为True以测试实际的策略生成
        
        if test_actual_generation:
            print(f"\n🔧 测试实际策略生成调用...")
            try:
                # 这里只是展示如何调用，不实际执行
                result = await AIService._generate_strategy_code_only(
                    user_input=user_message_2,
                    user_id=user_id,
                    user_membership="basic",
                    session_id=session_id,
                    conversation_history=conversation_history
                )
                
                if result.get('success'):
                    print(f"   ✅ 策略生成成功")
                    strategy_code = result.get('strategy_code', '')
                    
                    # 验证生成的代码是否包含关键元素
                    code_checks = {
                        "MACD实现": 'macd' in strategy_code.lower(),
                        "RSI实现": 'rsi' in strategy_code.lower(),
                        "背离检测": '背离' in strategy_code or 'divergence' in strategy_code.lower(),
                        "止损设置": '止损' in strategy_code or 'stop_loss' in strategy_code.lower(),
                        "止盈设置": '止盈' in strategy_code or 'take_profit' in strategy_code.lower()
                    }
                    
                    print(f"\n   生成代码验证：")
                    for check_name, found in code_checks.items():
                        status = "✅" if found else "❌"
                        print(f"      {status} {check_name}: {'找到' if found else '未找到'}")
                else:
                    print(f"   ❌ 策略生成失败: {result.get('error')}")
                    
            except Exception as e:
                print(f"   ❌ 测试出错: {e}")
        
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(simulate_conversation())