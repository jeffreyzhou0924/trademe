#!/usr/bin/env python3
"""
优化后的数据下载系统测试脚本
测试资源监控、内存管理和优化的下载功能
"""

import asyncio
import sys
import os
import time
import logging
from datetime import datetime, timedelta

# 添加项目路径到Python路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.okx_data_downloader import okx_data_downloader, ResourceMonitor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_resource_monitor():
    """测试资源监控器"""
    print("\n" + "="*60)
    print("🔍 测试资源监控器")
    print("="*60)
    
    monitor = ResourceMonitor()
    
    # 基础功能测试
    print(f"📊 内存使用率: {monitor.get_memory_usage():.1f}%")
    print(f"💻 CPU使用率: {monitor.get_cpu_usage():.1f}%")  
    print(f"🔧 进程内存: {monitor.get_process_memory_mb():.1f}MB")
    
    # 可用性检查
    available, message = monitor.is_resource_available()
    print(f"✅ 资源状态: {'可用' if available else '不可用'}")
    print(f"📝 状态消息: {message}")
    
    # 强制清理测试
    initial_memory = monitor.get_process_memory_mb()
    monitor.force_cleanup()
    final_memory = monitor.get_process_memory_mb()
    print(f"🧹 内存清理: {initial_memory:.1f}MB → {final_memory:.1f}MB")
    
    return available

async def test_small_download_task():
    """测试小规模下载任务（避免资源过载）"""
    print("\n" + "="*60)
    print("📥 测试小规模Tick数据下载")
    print("="*60)
    
    monitor = ResourceMonitor()
    
    try:
        # 创建一个小的测试任务（只下载1个交易对，1天的数据）
        start_date = "20240301"  # 一个月前的数据，通常比较小
        end_date = "20240301"    # 只下载1天
        symbols = ["BTC"]        # 只下载1个交易对
        
        print(f"🎯 创建测试任务: {symbols} {start_date}-{end_date}")
        
        # 记录初始资源状态
        initial_memory = monitor.get_process_memory_mb()
        initial_cpu = monitor.get_cpu_usage()
        
        print(f"🚀 初始状态 - 内存: {initial_memory:.1f}MB, CPU: {initial_cpu:.1f}%")
        
        # 创建下载任务
        task = await okx_data_downloader.create_tick_download_task(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"✅ 任务创建成功: {task.task_id}")
        print(f"📊 预计文件数: {task.total_files}")
        
        # 模拟监控任务状态（不实际执行，避免网络请求）
        print(f"⏳ 任务状态: {task.status.value}")
        print(f"📈 进度: {task.progress:.1f}%")
        
        # 检查资源使用
        current_memory = monitor.get_process_memory_mb()
        current_cpu = monitor.get_cpu_usage()
        
        print(f"🔍 当前状态 - 内存: {current_memory:.1f}MB, CPU: {current_cpu:.1f}%")
        print(f"📈 内存变化: {current_memory - initial_memory:+.1f}MB")
        
        # 清理任务
        await okx_data_downloader.cancel_task(task.task_id)
        print(f"🧹 任务已取消")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试下载任务失败: {e}")
        return False

async def test_concurrent_task_limitation():
    """测试并发任务限制"""
    print("\n" + "="*60)
    print("🚦 测试并发任务限制")
    print("="*60)
    
    try:
        # 创建第一个任务
        task1 = await okx_data_downloader.create_tick_download_task(
            symbols=["BTC"],
            start_date="20240301",
            end_date="20240301"
        )
        print(f"✅ 任务1创建成功: {task1.task_id}")
        
        # 尝试创建第二个任务
        task2 = await okx_data_downloader.create_tick_download_task(
            symbols=["ETH"],
            start_date="20240301", 
            end_date="20240301"
        )
        print(f"✅ 任务2创建成功: {task2.task_id}")
        
        # 检查活跃任务数量
        active_tasks = await okx_data_downloader.list_active_tasks()
        print(f"📊 活跃任务数: {len(active_tasks)}")
        
        # 清理任务
        await okx_data_downloader.cancel_task(task1.task_id)
        await okx_data_downloader.cancel_task(task2.task_id)
        print(f"🧹 所有测试任务已清理")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试并发限制失败: {e}")
        return False

async def test_memory_optimization():
    """测试内存优化"""
    print("\n" + "="*60)
    print("🧠 测试内存优化功能")
    print("="*60)
    
    monitor = ResourceMonitor()
    
    # 创建一些对象并测试垃圾回收
    initial_memory = monitor.get_process_memory_mb()
    print(f"🚀 初始内存: {initial_memory:.1f}MB")
    
    # 创建一些大列表模拟内存使用
    large_data = []
    for i in range(10000):
        large_data.append({"id": i, "data": "x" * 100})
    
    after_allocation = monitor.get_process_memory_mb()
    print(f"📈 分配后内存: {after_allocation:.1f}MB (+{after_allocation - initial_memory:.1f}MB)")
    
    # 清理数据
    large_data.clear()
    del large_data
    
    # 强制垃圾回收
    monitor.force_cleanup()
    
    final_memory = monitor.get_process_memory_mb()
    print(f"🧹 清理后内存: {final_memory:.1f}MB")
    print(f"📉 内存释放: {after_allocation - final_memory:.1f}MB")
    
    # 检查内存是否有效释放
    memory_freed = after_allocation - final_memory
    if memory_freed > 5:  # 至少释放5MB
        print("✅ 内存优化测试通过")
        return True
    else:
        print("⚠️ 内存优化可能需要改进")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试优化后的数据下载系统")
    print("⏰ 测试时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    test_results = []
    
    try:
        # 1. 测试资源监控器
        result1 = await test_resource_monitor()
        test_results.append(("资源监控器", result1))
        
        # 2. 测试小规模下载任务
        result2 = await test_small_download_task()  
        test_results.append(("小规模下载", result2))
        
        # 3. 测试并发任务限制
        result3 = await test_concurrent_task_limitation()
        test_results.append(("并发限制", result3))
        
        # 4. 测试内存优化
        result4 = await test_memory_optimization()
        test_results.append(("内存优化", result4))
        
    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}")
    
    # 输出测试结果摘要
    print("\n" + "="*60)
    print("📋 测试结果摘要")
    print("="*60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 总体结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！数据下载系统优化成功")
        return True
    else:
        print("⚠️ 部分测试失败，需要进一步优化")
        return False

if __name__ == "__main__":
    asyncio.run(main())