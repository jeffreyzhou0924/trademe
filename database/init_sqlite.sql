-- Trademe 数字货币交易平台 - SQLite数据库初始化脚本
-- 适用于50用户规模的单机部署架构

-- 开启外键约束
PRAGMA foreign_keys = ON;

-- 开启WAL模式以提高并发性能
PRAGMA journal_mode = WAL;

-- 设置同步模式为NORMAL以平衡性能和安全性
PRAGMA synchronous = NORMAL;

-- 设置缓存大小 (10000 pages ≈ 40MB)
PRAGMA cache_size = 10000;

-- 设置临时存储为内存
PRAGMA temp_store = memory;

-- ================================
-- 用户相关表 (从user-service迁移)
-- ================================

-- 用户基础信息表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    google_id VARCHAR(100),
    phone VARCHAR(20),
    avatar_url TEXT,
    membership_level VARCHAR(20) DEFAULT 'basic',
    membership_expires_at DATETIME,
    email_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 用户会话表
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 会员计划表
CREATE TABLE IF NOT EXISTS membership_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    level VARCHAR(20) NOT NULL,
    duration_months INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    features TEXT, -- JSON string: {"api_keys_limit": -1, "ai_queries_daily": 30}
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 支付订单表
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    order_number VARCHAR(100) UNIQUE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, COMPLETED, FAILED, CANCELLED
    payment_method VARCHAR(50),
    payment_details TEXT, -- JSON string
    paid_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id)
);

-- ================================
-- 交易相关表
-- ================================

-- API密钥管理表
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    api_key VARCHAR(255) NOT NULL,
    secret_key VARCHAR(255) NOT NULL, -- 加密存储
    passphrase VARCHAR(255), -- OKX等需要
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 交易策略表
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    code TEXT NOT NULL, -- 策略Python代码
    parameters TEXT, -- JSON string: {"timeframe": "1h", "ema_period": 20}
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE, -- 是否公开分享
    performance_score DECIMAL(5,2) DEFAULT 0, -- 性能评分 0-100
    total_runs INTEGER DEFAULT 0, -- 总运行次数
    success_rate DECIMAL(5,2) DEFAULT 0, -- 成功率
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 回测记录表
CREATE TABLE IF NOT EXISTS backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    name VARCHAR(100), -- 回测名称
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL,
    final_capital DECIMAL(15,2),
    total_return DECIMAL(8,4), -- 总收益率
    annualized_return DECIMAL(8,4), -- 年化收益率
    max_drawdown DECIMAL(8,4), -- 最大回撤
    sharpe_ratio DECIMAL(6,4), -- 夏普比率
    win_rate DECIMAL(5,2), -- 胜率
    total_trades INTEGER DEFAULT 0, -- 总交易次数
    results TEXT, -- JSON string: 详细回测结果
    status VARCHAR(20) DEFAULT 'RUNNING', -- RUNNING, COMPLETED, FAILED, STOPPED
    error_message TEXT, -- 错误信息
    duration_seconds INTEGER, -- 回测耗时（秒）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 交易记录表
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    strategy_id INTEGER, -- 可以为空（手动交易）
    backtest_id INTEGER, -- 回测交易记录
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL, -- BTC/USDT
    side VARCHAR(10) NOT NULL, -- BUY, SELL
    quantity DECIMAL(18,8) NOT NULL, -- 交易数量
    price DECIMAL(18,8) NOT NULL, -- 交易价格
    total_amount DECIMAL(18,8) NOT NULL, -- 总金额
    fee DECIMAL(18,8) NOT NULL DEFAULT 0, -- 手续费
    commission_rate DECIMAL(6,4) DEFAULT 0.001, -- 手续费率
    order_id VARCHAR(100), -- 交易所订单ID
    trade_type VARCHAR(20) NOT NULL, -- BACKTEST, LIVE, MANUAL
    signal_type VARCHAR(20), -- ENTRY, EXIT, STOP_LOSS, TAKE_PROFIT
    pnl DECIMAL(18,8), -- 盈亏金额
    pnl_percentage DECIMAL(8,4), -- 盈亏百分比
    executed_at DATETIME NOT NULL, -- 执行时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE SET NULL,
    FOREIGN KEY (backtest_id) REFERENCES backtests(id) ON DELETE CASCADE
);

-- ================================
-- 市场数据表 (替代InfluxDB)
-- ================================

-- K线数据表
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- 1m, 5m, 15m, 1h, 4h, 1d
    open_price DECIMAL(18,8) NOT NULL,
    high_price DECIMAL(18,8) NOT NULL,
    low_price DECIMAL(18,8) NOT NULL,
    close_price DECIMAL(18,8) NOT NULL,
    volume DECIMAL(18,8) NOT NULL,
    quote_volume DECIMAL(18,8), -- 计价货币成交量
    timestamp DATETIME NOT NULL, -- K线时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 实时价格表 (最新价格缓存)
CREATE TABLE IF NOT EXISTS latest_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    volume_24h DECIMAL(18,8),
    change_24h DECIMAL(8,4), -- 24小时涨跌幅
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, symbol)
);

-- ================================
-- AI和用户行为表
-- ================================

-- AI对话记录表
CREATE TABLE IF NOT EXISTS ai_chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL, -- USER, ASSISTANT, SYSTEM
    content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    model VARCHAR(50),
    context TEXT, -- JSON string
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 用户自选股表
CREATE TABLE IF NOT EXISTS user_watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, exchange, symbol)
);

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE, -- 是否对前端公开
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 系统日志表
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level VARCHAR(20) NOT NULL, -- INFO, WARNING, ERROR, CRITICAL
    source VARCHAR(50) NOT NULL, -- 日志来源服务
    message TEXT NOT NULL,
    details TEXT, -- JSON string
    user_id INTEGER, -- 相关用户ID
    ip_address VARCHAR(45), -- IPv4/IPv6地址
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ================================
-- 索引优化
-- ================================

-- 用户相关索引
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token_hash);

-- 交易相关索引
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_user_id ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_public ON strategies(is_public, is_active);
CREATE INDEX IF NOT EXISTS idx_backtests_user_id ON backtests(user_id);
CREATE INDEX IF NOT EXISTS idx_backtests_strategy_id ON backtests(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtests_status ON backtests(status);
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);

-- 市场数据索引（核心性能优化）
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(exchange, symbol, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_latest_prices_symbol ON latest_prices(exchange, symbol);

-- AI和行为数据索引
CREATE INDEX IF NOT EXISTS idx_chat_history_user_session ON ai_chat_history(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON ai_chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON user_watchlist(user_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level, created_at);
CREATE INDEX IF NOT EXISTS idx_system_logs_source ON system_logs(source, created_at);

-- ================================
-- 初始化数据
-- ================================

-- 插入默认会员计划
INSERT OR IGNORE INTO membership_plans (id, name, level, duration_months, price, features) VALUES
(1, '基础版', 'basic', 0, 0.00, '{"api_keys_limit": 5, "ai_queries_daily": 2, "ai_strategy_optimization_daily": 0, "advanced_charts": false, "priority_support": false}'),
(2, '高级版(月付)', 'premium', 1, 19.99, '{"api_keys_limit": -1, "ai_queries_daily": 30, "ai_strategy_optimization_daily": 5, "advanced_charts": true, "priority_support": true}'),
(3, '高级版(季付)', 'premium', 3, 53.99, '{"api_keys_limit": -1, "ai_queries_daily": 30, "ai_strategy_optimization_daily": 5, "advanced_charts": true, "priority_support": true}'),
(4, '高级版(年付)', 'premium', 12, 199.99, '{"api_keys_limit": -1, "ai_queries_daily": 50, "ai_strategy_optimization_daily": 10, "advanced_charts": true, "priority_support": true}');

-- 插入系统配置
INSERT OR IGNORE INTO system_configs (key, value, description, is_public) VALUES
('app_name', 'Trademe', '应用名称', true),
('app_version', '1.0.0', '应用版本', true),
('maintenance_mode', 'false', '维护模式', true),
('max_file_upload_size', '10485760', '文件上传最大尺寸(字节)', false),
('default_timeframe', '1h', '默认时间周期', true),
('supported_exchanges', '["binance", "okx", "bybit"]', '支持的交易所', true),
('rate_limit_per_minute', '1000', '每分钟API调用限制', false);

-- ================================
-- 触发器 (自动更新时间戳)
-- ================================

-- 用户表更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_users_timestamp 
    AFTER UPDATE ON users 
    FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 策略表更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_strategies_timestamp 
    AFTER UPDATE ON strategies 
    FOR EACH ROW
BEGIN
    UPDATE strategies SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 系统配置更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_system_configs_timestamp 
    AFTER UPDATE ON system_configs 
    FOR EACH ROW
BEGIN
    UPDATE system_configs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ================================
-- 视图 (常用查询优化)
-- ================================

-- 用户策略统计视图
CREATE VIEW IF NOT EXISTS user_strategy_stats AS
SELECT 
    u.id as user_id,
    u.username,
    u.membership_level,
    COUNT(s.id) as total_strategies,
    COUNT(CASE WHEN s.is_active = 1 THEN 1 END) as active_strategies,
    COUNT(b.id) as total_backtests,
    AVG(s.performance_score) as avg_performance_score
FROM users u
LEFT JOIN strategies s ON u.id = s.user_id
LEFT JOIN backtests b ON s.id = b.strategy_id
GROUP BY u.id, u.username, u.membership_level;

-- 策略性能统计视图
CREATE VIEW IF NOT EXISTS strategy_performance_stats AS
SELECT 
    s.id as strategy_id,
    s.name as strategy_name,
    s.user_id,
    COUNT(b.id) as backtest_count,
    AVG(b.total_return) as avg_return,
    MAX(b.total_return) as best_return,
    AVG(b.sharpe_ratio) as avg_sharpe_ratio,
    AVG(b.max_drawdown) as avg_max_drawdown,
    COUNT(t.id) as total_trades
FROM strategies s
LEFT JOIN backtests b ON s.id = b.strategy_id AND b.status = 'COMPLETED'
LEFT JOIN trades t ON s.id = t.strategy_id
GROUP BY s.id, s.name, s.user_id;

-- ================================
-- 数据库元信息
-- ================================

-- 记录数据库版本
INSERT OR REPLACE INTO system_configs (key, value, description, is_public) VALUES
('database_version', '1.0.0', '数据库Schema版本', false),
('database_initialized_at', datetime('now'), '数据库初始化时间', false);

-- 记录表统计信息
INSERT OR REPLACE INTO system_configs (key, value, description, is_public) VALUES
('total_tables', '15', '数据库表总数', false),
('total_indexes', '20', '数据库索引总数', false),
('estimated_max_users', '50', '估计最大用户数', false);

-- 启用统计信息收集
ANALYZE;

-- 输出初始化完成信息
SELECT 'SQLite数据库初始化完成' as status,
       datetime('now') as initialized_at,
       '支持50用户规模' as capacity,
       'WAL模式已启用' as performance_mode;