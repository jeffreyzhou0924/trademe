#!/usr/bin/env python3
"""
清除数据库中所有tick数据和相关任务的脚本
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import AsyncSessionLocal

async def clear_tick_database():
    """清除数据库中所有tick相关数据"""
    try:
        # 获取数据库连接
        async with AsyncSessionLocal() as db:
            
            # 1. 查询当前tick数据数量
            tick_count_result = await db.execute(text("SELECT COUNT(*) FROM tick_data"))
            tick_count = tick_count_result.scalar()
            print(f"🔍 当前tick数据记录数: {tick_count}")
            
            if tick_count == 0:
                print("ℹ️ 数据库中没有tick数据，无需清理")
                return True
            
            # 2. 清除tick数据
            await db.execute(text("DELETE FROM tick_data"))
            print(f"✅ 已删除 {tick_count} 条tick数据记录")
            
            # 3. 重置序列（如果使用SQLite的自动增长主键）
            await db.execute(text("DELETE FROM sqlite_sequence WHERE name = 'tick_data'"))
            print("✅ 已重置tick_data表序列")
            
            # 4. 提交事务
            await db.commit()
            print("✅ 数据库事务已提交")
            
            # 5. 验证清理结果
            final_tick_count = await db.execute(text("SELECT COUNT(*) FROM tick_data"))
            print(f"✅ 清理后tick数据数量: {final_tick_count.scalar()}")
            
            return True
            
    except Exception as e:
        print(f"❌ 清理数据库时出错: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(clear_tick_database())
    if result:
        print("🎉 数据库tick数据清理完成！")
    else:
        print("💥 数据库清理失败，请检查错误信息")