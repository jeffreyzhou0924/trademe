"""
策略需求提取器 - 从对话历史中智能提取完整的策略需求

用于解决策略生成时上下文丢失的问题，确保生成的策略包含用户描述的所有细节
"""

import re
import json
from typing import Dict, List, Any, Optional
from loguru import logger


class StrategyRequirementsExtractor:
    """策略需求提取器"""
    
    # 指标关键词映射
    INDICATOR_KEYWORDS = {
        'MACD': ['macd', '指数平滑移动平均线', '快线', '慢线', '柱状图', 'dif', 'dea', 'histogram'],
        'RSI': ['rsi', '相对强弱指标', '超买', '超卖', '强弱'],
        'MA': ['ma', 'sma', 'ema', '均线', '移动平均', '移动平均线'],
        'BOLL': ['boll', 'bollinger', '布林带', '布林线', '上轨', '中轨', '下轨'],
        'KDJ': ['kdj', 'k线', 'd线', 'j线', '随机指标'],
        'CCI': ['cci', '商品通道指数'],
        'ATR': ['atr', '平均真实波幅', '真实波幅'],
        'VOLUME': ['volume', '成交量', '量能', '放量', '缩量']
    }
    
    # 交易逻辑关键词
    LOGIC_KEYWORDS = {
        'entry': ['买入', '开仓', '入场', '做多', '做空', '进场', '建仓', '买点'],
        'exit': ['卖出', '平仓', '出场', '离场', '止盈', '止损', '清仓', '卖点'],
        'condition': ['当', '如果', '条件', '满足', '触发', '信号', '出现', '形成'],
        'divergence': ['背离', '顶背离', '底背离', '背驰', '反向'],
        'cross': ['金叉', '死叉', '交叉', '穿越', '突破', '跌破'],
        'trend': ['趋势', '上升', '下降', '震荡', '盘整', '突破', '回调']
    }
    
    # 数值参数正则表达式
    NUMERIC_PATTERNS = {
        'period': r'(\d+)\s*(?:日|天|小时|分钟|周期|根|bar|bars|candle)',
        'percentage': r'(\d+(?:\.\d+)?)\s*[%％]',
        'value': r'(?:大于|小于|等于|超过|低于|高于|达到)\s*(\d+(?:\.\d+)?)',
        'threshold': r'(?:阈值|临界值|水平|位置)\s*(?:为|是|在)?\s*(\d+(?:\.\d+)?)'
    }
    
    @staticmethod
    async def extract_requirements(conversation_history: List[Any]) -> Dict[str, Any]:
        """
        从对话历史中提取完整的策略需求
        
        Args:
            conversation_history: 对话历史记录列表
            
        Returns:
            包含策略需求的字典
        """
        requirements = {
            "indicators": {},
            "entry_conditions": [],
            "exit_conditions": [],
            "risk_management": {},
            "parameters": {},
            "special_logic": [],
            "timeframe": None,
            "trading_pair": None,
            "strategy_type": None,
            "user_description": ""
        }
        
        if not conversation_history:
            return requirements
        
        # 合并所有用户消息作为需求描述
        user_messages = []
        for msg in conversation_history:
            if hasattr(msg, 'message_type') and msg.message_type == "user":
                content = msg.content if hasattr(msg, 'content') else str(msg)
                # 过滤简单确认消息
                if content and content not in ["确认生成代码", "是", "好的", "确认", "生成", "yes", "ok"]:
                    user_messages.append(content)
        
        full_description = " ".join(user_messages)
        requirements["user_description"] = full_description
        
        # 提取指标
        requirements["indicators"] = StrategyRequirementsExtractor._extract_indicators(full_description)
        
        # 提取交易逻辑
        entry_conditions, exit_conditions = StrategyRequirementsExtractor._extract_trading_logic(full_description)
        requirements["entry_conditions"] = entry_conditions
        requirements["exit_conditions"] = exit_conditions
        
        # 提取风险管理参数
        requirements["risk_management"] = StrategyRequirementsExtractor._extract_risk_parameters(full_description)
        
        # 提取数值参数
        requirements["parameters"] = StrategyRequirementsExtractor._extract_numeric_parameters(full_description)
        
        # 提取特殊逻辑（如背离）
        requirements["special_logic"] = StrategyRequirementsExtractor._extract_special_logic(full_description)
        
        # 提取时间框架
        requirements["timeframe"] = StrategyRequirementsExtractor._extract_timeframe(full_description)
        
        # 提取交易对
        requirements["trading_pair"] = StrategyRequirementsExtractor._extract_trading_pair(full_description)
        
        logger.info(f"📋 提取的策略需求: 指标={list(requirements['indicators'].keys())}, "
                   f"入场条件={len(requirements['entry_conditions'])}, "
                   f"出场条件={len(requirements['exit_conditions'])}")
        
        return requirements
    
    @staticmethod
    def _extract_indicators(text: str) -> Dict[str, Dict]:
        """提取技术指标及其参数"""
        indicators = {}
        text_lower = text.lower()
        
        for indicator, keywords in StrategyRequirementsExtractor.INDICATOR_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # 提取指标参数
                    params = {}
                    
                    # 特殊处理MACD参数（可能以12,26,9格式出现）
                    if indicator == 'MACD':
                        # 查找Macd指标参数，例如12,26,9
                        macd_pattern = r'(?:MACD|指标)[^数\d]*(\d+)[,，\s]*(\d+)[,，\s]*(\d+)'
                        macd_match = re.search(macd_pattern, text, re.IGNORECASE)
                        if macd_match:
                            params['fast_period'] = int(macd_match.group(1))
                            params['slow_period'] = int(macd_match.group(2))
                            params['signal_period'] = int(macd_match.group(3))
                        else:
                            # 默认MACD参数
                            params['fast_period'] = 12
                            params['slow_period'] = 26
                            params['signal_period'] = 9
                    
                    # 处理RSI参数
                    elif indicator == 'RSI':
                        # 查找RSI(14)或RSI 14等格式
                        rsi_pattern = r'RSI[\(\[（\s]*(\d+)'
                        rsi_match = re.search(rsi_pattern, text, re.IGNORECASE)
                        if rsi_match:
                            params['period'] = int(rsi_match.group(1))
                        else:
                            params['period'] = 14  # 默认值
                    
                    # 处理其他指标参数
                    elif indicator in ['MA', 'CCI', 'ATR']:
                        # 查找指标附近的数字参数
                        pattern = rf'{keyword}[^\d]*(\d+)'
                        match = re.search(pattern, text_lower)
                        if match:
                            params['period'] = int(match.group(1))
                    
                    elif indicator == 'BOLL':
                        # 查找布林带参数
                        boll_pattern = r'(?:BOLL|布林带)[^数\d]*(\d+)[,，\s]*(\d+)?'
                        boll_match = re.search(boll_pattern, text, re.IGNORECASE)
                        if boll_match:
                            params['period'] = int(boll_match.group(1))
                            if boll_match.group(2):
                                params['std_dev'] = int(boll_match.group(2))
                    
                    indicators[indicator] = params
                    break
        
        return indicators
    
    @staticmethod
    def _extract_trading_logic(text: str) -> tuple:
        """提取入场和出场条件"""
        entry_conditions = []
        exit_conditions = []
        
        # 分句处理
        sentences = re.split(r'[。；;]', text)
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # 判断是入场还是出场条件
            is_entry = any(keyword in sentence_lower for keyword in StrategyRequirementsExtractor.LOGIC_KEYWORDS['entry'])
            is_exit = any(keyword in sentence_lower for keyword in StrategyRequirementsExtractor.LOGIC_KEYWORDS['exit'])
            
            # 提取条件描述
            if is_entry or is_exit:
                # 查找条件关键词
                has_condition = any(keyword in sentence_lower for keyword in StrategyRequirementsExtractor.LOGIC_KEYWORDS['condition'])
                
                if has_condition or '时' in sentence or '则' in sentence:
                    condition = sentence.strip()
                    if condition:
                        if is_entry:
                            entry_conditions.append(condition)
                        elif is_exit:
                            exit_conditions.append(condition)
        
        return entry_conditions, exit_conditions
    
    @staticmethod
    def _extract_risk_parameters(text: str) -> Dict[str, Any]:
        """提取风险管理参数"""
        risk_params = {}
        
        # 止损
        stop_loss_match = re.search(r'止损[^\d]*(\d+(?:\.\d+)?)\s*[%％]?', text)
        if stop_loss_match:
            risk_params['stop_loss'] = float(stop_loss_match.group(1))
        
        # 止盈
        take_profit_match = re.search(r'止盈[^\d]*(\d+(?:\.\d+)?)\s*[%％]?', text)
        if take_profit_match:
            risk_params['take_profit'] = float(take_profit_match.group(1))
        
        # 仓位
        position_match = re.search(r'仓位[^\d]*(\d+(?:\.\d+)?)\s*[%％]?', text)
        if position_match:
            risk_params['position_size'] = float(position_match.group(1))
        
        return risk_params
    
    @staticmethod
    def _extract_numeric_parameters(text: str) -> Dict[str, Any]:
        """提取所有数值参数"""
        params = {}
        
        for param_type, pattern in StrategyRequirementsExtractor.NUMERIC_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                if param_type == 'period':
                    params['periods'] = [int(m) for m in matches]
                else:
                    params[param_type] = [float(m) for m in matches]
        
        return params
    
    @staticmethod
    def _extract_special_logic(text: str) -> List[str]:
        """提取特殊交易逻辑（如背离）"""
        special_logic = []
        
        # 背离检测
        if any(keyword in text.lower() for keyword in ['背离', '背驰', 'divergence']):
            if '顶背离' in text or 'top divergence' in text.lower():
                special_logic.append('bearish_divergence')
            if '底背离' in text or 'bottom divergence' in text.lower():
                special_logic.append('bullish_divergence')
            if '背离' in text and '顶' not in text and '底' not in text:
                special_logic.append('divergence')
        
        # 金叉死叉
        if '金叉' in text:
            special_logic.append('golden_cross')
        if '死叉' in text:
            special_logic.append('death_cross')
        
        return special_logic
    
    @staticmethod
    def _extract_timeframe(text: str) -> Optional[str]:
        """提取时间框架"""
        timeframe_map = {
            '1分钟': '1m', '1min': '1m', '1m': '1m',
            '5分钟': '5m', '5min': '5m', '5m': '5m',
            '15分钟': '15m', '15min': '15m', '15m': '15m',
            '30分钟': '30m', '30min': '30m', '30m': '30m',
            '1小时': '1h', '1hour': '1h', '1h': '1h',
            '4小时': '4h', '4hour': '4h', '4h': '4h',
            '1天': '1d', '1日': '1d', '日线': '1d', '1d': '1d',
            '1周': '1w', '周线': '1w', '1w': '1w'
        }
        
        text_lower = text.lower()
        for key, value in timeframe_map.items():
            if key in text_lower:
                return value
        
        return '1h'  # 默认1小时
    
    @staticmethod
    def _extract_trading_pair(text: str) -> Optional[str]:
        """提取交易对"""
        # 常见交易对
        pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'DOGE/USDT']
        
        text_upper = text.upper()
        for pair in pairs:
            if pair.replace('/', '') in text_upper or pair in text_upper:
                return pair
        
        # 查找模式 XXX/USDT 或 XXXUSDT
        pattern = r'([A-Z]{2,10})[/]?USDT'
        match = re.search(pattern, text_upper)
        if match:
            return f"{match.group(1)}/USDT"
        
        return 'BTC/USDT'  # 默认BTC/USDT
    
    @staticmethod
    def format_requirements_prompt(requirements: Dict[str, Any]) -> str:
        """
        将提取的需求格式化为详细的策略生成提示
        """
        prompt_parts = []
        
        # 用户原始描述
        if requirements.get("user_description"):
            prompt_parts.append(f"用户策略需求描述：\n{requirements['user_description']}\n")
        
        # 指标要求
        if requirements.get("indicators"):
            indicators_desc = []
            for indicator, params in requirements["indicators"].items():
                if params:
                    params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                    indicators_desc.append(f"- {indicator}({params_str})")
                else:
                    indicators_desc.append(f"- {indicator}")
            prompt_parts.append(f"使用的技术指标：\n" + "\n".join(indicators_desc) + "\n")
        
        # 入场条件
        if requirements.get("entry_conditions"):
            prompt_parts.append(f"入场条件：\n" + "\n".join([f"- {c}" for c in requirements["entry_conditions"]]) + "\n")
        
        # 出场条件
        if requirements.get("exit_conditions"):
            prompt_parts.append(f"出场条件：\n" + "\n".join([f"- {c}" for c in requirements["exit_conditions"]]) + "\n")
        
        # 风险管理
        if requirements.get("risk_management"):
            risk_desc = []
            for key, value in requirements["risk_management"].items():
                risk_desc.append(f"- {key}: {value}")
            prompt_parts.append(f"风险管理参数：\n" + "\n".join(risk_desc) + "\n")
        
        # 特殊逻辑
        if requirements.get("special_logic"):
            prompt_parts.append(f"特殊交易逻辑：\n" + "\n".join([f"- {logic}" for logic in requirements["special_logic"]]) + "\n")
        
        # 时间框架和交易对
        if requirements.get("timeframe"):
            prompt_parts.append(f"时间框架：{requirements['timeframe']}\n")
        if requirements.get("trading_pair"):
            prompt_parts.append(f"交易对：{requirements['trading_pair']}\n")
        
        return "\n".join(prompt_parts)