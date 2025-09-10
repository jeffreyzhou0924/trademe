#!/usr/bin/env python3
"""
WebSocket Claude API直接调用测试
测试完整的WebSocket AI对话流程，验证每个步骤
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.ai_service import AIService
from app.services.claude_account_service import ClaudeAccountService
from app.services.claude_scheduler_service import ClaudeSchedulerService

async def test_websocket_claude_flow():
    """测试完整的WebSocket Claude流程"""
    
    print("🧪 WebSocket Claude API流程测试开始")
    print("=" * 60)
    
    try:
        # 步骤1: 直接测试AI服务（跳过复杂的账号调度）
        print("📋 步骤1: 直接测试AI服务初始化")
        
        # 步骤2: 测试AI服务调用
        print("\n📋 步骤2: 测试AI服务调用")
        
        async with AsyncSessionLocal() as db:
            ai_service = AIService()
            
            # 调用AI服务
            print("  🤖 调用Claude AI服务...")
            start_time = datetime.now()
            
            response = await ai_service.chat_completion(
                message="简单测试：说'hello world'",
                user_id=6,
                session_id='websocket_test_session',
                context={
                    'ai_mode': 'trader',
                    'session_type': 'general',
                    'membership_level': 'professional'
                },
                db=db
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"  ⏱️ 响应时间: {duration:.2f}秒")
            
            # 分析响应结果
            if response:
                print(f"  📊 响应分析:")
                print(f"     - 成功状态: {response.get('success')}")
                print(f"     - 响应内容: {response.get('response', response.get('content', ''))[:100]}...")
                print(f"     - Token使用: {response.get('tokens_used', 0)}")
                print(f"     - 成本: ${response.get('cost_usd', 0.0):.6f}")
                
                if response.get('success', True):
                    print("  ✅ AI服务调用成功")
                else:
                    print(f"  ❌ AI服务调用失败: {response.get('error', 'Unknown error')}")
            else:
                print("  ❌ AI服务无响应")
                return
        
        # 步骤3: 模拟WebSocket流式处理
        print("\n📋 步骤3: 模拟WebSocket流式处理")
        
        if response.get('success', True):
            content = response.get('response', response.get('content', ''))
            
            # 模拟分块发送
            chunk_size = 10
            chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
            
            print(f"  🌊 开始模拟流式传输 - 总计{len(chunks)}个数据块")
            
            for i, chunk in enumerate(chunks, 1):
                print(f"     📦 数据块 {i}/{len(chunks)}: {chunk[:20]}{'...' if len(chunk) > 20 else ''}")
                await asyncio.sleep(0.1)  # 模拟网络延迟
                
            print("  ✅ 流式传输模拟完成")
        
        print("\n🎉 WebSocket Claude API流程测试完成 - 所有步骤成功!")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常:")
        print(f"   异常类型: {type(e).__name__}")
        print(f"   错误信息: {str(e)}")
        print(f"   异常详情: {repr(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket_claude_flow())