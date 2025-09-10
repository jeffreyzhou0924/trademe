#!/usr/bin/env python3

"""
直接测试数据库查询逻辑的调试脚本
"""

import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
import sys
import os

# 添加项目路径到sys.path
sys.path.append('/root/trademe/backend/trading-service')

async def test_tick_query():
    """测试tick数据查询"""
    
    # 1. 首先直接用sqlite3测试
    print("=== 直接SQLite查询测试 ===")
    conn = sqlite3.connect('/root/trademe/data/trademe.db')
    cursor = conn.cursor()
    
    # 测试原始查询
    cursor.execute("SELECT COUNT(*) FROM tick_data WHERE exchange = ? AND symbol = ?", ("okx", "BTC/USDT"))
    count = cursor.fetchone()[0]
    print(f"直接查询结果: exchange=okx, symbol=BTC/USDT, 记录数={count}")
    
    # 测试聚合查询（和API中使用的相同）
    cursor.execute("""
        SELECT 
            symbol,
            MIN(timestamp) as start_timestamp,
            MAX(timestamp) as end_timestamp,
            COUNT(*) as record_count,
            MIN(created_at) as first_created,
            MAX(created_at) as last_created
        FROM tick_data 
        WHERE exchange = ? AND symbol = ?
        GROUP BY symbol
    """, ("okx", "BTC/USDT"))
    
    result = cursor.fetchall()
    print(f"聚合查询结果: {result}")
    
    conn.close()
    
    # 2. 使用AsyncSession测试（和API中使用的相同）
    print("\n=== AsyncSession查询测试 ===")
    
    # 创建数据库连接
    DATABASE_URL = "sqlite+aiosqlite:////root/trademe/data/trademe.db"
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        query = text("""
        SELECT 
            symbol,
            MIN(timestamp) as start_timestamp,
            MAX(timestamp) as end_timestamp,
            COUNT(*) as record_count,
            MIN(created_at) as first_created,
            MAX(created_at) as last_created
        FROM tick_data 
        WHERE exchange = :exchange AND symbol = :symbol
        GROUP BY symbol
        """)
        
        query_params = {"exchange": "okx", "symbol": "BTC/USDT"}
        print(f"查询参数: {query_params}")
        
        result = await db.execute(query, query_params)
        rows = result.fetchall()
        
        print(f"AsyncSession查询结果: {rows}")
        
        if rows:
            for row in rows:
                print(f"  - Symbol: {row.symbol}")
                print(f"  - 记录数: {row.record_count}")
                print(f"  - 开始时间戳: {row.start_timestamp}")
                print(f"  - 结束时间戳: {row.end_timestamp}")
        else:
            print("  - 没有找到记录")
    
    await engine.dispose()

def test_symbol_normalization():
    """测试symbol转换逻辑"""
    print("\n=== Symbol转换逻辑测试 ===")
    
    def _normalize_symbol_for_query(symbol: str) -> str:
        """测试转换函数"""
        if not symbol:
            return symbol
        
        # 如果是期货合约格式 BTC-USDT-SWAP
        if '-SWAP' in symbol:
            # BTC-USDT-SWAP -> BTC/USDT:USDT -> BTCUSDTUSDT
            base_symbol = symbol.replace('-SWAP', '').replace('-', '/')
            ccxt_format = base_symbol + ':USDT'  # BTC/USDT:USDT
            normalized = ccxt_format.replace('/', '').replace(':', '')  # BTCUSDTUSDT
        elif '-' in symbol:
            # 包含短横线的格式: BTC-USDT -> BTCUSDT
            normalized = symbol.replace('-', '').replace('/', '').replace(':', '')
        else:
            # 简单格式 (主要是tick数据): BTC -> BTC/USDT
            # 这是针对tick数据查询的特殊处理，因为tick数据存储格式是 BTC/USDT
            normalized = f"{symbol}/USDT"
        
        print(f"符号转换: {symbol} -> {normalized}")
        return normalized
    
    # 测试不同输入
    test_symbols = ["BTC", "BTC-USDT", "BTC-USDT-SWAP", "ETH", "BTC/USDT"]
    
    for symbol in test_symbols:
        normalized = _normalize_symbol_for_query(symbol)
        print(f"  {symbol} -> {normalized}")

if __name__ == "__main__":
    print("开始调试tick数据查询问题...")
    
    # 测试symbol转换逻辑
    test_symbol_normalization()
    
    # 测试数据库查询
    asyncio.run(test_tick_query())
    
    print("\n调试完成！")