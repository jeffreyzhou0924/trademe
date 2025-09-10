#!/usr/bin/env python3
"""
清理OKX下载器任务状态的脚本
解决"已有1个下载任务正在运行"的问题
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def clear_okx_tasks():
    """清理OKX下载器的所有任务状态"""
    try:
        # 导入OKX下载器实例
        from app.services.okx_data_downloader import okx_data_downloader
        
        print(f"🔍 当前活跃任务数量: {len(okx_data_downloader.active_tasks)}")
        
        # 显示当前任务列表
        if okx_data_downloader.active_tasks:
            print("📋 当前活跃任务:")
            for task_id, task in okx_data_downloader.active_tasks.items():
                print(f"  - {task_id}: {task.status} (类型: {task.data_type})")
        
        # 清空所有内存中的任务
        okx_data_downloader.active_tasks.clear()
        print("✅ 已清空OKX下载器内存中的所有任务")
        
        # 验证清理结果
        active_tasks = await okx_data_downloader.list_active_tasks()
        print(f"✅ 清理后活跃任务数量: {len(active_tasks)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 清理任务时出错: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(clear_okx_tasks())
    if result:
        print("🎉 OKX任务状态清理完成！")
    else:
        print("💥 清理失败，请检查错误信息")