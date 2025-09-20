"""
回填 MarketData.product_type 脚本

用途：
- 将历史已入库的 OKX 永续合约数据统一标注为 futures（符号包含 -SWAP）
- 将历史现货数据标注为 spot（其余情况）

运行方式：
  cd backend/trading-service
  python -m scripts.backfill_product_type_market_data

注意：
- 该脚本只读写 MarketData 表，不会影响其它表
- 建议先备份数据库
"""
import asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.market_data import MarketData
from loguru import logger


async def backfill_product_type():
    async with AsyncSessionLocal() as session:  # type: AsyncSession
        # 1) OKX 永续：symbol 以 -SWAP 结尾 → futures
        logger.info("回填 OKX 永续合约 product_type=futures ...")
        futures_stmt = (
            update(MarketData)
            .where(
                MarketData.exchange == 'okx',
                MarketData.symbol.ilike('%-SWAP')
            )
            .values(product_type='futures')
        )
        result1 = await session.execute(futures_stmt)

        # 2) 其它（OKX 非 -SWAP）标记为现货 spot（仅修复未设置的记录，避免覆盖已有）
        logger.info("回填 OKX 现货 product_type=spot ...")
        spot_stmt = (
            update(MarketData)
            .where(
                MarketData.exchange == 'okx',
                MarketData.symbol.ilike('%'),
                MarketData.product_type.is_(None)
            )
            .values(product_type='spot')
        )
        result2 = await session.execute(spot_stmt)

        await session.commit()
        logger.info(
            f"回填完成：futures 更新 {getattr(result1, 'rowcount', 0)} 条，spot 更新 {getattr(result2, 'rowcount', 0)} 条"
        )


if __name__ == '__main__':
    asyncio.run(backfill_product_type())

