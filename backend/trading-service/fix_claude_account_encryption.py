#!/usr/bin/env python3
"""
Claude账号加密状态修复脚本
用于检查和修复Claude账号API密钥的加密存储问题
"""

import asyncio
import sqlite3
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from app.security.crypto_manager import CryptoManager
from app.database import AsyncSessionLocal
from app.models.claude_proxy import ClaudeAccount
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_claude_account_encryption():
    """检查Claude账号表的加密状态"""
    try:
        logger.info("=== 检查Claude账号加密状态 ===")
        
        # 初始化加密管理器
        crypto_manager = CryptoManager()
        logger.info(f"加密管理器配置: {crypto_manager.get_encryption_info()}")
        
        async with AsyncSessionLocal() as session:
            # 查询所有Claude账号
            result = await session.execute(select(ClaudeAccount))
            accounts = result.scalars().all()
            
            logger.info(f"找到 {len(accounts)} 个Claude账号")
            
            for account in accounts:
                logger.info(f"\n账号 {account.id}: {account.account_name}")
                logger.info(f"  API密钥长度: {len(account.api_key)}")
                logger.info(f"  API密钥前缀: {account.api_key[:20]}...")
                
                # 尝试判断是否已加密
                is_encrypted = len(account.api_key) > 100  # 加密后的长度通常远大于原始长度
                logger.info(f"  估计是否加密: {is_encrypted}")
                
                if is_encrypted:
                    # 尝试解密
                    try:
                        decrypted_key = crypto_manager.decrypt_private_key(
                            account.api_key, 
                            account.account_name
                        )
                        logger.info(f"  ✅ 解密成功: {decrypted_key[:20]}...")
                    except Exception as e:
                        logger.error(f"  ❌ 解密失败: {e}")
                else:
                    # 明文API密钥，需要加密
                    logger.warning(f"  ⚠️  发现明文API密钥，建议加密")
                    
    except Exception as e:
        logger.error(f"检查失败: {e}")
        return False
    
    return True


async def encrypt_plaintext_api_keys():
    """加密明文存储的API密钥"""
    try:
        logger.info("\n=== 开始加密明文API密钥 ===")
        
        crypto_manager = CryptoManager()
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ClaudeAccount))
            accounts = result.scalars().all()
            
            updated_count = 0
            
            for account in accounts:
                # 判断是否为明文密钥（长度较短且以cr_开头）
                if len(account.api_key) < 100 and account.api_key.startswith('cr_'):
                    logger.info(f"正在加密账号 {account.id}: {account.account_name}")
                    
                    try:
                        # 加密API密钥
                        encrypted_key = crypto_manager.encrypt_private_key(
                            account.api_key, 
                            account.account_name
                        )
                        
                        # 更新数据库
                        await session.execute(
                            update(ClaudeAccount)
                            .where(ClaudeAccount.id == account.id)
                            .values(api_key=encrypted_key)
                        )
                        
                        logger.info(f"  ✅ 加密完成，新长度: {len(encrypted_key)}")
                        updated_count += 1
                        
                    except Exception as e:
                        logger.error(f"  ❌ 加密失败: {e}")
                        continue
                else:
                    logger.info(f"账号 {account.id} 已加密，跳过")
            
            if updated_count > 0:
                await session.commit()
                logger.info(f"\n✅ 成功加密 {updated_count} 个账号")
            else:
                logger.info(f"\n📋 无需加密的账号")
                
    except Exception as e:
        logger.error(f"加密处理失败: {e}")
        return False
    
    return True


async def create_backup():
    """创建数据库备份"""
    try:
        import shutil
        from datetime import datetime
        
        source_db = "/root/trademe/data/trademe.db"
        backup_db = f"/root/trademe/data/trademe_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        shutil.copy2(source_db, backup_db)
        logger.info(f"✅ 数据库备份完成: {backup_db}")
        return backup_db
        
    except Exception as e:
        logger.error(f"❌ 备份失败: {e}")
        return None


async def main():
    """主函数"""
    logger.info("🔧 Claude账号加密修复脚本启动")
    
    # 1. 创建备份
    backup_path = await create_backup()
    if not backup_path:
        logger.error("❌ 备份失败，终止操作")
        return
    
    # 2. 检查当前状态
    logger.info("\n📋 第一步：检查当前加密状态")
    check_success = await check_claude_account_encryption()
    if not check_success:
        logger.error("❌ 检查失败，终止操作")
        return
    
    # 3. 询问是否执行加密
    try:
        user_input = input("\n是否要加密明文API密钥？[y/N]: ").strip().lower()
        if user_input in ['y', 'yes']:
            logger.info("\n🔐 第二步：加密明文API密钥")
            encrypt_success = await encrypt_plaintext_api_keys()
            
            if encrypt_success:
                logger.info("\n✅ 加密操作完成")
                
                # 4. 再次检查验证
                logger.info("\n🔍 第三步：验证加密结果")
                await check_claude_account_encryption()
                
            else:
                logger.error("\n❌ 加密操作失败")
        else:
            logger.info("\n📋 用户取消加密操作")
            
    except KeyboardInterrupt:
        logger.info("\n📋 操作被用户中断")
    
    logger.info("\n🏁 脚本执行完成")


if __name__ == "__main__":
    asyncio.run(main())