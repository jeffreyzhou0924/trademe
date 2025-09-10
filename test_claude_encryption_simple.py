#!/usr/bin/env python3
"""
简单测试Claude账号加密解密功能
"""

import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

from app.security.crypto_manager import CryptoManager
from app.config import settings
import base64

def test_crypto_manager_direct():
    """直接测试加密管理器"""
    
    print("🔧 直接测试加密管理器")
    print("="*50)
    
    try:
        # 初始化加密管理器
        crypto = CryptoManager()
        print("✅ 加密管理器初始化成功")
        print(f"   主密钥配置: {'✅' if settings.wallet_master_key else '❌'}")
        print(f"   主密钥长度: {len(settings.wallet_master_key)}")
        
        # 测试加密解密
        test_data = "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
        print(f"\n🧪 测试数据: {test_data[:20]}...")
        
        print("\n🔒 执行加密...")
        encrypted = crypto.encrypt_private_key(test_data, "claude_api_key")
        print(f"✅ 加密成功")
        print(f"   加密后长度: {len(encrypted)}")
        print(f"   加密后前20字符: {encrypted[:20]}...")
        
        print("\n🔓 执行解密...")
        decrypted = crypto.decrypt_private_key(encrypted, "claude_api_key")
        print(f"✅ 解密成功")
        print(f"   解密后: {decrypted[:20]}...")
        
        if decrypted == test_data:
            print("✅ 加密解密循环测试通过!")
            return True
        else:
            print("❌ 加密解密不匹配!")
            return False
            
    except Exception as e:
        print(f"❌ 加密管理器测试失败: {str(e)}")
        return False

def test_existing_encrypted_data():
    """测试现有的加密数据"""
    
    print("\n🔍 测试现有加密数据")
    print("="*50)
    
    try:
        crypto = CryptoManager()
        
        # 从数据库获取实际的加密数据
        import sqlite3
        db_path = "/root/trademe/data/trademe.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, account_name, api_key FROM claude_accounts LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print("❌ 数据库中没有Claude账号数据")
            return False
        
        account_id, account_name, encrypted_key = result
        print(f"✅ 找到账号: {account_name} (ID: {account_id})")
        print(f"   加密数据长度: {len(encrypted_key)}")
        print(f"   加密数据前20字符: {encrypted_key[:20]}...")
        
        print("\n🔓 尝试解密现有数据...")
        
        # 尝试不同的上下文参数
        contexts_to_try = [
            "",  # 空上下文
            "claude_api_key",  # 标准上下文
            "api_key",  # 简化上下文
            "anthropic_api_key"  # anthropic上下文
        ]
        
        for context in contexts_to_try:
            try:
                print(f"   尝试上下文: '{context}'")
                decrypted = crypto.decrypt_private_key(encrypted_key, context)
                print(f"✅ 解密成功 (上下文: '{context}')")
                print(f"   解密结果: {decrypted[:20]}...")
                
                # 验证解密结果是否是有效的API密钥格式
                if decrypted and (decrypted.startswith('sk-') or decrypted.startswith('cr_')):
                    print("✅ 解密的API密钥格式正确!")
                    return True
                else:
                    print("⚠️  解密成功但格式不正确")
                    
            except Exception as e:
                print(f"   ❌ 上下文 '{context}' 解密失败: {str(e)}")
                continue
        
        print("❌ 所有上下文尝试都失败了")
        return False
        
    except Exception as e:
        print(f"❌ 测试现有数据失败: {str(e)}")
        return False

def main():
    """主测试函数"""
    
    print("🚀 开始Claude账号加密解密简单测试")
    print("="*60)
    
    # 测试1: 加密管理器基础功能
    basic_test = test_crypto_manager_direct()
    
    # 测试2: 现有数据解密
    existing_test = test_existing_encrypted_data()
    
    print("\n📊 测试结果总结:")
    print(f"   加密管理器基础测试: {'✅' if basic_test else '❌'}")
    print(f"   现有数据解密测试: {'✅' if existing_test else '❌'}")
    
    if basic_test and existing_test:
        print("\n🎉 Claude账号加密解密功能完全正常!")
        return True
    elif basic_test and not existing_test:
        print("\n⚠️  加密功能正常，但现有数据可能使用了不同的加密参数")
        print("💡 这解释了为什么AI对话会出现'Claude账号配置错误'")
        return False
    else:
        print("\n❌ 加密解密功能存在基础问题")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)