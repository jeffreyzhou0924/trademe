#!/usr/bin/env python3
"""
测试Claude API连接
"""
import os
import sys
import asyncio
import aiohttp
from datetime import datetime

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.ai.core.claude_client import ClaudeClient
from app.security.crypto_manager import CryptoManager
from app.database import get_session
from app.models.claude_conversation import ClaudeAccount
from sqlalchemy import select

async def test_claude_connection():
    """测试Claude连接"""
    print("🔧 开始测试Claude API连接...")
    
    try:
        # 获取数据库会话
        async with get_session() as db:
            # 获取Claude账号
            result = await db.execute(select(ClaudeAccount).where(ClaudeAccount.status == 'active'))
            account = result.scalar_first()
            
            if not account:
                print("❌ 未找到活跃的Claude账号")
                return False
            
            print(f"📋 使用账号: {account.account_name}")
            print(f"📋 代理类型: {account.proxy_type}")
            print(f"📋 代理URL: {account.proxy_base_url}")
            
            # 解密API密钥
            crypto_manager = CryptoManager()
            api_key = crypto_manager.decrypt(account.api_key)
            print(f"📋 API密钥状态: {'有效' if api_key else '无效'}")
            
            # 测试代理连接
            if account.proxy_base_url:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(f"{account.proxy_base_url}/v1/models") as response:
                            print(f"📋 代理连接状态: {response.status}")
                            if response.status != 401:  # 401是预期的，因为没有API密钥
                                print("❌ 代理服务响应异常")
                                return False
                except Exception as e:
                    print(f"❌ 代理连接失败: {e}")
                    return False
            
            # 初始化Claude客户端
            claude_client = ClaudeClient()
            print(f"📋 Claude客户端状态: {'初始化成功' if claude_client else '初始化失败'}")
            
            # 测试简单对话
            print("🧪 测试简单对话...")
            try:
                response = await claude_client.chat_completion(
                    messages=[{"role": "user", "content": "简单回复一个词：测试"}],
                    timeout=15
                )
                
                if response and response.get('content'):
                    print(f"✅ 对话测试成功: {response['content'][:50]}...")
                    return True
                else:
                    print("❌ 对话测试失败: 没有返回内容")
                    return False
                    
            except Exception as e:
                print(f"❌ 对话测试异常: {e}")
                return False
                
    except Exception as e:
        print(f"❌ 测试过程异常: {e}")
        return False

if __name__ == "__main__":
    print(f"🕐 开始时间: {datetime.now()}")
    success = asyncio.run(test_claude_connection())
    print(f"🕐 结束时间: {datetime.now()}")
    print(f"🎯 测试结果: {'成功' if success else '失败'}")
    sys.exit(0 if success else 1)
