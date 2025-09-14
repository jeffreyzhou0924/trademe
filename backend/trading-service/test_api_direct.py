#!/usr/bin/env python3
"""
直接测试API端点
"""

import requests
import json

def test_health():
    """测试健康检查"""
    try:
        response = requests.get("http://localhost:8001/health")
        print(f"健康检查: {response.status_code}")
        if response.status_code == 200:
            print(f"响应: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

def test_strategies_list():
    """测试策略列表API"""
    try:
        # 这个需要认证，我们期望401
        response = requests.get("http://localhost:8001/api/v1/strategies/")
        print(f"策略列表API: {response.status_code}")
        if response.status_code == 401:
            print("✅ API正常（需要认证）")
            return True
        else:
            print(f"意外响应: {response.text}")
        return False
    except Exception as e:
        print(f"策略列表测试失败: {e}")
        return False

def main():
    print("🧪 直接API测试")
    print("=" * 40)
    
    if test_health():
        print("✅ 交易服务运行正常")
    else:
        print("❌ 交易服务健康检查失败")
        return
    
    if test_strategies_list():
        print("✅ 策略API端点正常")
    else:
        print("❌ 策略API端点异常")

if __name__ == "__main__":
    main()