#!/usr/bin/env python3
import jwt
from datetime import datetime, timedelta

# JWT配置 (从config.py复制)
JWT_SECRET = "trademe_secret_key_very_strong_and_unique_2024"  # 应该与config.py中的一致
JWT_ALGORITHM = "HS256"

def generate_admin_token():
    """生成管理员token"""
    payload = {
        "userId": "6", 
        "email": "admin@trademe.com",
        "membershipLevel": "professional",
        "type": "access",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(days=7)).timestamp()),  # 7天有效期
        "aud": "trademe-app",
        "iss": "trademe-user-service"
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

if __name__ == "__main__":
    token = generate_admin_token()
    print(f"New JWT Token: {token}")
    print("\nToken expires in 7 days")
    print("\nYou can now use this token for API requests:")
    print(f'curl -X GET "http://43.167.252.120/api/v1/data/query?data_type=kline&exchange=okx&symbol=BTC-USDT-SWAP" -H "Authorization: Bearer {token}"')