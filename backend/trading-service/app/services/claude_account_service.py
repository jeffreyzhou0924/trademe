"""
Claude账号池管理服务 - 基于claude-relay-service架构的企业级实现
功能包括：账号管理、智能调度、健康监控、成本控制、OAuth管理、代理支持
"""

import asyncio
import json
import logging
import hashlib
import aiohttp
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from cryptography.fernet import Fernet
from sqlalchemy import select, update, and_, or_, func, desc, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.claude_proxy import (
    ClaudeAccount, 
    Proxy, 
    ClaudeUsageLog, 
    ClaudeSchedulerConfig,
    ProxyHealthCheck
)
from app.config import settings
from app.security.crypto_manager import CryptoManager
from app.services.claude_webhook_service import (
    webhook_service,
    notify_account_anomaly,
    notify_quota_warning,
    AccountStatus,
    NotificationType
)
from app.services.claude_session_manager import (
    session_manager,
    SessionWindow,
    get_or_create_session_window,
    update_session_usage as update_window_usage
)

logger = logging.getLogger(__name__)


class ClaudeAccountService:
    """Claude账号池管理服务 - 企业级智能调度系统"""
    
    def __init__(self):
        # 使用统一的加密管理器
        self.crypto_manager = CryptoManager()
        
        # Claude API配置
        self.claude_api_base = "https://api.anthropic.com/v1"
        self.anthropic_version = "2023-06-01"
        
        # 调度配置缓存
        self._scheduler_config_cache = {}
        self._cache_expires_at = None
        
        # 限流缓存（保留原有功能）
        self._rate_limit_cache = {}
        
        # 代理连接池
        self._proxy_connections = {}
        
        # 初始化会话管理器（异步初始化）
        self._session_manager_initialized = False
    
    def _encrypt_sensitive_data(self, data: str, additional_context: str = "") -> str:
        """加密敏感数据 - 使用统一加密管理器"""
        if not data:
            return ""
        return self.crypto_manager.encrypt_private_key(data, additional_context)
    
    def _decrypt_sensitive_data(self, encrypted_data: str, additional_context: str = "") -> str:
        """解密敏感数据 - 使用统一加密管理器"""
        if not encrypted_data:
            return ""
        try:
            return self.crypto_manager.decrypt_private_key(encrypted_data, additional_context)
        except Exception as e:
            logger.error(f"Failed to decrypt data for {additional_context}: {e}")
            # 不要返回密文作为明文使用，这是严重的安全问题
            # 如果数据确实是明文（旧数据），应该在数据迁移时处理
            # 这里直接抛出异常，让调用者处理
            raise ValueError(f"Failed to decrypt sensitive data: {e}")
    
    async def _ensure_session_manager_initialized(self):
        """确保会话管理器已初始化"""
        if not self._session_manager_initialized:
            try:
                await session_manager.initialize()
                self._session_manager_initialized = True
                logger.info("✅ Session manager initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize session manager: {e}")
                # 不抛出异常，允许系统在没有会话管理器的情况下运行
    
    async def create_account(
        self,
        account_name: str,
        api_key: str,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        daily_limit: Decimal = Decimal("100.00"),
        proxy_id: Optional[int] = None
    ) -> ClaudeAccount:
        """创建新的Claude账号"""
        
        async with AsyncSessionLocal() as session:
            # 加密API密钥
            encrypted_api_key = self._encrypt_sensitive_data(api_key)
            
            account = ClaudeAccount(
                account_name=account_name,
                api_key=encrypted_api_key,
                organization_id=organization_id,
                project_id=project_id,
                daily_limit=daily_limit,
                proxy_id=proxy_id,
                status="active",
                current_usage=Decimal("0.00"),
                success_rate=Decimal("100.00"),
                total_requests=0,
                failed_requests=0
            )
            
            session.add(account)
            await session.commit()
            await session.refresh(account)
            
            logger.info(f"Created Claude account: {account_name} (ID: {account.id})")
            return account
    
    async def get_account(self, account_id: int) -> Optional[ClaudeAccount]:
        """获取指定账号信息"""
        async with AsyncSessionLocal() as session:
            query = select(ClaudeAccount).where(ClaudeAccount.id == account_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def list_accounts(
        self,
        status: Optional[str] = None,
        active_only: bool = False,
        with_proxy: bool = False
    ) -> List[ClaudeAccount]:
        """获取账号列表"""
        async with AsyncSessionLocal() as session:
            query = select(ClaudeAccount)
            
            if active_only:
                query = query.where(ClaudeAccount.status == "active")
            elif status:
                query = query.where(ClaudeAccount.status == status)
                
            if with_proxy:
                query = query.options(selectinload(ClaudeAccount.proxy))
            
            query = query.order_by(ClaudeAccount.created_at.desc())
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def update_account(
        self,
        account_id: int,
        **updates
    ) -> Optional[ClaudeAccount]:
        """更新账号信息"""
        async with AsyncSessionLocal() as session:
            # 如果更新API密钥，需要加密
            if 'api_key' in updates:
                updates['api_key'] = self._encrypt_sensitive_data(updates['api_key'])
            
            # 更新时间戳
            updates['updated_at'] = datetime.utcnow()
            
            query = update(ClaudeAccount).where(
                ClaudeAccount.id == account_id
            ).values(**updates)
            
            result = await session.execute(query)
            await session.commit()
            
            if result.rowcount > 0:
                return await self.get_account(account_id)
            return None
    
    async def delete_account(self, account_id: int) -> bool:
        """删除账号（软删除，设置为inactive状态）"""
        result = await self.update_account(account_id, status="inactive")
        return result is not None
    
    async def get_decrypted_api_key(self, account_id: int) -> Optional[str]:
        """获取解密后的API密钥"""
        account = await self.get_account(account_id)
        if account:
            # 优先使用anthropic_api_key字段（新版本）
            if hasattr(account, 'anthropic_api_key') and account.anthropic_api_key:
                try:
                    return self._decrypt_sensitive_data(account.anthropic_api_key)
                except ValueError as e:
                    logger.error(f"Cannot decrypt anthropic_api_key for account {account_id}: {e}")
                    # 如果解密失败，检查是否是明文密钥
                    if account.anthropic_api_key.startswith('sk-ant-'):
                        logger.warning(f"Using plaintext anthropic_api_key for account {account_id} - should be encrypted!")
                        return account.anthropic_api_key
            
            # 回退到api_key字段（兼容旧版本）
            if account.api_key:
                try:
                    return self._decrypt_sensitive_data(account.api_key)
                except ValueError as e:
                    # 兼容处理：如果解密失败，检查是否是明文API密钥
                    if account.api_key and (account.api_key.startswith('sk-') or account.api_key.startswith('cr_')):
                        logger.warning(f"Using plaintext API key for account {account_id} - should be encrypted!")
                        return account.api_key
                    else:
                        logger.error(f"Cannot decrypt API key for account {account_id}: {e}")
                        return None
        return None
    
    async def select_best_account(
        self,
        excluded_accounts: Optional[List[int]] = None,
        min_remaining_quota: Optional[Decimal] = None,
        prefer_proxy: bool = False,
        sticky_session_id: Optional[str] = None
    ) -> Optional[ClaudeAccount]:
        """
        智能选择最佳账号 - 参考claude-relay-service的调度逻辑
        
        Args:
            excluded_accounts: 排除的账号ID列表
            min_remaining_quota: 最小剩余配额要求
            prefer_proxy: 是否优先选择有代理的账号
            sticky_session_id: 会话粘性ID
        """
        async with AsyncSessionLocal() as session:
            # 如果有会话粘性，先尝试使用之前的账号
            if sticky_session_id:
                cached_account_id = await self._get_sticky_session_account(sticky_session_id)
                if cached_account_id:
                    account = await self.get_account(cached_account_id)
                    if account and account.status == "active":
                        # 验证账号是否仍然可用
                        if await self._is_account_available(account):
                            await self._update_account_usage_stats(account.id)
                            return account
                        else:
                            await self._clear_sticky_session(sticky_session_id)
            
            # 构建查询条件
            conditions = [ClaudeAccount.status == "active"]
            
            if excluded_accounts:
                conditions.append(~ClaudeAccount.id.in_(excluded_accounts))
            
            if min_remaining_quota:
                conditions.append(
                    ClaudeAccount.daily_limit - ClaudeAccount.current_usage >= min_remaining_quota
                )
            
            query = select(ClaudeAccount).where(and_(*conditions))
            
            if prefer_proxy:
                query = query.where(ClaudeAccount.proxy_id.isnot(None))
                query = query.options(selectinload(ClaudeAccount.proxy))
            
            # 按优先级排序：成功率 > 剩余配额 > 最少使用时间
            query = query.order_by(
                desc(ClaudeAccount.success_rate),
                desc(ClaudeAccount.daily_limit - ClaudeAccount.current_usage),
                ClaudeAccount.last_used_at.asc().nulls_first()
            )
            
            result = await session.execute(query)
            accounts = result.scalars().all()
            
            if not accounts:
                return None
            
            # 选择最佳账号
            selected_account = accounts[0]
            
            # 设置会话粘性
            if sticky_session_id:
                await self._set_sticky_session(sticky_session_id, selected_account.id)
            
            # 更新使用统计
            await self._update_account_usage_stats(selected_account.id)
            
            logger.info(f"Selected Claude account: {selected_account.account_name} (ID: {selected_account.id})")
            return selected_account
    
    async def _is_account_available(self, account: ClaudeAccount) -> bool:
        """检查账号是否可用"""
        # 检查配额
        if account.current_usage >= account.daily_limit:
            logger.debug(f"Account {account.id} unavailable: quota exceeded")
            return False
            
        # 检查成功率 (仅在有足够的请求数据时才检查)
        if account.total_requests > 10 and account.success_rate < Decimal("85.0"):
            logger.debug(f"Account {account.id} unavailable: low success rate {account.success_rate}%")
            return False
            
        # 检查最近的失败率（放宽限制以避免过度严格）
        if account.total_requests >= 20:  # 只有在有足够样本时才检查失败率
            failure_rate = Decimal(account.failed_requests) / Decimal(account.total_requests)
            # 如果最近5分钟内有请求，且失败率超过50%（放宽到50%），暂时不可用
            if account.last_check_at:
                now = datetime.utcnow()
                time_diff = now - account.last_check_at
                if time_diff < timedelta(minutes=5) and failure_rate > Decimal("0.5"):
                    logger.debug(f"Account {account.id} unavailable: recent failure rate {failure_rate:.2%}")
                    return False
        
        return True
    
    async def _update_account_usage_stats(self, account_id: int):
        """更新账号使用统计"""
        await self.update_account(
            account_id,
            last_used_at=datetime.utcnow(),
            total_requests=ClaudeAccount.total_requests + 1
        )
    
    async def log_usage(
        self,
        account_id: int,
        user_id: Optional[int],
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        api_cost: Decimal,
        response_time: Optional[int] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> ClaudeUsageLog:
        """记录使用日志"""
        async with AsyncSessionLocal() as session:
            usage_log = ClaudeUsageLog(
                account_id=account_id,
                user_id=user_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                api_cost=api_cost,
                response_time=response_time,
                success=success,
                error_code=error_code,
                error_message=error_message,
                request_date=datetime.utcnow()
            )
            
            session.add(usage_log)
            
            # 更新账号当前使用量
            await session.execute(
                update(ClaudeAccount)
                .where(ClaudeAccount.id == account_id)
                .values(
                    current_usage=ClaudeAccount.current_usage + api_cost,
                    last_check_at=datetime.utcnow()
                )
            )
            
            if not success:
                await session.execute(
                    update(ClaudeAccount)
                    .where(ClaudeAccount.id == account_id)
                    .values(failed_requests=ClaudeAccount.failed_requests + 1)
                )
            
            await session.commit()
            await session.refresh(usage_log)
            
            # 检查配额使用率并发送警告通知
            try:
                account = await self.get_account(account_id)
                if account:
                    usage_percentage = (float(account.current_usage + api_cost) / float(account.daily_limit)) * 100
                    
                    # 配额警告阈值：75%, 90%, 95%
                    warning_thresholds = [75, 90, 95]
                    old_usage_percentage = (float(account.current_usage) / float(account.daily_limit)) * 100
                    
                    for threshold in warning_thresholds:
                        if usage_percentage >= threshold and old_usage_percentage < threshold:
                            await notify_quota_warning(account, usage_percentage)
                            logger.warning(f"📊 Quota warning sent for account {account_id}: {usage_percentage:.1f}% usage")
                            break
                    
                    # 如果使用率超过100%，发送超额通知
                    if usage_percentage >= 100 and old_usage_percentage < 100:
                        await notify_account_anomaly(
                            account=account,
                            status=AccountStatus.QUOTA_EXCEEDED,
                            reason=f"Daily quota exceeded: {usage_percentage:.1f}% usage",
                            error_code="QUOTA_EXCEEDED"
                        )
                        logger.error(f"🚨 Quota exceeded notification sent for account {account_id}")
                        
            except Exception as webhook_error:
                logger.error(f"❌ Failed to send quota notification: {webhook_error}")
            
            return usage_log
    
    async def get_usage_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取使用统计"""
        async with AsyncSessionLocal() as session:
            conditions = []
            
            if start_date:
                conditions.append(ClaudeUsageLog.request_date >= start_date)
            if end_date:
                conditions.append(ClaudeUsageLog.request_date <= end_date)
            if account_id:
                conditions.append(ClaudeUsageLog.account_id == account_id)
            if user_id:
                conditions.append(ClaudeUsageLog.user_id == user_id)
            
            where_clause = and_(*conditions) if conditions else True
            
            # 总体统计
            total_query = select(
                func.count(ClaudeUsageLog.id).label('total_requests'),
                func.sum(ClaudeUsageLog.input_tokens).label('total_input_tokens'),
                func.sum(ClaudeUsageLog.output_tokens).label('total_output_tokens'),
                func.sum(ClaudeUsageLog.api_cost).label('total_cost'),
                func.avg(ClaudeUsageLog.response_time).label('avg_response_time'),
                func.sum(func.cast(ClaudeUsageLog.success, Integer)).label('successful_requests')
            ).where(where_clause)
            
            result = await session.execute(total_query)
            stats = result.first()
            
            # 按请求类型统计
            type_query = select(
                ClaudeUsageLog.request_type,
                func.count(ClaudeUsageLog.id).label('count'),
                func.sum(ClaudeUsageLog.api_cost).label('cost')
            ).where(where_clause).group_by(ClaudeUsageLog.request_type)
            
            type_result = await session.execute(type_query)
            type_stats = {row.request_type: {'count': row.count, 'cost': float(row.cost or 0)} 
                         for row in type_result}
            
            return {
                'total_requests': stats.total_requests or 0,
                'total_input_tokens': stats.total_input_tokens or 0,
                'total_output_tokens': stats.total_output_tokens or 0,
                'total_cost_usd': float(stats.total_cost or 0),
                'avg_response_time_ms': float(stats.avg_response_time or 0),
                'success_rate': (stats.successful_requests or 0) / max(stats.total_requests or 1, 1) * 100,
                'by_request_type': type_stats
            }
    
    async def reset_daily_usage(self, account_id: Optional[int] = None):
        """重置每日使用量（通常在每日定时任务中调用）"""
        async with AsyncSessionLocal() as session:
            if account_id:
                conditions = [ClaudeAccount.id == account_id]
            else:
                conditions = [ClaudeAccount.status == "active"]
            
            await session.execute(
                update(ClaudeAccount)
                .where(and_(*conditions))
                .values(
                    current_usage=Decimal("0.00"),
                    failed_requests=0
                )
            )
            await session.commit()
            
            logger.info(f"Reset daily usage for account(s): {account_id or 'all'}")
    
    # 会话粘性管理（简单的内存缓存实现，生产环境建议用Redis）
    _sticky_sessions = {}
    
    async def _get_sticky_session_account(self, session_id: str) -> Optional[int]:
        """获取会话绑定的账号ID"""
        session_data = self._sticky_sessions.get(session_id)
        if session_data and session_data['expires_at'] > datetime.utcnow():
            return session_data['account_id']
        elif session_data:
            # 清理过期的会话
            del self._sticky_sessions[session_id]
        return None
    
    async def _set_sticky_session(self, session_id: str, account_id: int):
        """设置会话绑定账号"""
        self._sticky_sessions[session_id] = {
            'account_id': account_id,
            'expires_at': datetime.utcnow() + timedelta(hours=1)  # 1小时过期
        }
    
    async def _clear_sticky_session(self, session_id: str):
        """清除会话绑定"""
        self._sticky_sessions.pop(session_id, None)
    
    async def cleanup_expired_sessions(self):
        """清理过期的会话绑定和会话窗口"""
        # 清理粘性会话绑定
        now = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, data in self._sticky_sessions.items()
            if data['expires_at'] <= now
        ]
        for session_id in expired_sessions:
            del self._sticky_sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sticky sessions")
        
        # 清理会话窗口（使用新的会话管理器）
        try:
            await self._ensure_session_manager_initialized()
            cleanup_stats = await session_manager.cleanup_expired_windows()
            if cleanup_stats.get("total_cleaned", 0) > 0:
                logger.info(f"Session manager cleaned up {cleanup_stats['total_cleaned']} expired windows")
        except Exception as e:
            logger.error(f"❌ Failed to cleanup session windows: {e}")

    # ===================== 企业级高级功能 =====================
    # 基于claude-relay-service架构的增强功能
    
    async def create_proxy_agent(self, proxy: Proxy) -> Optional[Dict[str, Any]]:
        """
        创建代理连接配置
        参考claude-relay-service的_createProxyAgent方法
        """
        try:
            if not proxy:
                return None
            
            proxy_config = {
                "type": proxy.proxy_type,
                "host": proxy.host,
                "port": proxy.port
            }
            
            if proxy.username and proxy.password:
                # 解密代理密码
                decrypted_password = self._decrypt_sensitive_data(proxy.password, f"proxy_{proxy.id}")
                proxy_config.update({
                    "username": proxy.username,
                    "password": decrypted_password
                })
            
            # 构建代理URL
            if proxy.proxy_type in ["http", "https"]:
                auth_part = ""
                if proxy.username and proxy.password:
                    auth_part = f"{proxy.username}:{decrypted_password}@"
                proxy_url = f"{proxy.proxy_type}://{auth_part}{proxy.host}:{proxy.port}"
            elif proxy.proxy_type == "socks5":
                auth_part = ""
                if proxy.username and proxy.password:
                    auth_part = f"{proxy.username}:{decrypted_password}@"
                proxy_url = f"socks5://{auth_part}{proxy.host}:{proxy.port}"
            else:
                return None
            
            proxy_config["url"] = proxy_url
            return proxy_config
            
        except Exception as e:
            logger.error(f"❌ Failed to create proxy agent: {str(e)}")
            return None
    
    async def health_check_account_with_retry(
        self, 
        account_id: int, 
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        带重试的账号健康检查
        参考claude-relay-service的健康检查机制
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await self._perform_single_health_check(account_id)
                
                if result["success"]:
                    # 获取账号信息以检查状态变化
                    account = await self.get_account(account_id)
                    old_status = account.status if account else "unknown"
                    
                    # 成功时更新账号状态
                    await self.update_account(
                        account_id,
                        status="active",
                        last_check_at=datetime.utcnow(),
                        avg_response_time=result.get("response_time", 0)
                    )
                    
                    # 如果从错误状态恢复，发送恢复通知
                    if account and old_status in ["error", "inactive", "suspended"]:
                        try:
                            await webhook_service.send_account_status_change_notification(
                                account_id=account_id,
                                account_name=account.account_name,
                                old_status=old_status,
                                new_status="active",
                                additional_data={
                                    "reason": "health_check_recovery",
                                    "response_time_ms": result.get("response_time", 0)
                                }
                            )
                        except Exception as webhook_error:
                            logger.error(f"❌ Failed to send recovery notification: {webhook_error}")
                    
                    return result
                
                last_error = result.get("error", "Unknown error")
                
                # 失败时等待后重试
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ Health check attempt {attempt + 1} failed for account {account_id}: {e}")
        
        # 所有重试都失败，标记账号为错误状态并发送Webhook通知
        account = await self.get_account(account_id)
        old_status = account.status if account else "unknown"
        
        await self.update_account(
            account_id,
            status="error",
            last_check_at=datetime.utcnow()
        )
        
        # 发送账号异常通知
        if account:
            try:
                await notify_account_anomaly(
                    account=account,
                    status=AccountStatus.ERROR,
                    reason=f"Health check failed after {max_retries} attempts: {last_error}",
                    error_code="HEALTH_CHECK_FAILED"
                )
                
                # 如果状态发生变化，发送状态变更通知
                if old_status != "error":
                    await webhook_service.send_account_status_change_notification(
                        account_id=account_id,
                        account_name=account.account_name,
                        old_status=old_status,
                        new_status="error",
                        additional_data={"reason": "health_check_failure", "attempts": max_retries}
                    )
                    
            except Exception as webhook_error:
                logger.error(f"❌ Failed to send webhook notification: {webhook_error}")
        
        return {
            "success": False,
            "account_id": account_id,
            "error": f"Health check failed after {max_retries} attempts: {last_error}"
        }
    
    async def _perform_single_health_check(self, account_id: int) -> Dict[str, Any]:
        """执行单次健康检查"""
        try:
            async with AsyncSessionLocal() as session:
                # 获取账号信息
                result = await session.execute(
                    select(ClaudeAccount)
                    .options(selectinload(ClaudeAccount.proxy))
                    .where(ClaudeAccount.id == account_id)
                )
                account = result.scalar_one_or_none()
                
                if not account:
                    return {"success": False, "error": "Account not found"}
                
                # 解密API密钥
                api_key = self._decrypt_sensitive_data(account.api_key, account.account_name)
                if not api_key:
                    return {"success": False, "error": "Failed to decrypt API key"}
                
                # 创建代理配置
                proxy_config = None
                if account.proxy:
                    proxy_config = await self.create_proxy_agent(account.proxy)
                
                # 执行健康检查请求
                start_time = datetime.utcnow()
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "anthropic-version": self.anthropic_version
                }
                
                test_payload = {
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "test"}]
                }
                
                timeout = aiohttp.ClientTimeout(total=30)
                
                async with aiohttp.ClientSession(timeout=timeout) as http_session:
                    proxy_url = proxy_config["url"] if proxy_config else None
                    
                    async with http_session.post(
                        f"{self.claude_api_base}/messages",
                        json=test_payload,
                        headers=headers,
                        proxy=proxy_url
                    ) as response:
                        response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        
                        if response.status == 200:
                            return {
                                "success": True,
                                "account_id": account_id,
                                "status": "healthy",
                                "response_time": response_time,
                                "message": "API响应正常"
                            }
                        elif response.status == 401:
                            return {
                                "success": False,
                                "error": "API密钥无效或已过期",
                                "status_code": 401
                            }
                        elif response.status == 429:
                            # 限流不算错误，账号本身是健康的
                            return {
                                "success": True,
                                "account_id": account_id,
                                "status": "rate_limited",
                                "response_time": response_time,
                                "message": "API调用受限，但账号健康"
                            }
                        else:
                            error_text = await response.text()
                            return {
                                "success": False,
                                "error": f"HTTP {response.status}: {error_text[:200]}",
                                "status_code": response.status
                            }
                            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "健康检查请求超时"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"健康检查异常: {str(e)}"
            }
    
    async def mark_account_rate_limited(
        self, 
        account_id: int, 
        reset_time: Optional[datetime] = None
    ) -> bool:
        """
        标记账号为限流状态
        参考claude-relay-service的markAccountRateLimited方法
        """
        try:
            # 计算限流重置时间
            if not reset_time:
                reset_time = datetime.utcnow() + timedelta(hours=1)  # 默认1小时
            
            # 更新限流缓存
            self._rate_limit_cache[account_id] = {
                "limited_at": datetime.utcnow(),
                "reset_at": reset_time,
                "status": "rate_limited"
            }
            
            # 更新数据库
            await self.update_account(
                account_id,
                status="rate_limited",
                last_check_at=datetime.utcnow()
            )
            
            logger.warning(f"🚫 Account {account_id} marked as rate limited until {reset_time}")
            
            # 发送限流通知
            try:
                account = await self.get_account(account_id)
                if account:
                    await notify_account_anomaly(
                        account=account,
                        status=AccountStatus.RATE_LIMITED,
                        reason=f"Account rate limited until {reset_time.isoformat()}",
                        error_code="RATE_LIMITED"
                    )
                    
                    await webhook_service.send_account_status_change_notification(
                        account_id=account_id,
                        account_name=account.account_name,
                        old_status="active",
                        new_status="rate_limited",
                        additional_data={
                            "reason": "rate_limit_exceeded",
                            "reset_time": reset_time.isoformat(),
                            "limited_at": datetime.utcnow().isoformat()
                        }
                    )
                    
            except Exception as webhook_error:
                logger.error(f"❌ Failed to send rate limit notification: {webhook_error}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to mark account {account_id} as rate limited: {e}")
            return False
    
    async def check_rate_limit_status(self, account_id: int) -> Dict[str, Any]:
        """检查账号限流状态"""
        try:
            rate_limit_info = self._rate_limit_cache.get(account_id)
            
            if not rate_limit_info:
                return {"is_rate_limited": False}
            
            now = datetime.utcnow()
            reset_at = rate_limit_info["reset_at"]
            
            if now >= reset_at:
                # 限流已过期，清除状态并发送恢复通知
                del self._rate_limit_cache[account_id]
                await self.update_account(account_id, status="active")
                
                try:
                    account = await self.get_account(account_id)
                    if account:
                        await webhook_service.send_account_status_change_notification(
                            account_id=account_id,
                            account_name=account.account_name,
                            old_status="rate_limited",
                            new_status="active",
                            additional_data={
                                "reason": "rate_limit_expired",
                                "reset_at": reset_at.isoformat(),
                                "recovery_time": now.isoformat()
                            }
                        )
                        logger.info(f"✅ Rate limit cleared for account {account_id}, recovery notification sent")
                except Exception as webhook_error:
                    logger.error(f"❌ Failed to send rate limit recovery notification: {webhook_error}")
                
                return {"is_rate_limited": False}
            
            # 仍在限流中
            remaining_minutes = int((reset_at - now).total_seconds() / 60)
            return {
                "is_rate_limited": True,
                "limited_at": rate_limit_info["limited_at"].isoformat(),
                "reset_at": reset_at.isoformat(),
                "remaining_minutes": remaining_minutes
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to check rate limit status for account {account_id}: {e}")
            return {"is_rate_limited": False, "error": str(e)}
    
    async def get_account_with_session_window(
        self, 
        account_id: int, 
        create_window: bool = True,
        window_type: str = "standard"
    ) -> Dict[str, Any]:
        """
        获取账号的会话窗口信息
        使用企业级会话管理器替代原有实现
        """
        try:
            await self._ensure_session_manager_initialized()
            
            # 获取或创建会话窗口
            window = await session_manager.get_session_window(
                account_id=account_id, 
                auto_create=create_window
            )
            
            if not window:
                return {"has_active_window": False}
            
            window_info = window.to_dict()
            
            return {
                "has_active_window": True,
                "window_id": window.window_id,
                "window_type": window.window_type,
                "window_start": window_info["start_time"],
                "window_end": window_info["end_time"], 
                "current_usage": window_info["current_usage"],
                "total_limit": window_info["total_limit"],
                "usage_percent": window_info["usage_percentage"],
                "remaining_minutes": window_info["remaining_minutes"],
                "request_count": window_info["request_count"],
                "is_expired": window_info["is_expired"]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get session window for account {account_id}: {e}")
            return {"error": str(e), "has_active_window": False}
    
    async def update_session_window_usage(
        self, 
        account_id: int, 
        cost_increment: float,
        window_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        更新会话窗口使用量
        使用企业级会话管理器替代原有实现
        
        Returns:
            (success, result_info)
        """
        try:
            await self._ensure_session_manager_initialized()
            
            # 如果没有指定window_id，获取活跃窗口
            if not window_id:
                window = await session_manager.get_session_window(account_id, auto_create=True)
                if not window:
                    return False, {"error": "No active session window"}
                window_id = window.window_id
            
            # 更新使用量
            success, result = await session_manager.update_session_usage(
                window_id=window_id,
                cost_increment=cost_increment,
                request_increment=1
            )
            
            # 如果超过限额，标记账号为限流
            if not success and result.get("is_over_limit"):
                window_info = result.get("window_info", {})
                end_time_value = window_info.get("end_time", datetime.utcnow().isoformat())
                if isinstance(end_time_value, str):
                    try:
                        end_time = datetime.fromisoformat(end_time_value)
                    except (ValueError, TypeError):
                        end_time = datetime.utcnow()
                elif isinstance(end_time_value, datetime):
                    end_time = end_time_value
                else:
                    end_time = datetime.utcnow()
                await self.mark_account_rate_limited(account_id, end_time)
            
            return success, result
            
        except Exception as e:
            logger.error(f"❌ Failed to update session window usage for account {account_id}: {e}")
            return False, {"error": str(e)}
    
    async def get_scheduler_health_report(self) -> Dict[str, Any]:
        """
        获取调度器健康报告
        参考claude-relay-service的监控功能
        """
        try:
            async with AsyncSessionLocal() as session:
                # 统计账号状态
                account_stats = await session.execute(
                    select(
                        ClaudeAccount.status,
                        func.count(ClaudeAccount.id).label("count")
                    )
                    .group_by(ClaudeAccount.status)
                )
                
                status_distribution = {row.status: row.count for row in account_stats}
                
                # 统计代理状态
                proxy_stats = await session.execute(
                    select(
                        Proxy.status,
                        func.count(Proxy.id).label("count")
                    )
                    .group_by(Proxy.status)
                )
                
                proxy_distribution = {row.status: row.count for row in proxy_stats}
                
                # 最近24小时使用统计
                yesterday = datetime.utcnow() - timedelta(days=1)
                usage_stats = await session.execute(
                    select(
                        func.count(ClaudeUsageLog.id).label("total_requests"),
                        func.sum(ClaudeUsageLog.api_cost).label("total_cost"),
                        func.avg(ClaudeUsageLog.response_time).label("avg_response_time"),
                        func.sum(func.cast(ClaudeUsageLog.success, Integer)).label("successful_requests")
                    )
                    .where(ClaudeUsageLog.request_date >= yesterday)
                )
                
                usage_data = usage_stats.first()
                
                # 计算成功率
                total_requests = usage_data.total_requests or 0
                successful_requests = usage_data.successful_requests or 0
                success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 100
                
                # 会话窗口统计（使用新的会话管理器）
                await self._ensure_session_manager_initialized()
                session_stats = await session_manager.get_session_statistics()
                active_windows = session_stats.get("active_windows", 0)
                rate_limited_accounts = len(self._rate_limit_cache)
                
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "account_status": status_distribution,
                    "proxy_status": proxy_distribution,
                    "last_24h_stats": {
                        "total_requests": total_requests,
                        "total_cost_usd": float(usage_data.total_cost or 0),
                        "avg_response_time_ms": float(usage_data.avg_response_time or 0),
                        "success_rate_percent": round(success_rate, 2)
                    },
                    "scheduler_status": {
                        "active_session_windows": active_windows,
                        "rate_limited_accounts": rate_limited_accounts,
                        "healthy_accounts": status_distribution.get("active", 0)
                    },
                    "session_manager_stats": {
                        "total_windows": session_stats.get("total_windows", 0),
                        "expired_windows": session_stats.get("expired_windows", 0),
                        "by_type": session_stats.get("by_type", {}),
                        "total_session_usage": session_stats.get("total_usage", 0.0),
                        "total_session_requests": session_stats.get("total_requests", 0)
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to generate scheduler health report: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "error"
            }
    
    async def optimize_account_distribution(self) -> Dict[str, Any]:
        """
        优化账号分配
        基于使用统计和性能数据进行智能优化
        """
        try:
            async with AsyncSessionLocal() as session:
                # 获取所有活跃账号的使用统计
                accounts_with_stats = await session.execute(
                    select(
                        ClaudeAccount,
                        func.count(ClaudeUsageLog.id).label("request_count"),
                        func.avg(ClaudeUsageLog.response_time).label("avg_response"),
                        func.sum(ClaudeUsageLog.api_cost).label("total_cost")
                    )
                    .outerjoin(ClaudeUsageLog, ClaudeAccount.id == ClaudeUsageLog.account_id)
                    .where(ClaudeAccount.status == "active")
                    .group_by(ClaudeAccount.id)
                )
                
                optimization_report = {
                    "optimization_time": datetime.utcnow().isoformat(),
                    "accounts_analyzed": 0,
                    "recommendations": [],
                    "cost_savings_potential": 0.0
                }
                
                for row in accounts_with_stats:
                    account = row.ClaudeAccount
                    request_count = row.request_count or 0
                    avg_response = row.avg_response or 0
                    total_cost = float(row.total_cost or 0)
                    
                    optimization_report["accounts_analyzed"] += 1
                    
                    # 分析账号使用模式并给出建议
                    recommendations = []
                    
                    # 使用率分析
                    usage_rate = (account.current_usage / account.daily_limit) * 100
                    if usage_rate < 20:
                        recommendations.append({
                            "type": "underutilized",
                            "message": f"账号使用率仅{usage_rate:.1f}%，可考虑降低每日限额",
                            "potential_savings": float(account.daily_limit - account.current_usage) * 0.8
                        })
                    elif usage_rate > 90:
                        recommendations.append({
                            "type": "overutilized", 
                            "message": f"账号使用率达{usage_rate:.1f}%，建议增加限额或添加备用账号",
                            "suggested_action": "increase_limit"
                        })
                    
                    # 响应时间分析
                    if avg_response > 5000:  # 超过5秒
                        recommendations.append({
                            "type": "slow_response",
                            "message": f"平均响应时间{avg_response:.0f}ms过长，建议检查代理配置",
                            "suggested_action": "check_proxy"
                        })
                        
                        # 发送性能警告通知
                        try:
                            await webhook_service.send_performance_alert_notification(
                                account_id=account.id,
                                account_name=account.account_name,
                                metric_type="response_time",
                                current_value=avg_response,
                                threshold=5000,
                                additional_data={
                                    "optimization_context": "account_distribution_analysis",
                                    "analysis_time": datetime.utcnow().isoformat()
                                }
                            )
                        except Exception as webhook_error:
                            logger.error(f"❌ Failed to send performance alert: {webhook_error}")
                    
                    # 成功率分析
                    if account.success_rate < 95:
                        recommendations.append({
                            "type": "low_success_rate",
                            "message": f"成功率{account.success_rate:.1f}%偏低，建议进行健康检查",
                            "suggested_action": "health_check"
                        })
                        
                        # 发送成功率警告通知
                        try:
                            await webhook_service.send_performance_alert_notification(
                                account_id=account.id,
                                account_name=account.account_name,
                                metric_type="success_rate",
                                current_value=float(account.success_rate),
                                threshold=95.0,
                                additional_data={
                                    "optimization_context": "account_distribution_analysis", 
                                    "analysis_time": datetime.utcnow().isoformat(),
                                    "total_requests": account.total_requests,
                                    "failed_requests": account.failed_requests
                                }
                            )
                        except Exception as webhook_error:
                            logger.error(f"❌ Failed to send success rate alert: {webhook_error}")
                    
                    if recommendations:
                        optimization_report["recommendations"].append({
                            "account_id": account.id,
                            "account_name": account.account_name,
                            "current_stats": {
                                "usage_rate": f"{usage_rate:.1f}%",
                                "avg_response_ms": avg_response,
                                "success_rate": f"{account.success_rate:.1f}%",
                                "total_cost": total_cost
                            },
                            "recommendations": recommendations
                        })
                
                # 计算潜在成本节省
                for rec in optimization_report["recommendations"]:
                    for suggestion in rec["recommendations"]:
                        if "potential_savings" in suggestion:
                            optimization_report["cost_savings_potential"] += suggestion["potential_savings"]
                
                logger.info(f"📊 Account optimization completed: analyzed {optimization_report['accounts_analyzed']} accounts")
                return optimization_report
                
        except Exception as e:
            logger.error(f"❌ Failed to optimize account distribution: {e}")
            return {
                "optimization_time": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "failed"
            }
    
    async def update_account_status(self, account_id: int, status: str) -> bool:
        """
        更新Claude账号状态
        
        Args:
            account_id: 账号ID
            status: 新状态 ('active', 'inactive', 'error')
            
        Returns:
            bool: 更新是否成功
        """
        try:
            async with AsyncSessionLocal() as session:
                # 查询账号
                query = select(ClaudeAccount).where(ClaudeAccount.id == account_id)
                result = await session.execute(query)
                account = result.scalar_one_or_none()
                
                if not account:
                    logger.warning(f"Account {account_id} not found for status update")
                    return False
                
                # 更新状态
                account.status = status
                account.updated_at = datetime.utcnow()
                
                await session.commit()
                logger.info(f"✅ Updated account {account_id} status to {status}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to update account {account_id} status: {e}")
            return False
    
    async def close(self):
        """
        清理资源，关闭连接
        """
        try:
            # 关闭会话管理器
            if self._session_manager_initialized:
                await session_manager.close()
                logger.info("✅ Session manager closed")
            
            # 关闭Webhook服务连接
            await webhook_service.close()
            
            # 清理代理连接池
            for connection in self._proxy_connections.values():
                if hasattr(connection, 'close'):
                    await connection.close()
            self._proxy_connections.clear()
            
            # 清理缓存
            self._scheduler_config_cache.clear()
            self._rate_limit_cache.clear()
            self._sticky_sessions.clear()
            
            logger.info("✅ Claude Account Service closed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error closing Claude Account Service: {e}")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            # 注意：这里不能使用await，所以只做同步清理
            self._scheduler_config_cache.clear()
            self._rate_limit_cache.clear() 
            self._sticky_sessions.clear()
            self._proxy_connections.clear()
        except Exception:
            pass  # 避免析构函数中的异常


# 全局实例
claude_account_service = ClaudeAccountService()