"""
API参数验证服务
提供企业级API参数验证、数据转换、安全检查、错误处理等功能
"""

import re
import json
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable, Type, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from enum import Enum
import logging
from functools import wraps
from pydantic import BaseModel, ValidationError, validator, Field
from fastapi import HTTPException, Request
from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)

class ValidationType(Enum):
    """验证类型"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    JSON = "json"
    LIST = "list"
    DICT = "dict"

class ValidationRule(Enum):
    """验证规则"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    REGEX = "regex"
    IN_CHOICES = "in_choices"
    NOT_IN = "not_in"
    CUSTOM = "custom"

@dataclass
class ValidationConfig:
    """验证配置"""
    field_name: str
    validation_type: ValidationType
    rules: Dict[ValidationRule, Any] = field(default_factory=dict)
    error_messages: Dict[str, str] = field(default_factory=dict)
    transform_func: Optional[Callable] = None
    security_check: bool = True
    
@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    validated_data: Any = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    transformed_data: Optional[Any] = None

class APIValidationService:
    """API参数验证服务"""
    
    def __init__(self):
        self.validation_configs: Dict[str, Dict[str, ValidationConfig]] = {}
        self.custom_validators: Dict[str, Callable] = {}
        self.security_patterns = self._init_security_patterns()
        
        # 注册默认验证器
        self._register_default_validators()
        
    def _init_security_patterns(self) -> Dict[str, re.Pattern]:
        """初始化安全检查正则模式"""
        return {
            'sql_injection': re.compile(
                r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b|[\'";]|--|\*|\/\*)',
                re.IGNORECASE
            ),
            'xss': re.compile(
                r'<script|javascript:|onerror=|onload=|onclick=|<iframe|<object|<embed',
                re.IGNORECASE
            ),
            'command_injection': re.compile(
                r'(\||&|;|\$\(|\`|<|>|\{|\})',
                re.IGNORECASE
            ),
            'path_traversal': re.compile(
                r'(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)',
                re.IGNORECASE
            )
        }
    
    def _register_default_validators(self):
        """注册默认验证器"""
        self.custom_validators.update({
            'symbol_format': self._validate_trading_symbol,
            'price_format': self._validate_price,
            'quantity_format': self._validate_quantity,
            'password_strength': self._validate_password_strength,
            'api_key_format': self._validate_api_key,
            'session_id_format': self._validate_session_id,
            'jwt_token_format': self._validate_jwt_token,
            'timestamp_format': self._validate_timestamp,
            'ip_address': self._validate_ip_address,
            'strategy_code': self._validate_strategy_code
        })
    
    def register_endpoint_validation(self, endpoint: str, validations: Dict[str, ValidationConfig]):
        """注册端点验证配置"""
        self.validation_configs[endpoint] = validations
        logger.info(f"注册端点验证配置: {endpoint}, 字段数: {len(validations)}")
    
    def register_custom_validator(self, name: str, validator_func: Callable):
        """注册自定义验证器"""
        self.custom_validators[name] = validator_func
        logger.info(f"注册自定义验证器: {name}")
    
    async def validate_request_data(self, endpoint: str, data: Dict[str, Any], 
                                  request: Optional[Request] = None) -> ValidationResult:
        """验证请求数据"""
        try:
            if endpoint not in self.validation_configs:
                logger.warning(f"端点验证配置不存在: {endpoint}")
                return ValidationResult(is_valid=True, validated_data=data)
            
            validations = self.validation_configs[endpoint]
            validated_data = {}
            errors = []
            warnings = []
            
            # 验证每个字段
            for field_name, config in validations.items():
                field_value = data.get(field_name)
                
                # 验证字段
                result = await self._validate_field(field_name, field_value, config, request)
                
                if not result.is_valid:
                    errors.extend(result.errors)
                else:
                    validated_data[field_name] = result.transformed_data or result.validated_data
                
                if result.warnings:
                    warnings.extend(result.warnings)
            
            # 检查必填字段
            for field_name, config in validations.items():
                if ValidationRule.REQUIRED in config.rules and field_name not in data:
                    errors.append(f"字段 '{field_name}' 是必填的")
            
            # 检查多余字段
            extra_fields = set(data.keys()) - set(validations.keys())
            if extra_fields:
                warnings.append(f"发现未定义的字段: {', '.join(extra_fields)}")
            
            is_valid = len(errors) == 0
            
            return ValidationResult(
                is_valid=is_valid,
                validated_data=validated_data if is_valid else data,
                errors=errors,
                warnings=warnings,
                transformed_data=validated_data if is_valid else None
            )
            
        except Exception as e:
            logger.error(f"验证请求数据失败: {e}")
            return ValidationResult(
                is_valid=False,
                validated_data=data,
                errors=[f"验证过程出错: {str(e)}"]
            )
    
    async def _validate_field(self, field_name: str, value: Any, 
                            config: ValidationConfig, 
                            request: Optional[Request] = None) -> ValidationResult:
        """验证单个字段"""
        try:
            errors = []
            warnings = []
            validated_value = value
            
            # 检查必填字段
            if ValidationRule.REQUIRED in config.rules and (value is None or value == ""):
                errors.append(config.error_messages.get('required', f"字段 '{field_name}' 是必填的"))
                return ValidationResult(is_valid=False, errors=errors)
            
            # 可选字段且值为空
            if ValidationRule.OPTIONAL in config.rules and (value is None or value == ""):
                return ValidationResult(is_valid=True, validated_data=None)
            
            # 安全检查
            if config.security_check and isinstance(value, str):
                security_result = self._check_security_threats(value)
                if not security_result.is_valid:
                    errors.extend(security_result.errors)
                    return ValidationResult(is_valid=False, errors=errors)
            
            # 类型验证和转换
            type_result = await self._validate_type(value, config.validation_type)
            if not type_result.is_valid:
                errors.extend(type_result.errors)
                return ValidationResult(is_valid=False, errors=errors)
            
            validated_value = type_result.validated_data
            
            # 规则验证
            rules_result = await self._validate_rules(validated_value, config.rules, field_name)
            if not rules_result.is_valid:
                errors.extend(rules_result.errors)
            
            if rules_result.warnings:
                warnings.extend(rules_result.warnings)
            
            # 数据转换
            if config.transform_func and callable(config.transform_func):
                try:
                    transformed_value = config.transform_func(validated_value)
                    validated_value = transformed_value
                except Exception as e:
                    warnings.append(f"字段 '{field_name}' 转换失败: {str(e)}")
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                validated_data=validated_value,
                errors=errors,
                warnings=warnings,
                transformed_data=validated_value if len(errors) == 0 else None
            )
            
        except Exception as e:
            logger.error(f"字段验证失败 {field_name}: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"字段 '{field_name}' 验证过程出错: {str(e)}"]
            )
    
    def _check_security_threats(self, value: str) -> ValidationResult:
        """检查安全威胁"""
        errors = []
        
        for threat_type, pattern in self.security_patterns.items():
            if pattern.search(value):
                errors.append(f"检测到{threat_type}安全威胁")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    async def _validate_type(self, value: Any, validation_type: ValidationType) -> ValidationResult:
        """验证数据类型"""
        try:
            if validation_type == ValidationType.STRING:
                if not isinstance(value, str):
                    return ValidationResult(is_valid=False, errors=[f"值必须是字符串类型"])
                return ValidationResult(is_valid=True, validated_data=str(value))
                
            elif validation_type == ValidationType.INTEGER:
                try:
                    validated_value = int(value)
                    return ValidationResult(is_valid=True, validated_data=validated_value)
                except (ValueError, TypeError):
                    return ValidationResult(is_valid=False, errors=[f"值必须是整数类型"])
                    
            elif validation_type == ValidationType.FLOAT:
                try:
                    validated_value = float(value)
                    return ValidationResult(is_valid=True, validated_data=validated_value)
                except (ValueError, TypeError):
                    return ValidationResult(is_valid=False, errors=[f"值必须是浮点数类型"])
                    
            elif validation_type == ValidationType.DECIMAL:
                try:
                    validated_value = Decimal(str(value))
                    return ValidationResult(is_valid=True, validated_data=validated_value)
                except (InvalidOperation, TypeError):
                    return ValidationResult(is_valid=False, errors=[f"值必须是有效的小数"])
                    
            elif validation_type == ValidationType.BOOLEAN:
                if isinstance(value, bool):
                    return ValidationResult(is_valid=True, validated_data=value)
                elif isinstance(value, str):
                    if value.lower() in ['true', '1', 'yes', 'on']:
                        return ValidationResult(is_valid=True, validated_data=True)
                    elif value.lower() in ['false', '0', 'no', 'off']:
                        return ValidationResult(is_valid=True, validated_data=False)
                return ValidationResult(is_valid=False, errors=[f"值必须是布尔类型"])
                
            elif validation_type == ValidationType.DATE:
                try:
                    if isinstance(value, str):
                        validated_value = datetime.strptime(value, '%Y-%m-%d').date()
                    elif isinstance(value, datetime):
                        validated_value = value.date()
                    elif isinstance(value, date):
                        validated_value = value
                    else:
                        return ValidationResult(is_valid=False, errors=[f"日期格式无效"])
                    return ValidationResult(is_valid=True, validated_data=validated_value)
                except ValueError:
                    return ValidationResult(is_valid=False, errors=[f"日期格式必须是YYYY-MM-DD"])
                    
            elif validation_type == ValidationType.DATETIME:
                try:
                    if isinstance(value, str):
                        # 尝试多种时间格式
                        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']
                        validated_value = None
                        for fmt in formats:
                            try:
                                validated_value = datetime.strptime(value, fmt)
                                break
                            except ValueError:
                                continue
                        if validated_value is None:
                            return ValidationResult(is_valid=False, errors=[f"时间格式无效"])
                    elif isinstance(value, datetime):
                        validated_value = value
                    else:
                        return ValidationResult(is_valid=False, errors=[f"时间格式无效"])
                    return ValidationResult(is_valid=True, validated_data=validated_value)
                except ValueError:
                    return ValidationResult(is_valid=False, errors=[f"时间格式无效"])
                    
            elif validation_type == ValidationType.EMAIL:
                try:
                    validated_email = validate_email(value)
                    return ValidationResult(is_valid=True, validated_data=validated_email.email)
                except EmailNotValidError:
                    return ValidationResult(is_valid=False, errors=[f"邮箱格式无效"])
                    
            elif validation_type == ValidationType.URL:
                url_pattern = re.compile(
                    r'^https?://'  # http:// or https://
                    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                    r'localhost|'  # localhost...
                    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                    r'(?::\d+)?'  # optional port
                    r'(?:/?|[/?]\S+)$', re.IGNORECASE)
                
                if url_pattern.match(value):
                    return ValidationResult(is_valid=True, validated_data=value)
                return ValidationResult(is_valid=False, errors=[f"URL格式无效"])
                
            elif validation_type == ValidationType.UUID:
                uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                if uuid_pattern.match(value):
                    return ValidationResult(is_valid=True, validated_data=value)
                return ValidationResult(is_valid=False, errors=[f"UUID格式无效"])
                
            elif validation_type == ValidationType.JSON:
                try:
                    if isinstance(value, str):
                        validated_value = json.loads(value)
                    else:
                        validated_value = value
                    return ValidationResult(is_valid=True, validated_data=validated_value)
                except json.JSONDecodeError:
                    return ValidationResult(is_valid=False, errors=[f"JSON格式无效"])
                    
            elif validation_type == ValidationType.LIST:
                if isinstance(value, list):
                    return ValidationResult(is_valid=True, validated_data=value)
                elif isinstance(value, str):
                    try:
                        validated_value = json.loads(value)
                        if isinstance(validated_value, list):
                            return ValidationResult(is_valid=True, validated_data=validated_value)
                    except json.JSONDecodeError:
                        pass
                return ValidationResult(is_valid=False, errors=[f"值必须是数组类型"])
                
            elif validation_type == ValidationType.DICT:
                if isinstance(value, dict):
                    return ValidationResult(is_valid=True, validated_data=value)
                elif isinstance(value, str):
                    try:
                        validated_value = json.loads(value)
                        if isinstance(validated_value, dict):
                            return ValidationResult(is_valid=True, validated_data=validated_value)
                    except json.JSONDecodeError:
                        pass
                return ValidationResult(is_valid=False, errors=[f"值必须是对象类型"])
            
            return ValidationResult(is_valid=True, validated_data=value)
            
        except Exception as e:
            logger.error(f"类型验证失败: {e}")
            return ValidationResult(is_valid=False, errors=[f"类型验证过程出错: {str(e)}"])
    
    async def _validate_rules(self, value: Any, rules: Dict[ValidationRule, Any], 
                            field_name: str) -> ValidationResult:
        """验证规则"""
        errors = []
        warnings = []
        
        try:
            # 长度检查（字符串、列表等）
            if ValidationRule.MIN_LENGTH in rules:
                min_len = rules[ValidationRule.MIN_LENGTH]
                if hasattr(value, '__len__') and len(value) < min_len:
                    errors.append(f"字段 '{field_name}' 长度不能少于 {min_len}")
            
            if ValidationRule.MAX_LENGTH in rules:
                max_len = rules[ValidationRule.MAX_LENGTH]
                if hasattr(value, '__len__') and len(value) > max_len:
                    errors.append(f"字段 '{field_name}' 长度不能超过 {max_len}")
            
            # 数值范围检查
            if ValidationRule.MIN_VALUE in rules:
                min_val = rules[ValidationRule.MIN_VALUE]
                if isinstance(value, (int, float, Decimal)) and value < min_val:
                    errors.append(f"字段 '{field_name}' 值不能小于 {min_val}")
            
            if ValidationRule.MAX_VALUE in rules:
                max_val = rules[ValidationRule.MAX_VALUE]
                if isinstance(value, (int, float, Decimal)) and value > max_val:
                    errors.append(f"字段 '{field_name}' 值不能大于 {max_val}")
            
            # 正则表达式检查
            if ValidationRule.REGEX in rules:
                pattern = rules[ValidationRule.REGEX]
                if isinstance(value, str) and not re.match(pattern, value):
                    errors.append(f"字段 '{field_name}' 格式不正确")
            
            # 选择范围检查
            if ValidationRule.IN_CHOICES in rules:
                choices = rules[ValidationRule.IN_CHOICES]
                if value not in choices:
                    errors.append(f"字段 '{field_name}' 必须是以下值之一: {', '.join(map(str, choices))}")
            
            if ValidationRule.NOT_IN in rules:
                forbidden = rules[ValidationRule.NOT_IN]
                if value in forbidden:
                    errors.append(f"字段 '{field_name}' 不能是以下值: {', '.join(map(str, forbidden))}")
            
            # 自定义验证
            if ValidationRule.CUSTOM in rules:
                custom_validator_name = rules[ValidationRule.CUSTOM]
                if custom_validator_name in self.custom_validators:
                    validator_func = self.custom_validators[custom_validator_name]
                    try:
                        custom_result = await validator_func(value, field_name) if asyncio.iscoroutinefunction(validator_func) else validator_func(value, field_name)
                        if isinstance(custom_result, ValidationResult):
                            if not custom_result.is_valid:
                                errors.extend(custom_result.errors)
                            if custom_result.warnings:
                                warnings.extend(custom_result.warnings)
                        elif not custom_result:
                            errors.append(f"字段 '{field_name}' 自定义验证失败")
                    except Exception as e:
                        errors.append(f"字段 '{field_name}' 自定义验证出错: {str(e)}")
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                validated_data=value,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"规则验证失败 {field_name}: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"字段 '{field_name}' 规则验证出错: {str(e)}"]
            )
    
    # ===========================================
    # 自定义验证器
    # ===========================================
    
    def _validate_trading_symbol(self, value: str, field_name: str) -> ValidationResult:
        """验证交易对格式"""
        symbol_pattern = r'^[A-Z]{3,10}[/-]?[A-Z]{3,10}$'
        if re.match(symbol_pattern, value.upper()):
            return ValidationResult(is_valid=True, validated_data=value.upper())
        return ValidationResult(is_valid=False, errors=[f"交易对格式无效，应为 'BTC/USDT' 或 'BTCUSDT' 格式"])
    
    def _validate_price(self, value: Union[str, int, float], field_name: str) -> ValidationResult:
        """验证价格格式"""
        try:
            price = Decimal(str(value))
            if price <= 0:
                return ValidationResult(is_valid=False, errors=[f"价格必须大于0"])
            
            # 检查小数位数（最多8位小数）
            if price.as_tuple().exponent < -8:
                return ValidationResult(is_valid=False, errors=[f"价格小数位数不能超过8位"])
            
            return ValidationResult(is_valid=True, validated_data=float(price))
            
        except (ValueError, InvalidOperation):
            return ValidationResult(is_valid=False, errors=[f"价格格式无效"])
    
    def _validate_quantity(self, value: Union[str, int, float], field_name: str) -> ValidationResult:
        """验证数量格式"""
        try:
            quantity = Decimal(str(value))
            if quantity <= 0:
                return ValidationResult(is_valid=False, errors=[f"数量必须大于0"])
            
            return ValidationResult(is_valid=True, validated_data=float(quantity))
            
        except (ValueError, InvalidOperation):
            return ValidationResult(is_valid=False, errors=[f"数量格式无效"])
    
    def _validate_password_strength(self, value: str, field_name: str) -> ValidationResult:
        """验证密码强度"""
        errors = []
        warnings = []
        
        if len(value) < 8:
            errors.append("密码长度不能少于8位")
        
        if not re.search(r'[A-Z]', value):
            warnings.append("密码应包含大写字母")
        
        if not re.search(r'[a-z]', value):
            warnings.append("密码应包含小写字母")
        
        if not re.search(r'\d', value):
            warnings.append("密码应包含数字")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            warnings.append("密码应包含特殊字符")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            validated_data=value,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_api_key(self, value: str, field_name: str) -> ValidationResult:
        """验证API密钥格式"""
        # API密钥通常是64位十六进制字符串
        api_key_pattern = r'^[a-fA-F0-9]{64}$'
        if re.match(api_key_pattern, value):
            return ValidationResult(is_valid=True, validated_data=value)
        
        # 或者Base64格式
        if re.match(r'^[A-Za-z0-9+/]{40,}={0,2}$', value):
            return ValidationResult(is_valid=True, validated_data=value)
        
        return ValidationResult(is_valid=False, errors=[f"API密钥格式无效"])
    
    def _validate_session_id(self, value: str, field_name: str) -> ValidationResult:
        """验证会话ID格式"""
        session_pattern = r'^[a-fA-F0-9]{32,128}$'
        if re.match(session_pattern, value):
            return ValidationResult(is_valid=True, validated_data=value)
        return ValidationResult(is_valid=False, errors=[f"会话ID格式无效"])
    
    def _validate_jwt_token(self, value: str, field_name: str) -> ValidationResult:
        """验证JWT令牌格式"""
        jwt_pattern = r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$'
        if re.match(jwt_pattern, value):
            return ValidationResult(is_valid=True, validated_data=value)
        return ValidationResult(is_valid=False, errors=[f"JWT令牌格式无效"])
    
    def _validate_timestamp(self, value: Union[str, int, float], field_name: str) -> ValidationResult:
        """验证时间戳格式"""
        try:
            if isinstance(value, str):
                timestamp = float(value)
            else:
                timestamp = value
            
            # 检查时间戳范围（1970年到2100年）
            if timestamp < 0 or timestamp > 4102444800:  # 2100-01-01
                return ValidationResult(is_valid=False, errors=[f"时间戳超出有效范围"])
            
            # 转换为datetime验证
            dt = datetime.fromtimestamp(timestamp)
            
            return ValidationResult(is_valid=True, validated_data=timestamp)
            
        except (ValueError, OSError):
            return ValidationResult(is_valid=False, errors=[f"时间戳格式无效"])
    
    def _validate_ip_address(self, value: str, field_name: str) -> ValidationResult:
        """验证IP地址格式"""
        # IPv4格式
        ipv4_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        
        # IPv6格式（简化）
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        
        if re.match(ipv4_pattern, value) or re.match(ipv6_pattern, value):
            return ValidationResult(is_valid=True, validated_data=value)
        
        return ValidationResult(is_valid=False, errors=[f"IP地址格式无效"])
    
    def _validate_strategy_code(self, value: str, field_name: str) -> ValidationResult:
        """验证策略代码安全性"""
        warnings = []
        errors = []
        
        # 检查危险的Python关键字和模块
        dangerous_patterns = [
            r'\b(exec|eval|compile|__import__|open|file)\b',
            r'\b(os|sys|subprocess|socket|urllib|requests)\b',
            r'\b(pickle|marshal|shelve|dbm)\b',
            r'__|delattr|setattr|getattr',
            r'globals\(\)|locals\(\)',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                errors.append(f"策略代码包含潜在危险操作: {pattern}")
        
        # 检查代码长度
        if len(value) > 50000:  # 50KB限制
            errors.append("策略代码长度超过限制（50KB）")
        
        # 检查语法（简单）
        try:
            compile(value, '<strategy>', 'exec')
        except SyntaxError as e:
            errors.append(f"策略代码语法错误: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            validated_data=value,
            errors=errors,
            warnings=warnings
        )

# 全局验证服务实例
api_validation_service = APIValidationService()

# 装饰器
def validate_params(endpoint: str, raise_on_error: bool = True):
    """参数验证装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中提取request对象和数据
            request = kwargs.get('request')
            
            # 尝试获取请求数据
            data = {}
            if request:
                try:
                    if request.method in ['POST', 'PUT', 'PATCH']:
                        data = await request.json()
                    else:
                        data = dict(request.query_params)
                except Exception as e:
                    logger.warning(f"获取请求数据失败: {e}")
            
            # 执行验证
            result = await api_validation_service.validate_request_data(endpoint, data, request)
            
            if not result.is_valid and raise_on_error:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "参数验证失败",
                        "errors": result.errors,
                        "warnings": result.warnings
                    }
                )
            
            # 将验证后的数据传入函数
            if result.is_valid and result.transformed_data:
                kwargs['validated_data'] = result.transformed_data
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator