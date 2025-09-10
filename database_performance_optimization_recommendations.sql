-- ================================================================================================
-- Trademe 数据库性能优化建议 SQL 脚本
-- 基于深度架构分析的专业优化方案
-- 生成时间: 2025-09-01
-- ================================================================================================

-- ========================================
-- 1. 索引优化建议
-- ========================================

-- 1.1 时序数据优化索引 (针对200万+tick数据)
-- 当前: idx_tick_data_symbol_time, idx_tick_data_time_range
-- 建议: 增加覆盖索引减少回表查询
CREATE INDEX IF NOT EXISTS idx_tick_data_covering 
ON tick_data(exchange, symbol, timestamp, price, volume);

-- 1.2 用户活动分析优化
-- 针对用户行为分析的高频查询
CREATE INDEX IF NOT EXISTS idx_user_activity_composite 
ON user_activity_logs(user_id, activity_type, created_at);

-- 1.3 AI使用统计优化  
-- 针对成本统计和使用分析
CREATE INDEX IF NOT EXISTS idx_claude_usage_cost_analysis
ON user_claude_usage(user_id, request_timestamp, api_cost_usd);

-- 1.4 支付订单状态查询优化
-- 针对支付状态实时查询
CREATE INDEX IF NOT EXISTS idx_payment_orders_status_time
ON usdt_payment_orders(status, created_at, user_id);

-- ========================================
-- 2. 查询优化建议
-- ========================================

-- 2.1 用户交易统计优化查询
-- 替代方案: 使用物化视图思想
CREATE VIEW IF NOT EXISTS user_trading_stats AS
SELECT 
    u.id as user_id,
    u.username,
    u.email,
    COUNT(t.id) as total_trades,
    COALESCE(SUM(t.total_amount), 0) as total_volume,
    COALESCE(AVG(t.total_amount), 0) as avg_trade_size,
    MAX(t.executed_at) as last_trade_time
FROM users u
LEFT JOIN trades t ON u.id = t.user_id
GROUP BY u.id, u.username, u.email;

-- 2.2 AI使用成本统计优化
CREATE VIEW IF NOT EXISTS user_ai_cost_summary AS
SELECT 
    u.id as user_id,
    u.username,
    COUNT(cu.id) as total_requests,
    SUM(cu.total_tokens) as total_tokens,
    SUM(cu.api_cost_usd) as total_cost_usd,
    AVG(cu.response_time_ms) as avg_response_time,
    DATE(cu.request_timestamp) as usage_date
FROM users u
LEFT JOIN user_claude_usage cu ON u.id = cu.user_id
GROUP BY u.id, u.username, DATE(cu.request_timestamp);

-- ========================================
-- 3. 分区策略建议 
-- ========================================

-- 3.1 Tick数据按时间分区策略
-- 注意: SQLite不支持原生分区，使用表分离策略

-- 创建当月tick数据表
CREATE TABLE IF NOT EXISTS tick_data_current AS 
SELECT * FROM tick_data WHERE 0; -- 创建相同结构的空表

-- 创建历史tick数据表  
CREATE TABLE IF NOT EXISTS tick_data_archive AS
SELECT * FROM tick_data WHERE 0;

-- 分区管理触发器示例
CREATE TRIGGER IF NOT EXISTS tick_data_partition_trigger
    BEFORE INSERT ON tick_data
BEGIN
    -- 可以在应用层实现分区逻辑
    INSERT INTO tick_data_current VALUES (NEW.id, NEW.exchange, NEW.symbol, 
        NEW.price, NEW.volume, NEW.side, NEW.trade_id, NEW.timestamp, 
        NEW.best_bid, NEW.best_ask, NEW.bid_size, NEW.ask_size, 
        NEW.is_validated, NEW.data_source, NEW.sequence_number, NEW.created_at);
END;

-- 3.2 用户数据分片建议
-- 基于用户ID进行水平分片
CREATE VIEW IF NOT EXISTS users_shard_0 AS
SELECT * FROM users WHERE id % 4 = 0;

CREATE VIEW IF NOT EXISTS users_shard_1 AS  
SELECT * FROM users WHERE id % 4 = 1;

CREATE VIEW IF NOT EXISTS users_shard_2 AS
SELECT * FROM users WHERE id % 4 = 2;

CREATE VIEW IF NOT EXISTS users_shard_3 AS
SELECT * FROM users WHERE id % 4 = 3;

-- ========================================
-- 4. 缓存优化建议
-- ========================================

-- 4.1 热点数据识别查询
-- 识别需要缓存的热点数据
CREATE VIEW IF NOT EXISTS cache_hot_symbols AS
SELECT 
    exchange,
    symbol,
    COUNT(*) as access_frequency,
    MAX(timestamp) as last_access,
    AVG(price) as avg_price
FROM tick_data 
WHERE created_at > datetime('now', '-1 day')
GROUP BY exchange, symbol
HAVING COUNT(*) > 100
ORDER BY access_frequency DESC;

-- 4.2 用户会话缓存策略
-- 识别活跃用户会话
CREATE VIEW IF NOT EXISTS active_user_sessions AS
SELECT 
    us.*,
    u.username,
    u.membership_level,
    CASE 
        WHEN us.expires_at > datetime('now', '+1 hour') THEN 'cache_long'
        WHEN us.expires_at > datetime('now', '+10 minutes') THEN 'cache_medium'  
        ELSE 'cache_short'
    END as cache_strategy
FROM user_sessions us
JOIN users u ON us.user_id = u.id
WHERE us.is_active = 1 AND us.expires_at > datetime('now');

-- ========================================
-- 5. 数据清理和维护建议
-- ========================================

-- 5.1 历史数据清理策略
-- 清理超过90天的系统日志
CREATE VIEW IF NOT EXISTS logs_to_cleanup AS
SELECT 
    'user_activity_logs' as table_name,
    COUNT(*) as records_count,
    MIN(created_at) as oldest_record,
    MAX(created_at) as newest_record
FROM user_activity_logs 
WHERE created_at < datetime('now', '-90 days')
UNION ALL
SELECT 
    'claude_usage_logs' as table_name,
    COUNT(*) as records_count, 
    MIN(created_at) as oldest_record,
    MAX(created_at) as newest_record
FROM claude_usage_logs
WHERE created_at < datetime('now', '-90 days');

-- 5.2 定期维护任务
-- VACUUM和ANALYZE操作建议
-- 注意: 这些操作应该在维护窗口期执行

-- 重建索引统计信息
-- ANALYZE;

-- 清理碎片空间  
-- VACUUM;

-- 增量VACUUM (生产环境推荐)
-- PRAGMA incremental_vacuum;

-- ========================================
-- 6. 监控和告警建议
-- ========================================

-- 6.1 慢查询监控视图
CREATE VIEW IF NOT EXISTS slow_queries_monitor AS
SELECT 
    'AI Usage Queries' as query_type,
    COUNT(*) as slow_query_count,
    AVG(response_time_ms) as avg_response_time
FROM user_claude_usage 
WHERE response_time_ms > 5000 -- 5秒以上查询
    AND request_timestamp > datetime('now', '-1 day')
UNION ALL
SELECT 
    'Data Access Queries' as query_type,
    COUNT(*) as slow_query_count,
    AVG(query_duration_ms) as avg_response_time  
FROM data_access_audit
WHERE query_duration_ms > 3000 -- 3秒以上查询
    AND created_at > datetime('now', '-1 day');

-- 6.2 存储空间监控
-- 注意: 需要定期执行以监控增长趋势
CREATE VIEW IF NOT EXISTS storage_usage_monitor AS
SELECT 
    'tick_data' as table_name,
    COUNT(*) as record_count,
    'High Growth' as growth_category,
    datetime('now') as check_time
FROM tick_data
UNION ALL
SELECT 
    'market_data' as table_name,
    COUNT(*) as record_count,
    'Medium Growth' as growth_category,
    datetime('now') as check_time
FROM market_data;

-- ========================================
-- 7. 性能基准测试查询
-- ========================================

-- 7.1 典型业务查询性能测试
-- 用户仪表板查询 (应该 < 100ms)
CREATE VIEW IF NOT EXISTS performance_test_user_dashboard AS
SELECT 
    u.id,
    u.username,
    u.membership_level,
    COUNT(DISTINCT s.id) as strategy_count,
    COUNT(DISTINCT t.id) as trade_count,
    COALESCE(SUM(t.total_amount), 0) as total_volume,
    MAX(t.executed_at) as last_trade
FROM users u
LEFT JOIN strategies s ON u.id = s.user_id AND s.is_active = 1
LEFT JOIN trades t ON u.id = t.user_id AND t.executed_at > datetime('now', '-30 days')
WHERE u.is_active = 1
GROUP BY u.id, u.username, u.membership_level;

-- 7.2 实时数据查询性能测试
-- 市场数据实时获取 (应该 < 50ms)  
CREATE VIEW IF NOT EXISTS performance_test_realtime_data AS
SELECT 
    md.symbol,
    md.close_price as current_price,
    md.volume as current_volume,
    md.timestamp as last_update,
    -- 计算价格变化
    LAG(md.close_price) OVER (PARTITION BY md.symbol ORDER BY md.timestamp) as prev_price,
    ROUND((md.close_price - LAG(md.close_price) OVER (PARTITION BY md.symbol ORDER BY md.timestamp)) / 
          LAG(md.close_price) OVER (PARTITION BY md.symbol ORDER BY md.timestamp) * 100, 2) as price_change_pct
FROM market_data md
WHERE md.exchange = 'OKX' 
    AND md.timeframe = '1m'
    AND md.timestamp > datetime('now', '-1 hour')
ORDER BY md.symbol, md.timestamp DESC;

-- ========================================
-- 8. 执行建议和注意事项
-- ========================================

/*
执行优先级建议:

1. 高优先级 (立即执行):
   - idx_tick_data_covering: 覆盖索引优化200万+记录查询
   - idx_payment_orders_status_time: 支付状态查询优化
   - user_trading_stats视图: 用户统计查询优化

2. 中优先级 (1周内执行):  
   - 缓存热点数据识别
   - 历史数据清理策略实施
   - 监控视图部署

3. 低优先级 (规划执行):
   - 数据分区策略 (需要应用层配合)
   - 分片架构设计 (需要架构调整)

注意事项:
- 所有索引创建建议在维护窗口期执行
- VACUUM操作会锁表，建议离线执行  
- 分区策略需要应用层代码配合
- 定期监控index usage和query performance
- 建议设置query timeout防止慢查询影响系统

性能预期:
- 索引优化后查询性能提升30-50%
- 缓存命中率达到85%+
- 用户仪表板加载时间 < 200ms
- API平均响应时间 < 100ms
*/

-- ================================================================================================
-- 脚本结束 - Trademe数据库性能优化建议
-- 建议定期review和更新优化策略
-- ================================================================================================