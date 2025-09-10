#!/usr/bin/env python3
"""
统一重新加密Claude代理账户密钥
使用提供的正确密钥重新加密所有Claude账号
"""

import sqlite3
import sys
import os
from datetime import datetime

# 添加路径以便导入模块
sys.path.append('/root/trademe/backend/trading-service')

from app.security.crypto_manager import CryptoManager
from app.config import settings

def unified_claude_key_reencryption():
    """统一重新加密Claude代理账户密钥"""
    
    print("🔧 Claude代理账户密钥统一重新加密")
    print("="*50)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 正确的claudecnd7代理账户密钥
    correct_api_key = "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
    print(f"✅ 使用提供的正确密钥: {correct_api_key[:20]}...")
    
    # 检查配置
    print("\n📋 检查系统配置:")
    print(f"   主密钥配置: {'✅' if settings.wallet_master_key else '❌'}")
    print(f"   主密钥长度: {len(settings.wallet_master_key)}")
    
    if not settings.wallet_master_key:
        print("❌ 主密钥未配置，无法继续")
        return False
    
    try:
        # 创建数据库备份
        main_db = "/root/trademe/data/trademe.db"
        backup_db = f"/root/trademe/data/trademe_backup_unified_reencryption_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        print(f"\n💾 创建数据库备份...")
        os.system(f"cp '{main_db}' '{backup_db}'")
        print(f"✅ 备份完成: {backup_db}")
        
        # 初始化加密管理器
        crypto = CryptoManager()
        print("✅ 加密管理器初始化成功")
        
        # 连接数据库
        conn = sqlite3.connect(main_db)
        cursor = conn.cursor()
        
        # 查询所有Claude账号
        print(f"\n🔍 查询现有Claude账号...")
        cursor.execute("SELECT id, account_name, api_key, status FROM claude_accounts")
        accounts = cursor.fetchall()
        
        if not accounts:
            print("❌ 没有找到Claude账号")
            conn.close()
            return False
        
        print(f"✅ 找到 {len(accounts)} 个Claude账号")
        
        # 处理每个账号
        updated_accounts = 0
        for account_id, account_name, current_api_key, status in accounts:
            print(f"\n🔄 处理账号: {account_name} (ID: {account_id})")
            print(f"   当前状态: {status}")
            print(f"   当前密钥长度: {len(current_api_key) if current_api_key else 0}")
            
            # 使用正确的密钥进行重新加密
            print(f"   🔒 使用正确密钥重新加密...")
            try:
                # 使用空上下文进行加密（与之前修复时一致）
                new_encrypted_key = crypto.encrypt_private_key(correct_api_key, "")
                print(f"   ✅ 重新加密成功，新长度: {len(new_encrypted_key)}")
                
                # 立即验证新加密的密钥
                print(f"   🔓 验证新加密密钥...")
                decrypted_key = crypto.decrypt_private_key(new_encrypted_key, "")
                
                if decrypted_key == correct_api_key:
                    print(f"   ✅ 解密验证通过")
                    
                    # 更新数据库
                    cursor.execute(
                        """UPDATE claude_accounts 
                           SET api_key = ?, 
                               updated_at = CURRENT_TIMESTAMP,
                               status = 'active'
                           WHERE id = ?""",
                        (new_encrypted_key, account_id)
                    )
                    print(f"   ✅ 数据库更新完成")
                    updated_accounts += 1
                    
                else:
                    print(f"   ❌ 解密验证失败! 预期: {correct_api_key[:20]}..., 实际: {decrypted_key[:20]}...")
                    return False
                    
            except Exception as e:
                print(f"   ❌ 加密过程出错: {str(e)}")
                return False
        
        # 提交所有更改
        conn.commit()
        print(f"\n💾 数据库更改已提交")
        
        # 最终验证所有账号
        print(f"\n🔍 最终验证所有账号...")
        cursor.execute("SELECT id, account_name, api_key FROM claude_accounts")
        final_accounts = cursor.fetchall()
        
        verification_passed = 0
        for account_id, account_name, encrypted_key in final_accounts:
            print(f"   验证账号: {account_name}...")
            try:
                decrypted = crypto.decrypt_private_key(encrypted_key, "")
                if decrypted == correct_api_key:
                    print(f"   ✅ {account_name} 解密验证通过")
                    verification_passed += 1
                else:
                    print(f"   ❌ {account_name} 解密结果不匹配")
                    return False
            except Exception as e:
                print(f"   ❌ {account_name} 解密失败: {str(e)}")
                return False
        
        conn.close()
        
        # 显示最终结果
        print(f"\n🎉 Claude代理账户密钥统一重新加密完成!")
        print(f"📊 处理结果:")
        print(f"   • 总计账号: {len(accounts)}")
        print(f"   • 成功更新: {updated_accounts}")
        print(f"   • 验证通过: {verification_passed}")
        print(f"   • 数据库备份: {backup_db}")
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n✅ 系统状态:")
        print(f"   • 所有Claude账号现在使用统一的正确密钥")
        print(f"   • 所有账号使用相同的加密参数")
        print(f"   • AI对话功能应该完全恢复正常")
        print(f"   • 账号状态已重置为active")
        
        return True
        
    except Exception as e:
        print(f"❌ 统一重新加密过程中出错: {str(e)}")
        return False

if __name__ == "__main__":
    success = unified_claude_key_reencryption()
    exit(0 if success else 1)