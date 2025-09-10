-- ================================
-- K线数据存储架构设计
-- 支持多交易所、多时间框架的历史数据存储
-- ================================

-- K线数据主表 (OHLCV格式)
CREATE TABLE IF NOT EXISTS kline_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,           -- 交易所名称 (binance, okx, huobi等)
    symbol VARCHAR(20) NOT NULL,             -- 交易对 (BTC/USDT, ETH/USDT等)
    timeframe VARCHAR(10) NOT NULL,          -- 时间框架 (1m, 5m, 15m, 1h, 4h, 1d)
    open_time BIGINT NOT NULL,               -- K线开盘时间戳(毫秒)
    close_time BIGINT NOT NULL,              -- K线收盘时间戳(毫秒)
    open_price DECIMAL(18,8) NOT NULL,       -- 开盘价
    high_price DECIMAL(18,8) NOT NULL,       -- 最高价
    low_price DECIMAL(18,8) NOT NULL,        -- 最低价
    close_price DECIMAL(18,8) NOT NULL,      -- 收盘价
    volume DECIMAL(18,8) NOT NULL,           -- 成交量(基础货币)
    quote_volume DECIMAL(18,8),              -- 成交额(计价货币)
    trades_count INTEGER,                    -- 成交笔数
    taker_buy_volume DECIMAL(18,8),         -- 主动买入成交量
    taker_buy_quote_volume DECIMAL(18,8),   -- 主动买入成交额
    data_source VARCHAR(20) DEFAULT 'api',   -- 数据来源(api/file/manual)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tick数据表 (高频数据)
CREATE TABLE IF NOT EXISTS tick_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,           -- 交易所名称
    symbol VARCHAR(20) NOT NULL,             -- 交易对
    timestamp BIGINT NOT NULL,               -- 时间戳(毫秒)
    price DECIMAL(18,8) NOT NULL,           -- 成交价格
    quantity DECIMAL(18,8) NOT NULL,        -- 成交数量
    side VARCHAR(10),                       -- 买卖方向(buy/sell)
    trade_id VARCHAR(50),                   -- 交易ID
    is_buyer_maker BOOLEAN,                 -- 是否为挂单成交
    data_source VARCHAR(20) DEFAULT 'api',  -- 数据来源
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 数据下载任务表
CREATE TABLE IF NOT EXISTS data_download_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    start_date DATETIME NOT NULL,           -- 下载开始日期
    end_date DATETIME NOT NULL,             -- 下载结束日期
    status VARCHAR(20) DEFAULT 'pending',   -- pending/running/completed/failed
    progress DECIMAL(5,2) DEFAULT 0.0,     -- 下载进度百分比
    total_records INTEGER DEFAULT 0,        -- 预计记录数
    downloaded_records INTEGER DEFAULT 0,   -- 已下载记录数
    error_message TEXT,                     -- 错误信息
    started_at DATETIME,                    -- 开始时间
    completed_at DATETIME,                  -- 完成时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 数据质量监控表
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    date_range_start DATETIME NOT NULL,     -- 统计日期范围开始
    date_range_end DATETIME NOT NULL,       -- 统计日期范围结束
    total_expected INTEGER NOT NULL,        -- 预期K线数量
    total_actual INTEGER NOT NULL,          -- 实际K线数量
    missing_count INTEGER NOT NULL,         -- 缺失数量
    duplicate_count INTEGER NOT NULL,       -- 重复数量
    gap_count INTEGER NOT NULL,             -- 数据缺口数量
    quality_score DECIMAL(5,2) NOT NULL,    -- 质量评分(0-100)
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 数据缓存元信息表
CREATE TABLE IF NOT EXISTS data_cache_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    first_timestamp BIGINT,                 -- 最早数据时间戳
    last_timestamp BIGINT,                  -- 最新数据时间戳
    total_records INTEGER DEFAULT 0,        -- 总记录数
    storage_size_mb DECIMAL(10,2),         -- 存储大小(MB)
    last_sync_at DATETIME,                 -- 最后同步时间
    sync_status VARCHAR(20) DEFAULT 'active', -- active/inactive/error
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ================================
-- 性能优化索引
-- ================================

-- K线数据核心索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_kline_unique ON kline_data(exchange, symbol, timeframe, open_time);
CREATE INDEX IF NOT EXISTS idx_kline_symbol_time ON kline_data(exchange, symbol, timeframe, open_time);
CREATE INDEX IF NOT EXISTS idx_kline_timestamp_range ON kline_data(open_time, close_time);
CREATE INDEX IF NOT EXISTS idx_kline_timeframe ON kline_data(timeframe, open_time);

-- Tick数据核心索引  
CREATE INDEX IF NOT EXISTS idx_tick_symbol_time ON tick_data(exchange, symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_tick_timestamp ON tick_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_tick_price_range ON tick_data(price, timestamp);

-- 任务管理索引
CREATE INDEX IF NOT EXISTS idx_download_tasks_status ON data_download_tasks(status, created_at);
CREATE INDEX IF NOT EXISTS idx_download_tasks_symbol ON data_download_tasks(exchange, symbol, timeframe);

-- 数据质量索引
CREATE INDEX IF NOT EXISTS idx_quality_metrics_symbol ON data_quality_metrics(exchange, symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_quality_metrics_date ON data_quality_metrics(date_range_start, date_range_end);

-- 缓存元信息索引
CREATE INDEX IF NOT EXISTS idx_cache_metadata_symbol ON data_cache_metadata(exchange, symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_cache_metadata_sync ON data_cache_metadata(last_sync_at, sync_status);

-- ================================
-- 数据分区策略(SQLite替代方案)
-- ================================

-- 按月分表的视图(模拟分区)
-- 示例：kline_data_202401, kline_data_202402 等月表
-- CREATE VIEW kline_data_current AS 
-- SELECT * FROM kline_data WHERE open_time >= strftime('%s', 'now', '-1 month') * 1000;

-- ================================
-- 数据存储优化配置
-- ================================

-- 启用压缩存储
PRAGMA auto_vacuum = INCREMENTAL;

-- 优化页面大小(针对时序数据)
PRAGMA page_size = 4096;

-- 设置checkpoint频率
PRAGMA wal_autocheckpoint = 1000;