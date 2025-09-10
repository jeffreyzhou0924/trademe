"""
回测配置检查器

检查用户是否已配置必要的回测参数，未配置时提醒用户进行配置
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

# from app.models.claude_conversation import BacktestConfiguration  # Model not defined


class BacktestConfigChecker:
    """回测配置检查器"""
    
    REQUIRED_CONFIG_FIELDS = {
        "basic": [
            "symbol",           # 交易对
            "start_date",       # 开始日期
            "end_date",         # 结束日期
            "initial_capital"   # 初始资金
        ],
        "premium": [
            "symbol", "start_date", "end_date", "initial_capital",
            "commission",       # 手续费率
            "slippage"         # 滑点
        ],
        "professional": [
            "symbol", "start_date", "end_date", "initial_capital",
            "commission", "slippage",
            "benchmark_symbol", # 基准标的
            "risk_free_rate"   # 无风险利率
        ]
    }
    
    DEFAULT_CONFIG_VALUES = {
        "symbol": "BTCUSDT",
        "start_date": (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "initial_capital": 10000,
        "commission": 0.001,   # 0.1% 手续费
        "slippage": 0.0005,    # 0.05% 滑点
        "benchmark_symbol": "BTCUSDT",
        "risk_free_rate": 0.02  # 2% 年化无风险利率
    }
    
    @staticmethod
    async def check_user_backtest_config(
        user_id: int,
        membership_level: str = "basic",
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        检查用户的回测配置完整性
        
        返回:
        {
            "has_config": bool,              # 是否有配置
            "is_complete": bool,             # 配置是否完整
            "missing_fields": list,          # 缺失字段
            "current_config": dict,          # 当前配置
            "config_prompt": str,            # 配置提醒信息
            "default_suggestions": dict      # 默认值建议
        }
        """
        try:
            if not db:
                logger.warning("数据库连接为空，返回默认配置检查结果")
                return BacktestConfigChecker._get_default_config_check(membership_level)
            
            # TODO: 实现BacktestConfiguration模型后启用数据库查询
            # 当前返回默认配置，假设用户需要首次设置
            config = None
            
            if not config:
                # 用户没有配置，需要首次设置
                return {
                    "has_config": False,
                    "is_complete": False,
                    "missing_fields": BacktestConfigChecker.REQUIRED_CONFIG_FIELDS[membership_level],
                    "current_config": {},
                    "config_prompt": BacktestConfigChecker._generate_first_time_config_prompt(membership_level),
                    "default_suggestions": BacktestConfigChecker._get_suggested_config(membership_level)
                }
            
            # 检查配置完整性
            current_config = {
                "symbol": config.symbol,
                "start_date": config.start_date.strftime("%Y-%m-%d") if config.start_date else None,
                "end_date": config.end_date.strftime("%Y-%m-%d") if config.end_date else None,
                "initial_capital": float(config.initial_capital) if config.initial_capital else None,
                "commission": float(config.commission) if config.commission else None,
                "slippage": float(config.slippage) if config.slippage else None,
                "benchmark_symbol": config.benchmark_symbol,
                "risk_free_rate": float(config.risk_free_rate) if config.risk_free_rate else None
            }
            
            required_fields = BacktestConfigChecker.REQUIRED_CONFIG_FIELDS[membership_level]
            missing_fields = [field for field in required_fields if not current_config.get(field)]
            
            is_complete = len(missing_fields) == 0
            
            if is_complete:
                return {
                    "has_config": True,
                    "is_complete": True,
                    "missing_fields": [],
                    "current_config": current_config,
                    "config_prompt": "回测配置已完整，可以进行回测",
                    "default_suggestions": {}
                }
            else:
                return {
                    "has_config": True,
                    "is_complete": False,
                    "missing_fields": missing_fields,
                    "current_config": current_config,
                    "config_prompt": BacktestConfigChecker._generate_incomplete_config_prompt(missing_fields, current_config, membership_level),
                    "default_suggestions": BacktestConfigChecker._get_suggested_config(membership_level, missing_fields)
                }
                
        except Exception as e:
            logger.error(f"检查用户回测配置异常: {e}")
            return BacktestConfigChecker._get_default_config_check(membership_level)
    
    @staticmethod
    def _generate_first_time_config_prompt(membership_level: str) -> str:
        """生成首次配置提醒"""
        prompt = "⚙️ **需要配置回测参数**\n\n"
        prompt += "检测到您还没有设置回测配置。在开始策略回测之前，需要先配置以下参数：\n\n"
        
        required_fields = BacktestConfigChecker.REQUIRED_CONFIG_FIELDS[membership_level]
        field_descriptions = {
            "symbol": "交易对 (如：BTCUSDT)",
            "start_date": "回测开始日期 (如：2024-01-01)",
            "end_date": "回测结束日期 (如：2024-03-31)",
            "initial_capital": "初始资金 (如：10000 USDT)",
            "commission": "手续费率 (如：0.001 = 0.1%)",
            "slippage": "滑点 (如：0.0005 = 0.05%)",
            "benchmark_symbol": "基准标的 (如：BTCUSDT)",
            "risk_free_rate": "无风险利率 (如：0.02 = 2%年化)"
        }
        
        for field in required_fields:
            desc = field_descriptions.get(field, field)
            prompt += f"• {desc}\n"
        
        prompt += "\n🔧 **配置方式**:\n"
        prompt += "请前往「交易设置」→「回测配置」页面进行设置，\n"
        prompt += "或回复\"我需要配置回测参数\"获取详细指导。\n\n"
        prompt += "配置完成后，我们就可以开始为您的策略进行专业回测了！"
        
        return prompt
    
    @staticmethod
    def _generate_incomplete_config_prompt(missing_fields: List[str], current_config: Dict, membership_level: str) -> str:
        """生成不完整配置提醒"""
        prompt = "⚠️ **回测配置不完整**\n\n"
        prompt += "您的回测配置还缺少以下必要参数：\n\n"
        
        field_descriptions = {
            "symbol": "交易对",
            "start_date": "回测开始日期",
            "end_date": "回测结束日期", 
            "initial_capital": "初始资金",
            "commission": "手续费率",
            "slippage": "滑点设置",
            "benchmark_symbol": "基准标的",
            "risk_free_rate": "无风险利率"
        }
        
        for field in missing_fields:
            desc = field_descriptions.get(field, field)
            prompt += f"• {desc}\n"
        
        prompt += "\n📋 **当前配置**:\n"
        for key, value in current_config.items():
            if value is not None:
                desc = field_descriptions.get(key, key)
                prompt += f"• {desc}: {value}\n"
        
        prompt += "\n🔧 **请完善配置后再进行回测**\n"
        prompt += "您可以前往「交易设置」→「回测配置」页面补充缺失参数。"
        
        return prompt
    
    @staticmethod
    def _get_suggested_config(membership_level: str, missing_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """获取建议的配置值"""
        required_fields = missing_fields or BacktestConfigChecker.REQUIRED_CONFIG_FIELDS[membership_level]
        
        suggestions = {}
        for field in required_fields:
            if field in BacktestConfigChecker.DEFAULT_CONFIG_VALUES:
                suggestions[field] = BacktestConfigChecker.DEFAULT_CONFIG_VALUES[field]
                
        return suggestions
    
    @staticmethod
    def _get_default_config_check(membership_level: str) -> Dict[str, Any]:
        """获取默认配置检查结果（降级处理）"""
        return {
            "has_config": False,
            "is_complete": False,
            "missing_fields": BacktestConfigChecker.REQUIRED_CONFIG_FIELDS[membership_level],
            "current_config": {},
            "config_prompt": "无法检查回测配置，请确保数据库连接正常。建议先配置回测参数再进行策略生成。",
            "default_suggestions": BacktestConfigChecker._get_suggested_config(membership_level)
        }
    
    @staticmethod
    def should_skip_backtest(config_check: Dict[str, Any]) -> bool:
        """判断是否应该跳过回测"""
        return not config_check.get("is_complete", False)
    
    @staticmethod
    def generate_strategy_saved_notification(
        strategy_name: str,
        config_check: Dict[str, Any],
        generation_id: str
    ) -> str:
        """生成策略保存成功的通知消息"""
        notification = f"✅ **策略已成功生成并保存**\n\n"
        notification += f"📝 策略名称: {strategy_name}\n"
        notification += f"🆔 生成ID: {generation_id[:8]}...\n"
        notification += f"💾 保存位置: 策略库 → 我的策略\n\n"
        
        if BacktestConfigChecker.should_skip_backtest(config_check):
            notification += "⚙️ **下一步：配置回测参数**\n"
            notification += config_check.get("config_prompt", "")
            notification += "\n\n💡 配置完成后，系统将自动为您的策略进行专业回测分析！"
        else:
            notification += "🚀 **回测配置已就绪，即将开始回测...**\n"
            notification += "系统将使用您的配置自动进行策略回测，请稍候查看结果。"
        
        return notification