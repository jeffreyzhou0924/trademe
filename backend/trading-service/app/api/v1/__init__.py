"""
Trademe Trading Service - API v1

版本1的API接口
"""

from fastapi import APIRouter
from .strategies import router as strategies_router
# 策略模板功能已恢复 - 前端功能完整，需要后端支持
from .strategy_templates import router as strategy_templates_router
from .backtests import router as backtests_router
from .trades import router as trades_router
from .market import router as market_router
from .ai import router as ai_router
from .exchanges import router as exchanges_router
from .api_keys import router as api_keys_router
from .tiered_backtests import router as tiered_backtests_router
# 移除图表交易和交易心得模块 - 不作为生产环境1.0功能
# from .trading import router as trading_router
# from .enhanced_trading import router as enhanced_trading_router
# from .trading_notes import router as trading_notes_router
from .membership import router as membership_router
from .admin.claude import router as admin_claude_router
from .admin.users import router as admin_users_router
from .admin_simple import router as admin_simple_router
# 钱包管理功能已验证，重新启用
from .admin.usdt_wallets import router as admin_usdt_wallets_router
# 区块链监控功能 - 暂时禁用(缺少依赖)
# from .blockchain_monitor import router as blockchain_monitor_router
# 支付订单管理API - 暂时禁用(依赖复杂服务)
# from .payment_orders import router as payment_orders_router
# 管理员支付API暂时禁用 - 依赖复杂
# from .admin.payment_orders import router as admin_payment_orders_router
# from .admin.payment_automation import router as admin_payment_automation_router
# 资金归集API
from .fund_consolidation import router as fund_consolidation_router
# 数据管理API
from .data_management import router as data_management_router
from .user_claude_keys import router as user_claude_keys_router
from .market_data import router as market_data_router
from .okx_api_keys import router as okx_api_keys_router
# 用户钱包管理API
from .user_wallets import router as user_wallets_router
# Claude API兼容端点 - 用于直接访问Claude服务
from .claude_compatible import router as claude_compatible_router
# AI WebSocket实时对话端点
from .ai_websocket import router as ai_websocket_router
# Anthropic官方API账户管理
from .anthropic_accounts import router as anthropic_accounts_router
# 实时回测API - AI对话中的即时回测功能
from .realtime_backtest import router as realtime_backtest_router
# 数据完整性检查API - 回测前的数据验证
from .data_integrity_check import router as data_integrity_check_router

# 创建API路由器
api_router = APIRouter()

# 注册子路由
api_router.include_router(strategies_router, prefix="/strategies", tags=["策略管理"])
# 策略模板功能已恢复 - 前端功能完整，需要后端支持
api_router.include_router(strategy_templates_router, prefix="/strategy-templates", tags=["策略模板"])
api_router.include_router(backtests_router, prefix="/backtests", tags=["回测分析"])
api_router.include_router(tiered_backtests_router, prefix="/tiered-backtests", tags=["分层回测"])
api_router.include_router(trades_router, prefix="/trades", tags=["交易管理"])
api_router.include_router(market_router, prefix="/market", tags=["市场数据"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI功能"])
api_router.include_router(exchanges_router, prefix="/exchanges", tags=["交易所管理"])
api_router.include_router(api_keys_router, prefix="/api-keys", tags=["API密钥管理"])
# 移除图表交易和交易心得模块的路由注册 - 不作为生产环境1.0功能
# api_router.include_router(trading_router, prefix="/trading", tags=["实盘交易"])
# api_router.include_router(trading_notes_router, tags=["交易心得"])  # prefix已在router定义中设置
# api_router.include_router(enhanced_trading_router, tags=["增强版实盘交易"])  # 注意：prefix已在router定义中设置
api_router.include_router(membership_router, tags=["会员管理"])  # prefix已在router定义中设置
api_router.include_router(admin_claude_router, tags=["Claude AI管理"])  # prefix已在router定义中设置
api_router.include_router(admin_users_router, tags=["高级用户管理"])  # 企业级高级用户管理系统 - /admin/users
api_router.include_router(admin_simple_router, tags=["简单管理员API"])  # 重新启用简单管理系统用于前端集成
# 钱包管理路由已验证，重新启用
api_router.include_router(admin_usdt_wallets_router, tags=["USDT钱包管理"])  # prefix已在router定义中设置
# 资金归集路由
api_router.include_router(fund_consolidation_router, tags=["资金归集"])  # prefix已在router定义中设置
# 数据管理路由
api_router.include_router(data_management_router, tags=["数据管理"])  # prefix已在router定义中设置
# 用户Claude Key管理路由  
api_router.include_router(user_claude_keys_router, prefix="/user-claude-keys", tags=["用户Claude密钥管理"])
# 用户钱包管理路由
api_router.include_router(user_wallets_router, prefix="/user-wallets", tags=["用户钱包管理"])
# 区块链监控路由 - 暂时禁用(缺少依赖)
# api_router.include_router(blockchain_monitor_router, tags=["区块链监控"])  # prefix已在router定义中设置
# 支付订单管理路由 - 暂时禁用(依赖复杂服务)
# api_router.include_router(payment_orders_router, tags=["支付订单管理"])  # prefix已在router定义中设置
# 管理员支付路由暂时禁用 - 依赖复杂
# api_router.include_router(admin_payment_orders_router, tags=["管理员支付订单"])  # prefix已在router定义中设置  
# api_router.include_router(admin_payment_automation_router, tags=["支付自动化管理"])  # prefix已在router定义中设置

# Claude API兼容端点已在main.py根级别注册，此处不再重复注册

# AI WebSocket实时对话路由 - 解决HTTP超时问题的实时通信方案
api_router.include_router(ai_websocket_router, tags=["AI WebSocket"])  # prefix已在router定义中设置

# 市场数据路由 - OKX真实数据获取
api_router.include_router(market_data_router, prefix="/market-data", tags=["市场数据"])

# OKX API密钥管理路由
api_router.include_router(okx_api_keys_router, prefix="/okx-api-keys", tags=["OKX API管理"])

# Anthropic官方API账户管理路由
api_router.include_router(anthropic_accounts_router, tags=["Anthropic官方API"])  # prefix已在router定义中设置

# 实时回测路由 - AI对话中的即时回测功能
api_router.include_router(realtime_backtest_router, tags=["实时回测"])  # prefix已在router定义中设置

# 数据完整性检查路由 - 回测前的数据验证
api_router.include_router(data_integrity_check_router, tags=["数据完整性"])  # prefix已在router定义中设置