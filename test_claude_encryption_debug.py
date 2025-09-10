#!/usr/bin/env python3
"""
测试Claude账号加密解密功能
"""

import sys
import os
import asyncio
sys.path.append('/root/trademe/backend/trading-service')

from app.services.claude_account_service import ClaudeAccountService
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

async def test_claude_account_encryption():
    """测试Claude账号加密解密"""
    
    print("🔧 测试Claude账号加密解密功能")
    print("="*50)
    
    # 获取数据库连接
    async for db in get_db():
        try:
            # 创建服务实例
            service = ClaudeAccountService()
            
            print("🔍 检查现有Claude账号...")
            accounts = await service.list_accounts()
            
            if not accounts:
                print("❌ 没有找到Claude账号")
                return False
            
            account = accounts[0]
            print(f"✅ 找到账号: {account.account_name} (ID: {account.id})")
            print(f"   API密钥长度: {len(account.api_key) if account.api_key else 0}")
            print(f"   API密钥前10字符: {account.api_key[:10] if account.api_key else 'None'}...")
            
            print("\n🔓 尝试解密API密钥...")
            try:
                decrypted_key = await service.get_decrypted_api_key(account.id)
                if decrypted_key:
                    print(f"✅ 解密成功!")
                    print(f"   解密后密钥前10字符: {decrypted_key[:10]}...")
                    print(f"   密钥格式正确: {'✅' if decrypted_key.startswith(('sk-', 'cr_')) else '❌'}")
                    return True
                else:
                    print("❌ 解密失败: 返回空值")
                    return False
            except Exception as e:
                print(f"❌ 解密失败: {str(e)}")
                return False
                
        except Exception as e:
            print(f"❌ 测试过程中出错: {str(e)}")
            return False
        finally:
            await db.close()
            break
    
    return False

async def test_encryption_decryption_cycle():
    """测试完整的加密解密周期"""
    
    print("\n🔄 测试完整加密解密周期")
    print("="*50)
    
    # 获取数据库连接
    async for db in get_db():
        try:
            service = ClaudeAccountService()
            
            # 测试数据
            test_key = "cr_test1234567890abcdef"
            print(f"🧪 测试密钥: {test_key}")
            
            print("\n🔒 加密测试密钥...")
            encrypted = service._encrypt_sensitive_data(test_key, "test_context")
            print(f"✅ 加密成功, 长度: {len(encrypted)}")
            print(f"   加密后前20字符: {encrypted[:20]}...")
            
            print("\n🔓 解密测试密钥...")
            decrypted = service._decrypt_sensitive_data(encrypted, "test_context")
            print(f"✅ 解密成功: {decrypted}")
            
            if decrypted == test_key:
                print("✅ 加密解密循环测试通过!")
                return True
            else:
                print("❌ 加密解密循环测试失败!")
                return False
                
        except Exception as e:
            print(f"❌ 加密解密循环测试出错: {str(e)}")
            return False
        finally:
            await db.close()
            break
    
    return False

async def main():
    """主测试函数"""
    
    print("🚀 开始Claude账号加密解密调试")
    print("="*60)
    
    # 测试1: 检查现有账号解密
    existing_test = await test_claude_account_encryption()
    
    # 测试2: 测试加密解密循环
    cycle_test = await test_encryption_decryption_cycle()
    
    print("\n📊 测试结果总结:")
    print(f"   现有账号解密测试: {'✅' if existing_test else '❌'}")
    print(f"   加密解密循环测试: {'✅' if cycle_test else '❌'}")
    
    if existing_test and cycle_test:
        print("\n🎉 Claude账号加密解密功能正常!")
        return True
    elif cycle_test and not existing_test:
        print("\n⚠️  加密解密功能正常，但现有账号数据有问题")
        print("💡 建议重新加密现有账号的API密钥")
        return False
    else:
        print("\n❌ Claude账号加密解密功能存在问题")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)