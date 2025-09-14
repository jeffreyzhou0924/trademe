#!/usr/bin/env python3
"""
修复回测表结构 - 添加AI相关字段
解决 "no such column: backtests.ai_session_id" 错误
"""

import asyncio
import sqlite3
import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

from app.database import get_db
from sqlalchemy import text

async def fix_backtest_table_structure():
    """添加缺失的AI相关字段"""
    print("🔧 开始修复回测表结构...")
    
    # 检查现有表结构
    db_path = '/root/trademe/backend/trading-service/data/trademe.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取当前表结构
    cursor.execute("PRAGMA table_info(backtests)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"📋 现有字段: {existing_columns}")
    
    # 定义需要添加的字段
    new_columns = [
        ("ai_session_id", "VARCHAR(100)"),
        ("is_ai_generated", "BOOLEAN DEFAULT 0"),
        ("realtime_task_id", "VARCHAR(100)"),
        ("membership_level", "VARCHAR(20)"),
        ("ai_enhanced_results", "TEXT"),
        ("completed_at", "DATETIME")
    ]
    
    # 添加缺失的字段
    added_count = 0
    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            try:
                sql = f"ALTER TABLE backtests ADD COLUMN {column_name} {column_type}"
                cursor.execute(sql)
                print(f"✅ 添加字段: {column_name} {column_type}")
                added_count += 1
            except Exception as e:
                print(f"❌ 添加字段 {column_name} 失败: {str(e)}")
        else:
            print(f"⚠️ 字段已存在: {column_name}")
    
    # 创建索引
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_backtests_ai_session_id ON backtests(ai_session_id)",
        "CREATE INDEX IF NOT EXISTS idx_backtests_is_ai_generated ON backtests(is_ai_generated)",  
        "CREATE INDEX IF NOT EXISTS idx_backtests_realtime_task_id ON backtests(realtime_task_id)"
    ]
    
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            print(f"✅ 创建索引成功")
        except Exception as e:
            print(f"⚠️ 创建索引: {str(e)}")
    
    # 检查ai_backtest_tasks表是否存在，如果不存在则创建
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_backtest_tasks'")
    if not cursor.fetchone():
        print("📋 创建ai_backtest_tasks表...")
        create_table_sql = """
        CREATE TABLE ai_backtest_tasks (
            id INTEGER NOT NULL,
            task_id VARCHAR(100) NOT NULL,
            user_id INTEGER NOT NULL,
            ai_session_id VARCHAR(100),
            strategy_id INTEGER,
            backtest_id INTEGER,
            strategy_name VARCHAR(200),
            strategy_code TEXT NOT NULL,
            config_data TEXT,
            membership_level VARCHAR(20) NOT NULL,
            status VARCHAR(20) DEFAULT 'running',
            progress INTEGER DEFAULT 0,
            current_step VARCHAR(200),
            logs TEXT,
            error_message TEXT,
            results_data TEXT,
            ai_score NUMERIC(5, 2),
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE (task_id),
            FOREIGN KEY(strategy_id) REFERENCES strategies (id),
            FOREIGN KEY(backtest_id) REFERENCES backtests (id)
        );
        """
        cursor.execute(create_table_sql)
        
        # 创建索引
        ai_task_indexes = [
            "CREATE INDEX ix_ai_backtest_tasks_id ON ai_backtest_tasks (id)",
            "CREATE INDEX ix_ai_backtest_tasks_task_id ON ai_backtest_tasks (task_id)",
            "CREATE INDEX ix_ai_backtest_tasks_user_id ON ai_backtest_tasks (user_id)",
            "CREATE INDEX ix_ai_backtest_tasks_ai_session_id ON ai_backtest_tasks (ai_session_id)",
            "CREATE INDEX ix_ai_backtest_tasks_status ON ai_backtest_tasks (status)"
        ]
        
        for idx_sql in ai_task_indexes:
            cursor.execute(idx_sql)
        
        print("✅ ai_backtest_tasks表创建成功")
    else:
        print("⚠️ ai_backtest_tasks表已存在")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 表结构修复完成！")
    print(f"📊 总计添加了 {added_count} 个字段")
    print(f"✅ 现在可以正常进行AI回测了")
    
    # 验证修复结果
    print("\n🔍 验证表结构...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(backtests)")
    final_columns = [row[1] for row in cursor.fetchall()]
    print(f"📋 修复后字段: {final_columns}")
    
    cursor.execute("PRAGMA table_info(ai_backtest_tasks)")
    ai_task_columns = [row[1] for row in cursor.fetchall()]
    print(f"📋 AI任务表字段: {ai_task_columns}")
    conn.close()

if __name__ == "__main__":
    asyncio.run(fix_backtest_table_structure())