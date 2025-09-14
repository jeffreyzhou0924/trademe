#!/usr/bin/env python3
"""
测试回测服务的交易所数据修复
验证系统不再返回错误交易所的数据
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.database import get_db
from app.services.backtest_service import BacktestEngine
from app.models.strategy import Strategy
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_binance_backtest():
    """测试使用币安交易所数据进行回测（应该失败）"""
    async for db in get_db():
        try:
            # 获取一个测试策略
            query = select(Strategy).limit(1)
            result = await db.execute(query)
            strategy = result.scalar_one_or_none()
            
            if not strategy:
                logger.error("没有找到任何策略进行测试")
                return
            
            engine = BacktestEngine()
            
            # 尝试使用币安数据进行回测
            logger.info("=== 测试1: 尝试使用Binance数据进行回测（应该失败）===")
            try:
                result = await engine.run_backtest(
                    strategy_id=strategy.id,
                    user_id=strategy.user_id,
                    start_date=datetime.now() - timedelta(days=30),
                    end_date=datetime.now(),
                    initial_capital=10000,
                    symbol="BTC/USDT",
                    exchange="binance",  # 尝试使用币安
                    timeframe="1h",
                    db=db
                )
                logger.error("❌ 测试失败！系统不应该为Binance返回回测结果")
                logger.error(f"   返回的结果: {result}")
            except ValueError as e:
                if "OKX" in str(e):
                    logger.info(f"✅ 测试通过！系统正确拒绝了Binance请求: {e}")
                else:
                    logger.error(f"❌ 错误消息不正确: {e}")
            
            # 尝试使用OKX数据进行回测
            logger.info("\n=== 测试2: 使用OKX数据进行回测（应该成功）===")
            try:
                result = await engine.run_backtest(
                    strategy_id=strategy.id,
                    user_id=strategy.user_id,
                    start_date=datetime.now() - timedelta(days=30),
                    end_date=datetime.now(),
                    initial_capital=10000,
                    symbol="BTC/USDT",  # 正确的符号格式
                    exchange="okx",  # 使用OKX
                    timeframe="1h",
                    db=db
                )
                logger.info(f"✅ OKX回测成功执行")
                logger.info(f"   最终资金: {result.get('final_capital')}")
                logger.info(f"   交易次数: {result.get('trades_count')}")
            except Exception as e:
                logger.error(f"❌ OKX回测失败: {e}")
            
            # 尝试使用Huobi数据进行回测
            logger.info("\n=== 测试3: 尝试使用Huobi数据进行回测（应该失败）===")
            try:
                result = await engine.run_backtest(
                    strategy_id=strategy.id,
                    user_id=strategy.user_id,
                    start_date=datetime.now() - timedelta(days=30),
                    end_date=datetime.now(),
                    initial_capital=10000,
                    symbol="BTC/USDT",
                    exchange="huobi",  # 尝试使用火币
                    timeframe="1h",
                    db=db
                )
                logger.error("❌ 测试失败！系统不应该为Huobi返回回测结果")
            except ValueError as e:
                if "OKX" in str(e):
                    logger.info(f"✅ 测试通过！系统正确拒绝了Huobi请求: {e}")
                else:
                    logger.error(f"❌ 错误消息不正确: {e}")
                    
        except Exception as e:
            logger.error(f"测试过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()

if __name__ == "__main__":
    logger.info("开始测试回测服务的交易所数据修复...")
    asyncio.run(test_binance_backtest())
    logger.info("\n测试完成！")