#!/usr/bin/env python3
"""
检查回测数据和错误问题
"""

import asyncio
from app.database import get_db
from sqlalchemy import text

async def check_backtest_issues():
    async for db in get_db():
        try:
            print('🔍 检查BTC K线数据和回测错误...')
            print('=' * 60)
            
            # 1. 检查BTC数据概览
            result = await db.execute(text('''
                SELECT 
                    symbol,
                    timeframe,
                    exchange,
                    COUNT(*) as count,
                    MIN(timestamp) as min_date,
                    MAX(timestamp) as max_date
                FROM market_data 
                WHERE symbol LIKE '%BTC%' 
                GROUP BY symbol, timeframe, exchange
                ORDER BY count DESC
                LIMIT 5
            '''))
            
            data_summary = result.fetchall()
            print('📊 BTC K线数据概览:')
            for row in data_summary:
                print(f'  {row.symbol} ({row.timeframe}) - {row.exchange}')
                print(f'    数据量: {row.count:,} 条')
                print(f'    时间范围: {row.min_date} ~ {row.max_date}')
            
            # 2. 检查指定时间范围的数据
            result = await db.execute(text('''
                SELECT 
                    symbol,
                    timeframe,
                    COUNT(*) as count,
                    MIN(timestamp) as start_date,
                    MAX(timestamp) as end_date
                FROM market_data 
                WHERE symbol LIKE '%BTC%' 
                AND timeframe = '1h'
                AND timestamp >= '2025-07-01' 
                AND timestamp <= '2025-08-31'
                GROUP BY symbol, timeframe
                ORDER BY count DESC
            '''))
            
            specific_data = result.fetchall()
            print(f'\n🗓️ 2025年7-8月BTC 1小时数据:')
            for row in specific_data:
                print(f'  {row.symbol}: {row.count:,} 条 ({row.start_date} ~ {row.end_date})')
            
            # 3. 检查最近的回测记录
            result = await db.execute(text('''
                SELECT 
                    id,
                    user_id,
                    symbol,
                    start_date,
                    end_date,
                    status,
                    error_message,
                    created_at,
                    strategy_code
                FROM backtests 
                ORDER BY created_at DESC 
                LIMIT 3
            '''))
            
            recent_backtests = result.fetchall()
            print(f'\n🔍 最近的回测记录:')
            for bt in recent_backtests:
                status_emoji = '✅' if bt.status == 'completed' else '❌' if bt.status == 'failed' else '🔄'
                print(f'{status_emoji} 回测ID: {bt.id}')
                print(f'   交易对: {bt.symbol}')
                print(f'   时间范围: {bt.start_date} ~ {bt.end_date}')
                print(f'   状态: {bt.status}')
                print(f'   创建时间: {bt.created_at}')
                
                if bt.error_message:
                    print(f'   ❌ 错误信息: {bt.error_message}')
                
                if bt.strategy_code:
                    code_preview = bt.strategy_code[:200] if len(bt.strategy_code) > 200 else bt.strategy_code
                    print(f'   📝 策略代码预览: {code_preview}...')
                
                print('-' * 50)
            
            # 4. 检查特定格式的数据样本
            result = await db.execute(text('''
                SELECT 
                    symbol,
                    timestamp,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume
                FROM market_data 
                WHERE symbol LIKE '%BTC%' 
                AND timeframe = '1h'
                AND timestamp BETWEEN '2025-07-01' AND '2025-07-03'
                ORDER BY timestamp
                LIMIT 5
            '''))
            
            sample_data = result.fetchall()
            print(f'\n📈 数据样本 (2025年7月前几天):')
            for row in sample_data:
                print(f'  {row.timestamp}: O:{row.open_price} H:{row.high_price} L:{row.low_price} C:{row.close_price} V:{row.volume}')
            
            break
        finally:
            await db.close()

asyncio.run(check_backtest_issues())