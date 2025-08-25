"""
用户管理系统扩展模型
包含用户标签、活动日志、统计快照、通知等高级用户管理功能
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Index
from sqlalchemy.sql.sqltypes import Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from app.database import Base


class TagType(PyEnum):
    """标签类型枚举"""
    SYSTEM = "system"  # 系统自动生成标签
    MANUAL = "manual"  # 管理员手动创建标签
    AUTO = "auto"      # 自动化规则生成标签


class ActivityType(PyEnum):
    """活动类型枚举"""
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    PROFILE_UPDATE = "profile_update"
    STRATEGY_CREATE = "strategy_create"
    STRATEGY_UPDATE = "strategy_update"
    STRATEGY_DELETE = "strategy_delete"
    BACKTEST_RUN = "backtest_run"
    LIVE_TRADING_START = "live_trading_start"
    LIVE_TRADING_STOP = "live_trading_stop"
    AI_CHAT = "ai_chat"
    MEMBERSHIP_UPGRADE = "membership_upgrade"
    API_KEY_CREATE = "api_key_create"
    API_KEY_DELETE = "api_key_delete"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFY = "email_verify"


class NotificationType(PyEnum):
    """通知类型枚举"""
    SYSTEM = "system"      # 系统通知
    SECURITY = "security"  # 安全通知
    TRADING = "trading"    # 交易通知
    MEMBERSHIP = "membership"  # 会员通知
    MARKETING = "marketing"    # 营销通知


class NotificationChannel(PyEnum):
    """通知渠道枚举"""
    EMAIL = "email"
    IN_APP = "in_app"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(PyEnum):
    """通知状态枚举"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class UserTag(Base):
    """用户标签表 - 支持灵活的用户分类和管理"""
    __tablename__ = "user_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True, comment="标签名称")
    display_name = Column(String(100), nullable=False, comment="显示名称")
    description = Column(Text, nullable=True, comment="标签描述")
    color = Column(String(7), default="#3B82F6", comment="标签颜色(HEX)")
    
    # 标签类型和属性
    tag_type = Column(SQLEnum(TagType), default=TagType.MANUAL, nullable=False, comment="标签类型")
    is_active = Column(Boolean, default=True, comment="是否启用")
    auto_assign_rule = Column(JSON, nullable=True, comment="自动分配规则(JSON)")
    
    # 统计信息
    user_count = Column(Integer, default=0, comment="使用该标签的用户数量")
    
    # 创建信息
    created_by = Column(Integer, ForeignKey("admins.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系映射
    tag_assignments = relationship("UserTagAssignment", back_populates="tag", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<UserTag(id={self.id}, name='{self.name}', type='{self.tag_type}')>"


class UserTagAssignment(Base):
    """用户标签分配表 - 多对多关系表"""
    __tablename__ = "user_tag_assignments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True, comment="用户ID")
    tag_id = Column(Integer, ForeignKey("user_tags.id"), nullable=False, comment="标签ID")
    
    # 分配信息
    assigned_by = Column(Integer, ForeignKey("admins.id"), nullable=True, comment="分配者ID")
    assigned_reason = Column(String(200), nullable=True, comment="分配原因")
    auto_assigned = Column(Boolean, default=False, comment="是否自动分配")
    
    # 时间信息
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime, nullable=True, comment="过期时间(可选)")
    
    # 关系映射
    tag = relationship("UserTag", back_populates="tag_assignments")
    
    # 索引
    __table_args__ = (
        Index('idx_user_tag_unique', 'user_id', 'tag_id', unique=True),
        Index('idx_user_tag_assignment_user', 'user_id'),
        Index('idx_user_tag_assignment_tag', 'tag_id'),
    )
    
    def __repr__(self):
        return f"<UserTagAssignment(user_id={self.user_id}, tag_id={self.tag_id})>"


class UserActivityLog(Base):
    """用户活动日志表 - 全面记录用户行为轨迹"""
    __tablename__ = "user_activity_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True, comment="用户ID")
    
    # 活动信息
    activity_type = Column(SQLEnum(ActivityType), nullable=False, comment="活动类型")
    activity_description = Column(String(500), nullable=False, comment="活动描述")
    
    # 请求信息
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    user_agent = Column(Text, nullable=True, comment="User Agent")
    referer = Column(String(500), nullable=True, comment="来源页面")
    
    # 上下文信息
    resource_type = Column(String(50), nullable=True, comment="资源类型")
    resource_id = Column(Integer, nullable=True, comment="资源ID")
    additional_data = Column(JSON, nullable=True, comment="附加数据")
    
    # 结果信息
    is_successful = Column(Boolean, default=True, comment="是否成功")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 索引
    __table_args__ = (
        Index('idx_user_activity_user_time', 'user_id', 'created_at'),
        Index('idx_user_activity_type_time', 'activity_type', 'created_at'),
        Index('idx_user_activity_resource', 'resource_type', 'resource_id'),
    )
    
    def __repr__(self):
        return f"<UserActivityLog(user_id={self.user_id}, type='{self.activity_type}', time='{self.created_at}')>"


class UserStatisticsSnapshot(Base):
    """用户统计快照表 - 定期保存用户关键指标"""
    __tablename__ = "user_statistics_snapshots"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True, comment="用户ID")
    snapshot_date = Column(DateTime, nullable=False, comment="快照日期")
    
    # 基础统计
    total_strategies = Column(Integer, default=0, comment="策略总数")
    active_strategies = Column(Integer, default=0, comment="活跃策略数")
    total_backtests = Column(Integer, default=0, comment="回测总数")
    total_trades = Column(Integer, default=0, comment="交易总数")
    
    # 活动统计
    login_count_30d = Column(Integer, default=0, comment="30天登录次数")
    last_login_days_ago = Column(Integer, nullable=True, comment="最后登录距今天数")
    active_days_30d = Column(Integer, default=0, comment="30天活跃天数")
    
    # 使用统计
    ai_chat_count_30d = Column(Integer, default=0, comment="30天AI对话次数")
    ai_cost_30d = Column(Numeric(10,4), default=0, comment="30天AI成本")
    feature_usage = Column(JSON, nullable=True, comment="功能使用统计")
    
    # 交易统计
    total_pnl = Column(Numeric(15,4), default=0, comment="累计盈亏")
    win_rate = Column(Numeric(5,4), nullable=True, comment="胜率")
    avg_trade_amount = Column(Numeric(15,4), default=0, comment="平均交易金额")
    
    # 会员统计
    membership_level = Column(String(20), nullable=True, comment="会员等级")
    membership_days_left = Column(Integer, nullable=True, comment="会员剩余天数")
    
    # 风险指标
    risk_score = Column(Numeric(5,2), default=0, comment="风险评分")
    account_health_score = Column(Numeric(5,2), default=100, comment="账户健康度评分")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_user_stats_user_date', 'user_id', 'snapshot_date', unique=True),
        Index('idx_user_stats_date', 'snapshot_date'),
    )
    
    def __repr__(self):
        return f"<UserStatisticsSnapshot(user_id={self.user_id}, date='{self.snapshot_date}')>"


class UserNotification(Base):
    """用户通知表 - 多渠道通知管理"""
    __tablename__ = "user_notifications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True, comment="用户ID")
    
    # 通知内容
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(Text, nullable=False, comment="通知内容")
    notification_type = Column(SQLEnum(NotificationType), nullable=False, comment="通知类型")
    
    # 渠道和状态
    channel = Column(SQLEnum(NotificationChannel), nullable=False, comment="通知渠道")
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, comment="通知状态")
    
    # 优先级和分类
    priority = Column(Integer, default=5, comment="优先级(1-10)")
    category = Column(String(50), nullable=True, comment="通知分类")
    
    # 处理信息
    sent_at = Column(DateTime, nullable=True, comment="发送时间")
    delivered_at = Column(DateTime, nullable=True, comment="送达时间")
    read_at = Column(DateTime, nullable=True, comment="阅读时间")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retry = Column(Integer, default=3, comment="最大重试次数")
    
    # 附加数据
    meta_data = Column(JSON, nullable=True, comment="元数据")
    action_url = Column(String(500), nullable=True, comment="操作链接")
    
    # 过期和删除
    expires_at = Column(DateTime, nullable=True, comment="过期时间")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    
    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_user_notification_user_status', 'user_id', 'status'),
        Index('idx_user_notification_type_time', 'notification_type', 'created_at'),
        Index('idx_user_notification_channel_status', 'channel', 'status'),
        Index('idx_user_notification_priority', 'priority', 'created_at'),
    )
    
    def __repr__(self):
        return f"<UserNotification(id={self.id}, user_id={self.user_id}, type='{self.notification_type}', status='{self.status}')>"


class UserBehaviorProfile(Base):
    """用户行为画像表 - AI分析生成的用户行为特征"""
    __tablename__ = "user_behavior_profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True, comment="用户ID")
    
    # 基础画像
    user_type = Column(String(50), nullable=True, comment="用户类型(新手/进阶/专家)")
    activity_level = Column(String(20), nullable=True, comment="活跃度(高/中/低)")
    engagement_score = Column(Numeric(5,2), default=0, comment="参与度评分")
    
    # 交易行为画像
    trading_style = Column(String(50), nullable=True, comment="交易风格")
    risk_preference = Column(String(20), nullable=True, comment="风险偏好")
    preferred_timeframe = Column(String(10), nullable=True, comment="偏好时间周期")
    preferred_instruments = Column(JSON, nullable=True, comment="偏好交易品种")
    
    # 使用习惯
    preferred_features = Column(JSON, nullable=True, comment="常用功能")
    usage_patterns = Column(JSON, nullable=True, comment="使用模式")
    peak_activity_hours = Column(JSON, nullable=True, comment="活跃时间段")
    
    # AI相关行为
    ai_usage_frequency = Column(String(20), nullable=True, comment="AI使用频率")
    preferred_ai_features = Column(JSON, nullable=True, comment="偏好AI功能")
    ai_interaction_style = Column(String(50), nullable=True, comment="AI交互风格")
    
    # 商业价值
    lifetime_value_score = Column(Numeric(8,2), default=0, comment="生命周期价值评分")
    churn_risk_score = Column(Numeric(5,2), default=0, comment="流失风险评分")
    upsell_potential_score = Column(Numeric(5,2), default=0, comment="升级潜力评分")
    
    # 更新信息
    last_analyzed_at = Column(DateTime, nullable=True, comment="最后分析时间")
    analysis_version = Column(String(10), default="1.0", comment="分析版本")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<UserBehaviorProfile(user_id={self.user_id}, type='{self.user_type}', activity='{self.activity_level}')>"