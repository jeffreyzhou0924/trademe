#!/usr/bin/env python3
"""
调试CSV文件格式
检查pandas实际读取的列名
"""

import pandas as pd
from pathlib import Path

# CSV文件路径
csv_file = Path("/root/trademe/backend/trading-service/data/okx_tick_data/BTC-USDT-SWAP-trades-2024-08-30-final.csv")

print(f"检查文件: {csv_file}")
print(f"文件存在: {csv_file.exists()}")
print(f"文件大小: {csv_file.stat().st_size / 1024 / 1024:.1f} MB")

# 尝试不同编码读取CSV
encodings = ['utf-8', 'gbk', 'latin1']

for encoding in encodings:
    try:
        print(f"\n--- 尝试编码: {encoding} ---")
        df = pd.read_csv(csv_file, encoding=encoding, nrows=5)  # 只读前5行
        
        print(f"成功读取，行数: {len(df)}")
        print(f"列名: {list(df.columns)}")
        print(f"数据类型: {df.dtypes.to_dict()}")
        
        # 显示前几行数据
        print("前3行数据:")
        print(df.head(3))
        
        # 检查是否有我们期望的列
        expected_cols = ['trade_id', 'side', 'size', 'price', 'created_time']
        print(f"\n期望的列: {expected_cols}")
        for col in expected_cols:
            if col in df.columns:
                print(f"✅ 找到列: {col}")
            else:
                print(f"❌ 缺少列: {col}")
                
        break  # 成功读取就退出循环
        
    except Exception as e:
        print(f"❌ 编码 {encoding} 失败: {e}")

print("\n=== 检查完成 ===")