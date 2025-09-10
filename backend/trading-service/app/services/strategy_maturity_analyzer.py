"""
策略讨论成熟度分析器

评估用户和AI的策略讨论是否达到可以生成代码的成熟度
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class StrategyMaturityAnalyzer:
    """策略讨论成熟度分析器"""
    
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
    
    MATURITY_CRITERIA = {
        "trading_logic": {
            "weight": 0.3,
            "required_elements": ["entry_conditions", "exit_conditions", "signal_source"]
        },
        "risk_management": {
            "weight": 0.25,
            "required_elements": ["stop_loss", "position_sizing", "risk_threshold"]
        },
        "technical_parameters": {
            "weight": 0.25,
            "required_elements": ["indicators", "timeframe", "parameters"]
        },
        "market_context": {
            "weight": 0.2,
            "required_elements": ["trading_pair", "market_conditions", "strategy_type"]
        }
    }
    
    @staticmethod
    async def analyze_conversation_maturity(
        conversation_history: List[Dict[str, Any]],
        current_message: str
    ) -> Dict[str, Any]:
        """
        分析对话历史和当前消息，判断策略讨论的成熟度
        
        返回:
        {
            "is_mature": bool,           # 是否成熟
            "maturity_score": float,     # 成熟度评分 (0-1)
            "missing_elements": list,    # 缺失的要素
            "ready_for_generation": bool, # 是否准备好生成代码
            "confirmation_prompt": str   # 如果准备好，返回确认提示
        }
        """
        try:
            # 构建分析提示词
            conversation_text = StrategyMaturityAnalyzer._format_conversation_history(conversation_history)
            
            analysis_prompt = f"""
            请分析这个交易策略讨论的成熟度。用户和AI已经讨论了一段时间，现在需要判断是否有足够的信息来生成策略代码。

            对话历史：
            {conversation_text}
            
            当前消息：{current_message}

            请评估以下方面的完整性（每个方面0-1分）：

            1. 交易逻辑 (0.3权重)
               - 入场条件是否明确
               - 出场条件是否明确  
               - 信号来源是否确定

            2. 风险管理 (0.25权重)
               - 止损策略是否明确
               - 仓位管理是否讨论
               - 风险阈值是否设定

            3. 技术参数 (0.25权重)
               - 技术指标是否确定
               - 时间框架是否明确
               - 参数设置是否讨论

            4. 市场背景 (0.2权重)
               - 交易对是否确定
               - 市场环境是否考虑
               - 策略类型是否明确

            严格按照以下JSON格式返回：
            {{
                "maturity_scores": {{
                    "trading_logic": 0.8,
                    "risk_management": 0.6,
                    "technical_parameters": 0.9,
                    "market_context": 0.7
                }},
                "overall_score": 0.75,
                "is_mature": true,
                "missing_elements": ["止损具体数值", "仓位大小"],
                "detailed_analysis": "详细分析说明...",
                "ready_for_generation": true,
                "next_questions": ["还需要确认哪些细节？"]
            }}

            评判标准：
            - overall_score >= 0.7 且每个方面 >= 0.5 才算成熟
            - ready_for_generation = true 时，用户可以选择生成代码
            - 如果不成熟，提供next_questions帮助用户完善

            只返回JSON，不要其他内容。
            """
            
            claude_client = await StrategyMaturityAnalyzer._get_claude_client()
            if not claude_client:
                logger.error("无法获取Claude客户端")
                return StrategyMaturityAnalyzer._get_fallback_analysis()
                
            response = await claude_client.create_message(
                messages=[{"role": "user", "content": analysis_prompt}],
                system="你是专业的量化策略分析师，精确评估策略讨论的完整性。返回标准JSON格式。",
                temperature=0.3
            )
            
            if response["success"]:
                try:
                    content = response["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # Anthropic原始格式
                        content = content[0].get("text", "")
                    elif isinstance(content, str):
                        # 包装格式
                        pass
                    else:
                        content = str(content)
                    content = content.strip()
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    analysis = json.loads(content)
                    
                    # 生成用户确认提示（如果成熟）
                    if analysis.get("ready_for_generation", False):
                        analysis["confirmation_prompt"] = StrategyMaturityAnalyzer._generate_confirmation_prompt(analysis)
                    
                    logger.info(f"策略成熟度分析完成: score={analysis.get('overall_score', 0)}, ready={analysis.get('ready_for_generation', False)}")
                    
                    return analysis
                    
                except json.JSONDecodeError as e:
                    logger.error(f"解析成熟度分析JSON失败: {e}")
                    return StrategyMaturityAnalyzer._get_fallback_analysis()
            else:
                logger.error(f"策略成熟度分析失败: {response}")
                return StrategyMaturityAnalyzer._get_fallback_analysis()
                
        except Exception as e:
            logger.error(f"策略成熟度分析异常: {e}")
            return StrategyMaturityAnalyzer._get_fallback_analysis()
    
    @staticmethod
    def _format_conversation_history(conversation_history: List[Dict[str, Any]]) -> str:
        """格式化对话历史"""
        if not conversation_history:
            return "（无对话历史）"
            
        formatted_messages = []
        for msg in conversation_history[-10:]:  # 只取最近10条消息
            role = "用户" if msg.get("message_type") == "user" else "AI助手"
            content = msg.get("content", "")[:200]  # 限制长度
            formatted_messages.append(f"{role}: {content}")
            
        return "\n".join(formatted_messages)
    
    @staticmethod
    def _generate_confirmation_prompt(analysis: Dict[str, Any]) -> str:
        """生成用户确认提示"""
        overall_score = analysis.get("overall_score", 0)
        missing_elements = analysis.get("missing_elements", [])
        
        prompt = f"📊 **策略讨论分析完成** (成熟度: {overall_score:.1%})\n\n"
        prompt += "✅ 您的策略已经具备了代码生成的基本条件：\n"
        
        scores = analysis.get("maturity_scores", {})
        if scores.get("trading_logic", 0) >= 0.5:
            prompt += "• 交易逻辑清晰 ✅\n"
        if scores.get("risk_management", 0) >= 0.5:
            prompt += "• 风险管理到位 ✅\n"  
        if scores.get("technical_parameters", 0) >= 0.5:
            prompt += "• 技术参数明确 ✅\n"
        if scores.get("market_context", 0) >= 0.5:
            prompt += "• 市场背景清楚 ✅\n"
            
        if missing_elements:
            prompt += f"\n⚠️ 还有一些细节可以进一步完善：\n"
            for element in missing_elements[:3]:  # 只显示前3个
                prompt += f"• {element}\n"
                
        prompt += "\n🤔 **是否现在生成策略代码？**\n"
        prompt += "您可以选择：\n"
        prompt += "1. 继续讨论完善策略细节\n"
        prompt += "2. 基于当前讨论生成策略代码\n\n"
        prompt += "如需生成代码，请明确回复\"生成代码\"或\"开始编码\"。"
        
        return prompt
    
    @staticmethod
    def _get_fallback_analysis() -> Dict[str, Any]:
        """获取降级分析结果"""
        return {
            "maturity_scores": {
                "trading_logic": 0.3,
                "risk_management": 0.3, 
                "technical_parameters": 0.3,
                "market_context": 0.3
            },
            "overall_score": 0.3,
            "is_mature": False,
            "missing_elements": ["需要更多策略细节"],
            "detailed_analysis": "分析系统暂时不可用，建议继续讨论策略细节",
            "ready_for_generation": False,
            "next_questions": ["请详细描述您的交易策略思路"]
        }
    
    @staticmethod
    def is_user_confirming_generation(message: str) -> bool:
        """检测用户是否确认生成代码"""
        confirmation_phrases = [
            "生成代码", "开始编码", "生成策略", "创建代码",
            "好的，生成", "确认生成", "开始生成", "可以生成",
            "写代码", "生成吧", "开始吧", "确定"
        ]
        
        message_lower = message.lower().replace(" ", "").replace("，", "").replace("。", "")
        
        return any(phrase.replace(" ", "") in message_lower for phrase in confirmation_phrases)