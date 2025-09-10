#!/usr/bin/env python3
"""
Trademe JWT令牌生成脚本
用于测试和调试AI功能
"""

import jwt
from datetime import datetime, timedelta, timezone
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.config import settings
    print(f"✅ 成功加载配置")
except ImportError:
    print("❌ 无法加载配置，使用默认值")
    # 使用默认配置
    class MockSettings:
        jwt_secret_key = "Mt#HHq9rTDDWn38pEFxPtS6PiF{Noz[s=[IHMNZGRq@j*W1JWA*RPgufyrrZWhXH"
        jwt_algorithm = "HS256"
        jwt_expire_minutes = 1440
    
    settings = MockSettings()

def generate_jwt_token(user_id: int, email: str, membership_level: str = "professional"):
    """生成JWT令牌"""
    
    # 当前时间
    now = datetime.now(timezone.utc)
    
    # 令牌载荷（必须与后端验证期望的格式一致）
    payload = {
        "userId": user_id,  # 注意是 userId 而不是 user_id
        "email": email,
        "membershipLevel": membership_level,  # 注意是 membershipLevel
        "type": "access",  # 必须包含 type 字段
        "iat": now,  # 签发时间
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),  # 过期时间
        "aud": "trademe-app",  # 受众必须是 trademe-app
        "iss": "trademe-user-service",  # 签发者必须是 trademe-user-service
    }
    
    # 生成令牌
    token = jwt.encode(
        payload, 
        settings.jwt_secret_key, 
        algorithm=settings.jwt_algorithm
    )
    
    return token

def main():
    """主函数"""
    print("🔐 Trademe JWT令牌生成器")
    print("=" * 50)
    
    # 用户信息
    user_id = 6
    email = "admin@trademe.com"
    membership_level = "professional"
    
    print(f"📄 用户信息:")
    print(f"   用户ID: {user_id}")
    print(f"   邮箱: {email}")
    print(f"   会员级别: {membership_level}")
    print(f"   令牌有效期: {settings.jwt_expire_minutes}分钟")
    
    try:
        # 生成令牌
        token = generate_jwt_token(user_id, email, membership_level)
        
        print(f"\n✅ JWT令牌生成成功!")
        print("=" * 50)
        print("🎯 令牌 (可直接复制使用):")
        print(token)
        print("=" * 50)
        
        # 验证令牌 - 启用完整安全验证
        try:
            decoded = jwt.decode(
                token, 
                settings.jwt_secret_key, 
                algorithms=[settings.jwt_algorithm],
                options={
                    "verify_aud": True,   # 验证受众
                    "verify_iss": True,   # 验证颁发者
                    "verify_exp": True    # 验证过期时间
                },
                audience="trademe-app",        # 预期受众
                issuer="trademe-user-service"  # 预期颁发者
            )
            print(f"\n✅ 令牌验证成功!")
            print(f"📋 解码后的载荷:")
            for key, value in decoded.items():
                if key in ['iat', 'exp']:
                    # 转换时间戳为可读格式
                    dt = datetime.fromtimestamp(value, tz=timezone.utc)
                    print(f"   {key}: {value} ({dt.strftime('%Y-%m-%d %H:%M:%S UTC')})")
                else:
                    print(f"   {key}: {value}")
        
        except jwt.InvalidTokenError as e:
            print(f"❌ 令牌验证失败: {e}")
        
        print(f"\n📝 使用示例:")
        print(f'curl -X POST "http://43.167.252.120:8001/api/v1/ai/chat" \\')
        print(f'  -H "Content-Type: application/json" \\')
        print(f'  -H "Authorization: Bearer {token}" \\')
        print(f'  -d \'{{"content":"测试AI策略生成","ai_mode":"trader","session_type":"strategy"}}\'')
        
    except Exception as e:
        print(f"❌ 令牌生成失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)