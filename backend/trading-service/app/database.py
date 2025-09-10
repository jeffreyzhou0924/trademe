"""
Trademe Trading Service - 数据库连接管理

SQLite数据库配置和连接管理
支持异步操作和连接池
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData
import asyncio
from typing import AsyncGenerator

from app.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # 在调试模式下显示SQL
    pool_pre_ping=True,   # 连接前检查
    pool_recycle=3600,    # 1小时回收连接
    connect_args={
        "check_same_thread": False,  # SQLite多线程支持
        "timeout": 20,               # 连接超时20秒
    }
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 创建基础模型
Base = declarative_base()

# 元数据
metadata = MetaData()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话 - 修复事务处理逻辑
    
    用法:
    async def some_function(db: AsyncSession = Depends(get_db)):
        # 使用db进行数据库操作
    """
    session = AsyncSessionLocal()
    try:
        # 提供会话给业务逻辑
        yield session
        
        # 如果没有显式提交，则提交事务
        if session.in_transaction():
            await session.commit()
            
    except Exception as e:
        # 发生异常时回滚事务
        if session.in_transaction():
            await session.rollback()
        raise
    finally:
        # 确保会话关闭
        await session.close()


async def init_db():
    """初始化数据库"""
    try:
        # 导入所有模型以确保表被创建
        from app.models import (
            user, strategy, backtest, trade, 
            api_key, market_data, claude_conversation, trading_note,
            # 管理后台模型
            admin, claude_proxy, payment, data_collection
        )
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ 数据库初始化成功")
        print("📋 包含的表：用户、策略、回测、交易、API密钥、市场数据、Claude对话、交易心得")
        print("📋 管理后台表：管理员、Claude代理池、USDT支付、数据采集")
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        raise


async def close_db():
    """关闭数据库连接"""
    try:
        await engine.dispose()
        print("✅ 数据库连接已关闭")
    except Exception as e:
        print(f"❌ 关闭数据库连接失败: {e}")


async def check_db_connection():
    """检查数据库连接"""
    try:
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"数据库连接检查失败: {e}")
        return False


# 数据库健康检查
async def db_health_check():
    """数据库健康检查"""
    try:
        is_connected = await check_db_connection()
        return {
            "database": "healthy" if is_connected else "unhealthy",
            "type": "SQLite",
            "url": settings.database_url
        }
    except Exception as e:
        return {
            "database": "error",
            "error": str(e)
        }


# 数据库工具函数
class DatabaseUtils:
    """数据库工具类"""
    
    @staticmethod
    async def execute_raw_sql(sql: str, params: dict = None):
        """执行原生SQL"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(sql, params or {})
            await session.commit()
            return result
    
    @staticmethod
    async def get_table_info(table_name: str):
        """获取表信息"""
        sql = f"PRAGMA table_info({table_name})"
        async with AsyncSessionLocal() as session:
            result = await session.execute(sql)
            return result.fetchall()
    
    @staticmethod
    async def get_all_tables():
        """获取所有表名"""
        sql = "SELECT name FROM sqlite_master WHERE type='table'"
        async with AsyncSessionLocal() as session:
            result = await session.execute(sql)
            return [row[0] for row in result.fetchall()]
    
    @staticmethod
    async def vacuum_database():
        """清理数据库(VACUUM操作)"""
        async with AsyncSessionLocal() as session:
            await session.execute("VACUUM")
            await session.commit()
    
    @staticmethod
    async def analyze_database():
        """分析数据库统计信息"""
        async with AsyncSessionLocal() as session:
            await session.execute("ANALYZE")
            await session.commit()


# 数据库迁移支持
async def check_migration_needed():
    """检查是否需要数据库迁移"""
    # 这里可以添加版本检查逻辑
    # 例如检查是否存在版本表，对比当前版本等
    pass


# 批量操作支持
async def bulk_insert_data(model_class, data_list: list, batch_size: int = 1000):
    """批量插入数据"""
    async with AsyncSessionLocal() as session:
        try:
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]
                session.add_all([model_class(**item) for item in batch])
                await session.commit()
            
            print(f"✅ 批量插入 {len(data_list)} 条记录成功")
            return True
            
        except Exception as e:
            await session.rollback()
            print(f"❌ 批量插入失败: {e}")
            raise


# 事务支持
class DatabaseTransaction:
    """数据库事务管理器 - 改进版本"""
    
    def __init__(self):
        self.session = None
        self._committed = False
    
    async def __aenter__(self):
        self.session = AsyncSessionLocal()
        await self.session.begin()  # 显式开始事务
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None and not self._committed:
                # 没有异常且未手动提交，自动提交
                await self.session.commit()
                self._committed = True
            elif exc_type is not None:
                # 有异常，回滚事务
                await self.session.rollback()
        except Exception as e:
            # 确保即使commit/rollback失败也能清理资源
            logger.error(f"事务管理器异常: {e}")
        finally:
            # 确保会话关闭
            await self.session.close()
    
    async def commit(self):
        """手动提交事务"""
        if self.session and not self._committed:
            await self.session.commit()
            self._committed = True
    
    async def rollback(self):
        """手动回滚事务"""
        if self.session:
            await self.session.rollback()


# 更安全的事务装饰器
def transactional(func):
    """事务装饰器 - 自动处理事务提交和回滚"""
    async def wrapper(*args, **kwargs):
        async with DatabaseTransaction() as session:
            # 将session注入到kwargs中
            kwargs['session'] = session
            return await func(*args, **kwargs)
    return wrapper