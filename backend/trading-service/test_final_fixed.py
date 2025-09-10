#!/usr/bin/env python3

"""
最终修复测试：直接模拟API查询流程
"""

import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

def _normalize_symbol_for_query(symbol: str) -> str:
    """符号转换逻辑"""
    if not symbol:
        return symbol
    
    if '-SWAP' in symbol:
        base_symbol = symbol.replace('-SWAP', '').replace('-', '/')
        ccxt_format = base_symbol + ':USDT'
        normalized = ccxt_format.replace('/', '').replace(':', '')
    elif '-' in symbol:
        normalized = symbol.replace('-', '').replace('/', '').replace(':', '')
    elif '/' in symbol and 'USDT' in symbol:
        normalized = symbol
    else:
        normalized = f"{symbol}/USDT"
    
    print(f"符号转换: {symbol} -> {normalized}")
    return normalized

async def test_api_query_flow():
    """模拟完整的API查询流程"""
    
    # 输入参数
    data_type = 'tick'
    exchange = 'okx'
    symbol = 'BTC'
    
    print(f"=== API查询流程测试 ===")
    print(f"输入参数: data_type={data_type}, exchange={exchange}, symbol={symbol}")
    
    # 1. 符号转换
    normalized_symbol = _normalize_symbol_for_query(symbol)
    print(f"转换后符号: {normalized_symbol}")
    
    # 2. 数据库连接
    DATABASE_URL = "sqlite+aiosqlite:////root/trademe/data/trademe.db"
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # 3. 执行查询
    async with async_session() as db:
        if data_type == 'tick':
            if symbol:
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
                
                query_params = {"exchange": exchange, "symbol": normalized_symbol}
                print(f"执行查询: {query_params}")
                
                result = await db.execute(query, query_params)
                rows = result.fetchall()
                
                print(f"查询结果: {len(rows)}行")
                
                if rows:
                    for row in rows:
                        row_dict = dict(row._mapping)
                        print(f"结果数据: {row_dict}")
                        
                        # 模拟API响应构造
                        data_info = [row_dict]
                        
                        # 计算汇总统计
                        summary_stats = {
                            "total_records": len(data_info),
                            "data_completeness_percent": 100 if data_info else 0,
                            "timeframes_available": 1 if data_info else 0,
                            "earliest_date": None,
                            "latest_date": None,
                            "days_span": 0
                        }
                        
                        # 模拟API响应
                        response = {
                            "success": True,
                            "data": {
                                "data_type": data_type,
                                "exchange": exchange,
                                "symbol": symbol,
                                "query_result": data_info,
                                "total_symbols": len(data_info) if not symbol else 1,
                                "summary": summary_stats
                            }
                        }
                        
                        print(f"API响应: {response}")
                else:
                    print("没有找到数据!")
                    
                    # 额外调试：直接查询看是否有数据
                    debug_query = text("SELECT COUNT(*) as count FROM tick_data WHERE exchange = :exchange AND symbol = :symbol")
                    debug_result = await db.execute(debug_query, query_params)
                    debug_count = debug_result.fetchone()
                    print(f"调试查询结果: {debug_count}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_api_query_flow())