"""
无状态回测引擎适配器

将无状态回测引擎适配到现有的BacktestEngine接口
解决状态污染问题，同时保持向前兼容性
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
import json
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

# 导入无状态回测引擎
from app.services.backtest_engine_stateless import (
    StatelessBacktestEngine, 
    BacktestConfig, 
    BacktestResult,
    run_stateless_backtest
)
from app.models.strategy import Strategy
from app.services.data_validation_service import DataValidationService


class StatelessBacktestAdapter:
    """
    无状态回测引擎适配器
    
    提供与原BacktestEngine兼容的接口，
    但内部使用无状态设计避免状态污染
    """
    
    def __init__(self):
        """
        初始化适配器
        注意：这个类本身不保存任何状态
        """
        pass
    
    async def execute_backtest(
        self,
        params: Dict[str, Any],
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        执行回测 - 兼容原接口
        
        Args:
            params: 回测参数字典
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            Dict: 回测结果
        """
        try:
            logger.info(f"🚀 开始无状态回测执行，用户: {user_id}")
            
            # 1. 解析回测参数
            config = await self._parse_backtest_params(params, user_id, db)
            
            # 2. 执行无状态回测
            result = await StatelessBacktestEngine.run_backtest(config, db)
            
            # 3. 转换结果格式以兼容原接口
            compatible_result = await self._convert_result_format(result)
            
            logger.info(f"✅ 无状态回测完成，成功: {result.success}")
            
            return {
                "success": result.success,
                "backtest_result": compatible_result,
                "error": result.error if not result.success else None
            }
            
        except Exception as e:
            logger.error(f"❌ 无状态回测执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "backtest_result": None
            }
    
    async def run_backtest(
        self,
        strategy_id: int,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        symbol: str = "BTC/USDT",
        exchange: str = "binance",
        timeframe: str = "1h",
        db: AsyncSession = None,
        # 🔧 新增：确定性参数支持
        deterministic: bool = False,
        random_seed: int = 42,
        product_type: str = "spot"
    ) -> Dict[str, Any]:
        """
        运行回测 - 兼容原接口
        
        这是对原BacktestEngine.run_backtest()方法的无状态替代
        """
        try:
            logger.info(f"📊 开始无状态回测，策略: {strategy_id}")
            
            # 1. 构建回测配置
            config = BacktestConfig(
                strategy_id=strategy_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                product_type=product_type,
                # 🔧 关键修复：支持确定性配置
                deterministic=deterministic,
                random_seed=random_seed
            )
            
            # 2. 执行无状态回测
            result = await StatelessBacktestEngine.run_backtest(config, db)
            
            # 3. 转换为兼容格式
            if result.success:
                return {
                    "backtest_id": result.backtest_id,
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "exchange": exchange,
                    "timeframe": timeframe,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "initial_capital": initial_capital,
                    "final_capital": result.performance_metrics.get("final_capital", initial_capital),
                    "performance": result.performance_metrics,
                    "trades_count": len(result.trades),
                    "status": "completed"
                }
            else:
                raise Exception(result.error)
                
        except Exception as e:
            logger.error(f"❌ 无状态回测失败: {e}")
            raise
    
    async def _parse_backtest_params(
        self,
        params: Dict[str, Any],
        user_id: int,
        db: AsyncSession
    ) -> BacktestConfig:
        """解析回测参数为BacktestConfig"""
        
        # 提取必需参数
        strategy_code = params.get('strategy_code')
        exchange = params.get('exchange', 'binance')
        symbols = params.get('symbols', ['BTC/USDT'])
        timeframes = params.get('timeframes', ['1h'])
        start_date_str = params.get('start_date')
        end_date_str = params.get('end_date')
        initial_capital = params.get('initial_capital', 10000.0)
        
        # 日期转换
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')) if isinstance(start_date_str, str) else start_date_str
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')) if isinstance(end_date_str, str) else end_date_str
        
        # 如果提供了策略代码，需要创建临时策略记录
        strategy_id = await self._create_temp_strategy(strategy_code, user_id, db) if strategy_code else 1
        
        return BacktestConfig(
            strategy_id=strategy_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            symbol=symbols[0] if symbols else "BTC/USDT",
            exchange=exchange,
            timeframe=timeframes[0] if timeframes else "1h",
            product_type=params.get('product_type', 'spot'),  # 🔧 关键修复：添加产品类型参数
            fee_rate=0.001,
            ai_session_id=params.get('ai_session_id'),
            is_ai_generated=params.get('is_ai_generated', False),
            membership_level=params.get('membership_level', 'basic'),
            # 🔧 关键修复：传递确定性参数
            deterministic=params.get('deterministic', False),
            random_seed=params.get('random_seed', 42)
        )
    
    async def _create_temp_strategy(
        self,
        strategy_code: str,
        user_id: int,
        db: AsyncSession
    ) -> int:
        """创建临时策略记录用于回测"""
        from app.models.strategy import Strategy
        
        temp_strategy = Strategy(
            name=f"临时策略_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description="API回测临时策略",
            code=strategy_code,
            user_id=user_id,
            strategy_type="strategy",
            is_active=True,
            is_public=False
        )
        
        db.add(temp_strategy)
        await db.commit()
        await db.refresh(temp_strategy)
        
        logger.info(f"📝 创建临时策略: {temp_strategy.id}")
        return temp_strategy.id
    
    async def _convert_result_format(self, result: BacktestResult) -> Dict[str, Any]:
        """将BacktestResult转换为兼容的结果格式"""
        
        if not result.success:
            return {"error": result.error}
        
        # 转换交易记录格式
        trades = []
        for trade_data in result.trades:
            trades.append({
                "timestamp": trade_data["timestamp"],
                "type": trade_data["type"],
                "price": trade_data["price"],
                "quantity": trade_data["quantity"],
                "fee": trade_data.get("fee", 0),
                "total": trade_data.get("total", 0),
                "pnl": trade_data.get("profit", 0)  # 映射profit到pnl
            })
        
        # 转换组合历史
        portfolio_history = []
        for history_point in result.portfolio_history:
            portfolio_history.append({
                "timestamp": history_point["timestamp"],
                "total_value": history_point["total_value"],
                "cash": history_point.get("cash", 0),
                "position_value": history_point.get("position_value", 0),
                "drawdown": history_point.get("drawdown", 0)
            })
        
        return {
            "trades": trades,
            "portfolio_history": portfolio_history,
            "final_portfolio_value": result.performance_metrics.get("final_capital", 0),
            "performance_metrics": result.performance_metrics,
            "execution_time": result.execution_time,
            "ai_analysis": result.ai_analysis,
            "optimization_suggestions": result.optimization_suggestions
        }


# 工厂方法 - 替换原有的工厂方法
def create_stateless_backtest_engine() -> StatelessBacktestAdapter:
    """创建无状态回测引擎适配器"""
    return StatelessBacktestAdapter()


def create_stateless_deterministic_backtest_engine(random_seed: int = 42) -> StatelessBacktestAdapter:
    """创建确定性无状态回测引擎适配器"""
    # 无状态引擎本身就支持确定性配置
    # 这里返回相同的适配器，确定性通过BacktestConfig控制
    return StatelessBacktestAdapter()