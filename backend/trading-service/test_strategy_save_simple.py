#!/usr/bin/env python3
"""
简单的策略保存测试

直接测试策略保存逻辑，不依赖登录
"""

import asyncio
import sqlite3
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def check_database_tables():
    """检查数据库表结构和数据"""
    try:
        # 检查主数据库
        print("🔍 检查数据库状态...")
        
        # 使用交易服务目录下的数据库
        db_path = "/root/trademe/data/trademe.db"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查strategies表
        cursor.execute("SELECT COUNT(*) FROM strategies")
        strategies_count = cursor.fetchone()[0]
        print(f"strategies表记录数: {strategies_count}")
        
        # 检查generated_strategies表
        cursor.execute("SELECT COUNT(*) FROM generated_strategies")
        generated_count = cursor.fetchone()[0]
        print(f"generated_strategies表记录数: {generated_count}")
        
        # 检查claude_conversations表
        cursor.execute("SELECT COUNT(*) FROM claude_conversations")
        conversations_count = cursor.fetchone()[0]
        print(f"claude_conversations表记录数: {conversations_count}")
        
        # 如果有策略记录，显示最新的几条
        if strategies_count > 0:
            print("\n📊 最新策略记录:")
            cursor.execute("SELECT id, name, description, ai_session_id, created_at FROM strategies ORDER BY created_at DESC LIMIT 3")
            for row in cursor.fetchall():
                print(f"   - ID: {row[0]}, 名称: {row[1]}, 会话ID: {row[3]}, 创建时间: {row[4]}")
        
        if generated_count > 0:
            print("\n📊 最新生成记录:")
            cursor.execute("SELECT id, user_id, substr(prompt, 1, 50), created_at FROM generated_strategies ORDER BY created_at DESC LIMIT 3")
            for row in cursor.fetchall():
                print(f"   - ID: {row[0]}, 用户: {row[1]}, 提示: {row[2]}..., 时间: {row[3]}")
        
        conn.close()
        
        return {
            "strategies": strategies_count,
            "generated": generated_count,
            "conversations": conversations_count
        }
        
    except Exception as e:
        print(f"❌ 数据库检查异常: {e}")
        return None

async def test_strategy_creation():
    """直接测试策略创建逻辑"""
    try:
        print("\n🧪 测试策略创建逻辑...")
        
        # 导入必需的模块
        from app.database import get_db, engine
        from app.services.strategy_service import StrategyService
        from app.schemas.strategy import StrategyCreate
        from app.models import Strategy
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # 创建数据库会话
        async for db in get_db():
            try:
                # 创建测试策略
                strategy_data = StrategyCreate(
                    name="测试MACD背离策略_0911_1456",
                    description="AI生成的测试策略 (会话: test1234...)",
                    code="""
class MACDDivergenceStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.name = "MACD背离策略"
        
    def on_data_update(self, data):
        # 计算MACD
        macd, signal = self.calculate_macd(data)
        # 检查背离
        if self.check_divergence(data, macd):
            return TradingSignal(SignalType.BUY, confidence=0.8)
        return None
                    """,
                    strategy_type="strategy",
                    ai_session_id="test-session-123",
                    parameters={"test": True}
                )
                
                # 创建策略
                strategy = await StrategyService.create_strategy(
                    db, strategy_data, user_id=6  # 测试用户ID
                )
                
                print(f"✅ 策略创建成功!")
                print(f"   - 策略ID: {strategy.id}")
                print(f"   - 策略名称: {strategy.name}")
                print(f"   - 会话ID: {strategy.ai_session_id}")
                
                return strategy
                
            except Exception as e:
                print(f"❌ 策略创建异常: {e}")
                return None
            finally:
                break
                
    except Exception as e:
        print(f"❌ 测试设置异常: {e}")
        return None

async def test_get_latest_strategy_api():
    """测试获取最新策略API"""
    try:
        print("\n🔍 测试获取最新策略API...")
        
        from app.database import get_db
        from app.services.strategy_service import StrategyService
        
        async for db in get_db():
            try:
                # 测试获取最新策略
                latest_strategy = await StrategyService.get_latest_strategy_by_session(
                    db, "test-session-123", 6
                )
                
                if latest_strategy:
                    print(f"✅ 找到最新策略:")
                    print(f"   - 策略ID: {latest_strategy.id}")
                    print(f"   - 策略名称: {latest_strategy.name}")
                    print(f"   - 会话ID: {latest_strategy.ai_session_id}")
                    return latest_strategy
                else:
                    print("❌ 没有找到策略")
                    return None
                    
            except Exception as e:
                print(f"❌ API测试异常: {e}")
                return None
            finally:
                break
    
    except Exception as e:
        print(f"❌ API测试设置异常: {e}")
        return None

async def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 简单策略保存测试")
    print("=" * 60)
    
    # 1. 检查数据库状态
    db_status = await check_database_tables()
    
    if db_status is None:
        print("❌ 数据库检查失败")
        return 1
    
    # 2. 测试策略创建
    strategy = await test_strategy_creation()
    
    if not strategy:
        print("❌ 策略创建失败")
        return 1
    
    # 3. 再次检查数据库
    print("\n🔍 创建后的数据库状态:")
    await check_database_tables()
    
    # 4. 测试API获取
    api_strategy = await test_get_latest_strategy_api()
    
    if api_strategy:
        print("\n✅ 完整测试通过！策略创建和获取都正常工作。")
        return 0
    else:
        print("\n❌ API获取失败，前端仍然会有问题。")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)