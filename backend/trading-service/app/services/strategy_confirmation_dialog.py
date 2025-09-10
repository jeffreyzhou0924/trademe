"""
策略确认对话管理器
实现渐进式确认机制，根据策略成熟度生成合适的用户确认提示
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StrategyConfirmationDialog:
    """策略确认对话管理器"""
    
    def __init__(self):
        # 确认类型配置
        self.confirmation_types = {
            "ready_confirmation": {
                "threshold": 71,  # 成熟可用以上主动询问确认
                "template": "strategy_ready",
                "action_required": True
            },
            "improvement_confirmation": {
                "threshold": 51,  # 相对完善时提供选择
                "template": "strategy_improvable", 
                "action_required": False
            },
            "discussion_guidance": {
                "threshold": 0,   # 需要继续讨论
                "template": "strategy_discussion",
                "action_required": False
            }
        }
        
        # 消息模板
        self.message_templates = {
            "strategy_ready": """✨ **策略讨论已经很完善！** (成熟度: {score:.0f}/100)

📊 **策略概述**:
• **策略类型**: {strategy_type}
• **技术指标**: {indicators}
• **时间周期**: {timeframe}
• **风险控制**: {risk_status}

🎯 **是否开始生成可执行的策略代码？**

生成的代码将包含：
• 完整的买入卖出逻辑
• 技术指标计算和信号判断
• 风险管理和仓位控制
• 回测验证和性能分析

👆 请回复 "**确认生成**" 开始创建您的专属策略，或继续讨论完善策略细节。""",

            "strategy_improvable": """🚧 **策略框架基本完整，建议完善以下细节** (成熟度: {score:.0f}/100):

{suggestions_text}

🤔 **两个选择**:
1️⃣ 回复 "**确认生成**" - 基于当前信息生成策略代码
2️⃣ 继续讨论 - 我们完善上述建议后再生成

💡 完善后的策略将有更好的稳定性和收益表现！""",

            "strategy_discussion": """💭 **让我们继续完善您的策略想法** (当前成熟度: {score:.0f}/100)

🔍 **当前缺失的关键信息**:
{missing_text}

💡 **建议优先讨论**:
{suggestions_text}

🗣️ 您可以详细描述：
• 具体的买入卖出条件
• 希望使用的技术指标和参数
• 风险控制和资金管理方式
• 适用的市场环境和时间框架

我会根据您的描述逐步完善策略框架！"""
        }

    async def generate_confirmation_prompt(
        self, 
        maturity_analysis: Dict[str, Any],
        user_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """
        生成用户确认提示
        
        Args:
            maturity_analysis: 成熟度分析结果
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            确认提示信息
        """
        
        try:
            total_score = maturity_analysis["total_score"]
            strategy_info = maturity_analysis["strategy_info"]
            
            # 确定确认类型
            confirmation_type = self._determine_confirmation_type(total_score)
            
            # 生成对应的提示消息
            if confirmation_type == "ready_confirmation":
                message = self._generate_ready_confirmation(maturity_analysis)
                action_type = "confirmation_required"
                
            elif confirmation_type == "improvement_confirmation":
                message = self._generate_improvement_confirmation(maturity_analysis)
                action_type = "optional_confirmation"
                
            else:  # discussion_guidance
                message = self._generate_discussion_guidance(maturity_analysis)
                action_type = "continue_discussion"
            
            return {
                "message": message,
                "confirmation_type": confirmation_type,
                "action_type": action_type,
                "requires_user_action": confirmation_type == "ready_confirmation",
                "maturity_score": total_score,
                "strategy_summary": self._extract_strategy_summary(strategy_info),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"生成确认提示失败: {str(e)}")
            return self._get_error_response(str(e))

    def _determine_confirmation_type(self, score: float) -> str:
        """根据分数确定确认类型"""
        
        if score >= 71:
            return "ready_confirmation"
        elif score >= 51:
            return "improvement_confirmation"
        else:
            return "discussion_guidance"

    def _generate_ready_confirmation(self, maturity_analysis: Dict[str, Any]) -> str:
        """生成策略就绪确认提示"""
        
        strategy_info = maturity_analysis["strategy_info"]
        score = maturity_analysis["total_score"]
        
        # 提取策略信息
        strategy_type = strategy_info.get("strategy_type", "自定义策略")
        indicators = ", ".join(strategy_info.get("indicators", [])) or "待配置"
        timeframe = strategy_info.get("timeframe", "待设定")
        
        # 风险控制状态
        risk_elements = []
        if strategy_info.get("stop_loss"):
            risk_elements.append("止损")
        if strategy_info.get("take_profit"):
            risk_elements.append("止盈")
        if strategy_info.get("position_sizing"):
            risk_elements.append("仓位管理")
            
        risk_status = "、".join(risk_elements) if risk_elements else "待完善"
        
        return self.message_templates["strategy_ready"].format(
            score=score,
            strategy_type=strategy_type,
            indicators=indicators,
            timeframe=timeframe,
            risk_status=risk_status
        )

    def _generate_improvement_confirmation(self, maturity_analysis: Dict[str, Any]) -> str:
        """生成改进建议确认"""
        
        suggestions = maturity_analysis.get("improvement_suggestions", [])
        score = maturity_analysis["total_score"]
        
        # 格式化建议文本
        suggestions_text = self._format_suggestions(suggestions[:3])
        
        return self.message_templates["strategy_improvable"].format(
            score=score,
            suggestions_text=suggestions_text
        )

    def _generate_discussion_guidance(self, maturity_analysis: Dict[str, Any]) -> str:
        """生成继续讨论的引导"""
        
        missing_elements = maturity_analysis.get("missing_elements", [])
        suggestions = maturity_analysis.get("improvement_suggestions", [])
        score = maturity_analysis["total_score"]
        
        # 格式化缺失要素
        missing_text = self._format_missing_elements(missing_elements[:4])
        
        # 格式化建议
        suggestions_text = self._format_suggestions(suggestions[:3])
        
        return self.message_templates["strategy_discussion"].format(
            score=score,
            missing_text=missing_text,
            suggestions_text=suggestions_text
        )

    def _format_suggestions(self, suggestions: List[Dict[str, Any]]) -> str:
        """格式化改进建议"""
        
        if not suggestions:
            return "• 当前策略框架基本合理，可以考虑生成"
        
        formatted_suggestions = []
        for suggestion in suggestions:
            priority_icon = {
                "critical": "🔴",
                "high": "🟡", 
                "medium": "🟢"
            }.get(suggestion.get("priority", "medium"), "⚪")
            
            formatted_suggestions.append(f"{priority_icon} **{suggestion.get('category', '建议')}**: {suggestion.get('suggestion', '')}")
        
        return "\n".join(formatted_suggestions)

    def _format_missing_elements(self, missing_elements: List[str]) -> str:
        """格式化缺失要素"""
        
        if not missing_elements:
            return "• 基本要素已齐备"
        
        return "\n".join([f"• {element}" for element in missing_elements])

    def _extract_strategy_summary(self, strategy_info: Dict[str, Any]) -> Dict[str, Any]:
        """提取策略摘要"""
        
        return {
            "type": strategy_info.get("strategy_type"),
            "indicators": strategy_info.get("indicators", []),
            "timeframe": strategy_info.get("timeframe"),
            "has_risk_management": bool(strategy_info.get("stop_loss") or strategy_info.get("take_profit")),
            "entry_conditions_count": len(strategy_info.get("entry_conditions", [])),
            "exit_conditions_count": len(strategy_info.get("exit_conditions", []))
        }

    def _get_error_response(self, error_message: str) -> Dict[str, Any]:
        """返回错误响应"""
        return {
            "message": f"生成确认提示时遇到问题: {error_message}",
            "confirmation_type": "error",
            "action_type": "retry",
            "requires_user_action": False,
            "error": error_message,
            "generated_at": datetime.now().isoformat()
        }

    async def parse_user_confirmation(self, user_response: str) -> Dict[str, Any]:
        """
        解析用户确认响应
        
        Args:
            user_response: 用户响应内容
            
        Returns:
            解析结果
        """
        
        try:
            user_response_lower = user_response.lower().strip()
            
            # 确认生成关键词
            confirmation_keywords = [
                "确认生成", "开始生成", "生成代码", "确认", "好的", "开始吧",
                "同意", "可以", "是的", "ok", "yes", "确定"
            ]
            
            # 继续讨论关键词
            discussion_keywords = [
                "继续讨论", "再想想", "完善一下", "不急", "等等", "先不生成",
                "再聊聊", "完善", "改进", "优化"
            ]
            
            # 检测确认意图
            is_confirmed = any(keyword in user_response_lower for keyword in confirmation_keywords)
            wants_discussion = any(keyword in user_response_lower for keyword in discussion_keywords)
            
            if is_confirmed and not wants_discussion:
                intent = "confirm_generation"
                confidence = 0.9
                action = "proceed_with_generation"
                
            elif wants_discussion:
                intent = "continue_discussion"
                confidence = 0.8
                action = "continue_refinement"
                
            else:
                # 模糊响应，根据长度和内容判断
                if len(user_response) > 20 and any(word in user_response_lower 
                    for word in ["策略", "指标", "条件", "风险", "参数"]):
                    intent = "continue_discussion"
                    confidence = 0.6
                    action = "continue_refinement"
                else:
                    intent = "unclear"
                    confidence = 0.3
                    action = "request_clarification"
            
            return {
                "intent": intent,
                "confidence": confidence,
                "action": action,
                "original_response": user_response,
                "parsed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"解析用户确认响应失败: {str(e)}")
            return {
                "intent": "error",
                "confidence": 0.0,
                "action": "handle_error",
                "error": str(e),
                "original_response": user_response,
                "parsed_at": datetime.now().isoformat()
            }

    def generate_clarification_request(self) -> str:
        """生成澄清请求"""
        
        return """🤔 **请明确您的选择**:

我刚才的建议您看到了吗？您希望：

1️⃣ **立即生成策略代码** - 回复 "确认生成"
2️⃣ **继续完善策略** - 告诉我您想调整的地方

💡 如果您有其他想法或疑问，也可以直接告诉我！"""

    def get_confirmation_summary(self, confirmation_result: Dict[str, Any]) -> str:
        """获取确认结果摘要"""
        
        confirmation_type = confirmation_result.get("confirmation_type", "unknown")
        score = confirmation_result.get("maturity_score", 0)
        
        type_descriptions = {
            "ready_confirmation": "策略成熟，询问用户确认",
            "improvement_confirmation": "策略可用，提供改进选择",
            "discussion_guidance": "策略待完善，继续讨论引导",
            "error": "生成确认提示失败"
        }
        
        description = type_descriptions.get(confirmation_type, "未知类型")
        
        return f"确认类型: {description} | 成熟度: {score:.0f}/100"