"""
数据完整性验证服务
确保回测参数与实际数据源匹配
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.market_data import MarketData
from loguru import logger


class DataValidationService:
    """数据验证服务"""
    
    @staticmethod
    async def validate_backtest_data_availability(
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        product_type: str = "spot"  # 新增：严格验证产品类型
    ) -> Dict[str, Any]:
        """
        验证回测数据可用性
        
        Returns:
            {
                "available": bool,
                "actual_symbol": str,
                "record_count": int,
                "date_range": tuple,
                "suggestions": list,
                "error_message": str
            }
        """
        try:
            # 标准化交易对格式
            normalized_symbols = DataValidationService._normalize_symbol_formats(symbol)
            
            # 查询数据库中的实际数据
            actual_data = None
            actual_symbol = None
            
            for norm_symbol in normalized_symbols:
                query = select(MarketData).where(
                    and_(
                        MarketData.exchange == exchange.lower(),
                        MarketData.symbol == norm_symbol,
                        MarketData.timeframe == timeframe,
                        MarketData.product_type == product_type.lower(),  # 🔧 新增：严格匹配产品类型
                        MarketData.timestamp >= start_date,
                        MarketData.timestamp <= end_date
                    )
                ).limit(1)
                
                result = await db.execute(query)
                data = result.scalar_one_or_none()
                
                if data:
                    actual_data = data
                    actual_symbol = norm_symbol
                    break
            
            if not actual_data:
                # 数据不可用，提供建议
                return await DataValidationService._generate_data_suggestions(
                    db, exchange, symbol, timeframe, product_type
                )
            
            # 统计实际可用数据
            count_query = select(MarketData).where(
                and_(
                    MarketData.exchange == exchange.lower(),
                    MarketData.symbol == actual_symbol,
                    MarketData.timeframe == timeframe,
                    MarketData.product_type == product_type.lower(),  # 🔧 新增：统计时也匹配产品类型
                    MarketData.timestamp >= start_date,
                    MarketData.timestamp <= end_date
                )
            )
            
            result = await db.execute(count_query)
            records = result.scalars().all()
            record_count = len(records)
            
            if record_count < 10:
                return {
                    "available": False,
                    "actual_symbol": actual_symbol,
                    "record_count": record_count,
                    "error_message": f"❌ {product_type.upper()}数据量不足：{exchange.upper()} {actual_symbol} 只有{record_count}条记录，建议至少100条以上",
                    "suggestions": [
                        "扩大时间范围",
                        "选择有更多历史数据的交易对",
                        "使用不同的时间框架",
                        f"确认{exchange.upper()}是否支持{product_type.upper()}交易"
                    ]
                }
            
            # 获取实际日期范围
            date_range = (records[0].timestamp, records[-1].timestamp) if records else None
            
            return {
                "available": True,
                "actual_symbol": actual_symbol,
                "record_count": record_count,
                "date_range": date_range,
                "suggestions": [],
                "error_message": None
            }
            
        except Exception as e:
            logger.error(f"数据验证失败: {str(e)}")
            return {
                "available": False,
                "error_message": f"数据验证过程出错: {str(e)}",
                "suggestions": ["检查数据库连接", "联系系统管理员"]
            }
    
    @staticmethod
    def _normalize_symbol_formats(symbol: str) -> List[str]:
        """
        标准化交易对格式，生成可能的格式变体
        
        Args:
            symbol: 原始交易对格式
            
        Returns:
            可能的交易对格式列表
        """
        formats = []
        
        # 移除空格并转大写
        symbol = symbol.replace(" ", "").upper()
        
        # 处理不同的分隔符格式
        if "/" in symbol:
            # BTC/USDT -> BTC/USDT, BTC-USDT, BTCUSDT, BTC-USDT-SWAP
            base, quote = symbol.split("/")
            formats.extend([
                f"{base}/{quote}",           # BTC/USDT
                f"{base}-{quote}",           # BTC-USDT  
                f"{base}{quote}",            # BTCUSDT
                f"{base}-{quote}-SWAP"       # BTC-USDT-SWAP
            ])
        elif "-" in symbol:
            # BTC-USDT-SWAP -> BTC/USDT, BTC-USDT, BTC-USDT-SWAP
            parts = symbol.split("-")
            if len(parts) >= 2:
                base, quote = parts[0], parts[1]
                formats.extend([
                    f"{base}/{quote}",       # BTC/USDT
                    f"{base}-{quote}",       # BTC-USDT
                    symbol                   # 原始格式
                ])
        else:
            # BTCUSDT -> 尝试常见分割
            if "USDT" in symbol:
                base = symbol.replace("USDT", "")
                formats.extend([
                    f"{base}/USDT",
                    f"{base}-USDT", 
                    symbol,
                    f"{base}-USDT-SWAP"
                ])
        
        # 去重并返回
        return list(set(formats))
    
    @staticmethod
    async def _generate_data_suggestions(
        db: AsyncSession,
        exchange: str,
        symbol: str,
        timeframe: str,
        product_type: str = "spot"
    ) -> Dict[str, Any]:
        """生成数据可用性建议"""
        
        # 查询数据库中实际可用的数据（包含产品类型）
        query = select(MarketData.symbol, MarketData.exchange, MarketData.timeframe, MarketData.product_type).distinct()
        result = await db.execute(query)
        available_data = result.all()
        
        suggestions = []
        
        # 建议可用的交易所
        available_exchanges = set(row[1] for row in available_data)
        if exchange.lower() not in available_exchanges:
            suggestions.append(f"建议使用以下交易所: {', '.join(available_exchanges)}")
        
        # 检查是否存在不同产品类型的相同交易对
        same_symbol_different_type = [
            row for row in available_data 
            if row[1] == exchange.lower() and row[3] != product_type.lower()
        ]
        
        if same_symbol_different_type:
            other_types = set(row[3] for row in same_symbol_different_type)
            suggestions.append(f"🔄 发现相同交易对的其他类型: {', '.join(other_types.intersection({t.lower() for t in ['spot', 'futures']}))}")
        
        # 建议可用的交易对
        available_symbols = set(row[0] for row in available_data if row[1] == exchange.lower() and row[3] == product_type.lower())
        if available_symbols:
            # 找到最相似的交易对
            similar_symbols = [s for s in available_symbols if any(part in s.upper() for part in symbol.upper().split("-"))]
            if similar_symbols:
                suggestions.append(f"建议使用以下{product_type.upper()}交易对: {', '.join(similar_symbols[:3])}")
        
        # 建议可用的时间框架
        available_timeframes = set(row[2] for row in available_data if row[1] == exchange.lower() and row[3] == product_type.lower())
        if timeframe not in available_timeframes and available_timeframes:
            suggestions.append(f"建议使用以下时间框架: {', '.join(available_timeframes)}")
        
        return {
            "available": False,
            "actual_symbol": None,
            "record_count": 0,
            "date_range": None,
            "error_message": f"❌ 未找到 {exchange.upper()} 交易所 {symbol} {timeframe} {product_type.upper()}数据",
            "suggestions": suggestions or [f"请联系管理员添加所需的{product_type.upper()}市场数据"]
        }
    
    @staticmethod
    def validate_strategy_symbol_consistency(
        strategy_code: str,
        user_symbols: List[str]
    ) -> Dict[str, Any]:
        """
        验证策略代码中的交易对与用户配置的一致性
        
        Args:
            strategy_code: 策略代码字符串
            user_symbols: 用户配置的交易对列表
            
        Returns:
            验证结果和修复建议
        """
        # 从策略代码中提取symbol
        import re
        
        # 查找DataRequest中的symbol参数
        pattern = r'symbol\s*=\s*["\']([^"\']+)["\']'
        matches = re.findall(pattern, strategy_code)
        
        if not matches:
            return {
                "consistent": True,
                "strategy_symbols": [],
                "user_symbols": user_symbols,
                "message": "策略代码中未找到硬编码的交易对"
            }
        
        strategy_symbols = matches
        
        # 检查一致性
        for strategy_symbol in strategy_symbols:
            normalized_strategy = DataValidationService._normalize_symbol_formats(strategy_symbol)
            normalized_user = []
            for user_symbol in user_symbols:
                normalized_user.extend(DataValidationService._normalize_symbol_formats(user_symbol))
            
            if not any(s in normalized_user for s in normalized_strategy):
                return {
                    "consistent": False,
                    "strategy_symbols": strategy_symbols,
                    "user_symbols": user_symbols,
                    "message": f"策略代码中的交易对 {strategy_symbol} 与用户配置不匹配",
                    "suggestions": [
                        f"将策略代码中的 {strategy_symbol} 修改为 {user_symbols[0]}",
                        "或者修改回测配置以匹配策略代码"
                    ]
                }
        
        return {
            "consistent": True,
            "strategy_symbols": strategy_symbols,
            "user_symbols": user_symbols,
            "message": "策略代码与用户配置一致"
        }


class BacktestDataValidator:
    """回测数据验证器 - 增强的参数验证"""
    
    @staticmethod
    async def comprehensive_validation(
        db: AsyncSession,
        strategy_code: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        综合验证回测配置和数据可用性
        
        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str], 
                "suggestions": List[str],
                "corrected_config": Dict[str, Any]
            }
        """
        errors = []
        warnings = []
        suggestions = []
        corrected_config = config.copy()
        
        # 1. 验证策略代码与配置的一致性
        consistency_check = DataValidationService.validate_strategy_symbol_consistency(
            strategy_code, config.get("symbols", [])
        )
        
        if not consistency_check["consistent"]:
            errors.append(consistency_check["message"])
            suggestions.extend(consistency_check.get("suggestions", []))
            
            # 尝试自动修正配置
            if consistency_check["strategy_symbols"]:
                strategy_symbol = consistency_check["strategy_symbols"][0]
                # 将策略中的symbol格式转换为配置格式
                if "-SWAP" in strategy_symbol:
                    corrected_config["product_type"] = "swap"
                    corrected_config["symbols"] = [strategy_symbol.replace("-SWAP", "")]
                else:
                    corrected_config["symbols"] = [strategy_symbol]
        
        # 2. 验证数据可用性
        symbols_to_check = corrected_config.get("symbols", config.get("symbols", []))
        product_type = corrected_config.get("product_type", config.get("product_type", "spot"))
        
        for symbol in symbols_to_check:
            validation = await DataValidationService.validate_backtest_data_availability(
                db=db,
                exchange=config.get("exchange", "okx"),
                symbol=symbol,
                timeframe=config.get("timeframes", ["1h"])[0],
                start_date=datetime.fromisoformat(config.get("start_date")),
                end_date=datetime.fromisoformat(config.get("end_date")),
                product_type=product_type  # 🔧 新增：严格验证产品类型匹配
            )
            
            if not validation["available"]:
                errors.append(f"交易对 {symbol}: {validation['error_message']}")
                suggestions.extend(validation.get("suggestions", []))
            else:
                # 如果找到了不同格式的数据，建议使用
                if validation["actual_symbol"] != symbol:
                    warnings.append(f"将使用 {validation['actual_symbol']} 数据代替 {symbol}")
                    corrected_config["symbols"] = [validation["actual_symbol"]]
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "corrected_config": corrected_config
        }