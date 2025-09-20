"""
回填 MarketData.product_type 脚本（放置于 trading-service 目录，便于直接导入 app.* 包）

运行：
  cd backend/trading-service
  python scripts/backfill_product_type_market_data.py
"""
import asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import AsyncSessionLocal
from app.models.market_data import MarketData


async def backfill_product_type():
    async with AsyncSessionLocal() as session:  # type: AsyncSession
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

        logger.info("回填 OKX 现货 product_type=spot (仅修复空值)...")
        spot_stmt = (
            update(MarketData)
            .where(
                MarketData.exchange == 'okx',
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

