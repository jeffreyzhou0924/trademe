"""
Trademe Trading Service - 配置管理

统一管理应用配置，支持环境变量和默认值
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    app_name: str = Field(default="Trademe Trading Service", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8001, alias="PORT")
    
    # 数据库配置 (SQLite统一数据库)
    database_url: str = Field(
        default="sqlite+aiosqlite:////root/trademe/data/trademe.db",
        alias="DATABASE_URL"
    )
    
    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    
    # JWT配置 (与用户服务一致，支持多种环境变量名)
    jwt_secret_key: str = Field(
        default="Mt#HHq9rTDDWn38pEFxPtS6PiF{Noz[s=[IHMNZGRq@j*W1JWA*RPgufyrrZWhXH",
        alias="JWT_SECRET_KEY"
    )
    jwt_secret: str = Field(
        default="Mt#HHq9rTDDWn38pEFxPtS6PiF{Noz[s=[IHMNZGRq@j*W1JWA*RPgufyrrZWhXH", 
        alias="JWT_SECRET"
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")
    jwt_expires_in: str = Field(default="24h", alias="JWT_EXPIRES_IN")
    
    # CORS配置
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        alias="CORS_ORIGINS"
    )
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        alias="ALLOWED_HOSTS"
    )
    
    # OpenAI配置 (备用)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=2000, alias="OPENAI_MAX_TOKENS")
    
    # Claude配置 (主要AI服务)
    claude_api_key: str = Field(default="", alias="CLAUDE_API_KEY")
    claude_auth_token: str = Field(default="", alias="ANTHROPIC_AUTH_TOKEN")  # 支持ANTHROPIC_AUTH_TOKEN
    claude_base_url: str = Field(default="", alias="CLAUDE_BASE_URL")
    anthropic_base_url: str = Field(default="", alias="ANTHROPIC_BASE_URL")  # 支持ANTHROPIC_BASE_URL
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")  # 升级到Claude 4 Sonnet！
    claude_max_tokens: int = Field(default=4096, alias="CLAUDE_MAX_TOKENS")
    claude_timeout: int = Field(default=180, alias="CLAUDE_TIMEOUT")  # 180秒超时，适应第三方代理延迟
    
    # 交易所配置
    ccxt_timeout: int = Field(default=30000, alias="CCXT_TIMEOUT")  # 30秒
    max_concurrent_requests: int = Field(default=10, alias="MAX_CONCURRENT_REQUESTS")
    
    # 🆕 OKX API配置
    okx_api_key: str = Field(default="76ba9b3a-38b6-4ed3-9ce7-44d603188b13", alias="OKX_API_KEY")
    okx_secret_key: str = Field(default="4021858325F5A3BEC3F64B6D0533E412", alias="OKX_SECRET_KEY")
    okx_passphrase: str = Field(default="Woaiziji..123", alias="OKX_PASSPHRASE")
    okx_sandbox: bool = Field(default=False, alias="OKX_SANDBOX")  # 是否使用沙盒环境
    
    # WebSocket配置
    websocket_max_connections: int = Field(default=100, alias="WS_MAX_CONNECTIONS")
    websocket_ping_interval: int = Field(default=30, alias="WS_PING_INTERVAL")
    
    # 数据缓存配置
    market_data_cache_ttl: int = Field(default=30, alias="MARKET_DATA_CACHE_TTL")  # 秒
    kline_data_cache_ttl: int = Field(default=3600, alias="KLINE_DATA_CACHE_TTL")  # 1小时
    
    # 安全配置
    api_rate_limit: int = Field(default=1000, alias="API_RATE_LIMIT")  # 每分钟请求数
    max_upload_size: int = Field(default=10485760, alias="MAX_UPLOAD_SIZE")  # 10MB
    
    # 日志配置
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/trading-service.log", alias="LOG_FILE")
    
    # 数据目录配置
    data_dir: str = Field(default="./data", alias="DATA_DIR")
    logs_dir: str = Field(default="./logs", alias="LOGS_DIR")
    
    # 回测配置
    backtest_max_duration_days: int = Field(default=365, alias="BACKTEST_MAX_DURATION_DAYS")
    backtest_default_commission: float = Field(default=0.001, alias="BACKTEST_DEFAULT_COMMISSION")
    
    # 风控配置
    max_position_size: float = Field(default=0.1, alias="MAX_POSITION_SIZE")  # 最大10%仓位
    max_daily_loss: float = Field(default=0.05, alias="MAX_DAILY_LOSS")  # 最大5%日亏损
    
    # 加密配置
    wallet_master_key: str = Field(default="", alias="WALLET_MASTER_KEY")
    
    # 区块链监控配置
    # TRON网络配置
    tron_api_url: str = Field(default="https://api.trongrid.io", alias="TRON_API_URL")
    tron_api_key: str = Field(default="", alias="TRON_API_KEY")
    tron_usdt_contract: str = Field(default="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", alias="TRON_USDT_CONTRACT")
    
    # Ethereum网络配置  
    ethereum_rpc_url: str = Field(default="https://eth-mainnet.g.alchemy.com/v2", alias="ETHEREUM_RPC_URL")
    ethereum_api_key: str = Field(default="", alias="ETHEREUM_API_KEY")
    ethereum_usdt_contract: str = Field(default="0xdAC17F958D2ee523a2206206994597C13D831ec7", alias="ETHEREUM_USDT_CONTRACT")
    etherscan_api_key: str = Field(default="", alias="ETHERSCAN_API_KEY")
    
    # BSC网络配置
    bsc_rpc_url: str = Field(default="https://bsc-dataseed1.binance.org", alias="BSC_RPC_URL")
    bsc_api_key: str = Field(default="", alias="BSC_API_KEY")
    bscscan_api_key: str = Field(default="", alias="BSCSCAN_API_KEY")
    
    # 监控配置
    blockchain_monitor_interval: int = Field(default=15, alias="BLOCKCHAIN_MONITOR_INTERVAL")  # 监控间隔(秒)
    blockchain_confirmation_blocks: int = Field(default=12, alias="BLOCKCHAIN_CONFIRMATION_BLOCKS")  # 确认块数
    payment_timeout_minutes: int = Field(default=30, alias="PAYMENT_TIMEOUT_MINUTES")  # 支付超时时间(分钟)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)


# 创建全局配置实例
settings = Settings()

# 配置验证
def validate_settings():
    """验证关键配置"""
    errors = []
    
    # 检查JWT密钥 (支持多种字段名)
    jwt_key = settings.jwt_secret_key or settings.jwt_secret
    unsafe_keys = [
        "your-secret-key-here",
        "your_super_secret_jwt_key_here",
        "trademe_super_secret_jwt_key_for_development_only_32_chars",
        "TrademeSecure2024!@#$%^&*()_+{}|:<>?[];',./`~abcdefghijklmnop",
        "Mt#HHq9rTDDWn38pEFxPtS6PiF{Noz[s=[IHMNZGRq@j*W1JWA*RPgufyrrZWhXH"
    ]
    if not jwt_key or jwt_key in unsafe_keys:
        errors.append("JWT密钥 (JWT_SECRET_KEY或JWT_SECRET) 必须设置且不能为默认值")
    elif len(jwt_key) < 32:
        errors.append("JWT密钥长度必须至少32字符以确保安全性")
    elif settings.environment == "production" and len(jwt_key) < 64:
        errors.append("生产环境JWT密钥长度必须至少64字符")
    
    # 检查JWT密钥复杂度（生产环境）
    if settings.environment == "production":
        has_upper = any(c.isupper() for c in jwt_key)
        has_lower = any(c.islower() for c in jwt_key)
        has_digit = any(c.isdigit() for c in jwt_key)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in jwt_key)
        
        if not (has_upper and has_lower and has_digit and has_special):
            errors.append("生产环境JWT密钥必须包含大小写字母、数字和特殊字符")
    
    if settings.environment == "production":
        if settings.debug:
            errors.append("生产环境不应启用DEBUG模式")
        if not settings.claude_api_key:
            errors.append("生产环境必须设置CLAUDE_API_KEY")
    
    if errors:
        raise ValueError(f"配置验证失败: {'; '.join(errors)}")
    
    return True

# 在导入时验证配置
if settings.environment == "production":
    validate_settings()