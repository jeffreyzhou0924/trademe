"""
Trademe Trading Service - API v1

版本1的API接口
"""

from fastapi import APIRouter
from .strategies import router as strategies_router
# 策略模板功能暂时隐藏 - 项目初期未考虑此功能
# from .strategy_templates import router as strategy_templates_router
from .backtests import router as backtests_router
from .trades import router as trades_router
from .trading import router as trading_router
from .market import router as market_router
from .ai import router as ai_router
from .exchanges import router as exchanges_router
from .api_keys import router as api_keys_router
from .tiered_backtests import router as tiered_backtests_router
from .enhanced_trading import router as enhanced_trading_router
from .trading_notes import router as trading_notes_router
from .membership import router as membership_router
from .admin.claude import router as admin_claude_router
from .admin.users import router as admin_users_router
from .admin_simple import router as admin_simple_router
# 钱包管理功能已验证，重新启用
from .admin.usdt_wallets import router as admin_usdt_wallets_router
# 区块链监控功能
from .blockchain_monitor import router as blockchain_monitor_router
# 支付订单管理API
from .payments import router as payments_router
# from .admin.blockchain import router as admin_blockchain_router
# from .admin.payment_automation import router as admin_payment_automation_router

# 创建API路由器
api_router = APIRouter()

# 注册子路由
api_router.include_router(strategies_router, prefix="/strategies", tags=["策略管理"])
# 策略模板功能暂时隐藏 - 项目初期未考虑此功能
# api_router.include_router(strategy_templates_router, prefix="/strategy-templates", tags=["策略模板"])
api_router.include_router(backtests_router, prefix="/backtests", tags=["回测分析"])
api_router.include_router(tiered_backtests_router, prefix="/tiered-backtests", tags=["分层回测"])
api_router.include_router(trades_router, prefix="/trades", tags=["交易管理"])
api_router.include_router(trading_router, prefix="/trading", tags=["实盘交易"])
api_router.include_router(market_router, prefix="/market", tags=["市场数据"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI功能"])
api_router.include_router(exchanges_router, prefix="/exchanges", tags=["交易所管理"])
api_router.include_router(api_keys_router, prefix="/api-keys", tags=["API密钥管理"])
api_router.include_router(trading_notes_router, tags=["交易心得"])  # prefix已在router定义中设置
api_router.include_router(membership_router, tags=["会员管理"])  # prefix已在router定义中设置
api_router.include_router(enhanced_trading_router, tags=["增强版实盘交易"])  # 注意：prefix已在router定义中设置
api_router.include_router(admin_claude_router, tags=["Claude AI管理"])  # prefix已在router定义中设置
api_router.include_router(admin_users_router, tags=["用户管理"])  # prefix已在router定义中设置
api_router.include_router(admin_simple_router, tags=["简单管理员API"])  # prefix已在router定义中设置
# 钱包管理路由已验证，重新启用
api_router.include_router(admin_usdt_wallets_router, tags=["USDT钱包管理"])  # prefix已在router定义中设置
# 区块链监控路由
api_router.include_router(blockchain_monitor_router, tags=["区块链监控"])  # prefix已在router定义中设置
# 支付订单管理路由
api_router.include_router(payments_router, tags=["支付管理"])  # prefix已在router定义中设置  
# api_router.include_router(admin_blockchain_router, tags=["区块链监控管理"])  # prefix已在router定义中设置
# api_router.include_router(admin_payment_automation_router, tags=["支付自动化管理"])  # prefix已在router定义中设置