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
from loguru import logger

from app.config import settings

# 创建异步引擎 - 优化连接池配置防止泄漏
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # 在调试模式下显示SQL
    pool_pre_ping=True,   # 连接前检查
    pool_recycle=1800,    # 30分钟回收连接（缩短周期）
    pool_timeout=30,      # 连接池获取连接超时30秒
    pool_size=10,         # 连接池大小
    max_overflow=20,      # 最大溢出连接数
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
    获取数据库会话 - 修复版（简化逻辑，确保连接必定释放）
    
    核心原则：
    1. 无条件释放连接
    2. 简化异常处理
    3. 确保资源清理
    
    用法:
    async def some_function(db: AsyncSession = Depends(get_db)):
        # 使用db进行数据库操作
    """
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        # 简化异常处理：只回滚，不做复杂判断
        await session.rollback()
        raise
    finally:
        # 无条件关闭会话 - 这是修复的关键
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


# 数据库健康检查 - 增强版
async def db_health_check():
    """数据库健康检查 - 包含连接池状态监控"""
    import gc
    import psutil
    
    try:
        is_connected = await check_db_connection()
        
        # 获取连接池状态
        pool_stats = {
            "pool_size": engine.pool.size(),
            "checked_out": engine.pool.checkedout(),
            "checked_in": engine.pool.checkedin(),
            "overflow": engine.pool.overflow(),
            "invalid": engine.pool.invalid(),
        }
        
        # 检查系统内存使用
        memory_info = psutil.virtual_memory()
        swap_info = psutil.swap_memory()
        
        # 计算健康评分
        health_score = 100
        warning_messages = []
        
        # 连接池健康检查
        if pool_stats["checked_out"] / max(pool_stats["pool_size"], 1) > 0.8:
            health_score -= 30
            warning_messages.append("连接池使用率过高")
        
        if pool_stats["overflow"] > 5:
            health_score -= 20
            warning_messages.append("连接池溢出过多")
            
        # 内存健康检查
        if memory_info.percent > 85:
            health_score -= 25
            warning_messages.append("系统内存使用率过高")
            
        if swap_info.percent > 50:
            health_score -= 25
            warning_messages.append("交换空间使用过多")
        
        # 垃圾收集统计
        gc_stats = gc.get_stats()
        leaked_sessions = sum(1 for obj in gc.get_objects() 
                             if hasattr(obj, '__class__') and 'AsyncSession' in str(obj.__class__))
        
        if leaked_sessions > 10:
            health_score -= 20
            warning_messages.append(f"检测到{leaked_sessions}个可能泄漏的会话")
        
        status = "healthy" if health_score >= 70 else "warning" if health_score >= 40 else "critical"
        
        return {
            "database": status,
            "health_score": health_score,
            "type": "SQLite",
            "url": settings.database_url,
            "pool_stats": pool_stats,
            "memory_usage_percent": memory_info.percent,
            "swap_usage_percent": swap_info.percent,
            "leaked_sessions": leaked_sessions,
            "warnings": warning_messages,
            "recommendations": _get_health_recommendations(health_score, pool_stats, warning_messages)
        }
        
    except Exception as e:
        return {
            "database": "error",
            "error": str(e),
            "health_score": 0
        }


def _get_health_recommendations(score, pool_stats, warnings):
    """生成健康建议"""
    recommendations = []
    
    if score < 70:
        recommendations.append("建议重启交易服务以清理资源")
    
    if "连接池使用率过高" in warnings:
        recommendations.append("考虑增加连接池大小或检查连接泄漏")
    
    if "系统内存使用率过高" in warnings:
        recommendations.append("检查内存泄漏并考虑增加系统内存")
        
    if "交换空间使用过多" in warnings:
        recommendations.append("系统内存不足，需要优化内存使用")
        
    if pool_stats.get("overflow", 0) > 5:
        recommendations.append("连接池溢出过多，考虑优化数据库访问模式")
    
    return recommendations


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