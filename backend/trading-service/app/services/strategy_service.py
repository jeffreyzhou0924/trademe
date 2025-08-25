"""
策略服务 - 策略管理业务逻辑
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.orm import selectinload
import json
import ast
import traceback
from datetime import datetime, timedelta

from app.models.strategy import Strategy
from app.schemas.strategy import StrategyCreate, StrategyUpdate


class StrategyService:
    """策略服务类"""
    
    @staticmethod
    async def get_user_strategies(
        db: AsyncSession, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 20, 
        active_only: bool = True
    ) -> List[Strategy]:
        """获取用户策略列表"""
        query = select(Strategy).where(Strategy.user_id == user_id)
        
        if active_only:
            query = query.where(Strategy.is_active == True)
        
        query = query.offset(skip).limit(limit).order_by(Strategy.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def count_user_strategies(
        db: AsyncSession, 
        user_id: int, 
        active_only: bool = True
    ) -> int:
        """统计用户策略数量"""
        query = select(func.count()).select_from(Strategy).where(Strategy.user_id == user_id)
        
        if active_only:
            query = query.where(Strategy.is_active == True)
        
        result = await db.execute(query)
        return result.scalar()
    
    @staticmethod
    async def get_strategy_by_id(
        db: AsyncSession, 
        strategy_id: int, 
        user_id: int
    ) -> Optional[Strategy]:
        """根据ID获取策略"""
        query = select(Strategy).where(
            and_(Strategy.id == strategy_id, Strategy.user_id == user_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def validate_strategy_code(code: str, detailed: bool = False) -> tuple:
        """验证策略代码"""
        try:
            # 基础语法检查
            ast.parse(code)
            
            # 检查必需的函数和类
            warnings = []
            
            if "def on_tick" not in code:
                warnings.append("建议定义 on_tick 函数处理实时数据")
            
            if "def on_bar" not in code:
                warnings.append("建议定义 on_bar 函数处理K线数据")
            
            if "class Strategy" not in code and "def strategy" not in code:
                warnings.append("建议定义策略类或策略函数")
            
            # 检查危险函数
            dangerous_imports = ['os', 'subprocess', 'sys', 'eval', 'exec']
            for danger in dangerous_imports:
                if f"import {danger}" in code or f"from {danger}" in code:
                    return False, f"不允许使用危险模块: {danger}", warnings
            
            if detailed:
                return True, None, warnings
            else:
                return True, None
                
        except SyntaxError as e:
            error_msg = f"语法错误: {str(e)}"
            if detailed:
                return False, error_msg, []
            else:
                return False, error_msg
        except Exception as e:
            error_msg = f"代码验证失败: {str(e)}"
            if detailed:
                return False, error_msg, []
            else:
                return False, error_msg
    
    @staticmethod
    async def create_strategy(
        db: AsyncSession, 
        strategy_data: StrategyCreate, 
        user_id: int
    ) -> Strategy:
        """创建策略"""
        # 将参数序列化为JSON字符串
        parameters_json = json.dumps(strategy_data.parameters) if strategy_data.parameters else None
        
        db_strategy = Strategy(
            user_id=user_id,
            name=strategy_data.name,
            description=strategy_data.description,
            code=strategy_data.code,
            parameters=parameters_json,
            strategy_type=getattr(strategy_data, 'strategy_type', 'strategy'),
            ai_session_id=getattr(strategy_data, 'ai_session_id', None),
            is_active=True
        )
        
        db.add(db_strategy)
        await db.commit()
        await db.refresh(db_strategy)
        
        return db_strategy
    
    @staticmethod
    async def update_strategy(
        db: AsyncSession, 
        strategy_id: int, 
        strategy_data: StrategyUpdate
    ) -> Strategy:
        """更新策略"""
        # 构建更新数据
        update_data = {}
        
        if strategy_data.name is not None:
            update_data['name'] = strategy_data.name
            
        if strategy_data.description is not None:
            update_data['description'] = strategy_data.description
            
        if strategy_data.code is not None:
            update_data['code'] = strategy_data.code
            
        if strategy_data.parameters is not None:
            update_data['parameters'] = json.dumps(strategy_data.parameters)
            
        if strategy_data.is_active is not None:
            update_data['is_active'] = strategy_data.is_active
        
        # 执行更新
        query = update(Strategy).where(Strategy.id == strategy_id).values(**update_data)
        await db.execute(query)
        await db.commit()
        
        # 返回更新后的策略
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
        return result.scalar_one()
    
    @staticmethod
    async def delete_strategy(db: AsyncSession, strategy_id: int) -> bool:
        """删除策略"""
        query = delete(Strategy).where(Strategy.id == strategy_id)
        result = await db.execute(query)
        await db.commit()
        
        return result.rowcount > 0
    
    @staticmethod
    async def has_running_operations(db: AsyncSession, strategy_id: int) -> bool:
        """检查是否有正在运行的操作"""
        try:
            # 检查是否有正在运行的实盘交易
            from sqlalchemy import text
            
            # 使用原生SQL查询live_strategies表
            result = await db.execute(
                text("SELECT COUNT(*) FROM live_strategies WHERE strategy_id = :strategy_id AND status IN ('running', 'paused')"),
                {"strategy_id": strategy_id}
            )
            count = result.scalar()
            
            print(f"策略ID {strategy_id} 的运行中实盘数量: {count}")
            return count > 0
            
        except Exception as e:
            print(f"检查运行状态失败: {e}")
            # 出错时返回False，不阻止删除
            return False
    
    @staticmethod
    async def start_backtest(db: AsyncSession, strategy_id: int, user_id: int) -> Dict:
        """开始回测"""
        # TODO: 实现回测启动逻辑
        # 1. 创建回测记录
        # 2. 启动回测任务
        # 3. 返回执行ID
        execution_id = f"backtest_{strategy_id}_{int(datetime.now().timestamp())}"
        return {
            "execution_id": execution_id, 
            "message": "回测已提交，正在准备执行"
        }
    
    @staticmethod
    async def start_live_trading(db: AsyncSession, strategy_id: int, user_id: int) -> Dict:
        """开始实盘交易"""
        # TODO: 实现实盘交易启动逻辑
        # 1. 检查API密钥配置
        # 2. 创建交易记录
        # 3. 启动实盘交易任务
        execution_id = f"live_{strategy_id}_{int(datetime.now().timestamp())}"
        return {
            "execution_id": execution_id, 
            "message": "实盘交易已启动"
        }
    
    @staticmethod
    async def stop_strategy_execution(db: AsyncSession, strategy_id: int) -> Dict:
        """停止策略执行"""
        # TODO: 实现策略停止逻辑
        # 1. 查找正在运行的任务
        # 2. 发送停止信号
        # 3. 更新状态
        return {"stopped": True, "message": "策略执行已停止"}
    
    @staticmethod
    async def get_strategy_performance(db: AsyncSession, strategy_id: int, days: int) -> Dict:
        """获取策略性能"""
        # TODO: 实现性能统计
        # 1. 查询指定天数内的交易记录
        # 2. 计算收益率、胜率、最大回撤等指标
        # 3. 返回性能数据
        return {
            "strategy_id": strategy_id,
            "period_days": days,
            "total_return": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "total_trades": 0,
            "message": "性能统计功能开发中"
        }
    
    @staticmethod
    async def clone_strategy(
        db: AsyncSession, 
        strategy_id: int, 
        user_id: int, 
        new_name: Optional[str] = None
    ) -> Strategy:
        """克隆策略"""
        # 获取原策略
        original = await StrategyService.get_strategy_by_id(db, strategy_id, user_id)
        if not original:
            raise ValueError("原策略不存在")
        
        # 创建克隆策略
        cloned_name = new_name or f"{original.name}_副本"
        
        cloned_strategy = Strategy(
            user_id=user_id,
            name=cloned_name,
            description=f"克隆自: {original.name}",
            code=original.code,
            parameters=original.parameters,
            is_active=False  # 新克隆的策略默认不激活
        )
        
        db.add(cloned_strategy)
        await db.commit()
        await db.refresh(cloned_strategy)
        
        return cloned_strategy
    
    @staticmethod
    async def get_strategy_logs(db: AsyncSession, strategy_id: int, limit: int) -> List[Dict]:
        """获取策略日志"""
        # TODO: 实现日志查询
        # 1. 查询策略执行日志表
        # 2. 返回最近的日志记录
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "message": "策略日志功能开发中",
                "strategy_id": strategy_id
            }
        ]
    
    @staticmethod
    async def get_strategy_live_details(db: AsyncSession, strategy_id: int) -> Dict[str, Any]:
        """获取策略实盘详细信息"""
        from app.models.trade import Trade
        from sqlalchemy import func, case
        
        try:
            # 获取交易统计
            trade_stats_query = select(
                func.count(Trade.id).label('total_trades'),
                func.sum(case((Trade.side == 'BUY', Trade.total_amount), else_=0)).label('buy_volume'),
                func.sum(case((Trade.side == 'SELL', Trade.total_amount), else_=0)).label('sell_volume'),
                func.sum(Trade.fee).label('total_fees'),
                func.avg(Trade.price).label('avg_price'),
                func.min(Trade.executed_at).label('first_trade'),
                func.max(Trade.executed_at).label('last_trade')
            ).where(and_(
                Trade.strategy_id == strategy_id,
                Trade.trade_type == 'LIVE'
            ))
            
            trade_stats_result = await db.execute(trade_stats_query)
            trade_stats = trade_stats_result.first()
            
            # 获取最近的交易记录
            recent_trades_query = select(Trade).where(and_(
                Trade.strategy_id == strategy_id,
                Trade.trade_type == 'LIVE'
            )).order_by(Trade.executed_at.desc()).limit(10)
            
            recent_trades_result = await db.execute(recent_trades_query)
            recent_trades = recent_trades_result.scalars().all()
            
            # 计算简单的性能指标
            total_trades = trade_stats.total_trades or 0
            buy_volume = float(trade_stats.buy_volume or 0)
            sell_volume = float(trade_stats.sell_volume or 0)
            total_fees = float(trade_stats.total_fees or 0)
            
            # 简单的盈亏计算（实际实现会更复杂）
            profit_loss = sell_volume - buy_volume - total_fees if total_trades > 0 else 0.0
            profit_percentage = (profit_loss / buy_volume * 100) if buy_volume > 0 else 0.0
            
            return {
                "stats": {
                    "total_trades": total_trades,
                    "buy_volume": buy_volume,
                    "sell_volume": sell_volume,
                    "total_fees": total_fees,
                    "profit_loss": profit_loss,
                    "profit_percentage": profit_percentage,
                    "avg_price": float(trade_stats.avg_price or 0),
                    "first_trade": trade_stats.first_trade.isoformat() if trade_stats.first_trade else None,
                    "last_trade": trade_stats.last_trade.isoformat() if trade_stats.last_trade else None,
                },
                "trades": [
                    {
                        "id": trade.id,
                        "side": trade.side,
                        "quantity": float(trade.quantity),
                        "price": float(trade.price),
                        "total_amount": float(trade.total_amount),
                        "fee": float(trade.fee),
                        "executed_at": trade.executed_at.isoformat()
                    }
                    for trade in recent_trades
                ],
                "performance": {
                    "total_return": profit_percentage,
                    "win_rate": 0.0,  # TODO: 实现胜率计算
                    "max_drawdown": 0.0,  # TODO: 实现最大回撤计算
                    "sharpe_ratio": 0.0,  # TODO: 实现夏普比率计算
                },
                "status": "running" if total_trades > 0 else "stopped"
            }
            
        except Exception as e:
            print(f"Error getting live details: {e}")
            # 返回默认数据
            return {
                "stats": {
                    "total_trades": 0,
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "total_fees": 0.0,
                    "profit_loss": 0.0,
                    "profit_percentage": 0.0,
                    "avg_price": 0.0,
                    "first_trade": None,
                    "last_trade": None,
                },
                "trades": [],
                "performance": {
                    "total_return": 0.0,
                    "win_rate": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                },
                "status": "stopped"
            }
    
    @staticmethod
    async def get_strategy_trades(
        db: AsyncSession, 
        strategy_id: int, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取策略交易记录"""
        from app.models.trade import Trade
        
        try:
            query = select(Trade).where(and_(
                Trade.strategy_id == strategy_id,
                Trade.trade_type == 'LIVE'
            )).order_by(Trade.executed_at.desc()).limit(limit).offset(offset)
            
            result = await db.execute(query)
            trades = result.scalars().all()
            
            return [
                {
                    "id": trade.id,
                    "exchange": trade.exchange,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": float(trade.quantity),
                    "price": float(trade.price),
                    "total_amount": float(trade.total_amount),
                    "fee": float(trade.fee),
                    "order_id": trade.order_id,
                    "executed_at": trade.executed_at.isoformat(),
                    "created_at": trade.created_at.isoformat()
                }
                for trade in trades
            ]
        except Exception as e:
            print(f"Error getting strategy trades: {e}")
            return []
    
    @staticmethod
    async def count_strategy_trades(db: AsyncSession, strategy_id: int) -> int:
        """统计策略交易记录数量"""
        from app.models.trade import Trade
        
        try:
            query = select(func.count()).select_from(Trade).where(and_(
                Trade.strategy_id == strategy_id,
                Trade.trade_type == 'LIVE'
            ))
            
            result = await db.execute(query)
            return result.scalar() or 0
        except Exception as e:
            print(f"Error counting strategy trades: {e}")
            return 0

    @staticmethod
    async def get_public_strategies(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20
    ) -> List[Strategy]:
        """获取公开策略列表"""
        query = select(Strategy).where(
            and_(Strategy.is_active == True, Strategy.is_public == True)
        ).offset(skip).limit(limit).order_by(Strategy.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_strategy_by_ai_session(
        db: AsyncSession,
        ai_session_id: str,
        user_id: int,
        strategy_type: str
    ) -> Optional[Strategy]:
        """根据AI会话ID获取用户的策略/指标"""
        query = select(Strategy).where(and_(
            Strategy.ai_session_id == ai_session_id,
            Strategy.user_id == user_id,
            Strategy.strategy_type == strategy_type,
            Strategy.is_active == True
        ))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_strategies_by_type(
        db: AsyncSession,
        user_id: int,
        strategy_type: str,
        skip: int = 0,
        limit: int = 20,
        active_only: bool = True
    ) -> List[Strategy]:
        """根据类型获取用户的策略或指标"""
        query = select(Strategy).where(and_(
            Strategy.user_id == user_id,
            Strategy.strategy_type == strategy_type
        ))
        
        if active_only:
            query = query.where(Strategy.is_active == True)
        
        query = query.offset(skip).limit(limit).order_by(Strategy.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def count_strategies_by_type(
        db: AsyncSession,
        user_id: int,
        strategy_type: str,
        active_only: bool = True
    ) -> int:
        """统计用户指定类型的策略/指标数量"""
        query = select(func.count()).select_from(Strategy).where(and_(
            Strategy.user_id == user_id,
            Strategy.strategy_type == strategy_type
        ))
        
        if active_only:
            query = query.where(Strategy.is_active == True)
        
        result = await db.execute(query)
        return result.scalar() or 0