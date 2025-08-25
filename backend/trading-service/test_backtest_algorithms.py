#!/usr/bin/env python3
"""
测试回测引擎算法功能
专注于性能指标计算的准确性
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.backtest_service import BacktestEngine

def test_performance_metrics():
    """测试性能指标计算算法"""
    print("🧮 测试性能指标计算算法...")
    
    # 创建回测引擎实例
    engine = BacktestEngine()
    
    # 模拟一些日收益率数据
    np.random.seed(42)  # 固定随机种子，确保结果一致
    
    # 模拟30天的日收益率数据（有正有负）
    returns = np.array([
        0.02, -0.01, 0.015, 0.008, -0.005,
        0.01, 0.025, -0.018, 0.003, 0.012,
        -0.02, 0.007, 0.018, -0.012, 0.006,
        0.013, -0.008, 0.022, 0.004, -0.015,
        0.009, 0.017, -0.011, 0.014, 0.003,
        -0.006, 0.021, 0.008, -0.009, 0.016
    ])
    
    engine.daily_returns = returns.tolist()
    initial_capital = 10000.0
    engine.total_value = initial_capital * (1 + returns.sum())  # 模拟最终价值
    
    # 模拟一些交易记录
    engine.trades = [
        {'signal': 'buy', 'value': 1000, 'timestamp': datetime.now()},
        {'signal': 'sell', 'value': 1050, 'timestamp': datetime.now()},
        {'signal': 'buy', 'value': 800, 'timestamp': datetime.now()},
        {'signal': 'sell', 'value': 750, 'timestamp': datetime.now()},
        {'signal': 'buy', 'value': 1200, 'timestamp': datetime.now()},
        {'signal': 'sell', 'value': 1300, 'timestamp': datetime.now()},
    ]
    
    # 计算性能指标
    print("计算性能指标...")
    metrics = engine._calculate_performance_metrics(initial_capital)
    
    # 验证和展示结果
    print("\n" + "="*60)
    print("性能指标计算结果")
    print("="*60)
    
    print(f"📊 基础收益指标:")
    print(f"总收益率: {metrics['total_return']:.2%}")
    print(f"年化收益率: {metrics['annualized_return']:.2%}")
    print(f"交易天数: {metrics['trading_days']}")
    
    print(f"\n⚠️ 风险指标:")
    print(f"波动率: {metrics['volatility']:.2%}")
    print(f"下行偏差: {metrics['downside_deviation']:.2%}")
    print(f"最大回撤: {metrics['max_drawdown']:.2%}")
    print(f"回撤持续期: {metrics['max_drawdown_duration']} 天")
    
    print(f"\n📈 风险调整收益:")
    print(f"夏普比率: {metrics['sharpe_ratio']:.3f}")
    print(f"索提诺比率: {metrics['sortino_ratio']:.3f}")
    print(f"卡尔玛比率: {metrics['calmar_ratio']:.3f}")
    
    print(f"\n💼 风险价值 (VaR/CVaR):")
    print(f"VaR (95%): {metrics['var_95']:.2%}")
    print(f"CVaR (95%): {metrics['cvar_95']:.2%}")
    print(f"VaR (99%): {metrics['var_99']:.2%}")
    print(f"CVaR (99%): {metrics['cvar_99']:.2%}")
    
    print(f"\n📋 交易统计:")
    print(f"总交易数: {metrics['total_trades']}")
    print(f"盈利交易: {metrics['winning_trades']}")
    print(f"亏损交易: {metrics['losing_trades']}")
    print(f"胜率: {metrics['win_rate']:.1%}")
    print(f"盈亏比: {metrics['profit_factor']:.2f}")
    print(f"平均盈利: ${metrics['avg_win']:.2f}")
    print(f"平均亏损: ${metrics['avg_loss']:.2f}")
    print(f"最大连胜: {metrics['max_consecutive_wins']}")
    print(f"最大连亏: {metrics['max_consecutive_losses']}")
    
    print(f"\n📊 收益分布:")
    print(f"偏度: {metrics['skewness']:.3f}")
    print(f"峰度: {metrics['kurtosis']:.3f}")
    
    # 基本合理性检查
    print(f"\n🔍 合理性检查:")
    checks = []
    
    # 检查总收益率
    expected_return = (engine.total_value - initial_capital) / initial_capital
    actual_return = metrics['total_return']
    if abs(expected_return - actual_return) < 0.001:
        checks.append("✅ 总收益率计算正确")
    else:
        checks.append(f"❌ 总收益率计算错误: 期望{expected_return:.2%}, 实际{actual_return:.2%}")
    
    # 检查波动率是否为正数
    if metrics['volatility'] > 0:
        checks.append("✅ 波动率为正数")
    else:
        checks.append("❌ 波动率应为正数")
    
    # 检查夏普比率范围合理性
    if -5 <= metrics['sharpe_ratio'] <= 5:
        checks.append("✅ 夏普比率在合理范围内")
    else:
        checks.append("❌ 夏普比率超出合理范围")
    
    # 检查胜率范围
    if 0 <= metrics['win_rate'] <= 1:
        checks.append("✅ 胜率在合理范围内")
    else:
        checks.append("❌ 胜率超出合理范围")
    
    # 检查VaR是否为正数
    if metrics['var_95'] >= 0 and metrics['cvar_95'] >= 0:
        checks.append("✅ VaR/CVaR为非负数")
    else:
        checks.append("❌ VaR/CVaR应为非负数")
    
    for check in checks:
        print(check)
    
    success_count = len([c for c in checks if c.startswith("✅")])
    total_checks = len(checks)
    
    print(f"\n📈 算法验证结果: {success_count}/{total_checks} 项检查通过")
    
    return success_count == total_checks

def test_technical_indicators():
    """测试技术指标计算"""
    print("\n📊 测试技术指标计算...")
    
    engine = BacktestEngine()
    
    # 创建测试数据
    dates = pd.date_range(start='2025-07-01', end='2025-07-31', freq='D')
    np.random.seed(42)
    
    # 生成模拟价格数据
    base_price = 50000
    prices = []
    current_price = base_price
    
    for _ in range(len(dates)):
        change = np.random.normal(0, 0.02)  # 2%标准差
        current_price *= (1 + change)
        prices.append(current_price)
    
    # 创建DataFrame
    df = pd.DataFrame({
        'close': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'volume': np.random.uniform(100, 1000, len(prices))
    }, index=dates)
    
    # 计算技术指标
    df_with_indicators = engine._add_technical_indicators(df)
    
    print("技术指标计算完成:")
    print(f"数据点数: {len(df_with_indicators)}")
    print(f"列数: {len(df_with_indicators.columns)}")
    print(f"包含指标: {list(df_with_indicators.columns)}")
    
    # 检查指标有效性
    checks = []
    
    # 检查MA指标
    if not df_with_indicators['ma_5'].isna().all():
        checks.append("✅ MA5计算成功")
    else:
        checks.append("❌ MA5计算失败")
    
    # 检查RSI指标
    rsi_values = df_with_indicators['rsi'].dropna()
    if len(rsi_values) > 0 and rsi_values.min() >= 0 and rsi_values.max() <= 100:
        checks.append("✅ RSI计算成功，范围正确")
    else:
        checks.append("❌ RSI计算失败或范围错误")
    
    # 检查MACD指标
    if not df_with_indicators['macd'].isna().all():
        checks.append("✅ MACD计算成功")
    else:
        checks.append("❌ MACD计算失败")
    
    # 检查布林带
    if not df_with_indicators['bb_upper'].isna().all():
        checks.append("✅ 布林带计算成功")
        # 检查上轨>中轨>下轨
        valid_bb = (df_with_indicators['bb_upper'] >= df_with_indicators['bb_middle']).all() and \
                   (df_with_indicators['bb_middle'] >= df_with_indicators['bb_lower']).all()
        if valid_bb:
            checks.append("✅ 布林带上下轨关系正确")
        else:
            checks.append("❌ 布林带上下轨关系错误")
    else:
        checks.append("❌ 布林带计算失败")
    
    for check in checks:
        print(check)
    
    success_count = len([c for c in checks if c.startswith("✅")])
    total_checks = len(checks)
    
    print(f"技术指标验证结果: {success_count}/{total_checks} 项检查通过")
    
    return success_count == total_checks

def test_var_cvar_calculation():
    """专门测试VaR和CVaR计算"""
    print("\n💼 测试VaR和CVaR计算...")
    
    engine = BacktestEngine()
    
    # 创建测试收益率数据
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 1000)  # 1000个样本
    
    # 计算VaR和CVaR
    var_95, cvar_95 = engine._calculate_var_cvar(returns, 0.95)
    var_99, cvar_99 = engine._calculate_var_cvar(returns, 0.99)
    
    print(f"样本数: {len(returns)}")
    print(f"收益率统计: 均值={np.mean(returns):.4f}, 标准差={np.std(returns):.4f}")
    print(f"VaR (95%): {var_95:.4f}")
    print(f"CVaR (95%): {cvar_95:.4f}")
    print(f"VaR (99%): {var_99:.4f}")
    print(f"CVaR (99%): {cvar_99:.4f}")
    
    # 验证CVaR >= VaR (CVaR应该更保守)
    checks = []
    if cvar_95 >= var_95:
        checks.append("✅ CVaR(95%) >= VaR(95%)")
    else:
        checks.append("❌ CVaR(95%) < VaR(95%)")
    
    if cvar_99 >= var_99:
        checks.append("✅ CVaR(99%) >= VaR(99%)")
    else:
        checks.append("❌ CVaR(99%) < VaR(99%)")
    
    # 验证99%VaR >= 95%VaR (更高置信度应该更保守)
    if var_99 >= var_95:
        checks.append("✅ VaR(99%) >= VaR(95%)")
    else:
        checks.append("❌ VaR(99%) < VaR(95%)")
    
    for check in checks:
        print(check)
    
    success_count = len([c for c in checks if c.startswith("✅")])
    return success_count == len(checks)

def main():
    """主测试函数"""
    print("🚀 开始测试回测引擎算法功能...")
    print("="*60)
    
    # 运行各项测试
    test1_success = test_performance_metrics()
    test2_success = test_technical_indicators() 
    test3_success = test_var_cvar_calculation()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"性能指标计算: {'✅ 通过' if test1_success else '❌ 失败'}")
    print(f"技术指标计算: {'✅ 通过' if test2_success else '❌ 失败'}")
    print(f"VaR/CVaR计算: {'✅ 通过' if test3_success else '❌ 失败'}")
    
    if test1_success and test2_success and test3_success:
        print("\n🎉 所有算法测试通过! 回测引擎核心算法功能正常。")
        print("\n✨ 算法增强完成项目:")
        print("• 完整的性能指标计算 (夏普比率、索提诺比率、卡尔玛比率)")
        print("• 高级风险指标 (VaR、CVaR、下行偏差)")
        print("• 详细交易统计 (胜率、盈亏比、连续盈亏)")
        print("• 收益分布分析 (偏度、峰度)")
        print("• 回撤分析 (最大回撤、回撤持续期)")
        print("• 技术指标库 (MA、RSI、MACD、布林带)")
        return True
    else:
        print("\n⚠️ 部分测试失败，请检查算法实现。")
        return False

if __name__ == "__main__":
    main()