"""
协作式策略优化器

用户主导的策略优化对话系统：
1. 详细解释问题 → 2. 用户讨论决策 → 3. 方案确认 → 4. 生成代码 → 5. 回测验证 → 6. 循环改进
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from app.services.strategy_optimization_advisor import StrategyOptimizationAdvisor
from app.services.enhanced_auto_backtest_service import EnhancedAutoBacktestService
from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class CollaborativeStrategyOptimizer:
    """协作式策略优化器"""
    
    def __init__(self):
        # 对话状态管理 {session_id: ConversationState}
        self.conversations = {}
    
    @staticmethod
    async def _get_claude_client() -> Optional[ClaudeClient]:
        """获取Claude客户端实例"""
        try:
            account = await claude_account_service.select_best_account()
            if not account:
                return None
            
            decrypted_api_key = await claude_account_service.get_decrypted_api_key(account.id)
            if not decrypted_api_key:
                return None
            
            return ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
        except Exception as e:
            logger.error(f"Failed to get Claude client: {e}")
            return None
    
    async def start_collaborative_optimization(
        self,
        backtest_results: Dict[str, Any],
        original_strategy_code: str,
        user_intent: Dict[str, Any],
        session_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        启动协作式优化流程
        
        流程：问题诊断 → 详细解释 → 等待用户讨论
        """
        
        try:
            # 1. 问题诊断和分析
            optimization_analysis = await StrategyOptimizationAdvisor.analyze_and_suggest(
                backtest_results.get("backtest_results", {}),
                user_intent,
                original_strategy_code
            )
            
            if not optimization_analysis.get("identified_issues"):
                return {
                    "success": False,
                    "message": "未检测到明确的优化问题，回测结果可能已经较优",
                    "stage": "no_issues_found"
                }
            
            # 2. 保存对话状态
            conversation_state = {
                "stage": "explaining_issues",
                "session_id": session_id,
                "user_id": user_id,
                "original_code": original_strategy_code,
                "user_intent": user_intent,
                "backtest_results": backtest_results,
                "optimization_analysis": optimization_analysis,
                "iteration_count": 1,
                "discussed_issues": [],
                "confirmed_solutions": [],
                "pending_solutions": [],
                "conversation_history": [],
                "started_at": datetime.now().isoformat()
            }
            
            self.conversations[session_id] = conversation_state
            
            # 3. 生成详细问题解释
            explanation_message = await self._generate_detailed_explanation(
                optimization_analysis, backtest_results, session_id
            )
            
            logger.info(f"协作优化启动: session={session_id}, 问题数={len(optimization_analysis.get('identified_issues', []))}")
            
            return {
                "success": True,
                "message": explanation_message,
                "stage": "explaining_issues",
                "requires_user_input": True,
                "conversation_context": {
                    "total_issues": len(optimization_analysis.get("identified_issues", [])),
                    "performance_level": optimization_analysis.get("performance_level", "poor"),
                    "iteration": 1
                }
            }
            
        except Exception as e:
            logger.error(f"启动协作优化失败: {e}")
            return {
                "success": False,
                "message": f"优化启动失败: {str(e)}",
                "stage": "error"
            }
    
    async def continue_optimization_conversation(
        self,
        user_message: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        继续优化对话
        
        根据当前对话阶段和用户输入，推进优化流程
        """
        
        if session_id not in self.conversations:
            return {
                "success": False,
                "message": "对话会话已过期，请重新开始策略优化",
                "stage": "session_expired"
            }
        
        state = self.conversations[session_id]
        current_stage = state.get("stage", "")
        
        # 记录用户输入到对话历史
        state["conversation_history"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # 根据当前阶段处理用户输入
            if current_stage == "explaining_issues":
                return await self._handle_issue_discussion(user_message, session_id, state)
            elif current_stage == "discussing_solution":
                return await self._handle_solution_discussion(user_message, session_id, state)
            elif current_stage == "confirming_solution":
                return await self._handle_solution_confirmation(user_message, session_id, state)
            elif current_stage == "generating_code":
                return await self._handle_code_generation(user_message, session_id, state)
            elif current_stage == "backtest_review":
                return await self._handle_backtest_review(user_message, session_id, state)
            else:
                return await self._handle_general_discussion(user_message, session_id, state)
        
        except Exception as e:
            logger.error(f"处理优化对话异常: {e}")
            return {
                "success": False,
                "message": f"对话处理失败: {str(e)}",
                "stage": "error"
            }
    
    async def _generate_detailed_explanation(
        self,
        optimization_analysis: Dict[str, Any],
        backtest_results: Dict[str, Any],
        session_id: str
    ) -> str:
        """生成详细的问题解释"""
        
        identified_issues = optimization_analysis.get("identified_issues", [])
        performance = backtest_results.get("backtest_results", {}).get("performance", {})
        
        explanation = "🔍 **策略诊断报告**\n\n"
        
        # 回测结果摘要
        total_return = performance.get("total_return", 0)
        sharpe_ratio = performance.get("sharpe_ratio", 0)
        max_drawdown = abs(performance.get("max_drawdown", 0))
        win_rate = performance.get("win_rate", 0)
        
        explanation += f"📊 **当前表现**:\n"
        explanation += f"• 总收益率: {total_return:.1%} {'✅' if total_return > 0.05 else '❌'}\n"
        explanation += f"• 夏普比率: {sharpe_ratio:.2f} {'✅' if sharpe_ratio > 1.0 else '❌'}\n"
        explanation += f"• 最大回撤: {max_drawdown:.1%} {'✅' if max_drawdown < 0.15 else '❌'}\n"
        explanation += f"• 胜率: {win_rate:.1%} {'✅' if win_rate > 0.5 else '❌'}\n\n"
        
        explanation += "🚨 **发现的主要问题**:\n\n"
        
        # 详细解释每个问题
        for i, issue in enumerate(identified_issues, 1):
            severity_emoji = "🔴" if issue["severity"] == "high" else "🟡" if issue["severity"] == "medium" else "🟢"
            explanation += f"### {i}. {severity_emoji} {issue['description']} (严重程度: {issue['severity']})\n\n"
            
            explanation += f"**📈 数据分析**:\n"
            explanation += f"• 当前值: {issue['current_value']}\n"
            explanation += f"• 理想目标: {issue['target_value']}\n"
            explanation += f"• 对策略的影响: {issue['impact']}\n\n"
            
            # 详细解释问题成因
            explanation += f"**🔍 问题成因分析**:\n"
            explanation += await self._explain_issue_root_cause(issue["type"])
            explanation += "\n\n"
            
            # 可能的解决方向
            explanation += f"**💡 改进方向**:\n"
            improvement_plan = optimization_analysis.get("improvement_plan", [])
            matching_plan = next(
                (plan for plan in improvement_plan if plan.get("issue_type") == issue["type"]),
                None
            )
            
            if matching_plan:
                for action in matching_plan.get("actions", [])[:3]:
                    explanation += f"• {action}\n"
            
            explanation += "\n---\n\n"
        
        # AI专业建议
        ai_analysis = optimization_analysis.get("ai_analysis", {})
        if ai_analysis.get("success"):
            analysis_data = ai_analysis.get("analysis", {})
            if analysis_data.get("root_cause_analysis"):
                explanation += f"🎯 **AI专业分析**:\n"
                explanation += f"{analysis_data.get('root_cause_analysis')}\n\n"
        
        explanation += "💬 **让我们来讨论**:\n"
        explanation += "现在您已经了解了策略存在的问题，我们可以深入讨论任何一个问题。\n\n"
        explanation += "您可以:\n"
        explanation += "• 询问某个具体问题的更多细节\n"
        explanation += "• 讨论您对某个改进方向的看法\n"
        explanation += "• 分享您的策略设计思路\n"
        explanation += "• 提出您的优化想法\n\n"
        explanation += "**您最想先讨论哪个问题？或者有什么想法想和我分享？**"
        
        return explanation
    
    async def _explain_issue_root_cause(self, issue_type: str) -> str:
        """解释问题的根本成因"""
        
        explanations = {
            "negative_return": "策略产生负收益通常是因为:\n• 交易信号可能存在逻辑错误(买卖信号颠倒)\n• 市场环境与策略设计假设不符\n• 技术指标参数不适合当前市场周期\n• 缺乏有效的趋势或震荡过滤机制",
            
            "low_return": "收益率偏低可能的原因:\n• 入场时机不够精准，错过了最佳买卖点\n• 持仓时间过短，没有充分享受趋势收益\n• 仓位管理保守，没有在高胜率机会中加大投入\n• 技术指标过于滞后，信号来得太晚",
            
            "high_drawdown": "回撤过大的主要原因:\n• 缺乏有效的止损机制\n• 单笔交易仓位过重\n• 在不利市场环境下继续交易\n• 连续亏损时没有降低仓位的保护机制",
            
            "low_sharpe": "夏普比率低表示风险调整收益不佳:\n• 策略波动性过大，但收益没有相应提升\n• 交易频率过高，产生过多噪音交易\n• 缺乏市场环境判断，在震荡市也频繁交易\n• 风险控制不足，亏损时损失过大",
            
            "low_win_rate": "胜率偏低通常是因为:\n• 入场条件过于宽松，信号质量不高\n• 缺乏有效的信号确认机制\n• 技术指标容易产生虚假突破信号\n• 没有过滤掉低质量的交易机会",
            
            "low_frequency": "交易频率过低可能因为:\n• 入场条件设置过于严格\n• 技术指标参数过大，信号稀少\n• 时间周期选择不当，错过交易机会\n• 市场品种选择限制了交易机会",
            
            "high_frequency": "交易频率过高的问题:\n• 入场标准过于宽松，接收到过多噪音信号\n• 缺乏信号确认时间，容易被市场噪音误导\n• 技术指标参数过小，过于敏感\n• 没有设置交易冷却期，过度交易",
            
            "poor_profit_factor": "盈亏比差的核心问题:\n• 止盈设置过于保守，盈利单没有充分获利\n• 止损设置过于宽松，亏损单损失过大\n• 缺乏趋势跟踪机制，无法让盈利单跑得更远\n• 出场策略不当，经常在趋势刚开始时就离场"
        }
        
        return explanations.get(issue_type, "这个问题需要进一步分析具体情况才能确定根本原因。")
    
    async def _handle_issue_discussion(
        self,
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理问题讨论阶段的用户输入"""
        
        # 使用AI分析用户的问题和关注点
        discussion_response = await self._analyze_user_concern_and_respond(
            user_message, state
        )
        
        # 记录AI响应
        state["conversation_history"].append({
            "role": "assistant",
            "content": discussion_response["message"],
            "timestamp": datetime.now().isoformat()
        })
        
        # 检查用户是否准备进入解决方案讨论阶段
        if self._is_user_ready_for_solution(user_message):
            state["stage"] = "discussing_solution"
            solution_discussion = await self._start_solution_discussion(session_id, state)
            return solution_discussion
        
        return {
            "success": True,
            "message": discussion_response["message"],
            "stage": "explaining_issues",
            "requires_user_input": True,
            "conversation_context": {
                "discussion_turn": len(state["conversation_history"]) // 2
            }
        }
    
    async def _analyze_user_concern_and_respond(
        self,
        user_message: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析用户关注点并生成响应"""
        
        optimization_analysis = state.get("optimization_analysis", {})
        identified_issues = optimization_analysis.get("identified_issues", [])
        
        # 构建上下文提示词
        context_prompt = f"""
用户正在讨论他们的交易策略优化问题。

策略存在的问题:
{json.dumps(identified_issues, indent=2, ensure_ascii=False)}

用户的最新消息: "{user_message}"

请作为专业的量化交易顾问，针对用户的关注点进行深入、教育性的回应。

回应要求:
1. 针对用户提到的具体问题进行详细解释
2. 提供教育性的见解，帮助用户理解问题的本质
3. 如果用户询问解决方案，提供2-3个具体的改进建议
4. 保持对话的互动性，引导用户继续深入思考
5. 如果用户表达了改进意向，询问他们的具体想法

回应风格要专业而友好，有教育价值。
        """
        
        try:
            claude_client = await self._get_claude_client()
            if not claude_client:
                return {
                    "success": True,
                    "message": "让我们继续讨论您关心的问题。您希望优先解决哪个方面的问题？"
                }
            
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": context_prompt}],
                system="你是一位经验丰富的量化交易策略顾问，擅长教育性地指导用户优化交易策略。",
                temperature=0.7
            )
            
            # Handle chat_completion response format
            ai_response = ""
            try:
                if "content" in response and isinstance(response["content"], list):
                    # Extract text from content array
                    for item in response["content"]:
                        if item.get("type") == "text":
                            ai_response = item.get("text", "")
                            break
                elif isinstance(response.get("content"), str):
                    ai_response = response["content"]
                else:
                    ai_response = str(response.get("content", ""))
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                ai_response = ""
            
            if ai_response:
                # 添加引导性结尾
                ai_response += "\n\n您对这个解释有什么想法吗？或者想深入讨论某个特定方面？"
                
                return {
                    "success": True,
                    "message": ai_response
                }
            else:
                return {
                    "success": True,
                    "message": "我需要更多信息来回答您的问题。能否详细说明您最关心的是哪个方面的问题？"
                }
        
        except Exception as e:
            logger.error(f"分析用户关注点失败: {e}")
            return {
                "success": True,
                "message": "让我们继续讨论您关心的问题。您希望优先解决哪个方面的问题？"
            }
    
    def _is_user_ready_for_solution(self, user_message: str) -> bool:
        """判断用户是否准备讨论解决方案"""
        
        solution_keywords = [
            "怎么解决", "如何改进", "怎么优化", "解决方案", "改进方案", 
            "我想改", "我们来改", "开始优化", "改进策略", "修改代码",
            "我同意", "可以开始", "那我们", "好的，我们"
        ]
        
        message_lower = user_message.lower().replace(" ", "")
        return any(keyword in message_lower for keyword in solution_keywords)
    
    async def _handle_solution_discussion(
        self,
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理解决方案讨论阶段"""
        
        # 分析用户对方案的选择和想法
        solution_analysis = await self._analyze_user_solution_preference(
            user_message, state
        )
        
        # 记录AI响应
        state["conversation_history"].append({
            "role": "assistant", 
            "content": solution_analysis["message"],
            "timestamp": datetime.now().isoformat()
        })
        
        # 检查用户是否确认了具体方案
        if self._is_user_confirming_solution(user_message):
            return await self._start_solution_confirmation(session_id, state, user_message)
        
        return {
            "success": True,
            "message": solution_analysis["message"],
            "stage": "discussing_solution",
            "requires_user_input": True
        }
    
    async def _handle_solution_confirmation(
        self,
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理解决方案确认阶段"""
        
        if self._is_user_final_confirmation(user_message):
            # 用户最终确认，开始生成代码
            return await self._start_code_generation(session_id, state)
        elif self._is_user_requesting_changes(user_message):
            # 用户要求修改方案
            state["stage"] = "discussing_solution"
            return {
                "success": True,
                "message": "好的，让我们重新讨论方案。您希望做哪些调整？",
                "stage": "discussing_solution",
                "requires_user_input": True
            }
        else:
            # 继续确认对话
            confirmation_response = await self._generate_confirmation_clarification(
                user_message, state
            )
            return {
                "success": True,
                "message": confirmation_response,
                "stage": "confirming_solution",
                "requires_user_input": True
            }
    
    async def _handle_code_generation(
        self,
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理代码生成阶段"""
        
        if state.get("code_generation_complete"):
            # 代码已生成，用户可能在询问或准备回测
            return await self._handle_post_generation_discussion(user_message, session_id, state)
        else:
            return {
                "success": True,
                "message": "⏳ 正在根据我们讨论的方案生成优化代码，请稍等...",
                "stage": "generating_code",
                "requires_user_input": False,
                "is_processing": True
            }
    
    async def _handle_backtest_review(
        self,
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理回测结果审查阶段"""
        
        # 分析用户对回测结果的反应
        if self._is_user_satisfied_with_results(user_message):
            # 用户满意，结束优化循环
            return await self._complete_optimization_cycle(session_id, state)
        elif self._is_user_wanting_further_optimization(user_message):
            # 用户希望进一步优化，开始新的循环
            return await self._start_new_optimization_cycle(session_id, state)
        else:
            # 继续讨论回测结果
            backtest_discussion = await self._discuss_backtest_results(
                user_message, session_id, state
            )
            return backtest_discussion
    
    async def _start_solution_discussion(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """开始解决方案讨论"""
        
        state["stage"] = "discussing_solution"
        
        optimization_analysis = state.get("optimization_analysis", {})
        identified_issues = optimization_analysis.get("identified_issues", [])
        
        # 按优先级排序问题
        high_priority_issues = [issue for issue in identified_issues if issue["severity"] == "high"]
        medium_priority_issues = [issue for issue in identified_issues if issue["severity"] == "medium"]
        
        priority_issues = high_priority_issues + medium_priority_issues
        
        message = "💡 **很好！让我们制定具体的改进方案**\n\n"
        
        if priority_issues:
            most_critical = priority_issues[0]
            message += f"我建议我们先重点解决最关键的问题:\n"
            message += f"🔴 **{most_critical['description']}**\n\n"
            
            # 提供具体的解决选项
            improvement_plan = optimization_analysis.get("improvement_plan", [])
            matching_plan = next(
                (plan for plan in improvement_plan if plan.get("issue_type") == most_critical["type"]),
                None
            )
            
            if matching_plan:
                message += "**我为您准备了几个解决方案**:\n\n"
                for i, action in enumerate(matching_plan.get("actions", [])[:3], 1):
                    message += f"**方案{i}**: {action}\n"
                    message += f"• 实施难度: {matching_plan.get('estimated_effort', 'medium')}\n"
                    message += f"• 预期效果: {matching_plan.get('expected_impact', 'moderate')}\n\n"
        
        message += "**您觉得哪个方案比较合适？或者您有其他的想法？**\n\n"
        message += "我们可以详细讨论任何一个方案的具体实施细节。"
        
        return {
            "success": True,
            "message": message,
            "stage": "discussing_solution",
            "requires_user_input": True
        }
    
    async def _analyze_user_solution_preference(
        self,
        user_message: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析用户的方案偏好"""
        
        optimization_analysis = state.get("optimization_analysis", {})
        
        prompt = f"""
用户正在讨论策略优化方案。

用户的消息: "{user_message}"

优化分析数据:
{json.dumps(optimization_analysis, indent=2, ensure_ascii=False)}

作为专业顾问，请:
1. 理解用户对哪个方案感兴趣或有疑问
2. 针对用户的具体关注点进行详细说明  
3. 如果用户选择了方案，详细解释该方案的实施细节
4. 如果用户有自己的想法，与我们的建议进行对比分析
5. 引导用户进一步明确方案的具体实施方式

保持教育性和互动性。
        """
        
        try:
            claude_client = await self._get_claude_client()
            if not claude_client:
                return {
                    "success": True,
                    "message": "让我们继续细化方案的具体实施步骤。您更倾向于哪种改进方式？"
                }
            
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system="你是量化交易策略优化专家，擅长引导用户制定具体的改进方案。",
                temperature=0.6
            )
            
            # Handle chat_completion response format
            ai_response = ""
            try:
                if "content" in response and isinstance(response["content"], list):
                    # Extract text from content array
                    for item in response["content"]:
                        if item.get("type") == "text":
                            ai_response = item.get("text", "")
                            break
                elif isinstance(response.get("content"), str):
                    ai_response = response["content"]
                else:
                    ai_response = str(response.get("content", ""))
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                ai_response = ""
            
            if ai_response:
                ai_response += "\n\n您对这个方案还有什么疑问，或者我们是否可以确定具体的实施细节？"
                
                return {
                    "success": True,
                    "message": ai_response
                }
            else:
                return {
                    "success": True,
                    "message": "让我们继续细化方案的具体实施步骤。您更倾向于哪种改进方式？"
                }
        
        except Exception as e:
            logger.error(f"分析用户方案偏好失败: {e}")
            return {
                "success": True,
                "message": "我们来具体讨论您选择的方案。您希望了解哪个方面的实施细节？"
            }
    
    def _is_user_confirming_solution(self, user_message: str) -> bool:
        """判断用户是否在确认解决方案"""
        
        confirmation_keywords = [
            "我选择", "我觉得", "方案", "这个好", "用这个", "就这样",
            "可以", "同意", "采用", "实施", "我想要", "我希望"
        ]
        
        message_lower = user_message.lower().replace(" ", "")
        return any(keyword in message_lower for keyword in confirmation_keywords)
    
    async def _start_solution_confirmation(
        self,
        session_id: str,
        state: Dict[str, Any],
        user_choice: str
    ) -> Dict[str, Any]:
        """开始解决方案确认流程"""
        
        state["stage"] = "confirming_solution"
        state["user_chosen_solution"] = user_choice
        
        # 生成确认摘要
        confirmation_summary = await self._generate_solution_summary(user_choice, state)
        
        message = "✅ **太好了！让我确认一下我们达成的方案**:\n\n"
        message += confirmation_summary
        message += "\n\n🔍 **实施细节**:\n"
        message += "• 我将根据这个方案修改您的策略代码\n"
        message += "• 保持核心交易逻辑不变，只优化存在问题的部分\n"  
        message += "• 生成代码后立即进行回测验证效果\n\n"
        message += "**您确认按照这个方案来优化策略吗？**\n"
        message += "(回复\"确认\"或\"是的\"开始生成代码，或告诉我需要调整的地方)"
        
        return {
            "success": True,
            "message": message,
            "stage": "confirming_solution", 
            "requires_user_input": True
        }
    
    def _is_user_final_confirmation(self, user_message: str) -> bool:
        """判断用户最终确认"""
        
        confirmation_phrases = [
            "确认", "是的", "好的", "开始", "生成", "可以",
            "同意", "没问题", "就这样", "ok", "yes"
        ]
        
        message_lower = user_message.lower().replace(" ", "").replace("，", "").replace("。", "")
        return any(phrase in message_lower for phrase in confirmation_phrases)
    
    def _is_user_requesting_changes(self, user_message: str) -> bool:
        """判断用户要求修改"""
        
        change_keywords = [
            "修改", "调整", "改一下", "不对", "换个", "重新",
            "不是", "不要", "改成", "变成", "另外"
        ]
        
        message_lower = user_message.lower().replace(" ", "")
        return any(keyword in message_lower for keyword in change_keywords)
    
    async def _start_code_generation(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """开始代码生成"""
        
        state["stage"] = "generating_code"
        
        # 启动异步代码生成任务
        asyncio.create_task(self._execute_collaborative_code_generation(session_id, state))
        
        message = "🤖 **正在生成优化代码...**\n\n"
        message += "⏳ **进度**:\n"
        message += "• 分析确认的优化方案 ✅\n"
        message += "• 应用改进到原始策略 🔄\n"
        message += "• 生成完整的优化代码 ⏭️\n"
        message += "• 准备自动回测验证 ⏭️\n\n"
        message += "**预计需要30-60秒，请稍等...**"
        
        return {
            "success": True,
            "message": message,
            "stage": "generating_code",
            "requires_user_input": False,
            "is_processing": True
        }
    
    async def _execute_collaborative_code_generation(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """执行协作式代码生成"""
        
        try:
            original_code = state.get("original_code", "")
            user_chosen_solution = state.get("user_chosen_solution", "")
            optimization_analysis = state.get("optimization_analysis", {})
            
            # 构建优化提示词
            optimization_prompt = f"""
基于与用户的详细讨论，请优化以下交易策略:

原始策略代码:
```python
{original_code}
```

用户确认的改进方案:
{user_chosen_solution}

详细分析结果:
{json.dumps(optimization_analysis, indent=2, ensure_ascii=False)}

优化要求:
1. 严格按照用户确认的方案进行修改
2. 保持原始策略的核心逻辑和结构
3. 针对识别的问题进行精确改进
4. 确保代码完整可执行
5. 添加清晰注释说明优化部分

请生成完整的优化策略代码。
            """
            
            # 获取正确的Claude客户端
            claude_client = await self._get_claude_client()
            if not claude_client:
                state.update({
                    "code_generation_error": "无法获取Claude客户端",
                    "stage": "generation_error"
                })
                return
            
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": optimization_prompt}],
                system="你是专业的量化策略优化师，严格按照用户确认的方案生成优化代码。",
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
                    
                    optimized_code = self._extract_code_from_response(content)
                    
                    # 保存优化结果
                    state.update({
                        "optimized_code": optimized_code,
                        "optimization_explanation": content,
                        "code_generation_complete": True,
                        "stage": "code_generated"
                    })
                    
                    # 自动触发回测
                    await self._trigger_automated_backtest(session_id, state)
                    
                    logger.info(f"协作代码生成完成: session={session_id}")
                else:
                    logger.error("空响应内容")
                    state.update({
                        "code_generation_error": "AI返回空内容",
                        "stage": "generation_error"
                    })
                    
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                state.update({
                    "code_generation_error": f"处理AI响应失败: {str(e)}",
                    "stage": "generation_error"
                })
                
        except Exception as e:
            logger.error(f"执行协作代码生成异常: {e}")
            state.update({
                "code_generation_error": str(e),
                "stage": "generation_error"  
            })
    
    def _extract_code_from_response(self, ai_response: str) -> str:
        """从AI响应中提取代码"""
        
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
    
    async def _trigger_automated_backtest(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """触发自动化回测"""
        
        try:
            optimized_code = state.get("optimized_code", "")
            user_intent = state.get("user_intent", {})
            user_id = state.get("user_id")
            
            if not optimized_code:
                logger.error("无优化代码，跳过回测")
                return
            
            # 执行回测
            backtest_result = await EnhancedAutoBacktestService.run_enhanced_backtest_with_suggestions(
                strategy_code=optimized_code,
                intent=user_intent,
                user_id=user_id,
                config={
                    "initial_capital": 10000,
                    "days_back": 30,
                    "symbol": "BTC-USDT-SWAP"
                }
            )
            
            # 保存回测结果
            state.update({
                "new_backtest_results": backtest_result,
                "backtest_complete": True,
                "stage": "backtest_complete"
            })
            
            logger.info(f"协作优化回测完成: session={session_id}, 等级={backtest_result.get('performance_grade', 'N/A')}")
            
        except Exception as e:
            logger.error(f"自动回测失败: {e}")
            state.update({
                "backtest_error": str(e),
                "stage": "backtest_error"
            })
    
    def clear_conversation(self, session_id: str) -> None:
        """清理对话状态"""
        if session_id in self.conversations:
            del self.conversations[session_id]
    
    def get_conversation_stage(self, session_id: str) -> Optional[str]:
        """获取对话阶段"""
        return self.conversations.get(session_id, {}).get("stage")


# 全局实例
collaborative_optimizer = CollaborativeStrategyOptimizer()