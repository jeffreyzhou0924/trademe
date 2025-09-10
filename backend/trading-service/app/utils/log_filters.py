"""
日志过滤器 - 实现速率限制和敏感数据过滤
"""

import logging
import time
import re
from collections import defaultdict, deque
from typing import Dict, Set, Pattern


class RateLimitFilter(logging.Filter):
    """日志速率限制过滤器 - 防止日志爆炸"""
    
    def __init__(self, max_per_minute: int = 1000, name: str = ""):
        super().__init__(name)
        self.max_per_minute = max_per_minute
        self.timestamps: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_per_minute))
        self.warning_sent: Dict[str, bool] = defaultdict(bool)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录，实施速率限制"""
        current_time = time.time()
        logger_name = record.name
        
        # 获取这个logger的时间戳队列
        timestamps = self.timestamps[logger_name]
        
        # 移除超过1分钟的时间戳
        while timestamps and current_time - timestamps[0] > 60:
            timestamps.popleft()
        
        # 检查是否超过限制
        if len(timestamps) >= self.max_per_minute:
            # 超过限制，发送一次警告后丢弃
            if not self.warning_sent[logger_name]:
                # 创建一个警告记录
                warning_record = logging.LogRecord(
                    name=logger_name,
                    level=logging.WARNING,
                    pathname="",
                    lineno=0,
                    msg=f"日志速率限制触发: {logger_name} 超过 {self.max_per_minute} 条/分钟",
                    args=(),
                    exc_info=None
                )
                # 发送警告
                logging.getLogger(logger_name).handle(warning_record)
                self.warning_sent[logger_name] = True
            
            return False
        
        # 添加当前时间戳
        timestamps.append(current_time)
        
        # 重置警告标志
        if len(timestamps) < self.max_per_minute * 0.8:  # 80%阈值
            self.warning_sent[logger_name] = False
        
        return True


class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器 - 脱敏处理"""
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        
        # 敏感数据模式
        self.patterns: Dict[str, Pattern] = {
            # JWT Token
            'jwt_token': re.compile(r'\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b'),
            
            # API密钥
            'api_key': re.compile(r'(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?key)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]{16,})', re.IGNORECASE),
            
            # 私钥
            'private_key': re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----.*?-----END (?:RSA |EC )?PRIVATE KEY-----', re.DOTALL),
            
            # 银行卡号
            'card_number': re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),
            
            # 邮箱地址（部分脱敏）
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            
            # 手机号
            'phone': re.compile(r'\b(?:\+86)?1[3-9]\d{9}\b'),
            
            # IP地址（保留前两段）
            'ip_address': re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
            
            # 密码字段
            'password': re.compile(r'(?i)(?:password|pwd|pass)["\']?\s*[:=]\s*["\']?([^"\'\s,}]{6,})', re.IGNORECASE),
            
            # 钱包地址（区块链地址）
            'wallet_address': re.compile(r'\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59}|0x[a-fA-F0-9]{40}|T[A-Za-z1-9]{33})\b'),
        }
        
        # 敏感关键词
        self.sensitive_keywords: Set[str] = {
            'secret', 'password', 'token', 'key', 'private', 'auth', 'credential',
            'sign', 'signature', 'encrypt', 'decrypt', 'hash', 'salt'
        }
    
    def mask_sensitive_data(self, text: str) -> str:
        """脱敏处理敏感数据"""
        if not text:
            return text
        
        # JWT Token脱敏
        text = self.patterns['jwt_token'].sub(
            lambda m: f"{m.group()[:10]}...{m.group()[-6:]}",
            text
        )
        
        # API密钥脱敏
        text = self.patterns['api_key'].sub(
            lambda m: f"{m.group().split('=')[0] if '=' in m.group() else m.group().split(':')[0]}=***MASKED***",
            text
        )
        
        # 私钥脱敏
        text = self.patterns['private_key'].sub("-----PRIVATE KEY MASKED-----", text)
        
        # 银行卡号脱敏
        text = self.patterns['card_number'].sub(
            lambda m: f"****-****-****-{m.group()[-4:]}",
            text
        )
        
        # 邮箱脱敏
        text = self.patterns['email'].sub(
            lambda m: f"{m.group().split('@')[0][:3]}***@{m.group().split('@')[1]}",
            text
        )
        
        # 手机号脱敏
        text = self.patterns['phone'].sub(
            lambda m: f"{m.group()[:3]}****{m.group()[-4:]}",
            text
        )
        
        # IP地址脱敏
        text = self.patterns['ip_address'].sub(
            lambda m: f"{'.'.join(m.group().split('.')[:2])}.***.***.***",
            text
        )
        
        # 密码脱敏
        text = self.patterns['password'].sub(
            lambda m: f"{m.group().split('=')[0] if '=' in m.group() else m.group().split(':')[0]}=***MASKED***",
            text
        )
        
        # 钱包地址脱敏
        text = self.patterns['wallet_address'].sub(
            lambda m: f"{m.group()[:6]}...{m.group()[-6:]}",
            text
        )
        
        return text
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录"""
        # 脱敏消息内容
        if hasattr(record, 'msg') and record.msg:
            record.msg = self.mask_sensitive_data(str(record.msg))
        
        # 脱敏参数
        if hasattr(record, 'args') and record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(self.mask_sensitive_data(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        
        # 脱敏异常信息
        if hasattr(record, 'exc_text') and record.exc_text:
            record.exc_text = self.mask_sensitive_data(record.exc_text)
        
        return True


class StructuredLogFilter(logging.Filter):
    """结构化日志过滤器 - 添加上下文信息"""
    
    def __init__(self, name: str = ""):
        super().__init__(name)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """为日志记录添加结构化信息"""
        # 添加进程信息
        import os
        record.process_id = os.getpid()
        
        # 添加线程信息
        import threading
        record.thread_id = threading.get_ident()
        
        # 添加服务信息
        record.service_name = "trading-service"
        record.service_version = "1.0.0"
        
        # 添加环境信息
        record.environment = "production"
        
        return True


class ErrorContextFilter(logging.Filter):
    """错误上下文过滤器 - 为错误日志添加额外上下文"""
    
    def __init__(self, name: str = ""):
        super().__init__(name)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """为错误日志添加上下文信息"""
        if record.levelno >= logging.ERROR:
            # 添加错误分类
            if hasattr(record, 'exc_info') and record.exc_info:
                exc_type = record.exc_info[0]
                if exc_type:
                    record.error_category = exc_type.__name__
                else:
                    record.error_category = "Unknown"
            else:
                record.error_category = "LogError"
            
            # 添加错误严重程度
            if "critical" in str(record.msg).lower() or "fatal" in str(record.msg).lower():
                record.error_severity = "CRITICAL"
            elif record.levelno >= logging.CRITICAL:
                record.error_severity = "CRITICAL"
            elif record.levelno >= logging.ERROR:
                record.error_severity = "HIGH"
            else:
                record.error_severity = "MEDIUM"
        
        return True