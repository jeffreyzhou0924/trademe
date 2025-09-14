"""
策略意图分析器

解析用户的策略需求，提取关键信息并进行模板兼容性检查
"""

import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class StrategyIntentAnalyzer:
    """策略意图分析器"""
    
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
    
    SUPPORTED_DATA_TYPES = [
        "kline", "orderbook", "funding_flow", 
        "news_sentiment", "technical_indicator"
    ]
    
    COMPLEXITY_THRESHOLDS = {
        "basic": {"max_data_sources": 2, "max_indicators": 3},
        "premium": {"max_data_sources": 5, "max_indicators": 8},
        "professional": {"max_data_sources": 10, "max_indicators": 15}
    }
    
    @staticmethod
    async def analyze_user_intent(user_input: str) -> Dict[str, Any]:
        """解析用户策略意图"""
        try:
            # AI意图解析提示词
            intent_analysis_prompt = f"""
            分析用户的策略需求，提取关键信息。

            用户输入：{user_input}

            请严格按照以下JSON格式返回分析结果：
            {{
                "strategy_type": "技术指标策略|量价策略|多因子策略|套利策略|其他",
                "primary_indicators": ["RSI", "MACD", "MA"],
                "data_requirements": ["kline", "orderbook", "funding_flow"],
                "trading_logic": "具体交易逻辑描述",
                "risk_controls": ["止损", "止盈", "仓位控制"],
                "complexity_score": 1,
                "missing_details": [],
                "template_compatibility": true,
                "confidence": 0.9
            }}

            说明：
            - strategy_type: 策略类型分类
            - primary_indicators: 主要技术指标列表
            - data_requirements: 需要的数据源类型
            - trading_logic: 交易逻辑的文字描述
            - risk_controls: 风险控制措施
            - complexity_score: 复杂度评分(1-10)
            - missing_details: 需要用户补充的信息
            - template_compatibility: 是否与模板兼容
            - confidence: 分析置信度(0-1)

            只返回JSON，不要其他文字。
            """
            
            claude_client = await StrategyIntentAnalyzer._get_claude_client()
            if not claude_client:
                logger.error("无法获取Claude客户端")
                return StrategyIntentAnalyzer._get_fallback_intent(user_input)
                
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": intent_analysis_prompt}],
                system="你是专业的量化策略分析师，精确提取用户需求信息。返回标准JSON格式。",
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
                    logger.error(f"Unexpected response format: {response}")
                    return StrategyIntentAnalyzer._get_fallback_intent(user_input)
                
                content = content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                intent = json.loads(content)
                
                # 验证必需字段
                required_fields = ["strategy_type", "data_requirements", "template_compatibility"]
                for field in required_fields:
                    if field not in intent:
                        intent[field] = None
                
                return intent
                
            except json.JSONDecodeError as e:
                logger.error(f"解析意图JSON失败: {e}, 内容: {content}")
                return StrategyIntentAnalyzer._get_fallback_intent(user_input)
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                return StrategyIntentAnalyzer._get_fallback_intent(user_input)
                
        except Exception as e:
            logger.error(f"策略意图分析异常: {e}")
            return StrategyIntentAnalyzer._get_fallback_intent(user_input)
    
    @staticmethod
    def _get_fallback_intent(user_input: str) -> Dict[str, Any]:
        """获取降级的意图分析结果"""
        # 简单的关键词匹配作为降级方案
        indicators = []
        if "rsi" in user_input.lower():
            indicators.append("RSI")
        if "macd" in user_input.lower():
            indicators.append("MACD")
        if "均线" in user_input or "ma" in user_input.lower():
            indicators.append("MA")
        if "布林" in user_input or "boll" in user_input.lower():
            indicators.append("BOLL")
        
        return {
            "strategy_type": "技术指标策略",
            "primary_indicators": indicators or ["MA"],
            "data_requirements": ["kline"],
            "trading_logic": "基于技术指标的交易策略",
            "risk_controls": ["止损", "止盈"],
            "complexity_score": 3,
            "missing_details": ["请详细描述交易条件"],
            "template_compatibility": True,
            "confidence": 0.3
        }
    
    @staticmethod
    async def check_compatibility(
        intent: Dict[str, Any],
        user_membership: str = "basic"
    ) -> Dict[str, Any]:
        """检查策略是否与模板兼容"""
        
        issues = []
        suggestions = []
        
        # 检查数据源支持
        required_data = intent.get("data_requirements", [])
        unsupported = [d for d in required_data if d not in StrategyIntentAnalyzer.SUPPORTED_DATA_TYPES]
        if unsupported:
            issues.append(f"不支持的数据源: {', '.join(unsupported)}")
            suggestions.append("请选择支持的数据源：K线数据、订单簿、资金流、新闻情绪")
        
        # 检查复杂度限制
        complexity = intent.get("complexity_score", 5)
        threshold = StrategyIntentAnalyzer.COMPLEXITY_THRESHOLDS.get(
            user_membership, 
            StrategyIntentAnalyzer.COMPLEXITY_THRESHOLDS["basic"]
        )
        
        if len(required_data) > threshold["max_data_sources"]:
            issues.append(f"数据源过多({len(required_data)}>{threshold['max_data_sources']})")
            suggestions.append("请升级会员或减少数据源数量")
        
        indicators = intent.get("primary_indicators", [])
        if len(indicators) > threshold["max_indicators"]:
            issues.append(f"指标过多({len(indicators)}>{threshold['max_indicators']})")
            suggestions.append("请简化指标使用或升级会员")
        
        # 检查逻辑完整性
        if not intent.get("trading_logic") or intent["trading_logic"] == "未知":
            issues.append("缺少具体的交易逻辑")
            suggestions.append("请详细描述买入/卖出条件")
        
        # 置信度检查
        if intent.get("confidence", 0) < 0.6:
            issues.append("策略描述不够清晰")
            suggestions.append("请提供更详细的策略说明")
        
        return {
            "compatible": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
            "confidence_score": max(0, 1 - len(issues) * 0.2),
            "membership_limit": user_membership not in ["premium", "professional"] and len(required_data) > 2
        }
    
    @staticmethod
    async def generate_guidance(
        intent: Dict[str, Any],
        compatibility_check: Dict[str, Any]
    ) -> str:
        """生成用户引导建议"""
        
        if compatibility_check["compatible"]:
            return "✅ 您的策略设想很好！我现在开始为您生成策略代码。"
        
        guidance_prompt = f"""
        用户策略意图：{json.dumps(intent, ensure_ascii=False)}
        
        发现的问题：
        {chr(10).join(f"• {issue}" for issue in compatibility_check["issues"])}
        
        建议：
        {chr(10).join(f"• {suggestion}" for suggestion in compatibility_check["suggestions"])}
        
        请生成友好、专业的引导建议，帮助用户完善策略设想。要求：
        1. 用鼓励和专业的语气
        2. 具体说明需要补充什么信息
        3. 给出2-3个具体的改进建议
        4. 不超过150字
        5. 用中文回答
        """
        
        try:
            claude_client = await StrategyIntentAnalyzer._get_claude_client()
            if not claude_client:
                return StrategyIntentAnalyzer._get_default_guidance(compatibility_check)
                
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": guidance_prompt}],
                system="你是专业的量化策略顾问，善于引导用户完善策略设想。",
                temperature=0.7
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
                    logger.error(f"Unexpected response format: {response}")
                    return StrategyIntentAnalyzer._get_default_guidance(compatibility_check)
                
                return content.strip() if content else StrategyIntentAnalyzer._get_default_guidance(compatibility_check)
                
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                return StrategyIntentAnalyzer._get_default_guidance(compatibility_check)
                
        except Exception as e:
            logger.error(f"生成引导建议失败: {e}")
            return StrategyIntentAnalyzer._get_default_guidance(compatibility_check)
    
    @staticmethod
    def _get_default_guidance(compatibility_check: Dict[str, Any]) -> str:
        """获取默认引导建议"""
        issues = compatibility_check.get("issues", [])
        suggestions = compatibility_check.get("suggestions", [])
        
        guidance = "您的策略想法很有潜力，但需要完善一些细节：\n\n"
        
        if issues:
            guidance += "需要解决的问题：\n"
            for i, issue in enumerate(issues[:3], 1):
                guidance += f"{i}. {issue}\n"
        
        if suggestions:
            guidance += "\n建议：\n"
            for i, suggestion in enumerate(suggestions[:3], 1):
                guidance += f"{i}. {suggestion}\n"
        
        guidance += "\n请补充更详细的策略描述，我将为您生成优质的策略代码。"
        
        return guidance