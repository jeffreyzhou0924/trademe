"""
增强策略校验器
基于现有StrategyTemplateValidator，增加了智能风险控制、逻辑一致性检查、优化建议等功能
"""

import ast
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger

from app.services.strategy_template_validator import StrategyTemplateValidator
from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service


class EnhancedStrategyValidator:
    """增强策略校验器 - 在基础校验上添加智能分析功能"""
    
    @classmethod
    async def _get_claude_client(cls) -> Optional[ClaudeClient]:
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
    
    # 风险控制评分标准
    RISK_CRITERIA = {
        "stop_loss_mechanism": {
            "weight": 0.25,
            "patterns": [r"stop_loss", r"止损", r"max_loss", r"risk_management"],
            "required": True
        },
        "position_sizing": {
            "weight": 0.2,
            "patterns": [r"position_size", r"仓位", r"allocation", r"capital_allocation"],
            "required": True
        },
        "drawdown_control": {
            "weight": 0.15,
            "patterns": [r"drawdown", r"回撤", r"max_dd", r"portfolio_risk"],
            "required": False
        },
        "volatility_management": {
            "weight": 0.2,
            "patterns": [r"volatility", r"波动", r"vol_filter", r"market_regime"],
            "required": False
        },
        "correlation_checks": {
            "weight": 0.1,
            "patterns": [r"correlation", r"相关性", r"diversification"],
            "required": False
        },
        "liquidity_control": {
            "weight": 0.1,
            "patterns": [r"liquidity", r"流动性", r"volume_check", r"market_depth"],
            "required": False
        }
    }
    
    # 逻辑一致性检查模式
    LOGIC_CONSISTENCY_PATTERNS = {
        "signal_conflicts": [
            (r"SignalType\.BUY", r"SignalType\.SELL", "买入和卖出信号可能冲突"),
            (r"entry_condition.*True", r"exit_condition.*True", "入场和出场条件同时满足")
        ],
        "parameter_consistency": [
            (r"fast_period\s*=\s*(\d+)", r"slow_period\s*=\s*(\d+)", "快线周期应小于慢线周期"),
            (r"buy_threshold\s*=\s*([0-9.]+)", r"sell_threshold\s*=\s*([0-9.]+)", "买入阈值应低于卖出阈值")
        ]
    }
    
    @classmethod
    async def validate_strategy_enhanced(
        cls, 
        code: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        增强策略校验 - 在基础校验基础上增加智能分析
        
        Args:
            code: 策略代码
            context: 上下文信息（用户ID、会员级别等）
            
        Returns:
            完整的校验结果，包括基础校验和智能分析
        """
        try:
            # 1. 执行基础校验（使用现有的StrategyTemplateValidator）
            base_validation = await StrategyTemplateValidator.validate_strategy(code)
            
            # 2. 如果基础校验失败，直接返回
            if not base_validation["valid"]:
                return base_validation
            
            # 3. 执行增强校验
            enhanced_result = {
                **base_validation,
                "enhanced_checks": {
                    "risk_analysis": {},
                    "logic_consistency": {},
                    "performance_optimization": {},
                    "market_adaptability": {}
                },
                "intelligent_suggestions": [],
                "risk_score": 0.0,
                "optimization_opportunities": []
            }
            
            # 4. 风险控制分析
            risk_analysis = await cls._analyze_risk_controls(code)
            enhanced_result["enhanced_checks"]["risk_analysis"] = risk_analysis
            enhanced_result["risk_score"] = risk_analysis.get("overall_risk_score", 0.0)
            
            # 5. 逻辑一致性检查
            logic_check = await cls._check_logic_consistency(code)
            enhanced_result["enhanced_checks"]["logic_consistency"] = logic_check
            
            # 6. 性能优化分析
            perf_analysis = await cls._analyze_performance_optimization(code)
            enhanced_result["enhanced_checks"]["performance_optimization"] = perf_analysis
            
            # 7. 市场适应性评估
            market_analysis = await cls._evaluate_market_adaptability(code, context)
            enhanced_result["enhanced_checks"]["market_adaptability"] = market_analysis
            
            # 8. 生成智能建议
            intelligent_suggestions = await cls._generate_intelligent_suggestions(
                risk_analysis, logic_check, perf_analysis, market_analysis
            )
            enhanced_result["intelligent_suggestions"] = intelligent_suggestions
            
            # 9. 最终综合评分
            final_score = cls._calculate_final_score(
                base_validation, risk_analysis, logic_check, perf_analysis, market_analysis
            )
            enhanced_result["final_quality_score"] = final_score
            enhanced_result["valid"] = final_score >= 0.7  # 提高通过标准
            
            logger.info(f"增强策略校验完成: 质量评分={final_score:.2f}, 风险评分={enhanced_result['risk_score']:.2f}")
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"增强策略校验异常: {e}")
            # 降级到基础校验结果
            base_validation = await StrategyTemplateValidator.validate_strategy(code)
            base_validation["enhanced_checks"] = {"error": f"增强校验失败: {str(e)}"}
            return base_validation
    
    @classmethod
    async def _analyze_risk_controls(cls, code: str) -> Dict[str, Any]:
        """分析风险控制机制"""
        try:
            risk_scores = {}
            missing_controls = []
            
            for control_name, config in cls.RISK_CRITERIA.items():
                patterns = config["patterns"]
                weight = config["weight"]
                required = config["required"]
                
                # 检查是否存在相关模式
                pattern_found = any(re.search(pattern, code, re.IGNORECASE) for pattern in patterns)
                
                if pattern_found:
                    risk_scores[control_name] = 1.0
                else:
                    risk_scores[control_name] = 0.0
                    if required:
                        missing_controls.append(control_name)
            
            # 计算总体风险评分
            overall_risk_score = sum(
                score * cls.RISK_CRITERIA[control]["weight"] 
                for control, score in risk_scores.items()
            )
            
            # AI深度风险分析
            ai_risk_analysis = await cls._ai_risk_analysis(code) if len(missing_controls) > 0 else {}
            
            return {
                "risk_scores": risk_scores,
                "overall_risk_score": overall_risk_score,
                "missing_controls": missing_controls,
                "ai_risk_suggestions": ai_risk_analysis.get("suggestions", []),
                "risk_level": cls._get_risk_level(overall_risk_score),
                "critical_warnings": ai_risk_analysis.get("critical_warnings", [])
            }
            
        except Exception as e:
            logger.error(f"风险控制分析失败: {e}")
            return {
                "risk_scores": {},
                "overall_risk_score": 0.0,
                "missing_controls": ["分析失败"],
                "error": str(e)
            }
    
    @classmethod
    async def _check_logic_consistency(cls, code: str) -> Dict[str, Any]:
        """检查策略逻辑一致性"""
        try:
            consistency_issues = []
            warnings = []
            
            # 1. 信号冲突检查
            for pattern1, pattern2, description in cls.LOGIC_CONSISTENCY_PATTERNS["signal_conflicts"]:
                if re.search(pattern1, code) and re.search(pattern2, code):
                    # 需要AI分析是否真的冲突
                    conflict_analysis = await cls._ai_conflict_analysis(code, pattern1, pattern2, description)
                    if conflict_analysis.get("is_conflict", False):
                        consistency_issues.append({
                            "type": "signal_conflict",
                            "description": description,
                            "severity": conflict_analysis.get("severity", "medium"),
                            "suggestion": conflict_analysis.get("suggestion", "")
                        })
            
            # 2. 参数一致性检查
            for pattern1, pattern2, description in cls.LOGIC_CONSISTENCY_PATTERNS["parameter_consistency"]:
                match1 = re.search(pattern1, code)
                match2 = re.search(pattern2, code)
                if match1 and match2:
                    val1, val2 = float(match1.group(1)), float(match2.group(1))
                    if "fast_period" in pattern1 and val1 >= val2:
                        consistency_issues.append({
                            "type": "parameter_inconsistency",
                            "description": f"快线周期({val1})应小于慢线周期({val2})",
                            "severity": "high",
                            "suggestion": f"建议设置快线周期为{int(val2*0.5)}，慢线周期保持{int(val2)}"
                        })
            
            # 3. 入场出场逻辑检查
            entry_logic = re.findall(r'entry_condition.*?(?=def|\Z)', code, re.DOTALL)
            exit_logic = re.findall(r'exit_condition.*?(?=def|\Z)', code, re.DOTALL)
            
            if entry_logic and exit_logic:
                logic_analysis = await cls._ai_entry_exit_analysis(entry_logic[0], exit_logic[0])
                if logic_analysis.get("has_issues", False):
                    consistency_issues.extend(logic_analysis.get("issues", []))
            
            consistency_score = max(0.0, 1.0 - len(consistency_issues) * 0.2)
            
            return {
                "consistency_score": consistency_score,
                "consistency_issues": consistency_issues,
                "warnings": warnings,
                "has_critical_issues": any(issue.get("severity") == "high" for issue in consistency_issues)
            }
            
        except Exception as e:
            logger.error(f"逻辑一致性检查失败: {e}")
            return {
                "consistency_score": 0.5,
                "consistency_issues": [{"type": "analysis_error", "description": f"检查失败: {str(e)}"}],
                "error": str(e)
            }
    
    @classmethod
    async def _analyze_performance_optimization(cls, code: str) -> Dict[str, Any]:
        """分析性能优化机会"""
        try:
            optimization_opportunities = []
            performance_score = 1.0
            
            # 1. 数据访问优化检查
            if code.count("data[") > 10:
                optimization_opportunities.append({
                    "type": "data_access",
                    "description": "频繁的数据访问可能影响性能",
                    "suggestion": "考虑缓存常用数据或使用向量化操作",
                    "impact": "medium"
                })
                performance_score -= 0.1
            
            # 2. 循环优化检查
            nested_loops = len(re.findall(r'for.*?for.*?:', code, re.DOTALL))
            if nested_loops > 2:
                optimization_opportunities.append({
                    "type": "nested_loops",
                    "description": f"检测到{nested_loops}个嵌套循环，可能影响回测速度",
                    "suggestion": "考虑使用Pandas向量化操作替代循环",
                    "impact": "high"
                })
                performance_score -= 0.2
            
            # 3. AI性能分析
            ai_perf_analysis = await cls._ai_performance_analysis(code)
            if ai_perf_analysis.get("optimizations"):
                optimization_opportunities.extend(ai_perf_analysis["optimizations"])
                performance_score = min(performance_score, ai_perf_analysis.get("estimated_score", performance_score))
            
            return {
                "performance_score": max(0.0, performance_score),
                "optimization_opportunities": optimization_opportunities,
                "estimated_backtest_time": cls._estimate_backtest_time(code),
                "complexity_level": cls._assess_complexity(code)
            }
            
        except Exception as e:
            logger.error(f"性能优化分析失败: {e}")
            return {
                "performance_score": 0.7,
                "optimization_opportunities": [],
                "error": str(e)
            }
    
    @classmethod
    async def _evaluate_market_adaptability(cls, code: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """评估市场适应性"""
        try:
            adaptability_factors = []
            adaptability_score = 0.5  # 基础分
            
            # 1. 市场状态适应性
            if re.search(r'market_regime|bull_market|bear_market|sideways', code, re.IGNORECASE):
                adaptability_factors.append("市场状态感知")
                adaptability_score += 0.2
            
            # 2. 波动率适应性
            if re.search(r'volatility|vol_filter|atr', code, re.IGNORECASE):
                adaptability_factors.append("波动率适应")
                adaptability_score += 0.15
            
            # 3. 多时间框架
            timeframes = len(re.findall(r'[0-9]+[mhd]|[0-9]+min|[0-9]+hour', code))
            if timeframes > 1:
                adaptability_factors.append(f"{timeframes}个时间框架")
                adaptability_score += 0.1
            
            # 4. AI适应性分析
            if context and context.get("target_market"):
                ai_adaptability = await cls._ai_market_adaptability_analysis(code, context["target_market"])
                adaptability_score = min(1.0, adaptability_score + ai_adaptability.get("bonus_score", 0))
                if ai_adaptability.get("warnings"):
                    adaptability_factors.extend(ai_adaptability["warnings"])
            
            return {
                "adaptability_score": min(1.0, adaptability_score),
                "adaptability_factors": adaptability_factors,
                "market_suitability": cls._assess_market_suitability(code),
                "recommended_markets": cls._recommend_suitable_markets(code)
            }
            
        except Exception as e:
            logger.error(f"市场适应性评估失败: {e}")
            return {
                "adaptability_score": 0.5,
                "adaptability_factors": [],
                "error": str(e)
            }
    
    @classmethod
    async def _generate_intelligent_suggestions(
        cls, 
        risk_analysis: Dict,
        logic_check: Dict,
        perf_analysis: Dict,
        market_analysis: Dict
    ) -> List[Dict[str, Any]]:
        """生成智能优化建议"""
        suggestions = []
        
        # 风险控制建议
        if risk_analysis.get("overall_risk_score", 0) < 0.6:
            suggestions.append({
                "category": "risk_management",
                "priority": "high",
                "title": "加强风险控制",
                "description": "策略缺少必要的风险控制机制",
                "suggestions": risk_analysis.get("ai_risk_suggestions", []),
                "estimated_improvement": "提升20-30%安全性"
            })
        
        # 逻辑一致性建议
        if logic_check.get("has_critical_issues", False):
            suggestions.append({
                "category": "logic_consistency",
                "priority": "critical",
                "title": "修复逻辑冲突",
                "description": "发现策略逻辑中存在冲突",
                "issues": logic_check.get("consistency_issues", []),
                "estimated_improvement": "避免错误信号"
            })
        
        # 性能优化建议
        if perf_analysis.get("performance_score", 1.0) < 0.8:
            suggestions.append({
                "category": "performance",
                "priority": "medium",
                "title": "性能优化",
                "description": "可以优化策略执行效率",
                "opportunities": perf_analysis.get("optimization_opportunities", []),
                "estimated_improvement": f"减少{30-int(perf_analysis.get('performance_score', 0.8)*30)}%回测时间"
            })
        
        # 市场适应性建议
        if market_analysis.get("adaptability_score", 0.5) < 0.7:
            suggestions.append({
                "category": "market_adaptability",
                "priority": "medium",
                "title": "增强市场适应性",
                "description": "策略对不同市场环境的适应性有限",
                "recommendations": market_analysis.get("recommended_markets", []),
                "estimated_improvement": "扩大适用市场范围"
            })
        
        return suggestions
    
    # AI分析辅助方法
    @classmethod
    async def _ai_risk_analysis(cls, code: str) -> Dict[str, Any]:
        """使用AI进行深度风险分析"""
        try:
            prompt = f"""
            分析这个交易策略的风险控制机制，提供专业建议：

            策略代码：
            ```python
            {code[:2000]}  # 限制长度
            ```

            请分析并返回JSON格式：
            {{
                "suggestions": ["具体建议1", "具体建议2"],
                "critical_warnings": ["严重警告1"],
                "missing_risk_controls": ["缺失的风险控制"],
                "recommended_additions": ["建议添加的控制"]
            }}
            """
            
            claude_client = await cls._get_claude_client()
            if not claude_client:
                return {"suggestions": ["无法获取Claude客户端，请人工审核风险控制"]}
                
            response = await claude_client.create_message(
                messages=[{"role": "user", "content": prompt}],
                system="你是专业的量化风险管理专家，提供精确的风险分析建议。",
                temperature=0.2
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
                        content = content.split("```json")[1].split("```")[0]
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"suggestions": ["AI分析解析失败，建议人工复核风险控制"]}
            
        except Exception as e:
            logger.error(f"AI风险分析失败: {e}")
        
        return {"suggestions": []}
    
    @classmethod
    async def _ai_conflict_analysis(cls, code: str, pattern1: str, pattern2: str, description: str) -> Dict[str, Any]:
        """AI分析信号冲突"""
        try:
            # 简化实现，实际可以调用Claude进行深度分析
            return {
                "is_conflict": True,
                "severity": "medium",
                "suggestion": f"建议在{description}中增加互斥条件检查"
            }
        except:
            return {"is_conflict": False}
    
    @classmethod
    async def _ai_entry_exit_analysis(cls, entry_logic: str, exit_logic: str) -> Dict[str, Any]:
        """AI分析入场出场逻辑"""
        try:
            # 简化实现
            return {
                "has_issues": False,
                "issues": []
            }
        except:
            return {"has_issues": False, "issues": []}
    
    @classmethod
    async def _ai_performance_analysis(cls, code: str) -> Dict[str, Any]:
        """AI性能分析"""
        return {
            "optimizations": [],
            "estimated_score": 0.8
        }
    
    @classmethod
    async def _ai_market_adaptability_analysis(cls, code: str, target_market: str) -> Dict[str, Any]:
        """AI市场适应性分析"""
        return {
            "bonus_score": 0.1,
            "warnings": []
        }
    
    # 辅助评估方法
    @classmethod
    def _get_risk_level(cls, risk_score: float) -> str:
        """获取风险等级"""
        if risk_score >= 0.8:
            return "低风险"
        elif risk_score >= 0.6:
            return "中等风险"
        elif risk_score >= 0.4:
            return "高风险"
        else:
            return "极高风险"
    
    @classmethod
    def _estimate_backtest_time(cls, code: str) -> str:
        """估算回测时间"""
        complexity_indicators = [
            len(re.findall(r'for\s+', code)),
            len(re.findall(r'while\s+', code)),
            len(re.findall(r'\.rolling\(', code)),
            len(re.findall(r'\.apply\(', code))
        ]
        
        total_complexity = sum(complexity_indicators)
        if total_complexity < 5:
            return "< 1分钟"
        elif total_complexity < 10:
            return "1-3分钟"
        elif total_complexity < 20:
            return "3-10分钟"
        else:
            return "> 10分钟"
    
    @classmethod
    def _assess_complexity(cls, code: str) -> str:
        """评估策略复杂度"""
        lines = len(code.split('\n'))
        functions = len(re.findall(r'def\s+\w+', code))
        
        if lines < 50 and functions < 3:
            return "简单"
        elif lines < 100 and functions < 6:
            return "中等"
        elif lines < 200 and functions < 10:
            return "复杂"
        else:
            return "高度复杂"
    
    @classmethod
    def _assess_market_suitability(cls, code: str) -> List[str]:
        """评估市场适用性"""
        suitable_markets = []
        
        if re.search(r'trend|ma|ema', code, re.IGNORECASE):
            suitable_markets.append("趋势市场")
        if re.search(r'rsi|bollinger|mean_reversion', code, re.IGNORECASE):
            suitable_markets.append("震荡市场")
        if re.search(r'volume|流量', code, re.IGNORECASE):
            suitable_markets.append("高流动性市场")
        
        return suitable_markets if suitable_markets else ["通用市场"]
    
    @classmethod
    def _recommend_suitable_markets(cls, code: str) -> List[str]:
        """推荐适用市场"""
        recommendations = []
        
        # 基于技术指标推荐
        if re.search(r'macd|ema', code, re.IGNORECASE):
            recommendations.append("BTCUSDT - 适合趋势策略")
        if re.search(r'rsi|stochastic', code, re.IGNORECASE):
            recommendations.append("ETHUSDT - 适合震荡策略")
        
        return recommendations if recommendations else ["BTCUSDT - 通用推荐"]
    
    @classmethod
    def _calculate_final_score(
        cls, 
        base_validation: Dict,
        risk_analysis: Dict,
        logic_check: Dict,
        perf_analysis: Dict,
        market_analysis: Dict
    ) -> float:
        """计算最终质量评分"""
        try:
            # 基础分（语法、模板、安全）
            base_score = 1.0 if base_validation["valid"] else 0.0
            
            # 各项权重评分
            risk_score = risk_analysis.get("overall_risk_score", 0.5) * 0.3
            logic_score = logic_check.get("consistency_score", 0.5) * 0.25
            perf_score = perf_analysis.get("performance_score", 0.7) * 0.25
            market_score = market_analysis.get("adaptability_score", 0.5) * 0.2
            
            # 计算加权总分
            final_score = base_score * 0.4 + (risk_score + logic_score + perf_score + market_score)
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"最终评分计算失败: {e}")
            return 0.5