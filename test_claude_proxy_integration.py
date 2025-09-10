#!/usr/bin/env python3
"""
Trademe Claude代理系统集成测试
测试完整的虚拟密钥认证和Claude API兼容端点访问流程

运行命令:
python test_claude_proxy_integration.py
"""

import asyncio
import json
import requests
import time
from typing import Dict, Any
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

# 测试配置
TRADING_SERVICE_URL = "http://localhost:8001"
TEST_USER_ID = 9  # publictest@example.com 用户
TEST_EMAIL = "publictest@example.com"

class ClaudeProxyIntegrationTest:
    """Claude代理系统集成测试类"""
    
    def __init__(self):
        self.base_url = TRADING_SERVICE_URL
        self.virtual_key = None
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if success else "❌ 失败"
        self.test_results.append({
            "test_name": test_name,
            "success": success,
            "details": details
        })
        print(f"{status} {test_name}")
        if details:
            print(f"   详情: {details}")
        print()
    
    def get_virtual_key(self) -> bool:
        """获取测试用户的虚拟密钥"""
        try:
            print("🔍 步骤1: 获取虚拟密钥...")
            
            # 这里模拟从数据库获取虚拟密钥的过程
            # 实际场景中，用户在注册后会自动分配虚拟密钥
            import sqlite3
            
            conn = sqlite3.connect('/root/trademe/data/trademe.db')
            cursor = conn.cursor()
            
            # 查找publictest用户的虚拟密钥
            cursor.execute("""
                SELECT virtual_key, status FROM user_claude_keys 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """, (TEST_USER_ID,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                self.virtual_key = result[0]
                self.log_test("获取虚拟密钥", True, f"密钥: {self.virtual_key[:20]}...")
                return True
            else:
                self.log_test("获取虚拟密钥", False, "未找到活跃的虚拟密钥")
                return False
                
        except Exception as e:
            self.log_test("获取虚拟密钥", False, f"异常: {str(e)}")
            return False
    
    def test_health_endpoint(self) -> bool:
        """测试健康检查端点"""
        try:
            print("🩺 步骤2: 测试健康检查端点...")
            
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                details = f"状态: {data.get('status', 'unknown')}"
                self.log_test("健康检查端点", True, details)
                return True
            else:
                self.log_test("健康检查端点", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("健康检查端点", False, f"异常: {str(e)}")
            return False
    
    def test_virtual_key_auth(self) -> bool:
        """测试虚拟密钥认证"""
        if not self.virtual_key:
            self.log_test("虚拟密钥认证", False, "没有可用的虚拟密钥")
            return False
        
        try:
            print("🔐 步骤3: 测试虚拟密钥认证...")
            
            headers = {
                "Authorization": f"Bearer {self.virtual_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/v1/me",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                username = data.get('username', 'unknown')
                membership = data.get('membership_level', 'unknown')
                details = f"用户: {username}, 会员: {membership}"
                self.log_test("虚拟密钥认证", True, details)
                return True
            else:
                error_detail = "未知错误"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(error_data))
                except:
                    error_detail = response.text
                
                self.log_test("虚拟密钥认证", False, f"状态码: {response.status_code}, 错误: {error_detail}")
                return False
                
        except Exception as e:
            self.log_test("虚拟密钥认证", False, f"异常: {str(e)}")
            return False
    
    def test_models_endpoint(self) -> bool:
        """测试模型列表端点"""
        if not self.virtual_key:
            self.log_test("模型列表端点", False, "没有可用的虚拟密钥")
            return False
        
        try:
            print("🤖 步骤4: 测试模型列表端点...")
            
            headers = {
                "Authorization": f"Bearer {self.virtual_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('data', [])
                model_count = len(models)
                model_names = [model.get('id', 'unknown') for model in models[:3]]
                details = f"可用模型: {model_count}个, 包括: {', '.join(model_names)}"
                self.log_test("模型列表端点", True, details)
                return True
            else:
                self.log_test("模型列表端点", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("模型列表端点", False, f"异常: {str(e)}")
            return False
    
    def test_usage_stats_endpoint(self) -> bool:
        """测试使用统计端点"""
        if not self.virtual_key:
            self.log_test("使用统计端点", False, "没有可用的虚拟密钥")
            return False
        
        try:
            print("📊 步骤5: 测试使用统计端点...")
            
            headers = {
                "Authorization": f"Bearer {self.virtual_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/v1/usage",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total_requests = data.get('total_requests', 0)
                today_requests = data.get('today_usage', {}).get('requests', 0)
                details = f"总请求: {total_requests}, 今日: {today_requests}"
                self.log_test("使用统计端点", True, details)
                return True
            else:
                self.log_test("使用统计端点", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("使用统计端点", False, f"异常: {str(e)}")
            return False
    
    def test_messages_endpoint_validation(self) -> bool:
        """测试消息端点的验证逻辑（不实际发送给Claude）"""
        if not self.virtual_key:
            self.log_test("消息端点验证", False, "没有可用的虚拟密钥")
            return False
        
        try:
            print("💬 步骤6: 测试消息端点验证逻辑...")
            
            headers = {
                "Authorization": f"Bearer {self.virtual_key}",
                "Content-Type": "application/json"
            }
            
            # 测试空消息（应该失败）
            invalid_payload = {
                "messages": [],
                "max_tokens": 100
            }
            
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=invalid_payload,
                timeout=10
            )
            
            if response.status_code == 400:
                # 这是期望的结果：空消息应该被拒绝
                error_data = response.json()
                error_type = error_data.get('detail', {}).get('type', 'unknown')
                if error_type == 'invalid_request_error':
                    self.log_test("消息端点验证", True, "正确拒绝空消息请求")
                    return True
            
            self.log_test("消息端点验证", False, f"验证逻辑异常，状态码: {response.status_code}")
            return False
                
        except Exception as e:
            self.log_test("消息端点验证", False, f"异常: {str(e)}")
            return False
    
    def print_summary(self):
        """打印测试总结"""
        print("=" * 60)
        print("🔍 Trademe Claude代理系统集成测试结果")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        success_rate = (passed / total) * 100 if total > 0 else 0
        
        print(f"📊 总体结果: {passed}/{total} 通过 ({success_rate:.1f}%)")
        print()
        
        if passed == total:
            print("🎉 所有测试通过！Claude代理系统集成成功。")
            print()
            print("✅ 系统组件状态:")
            print("   - 虚拟密钥认证系统: 正常")
            print("   - Claude API兼容端点: 正常") 
            print("   - 请求验证和路由: 正常")
            print("   - 使用统计跟踪: 正常")
            print()
            print("🚀 下一步:")
            print("   1. 配置有效的Claude账号(OAuth或API密钥)")
            print("   2. 测试实际的AI对话功能")
            print("   3. 集成前端AI对话界面")
        else:
            print("⚠️  部分测试失败，需要检查以下组件:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   - {result['test_name']}: {result['details']}")
        
        print()
        print("🔗 API端点可用:")
        print(f"   - 健康检查: {self.base_url}/health")
        print(f"   - Claude消息: {self.base_url}/v1/messages")
        print(f"   - 用户信息: {self.base_url}/v1/me") 
        print(f"   - 模型列表: {self.base_url}/v1/models")
        print(f"   - 使用统计: {self.base_url}/v1/usage")
        print("=" * 60)

def main():
    """主测试函数"""
    print("🚀 启动 Trademe Claude代理系统集成测试")
    print("=" * 60)
    
    tester = ClaudeProxyIntegrationTest()
    
    # 按顺序执行测试步骤
    tests_to_run = [
        tester.get_virtual_key,
        tester.test_health_endpoint,
        tester.test_virtual_key_auth,
        tester.test_models_endpoint,
        tester.test_usage_stats_endpoint,
        tester.test_messages_endpoint_validation,
    ]
    
    for test_func in tests_to_run:
        try:
            result = test_func()
            if not result:
                print(f"⚠️  测试 {test_func.__name__} 失败，继续执行其他测试...")
            time.sleep(0.5)  # 短暂延迟以避免过快请求
        except KeyboardInterrupt:
            print("\n⏹️  测试被用户中断")
            break
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 出现异常: {e}")
    
    # 打印测试总结
    tester.print_summary()

if __name__ == "__main__":
    main()