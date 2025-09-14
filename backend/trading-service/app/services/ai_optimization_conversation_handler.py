"""
AI优化对话处理器

处理回测结果不达标后的优化建议对话流程
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from app.services.enhanced_auto_backtest_service import EnhancedAutoBacktestService, BacktestResultsFormatter
from app.services.strategy_optimization_advisor import StrategyOptimizationAdvisor
from app.services.ai_service import AIService
from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class AIOptimizationConversationHandler:
    """AI优化对话处理器"""
    
    def __init__(self):
        self.conversation_states = {}  # {session_id: conversation_state}
    
    async def _get_claude_client(self) -> Optional[ClaudeClient]:
        """获取Claude客户端实例"""
        try:
            account = await claude_account_service.select_best_account()
            if not account:
                logger.error("没有可用的Claude账号")
                return None
            
            decrypted_api_key = await claude_account_service.get_decrypted_api_key(account.id)
            if not decrypted_api_key:
                logger.error("无法获取解密的API密钥")
                return None
            
            return ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
        except Exception as e:
            logger.error(f"获取Claude客户端失败: {e}")
            return None
    
    async def handle_backtest_result_with_optimization(
        self,
        backtest_results: Dict[str, Any],
        original_strategy_code: str,
        user_intent: Dict[str, Any],
        session_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        处理回测结果并启动优化对话
        
        Args:
            backtest_results: 增强回测结果
            original_strategy_code: 原始策略代码
            user_intent: 用户原始意图
            session_id: 会话ID  
            user_id: 用户ID
            
        Returns:
            对话响应结果
        """
        try:
            is_satisfactory = backtest_results.get("is_satisfactory", False)
            
            if is_satisfactory:
                # 策略达标，返回成功消息
                return await self._handle_satisfactory_result(backtest_results, session_id)
            else:
                # 策略不达标，启动优化对话
                return await self._start_optimization_conversation(
                    backtest_results, original_strategy_code, user_intent, session_id, user_id
                )
        
        except Exception as e:
            logger.error(f"处理优化对话异常: {e}")
            return {
                "success": False,
                "message": f"优化建议生成失败: {str(e)}",
                "requires_user_input": False
            }
    
    async def _handle_satisfactory_result(
        self,
        backtest_results: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """处理达标结果"""
        
        grade = backtest_results.get("performance_grade", "B")
        summary = backtest_results.get("user_friendly_summary", "")
        
        success_message = f"{summary}\n\n"
        success_message += f"🎉 **恭喜！** 您的策略达到了 **{grade}级** 标准！\n\n"
        success_message += "📈 **下一步建议**:\n"
        success_message += "1. 在不同市场环境下进行更多回测\n"
        success_message += "2. 考虑少量资金试验实盘交易\n"
        success_message += "3. 持续监控策略表现并调整\n\n"
        success_message += "您还需要我帮您分析其他策略，还是有其他问题？"
        
        return {
            "success": True,
            "message": success_message,
            "requires_user_input": True,
            "optimization_needed": False,
            "backtest_grade": grade
        }
    
    async def _start_optimization_conversation(
        self,
        backtest_results: Dict[str, Any],
        original_strategy_code: str,
        user_intent: Dict[str, Any],
        session_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """启动优化对话流程"""
        
        try:
            # 保存对话状态
            self.conversation_states[session_id] = {
                "stage": "optimization_started",
                "backtest_results": backtest_results,
                "original_strategy_code": original_strategy_code,
                "user_intent": user_intent,
                "optimization_suggestions": backtest_results.get("optimization_suggestions", {}),
                "current_focus": None,
                "user_preferences": {},
                "started_at": datetime.now().isoformat()
            }
            
            # 格式化结果消息
            formatted_message = BacktestResultsFormatter.format_for_ai_conversation(backtest_results)
            
            # 添加优化选项
            formatted_message += "\n🎯 **优化方式选择**:\n"
            formatted_message += "1. 📝 **详细解释** - 我来解释每个问题的成因和解决方案\n"
            formatted_message += "2. 🤖 **AI自动优化** - 我直接生成优化后的策略代码\n"
            formatted_message += "3. 🧪 **参数调优** - 智能调整技术指标参数\n"
            formatted_message += "4. 🔄 **逐步优化** - 一个问题一个问题地改进\n\n"
            formatted_message += "请告诉我您希望采用哪种优化方式？"
            
            return {
                "success": True,
                "message": formatted_message,
                "requires_user_input": True,
                "optimization_needed": True,
                "available_options": ["detailed_explanation", "auto_optimize", "parameter_tuning", "step_by_step"],
                "conversation_stage": "optimization_started"
            }
            
        except Exception as e:
            logger.error(f"启动优化对话失败: {e}")
            return {
                "success": False,
                "message": f"启动优化对话失败: {str(e)}",
                "requires_user_input": False
            }
    
    async def handle_optimization_user_response(
        self,
        user_message: str,
        session_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """处理用户的优化对话响应"""
        
        if session_id not in self.conversation_states:
            return {
                "success": False,
                "message": "对话状态丢失，请重新开始策略优化",
                "requires_user_input": False
            }
        
        state = self.conversation_states[session_id]
        current_stage = state.get("stage", "")
        
        try:
            if current_stage == "optimization_started":
                return await self._handle_optimization_choice(user_message, session_id, user_id, state)
            elif current_stage == "detailed_explanation":
                return await self._handle_explanation_followup(user_message, session_id, user_id, state)
            elif current_stage == "auto_optimize":
                return await self._handle_auto_optimize_request(user_message, session_id, user_id, state)
            elif current_stage == "parameter_tuning":
                return await self._handle_parameter_tuning(user_message, session_id, user_id, state)
            elif current_stage == "step_by_step":
                return await self._handle_step_by_step(user_message, session_id, user_id, state)
            else:
                return await self._handle_general_optimization_query(user_message, session_id, user_id, state)
        
        except Exception as e:
            logger.error(f"处理优化对话响应异常: {e}")
            return {
                "success": False,
                "message": f"处理优化建议失败: {str(e)}",
                "requires_user_input": False
            }
    
    async def _handle_optimization_choice(
        self,
        user_message: str,
        session_id: str,
        user_id: int,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理用户的优化方式选择"""
        
        message_lower = user_message.lower().replace(" ", "")
        
        if any(word in message_lower for word in ["详细", "解释", "1", "第一"]):
            return await self._provide_detailed_explanation(session_id, state)
        elif any(word in message_lower for word in ["自动", "ai", "2", "第二", "直接生成"]):
            return await self._start_auto_optimization(session_id, state)
        elif any(word in message_lower for word in ["参数", "调优", "3", "第三"]):
            return await self._start_parameter_tuning(session_id, state)
        elif any(word in message_lower for word in ["逐步", "一个", "4", "第四"]):
            return await self._start_step_by_step_optimization(session_id, state)
        else:
            # 默认提供详细解释
            return await self._provide_detailed_explanation(session_id, state)
    
    async def _provide_detailed_explanation(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提供详细问题解释"""
        
        optimization_suggestions = state.get("optimization_suggestions", {})
        identified_issues = optimization_suggestions.get("identified_issues", [])
        improvement_plan = optimization_suggestions.get("improvement_plan", [])
        
        if not identified_issues:
            return {
                "success": False,
                "message": "优化建议数据缺失，请重新生成策略",
                "requires_user_input": False
            }
        
        explanation = "📋 **策略问题详细分析**:\n\n"
        
        for i, issue in enumerate(identified_issues[:3], 1):
            severity_emoji = "🔴" if issue["severity"] == "high" else "🟡" if issue["severity"] == "medium" else "🟢"
            explanation += f"## {i}. {severity_emoji} {issue['description']} (严重程度: {issue['severity']})\n\n"
            explanation += f"**当前值**: {issue['current_value']}\n"
            explanation += f"**目标值**: {issue['target_value']}\n"
            explanation += f"**影响**: {issue['impact']}\n\n"
            
            # 找到对应的改进计划
            matching_plan = next(
                (plan for plan in improvement_plan if plan.get("issue_type") == issue["type"]), 
                None
            )
            
            if matching_plan:
                explanation += "**具体解决方案**:\n"
                for action in matching_plan.get("actions", [])[:3]:
                    explanation += f"• {action}\n"
                
                ai_suggestions = matching_plan.get("ai_suggestions", [])
                if ai_suggestions:
                    explanation += "\n**AI深度建议**:\n"
                    for suggestion in ai_suggestions[:2]:
                        explanation += f"• {suggestion}\n"
                explanation += "\n"
            
            explanation += "---\n\n"
        
        explanation += "🤔 **接下来您希望**:\n"
        explanation += "• 让我直接生成优化后的代码\n"
        explanation += "• 针对某个具体问题进行深入讨论\n"
        explanation += "• 先从最严重的问题开始逐步优化\n\n"
        explanation += "请告诉我您的选择！"
        
        # 更新状态
        self.conversation_states[session_id]["stage"] = "detailed_explanation"
        
        return {
            "success": True,
            "message": explanation,
            "requires_user_input": True,
            "conversation_stage": "detailed_explanation"
        }
    
    async def _start_auto_optimization(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """开始AI自动优化"""
        
        original_code = state.get("original_strategy_code", "")
        optimization_suggestions = state.get("optimization_suggestions", {})
        
        if not original_code:
            return {
                "success": False,
                "message": "原始策略代码缺失，无法进行自动优化",
                "requires_user_input": False
            }
        
        # 更新状态
        self.conversation_states[session_id]["stage"] = "auto_optimize"
        
        response = "🤖 **AI自动优化启动中...**\n\n"
        response += "我正在基于以下优化建议重新生成策略代码:\n\n"
        
        priority_actions = optimization_suggestions.get("priority_actions", [])
        for i, action in enumerate(priority_actions[:3], 1):
            response += f"{i}. {action}\n"
        
        response += "\n⏳ **优化进度**:\n"
        response += "• 分析原始策略结构 ✅\n"
        response += "• 应用优化建议 🔄\n"
        response += "• 生成改进代码 ⏭️\n"
        response += "• 验证优化效果 ⏭️\n\n"
        response += "预计需要30-60秒，请稍等..."
        
        # 启动异步优化任务
        asyncio.create_task(self._execute_auto_optimization(session_id, state))
        
        return {
            "success": True,
            "message": response,
            "requires_user_input": False,
            "conversation_stage": "auto_optimize",
            "is_processing": True
        }
    
    async def _execute_auto_optimization(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """执行自动优化（异步任务）"""
        
        try:
            original_code = state.get("original_strategy_code", "")
            optimization_suggestions = state.get("optimization_suggestions", {})
            user_intent = state.get("user_intent", {})
            
            # 构建优化提示词
            optimization_prompt = self._build_optimization_prompt(
                original_code, optimization_suggestions, user_intent
            )
            
            # 调用Claude生成优化代码
            claude_client = await self._get_claude_client()
            if not claude_client:
                logger.error("无法获取Claude客户端")
                return
                
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": optimization_prompt}],
                system="你是专业的量化策略优化师，擅长根据回测结果优化交易策略。",
                temperature=0.3
            )
            
            # Handle chat_completion response format
            try:
                content = ""
                if "content" in response and isinstance(response["content"], list):
                    # Extract text from content array
                    for item in response["content"]:
                        if item.get("type") == "text":
                            content = item.get("text", "")
                            break
                elif isinstance(response.get("content"), str):
                    content = response["content"]
                else:
                    content = str(response.get("content", ""))
                
                if content:
                    optimized_code = self._extract_optimized_code(content)
                    
                    # 保存优化结果
                    self.conversation_states[session_id].update({
                        "optimized_code": optimized_code,
                        "optimization_complete": True,
                        "stage": "optimization_complete"
                    })
                    
                    logger.info(f"策略自动优化完成: session={session_id}")
                else:
                    logger.error("AI返回空内容")
                    
            except Exception as e:
                logger.error(f"处理AI优化响应失败: {e}")
                self.conversation_states[session_id].update({
                    "optimization_error": str(e),
                    "stage": "optimization_error"
                })
                
        except Exception as e:
            logger.error(f"执行自动优化异常: {e}")
    
    def _build_optimization_prompt(
        self,
        original_code: str,
        optimization_suggestions: Dict[str, Any],
        user_intent: Dict[str, Any]
    ) -> str:
        """构建优化提示词"""
        
        prompt = f"""
请根据以下回测分析结果，优化这个交易策略：

原始策略代码:
```python
{original_code}
```

识别的主要问题:
{json.dumps(optimization_suggestions.get("identified_issues", []), indent=2, ensure_ascii=False)}

改进建议:
{json.dumps(optimization_suggestions.get("improvement_plan", []), indent=2, ensure_ascii=False)}

用户原始需求:
{json.dumps(user_intent, indent=2, ensure_ascii=False)}

请生成优化后的策略代码，重点解决以下问题：
1. 如果存在负收益问题，检查交易信号逻辑
2. 如果回撤过大，加强止损和风险控制
3. 如果夏普比率低，提升信号质量
4. 如果胜率低，优化入场条件
5. 如果交易频率不合适，调整信号触发条件

优化要求：
- 保持原策略的核心逻辑
- 根据问题优先级进行针对性改进
- 确保代码完整可执行
- 添加清晰的注释说明优化点

请返回完整的优化策略代码。
        """
        
        return prompt
    
    def _extract_optimized_code(self, ai_response: str) -> str:
        """从AI响应中提取优化的代码"""
        
        # 提取代码块
        if "```python" in ai_response:
            code_start = ai_response.find("```python") + 9
            code_end = ai_response.find("```", code_start)
            return ai_response[code_start:code_end].strip()
        elif "```" in ai_response:
            code_start = ai_response.find("```") + 3
            code_end = ai_response.find("```", code_start)
            return ai_response[code_start:code_end].strip()
        else:
            return ai_response.strip()
    
    async def _start_parameter_tuning(
        self,
        session_id: str, 
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """开始参数调优"""
        
        # 更新状态
        self.conversation_states[session_id]["stage"] = "parameter_tuning"
        
        response = "🧪 **智能参数调优模式**\n\n"
        response += "我将帮您优化策略中的技术指标参数。\n\n"
        response += "**可调优参数类型**:\n"
        response += "• 移动平均线周期 (MA, EMA)\n"
        response += "• RSI超买超卖阈值\n"
        response += "• MACD参数组合\n"
        response += "• 布林带标准差倍数\n"
        response += "• 止损止盈比例\n\n"
        response += "请告诉我您希望重点优化哪类参数？或者让我自动识别需要优化的参数？"
        
        return {
            "success": True,
            "message": response,
            "requires_user_input": True,
            "conversation_stage": "parameter_tuning"
        }
    
    async def _start_step_by_step_optimization(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """开始逐步优化"""
        
        optimization_suggestions = state.get("optimization_suggestions", {})
        identified_issues = optimization_suggestions.get("identified_issues", [])
        
        if not identified_issues:
            return {
                "success": False,
                "message": "没有找到需要优化的问题",
                "requires_user_input": False
            }
        
        # 找出最严重的问题
        high_priority_issues = [issue for issue in identified_issues if issue["severity"] == "high"]
        current_issue = high_priority_issues[0] if high_priority_issues else identified_issues[0]
        
        # 更新状态
        self.conversation_states[session_id].update({
            "stage": "step_by_step",
            "current_issue": current_issue,
            "remaining_issues": identified_issues[1:]
        })
        
        response = f"🔄 **逐步优化模式** (共{len(identified_issues)}个问题)\n\n"
        response += f"我们先解决最重要的问题:\n\n"
        
        severity_emoji = "🔴" if current_issue["severity"] == "high" else "🟡" if current_issue["severity"] == "medium" else "🟢"
        response += f"{severity_emoji} **{current_issue['description']}**\n\n"
        response += f"**当前表现**: {current_issue['current_value']}\n"
        response += f"**目标表现**: {current_issue['target_value']}\n"
        response += f"**主要影响**: {current_issue['impact']}\n\n"
        
        # 提供具体解决建议
        improvement_plan = optimization_suggestions.get("improvement_plan", [])
        matching_plan = next(
            (plan for plan in improvement_plan if plan.get("issue_type") == current_issue["type"]), 
            None
        )
        
        if matching_plan:
            response += "**解决方案**:\n"
            for i, action in enumerate(matching_plan.get("actions", [])[:3], 1):
                response += f"{i}. {action}\n"
        
        response += "\n您希望我直接实施这些改进，还是需要我详细解释每个解决方案？"
        
        return {
            "success": True,
            "message": response,
            "requires_user_input": True,
            "conversation_stage": "step_by_step",
            "current_issue_type": current_issue["type"]
        }
    
    def get_conversation_stage(self, session_id: str) -> Optional[str]:
        """获取对话阶段"""
        return self.conversation_states.get(session_id, {}).get("stage")
    
    def clear_conversation_state(self, session_id: str) -> None:
        """清除对话状态"""
        if session_id in self.conversation_states:
            del self.conversation_states[session_id]


# 全局实例
ai_optimization_handler = AIOptimizationConversationHandler()