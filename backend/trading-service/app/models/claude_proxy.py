"""
Claude代理池模型 - Claude账号和代理服务器管理
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ClaudeAccount(Base):
    """Claude账号池模型"""
    __tablename__ = "claude_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String(100), nullable=False)
    api_key = Column(String(255), nullable=False)  # 加密存储的API密钥
    
    # 代理服务配置
    proxy_base_url = Column(String(255), nullable=True)  # 代理服务基础URL
    proxy_type = Column(String(50), default="direct")    # direct, proxy_service, oauth, official_api
    
    # Anthropic官方API配置
    anthropic_api_key = Column(String(500), nullable=True)  # 加密存储的官方API密钥
    anthropic_api_version = Column(String(20), default="2023-06-01")  # API版本
    anthropic_beta_header = Column(Text, nullable=True)  # Beta功能Header
    
    # 传统字段保留兼容性
    organization_id = Column(String(100), nullable=True)
    project_id = Column(String(100), nullable=True)
    daily_limit = Column(DECIMAL(10, 2), nullable=False)  # 每日限额(USD)
    current_usage = Column(DECIMAL(10, 2), default=0)     # 当前使用量
    remaining_balance = Column(DECIMAL(10, 2), nullable=True)  # 剩余余额
    status = Column(String(20), default="active")  # active, inactive, error, suspended
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    avg_response_time = Column(Integer, default=0)  # 平均响应时间(ms)
    success_rate = Column(DECIMAL(5, 2), default=100.0)  # 成功率(%)
    total_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    last_check_at = Column(DateTime, nullable=True)
    
    # OAuth认证字段 (新增) - 所有token均加密存储
    oauth_access_token = Column(Text, nullable=True)  # 加密存储的访问令牌
    oauth_refresh_token = Column(Text, nullable=True)  # 加密存储的刷新令牌
    oauth_expires_at = Column(DateTime, nullable=True)  # 令牌过期时间
    oauth_scopes = Column(Text, nullable=True)  # JSON字符串存储作用域
    oauth_token_type = Column(String(20), default="Bearer")  # 令牌类型
    
    # 扩展功能字段
    subscription_info = Column(Text, nullable=True)  # JSON字符串存储订阅信息
    error_message = Column(Text, nullable=True)  # 错误信息
    priority = Column(Integer, default=50)  # 调度优先级 (1-100，数字越小优先级越高)
    is_schedulable = Column(Boolean, default=True)  # 是否可被调度
    account_type = Column(String(20), default="shared")  # shared, dedicated
    proxy_config = Column(Text, nullable=True)  # JSON字符串存储代理配置(敏感信息已加密)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关联关系
    proxy = relationship("Proxy", back_populates="claude_accounts")


class Proxy(Base):
    """代理服务器模型"""
    __tablename__ = "proxies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    proxy_type = Column(String(20), nullable=False)  # http, https, socks5
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)  # 代理用户名
    password = Column(String(255), nullable=True)  # 加密存储的代理密码
    country = Column(String(50), nullable=True)
    region = Column(String(100), nullable=True)
    status = Column(String(20), default="active")  # active, inactive, error, banned
    response_time = Column(Integer, nullable=True)  # 响应时间(ms)
    success_rate = Column(DECIMAL(5, 2), default=100.0)  # 成功率(%)
    total_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    bandwidth_limit = Column(Integer, nullable=True)  # 带宽限制(MB/day)
    monthly_cost = Column(DECIMAL(8, 2), nullable=True)  # 月成本(USD)
    last_check_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关联关系
    claude_accounts = relationship("ClaudeAccount", back_populates="proxy")


class ClaudeUsageLog(Base):
    """Claude使用日志模型"""
    __tablename__ = "claude_usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("claude_accounts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    request_type = Column(String(50), nullable=False)  # chat, analysis, generation
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    api_cost = Column(DECIMAL(10, 6), default=0)  # API成本(USD)
    response_time = Column(Integer, nullable=True)  # 响应时间(ms)
    success = Column(Boolean, default=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    request_date = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClaudeSchedulerConfig(Base):
    """Claude调度器配置模型"""
    __tablename__ = "claude_scheduler_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    config_name = Column(String(100), nullable=False, unique=True)
    config_type = Column(String(50), nullable=False)  # load_balance, cost_optimize, failover
    config_data = Column(Text, nullable=False)  # JSON配置数据
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=100)  # 优先级，数字越小优先级越高
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserClaudeKey(Base):
    """用户虚拟Claude Key模型 - 用于统计用户使用情况"""
    __tablename__ = "user_claude_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    virtual_key = Column(String(255), nullable=False, unique=True, index=True)  # 虚拟密钥
    key_name = Column(String(100), nullable=False)  # 密钥名称
    status = Column(String(20), default="active")  # active, inactive, suspended, expired
    
    # 使用统计
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0) 
    failed_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(DECIMAL(10, 6), default=0)  # 总成本
    
    # 限制配置
    daily_request_limit = Column(Integer, nullable=True)  # 每日请求限制
    daily_token_limit = Column(Integer, nullable=True)   # 每日token限制
    daily_cost_limit = Column(DECIMAL(8, 2), nullable=True)  # 每日成本限制(USD)
    
    # 当日使用统计
    today_requests = Column(Integer, default=0)
    today_tokens = Column(Integer, default=0) 
    today_cost_usd = Column(DECIMAL(10, 6), default=0)
    usage_reset_date = Column(DateTime, nullable=True)  # 使用量重置日期
    
    # 会话管理
    sticky_session_enabled = Column(Boolean, default=False)  # 是否启用粘性会话
    preferred_account_id = Column(Integer, ForeignKey("claude_accounts.id"), nullable=True)  # 首选账号
    
    # 元数据
    description = Column(Text, nullable=True)
    extra_metadata = Column(Text, nullable=True)  # JSON扩展字段
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # 密钥过期时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())



class ProxyHealthCheck(Base):
    """代理健康检查记录模型"""
    __tablename__ = "proxy_health_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=False, index=True)
    check_type = Column(String(50), nullable=False)  # connectivity, speed, location
    check_result = Column(String(20), nullable=False)  # success, failed, timeout
    response_time = Column(Integer, nullable=True)  # 响应时间(ms)
    error_message = Column(Text, nullable=True)
    check_details = Column(Text, nullable=True)  # JSON详细信息
    checked_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())