-- ================================
-- Tick数据存储架构设计  
-- 高频交易数据的分区存储和压缩管理
-- ================================

-- Tick数据压缩存储表
CREATE TABLE IF NOT EXISTS tick_data_compressed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,           -- 交易所名称
    symbol VARCHAR(20) NOT NULL,             -- 交易对
    time_range_start BIGINT NOT NULL,        -- 时间范围开始(毫秒)
    time_range_end BIGINT NOT NULL,          -- 时间范围结束(毫秒)
    compressed_data BLOB NOT NULL,           -- 压缩的tick数据(gzip+pickle)
    original_count INTEGER NOT NULL,         -- 原始记录数
    compression_ratio DECIMAL(5,3) NOT NULL, -- 压缩比
    compression_method VARCHAR(20) DEFAULT 'gzip_pickle', -- 压缩方法
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tick数据实时缓存表 (最近1小时)
CREATE TABLE IF NOT EXISTS tick_data_realtime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,               -- 时间戳(毫秒)
    price DECIMAL(18,8) NOT NULL,           -- 成交价格
    quantity DECIMAL(18,8) NOT NULL,        -- 成交数量
    side VARCHAR(10),                       -- 买卖方向(buy/sell)
    trade_id VARCHAR(50),                   -- 交易ID
    is_buyer_maker BOOLEAN,                 -- 是否为挂单成交
    data_source VARCHAR(20) DEFAULT 'websocket', -- 数据来源
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 自动过期策略：超过1小时自动清理
    expires_at DATETIME DEFAULT (datetime('now', '+1 hour'))
);

-- 自定义时间框架K线表
CREATE TABLE IF NOT EXISTS custom_kline_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    custom_timeframe VARCHAR(10) NOT NULL,   -- 自定义时间框架(如3m, 7m, 2h等)
    open_time BIGINT NOT NULL,
    close_time BIGINT NOT NULL,
    open_price DECIMAL(18,8) NOT NULL,
    high_price DECIMAL(18,8) NOT NULL,
    low_price DECIMAL(18,8) NOT NULL,
    close_price DECIMAL(18,8) NOT NULL,
    volume DECIMAL(18,8) NOT NULL,
    trades_count INTEGER,
    aggregation_source VARCHAR(20) DEFAULT 'tick', -- tick/kline
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 数据聚合任务表
CREATE TABLE IF NOT EXISTS data_aggregation_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type VARCHAR(20) NOT NULL,        -- tick/kline
    target_timeframe VARCHAR(10) NOT NULL,   -- 目标时间框架
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    time_range_start BIGINT NOT NULL,
    time_range_end BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',    -- pending/running/completed/failed
    progress DECIMAL(5,2) DEFAULT 0.0,
    source_records INTEGER DEFAULT 0,       -- 源记录数
    output_records INTEGER DEFAULT 0,       -- 输出记录数
    aggregation_method VARCHAR(50),         -- 聚合方法描述
    error_message TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 数据存储统计表
CREATE TABLE IF NOT EXISTS data_storage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name VARCHAR(50) NOT NULL,         -- 表名
    exchange VARCHAR(50),
    symbol VARCHAR(20),
    timeframe VARCHAR(10),
    record_count INTEGER NOT NULL,          -- 记录数量
    storage_size_mb DECIMAL(10,3) NOT NULL, -- 存储大小(MB)
    compressed_size_mb DECIMAL(10,3),      -- 压缩后大小
    oldest_timestamp BIGINT,               -- 最早时间戳
    newest_timestamp BIGINT,               -- 最新时间戳
    last_calculated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ================================
-- Tick数据索引设计(高性能查询)
-- ================================

-- Tick数据核心索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_tick_unique ON tick_data(exchange, symbol, timestamp, trade_id);
CREATE INDEX IF NOT EXISTS idx_tick_symbol_time_range ON tick_data(exchange, symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_tick_price_volume ON tick_data(price, quantity, timestamp);
CREATE INDEX IF NOT EXISTS idx_tick_side_maker ON tick_data(side, is_buyer_maker, timestamp);

-- 实时tick数据索引
CREATE INDEX IF NOT EXISTS idx_tick_realtime_symbol ON tick_data_realtime(exchange, symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_tick_realtime_expires ON tick_data_realtime(expires_at);

-- 压缩数据索引
CREATE INDEX IF NOT EXISTS idx_tick_compressed_range ON tick_data_compressed(exchange, symbol, time_range_start, time_range_end);
CREATE INDEX IF NOT EXISTS idx_tick_compressed_time ON tick_data_compressed(time_range_start);

-- 自定义K线索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_custom_kline_unique ON custom_kline_data(exchange, symbol, custom_timeframe, open_time);
CREATE INDEX IF NOT EXISTS idx_custom_kline_timeframe ON custom_kline_data(custom_timeframe, open_time);

-- 聚合任务索引
CREATE INDEX IF NOT EXISTS idx_aggregation_tasks_status ON data_aggregation_tasks(status, created_at);
CREATE INDEX IF NOT EXISTS idx_aggregation_tasks_symbol ON data_aggregation_tasks(exchange, symbol, target_timeframe);

-- 存储统计索引
CREATE INDEX IF NOT EXISTS idx_storage_stats_table ON data_storage_stats(table_name, last_calculated);
CREATE INDEX IF NOT EXISTS idx_storage_stats_symbol ON data_storage_stats(exchange, symbol, timeframe);

-- ================================
-- 分区管理策略 (SQLite模拟)
-- ================================

-- 按日期创建视图来模拟分区
CREATE VIEW IF NOT EXISTS tick_data_today AS
SELECT * FROM tick_data 
WHERE timestamp >= strftime('%s', 'now', 'start of day') * 1000;

CREATE VIEW IF NOT EXISTS tick_data_yesterday AS  
SELECT * FROM tick_data
WHERE timestamp >= strftime('%s', 'now', '-1 day', 'start of day') * 1000
  AND timestamp < strftime('%s', 'now', 'start of day') * 1000;

CREATE VIEW IF NOT EXISTS tick_data_last_hour AS
SELECT * FROM tick_data_realtime
WHERE timestamp >= strftime('%s', 'now', '-1 hour') * 1000;

-- ================================
-- 自动清理和维护策略
-- ================================

-- 创建自动过期触发器(模拟)
-- 实际使用中需要定时任务清理expired数据

-- 压缩任务调度配置
CREATE TABLE IF NOT EXISTS data_maintenance_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(50) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 默认维护配置
INSERT OR REPLACE INTO data_maintenance_config (config_key, config_value, description) VALUES
('tick_compression_threshold_hours', '1', 'Tick数据压缩时间阈值(小时)'),
('tick_retention_days', '30', 'Tick数据保留天数'),
('kline_retention_days', '365', 'K线数据保留天数'),
('realtime_cache_hours', '1', '实时缓存保留小时数'),
('compression_batch_size', '10000', '压缩批处理大小'),
('aggregation_batch_size', '50000', '聚合批处理大小');

-- ================================
-- 性能监控表
-- ================================

CREATE TABLE IF NOT EXISTS data_performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type VARCHAR(50) NOT NULL,    -- insert/query/aggregate/compress
    table_name VARCHAR(50) NOT NULL,
    record_count INTEGER NOT NULL,
    execution_time_ms INTEGER NOT NULL,     -- 执行时间(毫秒)
    memory_usage_mb DECIMAL(10,2),         -- 内存使用(MB)
    cpu_usage_percent DECIMAL(5,2),       -- CPU使用率
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_performance_operation ON data_performance_metrics(operation_type, created_at);
CREATE INDEX IF NOT EXISTS idx_performance_table ON data_performance_metrics(table_name, success, created_at);