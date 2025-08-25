-- ======================================
-- USDT结算历史数据表结构设计
-- ======================================

-- 现货日K线数据表 (策略回测用)
CREATE TABLE IF NOT EXISTS spot_daily_klines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(20) NOT NULL,              -- BTC-USDT, ETH-USDT
    trade_date DATE NOT NULL,                 -- 交易日期 YYYY-MM-DD
    open_price DECIMAL(18,8) NOT NULL,        -- 开盘价
    high_price DECIMAL(18,8) NOT NULL,        -- 最高价
    low_price DECIMAL(18,8) NOT NULL,         -- 最低价
    close_price DECIMAL(18,8) NOT NULL,       -- 收盘价
    volume DECIMAL(18,8) NOT NULL,            -- 成交量(基础货币)
    quote_volume DECIMAL(18,8) NOT NULL,      -- 成交金额(USDT)
    trade_count INTEGER DEFAULT 0,            -- 成交笔数
    data_source VARCHAR(10) DEFAULT 'okx',    -- 数据源
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, trade_date, data_source)
);

-- 现货日交易聚合数据表 (TICK回测用)  
CREATE TABLE IF NOT EXISTS spot_daily_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    total_trades INTEGER NOT NULL,            -- 总交易笔数
    total_buy_volume DECIMAL(18,8),           -- 总买入量(基础货币)
    total_sell_volume DECIMAL(18,8),          -- 总卖出量(基础货币)
    total_buy_amount DECIMAL(18,8),           -- 总买入金额(USDT)
    total_sell_amount DECIMAL(18,8),          -- 总卖出金额(USDT)
    avg_trade_size DECIMAL(18,8),             -- 平均交易大小
    median_trade_size DECIMAL(18,8),          -- 中位数交易大小
    large_trades_count INTEGER DEFAULT 0,     -- 大单交易数量(>均值2倍)
    price_volatility DECIMAL(8,6),            -- 价格波动率
    tick_data BLOB,                           -- 压缩的tick数据
    volume_profile BLOB,                      -- 价格区间成交量分布
    data_source VARCHAR(10) DEFAULT 'okx',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, trade_date, data_source)
);

-- 合约日K线数据表 (合约策略回测用)
CREATE TABLE IF NOT EXISTS futures_daily_klines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,              -- BTC-USDT-SWAP, ETH-USDT-SWAP
    trade_date DATE NOT NULL,
    open_price DECIMAL(18,8) NOT NULL,
    high_price DECIMAL(18,8) NOT NULL,
    low_price DECIMAL(18,8) NOT NULL,
    close_price DECIMAL(18,8) NOT NULL,
    volume DECIMAL(18,8) NOT NULL,            -- 成交量(张数)
    quote_volume DECIMAL(18,8) NOT NULL,      -- 成交金额(USDT)
    open_interest DECIMAL(18,8),              -- 持仓量
    funding_rate DECIMAL(12,8),               -- 资金费率
    funding_rate_8h DECIMAL(12,8),            -- 8小时资金费率
    index_price DECIMAL(18,8),                -- 指数价格
    mark_price DECIMAL(18,8),                 -- 标记价格
    trade_count INTEGER DEFAULT 0,
    data_source VARCHAR(10) DEFAULT 'okx',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, trade_date, data_source)
);

-- 合约日交易聚合数据表 (合约TICK回测用)
CREATE TABLE IF NOT EXISTS futures_daily_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    trade_date DATE NOT NULL,
    total_trades INTEGER NOT NULL,
    total_long_volume DECIMAL(18,8),          -- 总多仓成交量
    total_short_volume DECIMAL(18,8),         -- 总空仓成交量
    total_long_amount DECIMAL(18,8),          -- 总多仓成交金额(USDT)
    total_short_amount DECIMAL(18,8),         -- 总空仓成交金额(USDT)
    avg_trade_size DECIMAL(18,8),
    median_trade_size DECIMAL(18,8),
    large_trades_count INTEGER DEFAULT 0,
    liquidation_trades INTEGER DEFAULT 0,     -- 强平交易数量
    price_volatility DECIMAL(8,6),
    funding_pnl DECIMAL(18,8),                -- 资金费用盈亏
    tick_data BLOB,                           -- 压缩的tick数据
    volume_profile BLOB,
    oi_changes BLOB,                          -- 持仓量变化数据
    data_source VARCHAR(10) DEFAULT 'okx',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, trade_date, data_source)
);

-- ======================================
-- 索引优化 (提升查询性能)
-- ======================================

-- 现货K线查询索引
CREATE INDEX IF NOT EXISTS idx_spot_klines_symbol_date ON spot_daily_klines(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_spot_klines_date_range ON spot_daily_klines(trade_date DESC, symbol);
CREATE INDEX IF NOT EXISTS idx_spot_klines_symbol_source ON spot_daily_klines(symbol, data_source, trade_date);

-- 现货交易查询索引  
CREATE INDEX IF NOT EXISTS idx_spot_trades_symbol_date ON spot_daily_trades(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_spot_trades_date_range ON spot_daily_trades(trade_date DESC, symbol);

-- 合约K线查询索引
CREATE INDEX IF NOT EXISTS idx_futures_klines_symbol_date ON futures_daily_klines(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_futures_klines_date_range ON futures_daily_klines(trade_date DESC, symbol);
CREATE INDEX IF NOT EXISTS idx_futures_klines_symbol_source ON futures_daily_klines(symbol, data_source, trade_date);

-- 合约交易查询索引
CREATE INDEX IF NOT EXISTS idx_futures_trades_symbol_date ON futures_daily_trades(symbol, trade_date);  
CREATE INDEX IF NOT EXISTS idx_futures_trades_date_range ON futures_daily_trades(trade_date DESC, symbol);

-- ======================================
-- 支持表 (辅助功能)
-- ======================================

-- USDT交易对管理表
CREATE TABLE IF NOT EXISTS usdt_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL UNIQUE,
    market_type VARCHAR(10) NOT NULL,         -- 'spot' 或 'futures'
    base_currency VARCHAR(10) NOT NULL,       -- BTC, ETH, etc.
    quote_currency VARCHAR(10) DEFAULT 'USDT',
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,               -- 优先级: 0=高, 1=中, 2=低
    min_volume_24h DECIMAL(18,8),            -- 24小时最小成交量过滤
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 数据拉取状态表
CREATE TABLE IF NOT EXISTS data_fetch_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    market_type VARCHAR(10) NOT NULL,         -- 'spot' 或 'futures'  
    data_type VARCHAR(10) NOT NULL,           -- 'klines' 或 'trades'
    fetch_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',     -- 'pending', 'fetching', 'completed', 'failed'
    records_count INTEGER DEFAULT 0,
    error_message TEXT,
    fetch_started_at DATETIME,
    fetch_completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(symbol, market_type, data_type, fetch_date)
);

-- 数据质量检查表
CREATE TABLE IF NOT EXISTS data_quality_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    market_type VARCHAR(10) NOT NULL,
    data_type VARCHAR(10) NOT NULL, 
    check_date DATE NOT NULL,
    check_type VARCHAR(20) NOT NULL,          -- 'completeness', 'accuracy', 'consistency'
    check_result VARCHAR(10) NOT NULL,        -- 'pass', 'fail', 'warning'
    check_details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_quality_checks_symbol_date (symbol, check_date)
);