"""
Anthropic OAuth Setup Token Service
基于claude-relay-service的OAuth Helper实现
完整支持真实的OAuth流程，不是简单的API Key
"""

import asyncio
import base64
import hashlib
import secrets
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import aiohttp
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.claude_proxy import ClaudeAccount
from app.core.exceptions import APIException

logger = logging.getLogger(__name__)

# OAuth 配置常量 - 从claude-relay-service提取
OAUTH_CONFIG = {
    "AUTHORIZE_URL": "https://claude.ai/oauth/authorize",
    "TOKEN_URL": "https://console.anthropic.com/v1/oauth/token",
    "CLIENT_ID": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
    "REDIRECT_URI": "https://console.anthropic.com/oauth/code/callback",
    "SCOPES": "org:create_api_key user:profile user:inference",  # 标准OAuth权限
    "SCOPES_SETUP": "user:inference"  # Setup Token 只需要推理权限
}

class AnthropicOAuthService:
    """Anthropic OAuth Setup Token服务"""
    
    def __init__(self):
        self.session_cache = {}  # 临时存储OAuth会话状态
    
    def generate_state(self) -> str:
        """生成随机的 state 参数"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    def generate_code_verifier(self) -> str:
        """生成随机的 code verifier（PKCE）"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    def generate_code_challenge(self, code_verifier: str) -> str:
        """生成 code challenge（PKCE）"""
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    
    def generate_setup_token_auth_url(self, code_challenge: str, state: str) -> str:
        """生成 Setup Token 授权 URL"""
        from urllib.parse import urlencode
        
        params = {
            'code': 'true',
            'client_id': OAUTH_CONFIG["CLIENT_ID"],
            'response_type': 'code',
            'redirect_uri': OAUTH_CONFIG["REDIRECT_URI"],
            'scope': OAUTH_CONFIG["SCOPES_SETUP"],
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'state': state
        }
        
        return f"{OAUTH_CONFIG['AUTHORIZE_URL']}?{urlencode(params)}"
    
    async def generate_setup_token_params(self) -> Dict[str, Any]:
        """生成Setup Token授权URL和相关参数"""
        state = self.generate_state()
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)
        
        auth_url = self.generate_setup_token_auth_url(code_challenge, state)
        
        # 生成唯一的会话ID
        session_id = secrets.token_urlsafe(32)
        
        # 临时存储会话参数（实际生产环境应该使用Redis等）
        self.session_cache[session_id] = {
            'type': 'setup-token',
            'code_verifier': code_verifier,
            'state': state,
            'code_challenge': code_challenge,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=10)  # 10分钟过期
        }
        
        logger.info(f"🔗 Generated Setup Token authorization URL with session: {session_id}")
        
        return {
            'auth_url': auth_url,
            'session_id': session_id,
            'expires_in': 600  # 10分钟
        }
    
    async def exchange_setup_token_code(
        self, 
        session_id: str, 
        authorization_code: str,
        session: AsyncSession,
        use_manual_mode: bool = False
    ) -> Dict[str, Any]:
        """使用授权码交换Setup Token（访问令牌）
        
        这是真正的OAuth流程，不是简单地把授权码当作API key
        参考claude-relay-service的实现
        
        Args:
            session_id: OAuth会话ID
            authorization_code: 授权码或包含token的完整URL
            session: 数据库会话
            use_manual_mode: 是否使用手动模式（用户在浏览器完成OAuth后提供完整URL）
        """
        
        # 获取会话信息
        if session_id not in self.session_cache:
            raise APIException(400, "无效的会话ID或会话已过期")
        
        oauth_session = self.session_cache[session_id]
        
        # 检查会话类型
        if oauth_session['type'] != 'setup-token':
            raise APIException(400, "无效的会话类型")
        
        # 检查会话是否过期
        if datetime.now() > oauth_session['expires_at']:
            del self.session_cache[session_id]
            raise APIException(400, "授权会话已过期，请重新生成授权链接")
        
        # 首先检查是否是包含access_token的URL（手动模式）
        if '#' in authorization_code and 'access_token=' in authorization_code:
            logger.info("🔄 Detected manual mode: parsing token from callback URL")
            return self._parse_token_from_callback_url(authorization_code, session_id)
        
        # 解析授权码
        cleaned_code = self._parse_authorization_code(authorization_code)
        
        # 准备OAuth token交换参数（与claude-relay-service完全一致）
        params = {
            'grant_type': 'authorization_code',
            'client_id': OAUTH_CONFIG["CLIENT_ID"],
            'code': cleaned_code,
            'redirect_uri': OAUTH_CONFIG["REDIRECT_URI"],
            'code_verifier': oauth_session['code_verifier'],
            'state': oauth_session['state'],
            'expires_in': 31536000  # Setup Token 可以设置较长的过期时间 (与claude-relay-service一致)
        }
        
        headers = {
            'Content-Type': 'application/json',  # 注意：claude-relay-service使用JSON
            'User-Agent': 'claude-cli/1.0.56 (external, cli)',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://claude.ai/',
            'Origin': 'https://claude.ai',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site'
        }
        
        try:
            logger.info(f"🔄 Attempting Setup Token OAuth exchange for session: {session_id}")
            logger.info(f"Token exchange URL: {OAUTH_CONFIG['TOKEN_URL']}")
            logger.info(f"Code prefix: {cleaned_code[:10]}...")
            logger.info(f"Request params: {list(params.keys())}")  # 记录参数键，不记录敏感值
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(
                    OAUTH_CONFIG["TOKEN_URL"],
                    json=params,  # 使用JSON而不是form data
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()
                    logger.info(f"Response status: {response.status}")
                    logger.info(f"Response headers: {dict(response.headers)}")
                    
                    if response.status != 200:
                        logger.error(f"❌ Setup Token exchange failed: HTTP {response.status}")
                        logger.error(f"Response body: {response_text[:500]}")
                        
                        # 尝试解析错误信息
                        try:
                            error_data = json.loads(response_text)
                            error_msg = error_data.get('error', 'Unknown error')
                            error_desc = error_data.get('error_description', '')
                            raise APIException(400, f"OAuth交换失败: {error_msg} - {error_desc}")
                        except json.JSONDecodeError:
                            raise APIException(400, f"OAuth交换失败: HTTP {response.status}")
                    
                    # 解析成功响应
                    try:
                        token_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        logger.error(f"❌ Failed to parse token response: {response_text[:200]}")
                        raise APIException(500, "服务器返回了无效的JSON响应")
                    
                    logger.info("✅ Setup Token OAuth exchange successful")
                    logger.info(f"Token data keys: {list(token_data.keys())}")
                    
                    # 清理已使用的会话
                    del self.session_cache[session_id]
                    
                    # 返回OAuth token数据（格式与claude-relay-service一致）
                    result = {
                        'access_token': token_data.get('access_token'),
                        'refresh_token': token_data.get('refresh_token', ''),  # Setup Token通常没有refresh token
                        'expires_at': (datetime.now() + timedelta(seconds=token_data.get('expires_in', 31536000))).isoformat(),
                        'scopes': token_data.get('scope', 'user:inference').split(' '),
                        'token_type': token_data.get('token_type', 'Bearer')
                    }
                    
                    # 提取可能的订阅信息
                    if any(key in token_data for key in ['subscription', 'plan', 'tier', 'account_type']):
                        result['subscription_info'] = {
                            k: v for k, v in token_data.items() 
                            if k in ['subscription', 'plan', 'tier', 'account_type', 'features', 'limits']
                        }
                        logger.info(f"🎯 Found subscription info: {result['subscription_info']}")
                    
                    return result
                    
        except APIException:
            raise
        except aiohttp.ClientError as e:
            logger.error(f"❌ Network error during OAuth exchange: {e}")
            raise APIException(500, f"网络错误: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error during OAuth exchange: {e}")
            raise APIException(500, f"OAuth交换失败: {str(e)}")
    
    def _parse_token_from_callback_url(self, callback_url: str, session_id: str) -> Dict[str, Any]:
        """从回调URL中解析access_token（手动模式）
        
        当Cloudflare阻止自动交换时，用户可以在浏览器中完成OAuth流程，
        然后将包含access_token的完整回调URL提供给我们
        
        示例URL格式:
        https://console.anthropic.com/oauth/code/callback#access_token=xxx&token_type=Bearer&expires_in=31536000
        """
        try:
            from urllib.parse import urlparse, parse_qs
            
            # 解析URL
            parsed = urlparse(callback_url)
            
            # OAuth token通常在fragment中（#后面的部分）
            fragment_params = parse_qs(parsed.fragment)
            
            # 提取token信息
            access_token = fragment_params.get('access_token', [None])[0]
            token_type = fragment_params.get('token_type', ['Bearer'])[0]
            expires_in = int(fragment_params.get('expires_in', [31536000])[0])
            scope = fragment_params.get('scope', ['user:inference'])[0]
            
            if not access_token:
                # 尝试从query参数中获取
                query_params = parse_qs(parsed.query)
                access_token = query_params.get('access_token', [None])[0]
                
                if not access_token:
                    raise APIException(400, "回调URL中未找到access_token")
            
            logger.info(f"✅ Successfully parsed token from callback URL")
            logger.info(f"   Token type: {token_type}, Expires in: {expires_in} seconds")
            
            # 清理会话
            if session_id in self.session_cache:
                del self.session_cache[session_id]
            
            # 返回与正常OAuth流程相同的格式
            return {
                'access_token': access_token,
                'refresh_token': '',  # 手动模式通常没有refresh token
                'expires_at': (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
                'scopes': scope.split(' ') if scope else ['user:inference'],
                'token_type': token_type,
                'manual_mode': True  # 标记为手动模式
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to parse token from callback URL: {e}")
            raise APIException(400, f"解析回调URL失败: {str(e)}")
    
    def _parse_authorization_code(self, input_str: str) -> str:
        """解析授权码（可能是完整URL或直接的code）
        
        参考claude-relay-service的parseCallbackUrl函数
        """
        if not input_str or not isinstance(input_str, str):
            raise APIException(400, "请提供有效的授权码或回调URL")
        
        trimmed = input_str.strip()
        
        # 尝试作为完整URL解析
        if trimmed.startswith('http://') or trimmed.startswith('https://'):
            try:
                from urllib.parse import urlparse, parse_qs
                url_obj = urlparse(trimmed)
                
                # 先检查query参数
                code = parse_qs(url_obj.query).get('code', [None])[0]
                if code:
                    return code
                
                # 再检查fragment（有些情况下code在fragment中）
                code = parse_qs(url_obj.fragment).get('code', [None])[0]
                if code:
                    return code
                
                raise APIException(400, "回调URL中未找到授权码(code参数)")
            except Exception as e:
                if "回调URL中未找到授权码" in str(e):
                    raise
                raise APIException(400, "无效的URL格式")
        
        # 直接的授权码
        # 移除可能的URL fragments
        cleaned = trimmed.split('#')[0].split('&')[0]
        
        # 验证授权码格式
        if not cleaned or len(cleaned) < 10:
            raise APIException(400, "授权码格式无效")
        
        # 基本格式验证：授权码应该只包含字母、数字、下划线、连字符
        import re
        if not re.match(r'^[A-Za-z0-9_-]+$', cleaned):
            raise APIException(400, "授权码包含无效字符")
        
        return cleaned
    
    async def create_account_with_setup_token(
        self, 
        account_name: str,
        token_data: Dict[str, Any],
        description: str = None,
        daily_limit: float = 50.0,
        priority: int = 50,
        session: AsyncSession = None
    ) -> ClaudeAccount:
        """使用Setup Token创建Claude账户
        
        Setup Token通过OAuth获取的access_token存储在oauth_access_token字段
        与claude-relay-service保持一致
        """
        
        access_token = token_data['access_token']
        
        account = ClaudeAccount(
            account_name=account_name,
            api_key="",  # Setup Token不使用api_key字段
            proxy_type="setup_token",  # 标记为setup token类型
            
            # OAuth字段存储真实的OAuth token
            oauth_access_token=access_token,  # OAuth访问令牌
            oauth_refresh_token=token_data.get('refresh_token', ''),
            oauth_expires_at=datetime.fromisoformat(token_data['expires_at']) if token_data.get('expires_at') else None,
            oauth_scopes=','.join(token_data.get('scopes', [])),
            oauth_token_type=token_data.get('token_type', 'Bearer'),
            
            # 基本设置
            daily_limit=daily_limit,
            current_usage=0,
            status="active",
            priority=priority,
            success_rate=100.0,
            total_requests=0,
            failed_requests=0,
            is_schedulable=True,
            account_type="setup_token",
            
            # 额外信息
            description=description,
            subscription_info=json.dumps(token_data.get('subscription_info', {})) if token_data.get('subscription_info') else None
        )
        
        session.add(account)
        await session.commit()
        await session.refresh(account)
        
        logger.info(f"✅ Created Setup Token account: {account_name} (ID: {account.id})")
        logger.info(f"   Token type: {account.oauth_token_type}, Scopes: {account.oauth_scopes}")
        
        return account
    
    async def test_account_connection(self, account: ClaudeAccount) -> Dict[str, Any]:
        """测试Setup Token账户连接
        
        Setup Token使用OAuth访问令牌，通过Authorization header传递
        """
        
        # Setup Token存储在oauth_access_token字段
        if not account.oauth_access_token:
            return {
                "success": False,
                "error": "未找到访问令牌"
            }
        
        # 检查token是否过期（如果设置了过期时间）
        if account.oauth_expires_at and datetime.now() > account.oauth_expires_at:
            return {
                "success": False,
                "error": "访问令牌已过期"
            }
        
        # 构建请求头（与claude-relay-service一致）
        headers = {
            'Authorization': f'{account.oauth_token_type} {account.oauth_access_token}',
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
            'User-Agent': 'TrademeApp/1.0'
        }
        
        # 测试消息
        test_payload = {
            "model": "claude-3-haiku-20240307",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }
        
        try:
            async with aiohttp.ClientSession() as http_session:
                # 使用Claude的消息API进行测试
                async with http_session.post(
                    "https://api.anthropic.com/v1/messages",
                    json=test_payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    logger.info(f"Testing OAuth token for account: {account.account_name}, status: {response.status}")
                    
                    if response.status == 200:
                        return {
                            "success": True,
                            "account_name": account.account_name,
                            "scopes": account.oauth_scopes.split(',') if account.oauth_scopes else [],
                            "token_type": account.oauth_token_type,
                            "expires_at": account.oauth_expires_at.isoformat() if account.oauth_expires_at else None,
                            "message": "访问令牌有效且工作正常"
                        }
                    elif response.status == 429:
                        return {
                            "success": True,
                            "account_name": account.account_name,
                            "scopes": account.oauth_scopes.split(',') if account.oauth_scopes else [],
                            "token_type": account.oauth_token_type,
                            "expires_at": account.oauth_expires_at.isoformat() if account.oauth_expires_at else None,
                            "message": "访问令牌有效（当前速率限制）"
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "error": "访问令牌无效或已过期"
                        }
                    elif response.status == 403:
                        return {
                            "success": False,
                            "error": "访问令牌权限不足"
                        }
                    else:
                        response_text = await response.text()
                        return {
                            "success": False,
                            "error": f"测试失败: HTTP {response.status} - {response_text[:200]}"
                        }
            
        except Exception as e:
            logger.error(f"❌ OAuth token connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup_expired_sessions(self):
        """清理过期的OAuth会话"""
        current_time = datetime.now()
        expired_sessions = [
            session_id for session_id, session_data in self.session_cache.items()
            if current_time > session_data['expires_at']
        ]
        
        for session_id in expired_sessions:
            del self.session_cache[session_id]
            logger.info(f"🧹 Cleaned up expired OAuth session: {session_id}")

# 全局实例
anthropic_oauth_service = AnthropicOAuthService()