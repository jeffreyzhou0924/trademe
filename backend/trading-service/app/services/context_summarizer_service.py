"""
智能上下文摘要服务
- 当对话历史过长时自动压缩重要信息
- 保留关键决策、参数设置、用户偏好
- 支持多轮摘要压缩
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from loguru import logger

from app.models.claude_conversation import ClaudeConversation
# 延迟导入避免循环导入


class ContextSummarizerService:
    """上下文摘要服务"""
    
    def __init__(self):
        self.ai_service = None  # 延迟初始化
        self.max_context_length = 20  # 超过20条消息开始摘要
        self.summary_compression_ratio = 0.6  # 压缩为60%的内容
        
    async def should_summarize_context(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> bool:
        """判断是否需要进行上下文摘要"""
        try:
            # 统计该会话的消息数量
            query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type != 'summary'  # 排除已有摘要
                )
            )
            
            result = await db.execute(query)
            messages = result.scalars().all()
            
            return len(messages) >= self.max_context_length
            
        except Exception as e:
            logger.error(f"检查摘要需求失败: {e}")
            return False
    
    async def generate_context_summary(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> Optional[str]:
        """生成智能上下文摘要"""
        try:
            # 获取需要摘要的消息（除最近5条）
            query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type != 'summary'
                )
            ).order_by(ClaudeConversation.created_at.asc())
            
            result = await db.execute(query)
            all_messages = result.scalars().all()
            
            if len(all_messages) < self.max_context_length:
                return None
                
            # 保留最近5条，摘要其余内容
            messages_to_summarize = all_messages[:-5]
            recent_messages = all_messages[-5:]
            
            # 构建摘要请求
            conversation_text = self._build_conversation_text(messages_to_summarize)
            summary_prompt = self._build_summary_prompt(conversation_text, session_id)
            
            # 调用AI生成摘要
            summary_response = await self.ai_service.chat_completion(
                message=summary_prompt,
                user_id=user_id,
                session_id=f"{session_id}_summary",
                ai_mode="developer",
                stream=False,
                max_tokens=800,
                temperature=0.3  # 降低温度保证摘要准确性
            )
            
            if not summary_response.get("success", True):
                logger.warning(f"摘要生成失败: {summary_response.get('error')}")
                return None
                
            summary_content = summary_response.get("content", "")
            
            # 保存摘要到数据库
            await self._save_summary_and_cleanup(
                db, user_id, session_id, summary_content, messages_to_summarize
            )
            
            logger.info(f"成功生成上下文摘要 - 会话: {session_id}, 压缩: {len(messages_to_summarize)} -> 1条摘要")
            
            return summary_content
            
        except Exception as e:
            logger.error(f"生成上下文摘要失败: {e}")
            return None
    
    def _build_conversation_text(self, messages: List[ClaudeConversation]) -> str:
        """构建对话文本用于摘要"""
        conversation_parts = []
        
        for msg in messages:
            role = "用户" if msg.message_type == "user" else "助手"
            timestamp = msg.created_at.strftime("%H:%M")
            conversation_parts.append(f"[{timestamp}] {role}: {msg.content}")
            
        return "\n".join(conversation_parts)
    
    def _build_summary_prompt(self, conversation_text: str, session_id: str) -> str:
        """构建摘要生成提示"""
        return f"""请为以下交易策略对话生成一份智能摘要。重点保留：

1. **用户偏好与需求**
   - 交易风格偏好
   - 风险承受能力
   - 预期收益目标

2. **关键技术决策**
   - 选用的技术指标
   - 重要参数设置
   - 策略逻辑要点

3. **重要讨论结论**
   - 达成的共识
   - 确定的方向
   - 待解决问题

4. **上下文信息**
   - 市场环境假设
   - 数据源要求
   - 回测期间设置

**对话内容：**
```
{conversation_text}
```

**摘要要求：**
- 以结构化方式组织信息
- 保留关键数字参数
- 突出重要决策点
- 简洁但不丢失关键信息
- 为后续对话提供有效上下文

请生成摘要："""

    async def _save_summary_and_cleanup(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        summary_content: str,
        old_messages: List[ClaudeConversation]
    ):
        """保存摘要并清理旧消息"""
        try:
            # 创建摘要消息
            summary_message = ClaudeConversation(
                user_id=user_id,
                session_id=session_id,
                message_type="summary",
                content=summary_content,
                context=json.dumps({
                    "summary_type": "context_compression",
                    "original_message_count": len(old_messages),
                    "compression_ratio": self.summary_compression_ratio,
                    "created_at": datetime.utcnow().isoformat()
                }),
                tokens_used=0,  # 摘要不计入token消耗
                model="claude-sonnet-4-20250514",
                success=True
            )
            
            db.add(summary_message)
            
            # 标记旧消息为已摘要（软删除）
            old_message_ids = [msg.id for msg in old_messages]
            if old_message_ids:
                await db.execute(
                    update(ClaudeConversation)
                    .where(ClaudeConversation.id.in_(old_message_ids))
                    .values(
                        message_type="archived",
                        context=json.dumps({
                            "archived_reason": "context_summarized",
                            "summary_created_at": datetime.utcnow().isoformat()
                        })
                    )
                )
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"保存摘要失败: {e}")
            await db.rollback()
            raise
    
    async def get_context_with_summary(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        limit: int = 15
    ) -> List[ClaudeConversation]:
        """获取包含摘要的上下文历史"""
        try:
            # 获取摘要消息
            summary_query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type == "summary"
                )
            ).order_by(ClaudeConversation.created_at.desc()).limit(1)
            
            summary_result = await db.execute(summary_query)
            summary_message = summary_result.scalar_one_or_none()
            
            # 获取最近的活跃消息
            recent_query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type.in_(["user", "assistant"])
                )
            ).order_by(ClaudeConversation.created_at.desc()).limit(limit)
            
            recent_result = await db.execute(recent_query)
            recent_messages = recent_result.scalars().all()
            
            # 组合结果：摘要 + 最近消息
            context_messages = []
            if summary_message:
                context_messages.append(summary_message)
                
            # 按时间顺序添加最近消息
            context_messages.extend(reversed(recent_messages))
            
            return context_messages
            
        except Exception as e:
            logger.error(f"获取带摘要的上下文失败: {e}")
            return []

    async def maintain_context_health(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ):
        """维护上下文健康度 - 定期检查并摘要"""
        try:
            if await self.should_summarize_context(db, user_id, session_id):
                await self.generate_context_summary(db, user_id, session_id)
                logger.info(f"会话 {session_id} 上下文维护完成")
                
        except Exception as e:
            logger.error(f"上下文健康维护失败: {e}")


# 暂时禁用全局实例以避免循环导入
context_summarizer = None