"""
Claude OAuth认证服务 - 完全兼容claude-relay-service设计
支持通过OAuth添加Claude账户和token管理
"""

import json
import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceException
from app.database import AsyncSessionLocal, get_db
from app.models.claude_proxy import ClaudeAccount, UserClaudeKey
from app.core.logger import get_logger

logger = get_logger(__name__)


class ClaudeOAuthService:
    """Claude OAuth认证服务 - 参考claude-relay-service实现"""
    
    # Claude官方OAuth配置
    CLAUDE_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    CLAUDE_OAUTH_BASE_URL = "https://console.anthropic.com/v1/oauth"
    CLAUDE_API_BASE_URL = "https://api.anthropic.com"
    
    # 加密配置
    ENCRYPTION_SALT = b"trademe_claude_salt_2025"
    
    def __init__(self, encryption_key: str = None):
        """初始化OAuth服务"""
        self.encryption_key = encryption_key or "trademe_claude_encryption_key_2025_secure"
        self._cipher = self._create_cipher()
        self._client = httpx.AsyncClient(timeout=30.0)
    
    def _create_cipher(self) -> Fernet:
        """创建加密器"""
        key_bytes = self.encryption_key.encode()[:32].ljust(32, b'0')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.ENCRYPTION_SALT,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
        return Fernet(key)
    
    def _encrypt_data(self, data: str) -> str:
        """加密敏感数据"""
        if not data:
            return ""
        return self._cipher.encrypt(data.encode()).decode()
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """解密敏感数据"""
        if not encrypted_data:
            return ""
        try:
            return self._cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            return ""
    
    def generate_oauth_url(self, proxy_config: Dict[str, Any] = None) -> Tuple[str, str]:
        """
        生成OAuth授权URL
        
        Args:
            proxy_config: 代理配置 (可选)
            
        Returns:
            Tuple[str, str]: (授权URL, state参数)
        """
        # 生成随机state参数用于防CSRF攻击
        state = secrets.token_urlsafe(32)
        
        # 构建OAuth授权URL
        auth_url = (
            f"{self.CLAUDE_OAUTH_BASE_URL}/authorize"
            f"?client_id={self.CLAUDE_OAUTH_CLIENT_ID}"
            f"&response_type=code"
            f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"  # OOB流程
            f"&scope=read%20write"
            f"&state={state}"
        )
        
        logger.info(f"Generated OAuth URL with state: {state[:8]}...")
        return auth_url, state
    
    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
        state: str,
        proxy_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        使用授权码换取访问令牌
        
        Args:
            authorization_code: OAuth授权码
            state: state参数 (用于验证)
            proxy_config: 代理配置
            
        Returns:
            Dict: OAuth令牌数据
        """
        try:
            # 设置代理客户端
            client = self._client
            if proxy_config:
                proxy_url = self._build_proxy_url(proxy_config)
                client = httpx.AsyncClient(proxies=proxy_url, timeout=30.0)
            
            # 构建token交换请求
            token_data = {
                "grant_type": "authorization_code",
                "client_id": self.CLAUDE_OAUTH_CLIENT_ID,
                "code": authorization_code,
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob"
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TrademeApp/1.0"
            }
            
            # 发送token请求
            response = await client.post(
                f"{self.CLAUDE_OAUTH_BASE_URL}/token",
                data=token_data,
                headers=headers
            )
            
            if response.status_code != 200:
                error_text = await response.aread() if hasattr(response, 'aread') else response.text
                logger.error(f"Token exchange failed: {response.status_code} - {error_text}")
                raise ServiceException(f"OAuth token exchange failed: {response.status_code}")
            
            token_data = response.json()
            
            # 验证响应数据
            required_fields = ['access_token', 'refresh_token', 'expires_in', 'token_type']
            for field in required_fields:
                if field not in token_data:
                    raise ServiceException(f"Missing required field in token response: {field}")
            
            # 计算过期时间
            expires_at = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
            
            # 构建返回数据
            oauth_data = {
                'access_token': token_data['access_token'],
                'refresh_token': token_data['refresh_token'], 
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': expires_at,
                'expires_in': token_data['expires_in'],
                'scopes': token_data.get('scope', 'read write').split(),
                'raw_response': token_data
            }
            
            # 获取用户信息 
            user_info = await self._fetch_user_info(oauth_data['access_token'], client)
            if user_info:
                oauth_data['user_info'] = user_info
            
            logger.success(f"Successfully exchanged OAuth code for tokens")
            return oauth_data
            
        except httpx.RequestError as e:
            logger.error(f"Network error during token exchange: {e}")
            raise ServiceException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            raise ServiceException(f"Token exchange failed: {e}")
        finally:
            if 'client' in locals() and client != self._client:
                await client.aclose()
    
    async def _fetch_user_info(self, access_token: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "TrademeApp/1.0"
            }
            
            response = await client.get(
                "https://api.anthropic.com/v1/me",  # 假设的用户信息端点
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            logger.warning(f"Failed to fetch user info: {e}")
        
        return None
    
    def _build_proxy_url(self, proxy_config: Dict[str, Any]) -> str:
        """构建代理URL"""
        proxy_type = proxy_config.get('type', 'http')
        host = proxy_config.get('host')
        port = proxy_config.get('port')
        username = proxy_config.get('username')
        password = proxy_config.get('password')
        
        if not host or not port:
            return None
        
        auth_str = f"{username}:{password}@" if username and password else ""
        return f"{proxy_type}://{auth_str}{host}:{port}"
    
    async def create_account_from_oauth(
        self,
        db: Session,
        oauth_data: Dict[str, Any],
        account_options: Dict[str, Any] = None
    ) -> ClaudeAccount:
        """
        从OAuth数据创建Claude账户
        
        Args:
            db: 数据库会话
            oauth_data: OAuth令牌数据
            account_options: 账户选项配置
            
        Returns:
            ClaudeAccount: 创建的账户对象
        """
        options = account_options or {}
        
        # 加密敏感数据
        encrypted_access_token = self._encrypt_data(oauth_data['access_token'])
        encrypted_refresh_token = self._encrypt_data(oauth_data['refresh_token'])
        
        # 获取用户信息
        user_info = oauth_data.get('user_info', {})
        email = user_info.get('email', options.get('email', ''))
        
        # 创建账户记录
        account = ClaudeAccount(
            account_name=options.get('name', f"Claude账户 {datetime.now().strftime('%m-%d %H:%M')}"),
            api_key=encrypted_access_token[:50] + "...",  # 显示用途
            oauth_access_token=encrypted_access_token,
            oauth_refresh_token=encrypted_refresh_token,
            oauth_expires_at=oauth_data['expires_at'],
            oauth_scopes=json.dumps(oauth_data['scopes']),
            oauth_token_type=oauth_data['token_type'],
            daily_limit=options.get('daily_limit', 100.0),
            status="active",
            priority=options.get('priority', 50),
            is_schedulable=options.get('schedulable', True),
            account_type=options.get('account_type', 'shared'),
            subscription_info=json.dumps(user_info) if user_info else None,
            proxy_config=json.dumps(options.get('proxy_config')) if options.get('proxy_config') else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(account)
        db.commit()
        db.refresh(account)
        
        logger.success(f"Created Claude account: {account.account_name} (ID: {account.id})")
        return account
    
    async def refresh_account_token(self, db: Session, account_id: int) -> bool:
        """
        刷新账户访问令牌
        
        Args:
            db: 数据库会话
            account_id: 账户ID
            
        Returns:
            bool: 是否刷新成功
        """
        try:
            # 获取账户信息
            account = db.query(ClaudeAccount).filter(ClaudeAccount.id == account_id).first()
            if not account:
                raise ServiceException(f"Account {account_id} not found")
            
            # 解密refresh token
            refresh_token = self._decrypt_data(account.oauth_refresh_token)
            if not refresh_token:
                raise ServiceException("No refresh token available")
            
            # 准备刷新请求
            token_data = {
                "grant_type": "refresh_token",
                "client_id": self.CLAUDE_OAUTH_CLIENT_ID,
                "refresh_token": refresh_token
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TrademeApp/1.0"
            }
            
            # 发送刷新请求
            response = await self._client.post(
                f"{self.CLAUDE_OAUTH_BASE_URL}/token",
                data=token_data,
                headers=headers
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Token refresh failed for account {account_id}: {error_text}")
                # 将账户标记为错误状态
                account.status = "error"
                account.error_message = f"Token refresh failed: {response.status_code}"
                db.commit()
                return False
            
            new_token_data = response.json()
            
            # 更新账户token信息
            account.oauth_access_token = self._encrypt_data(new_token_data['access_token'])
            if 'refresh_token' in new_token_data:
                account.oauth_refresh_token = self._encrypt_data(new_token_data['refresh_token'])
            
            expires_at = datetime.utcnow() + timedelta(seconds=new_token_data['expires_in'])
            account.oauth_expires_at = expires_at
            account.status = "active"
            account.error_message = None
            account.updated_at = datetime.utcnow()
            
            db.commit()
            
            logger.success(f"Successfully refreshed token for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Token refresh failed for account {account_id}: {e}")
            return False
    
    async def validate_account_token(self, db: Session, account_id: int) -> bool:
        """
        验证账户token有效性
        
        Args:
            db: 数据库会话  
            account_id: 账户ID
            
        Returns:
            bool: token是否有效
        """
        try:
            account = db.query(ClaudeAccount).filter(ClaudeAccount.id == account_id).first()
            if not account:
                return False
            
            # 检查token是否即将过期 (10分钟内)
            if account.oauth_expires_at and account.oauth_expires_at <= datetime.utcnow() + timedelta(minutes=10):
                logger.info(f"Token for account {account_id} is expiring soon, attempting refresh...")
                return await self.refresh_account_token(db, account_id)
            
            # 解密access token并验证
            access_token = self._decrypt_data(account.oauth_access_token)
            if not access_token:
                return False
            
            # 发送测试请求验证token
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "TrademeApp/1.0"
            }
            
            response = await self._client.get(
                f"{self.CLAUDE_API_BASE_URL}/v1/me",
                headers=headers
            )
            
            is_valid = response.status_code == 200
            
            if not is_valid:
                logger.warning(f"Token validation failed for account {account_id}: {response.status_code}")
                account.status = "error"
                account.error_message = f"Token validation failed: {response.status_code}"
                db.commit()
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Token validation error for account {account_id}: {e}")
            return False
    
    def get_decrypted_access_token(self, account: ClaudeAccount) -> str:
        """获取解密后的访问令牌"""
        return self._decrypt_data(account.oauth_access_token)
    
    def get_account_headers(self, account: ClaudeAccount) -> Dict[str, str]:
        """获取账户API请求头"""
        access_token = self.get_decrypted_access_token(account)
        return {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "TrademeApp/1.0",
            "Content-Type": "application/json"
        }
    
    async def list_active_accounts(self, db: Session) -> List[ClaudeAccount]:
        """获取所有活跃账户列表"""
        return db.query(ClaudeAccount).filter(
            and_(
                ClaudeAccount.status == "active",
                ClaudeAccount.is_schedulable == True
            )
        ).order_by(ClaudeAccount.priority.asc()).all()
    
    async def get_account_usage_stats(self, db: Session, account_id: int) -> Dict[str, Any]:
        """获取账户使用统计"""
        # 这里可以实现详细的使用统计逻辑
        # 包括token使用量、成本、成功率等
        account = db.query(ClaudeAccount).filter(ClaudeAccount.id == account_id).first()
        if not account:
            return {}
        
        return {
            "account_id": account_id,
            "account_name": account.account_name,
            "total_requests": account.total_requests,
            "failed_requests": account.failed_requests,
            "success_rate": float(account.success_rate),
            "avg_response_time": account.avg_response_time,
            "current_usage": float(account.current_usage),
            "daily_limit": float(account.daily_limit),
            "status": account.status,
            "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None
        }
    
    async def close(self):
        """关闭HTTP客户端"""
        await self._client.aclose()


# 全局OAuth服务实例
claude_oauth_service = ClaudeOAuthService()