#!/usr/bin/env python3
"""
测试回测系统和AI分析修复
验证关键组件是否正常工作
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.database import get_db, init_db
from app.services.ai_service import AIService
from app.middleware.auth import verify_jwt_token, create_access_token
from loguru import logger


async def test_database_connection():
    """测试数据库连接"""
    print("🔍 测试数据库连接...")
    try:
        async for db in get_db():
            # 尝试执行一个简单查询
            result = await db.execute("SELECT 1 as test")
            row = result.fetchone()
            if row and row[0] == 1:
                print("✅ 数据库连接正常")
                return True
            else:
                print("❌ 数据库查询失败")
                return False
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


async def test_ai_backtest_analysis():
    """测试AI回测分析的错误处理"""
    print("🔍 测试AI回测分析错误处理...")
    try:
        # 模拟回测结果
        fake_backtest_results = {
            "strategy_name": "测试策略",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 10000,
            "performance": {
                "total_return": 15.5,
                "sharpe_ratio": 1.2,
                "max_drawdown": 8.3
            }
        }
        
        result = await AIService.analyze_backtest_performance(
            backtest_results=fake_backtest_results,
            user_id=1
        )
        
        # 检查返回结果是否有预期的键
        required_keys = ["summary", "strengths", "weaknesses", "suggestions", "risk_analysis"]
        if all(key in result for key in required_keys):
            print("✅ AI分析错误处理正常")
            print(f"   返回消息: {result['summary'][:50]}...")
            return True
        else:
            print(f"❌ AI分析返回结果缺少必要字段: {result.keys()}")
            return False
            
    except Exception as e:
        print(f"❌ AI分析测试失败: {e}")
        return False


def test_jwt_token_creation():
    """测试JWT token创建和验证"""
    print("🔍 测试JWT token处理...")
    try:
        # 创建测试token
        test_data = {
            "userId": 1,
            "email": "test@example.com",
            "username": "testuser",
            "membershipLevel": "premium"
        }
        
        token = create_access_token(test_data)
        if not token:
            print("❌ JWT token创建失败")
            return False
        
        # 验证token
        payload = verify_jwt_token(token)
        if payload and payload.get("user_id") == 1:
            print("✅ JWT token创建和验证正常")
            return True
        else:
            print("❌ JWT token验证失败")
            return False
            
    except Exception as e:
        print(f"❌ JWT token测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("🚀 开始回测系统修复验证测试")
    print("=" * 50)
    
    tests = [
        ("数据库连接", test_database_connection),
        ("AI回测分析", test_ai_backtest_analysis), 
        ("JWT Token处理", test_jwt_token_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}测试:")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
    
    print(f"\n{'='*50}")
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有修复验证测试通过！")
        print("✨ 回测启动和AI分析的关键问题已修复")
    else:
        print("⚠️  部分测试失败，需要进一步检查")
    
    return passed == total


if __name__ == "__main__":
    asyncio.run(main())