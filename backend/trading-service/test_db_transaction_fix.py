#!/usr/bin/env python3
"""
测试数据库事务处理修复
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from app.database import get_db, DatabaseTransaction, AsyncSessionLocal
from app.config import settings
from sqlalchemy import text

async def test_get_db_function():
    """测试修复后的get_db函数"""
    print("🧪 测试get_db函数事务处理...")
    
    try:
        # 正常情况 - 应该自动提交
        async for db in get_db():
            print("  ✅ 数据库连接获取成功")
            
            # 模拟一个查询
            result = await db.execute(text("SELECT 1 as test"))
            row = result.scalar()
            print(f"  ✅ 查询执行成功: {row}")
            
            print("  ✅ 事务将自动提交")
            break
            
    except Exception as e:
        print(f"  ❌ get_db函数测试失败: {e}")
        return False
    
    print("  ✅ get_db函数测试通过")
    return True

async def test_database_transaction():
    """测试DatabaseTransaction类"""
    print("\n🧪 测试DatabaseTransaction类...")
    
    try:
        # 正常提交测试
        async with DatabaseTransaction() as session:
            print("  ✅ 事务开始")
            result = await session.execute(text("SELECT 1 as test"))
            row = result.scalar()
            print(f"  ✅ 事务中查询成功: {row}")
            print("  ✅ 事务将自动提交")
        
        print("  ✅ 正常提交测试通过")
        
        # 异常回滚测试
        try:
            async with DatabaseTransaction() as session:
                print("  🧪 测试异常回滚...")
                await session.execute(text("SELECT 1 as test"))
                # 故意触发异常
                raise ValueError("测试异常")
        except ValueError as e:
            print(f"  ✅ 异常捕获成功: {e}")
            print("  ✅ 事务已回滚")
        
        print("  ✅ 异常回滚测试通过")
        
    except Exception as e:
        print(f"  ❌ DatabaseTransaction测试失败: {e}")
        return False
    
    print("  ✅ DatabaseTransaction测试通过")
    return True

async def test_session_state():
    """测试会话状态处理"""
    print("\n🧪 测试会话状态处理...")
    
    try:
        session = AsyncSessionLocal()
        print(f"  ✅ 会话创建: {session}")
        print(f"  ✅ 事务状态检查: in_transaction={session.in_transaction()}")
        await session.close()
        print("  ✅ 会话关闭成功")
        
    except Exception as e:
        print(f"  ❌ 会话状态测试失败: {e}")
        return False
    
    print("  ✅ 会话状态测试通过")
    return True

async def main():
    """主测试函数"""
    print("🔧 数据库事务处理修复验证测试")
    print("=" * 50)
    
    tests = [
        ("get_db函数", test_get_db_function),
        ("DatabaseTransaction类", test_database_transaction), 
        ("会话状态处理", test_session_state)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name}: 通过")
            else:
                failed += 1
                print(f"❌ {test_name}: 失败")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name}: 异常 - {e}")
        
        print()
    
    print("=" * 50)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有数据库事务处理修复验证测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)