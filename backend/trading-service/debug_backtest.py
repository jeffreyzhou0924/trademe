#!/usr/bin/env python3
"""
回测系统调试脚本
直接测试回测引擎，找出具体失败原因
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import asyncio
from datetime import datetime
from app.services.backtest_service import BacktestEngine
from app.database import AsyncSessionLocal

async def debug_backtest():
    """调试回测功能"""
    print("🔧 开始调试回测系统...")
    
    try:
        # 创建回测引擎
        engine = BacktestEngine()
        
        # 使用与测试相同的参数
        strategy_id = 19  # 我们刚才生成的MACD+RSI策略
        user_id = 9      # publictest用户
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 3, 1) 
        initial_capital = 10000.0
        
        print(f"📊 回测参数:")
        print(f"   策略ID: {strategy_id}")
        print(f"   用户ID: {user_id}")
        print(f"   开始日期: {start_date}")
        print(f"   结束日期: {end_date}")
        print(f"   初始资金: ${initial_capital}")
        
        # 创建数据库会话
        async with AsyncSessionLocal() as db:
            print(f"💾 数据库连接成功")
            
            # 执行回测
            result = await engine.run_backtest(
                strategy_id=strategy_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                symbol="BTC/USDT",
                exchange="okx",
                timeframe="1h",
                db=db
            )
            
            print(f"✅ 回测成功完成!")
            print(f"📈 最终资金: ${result.get('final_capital', 0):.2f}")
            print(f"📊 总收益率: {result.get('performance', {}).get('total_return', 0)*100:.2f}%")
            print(f"📊 交易次数: {result.get('trades_count', 0)}")
            
        return True
        
    except Exception as e:
        print(f"❌ 回测失败: {str(e)}")
        import traceback
        print(f"🔍 详细错误:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(debug_backtest())
    if success:
        print(f"\n🎉 回测系统工作正常!")
        sys.exit(0)
    else:
        print(f"\n⚠️  回测系统存在问题，需要修复")
        sys.exit(1)