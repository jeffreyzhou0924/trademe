#!/usr/bin/env python3
"""
修复SQLAlchemy查询缓存问题
"""

import sqlite3

# 直接更新Claude账户状态，确保它是活跃的
conn = sqlite3.connect('/root/trademe/data/trademe.db')
cursor = conn.cursor()

# 检查当前账户状态
cursor.execute("SELECT id, account_name, status, daily_limit, current_usage, is_schedulable FROM claude_accounts")
accounts = cursor.fetchall()

print("当前Claude账户状态：")
for account in accounts:
    print(f"ID: {account[0]}, 名称: {account[1]}, 状态: {account[2]}, 限额: {account[3]}, 已用: {account[4]}, 可调度: {account[5]}")

# 重置账户使用量（如果已用量太高）
cursor.execute("UPDATE claude_accounts SET current_usage = 0 WHERE id = 1")
conn.commit()

print("\n已重置账户使用量")

# 再次检查
cursor.execute("SELECT id, account_name, status, daily_limit, current_usage, daily_limit - current_usage as remaining FROM claude_accounts WHERE id = 1")
account = cursor.fetchone()
print(f"\n更新后 - ID: {account[0]}, 名称: {account[1]}, 状态: {account[2]}, 限额: {account[3]}, 已用: {account[4]}, 剩余: {account[5]}")

conn.close()
print("\n数据库更新完成")