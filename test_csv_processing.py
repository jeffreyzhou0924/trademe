#!/usr/bin/env python3
"""
测试CSV文件处理功能
用修复后的代码重新处理现有的CSV文件
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.okx_data_downloader import okx_data_downloader
from app.database import AsyncSessionLocal
from sqlalchemy import text
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_csv_processing():
    """测试CSV文件处理"""
    try:
        logger.info("🧪 开始测试CSV文件处理功能")
        
        # CSV文件路径
        csv_file = Path("/root/trademe/backend/trading-service/data/okx_tick_data/BTC-USDT-SWAP-trades-2024-08-30-final.csv")
        output_file = Path("/root/trademe/backend/trading-service/data/okx_tick_data/BTC-USDT-SWAP-trades-2024-08-30-final2.csv")
        
        if not csv_file.exists():
            logger.error(f"❌ CSV文件不存在: {csv_file}")
            return False
        
        logger.info(f"📂 处理文件: {csv_file}")
        logger.info(f"📊 文件大小: {csv_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        # 调用处理方法
        processed_records = await okx_data_downloader._process_tick_csv(csv_file, "BTC", output_file)
        
        logger.info(f"✅ CSV处理完成，插入记录数: {processed_records}")
        
        # 检查数据库中的记录
        async with AsyncSessionLocal() as db:
            tick_count_query = text("SELECT COUNT(*) FROM tick_data WHERE data_source='okx_historical'")
            tick_result = await db.execute(tick_count_query)
            tick_count = tick_result.scalar()
            
            logger.info(f"📊 数据库中OKX历史记录总数: {tick_count}")
            
            if tick_count > 0:
                # 查看最新记录
                latest_query = text("""
                    SELECT symbol, price, volume, side, timestamp, trade_id 
                    FROM tick_data 
                    WHERE data_source='okx_historical' 
                    ORDER BY created_at DESC 
                    LIMIT 3
                """)
                latest_result = await db.execute(latest_query)
                latest_records = latest_result.fetchall()
                
                logger.info("📋 最新插入的3条记录:")
                for i, record in enumerate(latest_records, 1):
                    logger.info(f"   {i}. {record[0]} - 价格:{record[1]}, 量:{record[2]}, 方向:{record[3]}, 时间戳:{record[4]}, ID:{record[5]}")
        
        return processed_records > 0
        
    except Exception as e:
        logger.error(f"❌ CSV处理测试失败: {e}")
        return False

async def main():
    """主函数"""
    logger.info("🎯 开始CSV文件处理测试")
    logger.info("=" * 50)
    
    success = await test_csv_processing()
    
    logger.info("\n" + "=" * 50)
    if success:
        logger.info("🎉 测试成功！CSV文件处理和数据插入功能正常！")
    else:
        logger.error("❌ 测试失败！需要进一步调试")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())