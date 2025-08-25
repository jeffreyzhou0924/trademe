-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS trademe 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE trademe;

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    google_id VARCHAR(100) UNIQUE,
    avatar_url VARCHAR(255),
    phone VARCHAR(20),
    membership_level ENUM('BASIC', 'PREMIUM', 'PROFESSIONAL') DEFAULT 'BASIC',
    membership_expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP NULL,
    preferences JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_email (email),
    INDEX idx_username (username),
    INDEX idx_google_id (google_id),
    INDEX idx_membership_level (membership_level),
    INDEX idx_created_at (created_at)
);

-- 创建用户会话表
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_token (token),
    INDEX idx_refresh_token (refresh_token),
    INDEX idx_expires_at (expires_at)
);

-- 创建邮箱验证表
CREATE TABLE IF NOT EXISTS email_verifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    email VARCHAR(100) NOT NULL,
    code VARCHAR(6) NOT NULL,
    type ENUM('REGISTER', 'LOGIN', 'RESET_PASSWORD', 'CHANGE_EMAIL') DEFAULT 'REGISTER',
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_email_type (email, type),
    INDEX idx_code (code),
    INDEX idx_expires_at (expires_at)
);

-- 创建会员套餐表
CREATE TABLE IF NOT EXISTS membership_plans (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    level ENUM('BASIC', 'PREMIUM', 'PROFESSIONAL') NOT NULL,
    duration_months INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    original_price DECIMAL(10, 2),
    discount INT DEFAULT 0,
    features JSON NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    popular BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_level (level),
    INDEX idx_is_active (is_active)
);

-- 创建订单表
CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    plan_id INT NOT NULL,
    order_number VARCHAR(32) UNIQUE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    payment_method ENUM('USDT', 'BTC') NOT NULL,
    payment_address VARCHAR(100),
    payment_txid VARCHAR(100),
    status ENUM('PENDING', 'PAID', 'EXPIRED', 'CANCELLED') DEFAULT 'PENDING',
    expires_at TIMESTAMP NOT NULL,
    paid_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id),
    INDEX idx_user_id (user_id),
    INDEX idx_order_number (order_number),
    INDEX idx_status (status),
    INDEX idx_payment_method (payment_method),
    INDEX idx_created_at (created_at)
);

-- 创建系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_config_key (config_key)
);

-- 创建系统日志表
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    level ENUM('INFO', 'WARNING', 'ERROR') NOT NULL,
    action VARCHAR(100) NOT NULL,
    message TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_level (level),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
);

-- 插入默认会员套餐数据
INSERT IGNORE INTO membership_plans (name, level, duration_months, price, original_price, discount, features, is_active, popular) VALUES
('基础版', 'BASIC', 0, 0.00, NULL, 0, JSON_OBJECT(
    'api_keys_limit', 5,
    'ai_queries_daily', 2,
    'ai_strategy_optimization_daily', 0,
    'advanced_charts', false,
    'priority_support', false
), TRUE, FALSE),

('高级版(月付)', 'PREMIUM', 1, 19.99, 19.99, 0, JSON_OBJECT(
    'api_keys_limit', -1,
    'ai_queries_daily', 30,
    'ai_strategy_optimization_daily', 5,
    'advanced_charts', true,
    'priority_support', true
), TRUE, FALSE),

('高级版(季付)', 'PREMIUM', 3, 53.99, 59.97, 10, JSON_OBJECT(
    'api_keys_limit', -1,
    'ai_queries_daily', 30,
    'ai_strategy_optimization_daily', 5,
    'advanced_charts', true,
    'priority_support', true
), TRUE, TRUE),

('高级版(年付)', 'PREMIUM', 12, 191.90, 239.88, 20, JSON_OBJECT(
    'api_keys_limit', -1,
    'ai_queries_daily', 30,
    'ai_strategy_optimization_daily', 5,
    'advanced_charts', true,
    'priority_support', true
), TRUE, FALSE),

('专业版(月付)', 'PROFESSIONAL', 1, 49.99, 49.99, 0, JSON_OBJECT(
    'api_keys_limit', -1,
    'ai_queries_daily', 100,
    'ai_strategy_optimization_daily', 20,
    'advanced_charts', true,
    'priority_support', true,
    'custom_strategies', true,
    'api_trading', true
), TRUE, FALSE);

-- 插入系统配置数据
INSERT IGNORE INTO system_configs (config_key, config_value, description) VALUES
('app_name', 'Trademe', '应用名称'),
('app_version', '1.0.0', '应用版本'),
('maintenance_mode', 'false', '维护模式'),
('registration_enabled', 'true', '是否允许注册'),
('email_verification_required', 'true', '是否需要邮箱验证'),
('max_file_upload_size', '5242880', '最大文件上传大小（字节）'),
('supported_languages', '["zh-CN", "en-US"]', '支持的语言'),
('api_rate_limit_per_minute', '100', 'API每分钟限制次数');

-- 创建测试用户（可选，仅开发环境）
-- 密码: password123
INSERT IGNORE INTO users (username, email, password_hash, email_verified, preferences) VALUES
('admin', 'admin@trademe.com', '$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LQv3c1yqBWVHxkd0LO', TRUE, JSON_OBJECT(
    'language', 'zh-CN',
    'timezone', 'Asia/Shanghai',
    'theme', 'light'
)),
('testuser', 'test@trademe.com', '$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LQv3c1yqBWVHxkd0LO', TRUE, JSON_OBJECT(
    'language', 'zh-CN',
    'timezone', 'Asia/Shanghai',
    'theme', 'light'
));