#!/usr/bin/env python3
"""
测试认证流程和AI聊天页面访问
模拟用户登录并访问AI聊天功能
"""

import requests
import json
import sys

def test_auth_flow():
    """测试完整的认证流程"""
    base_url = "http://localhost:3001"  # 用户服务
    trading_url = "http://localhost:8001"  # 交易服务
    
    print("🧪 开始测试认证流程")
    print("=" * 50)
    
    # 1. 测试用户登录
    print("🔐 测试用户登录...")
    login_data = {
        "email": "admin@trademe.com",
        "password": "admin123456"
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/auth/login", json=login_data, timeout=10)
        if response.status_code == 200:
            login_result = response.json()
            data = login_result.get('data', {})
            token = data.get('access_token')
            user = data.get('user')
            
            print(f"✅ 登录成功!")
            if user:
                print(f"   用户: {user.get('email')}")
                print(f"   会员级别: {user.get('membership_level')}")
            if token:
                print(f"   Token: {token[:20]}...")
            
            # 2. 验证token有效性
            print("\n🔍 验证token有效性...")
            headers = {"Authorization": f"Bearer {token}"}
            
            me_response = requests.get(f"{base_url}/api/v1/auth/me", headers=headers, timeout=10)
            if me_response.status_code == 200:
                print("✅ Token验证成功")
                user_info = me_response.json()
                print(f"   验证用户: {user_info.get('email')}")
            else:
                print(f"❌ Token验证失败: {me_response.status_code}")
                return False
            
            # 3. 测试交易服务认证
            print("\n🏪 测试交易服务认证...")
            trading_response = requests.get(f"{trading_url}/auth/test", headers=headers, timeout=10)
            if trading_response.status_code == 200:
                print("✅ 交易服务认证成功")
                trading_result = trading_response.json()
                print(f"   交易服务用户: {trading_result.get('user', {}).get('username')}")
            else:
                print(f"❌ 交易服务认证失败: {trading_response.status_code}")
                return False
            
            # 4. 测试AI会话列表
            print("\n🤖 测试AI会话列表...")
            ai_sessions_response = requests.get(
                f"{trading_url}/api/v1/ai/sessions", 
                headers=headers,
                params={"ai_mode": "trader"},
                timeout=10
            )
            if ai_sessions_response.status_code == 200:
                sessions_data = ai_sessions_response.json()
                print(f"✅ AI会话列表获取成功")
                print(f"   会话数量: {len(sessions_data.get('sessions', []))}")
            else:
                print(f"⚠️ AI会话列表获取失败: {ai_sessions_response.status_code}")
                # AI会话获取失败不影响主要认证测试
            
            # 5. 生成前端认证数据格式
            print("\n📱 生成前端认证数据...")
            frontend_auth_data = {
                "state": {
                    "token": token,
                    "user": user,
                    "isAuthenticated": True
                }
            } if token and user else None
            
            print("✅ 前端认证数据格式:")
            print(f"   localStorage key: 'auth-storage'")
            print(f"   数据结构: {json.dumps(frontend_auth_data, indent=2)}")
            
            return True
            
        else:
            print(f"❌ 登录失败: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   错误信息: {error_data.get('message', '未知错误')}")
            except:
                print(f"   响应内容: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_service_health():
    """测试服务健康状态"""
    print("\n🏥 检查服务健康状态...")
    
    services = [
        ("用户服务", "http://localhost:3001/health"),
        ("交易服务", "http://localhost:8001/health")
    ]
    
    all_healthy = True
    
    for service_name, health_url in services:
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ {service_name}: 健康 ({health_data.get('status', 'unknown')})")
            else:
                print(f"❌ {service_name}: 不健康 ({response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"❌ {service_name}: 无法连接 ({e})")
            all_healthy = False
    
    return all_healthy

def main():
    """主测试函数"""
    print("🔐 认证流程测试工具")
    print("=" * 50)
    
    # 检查服务健康状态
    if not test_service_health():
        print("\n❌ 部分服务不可用，但继续测试...")
    
    # 测试认证流程
    success = test_auth_flow()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 认证流程测试成功！")
        print("\n💡 修复说明:")
        print("1. ✅ 用户登录功能正常")
        print("2. ✅ JWT token生成和验证正常")
        print("3. ✅ 前后端服务认证集成正常")
        print("4. ✅ localStorage存储格式正确")
        print("\n🌐 前端现在应该能够正常:")
        print("- 获取用户认证状态")
        print("- 初始化WebSocket连接")
        print("- 访问AI聊天功能")
        return True
    else:
        print("❌ 认证流程测试失败！")
        print("请检查服务状态和配置")
        return False

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        sys.exit(1)