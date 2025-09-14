#!/usr/bin/env python3
"""
数据完整性修复验证测试
测试新的数据验证和策略修复功能
"""

import asyncio
import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

from app.services.data_validation_service import DataValidationService, BacktestDataValidator
from app.services.strategy_symbol_fix_service import StrategySymbolFixService, SmartStrategyRepairer
from app.database import get_db
from datetime import datetime
import json
from datetime import datetime as dt


def json_serializer(obj):
    """JSON序列化器，处理datetime对象"""
    if isinstance(obj, dt):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


# 测试用的策略代码（与用户实际遇到的问题相同）
PROBLEM_STRATEGY_CODE = '''from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    """MA5和MA10金叉死叉策略"""
    
    def __init__(self):
        super().__init__()
        self.last_signal = None
        
    def get_data_requirements(self) -> List[DataRequest]:
        """定义策略所需的数据源"""
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP",  # 问题：硬编码为合约
                timeframe="1h",
                required=True
            )
        ]
'''

# 用户的回测配置（现货）
USER_CONFIG = {
    "exchange": "okx",
    "product_type": "spot",
    "symbols": ["BTC/USDT"],
    "timeframes": ["1h"],
    "start_date": "2025-08-15",
    "end_date": "2025-09-14"
}


async def test_data_validation_service():
    """测试数据验证服务"""
    print("🔍 测试数据验证服务...")
    
    async for db in get_db():
        # 测试数据可用性验证
        validation_result = await DataValidationService.validate_backtest_data_availability(
            db=db,
            exchange="okx",
            symbol="BTC-USDT-SWAP",  # 不存在的合约数据
            timeframe="1h",
            start_date=datetime.fromisoformat("2025-08-15"),
            end_date=datetime.fromisoformat("2025-09-14")
        )
        
        print(f"❌ 合约数据验证结果: {json.dumps(validation_result, indent=2, ensure_ascii=False, default=json_serializer)}")
        
        # 测试现货数据验证
        validation_result2 = await DataValidationService.validate_backtest_data_availability(
            db=db,
            exchange="okx", 
            symbol="BTC/USDT",  # 存在的现货数据
            timeframe="1h",
            start_date=datetime.fromisoformat("2025-08-15"),
            end_date=datetime.fromisoformat("2025-09-14")
        )
        
        print(f"✅ 现货数据验证结果: {json.dumps(validation_result2, indent=2, ensure_ascii=False, default=json_serializer)}")
        break  # 只需要一次数据库连接


def test_strategy_symbol_consistency():
    """测试策略代码一致性检查"""
    print("\n📋 测试策略代码一致性检查...")
    
    consistency_result = DataValidationService.validate_strategy_symbol_consistency(
        strategy_code=PROBLEM_STRATEGY_CODE,
        user_symbols=USER_CONFIG["symbols"]
    )
    
    print(f"一致性检查结果: {json.dumps(consistency_result, indent=2, ensure_ascii=False)}")


def test_strategy_symbol_fix():
    """测试策略代码自动修复"""
    print("\n🔧 测试策略代码自动修复...")
    
    fix_result = StrategySymbolFixService.fix_strategy_symbol_mismatch(
        strategy_code=PROBLEM_STRATEGY_CODE,
        user_config=USER_CONFIG
    )
    
    print(f"修复结果: {json.dumps({k: v for k, v in fix_result.items() if k != 'fixed_code'}, indent=2, ensure_ascii=False)}")
    
    if fix_result["fixed"]:
        print("\n修复后的策略代码片段:")
        lines = fix_result["fixed_code"].split('\n')
        for i, line in enumerate(lines[15:25], 16):  # 显示关键部分
            print(f"{i:2d}: {line}")


async def test_comprehensive_validation():
    """测试综合验证"""
    print("\n🎯 测试综合验证系统...")
    
    async for db in get_db():
        comprehensive_result = await BacktestDataValidator.comprehensive_validation(
            db=db,
            strategy_code=PROBLEM_STRATEGY_CODE,
            config=USER_CONFIG
        )
        
        print(f"综合验证结果: {json.dumps(comprehensive_result, indent=2, ensure_ascii=False)}")
        break  # 只需要一次数据库连接


async def test_smart_strategy_repairer():
    """测试智能策略修复器"""
    print("\n🤖 测试智能策略修复器...")
    
    # 模拟数据库中可用的数据
    available_data = [
        {"symbol": "BTC/USDT", "exchange": "okx", "timeframe": "1h"},
        {"symbol": "ETH/USDT", "exchange": "okx", "timeframe": "1h"}
    ]
    
    repair_result = await SmartStrategyRepairer.auto_repair_strategy_for_backtest(
        strategy_code=PROBLEM_STRATEGY_CODE,
        user_config=USER_CONFIG,
        available_data=available_data
    )
    
    print(f"智能修复结果: {json.dumps({k: v for k, v in repair_result.items() if k != 'fixed_code'}, indent=2, ensure_ascii=False)}")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始数据完整性修复验证测试\n")
    
    try:
        await test_data_validation_service()
        test_strategy_symbol_consistency()
        test_strategy_symbol_fix()
        await test_comprehensive_validation()
        await test_smart_strategy_repairer()
        
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())