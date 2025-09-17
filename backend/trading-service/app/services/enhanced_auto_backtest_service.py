"""
增强的自动回测服务 - 集成策略优化建议

当回测结果不达标时，自动生成详细的改进建议和具体行动方案
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger

from app.services.backtest_engine_stateless import StatelessBacktestEngine, BacktestConfig
from app.services.strategy_optimization_advisor import StrategyOptimizationAdvisor
from app.services.auto_backtest_service import calculate_performance_grade, check_performance_targets
from app.database import get_db


class EnhancedAutoBacktestService:
    """增强的自动回测服务"""
    
    @staticmethod
    async def run_enhanced_backtest_with_suggestions(
        strategy_code: str,
        intent: Dict[str, Any],
        user_id: int,
        config: Dict[str, Any],
        db_session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        运行增强回测并生成优化建议
        
        Returns:
        {
            "backtest_results": {...},           # 原始回测结果
            "performance_grade": "B+",           # 性能等级
            "is_satisfactory": false,            # 是否达标
            "optimization_suggestions": {...},   # 优化建议（不达标时）
            "user_friendly_summary": "...",      # 用户友好的总结
            "next_actions": [...],              # 下一步行动建议
            "improvement_plan": [...]           # 具体改进计划
        }
        """
        try:
            logger.info("开始增强回测分析")
            
            # 1. 运行常规回测
            backtest_results = await EnhancedAutoBacktestService._run_base_backtest(
                strategy_code, intent, user_id, config
            )
            
            if not backtest_results.get("success", False):
                return {
                    "success": False,
                    "error": "回测执行失败",
                    "details": backtest_results
                }
            
            performance = backtest_results.get("performance", {})
            
            # 2. 计算性能等级
            performance_grade = calculate_performance_grade(performance)
            
            # 3. 检查是否达标
            is_satisfactory = check_performance_targets(performance, intent)
            
            # 4. 生成用户友好摘要
            summary = EnhancedAutoBacktestService._generate_performance_summary(
                performance, performance_grade, is_satisfactory
            )
            
            result = {
                "success": True,
                "backtest_results": backtest_results,
                "performance_grade": performance_grade,
                "is_satisfactory": is_satisfactory,
                "user_friendly_summary": summary,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # 5. 如果不达标，生成优化建议
            if not is_satisfactory:
                logger.info("性能不达标，开始生成优化建议")
                
                optimization_suggestions = await StrategyOptimizationAdvisor.analyze_and_suggest(
                    backtest_results, intent, strategy_code
                )
                
                # 生成用户友好的改进建议
                user_suggestions = EnhancedAutoBacktestService._format_user_friendly_suggestions(
                    optimization_suggestions
                )
                
                result.update({
                    "optimization_suggestions": optimization_suggestions,
                    "next_actions": user_suggestions.get("priority_actions", []),
                    "improvement_plan": user_suggestions.get("improvement_plan", []),
                    "expected_improvement": optimization_suggestions.get("expected_improvement", {}),
                    "user_friendly_advice": user_suggestions.get("advice_text", "")
                })
            else:
                logger.info("策略性能达标，无需优化建议")
                result.update({
                    "optimization_suggestions": None,
                    "next_actions": [f"🎉 恭喜！您的策略达到{performance_grade}级标准，可以考虑实盘应用"],
                    "improvement_plan": [],
                    "user_friendly_advice": "策略表现优秀，建议进行更长时间段的回测验证后考虑实盘部署。"
                })
            
            logger.info(f"增强回测分析完成: 等级={performance_grade}, 达标={is_satisfactory}")
            return result
            
        except Exception as e:
            logger.error(f"增强回测分析失败: {e}")
            return {
                "success": False,
                "error": f"增强回测分析失败: {str(e)}",
                "backtest_results": None,
                "performance_grade": "F",
                "is_satisfactory": False
            }
    
    @staticmethod
    async def _run_base_backtest(
        strategy_code: str,
        intent: Dict[str, Any],
        user_id: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行基础回测 - 使用修复后的无状态引擎"""
        try:
            logger.info("🚀 使用无状态回测引擎执行真实回测")

            # 构建回测配置
            start_date = datetime.now() - timedelta(days=config.get("days_back", 30))
            end_date = datetime.now()

            backtest_config = BacktestConfig(
                strategy_code=strategy_code,
                symbol=config.get("symbol", "BTC-USDT-SWAP"),
                exchange="okx",
                timeframe=config.get("timeframe", "1h"),
                start_date=start_date,
                end_date=end_date,
                initial_capital=config.get("initial_capital", 10000.0),
                user_id=user_id
            )

            # 获取数据库连接并运行回测
            async for db in get_db():
                try:
                    result = await StatelessBacktestEngine.run_backtest(backtest_config, db)

                    if result.success:
                        logger.info("✅ 无状态引擎回测成功")
                        return {
                            "success": True,
                            "performance": result.metrics,
                            "config": {
                                "symbol": backtest_config.symbol,
                                "start_date": start_date,
                                "end_date": end_date,
                                "initial_capital": backtest_config.initial_capital,
                                "timeframe": backtest_config.timeframe
                            },
                            "trade_details": result.trades
                        }
                    else:
                        logger.error(f"❌ 回测失败: {result.error}")
                        return {
                            "success": False,
                            "error": f"回测执行失败: {result.error}",
                            "performance": {},
                            "trade_details": []
                        }
                finally:
                    await db.close()
                    break

        except Exception as e:
            logger.error(f"❌ 回测执行异常: {e}")
            return {
                "success": False,
                "error": f"回测执行异常: {str(e)}",
                "performance": {},
                "trade_details": []
            }
    
    @staticmethod
    def _generate_performance_summary(
        performance: Dict[str, Any], 
        grade: str, 
        is_satisfactory: bool
    ) -> str:
        """生成性能摘要"""
        
        total_return = performance.get("total_return", 0)
        sharpe_ratio = performance.get("sharpe_ratio", 0)
        max_drawdown = abs(performance.get("max_drawdown", 0))
        win_rate = performance.get("win_rate", 0)
        
        summary = f"📊 **策略回测报告** (等级: {grade})\n\n"
        
        # 核心指标展示
        summary += "**核心指标**:\n"
        summary += f"• 总收益率: {total_return:.1%}\n"
        summary += f"• 夏普比率: {sharpe_ratio:.2f}\n"  
        summary += f"• 最大回撤: {max_drawdown:.1%}\n"
        summary += f"• 胜率: {win_rate:.1%}\n\n"
        
        # 性能评价
        if is_satisfactory:
            summary += "✅ **评价**: 策略表现达到预期标准\n"
            summary += "建议进行更长周期测试后考虑实盘部署。"
        else:
            summary += "⚠️ **评价**: 策略表现需要改进\n"
            summary += "我们为您生成了详细的优化建议，请查看下方改进方案。"
        
        return summary
    
    @staticmethod
    def _format_user_friendly_suggestions(optimization_suggestions: Dict[str, Any]) -> Dict[str, Any]:
        """格式化用户友好的建议"""
        
        if not optimization_suggestions or "identified_issues" not in optimization_suggestions:
            return {
                "advice_text": "暂时无法生成优化建议，建议手动调整策略参数后重新回测。",
                "priority_actions": ["检查策略逻辑", "调整技术指标参数"],
                "improvement_plan": []
            }
        
        issues = optimization_suggestions.get("identified_issues", [])
        improvement_plan = optimization_suggestions.get("improvement_plan", [])
        priority_actions = optimization_suggestions.get("priority_actions", [])
        
        # 生成建议文本
        advice_text = "🔍 **策略诊断结果**:\n\n"
        
        if issues:
            advice_text += "发现以下需要改进的问题:\n"
            for i, issue in enumerate(issues[:3], 1):  # 只显示前3个问题
                severity_emoji = "🔴" if issue["severity"] == "high" else "🟡" if issue["severity"] == "medium" else "🟢"
                advice_text += f"{i}. {severity_emoji} {issue['description']}\n"
            
            advice_text += f"\n共识别 {len(issues)} 个问题，按优先级为您制定了改进方案。\n\n"
        
        # 格式化改进计划
        formatted_plan = []
        for plan_item in improvement_plan[:3]:  # 只显示前3个
            formatted_item = {
                "priority": plan_item.get("priority", 1),
                "title": plan_item.get("description", ""),
                "actions": plan_item.get("actions", []),
                "expected_impact": plan_item.get("expected_impact", "moderate"),
                "effort": plan_item.get("estimated_effort", "medium")
            }
            formatted_plan.append(formatted_item)
        
        advice_text += "💡 **改进建议**: 请按优先级依次实施改进方案，预期能显著提升策略表现。"
        
        return {
            "advice_text": advice_text,
            "priority_actions": priority_actions,
            "improvement_plan": formatted_plan
        }


class BacktestResultsFormatter:
    """回测结果格式化工具"""
    
    @staticmethod
    def format_for_ai_conversation(enhanced_results: Dict[str, Any]) -> str:
        """格式化回测结果用于AI对话"""
        
        if not enhanced_results.get("success", False):
            return "❌ 回测执行失败，请检查策略代码或联系技术支持。"
        
        grade = enhanced_results.get("performance_grade", "F")
        is_satisfactory = enhanced_results.get("is_satisfactory", False)
        summary = enhanced_results.get("user_friendly_summary", "")
        
        message = f"{summary}\n\n"
        
        if not is_satisfactory:
            advice = enhanced_results.get("user_friendly_advice", "")
            next_actions = enhanced_results.get("next_actions", [])
            
            message += f"{advice}\n\n"
            
            if next_actions:
                message += "🎯 **立即行动建议**:\n"
                for i, action in enumerate(next_actions[:3], 1):
                    message += f"{i}. {action}\n"
                message += "\n"
            
            improvement_plan = enhanced_results.get("improvement_plan", [])
            if improvement_plan:
                message += "📋 **详细改进计划**:\n"
                for plan_item in improvement_plan:
                    title = plan_item.get("title", "")
                    effort = plan_item.get("effort", "medium")
                    impact = plan_item.get("expected_impact", "moderate")
                    
                    effort_emoji = "🟢" if effort == "low" else "🟡" if effort == "medium" else "🔴"
                    impact_emoji = "⭐" if impact == "minor" else "⭐⭐" if impact == "moderate" else "⭐⭐⭐"
                    
                    message += f"• {title} ({effort_emoji}工作量: {effort}, {impact_emoji}预期效果: {impact})\n"
                message += "\n"
            
            expected_improvement = enhanced_results.get("expected_improvement", {})
            if expected_improvement:
                final_return = expected_improvement.get("estimated_final_return", 0)
                improvement_time = expected_improvement.get("time_to_improve", "5天")
                
                message += f"🚀 **预期改进效果**: 优化后收益率可达 {final_return:.1%}, 预计耗时 {improvement_time}\n\n"
        
        message += "您希望我详细解释某个改进建议，还是开始优化策略代码？"
        
        return message