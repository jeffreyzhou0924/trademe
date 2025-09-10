"""
API验证中间件
为FastAPI应用提供自动参数验证、安全检查、请求日志记录等功能
"""

import time
import json
import asyncio
import re
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..services.api_validation_service import (
    APIValidationService, ValidationConfig, ValidationType, ValidationRule
)
from ..services.integrated_cache_manager import cache_manager

logger = logging.getLogger(__name__)

class APIValidationMiddleware(BaseHTTPMiddleware):
    """API验证中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        validation_service: APIValidationService,
        enable_logging: bool = True,
        enable_rate_limiting: bool = True,
        enable_security_checks: bool = True,
        enable_caching: bool = True
    ):
        super().__init__(app)
        self.validation_service = validation_service
        self.enable_logging = enable_logging
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_security_checks = enable_security_checks
        self.enable_caching = enable_caching
        
        # 配置端点验证规则
        self._setup_endpoint_validations()
        
        # 排除的路径（不需要验证的）
        self.excluded_paths = {
            "/docs", "/redoc", "/openapi.json",
            "/health", "/metrics", "/favicon.ico"
        }
        
        # 只读端点（GET请求，可以缓存）
        self.readonly_endpoints = {
            "/api/v1/strategies", "/api/v1/market-data",
            "/api/v1/users/profile", "/api/v1/backtest/results"
        }
    
    def _setup_endpoint_validations(self):
        """设置端点验证规则"""
        # 用户相关端点
        self.validation_service.register_endpoint_validation("/api/v1/auth/register", {
            "email": ValidationConfig(
                field_name="email",
                validation_type=ValidationType.EMAIL,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MAX_LENGTH: 100
                },
                error_messages={"required": "邮箱是必填的", "invalid": "邮箱格式无效"}
            ),
            "password": ValidationConfig(
                field_name="password",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_LENGTH: 8,
                    ValidationRule.MAX_LENGTH: 128,
                    ValidationRule.CUSTOM: "password_strength"
                }
            )
        })
        
        self.validation_service.register_endpoint_validation("/api/v1/auth/login", {
            "email": ValidationConfig(
                field_name="email",
                validation_type=ValidationType.EMAIL,
                rules={ValidationRule.REQUIRED: True}
            ),
            "password": ValidationConfig(
                field_name="password",
                validation_type=ValidationType.STRING,
                rules={ValidationRule.REQUIRED: True}
            )
        })
        
        # 交易相关端点
        self.validation_service.register_endpoint_validation("/api/v1/trading/orders", {
            "symbol": ValidationConfig(
                field_name="symbol",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.CUSTOM: "symbol_format"
                }
            ),
            "side": ValidationConfig(
                field_name="side",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.IN_CHOICES: ["buy", "sell"]
                }
            ),
            "type": ValidationConfig(
                field_name="type",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.IN_CHOICES: ["market", "limit", "stop", "stop_limit"]
                }
            ),
            "quantity": ValidationConfig(
                field_name="quantity",
                validation_type=ValidationType.DECIMAL,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_VALUE: 0.00000001,
                    ValidationRule.CUSTOM: "quantity_format"
                }
            ),
            "price": ValidationConfig(
                field_name="price",
                validation_type=ValidationType.DECIMAL,
                rules={
                    ValidationRule.OPTIONAL: True,
                    ValidationRule.MIN_VALUE: 0.00000001,
                    ValidationRule.CUSTOM: "price_format"
                }
            )
        })
        
        # 策略相关端点
        self.validation_service.register_endpoint_validation("/api/v1/strategies", {
            "name": ValidationConfig(
                field_name="name",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_LENGTH: 1,
                    ValidationRule.MAX_LENGTH: 100
                }
            ),
            "code": ValidationConfig(
                field_name="code",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MAX_LENGTH: 50000,
                    ValidationRule.CUSTOM: "strategy_code"
                }
            ),
            "symbols": ValidationConfig(
                field_name="symbols",
                validation_type=ValidationType.LIST,
                rules={ValidationRule.REQUIRED: True}
            )
        })
        
        # AI相关端点
        self.validation_service.register_endpoint_validation("/api/v1/ai/chat", {
            "content": ValidationConfig(
                field_name="content",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_LENGTH: 1,
                    ValidationRule.MAX_LENGTH: 5000
                }
            ),
            "session_type": ValidationConfig(
                field_name="session_type",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.OPTIONAL: True,
                    ValidationRule.IN_CHOICES: ["strategy", "indicator", "debugging", "trading_system", "analysis"]
                }
            ),
            "session_id": ValidationConfig(
                field_name="session_id",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.OPTIONAL: True,
                    ValidationRule.CUSTOM: "session_id_format"
                }
            )
        })
        
        # 市场数据端点
        self.validation_service.register_endpoint_validation("/api/v1/market-data/klines", {
            "symbol": ValidationConfig(
                field_name="symbol",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.CUSTOM: "symbol_format"
                }
            ),
            "interval": ValidationConfig(
                field_name="interval",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.IN_CHOICES: ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
                }
            ),
            "limit": ValidationConfig(
                field_name="limit",
                validation_type=ValidationType.INTEGER,
                rules={
                    ValidationRule.OPTIONAL: True,
                    ValidationRule.MIN_VALUE: 1,
                    ValidationRule.MAX_VALUE: 1000
                }
            )
        })
        
        # 回测相关端点
        self.validation_service.register_endpoint_validation("/api/v1/backtest", {
            "strategy_id": ValidationConfig(
                field_name="strategy_id",
                validation_type=ValidationType.INTEGER,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_VALUE: 1
                }
            ),
            "symbol": ValidationConfig(
                field_name="symbol",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.CUSTOM: "symbol_format"
                }
            ),
            "start_date": ValidationConfig(
                field_name="start_date",
                validation_type=ValidationType.DATE,
                rules={ValidationRule.REQUIRED: True}
            ),
            "end_date": ValidationConfig(
                field_name="end_date",
                validation_type=ValidationType.DATE,
                rules={ValidationRule.REQUIRED: True}
            ),
            "initial_capital": ValidationConfig(
                field_name="initial_capital",
                validation_type=ValidationType.DECIMAL,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_VALUE: 1000
                }
            )
        })
        
        # 钱包相关端点
        self.validation_service.register_endpoint_validation("/api/v1/wallet/transfer", {
            "to_address": ValidationConfig(
                field_name="to_address",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_LENGTH: 25,
                    ValidationRule.MAX_LENGTH: 62
                }
            ),
            "amount": ValidationConfig(
                field_name="amount",
                validation_type=ValidationType.DECIMAL,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.MIN_VALUE: 0.000001
                }
            ),
            "asset": ValidationConfig(
                field_name="asset",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.IN_CHOICES: ["USDT", "BTC", "ETH", "TRX"]
                }
            )
        })
        
        # 数据管理端点
        self.validation_service.register_endpoint_validation("/api/v1/data/download", {
            "exchange": ValidationConfig(
                field_name="exchange",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.IN_CHOICES: ["okx", "binance", "huobi", "bybit"]
                }
            ),
            "symbols": ValidationConfig(
                field_name="symbols",
                validation_type=ValidationType.LIST,
                rules={ValidationRule.REQUIRED: True}
            ),
            "data_type": ValidationConfig(
                field_name="data_type",
                validation_type=ValidationType.STRING,
                rules={
                    ValidationRule.REQUIRED: True,
                    ValidationRule.IN_CHOICES: ["kline", "tick", "orderbook"]
                }
            ),
            "start_date": ValidationConfig(
                field_name="start_date",
                validation_type=ValidationType.DATE,
                rules={ValidationRule.REQUIRED: True}
            ),
            "end_date": ValidationConfig(
                field_name="end_date",
                validation_type=ValidationType.DATE,
                rules={ValidationRule.REQUIRED: True}
            )
        })
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        start_time = time.time()
        
        # 检查是否需要验证
        if self._should_skip_validation(request):
            return await call_next(request)
        
        try:
            # 记录请求日志
            if self.enable_logging:
                await self._log_request(request)
            
            # 安全检查
            if self.enable_security_checks:
                security_check = await self._perform_security_checks(request)
                if not security_check["allowed"]:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "success": False,
                            "message": "安全检查失败",
                            "errors": security_check["errors"]
                        }
                    )
            
            # 访问频率限制
            if self.enable_rate_limiting:
                rate_limit_check = await self._check_rate_limit(request)
                if not rate_limit_check["allowed"]:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "success": False,
                            "message": "访问频率过高",
                            "rate_limit_info": rate_limit_check
                        }
                    )
            
            # 缓存检查（只对GET请求）
            cached_response = None
            if self.enable_caching and request.method == "GET":
                cached_response = await self._check_cache(request)
                if cached_response:
                    return JSONResponse(content=cached_response)
            
            # 参数验证
            validation_result = await self._validate_request(request)
            if not validation_result["is_valid"]:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "参数验证失败",
                        "errors": validation_result["errors"],
                        "warnings": validation_result.get("warnings", [])
                    }
                )
            
            # 将验证后的数据添加到请求中
            if validation_result.get("validated_data"):
                request.state.validated_data = validation_result["validated_data"]
            
            # 执行请求
            response = await call_next(request)
            
            # 缓存响应（对于GET请求和成功响应）
            if (self.enable_caching and request.method == "GET" 
                and response.status_code == 200 and not cached_response):
                await self._cache_response(request, response)
            
            # 记录响应日志
            if self.enable_logging:
                await self._log_response(request, response, start_time)
            
            return response
            
        except Exception as e:
            logger.error(f"API验证中间件处理请求失败: {e}")
            
            # 记录错误日志
            if self.enable_logging:
                await self._log_error(request, e, start_time)
            
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "服务器内部错误",
                    "error": str(e) if logger.level <= logging.DEBUG else "请联系管理员"
                }
            )
    
    def _should_skip_validation(self, request: Request) -> bool:
        """检查是否应跳过验证"""
        path = request.url.path
        
        # 排除的路径
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return True
        
        # 静态资源
        if any(path.endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.ico']):
            return True
        
        return False
    
    async def _log_request(self, request: Request):
        """记录请求日志"""
        try:
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            log_data = {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "timestamp": datetime.utcnow().isoformat(),
                "headers": dict(request.headers)
            }
            
            # 记录请求参数（敏感信息过滤）
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await self._get_request_body(request)
                    if body:
                        # 过滤敏感信息
                        filtered_body = self._filter_sensitive_data(body)
                        log_data["body"] = filtered_body
                except Exception as e:
                    log_data["body_error"] = str(e)
            else:
                log_data["query_params"] = dict(request.query_params)
            
            logger.info(f"API请求: {json.dumps(log_data, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"记录请求日志失败: {e}")
    
    async def _log_response(self, request: Request, response: Response, start_time: float):
        """记录响应日志"""
        try:
            duration = time.time() - start_time
            
            log_data = {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": round(duration * 1000, 2),  # 毫秒
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"API响应: {json.dumps(log_data, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"记录响应日志失败: {e}")
    
    async def _log_error(self, request: Request, error: Exception, start_time: float):
        """记录错误日志"""
        try:
            duration = time.time() - start_time
            
            log_data = {
                "method": request.method,
                "path": request.url.path,
                "error": str(error),
                "error_type": type(error).__name__,
                "duration": round(duration * 1000, 2),
                "client_ip": self._get_client_ip(request),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.error(f"API错误: {json.dumps(log_data, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"记录错误日志失败: {e}")
    
    async def _perform_security_checks(self, request: Request) -> Dict[str, Any]:
        """执行安全检查"""
        try:
            errors = []
            client_ip = self._get_client_ip(request)
            
            # 检查IP黑名单
            # 这里可以实现IP黑名单检查
            
            # 检查User-Agent
            user_agent = request.headers.get("user-agent", "")
            if not user_agent or len(user_agent) < 10:
                errors.append("无效的User-Agent")
            
            # 检查请求头安全性
            suspicious_headers = ["X-Forwarded-For", "X-Real-IP"]
            for header in suspicious_headers:
                if header in request.headers:
                    value = request.headers[header]
                    if self._contains_suspicious_content(value):
                        errors.append(f"可疑的请求头: {header}")
            
            # 检查请求体（如果有）
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await self._get_request_body(request)
                    if body and isinstance(body, dict):
                        for key, value in body.items():
                            if isinstance(value, str) and self._contains_suspicious_content(value):
                                errors.append(f"可疑的参数内容: {key}")
                except:
                    pass  # 忽略解析错误
            
            return {
                "allowed": len(errors) == 0,
                "errors": errors,
                "client_ip": client_ip
            }
            
        except Exception as e:
            logger.error(f"安全检查失败: {e}")
            return {"allowed": True, "errors": [], "error": str(e)}
    
    def _contains_suspicious_content(self, content: str) -> bool:
        """检查是否包含可疑内容"""
        import re  # Import re locally to ensure it's available in method scope
        
        suspicious_patterns = [
            r'<script', r'javascript:', r'onerror=', r'onload=',
            r'union.*select', r'drop.*table', r'insert.*into',
            r'\.\./.*\.\./', r'%2e%2e%2f', r'%252e%252e%252f'
        ]
        
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, content_lower):
                return True
        
        return False
    
    async def _check_rate_limit(self, request: Request) -> Dict[str, Any]:
        """检查访问频率限制"""
        try:
            client_ip = self._get_client_ip(request)
            endpoint = request.url.path
            
            # 从用户认证信息获取用户ID
            user_id = self._get_user_id_from_request(request)
            
            if user_id:
                # 使用缓存管理器检查频率限制
                if hasattr(cache_manager, 'check_api_rate_limit'):
                    rate_limit_result = await cache_manager.check_api_rate_limit(user_id, endpoint)
                    return rate_limit_result
            
            # 如果没有用户ID，使用IP进行简单限制
            # 这里可以实现基于IP的频率限制
            return {"allowed": True}
            
        except Exception as e:
            logger.error(f"检查访问频率限制失败: {e}")
            return {"allowed": True, "error": str(e)}
    
    async def _check_cache(self, request: Request) -> Optional[Dict[str, Any]]:
        """检查缓存"""
        try:
            if not hasattr(cache_manager, 'get_cache_value'):
                return None
            
            # 生成缓存键
            cache_key = f"api_response:{request.url.path}:{hash(str(request.query_params))}"
            
            # 检查缓存
            cached_data = await cache_manager.get_cache_value(cache_key, "api_responses")
            return cached_data
            
        except Exception as e:
            logger.error(f"检查缓存失败: {e}")
            return None
    
    async def _cache_response(self, request: Request, response: Response):
        """缓存响应"""
        try:
            if (not hasattr(cache_manager, 'set_cache_value') or 
                request.url.path not in self.readonly_endpoints):
                return
            
            # 只缓存成功的JSON响应
            if response.status_code == 200:
                cache_key = f"api_response:{request.url.path}:{hash(str(request.query_params))}"
                
                # 这里需要从response中提取内容
                # 由于response已经被处理，这个实现需要在实际使用时调整
                pass
                
        except Exception as e:
            logger.error(f"缓存响应失败: {e}")
    
    async def _validate_request(self, request: Request) -> Dict[str, Any]:
        """验证请求参数"""
        try:
            endpoint = request.url.path
            
            # 获取请求数据
            request_data = {}
            
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await self._get_request_body(request)
                if body:
                    request_data.update(body)
            
            # 添加查询参数
            request_data.update(dict(request.query_params))
            
            # 执行验证
            validation_result = await self.validation_service.validate_request_data(
                endpoint, request_data, request
            )
            
            return {
                "is_valid": validation_result.is_valid,
                "validated_data": validation_result.validated_data,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "transformed_data": validation_result.transformed_data
            }
            
        except Exception as e:
            logger.error(f"验证请求参数失败: {e}")
            return {
                "is_valid": True,  # 验证出错时允许通过
                "errors": [],
                "error": str(e)
            }
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 尝试从代理头获取真实IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 从连接信息获取
        return getattr(request.client, 'host', 'unknown')
    
    def _get_user_id_from_request(self, request: Request) -> Optional[int]:
        """从请求中获取用户ID"""
        try:
            # 这里需要从JWT令牌或会话中获取用户ID
            # 实际实现需要根据认证系统调整
            if hasattr(request.state, 'user'):
                return getattr(request.state.user, 'id', None)
            
            # 从Authorization头解析
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # 这里需要实现JWT解析逻辑
                pass
            
            return None
            
        except Exception as e:
            logger.error(f"获取用户ID失败: {e}")
            return None
    
    async def _get_request_body(self, request: Request) -> Optional[Dict[str, Any]]:
        """获取请求体"""
        try:
            # 检查是否已经读取过
            if hasattr(request.state, 'body'):
                return request.state.body
            
            content_type = request.headers.get("Content-Type", "")
            
            if "application/json" in content_type:
                body = await request.json()
                request.state.body = body
                return body
            elif "application/x-www-form-urlencoded" in content_type:
                form = await request.form()
                body = dict(form)
                request.state.body = body
                return body
            
            return None
            
        except Exception as e:
            logger.error(f"获取请求体失败: {e}")
            return None
    
    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """过滤敏感数据"""
        sensitive_fields = {
            'password', 'confirm_password', 'api_key', 'secret_key',
            'private_key', 'token', 'jwt', 'authorization'
        }
        
        filtered_data = {}
        for key, value in data.items():
            if key.lower() in sensitive_fields:
                filtered_data[key] = "***"
            elif isinstance(value, dict):
                filtered_data[key] = self._filter_sensitive_data(value)
            else:
                filtered_data[key] = value
        
        return filtered_data

# 工具函数
def create_validation_middleware(
    app: FastAPI,
    validation_service: Optional[APIValidationService] = None,
    **middleware_options
) -> APIValidationMiddleware:
    """创建验证中间件"""
    from ..services.api_validation_service import api_validation_service
    
    service = validation_service or api_validation_service
    middleware = APIValidationMiddleware(app, service, **middleware_options)
    
    return middleware

def register_additional_validations(validation_service: APIValidationService):
    """注册额外的验证规则"""
    # 这里可以添加更多的端点验证配置
    pass