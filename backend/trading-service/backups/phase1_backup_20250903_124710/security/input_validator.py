"""
输入验证和安全过滤系统 - Input Validator & Security Filter

功能特性:
- SQL注入防护
- XSS攻击防护  
- 数据格式验证
- 敏感信息过滤
- 文件上传安全
- API参数校验
- 长度和范围检查
"""

import re
import os
import hashlib
import secrets
import html
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email_validator import validate_email, EmailNotValidError
import magic
from loguru import logger

# 危险字符模式
DANGEROUS_PATTERNS = {
    'sql_injection': [
        r'(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b)',
        r'(\bEXEC\b|\bEXECUTE\b|\bSP_\w+)',
        r'(\'|";|--|\*|\|)',
        r'(\bOR\b\s+\d+\s*=\s*\d+|\bAND\b\s+\d+\s*=\s*\d+)',
        r'(\bSCRIPT\b|\bJAVASCRIPT\b|\bVBSCRIPT\b)',
    ],
    'xss_injection': [
        r'<\s*script\b[^<]*(?:(?!<\/\s*script\s*>)<[^<]*)*<\/\s*script\s*>',
        r'<\s*iframe\b[^<]*(?:(?!<\/\s*iframe\s*>)<[^<]*)*<\/\s*iframe\s*>',
        r'javascript\s*:',
        r'on\w+\s*=',
        r'<\s*img\b[^>]*\bsrc\s*=\s*["\']?\s*javascript:',
        r'<\s*link\b[^>]*\bhref\s*=\s*["\']?\s*javascript:',
    ],
    'path_traversal': [
        r'\.\.[\\/]',
        r'[\\/]\.\.[\\/]',
        r'%2e%2e%2f',
        r'%252e%252e%252f',
        r'\0',
    ],
    'command_injection': [
        r'[;&|`$]',
        r'\b(cat|ls|pwd|whoami|id|uname|ps|netstat|ifconfig|ping)\b',
        r'\$\{.*\}',
        r'`.*`',
    ]
}

# 允许的文件类型
ALLOWED_FILE_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': ['application/pdf', 'text/plain', 'text/csv'],
    'archive': ['application/zip', 'application/x-tar', 'application/gzip']
}

# 敏感信息模式
SENSITIVE_PATTERNS = {
    'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone': r'\b\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b',
    'api_key': r'\b[A-Za-z0-9]{32,64}\b',
    'password': r'(?i)password["\s]*[:=]["\s]*([^"\s,}]+)',
    'secret': r'(?i)secret["\s]*[:=]["\s]*([^"\s,}]+)',
    'token': r'(?i)token["\s]*[:=]["\s]*([^"\s,}]+)',
}


class ValidationError(Exception):
    """验证错误异常"""
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


class SecurityThreat(Exception):
    """安全威胁异常"""
    def __init__(self, message: str, threat_type: str, input_data: str):
        self.message = message
        self.threat_type = threat_type
        self.input_data = input_data
        super().__init__(message)


class InputValidator:
    """输入验证器"""
    
    def __init__(self):
        self.logger = logger.bind(service="InputValidator")
        
        # 编译正则表达式以提高性能
        self._compiled_patterns = {}
        for category, patterns in DANGEROUS_PATTERNS.items():
            self._compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
        
        self._sensitive_patterns = {}
        for name, pattern in SENSITIVE_PATTERNS.items():
            self._sensitive_patterns[name] = re.compile(pattern, re.IGNORECASE)
    
    def validate_string(
        self,
        value: str,
        field_name: str = "input",
        max_length: int = 1000,
        min_length: int = 0,
        allow_empty: bool = True,
        sanitize: bool = True,
        check_threats: bool = True
    ) -> str:
        """
        验证字符串输入
        
        Args:
            value: 输入值
            field_name: 字段名
            max_length: 最大长度
            min_length: 最小长度
            allow_empty: 是否允许空值
            sanitize: 是否进行清理
            check_threats: 是否检查安全威胁
            
        Returns:
            验证并清理后的字符串
        """
        if not isinstance(value, str):
            if value is None and allow_empty:
                return ""
            value = str(value)
        
        # 检查是否为空
        if not value.strip() and not allow_empty:
            raise ValidationError(f"{field_name}不能为空", field_name, "EMPTY_VALUE")
        
        # 长度检查
        if len(value) > max_length:
            raise ValidationError(
                f"{field_name}长度不能超过{max_length}个字符",
                field_name, 
                "MAX_LENGTH_EXCEEDED"
            )
        
        if len(value) < min_length:
            raise ValidationError(
                f"{field_name}长度不能少于{min_length}个字符",
                field_name,
                "MIN_LENGTH_NOT_REACHED"
            )
        
        # 安全威胁检查
        if check_threats and value.strip():
            threat_type = self._detect_security_threats(value)
            if threat_type:
                self.logger.warning(f"检测到安全威胁: {threat_type} in {field_name}")
                raise SecurityThreat(
                    f"检测到{threat_type}攻击尝试",
                    threat_type,
                    value[:100] + "..." if len(value) > 100 else value
                )
        
        # 清理输入
        if sanitize:
            value = self._sanitize_string(value)
        
        return value
    
    def validate_numeric(
        self,
        value: Any,
        field_name: str = "numeric",
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        allow_negative: bool = True,
        decimal_places: Optional[int] = None
    ) -> Union[int, float, Decimal]:
        """
        验证数字输入
        
        Args:
            value: 输入值
            field_name: 字段名
            min_value: 最小值
            max_value: 最大值
            allow_negative: 是否允许负数
            decimal_places: 小数位数限制
        """
        if value is None:
            raise ValidationError(f"{field_name}不能为空", field_name, "NULL_VALUE")
        
        # 转换为数字
        try:
            if isinstance(value, str):
                # 检查是否包含危险字符
                if re.search(r'[^\d\.\-\+eE]', value):
                    raise ValidationError(f"{field_name}包含非法字符", field_name, "INVALID_CHARS")
                
                if decimal_places is not None:
                    numeric_value = Decimal(value)
                else:
                    numeric_value = float(value)
            elif isinstance(value, (int, float)):
                numeric_value = Decimal(str(value)) if decimal_places is not None else value
            else:
                raise ValidationError(f"{field_name}类型无效", field_name, "INVALID_TYPE")
                
        except (ValueError, InvalidOperation):
            raise ValidationError(f"{field_name}不是有效的数字", field_name, "INVALID_NUMBER")
        
        # 范围检查
        if min_value is not None and numeric_value < min_value:
            raise ValidationError(
                f"{field_name}不能小于{min_value}",
                field_name,
                "MIN_VALUE_NOT_REACHED"
            )
        
        if max_value is not None and numeric_value > max_value:
            raise ValidationError(
                f"{field_name}不能大于{max_value}",
                field_name,
                "MAX_VALUE_EXCEEDED"
            )
        
        # 负数检查
        if not allow_negative and numeric_value < 0:
            raise ValidationError(f"{field_name}不能为负数", field_name, "NEGATIVE_NOT_ALLOWED")
        
        # 小数位检查
        if decimal_places is not None:
            if isinstance(numeric_value, Decimal):
                if len(str(numeric_value).split('.')[-1]) > decimal_places:
                    raise ValidationError(
                        f"{field_name}小数位数不能超过{decimal_places}位",
                        field_name,
                        "DECIMAL_PLACES_EXCEEDED"
                    )
                return numeric_value
        
        return numeric_value
    
    def validate_email(self, email: str, field_name: str = "email") -> str:
        """验证邮箱地址"""
        if not email:
            raise ValidationError(f"{field_name}不能为空", field_name, "EMPTY_EMAIL")
        
        # 基本安全检查
        email = self.validate_string(email, field_name, max_length=254)
        
        try:
            # 使用email-validator库验证
            validated_email = validate_email(email)
            return validated_email.email
        except EmailNotValidError as e:
            raise ValidationError(f"{field_name}格式无效: {str(e)}", field_name, "INVALID_EMAIL")
    
    def validate_password(
        self,
        password: str,
        field_name: str = "password",
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digits: bool = True,
        require_special_chars: bool = True
    ) -> str:
        """
        验证密码强度
        
        Args:
            password: 密码
            field_name: 字段名
            min_length: 最小长度
            require_uppercase: 需要大写字母
            require_lowercase: 需要小写字母
            require_digits: 需要数字
            require_special_chars: 需要特殊字符
        """
        if not password:
            raise ValidationError(f"{field_name}不能为空", field_name, "EMPTY_PASSWORD")
        
        # 长度检查
        if len(password) < min_length:
            raise ValidationError(
                f"{field_name}长度不能少于{min_length}个字符",
                field_name,
                "PASSWORD_TOO_SHORT"
            )
        
        # 复杂度检查
        errors = []
        
        if require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("至少包含一个大写字母")
        
        if require_lowercase and not re.search(r'[a-z]', password):
            errors.append("至少包含一个小写字母")
        
        if require_digits and not re.search(r'\d', password):
            errors.append("至少包含一个数字")
        
        if require_special_chars and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("至少包含一个特殊字符")
        
        if errors:
            raise ValidationError(
                f"{field_name}强度不够: " + ", ".join(errors),
                field_name,
                "PASSWORD_TOO_WEAK"
            )
        
        return password
    
    def validate_file_upload(
        self,
        file_data: bytes,
        filename: str,
        allowed_types: List[str] = None,
        max_size: int = 10 * 1024 * 1024,  # 10MB
        scan_content: bool = True
    ) -> Dict[str, Any]:
        """
        验证文件上传
        
        Args:
            file_data: 文件数据
            filename: 文件名
            allowed_types: 允许的文件类型
            max_size: 最大文件大小
            scan_content: 是否扫描文件内容
        """
        if not file_data:
            raise ValidationError("文件不能为空", "file", "EMPTY_FILE")
        
        # 文件大小检查
        if len(file_data) > max_size:
            raise ValidationError(
                f"文件大小不能超过{max_size // 1024 // 1024}MB",
                "file_size",
                "FILE_TOO_LARGE"
            )
        
        # 文件名安全检查
        safe_filename = self._sanitize_filename(filename)
        
        # 路径遍历检查
        if self._detect_path_traversal(filename):
            raise SecurityThreat(
                "检测到路径遍历攻击尝试",
                "path_traversal",
                filename
            )
        
        # 文件类型检查
        try:
            detected_type = magic.from_buffer(file_data, mime=True)
        except Exception:
            detected_type = "application/octet-stream"
        
        if allowed_types:
            type_allowed = False
            for type_category in allowed_types:
                if type_category in ALLOWED_FILE_TYPES:
                    if detected_type in ALLOWED_FILE_TYPES[type_category]:
                        type_allowed = True
                        break
                elif detected_type == type_category:
                    type_allowed = True
                    break
            
            if not type_allowed:
                raise ValidationError(
                    f"不支持的文件类型: {detected_type}",
                    "file_type",
                    "UNSUPPORTED_FILE_TYPE"
                )
        
        # 内容扫描
        if scan_content:
            threat_type = self._scan_file_content(file_data)
            if threat_type:
                raise SecurityThreat(
                    f"文件包含恶意内容: {threat_type}",
                    threat_type,
                    filename
                )
        
        return {
            'safe_filename': safe_filename,
            'detected_type': detected_type,
            'file_size': len(file_data),
            'hash': hashlib.sha256(file_data).hexdigest()
        }
    
    def validate_json_data(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Dict[str, Any]],
        field_prefix: str = ""
    ) -> Dict[str, Any]:
        """
        验证JSON数据
        
        Args:
            data: 待验证的数据
            schema: 验证schema
            field_prefix: 字段前缀
            
        Schema格式:
        {
            "field_name": {
                "type": "string|number|email|password",
                "required": True,
                "max_length": 100,
                "min_value": 0,
                "max_value": 1000,
                "allow_empty": False
            }
        }
        """
        validated_data = {}
        
        # 检查必填字段
        for field_name, field_schema in schema.items():
            full_field_name = f"{field_prefix}.{field_name}" if field_prefix else field_name
            
            # 检查是否为必填字段
            if field_schema.get('required', False) and field_name not in data:
                raise ValidationError(f"缺少必填字段: {full_field_name}", field_name, "MISSING_REQUIRED_FIELD")
            
            if field_name not in data:
                continue
            
            value = data[field_name]
            field_type = field_schema.get('type', 'string')
            
            try:
                # 根据类型进行验证
                if field_type == 'string':
                    validated_value = self.validate_string(
                        value,
                        full_field_name,
                        max_length=field_schema.get('max_length', 1000),
                        min_length=field_schema.get('min_length', 0),
                        allow_empty=field_schema.get('allow_empty', True),
                        sanitize=field_schema.get('sanitize', True),
                        check_threats=field_schema.get('check_threats', True)
                    )
                elif field_type == 'number':
                    validated_value = self.validate_numeric(
                        value,
                        full_field_name,
                        min_value=field_schema.get('min_value'),
                        max_value=field_schema.get('max_value'),
                        allow_negative=field_schema.get('allow_negative', True),
                        decimal_places=field_schema.get('decimal_places')
                    )
                elif field_type == 'email':
                    validated_value = self.validate_email(value, full_field_name)
                elif field_type == 'password':
                    validated_value = self.validate_password(
                        value,
                        full_field_name,
                        min_length=field_schema.get('min_length', 8),
                        require_uppercase=field_schema.get('require_uppercase', True),
                        require_lowercase=field_schema.get('require_lowercase', True),
                        require_digits=field_schema.get('require_digits', True),
                        require_special_chars=field_schema.get('require_special_chars', True)
                    )
                elif field_type == 'boolean':
                    validated_value = self._validate_boolean(value, full_field_name)
                elif field_type == 'array':
                    validated_value = self._validate_array(
                        value, 
                        full_field_name,
                        field_schema
                    )
                elif field_type == 'object':
                    nested_schema = field_schema.get('properties', {})
                    validated_value = self.validate_json_data(
                        value,
                        nested_schema,
                        full_field_name
                    )
                else:
                    validated_value = value  # 未知类型，直接通过
                
                validated_data[field_name] = validated_value
                
            except (ValidationError, SecurityThreat) as e:
                # 重新抛出异常，保留原始字段信息
                if hasattr(e, 'field') and not e.field:
                    e.field = full_field_name
                raise
        
        return validated_data
    
    def sanitize_log_data(self, data: str) -> str:
        """清理日志数据，移除敏感信息"""
        if not isinstance(data, str):
            data = str(data)
        
        sanitized = data
        
        # 替换敏感信息
        for pattern_name, pattern in self._sensitive_patterns.items():
            if pattern_name in ['password', 'secret', 'token']:
                sanitized = pattern.sub(f'{pattern_name}=***HIDDEN***', sanitized)
            elif pattern_name == 'credit_card':
                sanitized = pattern.sub('****-****-****-****', sanitized)
            elif pattern_name == 'email':
                sanitized = pattern.sub('***@***.***', sanitized)
            elif pattern_name == 'phone':
                sanitized = pattern.sub('***-***-****', sanitized)
            elif pattern_name == 'api_key':
                sanitized = pattern.sub('***API_KEY***', sanitized)
        
        return sanitized
    
    def _detect_security_threats(self, input_data: str) -> Optional[str]:
        """检测安全威胁"""
        for threat_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(input_data):
                    return threat_type
        return None
    
    def _sanitize_string(self, value: str) -> str:
        """清理字符串"""
        # HTML实体编码
        sanitized = html.escape(value)
        
        # 移除控制字符
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # 移除多余的空白字符
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        if not filename:
            return f"file_{secrets.token_hex(8)}"
        
        # 移除路径字符
        filename = os.path.basename(filename)
        
        # 移除危险字符
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # 限制长度
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        
        # 确保不为空
        if not filename or filename == '.' or filename == '..':
            filename = f"file_{secrets.token_hex(8)}"
        
        return filename
    
    def _detect_path_traversal(self, path: str) -> bool:
        """检测路径遍历攻击"""
        for pattern in self._compiled_patterns['path_traversal']:
            if pattern.search(path):
                return True
        return False
    
    def _scan_file_content(self, file_data: bytes) -> Optional[str]:
        """扫描文件内容中的威胁"""
        try:
            # 尝试将文件内容转换为文本进行检查
            text_content = file_data.decode('utf-8', errors='ignore')
            return self._detect_security_threats(text_content)
        except Exception:
            # 无法解码为文本，跳过内容检查
            return None
    
    def _validate_boolean(self, value: Any, field_name: str) -> bool:
        """验证布尔值"""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            lower_value = value.lower()
            if lower_value in ('true', '1', 'yes', 'on'):
                return True
            elif lower_value in ('false', '0', 'no', 'off'):
                return False
        
        if isinstance(value, int):
            return bool(value)
        
        raise ValidationError(f"{field_name}不是有效的布尔值", field_name, "INVALID_BOOLEAN")
    
    def _validate_array(
        self,
        value: Any,
        field_name: str,
        field_schema: Dict[str, Any]
    ) -> List[Any]:
        """验证数组"""
        if not isinstance(value, list):
            raise ValidationError(f"{field_name}必须是数组", field_name, "NOT_ARRAY")
        
        max_items = field_schema.get('max_items', 100)
        min_items = field_schema.get('min_items', 0)
        
        if len(value) > max_items:
            raise ValidationError(
                f"{field_name}数组长度不能超过{max_items}",
                field_name,
                "ARRAY_TOO_LONG"
            )
        
        if len(value) < min_items:
            raise ValidationError(
                f"{field_name}数组长度不能少于{min_items}",
                field_name,
                "ARRAY_TOO_SHORT"
            )
        
        # 验证数组元素
        item_schema = field_schema.get('items', {})
        if item_schema:
            validated_items = []
            for i, item in enumerate(value):
                try:
                    if item_schema.get('type') == 'string':
                        validated_item = self.validate_string(
                            item,
                            f"{field_name}[{i}]",
                            max_length=item_schema.get('max_length', 1000)
                        )
                    elif item_schema.get('type') == 'number':
                        validated_item = self.validate_numeric(
                            item,
                            f"{field_name}[{i}]",
                            min_value=item_schema.get('min_value'),
                            max_value=item_schema.get('max_value')
                        )
                    else:
                        validated_item = item
                    
                    validated_items.append(validated_item)
                except (ValidationError, SecurityThreat) as e:
                    if hasattr(e, 'field'):
                        e.field = f"{field_name}[{i}]"
                    raise
            
            return validated_items
        
        return value
    
    def generate_csrf_token(self) -> str:
        """生成CSRF令牌"""
        return secrets.token_urlsafe(32)
    
    def verify_csrf_token(self, token: str, session_token: str) -> bool:
        """验证CSRF令牌"""
        if not token or not session_token:
            return False
        
        try:
            return secrets.compare_digest(token, session_token)
        except Exception:
            return False


# 全局输入验证器实例
input_validator = InputValidator()