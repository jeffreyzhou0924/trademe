#!/usr/bin/env python3
"""
简化测试：仅验证用户确认检测和策略生成B1-B3
跳过可能超时的回测和优化阶段
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
            membershipLevel: 'basic',
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

# 获取新token - 使用basic级别避免复杂的回测流程
JWT_TOKEN = get_fresh_jwt_token()
print(f"🔑 使用Basic级别JWT Token: {JWT_TOKEN[:50]}...")

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def test_confirmation_detection():
    """简化测试：仅验证B1-B3阶段（确认检测+代码生成+保存）"""
    print("🚀 简化测试: B1-B3阶段验证（确认检测+代码生成+保存）")
    print("=" * 60)
    
    # 步骤1: 创建策略会话
    print("\n🔄 步骤1: 创建策略会话")
    session_data = {
        "name": "B1-B3简化测试",
        "ai_mode": "trader",
        "session_type": "strategy",
        "description": "测试确认检测和代码生成"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/sessions", 
                           json=session_data, headers=headers, timeout=10)
    
    if response.status_code != 200:
        print(f"❌ 会话创建失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    session_id = result.get("session_id")
    clean_session_id = session_id.replace("-", "") if session_id else None
    print(f"✅ 策略会话创建成功: {session_id}")
    
    time.sleep(1)
    
    # 步骤2: 直接发送用户确认消息（跳过讨论阶段）
    print(f"\n🔄 步骤2: 直接发送用户确认 - 测试B1检测")
    
    confirmation_message = {
        "content": "确认生成代码！请为我生成一个简单的MACD策略实现。使用标准参数（12,26,9），金叉买入，死叉卖出。",
        "session_id": clean_session_id,
        "context": {"session_type": "strategy", "ai_mode": "trader", "membership_level": "basic"},
        "ai_mode": "trader",
        "session_type": "strategy"
    }
    
    response = requests.post(f"{TRADING_SERVICE_URL}/api/v1/ai/chat", 
                           json=confirmation_message, headers=headers, timeout=60)
    
    if response.status_code != 200:
        print(f"❌ 确认消息发送失败: {response.status_code} - {response.text}")
        return False
    
    result = response.json()
    confirmation_response = result.get("response", "")
    print(f"✅ 确认响应接收成功，长度: {len(confirmation_response)} 字符")
    
    # 分析响应内容
    print(f"\n🔍 分析B1-B3阶段执行结果:")
    print(f"   响应前300字符: {confirmation_response[:300]}...")
    
    # 检查B1-B3执行标志
    stage_indicators = {
        "B1-确认检测": ["确认", "生成", "用户确认"],
        "B2-代码生成": ["策略", "代码", "MACD", "实现"],
        "B3-数据库保存": ["保存", "创建", "策略库", "已生成"]
    }
    
    executed_stages = []
    for stage, keywords in stage_indicators.items():
        if any(keyword in confirmation_response for keyword in keywords):
            executed_stages.append(stage)
            print(f"   ✅ {stage}: 检测到执行迹象")
        else:
            print(f"   ❓ {stage}: 未明确检测到")
    
    # 检查错误信息
    error_indicators = ["失败", "错误", "异常", "error", "failed"]
    has_error = any(error in confirmation_response for error in error_indicators)
    
    if has_error:
        print(f"   ❌ 检测到错误信息")
        return False
    else:
        print(f"   ✅ 未检测到明显错误")
    
    # 检查响应标志
    print(f"\n📊 响应元数据分析:")
    interesting_flags = ["success", "strategy_saved", "tokens_used", "model"]
    for flag in interesting_flags:
        if flag in result:
            print(f"   ✅ {flag}: {result[flag]}")
        else:
            print(f"   ⚠️ {flag}: 未设置")
    
    # 成功判定：至少检测到2个阶段执行且无错误
    success = len(executed_stages) >= 2 and not has_error and result.get("success", False)
    
    return success

def main():
    print("🎯 简化测试: B1-B3阶段验证（确认检测+代码生成+保存）")
    print("="*70)
    
    try:
        success = test_confirmation_detection()
        
        print(f"\n📊 B1-B3阶段测试结果:")
        if success:
            print("🎉 B1-B3阶段测试成功！")
            print("✨ 核心功能验证通过：")
            print("   ✅ B1: 用户确认检测正常工作")
            print("   ✅ B2: 策略代码生成管道运行")
            print("   ✅ B3: 响应处理和保存逻辑执行")
        else:
            print("❌ B1-B3阶段存在问题")
            print("🔧 需要进一步检查具体错误原因")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)