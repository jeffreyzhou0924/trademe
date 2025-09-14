"""
协作式策略优化器辅助方法

包含回测结果处理、循环优化等辅助功能
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class CollaborativeOptimizerHelpers:
    """协作优化器辅助方法类"""
    
    @staticmethod
    async def _get_claude_client() -> Optional[ClaudeClient]:
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
    
    @staticmethod
    async def generate_solution_summary(
        user_choice: str,
        state: Dict[str, Any]
    ) -> str:
        """生成解决方案摘要"""
        
        optimization_analysis = state.get("optimization_analysis", {})
        identified_issues = optimization_analysis.get("identified_issues", [])
        
        # 找出最高优先级的问题
        high_priority_issues = [issue for issue in identified_issues if issue["severity"] == "high"]
        primary_issue = high_priority_issues[0] if high_priority_issues else identified_issues[0] if identified_issues else None
        
        summary = f"**针对问题**: {primary_issue['description'] if primary_issue else '策略优化'}\n"
        summary += f"**用户选择**: {user_choice}\n"
        summary += f"**改进目标**: "
        
        if primary_issue:
            summary += f"将{primary_issue['description']}从 {primary_issue['current_value']} 改善至 {primary_issue['target_value']}"
        else:
            summary += "整体提升策略表现"
        
        return summary
    
    @staticmethod
    async def generate_confirmation_clarification(
        user_message: str,
        state: Dict[str, Any]
    ) -> str:
        """生成确认澄清响应"""
        
        user_chosen_solution = state.get("user_chosen_solution", "")
        
        prompt = f"""
用户正在确认优化方案，但可能需要进一步澄清。

用户选择的方案: {user_chosen_solution}
用户最新消息: "{user_message}"

请作为专业顾问：
1. 理解用户的疑虑或需要澄清的地方
2. 进一步确认实施细节
3. 确保方案的可行性和用户的理解
4. 引导用户明确确认或提出调整

保持友好和耐心。
        """
        
        try:
            claude_client = await CollaborativeOptimizerHelpers._get_claude_client()
            if not claude_client:
                return "请明确告诉我您是否确认这个优化方案，或者需要调整哪些地方？"
                
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system="你是耐心的量化策略优化顾问，帮助用户明确优化方案。",
                temperature=0.5
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
                    return content + "\n\n请明确回复"确认"开始生成代码，或告诉我需要调整的地方。"
                else:
                    return "让我们再确认一下细节。您对这个优化方案还有什么担心的地方吗？"
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                return "让我们再确认一下细节。您对这个优化方案还有什么担心的地方吗？"
        
        except Exception as e:
            logger.error(f"生成确认澄清失败: {e}")
            return "请明确告诉我您是否确认这个优化方案，或者需要调整哪些地方？"
    
    @staticmethod
    async def handle_post_generation_discussion(
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理代码生成后的讨论"""
        
        if state.get("backtest_complete"):
            # 回测已完成，展示结果
            return CollaborativeOptimizerHelpers._present_optimization_results(session_id, state)
        else:
            # 回测还在进行中
            return {
                "success": True,
                "message": "✅ 优化代码已生成完成！\n\n🚀 正在自动进行回测验证，请稍等约30秒...\n\n回测完成后我会立即为您展示优化效果对比。",
                "stage": "awaiting_backtest",
                "requires_user_input": False,
                "is_processing": True
            }
    
    @staticmethod
    def _present_optimization_results(
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """展示优化结果"""
        
        original_results = state.get("backtest_results", {})
        new_results = state.get("new_backtest_results", {})
        
        # 更新状态到结果审查阶段
        state["stage"] = "backtest_review"
        
        message = "🎉 **策略优化完成！让我们看看效果**\n\n"
        
        # 对比原始和优化后的结果
        original_performance = original_results.get("backtest_results", {}).get("performance", {})
        new_performance = new_results.get("backtest_results", {}).get("performance", {})
        
        message += "📊 **优化效果对比**:\n\n"
        
        # 收益率对比
        orig_return = original_performance.get("total_return", 0)
        new_return = new_performance.get("total_return", 0)
        return_change = new_return - orig_return
        return_emoji = "📈" if return_change > 0 else "📉" if return_change < 0 else "➡️"
        
        message += f"**总收益率**:\n"
        message += f"• 优化前: {orig_return:.1%}\n"
        message += f"• 优化后: {new_return:.1%}\n"
        message += f"• 改进: {return_emoji} {return_change:+.1%}\n\n"
        
        # 夏普比率对比
        orig_sharpe = original_performance.get("sharpe_ratio", 0)
        new_sharpe = new_performance.get("sharpe_ratio", 0)
        sharpe_change = new_sharpe - orig_sharpe
        sharpe_emoji = "📈" if sharpe_change > 0 else "📉" if sharpe_change < 0 else "➡️"
        
        message += f"**夏普比率**:\n"
        message += f"• 优化前: {orig_sharpe:.2f}\n"
        message += f"• 优化后: {new_sharpe:.2f}\n"
        message += f"• 改进: {sharpe_emoji} {sharpe_change:+.2f}\n\n"
        
        # 最大回撤对比
        orig_drawdown = abs(original_performance.get("max_drawdown", 0))
        new_drawdown = abs(new_performance.get("max_drawdown", 0))
        drawdown_change = new_drawdown - orig_drawdown
        drawdown_emoji = "💚" if drawdown_change < 0 else "❌" if drawdown_change > 0 else "➡️"
        
        message += f"**最大回撤**:\n"
        message += f"• 优化前: {orig_drawdown:.1%}\n"
        message += f"• 优化后: {new_drawdown:.1%}\n"
        message += f"• 改进: {drawdown_emoji} {drawdown_change:+.1%}\n\n"
        
        # 整体评价
        original_grade = original_results.get("performance_grade", "F")
        new_grade = new_results.get("performance_grade", "F")
        
        message += f"**策略等级**: {original_grade} → {new_grade}\n\n"
        
        # 判断优化是否成功
        improvements = []
        if return_change > 0.01:  # 收益率提升1%以上
            improvements.append("收益率显著提升")
        if sharpe_change > 0.1:   # 夏普比率提升0.1以上
            improvements.append("风险调整收益改善")
        if drawdown_change < -0.02:  # 回撤减少2%以上
            improvements.append("风险控制加强")
        
        if improvements:
            message += f"✅ **优化成功**: {', '.join(improvements)}\n\n"
            message += "🎯 **您对这个优化效果满意吗？**\n"
            message += "• 如果满意，我们可以保存这个优化策略\n"
            message += "• 如果希望进一步改进，我们可以继续优化其他问题\n"
            message += "• 您也可以询问任何关于优化结果的问题"
        else:
            message += "⚠️ **优化效果有限**: 可能需要尝试其他改进方案\n\n"
            message += "💡 **建议**:\n"
            message += "• 我们可以尝试另一种优化方案\n"
            message += "• 深入分析其他潜在问题\n"
            message += "• 调整优化的参数和力度\n\n"
            message += "您希望如何继续？"
        
        return {
            "success": True,
            "message": message,
            "stage": "backtest_review",
            "requires_user_input": True,
            "optimization_results": {
                "original_grade": original_grade,
                "new_grade": new_grade,
                "improvements": improvements,
                "return_improvement": return_change,
                "sharpe_improvement": sharpe_change,
                "drawdown_improvement": drawdown_change
            }
        }
    
    @staticmethod
    def is_user_satisfied_with_results(user_message: str) -> bool:
        """判断用户是否满意结果"""
        
        satisfaction_keywords = [
            "满意", "很好", "不错", "可以", "挺好", "ok", "好的",
            "满足", "达到", "够了", "完成", "结束", "保存"
        ]
        
        message_lower = user_message.lower().replace(" ", "")
        return any(keyword in message_lower for keyword in satisfaction_keywords)
    
    @staticmethod
    def is_user_wanting_further_optimization(user_message: str) -> bool:
        """判断用户是否希望进一步优化"""
        
        continue_keywords = [
            "继续", "再次", "进一步", "还能", "更好", "优化",
            "改进", "提升", "再来", "下一步", "其他问题"
        ]
        
        message_lower = user_message.lower().replace(" ", "")
        return any(keyword in message_lower for keyword in continue_keywords)
    
    @staticmethod
    async def discuss_backtest_results(
        user_message: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """讨论回测结果"""
        
        optimization_results = state.get("optimization_results", {})
        new_results = state.get("new_backtest_results", {})
        
        prompt = f"""
用户正在讨论策略优化后的回测结果。

用户消息: "{user_message}"

优化结果数据:
{json.dumps(optimization_results, indent=2, ensure_ascii=False)}

回测详细结果:
{json.dumps(new_results, indent=2, ensure_ascii=False)}

作为专业顾问，请:
1. 针对用户的疑问或关注点进行专业解答
2. 分析回测结果的具体含义
3. 解释优化效果的原因
4. 提供进一步的改进建议（如果需要）
5. 引导用户做出决策：满意结束还是继续优化

保持专业和教育性。
        """
        
        try:
            claude_client = await CollaborativeOptimizerHelpers._get_claude_client()
            if not claude_client:
                return {
                    "success": True,
                    "message": "让我们详细讨论这个回测结果。您对哪个指标有疑问？",
                    "stage": "backtest_review",
                    "requires_user_input": True
                }
                
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system="你是专业的量化交易结果分析师，善于解释回测数据和优化效果。",
                temperature=0.6
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
                    ai_response = content + "\n\n您对结果还有什么疑问，或者我们是否继续优化？"
                    
                    return {
                        "success": True,
                        "message": ai_response,
                        "stage": "backtest_review",
                        "requires_user_input": True
                    }
                else:
                    return {
                        "success": True,
                        "message": "让我们详细讨论这个回测结果。您对哪个指标有疑问？",
                        "stage": "backtest_review", 
                        "requires_user_input": True
                    }
                    
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                return {
                    "success": True,
                    "message": "让我们详细讨论这个回测结果。您对哪个指标有疑问？",
                    "stage": "backtest_review",
                    "requires_user_input": True
                }
        
        except Exception as e:
            logger.error(f"讨论回测结果失败: {e}")
            return {
                "success": True,
                "message": "您对这次优化的结果有什么看法？是否满意，或者希望继续改进？",
                "stage": "backtest_review",
                "requires_user_input": True
            }
    
    @staticmethod
    async def complete_optimization_cycle(
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """完成优化循环"""
        
        iteration_count = state.get("iteration_count", 1)
        optimization_results = state.get("optimization_results", {})
        
        message = "🎉 **策略优化成功完成！**\n\n"
        message += f"📈 **本次优化总结** (第{iteration_count}轮):\n"
        
        improvements = optimization_results.get("improvements", [])
        if improvements:
            for improvement in improvements:
                message += f"• ✅ {improvement}\n"
        
        return_improvement = optimization_results.get("return_improvement", 0)
        new_grade = optimization_results.get("new_grade", "N/A")
        
        message += f"\n🏆 **最终成果**:\n"
        message += f"• 策略等级: {new_grade}\n"
        message += f"• 收益提升: {return_improvement:+.1%}\n"
        message += f"• 优化轮次: {iteration_count}\n\n"
        
        message += "💾 **下一步**:\n"
        message += "• 优化后的策略已自动保存到您的策略库\n"
        message += "• 建议在不同市场环境下进一步测试\n"
        message += "• 可以考虑小资金实盘验证\n\n"
        message += "感谢您的耐心配合！有其他策略需要优化吗？"
        
        # 清理会话状态
        state["stage"] = "completed"
        
        return {
            "success": True,
            "message": message,
            "stage": "completed",
            "requires_user_input": True,
            "optimization_completed": True,
            "final_results": optimization_results
        }
    
    @staticmethod
    async def start_new_optimization_cycle(
        session_id: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """开始新的优化循环"""
        
        # 更新迭代计数
        current_iteration = state.get("iteration_count", 1)
        state["iteration_count"] = current_iteration + 1
        
        # 使用优化后的代码作为新的基准
        optimized_code = state.get("optimized_code", "")
        new_backtest_results = state.get("new_backtest_results", {})
        
        if optimized_code:
            state["original_code"] = optimized_code
            state["backtest_results"] = new_backtest_results
        
        message = f"🔄 **开始第{state['iteration_count']}轮优化**\n\n"
        message += "我将基于刚刚优化的策略，寻找进一步改进的机会。\n\n"
        message += "⏳ 正在分析当前策略的表现，识别新的优化点..."
        
        # 重新启动优化分析
        asyncio.create_task(
            CollaborativeOptimizerHelpers._restart_optimization_analysis(session_id, state)
        )
        
        return {
            "success": True,
            "message": message,
            "stage": "restarting_optimization",
            "requires_user_input": False,
            "is_processing": True,
            "iteration": state["iteration_count"]
        }
    
    @staticmethod
    async def _restart_optimization_analysis(
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """重新启动优化分析"""
        
        try:
            from app.services.collaborative_strategy_optimizer import collaborative_optimizer
            from app.services.strategy_optimization_advisor import StrategyOptimizationAdvisor
            
            # 获取当前策略和回测结果
            current_code = state.get("original_code", "")
            current_backtest = state.get("backtest_results", {})
            user_intent = state.get("user_intent", {})
            
            # 重新分析优化机会
            new_analysis = await StrategyOptimizationAdvisor.analyze_and_suggest(
                current_backtest.get("backtest_results", {}),
                user_intent,
                current_code
            )
            
            # 更新分析结果
            state["optimization_analysis"] = new_analysis
            state["stage"] = "explaining_issues"
            
            logger.info(f"重新启动优化分析完成: session={session_id}, iteration={state.get('iteration_count')}")
            
        except Exception as e:
            logger.error(f"重新启动优化分析失败: {e}")
            state.update({
                "restart_error": str(e),
                "stage": "restart_error"
            })


# 辅助函数导入到主类中
import asyncio