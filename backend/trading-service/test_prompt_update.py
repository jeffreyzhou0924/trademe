#!/usr/bin/env python3
"""
测试AI提示词更新 - 验证不再询问交易标的和时间周期
"""
import asyncio
import aiohttp
import json

# 配置
BASE_URL = "http://localhost:8001"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc2NTA5OTYsImV4cCI6MTc1ODI1NTc5NiwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.gg8WM2teIx6rcBJWJpbX0vgpTwlR_7if5yJUUgcJNf8"

async def test_strategy_discussion():
    """测试策略讨论不再询问交易标的和时间周期"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    # 测试消息
    test_message = {
        "content": "我想开发一个均线交叉策略，可以帮我分析一下吗？",
        "ai_mode": "trader",
        "session_type": "strategy"
    }
    
    print("🧪 测试AI策略讨论 - 验证不询问交易标的...")
    print(f"📨 发送消息: {test_message['content']}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/v1/ai/chat",
                headers=headers,
                json=test_message
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    ai_response = result.get('content', '')
                    
                    print(f"\n🤖 AI回复: {ai_response[:300]}...")
                    
                    # 检查是否询问了交易标的和时间周期
                    forbidden_phrases = [
                        "哪个品种",
                        "交易品种", 
                        "BTC还是ETH",
                        "时间周期",
                        "1分钟",
                        "5分钟",
                        "15分钟",
                        "1小时",
                        "什么时间框架",
                        "使用什么周期"
                    ]
                    
                    found_forbidden = []
                    for phrase in forbidden_phrases:
                        if phrase in ai_response:
                            found_forbidden.append(phrase)
                    
                    print(f"\n📊 分析结果:")
                    if found_forbidden:
                        print(f"❌ 仍然询问了禁止的内容: {found_forbidden}")
                        return False
                    else:
                        print("✅ AI没有询问交易标的和时间周期 - 提示词更新成功！")
                        
                        # 检查是否专注于策略逻辑
                        strategy_focus_keywords = [
                            "均线",
                            "策略",
                            "信号",
                            "逻辑",
                            "参数",
                            "条件"
                        ]
                        
                        focus_count = sum(1 for keyword in strategy_focus_keywords if keyword in ai_response)
                        if focus_count >= 2:
                            print(f"✅ AI正确专注于策略逻辑讨论 (匹配{focus_count}个关键词)")
                        else:
                            print(f"⚠️ AI策略逻辑专注度可能需要提高")
                        
                        return True
                else:
                    error = await response.text()
                    print(f"❌ API请求失败: {error}")
                    return False
                    
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return False

async def test_code_generation_focus():
    """测试代码生成阶段的专注性"""
    
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    # 模拟用户确认生成代码的消息
    test_message = {
        "content": "好的，确认生成代码",
        "ai_mode": "trader", 
        "session_type": "strategy"
    }
    
    print("\n🧪 测试代码生成 - 验证专注于策略逻辑...")
    print(f"📨 发送消息: {test_message['content']}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/v1/ai/chat",
                headers=headers,
                json=test_message
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    ai_response = result.get('content', '')
                    
                    print(f"\n🤖 AI回复: {ai_response[:200]}...")
                    
                    # 检查是否包含系统配置相关内容
                    forbidden_system_content = [
                        "API密钥",
                        "配置API",
                        "连接交易所",
                        "数据库",
                        "部署",
                        "回测框架"
                    ]
                    
                    found_system_config = []
                    for content in forbidden_system_content:
                        if content in ai_response:
                            found_system_config.append(content)
                    
                    print(f"\n📊 代码生成分析:")
                    if found_system_config:
                        print(f"❌ 仍然包含系统配置内容: {found_system_config}")
                    else:
                        print("✅ AI专注于策略代码生成，没有系统配置内容")
                    
                    return len(found_system_config) == 0
                else:
                    print(f"❌ API请求失败: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试AI提示词更新效果...")
    print("=" * 60)
    
    # 测试1: 策略讨论不询问交易标的
    test1_result = await test_strategy_discussion()
    
    # 测试2: 代码生成专注于策略逻辑 
    test2_result = await test_code_generation_focus()
    
    print("=" * 60)
    print("📋 测试总结:")
    print(f"✅ 策略讨论测试: {'通过' if test1_result else '失败'}")
    print(f"✅ 代码生成测试: {'通过' if test2_result else '失败'}")
    
    if test1_result and test2_result:
        print("🎉 提示词更新成功！AI不再询问交易标的和时间周期")
    else:
        print("❌ 提示词更新需要进一步调整")
    
    return test1_result and test2_result

if __name__ == "__main__":
    print("🔧 AI提示词更新效果测试")
    print("📝 验证AI不再询问交易标的和时间周期")
    print("=" * 60)
    
    try:
        result = asyncio.run(main())
        if result:
            print("✅ 全部测试通过！")
        else:
            print("❌ 部分测试失败，需要调整")
    except Exception as e:
        print(f"❌ 测试运行异常: {e}")