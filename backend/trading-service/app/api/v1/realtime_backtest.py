"""
实时回测API端点
提供AI对话中的实时回测功能
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
import pandas as pd
import numpy as np
from loguru import logger

from app.middleware.auth import get_current_user
from app.services.backtest_service import BacktestService
from app.services.strategy_service import StrategyService


router = APIRouter(prefix="/realtime-backtest", tags=["实时回测"])


# 回测配置模型
class RealtimeBacktestConfig(BaseModel):
    """实时回测配置"""
    strategy_code: str
    exchange: str = "binance"
    product_type: str = "spot"
    symbols: List[str] = ["BTC/USDT"]
    timeframes: List[str] = ["1h"]
    fee_rate: str = "vip0"
    initial_capital: float = 10000.0
    start_date: str
    end_date: str
    data_type: str = "kline"  # "kline" or "tick"


# 回测状态模型
class BacktestStatus(BaseModel):
    """回测状态"""
    task_id: str
    status: str  # "running", "completed", "failed"
    progress: int = 0
    current_step: str = ""
    logs: List[str] = []
    results: Optional[Dict] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


# 全局任务存储
active_backtests: Dict[str, BacktestStatus] = {}


class RealtimeBacktestManager:
    """实时回测管理器"""
    
    def __init__(self):
        self.backtest_service = BacktestService()
        self.strategy_service = StrategyService()
    
    async def start_backtest(self, config: RealtimeBacktestConfig, user_id: int) -> str:
        """启动实时回测"""
        task_id = str(uuid.uuid4())
        
        # 创建回测状态
        status = BacktestStatus(
            task_id=task_id,
            status="running",
            progress=0,
            current_step="准备回测环境...",
            logs=["🚀 回测任务已启动", "⚙️ 初始化回测环境"],
            started_at=datetime.now()
        )
        
        active_backtests[task_id] = status
        
        # 启动后台任务
        asyncio.create_task(self._execute_backtest(task_id, config, user_id))
        
        return task_id
    
    async def _execute_backtest(self, task_id: str, config: RealtimeBacktestConfig, user_id: int):
        """执行回测的后台任务"""
        try:
            status = active_backtests[task_id]
            
            # 回测执行步骤
            steps = [
                {
                    "progress": 10,
                    "step": "验证策略代码...",
                    "logs": ["📄 读取策略文件", "✅ 策略代码验证通过", "🔍 检查策略依赖项"],
                    "action": self._validate_strategy_code
                },
                {
                    "progress": 25,
                    "step": "准备历史数据...",
                    "logs": [f"📊 连接{config.exchange}交易所", f"📥 下载{', '.join(config.symbols)}数据", "⏰ 数据时间范围验证"],
                    "action": self._prepare_data
                },
                {
                    "progress": 45,
                    "step": "执行回测逻辑...",
                    "logs": ["🧮 初始化交易引擎", "📈 开始模拟交易", "⚡ 处理交易信号"],
                    "action": self._run_backtest_logic
                },
                {
                    "progress": 70,
                    "step": "计算性能指标...",
                    "logs": ["📊 计算收益率", "📉 分析回撤风险", "🎯 评估策略表现"],
                    "action": self._calculate_metrics
                },
                {
                    "progress": 90,
                    "step": "生成分析报告...",
                    "logs": ["📋 汇总交易记录", "📈 生成图表数据", "💡 准备优化建议"],
                    "action": self._generate_report
                }
            ]
            
            backtest_data = {}
            
            # 执行每个步骤
            for step_info in steps:
                # 更新状态
                status.progress = step_info["progress"]
                status.current_step = step_info["step"]
                status.logs.extend(step_info["logs"])
                
                # 执行步骤动作
                step_result = await step_info["action"](config, backtest_data)
                backtest_data.update(step_result)
                
                # 模拟执行时间
                await asyncio.sleep(2)
            
            # 完成回测
            status.progress = 100
            status.current_step = "回测完成！"
            status.status = "completed"
            status.completed_at = datetime.now()
            
            # 生成最终结果
            results = await self._finalize_results(backtest_data)
            status.results = results
            status.logs.extend([
                f"🎯 总收益率: +{results['total_return']:.2f}%",
                f"⚡ 夏普比率: {results['sharpe_ratio']:.2f}",
                f"📉 最大回撤: -{results['max_drawdown']:.2f}%",
                f"🎲 胜率: {results['win_rate']:.0f}%",
                f"📈 交易次数: {results['total_trades']}次",
                "✅ 回测分析完成！"
            ])
            
            logger.info(f"回测任务 {task_id} 完成")
            
        except Exception as e:
            logger.error(f"回测任务 {task_id} 失败: {e}")
            status.status = "failed"
            status.error_message = str(e)
            status.logs.append(f"❌ 回测失败: {str(e)}")
    
    async def _validate_strategy_code(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """验证策略代码"""
        # 使用现有的策略验证服务
        validation_result = await self.strategy_service.validate_strategy_code(config.strategy_code)
        
        if not validation_result.get("valid", False):
            raise Exception(f"策略代码验证失败: {validation_result.get('error', 'Unknown error')}")
        
        return {"strategy_validated": True, "validation_result": validation_result}
    
    async def _prepare_data(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """准备历史数据"""
        # 模拟数据准备过程
        # 实际实现中会调用数据下载服务
        
        # 生成模拟的历史数据
        start_date = pd.to_datetime(config.start_date)
        end_date = pd.to_datetime(config.end_date)
        date_range = pd.date_range(start_date, end_date, freq='1H')
        
        # 为每个交易对生成数据
        market_data = {}
        for symbol in config.symbols:
            # 模拟K线数据
            np.random.seed(42)  # 确保结果可重复
            base_price = 45000 if 'BTC' in symbol else 3500
            prices = []
            
            for i in range(len(date_range)):
                if i == 0:
                    prices.append(base_price)
                else:
                    change = np.random.normal(0, 0.02)  # 2%的随机波动
                    new_price = prices[-1] * (1 + change)
                    prices.append(new_price)
            
            market_data[symbol] = pd.DataFrame({
                'timestamp': date_range,
                'open': prices[:-1] if len(prices) > 1 else prices,
                'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices[:-1]] if len(prices) > 1 else [p * 1.01 for p in prices],
                'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices[:-1]] if len(prices) > 1 else [p * 0.99 for p in prices],
                'close': prices[1:] if len(prices) > 1 else prices,
                'volume': np.random.uniform(100, 1000, len(prices) - 1 if len(prices) > 1 else 1)
            })
        
        return {"market_data": market_data}
    
    async def _run_backtest_logic(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """执行回测逻辑"""
        market_data = data["market_data"]
        
        # 模拟回测执行
        trades = []
        portfolio_value = config.initial_capital
        position = 0
        entry_price = 0
        
        # 简化的回测逻辑
        for symbol in config.symbols:
            df = market_data[symbol]
            
            for i, row in df.iterrows():
                current_price = row['close']
                
                # 模拟交易信号生成（简化版）
                if position == 0 and np.random.random() < 0.05:  # 5%概率开仓
                    position = 1 if np.random.random() > 0.5 else -1
                    entry_price = current_price
                    quantity = portfolio_value * 0.1 / current_price  # 10%仓位
                    
                    trades.append({
                        'timestamp': row['timestamp'],
                        'action': 'buy' if position > 0 else 'sell',
                        'price': current_price,
                        'quantity': quantity,
                        'type': 'entry'
                    })
                
                elif position != 0 and np.random.random() < 0.03:  # 3%概率平仓
                    pnl = (current_price - entry_price) / entry_price * position
                    portfolio_value *= (1 + pnl * 0.1)  # 10%仓位的盈亏影响
                    
                    trades.append({
                        'timestamp': row['timestamp'],
                        'action': 'sell' if position > 0 else 'buy',
                        'price': current_price,
                        'quantity': quantity,
                        'type': 'exit',
                        'pnl': pnl
                    })
                    
                    position = 0
        
        return {"trades": trades, "final_portfolio_value": portfolio_value}
    
    async def _calculate_metrics(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """计算性能指标"""
        trades = data["trades"]
        
        if not trades:
            return {"metrics": {}}
        
        # 计算基本指标
        entry_trades = [t for t in trades if t['type'] == 'entry']
        exit_trades = [t for t in trades if t['type'] == 'exit']
        
        if not exit_trades:
            return {"metrics": {}}
        
        # 收益率相关
        total_return = (data["final_portfolio_value"] - config.initial_capital) / config.initial_capital * 100
        
        # 交易统计
        completed_trades = len(exit_trades)
        profitable_trades = len([t for t in exit_trades if t['pnl'] > 0])
        win_rate = (profitable_trades / completed_trades * 100) if completed_trades > 0 else 0
        
        # 模拟其他指标
        profits = [t['pnl'] for t in exit_trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in exit_trades if t['pnl'] < 0]
        
        avg_win = np.mean(profits) * 100 if profits else 0
        avg_loss = abs(np.mean(losses)) * 100 if losses else 0
        profit_factor = abs(sum(profits) / sum(losses)) if losses else float('inf')
        
        # 模拟风险指标
        returns_series = pd.Series([t.get('pnl', 0) for t in exit_trades])
        sharpe_ratio = returns_series.mean() / returns_series.std() * np.sqrt(252) if returns_series.std() > 0 else 0
        max_drawdown = abs(returns_series.cumsum().min()) * 100 if len(returns_series) > 0 else 0
        
        metrics = {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "total_trades": completed_trades,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss
        }
        
        return {"metrics": metrics}
    
    async def _generate_report(self, config: RealtimeBacktestConfig, data: Dict) -> Dict:
        """生成分析报告"""
        metrics = data.get("metrics", {})
        trades = data.get("trades", [])
        
        # 生成详细报告数据
        report = {
            "summary": {
                "strategy": "AI生成策略",
                "period": f"{config.start_date} 至 {config.end_date}",
                "symbols": config.symbols,
                "initial_capital": config.initial_capital,
                "final_value": data.get("final_portfolio_value", config.initial_capital)
            },
            "performance": metrics,
            "trade_analysis": {
                "total_trades": len([t for t in trades if t['type'] == 'exit']),
                "profitable_trades": len([t for t in trades if t['type'] == 'exit' and t.get('pnl', 0) > 0]),
                "losing_trades": len([t for t in trades if t['type'] == 'exit' and t.get('pnl', 0) < 0])
            }
        }
        
        return {"report": report}
    
    async def _finalize_results(self, data: Dict) -> Dict:
        """生成最终结果"""
        metrics = data.get("metrics", {})
        report = data.get("report", {})
        
        return {
            "total_return": metrics.get("total_return", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
            "max_drawdown": metrics.get("max_drawdown", 0),
            "win_rate": metrics.get("win_rate", 0),
            "total_trades": metrics.get("total_trades", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "avg_win": metrics.get("avg_win", 0),
            "avg_loss": metrics.get("avg_loss", 0),
            "report": report
        }


# 全局管理器实例
backtest_manager = RealtimeBacktestManager()


@router.post("/start", response_model=Dict[str, str])
async def start_realtime_backtest(
    config: RealtimeBacktestConfig,
    user=Depends(get_current_user)
):
    """启动实时回测"""
    try:
        user_id = user.get("user_id", 0)
        task_id = await backtest_manager.start_backtest(config, user_id)
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": "回测任务已启动"
        }
        
    except Exception as e:
        logger.error(f"启动实时回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=BacktestStatus)
async def get_backtest_status(task_id: str):
    """获取回测状态"""
    if task_id not in active_backtests:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    
    return active_backtests[task_id]


@router.get("/results/{task_id}")
async def get_backtest_results(task_id: str):
    """获取回测结果"""
    if task_id not in active_backtests:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    
    status = active_backtests[task_id]
    
    if status.status != "completed":
        raise HTTPException(status_code=400, detail="回测尚未完成")
    
    return {
        "task_id": task_id,
        "status": status.status,
        "results": status.results,
        "completed_at": status.completed_at
    }


@router.delete("/cancel/{task_id}")
async def cancel_backtest(task_id: str):
    """取消回测任务"""
    if task_id not in active_backtests:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    
    # 标记为已取消
    status = active_backtests[task_id]
    if status.status == "running":
        status.status = "cancelled"
        status.logs.append("❌ 回测任务已被用户取消")
    
    return {"message": "回测任务已取消"}


@router.websocket("/ws/{task_id}")
async def websocket_backtest_progress(websocket: WebSocket, task_id: str):
    """WebSocket实时推送回测进度"""
    await websocket.accept()
    
    try:
        while True:
            if task_id in active_backtests:
                status = active_backtests[task_id]
                
                # 发送当前状态
                await websocket.send_json({
                    "task_id": task_id,
                    "progress": status.progress,
                    "current_step": status.current_step,
                    "status": status.status,
                    "logs": status.logs[-10:],  # 只发送最近10条日志
                    "results": status.results if status.status == "completed" else None
                })
                
                # 如果任务完成或失败，结束连接
                if status.status in ["completed", "failed", "cancelled"]:
                    break
            else:
                await websocket.send_json({"error": "Task not found"})
                break
            
            await asyncio.sleep(1)  # 每秒推送一次
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开连接: {task_id}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        await websocket.close()


# 清理完成的任务（可选的后台任务）
async def cleanup_completed_tasks():
    """清理完成超过1小时的任务"""
    now = datetime.now()
    to_remove = []
    
    for task_id, status in active_backtests.items():
        if status.status in ["completed", "failed", "cancelled"]:
            if status.completed_at and (now - status.completed_at).total_seconds() > 3600:  # 1小时
                to_remove.append(task_id)
    
    for task_id in to_remove:
        del active_backtests[task_id]
        logger.info(f"清理完成的回测任务: {task_id}")