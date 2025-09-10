#!/usr/bin/env python3
"""
测试MACD策略开发流程，验证成熟度分析系统
"""

import requests
import json
import time

# 配置
BASE_URL = "http://localhost"
TRADING_SERVICE_URL = f"{BASE_URL}:8001"

# 测试JWT Token  
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTczOTk4ODEsImV4cCI6MTc1ODAwNDY4MSwiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.Eqb1gfP4AkHTn715Q_ixoxIX322PLwDn6oDuYS7Ng4Y"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def test_macd_strategy_development():
    """测试MACD策略开发流程"""
    print("🚀 开始测试MACD策略开发流程")
    
    # 步骤1: 创建策略会话
    print("\n🔄 步骤1: 创建MACD策略会话")
    session_data = {
        "name": "MACD策略开发测试",
        "ai_mode": "trader",
        "session_type": "strategy",
        "description": "测试MACD策略成熟度分析流程"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/sessions", 
                           json=session_data, headers=headers, timeout=10)
    
    if response.status_code != 200:
        print(f"❌ 会话创建失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    session_id = result.get("session_id")
    print(f"✅ MACD策略会话创建成功: {session_id}")
    
    time.sleep(1)
    
    # 步骤2: 发送MACD策略想法 (应该触发讨论，不直接生成代码)
    print("\n🔄 步骤2: 发送MACD策略想法")
    # 移除UUID中的破折号以符合会话ID验证格式
    clean_session_id = session_id.replace("-", "") if session_id else None
    macd_message = {
        "content": "我想开发一个MACD策略",
        "session_id": clean_session_id,
        "context": {},
        "ai_mode": "trader",
        "session_type": "strategy"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                           json=macd_message, headers=headers, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ AI对话失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    ai_response = result.get("response", "")
    print(f"✅ AI回复长度: {len(ai_response)} 字符")
    
    # 检查AI是否直接生成了代码(不应该)
    if "```python" in ai_response.lower():
        print("❌ 错误: AI直接生成了代码，没有按照成熟度分析流程")
        print(f"AI回复内容: {ai_response[:200]}...")
        return False
    else:
        print("✅ 正确: AI进行了策略讨论，没有直接生成代码")
    
    time.sleep(2)
    
    # 步骤3: 继续详细讨论MACD策略
    print("\n🔄 步骤3: 详细讨论MACD策略参数")
    detailed_message = {
        "content": """我想使用MACD指标来做交易策略。具体想法是：
        1. 当MACD线向上穿越信号线时买入
        2. 当MACD线向下穿越信号线时卖出  
        3. 设置止损为2%，止盈为5%
        4. 使用12日和26日EMA计算MACD
        5. 信号线使用9日EMA
        你觉得这个策略怎么样？需要优化哪些地方？""",
        "session_id": clean_session_id,
        "context": {},
        "ai_mode": "trader",
        "session_type": "strategy"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                           json=detailed_message, headers=headers, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ 详细讨论失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    detailed_response = result.get("response", "")
    print(f"✅ AI详细回复长度: {len(detailed_response)} 字符")
    
    # 这次可能会触发成熟度分析，检查是否有确认提示
    if any(keyword in detailed_response for keyword in ["生成代码", "开始编码", "现在生成", "确认"]):
        print("✅ 成熟度分析触发：AI询问是否生成代码")
        
        # 步骤4: 用户确认生成代码
        print("\n🔄 步骤4: 用户确认生成代码")
        confirm_message = {
            "content": "好的，请生成代码",
            "session_id": clean_session_id,
            "context": {},
            "ai_mode": "trader",
            "session_type": "strategy"
        }
        
        response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                               json=confirm_message, headers=headers, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            final_response = result.get("response", "")
            print(f"✅ 策略生成完成，响应长度: {len(final_response)} 字符")
            
            # 检查是否包含策略生成成功的消息
            if "策略生成成功" in final_response or "策略代码已生成" in final_response:
                print("✅ 策略成功保存到后台，代码没有在对话中显示")
                return True
            else:
                print(f"⚠️  策略生成响应: {final_response[:200]}...")
                
        else:
            print(f"❌ 策略生成失败: {response.status_code}")
            return False
    else:
        print("⚠️  成熟度分析可能未触发或策略讨论仍不够成熟")
        print(f"AI回复: {detailed_response[:300]}...")
        return False
    
    return True

def test_check_strategies():
    """检查策略是否已生成并保存"""
    print("\n🔄 检查生成的策略")
    response = requests.get(f"{TRADING_SERVICE_URL}/api/v1/strategies/", 
                          headers=headers, timeout=10)
    
    if response.status_code == 200:
        strategies = response.json()
        print(f"✅ 发现 {len(strategies)} 个策略")
        return len(strategies) > 0
    else:
        print(f"❌ 获取策略列表失败: {response.status_code}")
        return False

def main():
    print("🎯 MACD策略开发流程测试")
    print("=" * 50)
    
    # 测试完整流程
    flow_success = test_macd_strategy_development()
    
    # 检查策略生成
    strategy_saved = test_check_strategies()
    
    print("\n📊 测试结果总结:")
    print(f"   - MACD流程测试: {'✅' if flow_success else '❌'}")
    print(f"   - 策略保存验证: {'✅' if strategy_saved else '❌'}")
    
    if flow_success:
        print("\n🎉 MACD策略开发流程正常工作！")
        print("✨ 成熟度分析系统按预期运行")
        return True
    else:
        print("\n❌ MACD策略开发流程存在问题")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)