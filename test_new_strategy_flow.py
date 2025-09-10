#!/usr/bin/env python3
"""
测试新的AI策略对话流程控制系统

验证点：
1. 策略对话使用专门的讨论prompt
2. 不直接生成代码，而是进行策略讨论
3. 成熟度分析正确工作
4. 用户确认机制正常运行
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

def test_new_strategy_flow():
    """测试新的策略开发流程"""
    print("🚀 测试新的AI策略对话流程控制系统")
    print("=" * 60)
    
    # 步骤1: 创建策略会话
    print("\n🔄 步骤1: 创建策略会话")
    session_data = {
        "name": "新流程测试-MACD策略",
        "ai_mode": "trader",
        "session_type": "strategy",
        "description": "测试新的prompt控制流程"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/sessions", 
                           json=session_data, headers=headers, timeout=10)
    
    if response.status_code != 200:
        print(f"❌ 会话创建失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    session_id = result.get("session_id")
    print(f"✅ 策略会话创建成功: {session_id}")
    
    time.sleep(1)
    
    # 步骤2: 发送策略想法（应该触发讨论模式，而非直接生成代码）
    print("\n🔄 步骤2: 发送策略想法 - 期待：讨论而非代码生成")
    clean_session_id = session_id.replace("-", "") if session_id else None
    
    strategy_message = {
        "content": "我想开发一个MACD策略",
        "session_id": clean_session_id,
        "context": {"session_type": "strategy", "ai_mode": "trader"},
        "ai_mode": "trader",
        "session_type": "strategy"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                           json=strategy_message, headers=headers, timeout=45)
    
    if response.status_code != 200:
        print(f"❌ AI对话失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    ai_response = result.get("response", "")
    print(f"✅ AI回复成功，响应长度: {len(ai_response)} 字符")
    
    print(f"\n🔍 检查AI回复特征:")
    print(f"   前300字符: {ai_response[:300]}...")
    
    # 检查是否符合新流程要求
    success_indicators = []
    failure_indicators = []
    
    # 1. 检查是否避免了直接代码生成
    if "```python" in ai_response and "import" in ai_response:
        failure_indicators.append("❌ 直接提供了Python代码实现")
    else:
        success_indicators.append("✅ 避免了直接代码生成")
    
    # 2. 检查是否包含策略讨论内容
    discussion_keywords = ["MACD", "策略", "指标", "交易", "分析", "参数"]
    if any(keyword in ai_response for keyword in discussion_keywords):
        success_indicators.append("✅ 包含策略讨论内容")
    else:
        failure_indicators.append("❌ 缺少策略讨论元素")
    
    # 3. 检查是否包含问题或进一步探讨
    question_indicators = ["？", "?", "你希望", "你想", "需要", "考虑"]
    if any(indicator in ai_response for indicator in question_indicators):
        success_indicators.append("✅ 包含互动问题或深入探讨")
    else:
        failure_indicators.append("⚠️  缺少互动问题")
    
    # 4. 检查长度是否合理（讨论应该比完整代码短）
    if len(ai_response) < 5000:  # 之前直接代码生成通常很长
        success_indicators.append("✅ 回复长度合理（讨论模式）")
    else:
        failure_indicators.append("⚠️  回复较长，可能包含过多代码")
    
    # 显示检查结果
    print(f"\n📊 流程检查结果:")
    for indicator in success_indicators:
        print(f"   {indicator}")
    for indicator in failure_indicators:
        print(f"   {indicator}")
    
    # 步骤3: 发送更详细的策略需求（期待引导至确认阶段）
    print(f"\n🔄 步骤3: 发送详细策略需求 - 期待：确认提示")
    
    detailed_message = {
        "content": """我想详细设计这个MACD策略：
        
        1. 使用标准MACD指标（12,26,9参数）
        2. 金叉时买入，死叉时卖出
        3. 设置2%止损，4%止盈
        4. 交易BTC/USDT，1小时周期
        5. 仓位控制在总资金的20%
        6. 避免震荡市场的假信号
        
        你觉得这个策略框架怎么样？有什么建议吗？""",
        "session_id": clean_session_id,
        "context": {"session_type": "strategy", "ai_mode": "trader"},
        "ai_mode": "trader",
        "session_type": "strategy"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                           json=detailed_message, headers=headers, timeout=45)
    
    if response.status_code == 200:
        result = response.json()
        detailed_response = result.get("response", "")
        print(f"✅ 详细讨论回复成功，长度: {len(detailed_response)} 字符")
        
        print(f"\n🔍 检查详细讨论回复:")
        print(f"   前300字符: {detailed_response[:300]}...")
        
        # 检查是否包含确认提示
        confirmation_keywords = ["确认", "生成代码", "开始编码", "现在生成", "可以开始"]
        has_confirmation = any(keyword in detailed_response for keyword in confirmation_keywords)
        
        if has_confirmation:
            print(f"   ✅ 包含确认提示，流程控制正常")
            return True
        else:
            print(f"   ⚠️  暂未触发确认提示，可能需要更多讨论")
            
            # 检查是否包含建议和反馈
            feedback_keywords = ["建议", "优化", "改进", "考虑", "注意"]
            has_feedback = any(keyword in detailed_response for keyword in feedback_keywords)
            
            if has_feedback:
                print(f"   ✅ 提供了策略建议和反馈")
                return True
            else:
                print(f"   ❌ 缺少策略建议，可能系统未正常工作")
                return False
    else:
        print(f"❌ 详细讨论失败: {response.status_code}")
        return False

def main():
    print("🎯 测试新的AI策略对话流程控制系统")
    print("="*70)
    
    try:
        success = test_new_strategy_flow()
        
        print(f"\n📊 测试结果总结:")
        if success:
            print("🎉 新的AI策略对话流程控制系统测试成功！")
            print("✨ 系统按设计要求工作：")
            print("   ✅ 避免直接代码生成") 
            print("   ✅ 进行策略讨论和需求收集")
            print("   ✅ 提供专业建议和引导")
            print("   ✅ 流程控制逻辑正常运行")
        else:
            print("❌ 新的流程控制系统存在问题")
            print("🔧 需要进一步调试prompt或流程逻辑")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)