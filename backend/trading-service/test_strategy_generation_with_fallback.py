#!/usr/bin/env python3
"""
测试策略生成时的对话历史fallback机制
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.ai_service import AIService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_strategy_generation():
    """测试策略生成是否能正确使用fallback历史"""
    
    async for db in get_db():
        user_id = 6
        # 使用一个新的session_id（模拟前端创建的新会话）
        new_session_id = str(uuid.uuid4())
        
        logger.info(f"测试用新session_id: {new_session_id}")
        
        try:
            # 模拟用户确认生成代码
            result = await AIService.generate_strategy_with_config_check(
                user_input="确认生成代码",
                user_id=user_id,
                membership_level="premium",
                session_id=new_session_id,
                config_check=None,  # 简化测试
                db=db,
                conversation_history=[]  # 传递空的历史，测试fallback
            )
            
            if result.get("success"):
                logger.info("✅ 策略生成成功！")
                strategy_code = result.get("strategy_code", "")
                
                # 检查是否包含MACD相关代码
                if "MACD" in strategy_code or "macd" in strategy_code:
                    logger.info("✅ 策略代码包含MACD指标，fallback机制工作正常！")
                    # 打印部分代码确认
                    lines = strategy_code.split('\n')
                    for line in lines[:30]:
                        if 'macd' in line.lower():
                            logger.info(f"MACD相关代码: {line}")
                else:
                    logger.warning("⚠️ 策略代码中没有找到MACD指标，可能fallback失败")
                    logger.info("生成的策略代码前500字符：")
                    logger.info(strategy_code[:500])
            else:
                logger.error(f"策略生成失败: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"测试失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_strategy_generation())