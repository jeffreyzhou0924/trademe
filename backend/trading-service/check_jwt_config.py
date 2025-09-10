#!/usr/bin/env python3
from app.config import settings

print(f"JWT Secret Key: {settings.jwt_secret_key}")
print(f"JWT Secret: {settings.jwt_secret}")
print(f"JWT Algorithm: {settings.jwt_algorithm}")

# 使用实际配置的密钥
import jwt
from datetime import datetime, timedelta

jwt_key = settings.jwt_secret_key or settings.jwt_secret
print(f"Using JWT Key: {jwt_key}")

def generate_admin_token():
    """生成管理员token使用实际配置的密钥"""
    payload = {
        "userId": "6", 
        "email": "admin@trademe.com",
        "membershipLevel": "professional",
        "type": "access",
        "iat": int(datetime.now().timestamp()),
        "exp": int((datetime.now() + timedelta(days=7)).timestamp()),  # 7天有效期
        "aud": "trademe-app",
        "iss": "trademe-user-service"
    }
    
    token = jwt.encode(payload, jwt_key, algorithm=settings.jwt_algorithm)
    return token

if __name__ == "__main__":
    token = generate_admin_token()
    print(f"\nCorrect JWT Token: {token}")
    print("\nToken expires in 7 days")