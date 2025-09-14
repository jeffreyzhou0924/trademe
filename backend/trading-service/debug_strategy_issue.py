#!/usr/bin/env python3
"""
调试用户报告的具体策略ID问题
策略ID: strategy_08cba7cc-d985-4c16-9a51-7c29aa52ed8b_1757843815700
"""

import asyncio
import json
from datetime import datetime
from loguru import logger

async def check_strategy_and_backtest():
    """检查用户策略和回测状态"""
    from app.database import get_db
    from app.models.strategy import Strategy
    from app.models.backtest import Backtest
    from sqlalchemy import select, text, desc
    
    strategy_id_part = "08cba7cc-d985-4c16-9a51-7c29aa52ed8b"
    timestamp_part = "1757843815700"
    full_strategy_id = f"strategy_{strategy_id_part}_{timestamp_part}"
    
    print(f"🔍 调试策略ID问题")
    print(f"完整策略ID: {full_strategy_id}")
    print(f"UUID部分: {strategy_id_part}")
    print(f"时间戳部分: {timestamp_part}")
    print("=" * 60)
    
    async for db in get_db():
        try:
            # 1. 查找策略记录
            print("📋 1. 查找策略记录...")
            
            # 尝试多种查找方式
            search_patterns = [
                full_strategy_id,
                strategy_id_part,
                f"%{strategy_id_part}%",
                f"%{timestamp_part}%"
            ]
            
            for i, pattern in enumerate(search_patterns):
                if pattern.startswith("%") and pattern.endswith("%"):
                    query = select(Strategy).where(Strategy.id.like(pattern))
                    search_type = f"LIKE模糊搜索 ({pattern})"
                else:
                    query = select(Strategy).where(Strategy.id == pattern)
                    search_type = f"精确匹配 ({pattern})"
                
                result = await db.execute(query)
                strategies = result.scalars().all()
                
                print(f"   {i+1}. {search_type}: 找到 {len(strategies)} 个策略")
                
                for strategy in strategies:
                    print(f"      ID: {strategy.id}")
                    print(f"      名称: {strategy.name}")
                    print(f"      用户ID: {strategy.user_id}")
                    print(f"      创建时间: {strategy.created_at}")
                    print(f"      代码长度: {len(strategy.code) if strategy.code else 0} 字符")
                    
                    # 检查这个策略的回测记录
                    backtest_query = select(Backtest).where(Backtest.strategy_id == strategy.id).order_by(desc(Backtest.created_at))
                    backtest_result = await db.execute(backtest_query)
                    backtests = backtest_result.scalars().all()
                    
                    print(f"      相关回测: {len(backtests)} 个")
                    for j, bt in enumerate(backtests[:3]):  # 只显示最近3个
                        print(f"        回测{j+1}: ID={bt.id}, 状态={bt.status}, 时间={bt.created_at}")
                        # Backtest模型没有error_message字段，只有AIBacktestTask有
                        if hasattr(bt, 'results') and bt.results:
                            print(f"          结果摘要: {bt.results[:100]}...")
                    print()
            
            # 2. 查找最近的策略记录
            print("📈 2. 查找用户6的最近策略...")
            recent_query = select(Strategy).where(Strategy.user_id == 6).order_by(desc(Strategy.created_at)).limit(10)
            recent_result = await db.execute(recent_query)
            recent_strategies = recent_result.scalars().all()
            
            print(f"   用户6最近的 {len(recent_strategies)} 个策略:")
            for i, strategy in enumerate(recent_strategies):
                print(f"   {i+1}. {strategy.id} | {strategy.name} | {strategy.created_at}")
            
            # 3. 查找最近的回测记录
            print("\n🔬 3. 查找用户6的最近回测记录...")
            recent_backtest_query = select(Backtest).where(Backtest.user_id == 6).order_by(desc(Backtest.created_at)).limit(5)
            recent_backtest_result = await db.execute(recent_backtest_query)
            recent_backtests = recent_backtest_result.scalars().all()
            
            print(f"   用户6最近的 {len(recent_backtests)} 个回测:")
            for i, bt in enumerate(recent_backtests):
                print(f"   {i+1}. 回测ID: {bt.id}")
                print(f"       策略ID: {bt.strategy_id}")  
                print(f"       状态: {bt.status}")
                print(f"       时间范围: {bt.start_date} ~ {bt.end_date}")
                print(f"       创建时间: {bt.created_at}")
                # Backtest模型没有error_message字段
                if hasattr(bt, 'results') and bt.results:
                    print(f"       结果摘要: {bt.results[:100]}...")
                print()
            
            # 4. 检查时间戳的含义
            print("🕐 4. 分析时间戳...")
            try:
                # 时间戳可能是毫秒级
                timestamp_ms = int(timestamp_part)
                timestamp_s = timestamp_ms / 1000
                dt = datetime.fromtimestamp(timestamp_s)
                print(f"   时间戳 {timestamp_part} 转换为日期: {dt}")
            except:
                print(f"   无法解析时间戳: {timestamp_part}")
            
            # 5. 查看AIBacktestTask表中的任务记录
            print("\n⚡ 5. 查看AI回测任务记录...")
            from app.models.backtest import AIBacktestTask
            
            # 查找策略ID相关的AI任务
            ai_task_query = select(AIBacktestTask).where(
                AIBacktestTask.strategy_code.like(f"%{strategy_id_part}%")
            ).order_by(desc(AIBacktestTask.created_at)).limit(10)
            ai_task_result = await db.execute(ai_task_query)
            ai_tasks = ai_task_result.scalars().all()
            
            print(f"   找到包含UUID部分的AI任务: {len(ai_tasks)} 个")
            for i, task in enumerate(ai_tasks):
                print(f"   任务{i+1}: task_id={task.task_id}")
                print(f"         strategy_name={task.strategy_name}")
                print(f"         status={task.status}")
                print(f"         progress={task.progress}%")
                print(f"         ai_session_id={task.ai_session_id}")
                print(f"         created_at={task.created_at}")
                if task.error_message:
                    print(f"         错误: {task.error_message}")
                print()
            
            # 6. 查看当前活跃的内存中回测任务
            print("⚡ 6. 查看当前内存中活跃回测任务...")
            from app.api.v1.realtime_backtest import active_backtests
            print(f"   当前活跃任务数: {len(active_backtests)}")
            for task_id, status in active_backtests.items():
                print(f"   任务ID: {task_id}")
                print(f"   状态: {status.status}")
                print(f"   进度: {status.progress}%")
                print(f"   当前步骤: {status.current_step}")
                if hasattr(status, 'ai_session_id'):
                    print(f"   AI会话ID: {status.ai_session_id}")
                print()
            
            break
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(check_strategy_and_backtest())