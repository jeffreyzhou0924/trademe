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
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

# 这个导入已经不需要了，使用正确的Claude客户端
from app.ai.prompts.trading_prompts import TradingPrompts
from app.ai.prompts.system_prompts import SystemPrompts
from app.ai.prompts.strategy_flow_prompts import StrategyFlowPrompts
from app.models.claude_conversation import ClaudeConversation, GeneratedStrategy, AIChatSession
from app.models.claude_proxy import ClaudeUsageLog
from app.services.strategy_generation_orchestrator import StrategyGenerationOrchestrator
from app.services.claude_scheduler_service import claude_scheduler_service, SchedulerContext
from app.services.claude_account_service import claude_account_service
from app.services.dynamic_context_manager import dynamic_context_manager
from app.services.strategy_maturity_analyzer import StrategyMaturityAnalyzer
from app.services.backtest_config_checker import BacktestConfigChecker
from app.services.enhanced_auto_backtest_service import EnhancedAutoBacktestService
# from app.services.context_summarizer_service import context_summarizer  # 避免循环导入
from app.utils.data_validation import DataValidator


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
            
            # 获取对话历史用于成熟度分析
            conversation_history = []
            if db:
                try:
                    history_query = select(ClaudeConversation).where(
                        and_(
                            ClaudeConversation.user_id == user_id,
                            ClaudeConversation.session_id == session_id
                        )
                    ).order_by(ClaudeConversation.created_at.desc()).limit(10)
                    history_result = await db.execute(history_query)
                    history_messages = history_result.scalars().all()
                    conversation_history = [
                        {
                            "message_type": msg.message_type,
                            "content": msg.content,
                            "created_at": msg.created_at
                        }
                        for msg in reversed(history_messages)  # 保持时间顺序
                    ]
                except Exception as e:
                    logger.error(f"获取对话历史失败: {e}")
            
            # 检测用户是否确认生成代码
            if StrategyMaturityAnalyzer.is_user_confirming_generation(message):
                # 用户确认生成代码，执行策略生成流程
                membership_level = context.get('membership_level', 'basic') if context else 'basic'
                
                logger.info(f"用户确认生成策略代码 - 用户ID: {user_id}, 会话ID: {session_id}")
                
                # 检查回测配置
                config_check = await BacktestConfigChecker.check_user_backtest_config(
                    user_id=user_id,
                    membership_level=membership_level,
                    db=db
                )
                
                strategy_result = await AIService.generate_strategy_with_config_check(
                    user_input=message,
                    user_id=user_id,
                    membership_level=membership_level,
                    session_id=session_id,
                    config_check=config_check,
                    db=db
                )
                
                return strategy_result
            
            # 所有对话类型都尝试连接真实Claude服务
            session_type = context.get('session_type', 'general') if context else 'general'
            logger.info(f"AI对话请求 - 用户ID: {user_id}, 会话ID: {session_id}, 会话类型: {session_type}")
            
            # 如果不是策略请求，进入普通AI对话流程
            logger.info(f"进入普通AI对话 - 用户ID: {user_id}, 会话ID: {session_id}")
            
            # 初始化消息数组
            messages = []
            
            # 添加历史对话（最近5条）
            if db:
                try:
                    # 增强上下文管理 - 使用动态上下文管理器获取最优上下文窗口
                    enhanced_messages = await dynamic_context_manager.get_optimal_context_window(
                        user_id=user_id,
                        session_id=session_id,
                        session_type="general",
                        current_message=message,
                        db=db
                    )
                    messages = enhanced_messages
                except Exception as e:
                    logger.warning(f"动态上下文管理失败，使用基础历史: {e}")
                    
                    # 降级到基础历史获取
                    history_query = select(ClaudeConversation).where(
                        and_(
                            ClaudeConversation.user_id == user_id,
                            ClaudeConversation.session_id == session_id
                        )
                    ).order_by(ClaudeConversation.created_at.desc()).limit(5)
                    history_result = await db.execute(history_query)
                    history_messages = history_result.scalars().all()
                    
                    for msg in reversed(history_messages):
                        role = "user" if msg.message_type == "user" else "assistant"
                        messages.append({"role": role, "content": msg.content})
            
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
            
            # 调用真实Claude API（使用选定的账号）
            logger.info(f"🤖 调用真实Claude API - 账号: {selected_account.account_name}")
            
            # 根据会话类型和阶段选择合适的system prompt
            session_type = context.get('session_type', 'general') if context else 'general'
            system_prompt = SystemPrompts.TRADING_ASSISTANT_SYSTEM  # 默认prompt
            
            if session_type == 'strategy':
                # 策略会话使用专门的讨论阶段prompt  
                conversation_context = "\n".join([f"{msg['role']}: {msg['content'][:100]}..." for msg in messages[-3:]])
                system_prompt = StrategyFlowPrompts.get_discussion_prompt(conversation_context)
                logger.info(f"📋 使用策略讨论专用prompt - 会话ID: {session_id}")
            
            # 创建正确的Claude客户端实例
            from app.core.claude_client import ClaudeClient
            claude_client = ClaudeClient(
                api_key=api_key,
                base_url=selected_account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            try:
                # 真实Claude API调用
                response = await claude_client.chat_completion(
                        messages=messages,
                        system_prompt=system_prompt,
                        temperature=0.7,
                        api_key=api_key  # 使用智能选择的账号
                    )
            except Exception as e:
                logger.error(f"Claude API调用失败: {str(e)}")
                return {
                    "content": "AI服务繁忙，请稍后重试",
                    "session_id": session_id,
                    "tokens_used": 0,
                    "model": "service-unavailable",
                    "cost_usd": 0.0,
                    "success": False,
                    "requires_strategy_generation": False
                }
            
            # response已经是标准化格式: {"content": "...", "usage": {...}, "success": ...}
            # 计算总token数
            usage = response.get("usage", {})
            total_tokens = usage.get("total_tokens", 
                                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
            
            # 保存对话记录
            if db and response["success"]:
                await AIService._save_conversation(
                    db, user_id, session_id, "user", message, context
                )
                await AIService._save_conversation(
                    db, user_id, session_id, "assistant", response["content"], 
                    context, total_tokens, response.get("model", "claude")
                )
                
                # 保存使用统计
                await AIService._save_usage_stats(
                    db, user_id, "chat", 
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0),
                    response.get("model", "claude")
                )
                
                # 记录账号池使用情况
                estimated_cost = (usage.get("input_tokens", 0) * 3.0 + 
                                usage.get("output_tokens", 0) * 15.0) / 1000000 * 2.0
                await claude_account_service.log_usage(
                    account_id=selected_account.id,
                    user_id=user_id,
                    request_type="chat",
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    api_cost=Decimal(str(estimated_cost)),
                    response_time=None,  # TODO: 添加响应时间测量
                    success=True
                )
                
                # 更新会话活动信息
                cost_usd = (usage.get("input_tokens", 0) * 3.0 + usage.get("output_tokens", 0) * 15.0) / 1000000 * 2.0  # 2倍计费
                await AIService.update_session_activity(
                    db, session_id, user_id, 
                    response["content"][:200],  # 截取前200字符
                    total_tokens,
                    cost_usd
                )
                
                # =============== 策略成熟度分析 ===============
                # 如果是策略会话，分析对话成熟度
                session_type = context.get('session_type', 'general') if context else 'general'
                if session_type == 'strategy':
                    try:
                        logger.info(f"🔍 进行策略成熟度分析 - 会话ID: {session_id}")
                        
                        # 获取完整对话历史（包括刚保存的消息）
                        history_query = select(ClaudeConversation).where(
                            and_(
                                ClaudeConversation.user_id == user_id,
                                ClaudeConversation.session_id == session_id
                            )
                        ).order_by(ClaudeConversation.created_at.desc()).limit(20)
                        history_result = await db.execute(history_query)
                        conversation_history = history_result.scalars().all()
                        
                        # 进行成熟度分析
                        maturity_result = await StrategyMaturityAnalyzer.analyze_conversation_maturity(
                            conversation_history, message
                        )
                        
                        logger.info(f"📊 成熟度分析结果: {maturity_result.get('maturity_score', 0):.2f}, 准备生成: {maturity_result.get('ready_for_generation', False)}")
                        
                        # 如果策略讨论成熟，发送确认提示
                        if maturity_result.get("ready_for_generation", False):
                            confirmation_prompt = maturity_result.get("confirmation_prompt", "")
                            if confirmation_prompt:
                                # 保存确认提示为新的AI消息
                                await AIService._save_conversation(
                                    db, user_id, session_id, "assistant", confirmation_prompt,
                                    {"type": "maturity_confirmation"}, 0, "strategy-analyzer"
                                )
                                
                                logger.info(f"✅ 策略成熟度分析完成，已保存确认提示")
                                
                                # 修改返回内容，追加确认提示
                                response["content"] += "\n\n" + confirmation_prompt
                        
                    except Exception as maturity_error:
                        logger.error(f"❌ 策略成熟度分析失败: {maturity_error}")
                # =============== 策略成熟度分析结束 ===============
            
            # 检查Claude响应是否成功
            if not response.get("success", False):
                logger.error(f"Claude API响应失败: {response.get('error', 'Unknown error')}")
                return {
                    "content": "AI服务繁忙，请稍后重试",
                    "session_id": session_id,
                    "tokens_used": 0,
                    "model": "service-unavailable",
                    "cost_usd": 0.0,
                    "success": False,
                    "requires_strategy_generation": False
                }
            
            # 返回成功响应
            result = {
                "content": response.get("content", ""),
                "session_id": session_id,
                "tokens_used": total_tokens,
                "model": response.get("model", "claude"),
                "cost_usd": cost_usd,
                "success": True,
                "requires_strategy_generation": False
            }
            
            return result
            
        except Exception as e:
            # 增强异常信息记录
            error_str = str(e) if str(e) else "空异常对象"
            error_type = type(e).__name__
            logger.error(f"❌ AI对话失败详细分析:")
            logger.error(f"   📋 异常类型: {error_type}")
            logger.error(f"   📝 错误信息: '{error_str}'")
            logger.error(f"   🔍 原始异常: {repr(e)}")
            logger.error(f"   📄 异常参数: {e.args if hasattr(e, 'args') else 'No args'}")
            
            # 分析异常来源
            import traceback
            tb_str = traceback.format_exc()
            logger.error(f"   📍 异常堆栈: {tb_str}")
            
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
            
            # 构造详细的错误信息给WebSocket处理器
            detailed_error = f"AI服务调用失败: {error_type} - {error_str}"
            
            return {
                "content": "AI服务繁忙，请稍后重试",
                "session_id": session_id or str(uuid.uuid4()),
                "tokens_used": 0,
                "model": "service-unavailable",
                "success": False,
                "error": detailed_error,  # 添加错误字段供WebSocket处理器使用
                "requires_strategy_generation": False
            }
    
    @staticmethod
    async def stream_chat_completion(
        message: str,
        user_id: int,
        context: Optional[Dict] = None,
        session_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ):
        """流式AI聊天完成 - 实时返回数据块，支持策略成熟度分析"""
        
        try:
            # 检查每日使用限制
            membership_level = context.get('membership_level', 'basic') if context else 'basic'
            if db and not await AIService.check_daily_usage_limit(db, user_id, membership_level):
                yield {
                    "type": "ai_stream_error",
                    "error": "今日AI对话次数已达到限制",
                    "success": False
                }
                return
            
            # 获取会话ID
            if not session_id:
                session_id = str(uuid.uuid4())
                
            # 获取对话历史用于成熟度分析
            conversation_history = []
            if db:
                try:
                    history_query = select(ClaudeConversation).where(
                        and_(
                            ClaudeConversation.user_id == user_id,
                            ClaudeConversation.session_id == session_id
                        )
                    ).order_by(ClaudeConversation.created_at.desc()).limit(10)
                    history_result = await db.execute(history_query)
                    history_messages = history_result.scalars().all()
                    conversation_history = [
                        {
                            "message_type": msg.message_type,
                            "content": msg.content,
                            "created_at": msg.created_at
                        }
                        for msg in reversed(history_messages)  # 保持时间顺序
                    ]
                except Exception as e:
                    logger.error(f"获取对话历史失败: {e}")
            
            # =============== 策略意图检测和成熟度分析（与chat_completion一致）===============
            
            # 检测用户是否确认生成代码
            if StrategyMaturityAnalyzer.is_user_confirming_generation(message):
                # 用户确认生成代码，执行策略生成流程
                logger.info(f"[流式] 用户确认生成策略代码 - 用户ID: {user_id}, 会话ID: {session_id}")
                
                # 检查回测配置
                config_check = await BacktestConfigChecker.check_user_backtest_config(
                    user_id=user_id,
                    membership_level=membership_level,
                    db=db
                )
                
                # 流式返回策略生成结果
                yield {
                    "type": "ai_stream_start",
                    "session_id": session_id,
                    "model": "strategy-generation"
                }
                
                yield {
                    "type": "ai_stream_chunk",
                    "chunk": "🚀 开始生成策略代码...",
                    "session_id": session_id
                }
                
                strategy_result = await AIService.generate_strategy_with_config_check(
                    user_input=message,
                    user_id=user_id,
                    membership_level=membership_level,
                    session_id=session_id,
                    config_check=config_check,
                    db=db
                )
                
                # 流式返回策略生成结果
                if strategy_result["success"]:
                    final_content = f"""✅ **策略生成成功！**
                    
📊 **性能评级**: {strategy_result.get("backtest_results", {}).get("performance_grade", "未知")}
📈 **策略代码已生成并通过验证**
您可以在策略管理页面查看和使用生成的策略。"""
                else:
                    final_content = f"❌ **策略生成失败**: {strategy_result.get('error', '未知错误')}"
                
                yield {
                    "type": "ai_stream_chunk", 
                    "chunk": final_content,
                    "session_id": session_id
                }
                
                yield {
                    "type": "ai_stream_end",
                    "content": final_content,
                    "session_id": session_id,
                    "tokens_used": 100,  # 估算
                    "model": "strategy-generation"
                }
                
                # 保存用户确认消息和AI成功响应到数据库
                if db:
                    try:
                        # 保存用户确认消息
                        await AIService._save_conversation(
                            db, user_id, session_id, "user", message, context
                        )
                        # 保存AI策略生成成功响应
                        await AIService._save_conversation(
                            db, user_id, session_id, "assistant", final_content, 
                            {"type": "strategy_generation_success"}, 100, "strategy-generation"
                        )
                        logger.info(f"✅ [流式] 策略生成对话已保存到数据库 - 会话ID: {session_id}")
                    except Exception as e:
                        logger.error(f"❌ [流式] 保存策略生成对话失败: {e}")
                
                return
            
            # 所有对话类型都进入正常AI流式对话流程
            session_type = context.get('session_type', 'general') if context else 'general'
            logger.info(f"[流式] 进入普通AI对话 - 用户ID: {user_id}, 会话ID: {session_id}")
            
            # 构建消息列表
            messages = []
            for msg in conversation_history:
                role = "user" if msg["message_type"] == "user" else "assistant"
                messages.append({"role": role, "content": msg["content"]})
            messages.append({"role": "user", "content": message})
            
            # 使用Claude账号调度服务选择账号
            from app.services.claude_scheduler_service import claude_scheduler_service
            from app.services.claude_account_service import claude_account_service
            # 这个导入已经不需要了，使用正确的Claude客户端
            from decimal import Decimal
            
            scheduler_context = SchedulerContext(
                user_id=user_id,
                request_type="chat",
                session_id=session_id,
                min_quota=Decimal("0.02"),  # 预估单次对话成本
                priority=100
            )
            
            selected_account = await claude_scheduler_service.select_optimal_account(scheduler_context)
            if not selected_account:
                yield {
                    "type": "stream_error",
                    "error": "当前没有可用的Claude账号，请稍后重试",
                    "success": False
                }
                return
            
            # 获取解密的API密钥
            api_key = await claude_account_service.get_decrypted_api_key(selected_account.id)
            if not api_key:
                yield {
                    "type": "stream_error", 
                    "error": "Claude账号配置错误，请联系管理员",
                    "success": False
                }
                return
            
            logger.info(f"🌊 开始流式AI对话 - 用户: {user_id}, 账号: {selected_account.account_name}")
            
            # 流式处理变量
            full_content = ""
            total_tokens = 0
            cost_usd = 0.0
            
            # 根据会话类型选择system prompt
            session_type = context.get('session_type', 'general') if context else 'general'
            system_prompt = SystemPrompts.TRADING_ASSISTANT_SYSTEM  # 默认prompt
            
            if session_type == 'strategy':
                # 策略会话使用专门的讨论阶段prompt
                conversation_context = "\n".join([f"{msg['role']}: {msg['content'][:100]}..." for msg in messages[-3:]])
                system_prompt = StrategyFlowPrompts.get_discussion_prompt(conversation_context)
                logger.info(f"📋 流式对话使用策略讨论专用prompt - 会话ID: {session_id}")
            
            # 创建正确的Claude客户端实例
            from app.core.claude_client import ClaudeClient
            claude_client = ClaudeClient(
                api_key=api_key,
                base_url=selected_account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            # 使用流式Claude API
            try:
                async for chunk in claude_client.stream_chat_completion(
                    messages=messages,
                    system=system_prompt,
                    temperature=0.7
                ):
                    try:
                        chunk_type = chunk.get("type")
                        
                        if chunk_type == "stream_start":
                            # 流式开始
                            logger.info(f"🌊 AI流式响应开始 - 输入tokens: {chunk.get('input_tokens', 0)}")
                        
                            yield {
                                "type": "ai_stream_start",
                                "session_id": session_id,
                                "model": chunk.get("model", "claude-sonnet-4"),
                                "input_tokens": chunk.get("input_tokens", 0)
                            }
                        
                        elif chunk_type == "content_delta":
                            # 内容数据块
                            text_chunk = chunk.get("text", "")
                            full_content += text_chunk
                            
                            yield {
                                "type": "ai_stream_chunk",
                                "chunk": text_chunk,
                                "content_so_far": full_content,
                                "session_id": session_id
                            }
                        
                        elif chunk_type == "stream_end":
                            # 流式结束
                            usage = chunk.get("usage", {})
                            total_tokens = usage.get("total_tokens", 0)
                            cost_usd = (usage.get("input_tokens", 0) * 3.0 + 
                                       usage.get("output_tokens", 0) * 15.0) / 1000000 * 2.0
                            
                            logger.info(f"✅ AI流式对话完成 - Tokens: {total_tokens}, 成本: ${cost_usd:.6f}")
                        
                            # 记录使用日志
                            if db:
                                await claude_account_service.log_usage(
                                    account_id=selected_account.id,
                                    user_id=user_id,
                                    request_type="chat",
                                    input_tokens=usage.get("input_tokens", 0),
                                    output_tokens=usage.get("output_tokens", 0),
                                    api_cost=Decimal(str(cost_usd)),
                                    success=True
                                )
                                
                                # 保存对话记录
                                await AIService._save_conversation(
                                    db, user_id, session_id, "user", message
                                )
                                await AIService._save_conversation(
                                    db, user_id, session_id, "assistant", full_content, 
                                    context, total_tokens, usage.get("model", "claude-sonnet-4")
                                )
                            
                                # 更新会话活动
                                await AIService.update_session_activity(
                                    db, session_id, user_id, 
                                    full_content[:200],
                                    total_tokens,
                                    cost_usd
                                )
                                
                                # =============== 策略成熟度分析 ===============
                                # 如果是策略会话，分析对话成熟度
                                session_type = context.get('session_type', 'general') if context else 'general'
                                if session_type == 'strategy':
                                    try:
                                        logger.info(f"🔍 进行策略成熟度分析 - 会话ID: {session_id}")
                                        
                                        # 获取完整对话历史（包括刚保存的消息）
                                        history_query = select(ClaudeConversation).where(
                                            and_(
                                                ClaudeConversation.user_id == user_id,
                                                ClaudeConversation.session_id == session_id
                                            )
                                        ).order_by(ClaudeConversation.created_at.desc()).limit(20)
                                        history_result = await db.execute(history_query)
                                        conversation_history = history_result.scalars().all()
                                        
                                        # 进行成熟度分析
                                        maturity_result = await StrategyMaturityAnalyzer.analyze_conversation_maturity(
                                            conversation_history, message
                                        )
                                        
                                        logger.info(f"📊 成熟度分析结果: {maturity_result.get('overall_score', 0):.2f}, 准备生成: {maturity_result.get('ready_for_generation', False)}")
                                        
                                        # 如果策略讨论成熟，发送确认提示
                                        if maturity_result.get("ready_for_generation", False):
                                            confirmation_prompt = maturity_result.get("confirmation_prompt", "")
                                            if confirmation_prompt:
                                                # 保存确认提示为新的AI消息
                                                await AIService._save_conversation(
                                                    db, user_id, session_id, "assistant", confirmation_prompt,
                                                    {"type": "maturity_confirmation"}, 0, "strategy-analyzer"
                                                )
                                                
                                                # 发送额外的确认提示流事件
                                                yield {
                                                    "type": "strategy_maturity_confirmation",
                                                    "content": confirmation_prompt,
                                                    "maturity_score": maturity_result.get('overall_score', 0),
                                                    "session_id": session_id,
                                                    "ready_for_generation": True
                                                }
                                        
                                    except Exception as maturity_error:
                                        logger.error(f"❌ 策略成熟度分析失败: {maturity_error}")
                                # =============== 策略成熟度分析结束 ===============
                        
                            yield {
                                "type": "ai_stream_end",
                                "content": full_content,
                                "session_id": session_id,
                                "tokens_used": total_tokens,
                                "cost_usd": cost_usd,
                                "model": usage.get("model", "claude-sonnet-4"),
                                "success": True
                            }
                        
                        elif chunk_type == "stream_error":
                            # 流式错误
                            error_msg = chunk.get("error", "未知流式错误")
                            logger.error(f"❌ AI流式对话错误: {error_msg}")
                        
                            # 记录失败日志
                            if db and 'selected_account' in locals():
                                try:
                                    await claude_account_service.log_usage(
                                        account_id=selected_account.id,
                                        user_id=user_id,
                                        request_type="chat",
                                        input_tokens=0,
                                        output_tokens=0,
                                        api_cost=Decimal("0.0"),
                                        success=False,
                                        error_message=error_msg[:500]
                                    )
                                except Exception as log_error:
                                    logger.error(f"记录流式错误日志失败: {log_error}")
                        
                            yield {
                                "type": "ai_stream_error",
                                "error": "AI服务繁忙，请稍后重试",
                                "session_id": session_id,
                                "success": False
                            }
                            break
                        
                    except Exception as chunk_error:
                        logger.error(f"处理流式数据块错误: {chunk_error}")
                        yield {
                            "type": "ai_stream_error", 
                            "error": "AI服务繁忙，请稍后重试",
                            "session_id": session_id,
                            "success": False
                        }
                        break
                    
            except Exception as e:
                error_str = str(e)
                logger.error(f"❌ 流式Claude API调用失败: {error_str}")
                
                yield {
                    "type": "ai_stream_error",
                    "error": "AI服务繁忙，请稍后重试",
                    "session_id": session_id or str(uuid.uuid4()),
                    "success": False
                }
                
        except Exception as e:
            error_str = str(e)
            logger.error(f"❌ 流式AI对话失败: {error_str}")
            
            yield {
                "type": "ai_stream_error",
                "error": "AI服务繁忙，请稍后重试",
                "session_id": session_id or str(uuid.uuid4()),
                "success": False
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
                    usage_stat = ClaudeUsageLog(
                        user_id=user_id,
                        feature_type="complete_strategy_gen",
                        input_tokens=2000,  # 估算值，完整流程的token使用量
                        output_tokens=3000,  # 估算值
                        api_cost=DataValidator.safe_format_decimal(estimated_cost, decimals=6, currency="", default="0.000000"),
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
            
            # 创建正确的Claude客户端实例
            from app.core.claude_client import ClaudeClient
            claude_client = ClaudeClient(
                api_key=api_key,
                base_url=selected_account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            # 调用Claude进行市场分析
            response = await claude_client.analyze_market_data(
                market_data=market_data,
                symbols=symbols,
                analysis_type=analysis_type,
                api_key=api_key  # 使用智能选择的账号
            )
            
            if response.get("success"):
                # 保存使用统计
                usage = response.get("usage", {})
                if db:
                    await AIService._save_usage_stats(
                        db, user_id, "analysis",
                        usage.get("input_tokens", 0),
                        usage.get("output_tokens", 0),
                        response.get("model", "claude")
                    )
                    
                    # 记录账号池使用情况
                    estimated_cost = (usage.get("input_tokens", 0) * 3.0 + 
                                    usage.get("output_tokens", 0) * 15.0) / 1000000 * 2.0
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="market_analysis",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
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
            
            # 创建正确的Claude客户端实例
            from app.core.claude_client import ClaudeClient
            claude_client = ClaudeClient(
                api_key=api_key,
                base_url=selected_account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            response = await claude_client.chat_completion(
                messages=messages,
                system_prompt=prompts["system"],
                temperature=0.5,
                api_key=api_key  # 使用智能选择的账号
            )
            
            if response.get("success"):
                # 保存使用统计
                usage = response.get("usage", {})
                if db:
                    await AIService._save_usage_stats(
                        db, user_id, "analysis",
                        usage.get("input_tokens", 0),
                        usage.get("output_tokens", 0),
                        response.get("model", "claude")
                    )
                    
                    # 记录账号池使用情况
                    estimated_cost = (usage.get("input_tokens", 0) * 3.0 + 
                                    usage.get("output_tokens", 0) * 15.0) / 1000000 * 2.0
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="backtest_analysis",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
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
            query = select(ClaudeUsageLog).where(
                and_(
                    ClaudeUsageLog.user_id == user_id,
                    ClaudeUsageLog.request_date >= start_date
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
                "claude_client_stats": {}  # Claude客户端统计信息不可用
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
            
            # 创建正确的Claude客户端实例
            from app.core.claude_client import ClaudeClient
            claude_client = ClaudeClient(
                api_key=api_key,
                base_url=selected_account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            response = await claude_client.chat_completion(
                messages=messages,
                system_prompt=SystemPrompts.TRADING_ASSISTANT_SYSTEM,
                temperature=0.6,
                api_key=api_key  # 使用智能选择的账号
            )
            
            if response.get("success"):
                # 保存使用统计
                usage = response.get("usage", {})
                if db:
                    await AIService._save_usage_stats(
                        db, user_id, "analysis",
                        usage.get("input_tokens", 0),
                        usage.get("output_tokens", 0),
                        response.get("model", "claude")
                    )
                    
                    # 记录账号池使用情况
                    estimated_cost = (usage.get("input_tokens", 0) * 3.0 + 
                                    usage.get("output_tokens", 0) * 15.0) / 1000000 * 2.0
                    await claude_account_service.log_usage(
                        account_id=selected_account.id,
                        user_id=user_id,
                        request_type="trading_insights",
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
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
            
            usage_stat = ClaudeUsageLog(
                user_id=user_id,
                feature_type=feature_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost=DataValidator.safe_format_decimal(charged_cost, decimals=6, default="0.000000"),  # 保存按2倍计算的成本，用于用户扣费
                model_used=model
            )
            
            db.add(usage_stat)
            await db.commit()
            
            # 安全格式化成本显示
            actual_cost_formatted = DataValidator.safe_format_price(actual_cost, decimals=6)
            charged_cost_formatted = DataValidator.safe_format_price(charged_cost, decimals=6)
            logger.debug(f"AI使用统计 - 用户ID: {user_id}, 实际API成本: {actual_cost_formatted}, 用户计费成本: {charged_cost_formatted} (2倍计费)")
            
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
                select(func.sum(ClaudeUsageLog.api_cost)).where(
                    and_(
                        ClaudeUsageLog.user_id == user_id,
                        func.date(ClaudeUsageLog.request_date) == target_date,
                        ClaudeUsageLog.success == True
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
        """检测用户消息是否为策略生成请求 - 优化版"""
        try:
            # 强策略意图短语（直接判定为策略请求）
            strong_strategy_phrases = [
                "我想做一个", "我想创建", "我想生成", "我想写", "我想设计",
                "帮我做一个", "帮我创建", "帮我生成", "帮我写", "帮我设计",
                "生成一个", "创建一个", "设计一个", "写一个策略",
                "策略代码", "交易策略", "量化策略", "投资策略"
            ]
            
            # 技术指标关键词（高权重）
            technical_indicators = [
                "macd", "rsi", "kdj", "boll", "均线", "ma", "ema", "sma",
                "布林带", "成交量", "volume", "obv", "cci", "atr", "dmi"
            ]
            
            # 策略相关词汇
            strategy_keywords = [
                "策略", "背离", "突破", "反转", "趋势", "震荡",
                "买入", "卖出", "入场", "出场", "信号",
                "条件", "规则", "逻辑", "算法"
            ]
            
            message_lower = message.lower()
            
            # 检查强意图短语
            has_strong_intent = any(phrase in message_lower for phrase in strong_strategy_phrases)
            
            # 检查技术指标
            indicator_matches = sum(1 for indicator in technical_indicators if indicator in message_lower)
            
            # 检查策略词汇
            strategy_matches = sum(1 for keyword in strategy_keywords if keyword in message_lower)
            
            # 特殊策略类型检测
            strategy_types = ["背离", "突破", "反转", "网格", "马丁", "套利", "对冲"]
            has_strategy_type = any(stype in message_lower for stype in strategy_types)
            
            # 综合判断逻辑（更宽松）
            is_strategy_request = (
                has_strong_intent or  # 有明确的策略创建意图
                (indicator_matches >= 1 and (strategy_matches >= 1 or has_strategy_type)) or  # 技术指标+策略词汇
                strategy_matches >= 2 or  # 至少2个策略相关词汇
                (indicator_matches >= 2)  # 至少2个技术指标
            )
            
            # 计算置信度（确保策略请求有足够高的置信度）
            confidence = 0.2  # 基础置信度
            if has_strong_intent:
                confidence += 0.4
            confidence += min(0.3, indicator_matches * 0.15)  # 技术指标权重
            confidence += min(0.2, strategy_matches * 0.1)   # 策略词汇权重
            if has_strategy_type:
                confidence += 0.2
                
            confidence = min(0.95, confidence)  # 最大置信度限制
            
            # 如果是策略请求但置信度过低，提升到最低阈值
            if is_strategy_request and confidence < 0.6:
                confidence = 0.6
            
            all_matches = []
            if has_strong_intent:
                all_matches.extend([p for p in strong_strategy_phrases if p in message_lower])
            all_matches.extend([i for i in technical_indicators if i in message_lower])
            all_matches.extend([k for k in strategy_keywords if k in message_lower])
            
            return {
                "is_strategy_request": is_strategy_request,
                "confidence": confidence,
                "keyword_matches": len(all_matches),
                "detected_keywords": all_matches,
                "has_strong_intent": has_strong_intent,
                "indicator_matches": indicator_matches,
                "strategy_matches": strategy_matches
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
                    usage_stat = ClaudeUsageLog(
                        user_id=user_id,
                        feature_type="batch_strategy_gen",
                        input_tokens=len(user_requests) * 500,  # 估算值
                        output_tokens=len(user_requests) * 1500,  # 估算值
                        api_cost=DataValidator.safe_format_decimal(estimated_cost, decimals=6, currency="", default="0.000000"),
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
    
    @staticmethod
    async def generate_strategy_with_config_check(
        user_input: str,
        user_id: int,
        membership_level: str = "basic",
        session_id: Optional[str] = None,
        config_check: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        带回测配置检查和循环优化的策略生成流程
        
        新的完整流程：
        1. 生成策略代码但不在对话中展示
        2. 保存到数据库
        3. 检查回测配置，未配置则提醒
        4. 配置完整时自动执行回测
        5. 如果回测不达标，启动协作优化循环
        6. 只在策略库中展示生成的代码
        """
        try:
            # 检查用户AI使用限制
            if db:
                estimated_cost = 0.08
                can_use = await AIService.check_daily_usage_limit(
                    db, user_id, membership_level, estimated_cost
                )
                if not can_use:
                    return {
                        "content": "您今日的AI策略生成额度已用尽，请升级会员或明日再试",
                        "session_id": session_id,
                        "tokens_used": 0,
                        "model": "limit-exceeded",
                        "success": False
                    }
            
            # 调用策略生成编排器（不执行回测）
            result = await AIService._generate_strategy_code_only(
                user_input=user_input,
                user_id=user_id,
                user_membership=membership_level,
                session_id=session_id
            )
            
            if not result["success"]:
                return {
                    "content": f"策略生成失败：{result.get('error', '未知错误')}",
                    "session_id": session_id,
                    "tokens_used": 0,
                    "model": "generation-failed",
                    "success": False
                }
            
            # 保存策略到数据库（不在对话中展示代码）
            strategy_name = f"AI策略_{datetime.now().strftime('%m%d_%H%M')}"
            if db and result.get("strategy_code"):
                try:
                    generated_strategy = GeneratedStrategy(
                        user_id=user_id,
                        prompt=user_input,
                        generated_code=result["strategy_code"],
                        explanation=json.dumps(result.get("intent_analysis", {}), ensure_ascii=False),
                        parameters=json.dumps({
                            "generation_id": result["generation_id"],
                            "strategy_name": strategy_name,
                            "awaiting_backtest": True
                        }),
                        tokens_used=0,
                        generation_time_ms=int(result.get("execution_time", 0) * 1000),
                        model_used="claude-sonnet-4-orchestrated"
                    )
                    db.add(generated_strategy)
                    await db.commit()
                    logger.info(f"策略已保存到数据库 - 策略名称: {strategy_name}")
                    
                except Exception as e:
                    logger.error(f"保存策略到数据库失败: {e}")
                    return {
                        "content": "策略生成成功但保存失败，请重试",
                        "session_id": session_id,
                        "tokens_used": 0,
                        "model": "save-failed",
                        "success": False
                    }
            
            # 根据回测配置状态生成不同的响应
            if config_check and BacktestConfigChecker.should_skip_backtest(config_check):
                # 用户未配置回测，提醒配置
                notification = BacktestConfigChecker.generate_strategy_saved_notification(
                    strategy_name=strategy_name,
                    config_check=config_check,
                    generation_id=result["generation_id"]
                )
                
                return {
                    "content": notification,
                    "session_id": session_id,
                    "tokens_used": result.get("tokens_used", 0),
                    "model": "strategy-saved-config-needed",
                    "success": True,
                    "strategy_saved": True,
                    "needs_backtest_config": True
                }
            else:
                # 配置完整，执行增强回测和优化建议
                try:
                    # 使用增强回测服务进行完整的回测和优化建议
                    backtest_with_suggestions = await EnhancedAutoBacktestService.run_enhanced_backtest_with_suggestions(
                        strategy_code=result["strategy_code"],
                        intent=result.get("intent_analysis", {}),
                        user_id=user_id,
                        config=config_check or {},
                        db_session=db
                    )
                    
                    if backtest_with_suggestions["success"] and not backtest_with_suggestions["is_satisfactory"]:
                        # 回测不达标，启动协作优化系统
                        from app.services.collaborative_strategy_optimizer import collaborative_optimizer
                        
                        # 初始化优化会话
                        optimization_result = await collaborative_optimizer.start_optimization_conversation(
                            session_id=session_id or str(uuid.uuid4()),
                            user_id=user_id,
                            original_code=result["strategy_code"],
                            backtest_results=backtest_with_suggestions["backtest_results"],
                            user_intent=result.get("intent_analysis", {})
                        )
                        
                        if optimization_result["success"]:
                            return {
                                "content": optimization_result["message"],
                                "session_id": session_id,
                                "tokens_used": result.get("tokens_used", 0),
                                "model": "collaborative-optimization-start",
                                "success": True,
                                "strategy_saved": True,
                                "optimization_started": True,
                                "backtest_results": backtest_with_suggestions
                            }
                    
                    # 回测达标或者没有优化建议
                    performance_grade = backtest_with_suggestions.get("performance_grade", "F")
                    is_satisfactory = backtest_with_suggestions.get("is_satisfactory", False)
                    
                    notification = f"✅ **策略生成和回测完成**\n\n"
                    notification += f"📝 策略名称: {strategy_name}\n"
                    notification += f"📊 性能等级: {performance_grade}\n"
                    notification += f"🎯 达标状态: {'✅ 达标' if is_satisfactory else '⚠️ 需要优化'}\n\n"
                    
                    if is_satisfactory:
                        notification += "🎉 恭喜！您的策略表现优秀，可在策略库中查看详细结果并考虑实盘应用。"
                    else:
                        notification += "💡 虽然未完全达标，但策略已保存到您的策略库中，您可以根据建议进一步优化。"
                    
                    return {
                        "content": notification,
                        "session_id": session_id,
                        "tokens_used": result.get("tokens_used", 0),
                        "model": "strategy-completed",
                        "success": True,
                        "strategy_saved": True,
                        "backtest_completed": True,
                        "backtest_results": backtest_with_suggestions
                    }
                    
                except Exception as backtest_error:
                    logger.error(f"回测执行失败: {backtest_error}")
                    notification = f"✅ **策略已成功生成并保存**\n\n"
                    notification += f"📝 策略名称: {strategy_name}\n"
                    notification += f"⚠️ 回测执行遇到问题: {str(backtest_error)}\n\n"
                    notification += "策略代码已保存到策略库，您可以手动进行回测。"
                    
                    return {
                        "content": notification,
                        "session_id": session_id,
                        "tokens_used": result.get("tokens_used", 0),
                        "model": "strategy-saved-backtest-failed",
                        "success": True,
                        "strategy_saved": True,
                        "backtest_failed": True
                    }
                
        except Exception as e:
            logger.error(f"策略生成流程异常: {e}")
            return {
                "content": f"策略生成失败：{str(e)}",
                "session_id": session_id,
                "tokens_used": 0,
                "model": "system-error",
                "success": False
            }
    
    @staticmethod
    async def _generate_strategy_code_only(
        user_input: str,
        user_id: int,
        user_membership: str = "basic",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        只生成策略代码，不执行回测
        简化版的策略生成流程，用于新的用户体验
        """
        try:
            generation_id = str(uuid.uuid4())
            start_time = datetime.now()
            
            logger.info(f"开始策略代码生成 {generation_id} for user {user_id}")
            
            # 创建正确的Claude客户端（使用数据库代理配置）
            from app.core.claude_client import ClaudeClient
            from app.services.claude_account_service import claude_account_service
            
            account = await claude_account_service.select_best_account()
            if not account:
                return {
                    "generation_id": generation_id,
                    "success": False,
                    "stage": "client_init",
                    "error": "无可用的Claude账号"
                }
            
            # 解密API密钥
            decrypted_api_key = await claude_account_service.get_decrypted_api_key(account.id)
            
            if not decrypted_api_key:
                return {
                    "generation_id": generation_id,
                    "success": False,
                    "stage": "client_init",
                    "error": "无法解密Claude API密钥"
                }
            
            # 创建配置正确的Claude客户端
            proxy_claude_client = ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            logger.info(f"🔗 使用代理Claude客户端: {account.proxy_base_url}")
            
            # 1. 简化的意图分析（跳过复杂分析器）
            intent_analysis = {
                "strategy_type": "custom",
                "complexity": "medium",
                "indicators": ["MACD"],
                "timeframe": "1h",
                "risk_level": "medium"
            }
            
            # 2. 简化的兼容性检查（默认兼容）
            compatibility_check = {"compatible": True}
            
            # 3. 简化的策略代码生成 - 使用策略流程专用提示词
            generation_prompt = f"""
            基于以下用户需求和意图分析，生成一个完整的交易策略代码：
            
            用户需求：{user_input}
            意图分析：{json.dumps(intent_analysis, ensure_ascii=False)}
            
            请生成符合我们框架的策略代码，包含完整的入场、出场逻辑和风险控制。
            """
            
            response = await proxy_claude_client.chat_completion(
                messages=[{"role": "user", "content": generation_prompt}],
                system=TradingPrompts.ENHANCED_STRATEGY_GENERATION_SYSTEM,
                temperature=0.3
            )
            
            # 处理原始Anthropic API响应格式
            if isinstance(response, dict) and "content" in response:
                # 直接从Anthropic API响应中提取内容
                if isinstance(response["content"], list) and len(response["content"]) > 0:
                    strategy_code = response["content"][0].get("text", "")
                else:
                    strategy_code = response.get("content", "")
            elif isinstance(response, dict) and "success" in response:
                # 兼容旧格式
                if not response["success"]:
                    return {
                        "generation_id": generation_id,
                        "success": False,
                        "stage": "code_generation",
                        "error": f"策略代码生成失败: {response.get('error', '未知错误')}"
                    }
                strategy_code = response["content"]
            else:
                return {
                    "generation_id": generation_id,
                    "success": False,
                    "stage": "code_generation",
                    "error": f"未知的响应格式: {type(response)}"
                }
            
            if not strategy_code:
                return {
                    "generation_id": generation_id,
                    "success": False,
                    "stage": "code_generation",
                    "error": "策略代码生成为空"
                }
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "generation_id": generation_id,
                "success": True,
                "stage": "completed",
                "strategy_code": strategy_code,
                "intent_analysis": intent_analysis,
                "execution_time": execution_time,
                "tokens_used": response.get("usage", {}).get("total_tokens", 0)
            }
            
        except Exception as e:
            logger.error(f"策略代码生成异常: {e}")
            return {
                "generation_id": generation_id,
                "success": False,
                "stage": "system_error",
                "error": f"系统异常: {str(e)}"
            }