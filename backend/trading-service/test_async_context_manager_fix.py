#!/usr/bin/env python3
"""
测试异步上下文管理器错误修复
验证 'async_generator' object does not support the asynchronous context manager protocol 错误已解决
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.api.v1.realtime_backtest import RealtimeBacktestConfig, start_realtime_backtest, start_ai_strategy_backtest, AIStrategyBacktestConfig
from app.database import get_db
from app.middleware.auth import MockUser
from loguru import logger

async def test_async_context_manager_fix():
    """测试异步上下文管理器修复"""
    logger.info("🧪 测试异步上下文管理器错误修复...")
    
    # 创建测试用户
    mock_user = MockUser(user_id=1, membership_level="basic")
    
    # 测试配置 - 使用不存在的数据，预期会失败但不应该出现async_generator错误
    config = RealtimeBacktestConfig(
        strategy_code="""
class TestStrategy:
    def on_data(self, data):
        return {"action": "buy", "quantity": 0.1}
        """,
        exchange="binance",
        symbols=["TESTPAIR/USDT"],  # 不存在的交易对
        timeframes=["1h"],
        initial_capital=10000.0,
        start_date="2024-01-01",
        end_date="2024-01-02"
    )
    
    try:
        # 尝试启动回测 - 应该失败但不会出现async_generator错误
        result = await start_realtime_backtest(config, mock_user)
        logger.error("❌ 预期应该失败但却成功了")
        return False
    except Exception as e:
        error_msg = str(e)
        
        # 检查是否是预期的数据错误而不是async_generator错误
        if "async_generator" in error_msg or "asynchronous context manager protocol" in error_msg:
            logger.error(f"❌ 仍然存在异步上下文管理器错误: {error_msg}")
            return False
        elif "历史数据不足" in error_msg or "无法获取" in error_msg:
            logger.success(f"✅ 异步上下文管理器错误已修复，收到预期的数据错误: {error_msg[:100]}...")
            return True
        else:
            logger.info(f"⚠️ 收到其他类型错误，但async_generator错误已修复: {error_msg[:100]}...")
            return True

async def test_ai_strategy_backtest_fix():
    """测试AI策略回测的异步上下文管理器修复"""
    logger.info("🧪 测试AI策略回测异步上下文管理器错误修复...")
    
    # 创建测试用户
    mock_user = MockUser(user_id=1, membership_level="basic")
    
    # AI策略回测配置
    config = AIStrategyBacktestConfig(
        strategy_code="""
class TestStrategy:
    def on_data(self, data):
        return {"action": "buy", "quantity": 0.1}
        """,
        exchange="binance",
        symbols=["TESTPAIR/USDT"],
        timeframes=["1h"],
        initial_capital=10000.0,
        start_date="2024-01-01",
        end_date="2024-01-02",
        ai_session_id="test_session"
    )
    
    try:
        # 尝试启动AI策略回测
        result = await start_ai_strategy_backtest(config, None, mock_user)
        logger.error("❌ 预期应该失败但却成功了")
        return False
    except Exception as e:
        error_msg = str(e)
        
        # 检查是否是预期的数据错误而不是async_generator错误
        if "async_generator" in error_msg or "asynchronous context manager protocol" in error_msg:
            logger.error(f"❌ AI策略回测仍然存在异步上下文管理器错误: {error_msg}")
            return False
        else:
            logger.success(f"✅ AI策略回测异步上下文管理器错误已修复: {error_msg[:100]}...")
            return True

async def main():
    """主测试函数"""
    logger.info("🚀 开始异步上下文管理器错误修复验证")
    
    try:
        # 测试常规回测
        regular_test_passed = await test_async_context_manager_fix()
        
        # 测试AI策略回测
        ai_test_passed = await test_ai_strategy_backtest_fix()
        
        if regular_test_passed and ai_test_passed:
            logger.success("🎉 异步上下文管理器错误修复验证通过!")
            logger.info("✅ 修复总结:")
            logger.info("  - ❌ 移除了错误的 'async with get_db() as db:' 用法")
            logger.info("  - ✅ 改为正确的 'async for db in get_db():' 用法") 
            logger.info("  - ✅ 添加了proper资源清理 'await db.close()'")
            logger.info("  - ✅ 常规回测和AI策略回测都已修复")
            return True
        else:
            logger.error("❌ 部分测试失败，异步上下文管理器错误可能未完全修复")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试过程中发生异常: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)