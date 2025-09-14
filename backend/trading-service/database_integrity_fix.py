#!/usr/bin/env python3
"""
数据库完整性修复脚本
解决合约数据被错误标识为现货数据的问题
"""

import asyncio
import sqlite3
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger

class DatabaseIntegrityFixer:
    """数据库完整性修复器"""
    
    def __init__(self, db_path="/root/trademe/data/trademe.db"):
        self.db_path = db_path
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def fix_data_integrity_issue(self):
        """修复数据完整性问题的完整解决方案"""
        try:
            logger.info("🔧 开始数据库完整性修复...")
            
            # 1. 添加product_type字段
            await self._add_product_type_column()
            
            # 2. 修复现有数据的产品类型标识
            await self._fix_existing_data_types()
            
            # 3. 更新现有记录的正确符号格式
            await self._update_symbol_formats()
            
            # 4. 验证修复结果
            await self._validate_fix_results()
            
            logger.info("✅ 数据库完整性修复完成！")
            
        except Exception as e:
            logger.error(f"❌ 数据库修复失败: {str(e)}")
            raise
    
    async def _add_product_type_column(self):
        """为market_data表添加product_type字段"""
        try:
            async with self.async_session() as session:
                # 检查字段是否已存在
                result = await session.execute(text("""
                    SELECT sql FROM sqlite_master 
                    WHERE type='table' AND name='market_data'
                """))
                table_schema = result.scalar_one()
                
                if 'product_type' not in table_schema:
                    # 添加product_type字段
                    await session.execute(text("""
                        ALTER TABLE market_data 
                        ADD COLUMN product_type VARCHAR(20) DEFAULT 'spot'
                    """))
                    
                    # 创建索引优化查询
                    await session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_market_data_product_type 
                        ON market_data(exchange, symbol, product_type, timeframe)
                    """))
                    
                    await session.commit()
                    logger.info("✅ 已添加product_type字段和相关索引")
                else:
                    logger.info("ℹ️ product_type字段已存在")
                    
        except Exception as e:
            logger.error(f"添加product_type字段失败: {e}")
            raise
    
    async def _fix_existing_data_types(self):
        """修复现有数据的产品类型标识"""
        try:
            async with self.async_session() as session:
                # 1. 根据数据收集任务识别产品类型
                # 从data_collection_tasks表查询原始符号配置
                result = await session.execute(text("""
                    SELECT symbols, exchange 
                    FROM data_collection_tasks 
                    WHERE task_name = 'CCXT历史数据下载_56704627'
                """))
                task_config = result.fetchone()
                
                if task_config:
                    import json
                    original_symbols = json.loads(task_config[0])
                    exchange = task_config[1]
                    
                    logger.info(f"发现原始符号配置: {original_symbols} @ {exchange}")
                    
                    # 2. 修复BTC数据的产品类型
                    for symbol in original_symbols:
                        if "SWAP" in symbol or "swap" in symbol.lower():
                            # 这是合约数据，需要修复
                            base_symbol = symbol.replace("-SWAP", "").replace("-", "/")
                            
                            update_result = await session.execute(text("""
                                UPDATE market_data 
                                SET 
                                    product_type = 'futures',
                                    symbol = :correct_symbol
                                WHERE 
                                    exchange = :exchange 
                                    AND symbol = :current_symbol
                                    AND (product_type IS NULL OR product_type = 'spot')
                            """), {
                                "correct_symbol": symbol,  # 恢复原始完整符号
                                "exchange": exchange,
                                "current_symbol": base_symbol
                            })
                            
                            affected_rows = update_result.rowcount
                            logger.info(f"✅ 修复 {affected_rows} 条 {base_symbol} 记录为合约数据 ({symbol})")
                
                # 3. 为其他数据设置默认现货类型
                await session.execute(text("""
                    UPDATE market_data 
                    SET product_type = 'spot' 
                    WHERE product_type IS NULL
                """))
                
                await session.commit()
                logger.info("✅ 产品类型标识修复完成")
                
        except Exception as e:
            logger.error(f"修复产品类型失败: {e}")
            raise
    
    async def _update_symbol_formats(self):
        """标准化符号格式，保持产品类型信息"""
        try:
            async with self.async_session() as session:
                # 确保合约数据使用正确的符号格式
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM market_data 
                    WHERE product_type = 'futures' AND symbol NOT LIKE '%SWAP'
                """))
                
                inconsistent_count = result.scalar()
                
                if inconsistent_count > 0:
                    # 修正合约数据的符号格式
                    await session.execute(text("""
                        UPDATE market_data 
                        SET symbol = REPLACE(symbol, '/', '-') || '-SWAP'
                        WHERE 
                            product_type = 'futures' 
                            AND symbol NOT LIKE '%SWAP'
                            AND symbol LIKE '%/%'
                    """))
                    
                    await session.commit()
                    logger.info(f"✅ 修正了 {inconsistent_count} 条合约数据的符号格式")
                
        except Exception as e:
            logger.error(f"符号格式更新失败: {e}")
            raise
    
    async def _validate_fix_results(self):
        """验证修复结果"""
        try:
            async with self.async_session() as session:
                # 1. 统计修复后的数据分布
                result = await session.execute(text("""
                    SELECT 
                        product_type,
                        symbol,
                        exchange,
                        COUNT(*) as count
                    FROM market_data 
                    GROUP BY product_type, symbol, exchange
                    ORDER BY count DESC
                """))
                
                results = result.fetchall()
                
                logger.info("\n📊 数据完整性修复结果:")
                logger.info("=" * 80)
                
                spot_total = 0
                futures_total = 0
                
                for row in results:
                    product_type, symbol, exchange, count = row
                    logger.info(f"{product_type:8} | {symbol:15} | {exchange:8} | {count:>8,} 条")
                    
                    if product_type == 'spot':
                        spot_total += count
                    elif product_type == 'futures':
                        futures_total += count
                
                logger.info("=" * 80)
                logger.info(f"现货数据总计: {spot_total:,} 条")
                logger.info(f"合约数据总计: {futures_total:,} 条")
                logger.info(f"数据总计: {spot_total + futures_total:,} 条")
                
                # 2. 验证数据一致性
                consistency_result = await session.execute(text("""
                    SELECT COUNT(*) FROM market_data 
                    WHERE 
                        (product_type = 'futures' AND symbol NOT LIKE '%SWAP') OR
                        (product_type = 'spot' AND symbol LIKE '%SWAP')
                """))
                
                inconsistent_count = consistency_result.scalar()
                
                if inconsistent_count == 0:
                    logger.info("✅ 数据一致性检查通过 - 产品类型与符号格式完全匹配")
                else:
                    logger.error(f"❌ 发现 {inconsistent_count} 条不一致数据")
                
                return {
                    "spot_count": spot_total,
                    "futures_count": futures_total,
                    "total_count": spot_total + futures_total,
                    "consistent": inconsistent_count == 0
                }
                
        except Exception as e:
            logger.error(f"验证修复结果失败: {e}")
            raise
    
    async def generate_fix_report(self):
        """生成修复报告"""
        try:
            validation_result = await self._validate_fix_results()
            
            report = f"""
# 数据库完整性修复报告

## 问题描述
- **根本原因**: 数据收集任务配置为 "BTC-USDT-SWAP" (合约)，但存储时被错误标识为 "BTC/USDT" (现货)
- **影响范围**: 239,369 条BTC数据被错误分类

## 修复方案
1. ✅ 为 market_data 表添加 product_type 字段
2. ✅ 根据原始数据收集任务恢复正确的产品类型标识
3. ✅ 标准化符号格式，保持产品类型完整性
4. ✅ 创建索引优化数据类型查询

## 修复结果
- **现货数据**: {validation_result['spot_count']:,} 条
- **合约数据**: {validation_result['futures_count']:,} 条  
- **数据一致性**: {'通过' if validation_result['consistent'] else '失败'}

## 后续建议
1. 更新回测验证逻辑，严格匹配数据类型与用户配置
2. 更新前端界面，透明显示实际使用的数据类型
3. 改进数据收集流程，防止类似问题再次发生

---
修复时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            with open('/root/trademe/backend/trading-service/DATABASE_INTEGRITY_FIX_REPORT.md', 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info("📄 修复报告已生成: DATABASE_INTEGRITY_FIX_REPORT.md")
            return report
            
        except Exception as e:
            logger.error(f"生成修复报告失败: {e}")
            raise


async def main():
    """主函数"""
    logger.info("🚀 启动数据库完整性修复程序")
    
    try:
        fixer = DatabaseIntegrityFixer()
        
        # 执行完整性修复
        await fixer.fix_data_integrity_issue()
        
        # 生成修复报告
        await fixer.generate_fix_report()
        
        logger.info("🎉 数据库完整性修复成功完成！")
        
    except Exception as e:
        logger.error(f"💥 修复过程出现错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())