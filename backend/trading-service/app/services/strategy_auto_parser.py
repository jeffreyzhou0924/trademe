"""
智能策略生成闭环解析器
自动从Claude AI响应中提取策略代码、名称、参数等信息，并保存为策略
"""

import re
import json
import ast
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.strategy_service import StrategyService
from app.schemas.strategy import StrategyCreate


class StrategyAutoParser:
    """AI策略自动解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 策略代码识别模式
        self.code_patterns = [
            # Python代码块
            r'```python\s*\n(.*?)\n```',
            r'```py\s*\n(.*?)\n```',
            # 普通代码块
            r'```\s*\n(.*?)\n```',
            # 函数定义模式
            r'(def\s+\w+.*?(?=\n\n|\n#|\nclass|\ndef|\n\w|\Z))',
            # 类定义模式  
            r'(class\s+\w+.*?(?=\n\n|\n#|\nclass|\ndef|\n\w|\Z))'
        ]
        
        # 策略名称识别模式
        self.name_patterns = [
            # Python类名模式
            r'class\s+(\w+Strategy)\s*\(',
            r'class\s+(\w+Indicator)\s*\(',
            # 文档字符串中的策略名
            r'"""\s*\n\s*(.+?策略)\s*\n',
            r'"""\s*(.+?策略)\s*\n',
            # 传统格式模式
            r'#\s*(.+?)策略',
            r'策略名称[:：]\s*(.+?)(?:\n|$)',
            r'##\s*(.+?)(?:\n|$)',
            r'策略[:：]\s*(.+?)(?:\n|$)',
            r'名称[:：]\s*(.+?)(?:\n|$)',
            # 自然语言中的策略提及
            r'创建.*?(\w+交叉策略)',
            r'(\w+策略)(?:，|。|\s)',
            # 技术指标名称
            r'(\w+指标)(?:，|。|\s)',
        ]
        
        # 参数识别模式
        self.parameter_patterns = [
            r'参数[:：]\s*\{([^}]+)\}',
            r'参数配置[:：]\s*\{([^}]+)\}',
            r'默认参数[:：]\s*\{([^}]+)\}',
            r'参数设置[:：]\s*([^:\n]+)',
            r'(\w+)\s*[:=]\s*(\d+\.?\d*)',  # key: value 格式
            r'(\w+)\s*=\s*(\d+\.?\d*)'      # key = value 格式
        ]
    
    async def parse_ai_response(
        self, 
        response_content: str, 
        session_id: str,
        session_type: str,
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        解析AI响应内容，自动提取策略信息
        
        Args:
            response_content: AI完整响应内容
            session_id: AI会话ID
            session_type: 会话类型 (strategy/indicator)
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            解析结果字典
        """
        try:
            self.logger.info(f"开始解析AI响应，会话ID: {session_id}, 类型: {session_type}")
            
            # 1. 提取策略代码
            code_blocks = self._extract_code_blocks(response_content)
            if not code_blocks:
                return {
                    "success": False,
                    "message": "未检测到策略代码",
                    "details": {"response_length": len(response_content)}
                }
            
            # 2. 提取策略名称
            strategy_name = self._extract_strategy_name(response_content, session_type)
            
            # 3. 提取策略描述
            description = self._extract_description(response_content)
            
            # 4. 提取参数配置
            parameters = self._extract_parameters(response_content)
            
            # 5. 选择最佳代码块
            best_code = self._select_best_code_block(code_blocks)
            
            # 6. 验证代码
            is_valid, validation_message, warnings = await StrategyService.validate_strategy_code(
                best_code, detailed=True
            )
            
            if not is_valid:
                return {
                    "success": False,
                    "message": f"代码验证失败: {validation_message}",
                    "details": {
                        "extracted_name": strategy_name,
                        "code_preview": best_code[:200] + "..." if len(best_code) > 200 else best_code
                    }
                }
            
            # 7. 创建策略
            strategy_data = StrategyCreate(
                name=strategy_name,
                description=description,
                code=best_code,
                parameters=parameters,
                strategy_type=session_type,
                ai_session_id=session_id
            )
            
            created_strategy = await StrategyService.create_strategy(
                db, strategy_data, user_id
            )
            
            self.logger.info(f"成功创建策略: ID={created_strategy.id}, 名称={strategy_name}")
            
            # 8. 自动触发回测（仅对strategy类型，不对indicator类型）
            backtest_result = None
            if session_type == "strategy":
                try:
                    self.logger.info(f"开始为策略 {created_strategy.id} 自动触发回测")
                    backtest_result = await self.trigger_auto_backtest(
                        created_strategy.id, user_id, db
                    )
                    self.logger.info(f"自动回测触发完成: {backtest_result.get('success', False)}")
                except Exception as e:
                    self.logger.warning(f"自动回测触发失败，但策略已创建: {str(e)}")
                    # 回测失败不影响策略创建成功的返回
            
            return {
                "success": True,
                "message": f"成功从AI响应中提取并创建{session_type}",
                "strategy": {
                    "id": created_strategy.id,
                    "name": created_strategy.name,
                    "description": created_strategy.description,
                    "type": created_strategy.strategy_type,
                    "ai_session_id": created_strategy.ai_session_id,
                    "created_at": created_strategy.created_at.isoformat()
                },
                "backtest": backtest_result,  # 添加回测结果
                "details": {
                    "code_blocks_found": len(code_blocks),
                    "validation_warnings": warnings,
                    "extracted_parameters": parameters,
                    "auto_backtest_triggered": backtest_result is not None
                }
            }
            
        except Exception as e:
            self.logger.error(f"策略解析失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"策略解析失败: {str(e)}",
                "details": {"error_type": type(e).__name__}
            }
    
    def _extract_code_blocks(self, content: str) -> List[str]:
        """提取所有代码块"""
        code_blocks = []
        
        for pattern in self.code_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                
                # 清理代码块
                clean_code = self._clean_code_block(match.strip())
                if len(clean_code) > 50 and self._is_valid_strategy_code(clean_code):
                    code_blocks.append(clean_code)
        
        return code_blocks
    
    def _clean_code_block(self, code: str) -> str:
        """清理代码块"""
        # 移除多余的空行
        lines = [line.rstrip() for line in code.split('\n')]
        
        # 移除开头和结尾的空行
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    def _is_valid_strategy_code(self, code: str) -> bool:
        """检查是否为有效的策略代码"""
        try:
            # 基础语法检查
            ast.parse(code)
            
            # 检查是否包含策略相关关键词
            strategy_keywords = [
                'def ', 'class ', 'import ', 'from ',
                'strategy', 'trade', 'buy', 'sell', 'price', 'volume',
                'rsi', 'macd', 'ema', 'sma', 'bollinger', 'signal'
            ]
            
            code_lower = code.lower()
            keyword_count = sum(1 for keyword in strategy_keywords if keyword in code_lower)
            
            return keyword_count >= 3  # 至少包含3个相关关键词
            
        except SyntaxError:
            return False
    
    def _extract_strategy_name(self, content: str, session_type: str) -> str:
        """提取策略名称"""
        for pattern in self.name_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # 清理名称
                name = re.sub(r'[^\w\s\-_()]', '', name)[:100]
                if name:
                    return name
        
        # 如果未找到，生成默认名称
        type_name = "技术指标" if session_type == "indicator" else "交易策略"
        timestamp = datetime.now().strftime("%m%d_%H%M")
        return f"AI生成的{type_name}_{timestamp}"
    
    def _extract_description(self, content: str) -> str:
        """提取策略描述"""
        
        # 首先尝试从Python类的文档字符串中提取描述
        docstring_patterns = [
            r'class\s+\w+.*?:\s*"""\s*\n\s*(.+?)\s*\n\s*\n\s*策略原理',
            r'class\s+\w+.*?:\s*"""\s*(.+?策略)\s*\n',
            r'"""\s*\n\s*(.+?策略)\s*\n\s*\n\s*策略原理',
        ]
        
        for pattern in docstring_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 10 and '我将' not in desc and '创建' not in desc[:5]:
                    return desc[:200] + ("..." if len(desc) > 200 else "")
        
        # 查找策略原理描述
        principle_patterns = [
            r'策略原理[:：]\s*\n\s*(.+?)(?:\n\s*\n|\n\s*"""|$)',
            r'工作原理[:：]\s*\n\s*(.+?)(?:\n\s*\n|\n\s*"""|$)',
            r'算法说明[:：]\s*\n\s*(.+?)(?:\n\s*\n|\n\s*"""|$)',
        ]
        
        for pattern in principle_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                principle = match.group(1).strip()
                # 清理内容
                principle = re.sub(r'\s*-\s*', '\n• ', principle)  # 转换列表格式
                principle = re.sub(r'\n\s*\n', '\n', principle)    # 移除多余空行
                if len(principle) > 20:
                    return principle[:300] + ("..." if len(principle) > 300 else "")
        
        # 尝试从段落中提取，但跳过AI回复前言
        paragraphs = content.split('\n\n')
        for paragraph in paragraphs:
            # 跳过代码块
            if '```' in paragraph:
                continue
            
            clean_paragraph = paragraph.strip()
            
            # 跳过AI回复前言
            skip_phrases = ['我将', '我会', '让我', '现在', '这里', '以下是', '好的']
            if any(phrase in clean_paragraph[:10] for phrase in skip_phrases):
                continue
                
            # 寻找策略相关的段落
            if (len(clean_paragraph) > 30 and len(clean_paragraph) < 500 and
                ('策略' in clean_paragraph or '指标' in clean_paragraph or
                 '交易' in clean_paragraph or '信号' in clean_paragraph)):
                # 移除markdown标记
                clean_paragraph = re.sub(r'#+\s*', '', clean_paragraph)
                clean_paragraph = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_paragraph)
                clean_paragraph = re.sub(r'\*(.*?)\*', r'\1', clean_paragraph)
                return clean_paragraph[:250] + ("..." if len(clean_paragraph) > 250 else "")
        
        return "AI生成的智能交易策略，基于移动平均线等技术指标实现自动化交易信号生成"
    
    def _extract_parameters(self, content: str) -> Dict[str, Any]:
        """提取参数配置"""
        parameters = {}
        
        # 尝试提取JSON格式的参数
        json_pattern = r'\{([^{}]+)\}'
        json_matches = re.findall(json_pattern, content)
        
        for match in json_matches:
            try:
                # 尝试解析为JSON
                param_text = '{' + match + '}'
                parsed = json.loads(param_text)
                if isinstance(parsed, dict) and len(parsed) < 20:  # 限制参数数量
                    parameters.update(parsed)
                    break
            except json.JSONDecodeError:
                continue
        
        # 如果没有找到JSON格式，尝试提取key-value对
        if not parameters:
            for pattern in self.parameter_patterns[3:]:  # 跳过JSON模式
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple) and len(match) == 2:
                        key, value = match
                        try:
                            # 尝试转换为数字
                            if '.' in value:
                                parameters[key.strip()] = float(value)
                            else:
                                parameters[key.strip()] = int(value)
                        except ValueError:
                            parameters[key.strip()] = value.strip()
        
        # 添加一些默认参数
        if not parameters:
            parameters = {
                "period": 14,
                "threshold": 0.02,
                "auto_generated": True
            }
        else:
            parameters["auto_generated"] = True
            parameters["extraction_time"] = datetime.now().isoformat()
        
        return parameters
    
    def _select_best_code_block(self, code_blocks: List[str]) -> str:
        """选择最佳代码块"""
        if not code_blocks:
            return ""
        
        # 如果只有一个，直接返回
        if len(code_blocks) == 1:
            return code_blocks[0]
        
        # 选择最长且最复杂的代码块
        best_code = code_blocks[0]
        best_score = self._calculate_code_score(best_code)
        
        for code in code_blocks[1:]:
            score = self._calculate_code_score(code)
            if score > best_score:
                best_score = score
                best_code = code
        
        return best_code
    
    def _calculate_code_score(self, code: str) -> int:
        """计算代码块评分"""
        score = 0
        
        # 长度权重
        score += len(code) // 10
        
        # 函数定义权重
        score += len(re.findall(r'def\s+\w+', code)) * 20
        
        # 类定义权重
        score += len(re.findall(r'class\s+\w+', code)) * 30
        
        # 导入语句权重
        score += len(re.findall(r'import\s+\w+|from\s+\w+', code)) * 5
        
        # 策略相关关键词权重
        strategy_keywords = ['buy', 'sell', 'signal', 'strategy', 'indicator', 'rsi', 'macd', 'ema']
        code_lower = code.lower()
        for keyword in strategy_keywords:
            score += code_lower.count(keyword) * 3
        
        return score
    
    async def trigger_auto_backtest(
        self, 
        strategy_id: int, 
        user_id: int, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """自动触发增强回测（包含优化建议）"""
        try:
            from app.services.enhanced_auto_backtest_service import EnhancedAutoBacktestService
            
            # 获取策略信息
            strategy = await StrategyService.get_strategy(db, strategy_id, user_id)
            if not strategy:
                return {
                    "success": False,
                    "message": "策略不存在，无法执行回测"
                }
            
            # 构建用户意图（基于策略的默认设置）
            intent = {
                "expected_return": 15,  # 默认期望年化收益15%
                "max_drawdown": 20,     # 默认最大回撤20%
                "target_assets": ["BTC-USDT-SWAP"],  # 默认交易对
                "timeframe": "1h"       # 默认时间框架
            }
            
            # 调用增强自动回测服务（包含优化建议）
            enhanced_backtest_result = await EnhancedAutoBacktestService.run_enhanced_backtest_with_suggestions(
                strategy_code=strategy.code,
                intent=intent,
                user_id=user_id,
                config={
                    "initial_capital": 10000,
                    "days_back": 30,
                    "symbol": "BTC-USDT-SWAP"
                }
            )
            
            performance_grade = enhanced_backtest_result.get("performance_grade", "F")
            is_satisfactory = enhanced_backtest_result.get("is_satisfactory", False)
            
            self.logger.info(f"增强回测完成: 策略ID={strategy_id}, 等级={performance_grade}, 达标={is_satisfactory}")
            
            return {
                "success": enhanced_backtest_result.get("success", False),
                "message": "回测已完成" if enhanced_backtest_result.get("success") else "回测执行出现问题",
                "backtest": enhanced_backtest_result,
                "optimization_needed": not is_satisfactory,
                "has_suggestions": not is_satisfactory and "optimization_suggestions" in enhanced_backtest_result
            }
            
        except Exception as e:
            self.logger.error(f"增强回测触发失败: {str(e)}")
            return {
                "success": False,
                "message": f"增强回测失败: {str(e)}"
            }
    
    def extract_strategy_metrics(self, content: str) -> Dict[str, Any]:
        """提取策略的性能指标提及"""
        metrics = {}
        
        # 查找提及的性能指标
        metric_patterns = {
            'win_rate': r'胜率[:：]?\s*(\d+(?:\.\d+)?)[%％]?',
            'sharpe_ratio': r'夏普比[:：]?\s*(\d+(?:\.\d+)?)',
            'max_drawdown': r'最大回撤[:：]?\s*(\d+(?:\.\d+)?)[%％]?',
            'annual_return': r'年化收益[:：]?\s*(\d+(?:\.\d+)?)[%％]?'
        }
        
        for metric_name, pattern in metric_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    if metric_name in ['win_rate', 'max_drawdown', 'annual_return'] and value > 1:
                        value = value / 100  # 转换百分比
                    metrics[metric_name] = value
                except ValueError:
                    continue
        
        return metrics