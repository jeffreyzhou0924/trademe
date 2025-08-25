"""
数据采集管理模型 - 多交易所数据采集和质量监控
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, DECIMAL, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class DataCollectionTask(Base):
    """数据采集任务模型"""
    __tablename__ = "data_collection_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(100), nullable=False)
    exchange = Column(String(50), nullable=False, index=True)
    data_type = Column(String(50), nullable=False, index=True)  # kline, ticker, orderbook, trades, funding_rate
    symbols = Column(Text, nullable=False)  # JSON array
    timeframes = Column(Text, nullable=True)  # JSON array for kline
    
    # 任务配置
    status = Column(String(20), default="active", index=True)  # active, paused, stopped, error
    schedule_type = Column(String(20), default="interval")  # interval, cron
    schedule_config = Column(Text, nullable=True)  # JSON schedule configuration
    retry_config = Column(Text, nullable=True)  # JSON retry configuration
    
    # 执行统计
    last_run_at = Column(DateTime, nullable=True, index=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    total_records = Column(Integer, default=0)
    
    # 配置信息
    config = Column(Text, nullable=True)  # JSON additional config
    rate_limit = Column(Integer, default=10)  # 每秒请求数限制
    timeout = Column(Integer, default=30)     # 超时时间(秒)
    priority = Column(Integer, default=100)   # 优先级
    
    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_error_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)


class DataQualityMetric(Base):
    """数据质量监控指标模型"""
    __tablename__ = "data_quality_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("data_collection_tasks.id"), nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    data_type = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(10), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # 数据质量指标
    total_records = Column(Integer, default=0)
    missing_records = Column(Integer, default=0)
    duplicate_records = Column(Integer, default=0)
    invalid_records = Column(Integer, default=0)
    late_records = Column(Integer, default=0)  # 延迟到达的记录
    
    # 时效性指标
    avg_delay_ms = Column(Integer, default=0)    # 平均延迟(毫秒)
    max_delay_ms = Column(Integer, default=0)    # 最大延迟(毫秒)
    min_delay_ms = Column(Integer, default=0)    # 最小延迟(毫秒)
    
    # 完整性指标
    expected_records = Column(Integer, default=0)  # 期望记录数
    completeness_rate = Column(DECIMAL(5, 2), default=0)  # 完整性百分比
    
    # 质量评分
    quality_score = Column(DECIMAL(5, 2), default=0)  # 总质量评分(0-100)
    accuracy_score = Column(DECIMAL(5, 2), default=0)   # 准确性评分
    timeliness_score = Column(DECIMAL(5, 2), default=0) # 时效性评分
    consistency_score = Column(DECIMAL(5, 2), default=0) # 一致性评分
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExchangeAPIConfig(Base):
    """交易所API配置模型"""
    __tablename__ = "exchange_api_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=False)
    
    # API配置
    api_endpoint = Column(String(255), nullable=False)
    websocket_endpoint = Column(String(255), nullable=True)
    api_version = Column(String(20), nullable=True)
    
    # 限流配置
    rate_limit_per_second = Column(Integer, default=10)
    rate_limit_per_minute = Column(Integer, default=600)
    rate_limit_per_hour = Column(Integer, default=36000)
    weight_limit = Column(Integer, nullable=True)
    
    # 健康状态
    status = Column(String(20), default="active")  # active, maintenance, disabled, error
    health_check_url = Column(String(255), nullable=True)
    last_health_check = Column(DateTime, nullable=True)
    health_status = Column(String(20), default="unknown")  # healthy, unhealthy, unknown
    
    # 配置信息
    supported_data_types = Column(Text, nullable=True)  # JSON array
    supported_timeframes = Column(Text, nullable=True)  # JSON array
    timezone = Column(String(50), default="UTC")
    
    # 统计信息
    total_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    avg_response_time = Column(Integer, default=0)  # 毫秒
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DataCollectionLog(Base):
    """数据采集日志模型"""
    __tablename__ = "data_collection_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("data_collection_tasks.id"), nullable=False, index=True)
    execution_id = Column(String(50), nullable=False, index=True)  # 执行ID，同一次执行的所有日志共享
    
    # 日志信息
    log_level = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON additional details
    
    # 执行信息
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=True, index=True)
    data_type = Column(String(50), nullable=False)
    records_processed = Column(Integer, default=0)
    processing_time_ms = Column(Integer, default=0)
    
    # 错误信息
    error_code = Column(String(50), nullable=True)
    error_type = Column(String(100), nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DataStorageUsage(Base):
    """数据存储使用统计模型"""
    __tablename__ = "data_storage_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    exchange = Column(String(50), nullable=False, index=True)
    data_type = Column(String(50), nullable=False, index=True)
    
    # 存储统计
    total_records = Column(Integer, default=0)
    storage_size_mb = Column(DECIMAL(12, 2), default=0)  # 存储大小(MB)
    compressed_size_mb = Column(DECIMAL(12, 2), default=0)  # 压缩后大小(MB)
    compression_ratio = Column(DECIMAL(5, 2), default=0)    # 压缩比
    
    # 访问统计
    read_count = Column(Integer, default=0)     # 读取次数
    write_count = Column(Integer, default=0)    # 写入次数
    update_count = Column(Integer, default=0)   # 更新次数
    delete_count = Column(Integer, default=0)   # 删除次数
    
    # 成本统计
    storage_cost = Column(DECIMAL(10, 4), default=0)  # 存储成本
    bandwidth_cost = Column(DECIMAL(10, 4), default=0)  # 带宽成本
    api_cost = Column(DECIMAL(10, 4), default=0)        # API调用成本
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DataCleanupJob(Base):
    """数据清理任务模型"""
    __tablename__ = "data_cleanup_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), nullable=False)
    cleanup_type = Column(String(50), nullable=False)  # archive, delete, compress
    target_table = Column(String(100), nullable=False)
    
    # 清理规则
    retention_days = Column(Integer, nullable=False)  # 保留天数
    conditions = Column(Text, nullable=True)  # JSON where conditions
    batch_size = Column(Integer, default=1000)
    
    # 执行状态
    status = Column(String(20), default="scheduled")  # scheduled, running, completed, failed
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    records_processed = Column(Integer, default=0)
    records_affected = Column(Integer, default=0)
    
    # 结果统计
    space_freed_mb = Column(DECIMAL(12, 2), default=0)  # 释放的空间(MB)
    execution_time_seconds = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())