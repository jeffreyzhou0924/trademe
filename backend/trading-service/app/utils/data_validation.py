"""
数据验证和安全解析工具类
处理NULL值、类型转换和数据格式化的安全实现
"""

from typing import Any, Optional, Union
from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """数据验证和安全解析工具类"""

    @staticmethod
    def safe_parse_datetime(value: Any) -> Optional[datetime]:
        """安全地解析日期时间值"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                # 尝试ISO格式解析
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # 尝试时间戳格式
                    if value.isdigit():
                        timestamp = int(value)
                        # 处理毫秒级时间戳
                        if timestamp > 10**12:
                            timestamp = timestamp / 1000
                        return datetime.fromtimestamp(timestamp)
                except (ValueError, OSError):
                    pass
                logger.warning(f"无法解析日期时间值: 类型 {type(value).__name__}, 长度 {len(str(value)) if value else 0}")
                return None
        elif isinstance(value, datetime):
            return value
        elif isinstance(value, (int, float)):
            try:
                # 时间戳转换
                timestamp = float(value)
                if timestamp > 10**12:  # 毫秒级时间戳
                    timestamp = timestamp / 1000
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OSError):
                logger.warning(f"无法解析时间戳: 类型 {type(value).__name__}, 值范围异常")
                return None
        else:
            return None

    @staticmethod
    def safe_parse_float(value: Any, default: float = 0.0) -> float:
        """安全地解析浮点数值"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # 移除可能的货币符号和逗号
                cleaned = value.replace('$', '').replace(',', '').strip()
                return float(cleaned)
            except ValueError:
                logger.warning(f"无法解析浮点数值: 类型 {type(value).__name__}, 长度 {len(str(value)) if value else 0}")
                return default
        return default

    @staticmethod
    def safe_parse_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
        """安全地解析高精度decimal值（用于金融计算）"""
        if value is None:
            return default
        try:
            if isinstance(value, Decimal):
                return value
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            if isinstance(value, str):
                # 移除可能的货币符号和逗号
                cleaned = value.replace('$', '').replace(',', '').strip()
                return Decimal(cleaned)
        except (ValueError, InvalidOperation):
            logger.warning(f"无法解析Decimal值: 类型 {type(value).__name__}, 格式无效")
            return default
        return default

    @staticmethod
    def safe_parse_int(value: Any, default: int = 0) -> int:
        """安全地解析整数值"""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                # 移除可能的非数字字符
                cleaned = ''.join(c for c in value if c.isdigit() or c in '-+')
                return int(cleaned) if cleaned else default
            except ValueError:
                logger.warning(f"无法解析整数值: 类型 {type(value).__name__}, 格式无效")
                return default
        return default

    @staticmethod
    def safe_format_price(value: Any, currency: str = "$", decimals: int = 2, default: str = "N/A") -> str:
        """安全地格式化价格显示"""
        try:
            if value is None:
                return default
            
            # 使用safe_parse_float确保安全转换
            price = DataValidator.safe_parse_float(value, 0.0)
            
            # 格式化价格
            if decimals == 2:
                return f"{currency}{price:,.2f}"
            else:
                format_str = f"{currency}{{:,.{decimals}f}}"
                return format_str.format(price)
        except Exception as e:
            logger.error(f"价格格式化错误: 类型 {type(value).__name__}, 错误类型: {type(e).__name__}")
            return default

    @staticmethod
    def safe_format_decimal(value: Any, decimals: int = 2, default: str = "N/A") -> str:
        """安全地格式化Decimal值显示"""
        try:
            if value is None:
                return default
            
            # 使用safe_parse_decimal确保安全转换
            decimal_value = DataValidator.safe_parse_decimal(value, Decimal('0'))
            
            # 格式化decimal值
            format_str = f"{{:.{decimals}f}}"
            return format_str.format(float(decimal_value))
        except Exception as e:
            logger.error(f"Decimal格式化错误: 类型 {type(value).__name__}, 错误类型: {type(e).__name__}")
            return default

    @staticmethod
    def safe_format_percentage(value: Any, decimals: int = 2, default: str = "N/A") -> str:
        """安全地格式化百分比显示"""
        try:
            if value is None:
                return default
            
            # 使用safe_parse_float确保安全转换
            percentage = DataValidator.safe_parse_float(value, 0.0)
            
            # 添加正负号
            sign = "+" if percentage > 0 else ""
            format_str = f"{{:{sign}.{decimals}f}}%"
            return format_str.format(percentage)
        except Exception as e:
            logger.error(f"百分比格式化错误: 类型 {type(value).__name__}, 错误类型: {type(e).__name__}")
            return default

    @staticmethod
    def safe_format_volume(value: Any, default: str = "N/A") -> str:
        """安全地格式化交易量显示"""
        try:
            if value is None:
                return default
            
            volume = DataValidator.safe_parse_float(value, 0.0)
            
            # 自动选择合适的单位
            if volume >= 1_000_000_000:  # 十亿以上
                return f"{volume/1_000_000_000:.2f}B"
            elif volume >= 1_000_000:     # 百万以上
                return f"{volume/1_000_000:.2f}M"
            elif volume >= 1_000:         # 千以上
                return f"{volume/1_000:.2f}K"
            else:
                return f"{volume:.2f}"
        except Exception as e:
            logger.error(f"交易量格式化错误: 类型 {type(value).__name__}, 错误类型: {type(e).__name__}")
            return default

    @staticmethod
    def validate_price_data(ticker: dict) -> dict:
        """验证和清理价格数据"""
        validated_ticker = {
            "symbol": ticker.get("symbol", "UNKNOWN"),
            "price": DataValidator.safe_parse_float(ticker.get("price")),
            "change_24h": DataValidator.safe_parse_float(ticker.get("change_24h")),
            "volume_24h": DataValidator.safe_parse_float(ticker.get("volume_24h")),
        }
        
        # 添加格式化显示字段
        validated_ticker["formatted_price"] = DataValidator.safe_format_price(validated_ticker["price"])
        validated_ticker["formatted_change"] = DataValidator.safe_format_percentage(validated_ticker["change_24h"])
        validated_ticker["formatted_volume"] = DataValidator.safe_format_volume(validated_ticker["volume_24h"])
        
        # 添加趋势指示
        change = validated_ticker["change_24h"]
        if change > 0:
            validated_ticker["trend"] = "up"
        elif change < 0:
            validated_ticker["trend"] = "down"
        else:
            validated_ticker["trend"] = "flat"
        
        return validated_ticker

    @staticmethod
    def validate_non_null_string(value: Any, field_name: str = "字段", max_length: int = None) -> Optional[str]:
        """验证非空字符串"""
        if value is None:
            return None
        
        if not isinstance(value, str):
            value = str(value)
        
        value = value.strip()
        if not value:
            return None
        
        if max_length and len(value) > max_length:
            logger.warning(f"{field_name}长度超过限制: {len(value)} > {max_length} (内容已截断)")
            return value[:max_length]
        
        return value

    @staticmethod
    def validate_email(email: Any) -> Optional[str]:
        """验证邮箱格式"""
        if not email:
            return None
        
        email = DataValidator.validate_non_null_string(email, "邮箱")
        if not email:
            return None
        
        # 简单的邮箱格式验证
        if '@' in email and '.' in email.split('@')[-1]:
            return email.lower()
        else:
            logger.warning(f"邮箱格式不正确: 长度 {len(email)}, 包含@ {('@' in email)}")
            return None

    @staticmethod
    def sanitize_user_input(value: Any, max_length: int = 1000) -> Optional[str]:
        """清理用户输入，防止注入攻击"""
        if not value:
            return None
        
        # 转换为字符串并清理
        if isinstance(value, str):
            sanitized = value.strip()
        else:
            sanitized = str(value).strip()
        
        # 长度限制
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # 移除潜在的危险字符（基础SQL注入防护）
        dangerous_patterns = ["'", '"', ';', '--', '/*', '*/', 'DROP', 'DELETE', 'UPDATE', 'INSERT']
        for pattern in dangerous_patterns:
            if pattern.upper() in sanitized.upper():
                logger.warning(f"检测到潜在危险输入模式: {pattern}, 输入长度: {len(sanitized)}")
                # 可以选择拒绝输入或者清理，这里选择清理
                sanitized = sanitized.replace(pattern, "")
        
        return sanitized if sanitized else None


# 全局数据验证实例，可以直接导入使用
validator = DataValidator()