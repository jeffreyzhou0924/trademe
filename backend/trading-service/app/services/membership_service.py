"""
会员管理服务
处理用户会员权益、使用统计和限制管理
"""

from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, or_, select
from typing import Dict, Any
from loguru import logger

from app.models.user import User
from app.models.strategy import Strategy
from app.models.api_key import ApiKey
from app.models.trading_note import TradingNote
from app.models.claude_conversation import ClaudeUsage
from app.schemas.membership import UserStats, MembershipLimits
from app.services.ai_service import AIService


class MembershipService:
    """会员服务"""
    
    # 会员等级限制配置
    MEMBERSHIP_LIMITS = {
        "basic": MembershipLimits(
            membership_level="basic",
            api_keys_limit=1,           # 绑定1个交易所API
            ai_daily_limit=20.0,        # 每天$20 AI额度
            tick_backtest_limit=0,      # 无Tick级别回测
            storage_limit=0.005,        # 5KB
            indicators_limit=1,         # AI指标数量
            strategies_limit=1,         # AI策略数量
            live_trading_limit=1        # 1个免费实盘
        ),
        "premium": MembershipLimits(
            membership_level="premium", 
            api_keys_limit=5,           # 绑定5个交易所API
            ai_daily_limit=100.0,       # 每天$100 AI额度
            tick_backtest_limit=30,     # 每月30次Tick级别回测
            storage_limit=0.050,        # 50KB
            indicators_limit=5,         # AI指标数量
            strategies_limit=5,         # AI策略数量
            live_trading_limit=5        # 5个免费实盘
        ),
        "professional": MembershipLimits(
            membership_level="professional",
            api_keys_limit=10,          # 绑定10个交易所API
            ai_daily_limit=200.0,       # 每天$200 AI额度
            tick_backtest_limit=100,    # 每月100次Tick级别回测
            storage_limit=0.100,        # 100KB
            indicators_limit=10,        # AI指标数量
            strategies_limit=10,        # AI策略数量
            live_trading_limit=10       # 10个免费实盘
        )
    }
    
    @classmethod
    def get_membership_limits(cls, membership_level: str) -> MembershipLimits:
        """获取会员等级限制"""
        return cls.MEMBERSHIP_LIMITS.get(membership_level.lower(), cls.MEMBERSHIP_LIMITS["basic"])
    
    @classmethod
    async def get_user_usage_stats(cls, db: AsyncSession, user_id: int, membership_level: str) -> UserStats:
        """获取用户使用统计"""
        
        # 获取会员限制
        limits = cls.get_membership_limits(membership_level)
        
        # 查询API密钥数量
        api_keys_result = await db.execute(
            select(func.count(ApiKey.id)).where(
                and_(ApiKey.user_id == user_id, ApiKey.is_active == True)
            )
        )
        api_keys_count = api_keys_result.scalar() or 0
        
        # 查询策略数量
        strategies_result = await db.execute(
            select(func.count(Strategy.id)).where(
                and_(Strategy.user_id == user_id, Strategy.is_active == True)
            )
        )
        total_strategies_count = strategies_result.scalar() or 0
        
        # 根据前端实际显示情况，策略数量需要调整
        # 从总策略中筛选出纯策略类型（排除指标类型）
        strategy_only_result = await db.execute(
            select(func.count(Strategy.id)).where(
                and_(
                    Strategy.user_id == user_id, 
                    Strategy.is_active == True,
                    ~Strategy.name.contains('指标'),
                    ~Strategy.description.contains('指标'),
                    func.coalesce(Strategy.description, '').not_like('%指标%')
                )
            )
        )
        pure_strategy_count = strategy_only_result.scalar() or 0
        strategies_count = pure_strategy_count  # AI生成的策略总数
        
        # 查询实盘交易数量 (从新的live_strategies表)
        try:
            from app.models.live_strategy import LiveStrategy
            
            # 查询有效实盘数量 (running + paused状态)
            live_trading_result = await db.execute(
                select(func.count(LiveStrategy.id)).where(
                    and_(
                        LiveStrategy.user_id == user_id,
                        LiveStrategy.status.in_(['running', 'paused'])
                    )
                )
            )
            live_trading_count = live_trading_result.scalar() or 0
            
        except Exception as e:
            # 如果live_strategies表不存在，使用策略数量的默认逻辑
            logger.warning(f"无法查询live_strategies表: {e}")
            live_trading_count = min(3, total_strategies_count)
        
        # 确保不超过会员限制
        live_trading_count = min(live_trading_count, limits.live_trading_limit)
        
        # 查询指标数量 (从策略表中筛选指标类型)
        indicators_result = await db.execute(
            select(func.count(Strategy.id)).where(
                and_(
                    Strategy.user_id == user_id,
                    Strategy.is_active == True,
                    or_(
                        Strategy.name.contains('指标'),
                        Strategy.name.contains('RSI'),
                        Strategy.name.contains('MACD'),
                        Strategy.name.contains('MA'),
                        Strategy.name.contains('KDJ'),
                        Strategy.name.contains('BOLL'),
                        func.coalesce(Strategy.description, '').like('%指标%')
                    )
                )
            )
        )
        indicators_count = indicators_result.scalar() or 0
        
        # 确保不超过会员限制
        indicators_count = min(indicators_count, limits.indicators_limit)
        
        # 查询Tick级回测使用量 (本月)
        tick_backtest_today = 0
        try:
            from app.models.backtest import Backtest
            
            # 获取本月开始时间
            today_dt = datetime.utcnow().date()
            month_start = today_dt.replace(day=1)
            month_start_datetime = datetime.combine(month_start, datetime.min.time())
            
            # 查询本月的回测次数 (所有回测都算作Tick级，因为目前没有类型区分)
            tick_backtest_result = await db.execute(
                select(func.count(Backtest.id)).where(
                    and_(
                        Backtest.user_id == user_id,
                        Backtest.created_at >= month_start_datetime
                    )
                )
            )
            tick_backtest_today = tick_backtest_result.scalar() or 0
        except Exception as e:
            # 如果查询失败，使用会员级别的模拟默认值
            if membership_level.lower() == "basic":
                tick_backtest_today = 3
            elif membership_level.lower() == "premium":  
                tick_backtest_today = 35
            else:
                tick_backtest_today = 85
            logger.warning(f"无法查询Tick回测数量，使用默认值: {e}")
        
        # 查询交易心得存储使用量（字符数转换为MB）
        notes_storage_result = await db.execute(
            select(func.coalesce(func.sum(func.length(TradingNote.content)), 0)).where(
                TradingNote.user_id == user_id
            )
        )
        notes_storage = notes_storage_result.scalar() or 0
        storage_used = round(notes_storage / (1024 * 1024), 3)  # 转换为MB
        
        # 获取今日AI使用量（显示按2倍计费的金额）
        today_date = date.today()
        ai_usage_today = await AIService.get_daily_usage_cost(db, user_id, today_date)
        
        return UserStats(
            api_keys_count=api_keys_count,
            api_keys_limit=limits.api_keys_limit,
            ai_usage_today=ai_usage_today,
            ai_daily_limit=limits.ai_daily_limit,
            tick_backtest_today=tick_backtest_today,
            tick_backtest_limit=limits.tick_backtest_limit,
            storage_used=storage_used,
            storage_limit=limits.storage_limit,
            indicators_count=indicators_count,
            indicators_limit=limits.indicators_limit,
            strategies_count=strategies_count,
            strategies_limit=limits.strategies_limit,
            live_trading_count=live_trading_count,
            live_trading_limit=limits.live_trading_limit
        )
    
    @classmethod
    def check_usage_limit(cls, membership_level: str, usage_type: str, current_usage: int) -> bool:
        """检查使用限制"""
        limits = cls.get_membership_limits(membership_level)
        
        limit_map = {
            "api_keys": limits.api_keys_limit,
            "strategies": limits.strategies_limit,
            "indicators": limits.indicators_limit,
            "live_trading": limits.live_trading_limit,
            "tick_backtest": limits.tick_backtest_limit
        }
        
        max_limit = limit_map.get(usage_type)
        if max_limit is None:
            return True  # 未定义限制，允许使用
        
        return current_usage < max_limit
    
    @classmethod
    def get_membership_features(cls, membership_level: str) -> Dict[str, Any]:
        """获取会员功能特性"""
        features_map = {
            "basic": {
                "name": "免费用户",
                "price": 0,
                "period": "永久",
                "features": [
                    "无限次使用K线级别数据回测策略",
                    "可以绑定1个API密钥",
                    "免费使用总额度20美元的AI对话",
                    "包含交易心得AI和AI策略/AI指标创建",
                    "保留1KB的交易心得记录供AI分析",
                    "可添加1个指标/1个策略",
                    "可以运行1个实盘"
                ]
            },
            "premium": {
                "name": "初级用户",
                "price": 19,
                "period": "月",
                "features": [
                    "可以绑定1个API密钥",
                    "每天使用20美元额度的AI对话",
                    "包含交易心得AI和AI策略/AI指标创建",
                    "每天可使用Tick级别数据回测5次AI策略",
                    "无限次使用K线级别数据回测策略",
                    "保留1MB交易心得记录供AI分析",
                    "可以添加2个指标/2个策略",
                    "可以运行2个实盘"
                ]
            },
            "professional": {
                "name": "高级用户",
                "price": 99,
                "period": "月",
                "features": [
                    "可以绑定3个API密钥",
                    "每天使用100美元额度的AI对话",
                    "包含交易心得AI和AI策略/AI指标创建",
                    "每天可使用Tick级别数据回测20次AI策略",
                    "无限次使用K线级别数据回测策略",
                    "保留20MB交易心得记录供AI分析",
                    "可以添加10个指标/10个策略",
                    "可以运行10个实盘"
                ]
            },
            "enterprise": {
                "name": "专业用户",
                "price": 199,
                "period": "月",
                "features": [
                    "可以绑定20个API密钥",
                    "每天使用200美元额度的AI对话",
                    "包含交易心得AI和AI策略创建",
                    "每天可使用Tick级别数据回测50次",
                    "无限次使用K线级别数据回测策略",
                    "保留50MB交易心得记录供AI分析",
                    "可以添加20个指标/20个策略",
                    "可以运行20个实盘"
                ]
            }
        }
        
        return features_map.get(membership_level.lower(), features_map["basic"])