"""
回测引擎服务 - 清理版本

提供回测引擎工厂方法，实际回测逻辑使用 StatelessBacktestEngine
"""

from app.services.stateless_backtest_adapter import (
    create_stateless_backtest_engine,
    create_stateless_deterministic_backtest_engine
)
from loguru import logger


class BacktestService:
    """回测服务类 - 已简化，主要功能迁移到无状态引擎"""

    @staticmethod
    async def run_parallel_backtests(db, backtest_configs):
        """运行并行回测 - 已弃用，使用 StatelessBacktestEngine.run_parallel_backtests"""
        logger.warning("BacktestService.run_parallel_backtests 已弃用，请使用 StatelessBacktestEngine.run_parallel_backtests")
        from app.services.backtest_engine_stateless import StatelessBacktestEngine
        return await StatelessBacktestEngine.run_parallel_backtests(backtest_configs, db)


# 🔧 工厂方法：创建回测引擎实例
def create_backtest_engine() -> 'StatelessBacktestAdapter':
    """创建新的回测引擎实例，确保状态独立性 - 现在使用无状态引擎"""
    return create_stateless_backtest_engine()


def create_deterministic_backtest_engine(random_seed: int = 42) -> 'StatelessBacktestAdapter':
    """创建确定性回测引擎实例 - 解决回测结果不一致问题

    现在使用无状态引擎，彻底解决状态污染问题

    Args:
        random_seed: 随机种子，确保结果100%可重现

    Returns:
        StatelessBacktestAdapter: 无状态回测引擎适配器
    """
    return create_stateless_deterministic_backtest_engine(random_seed)