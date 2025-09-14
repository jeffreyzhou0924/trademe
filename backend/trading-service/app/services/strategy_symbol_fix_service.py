"""
策略代码交易对自动修复服务
解决策略代码中硬编码交易对与用户配置不匹配的问题
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger


class StrategySymbolFixService:
    """策略代码交易对自动修复服务"""
    
    @staticmethod
    def fix_strategy_symbol_mismatch(
        strategy_code: str,
        user_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        自动修复策略代码中的交易对不匹配问题
        
        Args:
            strategy_code: 原始策略代码
            user_config: 用户配置（包含exchange, symbols, product_type等）
            
        Returns:
            {
                "fixed": bool,
                "original_code": str,
                "fixed_code": str,
                "changes": List[str],
                "warnings": List[str]
            }
        """
        changes = []
        warnings = []
        fixed_code = strategy_code
        
        try:
            # 1. 提取策略代码中的交易对配置
            symbol_patterns = [
                # DataRequest中的symbol参数
                (r'symbol\s*=\s*["\']([^"\']+)["\']', 'DataRequest symbol'),
                # 其他可能的硬编码位置
                (r'self\.symbol\s*=\s*["\']([^"\']+)["\']', 'self.symbol assignment'),
                (r'symbol\s*:\s*str\s*=\s*["\']([^"\']+)["\']', 'symbol type annotation')
            ]
            
            # 获取用户配置的目标交易对
            target_symbols = user_config.get("symbols", [])
            target_exchange = user_config.get("exchange", "okx")
            target_product_type = user_config.get("product_type", "spot")
            
            if not target_symbols:
                return {
                    "fixed": False,
                    "original_code": strategy_code,
                    "fixed_code": strategy_code,
                    "changes": [],
                    "warnings": ["用户配置中没有指定交易对"]
                }
            
            target_symbol = target_symbols[0]  # 使用第一个交易对
            
            # 2. 根据用户配置生成正确的交易对格式
            correct_symbol = StrategySymbolFixService._generate_correct_symbol_format(
                target_symbol, target_exchange, target_product_type
            )
            
            # 3. 逐个模式匹配和替换
            for pattern, description in symbol_patterns:
                matches = re.finditer(pattern, fixed_code)
                for match in matches:
                    original_symbol = match.group(1)
                    if original_symbol != correct_symbol:
                        # 执行替换
                        fixed_code = fixed_code.replace(
                            match.group(0),
                            match.group(0).replace(original_symbol, correct_symbol)
                        )
                        changes.append(
                            f"{description}: '{original_symbol}' → '{correct_symbol}'"
                        )
                        logger.info(f"修复策略代码交易对: {original_symbol} → {correct_symbol}")
            
            # 4. 检查exchange参数是否需要修复
            exchange_pattern = r'exchange\s*=\s*["\']([^"\']+)["\']'
            exchange_matches = re.finditer(exchange_pattern, fixed_code)
            for match in exchange_matches:
                original_exchange = match.group(1)
                if original_exchange != target_exchange.lower():
                    fixed_code = fixed_code.replace(
                        match.group(0),
                        match.group(0).replace(original_exchange, target_exchange.lower())
                    )
                    changes.append(
                        f"Exchange: '{original_exchange}' → '{target_exchange.lower()}'"
                    )
            
            # 5. 生成警告信息
            if target_product_type == "swap" and "-SWAP" not in correct_symbol:
                warnings.append("配置为合约交易但交易对格式可能不正确")
            
            return {
                "fixed": len(changes) > 0,
                "original_code": strategy_code,
                "fixed_code": fixed_code,
                "changes": changes,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"策略代码修复失败: {str(e)}")
            return {
                "fixed": False,
                "original_code": strategy_code,
                "fixed_code": strategy_code,
                "changes": [],
                "warnings": [f"自动修复失败: {str(e)}"]
            }
    
    @staticmethod
    def _generate_correct_symbol_format(
        symbol: str,
        exchange: str,
        product_type: str
    ) -> str:
        """
        根据交易所和产品类型生成正确的交易对格式
        
        Args:
            symbol: 用户输入的交易对 (如 "BTC/USDT")
            exchange: 交易所 (如 "okx")
            product_type: 产品类型 (如 "spot", "swap")
            
        Returns:
            正确格式的交易对字符串
        """
        # 标准化输入
        symbol = symbol.upper().replace(" ", "")
        exchange = exchange.lower()
        product_type = product_type.lower()
        
        # 提取基础货币和计价货币
        if "/" in symbol:
            base, quote = symbol.split("/")
        elif "-" in symbol and not symbol.endswith("-SWAP"):
            base, quote = symbol.split("-")[:2]
        else:
            # 尝试从BTCUSDT格式中分离
            if "USDT" in symbol:
                base = symbol.replace("USDT", "")
                quote = "USDT"
            else:
                return symbol  # 无法解析，返回原格式
        
        # 根据交易所和产品类型生成格式
        if exchange == "okx":
            if product_type == "spot":
                return f"{base}/{quote}"
            elif product_type == "swap":
                return f"{base}-{quote}-SWAP"
            else:
                return f"{base}-{quote}"
        elif exchange == "binance":
            if product_type == "spot":
                return f"{base}/{quote}"
            elif product_type == "futures":
                return f"{base}/{quote}"
            else:
                return f"{base}/{quote}"
        else:
            # 默认使用斜杠格式
            return f"{base}/{quote}"
    
    @staticmethod
    def validate_symbol_data_availability(
        original_symbol: str,
        corrected_symbol: str,
        available_symbols: List[str]
    ) -> Dict[str, Any]:
        """
        验证修正后的交易对是否有数据可用
        
        Args:
            original_symbol: 原始交易对
            corrected_symbol: 修正后的交易对
            available_symbols: 数据库中可用的交易对列表
            
        Returns:
            验证结果和建议
        """
        # 检查修正后的符号是否在可用列表中
        if corrected_symbol in available_symbols:
            return {
                "valid": True,
                "message": f"修正后的交易对 {corrected_symbol} 数据可用",
                "recommendation": "使用修正后的交易对"
            }
        
        # 寻找最相似的可用交易对
        similar_symbols = []
        corrected_parts = corrected_symbol.replace("-", "/").split("/")
        
        for available_symbol in available_symbols:
            available_parts = available_symbol.replace("-", "/").split("/")
            if len(available_parts) >= 2 and len(corrected_parts) >= 2:
                if corrected_parts[0] in available_parts[0] and corrected_parts[1] in available_parts[1]:
                    similar_symbols.append(available_symbol)
        
        if similar_symbols:
            return {
                "valid": False,
                "message": f"修正后的交易对 {corrected_symbol} 数据不可用",
                "recommendation": f"建议使用: {similar_symbols[0]}",
                "alternatives": similar_symbols[:3]
            }
        
        return {
            "valid": False,
            "message": f"修正后的交易对 {corrected_symbol} 数据不可用",
            "recommendation": "请选择其他交易对或添加相应数据",
            "alternatives": available_symbols[:5] if available_symbols else []
        }


class SmartStrategyRepairer:
    """智能策略修复器 - 综合解决方案"""
    
    @staticmethod
    async def auto_repair_strategy_for_backtest(
        strategy_code: str,
        user_config: Dict[str, Any],
        available_data: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        为回测自动修复策略代码
        
        Args:
            strategy_code: 原始策略代码
            user_config: 用户回测配置
            available_data: 数据库中可用的数据列表 
                          [{"symbol": "BTC/USDT", "exchange": "okx", "timeframe": "1h"}, ...]
            
        Returns:
            完整的修复结果和建议
        """
        results = {
            "success": False,
            "original_code": strategy_code,
            "fixed_code": strategy_code,
            "changes_made": [],
            "validation_results": {},
            "recommendations": [],
            "can_proceed": False
        }
        
        try:
            # 1. 尝试修复交易对不匹配
            fix_result = StrategySymbolFixService.fix_strategy_symbol_mismatch(
                strategy_code, user_config
            )
            
            results["fixed_code"] = fix_result["fixed_code"]
            results["changes_made"] = fix_result["changes"]
            
            # 2. 验证修复后的代码是否有对应数据
            if fix_result["fixed"]:
                # 提取修复后的交易对
                corrected_symbols = []
                for change in fix_result["changes"]:
                    if "→" in change:
                        corrected_symbol = change.split("→")[1].strip().strip("'\"")
                        corrected_symbols.append(corrected_symbol)
                
                # 检查数据可用性
                available_symbols = [data["symbol"] for data in available_data]
                
                for corrected_symbol in corrected_symbols:
                    validation = StrategySymbolFixService.validate_symbol_data_availability(
                        original_symbol="unknown",
                        corrected_symbol=corrected_symbol,
                        available_symbols=available_symbols
                    )
                    
                    results["validation_results"][corrected_symbol] = validation
                    
                    if validation["valid"]:
                        results["can_proceed"] = True
                    else:
                        results["recommendations"].append(validation["recommendation"])
                        if "alternatives" in validation:
                            results["recommendations"].extend([
                                f"可选交易对: {alt}" for alt in validation["alternatives"][:3]
                            ])
            
            # 3. 如果没有进行修复，检查原始配置
            if not fix_result["fixed"]:
                available_symbols = [data["symbol"] for data in available_data]
                user_symbols = user_config.get("symbols", [])
                
                for user_symbol in user_symbols:
                    if user_symbol in available_symbols:
                        results["can_proceed"] = True
                        results["recommendations"].append(f"可以使用用户配置的交易对: {user_symbol}")
                    else:
                        results["recommendations"].append(f"用户配置的交易对 {user_symbol} 数据不可用")
            
            results["success"] = True
            
        except Exception as e:
            logger.error(f"智能策略修复失败: {str(e)}")
            results["recommendations"].append(f"自动修复失败: {str(e)}")
        
        return results