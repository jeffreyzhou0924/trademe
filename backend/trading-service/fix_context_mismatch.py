#!/usr/bin/env python3
"""
修复context参数不匹配问题
重新用空字符串context加密API密钥
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from app.security.crypto_manager import CryptoManager
from app.database import AsyncSessionLocal
from app.models.claude_proxy import ClaudeAccount
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_context_mismatch():
    """修复context参数不匹配问题"""
    try:
        logger.info("=== 修复context参数不匹配问题 ===")
        
        # 原始明文API密钥数据
        original_keys = {
            6: "cr_b48f228f987b3d94495498a9260fdb6032ccc4cd3dd49ea380c960ed699bab56",
            7: "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
        }
        
        # 初始化加密管理器
        crypto_manager = CryptoManager()
        logger.info(f"主密钥前缀: {crypto_manager.master_key[:20]}...")
        
        async with AsyncSessionLocal() as session:
            updated_count = 0
            
            for account_id, original_key in original_keys.items():
                logger.info(f"\n正在处理账号 {account_id}")
                logger.info(f"  原始密钥: {original_key[:20]}...")
                
                try:
                    # 使用空字符串context（与get_api_key方法一致）
                    encrypted_key = crypto_manager.encrypt_private_key(original_key, "")
                    
                    logger.info(f"  加密后长度: {len(encrypted_key)}")
                    
                    # 验证加密解密循环（使用空字符串context）
                    decrypted_key = crypto_manager.decrypt_private_key(encrypted_key, "")
                    if decrypted_key == original_key:
                        logger.info(f"  ✅ 空context加密验证成功")
                        
                        # 更新数据库
                        await session.execute(
                            update(ClaudeAccount)
                            .where(ClaudeAccount.id == account_id)
                            .values(api_key=encrypted_key)
                        )
                        
                        updated_count += 1
                        logger.info(f"  ✅ 数据库更新成功")
                        
                    else:
                        logger.error(f"  ❌ 加密验证失败")
                        
                except Exception as e:
                    logger.error(f"  ❌ 处理失败: {e}")
                    continue
            
            if updated_count > 0:
                await session.commit()
                logger.info(f"\n✅ 成功修复 {updated_count} 个账号的context问题")
            else:
                logger.error(f"\n❌ 没有成功修复任何账号")
                
    except Exception as e:
        logger.error(f"修复过程失败: {e}")
        return False
    
    return True


async def test_get_api_key():
    """测试get_api_key方法"""
    try:
        logger.info("\n=== 测试get_api_key方法 ===")
        
        from app.services.claude_account_service import ClaudeAccountService
        
        service = ClaudeAccountService()
        
        # 直接调用_decrypt_sensitive_data测试
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            result = await session.execute(select(ClaudeAccount).where(ClaudeAccount.id == 6))
            account = result.scalar_one_or_none()
            
            if account:
                logger.info(f"账号6 - {account.account_name}")
                logger.info(f"  加密后API密钥长度: {len(account.api_key)}")
                
                # 测试空context解密（get_api_key使用的方式）
                try:
                    decrypted_key = service._decrypt_sensitive_data(account.api_key, "")
                    logger.info(f"  ✅ 空context解密成功: {decrypted_key[:20]}...")
                    return True
                except Exception as e:
                    logger.error(f"  ❌ 空context解密失败: {e}")
                    
                    # 尝试account_name context解密
                    try:
                        decrypted_key = service._decrypt_sensitive_data(account.api_key, account.account_name)
                        logger.info(f"  🟡 account_name context解密成功: {decrypted_key[:20]}...")
                        logger.warning("  ⚠️  context不匹配问题确认")
                        return False
                    except Exception as e2:
                        logger.error(f"  ❌ account_name context解密也失败: {e2}")
                        return False
            else:
                logger.error("  ❌ 账号6不存在")
                return False
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False


async def main():
    """主函数"""
    logger.info("🔧 Context不匹配修复脚本启动")
    
    # 先测试当前状态
    test_result = await test_get_api_key()
    
    if not test_result:
        # 修复context不匹配问题
        fix_success = await fix_context_mismatch()
        
        if fix_success:
            # 再次测试
            final_test = await test_get_api_key()
            if final_test:
                logger.info("\n🎉 修复完成！API密钥解密现在应该正常工作")
            else:
                logger.error("\n❌ 修复后仍然有问题")
        else:
            logger.error("\n❌ 修复过程失败")
    else:
        logger.info("\n✅ API密钥解密已经正常工作，无需修复")


if __name__ == "__main__":
    asyncio.run(main())