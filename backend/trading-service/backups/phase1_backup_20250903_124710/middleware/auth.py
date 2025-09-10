"""
认证中间件
处理JWT token验证和用户身份认证
"""

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional, Set
from datetime import datetime, timezone
import hashlib

from app.config import settings
from app.schemas.user import TokenPayload
from app.models.user import User

# JWT Bearer认证
security = HTTPBearer(auto_error=False)

# Token黑名单（生产环境应使用Redis）
_token_blacklist: Set[str] = set()

def _hash_token(token: str) -> str:
    """对token进行哈希，避免在内存中存储完整token"""
    return hashlib.sha256(token.encode()).hexdigest()

def blacklist_token(token: str) -> None:
    """将token加入黑名单"""
    token_hash = _hash_token(token)
    _token_blacklist.add(token_hash)

def is_token_blacklisted(token: str) -> bool:
    """检查token是否在黑名单中"""
    token_hash = _hash_token(token)
    return token_hash in _token_blacklist

def clear_expired_tokens_from_blacklist() -> None:
    """清理过期token从黑名单中（简化实现）"""
    # 在生产环境中应该基于token的exp字段来清理
    # 这里为了简化，可以定期清理整个黑名单
    global _token_blacklist
    _token_blacklist.clear()


class AuthenticationError(HTTPException):
    """认证异常"""
    def __init__(self, detail: str = "认证失败"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


def verify_token(token: str) -> Optional[TokenPayload]:
    """验证JWT token"""
    try:
        # 检查token是否在黑名单中
        if is_token_blacklisted(token):
            return None
        
        # 检查token长度，防止过长的token
        if len(token) > 2048:  # JWT token通常不会超过2KB
            return None
        
        # 使用JWT密钥 (优先使用jwt_secret，回退到jwt_secret_key)
        jwt_key = settings.jwt_secret or settings.jwt_secret_key
        
        # 检查JWT密钥安全性
        if not jwt_key or len(jwt_key) < 32:
            raise ValueError("JWT密钥不安全：长度不足32字符")
        
        # 严格验证JWT token - 恢复所有安全检查
        payload = jwt.decode(
            token, 
            jwt_key, 
            algorithms=[settings.jwt_algorithm],
            options={
                "verify_aud": True,  # 验证受众
                "verify_iss": True,  # 验证颁发者  
                "verify_exp": True   # 验证过期时间
            },
            audience="trademe-app",    # 预期受众
            issuer="trademe-user-service"  # 预期颁发者
        )
        
        # 验证必要字段 (兼容用户服务JWT格式)
        user_id = payload.get("userId") or payload.get("user_id")  
        email = payload.get("email")
        username = payload.get("username") or f"user_{user_id}"  
        membership_level = payload.get("membershipLevel") or payload.get("membership_level", "basic")
        
        # 验证token类型
        token_type = payload.get("type")
        if token_type != "access":
            return None
            
        if not all([user_id, email]):
            return None
            
        # 额外的过期时间检查 (JWT库已经验证，这里是双重保险)
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None
        
        return TokenPayload(
            user_id=int(user_id),
            email=email,
            username=username,
            membership_level=membership_level.lower(),  # 转换为小写
            exp=exp
        )
        
    except JWTError as e:
        return None
    except Exception as e:
        return None


def verify_jwt_token(token: str) -> dict:
    """验证JWT token并返回payload - 用于WebSocket认证"""
    try:
        # 检查token是否在黑名单中
        if is_token_blacklisted(token):
            raise ValueError("Token已被吊销")
        
        # 检查token长度，防止过长的token
        if len(token) > 2048:  # JWT token通常不会超过2KB
            raise ValueError("Token长度异常")
        
        # 使用JWT密钥 (优先使用jwt_secret，回退到jwt_secret_key)
        jwt_key = settings.jwt_secret or settings.jwt_secret_key
        
        # 检查JWT密钥安全性
        if not jwt_key or len(jwt_key) < 32:
            raise ValueError("JWT密钥不安全：长度不足32字符")
        
        # 严格验证JWT token - 恢复所有安全检查
        payload = jwt.decode(
            token, 
            jwt_key, 
            algorithms=[settings.jwt_algorithm],
            options={
                "verify_aud": True,  # 验证受众
                "verify_iss": True,  # 验证颁发者  
                "verify_exp": True   # 验证过期时间
            },
            audience="trademe-app",    # 预期受众
            issuer="trademe-user-service"  # 预期颁发者
        )
        
        # 验证必要字段 (兼容用户服务JWT格式)
        user_id = payload.get("userId") or payload.get("user_id")
        email = payload.get("email")
        
        # 验证token类型
        token_type = payload.get("type")
        if token_type != "access":
            raise ValueError(f"无效的token类型: {token_type}")
        
        if not all([user_id, email]):
            raise ValueError(f"Token缺少必要字段: user_id={user_id}, email={email}")
            
        # JWT库已经验证过期时间，这里不需要重复检查
        
        # 标准化返回格式
        return {
            "user_id": int(user_id),
            "email": email,
            "username": payload.get("username") or f"user_{user_id}",
            "membership_level": (payload.get("membershipLevel") or payload.get("membership_level", "basic")).lower(),
            "exp": payload.get("exp")
        }
        
    except JWTError as e:
        raise ValueError("JWT验证失败")
    except Exception as e:
        raise ValueError("Token验证错误")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """获取当前用户"""
    
    # 检查是否提供了认证凭据
    token = None
    
    # 优先从credentials中获取
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        # 手动从headers中提取
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header:
            # 检查Bearer格式
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()  # 移除 "Bearer " 前缀并去除空格
    
    if not token:
        raise AuthenticationError("缺少认证令牌")
    
    # 验证token
    token_payload = verify_token(token)
    if not token_payload:
        raise AuthenticationError("无效的认证令牌")
        
    # 创建用户对象
    mock_user = MockUser(
        user_id=token_payload.user_id,
        membership_level=token_payload.membership_level
    )
    mock_user.email = token_payload.email
    mock_user.username = token_payload.username
    
    return mock_user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前激活用户"""
    if not current_user.is_active:
        raise AuthenticationError("用户账户已被禁用")
    
    return current_user


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc).timestamp() + expires_delta
    else:
        expire = datetime.now(timezone.utc).timestamp() + (settings.jwt_expire_minutes * 60)
    
    # 添加标准JWT字段以通过严格验证
    to_encode.update({
        "exp": expire,
        "aud": "trademe-app",           # 受众
        "iss": "trademe-user-service",  # 颁发者
        "iat": datetime.now(timezone.utc).timestamp(),  # 颁发时间
        "type": "access"                # token类型
    })
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.jwt_secret_key or settings.jwt_secret, 
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def verify_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """验证管理员用户"""
    # 严格的管理员权限检查
    allowed_levels = ["professional", "admin"]  # 仅professional和admin级别用户可以访问管理功能
    allowed_emails = ["admin@trademe.com"]  # 允许特定管理员邮箱
    
    if (current_user.membership_level not in allowed_levels and 
        current_user.email not in allowed_emails):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限"
        )
    
    return current_user


class MockUser:
    """模拟用户类 - 用于测试和开发"""
    def __init__(self, user_id: int = 1, membership_level: str = "basic"):
        self.id = user_id
        self.username = f"test_user_{user_id}"
        self.email = f"test{user_id}@example.com"
        self.membership_level = membership_level
        self.is_active = True
        self.email_verified = True
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.phone = None
        self.avatar_url = None
        self.membership_expires_at = None
        self.last_login_at = datetime.now(timezone.utc)


def get_mock_user(user_id: int = 1, membership_level: str = "basic") -> MockUser:
    """获取模拟用户 - 用于开发测试"""
    return MockUser(user_id, membership_level)


def logout_user(token: str) -> bool:
    """用户注销 - 将token加入黑名单"""
    try:
        # 先验证token格式是否正确（宽松验证，不检查audience和issuer）
        payload = jwt.decode(
            token,
            settings.jwt_secret_key or settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "verify_signature": True,
                "verify_exp": False,  # 即使过期也要加入黑名单
                "verify_aud": False,  # 注销时不验证audience
                "verify_iss": False   # 注销时不验证issuer
            }
        )
        
        # 将token加入黑名单
        blacklist_token(token)
        return True
        
    except JWTError:
        # 即使token格式不正确，也加入黑名单以防万一
        blacklist_token(token)
        return False


# 可选的认证依赖（用于不需要强制认证的端点）
async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """可选的当前用户获取（不强制认证）"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except AuthenticationError:
        return None