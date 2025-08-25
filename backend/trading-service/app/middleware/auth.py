"""
认证中间件
处理JWT token验证和用户身份认证
"""

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
from datetime import datetime

from app.config import settings
from app.schemas.user import TokenPayload
from app.models.user import User

# JWT Bearer认证
security = HTTPBearer(auto_error=False)


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
        # 使用JWT密钥 (优先使用jwt_secret，回退到jwt_secret_key)
        jwt_key = settings.jwt_secret or settings.jwt_secret_key
        
        payload = jwt.decode(
            token, 
            jwt_key, 
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False}  # 禁用audience和issuer验证
        )
        
        # 验证必要字段 (兼容用户服务JWT格式)
        user_id = payload.get("userId") or payload.get("user_id")  # 支持用户服务的userId格式
        email = payload.get("email")
        username = payload.get("username") or f"user_{user_id}"  # 如果没有username，生成一个
        membership_level = payload.get("membershipLevel") or payload.get("membership_level", "basic")
        
        # 验证issuer和audience (兼容用户服务格式)
        issuer = payload.get("iss")
        audience = payload.get("aud")
        token_type = payload.get("type")
        
        if not all([user_id, email]):
            print(f"❌ Auth Service - 缺少必要字段: user_id={user_id}, email={email}")
            return None
            
        # 检查过期时间
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            return None
        
        return TokenPayload(
            user_id=int(user_id),
            email=email,
            username=username,
            membership_level=membership_level.lower(),  # 转换为小写
            exp=exp
        )
        
    except JWTError as e:
        print(f"❌ Auth Service - JWT错误: {e}")
        return None
    except Exception as e:
        print(f"❌ Auth Service - 其他错误: {e}")
        return None


def verify_jwt_token(token: str) -> dict:
    """验证JWT token并返回payload - 用于WebSocket认证"""
    try:
        # 使用JWT密钥 (优先使用jwt_secret，回退到jwt_secret_key)
        jwt_key = settings.jwt_secret or settings.jwt_secret_key
        
        payload = jwt.decode(
            token, 
            jwt_key, 
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False, "verify_iss": False}  # 禁用audience和issuer验证
        )
        
        # 验证必要字段 (兼容用户服务JWT格式)
        user_id = payload.get("userId") or payload.get("user_id")  # 支持用户服务的userId格式
        email = payload.get("email")
        
        if not all([user_id, email]):
            raise ValueError(f"Token缺少必要字段: user_id={user_id}, email={email}")
            
        # 检查过期时间
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise ValueError("Token已过期")
        
        # 标准化返回格式
        return {
            "user_id": int(user_id),
            "email": email,
            "username": payload.get("username") or f"user_{user_id}",
            "membership_level": (payload.get("membershipLevel") or payload.get("membership_level", "basic")).lower(),
            "exp": exp
        }
        
    except JWTError as e:
        raise ValueError(f"JWT验证失败: {e}")
    except Exception as e:
        raise ValueError(f"Token验证错误: {e}")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """获取当前用户"""
    
    # 检查是否提供了认证凭据
    if not credentials:
        # 尝试手动从headers中提取
        auth_header = request.headers.get("authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # 移除 "Bearer " 前缀
            
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
        
        raise AuthenticationError("缺少认证令牌")
    
    # 验证token
    token_payload = verify_token(credentials.credentials)
    if not token_payload:
        raise AuthenticationError("无效的认证令牌")
    
    # 创建简化的用户对象 (不使用SQLAlchemy实例)
    # 实际应该从数据库获取，这里为了测试使用MockUser
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
        expire = datetime.utcnow().timestamp() + expires_delta
    else:
        expire = datetime.utcnow().timestamp() + (settings.jwt_expire_minutes * 60)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.jwt_secret_key, 
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def verify_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """验证管理员用户"""
    # 这里可以添加管理员权限检查逻辑
    # 目前简化为Elite用户具有管理员权限
    if current_user.membership_level not in ["elite", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
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
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.phone = None
        self.avatar_url = None
        self.membership_expires_at = None
        self.last_login_at = datetime.utcnow()


def get_mock_user(user_id: int = 1, membership_level: str = "basic") -> MockUser:
    """获取模拟用户 - 用于开发测试"""
    return MockUser(user_id, membership_level)


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