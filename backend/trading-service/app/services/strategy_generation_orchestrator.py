"""
AI策略生成完整流程编排器

整合策略意图分析、模板验证、自动修复、回测评估和优化建议的完整闭环系统
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from app.services.strategy_intent_analyzer import StrategyIntentAnalyzer
from app.services.strategy_template_validator import StrategyTemplateValidator
from app.services.enhanced_strategy_validator import EnhancedStrategyValidator
from app.services.strategy_auto_fix_service import StrategyAutoFixService
from app.services.auto_backtest_service import AutoBacktestService
from app.services.strategy_optimization_advisor import StrategyOptimizationAdvisor
from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import ClaudeAccountService


class StrategyGenerationOrchestrator:
    """AI策略生成完整流程编排器"""
    
    MAX_GENERATION_ATTEMPTS = 3
    MAX_OPTIMIZATION_CYCLES = 2
    
    @staticmethod
    async def generate_complete_strategy(
        user_input: str,
        user_id: int,
        user_membership: str = "basic",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        AI策略生成完整闭环流程
        
        流程: 意图分析 → 策略生成 → 模板验证 → 自动修复 → 自动回测 → 优化建议 → 迭代优化
        """
        
        generation_id = str(uuid.uuid4())
        session_id = session_id or generation_id
        start_time = datetime.now()
        
        logger.info(f"开始AI策略生成完整流程 {generation_id} for user {user_id}")
        
        try:
            # 第一步：用户意图分析
            logger.info(f"步骤1: 分析用户意图 - {generation_id}")
            intent_analysis = await StrategyIntentAnalyzer.analyze_user_intent(user_input)
            
            # 第二步：兼容性检查
            logger.info(f"步骤2: 兼容性检查 - {generation_id}")
            compatibility_check = await StrategyIntentAnalyzer.check_compatibility(
                intent_analysis, user_membership
            )
            
            if not compatibility_check["compatible"]:
                guidance = await StrategyIntentAnalyzer.generate_guidance(
                    intent_analysis, compatibility_check
                )
                return {
                    "generation_id": generation_id,
                    "success": False,
                    "stage": "compatibility_check",
                    "error": "策略需求与当前会员级别不兼容",
                    "intent_analysis": intent_analysis,
                    "compatibility_issues": compatibility_check["issues"],
                    "user_guidance": guidance,
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }
            
            # 第三步：AI策略代码生成
            logger.info(f"步骤3: AI策略生成 - {generation_id}")
            generation_result = await StrategyGenerationOrchestrator._generate_strategy_code(
                intent_analysis, user_input, session_id
            )
            
            if not generation_result["success"]:
                return {
                    "generation_id": generation_id,
                    "success": False,
                    "stage": "code_generation",
                    "error": generation_result["error"],
                    "intent_analysis": intent_analysis,
                    "execution_time": (datetime.now() - start_time).total_seconds()
                }
            
            strategy_code = generation_result["code"]
            generation_attempts = generation_result["attempts"]
            
            # 第四步：增强策略代码验证和自动修复
            logger.info(f"步骤4: 增强代码验证与修复 - {generation_id}")
            
            # 构建验证上下文
            validation_context = {
                "user_id": user_id,
                "membership_level": user_membership,
                "target_market": intent_analysis.get("trading_pair", "BTCUSDT"),
                "generation_id": generation_id
            }
            
            # 使用增强版策略校验器
            validation_result = await EnhancedStrategyValidator.validate_strategy_enhanced(
                strategy_code, validation_context
            )
            
            # 记录增强校验结果
            logger.info(f"增强校验完成 - 质量评分: {validation_result.get('final_quality_score', 0):.2f}, "
                       f"风险评分: {validation_result.get('risk_score', 0):.2f}")
            
            if not validation_result["valid"]:
                # 尝试自动修复
                fix_result = await StrategyAutoFixService.auto_fix_strategy(
                    strategy_code, validation_result["errors"], intent_analysis
                )
                
                if fix_result["success"]:
                    strategy_code = fix_result["fixed_code"]
                    logger.info(f"策略代码修复成功，使用{fix_result['attempts_used']}次尝试")
                    
                    # 重新验证修复后的代码
                    validation_result = await EnhancedStrategyValidator.validate_strategy_enhanced(
                        strategy_code, validation_context
                    )
                else:
                    return {
                        "generation_id": generation_id,
                        "success": False,
                        "stage": "enhanced_validation_and_fix",
                        "error": f"代码修复失败: {fix_result['error']}",
                        "validation_errors": validation_result["errors"],
                        "enhanced_analysis": validation_result.get("enhanced_checks", {}),
                        "quality_score": validation_result.get("final_quality_score", 0),
                        "fix_attempts": fix_result.get("attempts_used", 0),
                        "execution_time": (datetime.now() - start_time).total_seconds()
                    }
            
            # 第五步：自动回测评估
            logger.info(f"步骤5: 自动回测评估 - {generation_id}")
            backtest_result = await AutoBacktestService.auto_backtest_strategy(
                strategy_code, intent_analysis, user_id
            )
            
            performance_grade = backtest_result.get("performance_grade", "F")
            meets_expectations = backtest_result.get("meets_expectations", False)
            
            # 第六步：优化建议生成
            logger.info(f"步骤6: 生成优化建议 - {generation_id}")
            optimization_result = None
            if backtest_result.get("results"):
                optimization_result = await StrategyOptimizationAdvisor.analyze_and_suggest(
                    backtest_result["results"], intent_analysis, strategy_code
                )
            
            # 第七步：智能迭代优化（可选）
            final_result = {
                "generation_id": generation_id,
                "success": True,
                "strategy_code": strategy_code,
                "intent_analysis": intent_analysis,
                "validation_passed": True,
                "generation_attempts": generation_attempts,
                # 增强校验结果
                "enhanced_validation": {
                    "quality_score": validation_result.get("final_quality_score", 0),
                    "risk_score": validation_result.get("risk_score", 0),
                    "risk_level": validation_result.get("enhanced_checks", {}).get("risk_analysis", {}).get("risk_level", "未评估"),
                    "intelligent_suggestions": validation_result.get("intelligent_suggestions", []),
                    "optimization_opportunities": validation_result.get("optimization_opportunities", []),
                    "enhanced_checks": validation_result.get("enhanced_checks", {})
                },
                "backtest_results": {
                    "performance_grade": performance_grade,
                    "meets_expectations": meets_expectations,
                    "detailed_results": backtest_result.get("results"),
                    "backtest_report": backtest_result.get("report")
                },
                "optimization_advice": optimization_result,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "total_stages_completed": 6
            }
            
            # 如果性能不佳且用户是高级会员，尝试自动优化迭代
            if (not meets_expectations and 
                performance_grade in ["C", "D", "F"] and 
                user_membership in ["premium", "professional"]):
                
                logger.info(f"步骤7: 智能迭代优化 - {generation_id}")
                optimization_cycle_result = await StrategyGenerationOrchestrator._attempt_optimization_cycle(
                    strategy_code, intent_analysis, optimization_result, user_id, session_id
                )
                
                if optimization_cycle_result["success"]:
                    final_result.update({
                        "optimized_strategy_code": optimization_cycle_result["optimized_code"],
                        "optimization_cycles": optimization_cycle_result["cycles"],
                        "final_performance_grade": optimization_cycle_result["final_grade"],
                        "total_stages_completed": 7
                    })
            
            logger.info(f"AI策略生成完整流程成功完成 {generation_id}: grade={performance_grade}, optimized={final_result.get('optimization_cycles', 0)}次")
            
            return final_result
            
        except Exception as e:
            logger.error(f"AI策略生成流程异常 {generation_id}: {e}")
            return {
                "generation_id": generation_id,
                "success": False,
                "stage": "system_error",
                "error": f"系统异常: {str(e)}",
                "execution_time": (datetime.now() - start_time).total_seconds()
            }
    
    @staticmethod
    async def _generate_strategy_code(
        intent: Dict[str, Any],
        original_input: str,
        session_id: str,
        attempt: int = 1
    ) -> Dict[str, Any]:
        """AI策略代码生成"""
        
        if attempt > StrategyGenerationOrchestrator.MAX_GENERATION_ATTEMPTS:
            return {
                "success": False,
                "error": f"超过最大生成尝试次数 {StrategyGenerationOrchestrator.MAX_GENERATION_ATTEMPTS}",
                "attempts": attempt - 1
            }
        
        try:
            # 创建正确的Claude客户端（使用数据库代理配置）
            account = await ClaudeAccountService.get_available_account()
            if not account:
                return {
                    "success": False,
                    "error": "无可用的Claude账号",
                    "attempts": attempt
                }
            
            # 解密API密钥
            from app.security.crypto_manager import CryptoManager
            crypto_manager = CryptoManager()
            decrypted_api_key = crypto_manager.decrypt(account.api_key)
            
            if not decrypted_api_key:
                return {
                    "success": False,
                    "error": "无法解密Claude API密钥",
                    "attempts": attempt
                }
            
            # 创建配置正确的Claude客户端
            claude_client = ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            
            # 构建增强版策略生成提示词
            generation_prompt = f"""
基于用户需求和意图分析，生成专业的EnhancedBaseStrategy策略代码。

用户原始需求：
{original_input}

意图分析结果：
- 策略类型: {intent.get('strategy_type', '技术指标策略')}
- 主要指标: {', '.join(intent.get('primary_indicators', []))}
- 数据需求: {', '.join(intent.get('data_requirements', []))}
- 交易逻辑: {intent.get('trading_logic', '基于技术指标的交易策略')}
- 风险控制: {', '.join(intent.get('risk_controls', []))}

必须严格按照以下EnhancedBaseStrategy模板生成完整代码：

```python
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"基于用户需求的智能交易策略\"\"\"
    
    def get_data_requirements(self) -> List[DataRequest]:
        \"\"\"定义数据需求\"\"\"
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP",
                timeframe="1h",
                required=True
            )
            # 根据需求添加其他数据源...
        ]
    
    async def on_data_update(self, data_type: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        \"\"\"数据更新处理\"\"\"
        if data_type != "kline":
            return None
            
        df = self.get_kline_data()
        if df is None or len(df) < 20:
            return None
        
        # 实现具体的策略逻辑
        # 计算技术指标
        # 生成交易信号
        
        return None  # 或返回 TradingSignal
```

要求：
1. 根据意图分析实现具体的交易逻辑
2. 包含所需的技术指标计算
3. 实现明确的买入/卖出条件
4. 添加合理的风险控制
5. 确保代码语法正确且符合模板规范
6. 添加详细的中文注释

只返回完整的Python代码，用```python代码块包围。
"""
            
            response = await claude_client.chat_completion(
                messages=[{
                    "role": "user",
                    "content": generation_prompt
                }],
                system="你是专业的量化策略开发专家，严格按照EnhancedBaseStrategy框架生成高质量策略代码。",
                temperature=0.4
            )
            
            if response.get("success", False):
                # 提取代码
                content = response["content"]
                if "```python" in content:
                    code = content.split("```python")[1].split("```")[0].strip()
                elif "```" in content:
                    code = content.split("```")[1].split("```")[0].strip()
                else:
                    code = content.strip()
                
                return {
                    "success": True,
                    "code": code,
                    "attempts": attempt,
                    "raw_response": content
                }
            else:
                # 失败时重试
                if attempt < StrategyGenerationOrchestrator.MAX_GENERATION_ATTEMPTS:
                    logger.warning(f"第{attempt}次策略生成失败，重试中...")
                    await asyncio.sleep(1)  # 短暂延迟
                    return await StrategyGenerationOrchestrator._generate_strategy_code(
                        intent, original_input, session_id, attempt + 1
                    )
                else:
                    return {
                        "success": False,
                        "error": f"AI代码生成失败: {response.get('error', '未知错误')}",
                        "attempts": attempt
                    }
                    
        except Exception as e:
            logger.error(f"策略代码生成异常: {e}")
            return {
                "success": False,
                "error": f"代码生成异常: {str(e)}",
                "attempts": attempt
            }
    
    @staticmethod
    async def _attempt_optimization_cycle(
        original_code: str,
        intent: Dict[str, Any],
        optimization_advice: Dict[str, Any],
        user_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """智能优化迭代循环"""
        
        logger.info(f"开始策略优化迭代循环，session: {session_id}")
        
        best_code = original_code
        best_grade = "F"
        optimization_cycles = 0
        
        try:
            # 创建正确的Claude客户端（使用数据库代理配置）
            account = await ClaudeAccountService.get_available_account()
            if not account:
                logger.error("无可用的Claude账号")
                return {
                    "success": False,
                    "message": "无可用的Claude账号",
                    "best_code": original_code,
                    "optimization_cycles": 0
                }
            
            # 解密API密钥
            from app.security.crypto_manager import CryptoManager
            crypto_manager = CryptoManager()
            decrypted_api_key = crypto_manager.decrypt(account.api_key)
            
            if not decrypted_api_key:
                logger.error("无法解密Claude API密钥")
                return {
                    "success": False,
                    "message": "无法解密Claude API密钥",
                    "best_code": original_code,
                    "optimization_cycles": 0
                }
            
            # 创建配置正确的Claude客户端
            claude_client = ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
            logger.info(f"策略优化使用Claude账号: {account.account_name}, 代理: {account.proxy_base_url}")
            
            for cycle in range(StrategyGenerationOrchestrator.MAX_OPTIMIZATION_CYCLES):
                optimization_cycles += 1
                logger.info(f"优化迭代第{cycle + 1}轮")
                
                # 根据优化建议生成改进版本
                improvement_prompt = f"""
基于回测结果和优化建议，改进以下策略代码：

当前策略代码：
```python
{best_code}
```

优化建议：
{optimization_advice.get('improvement_plan', [])}

关键问题：
{optimization_advice.get('priority_actions', [])}

请生成改进版本的策略代码，重点解决识别的问题，提升策略表现。
严格按照EnhancedBaseStrategy模板，只返回完整的Python代码。
"""
                
                response = await claude_client.chat_completion(
                    messages=[{"role": "user", "content": improvement_prompt}],
                    system="你是量化策略优化专家，根据回测结果和分析建议改进策略性能。",
                    temperature=0.3
                )
                
                if not response.get("success", False):
                    break
                
                # 提取优化后的代码
                improved_code = response["content"]
                if "```python" in improved_code:
                    improved_code = improved_code.split("```python")[1].split("```")[0].strip()
                elif "```" in improved_code:
                    improved_code = improved_code.split("```")[1].split("```")[0].strip()
                
                # 验证改进版本
                validation = await StrategyTemplateValidator.validate_strategy(improved_code)
                if not validation["valid"]:
                    continue
                
                # 回测改进版本
                backtest_result = await AutoBacktestService.auto_backtest_strategy(
                    improved_code, intent, user_id
                )
                
                new_grade = backtest_result.get("performance_grade", "F")
                
                # 比较性能，保留更好的版本
                if StrategyGenerationOrchestrator._is_grade_better(new_grade, best_grade):
                    best_code = improved_code
                    best_grade = new_grade
                    logger.info(f"优化迭代成功：{best_grade} (第{cycle + 1}轮)")
                    
                    # 如果达到良好性能，提前结束
                    if best_grade in ["A+", "A", "B+"]:
                        break
                else:
                    logger.info(f"优化迭代无明显改善：{new_grade} vs {best_grade}")
            
            return {
                "success": True,
                "optimized_code": best_code,
                "final_grade": best_grade,
                "cycles": optimization_cycles,
                "improvement": best_grade != "F"
            }
            
        except Exception as e:
            logger.error(f"优化迭代循环异常: {e}")
            return {
                "success": False,
                "error": f"优化异常: {str(e)}",
                "cycles": optimization_cycles
            }
    
    @staticmethod
    def _is_grade_better(grade1: str, grade2: str) -> bool:
        """比较性能等级"""
        grade_order = ["F", "D", "C", "C+", "B", "B+", "A", "A+"]
        try:
            return grade_order.index(grade1) > grade_order.index(grade2)
        except ValueError:
            return False
    
    @staticmethod
    async def get_generation_status(generation_id: str) -> Dict[str, Any]:
        """获取策略生成状态（预留接口）"""
        # 预留：可以实现异步状态查询
        return {
            "generation_id": generation_id,
            "status": "completed",
            "progress": 100
        }
    
    @staticmethod
    async def batch_generate_strategies(
        user_requests: List[str],
        user_id: int,
        user_membership: str = "basic"
    ) -> Dict[str, Any]:
        """批量生成多个策略（高级功能）"""
        
        if user_membership not in ["premium", "professional"]:
            return {
                "success": False,
                "error": "批量生成功能需要高级会员"
            }
        
        logger.info(f"开始批量策略生成：{len(user_requests)}个请求")
        
        tasks = []
        for i, request in enumerate(user_requests):
            task = StrategyGenerationOrchestrator.generate_complete_strategy(
                request, user_id, user_membership, f"batch_{i}"
            )
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = [r for r in results if not isinstance(r, Exception) and r.get("success")]
        failed = [r for r in results if isinstance(r, Exception) or not r.get("success")]
        
        return {
            "success": True,
            "total_requests": len(user_requests),
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
            "success_rate": len(successful) / len(user_requests) if user_requests else 0
        }