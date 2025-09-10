#!/usr/bin/env python3
"""
修复Tick数据表的schema问题
解决NOT NULL constraint failed: tick_data.id的问题
"""

import sqlite3
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

def fix_tick_data_schema():
    """修复tick_data表的ID字段"""
    db_path = '/root/trademe/data/trademe.db'
    
    print("🔧 开始修复tick_data表schema...")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查当前tick_data表的结构
        cursor.execute("PRAGMA table_info(tick_data)")
        columns = cursor.fetchall()
        print(f"📋 当前tick_data表结构:")
        for col in columns:
            print(f"  - {col[1]} {col[2]} {'PRIMARY KEY' if col[5] else ''} {'NOT NULL' if col[3] else 'NULL'}")
        
        # 删除旧表（如果有数据需要备份的话先备份）
        cursor.execute("SELECT COUNT(*) FROM tick_data")
        record_count = cursor.fetchone()[0]
        
        if record_count > 0:
            print(f"⚠️ 表中有 {record_count} 条记录，需要备份")
            # 创建备份表
            cursor.execute("""
            CREATE TABLE tick_data_backup AS 
            SELECT * FROM tick_data
            """)
            print("✅ 数据已备份到 tick_data_backup")
        
        # 删除现有表
        cursor.execute("DROP TABLE IF EXISTS tick_data")
        print("🗑️ 删除了旧的tick_data表")
        
        # 重新创建表，使用正确的schema
        cursor.execute("""
        CREATE TABLE tick_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange VARCHAR(50) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            price DECIMAL(20, 8) NOT NULL,
            volume DECIMAL(18, 8) NOT NULL,
            side VARCHAR(4) NOT NULL,
            trade_id VARCHAR(50),
            timestamp BIGINT NOT NULL,
            best_bid DECIMAL(20, 8),
            best_ask DECIMAL(20, 8),
            bid_size DECIMAL(18, 8),
            ask_size DECIMAL(18, 8),
            is_validated BOOLEAN DEFAULT 0,
            data_source VARCHAR(50),
            sequence_number BIGINT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("✅ 重新创建了tick_data表")
        
        # 创建索引
        cursor.execute("""
        CREATE INDEX idx_tick_data_symbol_time 
        ON tick_data(exchange, symbol, timestamp)
        """)
        
        cursor.execute("""
        CREATE INDEX idx_tick_data_time_range 
        ON tick_data(timestamp, exchange)
        """)
        print("✅ 创建了性能优化索引")
        
        # 如果有备份数据，恢复数据（排除id字段让其自动生成）
        if record_count > 0:
            cursor.execute("""
            INSERT INTO tick_data (
                exchange, symbol, price, volume, side, trade_id, timestamp,
                best_bid, best_ask, bid_size, ask_size, is_validated, 
                data_source, sequence_number, created_at
            )
            SELECT 
                exchange, symbol, price, volume, side, trade_id, timestamp,
                best_bid, best_ask, bid_size, ask_size, is_validated, 
                data_source, sequence_number, created_at
            FROM tick_data_backup
            """)
            
            restored_count = cursor.rowcount
            print(f"✅ 恢复了 {restored_count} 条记录")
            
            # 删除备份表
            cursor.execute("DROP TABLE tick_data_backup")
            print("🗑️ 删除了备份表")
        
        # 验证新表结构
        cursor.execute("PRAGMA table_info(tick_data)")
        columns = cursor.fetchall()
        print(f"\n📋 修复后的tick_data表结构:")
        for col in columns:
            print(f"  - {col[1]} {col[2]} {'PRIMARY KEY' if col[5] else ''} {'NOT NULL' if col[3] else 'NULL'}")
        
        conn.commit()
        print("\n🎉 tick_data表schema修复完成!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 修复过程中发生错误: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_tick_data_schema()