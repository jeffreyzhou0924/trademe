"""
敏感信息脱敏工具类
处理日志记录、API响应和错误信息中的敏感数据保护
"""

import re
from typing import Any, Dict, Union, List
import logging

logger = logging.getLogger(__name__)


class SensitiveInfoMasker:
    """敏感信息脱敏工具类"""

    # 敏感字段模式
    SENSITIVE_PATTERNS = {
        # API密钥和令牌
        'api_key': r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
        'access_token': r'(?i)(access[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
        'bearer_token': r'(?i)(bearer\s+)([a-zA-Z0-9_\-\.]{20,})',
        'refresh_token': r'(?i)(refresh[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
        
        # 密码和秘钥
        'password': r'(?i)(password|pwd|pass)\s*[:=]\s*["\']?([^\s"\']{6,})["\']?',
        'secret': r'(?i)(secret|client_secret)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{10,})["\']?',
        'private_key': r'(?i)(private[_-]?key|privkey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
        
        # 钱包地址和会话ID
        'wallet_address': r'\b(0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|T[a-km-zA-HJ-NP-Z1-9]{33})\b',
        'session_id': r'(?i)(session[_-]?id|sessionid)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
        
        # JWT令牌
        'jwt_token': r'\beyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\b',
        
        # 邮箱地址（部分脱敏）
        'email': r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b',
        
        # 电话号码
        'phone': r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        
        # 信用卡号
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    }

    # 敏感字段名称（用于字典键检查）
    SENSITIVE_FIELD_NAMES = {
        'password', 'pwd', 'pass', 'secret', 'token', 'key', 'api_key', 'apikey',
        'access_token', 'refresh_token', 'bearer_token', 'session_id', 'sessionid',
        'private_key', 'privkey', 'client_secret', 'authorization', 'auth',
        'wallet_address', 'address', 'phone', 'mobile', 'email', 'credit_card'
    }

    @classmethod
    def mask_string(cls, text: str, preserve_chars: int = 4) -> str:
        """
        对字符串进行脱敏处理
        
        Args:
            text: 要脱敏的字符串
            preserve_chars: 保留的字符数（前后各保留多少字符）
            
        Returns:
            脱敏后的字符串
        """
        if not text or len(text) <= preserve_chars * 2:
            return "*" * len(text) if text else ""
        
        if len(text) <= 8:
            # 短字符串只显示首尾各1个字符
            return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"
        
        # 长字符串显示首尾各preserve_chars个字符
        prefix = text[:preserve_chars]
        suffix = text[-preserve_chars:]
        masked_length = len(text) - preserve_chars * 2
        
        return f"{prefix}{'*' * min(masked_length, 10)}{suffix}"

    @classmethod
    def mask_wallet_address(cls, address: str) -> str:
        """专门处理钱包地址的脱敏"""
        if not address:
            return ""
        
        if len(address) <= 10:
            return "*" * len(address)
        
        # 显示前6位和后4位
        return f"{address[:6]}...{address[-4:]}"

    @classmethod
    def mask_email(cls, email: str) -> str:
        """专门处理邮箱地址的脱敏"""
        if not email or '@' not in email:
            return "*" * len(email) if email else ""
        
        username, domain = email.split('@', 1)
        
        if len(username) <= 3:
            masked_username = "*" * len(username)
        else:
            masked_username = f"{username[0]}{'*' * (len(username) - 2)}{username[-1]}"
        
        # 域名也进行部分脱敏
        if '.' in domain:
            domain_parts = domain.split('.')
            masked_domain_parts = []
            for part in domain_parts[:-1]:  # 除了顶级域名外都脱敏
                if len(part) <= 3:
                    masked_domain_parts.append("*" * len(part))
                else:
                    masked_domain_parts.append(f"{part[0]}{'*' * (len(part) - 2)}{part[-1]}")
            masked_domain_parts.append(domain_parts[-1])  # 保留顶级域名
            masked_domain = '.'.join(masked_domain_parts)
        else:
            masked_domain = "*" * len(domain)
        
        return f"{masked_username}@{masked_domain}"

    @classmethod
    def mask_text_content(cls, text: str) -> str:
        """
        对文本内容中的敏感信息进行脱敏
        
        Args:
            text: 要处理的文本内容
            
        Returns:
            脱敏后的文本内容
        """
        if not text:
            return text
        
        masked_text = text
        
        # 应用各种敏感信息模式
        for pattern_name, pattern in cls.SENSITIVE_PATTERNS.items():
            if pattern_name == 'email':
                # 邮箱特殊处理
                def email_replacer(match):
                    return cls.mask_email(match.group(0))
                masked_text = re.sub(pattern, email_replacer, masked_text)
            
            elif pattern_name == 'wallet_address':
                # 钱包地址特殊处理
                def wallet_replacer(match):
                    return cls.mask_wallet_address(match.group(0))
                masked_text = re.sub(pattern, wallet_replacer, masked_text)
            
            elif pattern_name in ['bearer_token']:
                # Bearer token特殊处理
                def bearer_replacer(match):
                    return f"{match.group(1)}{cls.mask_string(match.group(2))}"
                masked_text = re.sub(pattern, bearer_replacer, masked_text)
            
            else:
                # 普通键值对模式
                def generic_replacer(match):
                    if len(match.groups()) >= 2:
                        key_part = match.group(1)
                        value_part = match.group(2)
                        return f"{key_part}: {cls.mask_string(value_part)}"
                    else:
                        return cls.mask_string(match.group(0))
                masked_text = re.sub(pattern, generic_replacer, masked_text)
        
        return masked_text

    @classmethod
    def mask_dict(cls, data: Dict[str, Any], deep_copy: bool = True) -> Dict[str, Any]:
        """
        对字典中的敏感信息进行脱敏
        
        Args:
            data: 要处理的字典
            deep_copy: 是否创建深拷贝
            
        Returns:
            脱敏后的字典
        """
        if not isinstance(data, dict):
            return data
        
        if deep_copy:
            import copy
            result = copy.deepcopy(data)
        else:
            result = data.copy()
        
        for key, value in result.items():
            # 检查键名是否敏感
            if isinstance(key, str) and key.lower() in cls.SENSITIVE_FIELD_NAMES:
                if isinstance(value, str):
                    if key.lower() in ['email']:
                        result[key] = cls.mask_email(value)
                    elif key.lower() in ['address', 'wallet_address']:
                        result[key] = cls.mask_wallet_address(value)
                    else:
                        result[key] = cls.mask_string(value)
                elif isinstance(value, (int, float)):
                    result[key] = "***"
                continue
            
            # 递归处理嵌套字典
            if isinstance(value, dict):
                result[key] = cls.mask_dict(value, deep_copy=False)
            elif isinstance(value, list):
                result[key] = [cls.mask_dict(item, deep_copy=False) if isinstance(item, dict) else item 
                              for item in value]
            elif isinstance(value, str):
                # 检查字符串内容是否包含敏感信息
                result[key] = cls.mask_text_content(value)
        
        return result

    @classmethod
    def mask_log_message(cls, message: str, extra_data: Dict[str, Any] = None) -> tuple[str, Dict[str, Any]]:
        """
        对日志消息进行脱敏处理
        
        Args:
            message: 日志消息
            extra_data: 额外的日志数据
            
        Returns:
            (脱敏后的消息, 脱敏后的额外数据)
        """
        masked_message = cls.mask_text_content(message)
        masked_extra = cls.mask_dict(extra_data) if extra_data else {}
        
        return masked_message, masked_extra

    @classmethod
    def safe_repr(cls, obj: Any, max_length: int = 200) -> str:
        """
        安全的对象字符串表示（自动脱敏）
        
        Args:
            obj: 要转换的对象
            max_length: 最大长度限制
            
        Returns:
            脱敏后的字符串表示
        """
        try:
            if isinstance(obj, dict):
                masked_obj = cls.mask_dict(obj)
                repr_str = str(masked_obj)
            elif isinstance(obj, str):
                repr_str = cls.mask_text_content(obj)
            else:
                repr_str = str(obj)
            
            if len(repr_str) > max_length:
                repr_str = repr_str[:max_length] + "..."
            
            return repr_str
        
        except Exception as e:
            logger.warning(f"对象脱敏表示失败: {e}")
            return f"<{type(obj).__name__} object>"


# 全局脱敏工具实例
masker = SensitiveInfoMasker()


# 便捷函数
def mask_sensitive_data(data: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """便捷的敏感信息脱敏函数"""
    if isinstance(data, str):
        return masker.mask_text_content(data)
    elif isinstance(data, dict):
        return masker.mask_dict(data)
    else:
        return data


def safe_log_format(message: str, *args, **kwargs) -> str:
    """安全的日志格式化函数"""
    try:
        # 脱敏所有参数
        safe_args = [masker.safe_repr(arg) for arg in args]
        safe_kwargs = {k: masker.safe_repr(v) for k, v in kwargs.items()}
        
        # 格式化消息
        if args or kwargs:
            formatted = message.format(*safe_args, **safe_kwargs)
        else:
            formatted = message
        
        # 对最终消息进行脱敏
        return masker.mask_text_content(formatted)
    
    except Exception as e:
        logger.warning(f"日志格式化脱敏失败: {e}")
        return masker.mask_text_content(message)