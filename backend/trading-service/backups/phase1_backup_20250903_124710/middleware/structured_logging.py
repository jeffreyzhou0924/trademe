"""
结构化日志中间件
提供JSON格式的结构化日志记录，支持请求追踪和性能监控
"""

import time
import uuid
import json
import sys
import traceback
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import Request, Response
from loguru import logger
import asyncio

from app.config import settings


class StructuredLogger:
    """结构化日志记录器 - 与标准logging配置兼容"""
    
    def __init__(self):
        self.setup_logger()
    
    def setup_logger(self):
        """配置日志记录器 - 使用标准logging而非loguru"""
        import logging.config
        import yaml
        from pathlib import Path
        
        # 检查是否存在logging.yaml配置文件
        config_file = Path("logging.yaml")
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                logging.config.dictConfig(config)
                print("✅ 使用logging.yaml配置文件")
                return
            except Exception as e:
                print(f"⚠️ 加载logging.yaml失败: {e}, 使用默认配置")
        
        # 回退到loguru配置（保持向后兼容）
        self._setup_loguru_fallback()
    
    def _setup_loguru_fallback(self):
        """Loguru回退配置"""
        # 移除默认的logger配置
        logger.remove()
        
        # 配置JSON格式的结构化日志
        log_format = self._get_log_format()
        
        # 控制台输出 (开发环境)
        if settings.environment == "development":
            logger.add(
                sys.stdout,
                format=log_format,
                level=settings.log_level,
                serialize=False,
                backtrace=True,
                diagnose=True,
                filter=lambda record: not any(skip in record["message"].lower() 
                                             for skip in ["heartbeat", "health check", "ping"])
            )
        
        # 文件输出 - 更小的文件大小和更多备份
        logger.add(
            settings.log_file,
            format=log_format,
            level=settings.log_level,
            rotation="20 MB",  # 减小到20MB
            retention="7 days",  # 减少到7天
            compression="gz",
            serialize=False,
            backtrace=True,
            diagnose=True,
            enqueue=True,  # 异步写入
            filter=lambda record: not any(skip in record["message"].lower() 
                                         for skip in ["heartbeat", "health check", "ping"])
        )
        
        # 错误日志单独文件
        error_log_file = settings.log_file.replace('.log', '.error.log')
        logger.add(
            error_log_file,
            format=log_format,
            level="ERROR",
            rotation="10 MB",
            retention="30 days", 
            compression="gz",
            serialize=False,
            enqueue=True,
            filter=lambda record: record["level"].name in ["ERROR", "CRITICAL"]
        )
        
        print("✅ 使用Loguru回退配置")
    
    def _get_log_format(self) -> str:
        """获取日志格式"""
        if settings.environment == "development":
            # 开发环境使用可读格式，让request_id为可选
            return (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "{message}"
            )
        else:
            # 生产环境使用JSON格式，让request_id为可选
            return "{time} | {level} | {name}:{function}:{line} | {message}"
    
    def log_request_start(self, request: Request, request_id: str) -> Dict[str, Any]:
        """记录请求开始"""
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "request_start"
        }
        
        # 记录用户信息 (如果已认证)
        if hasattr(request.state, 'user') and request.state.user:
            request_info["user_id"] = request.state.user.id
            request_info["user_email"] = request.state.user.email
            request_info["membership_level"] = request.state.user.membership_level
        
        # 过滤敏感信息
        request_info = self._filter_sensitive_data(request_info)
        
        logger.bind(request_id=request_id).info(
            "Request started",
            extra={"structured_data": request_info}
        )
        
        return request_info
    
    def log_request_end(self, request: Request, response: Response, 
                       request_id: str, start_time: float, 
                       request_info: Dict[str, Any]) -> None:
        """记录请求结束"""
        end_time = time.time()
        duration = end_time - start_time
        
        response_info = {
            **request_info,
            "status_code": response.status_code,
            "response_headers": dict(response.headers),
            "duration_ms": round(duration * 1000, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "request_end"
        }
        
        # 性能分级
        if duration > 2.0:
            log_level = "WARNING"
            message = f"Slow request completed in {duration:.3f}s"
        elif duration > 1.0:
            log_level = "INFO"
            message = f"Request completed in {duration:.3f}s"
        else:
            log_level = "INFO"
            message = f"Request completed in {duration:.3f}s"
        
        # 状态码分级
        if response.status_code >= 500:
            log_level = "ERROR"
            message = f"Server error: {response.status_code}"
        elif response.status_code >= 400:
            log_level = "WARNING"
            message = f"Client error: {response.status_code}"
        
        logger.bind(request_id=request_id).log(
            log_level,
            message,
            extra={"structured_data": response_info}
        )
    
    def log_error(self, request: Request, error: Exception, 
                  request_id: str, start_time: float) -> None:
        """记录请求错误"""
        end_time = time.time()
        duration = end_time - start_time
        
        error_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_ip": self._get_client_ip(request),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "duration_ms": round(duration * 1000, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "request_error"
        }
        
        # 记录用户信息 (如果已认证)
        if hasattr(request.state, 'user') and request.state.user:
            error_info["user_id"] = request.state.user.id
            error_info["user_email"] = request.state.user.email
        
        logger.bind(request_id=request_id).error(
            f"Request failed: {error_info.get('error_type', 'Unknown')}: {error_info.get('error_message', str(error))}",
            extra={"structured_data": error_info}
        )
    
    def log_business_event(self, event_type: str, data: Dict[str, Any], 
                          request_id: Optional[str] = None) -> None:
        """记录业务事件"""
        event_info = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        
        if request_id:
            event_info["request_id"] = request_id
        
        logger.bind(request_id=request_id or "system").info(
            f"Business event: {event_type}",
            extra={"structured_data": event_info}
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        return request.client.host if request.client else "unknown"
    
    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """过滤敏感数据"""
        sensitive_keys = {
            "password", "token", "api_key", "secret", "authorization", 
            "cookie", "x-api-key", "x-auth-token"
        }
        
        def filter_dict(d):
            if isinstance(d, dict):
                return {
                    k: filter_dict(v) if not any(sensitive in k.lower() for sensitive in sensitive_keys) 
                    else "[FILTERED]"
                    for k, v in d.items()
                }
            elif isinstance(d, (list, tuple)):
                return [filter_dict(item) for item in d]
            else:
                return d
        
        return filter_dict(data)


# 全局结构化日志器实例
structured_logger = StructuredLogger()


async def structured_logging_middleware(request: Request, call_next):
    """结构化日志中间件"""
    # 生成请求ID
    request_id = str(uuid.uuid4())
    
    # 将请求ID添加到request state
    request.state.request_id = request_id
    
    # 记录请求开始
    start_time = time.time()
    request_info = structured_logger.log_request_start(request, request_id)
    
    try:
        # 执行请求
        response = await call_next(request)
        
        # 记录请求结束
        structured_logger.log_request_end(
            request, response, request_id, start_time, request_info
        )
        
        # 添加请求ID到响应头 (用于调试)
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    except Exception as error:
        # 记录请求错误
        structured_logger.log_error(request, error, request_id, start_time)
        
        # 重新抛出异常让FastAPI处理
        raise


class BusinessEventLogger:
    """业务事件日志记录器"""
    
    @staticmethod
    def log_user_login(user_id: int, email: str, success: bool, 
                      request_id: Optional[str] = None) -> None:
        """记录用户登录事件"""
        structured_logger.log_business_event(
            "user_login",
            {
                "user_id": user_id,
                "email": email,
                "success": success,
                "ip_address": "unknown"  # 在实际使用时应从请求中获取
            },
            request_id
        )
    
    @staticmethod
    def log_strategy_execution(user_id: int, strategy_id: int, 
                              action: str, result: Dict[str, Any],
                              request_id: Optional[str] = None) -> None:
        """记录策略执行事件"""
        structured_logger.log_business_event(
            "strategy_execution",
            {
                "user_id": user_id,
                "strategy_id": strategy_id,
                "action": action,
                "result": result
            },
            request_id
        )
    
    @staticmethod
    def log_trade_execution(user_id: int, trade_data: Dict[str, Any],
                           request_id: Optional[str] = None) -> None:
        """记录交易执行事件"""
        structured_logger.log_business_event(
            "trade_execution",
            {
                "user_id": user_id,
                "trade_data": trade_data
            },
            request_id
        )
    
    @staticmethod
    def log_backtest_completion(user_id: int, backtest_id: int,
                               results: Dict[str, Any],
                               request_id: Optional[str] = None) -> None:
        """记录回测完成事件"""
        structured_logger.log_business_event(
            "backtest_completion",
            {
                "user_id": user_id,
                "backtest_id": backtest_id,
                "results": results
            },
            request_id
        )


# 业务事件日志器实例
business_logger = BusinessEventLogger()