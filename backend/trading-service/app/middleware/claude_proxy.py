"""
Claude请求代理中间件
- 拦截用户的Claude API请求
- 验证虚拟密钥
- 路由到后端Claude账号池
- 记录使用统计
"""

import uuid
import hashlib
import json
import time
import asyncio
from typing import Optional, Dict, Any, Tuple, AsyncGenerator, List
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from enum import Enum
import logging

from app.services.user_claude_key_service import UserClaudeKeyService
from app.services.claude_account_service import ClaudeAccountService
from app.services.claude_performance_monitor import claude_performance_monitor
from app.services.claude_cache_service import claude_cache_service, ContentType, CacheLevel
from app.models.claude_proxy import UserClaudeKey, ClaudeAccount
from app.core.claude_client import ClaudeClient
from app.utils.data_validation import DataValidator

logger = logging.getLogger(__name__)


class ProxyErrorType(str, Enum):
    """代理错误类型枚举"""
    AUTHENTICATION_ERROR = "auth_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    QUOTA_ERROR = "quota_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    ACCOUNT_UNAVAILABLE = "account_unavailable"
    SERVICE_OVERLOAD = "service_overload"
    UNKNOWN_ERROR = "unknown_error"


class CircuitBreakerState(str, Enum):
    """断路器状态"""
    CLOSED = "closed"      # 正常工作
    OPEN = "open"          # 断路器打开，拒绝请求
    HALF_OPEN = "half_open"  # 半开状态，尝试恢复


class AccountCircuitBreaker:
    """Claude账号断路器 - 防止持续请求失败的账号"""
    
    def __init__(self, account_id: int, failure_threshold: int = 5, 
                 recovery_timeout: int = 300, success_threshold: int = 2):
        """
        Args:
            account_id: Claude账号ID
            failure_threshold: 失败阈值，超过此值打开断路器
            recovery_timeout: 恢复超时时间（秒）
            success_threshold: 半开状态下成功阈值，达到后关闭断路器
        """
        self.account_id = account_id
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        # 状态跟踪
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_request_time: Optional[datetime] = None
        
    def record_success(self):
        """记录成功请求"""
        self.last_request_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._reset_to_closed()
        elif self.state == CircuitBreakerState.CLOSED:
            # 重置失败计数
            self.failure_count = 0
            
    def record_failure(self, error_type: ProxyErrorType):
        """记录失败请求"""
        self.last_request_time = datetime.utcnow()
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._open_circuit()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # 半开状态下失败，重新打开断路器
            self._open_circuit()
            
    def can_execute_request(self) -> bool:
        """判断是否可以执行请求"""
        current_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # 检查是否可以转为半开状态
            if (self.last_failure_time and 
                (current_time - self.last_failure_time).total_seconds() > self.recovery_timeout):
                self._move_to_half_open()
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def _open_circuit(self):
        """打开断路器"""
        self.state = CircuitBreakerState.OPEN
        self.success_count = 0
        logger.warning(f"🔴 Claude账号 {self.account_id} 断路器打开 - 失败次数: {self.failure_count}")
    
    def _move_to_half_open(self):
        """转为半开状态"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        logger.info(f"🟡 Claude账号 {self.account_id} 断路器半开 - 尝试恢复")
    
    def _reset_to_closed(self):
        """重置为关闭状态"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"🟢 Claude账号 {self.account_id} 断路器关闭 - 已恢复正常")
    
    def get_status(self) -> dict:
        """获取断路器状态"""
        return {
            "account_id": self.account_id,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "can_execute": self.can_execute_request()
        }


class ProxyFallbackManager:
    """代理降级管理器"""
    
    def __init__(self):
        self.circuit_breakers: Dict[int, AccountCircuitBreaker] = {}
        self.request_queue: Dict[str, List[datetime]] = {}  # 用于请求频率控制
        self.queue_timeout = timedelta(minutes=1)  # 队列清理超时
        
    def get_circuit_breaker(self, account_id: int) -> AccountCircuitBreaker:
        """获取或创建账号的断路器"""
        if account_id not in self.circuit_breakers:
            self.circuit_breakers[account_id] = AccountCircuitBreaker(account_id)
        return self.circuit_breakers[account_id]
    
    def can_use_account(self, account_id: int) -> bool:
        """判断账号是否可用"""
        breaker = self.get_circuit_breaker(account_id)
        return breaker.can_execute_request()
    
    def record_account_success(self, account_id: int):
        """记录账号成功"""
        breaker = self.get_circuit_breaker(account_id)
        breaker.record_success()
    
    def record_account_failure(self, account_id: int, error_type: ProxyErrorType):
        """记录账号失败"""
        breaker = self.get_circuit_breaker(account_id)
        breaker.record_failure(error_type)
    
    def add_request_to_queue(self, user_key: str) -> bool:
        """将请求添加到队列，实现简单的频率控制"""
        current_time = datetime.utcnow()
        
        if user_key not in self.request_queue:
            self.request_queue[user_key] = []
        
        # 清理过期的请求记录
        cutoff_time = current_time - self.queue_timeout
        self.request_queue[user_key] = [
            req_time for req_time in self.request_queue[user_key]
            if req_time > cutoff_time
        ]
        
        # 检查频率限制（每分钟最多60个请求）
        if len(self.request_queue[user_key]) >= 60:
            logger.warning(f"⚠️ 用户请求过于频繁: {user_key}")
            return False
        
        # 添加当前请求
        self.request_queue[user_key].append(current_time)
        return True
    
    def get_available_accounts(self, all_accounts: List[ClaudeAccount]) -> List[ClaudeAccount]:
        """获取可用的账号列表（过滤掉断路器打开的账号）"""
        available_accounts = []
        
        for account in all_accounts:
            if self.can_use_account(account.id):
                available_accounts.append(account)
            else:
                logger.debug(f"🚫 跳过不可用账号: {account.id}")
        
        return available_accounts
    
    def get_fallback_strategy(self, error_type: ProxyErrorType) -> str:
        """根据错误类型确定降级策略"""
        fallback_strategies = {
            ProxyErrorType.RATE_LIMIT_ERROR: "retry_with_delay",
            ProxyErrorType.QUOTA_ERROR: "switch_account", 
            ProxyErrorType.AUTHENTICATION_ERROR: "switch_account",
            ProxyErrorType.NETWORK_ERROR: "retry_with_backoff",
            ProxyErrorType.TIMEOUT_ERROR: "retry_with_timeout_increase",
            ProxyErrorType.ACCOUNT_UNAVAILABLE: "switch_account",
            ProxyErrorType.SERVICE_OVERLOAD: "queue_request",
            ProxyErrorType.UNKNOWN_ERROR: "retry_with_backoff"
        }
        return fallback_strategies.get(error_type, "fail_fast")
    
    def get_statistics(self) -> dict:
        """获取降级管理器统计信息"""
        circuit_stats = []
        for account_id, breaker in self.circuit_breakers.items():
            circuit_stats.append(breaker.get_status())
        
        return {
            "total_circuit_breakers": len(self.circuit_breakers),
            "active_users_in_queue": len(self.request_queue),
            "circuit_breaker_stats": circuit_stats
        }


class ClaudeProxyMiddleware:
    """Claude代理中间件 - 处理用户虚拟密钥到真实账号的路由，包含完整的错误处理和降级机制"""
    
    def __init__(self):
        self.fallback_manager = ProxyFallbackManager()
        
    @staticmethod
    def _create_instance() -> 'ClaudeProxyMiddleware':
        """创建实例（用于保持向后兼容）"""
        return ClaudeProxyMiddleware()
    
    async def validate_and_route_request(
        self,
        db: AsyncSession,
        virtual_api_key: str,
        request_data: Dict[str, Any],
        request_type: str = "chat"
    ) -> Tuple[UserClaudeKey, ClaudeAccount]:
        """
        验证虚拟密钥并路由到合适的Claude账号 - 增强版本，包含断路器和降级机制
        
        Args:
            db: 数据库会话
            virtual_api_key: 用户的虚拟API密钥
            request_data: 请求数据
            request_type: 请求类型 (chat, analysis, generation, etc.)
            
        Returns:
            Tuple[UserClaudeKey, ClaudeAccount]: 用户密钥和目标Claude账号
            
        Raises:
            HTTPException: 验证失败或路由失败时抛出
        """
        # 1. 验证虚拟密钥
        user_key = await UserClaudeKeyService.get_user_key_by_virtual_key(db, virtual_api_key)
        if not user_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的API密钥"
            )
        
        if user_key.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API密钥已{user_key.status}"
            )
        
        # 2. 频率控制检查
        if not self.fallback_manager.add_request_to_queue(virtual_api_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求频率过高，请稍后重试"
            )
        
        # 3. 检查使用限制
        estimated_tokens = self._estimate_tokens(request_data)
        estimated_cost = self._estimate_cost(estimated_tokens)
        
        limits_check = await UserClaudeKeyService.check_usage_limits(
            db, user_key, estimated_tokens, estimated_cost
        )
        
        if not limits_check["can_proceed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "使用量已达限制",
                    "limits_exceeded": limits_check["limit_exceeded"],
                    "remaining": limits_check["remaining"]
                }
            )
        
        # 4. 智能路由到Claude账号（使用断路器过滤）
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 获取所有可用账号
                claude_service = ClaudeAccountService()
                all_accounts = await claude_service.list_accounts(active_only=True)
                
                # 使用断路器过滤可用账号
                available_accounts = self.fallback_manager.get_available_accounts(all_accounts)
                
                if not available_accounts:
                    # 所有账号都不可用，检查是否可以等待恢复
                    if retry_count < max_retries - 1:
                        logger.warning(f"⚠️ 所有Claude账号不可用，等待恢复...")
                        await asyncio.sleep(2 ** retry_count)  # 指数退避
                        retry_count += 1
                        continue
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="所有Claude服务账号暂时不可用，请稍后重试"
                        )
                
                # 路由到最佳账号
                claude_account = await self._select_best_account(
                    db, user_key, available_accounts, request_type, estimated_cost, request_data
                )
                
                if claude_account:
                    logger.info(f"🎯 已路由到Claude账号: {claude_account.account_name} (ID: {claude_account.id})")
                    return user_key, claude_account
                else:
                    logger.warning(f"⚠️ 路由失败，尝试次数: {retry_count + 1}")
                    
            except Exception as e:
                logger.warning(f"⚠️ 路由过程异常 (尝试 {retry_count + 1}): {e}")
            
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(1)  # 短暂等待后重试
        
        # 最终失败
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="暂无可用的Claude服务账号，请稍后重试"
        )
    
    async def _select_best_account(
        self, 
        db: AsyncSession, 
        user_key: UserClaudeKey,
        available_accounts: List[ClaudeAccount],
        request_type: str,
        estimated_cost: Decimal,
        request_data: Dict[str, Any]
    ) -> Optional[ClaudeAccount]:
        """
        从可用账号中选择最佳账号
        
        Args:
            db: 数据库会话
            user_key: 用户虚拟密钥
            available_accounts: 可用账号列表
            request_type: 请求类型
            estimated_cost: 估算成本
            request_data: 请求数据
            
        Returns:
            选中的Claude账号，如果没有则返回None
        """
        if not available_accounts:
            return None
        
        # 优先级策略：
        # 1. 同会话粘性（如果有session_id）
        # 2. 负载最低的账号
        # 3. 成功率最高的账号
        
        session_id = request_data.get("session_id")
        
        # 1. 检查会话粘性
        if session_id:
            for account in available_accounts:
                if (hasattr(account, 'sticky_session_enabled') and 
                    account.sticky_session_enabled and
                    hasattr(account, 'preferred_sessions') and
                    session_id in getattr(account, 'preferred_sessions', [])):
                    logger.info(f"🔗 使用会话粘性账号: {account.id}")
                    return account
        
        # 2. 选择负载最低的账号（基于当前使用量）
        best_account = None
        lowest_load = float('inf')
        
        for account in available_accounts:
            # 计算负载分数（使用量/限额）
            current_usage = float(account.current_usage or 0)
            daily_limit = float(account.daily_limit or 100)
            load_ratio = current_usage / daily_limit if daily_limit > 0 else 1.0
            
            # 加入断路器状态权重
            circuit_breaker = self.fallback_manager.get_circuit_breaker(account.id)
            if circuit_breaker.state == CircuitBreakerState.CLOSED:
                load_penalty = 0
            elif circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
                load_penalty = 0.1  # 小额惩罚
            else:
                continue  # 跳过打开状态的断路器
            
            total_load = load_ratio + load_penalty
            
            if total_load < lowest_load:
                lowest_load = total_load
                best_account = account
        
        if best_account:
            logger.info(f"📊 选择最低负载账号: {best_account.id} (负载: {lowest_load:.3f})")
            return best_account
        
        # 3. 如果都不满足，返回第一个可用账号
        return available_accounts[0] if available_accounts else None
    
    async def proxy_claude_request(
        self,
        db: AsyncSession,
        user_key: UserClaudeKey,
        claude_account: ClaudeAccount,
        request_data: Dict[str, Any],
        request_type: str = "chat"
    ) -> Dict[str, Any]:
        """
        代理Claude请求到后端账号 - 集成断路器、降级机制、性能监控和智能缓存的完整版本
        
        Args:
            db: 数据库会话
            user_key: 用户虚拟密钥
            claude_account: 目标Claude账号
            request_data: 请求数据
            request_type: 请求类型
            
        Returns:
            Dict: Claude API响应数据
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        success = False
        error_type: Optional[ProxyErrorType] = None
        error_code = None
        error_message = None
        response_data = {}
        input_tokens = 0
        output_tokens = 0
        api_cost = Decimal('0')
        cache_hit = False
        
        # 🎯 1. 智能缓存检查
        content_type = self._determine_content_type(request_type, request_data)
        cache_key, content_hash = claude_cache_service.generate_cache_key(
            request_data, user_key.user_id, content_type
        )
        
        # 尝试从缓存获取响应
        cached_response = await claude_cache_service.get_cached_response(cache_key, content_hash)
        if cached_response:
            cache_hit = True
            response_data = cached_response
            success = True
            
            # 从缓存中提取token信息（如果有）
            usage_info = cached_response.get("usage", {})
            input_tokens = usage_info.get("input_tokens", 0)
            output_tokens = usage_info.get("output_tokens", 0)
            api_cost = Decimal('0')  # 缓存命中不产生API成本
            
            logger.info(f"🎯 缓存命中: {cache_key} - 用户{user_key.user_id}")
            
            # 记录性能指标（缓存命中）
            response_time_ms = int((time.time() - start_time) * 1000)
            claude_performance_monitor.record_api_call(
                account_id=claude_account.id,
                user_id=user_key.user_id,
                response_time_ms=response_time_ms,
                success=True,
                cost_usd=0.0,
                error_type=None
            )
            
            # 直接返回缓存结果，跳过API调用
            await self._log_request_completion(
                db, user_key, claude_account, request_id, request_type,
                input_tokens, output_tokens, api_cost, start_time,
                success=True, cache_hit=True,
                session_id=request_data.get("session_id"),
                ai_mode=request_data.get("ai_mode"),
                request_content_hash=content_hash,
                response_content_hash=ClaudeProxyMiddleware._hash_content(str(response_data))
            )
            
            return response_data
        
        # 🔄 2. 执行实际API调用
        # 获取降级策略配置
        max_retries = 3
        retry_count = 0
        base_delay = 1.0  # 基础重试延迟
        
        # 记录代理选择信息
        proxy_info = ClaudeProxyMiddleware._get_proxy_info(claude_account)
        logger.info(f"🔄 代理路由: 用户{user_key.user_id} -> 账号{claude_account.id} -> {proxy_info}")
        
        while retry_count <= max_retries:
            try:
                # 检查断路器状态
                if not self.fallback_manager.can_use_account(claude_account.id):
                    logger.warning(f"🚫 账号{claude_account.id}断路器开启，跳过请求")
                    error_type = ProxyErrorType.ACCOUNT_UNAVAILABLE
                    error_message = "账号暂时不可用"
                    break
                
                # 根据代理类型配置Claude客户端
                claude_client = await ClaudeProxyMiddleware._create_claude_client_with_proxy(claude_account)
                
                # 发送请求到Claude API
                if request_type == "chat":
                    response_data = await claude_client.chat_completion(
                        messages=request_data.get("messages", []),
                        model=request_data.get("model", "claude-sonnet-4-20250514"),
                        max_tokens=request_data.get("max_tokens", 4000),
                        temperature=request_data.get("temperature", 0.7),
                        system=request_data.get("system")
                    )
                elif request_type == "analysis":
                    response_data = await claude_client.analyze_content(
                        content=request_data.get("content", ""),
                        analysis_type=request_data.get("analysis_type", "general"),
                        context=request_data.get("context", {})
                    )
                elif request_type == "generation":
                    response_data = await claude_client.generate_content(
                        prompt=request_data.get("prompt", ""),
                        content_type=request_data.get("content_type", "text"),
                        parameters=request_data.get("parameters", {})
                    )
                else:
                    raise ValueError(f"不支持的请求类型: {request_type}")
                
                # 🎯 请求成功 - 记录到断路器
                success = True
                self.fallback_manager.record_account_success(claude_account.id)
                
                # 提取token使用信息
                usage_info = response_data.get("usage", {})
                input_tokens = usage_info.get("input_tokens", 0)
                output_tokens = usage_info.get("output_tokens", 0)
                
                # 计算成本 (根据Claude-3 Sonnet定价)
                api_cost = ClaudeProxyMiddleware._calculate_api_cost(input_tokens, output_tokens)
                
                # 🎯 3. 智能缓存存储 (成功响应)
                cache_level = claude_cache_service.determine_cache_level(request_data, content_type)
                if cache_level != CacheLevel.NONE:
                    await claude_cache_service.cache_response(
                        cache_key=cache_key,
                        content_hash=content_hash,
                        response=response_data,
                        cache_level=cache_level,
                        content_type=content_type,
                        user_id=user_key.user_id,
                        account_id=claude_account.id
                    )
                    logger.debug(f"💾 响应已缓存: {cache_key} (级别: {cache_level.value})")
                
                # 📊 4. 记录性能指标 (成功)
                response_time_ms = int((time.time() - start_time) * 1000)
                claude_performance_monitor.record_api_call(
                    account_id=claude_account.id,
                    user_id=user_key.user_id,
                    response_time_ms=response_time_ms,
                    success=True,
                    cost_usd=float(api_cost),
                    error_type=None
                )
                
                logger.info(f"✅ Claude请求成功: 账号{claude_account.id}, 耗时{response_time_ms}ms, 成本${DataValidator.safe_format_decimal(api_cost, decimals=6)}")
                break  # 成功后退出重试循环
                
            except Exception as e:
                error_message = str(e)
                
                # 🔍 分类错误类型 (使用ProxyErrorType枚举)
                if "rate_limit" in error_message.lower() or "429" in error_message:
                    error_type = ProxyErrorType.RATE_LIMIT_ERROR
                    error_code = "RATE_LIMIT_EXCEEDED"
                elif "quota" in error_message.lower() or "insufficient" in error_message.lower():
                    error_type = ProxyErrorType.QUOTA_ERROR
                    error_code = "QUOTA_EXCEEDED"
                elif "authentication" in error_message.lower() or "401" in error_message or "403" in error_message:
                    error_type = ProxyErrorType.AUTHENTICATION_ERROR
                    error_code = "AUTH_ERROR"
                elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
                    error_type = ProxyErrorType.TIMEOUT_ERROR
                    error_code = "TIMEOUT"
                elif "network" in error_message.lower() or "connection" in error_message.lower():
                    error_type = ProxyErrorType.NETWORK_ERROR
                    error_code = "NETWORK_ERROR"
                elif "service unavailable" in error_message.lower() or "502" in error_message or "503" in error_message:
                    error_type = ProxyErrorType.SERVICE_OVERLOAD
                    error_code = "SERVICE_OVERLOAD"
                else:
                    error_type = ProxyErrorType.UNKNOWN_ERROR
                    error_code = "UNKNOWN_ERROR"
                
                # 🚫 记录失败到断路器
                self.fallback_manager.record_account_failure(claude_account.id, error_type)
                logger.warning(f"❌ Claude请求失败: 账号{claude_account.id}, 错误类型{error_type}, 消息: {error_message}")
                
                # 🔄 获取降级策略
                fallback_strategy = self.fallback_manager.get_fallback_strategy(error_type)
                logger.info(f"🛠️ 采用降级策略: {fallback_strategy}")
                
                # 根据策略决定是否重试
                if retry_count < max_retries and fallback_strategy in ["retry_with_delay", "retry_with_backoff", "retry_with_timeout_increase"]:
                    retry_count += 1
                    
                    # 计算重试延迟
                    if fallback_strategy == "retry_with_backoff":
                        delay = base_delay * (2 ** (retry_count - 1))  # 指数退避
                    elif fallback_strategy == "retry_with_delay":
                        delay = base_delay * retry_count  # 线性延迟
                    else:
                        delay = base_delay
                    
                    logger.info(f"🔄 重试第{retry_count}次，延迟{delay:.1f}秒")
                    await asyncio.sleep(delay)
                    
                    # 对于超时错误，增加timeout参数
                    if error_type == ProxyErrorType.TIMEOUT_ERROR and "max_tokens" in request_data:
                        request_data["timeout"] = request_data.get("timeout", 30) + 10
                    
                    continue
                elif fallback_strategy == "switch_account":
                    # 应该在上层处理账号切换，这里直接失败
                    logger.error(f"🔄 需要切换账号，但在单账号请求中无法处理")
                    break
                elif fallback_strategy == "queue_request":
                    # 简单的队列处理：短暂延迟后重试
                    if retry_count < max_retries:
                        retry_count += 1
                        delay = 5.0  # 服务过载时等待5秒
                        logger.info(f"⏳ 服务过载，排队等待{delay}秒")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        break
                else:
                    # fail_fast 或其他策略，直接失败
                    break
        
        # 🏁 处理最终结果
        if success:
            logger.info(f"🎉 Claude代理请求最终成功: 账号{claude_account.id}")
        else:
            logger.error(f"💥 Claude代理请求最终失败: 账号{claude_account.id}, 错误类型: {error_type}")
            
            # 根据错误类型返回用户友好的消息
            if error_type == ProxyErrorType.RATE_LIMIT_ERROR:
                response_data = {"error": "请求过于频繁，请稍后重试"}
            elif error_type == ProxyErrorType.QUOTA_ERROR:
                response_data = {"error": "服务配额已耗尽，请联系管理员"}
            elif error_type == ProxyErrorType.AUTHENTICATION_ERROR:
                response_data = {"error": "认证失败，请检查API密钥配置"}
            elif error_type == ProxyErrorType.TIMEOUT_ERROR:
                response_data = {"error": "请求超时，请稍后重试"}
            elif error_type == ProxyErrorType.SERVICE_OVERLOAD:
                response_data = {"error": "服务繁忙，请稍后重试"}
            elif error_type == ProxyErrorType.ACCOUNT_UNAVAILABLE:
                response_data = {"error": "账号暂时不可用，系统正在自动恢复"}
            else:
                response_data = {"error": "请求处理失败，请稍后重试"}
        
        # 📊 记录统计信息
        response_time_ms = int((time.time() - start_time) * 1000)
        charged_cost = api_cost * Decimal('2')  # 按2倍成本计费
        
        try:
            await UserClaudeKeyService.log_usage(
                db=db,
                user_key=user_key,
                claude_account=claude_account,
                request_id=request_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost_usd=api_cost,
                charged_cost_usd=charged_cost,
                success=success,
                error_code=error_code,
                error_message=error_message,
                response_time_ms=response_time_ms,
                session_id=request_data.get("session_id"),
                ai_mode=request_data.get("ai_mode"),
                request_content_hash=ClaudeProxyMiddleware._hash_content(str(request_data)),
                response_content_hash=ClaudeProxyMiddleware._hash_content(str(response_data))
            )
            
            # 更新Claude账号使用统计
            claude_service = ClaudeAccountService()
            await claude_service.log_usage(
                account_id=claude_account.id,
                user_id=user_key.user_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost=api_cost,
                response_time=response_time_ms,
                success=success,
                error_code=error_code,
                error_message=error_message
            )
        except Exception as log_error:
            logger.error(f"📊 记录使用统计失败: {log_error}")
        
        # 🚨 如果请求最终失败，抛出HTTP异常
        if not success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Claude API请求失败",
                    "error_type": error_type.value if error_type else "unknown",
                    "error_code": error_code,
                    "error_details": error_message,
                    "retry_count": retry_count
                }
            )
        
        return response_data
    
    @staticmethod
    async def _create_claude_client_with_proxy(claude_account: ClaudeAccount) -> ClaudeClient:
        """
        根据账号配置创建支持不同代理类型的Claude客户端
        
        Args:
            claude_account: Claude账号配置
            
        Returns:
            配置好代理的ClaudeClient实例
        """
        # 1. 确定代理类型和配置
        proxy_type = claude_account.proxy_type or "direct"
        
        if proxy_type == "proxy_service" and claude_account.proxy_base_url:
            # 外部代理服务 (如 claude.cloudcdn7.com)
            claude_client = ClaudeClient(
                api_key=claude_account.api_key,
                base_url=claude_account.proxy_base_url,  # 使用代理服务URL
                organization_id=claude_account.organization_id,
                project_id=claude_account.project_id
            )
            
        elif proxy_type == "oauth" and claude_account.oauth_access_token:
            # OAuth代理认证
            claude_client = ClaudeClient(
                api_key=claude_account.oauth_access_token,  # 使用OAuth token
                base_url=claude_account.proxy_base_url or ClaudeClient.BASE_URL,
                organization_id=claude_account.organization_id,
                project_id=claude_account.project_id
            )
            
        elif proxy_type == "direct" or claude_account.proxy_id is None:
            # 直连模式
            claude_client = ClaudeClient(
                api_key=claude_account.api_key,
                base_url=claude_account.proxy_base_url or ClaudeClient.BASE_URL,
                organization_id=claude_account.organization_id,
                project_id=claude_account.project_id
            )
            
        else:
            # 默认直连
            claude_client = ClaudeClient(
                api_key=claude_account.api_key,
                organization_id=claude_account.organization_id,
                project_id=claude_account.project_id
            )
        
        # 2. 配置传统HTTP代理(如果存在)
        # 注意：现在主要使用proxy_base_url和proxy_type，不再依赖proxy关系
        # 如果需要配置传统HTTP代理，应该通过proxy_base_url字段
        
        return claude_client
    
    @staticmethod
    def _get_proxy_info(claude_account: ClaudeAccount) -> str:
        """
        获取代理配置的可读信息
        
        Args:
            claude_account: Claude账号配置
            
        Returns:
            代理信息字符串
        """
        proxy_type = claude_account.proxy_type or "direct"
        
        if proxy_type == "proxy_service" and claude_account.proxy_base_url:
            return f"外部代理服务({claude_account.proxy_base_url})"
        elif proxy_type == "oauth":
            return f"OAuth认证({claude_account.proxy_base_url or '标准端点'})"
        elif proxy_type == "direct":
            if claude_account.proxy_base_url:
                return f"直连({claude_account.proxy_base_url})"
            else:
                return "标准直连"
        elif claude_account.proxy_id is not None:
            return f"传统HTTP代理(ID: {claude_account.proxy_id})"
        else:
            return "默认配置"
    
    def _determine_content_type(self, request_type: str, request_data: Dict[str, Any]) -> ContentType:
        """
        根据请求类型和数据确定内容类型
        
        Args:
            request_type: 请求类型 (如 'chat', 'analysis', 'generation')
            request_data: 请求数据
            
        Returns:
            ContentType: 内容类型枚举值
        """
        # 根据request_type直接映射
        if request_type == "chat":
            return ContentType.CHAT
        elif request_type == "analysis":
            return ContentType.ANALYSIS
        elif request_type == "generation":
            return ContentType.GENERATION
        
        # 根据request_data中的session_type进一步判断
        session_type = request_data.get("session_type", "")
        if session_type == "strategy":
            return ContentType.STRATEGY
        elif session_type == "indicator":
            return ContentType.INDICATOR
        
        # 根据request_data中的ai_mode判断
        ai_mode = request_data.get("ai_mode", "")
        if ai_mode == "developer" and "策略" in str(request_data.get("content", "")):
            return ContentType.STRATEGY
        elif ai_mode == "developer" and "指标" in str(request_data.get("content", "")):
            return ContentType.INDICATOR
        
        # 默认返回CHAT类型
        return ContentType.CHAT
    
    @staticmethod
    def _estimate_tokens(request_data: Dict[str, Any]) -> int:
        """
        估算请求的token使用量
        """
        # 简单估算：每个字符约0.75个token (对中文)
        content_length = 0
        
        if "messages" in request_data:
            for message in request_data["messages"]:
                content_length += len(str(message.get("content", "")))
        elif "content" in request_data:
            content_length += len(str(request_data["content"]))
        elif "prompt" in request_data:
            content_length += len(str(request_data["prompt"]))
        
        estimated_tokens = int(content_length * 0.75)
        
        # 加上预期输出tokens (根据max_tokens参数)
        max_tokens = request_data.get("max_tokens", 4000)
        estimated_tokens += max_tokens * 0.3  # 假设平均使用30%的max_tokens
        
        return max(estimated_tokens, 100)  # 最少100 tokens
    
    @staticmethod
    def _estimate_cost(tokens: int) -> Decimal:
        """
        估算API成本 (基于Claude-3 Sonnet定价)
        """
        # Claude-3 Sonnet定价 (每1M tokens)
        # Input: $3.00, Output: $15.00
        # 保守估算：假设输入输出各占50%
        input_cost = Decimal(str(tokens * 0.5)) * Decimal('3.00') / Decimal('1000000')
        output_cost = Decimal(str(tokens * 0.5)) * Decimal('15.00') / Decimal('1000000')
        
        return input_cost + output_cost
    
    @staticmethod
    def _calculate_api_cost(input_tokens: int, output_tokens: int) -> Decimal:
        """
        计算实际API成本
        """
        input_cost = Decimal(str(input_tokens)) * Decimal('3.00') / Decimal('1000000')
        output_cost = Decimal(str(output_tokens)) * Decimal('15.00') / Decimal('1000000')
        
        return input_cost + output_cost
    
    @staticmethod
    def _hash_content(content: str) -> str:
        """
        生成内容MD5哈希
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    @staticmethod
    async def proxy_claude_stream_request(
        db: AsyncSession,
        user_key: UserClaudeKey,
        claude_account: ClaudeAccount,
        request_data: Dict[str, Any],
        request_type: str = "chat"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        代理Claude流式请求到后端账号
        
        Args:
            db: 数据库会话
            user_key: 用户虚拟密钥
            claude_account: 目标Claude账号
            request_data: 请求数据
            request_type: 请求类型
            
        Yields:
            流式响应数据块
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        success = False
        error_code = None
        error_message = None
        total_input_tokens = 0
        total_output_tokens = 0
        api_cost = Decimal('0')
        
        try:
            # 根据代理类型配置Claude客户端 (与非流式请求使用相同逻辑)
            claude_client = await ClaudeProxyMiddleware._create_claude_client_with_proxy(claude_account)
            
            # 记录代理选择信息
            proxy_info = ClaudeProxyMiddleware._get_proxy_info(claude_account)
            print(f"🔄 流式代理路由: 用户{user_key.user_id} -> 账号{claude_account.id} -> {proxy_info}")
            
            # 启用流式响应
            request_data["stream"] = True
            
            # 发送流式请求到Claude API
            if request_type == "chat":
                stream_generator = await claude_client.chat_completion(
                    messages=request_data.get("messages", []),
                    model=request_data.get("model", "claude-sonnet-4-20250514"),
                    max_tokens=request_data.get("max_tokens", 4000),
                    temperature=request_data.get("temperature", 0.7),
                    system=request_data.get("system"),
                    stream=True
                )
                
                # 处理流式响应
                async for chunk in stream_generator:
                    # 提取token使用信息（如果有）
                    if "usage" in chunk:
                        usage_info = chunk["usage"]
                        total_input_tokens += usage_info.get("input_tokens", 0)
                        total_output_tokens += usage_info.get("output_tokens", 0)
                    
                    # 转发流式数据到客户端
                    yield {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request_data.get("model", "claude-sonnet-4-20250514"),
                        "choices": [{
                            "index": 0,
                            "delta": chunk.get("delta", {}),
                            "finish_reason": chunk.get("finish_reason")
                        }]
                    }
                
                success = True
                
            else:
                # 流式模式目前仅支持chat类型
                raise ValueError(f"流式模式暂不支持请求类型: {request_type}")
            
            # 计算最终成本
            api_cost = ClaudeProxyMiddleware._calculate_api_cost(total_input_tokens, total_output_tokens)
            
        except Exception as e:
            success = False
            error_message = str(e)
            
            # 分类错误类型
            if "rate_limit" in error_message.lower():
                error_code = "RATE_LIMIT_EXCEEDED"
            elif "quota" in error_message.lower():
                error_code = "QUOTA_EXCEEDED"
            elif "authentication" in error_message.lower():
                error_code = "AUTH_ERROR"
            elif "timeout" in error_message.lower():
                error_code = "TIMEOUT"
            else:
                error_code = "UNKNOWN_ERROR"
            
            # 返回错误信息给客户端
            yield {
                "id": request_id,
                "object": "error",
                "error": {
                    "type": error_code,
                    "message": "请求处理失败，请稍后重试" if error_code != "RATE_LIMIT_EXCEEDED" else "请求过于频繁，请稍后重试"
                }
            }
        
        finally:
            # 确保客户端会话关闭
            if 'claude_client' in locals():
                await claude_client.close()
            
            # 计算响应时间
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # 记录使用统计 (异步执行，不阻塞流式响应)
            charged_cost = api_cost * Decimal('2')  # 按2倍成本计费
            
            asyncio.create_task(
                ClaudeProxyMiddleware._log_stream_usage(
                    db=db,
                    user_key=user_key,
                    claude_account=claude_account,
                    request_id=request_id,
                    request_type=request_type,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    api_cost_usd=api_cost,
                    charged_cost_usd=charged_cost,
                    success=success,
                    error_code=error_code,
                    error_message=error_message,
                    response_time_ms=response_time_ms,
                    session_id=request_data.get("session_id"),
                    ai_mode=request_data.get("ai_mode"),
                    request_content_hash=ClaudeProxyMiddleware._hash_content(str(request_data))
                )
            )
    
    @staticmethod
    async def _log_stream_usage(
        db: AsyncSession,
        user_key: UserClaudeKey,
        claude_account: ClaudeAccount,
        request_id: str,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        api_cost_usd: Decimal,
        charged_cost_usd: Decimal,
        success: bool,
        error_code: Optional[str],
        error_message: Optional[str],
        response_time_ms: int,
        session_id: Optional[str],
        ai_mode: Optional[str],
        request_content_hash: str
    ):
        """
        异步记录流式请求的使用统计
        """
        try:
            # 记录用户使用统计
            await UserClaudeKeyService.log_usage(
                db=db,
                user_key=user_key,
                claude_account=claude_account,
                request_id=request_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost_usd=api_cost_usd,
                charged_cost_usd=charged_cost_usd,
                success=success,
                error_code=error_code,
                error_message=error_message,
                response_time_ms=response_time_ms,
                session_id=session_id,
                ai_mode=ai_mode,
                request_content_hash=request_content_hash,
                response_content_hash=""  # 流式响应无法计算完整hash
            )
            
            # 更新Claude账号使用统计
            claude_service = ClaudeAccountService()
            await claude_service.log_usage(
                account_id=claude_account.id,
                user_id=user_key.user_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost=api_cost_usd,
                response_time=response_time_ms,
                success=success
            )
        except Exception as e:
            # 记录错误但不影响流式响应
            print(f"记录流式请求使用统计失败: {e}")
    
    @staticmethod
    async def handle_user_registration_hook(db: AsyncSession, user_id: int):
        """
        用户注册后的钩子函数 - 自动分配Claude Key
        """
        try:
            await UserClaudeKeyService.auto_allocate_key_for_new_user(db, user_id)
        except Exception as e:
            # 记录错误但不影响用户注册流程
            print(f"自动分配Claude Key失败 - 用户ID: {user_id}, 错误: {str(e)}")