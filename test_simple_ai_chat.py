#!/usr/bin/env python3
"""
简化的AI对话测试，验证基础功能是否正常
"""

import requests
import json

# 配置
BASE_URL = "http://localhost"
TRADING_SERVICE_URL = f"{BASE_URL}:8001"

# 测试JWT Token
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTczOTkxMTMsImV4cCI6MTc1ODAwMzkxMywiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.Cv-KOso9JFX0fQyIKc6BeYa_6bjqHvl2LoDRlhmjTz0"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def test_create_session():
    """测试创建会话"""
    print("🔄 测试创建AI会话...")
    
    session_data = {
        "name": "简单测试会话",
        "ai_mode": "trader",
        "session_type": "strategy",
        "description": "测试基础功能"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/sessions", 
                           json=session_data, headers=headers, timeout=10)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 会话创建成功: {result.get('session_id')}")
        return result.get('session_id')
    else:
        print(f"❌ 会话创建失败: {response.status_code} - {response.text}")
        return None

def test_chat_without_session():
    """测试不使用会话的AI对话"""
    print("🔄 测试基础AI对话...")
    
    # 最简单的消息格式
    message_data = {
        "content": "你好，我想了解一下量化交易策略。"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                           json=message_data, headers=headers, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ AI对话成功，响应长度: {len(result.get('response', ''))}")
        return True
    else:
        print(f"❌ AI对话失败: {response.status_code} - {response.text}")
        return False

def test_backtest_analysis():
    """测试回测分析功能"""
    print("🔄 测试回测分析...")
    
    # 使用一个通用的回测ID
    backtest_id = 1
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/backtest/analyze?backtest_id={backtest_id}", 
                           headers=headers, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ AI回测分析成功")
        print(f"   - 性能总结长度: {len(result.get('performance_summary', ''))}")
        print(f"   - 优势数量: {len(result.get('strengths', []))}")
        print(f"   - 建议数量: {len(result.get('improvement_suggestions', []))}")
        return result
    else:
        print(f"❌ AI回测分析失败: {response.status_code} - {response.text}")
        return None

def main():
    print("🚀 开始简化AI功能测试")
    
    # 测试1: 创建会话
    session_id = test_create_session()
    
    # 测试2: 基础AI对话
    chat_success = test_chat_without_session()
    
    # 测试3: 回测分析 (核心功能)
    analysis_result = test_backtest_analysis()
    
    print("\n📊 测试结果总结:")
    print(f"   - 会话创建: {'✅' if session_id else '❌'}")
    print(f"   - AI对话: {'✅' if chat_success else '❌'}")
    print(f"   - 回测分析: {'✅' if analysis_result else '❌'}")
    
    if analysis_result:
        print("\n🎉 核心AI分析功能正常工作！")
        return True
    else:
        print("\n❌ 部分功能测试失败")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)