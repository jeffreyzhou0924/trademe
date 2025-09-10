-- ================================
-- 数据库性能优化脚本
-- 针对大规模历史数据和高频tick数据的查询优化
-- ================================

-- ================================
-- 1. SQLite配置优化
-- ================================

-- 启用扩展功能
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- 针对时序数据优化的缓存配置
PRAGMA cache_size = 50000;        -- 200MB缓存 (50000 * 4KB)
PRAGMA temp_store = memory;       -- 临时表存储在内存
PRAGMA mmap_size = 1073741824;    -- 1GB内存映射
PRAGMA optimize;                  -- 启用查询优化器

-- 针对大表的读取优化
PRAGMA read_uncommitted = true;   -- 允许脏读提高查询性能

-- ================================
-- 2. 核心业务查询索引优化
-- ================================

-- K线数据高性能复合索引
CREATE INDEX IF NOT EXISTS idx_kline_backtest_optimized ON kline_data(
    exchange, symbol, timeframe, open_time
) WHERE open_time IS NOT NULL;

-- 支持范围查询的覆盖索引
CREATE INDEX IF NOT EXISTS idx_kline_range_query ON kline_data(
    open_time, close_price, volume
) WHERE timeframe IN ('1h', '1d');

-- 按交易所分组的性能索引
CREATE INDEX IF NOT EXISTS idx_kline_exchange_partition ON kline_data(
    exchange, open_time
) WHERE exchange IN ('binance', 'okx', 'huobi');

-- 支持聚合查询的统计索引
CREATE INDEX IF NOT EXISTS idx_kline_stats ON kline_data(
    symbol, timeframe, open_time, volume
);

-- ================================
-- 3. Tick数据高频查询优化
-- ================================

-- Tick数据时间序列索引
CREATE INDEX IF NOT EXISTS idx_tick_timeseries ON tick_data(
    timestamp, exchange, symbol
);

-- 支持价格范围查询
CREATE INDEX IF NOT EXISTS idx_tick_price_analysis ON tick_data(
    symbol, price, timestamp
) WHERE price > 0;

-- 成交量分析索引
CREATE INDEX IF NOT EXISTS idx_tick_volume_analysis ON tick_data(
    symbol, quantity, side, timestamp
) WHERE quantity > 0;

-- 实时数据查询优化
CREATE INDEX IF NOT EXISTS idx_tick_realtime_lookup ON tick_data_realtime(
    exchange, symbol, timestamp DESC
);

-- ================================
-- 4. 聚合查询性能优化
-- ================================

-- 支持时间框架聚合的索引
CREATE INDEX IF NOT EXISTS idx_kline_aggregation ON kline_data(
    exchange, symbol, 
    CASE timeframe 
        WHEN '1m' THEN 1
        WHEN '5m' THEN 2  
        WHEN '15m' THEN 3
        WHEN '1h' THEN 4
        WHEN '4h' THEN 5
        WHEN '1d' THEN 6
    END,
    open_time
);

-- 支持统计分析的表达式索引
CREATE INDEX IF NOT EXISTS idx_kline_price_stats ON kline_data(
    symbol,
    (high_price - low_price) as price_range,
    volume,
    open_time
) WHERE high_price > low_price;

-- ================================
-- 5. 任务管理查询优化
-- ================================

-- 下载任务状态查询优化
CREATE INDEX IF NOT EXISTS idx_download_tasks_active ON data_download_tasks(
    status, progress, started_at
) WHERE status IN ('pending', 'running');

-- 质量监控历史查询
CREATE INDEX IF NOT EXISTS idx_quality_history ON data_quality_metrics(
    exchange, symbol, timeframe, last_updated DESC
);

-- ================================
-- 6. 缓存元信息快速查询
-- ================================

-- 数据覆盖范围快速查询
CREATE INDEX IF NOT EXISTS idx_cache_metadata_coverage ON data_cache_metadata(
    exchange, symbol, timeframe, first_timestamp, last_timestamp
);

-- 同步状态监控
CREATE INDEX IF NOT EXISTS idx_cache_sync_status ON data_cache_metadata(
    sync_status, last_sync_at DESC
) WHERE sync_status != 'active';

-- ================================
-- 7. 分析型查询视图
-- ================================

-- 数据完整性概览视图
CREATE VIEW IF NOT EXISTS v_data_completeness_overview AS
SELECT 
    exchange,
    symbol,
    timeframe,
    total_actual as record_count,
    missing_count,
    (total_actual * 100.0 / (total_actual + missing_count)) as completeness_percent,
    quality_score,
    last_updated
FROM data_quality_metrics
WHERE last_updated >= datetime('now', '-7 days');

-- 数据存储统计视图
CREATE VIEW IF NOT EXISTS v_storage_statistics AS
SELECT 
    exchange,
    symbol,
    timeframe,
    COUNT(*) as kline_count,
    MIN(open_time) as earliest_data,
    MAX(open_time) as latest_data,
    SUM(volume) as total_volume,
    AVG(close_price) as avg_price
FROM kline_data
GROUP BY exchange, symbol, timeframe;

-- 实时数据流监控视图  
CREATE VIEW IF NOT EXISTS v_realtime_data_status AS
SELECT 
    exchange,
    symbol,
    COUNT(*) as tick_count_last_hour,
    MAX(timestamp) as last_tick_time,
    AVG(price) as avg_price_last_hour,
    SUM(quantity) as total_volume_last_hour
FROM tick_data_realtime
WHERE timestamp >= strftime('%s', 'now', '-1 hour') * 1000
GROUP BY exchange, symbol;

-- ================================
-- 8. 查询性能分析
-- ================================

-- 查询性能统计表
CREATE TABLE IF NOT EXISTS query_performance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type VARCHAR(50) NOT NULL,        -- 查询类型
    table_name VARCHAR(50) NOT NULL,        -- 主要表名
    execution_time_ms INTEGER NOT NULL,     -- 执行时间(毫秒)
    rows_examined INTEGER,                  -- 扫描行数
    rows_returned INTEGER,                  -- 返回行数
    index_used VARCHAR(100),               -- 使用的索引
    query_hash VARCHAR(32),                -- 查询hash(用于聚合统计)
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 查询性能索引
CREATE INDEX IF NOT EXISTS idx_query_perf_type ON query_performance_log(
    query_type, execution_time_ms DESC, executed_at
);

-- ================================
-- 9. 自动维护任务
-- ================================

-- 定义自动维护任务配置
CREATE TABLE IF NOT EXISTS auto_maintenance_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name VARCHAR(50) UNIQUE NOT NULL,
    task_type VARCHAR(30) NOT NULL,        -- vacuum/reindex/analyze/cleanup
    target_tables TEXT,                    -- JSON数组格式的目标表
    schedule_cron VARCHAR(50),             -- Cron表达式
    enabled BOOLEAN DEFAULT TRUE,
    last_run DATETIME,
    next_run DATETIME,
    run_duration_seconds INTEGER,
    status VARCHAR(20) DEFAULT 'ready',    -- ready/running/completed/failed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 默认维护任务
INSERT OR REPLACE INTO auto_maintenance_tasks 
(task_name, task_type, target_tables, schedule_cron, enabled) VALUES
('daily_vacuum', 'vacuum', '["kline_data", "tick_data"]', '0 2 * * *', true),
('weekly_reindex', 'reindex', '["kline_data", "tick_data"]', '0 3 * * 0', true),
('hourly_analyze', 'analyze', '["kline_data"]', '0 * * * *', true),
('daily_cleanup_realtime', 'cleanup', '["tick_data_realtime"]', '0 1 * * *', true);

-- ================================
-- 10. 存储空间监控
-- ================================

-- 表空间使用统计
CREATE VIEW IF NOT EXISTS v_table_size_analysis AS
SELECT 
    name as table_name,
    CASE 
        WHEN name LIKE 'kline_data%' THEN 'kline'
        WHEN name LIKE 'tick_data%' THEN 'tick'
        WHEN name LIKE '%_log%' THEN 'log'
        ELSE 'other'
    END as data_category,
    -- SQLite表大小估算 (需要实际PRAGMA table_info配合)
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=main.name) as exists_flag
FROM sqlite_master 
WHERE type = 'table' 
  AND name NOT LIKE 'sqlite_%';

-- ================================
-- 11. 数据归档策略
-- ================================

-- 数据归档配置表
CREATE TABLE IF NOT EXISTS data_archive_policy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type VARCHAR(20) NOT NULL,         -- kline/tick
    timeframe VARCHAR(10),                  -- 针对特定时间框架
    retention_days INTEGER NOT NULL,       -- 保留天数
    archive_method VARCHAR(20) NOT NULL,   -- compress/delete/export
    archive_threshold_mb INTEGER,          -- 触发归档的大小阈值(MB)
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 默认归档策略
INSERT OR REPLACE INTO data_archive_policy 
(data_type, timeframe, retention_days, archive_method, archive_threshold_mb) VALUES
('tick', NULL, 30, 'compress', 1000),      -- Tick数据30天后压缩
('kline', '1m', 90, 'compress', 500),      -- 1分钟K线90天后压缩
('kline', '5m', 180, 'compress', 200),     -- 5分钟K线180天后压缩
('kline', '1h', 365, 'archive', 100),      -- 1小时K线1年后归档
('kline', '1d', 1825, 'keep', NULL);      -- 日K线保留5年

-- ================================
-- 12. 实时监控查询函数
-- ================================

-- 数据延迟监控(最新数据时间)
CREATE VIEW IF NOT EXISTS v_data_freshness AS
SELECT 
    exchange,
    symbol,
    timeframe,
    datetime(MAX(open_time)/1000, 'unixepoch') as latest_data_time,
    (strftime('%s', 'now') - MAX(open_time)/1000) as delay_seconds,
    CASE 
        WHEN (strftime('%s', 'now') - MAX(open_time)/1000) < 3600 THEN 'fresh'
        WHEN (strftime('%s', 'now') - MAX(open_time)/1000) < 86400 THEN 'delayed'
        ELSE 'stale'
    END as freshness_status
FROM kline_data
GROUP BY exchange, symbol, timeframe;

-- 数据量增长趋势
CREATE VIEW IF NOT EXISTS v_data_growth_trend AS
SELECT 
    date(created_at) as data_date,
    COUNT(*) as records_added,
    SUM(volume) as total_volume,
    COUNT(DISTINCT symbol) as unique_symbols
FROM kline_data
WHERE created_at >= datetime('now', '-30 days')
GROUP BY date(created_at)
ORDER BY data_date DESC;

-- ================================
-- 13. 备份和恢复优化
-- ================================

-- 增量备份标识
ALTER TABLE kline_data ADD COLUMN backup_flag INTEGER DEFAULT 0;
ALTER TABLE tick_data ADD COLUMN backup_flag INTEGER DEFAULT 0;

-- 备份任务记录
CREATE TABLE IF NOT EXISTS data_backup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_type VARCHAR(20) NOT NULL,      -- full/incremental
    tables_included TEXT,                  -- JSON数组
    backup_size_mb DECIMAL(10,2),
    backup_path TEXT,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    status VARCHAR(20) DEFAULT 'running',  -- running/completed/failed
    error_message TEXT
);

-- 备份性能索引
CREATE INDEX IF NOT EXISTS idx_backup_log_status ON data_backup_log(status, started_at DESC);

-- ================================
-- 14. 查询优化建议
-- ================================

/*
针对时序数据的查询优化建议：

1. 范围查询优化：
   - 始终在WHERE子句中包含时间范围条件
   - 使用BETWEEN替代>= AND <=
   - 优先使用时间戳索引

2. 聚合查询优化：
   - 使用预计算的统计表而非实时聚合
   - 分批次处理大数据量聚合
   - 利用窗口函数减少扫描次数

3. 分页查询优化：
   - 使用基于时间戳的分页而非OFFSET
   - 限制单次查询返回记录数
   - 使用流式查询处理大结果集

4. 连表查询优化：
   - 避免跨大表的JOIN操作
   - 使用子查询分解复杂JOIN
   - 预先过滤减少连接数据量

示例优化查询：
-- 优化前 (慢)
SELECT * FROM kline_data k 
JOIN strategies s ON k.symbol = s.symbol 
WHERE k.open_time > :start_time;

-- 优化后 (快)  
SELECT k.* FROM kline_data k 
WHERE k.symbol IN (SELECT symbol FROM strategies WHERE active=1)
  AND k.open_time BETWEEN :start_time AND :end_time
  AND k.exchange = :exchange
ORDER BY k.open_time ASC
LIMIT 1000;
*/

-- ================================
-- 15. 定期维护脚本生成
-- ================================

-- 自动统计更新
CREATE TRIGGER IF NOT EXISTS update_data_stats 
AFTER INSERT ON kline_data
BEGIN
    INSERT OR REPLACE INTO data_storage_stats 
    (table_name, exchange, symbol, timeframe, record_count, last_calculated)
    VALUES ('kline_data', NEW.exchange, NEW.symbol, NEW.timeframe, 
            (SELECT COUNT(*) FROM kline_data 
             WHERE exchange=NEW.exchange AND symbol=NEW.symbol AND timeframe=NEW.timeframe),
            datetime('now'));
END;

-- 压缩表大小监控触发器
CREATE TRIGGER IF NOT EXISTS monitor_table_growth
AFTER INSERT ON tick_data  
WHEN (SELECT COUNT(*) FROM tick_data) % 10000 = 0
BEGIN
    INSERT INTO data_performance_metrics 
    (operation_type, table_name, record_count, execution_time_ms, success)
    VALUES ('size_check', 'tick_data', 
            (SELECT COUNT(*) FROM tick_data), 0, 1);
END;

-- ================================
-- 16. 查询计划分析工具
-- ================================

-- 创建查询分析辅助表
CREATE TABLE IF NOT EXISTS query_analysis_helper (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_description VARCHAR(100),
    sql_query TEXT,
    explain_output TEXT,
    execution_plan TEXT,
    optimization_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 常用查询的执行计划预分析
INSERT OR REPLACE INTO query_analysis_helper 
(query_description, sql_query, optimization_notes) VALUES
('回测历史数据查询', 
 'SELECT * FROM kline_data WHERE exchange=? AND symbol=? AND timeframe=? AND open_time BETWEEN ? AND ? ORDER BY open_time',
 '使用idx_kline_backtest_optimized索引，支持快速范围查询'),
 
('最新价格查询',
 'SELECT close_price FROM kline_data WHERE exchange=? AND symbol=? ORDER BY open_time DESC LIMIT 1',
 '使用idx_kline_timeseries索引，DESC排序优化'),
 
('成交量异常检测',
 'SELECT * FROM kline_data WHERE symbol=? AND volume > (SELECT AVG(volume)*10 FROM kline_data WHERE symbol=?)',
 '使用子查询预计算阈值，避免全表扫描'),
 
('数据完整性检查',
 'SELECT COUNT(*) FROM kline_data WHERE exchange=? AND symbol=? AND timeframe=? AND open_time BETWEEN ? AND ?',
 '使用idx_kline_range_query覆盖索引，避免表访问');

-- ================================
-- 17. 性能基准测试
-- ================================

-- 基准测试配置
CREATE TABLE IF NOT EXISTS performance_benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name VARCHAR(50) NOT NULL,
    test_description TEXT,
    target_table VARCHAR(50),
    test_query TEXT,
    baseline_time_ms INTEGER,              -- 基线执行时间
    target_time_ms INTEGER,               -- 目标执行时间
    last_test_time_ms INTEGER,            -- 最近测试时间
    performance_ratio DECIMAL(5,2),       -- 性能比率 (实际/目标)
    last_tested DATETIME,
    status VARCHAR(20) DEFAULT 'pending'   -- pending/passed/failed
);

-- 默认基准测试用例
INSERT OR REPLACE INTO performance_benchmarks 
(test_name, test_description, target_table, test_query, target_time_ms) VALUES
('kline_range_query', 'K线范围查询性能', 'kline_data',
 'SELECT COUNT(*) FROM kline_data WHERE symbol="BTC/USDT" AND open_time BETWEEN ? AND ?', 100),
 
('tick_aggregation', 'Tick数据聚合性能', 'tick_data',
 'SELECT COUNT(*), AVG(price) FROM tick_data WHERE symbol="BTC/USDT" AND timestamp BETWEEN ? AND ?', 500),
 
('quality_check', '数据质量检查性能', 'data_quality_metrics',
 'SELECT * FROM data_quality_metrics WHERE symbol="BTC/USDT" ORDER BY last_updated DESC LIMIT 10', 50);

-- ================================
-- 18. 应急性能恢复
-- ================================

-- 性能问题检测视图
CREATE VIEW IF NOT EXISTS v_performance_issues AS
SELECT 
    'slow_query' as issue_type,
    query_type,
    table_name,
    AVG(execution_time_ms) as avg_time_ms,
    COUNT(*) as occurrence_count
FROM data_performance_metrics
WHERE execution_time_ms > 1000  -- 超过1秒的查询
  AND executed_at >= datetime('now', '-1 hour')
GROUP BY query_type, table_name
HAVING COUNT(*) > 5;

-- 存储空间告警
CREATE VIEW IF NOT EXISTS v_storage_alerts AS
SELECT 
    table_name,
    storage_size_mb,
    record_count,
    (storage_size_mb / record_count) as bytes_per_record,
    CASE 
        WHEN storage_size_mb > 1000 THEN 'critical'
        WHEN storage_size_mb > 500 THEN 'warning'
        ELSE 'normal'
    END as alert_level
FROM data_storage_stats
WHERE last_calculated >= datetime('now', '-1 day');

-- 性能优化完成标记
INSERT OR REPLACE INTO data_maintenance_config 
(config_key, config_value, description) VALUES
('performance_optimization_version', '1.0', '性能优化脚本版本'),
('optimization_applied_at', strftime('%s', 'now'), '优化应用时间戳'),
('index_count', (SELECT COUNT(*) FROM sqlite_master WHERE type='index'), '索引总数'),
('view_count', (SELECT COUNT(*) FROM sqlite_master WHERE type='view'), '视图总数');