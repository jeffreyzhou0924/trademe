#!/usr/bin/env python3
"""
简化版本：仅分析系统提示差异，不进行网络请求
"""

import sys
import json

# 添加项目根目录到Python路径
sys.path.append('/root/trademe/backend/trading-service')

def analyze_system_prompt_differences():
    """分析系统提示的差异（不进行网络请求）"""
    
    print("🔍 TradeMe AI系统提示差异分析")
    print("=" * 60)
    
    # 直接构建系统提示（模拟 _build_system_prompt 方法）
    base_prompt = "你是Trademe平台的AI交易助手，专门帮助用户进行数字货币交易决策。"
    
    # 普通对话提示（developer模式）
    general_prompt = base_prompt + """
你的角色是量化开发专家，专注于:
- 交易策略代码编写
- 技术指标实现
- 回测系统优化
- 算法交易逻辑
请提供准确的代码和技术方案。
"""
    
    # 策略生成提示
    strategy_prompt = base_prompt + """
请帮助用户创建交易策略，提供完整的Python代码实现，包括策略类定义、方法实现、参数配置和注释。请将Python代码包装在 ```python 代码块中。
"""
    
    # 指标生成提示
    indicator_prompt = base_prompt + """
请帮助用户创建技术指标，提供完整的Python代码实现，包括指标类定义、计算方法、参数配置和注释。请将Python代码包装在 ```python 代码块中。
"""
    
    prompts = {
        "普通对话 (general)": general_prompt,
        "策略生成 (strategy)": strategy_prompt,
        "指标生成 (indicator)": indicator_prompt
    }
    
    print("📊 系统提示长度分析:")
    print(f"{'类型':<20} {'长度(字符)':<12} {'长度(字节)':<12} {'相对大小'}")
    print("-" * 60)
    
    base_length = len(general_prompt)
    
    for prompt_type, prompt_content in prompts.items():
        char_length = len(prompt_content)
        byte_length = len(prompt_content.encode('utf-8'))
        relative_size = f"{char_length/base_length:.2f}x"
        
        print(f"{prompt_type:<20} {char_length:<12} {byte_length:<12} {relative_size}")
    
    print("\n📝 详细系统提示内容:")
    print("-" * 60)
    
    for prompt_type, prompt_content in prompts.items():
        print(f"\n🏷️  {prompt_type}:")
        print(f"内容: {repr(prompt_content)}")
        print(f"实际显示:")
        print(prompt_content)
        print("-" * 40)
    
    # 分析不同用户消息的复杂度
    print("\n💬 用户消息复杂度分析:")
    print("-" * 60)
    
    test_messages = {
        "简单问候": "你好",
        "简单询问": "什么是MACD?", 
        "中等策略请求": "创建一个简单的MACD策略",
        "复杂策略请求": "请帮我创建一个完整的多因子量化交易策略，结合MACD、RSI、布林带指标，包含完整的风险管理、仓位管理、止损止盈逻辑，支持多种交易对，具备回测功能和实盘交易接口"
    }
    
    print(f"{'消息类型':<15} {'长度(字符)':<12} {'长度(字节)':<12} {'复杂度评估'}")
    print("-" * 60)
    
    for msg_type, message in test_messages.items():
        char_length = len(message)
        byte_length = len(message.encode('utf-8'))
        
        # 简单复杂度评估
        if char_length < 10:
            complexity = "简单"
        elif char_length < 50:
            complexity = "中等"
        elif char_length < 200:
            complexity = "复杂"
        else:
            complexity = "非常复杂"
        
        print(f"{msg_type:<15} {char_length:<12} {byte_length:<12} {complexity}")
    
    # 构建完整请求并分析大小
    print("\n📦 完整请求大小分析:")
    print("-" * 60)
    
    test_scenarios = [
        ("简单聊天", general_prompt, "你好"),
        ("中等策略请求", strategy_prompt, "创建一个简单的MACD策略"),
        ("复杂策略请求", strategy_prompt, test_messages["复杂策略请求"])
    ]
    
    print(f"{'场景':<15} {'系统提示':<8} {'用户消息':<8} {'总请求大小':<12} {'估算Token'}")
    print("-" * 60)
    
    for scenario, system_prompt, user_message in test_scenarios:
        # 构建完整请求
        full_request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "system": system_prompt
        }
        
        request_json = json.dumps(full_request, ensure_ascii=False)
        request_size = len(request_json.encode('utf-8'))
        
        # 粗略估算Token数量 (1 token ≈ 3-4字符对于中文)
        total_chars = len(system_prompt) + len(user_message)
        estimated_tokens = total_chars // 3
        
        system_chars = len(system_prompt)
        message_chars = len(user_message)
        
        print(f"{scenario:<15} {system_chars:<8} {message_chars:<8} {request_size:<12} {estimated_tokens}")
    
    print("\n🔍 关键发现:")
    print("1. 策略生成系统提示相对较短，不是导致超时的主要原因")
    print("2. 用户消息复杂度差异巨大，可能是超时的关键因素")
    print("3. 复杂策略请求的总Token数可能触发外部服务的处理限制")
    
    print("\n💡 初步结论:")
    print("- 超时问题可能不是系统提示导致，而是:")
    print("  a) 外部代理服务对复杂请求的处理时间限制")
    print("  b) 策略生成类请求需要AI生成大量代码，输出Token多")
    print("  c) 外部服务的负载均衡和排队机制")
    
    print("\n🎯 建议的解决方案:")
    print("1. 简化初始策略生成请求，分步骤生成")
    print("2. 使用更短的系统提示，减少不必要的指导内容")
    print("3. 实施请求预处理，检测可能超时的复杂请求")
    print("4. 考虑本地策略模板+AI优化的混合方案")
    
    return prompts, test_messages


if __name__ == "__main__":
    analyze_system_prompt_differences()
    print("\n✅ 系统提示分析完成")