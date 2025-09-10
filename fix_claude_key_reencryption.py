#!/usr/bin/env python3
"""
重新加密Claude API密钥
使用当前的加密系统参数重新加密API密钥
"""

import sqlite3
import sys
import os

# 添加路径以便导入模块
sys.path.append('/root/trademe/backend/trading-service')

from app.security.crypto_manager import CryptoManager
from app.config import settings

def fix_claude_api_key_encryption():
    """修复Claude API密钥加密问题"""
    
    print("🔧 Claude API密钥重新加密修复")
    print("="*50)
    
    # 检查配置
    print("📋 检查配置:")
    print(f"   主密钥配置: {'✅' if settings.wallet_master_key else '❌'}")
    print(f"   主密钥长度: {len(settings.wallet_master_key)}")
    
    if not settings.wallet_master_key:
        print("❌ 主密钥未配置，无法继续")
        return False
    
    try:
        # 初始化加密管理器
        crypto = CryptoManager()
        print("✅ 加密管理器初始化成功")
        
        # 从备份获取原始明文API密钥
        backup_db = "/root/trademe/data/trademe_backup_20250909_144415.db"
        print(f"\n📥 从备份获取原始API密钥: {backup_db}")
        
        backup_conn = sqlite3.connect(backup_db)
        backup_cursor = backup_conn.cursor()
        backup_cursor.execute("SELECT id, account_name, api_key FROM claude_accounts")
        backup_accounts = backup_cursor.fetchall()
        backup_conn.close()
        
        if not backup_accounts:
            print("❌ 备份中没有找到Claude账号")
            return False
        
        print(f"✅ 找到 {len(backup_accounts)} 个账号")
        
        # 连接主数据库
        main_db = "/root/trademe/data/trademe.db"
        print(f"\n📝 更新主数据库: {main_db}")
        
        main_conn = sqlite3.connect(main_db)
        main_cursor = main_conn.cursor()
        
        # 处理每个账号
        for account_id, account_name, original_api_key in backup_accounts:
            print(f"\n🔄 处理账号: {account_name} (ID: {account_id})")
            print(f"   原始密钥: {original_api_key[:20]}...")
            
            # 使用当前加密系统重新加密
            print("   🔒 重新加密...")
            new_encrypted_key = crypto.encrypt_private_key(original_api_key, "")
            print(f"   ✅ 重新加密成功，长度: {len(new_encrypted_key)}")
            
            # 验证新加密的密钥可以正确解密
            print("   🔓 验证解密...")
            decrypted_key = crypto.decrypt_private_key(new_encrypted_key, "")
            
            if decrypted_key == original_api_key:
                print("   ✅ 解密验证通过")
                
                # 更新数据库
                main_cursor.execute(
                    "UPDATE claude_accounts SET api_key = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_encrypted_key, account_id)
                )
                print("   ✅ 数据库更新完成")
                
            else:
                print("   ❌ 解密验证失败!")
                return False
        
        # 提交更改
        main_conn.commit()
        main_conn.close()
        print(f"\n✅ 所有账号重新加密完成")
        
        # 最终验证
        print(f"\n🔍 最终验证...")
        main_conn = sqlite3.connect(main_db)
        main_cursor = main_conn.cursor()
        main_cursor.execute("SELECT id, account_name, api_key FROM claude_accounts")
        updated_accounts = main_cursor.fetchall()
        main_conn.close()
        
        for account_id, account_name, encrypted_key in updated_accounts:
            print(f"   测试账号 {account_name}...")
            try:
                decrypted = crypto.decrypt_private_key(encrypted_key, "")
                if decrypted and decrypted.startswith(('sk-', 'cr_')):
                    print(f"   ✅ 账号 {account_name} 解密正常")
                else:
                    print(f"   ❌ 账号 {account_name} 解密结果格式不正确")
                    return False
            except Exception as e:
                print(f"   ❌ 账号 {account_name} 解密失败: {str(e)}")
                return False
        
        print("\n🎉 Claude API密钥重新加密修复完成!")
        print("✅ 所有账号现在使用统一的加密参数")
        print("✅ AI对话功能应该恢复正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 修复过程中出错: {str(e)}")
        return False

if __name__ == "__main__":
    success = fix_claude_api_key_encryption()
    exit(0 if success else 1)