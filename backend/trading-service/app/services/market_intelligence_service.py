"""
智能市场环境识别系统
实时分析市场状态，为策略选择提供AI驱动的环境判断
"""

import json
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, text
from loguru import logger

from app.models.market_data import MarketData
from app.services.claude_account_service import claude_account_service
from app.core.claude_client import ClaudeClient


class MarketIntelligenceService:
    """市场智能分析服务 - AI驱动的市场环境识别"""
    
    def __init__(self):
        self.market_analysis_prompt = """
你是一位专业的市场分析师和量化交易专家。基于以下市场数据，
请分析当前的市场环境特征，并为策略选择提供建议。

市场数据分析：
{market_data_summary}

技术指标分析：
{technical_indicators}

波动率分析：
{volatility_analysis}

成交量分析：
{volume_analysis}

请提供以下分析：
1. **市场环境判断**: 趋势市/震荡市/突破市等
2. **波动特征**: 高波动/低波动/异常波动
3. **流动性状况**: 成交量水平和市场深度
4. **风险评估**: 当前市场风险等级
5. **策略推荐**: 最适合当前环境的策略类型
6. **时间窗口**: 预期这种环境将持续多长时间

请用专业但简洁的语言提供分析结果。
"""

    async def analyze_current_market(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        lookback_hours: int = 168,  # 7天
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """分析当前市场环境"""
        try:
            # 获取历史数据
            market_data = await self._get_market_data(
                symbol, timeframe, lookback_hours, db
            )
            
            if not market_data:
                return {"error": "无法获取市场数据"}
            
            # 计算技术指标
            technical_indicators = await self._calculate_technical_indicators(market_data)
            
            # 波动率分析
            volatility_analysis = await self._analyze_volatility(market_data)
            
            # 成交量分析
            volume_analysis = await self._analyze_volume(market_data)
            
            # 市场状态分类
            market_state = await self._classify_market_state(
                market_data, technical_indicators, volatility_analysis
            )
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "analysis_time": datetime.now(),
                "data_points": len(market_data),
                "market_state": market_state,
                "technical_indicators": technical_indicators,
                "volatility_analysis": volatility_analysis,
                "volume_analysis": volume_analysis,
                "market_summary": await self._generate_market_summary(
                    market_state, technical_indicators, volatility_analysis, volume_analysis
                )
            }
            
        except Exception as e:
            logger.error(f"市场环境分析失败: {e}")
            return {"error": str(e)}
    
    async def _get_market_data(
        self, 
        symbol: str, 
        timeframe: str, 
        lookback_hours: int, 
        db: Optional[AsyncSession]
    ) -> List[Dict[str, Any]]:
        """获取市场数据"""
        if not db:
            return []
        
        try:
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=lookback_hours)
            
            # 转换symbol格式 (BTC/USDT -> BTCUSDT)
            db_symbol = symbol.replace('/', '')
            
            # 查询数据库
            query = select(MarketData).where(
                and_(
                    MarketData.symbol == db_symbol,
                    MarketData.timestamp >= start_time,
                    MarketData.timestamp <= end_time
                )
            ).order_by(MarketData.timestamp.asc())
            
            result = await db.execute(query)
            records = result.scalars().all()
            
            # 转换为字典格式
            market_data = []
            for record in records:
                market_data.append({
                    "timestamp": record.timestamp,
                    "open": float(record.open_price),
                    "high": float(record.high_price),
                    "low": float(record.low_price),
                    "close": float(record.close_price),
                    "volume": float(record.volume)
                })
            
            return market_data
            
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return []
    
    async def _calculate_technical_indicators(
        self, 
        market_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算技术指标"""
        if len(market_data) < 20:
            return {"error": "数据不足"}
        
        # 转换为numpy数组便于计算
        closes = np.array([d['close'] for d in market_data])
        highs = np.array([d['high'] for d in market_data])
        lows = np.array([d['low'] for d in market_data])
        volumes = np.array([d['volume'] for d in market_data])
        
        indicators = {}
        
        # 移动平均线
        if len(closes) >= 20:
            indicators['sma_20'] = np.mean(closes[-20:])
            indicators['sma_50'] = np.mean(closes[-50:]) if len(closes) >= 50 else None
        
        # RSI
        if len(closes) >= 14:
            indicators['rsi'] = self._calculate_rsi(closes, 14)
        
        # MACD
        if len(closes) >= 26:
            macd_line, signal_line, histogram = self._calculate_macd(closes)
            indicators['macd'] = {
                'macd_line': macd_line,
                'signal_line': signal_line,
                'histogram': histogram
            }
        
        # 布林带
        if len(closes) >= 20:
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes, 20)
            indicators['bollinger_bands'] = {
                'upper': bb_upper,
                'middle': bb_middle,
                'lower': bb_lower,
                'position': (closes[-1] - bb_lower) / (bb_upper - bb_lower)  # 价格在布林带中的位置
            }
        
        # 当前价格趋势
        if len(closes) >= 5:
            recent_trend = (closes[-1] - closes[-5]) / closes[-5] * 100
            indicators['recent_trend_pct'] = round(recent_trend, 2)
        
        return indicators
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """计算RSI"""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def _calculate_macd(
        self, 
        prices: np.ndarray, 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> Tuple[float, float, float]:
        """计算MACD"""
        # EMA计算
        def ema(data, period):
            alpha = 2 / (period + 1)
            ema_values = np.zeros_like(data)
            ema_values[0] = data[0]
            for i in range(1, len(data)):
                ema_values[i] = alpha * data[i] + (1 - alpha) * ema_values[i-1]
            return ema_values
        
        fast_ema = ema(prices, fast_period)
        slow_ema = ema(prices, slow_period)
        
        macd_line = fast_ema - slow_ema
        signal_line = ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return (
            round(macd_line[-1], 4),
            round(signal_line[-1], 4),
            round(histogram[-1], 4)
        )
    
    def _calculate_bollinger_bands(
        self, 
        prices: np.ndarray, 
        period: int = 20, 
        std_dev: int = 2
    ) -> Tuple[float, float, float]:
        """计算布林带"""
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return round(upper, 2), round(sma, 2), round(lower, 2)
    
    async def _analyze_volatility(
        self, 
        market_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析波动率"""
        if len(market_data) < 20:
            return {"error": "数据不足"}
        
        closes = [d['close'] for d in market_data]
        
        # 计算日收益率
        returns = []
        for i in range(1, len(closes)):
            ret = (closes[i] - closes[i-1]) / closes[i-1]
            returns.append(ret)
        
        # 波动率统计
        volatility = np.std(returns) * np.sqrt(24)  # 小时数据转日波动率
        avg_return = np.mean(returns)
        
        # 异常波动检测
        recent_returns = returns[-24:] if len(returns) >= 24 else returns
        recent_volatility = np.std(recent_returns) * np.sqrt(24)
        
        # 波动率等级分类
        if volatility > 0.05:
            volatility_level = "极高"
        elif volatility > 0.03:
            volatility_level = "高"
        elif volatility > 0.02:
            volatility_level = "中等"
        elif volatility > 0.01:
            volatility_level = "低"
        else:
            volatility_level = "极低"
        
        return {
            "daily_volatility": round(volatility * 100, 2),
            "recent_volatility": round(recent_volatility * 100, 2),
            "avg_return": round(avg_return * 100, 4),
            "volatility_level": volatility_level,
            "volatility_trend": "上升" if recent_volatility > volatility else "下降"
        }
    
    async def _analyze_volume(
        self, 
        market_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析成交量"""
        if len(market_data) < 20:
            return {"error": "数据不足"}
        
        volumes = [d['volume'] for d in market_data]
        
        # 成交量统计
        avg_volume = np.mean(volumes)
        recent_volume = np.mean(volumes[-24:]) if len(volumes) >= 24 else avg_volume
        volume_trend = (recent_volume - avg_volume) / avg_volume
        
        # 成交量水平分类
        if recent_volume > avg_volume * 2:
            volume_level = "异常高"
        elif recent_volume > avg_volume * 1.5:
            volume_level = "高"
        elif recent_volume > avg_volume * 0.8:
            volume_level = "正常"
        elif recent_volume > avg_volume * 0.5:
            volume_level = "低"
        else:
            volume_level = "异常低"
        
        return {
            "avg_volume": round(avg_volume, 2),
            "recent_volume": round(recent_volume, 2),
            "volume_trend_pct": round(volume_trend * 100, 2),
            "volume_level": volume_level
        }
    
    async def _classify_market_state(
        self,
        market_data: List[Dict[str, Any]],
        technical_indicators: Dict[str, Any],
        volatility_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分类市场状态"""
        closes = [d['close'] for d in market_data]
        
        # 趋势判断
        if len(closes) >= 20:
            short_term_trend = (closes[-1] - closes[-5]) / closes[-5]
            medium_term_trend = (closes[-1] - closes[-20]) / closes[-20]
        else:
            short_term_trend = 0
            medium_term_trend = 0
        
        # 市场状态分类
        rsi = technical_indicators.get('rsi', 50)
        volatility = volatility_analysis.get('daily_volatility', 2)
        
        # 趋势市 vs 震荡市判断
        if abs(medium_term_trend) > 0.1:  # 10%以上变化
            if medium_term_trend > 0:
                market_type = "上升趋势市"
                confidence = min(abs(medium_term_trend) * 10, 1.0)
            else:
                market_type = "下降趋势市"
                confidence = min(abs(medium_term_trend) * 10, 1.0)
        else:
            market_type = "震荡市"
            confidence = 1 - abs(medium_term_trend) * 5
        
        # 超买超卖状态
        if rsi > 70:
            overbought_oversold = "超买"
        elif rsi < 30:
            overbought_oversold = "超卖"
        else:
            overbought_oversold = "正常"
        
        return {
            "market_type": market_type,
            "confidence": round(confidence, 2),
            "short_term_trend": round(short_term_trend * 100, 2),
            "medium_term_trend": round(medium_term_trend * 100, 2),
            "overbought_oversold": overbought_oversold,
            "risk_level": self._assess_market_risk(volatility, rsi, abs(medium_term_trend))
        }
    
    def _assess_market_risk(
        self, 
        volatility: float, 
        rsi: float, 
        trend_strength: float
    ) -> str:
        """评估市场风险等级"""
        risk_score = 0
        
        # 波动率风险
        if volatility > 5:
            risk_score += 3
        elif volatility > 3:
            risk_score += 2
        elif volatility > 2:
            risk_score += 1
        
        # RSI极端值风险
        if rsi > 80 or rsi < 20:
            risk_score += 2
        elif rsi > 70 or rsi < 30:
            risk_score += 1
        
        # 趋势强度风险
        if trend_strength > 0.2:
            risk_score += 2
        elif trend_strength > 0.1:
            risk_score += 1
        
        if risk_score >= 5:
            return "高风险"
        elif risk_score >= 3:
            return "中等风险"
        else:
            return "低风险"
    
    async def _generate_market_summary(
        self,
        market_state: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        volatility_analysis: Dict[str, Any],
        volume_analysis: Dict[str, Any]
    ) -> str:
        """生成市场环境摘要"""
        market_type = market_state.get('market_type', '未知')
        risk_level = market_state.get('risk_level', '未知')
        volatility_level = volatility_analysis.get('volatility_level', '未知')
        volume_level = volume_analysis.get('volume_level', '未知')
        
        rsi = technical_indicators.get('rsi', 50)
        recent_trend = technical_indicators.get('recent_trend_pct', 0)
        
        summary = f"""
📊 市场环境快报:
• 市场类型: {market_type}
• 风险等级: {risk_level}
• 波动水平: {volatility_level}
• 成交量: {volume_level}
• RSI指标: {rsi:.1f}
• 近期趋势: {recent_trend:+.2f}%
        """.strip()
        
        return summary
    
    async def get_strategy_recommendations(
        self,
        market_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """基于市场环境推荐策略"""
        try:
            market_state = market_analysis.get('market_state', {})
            market_type = market_state.get('market_type', '')
            risk_level = market_state.get('risk_level', '')
            
            recommendations = []
            
            # 基于市场类型推荐策略
            if "上升趋势" in market_type:
                recommendations.append({
                    "strategy_type": "趋势跟踪",
                    "reason": "上升趋势市场适合趋势跟踪策略",
                    "priority": "高",
                    "suggested_parameters": {
                        "ma_period": "较短周期(5-10)",
                        "stop_loss": "3-5%",
                        "position_size": "中等"
                    }
                })
            elif "下降趋势" in market_type:
                recommendations.append({
                    "strategy_type": "反转策略",
                    "reason": "下降趋势中寻找反转机会",
                    "priority": "中",
                    "suggested_parameters": {
                        "rsi_threshold": "30以下买入",
                        "stop_loss": "严格控制2-3%",
                        "position_size": "较小"
                    }
                })
            elif "震荡市" in market_type:
                recommendations.append({
                    "strategy_type": "网格交易",
                    "reason": "震荡市场适合区间交易策略",
                    "priority": "高",
                    "suggested_parameters": {
                        "grid_spacing": "1-2%",
                        "stop_loss": "宽松5-8%",
                        "position_size": "较大"
                    }
                })
            
            # 基于风险等级调整
            if risk_level == "高风险":
                for rec in recommendations:
                    rec["suggested_parameters"]["position_size"] = "小仓位"
                    rec["suggested_parameters"]["stop_loss"] = "紧密止损"
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成策略推荐失败: {e}")
            return []


# 全局实例
market_intelligence_service = MarketIntelligenceService()