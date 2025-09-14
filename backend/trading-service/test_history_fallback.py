#!/usr/bin/env python3
"""
测试对话历史fallback机制
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.ai_service import AIService
from app.models.claude_conversation import ClaudeConversation
from sqlalchemy import select, and_, func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_history_fallback():
    """测试当session_id没有历史时的fallback机制"""
    
    async for db in get_db():
        user_id = 6
        # 使用一个不存在的session_id
        fake_session_id = "test-session-no-history"
        
        try:
            # 测试fallback查询逻辑
            conversation_history_for_strategy = []
            
            # 先尝试使用当前session_id获取对话历史
            if fake_session_id:
                history_query = select(ClaudeConversation).where(
                    and_(
                        ClaudeConversation.user_id == user_id,
                        ClaudeConversation.session_id == fake_session_id
                    )
                ).order_by(ClaudeConversation.created_at.asc()).limit(50)
                
                history_result = await db.execute(history_query)
                conversation_history_for_strategy = history_result.scalars().all()
                logger.info(f"使用fake session_id获取到 {len(conversation_history_for_strategy)} 条对话")
            
            # 如果当前session没有历史，尝试获取用户最近的有效对话
            if not conversation_history_for_strategy:
                logger.warning(f"⚠️ session_id {fake_session_id} 没有对话历史，尝试获取用户最近的策略对话")
                
                # 简化查询：获取用户最近的有效会话
                recent_session_subquery = (
                    select(ClaudeConversation.session_id, func.max(ClaudeConversation.created_at).label('last_activity'))
                    .where(ClaudeConversation.user_id == user_id)
                    .group_by(ClaudeConversation.session_id)
                    .having(func.count(ClaudeConversation.id) > 2)  # 至少有3条对话
                    .order_by(func.max(ClaudeConversation.created_at).desc())
                    .limit(1)
                    .subquery()
                )
                
                recent_session_result = await db.execute(select(recent_session_subquery.c.session_id))
                recent_session_id = recent_session_result.scalar()
                
                if recent_session_id:
                    logger.info(f"🔄 找到用户最近的有效会话: {recent_session_id}")
                    
                    # 获取该会话的对话历史
                    fallback_query = select(ClaudeConversation).where(
                        and_(
                            ClaudeConversation.user_id == user_id,
                            ClaudeConversation.session_id == recent_session_id
                        )
                    ).order_by(ClaudeConversation.created_at.asc()).limit(50)
                    
                    fallback_result = await db.execute(fallback_query)
                    conversation_history_for_strategy = fallback_result.scalars().all()
                    logger.info(f"✅ 从备用会话加载了{len(conversation_history_for_strategy)}条对话历史")
                    
                    # 打印一些对话内容确认是MACD相关
                    for i, msg in enumerate(conversation_history_for_strategy[:3]):
                        if msg.message_type == 'user':
                            logger.info(f"用户消息 {i+1}: {msg.content[:100]}...")
                else:
                    logger.error("没有找到任何有效的历史会话")
            
            return conversation_history_for_strategy
            
        except Exception as e:
            logger.error(f"测试失败: {e}")
            import traceback
            traceback.print_exc()
            return []

if __name__ == "__main__":
    result = asyncio.run(test_history_fallback())
    logger.info(f"最终获取到 {len(result)} 条对话历史")