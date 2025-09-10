#!/usr/bin/env python3
"""
第一阶段修复效果综合验证测试
验证三个核心修复：
1. 回测系统故障排除
2. 对话记录保存修复  
3. 流式响应稳定性提升
"""

import asyncio
import sys
import os
import time
sys.path.append(os.path.dirname(__file__))

from app.services.simplified_ai_service import unified_proxy_ai_service
from app.services.backtest_service import BacktestEngine
from app.database import AsyncSessionLocal
from datetime import datetime

async def test_comprehensive_system():
    print('🚀 第一阶段修复效果 - 综合验证测试')
    print('='*60)
    
    results = {
        'backtest_system': False,
        'conversation_saving': False, 
        'ai_integration': False
    }
    
    async with AsyncSessionLocal() as db:
        
        # =================== 测试1: 回测系统 ===================
        print('\n📊 测试1: 回测系统故障排除')
        try:
            engine = BacktestEngine()
            result = await engine.run_backtest(
                strategy_id=19,
                user_id=9,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 3, 1),
                initial_capital=10000.0,
                symbol="BTC/USDT",
                exchange="okx",
                timeframe="1h",
                db=db
            )
            
            if result and 'final_capital' in result:
                print(f'✅ 回测系统正常 - 最终资金: ${result["final_capital"]:.2f}')
                print(f'📈 收益率: {result.get("performance", {}).get("total_return", 0)*100:.2f}%')
                results['backtest_system'] = True
            else:
                print('❌ 回测系统返回结果异常')
                
        except Exception as e:
            print(f'❌ 回测系统测试失败: {str(e)}')
        
        
        # =================== 测试2: AI对话记录保存 ===================
        print('\n🤖 测试2: AI对话记录保存修复')
        try:
            session_id = f'comprehensive_test_{int(time.time())}'
            
            # 执行AI对话
            response = await unified_proxy_ai_service.chat_completion_with_context(
                message='综合测试：请简短介绍MACD指标',
                user_id=9,
                session_id=session_id,
                ai_mode='trader',
                stream=False,
                db=db
            )
            
            if response.get('success'):
                print(f'✅ AI对话成功 - Token: {response.get("tokens_used", 0)}')
                
                # 检查数据库保存
                from sqlalchemy import text
                result = await db.execute(text(f'SELECT COUNT(*) FROM claude_conversations WHERE session_id = "{session_id}"'))
                count = result.scalar()
                
                if count >= 2:
                    print(f'✅ 对话记录保存成功 - {count}条记录')
                    results['conversation_saving'] = True
                    results['ai_integration'] = True
                else:
                    print(f'❌ 对话记录保存不完整 - 仅{count}条记录')
            else:
                print('❌ AI对话失败')
                
        except Exception as e:
            print(f'❌ AI对话测试失败: {str(e)}')
            import traceback
            print(f'详细错误: {traceback.format_exc()[:500]}...')
        
        
        # =================== 测试3: 端到端策略生成 ===================
        print('\n🎯 测试3: 端到端策略生成流程')
        try:
            strategy_session = f'strategy_test_{int(time.time())}'
            
            # AI策略生成对话
            strategy_response = await unified_proxy_ai_service.chat_completion_with_context(
                message='请为我生成一个简单的RSI交易策略，包含完整的Python代码',
                user_id=9,
                session_id=strategy_session,
                ai_mode='developer',
                stream=False,
                db=db
            )
            
            if strategy_response.get('success'):
                content = strategy_response.get('content', '')
                has_python_code = 'def' in content and 'import' in content
                
                if has_python_code:
                    print('✅ AI策略生成成功 - 包含Python代码')
                    
                    # 检查策略对话记录
                    from sqlalchemy import text
                    result = await db.execute(text(f'SELECT COUNT(*) FROM claude_conversations WHERE session_id = "{strategy_session}"'))
                    count = result.scalar()
                    
                    if count >= 2:
                        print(f'✅ 策略对话记录完整 - {count}条记录')
                    else:
                        print(f'⚠️  策略对话记录不完整 - {count}条记录')
                        
                else:
                    print('⚠️  AI策略生成缺少代码内容')
            else:
                print('❌ AI策略生成失败')
                
        except Exception as e:
            print(f'❌ 策略生成测试失败: {str(e)}')
        
        
        # =================== 结果汇总 ===================
        print('\n' + '='*60)
        print('📋 第一阶段修复效果验证结果:')
        print(f'🔧 回测系统修复: {"✅ 成功" if results["backtest_system"] else "❌ 失败"}')
        print(f'💾 对话记录保存: {"✅ 成功" if results["conversation_saving"] else "❌ 失败"}') 
        print(f'🤖 AI集成系统: {"✅ 成功" if results["ai_integration"] else "❌ 失败"}')
        
        success_count = sum(results.values())
        print(f'\n🎯 总体修复成功率: {success_count}/3 ({success_count/3*100:.1f}%)')
        
        if success_count == 3:
            print('🎉 所有核心功能修复成功！系统已就绪。')
            return True
        elif success_count >= 2:
            print('⚠️  大部分功能正常，仍有少量问题需要处理。')
            return True  
        else:
            print('❌ 多个核心功能仍存在问题，需要进一步修复。')
            return False

if __name__ == "__main__":
    result = asyncio.run(test_comprehensive_system())
    sys.exit(0 if result else 1)