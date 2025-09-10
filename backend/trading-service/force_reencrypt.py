#!/usr/bin/env python3
"""
强制重新加密API密钥
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


async def force_reencrypt():
    """强制重新加密"""
    try:
        logger.info("=== 强制重新加密API密钥 ===")
        
        # 原始明文API密钥
        original_keys = {
            6: "cr_b48f228f987b3d94495498a9260fdb6032ccc4cd3dd49ea380c960ed699bab56",
            7: "cr_a6051ecd7d18b3430b21ff0ca7557bcbb564ce96a124beb40cb3c72f3072cc9a"
        }
        
        crypto_manager = CryptoManager()
        logger.info(f"主密钥: {crypto_manager.master_key[:20]}...")
        
        async with AsyncSessionLocal() as session:
            for account_id, original_key in original_keys.items():
                logger.info(f"\n处理账号 {account_id}")
                
                # 用空context加密
                encrypted_key = crypto_manager.encrypt_private_key(original_key, "")
                logger.info(f"  新加密长度: {len(encrypted_key)}")
                
                # 验证
                test_decrypt = crypto_manager.decrypt_private_key(encrypted_key, "")
                logger.info(f"  验证结果: {test_decrypt == original_key}")
                
                # 更新数据库
                await session.execute(
                    update(ClaudeAccount)
                    .where(ClaudeAccount.id == account_id)
                    .values(api_key=encrypted_key)
                )
                
                logger.info(f"  ✅ 数据库已更新")
            
            await session.commit()
            logger.info("\n✅ 所有账号重新加密完成")
            
    except Exception as e:
        logger.error(f"重新加密失败: {e}")


if __name__ == "__main__":
    asyncio.run(force_reencrypt())