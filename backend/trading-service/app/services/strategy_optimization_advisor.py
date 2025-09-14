"""
策略优化建议系统

基于回测结果和AI分析，为策略提供专业的优化建议
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class StrategyOptimizationAdvisor:
    """策略优化顾问"""
    
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
    
    PERFORMANCE_THRESHOLDS = {
        "excellent": {"return": 0.3, "sharpe": 2.0, "drawdown": 0.1},
        "good": {"return": 0.15, "sharpe": 1.5, "drawdown": 0.15},
        "acceptable": {"return": 0.05, "sharpe": 1.0, "drawdown": 0.2},
        "poor": {"return": 0, "sharpe": 0.5, "drawdown": 0.3}
    }
    
    @staticmethod
    async def analyze_and_suggest(
        backtest_results: Dict[str, Any],
        original_intent: Dict[str, Any],
        strategy_code: str
    ) -> Dict[str, Any]:
        """分析回测结果并提供优化建议"""
        
        try:
            logger.info("开始策略优化分析")
            
            performance = backtest_results.get("performance", {})
            
            # 性能分类
            performance_level = StrategyOptimizationAdvisor._classify_performance(performance)
            
            # 识别问题
            issues = StrategyOptimizationAdvisor._identify_issues(performance, original_intent)
            
            # 生成基础建议
            basic_suggestions = StrategyOptimizationAdvisor._generate_basic_suggestions(performance, issues)
            
            # AI深度分析
            ai_analysis = await StrategyOptimizationAdvisor._generate_ai_analysis(
                performance, original_intent, strategy_code, issues
            )
            
            # 生成具体改进方案
            improvement_plan = StrategyOptimizationAdvisor._create_improvement_plan(
                issues, basic_suggestions, ai_analysis
            )
            
            # 预测改进效果
            expected_improvement = StrategyOptimizationAdvisor._estimate_improvement_potential(
                performance, issues
            )
            
            result = {
                "performance_level": performance_level,
                "identified_issues": issues,
                "basic_suggestions": basic_suggestions,
                "ai_analysis": ai_analysis,
                "improvement_plan": improvement_plan,
                "expected_improvement": expected_improvement,
                "priority_actions": StrategyOptimizationAdvisor._get_priority_actions(issues),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"策略优化分析完成: {len(issues)}个问题, {len(improvement_plan)}个改进方案")
            
            return result
            
        except Exception as e:
            logger.error(f"策略优化分析失败: {e}")
            return {
                "error": f"分析失败: {str(e)}",
                "performance_level": "unknown",
                "identified_issues": [],
                "basic_suggestions": [],
                "improvement_plan": []
            }
    
    @staticmethod
    def _classify_performance(performance: Dict[str, Any]) -> str:
        """性能分类"""
        total_return = performance.get("total_return", 0)
        sharpe_ratio = performance.get("sharpe_ratio", 0)
        max_drawdown = abs(performance.get("max_drawdown", 1))
        
        thresholds = StrategyOptimizationAdvisor.PERFORMANCE_THRESHOLDS
        
        if (total_return >= thresholds["excellent"]["return"] and 
            sharpe_ratio >= thresholds["excellent"]["sharpe"] and
            max_drawdown <= thresholds["excellent"]["drawdown"]):
            return "excellent"
        elif (total_return >= thresholds["good"]["return"] and 
              sharpe_ratio >= thresholds["good"]["sharpe"] and
              max_drawdown <= thresholds["good"]["drawdown"]):
            return "good"
        elif (total_return >= thresholds["acceptable"]["return"] and 
              sharpe_ratio >= thresholds["acceptable"]["sharpe"] and
              max_drawdown <= thresholds["acceptable"]["drawdown"]):
            return "acceptable"
        else:
            return "poor"
    
    @staticmethod
    def _identify_issues(performance: Dict[str, Any], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """识别策略问题"""
        issues = []
        
        total_return = performance.get("total_return", 0)
        sharpe_ratio = performance.get("sharpe_ratio", 0)
        max_drawdown = abs(performance.get("max_drawdown", 1))
        win_rate = performance.get("win_rate", 0)
        total_trades = performance.get("total_trades", 0)
        profit_factor = performance.get("profit_factor", 0)
        
        # 收益率问题
        expected_return = intent.get("expected_return", 10) / 100
        if total_return < 0:
            issues.append({
                "type": "negative_return",
                "severity": "high",
                "description": "策略产生负收益",
                "current_value": total_return,
                "target_value": expected_return,
                "impact": "策略无法盈利"
            })
        elif total_return < expected_return * 0.5:
            issues.append({
                "type": "low_return",
                "severity": "medium",
                "description": "收益率远低于预期",
                "current_value": total_return,
                "target_value": expected_return,
                "impact": "收益不达预期"
            })
        
        # 风险调整收益问题
        if sharpe_ratio < 0.5:
            issues.append({
                "type": "low_sharpe",
                "severity": "high" if sharpe_ratio < 0 else "medium",
                "description": "夏普比率过低",
                "current_value": sharpe_ratio,
                "target_value": 1.0,
                "impact": "风险调整收益不佳"
            })
        
        # 回撤问题
        max_acceptable_drawdown = intent.get("max_drawdown", 20) / 100
        if max_drawdown > max_acceptable_drawdown:
            issues.append({
                "type": "high_drawdown",
                "severity": "high" if max_drawdown > 0.3 else "medium",
                "description": "最大回撤过大",
                "current_value": max_drawdown,
                "target_value": max_acceptable_drawdown,
                "impact": "风险控制不足"
            })
        
        # 胜率问题
        if win_rate < 0.4:
            issues.append({
                "type": "low_win_rate",
                "severity": "medium",
                "description": "胜率偏低",
                "current_value": win_rate,
                "target_value": 0.5,
                "impact": "交易成功率低"
            })
        
        # 交易频率问题
        if total_trades < 5:
            issues.append({
                "type": "low_frequency",
                "severity": "medium",
                "description": "交易频率过低",
                "current_value": total_trades,
                "target_value": 20,
                "impact": "信号生成不足"
            })
        elif total_trades > 100:
            issues.append({
                "type": "high_frequency",
                "severity": "low",
                "description": "交易频率过高",
                "current_value": total_trades,
                "target_value": 50,
                "impact": "可能存在过度交易"
            })
        
        # 盈亏比问题
        if profit_factor < 1:
            issues.append({
                "type": "poor_profit_factor",
                "severity": "high",
                "description": "盈亏比小于1",
                "current_value": profit_factor,
                "target_value": 1.5,
                "impact": "平均亏损大于平均盈利"
            })
        
        return issues
    
    @staticmethod
    def _generate_basic_suggestions(performance: Dict[str, Any], issues: List[Dict[str, Any]]) -> List[str]:
        """生成基础优化建议"""
        suggestions = []
        
        issue_types = [issue["type"] for issue in issues]
        
        if "negative_return" in issue_types:
            suggestions.extend([
                "重新评估交易逻辑，可能需要反向操作",
                "增加趋势过滤条件，避免震荡市场交易",
                "调整入场时机，提高交易精度"
            ])
        
        if "low_return" in issue_types:
            suggestions.extend([
                "优化入场点位，寻找更好的买卖时机",
                "增加仓位管理策略，提高收益效率",
                "考虑添加其他技术指标作为辅助"
            ])
        
        if "low_sharpe" in issue_types:
            suggestions.extend([
                "加强风险控制，设置合理的止损点",
                "优化仓位大小，降低单笔交易风险",
                "提高交易信号质量，减少噪音交易"
            ])
        
        if "high_drawdown" in issue_types:
            suggestions.extend([
                "实施更严格的止损策略",
                "降低单笔交易的仓位比例",
                "增加市场环境判断，避免不利时期交易"
            ])
        
        if "low_win_rate" in issue_types:
            suggestions.extend([
                "提高入场条件的严格性",
                "增加确认信号，减少虚假突破",
                "优化技术指标参数"
            ])
        
        if "low_frequency" in issue_types:
            suggestions.extend([
                "放宽入场条件，增加交易机会",
                "使用更短的时间周期",
                "考虑多品种交易"
            ])
        
        if "high_frequency" in issue_types:
            suggestions.extend([
                "提高入场标准，过滤低质量信号",
                "增加信号确认时间",
                "考虑使用更长的时间周期"
            ])
        
        if "poor_profit_factor" in issue_types:
            suggestions.extend([
                "优化止盈止损比例",
                "改进出场策略，让盈利订单跑得更久",
                "快速止损，减少单笔大亏损"
            ])
        
        return list(set(suggestions))  # 去重
    
    @staticmethod
    async def _generate_ai_analysis(
        performance: Dict[str, Any],
        intent: Dict[str, Any],
        strategy_code: str,
        issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成AI深度分析"""
        
        try:
            analysis_prompt = f"""
作为资深量化策略分析师，请深度分析以下策略的回测表现：

回测性能指标：
{json.dumps(performance, indent=2, ensure_ascii=False)}

用户原始需求：
{json.dumps(intent, indent=2, ensure_ascii=False)}

识别的问题：
{json.dumps(issues, indent=2, ensure_ascii=False)}

策略代码片段：
```python
{strategy_code[:1000]}...  # 截取前1000字符
```

请从以下维度进行专业分析：

1. 根本原因分析：为什么会出现这些问题？
2. 市场适应性：策略在什么市场环境下表现更好？
3. 参数优化方向：哪些参数需要调整？
4. 逻辑改进建议：交易逻辑需要如何优化？
5. 风控增强方案：如何改善风险管理？

请以JSON格式返回：
{{
    "root_cause_analysis": "根本原因分析",
    "market_suitability": "市场适应性分析", 
    "parameter_optimization": ["参数优化建议1", "建议2"],
    "logic_improvements": ["逻辑改进建议1", "建议2"],
    "risk_management": ["风控建议1", "建议2"],
    "expected_performance": {{
        "return_improvement": "预期收益改善",
        "risk_reduction": "预期风险降低"
    }},
    "implementation_difficulty": "easy/medium/hard",
    "confidence_level": 0.85
}}
"""
            
            claude_client = await StrategyOptimizationAdvisor._get_claude_client()
            if not claude_client:
                return {
                    "success": False,
                    "error": "无法获取Claude客户端"
                }
                
            response = await claude_client.chat_completion(
                messages=[{"role": "user", "content": analysis_prompt}],
                system="你是专业的量化策略分析师，具有丰富的策略优化经验。",
                temperature=0.4
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
                    return {
                        "success": False,
                        "error": "AI响应格式异常"
                    }
                
                content = content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                analysis = json.loads(content)
                return {
                    "success": True,
                    "analysis": analysis
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"AI分析JSON解析失败: {e}, content: {content}")
                return {
                    "success": False,
                    "raw_response": content,
                    "error": "JSON解析失败"
                }
            except Exception as e:
                logger.error(f"处理AI响应失败: {e}")
                return {
                    "success": False,
                    "error": f"处理AI响应失败: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"AI分析异常: {e}")
            return {
                "success": False,
                "error": f"AI分析异常: {str(e)}"
            }
    
    @staticmethod
    def _create_improvement_plan(
        issues: List[Dict[str, Any]],
        basic_suggestions: List[str],
        ai_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """创建改进计划"""
        
        improvement_plan = []
        
        # 按优先级排序问题
        high_priority_issues = [issue for issue in issues if issue["severity"] == "high"]
        medium_priority_issues = [issue for issue in issues if issue["severity"] == "medium"]
        low_priority_issues = [issue for issue in issues if issue["severity"] == "low"]
        
        priority_order = high_priority_issues + medium_priority_issues + low_priority_issues
        
        for i, issue in enumerate(priority_order[:5]):  # 只处理前5个最重要的问题
            plan_item = {
                "priority": i + 1,
                "issue_type": issue["type"],
                "description": issue["description"],
                "severity": issue["severity"],
                "current_value": issue["current_value"],
                "target_value": issue["target_value"],
                "actions": StrategyOptimizationAdvisor._get_specific_actions(issue["type"]),
                "estimated_effort": StrategyOptimizationAdvisor._estimate_effort(issue["type"]),
                "expected_impact": StrategyOptimizationAdvisor._estimate_impact(issue["severity"])
            }
            
            # 添加AI建议
            if ai_analysis.get("success"):
                analysis = ai_analysis["analysis"]
                if issue["type"] in ["negative_return", "low_return"]:
                    plan_item["ai_suggestions"] = analysis.get("logic_improvements", [])
                elif issue["type"] in ["high_drawdown", "low_sharpe"]:
                    plan_item["ai_suggestions"] = analysis.get("risk_management", [])
                else:
                    plan_item["ai_suggestions"] = analysis.get("parameter_optimization", [])
            
            improvement_plan.append(plan_item)
        
        return improvement_plan
    
    @staticmethod
    def _get_specific_actions(issue_type: str) -> List[str]:
        """获取具体行动方案"""
        actions_map = {
            "negative_return": [
                "检查交易信号逻辑是否颠倒",
                "增加趋势确认指标",
                "调整入场和出场条件"
            ],
            "low_return": [
                "优化技术指标参数",
                "增加仓位利用率",
                "改进入场时机选择"
            ],
            "low_sharpe": [
                "实施动态止损策略",
                "优化仓位管理",
                "提高信号质量"
            ],
            "high_drawdown": [
                "设置严格止损",
                "降低单笔仓位",
                "增加市场状态过滤"
            ],
            "low_win_rate": [
                "提高入场标准",
                "增加信号确认",
                "优化技术指标组合"
            ],
            "low_frequency": [
                "降低入场阈值",
                "使用多个时间周期",
                "增加交易品种"
            ],
            "high_frequency": [
                "提高信号过滤标准",
                "增加冷却期",
                "使用更长时间周期"
            ],
            "poor_profit_factor": [
                "优化止盈止损比例",
                "改进盈利保护策略",
                "快速止损机制"
            ]
        }
        
        return actions_map.get(issue_type, ["需要进一步分析"])
    
    @staticmethod
    def _estimate_effort(issue_type: str) -> str:
        """估算修复工作量"""
        effort_map = {
            "negative_return": "high",
            "low_return": "medium",
            "low_sharpe": "medium",
            "high_drawdown": "medium",
            "low_win_rate": "medium",
            "low_frequency": "low",
            "high_frequency": "low",
            "poor_profit_factor": "medium"
        }
        
        return effort_map.get(issue_type, "medium")
    
    @staticmethod
    def _estimate_impact(severity: str) -> str:
        """估算修复影响"""
        impact_map = {
            "high": "significant",
            "medium": "moderate",
            "low": "minor"
        }
        
        return impact_map.get(severity, "moderate")
    
    @staticmethod
    def _estimate_improvement_potential(performance: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """评估改进潜力"""
        
        current_return = performance.get("total_return", 0)
        current_sharpe = performance.get("sharpe_ratio", 0)
        current_drawdown = abs(performance.get("max_drawdown", 1))
        
        # 基于问题严重性估算改进潜力
        high_severity_count = len([i for i in issues if i["severity"] == "high"])
        medium_severity_count = len([i for i in issues if i["severity"] == "medium"])
        
        # 估算收益率改进
        return_improvement = 0
        if high_severity_count > 0:
            return_improvement += 0.1 * high_severity_count
        if medium_severity_count > 0:
            return_improvement += 0.05 * medium_severity_count
        
        # 估算夏普比率改进
        sharpe_improvement = 0
        if current_sharpe < 1:
            sharpe_improvement = min(0.5, 0.2 * (high_severity_count + medium_severity_count))
        
        # 估算回撤改进
        drawdown_improvement = 0
        if current_drawdown > 0.15:
            drawdown_improvement = min(current_drawdown * 0.3, 0.1)
        
        return {
            "potential_return_improvement": return_improvement,
            "potential_sharpe_improvement": sharpe_improvement,
            "potential_drawdown_reduction": drawdown_improvement,
            "estimated_final_return": current_return + return_improvement,
            "estimated_final_sharpe": current_sharpe + sharpe_improvement,
            "estimated_final_drawdown": current_drawdown - drawdown_improvement,
            "improvement_probability": 0.7 if high_severity_count > 0 else 0.8,
            "time_to_improve": f"{2 + high_severity_count + medium_severity_count}天"
        }
    
    @staticmethod
    def _get_priority_actions(issues: List[Dict[str, Any]]) -> List[str]:
        """获取优先行动清单"""
        
        actions = []
        
        high_priority_issues = [issue for issue in issues if issue["severity"] == "high"]
        
        if any(issue["type"] == "negative_return" for issue in high_priority_issues):
            actions.append("🔥 立即检查交易逻辑，可能存在信号反向问题")
        
        if any(issue["type"] == "high_drawdown" for issue in high_priority_issues):
            actions.append("🛡️ 紧急加强止损机制，控制下行风险")
        
        if any(issue["type"] == "poor_profit_factor" for issue in high_priority_issues):
            actions.append("⚖️ 立即优化止盈止损比例")
        
        if any(issue["type"] == "low_sharpe" for issue in issues):
            actions.append("📊 提升信号质量，减少无效交易")
        
        if not actions:
            actions.append("🔧 优化技术指标参数，提升整体表现")
        
        return actions[:3]  # 返回前3个最重要的行动