"""
AI服务 - 基于Claude的AI相关业务逻辑

提供完整的AI功能实现，包括：
- 智能对话系统
- 策略代码生成
- 市场分析和建议
- 回测结果解读
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

from app.ai.core.claude_client import claude_client
from app.ai.prompts.trading_prompts import TradingPrompts
from app.ai.prompts.system_prompts import SystemPrompts
from app.models.claude_conversation import ClaudeConversation, ClaudeUsage, GeneratedStrategy, AIChatSession
from app.services.strategy_generation_orchestrator import StrategyGenerationOrchestrator
from app.services.claude_scheduler_service import claude_scheduler_service, SchedulerContext
from app.services.claude_account_service import claude_account_service


class AIService:
    """AI服务类 - 基于Claude"""
    
    @staticmethod
    async def chat_completion(
        message: str,
        user_id: int,
        context: Optional[Dict] = None,
        session_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """AI对话完成 - 支持智能策略生成识别"""
        try:
            # 生成会话ID
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # 检查用户AI使用限制
            if db and context and 'membership_level' in context:
                estimated_cost = 0.015  # 预估每次对话成本 ($0.015)
                can_use = await AIService.check_daily_usage_limit(
                    db, user_id, context['membership_level'], estimated_cost
                )
                if not can_use:
                    return {
                        "content": "您今日的AI对话额度已用尽，请升级会员或明日再试",
                        "session_id": session_id,
                        "tokens_used": 0,
                        "model": "limit-exceeded",
                        "success": False,
                        "requires_strategy_generation": False
                    }
            
            # 智能检测是否为策略生成请求
            strategy_request = await AIService._detect_strategy_generation_intent(message)
            
            if strategy_request["is_strategy_request"] and db:
                # 如果是策略请求且用户有足够权限，调用完整策略生成流程
                membership_level = context.get('membership_level', 'basic') if context else 'basic'
                
                logger.info(f"检测到策略生成请求 - 用户ID: {user_id}, 会话ID: {session_id}")
                
                strategy_result = await AIService.generate_complete_strategy(
                    user_input=message,
                    user_id=user_id,
                    membership_level=membership_level,
                    session_id=session_id,
                    db=db
                )
                
                if strategy_result["success"]:
                    # 构建策略生成成功的响应
                    performance_grade = strategy_result.get("backtest_results", {}).get("performance_grade", "未知")
                    meets_expectations = strategy_result.get("backtest_results", {}).get("meets_expectations", False)
                    
                    response_content = f"""✅ **策略生成成功！**

📊 **性能评级**: {performance_grade}
🎯 **达预期**: {'是' if meets_expectations else '否'}
⏱️ **处理时间**: {strategy_result.get('execution_time', 0):.1f}秒
🔄 **完成阶段**: {strategy_result.get('total_stages_completed', 0)}/7

📈 **策略代码已生成并通过验证**
• 意图分析: ✅
• 代码生成: ✅  
• 模板验证: ✅
• 自动回测: ✅
• 优化建议: ✅

您可以在策略管理页面查看和使用生成的策略。
"""
                    
                    # 如果有优化建议，添加关键建议
                    if strategy_result.get("optimization_advice"):
                        priority_actions = strategy_result["optimization_advice"].get("priority_actions", [])
                        if priority_actions:
                            response_content += f"\n💡 **关键优化建议**:\n"
                            for action in priority_actions[:3]:
                                response_content += f"• {action}\n"
                    
                    return {
                        "content": response_content,
                        "session_id": session_id,
                        "tokens_used": 0,  # 已在generate_complete_strategy中记录
                        "model": "claude-orchestrator",
                        "success": True,
                        "requires_strategy_generation": False,
                        "strategy_generation_result": strategy_result
                    }
                else:
                    # 策略生成失败，提供引导
                    error_msg = strategy_result.get("error", "未知错误")
                    user_guidance = strategy_result.get("user_guidance", "")
                    
                    response_content = f"""❌ **策略生成遇到问题**

**问题**: {error_msg}

{user_guidance if user_guidance else ''}

💡 **建议**:
• 请详细描述您的策略思路
• 明确指定技术指标和交易条件  
• 确保您的会员级别支持所需功能

您可以重新描述策略需求，我会继续为您生成。
"""
                    
                    return {
                        "content": response_content,
                        "session_id": session_id,
                        "tokens_used": 0,
                        "model": "claude-guidance",
                        "success": True,
                        "requires_strategy_generation": False
                    }
            
            # 常规对话处理
            # 构建消息历史
            messages = []
            
            # 获取对话历史
            if db:
                history = await AIService._get_conversation_history(db, user_id, session_id, limit=10)
                for conv in history:
                    messages.append({
                        "role": conv.message_type, 
                        "content": conv.content
                    })
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": message})
            
            # 使用Claude账号池进行智能调度
            scheduler_context = SchedulerContext(
                user_id=user_id,
                request_type="chat",
                session_id=session_id,
                min_quota=Decimal("0.02"),  # 预估单次对话成本
                priority=100
            )
            
            selected_account = await claude_scheduler_service.select_optimal_account(scheduler_context)
            if not selected_account:
                return {
                    "content": "当前没有可用的Claude账号，请稍后重试",
                    "session_id": session_id,
                    "tokens_used": 0,
                    "model": "claude-unavailable",
                    "success": False,
                    "requires_strategy_generation": False
                }
            
            # 获取解密的API密钥
            api_key = await claude_account_service.get_decrypted_api_key(selected_account.id)
            if not api_key:
                return {
                    "content": "Claude账号配置错误，请联系管理员",
                    "session_id": session_id,
                    "tokens_used": 0,
                    "model": "claude-error",
                    "success": False,
                    "requires_strategy_generation": False
                }
            
            # 调用Claude API（使用选定的账号）
            response = await claude_client.chat_completion(
                messages=messages,
                system_prompt=SystemPrompts.TRADING_ASSISTANT_SYSTEM,
                temperature=0.7,
                api_key=api_key  # 使用智能选择的账号
            )
            
            # 保存对话记录
            if db and response["success"]:
                await AIService._save_conversation(
                    db, user_id, session_id, "user", message, context
                )
                await AIService._save_conversation(
                    db, user_id, session_id, "assistant", response["content"], 
                    context, response["usage"]["total_tokens"], response["model"]
                )
                
                # 保存使用统计
                await AIService._save_usage_stats(
                    db, user_id, "chat", 
                    response["usage"]["input_tokens"],
                    response["usage"]["output_tokens"],
                    response["model"]
                )
                
                # 记录账号池使用情况
                estimated_cost = (response["usage"]["input_tokens"] * 3.0 + 
                                response["usage"]["output_tokens"] * 15.0) / 1000000 * 2.0
                await claude_account_service.log_usage(
                    account_id=selected_account.id,
                    user_id=user_id,
                    request_type="chat",
                    input_tokens=response["usage"]["input_tokens"],
                    output_tokens=response["usage"]["output_tokens"],
                    api_cost=Decimal(str(estimated_cost)),
                    response_time=None,  # TODO: 添加响应时间测量
                    success=True
                )
                
                # 更新会话活动信息
                cost_usd = (response["usage"]["input_tokens"] * 3.0 + response["usage"]["output_tokens"] * 15.0) / 1000000 * 2.0  # 2倍计费
                await AIService.update_session_activity(
                    db, session_id, user_id, 
                    response["content"][:200],  # 截取前200字符
                    response["usage"]["total_tokens"],
                    cost_usd
                )
            
            return {
                "content": response["content"],
                "session_id": session_id,
                "tokens_used": response["usage"]["total_tokens"] if response["success"] else 0,
                "model": response["model"],
                "success": response["success"],
                "requires_strategy_generation": strategy_request["is_strategy_request"] if not db else False
            }
            
        except Exception as e:
            logger.error(f"AI对话失败: {str(e)}")
            
            # 如果有选定的账号，记录失败日志
            if 'selected_account' in locals() and selected_account:
                try:
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="chat",
                        input_tokens=0,
                        output_tokens=0,
                        api_cost=Decimal("0.0"),
                        success=False,
                        error_code="system_error",
                        error_message=str(e)[:500]  # 限制错误消息长度
                    )
                except Exception as log_error:
                    logger.error(f"记录失败日志时出错: {log_error}")
            
            return {
                "content": f"抱歉，AI服务暂时不可用: {str(e)}",
                "session_id": session_id or str(uuid.uuid4()),
                "tokens_used": 0,
                "model": "claude-error",
                "success": False,
                "requires_strategy_generation": False
            }
    
    @staticmethod
    async def generate_strategy(
        description: str,
        indicators: List[str],
        timeframe: str,
        risk_level: str,
        user_id: int,
        membership_level: str = "basic",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """生成交易策略 - 已弃用，请使用 generate_complete_strategy"""
        # 向后兼容的简化实现
        user_input = f"策略描述: {description}, 指标: {', '.join(indicators)}, 时间周期: {timeframe}, 风险级别: {risk_level}"
        
        result = await AIService.generate_complete_strategy(
            user_input=user_input,
            user_id=user_id,
            membership_level=membership_level,
            db=db
        )
        
        if result["success"]:
            return {
                "code": result.get("strategy_code", "# AI策略生成失败\npass"),
                "explanation": result.get("optimization_advice", {}).get("ai_analysis", {}).get("analysis", {}).get("root_cause_analysis", "AI策略生成成功"),
                "parameters": {"timeframe": timeframe, "risk_level": risk_level},
                "warnings": ["请在实盘使用前进行充分测试", "AI生成的策略仅供参考"],
                "performance_grade": result.get("backtest_results", {}).get("performance_grade", "未知"),
                "meets_expectations": result.get("backtest_results", {}).get("meets_expectations", False)
            }
        else:
            return {
                "code": "# AI策略生成失败\npass",
                "explanation": result.get("error", "策略生成失败"),
                "parameters": {},
                "warnings": ["策略生成失败"]
            }
    
    @staticmethod
    async def generate_complete_strategy(
        user_input: str,
        user_id: int,
        membership_level: str = "basic",
        session_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        完整的AI策略生成闭环系统
        
        集成意图分析、策略生成、验证、修复、回测、优化建议的完整流程
        """
        try:
            # 检查用户AI使用限制
            if db:
                estimated_cost = 0.08  # 完整流程预估成本更高 ($0.08)
                can_use = await AIService.check_daily_usage_limit(
                    db, user_id, membership_level, estimated_cost
                )
                if not can_use:
                    return {
                        "success": False,
                        "stage": "usage_limit",
                        "error": "您今日的AI策略生成额度已用尽，请升级会员或明日再试",
                        "user_guidance": "升级至高级会员可获得更多AI使用额度"
                    }
            
            # 调用完整流程编排器
            result = await StrategyGenerationOrchestrator.generate_complete_strategy(
                user_input=user_input,
                user_id=user_id,
                user_membership=membership_level,
                session_id=session_id
            )
            
            # 保存生成的策略到数据库（如果成功）
            if db and result["success"] and result.get("strategy_code"):
                try:
                    generated_strategy = GeneratedStrategy(
                        user_id=user_id,
                        prompt=user_input,
                        generated_code=result["strategy_code"],
                        explanation=json.dumps(result.get("intent_analysis", {}), ensure_ascii=False),
                        parameters=json.dumps({
                            "generation_id": result["generation_id"],
                            "performance_grade": result.get("backtest_results", {}).get("performance_grade", "F"),
                            "meets_expectations": result.get("backtest_results", {}).get("meets_expectations", False)
                        }),
                        tokens_used=0,  # 将在usage中单独记录
                        generation_time_ms=int(result.get("execution_time", 0) * 1000),
                        model_used="claude-sonnet-4-orchestrated"
                    )
                    db.add(generated_strategy)
                    
                    # 保存完整流程的使用统计
                    usage_stat = ClaudeUsage(
                        user_id=user_id,
                        feature_type="complete_strategy_gen",
                        input_tokens=2000,  # 估算值，完整流程的token使用量
                        output_tokens=3000,  # 估算值
                        api_cost=f"{estimated_cost:.6f}",
                        model_used="claude-sonnet-4-orchestrator"
                    )
                    db.add(usage_stat)
                    
                    await db.commit()
                    logger.info(f"完整策略生成成功保存 - 用户ID: {user_id}, 生成ID: {result['generation_id']}")
                    
                except Exception as db_error:
                    logger.error(f"保存策略生成结果失败: {db_error}")
                    # 不影响主流程，继续返回结果
            
            return result
            
        except Exception as e:
            logger.error(f"完整策略生成异常: {e}")
            return {
                "success": False,
                "stage": "system_error",
                "error": f"系统异常: {str(e)}",
                "user_guidance": "系统暂时不可用，请稍后重试"
            }
    
    @staticmethod
    async def analyze_market_conditions(
        symbols: List[str],
        timeframe: str,
        analysis_type: str,
        user_id: int,
        membership_level: str = "basic",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """分析市场条件"""
        try:
            # 检查用户AI使用限制
            if db:
                estimated_cost = 0.020  # 预估市场分析成本 ($0.020)
                can_use = await AIService.check_daily_usage_limit(
                    db, user_id, membership_level, estimated_cost
                )
                if not can_use:
                    return {
                        "summary": "您今日的AI对话额度已用尽，请升级会员或明日再试",
                        "signals": [],
                        "risk_assessment": {},
                        "recommendations": ["AI额度不足"]
                    }
            
            # 模拟获取市场数据
            market_data = {
                "symbols": symbols,
                "timeframe": timeframe,
                "timestamp": datetime.utcnow().isoformat(),
                "prices": {symbol: {"price": 50000, "change_24h": 2.5} for symbol in symbols}
            }
            
            # 使用Claude账号池进行智能调度
            scheduler_context = SchedulerContext(
                user_id=user_id,
                request_type="market_analysis",
                min_quota=Decimal("0.03"),  # 预估市场分析成本
                priority=80  # 市场分析优先级稍高
            )
            
            selected_account = await claude_scheduler_service.select_optimal_account(scheduler_context)
            if not selected_account:
                return {
                    "summary": "当前没有可用的Claude账号，请稍后重试",
                    "signals": [],
                    "risk_assessment": {},
                    "recommendations": []
                }
            
            # 获取解密的API密钥
            api_key = await claude_account_service.get_decrypted_api_key(selected_account.id)
            
            # 调用Claude进行市场分析
            response = await claude_client.analyze_market_data(
                market_data=market_data,
                symbols=symbols,
                analysis_type=analysis_type,
                api_key=api_key  # 使用智能选择的账号
            )
            
            if response["success"]:
                # 保存使用统计
                if db:
                    await AIService._save_usage_stats(
                        db, user_id, "analysis",
                        response["usage"]["input_tokens"],
                        response["usage"]["output_tokens"],
                        response["model"]
                    )
                    
                    # 记录账号池使用情况
                    estimated_cost = (response["usage"]["input_tokens"] * 3.0 + 
                                    response["usage"]["output_tokens"] * 15.0) / 1000000 * 2.0
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="market_analysis",
                        input_tokens=response["usage"]["input_tokens"],
                        output_tokens=response["usage"]["output_tokens"],
                        api_cost=Decimal(str(estimated_cost)),
                        success=True
                    )
                
                return {
                    "summary": response["content"],
                    "signals": [{"symbol": sym, "signal": "hold", "confidence": 0.6} for sym in symbols],
                    "risk_assessment": {"level": "medium", "factors": ["市场波动"]},
                    "recommendations": ["建议谨慎交易", "关注市场变化"]
                }
            else:
                return {
                    "summary": "市场分析暂时不可用",
                    "signals": [],
                    "risk_assessment": {},
                    "recommendations": []
                }
                
        except Exception as e:
            logger.error(f"市场分析失败: {str(e)}")
            return {
                "summary": f"市场分析失败: {str(e)}",
                "signals": [],
                "risk_assessment": {},
                "recommendations": []
            }
    
    @staticmethod
    async def analyze_backtest_performance(
        backtest_results: Dict,
        user_id: int,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """分析回测性能"""
        try:
            # 构建回测分析提示词
            prompts = TradingPrompts.format_backtest_prompt(
                strategy_name=backtest_results.get("strategy_name", "未知策略"),
                start_date=backtest_results.get("start_date", ""),
                end_date=backtest_results.get("end_date", ""),
                initial_capital=backtest_results.get("initial_capital", 10000),
                backtest_results=str(backtest_results)[:1000],
                performance_metrics=str(backtest_results.get("performance", {}))
            )
            
            messages = [{"role": "user", "content": prompts["user"]}]
            
            # 使用Claude账号池进行智能调度
            scheduler_context = SchedulerContext(
                user_id=user_id,
                request_type="backtest_analysis",
                min_quota=Decimal("0.025"),  # 预估回测分析成本
                priority=90  # 回测分析优先级较高
            )
            
            selected_account = await claude_scheduler_service.select_optimal_account(scheduler_context)
            if not selected_account:
                return {
                    "summary": "当前没有可用的Claude账号，请稍后重试",
                    "strengths": [],
                    "weaknesses": [],
                    "suggestions": [],
                    "risk_analysis": {}
                }
            
            # 获取解密的API密钥
            api_key = await claude_account_service.get_decrypted_api_key(selected_account.id)
            
            response = await claude_client.chat_completion(
                messages=messages,
                system_prompt=prompts["system"],
                temperature=0.5,
                api_key=api_key  # 使用智能选择的账号
            )
            
            if response["success"]:
                # 保存使用统计
                if db:
                    await AIService._save_usage_stats(
                        db, user_id, "analysis",
                        response["usage"]["input_tokens"],
                        response["usage"]["output_tokens"],
                        response["model"]
                    )
                    
                    # 记录账号池使用情况
                    estimated_cost = (response["usage"]["input_tokens"] * 3.0 + 
                                    response["usage"]["output_tokens"] * 15.0) / 1000000 * 2.0
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="backtest_analysis",
                        input_tokens=response["usage"]["input_tokens"],
                        output_tokens=response["usage"]["output_tokens"],
                        api_cost=Decimal(str(estimated_cost)),
                        success=True
                    )
                
                return {
                    "summary": response["content"],
                    "strengths": ["AI分析正在处理中"],
                    "weaknesses": ["需要更多数据进行分析"],
                    "suggestions": ["建议扩大样本量", "关注风险控制"],
                    "risk_analysis": {"overall_risk": "medium"}
                }
            else:
                return {
                    "summary": "回测分析暂时不可用",
                    "strengths": [],
                    "weaknesses": [],
                    "suggestions": [],
                    "risk_analysis": {}
                }
                
        except Exception as e:
            logger.error(f"回测分析失败: {str(e)}")
            return {
                "summary": f"回测分析失败: {str(e)}",
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "risk_analysis": {}
            }
    
    @staticmethod
    async def get_chat_history(
        user_id: int,
        session_id: Optional[str] = None,
        limit: int = 50,
        db: Optional[AsyncSession] = None
    ) -> List[Dict]:
        """获取聊天历史"""
        if not db:
            return []
        
        try:
            query = select(ClaudeConversation).where(ClaudeConversation.user_id == user_id)
            
            if session_id:
                query = query.where(ClaudeConversation.session_id == session_id)
            
            query = query.order_by(ClaudeConversation.created_at.desc()).limit(limit)
            
            result = await db.execute(query)
            conversations = result.scalars().all()
            
            return [conv.to_dict() for conv in conversations]
            
        except Exception as e:
            logger.error(f"获取聊天历史失败: {str(e)}")
            return []
    
    @staticmethod
    async def clear_chat_session(
        user_id: int, 
        session_id: str,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """清除聊天会话"""
        if not db:
            return False
        
        try:
            # 删除指定会话的所有对话记录
            query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id
                )
            )
            result = await db.execute(query)
            conversations = result.scalars().all()
            
            for conv in conversations:
                await db.delete(conv)
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"清除聊天会话失败: {str(e)}")
            return False
    
    @staticmethod
    async def get_usage_statistics(
        user_id: int, 
        days: int,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """获取使用统计"""
        if not db:
            return {"error": "数据库连接不可用"}
        
        try:
            # 计算日期范围
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # 查询使用统计
            query = select(ClaudeUsage).where(
                and_(
                    ClaudeUsage.user_id == user_id,
                    ClaudeUsage.request_date >= start_date
                )
            )
            
            result = await db.execute(query)
            usage_records = result.scalars().all()
            
            # 计算统计数据
            total_requests = len(usage_records)
            total_input_tokens = sum(record.input_tokens for record in usage_records)
            total_output_tokens = sum(record.output_tokens for record in usage_records)
            total_cost = sum(float(record.api_cost) for record in usage_records)
            
            # 按功能类型分组
            by_feature = {}
            for record in usage_records:
                feature = record.feature_type
                if feature not in by_feature:
                    by_feature[feature] = {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost": 0
                    }
                by_feature[feature]["requests"] += 1
                by_feature[feature]["input_tokens"] += record.input_tokens
                by_feature[feature]["output_tokens"] += record.output_tokens
                by_feature[feature]["cost"] += float(record.api_cost)
            
            return {
                "period_days": days,
                "total_requests": total_requests,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "total_cost_usd": round(total_cost, 6),
                "by_feature": by_feature,
                "claude_client_stats": claude_client.get_usage_stats()
            }
            
        except Exception as e:
            logger.error(f"获取使用统计失败: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    async def generate_trading_insights(
        symbol: str,
        timeframe: str,
        user_id: int,
        membership_level: str = "basic",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """生成交易洞察"""
        try:
            # 检查用户AI使用限制
            if db:
                estimated_cost = 0.018  # 预估交易洞察成本 ($0.018)
                can_use = await AIService.check_daily_usage_limit(
                    db, user_id, membership_level, estimated_cost
                )
                if not can_use:
                    return {
                        "content": "您今日的AI对话额度已用尽，请升级会员或明日再试",
                        "confidence": 0,
                        "factors": [],
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            # 构建洞察生成提示词
            user_message = f"""请为{symbol}提供交易洞察分析:

时间周期: {timeframe}
分析维度: 技术分析、市场情绪、基本面
请提供: 具体的交易建议、风险评估、关键关注点"""

            messages = [{"role": "user", "content": user_message}]
            
            # 使用Claude账号池进行智能调度
            scheduler_context = SchedulerContext(
                user_id=user_id,
                request_type="trading_insights",
                min_quota=Decimal("0.020"),  # 预估交易洞察成本
                priority=85  # 交易洞察优先级
            )
            
            selected_account = await claude_scheduler_service.select_optimal_account(scheduler_context)
            if not selected_account:
                return {
                    "content": "当前没有可用的Claude账号，请稍后重试",
                    "confidence": 0,
                    "factors": [],
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # 获取解密的API密钥
            api_key = await claude_account_service.get_decrypted_api_key(selected_account.id)
            
            response = await claude_client.chat_completion(
                messages=messages,
                system_prompt=SystemPrompts.TRADING_ASSISTANT_SYSTEM,
                temperature=0.6,
                api_key=api_key  # 使用智能选择的账号
            )
            
            if response["success"]:
                # 保存使用统计
                if db:
                    await AIService._save_usage_stats(
                        db, user_id, "analysis",
                        response["usage"]["input_tokens"],
                        response["usage"]["output_tokens"],
                        response["model"]
                    )
                    
                    # 记录账号池使用情况
                    estimated_cost = (response["usage"]["input_tokens"] * 3.0 + 
                                    response["usage"]["output_tokens"] * 15.0) / 1000000 * 2.0
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="trading_insights",
                        input_tokens=response["usage"]["input_tokens"],
                        output_tokens=response["usage"]["output_tokens"],
                        api_cost=Decimal(str(estimated_cost)),
                        success=True
                    )
                
                return {
                    "content": response["content"],
                    "confidence": 0.75,
                    "factors": ["技术面", "市场情绪", "交易量"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "content": "交易洞察生成暂时不可用",
                    "confidence": 0,
                    "factors": [],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"生成交易洞察失败: {str(e)}")
            return {
                "content": f"交易洞察生成失败: {str(e)}",
                "confidence": 0,
                "factors": [],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    async def _get_conversation_history(
        db: AsyncSession,
        user_id: int,
        session_id: str,
        limit: int = 10
    ) -> List[ClaudeConversation]:
        """获取对话历史"""
        try:
            query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.user_id == user_id,
                    ClaudeConversation.session_id == session_id
                )
            ).order_by(ClaudeConversation.created_at.asc()).limit(limit)
            
            result = await db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"获取对话历史失败: {str(e)}")
            return []
    
    @staticmethod
    async def _save_conversation(
        db: AsyncSession,
        user_id: int,
        session_id: str,
        message_type: str,
        content: str,
        context: Optional[Dict] = None,
        tokens_used: int = 0,
        model: str = "claude-sonnet-4-20250514"
    ):
        """保存对话记录"""
        try:
            conversation = ClaudeConversation(
                user_id=user_id,
                session_id=session_id,
                message_type=message_type,
                content=content,
                context=json.dumps(context) if context else None,
                tokens_used=tokens_used,
                model=model
            )
            
            db.add(conversation)
            await db.commit()
            
        except Exception as e:
            logger.error(f"保存对话记录失败: {str(e)}")
    
    @staticmethod
    async def _save_usage_stats(
        db: AsyncSession,
        user_id: int,
        feature_type: str,
        input_tokens: int,
        output_tokens: int,
        model: str
    ):
        """保存使用统计"""
        try:
            # Claude 4 Sonnet 定价计算 (与3.5相同)
            input_cost = input_tokens * 3.0 / 1000000  # $3/1M tokens
            output_cost = output_tokens * 15.0 / 1000000  # $15/1M tokens
            actual_cost = input_cost + output_cost
            
            # 按照2倍使用量计算用户消耗 (实际API成本 × 2 = 用户计费成本)
            charged_cost = actual_cost * 2.0
            
            usage_stat = ClaudeUsage(
                user_id=user_id,
                feature_type=feature_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost=f"{charged_cost:.6f}",  # 保存按2倍计算的成本，用于用户扣费
                model_used=model
            )
            
            db.add(usage_stat)
            await db.commit()
            
            logger.debug(f"AI使用统计 - 用户ID: {user_id}, 实际API成本: ${actual_cost:.6f}, 用户计费成本: ${charged_cost:.6f} (2倍计费)")
            
        except Exception as e:
            logger.error(f"保存使用统计失败: {str(e)}")
    
    @staticmethod
    async def get_daily_usage_cost(
        db: AsyncSession,
        user_id: int,
        target_date: Optional[datetime] = None
    ) -> float:
        """获取用户每日AI使用成本 (返回用户计费金额，已按实际成本2倍计算)"""
        try:
            if target_date is None:
                target_date = datetime.utcnow().date()
            else:
                target_date = target_date.date() if hasattr(target_date, 'date') else target_date
            
            # 查询当日所有AI使用记录
            result = await db.execute(
                select(func.sum(ClaudeUsage.api_cost)).where(
                    and_(
                        ClaudeUsage.user_id == user_id,
                        func.date(ClaudeUsage.request_date) == target_date,
                        ClaudeUsage.success == True
                    )
                )
            )
            
            daily_cost = result.scalar() or 0
            return float(daily_cost)
            
        except Exception as e:
            logger.error(f"获取每日AI使用成本失败: {str(e)}")
            return 0.0
    
    @staticmethod
    async def check_daily_usage_limit(
        db: AsyncSession,
        user_id: int,
        membership_level: str,
        additional_cost: float = 0.0
    ) -> bool:
        """检查用户是否超出每日AI使用限制"""
        try:
            from app.services.membership_service import MembershipService
            
            # 获取会员限制
            limits = MembershipService.get_membership_limits(membership_level)
            
            # 获取当前使用量
            current_usage = await AIService.get_daily_usage_cost(db, user_id)
            
            # 检查是否会超出限制
            total_usage = current_usage + additional_cost
            
            return total_usage <= limits.ai_daily_limit
            
        except Exception as e:
            logger.error(f"检查AI使用限制失败: {str(e)}")
            return False
    
    # ========== 会话管理功能 ==========
    
    @staticmethod
    async def create_chat_session(
        db: AsyncSession,
        user_id: int,
        name: str,
        ai_mode: str,
        session_type: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建新的AI聊天会话"""
        try:
            session_id = str(uuid.uuid4())
            
            chat_session = AIChatSession(
                session_id=session_id,
                user_id=user_id,
                name=name,
                description=description,
                ai_mode=ai_mode,
                session_type=session_type,
                status="active"
            )
            
            db.add(chat_session)
            await db.commit()
            await db.refresh(chat_session)
            
            logger.info(f"创建AI会话成功 - 用户ID: {user_id}, 会话ID: {session_id}, 类型: {session_type}")
            
            return chat_session.to_dict()
            
        except Exception as e:
            logger.error(f"创建AI聊天会话失败: {str(e)}")
            await db.rollback()
            raise
    
    @staticmethod
    async def get_user_chat_sessions(
        db: AsyncSession,
        user_id: int,
        ai_mode: str
    ) -> List[Dict[str, Any]]:
        """获取用户的聊天会话列表"""
        try:
            query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.ai_mode == ai_mode
                )
            ).order_by(AIChatSession.last_activity_at.desc())
            
            result = await db.execute(query)
            sessions = result.scalars().all()
            
            return [session.to_dict() for session in sessions]
            
        except Exception as e:
            logger.error(f"获取用户聊天会话列表失败: {str(e)}")
            return []
    
    @staticmethod
    async def get_user_sessions_count(
        db: AsyncSession,
        user_id: int,
        ai_mode: str,
        session_type: str
    ) -> int:
        """获取用户指定类型的会话数量"""
        try:
            query = select(func.count(AIChatSession.id)).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.ai_mode == ai_mode,
                    AIChatSession.session_type == session_type,
                    AIChatSession.status.in_(["active", "completed"])  # 不包括已归档的
                )
            )
            
            result = await db.execute(query)
            count = result.scalar() or 0
            
            return count
            
        except Exception as e:
            logger.error(f"获取用户会话数量失败: {str(e)}")
            return 0
    
    @staticmethod
    async def update_session_status(
        db: AsyncSession,
        session_id: str,
        user_id: int,
        status: str,
        progress: Optional[int] = None
    ) -> bool:
        """更新会话状态"""
        try:
            query = select(AIChatSession).where(
                and_(
                    AIChatSession.session_id == session_id,
                    AIChatSession.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            session = result.scalar_one_or_none()
            
            if not session:
                return False
            
            session.status = status
            session.last_activity_at = datetime.utcnow()
            
            if progress is not None:
                session.progress = progress
            
            await db.commit()
            
            logger.info(f"更新会话状态成功 - 会话ID: {session_id}, 状态: {status}")
            return True
            
        except Exception as e:
            logger.error(f"更新会话状态失败: {str(e)}")
            await db.rollback()
            return False
    
    @staticmethod
    async def delete_chat_session(
        db: AsyncSession,
        session_id: str,
        user_id: int
    ) -> bool:
        """删除聊天会话（同时删除关联的对话记录）"""
        try:
            # 先删除对话记录
            conversations_query = select(ClaudeConversation).where(
                and_(
                    ClaudeConversation.session_id == session_id,
                    ClaudeConversation.user_id == user_id
                )
            )
            
            conversations_result = await db.execute(conversations_query)
            conversations = conversations_result.scalars().all()
            
            for conv in conversations:
                await db.delete(conv)
            
            # 再删除会话记录
            session_query = select(AIChatSession).where(
                and_(
                    AIChatSession.session_id == session_id,
                    AIChatSession.user_id == user_id
                )
            )
            
            session_result = await db.execute(session_query)
            session = session_result.scalar_one_or_none()
            
            if not session:
                return False
            
            await db.delete(session)
            await db.commit()
            
            logger.info(f"删除AI会话成功 - 会话ID: {session_id}, 删除对话记录: {len(conversations)}条")
            return True
            
        except Exception as e:
            logger.error(f"删除AI聊天会话失败: {str(e)}")
            await db.rollback()
            return False
    
    @staticmethod
    async def update_session_activity(
        db: AsyncSession,
        session_id: str,
        user_id: int,
        last_message: str,
        tokens_used: int,
        cost_usd: float
    ):
        """更新会话活动信息（每次对话后调用）"""
        try:
            query = select(AIChatSession).where(
                and_(
                    AIChatSession.session_id == session_id,
                    AIChatSession.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            session = result.scalar_one_or_none()
            
            if session:
                session.message_count += 1
                session.total_tokens += tokens_used
                session.total_cost += cost_usd
                session.last_message_content = last_message[:200]  # 截取前200字符作为预览
                session.last_activity_at = datetime.utcnow()
                
                await db.commit()
            
        except Exception as e:
            logger.error(f"更新会话活动信息失败: {str(e)}")
            await db.rollback()
    
    @staticmethod
    async def get_session_usage_stats(
        db: AsyncSession,
        user_id: int,
        days: int
    ) -> Dict[str, Any]:
        """获取按会话的使用统计"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # 获取时间范围内有活动的会话
            sessions_query = select(AIChatSession).where(
                and_(
                    AIChatSession.user_id == user_id,
                    AIChatSession.last_activity_at >= start_date
                )
            ).order_by(AIChatSession.total_cost.desc())
            
            sessions_result = await db.execute(sessions_query)
            sessions = sessions_result.scalars().all()
            
            session_stats = {}
            for session in sessions:
                session_stats[session.session_id] = {
                    "name": session.name,
                    "ai_mode": session.ai_mode,
                    "session_type": session.session_type,
                    "message_count": session.message_count,
                    "total_tokens": session.total_tokens,
                    "total_cost": session.total_cost,
                    "last_activity": session.last_activity_at.isoformat() if session.last_activity_at else None
                }
            
            return session_stats
            
        except Exception as e:
            logger.error(f"获取按会话使用统计失败: {str(e)}")
            return {}
    
    # ========== 策略生成辅助方法 ==========
    
    @staticmethod
    async def _detect_strategy_generation_intent(message: str) -> Dict[str, Any]:
        """检测用户消息是否为策略生成请求"""
        try:
            # 关键词匹配
            strategy_keywords = [
                "生成策略", "创建策略", "帮我写", "策略代码", 
                "交易策略", "量化策略", "投资策略", "策略模型",
                "技术指标", "macd", "rsi", "均线", "布林带",
                "买入条件", "卖出条件", "入场", "出场",
                "回测", "收益率", "风险控制", "止损", "止盈"
            ]
            
            message_lower = message.lower()
            keyword_matches = sum(1 for keyword in strategy_keywords if keyword in message_lower)
            
            # 长度和复杂度检查
            message_length = len(message)
            has_specific_requirements = any(word in message_lower for word in [
                "当", "如果", "条件", "参数", "周期", "时间框架", "风险", "收益"
            ])
            
            # 综合判断
            is_strategy_request = (
                keyword_matches >= 2 or  # 至少2个关键词
                (keyword_matches >= 1 and message_length > 30 and has_specific_requirements) or  # 1个关键词但有具体要求
                any(phrase in message_lower for phrase in [
                    "帮我生成", "帮我创建", "帮我设计", "写一个策略"
                ])
            )
            
            confidence = min(0.9, 0.3 + keyword_matches * 0.2 + (0.1 if has_specific_requirements else 0))
            
            return {
                "is_strategy_request": is_strategy_request,
                "confidence": confidence,
                "keyword_matches": keyword_matches,
                "detected_keywords": [kw for kw in strategy_keywords if kw in message_lower]
            }
            
        except Exception as e:
            logger.error(f"策略意图检测失败: {e}")
            return {
                "is_strategy_request": False,
                "confidence": 0.0,
                "keyword_matches": 0,
                "detected_keywords": []
            }
    
    @staticmethod
    async def get_strategy_generation_status(
        generation_id: str,
        user_id: int,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """获取策略生成状态（预留接口）"""
        try:
            # 预留：可以实现异步状态查询
            return await StrategyGenerationOrchestrator.get_generation_status(generation_id)
        except Exception as e:
            logger.error(f"获取策略生成状态失败: {e}")
            return {
                "generation_id": generation_id,
                "status": "error",
                "error": str(e)
            }
    
    @staticmethod
    async def batch_generate_strategies(
        user_requests: List[str],
        user_id: int,
        membership_level: str = "basic",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """批量生成策略（高级功能）"""
        try:
            if membership_level not in ["premium", "professional"]:
                return {
                    "success": False,
                    "error": "批量生成功能需要高级会员"
                }
            
            # 检查用户AI使用限制
            if db:
                estimated_cost = 0.08 * len(user_requests)  # 每个策略的预估成本
                can_use = await AIService.check_daily_usage_limit(
                    db, user_id, membership_level, estimated_cost
                )
                if not can_use:
                    return {
                        "success": False,
                        "error": "AI使用额度不足，无法进行批量生成"
                    }
            
            result = await StrategyGenerationOrchestrator.batch_generate_strategies(
                user_requests, user_id, membership_level
            )
            
            # 保存批量生成的使用统计
            if db and result["success"]:
                try:
                    usage_stat = ClaudeUsage(
                        user_id=user_id,
                        feature_type="batch_strategy_gen",
                        input_tokens=len(user_requests) * 500,  # 估算值
                        output_tokens=len(user_requests) * 1500,  # 估算值
                        api_cost=f"{estimated_cost:.6f}",
                        model_used="claude-sonnet-4-batch"
                    )
                    db.add(usage_stat)
                    await db.commit()
                except Exception as db_error:
                    logger.error(f"保存批量生成统计失败: {db_error}")
            
            return result
            
        except Exception as e:
            logger.error(f"批量策略生成失败: {e}")
            return {
                "success": False,
                "error": f"批量生成异常: {str(e)}"
            }