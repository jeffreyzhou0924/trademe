"""
AI提示词模板模块
"""

from .trading_prompts import TradingPrompts
from .system_prompts import SystemPrompts
from .analysis_prompts import AnalysisPrompts

__all__ = [
    "TradingPrompts",
    "SystemPrompts", 
    "AnalysisPrompts"
]