"""
会话恢复机制服务
- 智能会话状态检测与恢复
- 中断会话的无缝续接
- 会话上下文完整性保证
- 多设备会话同步支持
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, update
from loguru import logger

from app.models.claude_conversation import ClaudeConversation, AIChatSession
from app.services.dynamic_context_manager import dynamic_context_manager
from app.services.context_summarizer_service import context_summarizer


class SessionRecoveryService:
    """会话恢复服务"""
    
    def __init__(self):
        # 恢复配置
        self.max_recovery_attempts = 3  # 最大恢复尝试次数
        self.session_timeout = 24 * 60 * 60  # 会话超时时间(秒) - 24小时
        self.recovery_window = 7 * 24 * 60 * 60  # 可恢复窗口(秒) - 7天
        
        # 会话状态定义
        self.valid_states = ["active", "paused", "interrupted", "completed", "archived"]
        self.recoverable_states = ["paused", "interrupted"]
        
        # 恢复优先级
        self.recovery_priorities = {
            "strategy_generation": 1,  # 策略生成会话最高优先级
            "indicator_development": 2, # 指标开发会话
            "debugging": 3,            # 调试会话  
            "general_chat": 4          # 一般对话会话
        }
    
    async def detect_interrupted_sessions(
        self,
        db: AsyncSession,
        user_id: int,
        check_hours: int = 2
    ) -> List[Dict[str, Any]]:
        """检测中断的会话"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=check_hours)
            
            # 查询可能中断的会话
            query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.status == "active",
                    AIChatSession.last_activity_at < cutoff_time
                )
            ).order_by(desc(AIChatSession.last_activity_at))
            
            result = await db.execute(query)
            potential_interruptions = result.scalars().all()
            
            interrupted_sessions = []
            for session in potential_interruptions:
                # 检查是否确实中断
                interruption_analysis = await self._analyze_session_interruption(
                    db, user_id, session.session_id
                )
                
                if interruption_analysis["is_interrupted"]:
                    session_info = {
                        "session_id": session.session_id,
                        "name": session.name,
                        "session_type": session.session_type,
                        "ai_mode": session.ai_mode,
                        "last_activity": session.last_activity_at.isoformat(),
                        "message_count": session.message_count,
                        "interruption_reason": interruption_analysis["reason"],
                        "recovery_priority": self._calculate_recovery_priority(session),
                        "recovery_feasibility": await self._assess_recovery_feasibility(
                            db, user_id, session.session_id
                        ),
                        "last_message_preview": session.last_message_content[:100] if session.last_message_content else ""
                    }
                    interrupted_sessions.append(session_info)
            
            logger.info(f"检测到 {len(interrupted_sessions)} 个中断会话 - 用户:{user_id}")
            return interrupted_sessions
            
        except Exception as e:
            logger.error(f"检测中断会话失败: {e}")
            return []
    
    async def _analyze_session_interruption(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """分析会话是否真正中断"""
        try:
            # 获取最近的对话记录
            recent_messages_query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type.in_(["user", "assistant"])
                )
            ).order_by(desc(ClaudeConversation.created_at)).limit(5)
            
            result = await db.execute(recent_messages_query)
            recent_messages = result.scalars().all()
            
            if not recent_messages:
                return {"is_interrupted": False, "reason": "no_messages"}
            
            last_message = recent_messages[0]
            hours_since_last = (datetime.utcnow() - last_message.created_at).total_seconds() / 3600
            
            # 分析中断原因
            interruption_indicators = []
            
            # 检查是否有未完成的用户请求
            if last_message.message_type == "user":
                interruption_indicators.append("pending_user_request")
            
            # 检查是否有错误消息
            if not last_message.success:
                interruption_indicators.append("error_occurred")
            
            # 检查会话类型和预期持续时间
            if hours_since_last > 2:  # 超过2小时未活动
                interruption_indicators.append("extended_inactivity")
            
            # 检查是否在策略生成过程中中断
            strategy_keywords = ["策略", "代码", "回测", "生成", "开发"]
            if any(keyword in last_message.content for keyword in strategy_keywords):
                if last_message.message_type == "user":
                    interruption_indicators.append("strategy_generation_interrupted")
            
            # 判断是否中断
            is_interrupted = len(interruption_indicators) > 0
            reason = ", ".join(interruption_indicators) if interruption_indicators else "normal_pause"
            
            return {
                "is_interrupted": is_interrupted,
                "reason": reason,
                "hours_since_last": hours_since_last,
                "indicators": interruption_indicators,
                "last_message_type": last_message.message_type,
                "last_message_success": last_message.success
            }
            
        except Exception as e:
            logger.error(f"分析会话中断失败: {e}")
            return {"is_interrupted": False, "reason": "analysis_error"}
    
    def _calculate_recovery_priority(self, session: AIChatSession) -> int:
        """计算会话恢复优先级"""
        base_priority = self.recovery_priorities.get(session.session_type, 5)
        
        # 根据消息数量调整优先级 (消息越多优先级越高)
        message_factor = min(session.message_count / 20, 1.0)  # 20条消息为满分
        
        # 根据会话进度调整优先级
        progress_factor = session.progress / 100.0 if session.progress else 0.0
        
        # 综合计算优先级分数 (越低优先级越高)
        priority_score = base_priority * (1 - message_factor * 0.3 - progress_factor * 0.2)
        
        return max(1, int(priority_score))
    
    async def _assess_recovery_feasibility(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """评估会话恢复可行性"""
        try:
            # 获取会话的所有消息
            all_messages_query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id
                )
            ).order_by(ClaudeConversation.created_at.asc())
            
            result = await db.execute(all_messages_query)
            all_messages = result.scalars().all()
            
            if not all_messages:
                return {
                    "feasibility": "impossible",
                    "score": 0.0,
                    "reasons": ["no_message_history"]
                }
            
            feasibility_factors = {
                "message_integrity": 0.0,
                "context_completeness": 0.0, 
                "session_coherence": 0.0,
                "technical_continuity": 0.0
            }
            
            # 评估消息完整性
            successful_messages = sum(1 for msg in all_messages if msg.success)
            message_integrity = successful_messages / len(all_messages) if all_messages else 0
            feasibility_factors["message_integrity"] = message_integrity
            
            # 评估上下文完整性
            user_messages = [msg for msg in all_messages if msg.message_type == "user"]
            assistant_messages = [msg for msg in all_messages if msg.message_type == "assistant"]
            
            # 理想情况下，用户消息和AI回复应该接近1:1比例
            message_balance = min(len(user_messages), len(assistant_messages)) / max(len(user_messages), len(assistant_messages), 1)
            feasibility_factors["context_completeness"] = message_balance
            
            # 评估会话连贯性 (检查消息间的时间间隔)
            time_gaps = []
            for i in range(1, len(all_messages)):
                gap = (all_messages[i].created_at - all_messages[i-1].created_at).total_seconds() / 60  # 分钟
                time_gaps.append(gap)
            
            if time_gaps:
                avg_gap = sum(time_gaps) / len(time_gaps)
                coherence_score = max(0, 1 - (avg_gap / 120))  # 2小时为临界值
                feasibility_factors["session_coherence"] = coherence_score
            
            # 评估技术连续性 (检查是否有代码生成、策略开发等)
            technical_keywords = ["def ", "class ", "import ", "策略", "代码", "函数"]
            technical_messages = sum(1 for msg in all_messages if any(kw in msg.content for kw in technical_keywords))
            technical_continuity = min(technical_messages / max(len(all_messages), 1), 1.0)
            feasibility_factors["technical_continuity"] = technical_continuity
            
            # 计算综合可行性分数
            overall_score = sum(feasibility_factors.values()) / len(feasibility_factors)
            
            # 确定可行性等级
            if overall_score >= 0.8:
                feasibility = "excellent"
            elif overall_score >= 0.6:
                feasibility = "good"
            elif overall_score >= 0.4:
                feasibility = "fair"
            elif overall_score >= 0.2:
                feasibility = "poor"
            else:
                feasibility = "impossible"
            
            return {
                "feasibility": feasibility,
                "score": round(overall_score, 3),
                "factors": feasibility_factors,
                "message_count": len(all_messages),
                "reasons": self._generate_feasibility_reasons(feasibility_factors, overall_score)
            }
            
        except Exception as e:
            logger.error(f"评估恢复可行性失败: {e}")
            return {
                "feasibility": "unknown",
                "score": 0.0,
                "reasons": ["assessment_error"]
            }
    
    def _generate_feasibility_reasons(self, factors: Dict[str, float], overall_score: float) -> List[str]:
        """生成可行性评估原因"""
        reasons = []
        
        if factors["message_integrity"] < 0.5:
            reasons.append("消息完整性不足")
        elif factors["message_integrity"] > 0.9:
            reasons.append("消息记录完整")
        
        if factors["context_completeness"] < 0.5:
            reasons.append("对话上下文不完整")
        elif factors["context_completeness"] > 0.8:
            reasons.append("对话上下文良好")
        
        if factors["session_coherence"] < 0.3:
            reasons.append("会话连贯性差")
        elif factors["session_coherence"] > 0.7:
            reasons.append("会话连贯性好")
        
        if factors["technical_continuity"] > 0.5:
            reasons.append("包含技术内容，恢复价值高")
        
        if overall_score > 0.8:
            reasons.append("总体恢复条件优秀")
        elif overall_score < 0.3:
            reasons.append("恢复条件不佳")
        
        return reasons if reasons else ["标准恢复条件"]
    
    async def recover_session(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        recovery_strategy: str = "auto"
    ) -> Dict[str, Any]:
        """恢复中断的会话"""
        try:
            # 检查会话是否存在
            session_query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.session_id == session_id
                )
            )
            result = await db.execute(session_query)
            session = result.scalar_one_or_none()
            
            if not session:
                return {
                    "success": False,
                    "error": "会话不存在",
                    "session_id": session_id
                }
            
            # 评估恢复可行性
            feasibility = await self._assess_recovery_feasibility(db, user_id, session_id)
            if feasibility["feasibility"] == "impossible":
                return {
                    "success": False,
                    "error": "会话无法恢复",
                    "reasons": feasibility["reasons"],
                    "session_id": session_id
                }
            
            # 执行恢复流程
            recovery_result = await self._execute_recovery(
                db, user_id, session_id, session, recovery_strategy
            )
            
            if recovery_result["success"]:
                # 更新会话状态
                await db.execute(
                    update(AIChatSession)
                    .where(AIChatSession.session_id == session_id)
                    .values(
                        status="active",
                        last_activity_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
                await db.commit()
                
                logger.info(f"会话恢复成功 - 用户:{user_id}, 会话:{session_id}")
            
            return recovery_result
            
        except Exception as e:
            logger.error(f"恢复会话失败: {e}")
            return {
                "success": False,
                "error": f"恢复过程异常: {str(e)}",
                "session_id": session_id
            }
    
    async def _execute_recovery(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        session: AIChatSession,
        recovery_strategy: str
    ) -> Dict[str, Any]:
        """执行会话恢复"""
        try:
            recovery_data = {
                "session_id": session_id,
                "session_name": session.name,
                "recovery_strategy": recovery_strategy,
                "recovery_timestamp": datetime.utcnow().isoformat()
            }
            
            # 根据恢复策略执行不同的恢复逻辑
            if recovery_strategy == "auto":
                return await self._auto_recovery(db, user_id, session_id, session, recovery_data)
            elif recovery_strategy == "context_rebuild":
                return await self._context_rebuild_recovery(db, user_id, session_id, session, recovery_data)
            elif recovery_strategy == "summary_based":
                return await self._summary_based_recovery(db, user_id, session_id, session, recovery_data)
            else:
                return await self._basic_recovery(db, user_id, session_id, session, recovery_data)
                
        except Exception as e:
            logger.error(f"执行恢复失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _auto_recovery(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        session: AIChatSession,
        recovery_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """自动智能恢复"""
        try:
            # 获取优化的上下文
            context_messages = await dynamic_context_manager.get_optimized_context(
                db, user_id, session_id, include_summary=True
            )
            
            # 检查是否需要生成恢复摘要
            if len(context_messages) > 15:
                # 生成会话恢复摘要
                recovery_summary = await self._generate_recovery_summary(
                    db, user_id, session_id, context_messages
                )
            else:
                recovery_summary = None
            
            # 构建恢复问候语
            recovery_greeting = await self._generate_recovery_greeting(
                session, context_messages, recovery_summary
            )
            
            # 保存恢复记录
            recovery_message = ClaudeConversation(
                user_id=user_id,
                session_id=session_id,
                message_type="system",
                content=recovery_greeting,
                context=json.dumps({
                    "recovery_type": "auto",
                    "context_messages": len(context_messages),
                    "has_summary": recovery_summary is not None,
                    **recovery_data
                }),
                tokens_used=0,
                model="session-recovery-system",
                success=True
            )
            db.add(recovery_message)
            
            await db.commit()
            
            return {
                "success": True,
                "recovery_type": "auto",
                "context_restored": len(context_messages),
                "recovery_greeting": recovery_greeting,
                "has_summary": recovery_summary is not None,
                "session_info": {
                    "name": session.name,
                    "type": session.session_type,
                    "ai_mode": session.ai_mode,
                    "progress": session.progress
                }
            }
            
        except Exception as e:
            logger.error(f"自动恢复失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _context_rebuild_recovery(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        session: AIChatSession,
        recovery_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """上下文重建恢复"""
        try:
            # 获取所有历史消息
            all_messages_query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type.in_(["user", "assistant"])
                )
            ).order_by(ClaudeConversation.created_at.asc())
            
            result = await db.execute(all_messages_query)
            all_messages = result.scalars().all()
            
            # 重建上下文结构
            rebuilt_context = {
                "total_messages": len(all_messages),
                "conversation_timeline": [],
                "key_topics": [],
                "decision_points": [],
                "technical_content": []
            }
            
            # 分析消息内容
            for i, msg in enumerate(all_messages):
                message_info = {
                    "index": i,
                    "type": msg.message_type,
                    "timestamp": msg.created_at.isoformat(),
                    "content_preview": msg.content[:100],
                    "success": msg.success
                }
                rebuilt_context["conversation_timeline"].append(message_info)
                
                # 识别关键主题
                if any(keyword in msg.content.lower() for keyword in ["策略", "指标", "参数", "回测"]):
                    rebuilt_context["key_topics"].append({
                        "message_index": i,
                        "topic_type": "trading_strategy",
                        "content_preview": msg.content[:150]
                    })
                
                # 识别决策点
                if any(keyword in msg.content.lower() for keyword in ["决定", "选择", "确定", "修改"]):
                    rebuilt_context["decision_points"].append({
                        "message_index": i,
                        "decision_type": "user_choice",
                        "content_preview": msg.content[:150]
                    })
                
                # 识别技术内容
                if "```" in msg.content or any(keyword in msg.content for keyword in ["def ", "class ", "import "]):
                    rebuilt_context["technical_content"].append({
                        "message_index": i,
                        "content_type": "code",
                        "language": "python" if "def " in msg.content else "unknown"
                    })
            
            # 生成重建报告
            rebuild_report = f"""📋 **会话上下文重建完成**

🔍 **基本信息**:
- 总消息数: {rebuilt_context['total_messages']}
- 关键主题: {len(rebuilt_context['key_topics'])}个
- 决策点: {len(rebuilt_context['decision_points'])}个  
- 技术内容: {len(rebuilt_context['technical_content'])}个

✅ **会话已恢复，您可以继续之前的对话**
"""
            
            # 保存重建记录
            rebuild_message = ClaudeConversation(
                user_id=user_id,
                session_id=session_id,
                message_type="system",
                content=rebuild_report,
                context=json.dumps({
                    "recovery_type": "context_rebuild",
                    "rebuilt_context": rebuilt_context,
                    **recovery_data
                }),
                tokens_used=0,
                model="context-rebuild-system", 
                success=True
            )
            db.add(rebuild_message)
            
            await db.commit()
            
            return {
                "success": True,
                "recovery_type": "context_rebuild",
                "rebuilt_context": rebuilt_context,
                "rebuild_report": rebuild_report
            }
            
        except Exception as e:
            logger.error(f"上下文重建恢复失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _summary_based_recovery(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        session: AIChatSession,
        recovery_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基于摘要的恢复"""
        try:
            # 检查是否已有摘要
            existing_summary = await context_summarizer.get_context_with_summary(
                db, user_id, session_id, limit=1
            )
            
            summary_content = ""
            if existing_summary and existing_summary[0].message_type == "summary":
                summary_content = existing_summary[0].content
            else:
                # 生成新摘要
                new_summary = await context_summarizer.generate_context_summary(
                    db, user_id, session_id
                )
                if new_summary:
                    summary_content = new_summary
            
            if not summary_content:
                # 回退到基本恢复
                return await self._basic_recovery(db, user_id, session_id, session, recovery_data)
            
            # 构建基于摘要的恢复消息
            recovery_message_content = f"""📄 **基于智能摘要的会话恢复**

🔄 **上一次对话要点摘要**:
{summary_content}

✅ **会话已恢复，基于以上摘要继续对话**

您可以：
- 继续之前讨论的主题
- 询问具体的技术细节
- 开始新的相关讨论
"""
            
            # 保存恢复记录
            recovery_message = ClaudeConversation(
                user_id=user_id,
                session_id=session_id,
                message_type="system",
                content=recovery_message_content,
                context=json.dumps({
                    "recovery_type": "summary_based",
                    "has_existing_summary": len(existing_summary) > 0,
                    "summary_length": len(summary_content),
                    **recovery_data
                }),
                tokens_used=0,
                model="summary-recovery-system",
                success=True
            )
            db.add(recovery_message)
            
            await db.commit()
            
            return {
                "success": True,
                "recovery_type": "summary_based",
                "summary_content": summary_content,
                "recovery_message": recovery_message_content
            }
            
        except Exception as e:
            logger.error(f"基于摘要的恢复失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _basic_recovery(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        session: AIChatSession,
        recovery_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基础恢复"""
        try:
            basic_greeting = f"""👋 **会话已恢复**

🔄 会话信息:
- 名称: {session.name}
- 类型: {session.session_type}
- 模式: {session.ai_mode}
- 消息数: {session.message_count}

✅ 您可以继续之前的对话或开始新的讨论
"""
            
            # 保存恢复记录
            recovery_message = ClaudeConversation(
                user_id=user_id,
                session_id=session_id,
                message_type="system", 
                content=basic_greeting,
                context=json.dumps({
                    "recovery_type": "basic",
                    **recovery_data
                }),
                tokens_used=0,
                model="basic-recovery-system",
                success=True
            )
            db.add(recovery_message)
            
            await db.commit()
            
            return {
                "success": True,
                "recovery_type": "basic",
                "greeting": basic_greeting
            }
            
        except Exception as e:
            logger.error(f"基础恢复失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_recovery_summary(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        context_messages: List[ClaudeConversation]
    ) -> Optional[str]:
        """生成恢复摘要"""
        try:
            if not context_messages:
                return None
            
            # 简化版摘要生成 - 提取关键信息
            key_points = []
            
            for msg in context_messages[-10:]:  # 取最近10条消息
                if msg.message_type == "user":
                    # 用户关键请求
                    if len(msg.content) > 50:
                        key_points.append(f"用户询问: {msg.content[:100]}...")
                elif msg.message_type == "assistant":
                    # AI关键回复
                    if any(keyword in msg.content for keyword in ["策略", "代码", "建议", "分析"]):
                        key_points.append(f"AI回复要点: {msg.content[:100]}...")
            
            if not key_points:
                return None
            
            return "\\n\\n".join(key_points[:5])  # 最多5个要点
            
        except Exception as e:
            logger.error(f"生成恢复摘要失败: {e}")
            return None
    
    async def _generate_recovery_greeting(
        self,
        session: AIChatSession,
        context_messages: List[ClaudeConversation],
        recovery_summary: Optional[str]
    ) -> str:
        """生成恢复问候语"""
        try:
            base_greeting = f"👋 欢迎回到「{session.name}」会话！"
            
            session_info = []
            if session.session_type == "strategy":
                session_info.append("🎯 策略开发会话")
            elif session.session_type == "indicator":
                session_info.append("📊 指标分析会话")
            elif session.session_type == "debugging":
                session_info.append("🔧 问题调试会话")
            else:
                session_info.append("💬 AI助手对话")
            
            session_info.append(f"💬 已有 {len(context_messages)} 条对话记录")
            
            if session.progress and session.progress > 0:
                session_info.append(f"📈 完成进度: {session.progress}%")
            
            greeting_parts = [base_greeting]
            greeting_parts.extend([f"- {info}" for info in session_info])
            
            if recovery_summary:
                greeting_parts.append(f"\\n📋 **上次对话要点**:\\n{recovery_summary}")
            
            greeting_parts.append("\\n✅ 会话已恢复，您可以继续对话！")
            
            return "\\n".join(greeting_parts)
            
        except Exception as e:
            logger.error(f"生成恢复问候语失败: {e}")
            return "👋 会话已恢复，您可以继续对话！"
    
    async def get_recoverable_sessions(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取可恢复的会话列表"""
        try:
            # 查询可恢复状态的会话
            query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.status.in_(self.recoverable_states),
                    AIChatSession.updated_at > (datetime.utcnow() - timedelta(seconds=self.recovery_window))
                )
            ).order_by(desc(AIChatSession.last_activity_at)).limit(limit)
            
            result = await db.execute(query)
            recoverable_sessions = result.scalars().all()
            
            session_list = []
            for session in recoverable_sessions:
                feasibility = await self._assess_recovery_feasibility(db, user_id, session.session_id)
                
                session_info = {
                    "session_id": session.session_id,
                    "name": session.name,
                    "session_type": session.session_type,
                    "ai_mode": session.ai_mode,
                    "status": session.status,
                    "last_activity": session.last_activity_at.isoformat(),
                    "message_count": session.message_count,
                    "progress": session.progress,
                    "recovery_feasibility": feasibility["feasibility"],
                    "recovery_score": feasibility["score"],
                    "priority": self._calculate_recovery_priority(session),
                    "estimated_recovery_time": self._estimate_recovery_time(feasibility)
                }
                session_list.append(session_info)
            
            # 按优先级排序
            session_list.sort(key=lambda x: x["priority"])
            
            return session_list
            
        except Exception as e:
            logger.error(f"获取可恢复会话列表失败: {e}")
            return []
    
    def _estimate_recovery_time(self, feasibility: Dict[str, Any]) -> str:
        """估算恢复时间"""
        score = feasibility["score"]
        
        if score >= 0.8:
            return "即时恢复"
        elif score >= 0.6:
            return "< 30秒"
        elif score >= 0.4:
            return "1-2分钟"
        elif score >= 0.2:
            return "2-5分钟"
        else:
            return "需要手动处理"
    
    async def cleanup_expired_sessions(
        self,
        db: AsyncSession,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """清理过期的会话"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.recovery_window)
            
            # 构建查询条件
            conditions = [
                AIChatSession.status.in_(["interrupted", "paused"]),
                AIChatSession.updated_at < cutoff_time
            ]
            
            if user_id:
                conditions.append(AIChatSession.user_id == user_id)
            
            # 查询过期会话
            query = select(AIChatSession).where(and_(*conditions))
            result = await db.execute(query)
            expired_sessions = result.scalars().all()
            
            # 更新为已归档状态
            cleanup_count = 0
            for session in expired_sessions:
                await db.execute(
                    update(AIChatSession)
                    .where(AIChatSession.session_id == session.session_id)
                    .values(
                        status="archived",
                        updated_at=datetime.utcnow()
                    )
                )
                cleanup_count += 1
            
            await db.commit()
            
            logger.info(f"清理过期会话完成 - 处理 {cleanup_count} 个会话")
            
            return {
                "success": True,
                "cleaned_sessions": cleanup_count,
                "cutoff_time": cutoff_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"清理过期会话失败: {e}")
            return {"success": False, "error": str(e)}


# 全局实例
session_recovery_service = SessionRecoveryService()