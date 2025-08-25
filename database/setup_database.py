#!/usr/bin/env python3
"""
Trademe 数据库初始化脚本

用于创建和初始化SQLite数据库
适用于开发环境和生产环境部署
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime


def setup_database(db_path: str = "./data/trademe.db", sql_file: str = "./init_sqlite.sql"):
    """
    设置数据库
    
    Args:
        db_path: 数据库文件路径
        sql_file: SQL初始化文件路径
    """
    print("🚀 开始初始化Trademe数据库...")
    
    # 确保数据目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        print(f"✅ 数据目录已创建: {db_dir}")
    
    # 检查SQL文件是否存在
    if not os.path.exists(sql_file):
        print(f"❌ SQL文件不存在: {sql_file}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
        
        print(f"📊 已连接到数据库: {db_path}")
        
        # 读取并执行SQL文件
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 分批执行SQL语句
        cursor = conn.cursor()
        try:
            cursor.executescript(sql_script)
            conn.commit()
            print("✅ SQL脚本执行成功")
        except Exception as e:
            print(f"❌ SQL脚本执行失败: {e}")
            conn.rollback()
            return False
        
        # 验证数据库结构
        print("\n📋 验证数据库结构...")
        tables = get_table_info(cursor)
        
        if tables:
            print(f"✅ 数据库初始化成功！共创建 {len(tables)} 个表:")
            for table_name, row_count in tables:
                print(f"   - {table_name}: {row_count} 行数据")
        else:
            print("❌ 数据库验证失败")
            return False
        
        # 创建测试用户 (仅开发环境)
        if "development" in os.environ.get("ENVIRONMENT", "development"):
            create_test_data(cursor)
            conn.commit()
            print("🧪 测试数据创建完成")
        
        conn.close()
        print(f"\n🎉 数据库初始化完成！")
        print(f"📍 数据库位置: {os.path.abspath(db_path)}")
        print(f"📊 数据库大小: {get_file_size(db_path)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


def get_table_info(cursor):
    """获取表信息"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cursor.fetchall()
    
    table_info = []
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        table_info.append((table_name, row_count))
    
    return table_info


def create_test_data(cursor):
    """创建测试数据 (仅开发环境)"""
    print("🧪 创建测试数据...")
    
    # 创建测试用户
    test_users = [
        (1, 'admin', 'admin@trademe.com', 'hashed_password_123', None, None, None, 'premium', None, True, True),
        (2, 'testuser', 'test@trademe.com', 'hashed_password_456', None, None, None, 'basic', None, True, True),
        (3, 'demo_trader', 'demo@trademe.com', 'hashed_password_789', None, None, None, 'premium', None, True, True)
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO users (
            id, username, email, password_hash, google_id, phone, avatar_url, 
            membership_level, membership_expires_at, email_verified, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_users)
    
    # 创建测试策略
    test_strategies = [
        (1, 1, 'EMA交叉策略', '基于EMA均线交叉的简单策略', 
         '''# EMA交叉策略示例
def strategy(data):
    ema_short = data.ema(12)
    ema_long = data.ema(26)
    
    if ema_short[-1] > ema_long[-1] and ema_short[-2] <= ema_long[-2]:
        return "BUY"
    elif ema_short[-1] < ema_long[-1] and ema_short[-2] >= ema_long[-2]:
        return "SELL"
    
    return "HOLD"
''', '{"ema_short": 12, "ema_long": 26, "timeframe": "1h"}', True, False, 85.5),
        
        (2, 1, 'RSI超买超卖策略', '基于RSI指标的反转策略', 
         '''# RSI策略示例
def strategy(data):
    rsi = data.rsi(14)
    
    if rsi[-1] < 30:
        return "BUY"  # 超卖买入
    elif rsi[-1] > 70:
        return "SELL"  # 超买卖出
    
    return "HOLD"
''', '{"rsi_period": 14, "oversold": 30, "overbought": 70}', True, True, 72.3),
        
        (3, 2, '布林带突破策略', '基于布林带的突破策略', 
         '''# 布林带策略示例
def strategy(data):
    bb_upper, bb_middle, bb_lower = data.bollinger_bands(20, 2)
    price = data.close[-1]
    
    if price > bb_upper[-1]:
        return "SELL"  # 突破上轨卖出
    elif price < bb_lower[-1]:
        return "BUY"   # 突破下轨买入
    
    return "HOLD"
''', '{"period": 20, "std_dev": 2}', True, False, 68.7)
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO strategies (
            id, user_id, name, description, code, parameters, 
            is_active, is_public, performance_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_strategies)
    
    # 创建测试API密钥
    test_api_keys = [
        (1, 1, 'binance', 'test_api_key_1', 'encrypted_secret_1', None, True),
        (2, 2, 'okx', 'test_api_key_2', 'encrypted_secret_2', 'test_passphrase', True),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO api_keys (
            id, user_id, exchange, api_key, secret_key, passphrase, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, test_api_keys)
    
    # 插入一些示例市场数据
    sample_market_data = [
        ('binance', 'BTC/USDT', '1h', 50000.0, 50500.0, 49800.0, 50200.0, 1250.5, '2024-01-01 00:00:00'),
        ('binance', 'BTC/USDT', '1h', 50200.0, 50800.0, 50100.0, 50600.0, 1180.3, '2024-01-01 01:00:00'),
        ('binance', 'ETH/USDT', '1h', 3000.0, 3050.0, 2980.0, 3020.0, 850.2, '2024-01-01 00:00:00'),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO market_data (
            exchange, symbol, timeframe, open_price, high_price, low_price, 
            close_price, volume, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_market_data)
    
    print("   - 创建了3个测试用户")
    print("   - 创建了3个示例策略")
    print("   - 创建了2个测试API密钥")
    print("   - 插入了示例市场数据")


def get_file_size(file_path):
    """获取文件大小的友好显示"""
    size = os.path.getsize(file_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def check_database_health(db_path: str):
    """检查数据库健康状态"""
    print("\n🔍 检查数据库健康状态...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查数据库完整性
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        
        if integrity == "ok":
            print("✅ 数据库完整性检查通过")
        else:
            print(f"❌ 数据库完整性检查失败: {integrity}")
        
        # 检查外键约束
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        
        if not fk_violations:
            print("✅ 外键约束检查通过")
        else:
            print(f"❌ 发现外键约束违规: {len(fk_violations)} 个")
        
        # 检查WAL模式
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        print(f"📊 日志模式: {journal_mode}")
        
        # 获取数据库统计信息
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
        index_count = cursor.fetchone()[0]
        
        print(f"📊 数据库统计: {table_count} 个表, {index_count} 个索引")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库健康检查失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("    Trademe 数据库初始化工具")
    print("=" * 50)
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='Trademe数据库初始化工具')
    parser.add_argument('--db-path', default='./data/trademe.db', help='数据库文件路径')
    parser.add_argument('--sql-file', default='./init_sqlite.sql', help='SQL初始化文件路径')
    parser.add_argument('--check-only', action='store_true', help='仅检查数据库健康状态')
    parser.add_argument('--force', action='store_true', help='强制重新创建数据库')
    
    args = parser.parse_args()
    
    # 如果只是检查数据库
    if args.check_only:
        if os.path.exists(args.db_path):
            check_database_health(args.db_path)
        else:
            print(f"❌ 数据库文件不存在: {args.db_path}")
        return
    
    # 检查是否需要强制重新创建
    if os.path.exists(args.db_path) and not args.force:
        print(f"⚠️  数据库文件已存在: {args.db_path}")
        response = input("是否要重新创建数据库? (y/N): ")
        if response.lower() != 'y':
            print("取消操作")
            return
        
        # 备份现有数据库
        backup_path = f"{args.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(args.db_path, backup_path)
        print(f"📦 已备份现有数据库到: {backup_path}")
    
    # 执行数据库初始化
    success = setup_database(args.db_path, args.sql_file)
    
    if success:
        # 检查数据库健康状态
        check_database_health(args.db_path)
        print("\n🎉 数据库初始化完成！")
        print("\n📋 下一步操作:")
        print("   1. 启动 trading-service: cd backend/trading-service && python -m app.main")
        print("   2. 访问 API 文档: http://localhost:8001/docs")
        print("   3. 检查数据库: python setup_database.py --check-only")
    else:
        print("\n❌ 数据库初始化失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()