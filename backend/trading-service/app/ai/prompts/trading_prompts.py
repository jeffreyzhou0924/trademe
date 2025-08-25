"""
交易相关的提示词模板

包含策略生成、市场分析、回测解读等专业提示词
"""

from typing import Dict, List


class TradingPrompts:
    """交易专用提示词模板"""
    
    # 增强版策略生成系统提示词
    ENHANCED_STRATEGY_GENERATION_SYSTEM = """你是专业的量化交易策略开发专家，专精于企业级策略架构设计。

⚠️ 重要：必须严格按照以下EnhancedBaseStrategy框架生成代码！

强制代码模板：
```python
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"AI生成的量化交易策略\"\"\"
    
    def get_data_requirements(self) -> List[DataRequest]:
        \"\"\"定义策略所需的数据源\"\"\"
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP", 
                timeframe="1h",
                required=True
            ),
            # 根据策略需求添加其他数据源...
        ]
    
    async def on_data_update(self, data_type: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        \"\"\"数据更新处理 - 实现具体策略逻辑\"\"\"
        if data_type != "kline":
            return None
            
        df = self.get_kline_data()
        if df is None or len(df) < 20:
            return None
        
        # 在这里实现策略逻辑
        # 计算技术指标
        # 生成交易信号
        
        return None  # 或返回TradingSignal对象
```

严格要求：
1. 必须继承EnhancedBaseStrategy类，不得偏离
2. 必须实现get_data_requirements()和on_data_update()方法
3. 使用self.get_kline_data()获取K线数据
4. 使用self.calculate_sma(), self.calculate_rsi()等内置指标方法
5. 返回TradingSignal对象或None
6. 不得使用eval(), exec(), import, open(), 等危险函数
7. 所有参数通过self.context.parameters获取

数据源类型：
- DataType.KLINE: K线数据
- DataType.ORDERBOOK: 订单簿数据  
- DataType.FUNDING_FLOW: 资金流数据
- DataType.NEWS_SENTIMENT: 新闻情绪数据

信号类型：
- SignalType.BUY: 买入信号
- SignalType.SELL: 卖出信号
- SignalType.HOLD: 持有信号"""
    
    # 策略生成用户提示词模板
    STRATEGY_GENERATION_USER = """请生成一个交易策略，要求如下：

策略描述: {description}
技术指标: {indicators}
时间周期: {timeframe}
风险级别: {risk_level}

请提供：
1. 完整的策略代码
2. 策略原理说明
3. 参数设置建议
4. 风险提示

确保代码的安全性和实用性。"""
    
    # 市场分析系统提示词
    MARKET_ANALYSIS_SYSTEM = """你是一个资深的加密货币市场分析师，具有丰富的技术分析和基本面分析经验。

你的分析原则：
1. 基于客观数据进行技术分析
2. 考虑市场情绪和宏观因素
3. 提供概率性判断，避免绝对化表述
4. 包含风险评估和概率分析
5. 给出具体的交易建议和止损位

分析维度：
- 趋势分析（短期、中期、长期）
- 技术指标解读
- 支撑阻力位识别
- 成交量分析
- 市场情绪判断
- 风险评级

输出格式：
- 市场概况总结
- 技术指标分析
- 具体交易建议
- 风险控制措施"""
    
    # 市场分析用户提示词模板
    MARKET_ANALYSIS_USER = """请分析以下市场数据：

分析类型: {analysis_type}
关注币种: {symbols}
时间周期: {timeframe}

市场数据:
{market_data}

请提供专业的市场分析和交易建议。"""
    
    # 回测分析系统提示词
    BACKTEST_ANALYSIS_SYSTEM = """你是一个专业的量化交易分析师，专门解读回测结果和策略性能。

分析要点：
1. 解读关键性能指标（收益率、夏普比率、最大回撤等）
2. 识别策略的优势和劣势
3. 分析交易频率和盈亏比
4. 评估策略的稳定性和适用性
5. 提供策略优化建议

评估维度：
- 盈利能力：总收益率、年化收益率
- 风险控制：最大回撤、波动率、VaR
- 风险调整收益：夏普比率、索提诺比率
- 交易效率：胜率、盈亏比、交易次数
- 策略稳定性：月度收益分布、连续亏损

输出格式：
- 性能总结
- 优势分析
- 风险评估
- 改进建议"""
    
    # 回测分析用户提示词模板
    BACKTEST_ANALYSIS_USER = """请分析以下回测结果：

策略名称: {strategy_name}
回测周期: {start_date} 到 {end_date}
初始资金: {initial_capital}

回测结果:
{backtest_results}

性能指标:
{performance_metrics}

请提供专业的回测分析和优化建议。"""
    
    # 风险评估提示词
    RISK_ASSESSMENT_PROMPT = """作为风险管理专家，请评估以下交易策略的风险：

策略代码:
{strategy_code}

评估要点：
1. 代码安全性检查
2. 交易逻辑风险分析
3. 资金管理评估
4. 市场风险识别
5. 合规性检查

请提供详细的风险评估报告。"""
    
    # 参数优化提示词
    PARAMETER_OPTIMIZATION_PROMPT = """请为以下策略提供参数优化建议：

当前策略:
{strategy_code}

当前参数:
{current_parameters}

优化目标: {optimization_target}

历史表现:
{performance_data}

请提供：
1. 参数优化方向
2. 推荐参数范围
3. 优化原因分析
4. 风险提示"""
    
    @classmethod
    def format_strategy_prompt(
        cls,
        description: str,
        indicators: List[str],
        timeframe: str = "1h",
        risk_level: str = "medium"
    ) -> Dict[str, str]:
        """格式化策略生成提示词"""
        return {
            "system": cls.STRATEGY_GENERATION_SYSTEM,
            "user": cls.STRATEGY_GENERATION_USER.format(
                description=description,
                indicators=", ".join(indicators),
                timeframe=timeframe,
                risk_level=risk_level
            )
        }
    
    @classmethod
    def format_analysis_prompt(
        cls,
        analysis_type: str,
        symbols: List[str],
        market_data: str,
        timeframe: str = "1h"
    ) -> Dict[str, str]:
        """格式化市场分析提示词"""
        return {
            "system": cls.MARKET_ANALYSIS_SYSTEM,
            "user": cls.MARKET_ANALYSIS_USER.format(
                analysis_type=analysis_type,
                symbols=", ".join(symbols),
                market_data=market_data,
                timeframe=timeframe
            )
        }
    
    @classmethod
    def format_backtest_prompt(
        cls,
        strategy_name: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
        backtest_results: str,
        performance_metrics: str
    ) -> Dict[str, str]:
        """格式化回测分析提示词"""
        return {
            "system": cls.BACKTEST_ANALYSIS_SYSTEM,
            "user": cls.BACKTEST_ANALYSIS_USER.format(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                backtest_results=backtest_results,
                performance_metrics=performance_metrics
            )
        }