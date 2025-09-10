#!/usr/bin/env python3
"""
最终清理验证脚本 - 确认所有tick相关数据已清理完成
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import AsyncSessionLocal

async def verify_cleanup():
    """验证清理结果"""
    print("🔍 正在验证清理结果...")
    
    try:
        # 1. 验证OKX下载器内存状态
        from app.services.okx_data_downloader import okx_data_downloader
        memory_tasks = len(okx_data_downloader.active_tasks)
        print(f"✅ OKX下载器内存任务数: {memory_tasks}")
        
        # 2. 验证数据库表状态
        async with AsyncSessionLocal() as db:
            # 检查所有可能包含tick数据的表
            tables_to_check = [
                ("market_data", "市场数据表"),
                ("tick_data", "tick数据表"),
            ]
            
            total_records = 0
            for table_name, description in tables_to_check:
                try:
                    result = await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar()
                    print(f"✅ {description} ({table_name}): {count} 条记录")
                    total_records += count
                except Exception as e:
                    print(f"ℹ️ {description} ({table_name}): 表不存在")
            
            print(f"\n📊 清理结果汇总:")
            print(f"   - 内存中的活跃任务: {memory_tasks}")
            print(f"   - 数据库中的数据记录: {total_records}")
            
            if memory_tasks == 0 and total_records == 0:
                print("\n🎉 所有tick任务和数据已完全清除！")
                return True
            else:
                print(f"\n⚠️ 清理可能不完整，请检查剩余数据")
                return False
                
    except Exception as e:
        print(f"❌ 验证过程中出错: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(verify_cleanup())
    if result:
        print("\n✅ 清理验证完成 - 系统状态正常")
    else:
        print("\n💥 验证失败，可能需要进一步清理")