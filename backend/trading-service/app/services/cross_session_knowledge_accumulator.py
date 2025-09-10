"""
跨会话知识积累系统
- 用户偏好和交易风格学习
- 技术知识提取与积累
- 个性化建议引擎
- 知识图谱构建
- 智能用户画像
"""

import json
import asyncio
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, text
from loguru import logger
from collections import defaultdict, Counter

from app.models.claude_conversation import ClaudeConversation, AIChatSession


class CrossSessionKnowledgeAccumulator:
    """跨会话知识积累器"""
    
    def __init__(self):
        # 知识积累配置
        self.learning_window_days = 30  # 学习窗口期（天）
        self.min_sessions_for_profile = 3  # 建立用户画像的最小会话数
        self.confidence_threshold = 0.6  # 知识置信度阈值
        
        # 用户偏好分类
        self.preference_categories = {
            "trading_style": ["短线交易", "长线投资", "量化交易", "技术分析", "基本面分析"],
            "risk_tolerance": ["保守", "稳健", "激进", "高风险高收益"],
            "indicators": ["MA", "RSI", "MACD", "BOLL", "KDJ", "STOCH", "ATR", "VWAP"],
            "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d", "1w"],
            "markets": ["股票", "数字货币", "外汇", "期货", "期权"],
            "complexity": ["初级", "中级", "高级", "专家级"]
        }
        
        # 技术知识关键词
        self.technical_keywords = {
            "strategies": ["策略", "交易策略", "算法", "量化策略", "套利", "对冲"],
            "indicators": ["指标", "技术指标", "信号", "买入信号", "卖出信号", "金叉", "死叉"],
            "risk_management": ["风险管理", "止损", "止盈", "仓位管理", "资金管理", "风控"],
            "patterns": ["形态", "价格形态", "K线形态", "图形模式", "支撑位", "阻力位"],
            "programming": ["代码", "函数", "算法实现", "回测", "优化", "参数调整"]
        }
        
        # 知识权重配置
        self.knowledge_weights = {
            "user_preference": 1.0,
            "technical_discussion": 2.0,
            "strategy_development": 3.0,
            "problem_solving": 2.5,
            "code_generation": 2.0
        }
    
    async def analyze_user_learning_patterns(
        self,
        db: AsyncSession,
        user_id: int,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """分析用户学习模式"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # 获取用户所有会话
            sessions_query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.created_at >= cutoff_date
                )
            ).order_by(AIChatSession.created_at.asc())
            
            result = await db.execute(sessions_query)
            user_sessions = result.scalars().all()
            
            if not user_sessions:
                return self._empty_learning_analysis(user_id)
            
            # 获取所有对话消息
            all_messages = []
            for session in user_sessions:
                messages_query = select(ClaudeConversation).where(
                    and_(
                        ClaudeConversation.user_id == user_id,
                        ClaudeConversation.session_id == session.session_id,
                        ClaudeConversation.created_at >= cutoff_date
                    )
                ).order_by(ClaudeConversation.created_at.asc())
                
                msg_result = await db.execute(messages_query)
                session_messages = msg_result.scalars().all()
                all_messages.extend(session_messages)
            
            # 执行深度学习分析
            learning_analysis = await self._perform_deep_learning_analysis(
                user_sessions, all_messages
            )
            
            logger.info(f"用户学习模式分析完成 - 用户:{user_id}, 会话:{len(user_sessions)}, 消息:{len(all_messages)}")
            
            return learning_analysis
            
        except Exception as e:
            logger.error(f"分析用户学习模式失败: {e}")
            return self._empty_learning_analysis(user_id)
    
    async def _perform_deep_learning_analysis(
        self,
        sessions: List[AIChatSession],
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """执行深度学习分析"""
        try:
            analysis = {
                "user_profile": await self._build_user_profile(sessions, messages),
                "preference_evolution": await self._analyze_preference_evolution(sessions, messages),
                "knowledge_accumulation": await self._analyze_knowledge_accumulation(messages),
                "behavioral_patterns": await self._analyze_behavioral_patterns(sessions, messages),
                "expertise_assessment": await self._assess_user_expertise(messages),
                "recommendations": await self._generate_personalized_recommendations(sessions, messages)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"深度学习分析失败: {e}")
            return {}
    
    async def _build_user_profile(
        self,
        sessions: List[AIChatSession],
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """构建用户画像"""
        try:
            profile = {
                "basic_stats": {
                    "total_sessions": len(sessions),
                    "total_messages": len(messages),
                    "avg_session_length": sum(s.message_count for s in sessions) / len(sessions) if sessions else 0,
                    "activity_span_days": (sessions[-1].created_at - sessions[0].created_at).days if len(sessions) > 1 else 0
                },
                "interaction_preferences": {},
                "technical_interests": {},
                "learning_style": {},
                "communication_pattern": {}
            }
            
            # 分析交互偏好
            profile["interaction_preferences"] = await self._analyze_interaction_preferences(sessions)
            
            # 分析技术兴趣
            profile["technical_interests"] = await self._analyze_technical_interests(messages)
            
            # 分析学习风格
            profile["learning_style"] = await self._analyze_learning_style(messages)
            
            # 分析沟通模式
            profile["communication_pattern"] = await self._analyze_communication_pattern(messages)
            
            return profile
            
        except Exception as e:
            logger.error(f"构建用户画像失败: {e}")
            return {}
    
    async def _analyze_interaction_preferences(
        self, 
        sessions: List[AIChatSession]
    ) -> Dict[str, Any]:
        """分析交互偏好"""
        try:
            session_types = [s.session_type for s in sessions if s.session_type]
            ai_modes = [s.ai_mode for s in sessions if s.ai_mode]
            
            # 统计偏好分布
            type_distribution = dict(Counter(session_types))
            mode_distribution = dict(Counter(ai_modes))
            
            # 分析活跃时间模式
            session_hours = [s.created_at.hour for s in sessions]
            peak_hours = Counter(session_hours).most_common(3)
            
            # 分析会话持续时间偏好
            session_durations = []
            for session in sessions:
                if session.updated_at and session.created_at:
                    duration = (session.updated_at - session.created_at).total_seconds() / 60  # 分钟
                    session_durations.append(duration)
            
            avg_duration = sum(session_durations) / len(session_durations) if session_durations else 0
            
            return {
                "preferred_session_types": type_distribution,
                "preferred_ai_modes": mode_distribution,
                "peak_activity_hours": [{"hour": hour, "count": count} for hour, count in peak_hours],
                "average_session_duration_minutes": round(avg_duration, 2),
                "total_active_sessions": len(sessions)
            }
            
        except Exception as e:
            logger.error(f"分析交互偏好失败: {e}")
            return {}
    
    async def _analyze_technical_interests(
        self, 
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """分析技术兴趣"""
        try:
            interest_scores = defaultdict(float)
            total_content = ""
            
            # 合并所有用户消息内容
            for msg in messages:
                if msg.message_type == "user":
                    total_content += msg.content.lower() + " "
            
            # 分析各技术领域的兴趣度
            for category, keywords in self.technical_keywords.items():
                category_score = 0
                for keyword in keywords:
                    count = total_content.count(keyword.lower())
                    category_score += count
                
                if category_score > 0:
                    interest_scores[category] = category_score
            
            # 分析偏好指标
            indicator_mentions = defaultdict(int)
            for indicator in self.preference_categories["indicators"]:
                count = total_content.count(indicator.lower())
                if count > 0:
                    indicator_mentions[indicator] = count
            
            # 分析时间周期偏好
            timeframe_mentions = defaultdict(int)
            for tf in self.preference_categories["timeframes"]:
                count = total_content.count(tf)
                if count > 0:
                    timeframe_mentions[tf] = count
            
            return {
                "technical_interest_distribution": dict(interest_scores),
                "preferred_indicators": dict(indicator_mentions),
                "preferred_timeframes": dict(timeframe_mentions),
                "interest_diversity_score": len(interest_scores) / len(self.technical_keywords),
                "total_technical_mentions": sum(interest_scores.values())
            }
            
        except Exception as e:
            logger.error(f"分析技术兴趣失败: {e}")
            return {}
    
    async def _analyze_learning_style(
        self, 
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """分析学习风格"""
        try:
            learning_indicators = {
                "question_asking": 0,      # 提问倾向
                "code_focused": 0,         # 代码导向
                "theory_focused": 0,       # 理论导向
                "practical_focused": 0,    # 实践导向
                "step_by_step": 0,        # 循序渐进
                "exploratory": 0          # 探索性学习
            }
            
            user_messages = [msg for msg in messages if msg.message_type == "user"]
            
            for msg in user_messages:
                content = msg.content.lower()
                
                # 提问倾向分析
                question_words = ["如何", "怎么", "为什么", "什么是", "能否", "可以", "?", "？"]
                if any(word in content for word in question_words):
                    learning_indicators["question_asking"] += 1
                
                # 代码导向分析
                if any(keyword in content for keyword in ["代码", "函数", "算法", "实现", "编程"]):
                    learning_indicators["code_focused"] += 1
                
                # 理论导向分析
                if any(keyword in content for keyword in ["原理", "理论", "概念", "定义", "解释"]):
                    learning_indicators["theory_focused"] += 1
                
                # 实践导向分析
                if any(keyword in content for keyword in ["实际", "实践", "例子", "案例", "演示"]):
                    learning_indicators["practical_focused"] += 1
                
                # 循序渐进分析
                if any(keyword in content for keyword in ["步骤", "流程", "逐步", "一步一步", "详细"]):
                    learning_indicators["step_by_step"] += 1
                
                # 探索性学习分析
                if any(keyword in content for keyword in ["尝试", "试试", "探索", "研究", "实验"]):
                    learning_indicators["exploratory"] += 1
            
            # 计算学习风格偏好
            total_indicators = sum(learning_indicators.values())
            if total_indicators > 0:
                learning_style_distribution = {
                    k: round(v / total_indicators, 3) for k, v in learning_indicators.items()
                }
            else:
                learning_style_distribution = {}
            
            # 确定主导学习风格
            dominant_style = max(learning_indicators, key=learning_indicators.get) if learning_indicators else "未知"
            
            return {
                "learning_indicators": learning_indicators,
                "learning_style_distribution": learning_style_distribution,
                "dominant_learning_style": dominant_style,
                "learning_engagement_score": total_indicators / len(user_messages) if user_messages else 0
            }
            
        except Exception as e:
            logger.error(f"分析学习风格失败: {e}")
            return {}
    
    async def _analyze_communication_pattern(
        self, 
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """分析沟通模式"""
        try:
            user_messages = [msg for msg in messages if msg.message_type == "user"]
            
            if not user_messages:
                return {}
            
            # 消息长度分析
            message_lengths = [len(msg.content) for msg in user_messages]
            avg_message_length = sum(message_lengths) / len(message_lengths)
            
            # 沟通频率分析
            message_times = [msg.created_at for msg in user_messages]
            time_intervals = []
            for i in range(1, len(message_times)):
                interval = (message_times[i] - message_times[i-1]).total_seconds() / 60  # 分钟
                time_intervals.append(interval)
            
            avg_interval = sum(time_intervals) / len(time_intervals) if time_intervals else 0
            
            # 表达风格分析
            formal_indicators = ["请", "您", "谢谢", "请问", "能否", "可以吗"]
            informal_indicators = ["咋", "啥", "搞", "弄", "整", "呢"]
            technical_indicators = ["函数", "算法", "参数", "变量", "代码", "API"]
            
            formal_count = sum(1 for msg in user_messages if any(indicator in msg.content for indicator in formal_indicators))
            informal_count = sum(1 for msg in user_messages if any(indicator in msg.content for indicator in informal_indicators))
            technical_count = sum(1 for msg in user_messages if any(indicator in msg.content for indicator in technical_indicators))
            
            # 问题复杂度分析
            simple_questions = sum(1 for msg in user_messages if len(msg.content) < 50)
            complex_questions = sum(1 for msg in user_messages if len(msg.content) > 200)
            
            return {
                "average_message_length": round(avg_message_length, 2),
                "average_response_interval_minutes": round(avg_interval, 2),
                "communication_style": {
                    "formal_ratio": round(formal_count / len(user_messages), 3),
                    "informal_ratio": round(informal_count / len(user_messages), 3),
                    "technical_ratio": round(technical_count / len(user_messages), 3)
                },
                "question_complexity": {
                    "simple_questions": simple_questions,
                    "complex_questions": complex_questions,
                    "complexity_ratio": round(complex_questions / max(simple_questions, 1), 3)
                },
                "total_user_messages": len(user_messages)
            }
            
        except Exception as e:
            logger.error(f"分析沟通模式失败: {e}")
            return {}
    
    async def _analyze_preference_evolution(
        self,
        sessions: List[AIChatSession],
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """分析偏好演变"""
        try:
            if len(sessions) < 2:
                return {"evolution_available": False, "reason": "insufficient_data"}
            
            # 按时间段分割会话
            total_days = (sessions[-1].created_at - sessions[0].created_at).days
            if total_days < 7:
                return {"evolution_available": False, "reason": "insufficient_time_span"}
            
            # 分成早期和后期两个阶段
            midpoint_date = sessions[0].created_at + timedelta(days=total_days//2)
            
            early_sessions = [s for s in sessions if s.created_at <= midpoint_date]
            late_sessions = [s for s in sessions if s.created_at > midpoint_date]
            
            early_messages = [m for m in messages if m.created_at <= midpoint_date]
            late_messages = [m for m in messages if m.created_at > midpoint_date]
            
            # 分析早期和后期的兴趣分布
            early_interests = await self._analyze_technical_interests(early_messages)
            late_interests = await self._analyze_technical_interests(late_messages)
            
            # 计算兴趣变化
            interest_changes = {}
            for category in self.technical_keywords.keys():
                early_score = early_interests.get("technical_interest_distribution", {}).get(category, 0)
                late_score = late_interests.get("technical_interest_distribution", {}).get(category, 0)
                
                if early_score > 0 or late_score > 0:
                    change_ratio = (late_score - early_score) / max(early_score, 1)
                    interest_changes[category] = {
                        "early_score": early_score,
                        "late_score": late_score,
                        "change_ratio": round(change_ratio, 3),
                        "trend": "increasing" if change_ratio > 0.2 else "decreasing" if change_ratio < -0.2 else "stable"
                    }
            
            # 分析会话类型演变
            early_types = Counter([s.session_type for s in early_sessions if s.session_type])
            late_types = Counter([s.session_type for s in late_sessions if s.session_type])
            
            return {
                "evolution_available": True,
                "analysis_period_days": total_days,
                "early_period": {
                    "sessions": len(early_sessions),
                    "messages": len(early_messages),
                    "interests": early_interests.get("technical_interest_distribution", {}),
                    "session_types": dict(early_types)
                },
                "late_period": {
                    "sessions": len(late_sessions),
                    "messages": len(late_messages),
                    "interests": late_interests.get("technical_interest_distribution", {}),
                    "session_types": dict(late_types)
                },
                "interest_evolution": interest_changes,
                "engagement_evolution": {
                    "early_avg_session_length": sum(s.message_count for s in early_sessions) / len(early_sessions) if early_sessions else 0,
                    "late_avg_session_length": sum(s.message_count for s in late_sessions) / len(late_sessions) if late_sessions else 0
                }
            }
            
        except Exception as e:
            logger.error(f"分析偏好演变失败: {e}")
            return {"evolution_available": False, "reason": "analysis_error"}
    
    async def _analyze_knowledge_accumulation(
        self, 
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """分析知识积累"""
        try:
            knowledge_areas = defaultdict(list)
            learning_progression = []
            
            # 按时间顺序分析知识获取
            sorted_messages = sorted(messages, key=lambda x: x.created_at)
            
            for i, msg in enumerate(sorted_messages):
                if msg.message_type == "assistant" and msg.success:
                    # 分析AI回复中的知识内容
                    knowledge_content = self._extract_knowledge_from_message(msg.content)
                    
                    if knowledge_content:
                        learning_progression.append({
                            "message_index": i,
                            "timestamp": msg.created_at.isoformat(),
                            "knowledge_areas": knowledge_content["areas"],
                            "complexity_score": knowledge_content["complexity"],
                            "content_preview": msg.content[:150]
                        })
                        
                        for area in knowledge_content["areas"]:
                            knowledge_areas[area].append({
                                "timestamp": msg.created_at,
                                "complexity": knowledge_content["complexity"],
                                "content_preview": msg.content[:100]
                            })
            
            # 分析知识积累趋势
            knowledge_summary = {}
            for area, instances in knowledge_areas.items():
                knowledge_summary[area] = {
                    "total_instances": len(instances),
                    "avg_complexity": sum(inst["complexity"] for inst in instances) / len(instances),
                    "first_encounter": instances[0]["timestamp"].isoformat() if instances else None,
                    "latest_encounter": instances[-1]["timestamp"].isoformat() if instances else None,
                    "learning_span_days": (instances[-1]["timestamp"] - instances[0]["timestamp"]).days if len(instances) > 1 else 0
                }
            
            return {
                "total_knowledge_instances": len(learning_progression),
                "knowledge_areas": knowledge_summary,
                "learning_progression": learning_progression[-10:],  # 最近10个知识点
                "knowledge_diversity": len(knowledge_areas),
                "accumulated_complexity_score": sum(lp["complexity_score"] for lp in learning_progression)
            }
            
        except Exception as e:
            logger.error(f"分析知识积累失败: {e}")
            return {}
    
    def _extract_knowledge_from_message(self, content: str) -> Optional[Dict[str, Any]]:
        """从消息中提取知识内容"""
        try:
            knowledge_indicators = {
                "strategies": ["策略", "交易策略", "算法", "方法"],
                "indicators": ["指标", "RSI", "MACD", "MA", "布林带"],
                "risk_management": ["风险", "止损", "仓位", "资金管理"],
                "programming": ["代码", "函数", "def ", "class ", "import"],
                "market_analysis": ["分析", "市场", "趋势", "支撑", "阻力"]
            }
            
            content_lower = content.lower()
            identified_areas = []
            complexity_score = 0
            
            for area, keywords in knowledge_indicators.items():
                area_score = 0
                for keyword in keywords:
                    if keyword.lower() in content_lower:
                        area_score += 1
                
                if area_score > 0:
                    identified_areas.append(area)
                    complexity_score += area_score
            
            # 根据内容长度和技术词汇密度调整复杂度
            if len(content) > 200:
                complexity_score += 1
            if "```" in content:  # 包含代码块
                complexity_score += 2
            if len(re.findall(r'[0-9]+\.[0-9]+|[0-9]+', content)) > 3:  # 包含数字
                complexity_score += 1
            
            if identified_areas:
                return {
                    "areas": identified_areas,
                    "complexity": min(complexity_score, 10)  # 复杂度上限10
                }
            
            return None
            
        except Exception as e:
            logger.error(f"提取知识内容失败: {e}")
            return None
    
    async def _analyze_behavioral_patterns(
        self,
        sessions: List[AIChatSession],
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """分析行为模式"""
        try:
            patterns = {
                "session_initiation_patterns": {},
                "problem_solving_patterns": {},
                "follow_up_patterns": {},
                "abandonment_patterns": {}
            }
            
            # 分析会话发起模式
            session_start_hours = [s.created_at.hour for s in sessions]
            session_start_days = [s.created_at.weekday() for s in sessions]  # 0=周一, 6=周日
            
            patterns["session_initiation_patterns"] = {
                "preferred_hours": dict(Counter(session_start_hours).most_common(5)),
                "preferred_weekdays": dict(Counter(session_start_days).most_common(7)),
                "avg_sessions_per_week": len(sessions) / max((sessions[-1].created_at - sessions[0].created_at).days / 7, 1) if len(sessions) > 1 else 0
            }
            
            # 分析问题解决模式
            user_messages = [m for m in messages if m.message_type == "user"]
            problem_keywords = ["错误", "问题", "不懂", "失败", "bug", "异常"]
            problem_messages = [m for m in user_messages if any(kw in m.content for kw in problem_keywords)]
            
            patterns["problem_solving_patterns"] = {
                "total_problem_instances": len(problem_messages),
                "problem_solving_ratio": len(problem_messages) / len(user_messages) if user_messages else 0,
                "avg_problem_message_length": sum(len(m.content) for m in problem_messages) / len(problem_messages) if problem_messages else 0
            }
            
            # 分析跟进模式
            follow_up_keywords = ["继续", "接着", "然后", "另外", "还有"]
            follow_up_messages = [m for m in user_messages if any(kw in m.content for kw in follow_up_keywords)]
            
            patterns["follow_up_patterns"] = {
                "follow_up_ratio": len(follow_up_messages) / len(user_messages) if user_messages else 0,
                "engagement_depth_score": len(follow_up_messages) / len(sessions) if sessions else 0
            }
            
            # 分析放弃模式
            incomplete_sessions = [s for s in sessions if s.status in ["interrupted", "paused"] or s.progress < 50]
            
            patterns["abandonment_patterns"] = {
                "abandonment_rate": len(incomplete_sessions) / len(sessions) if sessions else 0,
                "avg_abandonment_progress": sum(s.progress for s in incomplete_sessions) / len(incomplete_sessions) if incomplete_sessions else 0
            }
            
            return patterns
            
        except Exception as e:
            logger.error(f"分析行为模式失败: {e}")
            return {}
    
    async def _assess_user_expertise(
        self, 
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """评估用户专业水平"""
        try:
            expertise_indicators = {
                "beginner": 0,
                "intermediate": 0,
                "advanced": 0,
                "expert": 0
            }
            
            user_messages = [m for m in messages if m.message_type == "user"]
            
            for msg in user_messages:
                content = msg.content.lower()
                
                # 初级指标
                beginner_keywords = ["什么是", "如何", "怎么", "基础", "入门", "新手"]
                if any(kw in content for kw in beginner_keywords):
                    expertise_indicators["beginner"] += 1
                
                # 中级指标
                intermediate_keywords = ["优化", "改进", "调整", "参数", "配置", "实现"]
                if any(kw in content for kw in intermediate_keywords):
                    expertise_indicators["intermediate"] += 1
                
                # 高级指标
                advanced_keywords = ["算法", "架构", "设计", "框架", "模式", "策略"]
                if any(kw in content for kw in advanced_keywords):
                    expertise_indicators["advanced"] += 1
                
                # 专家指标
                expert_keywords = ["源码", "底层", "内核", "引擎", "协议", "规范"]
                if any(kw in content for kw in expert_keywords):
                    expertise_indicators["expert"] += 1
                
                # 技术深度指标
                if "```" in msg.content:  # 包含代码
                    expertise_indicators["advanced"] += 1
                
                if len(re.findall(r'\\b[A-Z][a-z]+\\([^)]*\\)', msg.content)) > 0:  # 函数调用
                    expertise_indicators["intermediate"] += 1
            
            # 计算专业水平分布
            total_indicators = sum(expertise_indicators.values())
            if total_indicators > 0:
                expertise_distribution = {
                    k: round(v / total_indicators, 3) for k, v in expertise_indicators.items()
                }
            else:
                expertise_distribution = {"beginner": 1.0}
            
            # 确定主要专业水平
            dominant_level = max(expertise_indicators, key=expertise_indicators.get)
            confidence = expertise_indicators[dominant_level] / total_indicators if total_indicators > 0 else 0
            
            return {
                "expertise_indicators": expertise_indicators,
                "expertise_distribution": expertise_distribution,
                "estimated_level": dominant_level,
                "confidence_score": round(confidence, 3),
                "expertise_evolution_potential": self._calculate_evolution_potential(expertise_indicators)
            }
            
        except Exception as e:
            logger.error(f"评估用户专业水平失败: {e}")
            return {}
    
    def _calculate_evolution_potential(self, indicators: Dict[str, int]) -> Dict[str, Any]:
        """计算专业水平演进潜力"""
        total = sum(indicators.values())
        if total == 0:
            return {"potential": "unknown", "score": 0}
        
        # 检查分布的平衡性
        beginner_ratio = indicators["beginner"] / total
        expert_ratio = indicators["expert"] / total
        
        if beginner_ratio > 0.6:
            return {"potential": "high", "score": 0.8, "direction": "learning_growth"}
        elif expert_ratio > 0.4:
            return {"potential": "teaching", "score": 0.7, "direction": "knowledge_sharing"}
        elif indicators["intermediate"] > indicators["advanced"]:
            return {"potential": "moderate", "score": 0.6, "direction": "skill_deepening"}
        else:
            return {"potential": "stable", "score": 0.4, "direction": "knowledge_consolidation"}
    
    async def _generate_personalized_recommendations(
        self,
        sessions: List[AIChatSession],
        messages: List[ClaudeConversation]
    ) -> Dict[str, Any]:
        """生成个性化建议"""
        try:
            recommendations = {
                "learning_path": [],
                "content_suggestions": [],
                "interaction_optimization": [],
                "next_session_topics": []
            }
            
            # 基于用户兴趣生成学习路径
            technical_interests = await self._analyze_technical_interests(messages)
            top_interests = sorted(
                technical_interests.get("technical_interest_distribution", {}).items(),
                key=lambda x: x[1], reverse=True
            )[:3]
            
            for interest, score in top_interests:
                recommendations["learning_path"].append({
                    "topic": interest,
                    "current_level": "intermediate" if score > 5 else "beginner",
                    "suggested_next_steps": self._get_next_steps_for_topic(interest),
                    "estimated_time": "1-2 hours",
                    "difficulty": "moderate"
                })
            
            # 基于行为模式生成内容建议
            user_messages = [m for m in messages if m.message_type == "user"]
            avg_message_length = sum(len(m.content) for m in user_messages) / len(user_messages) if user_messages else 0
            
            if avg_message_length < 50:
                recommendations["content_suggestions"].append({
                    "type": "interaction_improvement",
                    "suggestion": "尝试提出更详细的问题，这样我可以提供更准确的帮助",
                    "benefit": "获得更精准和实用的回答"
                })
            
            # 基于会话模式生成交互优化建议
            session_types = Counter([s.session_type for s in sessions if s.session_type])
            if session_types.get("strategy", 0) > session_types.get("indicator", 0):
                recommendations["interaction_optimization"].append({
                    "type": "diversification",
                    "suggestion": "考虑探索技术指标分析，可以增强您的策略开发能力",
                    "priority": "medium"
                })
            
            # 基于最近活动生成下次会话主题建议
            recent_messages = messages[-5:] if len(messages) >= 5 else messages
            recent_topics = []
            for msg in recent_messages:
                if msg.message_type == "user":
                    for category, keywords in self.technical_keywords.items():
                        if any(kw.lower() in msg.content.lower() for kw in keywords):
                            recent_topics.append(category)
            
            if recent_topics:
                most_recent_topic = Counter(recent_topics).most_common(1)[0][0]
                recommendations["next_session_topics"].append({
                    "topic": most_recent_topic,
                    "reason": "基于您最近的讨论兴趣",
                    "suggested_approach": "深入探讨实际应用案例",
                    "preparation": "准备具体的市场数据示例"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成个性化建议失败: {e}")
            return {}
    
    def _get_next_steps_for_topic(self, topic: str) -> List[str]:
        """获取特定主题的下一步学习建议"""
        next_steps_map = {
            "strategies": [
                "学习更多策略类型和应用场景",
                "实践策略回测和优化",
                "研究风险管理技术"
            ],
            "indicators": [
                "深入理解指标计算原理",
                "学习指标组合使用",
                "开发自定义指标"
            ],
            "risk_management": [
                "学习高级风险控制技术",
                "研究资金管理策略",
                "实践风险评估方法"
            ],
            "programming": [
                "提升代码质量和效率",
                "学习高级编程技巧",
                "实践算法优化"
            ]
        }
        
        return next_steps_map.get(topic, ["继续深入学习相关概念", "实践应用", "寻求高级指导"])
    
    def _empty_learning_analysis(self, user_id: int) -> Dict[str, Any]:
        """空的学习分析结果"""
        return {
            "user_id": user_id,
            "analysis_available": False,
            "reason": "insufficient_data",
            "recommendations": {
                "suggestion": "开始更多的AI对话来建立您的学习档案",
                "minimum_sessions": self.min_sessions_for_profile
            }
        }
    
    async def get_personalized_context_enhancement(
        self,
        db: AsyncSession,
        user_id: int,
        current_session_id: str,
        current_message: str
    ) -> Dict[str, Any]:
        """获取个性化上下文增强"""
        try:
            # 获取用户学习分析
            learning_analysis = await self.analyze_user_learning_patterns(db, user_id)
            
            if not learning_analysis.get("user_profile"):
                return {"enhancement_available": False}
            
            user_profile = learning_analysis["user_profile"]
            
            # 生成上下文增强建议
            enhancements = {
                "personalized_greeting": self._generate_personalized_greeting(user_profile),
                "relevant_background": self._extract_relevant_background(user_profile, current_message),
                "suggested_follow_ups": self._suggest_follow_up_questions(user_profile, current_message),
                "complexity_adjustment": self._suggest_complexity_level(user_profile),
                "learning_optimization": self._suggest_learning_optimization(user_profile)
            }
            
            return {
                "enhancement_available": True,
                "enhancements": enhancements,
                "user_profile_summary": {
                    "dominant_interests": list(user_profile.get("technical_interests", {}).get("technical_interest_distribution", {}).keys())[:3],
                    "learning_style": user_profile.get("learning_style", {}).get("dominant_learning_style", "unknown"),
                    "expertise_level": learning_analysis.get("expertise_assessment", {}).get("estimated_level", "intermediate")
                }
            }
            
        except Exception as e:
            logger.error(f"获取个性化上下文增强失败: {e}")
            return {"enhancement_available": False, "error": str(e)}
    
    def _generate_personalized_greeting(self, user_profile: Dict[str, Any]) -> str:
        """生成个性化问候语"""
        try:
            interests = user_profile.get("technical_interests", {}).get("technical_interest_distribution", {})
            learning_style = user_profile.get("learning_style", {}).get("dominant_learning_style", "")
            
            if not interests:
                return "您好！很高兴为您提供AI交易助手服务。"
            
            top_interest = max(interests, key=interests.get) if interests else "trading"
            
            greetings = {
                "strategies": "您好！我注意到您对交易策略很感兴趣，今天想探讨哪个方面呢？",
                "indicators": "您好！看起来您对技术指标分析颇有研究，有什么新的想法要讨论吗？",
                "programming": "您好！我看到您经常涉及代码实现，今天需要什么技术支持呢？",
                "risk_management": "您好！风险管理是交易的核心，今天想深入哪个风险控制话题？"
            }
            
            return greetings.get(top_interest, "您好！很高兴继续为您提供专业的交易技术支持。")
            
        except Exception:
            return "您好！很高兴为您提供AI交易助手服务。"
    
    def _extract_relevant_background(self, user_profile: Dict[str, Any], current_message: str) -> List[str]:
        """提取相关背景信息"""
        try:
            background = []
            
            # 基于用户历史兴趣提取相关背景
            interests = user_profile.get("technical_interests", {}).get("technical_interest_distribution", {})
            message_lower = current_message.lower()
            
            for interest, score in interests.items():
                if score > 2:  # 只考虑高兴趣度的领域
                    interest_keywords = self.technical_keywords.get(interest, [])
                    if any(kw.lower() in message_lower for kw in interest_keywords):
                        background.append(f"基于您在{interest}方面的经验")
            
            # 基于学习风格添加背景
            learning_style = user_profile.get("learning_style", {}).get("dominant_learning_style", "")
            if learning_style == "code_focused":
                background.append("考虑到您倾向于代码实现")
            elif learning_style == "theory_focused":
                background.append("结合您对理论基础的关注")
            elif learning_style == "practical_focused":
                background.append("基于您重视实际应用的特点")
            
            return background[:3]  # 最多3个背景点
            
        except Exception:
            return []
    
    def _suggest_follow_up_questions(self, user_profile: Dict[str, Any], current_message: str) -> List[str]:
        """建议后续问题"""
        try:
            suggestions = []
            
            # 基于用户学习风格建议问题
            learning_style = user_profile.get("learning_style", {}).get("dominant_learning_style", "")
            
            if "代码" in current_message or "实现" in current_message:
                suggestions.extend([
                    "需要我提供具体的代码示例吗？",
                    "想了解实现过程中的注意事项吗？",
                    "需要讨论代码优化方案吗？"
                ])
            
            if "策略" in current_message:
                suggestions.extend([
                    "想了解这个策略的风险控制措施吗？",
                    "需要探讨回测验证方法吗？",
                    "想看看类似策略的案例分析吗？"
                ])
            
            if "指标" in current_message:
                suggestions.extend([
                    "想了解这个指标与其他指标的组合使用吗？",
                    "需要讨论参数优化技巧吗？",
                    "想看看实际市场中的应用效果吗？"
                ])
            
            return suggestions[:3]
            
        except Exception:
            return []
    
    def _suggest_complexity_level(self, user_profile: Dict[str, Any]) -> str:
        """建议复杂度级别"""
        try:
            expertise = user_profile.get("learning_style", {}).get("learning_engagement_score", 0)
            
            if expertise > 0.7:
                return "advanced"  # 高级内容
            elif expertise > 0.4:
                return "intermediate"  # 中级内容
            else:
                return "beginner"  # 基础内容
                
        except Exception:
            return "intermediate"
    
    def _suggest_learning_optimization(self, user_profile: Dict[str, Any]) -> List[str]:
        """建议学习优化方案"""
        try:
            optimizations = []
            
            communication_pattern = user_profile.get("communication_pattern", {})
            avg_length = communication_pattern.get("average_message_length", 0)
            
            if avg_length < 50:
                optimizations.append("建议提供更详细的问题描述以获得更精准的帮助")
            
            learning_style = user_profile.get("learning_style", {})
            if learning_style.get("learning_indicators", {}).get("question_asking", 0) < 2:
                optimizations.append("尝试多问一些深入的问题来加深理解")
            
            if learning_style.get("learning_indicators", {}).get("practical_focused", 0) > 3:
                optimizations.append("可以尝试更多理论知识的学习来提升基础")
            
            return optimizations[:2]
            
        except Exception:
            return []


# 全局实例
cross_session_knowledge_accumulator = CrossSessionKnowledgeAccumulator()