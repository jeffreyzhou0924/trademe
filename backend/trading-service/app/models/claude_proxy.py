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
    api_key = Column(String(255), nullable=False)
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
    username = Column(String(100), nullable=True)
    password = Column(String(255), nullable=True)
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