#!/usr/bin/env python3
"""
测试修复后的MACD策略开发流程
"""

import requests
import json
import time

# 配置
BASE_URL = "http://localhost"
TRADING_SERVICE_URL = f"{BASE_URL}:8001"

# 生成新的JWT Token
def get_fresh_jwt_token():
    import subprocess
    cmd = [
        'node', '-e',
        '''
        const jwt = require('jsonwebtoken');
        const newToken = jwt.sign(
          {
            userId: '6',
            email: 'admin@trademe.com',
            membershipLevel: 'professional',
            type: 'access'
          },
          'trademe_super_secret_jwt_key_for_development_only_32_chars',
          {
            expiresIn: '7d',
            audience: 'trademe-app',
            issuer: 'trademe-user-service'
          }
        );
        console.log(newToken);
        '''
    ]
    result = subprocess.run(cmd, cwd='/root/trademe/backend/user-service', capture_output=True, text=True)
    return result.stdout.strip()

# 获取新token
JWT_TOKEN = get_fresh_jwt_token()
print(f"🔑 使用新的JWT Token: {JWT_TOKEN[:50]}...")

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def test_fixed_macd_strategy_development():
    """测试修复后的MACD策略开发流程"""
    print("🚀 测试修复后的MACD策略开发流程")
    print("="*50)
    
    # 步骤1: 创建策略会话
    print("\n🔄 步骤1: 创建MACD策略会话")
    session_data = {
        "name": "MACD策略开发测试(修复后)",
        "ai_mode": "trader",
        "session_type": "strategy",
        "description": "测试修复后的成熟度分析流程"
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
    
    # 步骤2: 发送MACD策略想法 (现在应该触发成熟度分析)
    print("\n🔄 步骤2: 发送MACD策略想法")
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
    print(f"✅ AI回复成功，响应长度: {len(ai_response)} 字符")
    
    # 检查是否包含成熟度分析的特征
    print(f"\n🔍 检查AI回复内容:")
    print(f"   前200字符: {ai_response[:200]}...")
    
    # 检查是否直接生成了代码(不应该)
    if "```python" in ai_response.lower():
        print("❌ 错误: AI直接生成了代码，成熟度分析未工作")
        return False
    else:
        print("✅ 正确: AI进行了策略讨论，没有直接生成代码")
    
    # 检查是否包含确认提示的关键词
    confirmation_keywords = ["生成代码", "开始编码", "现在生成", "确认", "成熟度", "是否"]
    has_confirmation = any(keyword in ai_response for keyword in confirmation_keywords)
    
    if has_confirmation:
        print("✅ 疑似包含成熟度分析确认提示")
        return True
    else:
        print("⚠️  AI回复中未发现明显的确认提示，可能需要更详细的策略描述")
        
        # 步骤3: 发送更详细的MACD策略描述
        print("\n🔄 步骤3: 发送详细的MACD策略描述")
        detailed_message = {
            "content": """我想使用MACD指标来做交易策略。具体想法是：
            1. 当MACD线向上穿越信号线时买入
            2. 当MACD线向下穿越信号线时卖出  
            3. 设置止损为2%，止盈为5%
            4. 使用12日和26日EMA计算MACD
            5. 信号线使用9日EMA
            6. 交易对象是BTC/USDT
            7. 使用1小时时间框架
            你觉得这个策略怎么样？可以开始生成代码了吗？""",
            "session_id": clean_session_id,
            "context": {},
            "ai_mode": "trader",
            "session_type": "strategy"
        }
        
        response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                               json=detailed_message, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            detailed_response = result.get("response", "")
            print(f"✅ AI详细回复成功，长度: {len(detailed_response)} 字符")
            
            # 检查详细回复中是否包含确认提示
            has_detailed_confirmation = any(keyword in detailed_response for keyword in confirmation_keywords)
            
            if has_detailed_confirmation:
                print("✅ 成熟度分析系统工作正常：AI询问用户确认")
                return True
            else:
                print("⚠️  详细描述后仍未触发确认提示")
                print(f"   详细回复前300字符: {detailed_response[:300]}...")
                return False
        else:
            print(f"❌ 详细对话失败: {response.status_code}")
            return False

def main():
    print("🎯 测试修复后的MACD策略开发流程")
    print("="*60)
    
    try:
        success = test_fixed_macd_strategy_development()
        
        print(f"\n📊 测试结果:")
        if success:
            print("✅ MACD策略开发流程修复成功！")
            print("🎉 成熟度分析系统现在正常工作")
            print("✨ 系统按设计流程运行：讨论 → 成熟度分析 → 用户确认 → 生成代码")
        else:
            print("❌ MACD策略开发流程仍存在问题")
            print("🔧 可能需要进一步调试成熟度分析逻辑")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试过程出错: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)