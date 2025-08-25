"""
用户相关的Pydantic模型
与用户服务的用户模型保持一致
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    phone: Optional[str] = Field(None, max_length=20, description="手机号码")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserCreate(UserBase):
    """创建用户模型"""
    password: str = Field(..., min_length=6, description="密码")


class UserUpdate(BaseModel):
    """更新用户模型"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, max_length=20, description="手机号码")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserResponse(UserBase):
    """用户响应模型"""
    id: int = Field(..., description="用户ID")
    membership_level: str = Field(default="basic", description="会员等级")
    membership_expires_at: Optional[datetime] = Field(None, description="会员到期时间")
    email_verified: bool = Field(default=False, description="邮箱是否验证")
    is_active: bool = Field(default=True, description="账户是否激活")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat() if dt else None
        }


class UserLogin(BaseModel):
    """用户登录模型"""
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class UserLoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="令牌有效期(秒)")
    user: UserResponse = Field(..., description="用户信息")


class TokenPayload(BaseModel):
    """JWT载荷模型"""
    user_id: int = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")
    username: str = Field(..., description="用户名")
    membership_level: str = Field(default="basic", description="会员等级")
    exp: Optional[float] = Field(None, description="过期时间戳")


class UserProfile(BaseModel):
    """用户资料模型"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    membership_level: str = Field(..., description="会员等级")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    trading_stats: Optional[dict] = Field(None, description="交易统计")
    preferences: Optional[dict] = Field(None, description="用户偏好设置")

    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """数据库中的用户模型 (继承自UserResponse)"""
    pass