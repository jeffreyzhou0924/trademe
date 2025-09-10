#!/usr/bin/env python3
"""
直接测试自动回测功能，绕过AI代理服务的超时问题
"""

import asyncio
import sys
import os
from datetime import datetime
import json

# 添加项目根目录到Python路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.auto_backtest_service import AutoBacktestService


# 测试策略代码 - 简单MACD策略
SIMPLE_MACD_STRATEGY = """
def strategy_logic(data, indicators):
    '''
    简单MACD交叉策略
    '''
    # 获取MACD指标
    macd = indicators.get('MACD', {})
    if not macd:
        return {'action': 'hold', 'reason': 'Missing MACD indicator'}
    
    current_macd = macd.get('macd', 0)
    current_signal = macd.get('signal', 0)
    
    # 金叉买入，死叉卖出
    if current_macd > current_signal:
        return {
            'action': 'buy',
            'reason': 'MACD金叉信号',
            'confidence': 0.8
        }
    elif current_macd < current_signal:
        return {
            'action': 'sell', 
            'reason': 'MACD死叉信号',
            'confidence': 0.7
        }
    else:
        return {
            'action': 'hold',
            'reason': '无明确信号'
        }
"""

# 用户意图配置
TEST_INTENT = {
    "strategy_type": "trend_following",
    "target_assets": ["BTC-USDT-SWAP"],
    "expected_return": 15,  # 期望15%收益率
    "max_drawdown": 20,     # 最大回撤20%
    "timeframe": "1h",
    "risk_level": "medium"
}

async def test_auto_backtest_service():
    """测试自动回测服务"""
    
    print("🧪 开始测试自动回测功能...")
    print(f"📊 测试策略: MACD交叉策略")
    print(f"🎯 测试配置: {json.dumps(TEST_INTENT, indent=2, ensure_ascii=False)}")
    print("-" * 60)
    
    try:
        # 执行自动回测
        result = await AutoBacktestService.auto_backtest_strategy(
            strategy_code=SIMPLE_MACD_STRATEGY,
            intent=TEST_INTENT,
            user_id=9,  # 测试用户ID
            config={
                "initial_capital": 10000,
                "days_back": 15,  # 缩短回测时间
                "symbol": "BTC-USDT-SWAP",
                "exchange": "okx",
                "timeframe": "1h"
            }
        )
        
        print("✅ 自动回测执行完成!")
        print(f"🆔 回测ID: {result.get('backtest_id')}")
        print(f"📈 性能等级: {result.get('performance_grade', 'N/A')}")
        print(f"🎯 符合预期: {result.get('meets_expectations', False)}")
        
        if result.get('results') and result['results'].get('performance'):
            perf = result['results']['performance']
            print(f"\n📊 回测结果:")
            print(f"  总收益率: {perf.get('total_return', 0):.2%}")
            print(f"  夏普比率: {perf.get('sharpe_ratio', 0):.2f}")
            print(f"  最大回撤: {perf.get('max_drawdown', 0):.2%}")
            print(f"  胜率: {perf.get('win_rate', 0):.2%}")
            print(f"  交易次数: {perf.get('total_trades', 0)}")
        
        if result.get('report'):
            report = result['report']
            print(f"\n📈 评估报告:")
            if report.get('evaluation'):
                eval_data = report['evaluation']
                print(f"  等级: {eval_data.get('grade', 'N/A')}")
                print(f"  优势: {eval_data.get('strengths', [])}")
                print(f"  弱点: {eval_data.get('weaknesses', [])}")
        
        if result.get('error'):
            print(f"❌ 回测执行错误: {result['error']}")
            return False
        
        print("\n🎉 自动回测功能测试成功!")
        return True
        
    except Exception as e:
        print(f"❌ 自动回测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_batch_backtest():
    """测试批量回测对比功能"""
    
    print("\n🔄 测试批量回测对比功能...")
    
    # 创建几个不同的策略版本
    strategy_variations = [
        SIMPLE_MACD_STRATEGY,
        SIMPLE_MACD_STRATEGY.replace("confidence': 0.8", "confidence': 0.9"),
        SIMPLE_MACD_STRATEGY.replace("confidence': 0.7", "confidence': 0.6")
    ]
    
    try:
        result = await AutoBacktestService.batch_backtest_comparison(
            strategy_codes=strategy_variations,
            intent=TEST_INTENT,
            user_id=9
        )
        
        print(f"📊 批量回测结果:")
        print(f"  测试总数: {result.get('total_tested', 0)}")
        print(f"  成功: {result.get('successful', 0)}")
        print(f"  失败: {result.get('failed', 0)}")
        
        if result.get('best_strategy'):
            best = result['best_strategy']
            print(f"  最佳策略: 版本{best.get('version', 'N/A')}")
            print(f"    等级: {best.get('grade', 'N/A')}")
            print(f"    收益率: {best.get('total_return', 0):.2%}")
        
        if result.get('comparison_summary'):
            summary = result['comparison_summary']
            print(f"  对比总结:")
            print(f"    平均收益率: {summary.get('avg_return', 0):.2%}")
            print(f"    最佳收益率: {summary.get('best_return', 0):.2%}")
            print(f"    成功率: {summary.get('success_rate', 0):.1%}")
        
        print("✅ 批量回测对比功能测试成功!")
        return True
        
    except Exception as e:
        print(f"❌ 批量回测测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    
    print("🚀 TradeMe自动回测功能集成测试")
    print("=" * 60)
    
    # 设置环境变量
    os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:////root/trademe/data/trademe.db'
    
    # 测试1: 单个策略自动回测
    test1_success = await test_auto_backtest_service()
    
    # 测试2: 批量策略对比回测
    test2_success = await test_batch_backtest()
    
    print("\n" + "=" * 60)
    print("📋 测试总结:")
    print(f"  ✅ 单策略自动回测: {'通过' if test1_success else '失败'}")
    print(f"  ✅ 批量对比回测: {'通过' if test2_success else '失败'}")
    
    if test1_success and test2_success:
        print("\n🎉 自动回测功能集成测试全部通过!")
        print("🔗 自动回测系统已准备就绪，可与AI策略生成系统集成")
        return True
    else:
        print("\n❌ 部分测试失败，需要进一步调试")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)