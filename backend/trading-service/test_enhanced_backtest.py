#!/usr/bin/env python3
"""
测试增强的回测引擎功能
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db, AsyncSessionLocal
from app.services.backtest_service import BacktestEngine, BacktestService
from app.models.strategy import Strategy
from app.models.backtest import Backtest
from loguru import logger

async def test_enhanced_backtest():
    """测试增强的回测引擎"""
    try:
        logger.info("开始测试增强的回测引擎功能...")
        
        # 创建测试策略
        test_strategy = Strategy(
            id=1,
            user_id=1,
            name="测试移动平均策略",
            description="简单的移动平均交叉策略",
            code="# 移动平均策略代码",
            parameters='{"short_ma": 5, "long_ma": 20}',
            is_active=True
        )
        
        # 设置回测参数
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now() - timedelta(days=1)
        initial_capital = 10000.0
        
        logger.info(f"回测参数: 起始日期={start_date.date()}, 结束日期={end_date.date()}, 初始资金={initial_capital}")
        
        # 创建回测引擎实例
        engine = BacktestEngine()
        
        # 模拟数据库会话
        async with AsyncSessionLocal() as db:
            # 运行回测 (使用模拟数据)
            logger.info("执行回测...")
            result = await engine.run_backtest(
                strategy_id=1,
                user_id=1,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                symbol="BTC/USDT",
                exchange="binance",
                timeframe="1h",
                db=db
            )
            
            logger.info("回测执行完成!")
            
            # 打印详细结果
            print("\n" + "="*60)
            print("回测结果报告")
            print("="*60)
            
            print(f"策略ID: {result['strategy_id']}")
            print(f"交易对: {result['symbol']}")
            print(f"交易所: {result['exchange']}")
            print(f"时间框架: {result['timeframe']}")
            print(f"回测期间: {result['start_date']} 到 {result['end_date']}")
            
            print("\n📊 基础指标:")
            print(f"初始资金: ${result['initial_capital']:,.2f}")
            print(f"最终资金: ${result['final_capital']:,.2f}")
            print(f"交易次数: {result['trades_count']}")
            
            # 详细性能指标
            performance = result.get('performance', {})
            if performance:
                print("\n📈 收益指标:")
                print(f"总收益率: {performance.get('total_return', 0):.2%}")
                print(f"年化收益率: {performance.get('annualized_return', 0):.2%}")
                
                print("\n⚠️ 风险指标:")
                print(f"波动率: {performance.get('volatility', 0):.2%}")
                print(f"最大回撤: {performance.get('max_drawdown', 0):.2%}")
                print(f"回撤持续期: {performance.get('max_drawdown_duration', 0)} 天")
                print(f"下行偏差: {performance.get('downside_deviation', 0):.2%}")
                
                print("\n📊 风险调整收益:")
                print(f"夏普比率: {performance.get('sharpe_ratio', 0):.3f}")
                print(f"索提诺比率: {performance.get('sortino_ratio', 0):.3f}")
                print(f"卡尔玛比率: {performance.get('calmar_ratio', 0):.3f}")
                
                print("\n💼 风险价值 (VaR/CVaR):")
                print(f"VaR (95%): {performance.get('var_95', 0):.2%}")
                print(f"CVaR (95%): {performance.get('cvar_95', 0):.2%}")
                print(f"VaR (99%): {performance.get('var_99', 0):.2%}")
                print(f"CVaR (99%): {performance.get('cvar_99', 0):.2%}")
                
                print("\n📋 交易统计:")
                print(f"总交易数: {performance.get('total_trades', 0)}")
                print(f"盈利交易: {performance.get('winning_trades', 0)}")
                print(f"亏损交易: {performance.get('losing_trades', 0)}")
                print(f"胜率: {performance.get('win_rate', 0):.1%}")
                print(f"盈亏比: {performance.get('profit_factor', 0):.2f}")
                print(f"平均盈利: ${performance.get('avg_win', 0):.2f}")
                print(f"平均亏损: ${performance.get('avg_loss', 0):.2f}")
                print(f"最大连胜: {performance.get('max_consecutive_wins', 0)}")
                print(f"最大连亏: {performance.get('max_consecutive_losses', 0)}")
                
                print("\n📊 收益分布:")
                print(f"偏度: {performance.get('skewness', 0):.3f}")
                print(f"峰度: {performance.get('kurtosis', 0):.3f}")
        
        print("\n" + "="*60)
        print("✅ 回测引擎增强功能测试完成!")
        
        return True
        
    except Exception as e:
        logger.error(f"回测引擎测试失败: {str(e)}")
        print(f"\n❌ 测试失败: {str(e)}")
        return False

async def test_parallel_backtest():
    """测试并行回测功能"""
    try:
        logger.info("开始测试并行回测功能...")
        
        # 模拟多个策略ID
        strategy_ids = [1, 2, 3]
        
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now() - timedelta(days=1)
        initial_capital = 10000.0
        
        async with AsyncSessionLocal() as db:
            logger.info(f"开始并行回测 {len(strategy_ids)} 个策略...")
            
            results = await BacktestService.run_parallel_backtests(
                db=db,
                strategies=strategy_ids,
                user_id=1,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                symbol="BTC/USDT",
                exchange="binance"
            )
            
            print("\n" + "="*50)
            print("并行回测结果汇总")
            print("="*50)
            
            summary = results.get('summary', {})
            print(f"总策略数: {summary.get('total_strategies', 0)}")
            print(f"成功回测: {summary.get('successful_count', 0)}")
            print(f"失败回测: {summary.get('failed_count', 0)}")
            print(f"成功率: {summary.get('success_rate', 0):.1%}")
            
            # 显示成功的回测结果
            successful = results.get('successful', [])
            if successful:
                print(f"\n✅ 成功的回测 ({len(successful)}个):")
                for i, result in enumerate(successful, 1):
                    perf = result.get('performance', {})
                    print(f"  {i}. 策略{result.get('strategy_id')}: "
                          f"收益率 {perf.get('total_return', 0):.2%}, "
                          f"夏普比率 {perf.get('sharpe_ratio', 0):.2f}")
            
            # 显示失败的回测
            failed = results.get('failed', [])
            if failed:
                print(f"\n❌ 失败的回测 ({len(failed)}个):")
                for result in failed:
                    print(f"  策略{result.get('strategy_id')}: {result.get('error')}")
        
        print("\n✅ 并行回测功能测试完成!")
        return True
        
    except Exception as e:
        logger.error(f"并行回测测试失败: {str(e)}")
        print(f"\n❌ 并行回测测试失败: {str(e)}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试增强的回测引擎...")
    
    # 测试单个回测
    test1_success = await test_enhanced_backtest()
    
    # 测试并行回测  
    test2_success = await test_parallel_backtest()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"单个回测测试: {'✅ 通过' if test1_success else '❌ 失败'}")
    print(f"并行回测测试: {'✅ 通过' if test2_success else '❌ 失败'}")
    
    if test1_success and test2_success:
        print("\n🎉 所有测试通过! 回测引擎增强功能正常工作。")
        return True
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息。")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())