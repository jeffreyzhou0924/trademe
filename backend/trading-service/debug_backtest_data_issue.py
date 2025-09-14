#!/usr/bin/env python3
"""
回测数据问题分析脚本

分析用户反映的问题：
1. 用户选择币安(Binance)数据进行回测
2. 数据库中只有OKX的BTC/USDT数据  
3. 系统却能返回回测结果，说明可能使用了模拟数据
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta

def analyze_database_data():
    """分析数据库中的市场数据"""
    print("=== 数据库市场数据分析 ===")
    
    # 检查主数据库
    try:
        conn = sqlite3.connect('/root/trademe/data/trademe.db')
        cursor = conn.cursor()
        
        # 查询所有交易所和交易对的数据
        cursor.execute("""
            SELECT exchange, symbol, 
                   COUNT(*) as record_count,
                   MIN(timestamp) as earliest_date,
                   MAX(timestamp) as latest_date
            FROM market_data 
            GROUP BY exchange, symbol
            ORDER BY exchange, symbol
        """)
        
        results = cursor.fetchall()
        
        if not results:
            print("❌ 主数据库中没有市场数据")
        else:
            print("主数据库市场数据:")
            for row in results:
                exchange, symbol, count, earliest, latest = row
                print(f"  {exchange} - {symbol}: {count:,} 条记录")
                if earliest and latest:
                    earliest_dt = datetime.fromtimestamp(earliest/1000)
                    latest_dt = datetime.fromtimestamp(latest/1000)
                    print(f"    时间范围: {earliest_dt.date()} 到 {latest_dt.date()}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 查询主数据库失败: {e}")
    
    # 检查交易服务数据库
    try:
        conn = sqlite3.connect('/root/trademe/backend/trading-service/data/trademe.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT exchange, symbol, 
                   COUNT(*) as record_count,
                   MIN(timestamp) as earliest_date,
                   MAX(timestamp) as latest_date
            FROM market_data 
            GROUP BY exchange, symbol
            ORDER BY exchange, symbol
        """)
        
        results = cursor.fetchall()
        
        if not results:
            print("❌ 交易服务数据库中没有市场数据")
        else:
            print("\n交易服务数据库市场数据:")
            for row in results:
                exchange, symbol, count, earliest, latest = row
                print(f"  {exchange} - {symbol}: {count:,} 条记录")
                if earliest and latest:
                    earliest_dt = datetime.fromtimestamp(earliest/1000)
                    latest_dt = datetime.fromtimestamp(latest/1000)
                    print(f"    时间范围: {earliest_dt.date()} 到 {latest_dt.date()}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 查询交易服务数据库失败: {e}")

def analyze_backtest_code_issues():
    """分析回测代码中的问题"""
    print("\n=== 回测代码问题分析 ===")
    
    issues_found = []
    
    # 检查1: realtime_backtest.py中调用不存在的方法
    print("1. 检查 BacktestEngine.execute_backtest 方法调用...")
    with open('/root/trademe/backend/trading-service/app/api/v1/realtime_backtest.py', 'r') as f:
        content = f.read()
        if 'backtest_engine.execute_backtest(' in content:
            issues_found.append({
                'file': 'realtime_backtest.py',
                'issue': 'BacktestEngine.execute_backtest 方法不存在',
                'line': '第685行',
                'severity': 'CRITICAL'
            })
            print("  ❌ 发现问题: 调用了不存在的 execute_backtest 方法")
    
    # 检查2: backtest_service.py中的模拟数据生成
    print("2. 检查模拟数据生成函数...")
    with open('/root/trademe/backend/trading-service/app/services/backtest_service.py', 'r') as f:
        content = f.read()
        if '_generate_mock_data' in content:
            issues_found.append({
                'file': 'backtest_service.py',
                'issue': '存在模拟数据生成函数',
                'line': '第202行',
                'severity': 'HIGH'
            })
            print("  ⚠️  发现问题: 存在 _generate_mock_data 模拟数据生成函数")
            
        # 检查fallback逻辑
        if 'logger.warning(f"无法获取真实数据，生成模拟数据进行回测")' in content:
            issues_found.append({
                'file': 'backtest_service.py',
                'issue': '数据获取失败时使用模拟数据',
                'line': '第195行',
                'severity': 'HIGH'
            })
            print("  ⚠️  发现问题: 数据获取失败时会自动使用模拟数据")

    # 检查3: 数据验证逻辑
    print("3. 检查数据验证逻辑...")
    if 'raise Exception(error_msg)' in content:
        print("  ✅ 发现改进: _prepare_data 方法在数据缺失时会抛出错误")
    else:
        issues_found.append({
            'file': 'backtest_service.py', 
            'issue': '缺少数据验证错误处理',
            'line': '未知',
            'severity': 'MEDIUM'
        })
    
    return issues_found

def check_binance_data_availability():
    """检查币安数据可用性"""
    print("\n=== 币安数据可用性检查 ===")
    
    # 检查主数据库
    try:
        conn = sqlite3.connect('/root/trademe/data/trademe.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM market_data 
            WHERE exchange = 'binance' OR exchange = 'Binance'
        """)
        
        binance_count = cursor.fetchone()[0]
        print(f"主数据库中币安数据: {binance_count} 条记录")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 查询主数据库币安数据失败: {e}")
    
    # 检查交易服务数据库
    try:
        conn = sqlite3.connect('/root/trademe/backend/trading-service/data/trademe.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM market_data 
            WHERE exchange = 'binance' OR exchange = 'Binance'
        """)
        
        binance_count = cursor.fetchone()[0]
        print(f"交易服务数据库中币安数据: {binance_count} 条记录")
        
        if binance_count == 0:
            print("❌ 关键问题: 两个数据库都没有币安数据，但系统能返回回测结果！")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 查询交易服务数据库币安数据失败: {e}")

def generate_fix_recommendations(issues):
    """生成修复建议"""
    print("\n=== 修复建议 ===")
    
    if not issues:
        print("✅ 未发现代码问题")
        return
    
    print("发现的关键问题:")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. 【{issue['severity']}】{issue['file']} - {issue['issue']}")
        if issue['line']:
            print(f"   位置: {issue['line']}")
    
    print("\n紧急修复建议:")
    
    print("1. 修复 BacktestEngine.execute_backtest 方法不存在的问题:")
    print("   - 添加缺失的 execute_backtest 方法到 BacktestEngine 类")
    print("   - 或修改调用代码使用正确的方法名")
    
    print("\n2. 移除模拟数据fallback机制:")
    print("   - 删除 _generate_mock_data 方法")  
    print("   - 修改数据获取失败时抛出明确错误而非使用模拟数据")
    
    print("\n3. 增强数据验证:")
    print("   - 在回测开始前验证所需交易所的数据是否存在")
    print("   - 如果用户选择币安数据但数据库只有OKX数据，应该明确提示用户")
    
    print("\n4. 生产环境修复:")
    print("   - 禁用所有模拟数据生成功能")
    print("   - 添加数据源验证机制")
    print("   - 记录和监控数据获取failures")

if __name__ == "__main__":
    print("🔍 开始分析回测系统数据问题...")
    print("=" * 60)
    
    # 分析数据库数据
    analyze_database_data()
    
    # 检查币安数据
    check_binance_data_availability() 
    
    # 分析代码问题
    issues = analyze_backtest_code_issues()
    
    # 生成修复建议
    generate_fix_recommendations(issues)
    
    print("\n" + "=" * 60)
    print("🎯 分析完成!")
    print("\n关键发现:")
    print("1. 数据库中只有OKX数据，没有币安数据")
    print("2. realtime_backtest.py调用了不存在的execute_backtest方法")
    print("3. backtest_service.py存在模拟数据fallback机制")
    print("4. 这解释了为什么用户选择币安数据仍能得到回测结果")
    print("\n⚠️  这是一个严重的生产环境问题，需要立即修复！")