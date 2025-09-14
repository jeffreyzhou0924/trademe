#!/usr/bin/env python3
"""
从策略44中提取纯Python代码用于测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.ai_service import AIService

def main():
    # 策略44的原始代码（包含中文说明）
    strategy_code_with_chinese = """基于您的详细需求分析，我将生成一个优化的MA均线策略。根据回测结果显示的良好表现（49.31%收益率，1.37夏普比率），我会在保持核心逻辑的基础上进行风险管理优化。

```python
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"优化的MA均线交叉策略 - 基于SMA5和SMA10金叉死叉\"\"\"
    
    def __init__(self):
        super().__init__()
        self.symbol = "BTC-USDT-SWAP"
        self.timeframe = "1h"
        
        # 策略参数
        self.sma_short_period = 5
        self.sma_long_period = 10
        self.position_size = 0.10  # 每次开仓10%资金
        self.stop_loss_pct = 5.0   # 止损5%
        self.take_profit_pct = 5.0 # 止盈5%
        
        # 优化参数
        self.kdj_k_period = 9
        self.kdj_d_period = 3
        self.kdj_smooth = 3
        
        # 状态跟踪
        self.last_signal = None
        self.signal_confirmed = False
        self.position_direction = None
        
    def get_data_requirements(self) -> List[DataRequest]:
        \"\"\"定义策略所需的数据源\"\"\"
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol=self.symbol,
                timeframe=self.timeframe,
                required=True
            )
        ]
    
    def calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, 
                      k_period: int = 9, d_period: int = 3, smooth: int = 3) -> tuple:
        \"\"\"计算KDJ指标\"\"\"
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        rsv = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        rsv = rsv.fillna(50)
        
        k = rsv.ewm(span=smooth).mean()
        d = k.ewm(span=d_period).mean()
        j = 3 * k - 2 * d
        
        return k, d, j
    
    def detect_golden_cross(self, sma_short: pd.Series, sma_long: pd.Series) -> bool:
        \"\"\"检测金叉信号\"\"\"
        if len(sma_short) < 2 or len(sma_long) < 2:
            return False
        
        # 当前短均线在长均线上方，且前一根K线短均线在长均线下方
        current_cross = sma_short.iloc[-1] > sma_long.iloc[-1]
        previous_cross = sma_short.iloc[-2] <= sma_long.iloc[-2]
        
        return current_cross and previous_cross
    
    def detect_death_cross(self, sma_short: pd.Series, sma_long: pd.Series) -> bool:
        \"\"\"检测死叉信号\"\"\"
        if len(sma_short) < 2 or len(sma_long) < 2:
            return False
        
        # 当前短均线在长均线下方，且前一根K线短均线在长均线上方
        current_cross = sma_short.iloc[-1] < sma_long.iloc[-1]
        previous_cross = sma_short.iloc[-2] >= sma_long.iloc[-2]
        
        return current_cross and previous_cross
    
    def should_add_position(self, signal_type: SignalType) -> bool:
        \"\"\"判断是否应该加仓\"\"\"
        # 重复信号加仓逻辑
        if self.position_direction is None:
            return True
        
        # 同方向信号允许加仓
        if signal_type == SignalType.BUY and self.position_direction == "long":
            return True
        elif signal_type == SignalType.SELL and self.position_direction == "short":
            return True
        
        return False
    
    def get_kdj_filter(self, k: pd.Series, d: pd.Series, j: pd.Series, signal_type: SignalType) -> bool:
        \"\"\"KDJ过滤条件 - 优化版本\"\"\"
        if len(k) < 1 or len(d) < 1:
            return True  # 数据不足时不过滤
        
        current_k = k.iloc[-1]
        current_d = d.iloc[-1]
        
        # 买入信号：KDJ不在超买区域
        if signal_type == SignalType.BUY:
            return current_k < 80 and current_d < 80
        
        # 卖出信号：KDJ不在超卖区域  
        elif signal_type == SignalType.SELL:
            return current_k > 20 and current_d > 20
        
        return True
    
    async def on_data_update(self, data_type: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        \"\"\"数据更新处理 - 实现MA均线交叉策略\"\"\"
        if data_type != "kline":
            return None
        
        # 获取K线数据
        df = self.get_kline_data()
        if df is None or len(df) < max(self.sma_long_period, self.kdj_k_period) + 2:
            return None
        
        # 计算技术指标
        sma_short = self.calculate_sma(df['close'], self.sma_short_period)
        sma_long = self.calculate_sma(df['close'], self.sma_long_period)
        
        # 计算KDJ指标用于过滤
        k, d, j = self.calculate_kdj(df['high'], df['low'], df['close'], 
                                     self.kdj_k_period, self.kdj_d_period, self.kdj_smooth)
        
        if sma_short is None or sma_long is None:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # 检测金叉和死叉
        golden_cross = self.detect_golden_cross(sma_short, sma_long)
        death_cross = self.detect_death_cross(sma_short, sma_long)
        
        signal = None
        
        # 金叉开多逻辑
        if golden_cross:
            # KDJ过滤条件
            if self.get_kdj_filter(k, d, j, SignalType.BUY):
                # 先平仓再开反向仓
                if self.position_direction == "short":
                    # 发送平仓信号
                    self.position_direction = None
                
                # 判断是否加仓或开新仓
                if self.should_add_position(SignalType.BUY):
                    signal = TradingSignal(
                        signal_type=SignalType.BUY,
                        symbol=self.symbol,
                        price=current_price,
                        quantity=self.position_size,
                        stop_loss=current_price * (1 - self.stop_loss_pct / 100),
                        take_profit=current_price * (1 + self.take_profit_pct / 100),
                        metadata={
                            "strategy": "ma_cross_optimized",
                            "signal_reason": "golden_cross",
                            "sma_short": float(sma_short.iloc[-1]),
                            "sma_long": float(sma_long.iloc[-1]),
                            "kdj_k": float(k.iloc[-1]),
                            "kdj_d": float(d.iloc[-1]),
                            "position_size_pct": self.position_size * 100
                        }
                    )
                    self.position_direction = "long"
        
        # 死叉开空逻辑
        elif death_cross:
            # KDJ过滤条件
            if self.get_kdj_filter(k, d, j, SignalType.SELL):
                # 先平仓再开反向仓
                if self.position_direction == "long":
                    # 发送平仓信号
                    self.position_direction = None
                
                # 判断是否加仓或开新仓
                if self.should_add_position(SignalType.SELL):
                    signal = TradingSignal(
                        signal_type=SignalType.SELL,
                        symbol=self.symbol,
                        price=current_price,
                        quantity=self.position_size,
                        stop_loss=current_price * (1 + self.stop_loss_pct / 100),
                        take_profit=current_price * (1 - self.take_profit_pct / 100),
                        metadata={
                            "strategy": "ma_cross_optimized",
                            "signal_reason": "death_cross",
                            "sma_short": float(sma_short.iloc[-1]),
                            "sma_long": float(sma_long.iloc[-1]),
                            "kdj_k": float(k.iloc[-1]),
                            "kdj_d": float(d.iloc[-1]),
                            "position_size_pct": self.position_size * 100
                        }
                    )
                    self.position_direction = "short"
        
        return signal
```

## 策略优化要点：

### 1. **风险管理优化**
- 保持5%固定止盈止损
- 添加KDJ过滤避免极端市场条件下的错误信号
- 先平仓再开反向仓的逻辑

### 2. **信号质量提升**
- 使用KDJ指标过滤超买超卖区域的信号
- 买入时避免KDJ超买（K<80, D<80）
- 卖出时避免KDJ超卖（K>20, D>20）

### 3. **加仓逻辑优化**
- 保持重复信号加仓10%资金
- 同方向信号允许加仓
- 反向信号先平仓再开新仓

### 4. **核心逻辑保持**
- SMA5和SMA10金叉死叉核心逻辑不变
- 1小时时间框架
- BTC-USDT-SWAP交易对
- 10%资金分配策略

这个优化版本在保持您原有策略49.31%收益率和1.37夏普比率的基础上，通过KDJ过滤减少了假信号，应该能进一步提升策略的稳定性和风险调整后收益。"""

    # 使用AI服务提取纯Python代码
    ai_service = AIService()
    extracted_code = ai_service.extract_python_code_from_response(strategy_code_with_chinese)
    
    print("🔧 提取纯Python代码成功！")
    print(f"原始长度: {len(strategy_code_with_chinese)} 字符")
    print(f"提取后长度: {len(extracted_code)} 字符")
    
    # 验证提取的代码
    try:
        import ast
        ast.parse(extracted_code)
        print("✅ Python语法验证通过")
    except SyntaxError as e:
        print(f"❌ Python语法验证失败: {e}")
        return
    
    # 输出提取的代码供测试使用
    print("\n📋 提取的纯Python代码：")
    print(extracted_code)

if __name__ == "__main__":
    main()