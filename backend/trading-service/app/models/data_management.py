"""
数据管理扩展模型 - 高频数据存储和管理功能增强
补充现有data_collection.py模型，专注于Tick数据和用户数据访问管理
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, DECIMAL, Date, BigInteger, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class TickData(Base):
    """Tick数据模型 - 高频交易数据存储"""
    __tablename__ = "tick_data"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    
    # Tick数据核心字段
    price = Column(DECIMAL(20, 8), nullable=False)
    volume = Column(DECIMAL(18, 8), nullable=False)
    side = Column(String(4), nullable=False)  # buy, sell
    trade_id = Column(String(50), nullable=True)  # 交易所原始ID
    timestamp = Column(BigInteger, nullable=False)  # 微秒级时间戳
    
    # 订单簿相关数据
    best_bid = Column(DECIMAL(20, 8), nullable=True)
    best_ask = Column(DECIMAL(20, 8), nullable=True)
    bid_size = Column(DECIMAL(18, 8), nullable=True)
    ask_size = Column(DECIMAL(18, 8), nullable=True)
    
    # 数据质量标记
    is_validated = Column(Boolean, default=False)
    data_source = Column(String(50), nullable=True)  # websocket, rest_api, file_import
    sequence_number = Column(BigInteger, nullable=True)  # 序列号用于数据完整性检查
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 创建复合索引优化查询性能
    __table_args__ = (
        Index('idx_tick_data_symbol_time', 'exchange', 'symbol', 'timestamp'),
        Index('idx_tick_data_time_range', 'timestamp', 'exchange'),
    )


class DataExportTask(Base):
    """数据导出任务模型 - 用户数据导出请求管理"""
    __tablename__ = "data_export_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    task_name = Column(String(100), nullable=False)
    export_type = Column(String(50), nullable=False)  # kline, tick, trades, orderbook
    
    # 导出参数
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    timeframe = Column(String(10), nullable=True)  # 仅用于K线数据
    
    # 导出配置
    format = Column(String(20), default="csv")  # csv, json, parquet, xlsx
    compression = Column(String(20), default="gzip")  # none, gzip, bz2, zip
    include_headers = Column(Boolean, default=True)
    max_records = Column(Integer, default=1000000)  # 最大记录数限制
    
    # 任务状态
    status = Column(String(20), default="pending")  # pending, processing, completed, failed, expired
    progress = Column(Integer, default=0)  # 进度百分比
    estimated_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    
    # 文件信息
    file_path = Column(String(500), nullable=True)
    file_size_mb = Column(DECIMAL(12, 2), default=0)
    download_token = Column(String(100), nullable=True)  # 下载令牌
    expires_at = Column(DateTime, nullable=True)  # 文件过期时间
    download_count = Column(Integer, default=0)
    max_downloads = Column(Integer, default=3)
    
    # 执行信息
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_time_seconds = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserDataAccess(Base):
    """用户数据访问权限模型"""
    __tablename__ = "user_data_access"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # 权限配置
    data_type = Column(String(50), nullable=False)  # kline, tick, trades, orderbook
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=True)  # null表示所有交易对
    
    # 访问限制
    max_records_per_request = Column(Integer, default=10000)
    max_time_range_days = Column(Integer, default=30)
    max_requests_per_hour = Column(Integer, default=100)
    max_requests_per_day = Column(Integer, default=1000)
    
    # 历史数据访问限制
    historical_data_days = Column(Integer, default=365)  # 可访问历史数据天数
    tick_data_access = Column(Boolean, default=False)    # 是否允许访问Tick数据
    real_time_access = Column(Boolean, default=True)     # 是否允许实时数据访问
    
    # 状态管理
    is_active = Column(Boolean, default=True)
    granted_by = Column(Integer, nullable=True)  # 管理员ID
    granted_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    
    # 使用统计
    total_requests = Column(Integer, default=0)
    total_records_accessed = Column(BigInteger, default=0)
    last_access_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DataPartition(Base):
    """数据分区管理模型 - 用于大数据存储优化"""
    __tablename__ = "data_partitions"
    
    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(100), nullable=False, index=True)
    partition_name = Column(String(100), nullable=False, unique=True)
    
    # 分区信息
    partition_type = Column(String(20), nullable=False)  # time, range, hash
    partition_key = Column(String(100), nullable=False)  # 分区字段
    partition_value = Column(String(100), nullable=False)  # 分区值/范围
    
    # 分区统计
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_records = Column(BigInteger, default=0)
    storage_size_mb = Column(DECIMAL(12, 2), default=0)
    index_size_mb = Column(DECIMAL(12, 2), default=0)
    
    # 性能统计
    avg_query_time_ms = Column(Integer, default=0)
    total_queries = Column(Integer, default=0)
    last_query_at = Column(DateTime, nullable=True)
    
    # 维护信息
    last_vacuum_at = Column(DateTime, nullable=True)
    last_analyze_at = Column(DateTime, nullable=True)
    maintenance_status = Column(String(20), default="active")  # active, readonly, maintenance, archived
    
    # 归档信息
    is_archived = Column(Boolean, default=False)
    archive_location = Column(String(500), nullable=True)
    archive_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DataPipelineConfig(Base):
    """数据管道配置模型 - ETL流程管理"""
    __tablename__ = "data_pipeline_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    pipeline_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # 管道配置
    source_type = Column(String(50), nullable=False)  # api, websocket, file, database
    source_config = Column(Text, nullable=False)  # JSON configuration
    target_table = Column(String(100), nullable=False)
    
    # 处理配置
    transform_rules = Column(Text, nullable=True)  # JSON transformation rules
    validation_rules = Column(Text, nullable=True)  # JSON validation rules
    deduplication_key = Column(String(100), nullable=True)  # 去重字段
    
    # 执行配置
    batch_size = Column(Integer, default=1000)
    parallel_workers = Column(Integer, default=1)
    max_retry_count = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)
    
    # 监控配置
    alert_on_failure = Column(Boolean, default=True)
    alert_recipients = Column(Text, nullable=True)  # JSON email list
    sla_minutes = Column(Integer, default=60)  # SLA时间限制
    
    # 状态管理
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="idle")  # idle, running, paused, error
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    
    # 统计信息
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)
    avg_runtime_seconds = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DataQualityRule(Base):
    """数据质量规则模型 - 自定义数据质量检查规则"""
    __tablename__ = "data_quality_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # 规则配置
    target_table = Column(String(100), nullable=False)
    rule_type = Column(String(50), nullable=False)  # completeness, accuracy, consistency, timeliness, validity
    rule_sql = Column(Text, nullable=False)  # SQL查询规则
    threshold_value = Column(DECIMAL(10, 4), nullable=True)  # 阈值
    threshold_operator = Column(String(10), default=">=")  # >=, <=, ==, !=
    
    # 执行配置
    schedule_cron = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    
    # 处理配置
    auto_fix_enabled = Column(Boolean, default=False)
    auto_fix_sql = Column(Text, nullable=True)
    notification_enabled = Column(Boolean, default=True)
    escalation_minutes = Column(Integer, default=60)
    
    # 统计信息
    total_checks = Column(Integer, default=0)
    passed_checks = Column(Integer, default=0)
    failed_checks = Column(Integer, default=0)
    last_check_at = Column(DateTime, nullable=True)
    last_check_result = Column(String(20), nullable=True)  # passed, failed, error
    last_check_value = Column(DECIMAL(15, 4), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DataAccessAudit(Base):
    """数据访问审计模型 - 记录所有数据访问活动"""
    __tablename__ = "data_access_audit"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    
    # 访问信息
    operation = Column(String(50), nullable=False)  # read, export, download, query
    data_type = Column(String(50), nullable=False)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=True)
    
    # 查询详情
    time_range_start = Column(DateTime, nullable=True)
    time_range_end = Column(DateTime, nullable=True)
    records_requested = Column(Integer, default=0)
    records_returned = Column(Integer, default=0)
    query_duration_ms = Column(Integer, default=0)
    
    # 网络信息
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    api_endpoint = Column(String(200), nullable=True)
    
    # 结果信息
    status = Column(String(20), nullable=False)  # success, failed, partial, denied
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    response_size_kb = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 创建索引优化审计查询
    __table_args__ = (
        Index('idx_data_access_user_time', 'user_id', 'created_at'),
        Index('idx_data_access_operation_time', 'operation', 'created_at'),
    )