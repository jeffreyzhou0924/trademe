#!/usr/bin/env python3
"""
测试回测一致性修复效果

验证相同配置的多次回测是否产生一致结果
"""

import asyncio
import os
import sys
import json
import pandas as pd
from datetime import datetime, date
from loguru import logger

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.backtest_service import create_backtest_engine

# 测试策略代码
TEST_STRATEGY_CODE = """
# 简单MACD策略测试
class MACDStrategy(BaseStrategy):
    def on_data(self, data):
        # 获取价格数据
        if len(data) < 30:
            return None  # 数据不足
        
        # 使用系统内置方法获取MACD指标
        macd_data = self.get_indicator('MACD', data, fast=12, slow=26, signal=9)
        if not macd_data or len(macd_data) < 2:
            return None
        
        current_macd = macd_data[-1]
        prev_macd = macd_data[-2]
        
        # 获取当前价格
        current_price = data['close'].iloc[-1]
        
        # MACD策略逻辑：MACD线上穿信号线买入，下穿卖出
        if current_macd['macd'] > current_macd['signal'] and prev_macd['macd'] <= prev_macd['signal']:
            return {
                'action': 'buy',
                'price': current_price,
                'size': 0.3,  # 30%仓位
                'reason': 'MACD金叉买入信号'
            }
        elif current_macd['macd'] < current_macd['signal'] and prev_macd['macd'] >= prev_macd['signal']:
            return {
                'action': 'sell', 
                'price': current_price,
                'size': 0.5,  # 卖出50%持仓
                'reason': 'MACD死叉卖出信号'
            }
        
        return None  # 无操作信号
"""

async def test_backtest_consistency():
    """测试回测一致性"""
    logger.info("🧪 开始测试回测一致性修复效果")
    
    # 测试配置
    test_config = {
        'strategy_code': TEST_STRATEGY_CODE,
        'exchange': 'okx',  # 使用有数据的交易所
        'symbols': ['BTC/USDT'],
        'timeframes': ['1h'],
        'start_date': '2025-07-01',
        'end_date': '2025-08-31',
        'initial_capital': 10000.0
    }
    
    # 存储多次回测结果
    results = []
    
    # 执行5次相同配置的回测
    for i in range(5):
        logger.info(f"🔄 执行第 {i+1} 次回测...")
        
        try:
            # 创建数据库连接
            async with AsyncSessionLocal() as db:
                # 🔧 关键：每次都创建新的引擎实例
                backtest_engine = create_backtest_engine()
                
                # 执行回测
                result = await backtest_engine.execute_backtest(
                    test_config,
                    user_id=1,
                    db=db
                )
                
                if result.get('success'):
                    backtest_result = result.get('backtest_result', {})
                    performance = backtest_result.get('performance_metrics', {})
                    
                    # 提取关键指标
                    key_metrics = {
                        'run_number': i + 1,
                        'total_return': performance.get('total_return', 0),
                        'final_value': backtest_result.get('final_portfolio_value', 0),
                        'total_trades': len(backtest_result.get('trades', [])),
                        'sharpe_ratio': performance.get('sharpe_ratio', 0),
                        'max_drawdown': performance.get('max_drawdown', 0),
                        'win_rate': performance.get('win_rate', 0),
                        'data_records': backtest_result.get('data_records', 0)
                    }
                    
                    results.append(key_metrics)
                    
                    logger.info(f"✅ 第{i+1}次回测完成:")
                    logger.info(f"   总收益率: {key_metrics['total_return']:.6f}")
                    logger.info(f"   最终价值: {key_metrics['final_value']:.2f}")
                    logger.info(f"   交易次数: {key_metrics['total_trades']}")
                    logger.info(f"   数据记录: {key_metrics['data_records']}")
                    
                else:
                    logger.error(f"❌ 第{i+1}次回测失败: {result.get('error', '未知错误')}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 第{i+1}次回测异常: {e}")
            return False
        
        # 短暂间隔
        await asyncio.sleep(0.5)
    
    # 分析结果一致性
    logger.info("\n📊 回测一致性分析:")
    logger.info("="*60)
    
    if len(results) < 2:
        logger.error("❌ 可用结果不足，无法进行一致性分析")
        return False
    
    # 检查关键指标的一致性
    consistency_checks = {
        'total_return': [],
        'final_value': [],
        'total_trades': [],
        'data_records': []
    }
    
    for result in results:
        for key in consistency_checks:
            consistency_checks[key].append(result[key])
    
    is_consistent = True
    tolerance = 1e-10  # 浮点数容差
    
    for metric, values in consistency_checks.items():
        unique_values = set(values)
        
        if metric in ['total_trades', 'data_records']:
            # 整数值必须完全一致
            is_metric_consistent = len(unique_values) == 1
        else:
            # 浮点数值允许微小差异
            if len(unique_values) <= 1:
                is_metric_consistent = True
            else:
                min_val, max_val = min(values), max(values)
                is_metric_consistent = abs(max_val - min_val) <= tolerance
        
        status = "✅ 一致" if is_metric_consistent else "❌ 不一致"
        logger.info(f"{metric:15}: {status} {unique_values}")
        
        if not is_metric_consistent:
            is_consistent = False
    
    # 显示详细结果表格
    logger.info("\n📋 详细结果对比:")
    logger.info("-"*80)
    logger.info(f"{'Run':<4} {'Return':<12} {'Final Value':<12} {'Trades':<8} {'Records':<8}")
    logger.info("-"*80)
    
    for result in results:
        logger.info(f"{result['run_number']:<4} {result['total_return']:<12.6f} "
                   f"{result['final_value']:<12.2f} {result['total_trades']:<8} "
                   f"{result['data_records']:<8}")
    
    # 保存结果到文件
    with open('/root/trademe/backend/trading-service/backtest_consistency_test_results.json', 'w') as f:
        json.dump({
            'test_config': test_config,
            'results': results,
            'is_consistent': is_consistent,
            'test_time': datetime.now().isoformat()
        }, f, indent=2, default=str)
    
    logger.info(f"\n🎯 一致性测试结果: {'✅ 通过' if is_consistent else '❌ 失败'}")
    
    if is_consistent:
        logger.info("🎉 回测引擎修复成功！相同配置产生一致结果")
    else:
        logger.error("⚠️  仍存在一致性问题，需要进一步调试")
    
    return is_consistent

async def main():
    """主测试函数"""
    try:
        logger.info("🚀 开始回测一致性修复验证")
        success = await test_backtest_consistency()
        
        if success:
            logger.info("✅ 测试完成：回测一致性问题已修复")
            return 0
        else:
            logger.error("❌ 测试失败：回测一致性问题仍然存在")
            return 1
            
    except Exception as e:
        logger.error(f"测试异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)