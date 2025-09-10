"""
动态上下文窗口调整管理器
- 基于对话复杂度智能调整上下文长度
- 根据token预算动态优化窗口大小
- 消息重要性评分与优先级管理
- 会话类型感知的上下文策略
"""

import json
import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from loguru import logger

from app.models.claude_conversation import ClaudeConversation, AIChatSession
from app.services.context_summarizer_service import context_summarizer


class DynamicContextManager:
    """动态上下文窗口管理器"""
    
    def __init__(self):
        # 基础配置 - 优化WebSocket响应时间
        self.base_context_window = 8   # 基础窗口大小 (减少默认上下文)
        self.max_context_window = 15   # 最大窗口大小 (防止超时)
        self.min_context_window = 3    # 最小窗口大小
        
        # Token预算配置 (Claude Sonnet 4)
        self.max_input_tokens = 200000  # Claude Sonnet 4 最大输入token
        self.safe_token_budget = 150000 # 安全token预算
        self.avg_tokens_per_message = 100  # 平均每条消息token数
        
        # 重要性评分权重
        self.importance_weights = {
            "technical_keywords": 2.0,      # 技术关键词权重
            "decision_making": 3.0,         # 决策制定权重  
            "parameter_setting": 2.5,       # 参数设置权重
            "error_handling": 2.0,          # 错误处理权重
            "user_feedback": 1.5,           # 用户反馈权重
            "code_generation": 2.8,         # 代码生成权重
            "strategy_logic": 3.0           # 策略逻辑权重
        }
        
        # 会话类型上下文策略 - 优化WebSocket超时
        self.session_type_strategies = {
            "strategy": {"base_window": 8, "priority": ["strategy_logic", "technical_keywords", "parameter_setting"]},
            "indicator": {"base_window": 6, "priority": ["technical_keywords", "code_generation", "parameter_setting"]},
            "general": {"base_window": 5, "priority": ["user_feedback", "decision_making"]},
            "debugging": {"base_window": 10, "priority": ["error_handling", "code_generation", "technical_keywords"]}
        }

    async def calculate_optimal_context_window(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        current_message: str = "",
        target_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """计算最优上下文窗口大小"""
        try:
            # 获取会话信息
            session_info = await self._get_session_info(db, user_id, session_id)
            if not session_info:
                return await self._default_context_config(session_id)
            
            # 获取所有历史消息
            all_messages = await self._get_all_messages(db, user_id, session_id)
            if not all_messages:
                return await self._default_context_config(session_id)
            
            # 计算消息重要性评分
            message_scores = await self._calculate_message_importance(
                all_messages, session_info["session_type"], current_message
            )
            
            # 基于会话类型确定基础窗口
            session_type = session_info.get("session_type", "general")
            base_config = self.session_type_strategies.get(session_type, self.session_type_strategies["general"])
            base_window = base_config["base_window"]
            
            # 动态调整窗口大小
            optimal_window = await self._optimize_window_size(
                message_scores, base_window, target_tokens or self.safe_token_budget
            )
            
            # 选择最重要的消息
            selected_messages = await self._select_priority_messages(
                message_scores, optimal_window
            )
            
            logger.info(f"动态上下文计算完成 - 会话:{session_id}, 窗口:{optimal_window}, 消息数:{len(selected_messages)}")
            
            return {
                "optimal_window_size": optimal_window,
                "selected_message_count": len(selected_messages),
                "selected_messages": selected_messages,
                "session_type": session_type,
                "estimated_tokens": len(selected_messages) * self.avg_tokens_per_message,
                "context_strategy": "dynamic_optimization",
                "importance_distribution": self._analyze_importance_distribution(message_scores),
                "recommendations": await self._generate_context_recommendations(
                    session_type, optimal_window, len(all_messages)
                )
            }
            
        except Exception as e:
            logger.error(f"动态上下文窗口计算失败: {e}")
            return await self._default_context_config(session_id)

    async def _get_session_info(
        self, 
        db: AsyncSession, 
        user_id: int, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.session_id == session_id
                )
            )
            result = await db.execute(query)
            session = result.scalar_one_or_none()
            
            if session:
                return {
                    "session_type": session.session_type,
                    "ai_mode": session.ai_mode,
                    "message_count": session.message_count,
                    "status": session.status
                }
            return None
            
        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
            return None

    async def _get_all_messages(
        self, 
        db: AsyncSession, 
        user_id: int, 
        session_id: str
    ) -> List[ClaudeConversation]:
        """获取所有消息(排除摘要)"""
        try:
            query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type.in_(["user", "assistant"])
                )
            ).order_by(ClaudeConversation.created_at.asc())
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"获取消息历史失败: {e}")
            return []

    async def _calculate_message_importance(
        self,
        messages: List[ClaudeConversation],
        session_type: str,
        current_message: str = ""
    ) -> List[Dict[str, Any]]:
        """计算消息重要性评分"""
        message_scores = []
        
        # 会话类型优先级
        priority_categories = self.session_type_strategies.get(
            session_type, self.session_type_strategies["general"]
        )["priority"]
        
        for i, msg in enumerate(messages):
            score_details = {
                "message_id": msg.id,
                "message_index": i,
                "content": msg.content,
                "message_type": msg.message_type,
                "created_at": msg.created_at,
                "base_score": 1.0,
                "category_scores": {},
                "total_score": 0.0,
                "importance_factors": []
            }
            
            content = msg.content.lower()
            total_score = 1.0
            
            # 技术关键词评分
            tech_keywords = [
                "策略", "指标", "回测", "参数", "信号", "买入", "卖出", 
                "止损", "止盈", "ma", "rsi", "macd", "bollinger", "kd",
                "python", "def", "class", "import", "return"
            ]
            tech_score = sum(1 for keyword in tech_keywords if keyword in content)
            if tech_score > 0:
                score_details["category_scores"]["technical_keywords"] = tech_score
                total_score += tech_score * self.importance_weights["technical_keywords"]
                score_details["importance_factors"].append(f"技术关键词:{tech_score}")
            
            # 决策制定评分
            decision_keywords = [
                "决定", "选择", "确定", "修改", "调整", "优化", "建议", "推荐",
                "应该", "最好", "建议", "采用", "使用"
            ]
            decision_score = sum(1 for keyword in decision_keywords if keyword in content)
            if decision_score > 0:
                score_details["category_scores"]["decision_making"] = decision_score
                total_score += decision_score * self.importance_weights["decision_making"]
                score_details["importance_factors"].append(f"决策制定:{decision_score}")
            
            # 参数设置评分
            param_patterns = [
                r'\d+\s*(天|日|period|周期)', r'=\s*\d+', r'\d+\.\d+', 
                r'(threshold|阈值|临界值).*\d', r'(比例|ratio|percent).*\d'
            ]
            param_score = sum(1 for pattern in param_patterns if re.search(pattern, content))
            if param_score > 0:
                score_details["category_scores"]["parameter_setting"] = param_score
                total_score += param_score * self.importance_weights["parameter_setting"]
                score_details["importance_factors"].append(f"参数设置:{param_score}")
            
            # 错误处理评分
            error_keywords = ["错误", "异常", "问题", "bug", "修复", "解决", "调试"]
            error_score = sum(1 for keyword in error_keywords if keyword in content)
            if error_score > 0:
                score_details["category_scores"]["error_handling"] = error_score
                total_score += error_score * self.importance_weights["error_handling"]
                score_details["importance_factors"].append(f"错误处理:{error_score}")
            
            # 代码生成评分
            if "```" in msg.content or any(keyword in content for keyword in ["def ", "class ", "import ", "return "]):
                code_score = 2.0
                score_details["category_scores"]["code_generation"] = code_score
                total_score += code_score * self.importance_weights["code_generation"]
                score_details["importance_factors"].append(f"代码生成:{code_score}")
            
            # 策略逻辑评分
            strategy_keywords = [
                "买入条件", "卖出条件", "入场", "出场", "交易逻辑", "策略思路",
                "风险控制", "资金管理", "仓位", "杠杆"
            ]
            strategy_score = sum(1 for keyword in strategy_keywords if keyword in content)
            if strategy_score > 0:
                score_details["category_scores"]["strategy_logic"] = strategy_score
                total_score += strategy_score * self.importance_weights["strategy_logic"]
                score_details["importance_factors"].append(f"策略逻辑:{strategy_score}")
            
            # 时间衰减因子 (越新越重要)
            hours_ago = (datetime.utcnow() - msg.created_at).total_seconds() / 3600
            time_decay = max(0.5, 1.0 - (hours_ago / 24))  # 24小时内线性衰减到0.5
            total_score *= time_decay
            score_details["time_decay_factor"] = time_decay
            
            # 会话类型优先级加权
            for priority_cat in priority_categories:
                if priority_cat in score_details["category_scores"]:
                    total_score *= 1.2  # 优先类别加权20%
                    score_details["importance_factors"].append("优先类别加权")
                    break
            
            score_details["total_score"] = total_score
            message_scores.append(score_details)
        
        return message_scores

    async def _optimize_window_size(
        self,
        message_scores: List[Dict[str, Any]],
        base_window: int,
        token_budget: int
    ) -> int:
        """优化窗口大小"""
        
        # 基于token预算的窗口上限
        max_messages_by_tokens = min(
            token_budget // self.avg_tokens_per_message,
            self.max_context_window
        )
        
        # 基于消息重要性的动态调整
        if not message_scores:
            return max(self.min_context_window, min(base_window, max_messages_by_tokens))
        
        # 计算高价值消息比例
        high_value_messages = sum(1 for msg in message_scores if msg["total_score"] > 3.0)
        high_value_ratio = high_value_messages / len(message_scores) if message_scores else 0
        
        # 动态调整系数
        complexity_factor = 1.0
        if high_value_ratio > 0.6:
            complexity_factor = 1.3  # 高复杂度对话，增大窗口
        elif high_value_ratio < 0.2:
            complexity_factor = 0.8  # 简单对话，减小窗口
        
        # 计算最终窗口大小
        optimal_window = int(base_window * complexity_factor)
        optimal_window = max(self.min_context_window, min(optimal_window, max_messages_by_tokens))
        
        return optimal_window

    async def _select_priority_messages(
        self,
        message_scores: List[Dict[str, Any]],
        window_size: int
    ) -> List[Dict[str, Any]]:
        """选择优先级最高的消息"""
        if not message_scores:
            return []
        
        # 按重要性评分排序
        sorted_messages = sorted(message_scores, key=lambda x: x["total_score"], reverse=True)
        
        # 确保包含最近的消息(前3条最新消息优先保留)
        recent_messages = sorted_messages[-3:] if len(sorted_messages) >= 3 else sorted_messages
        remaining_slots = max(0, window_size - len(recent_messages))
        
        # 从高分消息中选择剩余名额
        high_priority_messages = []
        for msg in sorted_messages:
            if msg not in recent_messages and len(high_priority_messages) < remaining_slots:
                high_priority_messages.append(msg)
        
        # 合并并按时间顺序排序
        selected_messages = recent_messages + high_priority_messages
        selected_messages.sort(key=lambda x: x["created_at"])
        
        return selected_messages[:window_size]

    def _analyze_importance_distribution(
        self, 
        message_scores: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析重要性分布"""
        if not message_scores:
            return {"total_messages": 0, "distribution": {}}
        
        distribution = {
            "high_importance": sum(1 for msg in message_scores if msg["total_score"] > 4.0),
            "medium_importance": sum(1 for msg in message_scores if 2.0 <= msg["total_score"] <= 4.0),
            "low_importance": sum(1 for msg in message_scores if msg["total_score"] < 2.0),
            "avg_score": sum(msg["total_score"] for msg in message_scores) / len(message_scores),
            "max_score": max(msg["total_score"] for msg in message_scores),
            "min_score": min(msg["total_score"] for msg in message_scores)
        }
        
        return {
            "total_messages": len(message_scores),
            "distribution": distribution
        }

    async def _generate_context_recommendations(
        self,
        session_type: str,
        optimal_window: int,
        total_messages: int
    ) -> List[str]:
        """生成上下文优化建议"""
        recommendations = []
        
        if optimal_window == self.max_context_window:
            recommendations.append("上下文窗口已达最大值，建议启用智能摘要功能")
        
        if total_messages > 50:
            recommendations.append("对话历史较长，建议定期生成上下文摘要")
        
        if session_type == "strategy":
            recommendations.append("策略开发会话，重点保留技术决策和参数设置相关消息")
        elif session_type == "debugging":
            recommendations.append("调试会话，优先保留错误信息和解决方案")
        
        if optimal_window < self.min_context_window * 2:
            recommendations.append("当前对话较简单，可适当增加探索性问题")
        
        return recommendations

    async def _default_context_config(self, session_id: str) -> Dict[str, Any]:
        """默认上下文配置"""
        return {
            "optimal_window_size": self.base_context_window,
            "selected_message_count": self.base_context_window,
            "selected_messages": [],
            "session_type": "general",
            "estimated_tokens": self.base_context_window * self.avg_tokens_per_message,
            "context_strategy": "default_fallback",
            "importance_distribution": {"total_messages": 0, "distribution": {}},
            "recommendations": ["使用默认上下文配置，建议增加对话深度"]
        }

    async def get_optimized_context(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        current_message: str = "",
        include_summary: bool = True
    ) -> List[ClaudeConversation]:
        """获取优化后的上下文消息列表"""
        try:
            # 计算最优上下文窗口
            context_config = await self.calculate_optimal_context_window(
                db, user_id, session_id, current_message
            )
            
            selected_messages = context_config["selected_messages"]
            
            # 如果上下文窗口超过10条消息，强制启用智能截断防止超时
            if context_config["optimal_window_size"] > 10:
                logger.warning(f"上下文窗口过大({context_config['optimal_window_size']})，启用智能截断防止超时 - 会话:{session_id}")
                # 保留最重要的8条消息
                if len(selected_messages) > 8:
                    original_count = len(selected_messages)
                    # 按重要性排序，保留前8条
                    # 兼容处理：检查selected_messages是否为字典还是ClaudeConversation对象
                    def get_score(x):
                        if isinstance(x, dict):
                            return x.get("total_score", 0)
                        else:
                            # 如果是ClaudeConversation对象，使用默认评分
                            return 1.0
                    sorted_messages = sorted(selected_messages, key=get_score, reverse=True)
                    selected_messages = sorted_messages[:8]
                    logger.info(f"智能截断完成 - 从{original_count}条消息截断到{len(selected_messages)}条 - 会话:{session_id}")
            
            # 转换选中的消息为ClaudeConversation对象
            if selected_messages:
                # 获取选中消息的实际对象
                # 兼容处理：检查selected_messages是否为字典还是ClaudeConversation对象
                message_ids = []
                for msg in selected_messages:
                    if isinstance(msg, dict):
                        message_ids.append(msg["message_id"])
                    else:
                        # 如果已经是ClaudeConversation对象，直接使用id
                        message_ids.append(msg.id)
                query = select(ClaudeConversation).where(
                    ClaudeConversation.id.in_(message_ids)
                ).order_by(ClaudeConversation.created_at.asc())
                
                result = await db.execute(query)
                return result.scalars().all()
            
            return []
            
        except Exception as e:
            logger.error(f"获取优化上下文失败: {e}")
            # 回退到基础上下文获取
            query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.message_type.in_(["user", "assistant"])
                )
            ).order_by(desc(ClaudeConversation.created_at)).limit(self.base_context_window)
            
            result = await db.execute(query)
            return list(reversed(result.scalars().all()))

    async def analyze_context_efficiency(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """分析上下文使用效率"""
        try:
            all_messages = await self._get_all_messages(db, user_id, session_id)
            if not all_messages:
                return {"efficiency": "N/A", "analysis": "无消息历史"}
            
            message_scores = await self._calculate_message_importance(
                all_messages, "general", ""
            )
            
            # 计算效率指标
            high_value_count = sum(1 for msg in message_scores if msg["total_score"] > 3.0)
            efficiency_ratio = high_value_count / len(message_scores) if message_scores else 0
            
            analysis = {
                "total_messages": len(all_messages),
                "high_value_messages": high_value_count,
                "efficiency_ratio": round(efficiency_ratio, 3),
                "efficiency_grade": self._grade_efficiency(efficiency_ratio),
                "token_utilization": len(all_messages) * self.avg_tokens_per_message,
                "recommendations": []
            }
            
            # 生成优化建议
            if efficiency_ratio < 0.3:
                analysis["recommendations"].append("对话效率偏低，建议增加技术深度")
            if len(all_messages) > 40:
                analysis["recommendations"].append("消息数量较多，建议启用智能摘要")
            if efficiency_ratio > 0.7:
                analysis["recommendations"].append("对话效率很高，保持当前节奏")
            
            return analysis
            
        except Exception as e:
            logger.error(f"分析上下文效率失败: {e}")
            return {"efficiency": "ERROR", "analysis": str(e)}

    def _grade_efficiency(self, ratio: float) -> str:
        """效率等级评定"""
        if ratio >= 0.7:
            return "A+ 优秀"
        elif ratio >= 0.5:
            return "A 良好"
        elif ratio >= 0.3:
            return "B 一般"
        elif ratio >= 0.1:
            return "C 偏低"
        else:
            return "D 需要改进"


# 全局实例
dynamic_context_manager = DynamicContextManager()