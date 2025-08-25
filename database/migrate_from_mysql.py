#!/usr/bin/env python3
"""
MySQL到SQLite数据迁移脚本

用于将现有MySQL数据迁移到SQLite数据库
适用于从复杂架构向简化架构的迁移
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Any


def migrate_user_data_from_mysql():
    """
    模拟从MySQL迁移用户数据到SQLite
    
    注意：这是一个示例脚本，实际使用时需要：
    1. 安装 pymysql: pip install pymysql
    2. 配置MySQL连接参数
    3. 适配实际的数据结构
    """
    
    print("🔄 开始用户数据迁移...")
    
    # TODO: 实际实现时的MySQL连接代码
    # import pymysql
    # mysql_conn = pymysql.connect(
    #     host='localhost',
    #     user='trademe',
    #     password='trademe123',
    #     database='trademe',
    #     charset='utf8mb4'
    # )
    
    # 连接SQLite数据库
    sqlite_path = "./data/trademe.db"
    if not os.path.exists(sqlite_path):
        print("❌ SQLite数据库不存在，请先运行 setup_database.py")
        return False
    
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()
    
    try:
        # 示例：迁移用户数据
        print("📊 迁移用户基础数据...")
        
        # 这里是示例数据，实际使用时从MySQL查询
        sample_users = [
            {
                'id': 1,
                'username': 'migrated_user_1',
                'email': 'migrated1@example.com',
                'password_hash': 'hashed_password_from_mysql',
                'membership_level': 'premium',
                'email_verified': True,
                'is_active': True,
                'created_at': '2024-01-01 00:00:00'
            },
            {
                'id': 2, 
                'username': 'migrated_user_2',
                'email': 'migrated2@example.com',
                'password_hash': 'hashed_password_from_mysql_2',
                'membership_level': 'basic',
                'email_verified': True,
                'is_active': True,
                'created_at': '2024-01-15 00:00:00'
            }
        ]
        
        # 插入迁移的用户数据
        for user in sample_users:
            sqlite_cursor.execute("""
                INSERT OR REPLACE INTO users (
                    id, username, email, password_hash, membership_level,
                    email_verified, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user['id'], user['username'], user['email'], 
                user['password_hash'], user['membership_level'],
                user['email_verified'], user['is_active'], user['created_at']
            ))
        
        print(f"✅ 已迁移 {len(sample_users)} 个用户")
        
        # 示例：迁移会员订单数据
        print("📊 迁移订单数据...")
        
        sample_orders = [
            {
                'id': 1,
                'user_id': 1,
                'plan_id': 2,
                'order_number': 'ORDER_20240101_001',
                'amount': 19.99,
                'status': 'COMPLETED',
                'created_at': '2024-01-01 10:00:00'
            }
        ]
        
        for order in sample_orders:
            sqlite_cursor.execute("""
                INSERT OR REPLACE INTO orders (
                    id, user_id, plan_id, order_number, amount, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order['id'], order['user_id'], order['plan_id'],
                order['order_number'], order['amount'], order['status'],
                order['created_at']
            ))
        
        print(f"✅ 已迁移 {len(sample_orders)} 个订单")
        
        # 提交事务
        sqlite_conn.commit()
        
        # 验证迁移结果
        sqlite_cursor.execute("SELECT COUNT(*) FROM users")
        user_count = sqlite_cursor.fetchone()[0]
        
        sqlite_cursor.execute("SELECT COUNT(*) FROM orders") 
        order_count = sqlite_cursor.fetchone()[0]
        
        print(f"\n📊 迁移结果统计:")
        print(f"   - 用户总数: {user_count}")
        print(f"   - 订单总数: {order_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据迁移失败: {e}")
        sqlite_conn.rollback()
        return False
        
    finally:
        sqlite_conn.close()


def export_data_to_json(db_path: str = "./data/trademe.db", output_dir: str = "./backup"):
    """
    导出SQLite数据为JSON格式
    用于数据备份和迁移验证
    """
    
    print("📦 导出数据为JSON格式...")
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    os.makedirs(output_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 启用字典形式的行访问
    cursor = conn.cursor()
    
    try:
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        exported_data = {}
        
        for table in tables:
            print(f"   导出表: {table}")
            
            # 查询表数据
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            # 转换为字典列表
            table_data = []
            for row in rows:
                table_data.append(dict(row))
            
            exported_data[table] = table_data
            print(f"     - {len(table_data)} 行数据")
        
        # 保存为JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = os.path.join(output_dir, f"trademe_backup_{timestamp}.json")
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(exported_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ 数据导出完成: {json_file}")
        print(f"📊 文件大小: {os.path.getsize(json_file) / 1024:.1f} KB")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据导出失败: {e}")
        return False
        
    finally:
        conn.close()


def import_data_from_json(json_file: str, db_path: str = "./data/trademe.db"):
    """
    从JSON文件导入数据到SQLite
    用于数据恢复和测试
    """
    
    print(f"📥 从JSON文件导入数据: {json_file}")
    
    if not os.path.exists(json_file):
        print(f"❌ JSON文件不存在: {json_file}")
        return False
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 读取JSON数据
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 导入每个表的数据
        for table_name, rows in data.items():
            if not rows:
                continue
                
            print(f"   导入表: {table_name} ({len(rows)} 行)")
            
            # 生成INSERT语句
            columns = list(rows[0].keys())
            placeholders = ', '.join(['?' for _ in columns])
            
            insert_sql = f"""
                INSERT OR REPLACE INTO {table_name} 
                ({', '.join(columns)}) 
                VALUES ({placeholders})
            """
            
            # 准备数据
            values = []
            for row in rows:
                values.append(tuple(row[col] for col in columns))
            
            # 批量插入
            cursor.executemany(insert_sql, values)
            
        conn.commit()
        print("✅ 数据导入完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据导入失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def main():
    """主函数"""
    print("=" * 50)
    print("    Trademe 数据迁移工具")
    print("=" * 50)
    
    import argparse
    parser = argparse.ArgumentParser(description='Trademe数据迁移工具')
    parser.add_argument('--action', choices=['migrate', 'export', 'import'], 
                       required=True, help='操作类型')
    parser.add_argument('--db-path', default='./data/trademe.db', help='SQLite数据库路径')
    parser.add_argument('--json-file', help='JSON文件路径 (用于import操作)')
    parser.add_argument('--output-dir', default='./backup', help='输出目录 (用于export操作)')
    
    args = parser.parse_args()
    
    if args.action == 'migrate':
        success = migrate_user_data_from_mysql()
    elif args.action == 'export':
        success = export_data_to_json(args.db_path, args.output_dir)
    elif args.action == 'import':
        if not args.json_file:
            print("❌ 导入操作需要指定 --json-file 参数")
            return
        success = import_data_from_json(args.json_file, args.db_path)
    
    if success:
        print("\n🎉 操作完成！")
    else:
        print("\n❌ 操作失败！")


if __name__ == "__main__":
    main()