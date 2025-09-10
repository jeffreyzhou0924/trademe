"""
Claude Webhook通知服务 - 企业级通知系统

基于参考项目 claude-relay-service/src/utils/webhookNotifier.js 实现
提供账号异常通知、状态变更通知、自动重试机制等功能
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.claude_proxy import ClaudeAccount

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """通知类型枚举"""
    ACCOUNT_ANOMALY = "account_anomaly"
    ACCOUNT_STATUS_CHANGE = "account_status_change" 
    QUOTA_WARNING = "quota_warning"
    PERFORMANCE_ALERT = "performance_alert"
    TEST = "test"


class AccountStatus(str, Enum):
    """账号状态枚举"""
    UNAUTHORIZED = "unauthorized"
    BLOCKED = "blocked"
    ERROR = "error"
    DISABLED = "disabled"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"


class ClaudeWebhookService:
    """
    Claude Webhook通知服务
    
    功能特性：
    1. 多Webhook URL支持，并行发送
    2. 指数退避重试机制
    3. 结构化通知载荷
    4. 超时控制和错误处理
    5. 不同平台的错误代码映射
    """
    
    def __init__(self):
        self.webhook_urls = self._get_webhook_urls()
        self.timeout = getattr(settings, 'WEBHOOK_TIMEOUT', 10)  # 10秒超时
        self.max_retries = getattr(settings, 'WEBHOOK_RETRIES', 3)  # 最多重试3次
        self.enabled = getattr(settings, 'WEBHOOK_ENABLED', True)
        
        # HTTP客户端会话
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _get_webhook_urls(self) -> List[str]:
        """获取Webhook URL列表"""
        webhook_config = getattr(settings, 'WEBHOOK_URLS', [])
        if isinstance(webhook_config, str):
            return [webhook_config]
        return webhook_config if webhook_config else []
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP客户端会话（延迟初始化）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={'User-Agent': 'claude-trademe-service/webhook-notifier'}
            )
        return self._session
    
    async def close(self):
        """关闭HTTP客户端会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def send_account_anomaly_notification(
        self,
        account_id: int,
        account_name: str,
        platform: str = "claude-oauth",
        status: AccountStatus = AccountStatus.ERROR,
        error_code: Optional[str] = None,
        reason: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送账号异常通知
        
        Args:
            account_id: 账号ID
            account_name: 账号名称
            platform: 平台类型 (claude-oauth, claude-console, gemini)
            status: 异常状态
            error_code: 错误代码
            reason: 异常原因
            additional_data: 额外数据
        
        Returns:
            发送结果统计
        """
        if not self.enabled or not self.webhook_urls:
            logger.debug("Webhook notification disabled or no URLs configured")
            return {"success": False, "reason": "disabled_or_no_urls"}
        
        # 构建通知载荷
        payload = {
            "type": NotificationType.ACCOUNT_ANOMALY.value,
            "data": {
                "accountId": str(account_id),
                "accountName": account_name,
                "platform": platform,
                "status": status.value,
                "errorCode": error_code or self._get_error_code(platform, status),
                "reason": reason or f"Account {account_name} encountered {status.value}",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "claude-trademe-service",
                **(additional_data or {})
            }
        }
        
        logger.info(
            f"📢 Sending account anomaly webhook notification: "
            f"{account_name} ({account_id}) - {status.value}"
        )
        
        # 并行发送到所有Webhook URL
        tasks = [
            self._send_webhook_with_retry(url, payload)
            for url in self.webhook_urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计发送结果
        success_count = sum(1 for result in results if isinstance(result, dict) and result.get("success"))
        total_count = len(self.webhook_urls)
        
        return {
            "success": success_count > 0,
            "success_count": success_count,
            "total_count": total_count,
            "results": results
        }
    
    async def send_account_status_change_notification(
        self,
        account_id: int,
        account_name: str,
        old_status: str,
        new_status: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发送账号状态变更通知"""
        payload = {
            "type": NotificationType.ACCOUNT_STATUS_CHANGE.value,
            "data": {
                "accountId": str(account_id),
                "accountName": account_name,
                "oldStatus": old_status,
                "newStatus": new_status,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "claude-trademe-service",
                **(additional_data or {})
            }
        }
        
        return await self._send_to_all_webhooks(payload)
    
    async def send_quota_warning_notification(
        self,
        account_id: int,
        account_name: str,
        current_usage: float,
        daily_limit: float,
        usage_percentage: float
    ) -> Dict[str, Any]:
        """发送配额警告通知"""
        payload = {
            "type": NotificationType.QUOTA_WARNING.value,
            "data": {
                "accountId": str(account_id),
                "accountName": account_name,
                "currentUsage": current_usage,
                "dailyLimit": daily_limit,
                "usagePercentage": usage_percentage,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "claude-trademe-service"
            }
        }
        
        return await self._send_to_all_webhooks(payload)
    
    async def send_performance_alert_notification(
        self,
        account_id: int,
        account_name: str,
        metric_type: str,  # response_time, success_rate, error_rate
        current_value: float,
        threshold: float,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发送性能警告通知"""
        payload = {
            "type": NotificationType.PERFORMANCE_ALERT.value,
            "data": {
                "accountId": str(account_id),
                "accountName": account_name,
                "metricType": metric_type,
                "currentValue": current_value,
                "threshold": threshold,
                "timestamp": datetime.utcnow().isoformat(),
                "service": "claude-trademe-service",
                **(additional_data or {})
            }
        }
        
        return await self._send_to_all_webhooks(payload)
    
    async def test_webhook(self, url: str) -> Dict[str, Any]:
        """
        测试Webhook连通性
        
        Args:
            url: 要测试的Webhook URL
            
        Returns:
            测试结果
        """
        test_payload = {
            "type": NotificationType.TEST.value,
            "data": {
                "message": "Claude Trademe Service webhook test",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "claude-trademe-service"
            }
        }
        
        return await self._send_webhook_with_retry(url, test_payload, max_retries=1)
    
    async def _send_to_all_webhooks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发送通知到所有Webhook URL"""
        if not self.enabled or not self.webhook_urls:
            return {"success": False, "reason": "disabled_or_no_urls"}
        
        tasks = [
            self._send_webhook_with_retry(url, payload)
            for url in self.webhook_urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if isinstance(result, dict) and result.get("success"))
        
        return {
            "success": success_count > 0,
            "success_count": success_count,
            "total_count": len(self.webhook_urls),
            "results": results
        }
    
    async def _send_webhook_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        发送Webhook请求（带重试机制）
        
        使用指数退避策略：1s, 2s, 4s, 8s...
        """
        max_retries = max_retries or self.max_retries
        
        for attempt in range(1, max_retries + 1):
            try:
                session = await self._get_session()
                
                async with session.post(
                    url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    
                    if 200 <= response.status < 300:
                        logger.info(f"✅ Webhook sent successfully to {url}")
                        return {
                            "success": True,
                            "url": url,
                            "status_code": response.status,
                            "attempt": attempt
                        }
                    else:
                        error_text = await response.text()
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}: {error_text}"
                        )
                        
            except Exception as error:
                logger.error(
                    f"❌ Failed to send webhook to {url} "
                    f"(attempt {attempt}/{max_retries}): {error}"
                )
                
                # 如果还有重试机会，等待后重试
                if attempt < max_retries:
                    delay = 2 ** (attempt - 1)  # 指数退避：1, 2, 4, 8...
                    logger.info(f"🔄 Retrying webhook to {url} in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"💥 All {max_retries} webhook attempts failed for {url}")
                    return {
                        "success": False,
                        "url": url,
                        "error": str(error),
                        "attempts": max_retries
                    }
        
        return {"success": False, "url": url, "error": "max_retries_exceeded"}
    
    def _get_error_code(self, platform: str, status: AccountStatus) -> str:
        """
        获取错误代码映射
        
        参考项目的错误代码映射逻辑
        """
        error_codes = {
            "claude-oauth": {
                AccountStatus.UNAUTHORIZED: "CLAUDE_OAUTH_UNAUTHORIZED",
                AccountStatus.ERROR: "CLAUDE_OAUTH_ERROR",
                AccountStatus.DISABLED: "CLAUDE_OAUTH_MANUALLY_DISABLED",
                AccountStatus.QUOTA_EXCEEDED: "CLAUDE_OAUTH_QUOTA_EXCEEDED",
                AccountStatus.RATE_LIMITED: "CLAUDE_OAUTH_RATE_LIMITED",
            },
            "claude-console": {
                AccountStatus.BLOCKED: "CLAUDE_CONSOLE_BLOCKED",
                AccountStatus.ERROR: "CLAUDE_CONSOLE_ERROR",
                AccountStatus.DISABLED: "CLAUDE_CONSOLE_MANUALLY_DISABLED",
            },
            "gemini": {
                AccountStatus.ERROR: "GEMINI_ERROR",
                AccountStatus.UNAUTHORIZED: "GEMINI_UNAUTHORIZED",
                AccountStatus.DISABLED: "GEMINI_MANUALLY_DISABLED",
            }
        }
        
        platform_codes = error_codes.get(platform, {})
        return platform_codes.get(status, "UNKNOWN_ERROR")


# 全局Webhook服务实例
webhook_service = ClaudeWebhookService()


async def notify_account_anomaly(
    account: ClaudeAccount,
    status: AccountStatus,
    reason: Optional[str] = None,
    error_code: Optional[str] = None
):
    """便捷方法：发送账号异常通知"""
    return await webhook_service.send_account_anomaly_notification(
        account_id=account.id,
        account_name=account.account_name,
        platform="claude-oauth",  # 默认平台
        status=status,
        reason=reason,
        error_code=error_code
    )


async def notify_quota_warning(account: ClaudeAccount, usage_percentage: float):
    """便捷方法：发送配额警告通知"""
    return await webhook_service.send_quota_warning_notification(
        account_id=account.id,
        account_name=account.account_name,
        current_usage=float(account.current_usage),
        daily_limit=float(account.daily_limit),
        usage_percentage=usage_percentage
    )


# 上下文管理器支持
class WebhookServiceManager:
    """Webhook服务上下文管理器"""
    
    async def __aenter__(self):
        return webhook_service
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await webhook_service.close()