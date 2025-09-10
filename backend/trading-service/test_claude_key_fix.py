#!/usr/bin/env python3
"""
Claude密钥修复验证测试脚本
直接测试AI服务调用，验证是否能成功连接到Claude CDN7
"""

import asyncio
import json
from datetime import datetime
import sys
import os

# 添加项目根目录到Python路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.ai_service import AIService
from app.database import AsyncSessionLocal

async def test_claude_key_fix():
    """测试Claude密钥修复"""
    print("🔧 开始Claude密钥修复验证测试")
    print(f"🕐 测试时间: {datetime.now()}")
    print("="*80)
    
    try:
        # 创建数据库会话
        async with AsyncSessionLocal() as db:
            print("📋 测试参数:")
            print("   用户ID: 6")
            print("   消息内容: 'Hello, 这是一个测试消息'")
            print("   会话ID: test_claude_fix_session")
            print("")
            
            # 调用AI服务
            print("🤖 调用AI服务...")
            result = await AIService.chat_completion(
                message="Hello, 这是一个测试消息，请简短回复确认收到",
                user_id=6,
                context={"membership_level": "professional"},
                session_id="test_claude_fix_session",
                db=db
            )
            
            print("📊 AI服务响应结果:")
            print("="*80)
            print(f"成功状态: {result.get('success', False)}")
            print(f"模型: {result.get('model', 'unknown')}")
            print(f"Token使用: {result.get('tokens_used', 0)}")
            print(f"成本: ${result.get('cost_usd', 0.0):.4f}")
            
            if result.get('success'):
                print(f"✅ AI回复内容:")
                print(f"   {result.get('content', '')[:200]}...")
                print("")
                print("🎉 Claude密钥修复成功！AI服务正常工作")
            else:
                print(f"❌ AI调用失败:")
                print(f"   错误: {result.get('error', '未知错误')}")
                print(f"   内容: {result.get('content', '')}")
                print("")
                print("⚠️  Claude密钥修复未完全成功，仍有问题")
                
            print("="*80)
                
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        print("异常详情:")
        print(traceback.format_exc())
        print("="*80)

if __name__ == "__main__":
    asyncio.run(test_claude_key_fix())