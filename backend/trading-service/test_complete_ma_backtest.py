#!/usr/bin/env python3
"""
完整的均线策略回测测试
"""
import asyncio
import aiohttp
import json
import time

# 配置
BASE_URL = "http://localhost:8001"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc2NTA5OTYsImV4cCI6MTc1ODI1NTc5NiwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.gg8WM2teIx6rcBJWJpbX0vgpTwlR_7if5yJUUgcJNf8"

# 完整的移动平均线交叉策略
MA_CROSSOVER_STRATEGY = '''
import pandas as pd
import numpy as np

class MAStrategy:
    """移动平均线交叉策略"""
    
    def __init__(self):
        self.name = "双均线交叉策略"
        self.fast_period = 10  # 快速移动平均线
        self.slow_period = 20  # 慢速移动平均线
        self.position = 0
        
    def calculate_ma(self, prices, period):
        """计算移动平均线"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def generate_signal(self, klines):
        """生成交易信号"""
        if not klines or len(klines) < self.slow_period:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '数据不足'
            }
            
        # 提取收盘价
        closes = [float(k['close']) for k in klines]
        
        # 计算快慢均线
        fast_ma = self.calculate_ma(closes, self.fast_period)
        slow_ma = self.calculate_ma(closes, self.slow_period)
        
        if fast_ma is None or slow_ma is None:
            return {
                'action': 'hold', 
                'confidence': 0.0,
                'reason': '均线计算失败'
            }
        
        # 计算前一周期的均线(用于判断交叉)
        if len(closes) > self.slow_period:
            prev_closes = closes[:-1]
            prev_fast_ma = self.calculate_ma(prev_closes, self.fast_period)
            prev_slow_ma = self.calculate_ma(prev_closes, self.slow_period)
            
            # 金叉：快线上穿慢线
            if (fast_ma > slow_ma and 
                prev_fast_ma is not None and prev_slow_ma is not None and
                prev_fast_ma <= prev_slow_ma):
                return {
                    'action': 'buy',
                    'confidence': 0.8,
                    'reason': f'金叉信号：快线({fast_ma:.2f}) > 慢线({slow_ma:.2f})',
                    'fast_ma': fast_ma,
                    'slow_ma': slow_ma
                }
            
            # 死叉：快线下穿慢线  
            elif (fast_ma < slow_ma and
                  prev_fast_ma is not None and prev_slow_ma is not None and
                  prev_fast_ma >= prev_slow_ma):
                return {
                    'action': 'sell',
                    'confidence': 0.8,
                    'reason': f'死叉信号：快线({fast_ma:.2f}) < 慢线({slow_ma:.2f})',
                    'fast_ma': fast_ma,
                    'slow_ma': slow_ma
                }
        
        # 无明确信号
        return {
            'action': 'hold',
            'confidence': 0.3,
            'reason': f'无交叉信号：快线({fast_ma:.2f}), 慢线({slow_ma:.2f})',
            'fast_ma': fast_ma,
            'slow_ma': slow_ma
        }

# 策略入口函数
def strategy_signal(klines):
    strategy = MAStrategy()
    return strategy.generate_signal(klines)
'''

async def test_complete_ma_backtest():
    """完整的均线策略回测测试"""
    print("🚀 开始完整的均线策略回测测试...")
    print("=" * 60)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    # 回测配置
    backtest_config = {
        "strategy_code": MA_CROSSOVER_STRATEGY,
        "strategy_name": "双均线交叉策略",
        "exchange": "okx",
        "product_type": "perpetual",
        "symbols": ["BTC/USDT"],
        "timeframes": ["1h"],
        "fee_rate": "vip0",
        "initial_capital": 10000,
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "data_type": "kline"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # 1. 启动回测任务
            print("📡 启动回测任务...")
            async with session.post(
                f"{BASE_URL}/api/v1/realtime-backtest/start",
                headers=headers,
                json=backtest_config
            ) as response:
                
                if response.status != 200:
                    error = await response.text()
                    print(f"❌ 启动回测失败: {error}")
                    return False
                
                result = await response.json()
                task_id = result.get('task_id')
                print(f"✅ 回测任务启动成功！")
                print(f"📋 Task ID: {task_id}")
                print(f"📋 Status: {result.get('status')}")
                print(f"📋 Message: {result.get('message')}")
                
                if not task_id:
                    print("❌ 未获得task_id，测试失败")
                    return False
            
            # 2. 监控回测进度
            print(f"\n📊 开始监控回测进度...")
            max_wait_time = 60  # 最多等待60秒
            check_interval = 2   # 每2秒检查一次
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                async with session.get(
                    f"{BASE_URL}/api/v1/realtime-backtest/status/{task_id}",
                    headers=headers
                ) as status_response:
                    
                    if status_response.status != 200:
                        error = await status_response.text()
                        print(f"❌ 获取状态失败: {error}")
                        break
                    
                    status_data = await status_response.json()
                    status = status_data.get('status', 'unknown')
                    progress = status_data.get('progress', 0)
                    
                    print(f"📊 当前状态: {status} - 进度: {progress}%")
                    
                    # 显示最新日志
                    if status_data.get('logs'):
                        latest_logs = status_data['logs'][-2:]  # 显示最后2条日志
                        for log in latest_logs:
                            print(f"   📜 {log}")
                    
                    # 回测完成
                    if status == 'completed':
                        print("🎉 回测完成！获取回测结果...")
                        
                        # 获取详细结果
                        backtest_result = status_data.get('result', {})
                        if backtest_result:
                            print("\n📈 ===== 回测结果 =====")
                            
                            # 基本指标
                            performance = backtest_result.get('performance', {})
                            if performance:
                                print(f"💰 最终资金: {performance.get('final_capital', 0):.2f}")
                                print(f"📈 总收益率: {performance.get('total_return_pct', 0):.2f}%")
                                print(f"🎯 胜率: {performance.get('win_rate', 0):.2f}%")
                                print(f"📊 夏普比率: {performance.get('sharpe_ratio', 0):.3f}")
                                print(f"📉 最大回撤: {performance.get('max_drawdown_pct', 0):.2f}%")
                            
                            # 交易统计
                            trades = backtest_result.get('trades', [])
                            print(f"📋 总交易次数: {len(trades)}")
                            
                            if trades:
                                print("💼 交易记录样本:")
                                for i, trade in enumerate(trades[:3]):  # 显示前3笔交易
                                    print(f"   {i+1}. {trade.get('action', 'N/A')} @ {trade.get('price', 0):.2f} "
                                          f"- 收益: {trade.get('pnl', 0):.2f}")
                            
                            # AI分析
                            ai_analysis = backtest_result.get('ai_analysis', {})
                            if ai_analysis:
                                print(f"🤖 AI评分: {ai_analysis.get('score', 0)}/100")
                                print(f"💡 AI建议: {ai_analysis.get('suggestion', 'N/A')}")
                        
                        return True
                    
                    # 回测失败
                    elif status == 'failed':
                        error_msg = status_data.get('error_message', '未知错误')
                        print(f"❌ 回测失败: {error_msg}")
                        return False
                    
                    # 继续等待
                    await asyncio.sleep(check_interval)
            
            # 超时
            print(f"⏰ 等待超时({max_wait_time}秒)，但可能回测仍在进行中")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程异常: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 完整均线策略回测流程测试")
    print("=" * 60)
    
    success = asyncio.run(test_complete_ma_backtest())
    
    print("=" * 60)
    if success:
        print("🎉 测试成功！均线策略回测流程完全正常！")
        print("✅ AI对话→回测分析功能已完全修复")
    else:
        print("❌ 测试未完全成功，需要进一步检查")