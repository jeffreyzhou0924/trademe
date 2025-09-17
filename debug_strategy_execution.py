#!/usr/bin/env python3
"""
策略执行过程调试脚本
逐步分析MA策略的计算过程
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import json

def get_market_data():
    """获取市场数据"""
    conn = sqlite3.connect('data/trademe.db')

    query = """
    SELECT timestamp, open_price, high_price, low_price, close_price, volume
    FROM market_data
    WHERE symbol = 'BTC-USDT-SWAP'
    AND exchange = 'okx'
    AND timeframe = '1h'
    AND timestamp >= '2025-07-01 00:00:00'
    AND timestamp <= '2025-08-31 23:59:59'
    ORDER BY timestamp ASC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # 转换数据类型
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['open'] = df['open_price'].astype(float)
    df['high'] = df['high_price'].astype(float)
    df['low'] = df['low_price'].astype(float)
    df['close'] = df['close_price'].astype(float)
    df['volume'] = df['volume'].astype(float)

    return df

def calculate_ma(series, period):
    """计算移动平均线"""
    return series.rolling(window=period).mean()

def simulate_strategy_execution(df, debug=True):
    """模拟策略执行过程"""
    print(f"📊 开始模拟策略执行...")
    print(f"数据范围: {df['timestamp'].min()} 到 {df['timestamp'].max()}")
    print(f"数据点数: {len(df)}")

    # 计算技术指标
    df['ma5'] = calculate_ma(df['close'], 5)
    df['ma10'] = calculate_ma(df['close'], 10)

    # 策略状态
    position_status = None
    entry_price = None
    trades = []

    # 初始资金
    initial_capital = 10000.0
    cash_balance = initial_capital
    position_size = 0.0
    portfolio_value = initial_capital

    print(f"\n🔄 开始逐行执行策略...")

    for i in range(20, len(df)):  # 从第20行开始，确保MA有足够数据
        row = df.iloc[i]
        timestamp = row['timestamp']
        current_price = row['close']
        current_ma5 = row['ma5']
        current_ma10 = row['ma10']

        # 获取前一个时间点的MA值
        prev_ma5 = df.iloc[i-1]['ma5']
        prev_ma10 = df.iloc[i-1]['ma10']

        # 检查是否可以计算（避免NaN）
        if pd.isna(current_ma5) or pd.isna(current_ma10) or pd.isna(prev_ma5) or pd.isna(prev_ma10):
            continue

        # 金叉检测
        golden_cross = prev_ma5 <= prev_ma10 and current_ma5 > current_ma10
        death_cross = prev_ma5 >= prev_ma10 and current_ma5 < current_ma10

        signal_generated = False

        # 金叉信号处理
        if golden_cross and position_status != 'long':
            position_size = (cash_balance * 0.05) / current_price  # 5%仓位
            cash_balance -= position_size * current_price
            position_status = 'long'
            entry_price = current_price

            trade = {
                'timestamp': timestamp.isoformat(),
                'type': 'entry',
                'side': 'buy',
                'price': current_price,
                'quantity': position_size,
                'reason': 'MA金叉买入',
                'ma5': current_ma5,
                'ma10': current_ma10,
                'cash_balance': cash_balance,
                'portfolio_value': cash_balance + position_size * current_price
            }
            trades.append(trade)
            signal_generated = True

            if debug and len(trades) <= 10:  # 只打印前10个信号
                print(f"🟢 {timestamp.strftime('%Y-%m-%d %H:%M')} 金叉买入: 价格={current_price:.2f}, MA5={current_ma5:.2f}, MA10={current_ma10:.2f}")

        # 死叉信号处理
        elif death_cross and position_status == 'long':
            # 卖出所有持仓
            cash_balance += position_size * current_price
            pnl = (current_price - entry_price) * position_size

            trade = {
                'timestamp': timestamp.isoformat(),
                'type': 'exit',
                'side': 'sell',
                'price': current_price,
                'quantity': position_size,
                'reason': 'MA死叉卖出',
                'pnl': pnl,
                'entry_price': entry_price,
                'ma5': current_ma5,
                'ma10': current_ma10,
                'cash_balance': cash_balance,
                'portfolio_value': cash_balance
            }
            trades.append(trade)

            position_size = 0.0
            position_status = None
            entry_price = None
            signal_generated = True

            if debug and len(trades) <= 10:
                print(f"🔴 {timestamp.strftime('%Y-%m-%d %H:%M')} 死叉卖出: 价格={current_price:.2f}, 盈亏={pnl:.2f}, MA5={current_ma5:.2f}, MA10={current_ma10:.2f}")

        # 更新资产价值
        if position_status == 'long':
            portfolio_value = cash_balance + position_size * current_price
        else:
            portfolio_value = cash_balance

    # 计算最终指标
    final_value = portfolio_value
    total_return = (final_value - initial_capital) / initial_capital * 100

    entry_trades = [t for t in trades if t['type'] == 'entry']
    exit_trades = [t for t in trades if t['type'] == 'exit']

    profitable_trades = len([t for t in exit_trades if t.get('pnl', 0) > 0])
    win_rate = (profitable_trades / len(exit_trades) * 100) if exit_trades else 0

    # 计算夏普比率 (简化)
    if exit_trades:
        returns = [t.get('pnl', 0) / initial_capital for t in exit_trades]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0

    # 计算最大回撤 (简化)
    if exit_trades:
        cumulative_pnl = np.cumsum([t.get('pnl', 0) for t in exit_trades])
        peak = np.maximum.accumulate(cumulative_pnl)
        drawdown = (peak - cumulative_pnl) / initial_capital * 100
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
    else:
        max_drawdown = 0

    results = {
        'initial_capital': initial_capital,
        'final_value': final_value,
        'total_return': total_return,
        'total_trades': len(exit_trades),
        'win_rate': win_rate,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'trades': trades
    }

    return results

def create_execution_hash(results):
    """创建执行过程的哈希值"""
    # 提取关键的执行数据
    execution_data = {
        'trade_count': len(results['trades']),
        'trade_details': []
    }

    for trade in results['trades']:
        execution_data['trade_details'].append({
            'timestamp': trade['timestamp'],
            'type': trade['type'],
            'price': round(trade['price'], 6),
            'quantity': round(trade['quantity'], 8),
            'ma5': round(trade['ma5'], 6),
            'ma10': round(trade['ma10'], 6)
        })

    # 转换为字符串并计算哈希
    import hashlib
    execution_str = json.dumps(execution_data, sort_keys=True)
    execution_hash = hashlib.md5(execution_str.encode()).hexdigest()

    return execution_hash, execution_data

def main():
    """主函数"""
    print("🔬 策略执行过程调试分析")
    print("=" * 50)

    # 获取市场数据
    print("📥 加载市场数据...")
    df = get_market_data()

    # 运行多次模拟
    print("\n🧪 运行3次策略模拟...")

    results_list = []
    for i in range(3):
        print(f"\n--- 第{i+1}次执行 ---")
        results = simulate_strategy_execution(df, debug=(i==0))  # 只在第一次显示详细调试

        execution_hash, execution_data = create_execution_hash(results)

        print(f"📊 结果摘要:")
        print(f"   总收益率: {results['total_return']:.4f}%")
        print(f"   交易次数: {results['total_trades']}")
        print(f"   胜率: {results['win_rate']:.2f}%")
        print(f"   夏普比率: {results['sharpe_ratio']:.4f}")
        print(f"   最大回撤: {results['max_drawdown']:.4f}%")
        print(f"   执行哈希: {execution_hash}")

        results_list.append({
            'execution': i+1,
            'results': results,
            'hash': execution_hash,
            'execution_data': execution_data
        })

    # 比较结果
    print(f"\n🔍 执行一致性分析:")
    print("=" * 30)

    hashes = [r['hash'] for r in results_list]
    unique_hashes = set(hashes)

    if len(unique_hashes) == 1:
        print("✅ 所有执行的哈希值相同，策略执行过程完全一致!")
        print(f"统一哈希值: {hashes[0]}")
    else:
        print("❌ 发现执行过程不一致!")
        for i, r in enumerate(results_list):
            print(f"第{i+1}次执行哈希: {r['hash']}")

    # 详细比较关键指标
    metrics = ['total_return', 'total_trades', 'win_rate', 'sharpe_ratio', 'max_drawdown']
    print(f"\n📊 关键指标对比:")

    for metric in metrics:
        values = [r['results'][metric] for r in results_list]
        unique_values = set(f"{v:.8f}" for v in values)

        if len(unique_values) == 1:
            print(f"✅ {metric}: 一致 ({values[0]:.8f})")
        else:
            print(f"❌ {metric}: 不一致 {[f'{v:.8f}' for v in values]}")

    # 保存详细数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"/tmp/strategy_execution_debug_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(results_list, f, indent=2, default=str)
    print(f"\n📝 详细执行数据保存到: {filename}")

if __name__ == "__main__":
    main()