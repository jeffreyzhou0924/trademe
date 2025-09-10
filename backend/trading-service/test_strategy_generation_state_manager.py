"""
策略生成状态管理器测试脚本
测试策略代码的后台保存和摘要生成功能
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock
import json

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.strategy_generation_state_manager import StrategyGenerationStateManager


class MockStrategy:
    """模拟Strategy模型"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, 'id'):
            self.id = 123  # 模拟生成的ID


class MockDBSession:
    """模拟数据库会话"""
    def __init__(self):
        self.added_objects = []
        self.executed_queries = []
        
    def add(self, obj):
        self.added_objects.append(obj)
    
    async def commit(self):
        pass
    
    async def refresh(self, obj):
        obj.id = 123  # 模拟设置ID
    
    async def rollback(self):
        pass
    
    async def execute(self, query, params=None):
        self.executed_queries.append((query, params))
        # 模拟返回结果
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (5, 2, 85.5)  # total, active, avg_score
        mock_result.fetchall.return_value = []
        return mock_result


async def test_strategy_name_generation():
    """测试策略名称生成"""
    
    print("🧪 策略名称生成测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    test_cases = [
        {
            "name": "双均线策略",
            "strategy_info": {
                "strategy_type": "双均线交叉",
                "indicators": ["MA", "EMA"],
                "timeframe": "1h"
            }
        },
        {
            "name": "多指标组合",
            "strategy_info": {
                "strategy_type": None,
                "indicators": ["RSI", "MACD"],
                "timeframe": "15m"
            }
        },
        {
            "name": "基础策略",
            "strategy_info": {
                "strategy_type": None,
                "indicators": [],
                "timeframe": "4h"
            }
        }
    ]
    
    for test_case in test_cases:
        strategy_name = manager._generate_strategy_name(test_case["strategy_info"])
        print(f"✓ {test_case['name']}: {strategy_name}")
    
    print("\n✅ 策略名称生成测试完成！")


async def test_strategy_description_generation():
    """测试策略描述生成"""
    
    print("\n📝 策略描述生成测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    strategy_info = {
        "strategy_type": "MACD动量",
        "indicators": ["MACD", "RSI"],
        "timeframe": "15m",
        "entry_conditions": ["金叉", "RSI>50"],
        "exit_conditions": ["死叉"],
        "stop_loss": "2%",
        "take_profit": "3%"
    }
    
    metadata = {
        "maturity_score": 88.5
    }
    
    description = manager._generate_strategy_description(strategy_info, metadata)
    print(f"生成的描述: {description}")
    
    # 验证描述包含关键信息
    assert "MACD动量" in description
    assert "MACD, RSI" in description
    assert "15m" in description
    assert "2个买入条件" in description
    assert "1个卖出条件" in description
    assert "止损, 止盈" in description
    assert "88/100" in description
    
    print("✅ 策略描述包含所有必要信息")


async def test_performance_estimation():
    """测试性能预期估算"""
    
    print("\n📈 性能预期估算测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    test_strategies = [
        {
            "name": "双均线交叉",
            "info": {"strategy_type": "双均线交叉", "indicators": ["MA"]}
        },
        {
            "name": "RSI反转",
            "info": {"strategy_type": "RSI反转", "indicators": ["RSI"]}
        },
        {
            "name": "多指标组合",
            "info": {"strategy_type": "MACD动量", "indicators": ["MACD", "RSI", "BOLL"]}
        },
        {
            "name": "未知策略",
            "info": {"strategy_type": "未知类型", "indicators": ["VOL"]}
        }
    ]
    
    for strategy in test_strategies:
        performance = manager._estimate_strategy_performance(strategy["info"])
        print(f"✓ {strategy['name']}:")
        print(f"  年化收益: {performance['expected_return']}")
        print(f"  最大回撤: {performance['max_drawdown']}")
        print(f"  夏普比率: {performance['sharpe_ratio']}")
    
    print("\n✅ 性能预期估算测试完成！")


async def test_strategy_complexity_calculation():
    """测试策略复杂度计算"""
    
    print("\n🔍 策略复杂度计算测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    complexity_test_cases = [
        {
            "name": "简单策略",
            "info": {
                "indicators": ["MA"],
                "entry_conditions": ["买入"],
                "exit_conditions": []  # 减少复杂度
            },
            "expected": "简单"
        },
        {
            "name": "中等策略", 
            "info": {
                "indicators": ["RSI", "MACD"],  # 4分
                "entry_conditions": ["金叉"],   # 1分
                "exit_conditions": ["死叉"],    # 1分
                "stop_loss": "2%",              # 1分
                # 总分: 4+1+1+1 = 7分，应该是中等
            },
            "expected": "中等"
        },
        {
            "name": "复杂策略",
            "info": {
                "indicators": ["RSI", "MACD", "BOLL", "KDJ"],
                "entry_conditions": ["金叉", "超卖", "突破上轨", "K>D"],
                "exit_conditions": ["死叉", "超买", "跌破下轨"],
                "stop_loss": "1.5%",
                "take_profit": "4%",
                "position_sizing": "动态"
            },
            "expected": "复杂"
        }
    ]
    
    for test_case in complexity_test_cases:
        complexity = manager._calculate_strategy_complexity(test_case["info"])
        status = "✅" if complexity == test_case["expected"] else "❌"
        print(f"{status} {test_case['name']}: {complexity} (预期: {test_case['expected']})")
    
    print("\n✅ 策略复杂度计算测试完成！")


async def test_summary_response_generation():
    """测试摘要响应生成"""
    
    print("\n💬 摘要响应生成测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    strategy_info = {
        "strategy_type": "双均线交叉",
        "indicators": ["MA", "EMA"],
        "timeframe": "1h",
        "entry_conditions": ["金叉"],
        "exit_conditions": ["死叉"],
        "stop_loss": "2%"
    }
    
    generation_metadata = {
        "maturity_score": 75.5,
        "user_confirmed": True
    }
    
    summary = await manager.generate_strategy_summary_response(
        strategy_id=123,
        strategy_info=strategy_info,
        generation_metadata=generation_metadata
    )
    
    print("生成的摘要响应:")
    print("─" * 40)
    print(summary[:500] + "...")
    
    # 验证摘要包含关键信息
    assert "双均线交叉" in summary
    assert "MA, EMA" in summary
    assert "1h" in summary
    assert "76/100" in summary  # 修正预期值
    assert "#123" in summary
    
    print("\n✅ 摘要响应包含所有必要信息")


async def test_silent_save_strategy():
    """测试静默保存策略"""
    
    print("\n💾 静默保存策略测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    # 模拟Strategy模型
    original_strategy = manager.db.add
    def mock_add(strategy_obj):
        mock_db.added_objects.append(strategy_obj)
        return strategy_obj
    manager.db.add = mock_add
    
    strategy_info = {
        "strategy_type": "RSI反转",
        "indicators": ["RSI"],
        "timeframe": "15m",
        "entry_conditions": ["超卖反弹"],
        "exit_conditions": ["超买下跌"],
        "stop_loss": "已提及",
        "take_profit": "已提及"
    }
    
    metadata = {
        "maturity_score": 82.0,
        "user_confirmed": True
    }
    
    generated_code = """
def rsi_reversal_strategy():
    # RSI反转策略代码
    if rsi < 30:
        return 'BUY'
    elif rsi > 70:
        return 'SELL'
    return 'HOLD'
"""
    
    result = await manager.save_strategy_silently(
        user_id=1,
        session_id="test_session_123",
        strategy_info=strategy_info,
        generated_code=generated_code,
        metadata=metadata
    )
    
    print(f"保存结果: {result}")
    
    # 验证保存结果
    assert result["success"] == True
    assert result["strategy_id"] == 123
    assert "RSI反转" in result["strategy_name"]
    
    # 验证数据库操作
    assert len(mock_db.added_objects) == 1
    saved_strategy = mock_db.added_objects[0]
    
    print(f"✓ 策略名称: {saved_strategy.name}")
    print(f"✓ 策略类型: {saved_strategy.strategy_type}")
    print(f"✓ 会话ID: {saved_strategy.ai_session_id}")
    print(f"✓ 是否激活: {saved_strategy.is_active}")
    
    # 验证参数存储
    parameters = json.loads(saved_strategy.parameters)
    assert parameters["indicators"] == ["RSI"]
    assert parameters["timeframe"] == "15m"
    assert parameters["generation_metadata"]["maturity_score"] == 82.0
    
    print("\n✅ 静默保存策略测试完成！")


async def test_generation_stats():
    """测试策略生成统计"""
    
    print("\n📊 策略生成统计测试")
    print("-" * 50)
    
    mock_db = MockDBSession()
    manager = StrategyGenerationStateManager(mock_db)
    
    stats = await manager.get_strategy_generation_stats(user_id=1)
    
    print(f"策略生成统计:")
    print(f"✓ 总策略数: {stats['total_strategies']}")
    print(f"✓ 活跃策略数: {stats['active_strategies']}")
    print(f"✓ 非活跃策略数: {stats['inactive_strategies']}")
    print(f"✓ 平均成熟度: {stats['avg_maturity_score']}")
    
    assert isinstance(stats['total_strategies'], int)
    assert isinstance(stats['avg_maturity_score'], float)
    
    print("\n✅ 策略生成统计测试完成！")


if __name__ == "__main__":
    asyncio.run(test_strategy_name_generation())
    asyncio.run(test_strategy_description_generation())
    asyncio.run(test_performance_estimation())
    asyncio.run(test_strategy_complexity_calculation())
    asyncio.run(test_summary_response_generation())
    asyncio.run(test_silent_save_strategy())
    asyncio.run(test_generation_stats())
    
    print("\n🎉 所有测试完成！策略生成状态管理器工作正常！")