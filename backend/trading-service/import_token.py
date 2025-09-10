#!/usr/bin/env python3
"""
直接导入Setup Token的脚本
用于绕过Cloudflare保护，直接将access_token导入系统
"""

import asyncio
import sys
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.claude_proxy import ClaudeAccount
from app.services.anthropic_oauth_service import anthropic_oauth_service

async def import_token(access_token: str, account_name: str):
    """直接导入access_token到系统"""
    
    # 创建数据库连接
    engine = create_async_engine(
        "sqlite+aiosqlite:////root/trademe/data/trademe.db",
        echo=True
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # 构建token数据
            token_data = {
                'access_token': access_token,
                'refresh_token': '',
                'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),
                'scopes': ['user:inference'],
                'token_type': 'Bearer',
                'manual_import': True
            }
            
            # 创建账户
            account = ClaudeAccount(
                account_name=account_name,
                api_key="",  # Setup Token不使用api_key字段
                proxy_type="setup_token",
                oauth_access_token=access_token,
                oauth_refresh_token="",
                oauth_expires_at=datetime.fromisoformat(token_data['expires_at']),
                oauth_scopes='user:inference',
                oauth_token_type='Bearer',
                daily_limit=50.0,
                current_usage=0,
                status="active",
                priority=50,
                success_rate=100.0,
                total_requests=0,
                failed_requests=0,
                is_schedulable=True,
                account_type="setup_token"
            )
            
            session.add(account)
            await session.commit()
            await session.refresh(account)
            
            print(f"✅ 成功导入账户: {account_name}")
            print(f"   账户ID: {account.id}")
            print(f"   类型: {account.proxy_type}")
            print(f"   状态: {account.status}")
            
            # 测试连接
            test_result = await anthropic_oauth_service.test_account_connection(account)
            if test_result['success']:
                print(f"✅ 连接测试成功: {test_result.get('message', 'Token有效')}")
            else:
                print(f"❌ 连接测试失败: {test_result.get('error', '未知错误')}")
                
        except Exception as e:
            print(f"❌ 导入失败: {e}")
            await session.rollback()
        finally:
            await engine.dispose()

def main():
    if len(sys.argv) != 3:
        print("使用方法:")
        print("  python import_token.py <access_token> <account_name>")
        print("\n示例:")
        print("  python import_token.py 'your_access_token_here' 'MyAccount'")
        print("\n说明:")
        print("  1. 从claude-relay-service或浏览器开发者工具中获取access_token")
        print("  2. 运行此脚本直接导入token，绕过Cloudflare保护")
        sys.exit(1)
    
    access_token = sys.argv[1]
    account_name = sys.argv[2]
    
    asyncio.run(import_token(access_token, account_name))

if __name__ == "__main__":
    main()