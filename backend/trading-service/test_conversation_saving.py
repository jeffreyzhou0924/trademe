#!/usr/bin/env python3
"""
测试对话记录保存功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.services.simplified_ai_service import unified_proxy_ai_service
from app.database import AsyncSessionLocal

async def test_conversation_saving():
    print('🧪 测试AI对话记录保存功能...')
    
    async with AsyncSessionLocal() as db:
        try:
            # 测试对话
            response = await unified_proxy_ai_service.chat_completion_with_context(
                message='测试对话记录保存，请简短回复',
                user_id=9,
                session_id='test_session_001',
                ai_mode='developer',
                stream=False,
                db=db
            )
            
            print(f'✅ AI对话成功: {response.get("success", False)}')
            print(f'📝 响应内容: {response.get("content", "")[:100]}...')
            print(f'🔗 会话ID: {response.get("session_id", "")}')
            print(f'💰 Token使用: {response.get("tokens_used", 0)}')
            print(f'💵 成本: ${response.get("cost_usd", 0.0):.4f}')
            
            # 检查数据库中是否有对话记录
            from sqlalchemy import select, text
            result = await db.execute(text('SELECT COUNT(*) FROM claude_conversations WHERE session_id = "test_session_001"'))
            count = result.scalar()
            print(f'📊 数据库中的对话记录数: {count}')
            
            if count >= 2:  # 用户消息 + AI回复
                print('✅ 对话记录保存成功！')
                return True
            else:
                print('❌ 对话记录保存失败')
                return False
                
        except Exception as e:
            print(f'❌ 测试失败: {str(e)}')
            import traceback
            print(traceback.format_exc())
            return False

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(test_conversation_saving())
    print(f'\n📋 测试结果: {"成功" if result else "失败"}')
    sys.exit(0 if result else 1)