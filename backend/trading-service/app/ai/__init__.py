"""
AI功能模块

提供基于Claude的AI服务，包括：
- 智能对话系统
- 策略代码生成
- 市场分析和建议
- 回测结果解读
"""

from .core.claude_client import ClaudeClient

__all__ = [
    "ClaudeClient"
]