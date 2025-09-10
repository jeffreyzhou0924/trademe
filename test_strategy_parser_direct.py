#!/usr/bin/env python3
"""
直接测试智能策略生成闭环解析器
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.strategy_auto_parser import StrategyAutoParser


async def test_strategy_parser():
    """测试策略自动解析器"""
    
    print("=== 直接测试智能策略生成闭环解析器 ===")
    
    # 模拟AI响应内容 - RSI策略
    ai_response = """
我来为您创建一个完整的RSI交易策略代码。这个策略将实现RSI指标计算、交易信号生成和回测功能。

```python
import pandas as pd
import numpy as np
from datetime import datetime

class RSIStrategy:
    def __init__(self, symbol='BTC-USDT', period=14, oversold=30, overbought=70):
        \"\"\"
        初始化RSI策略
        
        参数:
        symbol: 交易标的
        period: RSI计算周期
        oversold: 超卖阈值
        overbought: 超买阈值
        \"\"\"
        self.symbol = symbol
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.data = None
        
    def calculate_rsi(self, prices, period):
        \"\"\"计算RSI指标\"\"\"
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self):
        \"\"\"生成交易信号\"\"\"
        if self.data is None:
            return
            
        # 计算RSI
        self.data['RSI'] = self.calculate_rsi(self.data['Close'], self.period)
        
        # 生成信号
        self.data['Signal'] = 0
        
        # 买入信号：RSI < 30
        buy_signals = self.data['RSI'] < self.oversold
        # 卖出信号：RSI > 70
        sell_signals = self.data['RSI'] > self.overbought
        
        self.data.loc[buy_signals, 'Signal'] = 1   # 买入
        self.data.loc[sell_signals, 'Signal'] = -1  # 卖出
        
        return self.data
    
    def backtest(self, data):
        \"\"\"回测策略\"\"\"
        self.data = data
        self.generate_signals()
        
        # 计算收益
        self.data['Returns'] = self.data['Close'].pct_change()
        self.data['Strategy_Returns'] = self.data['Signal'].shift(1) * self.data['Returns']
        
        # 计算累计收益
        self.data['Cumulative_Returns'] = (1 + self.data['Strategy_Returns']).cumprod()
        
        return self.data
```

**策略说明：**
- 当RSI指标小于30时，表示市场超卖，产生买入信号
- 当RSI指标大于70时，表示市场超买，产生卖出信号
- 使用14日RSI作为默认参数，可根据市场调整

**参数配置：**
{"period": 14, "oversold": 30, "overbought": 70, "symbol": "BTC-USDT"}

这个策略适用于震荡行情，在趋势市场中可能会产生较多假信号，建议结合趋势指标使用。
    """
    
    try:
        # 创建解析器实例
        parser = StrategyAutoParser()
        
        # 创建数据库会话
        async with AsyncSessionLocal() as db:
            print("✅ 数据库连接成功")
            
            # 解析AI响应
            result = await parser.parse_ai_response(
                response_content=ai_response,
                session_id="test_session_001",
                session_type="strategy",
                user_id=9,
                db=db
            )
            
            print(f"\n📋 解析结果:")
            print(f"成功: {result['success']}")
            print(f"消息: {result['message']}")
            
            if result['success']:
                strategy_info = result['strategy']
                print(f"\n✅ 成功创建策略:")
                print(f"  ID: {strategy_info['id']}")
                print(f"  名称: {strategy_info['name']}")
                print(f"  描述: {strategy_info['description'][:100]}...")
                print(f"  类型: {strategy_info['type']}")
                print(f"  AI会话ID: {strategy_info['ai_session_id']}")
                print(f"  创建时间: {strategy_info['created_at']}")
                
                details = result['details']
                print(f"\n📊 详细信息:")
                print(f"  代码块数量: {details['code_blocks_found']}")
                print(f"  提取的参数: {details['extracted_parameters']}")
                if details['validation_warnings']:
                    print(f"  验证警告: {details['validation_warnings']}")
            else:
                print(f"\n❌ 解析失败:")
                print(f"  详细信息: {result.get('details', {})}")
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_strategy_parser())