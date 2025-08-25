"""
测试配置和共享fixtures
为所有测试提供数据库、Redis连接等基础设施
"""

import pytest
import asyncio
import tempfile
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.database import Base
from app.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """创建测试数据库引擎"""
    # 创建临时SQLite数据库
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    database_url = f"sqlite+aiosqlite:///{temp_db.name}"
    engine = create_async_engine(database_url, echo=False)
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # 清理
    await engine.dispose()
    os.unlink(temp_db.name)


@pytest.fixture
async def test_db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    AsyncTestSession = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncTestSession() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
async def clean_database(test_db_session: AsyncSession):
    """清理测试数据库"""
    # 删除所有表数据
    tables = [
        "usdt_payment_orders", "usdt_wallets", "payment_webhooks", 
        "payment_notifications", "claude_accounts", "proxies",
        "claude_usage_logs", "claude_scheduler_configs"
    ]
    
    for table in tables:
        try:
            await test_db_session.execute(text(f"DELETE FROM {table}"))
        except Exception:
            # 表不存在则跳过
            pass
    
    await test_db_session.commit()
    yield
    
    # 测试后清理
    for table in tables:
        try:
            await test_db_session.execute(text(f"DELETE FROM {table}"))
        except Exception:
            pass
    await test_db_session.commit()


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        "WALLET_MASTER_KEY": "test_master_key_32_bytes_long_12345",
        "PAYMENT_TIMEOUT_MINUTES": 30,
        "SUPPORTED_NETWORKS": ["TRC20", "ERC20", "BEP20"],
        "MIN_AMOUNTS": {
            "TRC20": 1.0,
            "ERC20": 10.0,  
            "BEP20": 1.0
        }
    }


@pytest.fixture
def sample_wallet_data():
    """示例钱包数据"""
    return {
        "network": "TRC20",
        "address": "TTestAddress123456789012345678901234567890",
        "private_key": "test_private_key_encrypted",
        "balance": 100.0,
        "risk_level": "LOW",
        "is_active": True,
        "success_rate": 0.98,
        "avg_response_time": 1.5
    }


@pytest.fixture
def sample_order_data():
    """示例订单数据"""
    return {
        "user_id": 1,
        "usdt_amount": 10.0,
        "network": "TRC20",
        "membership_plan_id": None,
        "extra_info": {
            "risk_level": "LOW",
            "add_random_suffix": True
        }
    }


@pytest.fixture
def mock_blockchain_responses():
    """模拟区块链响应数据"""
    return {
        "tron_latest_block": {
            "blockID": "0000000001234567",
            "block_header": {
                "raw_data": {
                    "number": 12345,
                    "timestamp": 1640995200000
                }
            }
        },
        "ethereum_latest_block": {
            "number": "0x1234",
            "hash": "0xabcdef123456789",
            "timestamp": "0x61c8c400"
        },
        "address_balance": {
            "TRC20": 100.5,
            "ERC20": 250.25
        },
        "transaction_status": {
            "success": True,
            "confirmations": 12,
            "block_height": 12345
        }
    }