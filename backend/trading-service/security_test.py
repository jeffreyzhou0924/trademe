#!/usr/bin/env python3
"""
Trademe平台安全测试脚本

验证安全修复效果，包括：
- JWT认证机制
- Token黑名单功能
- 配置安全性
- 敏感信息保护
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import asyncio
from datetime import datetime, timezone
from app.middleware.auth import (
    verify_token, verify_jwt_token, 
    blacklist_token, is_token_blacklisted,
    create_access_token, logout_user
)
from app.config import settings, validate_settings


class SecurityTester:
    """安全测试类"""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def log_test(self, test_name: str, result: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if result else "❌ FAIL"
        self.test_results.append(f"{status} {test_name}: {message}")
        if result:
            self.passed += 1
        else:
            self.failed += 1
    
    def test_jwt_security_enhancements(self):
        """测试JWT安全增强"""
        print("\n🔒 测试JWT安全增强...")
        
        # 测试1: 验证JWT密钥安全性检查
        try:
            # 创建一个测试用户数据
            user_data = {
                "user_id": 1,
                "email": "test@example.com",
                "username": "testuser",
                "membership_level": "basic",
                "type": "access"
            }
            
            # 创建token
            token = create_access_token(user_data)
            self.log_test("JWT Token创建", bool(token), f"Token长度: {len(token)}")
            
            # 验证token
            payload = verify_token(token)
            self.log_test("JWT Token验证", payload is not None, f"用户ID: {payload.user_id if payload else 'None'}")
            
        except Exception as e:
            self.log_test("JWT Token基础功能", False, f"错误: {str(e)}")
    
    def test_token_blacklist_functionality(self):
        """测试Token黑名单功能"""
        print("\n🚫 测试Token黑名单功能...")
        
        try:
            # 创建测试token
            user_data = {
                "user_id": 2,
                "email": "blacklist@example.com", 
                "username": "blacklistuser",
                "membership_level": "basic",
                "type": "access"
            }
            token = create_access_token(user_data)
            
            # 测试1: 正常token验证
            payload = verify_token(token)
            self.log_test("Token黑名单前验证", payload is not None, "Token应该有效")
            
            # 测试2: 加入黑名单
            blacklist_token(token)
            self.log_test("Token加入黑名单", is_token_blacklisted(token), "Token应该在黑名单中")
            
            # 测试3: 黑名单token验证
            payload_after = verify_token(token)
            self.log_test("Token黑名单后验证", payload_after is None, "Token应该被拒绝")
            
            # 测试4: 用户注销功能
            user_data2 = {"user_id": 3, "email": "logout@example.com", "type": "access"}
            token2 = create_access_token(user_data2)
            logout_result = logout_user(token2)
            self.log_test("用户注销功能", logout_result, "Token应该被成功注销")
            
            # 验证注销后的token
            payload_logout = verify_token(token2)
            self.log_test("注销后Token验证", payload_logout is None, "注销的Token应该被拒绝")
            
        except Exception as e:
            self.log_test("Token黑名单功能", False, f"错误: {str(e)}")
    
    def test_configuration_security(self):
        """测试配置安全性"""
        print("\n⚙️ 测试配置安全性...")
        
        try:
            # 测试JWT密钥长度
            jwt_key = settings.jwt_secret_key or settings.jwt_secret
            self.log_test("JWT密钥长度检查", len(jwt_key) >= 32, f"密钥长度: {len(jwt_key)}")
            
            # 测试JWT密钥不是默认值
            unsafe_keys = [
                "your-secret-key-here",
                "your_super_secret_jwt_key_here", 
                "trademe_super_secret_jwt_key_for_development_only_32_chars",
                "TrademeSecure2024!@#$%^&*()_+{}|:<>?[];',./`~abcdefghijklmnop",
                "Mt#HHq9rTDDWn38pEFxPtS6PiF{Noz[s=[IHMNZGRq@j*W1JWA*RPgufyrrZWhXH"
            ]
            is_safe_key = jwt_key not in unsafe_keys
            self.log_test("JWT密钥非默认值", is_safe_key, "密钥应该不是默认值")
            
            # 测试环境配置
            if settings.environment == "production":
                self.log_test("生产环境Debug关闭", not settings.debug, f"Debug: {settings.debug}")
                self.log_test("生产环境密钥长度", len(jwt_key) >= 64, f"生产环境密钥长度: {len(jwt_key)}")
            else:
                self.log_test("开发环境配置", True, f"环境: {settings.environment}")
            
        except Exception as e:
            self.log_test("配置安全性", False, f"错误: {str(e)}")
    
    def test_token_validation_edge_cases(self):
        """测试Token验证边界情况"""
        print("\n🧪 测试Token验证边界情况...")
        
        try:
            # 测试1: 空token
            self.log_test("空Token验证", verify_token("") is None, "空token应该被拒绝")
            
            # 测试2: 无效token
            self.log_test("无效Token验证", verify_token("invalid.token.here") is None, "无效token应该被拒绝")
            
            # 测试3: 超长token (>2KB)
            long_token = "a" * 3000
            self.log_test("超长Token验证", verify_token(long_token) is None, "超长token应该被拒绝")
            
            # 测试4: WebSocket token验证
            try:
                verify_jwt_token("invalid")
                self.log_test("WebSocket无效Token", False, "应该抛出异常")
            except ValueError:
                self.log_test("WebSocket无效Token", True, "正确抛出ValueError异常")
            
        except Exception as e:
            self.log_test("Token验证边界情况", False, f"错误: {str(e)}")
    
    def test_security_configuration_validation(self):
        """测试安全配置验证"""
        print("\n🔧 测试安全配置验证...")
        
        try:
            # 测试配置验证函数
            if settings.environment == "production":
                try:
                    validate_settings()
                    self.log_test("生产环境配置验证", True, "配置验证通过")
                except ValueError as ve:
                    self.log_test("生产环境配置验证", False, f"配置验证失败: {ve}")
            else:
                self.log_test("开发环境配置", True, "跳过生产环境验证")
            
            # 测试CORS配置
            cors_secure = all(
                origin.startswith('https://') 
                for origin in settings.cors_origins 
                if not origin.startswith('http://localhost')
            )
            if settings.environment == "production":
                self.log_test("CORS配置安全", cors_secure, f"CORS origins: {settings.cors_origins}")
            else:
                self.log_test("开发环境CORS", True, "开发环境允许localhost")
            
        except Exception as e:
            self.log_test("安全配置验证", False, f"错误: {str(e)}")
    
    def run_all_tests(self):
        """运行所有安全测试"""
        print("🛡️ Trademe平台安全测试开始")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # 运行所有测试
        self.test_jwt_security_enhancements()
        self.test_token_blacklist_functionality()
        self.test_configuration_security()
        self.test_token_validation_edge_cases()
        self.test_security_configuration_validation()
        
        # 输出测试结果
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print("📊 安全测试结果汇总")
        print("=" * 60)
        
        for result in self.test_results:
            print(result)
        
        print(f"\n📈 测试统计:")
        print(f"   ✅ 通过: {self.passed}")
        print(f"   ❌ 失败: {self.failed}")
        print(f"   📊 总计: {self.passed + self.failed}")
        print(f"   🕐 耗时: {duration.total_seconds():.2f}秒")
        
        # 安全评分
        if self.passed + self.failed > 0:
            success_rate = (self.passed / (self.passed + self.failed)) * 100
            print(f"   🎯 成功率: {success_rate:.1f}%")
            
            if success_rate >= 90:
                print("   🟢 安全等级: 优秀")
            elif success_rate >= 80:
                print("   🟡 安全等级: 良好")
            elif success_rate >= 70:
                print("   🟠 安全等级: 一般")
            else:
                print("   🔴 安全等级: 需要改进")
        
        print("\n🔒 安全建议:")
        print("   • 定期更换JWT密钥")
        print("   • 监控异常登录尝试")
        print("   • 使用HTTPS协议")
        print("   • 定期安全审计")
        
        return self.failed == 0


if __name__ == "__main__":
    tester = SecurityTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 所有安全测试通过！系统安全性良好。")
        sys.exit(0)
    else:
        print("\n⚠️  部分安全测试失败，请检查相关配置。")
        sys.exit(1)