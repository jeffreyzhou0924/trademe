#!/usr/bin/env python3
"""
最终验证Claude加密解密功能
"""

import sqlite3
import sys
import os

# 添加路径以便导入模块
sys.path.append('/root/trademe/backend/trading-service')

from app.security.crypto_manager import CryptoManager
from app.config import settings

def verify_claude_encryption():
    """验证Claude账号加密解密功能"""
    
    print("🔍 最终验证Claude加密解密功能")
    print("="*50)
    
    expected_key = "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
    
    try:
        # 初始化加密管理器
        crypto = CryptoManager()
        print("✅ 加密管理器初始化成功")
        
        # 连接数据库
        db_path = "/root/trademe/data/trademe.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有Claude账号
        cursor.execute("SELECT id, account_name, api_key, status FROM claude_accounts")
        accounts = cursor.fetchall()
        conn.close()
        
        if not accounts:
            print("❌ 没有找到Claude账号")
            return False
        
        print(f"🔍 验证 {len(accounts)} 个Claude账号:")
        
        all_passed = True
        for account_id, account_name, encrypted_key, status in accounts:
            print(f"\n📋 账号: {account_name} (ID: {account_id})")
            print(f"   状态: {status}")
            print(f"   加密密钥长度: {len(encrypted_key)}")
            print(f"   加密密钥前20字符: {encrypted_key[:20]}...")
            
            # 测试解密
            try:
                print("   🔓 执行解密...")
                decrypted_key = crypto.decrypt_private_key(encrypted_key, "")
                print(f"   ✅ 解密成功")
                print(f"   解密结果长度: {len(decrypted_key)}")
                print(f"   解密结果前20字符: {decrypted_key[:20]}...")
                
                # 验证密钥正确性
                if decrypted_key == expected_key:
                    print("   ✅ 密钥验证通过 - 与预期完全匹配")
                else:
                    print("   ❌ 密钥验证失败 - 与预期不符")
                    print(f"      预期: {expected_key}")
                    print(f"      实际: {decrypted_key}")
                    all_passed = False
                
                # 验证密钥格式
                if decrypted_key.startswith('cr_'):
                    print("   ✅ 密钥格式正确 - claudecnd7代理格式")
                else:
                    print("   ❌ 密钥格式错误")
                    all_passed = False
                    
            except Exception as e:
                print(f"   ❌ 解密失败: {str(e)}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ 验证过程出错: {str(e)}")
        return False

def test_encryption_cycle():
    """测试完整的加密解密循环"""
    
    print(f"\n🔄 测试完整加密解密循环")
    print("="*50)
    
    test_key = "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
    
    try:
        crypto = CryptoManager()
        
        print(f"🧪 测试密钥: {test_key[:20]}...")
        
        # 加密
        print("🔒 执行加密...")
        encrypted = crypto.encrypt_private_key(test_key, "")
        print(f"✅ 加密成功，长度: {len(encrypted)}")
        
        # 解密
        print("🔓 执行解密...")
        decrypted = crypto.decrypt_private_key(encrypted, "")
        print(f"✅ 解密成功，长度: {len(decrypted)}")
        
        # 验证
        if decrypted == test_key:
            print("✅ 加密解密循环测试通过")
            return True
        else:
            print("❌ 加密解密循环测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 加密解密循环测试出错: {str(e)}")
        return False

def main():
    """主验证函数"""
    
    print("🚀 Claude加密解密功能最终验证")
    print("="*60)
    
    # 测试1: 验证数据库中的加密数据
    db_test = verify_claude_encryption()
    
    # 测试2: 测试加密解密循环
    cycle_test = test_encryption_cycle()
    
    print(f"\n📊 验证结果总结:")
    print(f"   数据库解密验证: {'✅' if db_test else '❌'}")
    print(f"   加密解密循环测试: {'✅' if cycle_test else '❌'}")
    
    if db_test and cycle_test:
        print(f"\n🎉 Claude加密解密功能完全正常!")
        print(f"✅ 所有Claude账号密钥已统一重新加密")
        print(f"✅ 加密解密系统工作正常")
        print(f"✅ AI对话功能应该完全恢复")
        return True
    else:
        print(f"\n❌ Claude加密解密功能仍存在问题")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)