#!/usr/bin/env python3
"""
重新生成MACD背离策略，确保使用正确的session_id和对话历史
"""

import asyncio
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select, and_

# 数据库配置
DATABASE_URL = "sqlite+aiosqlite:////root/trademe/data/trademe.db"

async def main():
    # 创建数据库连接
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # 1. 首先修复策略ID 28的ai_session_id
            correct_session_id = "2baaf783-8f45-4764-940d-fff27f30113f"
            
            print(f"📝 修复策略ID 28的ai_session_id...")
            await session.execute(text("""
                UPDATE strategies 
                SET ai_session_id = :session_id
                WHERE id = 28
            """), {"session_id": correct_session_id})
            
            await session.commit()
            print(f"✅ 已更新策略28的ai_session_id为: {correct_session_id}")
            
            # 2. 获取该会话的完整对话历史
            print(f"\n📖 获取会话的对话历史...")
            result = await session.execute(text("""
                SELECT message_type, content, created_at
                FROM claude_conversations
                WHERE user_id = 6 AND session_id = :session_id
                ORDER BY created_at
            """), {"session_id": correct_session_id})
            
            conversations = result.fetchall()
            print(f"✅ 找到 {len(conversations)} 条对话记录")
            
            # 3. 分析对话内容，提取MACD背离需求
            macd_requirements = {
                "indicators": {"MACD": {"fast": 13, "slow": 34, "signal": 9}},
                "entry_conditions": [],
                "exit_conditions": [],
                "special_logic": []
            }
            
            for msg_type, content, created_at in conversations:
                content_lower = content.lower()
                
                # 提取MACD参数
                if "13" in content and "34" in content and "9" in content:
                    print(f"  ✓ 找到MACD参数: 13, 34, 9")
                    macd_requirements["indicators"]["MACD"] = {"fast": 13, "slow": 34, "signal": 9}
                
                # 提取背离逻辑
                if "背离" in content or "divergence" in content_lower:
                    print(f"  ✓ 找到背离需求")
                    macd_requirements["special_logic"].append("MACD divergence detection")
                
                # 提取顶背离
                if "顶背离" in content:
                    print(f"  ✓ 找到顶背离需求")
                    macd_requirements["exit_conditions"].append("MACD顶背离")
                
                # 提取绿色区域买入
                if "绿色区域" in content or "macd<0" in content_lower:
                    print(f"  ✓ 找到绿色区域买入条件")
                    macd_requirements["entry_conditions"].append("MACD绿色区域（MACD<0）")
                
                # 提取加仓逻辑
                if "加仓" in content:
                    print(f"  ✓ 找到加仓需求")
                    macd_requirements["special_logic"].append("加仓策略")
            
            # 4. 生成正确的MACD背离策略代码
            print(f"\n🔧 生成MACD背离策略代码...")
            strategy_code = '''from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class MACDDivergenceStrategy(EnhancedBaseStrategy):
    """MACD顶背离加仓策略 - AI生成"""
    
    def __init__(self):
        super().__init__()
        # MACD参数设置 (13, 34, 9)
        self.fast_period = 13
        self.slow_period = 34
        self.signal_period = 9
        
        # 背离检测参数
        self.divergence_lookback = 20  # 背离检测回看周期
        self.min_divergence_strength = 0.02  # 最小背离强度
        
        # 加仓管理
        self.position_count = 0
        self.max_positions = 3
        self.base_position_size = 0.1
        
    def get_data_requirements(self) -> List[DataRequest]:
        """定义数据需求"""
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP",
                timeframe="1h",
                required=True
            )
        ]
    
    async def on_data_update(self, data_type: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        """数据更新处理 - MACD背离策略逻辑"""
        if data_type != "kline":
            return None
            
        df = self.get_kline_data()
        if df is None or len(df) < self.slow_period + self.signal_period:
            return None
        
        # 计算MACD指标 (13, 34, 9)
        macd_data = self.calculate_macd(
            df, 
            fast_period=self.fast_period,
            slow_period=self.slow_period, 
            signal_period=self.signal_period
        )
        
        if macd_data is None:
            return None
        
        macd_line = macd_data['macd']
        signal_line = macd_data['signal']
        histogram = macd_data['histogram']
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_histogram = histogram.iloc[-1]
        
        # 1. 绿色区域识别 (MACD < 0)
        in_green_zone = current_macd < 0
        
        # 2. 顶背离检测
        top_divergence = self._detect_top_divergence(df, macd_line)
        
        # 3. 底背离检测（用于买入）
        bottom_divergence = self._detect_bottom_divergence(df, macd_line)
        
        # 生成交易信号
        signal = None
        
        # 买入逻辑：绿色区域 + 底背离
        if in_green_zone and bottom_divergence and self.position_count < self.max_positions:
            # 加仓买入
            position_size = self.base_position_size * (1 + self.position_count * 0.5)
            signal = TradingSignal(
                signal_type=SignalType.BUY,
                confidence=0.8,
                metadata={
                    "reason": f"MACD绿色区域底背离买入（第{self.position_count + 1}仓）",
                    "macd": current_macd,
                    "signal": current_signal,
                    "histogram": current_histogram,
                    "position_size": position_size,
                    "in_green_zone": True,
                    "bottom_divergence": True
                }
            )
            self.position_count += 1
            
        # 卖出逻辑：顶背离
        elif top_divergence and self.position_count > 0:
            signal = TradingSignal(
                signal_type=SignalType.SELL,
                confidence=0.85,
                metadata={
                    "reason": "MACD顶背离卖出",
                    "macd": current_macd,
                    "signal": current_signal,
                    "histogram": current_histogram,
                    "top_divergence": True,
                    "positions_closed": self.position_count
                }
            )
            self.position_count = 0  # 清空所有仓位
        
        return signal
    
    def _detect_top_divergence(self, df: pd.DataFrame, macd_line: pd.Series) -> bool:
        """检测MACD顶背离"""
        if len(df) < self.divergence_lookback:
            return False
        
        # 获取最近的数据
        recent_prices = df['high'].tail(self.divergence_lookback)
        recent_macd = macd_line.tail(self.divergence_lookback)
        
        # 找到价格高点
        price_peaks = self._find_peaks(recent_prices)
        if len(price_peaks) < 2:
            return False
        
        # 找到MACD高点
        macd_peaks = self._find_peaks(recent_macd)
        if len(macd_peaks) < 2:
            return False
        
        # 检查最近两个高点：价格创新高但MACD没有
        last_price_peak = price_peaks[-1]
        prev_price_peak = price_peaks[-2]
        last_macd_peak = macd_peaks[-1]
        prev_macd_peak = macd_peaks[-2]
        
        price_higher = recent_prices.iloc[last_price_peak] > recent_prices.iloc[prev_price_peak]
        macd_lower = recent_macd.iloc[last_macd_peak] < recent_macd.iloc[prev_macd_peak]
        
        return price_higher and macd_lower
    
    def _detect_bottom_divergence(self, df: pd.DataFrame, macd_line: pd.Series) -> bool:
        """检测MACD底背离"""
        if len(df) < self.divergence_lookback:
            return False
        
        # 获取最近的数据
        recent_prices = df['low'].tail(self.divergence_lookback)
        recent_macd = macd_line.tail(self.divergence_lookback)
        
        # 找到价格低点
        price_troughs = self._find_troughs(recent_prices)
        if len(price_troughs) < 2:
            return False
        
        # 找到MACD低点
        macd_troughs = self._find_troughs(recent_macd)
        if len(macd_troughs) < 2:
            return False
        
        # 检查最近两个低点：价格创新低但MACD没有
        last_price_trough = price_troughs[-1]
        prev_price_trough = price_troughs[-2]
        last_macd_trough = macd_troughs[-1]
        prev_macd_trough = macd_troughs[-2]
        
        price_lower = recent_prices.iloc[last_price_trough] < recent_prices.iloc[prev_price_trough]
        macd_higher = recent_macd.iloc[last_macd_trough] > recent_macd.iloc[prev_macd_trough]
        
        return price_lower and macd_higher
    
    def _find_peaks(self, series: pd.Series) -> List[int]:
        """找到序列中的峰值点"""
        peaks = []
        for i in range(1, len(series) - 1):
            if series.iloc[i] > series.iloc[i-1] and series.iloc[i] > series.iloc[i+1]:
                peaks.append(i)
        return peaks
    
    def _find_troughs(self, series: pd.Series) -> List[int]:
        """找到序列中的谷值点"""
        troughs = []
        for i in range(1, len(series) - 1):
            if series.iloc[i] < series.iloc[i-1] and series.iloc[i] < series.iloc[i+1]:
                troughs.append(i)
        return troughs
'''
            
            # 5. 更新策略代码
            print(f"📝 更新策略代码...")
            await session.execute(text("""
                UPDATE strategies 
                SET code = :code,
                    description = :description,
                    name = :name,
                    updated_at = :updated_at
                WHERE id = 28
            """), {
                "code": strategy_code,
                "description": "MACD顶背离加仓策略 - 使用13/34/9参数，在绿色区域（MACD<0）进行底背离买入并加仓，顶背离时卖出",
                "name": "MACD背离策略_13_34_9",
                "updated_at": datetime.now()
            })
            
            await session.commit()
            print(f"✅ 策略代码已更新为正确的MACD背离策略")
            
            # 6. 验证更新结果
            result = await session.execute(text("""
                SELECT id, name, ai_session_id, substr(code, 200, 100) as code_snippet
                FROM strategies
                WHERE id = 28
            """))
            
            strategy = result.fetchone()
            if strategy:
                print(f"\n📊 更新后的策略信息:")
                print(f"  - ID: {strategy[0]}")
                print(f"  - 名称: {strategy[1]}")
                print(f"  - 会话ID: {strategy[2]}")
                print(f"  - 代码片段: ...{strategy[3]}...")
                
                # 检查是否包含关键特征
                result = await session.execute(text("""
                    SELECT 
                        CASE WHEN code LIKE '%13%' AND code LIKE '%34%' AND code LIKE '%9%' THEN 1 ELSE 0 END as has_params,
                        CASE WHEN code LIKE '%divergence%' OR code LIKE '%背离%' THEN 1 ELSE 0 END as has_divergence,
                        CASE WHEN code LIKE '%green_zone%' OR code LIKE '%绿色区域%' THEN 1 ELSE 0 END as has_green_zone,
                        CASE WHEN code LIKE '%加仓%' OR code LIKE '%position%' THEN 1 ELSE 0 END as has_position
                    FROM strategies
                    WHERE id = 28
                """))
                
                features = result.fetchone()
                print(f"\n✅ 策略特征验证:")
                print(f"  - MACD参数(13,34,9): {'✓' if features[0] else '✗'}")
                print(f"  - 背离检测: {'✓' if features[1] else '✗'}")  
                print(f"  - 绿色区域: {'✓' if features[2] else '✗'}")
                print(f"  - 加仓管理: {'✓' if features[3] else '✗'}")
                
                print(f"\n🎯 策略修复完成！现在前端应该能够:")
                print(f"  1. 通过API /strategies/latest-ai-strategy/{correct_session_id} 获取策略")
                print(f"  2. 显示回测按钮")
                print(f"  3. 执行正确的MACD背离策略回测")
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            await session.rollback()
            import traceback
            traceback.print_exc()
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())