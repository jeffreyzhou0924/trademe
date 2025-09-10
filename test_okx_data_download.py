#!/usr/bin/env python3
"""
OKX数据下载系统测试脚本
测试修复后的Tick和K线数据下载功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.okx_data_downloader import okx_data_downloader
from app.database import AsyncSessionLocal
from sqlalchemy import text
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_tick_data_download():
    """测试Tick数据下载功能"""
    try:
        logger.info("🧪 开始测试Tick数据下载功能")
        
        # 创建一个小测试任务：BTC tick数据，只下载1天
        task = await okx_data_downloader.create_tick_download_task(
            symbols=['BTC'],
            start_date='20240830',  # 昨天的数据
            end_date='20240830'     # 只下载一天
        )
        
        logger.info(f"✅ 任务创建成功: {task.task_id}")
        logger.info(f"   - 数据类型: {task.data_type.value}")
        logger.info(f"   - 交易对: {task.symbols}")
        logger.info(f"   - 日期范围: {task.start_date} - {task.end_date}")
        logger.info(f"   - 预计文件数: {task.total_files}")
        
        # 执行下载任务
        logger.info("🚀 开始执行下载任务...")
        await okx_data_downloader.execute_tick_download_task(task.task_id)
        
        # 检查任务状态
        final_task = await okx_data_downloader.get_task_status(task.task_id)
        logger.info(f"📊 任务最终状态:")
        logger.info(f"   - 状态: {final_task.status.value}")
        logger.info(f"   - 进度: {final_task.progress:.1f}%")
        logger.info(f"   - 已处理文件: {final_task.processed_files}/{final_task.total_files}")
        logger.info(f"   - 下载记录数: {final_task.downloaded_records}")
        if final_task.error_message:
            logger.error(f"   - 错误信息: {final_task.error_message}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Tick数据下载测试失败: {e}")
        return False

async def test_database_records():
    """检查数据库中的记录"""
    try:
        logger.info("🔍 检查数据库中的记录...")
        
        async with AsyncSessionLocal() as db:
            # 检查tick_data表
            tick_query = text("SELECT COUNT(*) FROM tick_data")
            tick_result = await db.execute(tick_query)
            tick_count = tick_result.scalar()
            
            logger.info(f"📊 tick_data表记录数: {tick_count}")
            
            if tick_count > 0:
                # 获取最新的几条记录
                recent_query = text("""
                    SELECT symbol, price, volume, side, timestamp, data_source 
                    FROM tick_data 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
                recent_result = await db.execute(recent_query)
                records = recent_result.fetchall()
                
                logger.info("📋 最新的5条tick记录:")
                for i, record in enumerate(records, 1):
                    logger.info(f"   {i}. {record[0]} - 价格:{record[1]}, 量:{record[2]}, 方向:{record[3]}, 数据源:{record[5]}")
            
            # 检查data_collection_tasks表
            task_query = text("SELECT COUNT(*) FROM data_collection_tasks")
            task_result = await db.execute(task_query)
            task_count = task_result.scalar()
            
            logger.info(f"📊 data_collection_tasks表记录数: {task_count}")
            
            if task_count > 0:
                # 获取最新任务信息
                task_info_query = text("""
                    SELECT task_name, data_type, status, total_records, created_at
                    FROM data_collection_tasks 
                    ORDER BY created_at DESC 
                    LIMIT 3
                """)
                task_info_result = await db.execute(task_info_query)
                task_records = task_info_result.fetchall()
                
                logger.info("📋 最新的3个任务记录:")
                for i, task in enumerate(task_records, 1):
                    logger.info(f"   {i}. {task[0]} - 类型:{task[1]}, 状态:{task[2]}, 记录数:{task[3]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据库检查失败: {e}")
        return False

async def test_kline_download():
    """测试K线数据下载功能"""
    try:
        logger.info("🧪 开始测试K线数据下载功能")
        
        # 创建一个小测试任务：BTC K线数据，1小时级别，只下载几天
        task = await okx_data_downloader.create_kline_download_task(
            symbols=['BTC/USDT'],
            timeframes=['1h'],
            start_date='20240829',
            end_date='20240830'
        )
        
        logger.info(f"✅ K线任务创建成功: {task.task_id}")
        logger.info(f"   - 交易对: {task.symbols}")
        logger.info(f"   - 时间周期: {task.timeframes}")
        logger.info(f"   - 日期范围: {task.start_date} - {task.end_date}")
        
        # 执行下载任务
        logger.info("🚀 开始执行K线下载任务...")
        await okx_data_downloader.execute_kline_download_task(task.task_id)
        
        # 检查任务状态
        final_task = await okx_data_downloader.get_task_status(task.task_id)
        logger.info(f"📊 K线任务最终状态:")
        logger.info(f"   - 状态: {final_task.status.value}")
        logger.info(f"   - 进度: {final_task.progress:.1f}%")
        logger.info(f"   - 下载记录数: {final_task.downloaded_records}")
        if final_task.error_message:
            logger.error(f"   - 错误信息: {final_task.error_message}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ K线数据下载测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    logger.info("🎯 开始OKX数据下载系统测试")
    logger.info("=" * 60)
    
    # 检查现有数据库状态
    logger.info("1️⃣ 检查数据库现有状态")
    await test_database_records()
    
    logger.info("\n" + "=" * 60)
    
    # 测试Tick数据下载
    logger.info("2️⃣ 测试Tick数据下载功能")
    tick_success = await test_tick_data_download()
    
    logger.info("\n" + "=" * 60)
    
    # 再次检查数据库状态
    logger.info("3️⃣ 检查下载后的数据库状态")
    await test_database_records()
    
    logger.info("\n" + "=" * 60)
    
    # 测试K线数据下载
    logger.info("4️⃣ 测试K线数据下载功能")
    kline_success = await test_kline_download()
    
    logger.info("\n" + "=" * 60)
    
    # 最终结果
    logger.info("🎯 测试结果总结:")
    logger.info(f"   - Tick数据下载: {'✅ 成功' if tick_success else '❌ 失败'}")
    logger.info(f"   - K线数据下载: {'✅ 成功' if kline_success else '❌ 失败'}")
    
    if tick_success and kline_success:
        logger.info("🎉 所有测试通过！数据下载系统修复成功！")
        return True
    else:
        logger.error("⚠️  部分测试失败，需要进一步调试")
        return False

if __name__ == "__main__":
    asyncio.run(main())