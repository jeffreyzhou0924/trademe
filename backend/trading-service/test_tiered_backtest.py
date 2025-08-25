#!/usr/bin/env python3
"""
测试分层回测功能
验证不同用户等级的回测服务
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.tiered_backtest_service import (
    TieredBacktestService,
    UserTier,
    DataPrecision,
    tiered_backtest_service
)
from app.models.user import User
from app.models.strategy import Strategy
from loguru import logger


class MockUser:
    """模拟用户类"""
    def __init__(self, user_id: int, membership_level: str):
        self.id = user_id
        self.membership_level = membership_level
        self.username = f"user_{user_id}"
        self.email = f"user_{user_id}@test.com"


class MockStrategy:
    """模拟策略类"""
    def __init__(self, strategy_id: int, user_id: int):
        self.id = strategy_id
        self.user_id = user_id
        self.name = f"测试策略_{strategy_id}"
        self.description = "测试用策略"
        self.code = "# 简单移动平均策略"
        self.parameters = '{"short_ma": 5, "long_ma": 20}'


async def test_basic_user_backtest():
    """测试Basic用户回测"""
    print("\n🔵 测试Basic用户K线回测...")
    
    try:
        # 创建Basic用户
        user = MockUser(1, "basic")
        strategy = MockStrategy(1, 1)
        
        # 设置回测参数
        params = {
            "start_date": datetime.now() - timedelta(days=30),
            "end_date": datetime.now() - timedelta(days=1),
            "initial_capital": 10000.0,
            "symbol": "BTC/USDT",
            "exchange": "binance",
            "timeframe": "1h"
        }
        
        # 运行Basic回测
        result = await tiered_backtest_service.run_tiered_backtest(user, strategy, params)
        
        # 验证结果
        assert result["user_tier"] == "basic"
        assert result["data_precision"] == "kline"
        assert "features_used" in result
        assert "limitations" in result
        
        print("✅ Basic用户回测测试通过")
        print(f"   - 数据精度: {result['data_precision']}")
        print(f"   - 使用功能: {result['features_used']}")
        print(f"   - 收益率: {result.get('performance', {}).get('total_return', 0):.2%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic用户回测测试失败: {str(e)}")
        return False


async def test_pro_user_backtest():
    """测试Pro用户混合回测"""
    print("\n🟡 测试Pro用户混合精度回测...")
    
    try:
        # 创建Pro用户
        user = MockUser(2, "pro")
        strategy = MockStrategy(2, 2)
        
        # 设置回测参数
        params = {
            "start_date": datetime.now() - timedelta(days=15),
            "end_date": datetime.now() - timedelta(days=1),
            "initial_capital": 20000.0,
            "symbol": "ETH/USDT",
            "exchange": "binance"
        }
        
        # 运行Pro回测
        result = await tiered_backtest_service.run_tiered_backtest(user, strategy, params)
        
        # 验证结果
        assert result["user_tier"] == "pro"
        assert result["data_precision"] == "hybrid"
        assert "precision_segments" in result
        assert "volatility_analysis" in result
        
        print("✅ Pro用户回测测试通过")
        print(f"   - 数据精度: {result['data_precision']}")
        print(f"   - 精度段数: {result['precision_segments']}")
        print(f"   - 收益率: {result.get('performance', {}).get('total_return', 0):.2%}")
        
        # 显示精度分解
        if "precision_breakdown" in result:
            breakdown = result["precision_breakdown"]
            print(f"   - 精度分解: K线{breakdown.get('kline', 0)}段, 秒级{breakdown.get('second', 0)}段, Tick模拟{breakdown.get('tick_simulation', 0)}段")
        
        return True
        
    except Exception as e:
        print(f"❌ Pro用户回测测试失败: {str(e)}")
        return False


async def test_elite_user_backtest():
    """测试Elite用户Tick回测"""
    print("\n🔴 测试Elite用户Tick级回测...")
    
    try:
        # 创建Elite用户
        user = MockUser(3, "elite")
        strategy = MockStrategy(3, 3)
        
        # 设置回测参数
        params = {
            "start_date": datetime.now() - timedelta(days=5),
            "end_date": datetime.now() - timedelta(days=1),
            "initial_capital": 50000.0,
            "symbol": "BTC/USDT",
            "exchange": "binance"
        }
        
        # 运行Elite回测
        result = await tiered_backtest_service.run_tiered_backtest(user, strategy, params)
        
        # 验证结果
        assert result["user_tier"] == "elite"
        assert result["data_precision"] == "tick_real"
        assert "execution_analytics" in result
        assert "total_ticks_processed" in result
        
        print("✅ Elite用户回测测试通过")
        print(f"   - 数据精度: {result['data_precision']}")
        print(f"   - 处理Tick数: {result['total_ticks_processed']:,}")
        print(f"   - 收益率: {result.get('performance', {}).get('total_return', 0):.2%}")
        
        # 显示执行分析
        exec_analytics = result.get("execution_analytics", {})
        if exec_analytics:
            performance = exec_analytics.get("performance", {})
            print(f"   - 平均滑点: {performance.get('avg_slippage', 0):.4f}")
            print(f"   - 执行质量: {performance.get('execution_quality', 0):.2%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Elite用户回测测试失败: {str(e)}")
        return False


async def test_tier_determination():
    """测试用户等级判定"""
    print("\n📊 测试用户等级判定...")
    
    try:
        test_cases = [
            ("basic", UserTier.BASIC),
            ("pro", UserTier.PRO),
            ("premium", UserTier.PRO),  # 兼容映射
            ("elite", UserTier.ELITE),
            ("enterprise", UserTier.ELITE),  # 兼容映射
            ("unknown", UserTier.BASIC)  # 默认值
        ]
        
        for membership_level, expected_tier in test_cases:
            user = MockUser(99, membership_level)
            actual_tier = tiered_backtest_service._determine_user_tier(user)
            
            if actual_tier == expected_tier:
                print(f"✅ {membership_level} -> {expected_tier.value}")
            else:
                print(f"❌ {membership_level} -> 期望{expected_tier.value}, 实际{actual_tier.value}")
                return False
        
        print("✅ 用户等级判定测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 用户等级判定测试失败: {str(e)}")
        return False


async def test_tier_info():
    """测试等级信息获取"""
    print("\n📋 测试等级信息获取...")
    
    try:
        for tier in UserTier:
            info = tiered_backtest_service.get_tier_info(tier)
            
            required_fields = ["tier", "limits", "data_precision", "features"]
            for field in required_fields:
                if field not in info:
                    print(f"❌ {tier.value} 等级信息缺少字段: {field}")
                    return False
            
            print(f"✅ {tier.value} 等级信息完整")
            print(f"   - 数据精度: {info['data_precision']}")
            print(f"   - 并发限制: {info['limits']['max_concurrent_backtests']}")
            print(f"   - 功能数量: {len(info['features'])}")
        
        print("✅ 等级信息测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 等级信息测试失败: {str(e)}")
        return False


async def test_performance_comparison():
    """测试不同等级性能对比"""
    print("\n📈 测试性能对比...")
    
    try:
        # 使用相同策略和参数测试不同等级
        strategy = MockStrategy(99, 99)
        params = {
            "start_date": datetime.now() - timedelta(days=10),
            "end_date": datetime.now() - timedelta(days=1),
            "initial_capital": 10000.0,
            "symbol": "BTC/USDT",
            "exchange": "binance"
        }
        
        results = {}
        
        # 测试三个等级
        for tier_name, membership in [("Basic", "basic"), ("Pro", "pro"), ("Elite", "elite")]:
            user = MockUser(99, membership)
            result = await tiered_backtest_service.run_tiered_backtest(user, strategy, params)
            
            performance = result.get("performance", {})
            results[tier_name] = {
                "return": performance.get("total_return", 0),
                "sharpe": performance.get("sharpe_ratio", 0),
                "drawdown": performance.get("max_drawdown", 0),
                "precision": result.get("data_precision", "unknown")
            }
        
        # 显示对比结果
        print("\n📊 性能对比结果:")
        print(f"{'等级':<8} {'精度':<12} {'收益率':<10} {'夏普比率':<10} {'最大回撤':<10}")
        print("-" * 60)
        
        for tier, perf in results.items():
            print(f"{tier:<8} {perf['precision']:<12} {perf['return']:>8.2%} {perf['sharpe']:>9.2f} {perf['drawdown']:>9.2%}")
        
        # 验证精度递增
        precisions = ["kline", "hybrid", "tick_real"]
        actual_precisions = [results[tier]["precision"] for tier in ["Basic", "Pro", "Elite"]]
        
        if actual_precisions == precisions:
            print("✅ 精度递增正确")
        else:
            print(f"❌ 精度递增错误: 期望{precisions}, 实际{actual_precisions}")
            return False
        
        print("✅ 性能对比测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 性能对比测试失败: {str(e)}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始测试分层回测功能...")
    print("=" * 60)
    
    # 运行所有测试
    tests = [
        ("用户等级判定", test_tier_determination),
        ("等级信息获取", test_tier_info),
        ("Basic用户回测", test_basic_user_backtest),
        ("Pro用户回测", test_pro_user_backtest),
        ("Elite用户回测", test_elite_user_backtest),
        ("性能对比分析", test_performance_comparison)
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n🧪 正在执行: {test_name}")
        try:
            success = await test_func()
            results[test_name] = success
        except Exception as e:
            print(f"❌ {test_name} 执行异常: {str(e)}")
            results[test_name] = False
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name:<20} {status}")
    
    print("-" * 60)
    print(f"总计: {passed_tests}/{total_tests} 项测试通过")
    
    if passed_tests == total_tests:
        print("\n🎉 所有测试通过! 分层回测功能正常工作。")
        print("\n✨ 功能特性验证完成:")
        print("• Basic用户: K线级回测，适合初学者")
        print("• Pro用户: 混合精度回测，智能切换数据源")
        print("• Elite用户: Tick级回测，最高精度分析")
        print("• 等级管理: 自动识别用户等级并分配相应资源")
        print("• 性能递增: 高等级用户享受更好的回测精度")
        return True
    else:
        print(f"\n⚠️ {total_tests - passed_tests} 项测试失败，请检查实现。")
        return False


if __name__ == "__main__":
    asyncio.run(main())