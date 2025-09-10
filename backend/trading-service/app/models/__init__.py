"""
Trademe Trading Service - 数据模型

SQLAlchemy ORM模型定义
"""

from .api_key import ApiKey
from .backtest import Backtest
from .market_data import MarketData
from .strategy import Strategy
from .trade import Trade
from .user import User
from .claude_conversation import ClaudeConversation, GeneratedStrategy
from .trading_note import TradingNote, TradingNoteLike, TradingNoteComment

# 管理后台模型
from .admin import Admin, AdminRole, AdminOperationLog, AdminSession
from .claude_proxy import (
    ClaudeAccount, Proxy, ClaudeUsageLog, ClaudeSchedulerConfig, 
    ProxyHealthCheck, UserClaudeKey
)
from .payment import (
    USDTWallet, USDTPaymentOrder, BlockchainTransaction, PaymentWebhook, 
    WalletBalance, PaymentNotification
)
from .data_collection import (
    DataCollectionTask, DataQualityMetric, ExchangeAPIConfig, 
    DataCollectionLog, DataStorageUsage, DataCleanupJob
)
from .data_management import (
    TickData, DataExportTask, UserDataAccess, DataPartition,
    DataPipelineConfig, DataQualityRule, DataAccessAudit
)
from .membership import MembershipPlan

# 用户管理系统模型
from .user_management import (
    UserTag, UserTagAssignment, UserActivityLog, UserStatisticsSnapshot,
    UserNotification, UserBehaviorProfile, TagType, ActivityType,
    NotificationType, NotificationChannel, NotificationStatus
)

__all__ = [
    # 原有模型
    "ApiKey",
    "Backtest", 
    "MarketData",
    "Strategy",
    "Trade",
    "User",
    "ClaudeConversation",
    "GeneratedStrategy",
    "TradingNote",
    "TradingNoteLike", 
    "TradingNoteComment",
    
    # 管理后台模型
    "Admin",
    "AdminRole", 
    "AdminOperationLog",
    "AdminSession",
    
    # Claude代理池模型
    "ClaudeAccount",
    "Proxy",
    "ClaudeUsageLog",
    "ClaudeSchedulerConfig", 
    "ProxyHealthCheck",
    "UserClaudeKey",
    
    # 支付系统模型
    "USDTWallet",
    "USDTPaymentOrder",
    "BlockchainTransaction",
    "PaymentWebhook",
    "WalletBalance",
    "PaymentNotification",
    
    # 数据采集模型
    "DataCollectionTask",
    "DataQualityMetric",
    "ExchangeAPIConfig",
    "DataCollectionLog",
    "DataStorageUsage",
    "DataCleanupJob",
    
    # 数据管理扩展模型
    "TickData",
    "DataExportTask",
    "UserDataAccess",
    "DataPartition",
    "DataPipelineConfig",
    "DataQualityRule",
    "DataAccessAudit",
    
    # 会员计划模型
    "MembershipPlan",
    
    # 用户管理系统模型
    "UserTag",
    "UserTagAssignment", 
    "UserActivityLog",
    "UserStatisticsSnapshot",
    "UserNotification",
    "UserBehaviorProfile",
    "TagType",
    "ActivityType", 
    "NotificationType",
    "NotificationChannel",
    "NotificationStatus"
]