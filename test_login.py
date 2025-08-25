#!/usr/bin/env python3
"""
测试用户登录
"""

import requests
import json

# 测试账户
test_user = {
    "email": "publictest@example.com",
    "password": "PublicTest123!"
}

# 登录
response = requests.post(
    "http://localhost:3001/api/v1/auth/login",
    json=test_user
)

print("Status Code:", response.status_code)
print("Response:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

# 如果成功，提取token
if response.status_code == 200:
    data = response.json()
    token = data.get("accessToken") or data.get("token")
    if token:
        print(f"\nToken: {token}")
    else:
        print("\n没有找到token")