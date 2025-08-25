"""
Claude账号池管理服务 - 参考claude-relay-service架构设计
功能包括：账号管理、智能调度、健康监控、成本控制
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from cryptography.fernet import Fernet
from sqlalchemy import select, update, and_, or_, func, desc
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
from app.core.config import settings

logger = logging.getLogger(__name__)


class ClaudeAccountService:
    """Claude账号池管理服务"""
    
    def __init__(self):
        # 加密密钥初始化
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # 调度配置缓存
        self._scheduler_config_cache = {}
        self._cache_expires_at = None
        
    def _get_or_create_encryption_key(self) -> bytes:
        """获取或创建加密密钥"""
        key_file = settings.DATA_DIR / "claude_encryption.key"
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(key)
            return key
    
    def _encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感数据"""
        if not data:
            return ""
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """解密敏感数据"""
        if not encrypted_data:
            return ""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            return ""
    
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
            return self._decrypt_sensitive_data(account.api_key)
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
            return False
            
        # 检查成功率
        if account.success_rate < Decimal("90.0"):
            return False
            
        # 检查最近是否有失败记录（简单实现）
        now = datetime.utcnow()
        if account.last_check_at:
            time_diff = now - account.last_check_at
            if time_diff < timedelta(minutes=5) and account.failed_requests > account.total_requests * 0.1:
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
        """清理过期的会话绑定"""
        now = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, data in self._sticky_sessions.items()
            if data['expires_at'] <= now
        ]
        for session_id in expired_sessions:
            del self._sticky_sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sticky sessions")


# 全局实例
claude_account_service = ClaudeAccountService()