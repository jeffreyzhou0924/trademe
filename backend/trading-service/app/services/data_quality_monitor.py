"""
数据质量监控服务
监控K线和Tick数据的完整性、准确性和一致性
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import pandas as pd
import numpy as np
from decimal import Decimal

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class DataQualityMonitor:
    """数据质量监控器"""
    
    def __init__(self):
        self.quality_thresholds = {
            'completeness_min': 95.0,      # 最低完整性要求95%
            'price_volatility_max': 50.0,  # 价格波动上限50%
            'volume_anomaly_factor': 10.0, # 成交量异常因子
            'time_gap_max_minutes': 5      # 最大时间缺口5分钟
        }
    
    async def run_comprehensive_quality_check(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        check_days: int = 7,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """运行全面的数据质量检查"""
        
        should_close_db = False
        if not db:
            db = AsyncSessionLocal()
            should_close_db = True
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=check_days)
            
            logger.info(f"开始数据质量检查: {exchange} {symbol} {timeframe} ({check_days}天)")
            
            # 1. 完整性检查
            completeness_result = await self._check_data_completeness(
                db, exchange, symbol, timeframe, start_date, end_date
            )
            
            # 2. 价格合理性检查
            price_result = await self._check_price_validity(
                db, exchange, symbol, timeframe, start_date, end_date
            )
            
            # 3. 时间连续性检查
            continuity_result = await self._check_time_continuity(
                db, exchange, symbol, timeframe, start_date, end_date
            )
            
            # 4. 成交量异常检查
            volume_result = await self._check_volume_anomalies(
                db, exchange, symbol, timeframe, start_date, end_date
            )
            
            # 5. 数据重复检查
            duplication_result = await self._check_data_duplication(
                db, exchange, symbol, timeframe, start_date, end_date
            )
            
            # 计算综合质量评分
            quality_score = self._calculate_quality_score(
                completeness_result, price_result, continuity_result, 
                volume_result, duplication_result
            )
            
            # 保存质量检查结果
            await self._save_quality_metrics(
                db, exchange, symbol, timeframe, start_date, end_date,
                completeness_result, price_result, continuity_result,
                volume_result, duplication_result, quality_score
            )
            
            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'check_period': f"{start_date} - {end_date}",
                'quality_score': quality_score,
                'completeness': completeness_result,
                'price_validity': price_result,
                'time_continuity': continuity_result,
                'volume_analysis': volume_result,
                'duplication_check': duplication_result,
                'recommendation': self._generate_recommendations(quality_score, completeness_result, price_result)
            }
            
            logger.info(f"数据质量检查完成: 评分 {quality_score:.1f}/100")
            return result
            
        finally:
            if should_close_db:
                await db.close()
    
    async def _check_data_completeness(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """检查数据完整性"""
        
        # 计算期望的K线数量
        timeframe_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440
        }.get(timeframe, 60)
        
        total_minutes = int((end_date - start_date).total_seconds() / 60)
        expected_count = total_minutes // timeframe_minutes
        
        # 查询实际数据数量
        query = """
        SELECT COUNT(*) as actual_count,
               MIN(open_time) as first_timestamp,
               MAX(open_time) as last_timestamp
        FROM kline_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND open_time >= :start_ts 
          AND open_time <= :end_ts
        """
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        row = result.fetchone()
        actual_count = row[0] if row else 0
        first_ts = row[1] if row else None
        last_ts = row[2] if row else None
        
        # 计算完整性
        completeness_percent = (actual_count / expected_count * 100) if expected_count > 0 else 0
        missing_count = max(0, expected_count - actual_count)
        
        return {
            'expected_count': expected_count,
            'actual_count': actual_count,
            'missing_count': missing_count,
            'completeness_percent': completeness_percent,
            'first_timestamp': datetime.fromtimestamp(first_ts / 1000) if first_ts else None,
            'last_timestamp': datetime.fromtimestamp(last_ts / 1000) if last_ts else None,
            'is_complete': completeness_percent >= self.quality_thresholds['completeness_min']
        }
    
    async def _check_price_validity(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """检查价格数据有效性"""
        
        query = """
        SELECT open_price, high_price, low_price, close_price, volume, open_time
        FROM kline_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND open_time >= :start_ts 
          AND open_time <= :end_ts
        ORDER BY open_time ASC
        """
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        rows = result.fetchall()
        
        if not rows:
            return {'valid': False, 'error': '无数据'}
        
        # 转换为数值进行分析
        prices = []
        volumes = []
        invalid_records = []
        
        for i, row in enumerate(rows):
            open_p, high_p, low_p, close_p, volume, timestamp = row
            
            # 检查OHLC逻辑关系
            if not (low_p <= open_p <= high_p and low_p <= close_p <= high_p):
                invalid_records.append({
                    'timestamp': timestamp,
                    'issue': 'OHLC逻辑错误',
                    'data': f"O:{open_p} H:{high_p} L:{low_p} C:{close_p}"
                })
            
            # 检查零值或负值
            if any(p <= 0 for p in [open_p, high_p, low_p, close_p]):
                invalid_records.append({
                    'timestamp': timestamp,
                    'issue': '价格零值或负值',
                    'data': f"O:{open_p} H:{high_p} L:{low_p} C:{close_p}"
                })
            
            # 检查异常波动
            if i > 0:
                prev_close = float(rows[i-1][3])
                current_open = float(open_p)
                volatility = abs(current_open - prev_close) / prev_close * 100
                
                if volatility > self.quality_thresholds['price_volatility_max']:
                    invalid_records.append({
                        'timestamp': timestamp,
                        'issue': f'异常波动 {volatility:.2f}%',
                        'data': f"前收:{prev_close} 当开:{current_open}"
                    })
            
            prices.append(float(close_p))
            volumes.append(float(volume))
        
        # 统计分析
        price_stats = {
            'mean': np.mean(prices),
            'std': np.std(prices),
            'min': np.min(prices),
            'max': np.max(prices),
            'median': np.median(prices)
        }
        
        volume_stats = {
            'mean': np.mean(volumes),
            'std': np.std(volumes),
            'min': np.min(volumes),
            'max': np.max(volumes)
        }
        
        return {
            'valid': len(invalid_records) == 0,
            'total_records': len(rows),
            'invalid_count': len(invalid_records),
            'invalid_records': invalid_records[:10],  # 只返回前10个错误
            'price_statistics': price_stats,
            'volume_statistics': volume_stats,
            'validity_percent': (len(rows) - len(invalid_records)) / len(rows) * 100
        }
    
    async def _check_time_continuity(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """检查时间连续性"""
        
        query = """
        SELECT open_time 
        FROM kline_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND open_time >= :start_ts 
          AND open_time <= :end_ts
        ORDER BY open_time ASC
        """
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        timestamps = [row[0] for row in result.fetchall()]
        
        if not timestamps:
            return {'continuous': False, 'gaps': [], 'gap_count': 0}
        
        # 计算时间间隔
        timeframe_ms = {
            '1m': 60 * 1000, '5m': 5 * 60 * 1000, '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000, '4h': 4 * 60 * 60 * 1000, '1d': 24 * 60 * 60 * 1000
        }.get(timeframe, 60 * 60 * 1000)
        
        # 检查时间缺口
        gaps = []
        for i in range(1, len(timestamps)):
            expected_time = timestamps[i-1] + timeframe_ms
            actual_time = timestamps[i]
            
            if actual_time > expected_time + (timeframe_ms * 0.1):  # 允许10%误差
                gap_duration_minutes = (actual_time - expected_time) / (60 * 1000)
                
                if gap_duration_minutes > self.quality_thresholds['time_gap_max_minutes']:
                    gaps.append({
                        'start_time': datetime.fromtimestamp(timestamps[i-1] / 1000),
                        'end_time': datetime.fromtimestamp(actual_time / 1000),
                        'gap_duration_minutes': gap_duration_minutes
                    })
        
        return {
            'continuous': len(gaps) == 0,
            'total_records': len(timestamps),
            'gap_count': len(gaps),
            'gaps': gaps[:20],  # 最多返回20个缺口
            'continuity_percent': (len(timestamps) - len(gaps)) / len(timestamps) * 100 if timestamps else 0
        }
    
    async def _check_volume_anomalies(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """检查成交量异常"""
        
        query = """
        SELECT volume, open_time 
        FROM kline_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND open_time >= :start_ts 
          AND open_time <= :end_ts
          AND volume IS NOT NULL
        ORDER BY open_time ASC
        """
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        rows = result.fetchall()
        
        if not rows:
            return {'anomalies_detected': False, 'anomaly_count': 0}
        
        volumes = [float(row[0]) for row in rows]
        timestamps = [row[1] for row in rows]
        
        # 计算成交量统计
        volume_mean = np.mean(volumes)
        volume_std = np.std(volumes)
        
        # 检测异常值 (超过平均值+N倍标准差)
        anomaly_threshold = volume_mean + (self.quality_thresholds['volume_anomaly_factor'] * volume_std)
        
        anomalies = []
        for i, (volume, timestamp) in enumerate(zip(volumes, timestamps)):
            if volume > anomaly_threshold:
                anomalies.append({
                    'timestamp': datetime.fromtimestamp(timestamp / 1000),
                    'volume': volume,
                    'anomaly_factor': volume / volume_mean,
                    'description': f'成交量异常: {volume:.2f} (平均值的{volume/volume_mean:.1f}倍)'
                })
        
        return {
            'anomalies_detected': len(anomalies) > 0,
            'anomaly_count': len(anomalies),
            'anomalies': anomalies[:10],  # 最多返回10个异常
            'volume_statistics': {
                'mean': volume_mean,
                'std': volume_std,
                'min': np.min(volumes),
                'max': np.max(volumes),
                'median': np.median(volumes)
            },
            'anomaly_threshold': anomaly_threshold
        }
    
    async def _check_data_duplication(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """检查数据重复"""
        
        query = """
        SELECT open_time, COUNT(*) as count
        FROM kline_data 
        WHERE exchange = :exchange 
          AND symbol = :symbol 
          AND timeframe = :timeframe
          AND open_time >= :start_ts 
          AND open_time <= :end_ts
        GROUP BY open_time
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        """
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        result = await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts
        })
        
        duplicates = result.fetchall()
        
        total_duplicates = sum(row[1] - 1 for row in duplicates)  # 减去正常记录
        
        return {
            'has_duplicates': len(duplicates) > 0,
            'duplicate_timestamps': len(duplicates),
            'total_duplicate_records': total_duplicates,
            'duplicate_details': [
                {
                    'timestamp': datetime.fromtimestamp(row[0] / 1000),
                    'duplicate_count': row[1]
                }
                for row in duplicates[:10]
            ]
        }
    
    def _calculate_quality_score(
        self,
        completeness: Dict[str, Any],
        price_validity: Dict[str, Any],
        continuity: Dict[str, Any],
        volume_analysis: Dict[str, Any],
        duplication: Dict[str, Any]
    ) -> float:
        """计算综合数据质量评分"""
        
        # 权重分配
        weights = {
            'completeness': 0.3,    # 完整性权重30%
            'price_validity': 0.25, # 价格有效性权重25%
            'continuity': 0.25,     # 连续性权重25%
            'volume': 0.1,          # 成交量权重10%
            'duplication': 0.1      # 重复检查权重10%
        }
        
        # 计算各项得分
        completeness_score = min(completeness.get('completeness_percent', 0), 100)
        
        price_score = price_validity.get('validity_percent', 0) if price_validity.get('valid') else 0
        
        continuity_score = continuity.get('continuity_percent', 0) if continuity.get('continuous') else 0
        
        volume_score = 100 if not volume_analysis.get('anomalies_detected') else max(0, 100 - volume_analysis.get('anomaly_count', 0) * 5)
        
        duplication_score = 100 if not duplication.get('has_duplicates') else max(0, 100 - duplication.get('duplicate_timestamps', 0) * 2)
        
        # 加权平均
        total_score = (
            completeness_score * weights['completeness'] +
            price_score * weights['price_validity'] +
            continuity_score * weights['continuity'] +
            volume_score * weights['volume'] +
            duplication_score * weights['duplication']
        )
        
        return round(total_score, 2)
    
    def _generate_recommendations(
        self,
        quality_score: float,
        completeness: Dict[str, Any],
        price_validity: Dict[str, Any]
    ) -> List[str]:
        """生成数据质量改进建议"""
        
        recommendations = []
        
        if quality_score < 70:
            recommendations.append("🔴 数据质量较差，建议重新下载历史数据")
        elif quality_score < 85:
            recommendations.append("🟡 数据质量一般，建议进行数据清理")
        else:
            recommendations.append("✅ 数据质量良好")
        
        if completeness.get('completeness_percent', 0) < 95:
            missing = completeness.get('missing_count', 0)
            recommendations.append(f"📉 数据不完整，缺失 {missing} 条记录，建议补全")
        
        if not price_validity.get('valid', True):
            invalid_count = price_validity.get('invalid_count', 0)
            recommendations.append(f"💰 发现 {invalid_count} 条价格异常记录，建议人工审核")
        
        return recommendations
    
    async def _save_quality_metrics(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        completeness: Dict[str, Any],
        price_validity: Dict[str, Any],
        continuity: Dict[str, Any],
        volume_analysis: Dict[str, Any],
        duplication: Dict[str, Any],
        quality_score: float
    ):
        """保存质量检查结果到数据库"""
        
        query = """
        INSERT OR REPLACE INTO data_quality_metrics 
        (exchange, symbol, timeframe, date_range_start, date_range_end,
         total_expected, total_actual, missing_count, duplicate_count, 
         gap_count, quality_score)
        VALUES (:exchange, :symbol, :timeframe, :start_date, :end_date,
                :expected, :actual, :missing, :duplicates, :gaps, :quality_score)
        """
        
        await db.execute(query, {
            'exchange': exchange.lower(),
            'symbol': symbol,
            'timeframe': timeframe,
            'start_date': start_date,
            'end_date': end_date,
            'expected': completeness.get('expected_count', 0),
            'actual': completeness.get('actual_count', 0),
            'missing': completeness.get('missing_count', 0),
            'duplicates': duplication.get('total_duplicate_records', 0),
            'gaps': continuity.get('gap_count', 0),
            'quality_score': quality_score
        })
        
        await db.commit()

class DataCompletenessService:
    """数据完整性服务"""
    
    def __init__(self):
        self.quality_monitor = DataQualityMonitor()
    
    async def auto_repair_missing_data(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """自动修复缺失数据"""
        
        logger.info(f"开始自动修复数据: {exchange} {symbol} {timeframe}")
        
        # 检查最近7天数据质量
        quality_result = await self.quality_monitor.run_comprehensive_quality_check(
            exchange, symbol, timeframe, check_days=7, db=db
        )
        
        if quality_result['quality_score'] > 90:
            return {'success': True, 'message': '数据质量良好，无需修复'}
        
        # 获取缺失范围
        completeness = quality_result['completeness']
        if not completeness['is_complete']:
            # 尝试从其他数据源补全
            repair_result = await self._repair_from_alternative_sources(
                db, exchange, symbol, timeframe, completeness
            )
            return repair_result
        
        return {'success': False, 'message': '无法自动修复数据'}
    
    async def _repair_from_alternative_sources(
        self,
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        completeness: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从备用数据源修复数据"""
        
        # 尝试从tick数据聚合补全
        from app.services.tick_data_manager import tick_to_kline_aggregator
        
        try:
            # 计算缺失时间范围
            missing_start = completeness.get('first_timestamp') or datetime.now() - timedelta(days=7)
            missing_end = completeness.get('last_timestamp') or datetime.now()
            
            # 使用tick数据回填
            backfilled_count = await tick_to_kline_aggregator.backfill_missing_klines(
                exchange, symbol, timeframe, [(missing_start, missing_end)], db
            )
            
            if backfilled_count > 0:
                return {
                    'success': True,
                    'message': f'成功从tick数据回填 {backfilled_count} 条K线记录',
                    'backfilled_count': backfilled_count
                }
            else:
                return {
                    'success': False,
                    'message': '无可用tick数据进行回填'
                }
                
        except Exception as e:
            logger.error(f"数据修复失败: {str(e)}")
            return {
                'success': False,
                'message': f'数据修复失败: {str(e)}'
            }

# 全局实例
data_quality_monitor = DataQualityMonitor()
data_completeness_service = DataCompletenessService()