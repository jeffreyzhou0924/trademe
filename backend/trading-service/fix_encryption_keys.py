#!/usr/bin/env python3
"""
修复Claude账号API密钥加密问题
恢复明文密钥并用正确的主密钥重新加密
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


async def fix_encryption_keys():
    """修复加密密钥问题"""
    try:
        logger.info("=== 开始修复Claude账号加密密钥问题 ===")
        
        # 原始明文API密钥数据
        original_keys = {
            6: "cr_b48f228f987b3d94495498a9260fdb6032ccc4cd3dd49ea380c960ed699bab56",
            7: "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
        }
        
        # 初始化加密管理器（应该会使用正确的主密钥）
        crypto_manager = CryptoManager()
        logger.info(f"加密管理器配置: {crypto_manager.get_encryption_info()}")
        logger.info(f"主密钥前缀: {crypto_manager.master_key[:20]}...")
        
        async with AsyncSessionLocal() as session:
            updated_count = 0
            
            for account_id, original_key in original_keys.items():
                logger.info(f"\n正在处理账号 {account_id}")
                logger.info(f"  原始密钥: {original_key[:20]}...")
                
                try:
                    # 使用正确的主密钥加密
                    context = f"ClaudeCdn7代理服务" if account_id == 6 else "cdn71"
                    encrypted_key = crypto_manager.encrypt_private_key(original_key, context)
                    
                    logger.info(f"  加密后长度: {len(encrypted_key)}")
                    
                    # 验证加密解密循环
                    decrypted_key = crypto_manager.decrypt_private_key(encrypted_key, context)
                    if decrypted_key == original_key:
                        logger.info(f"  ✅ 加密验证成功")
                        
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
                logger.info(f"\n✅ 成功修复 {updated_count} 个账号的加密密钥")
            else:
                logger.error(f"\n❌ 没有成功修复任何账号")
                
    except Exception as e:
        logger.error(f"修复过程失败: {e}")
        return False
    
    return True


async def test_decryption():
    """测试解密是否正常工作"""
    try:
        logger.info("\n=== 测试解密功能 ===")
        
        from app.services.claude_account_service import ClaudeAccountService
        
        service = ClaudeAccountService()
        
        # 测试获取API密钥
        api_key_6 = await service.get_api_key(6)
        api_key_7 = await service.get_api_key(7)
        
        logger.info(f"账号6 API密钥: {api_key_6[:20] if api_key_6 else 'None'}...")
        logger.info(f"账号7 API密钥: {api_key_7[:20] if api_key_7 else 'None'}...")
        
        if api_key_6 and api_key_7:
            logger.info("✅ 解密功能测试成功")
            return True
        else:
            logger.error("❌ 解密功能测试失败")
            return False
            
    except Exception as e:
        logger.error(f"解密测试失败: {e}")
        return False


async def main():
    """主函数"""
    logger.info("🔧 Claude账号加密密钥修复脚本启动")
    
    # 修复加密密钥
    fix_success = await fix_encryption_keys()
    
    if fix_success:
        # 测试解密功能
        test_success = await test_decryption()
        
        if test_success:
            logger.info("\n🎉 修复完成！Claude账号加密系统现在应该正常工作")
        else:
            logger.error("\n❌ 修复后测试失败，可能需要进一步调试")
    else:
        logger.error("\n❌ 修复过程失败")


if __name__ == "__main__":
    asyncio.run(main())