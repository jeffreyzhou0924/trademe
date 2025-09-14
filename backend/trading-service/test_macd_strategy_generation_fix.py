#!/usr/bin/env python3
"""
MACD策略生成修复验证脚本

测试用户发送"确认生成代码"后的完整流程：
1. 策略生成
2. 数据库保存
3. 前端API可查询
"""

import asyncio
import aiohttp
import json
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置测试用户信息
TEST_USER_EMAIL = "publictest@example.com"
TEST_USER_PASSWORD = "PublicTest123!"

# API基础URL
BASE_URL = "http://localhost:8001"

class MACDStrategyGenerationTester:
    def __init__(self):
        self.session = None
        self.access_token = None
        self.user_id = None
        self.session_id = None
        
    async def setup_session(self):
        """设置HTTP会话"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """清理HTTP会话"""
        if self.session:
            await self.session.close()
    
    async def login(self):
        """用户登录获取token"""
        try:
            login_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
            
            # 调用用户服务登录（用户服务在3001端口）
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:3001/api/v1/auth/login", 
                    json=login_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data["access_token"]
                        self.user_id = data["user"]["id"]
                        print(f"✅ 用户登录成功: {TEST_USER_EMAIL} (用户ID: {self.user_id})")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ 用户登录失败: {response.status}, {error_text}")
                        return False
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False
    
    async def create_ai_session(self):
        """创建AI会话"""
        try:
            session_data = {
                "name": "MACD策略测试会话",
                "ai_mode": "trader",
                "session_type": "strategy", 
                "description": "测试MACD背离策略生成"
            }
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with self.session.post(
                f"{BASE_URL}/api/v1/ai/sessions", 
                json=session_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    self.session_id = data["session_id"]
                    print(f"✅ AI会话创建成功: {self.session_id}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ AI会话创建失败: {response.status}, {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 创建AI会话异常: {e}")
            return False
    
    async def simulate_strategy_generation(self):
        """模拟策略生成过程"""
        try:
            # 模拟用户输入"确认生成代码"
            message_data = {
                "content": "确认生成代码",
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            print("🚀 发送策略生成确认消息...")
            async with self.session.post(
                f"{BASE_URL}/api/v1/ai/chat", 
                json=message_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ AI回复成功: {data.get('content', '')[:100]}...")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ AI策略生成失败: {response.status}, {error_text}")
                    return False
        except Exception as e:
            print(f"❌ 策略生成异常: {e}")
            return False
    
    async def check_strategy_saved(self):
        """检查策略是否保存到数据库"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # 等待一秒确保数据库写入完成
            await asyncio.sleep(1)
            
            # 检查strategies表
            async with self.session.get(
                f"{BASE_URL}/api/v1/strategies/", 
                headers=headers
            ) as response:
                if response.status == 200:
                    strategies = await response.json()
                    if strategies:
                        print(f"✅ 发现 {len(strategies)} 个策略记录")
                        for strategy in strategies:
                            print(f"   - 策略: {strategy.get('name')} (ID: {strategy.get('id')})")
                        return True, strategies
                    else:
                        print("❌ strategies表中没有找到策略记录")
                        return False, []
                else:
                    error_text = await response.text()
                    print(f"❌ 查询策略失败: {response.status}, {error_text}")
                    return False, []
        except Exception as e:
            print(f"❌ 检查策略保存异常: {e}")
            return False, []
    
    async def test_latest_ai_strategy_api(self):
        """测试前端API能否获取最新策略"""
        if not self.session_id:
            print("❌ 没有会话ID，无法测试API")
            return False
            
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with self.session.get(
                f"{BASE_URL}/api/v1/strategies/latest-ai-strategy/{self.session_id}", 
                headers=headers
            ) as response:
                if response.status == 200:
                    strategy = await response.json()
                    print(f"✅ 前端API可以获取策略: {strategy.get('name')}")
                    print(f"   - 策略ID: {strategy.get('strategy_id')}")
                    print(f"   - 会话ID: {strategy.get('ai_session_id')}")
                    return True, strategy
                elif response.status == 404:
                    print("❌ 前端API找不到策略 (404) - 这就是回测按钮不显示的原因！")
                    return False, None
                else:
                    error_text = await response.text()
                    print(f"❌ 前端API调用失败: {response.status}, {error_text}")
                    return False, None
        except Exception as e:
            print(f"❌ 测试前端API异常: {e}")
            return False, None
    
    async def run_complete_test(self):
        """运行完整测试流程"""
        print("=" * 60)
        print("🧪 MACD策略生成修复验证测试")
        print("=" * 60)
        
        await self.setup_session()
        
        try:
            # 1. 用户登录
            if not await self.login():
                return False
            
            # 2. 创建AI会话
            if not await self.create_ai_session():
                return False
            
            # 3. 模拟策略生成
            if not await self.simulate_strategy_generation():
                return False
            
            # 4. 检查策略保存
            saved, strategies = await self.check_strategy_saved()
            
            # 5. 测试前端API
            api_success, strategy = await self.test_latest_ai_strategy_api()
            
            # 结果分析
            print("\n" + "=" * 60)
            print("📊 测试结果分析")
            print("=" * 60)
            
            if saved and api_success:
                print("✅ 修复成功！策略生成完整流程正常：")
                print("   1. ✅ 策略已保存到strategies表")
                print("   2. ✅ 前端API可以获取策略")
                print("   3. ✅ 回测按钮应该正常显示")
                return True
            elif saved and not api_success:
                print("⚠️  部分修复：策略已保存但API有问题")
                return False
            elif not saved:
                print("❌ 修复失败：策略未正确保存到数据库")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """主函数"""
    tester = MACDStrategyGenerationTester()
    success = await tester.run_complete_test()
    
    if success:
        print("\n🎉 修复验证成功！用户现在应该能看到回测按钮了。")
        return 0
    else:
        print("\n❌ 修复验证失败，需要进一步调试。")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)