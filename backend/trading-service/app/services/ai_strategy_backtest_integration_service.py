"""
AI策略与回测集成服务

实现AI策略生成后的无缝回测集成功能
"""

import uuid
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

from app.models.strategy import Strategy
from app.models.claude_conversation import ClaudeConversation, AIChatSession
from app.services.strategy_service import StrategyService
from app.api.v1.realtime_backtest import backtest_manager, AIStrategyBacktestConfig


class AIStrategyBacktestIntegrationService:
    """AI策略与回测集成服务"""
    
    def __init__(self):
        self.strategy_service = StrategyService()
        self.backtest_manager = backtest_manager
    
    async def auto_trigger_backtest_after_strategy_generation(
        self,
        db: AsyncSession,
        user_id: int,
        ai_session_id: str,
        strategy_code: str,
        strategy_name: str,
        membership_level: str = "basic",
        auto_config: bool = True
    ) -> Dict[str, Any]:
        """
        在AI策略生成完成后自动触发回测
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            ai_session_id: AI会话ID
            strategy_code: 策略代码
            strategy_name: 策略名称
            membership_level: 会员级别
            auto_config: 是否使用自动配置的回测参数
        
        Returns:
            包含策略信息和回测任务ID的字典
        """
        try:
            # 1. 保存AI生成的策略到数据库
            strategy_id = await self._save_ai_strategy_to_database(
                db, user_id, ai_session_id, strategy_code, strategy_name
            )
            
            # 2. 智能生成回测配置
            if auto_config:
                backtest_config = await self._generate_smart_backtest_config(
                    strategy_code, membership_level
                )
            else:
                # 使用默认配置
                backtest_config = self._get_default_backtest_config(membership_level)
            
            # 3. 启动AI策略回测
            task_id = await self._launch_ai_strategy_backtest(
                strategy_id=strategy_id,
                strategy_code=strategy_code,
                strategy_name=strategy_name,
                ai_session_id=ai_session_id,
                user_id=user_id,
                membership_level=membership_level,
                config=backtest_config
            )
            
            # 4. 记录集成操作日志
            await self._log_integration_action(
                db, user_id, ai_session_id, strategy_id, task_id, "auto_backtest_triggered"
            )
            
            return {
                "success": True,
                "strategy_id": strategy_id,
                "backtest_task_id": task_id,
                "strategy_name": strategy_name,
                "ai_session_id": ai_session_id,
                "backtest_config": backtest_config,
                "message": "AI策略已生成并自动启动回测"
            }
            
        except Exception as e:
            logger.error(f"AI策略回测集成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "AI策略回测集成失败"
            }
    
    async def get_ai_session_backtest_history(
        self,
        db: AsyncSession,
        user_id: int,
        ai_session_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取AI会话的回测历史记录
        """
        try:
            # 查找该AI会话生成的所有策略
            query = select(Strategy).where(and_(
                Strategy.user_id == user_id,
                Strategy.ai_session_id == ai_session_id,
                Strategy.is_active == True
            )).order_by(Strategy.created_at.desc())
            
            result = await db.execute(query)
            strategies = result.scalars().all()
            
            backtest_history = []
            
            for strategy in strategies:
                # 获取该策略的回测记录（从内存中的活跃回测任务查找）
                strategy_backtests = await self._get_strategy_backtest_tasks(strategy.id)
                
                backtest_history.append({
                    "strategy_id": strategy.id,
                    "strategy_name": strategy.name,
                    "strategy_code": strategy.code[:200] + "..." if len(strategy.code) > 200 else strategy.code,
                    "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
                    "backtest_tasks": strategy_backtests
                })
            
            return backtest_history
            
        except Exception as e:
            logger.error(f"获取AI会话回测历史失败: {e}")
            return []
    
    async def recommend_backtest_optimization(
        self,
        strategy_code: str,
        previous_results: Optional[Dict] = None,
        membership_level: str = "basic"
    ) -> Dict[str, Any]:
        """
        基于策略代码和历史结果推荐回测优化方案
        """
        try:
            recommendations = {
                "parameter_suggestions": [],
                "timeframe_suggestions": [],
                "symbol_suggestions": [],
                "optimization_tips": [],
                "risk_management_advice": []
            }
            
            # 分析策略代码内容
            code_lower = strategy_code.lower()
            
            # 参数建议
            if "rsi" in code_lower:
                recommendations["parameter_suggestions"].append({
                    "parameter": "RSI周期",
                    "suggestion": "尝试14、21、28天周期进行对比测试",
                    "reason": "不同RSI周期对市场反应敏感度不同"
                })
            
            if "ma" in code_lower or "sma" in code_lower:
                recommendations["parameter_suggestions"].append({
                    "parameter": "移动平均线周期",
                    "suggestion": "测试20/50、50/200等经典组合",
                    "reason": "经典移动平均线组合有更好的市场认知度"
                })
            
            # 时间框架建议
            if membership_level in ["premium", "professional"]:
                recommendations["timeframe_suggestions"] = [
                    {"timeframe": "1h", "reason": "适合日内交易策略测试"},
                    {"timeframe": "4h", "reason": "平衡信号频率和噪音的理想选择"},
                    {"timeframe": "1d", "reason": "适合中长期趋势策略"}
                ]
            else:
                recommendations["timeframe_suggestions"] = [
                    {"timeframe": "1h", "reason": "基础会员推荐的平衡时间框架"}
                ]
            
            # 基于历史结果的优化建议
            if previous_results:
                if previous_results.get("win_rate", 0) < 0.5:
                    recommendations["optimization_tips"].append({
                        "tip": "胜率偏低优化",
                        "suggestion": "考虑调整进场条件，提高信号质量",
                        "priority": "high"
                    })
                
                if previous_results.get("max_drawdown", 0) > 0.15:
                    recommendations["risk_management_advice"].append({
                        "advice": "回撤控制",
                        "suggestion": "添加止损机制或降低仓位大小",
                        "priority": "critical"
                    })
            
            # 会员级别专属建议
            if membership_level == "professional":
                recommendations["optimization_tips"].append({
                    "tip": "专业级多维度测试",
                    "suggestion": "进行参数网格搜索和蒙特卡洛模拟",
                    "priority": "medium"
                })
            
            return {
                "success": True,
                "recommendations": recommendations,
                "membership_level": membership_level,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"回测优化建议生成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendations": {}
            }
    
    async def _save_ai_strategy_to_database(
        self,
        db: AsyncSession,
        user_id: int,
        ai_session_id: str,
        strategy_code: str,
        strategy_name: str
    ) -> int:
        """保存AI生成的策略到数据库"""
        try:
            from app.schemas.strategy import StrategyCreate
            
            strategy_create = StrategyCreate(
                name=strategy_name,
                description=f"AI生成的策略 (会话: {ai_session_id[:8]}...)",
                code=strategy_code,
                strategy_type="strategy",
                ai_session_id=ai_session_id,
                parameters={}
            )
            
            strategy = await self.strategy_service.create_strategy(
                db, strategy_create, user_id
            )
            
            logger.info(f"AI策略已保存到数据库: strategy_id={strategy.id}")
            return strategy.id
            
        except Exception as e:
            logger.error(f"保存AI策略到数据库失败: {e}")
            raise
    
    async def _generate_smart_backtest_config(
        self,
        strategy_code: str,
        membership_level: str
    ) -> Dict[str, Any]:
        """智能生成回测配置"""
        # 基础配置
        config = self._get_default_backtest_config(membership_level)
        
        # 基于策略代码智能调整
        code_lower = strategy_code.lower()
        
        # 时间框架智能选择
        if any(term in code_lower for term in ['scalping', '分钟', 'minute']):
            config["timeframes"] = ["1m"] if membership_level == "basic" else ["1m", "5m"]
        elif any(term in code_lower for term in ['swing', 'daily', '日线']):
            config["timeframes"] = ["1d"]
        elif any(term in code_lower for term in ['trend', '趋势']):
            config["timeframes"] = ["4h"] if membership_level == "basic" else ["1h", "4h"]
        
        # 交易对智能选择
        if any(term in code_lower for term in ['btc', 'bitcoin']):
            config["symbols"] = ["BTC/USDT"]
        elif any(term in code_lower for term in ['eth', 'ethereum']):
            config["symbols"] = ["ETH/USDT"] if membership_level == "basic" else ["ETH/USDT", "BTC/USDT"]
        
        # 资金管理智能调整
        if any(term in code_lower for term in ['high_risk', 'aggressive']):
            config["initial_capital"] = min(config["initial_capital"] * 2, 100000)
        elif any(term in code_lower for term in ['conservative', '保守']):
            config["initial_capital"] = max(config["initial_capital"] * 0.5, 5000)
        
        return config
    
    def _get_default_backtest_config(self, membership_level: str) -> Dict[str, Any]:
        """获取默认回测配置"""
        base_config = {
            "exchange": "binance",
            "product_type": "spot",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "fee_rate": "vip0",
            "initial_capital": 10000.0,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "data_type": "kline"
        }
        
        # 根据会员级别调整默认配置
        if membership_level == "premium":
            base_config.update({
                "symbols": ["BTC/USDT", "ETH/USDT"],
                "timeframes": ["1h", "4h"],
                "initial_capital": 25000.0,
                "start_date": "2023-06-01"
            })
        elif membership_level == "professional":
            base_config.update({
                "symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
                "timeframes": ["1h", "4h", "1d"],
                "initial_capital": 50000.0,
                "start_date": "2023-01-01"
            })
        
        return base_config
    
    async def _launch_ai_strategy_backtest(
        self,
        strategy_id: int,
        strategy_code: str,
        strategy_name: str,
        ai_session_id: str,
        user_id: int,
        membership_level: str,
        config: Dict[str, Any]
    ) -> str:
        """启动AI策略回测"""
        ai_config = AIStrategyBacktestConfig(
            strategy_id=strategy_id,
            strategy_code=strategy_code,
            strategy_name=strategy_name,
            ai_session_id=ai_session_id,
            **config
        )
        
        # 转换为实时回测配置
        from app.api.v1.realtime_backtest import RealtimeBacktestConfig
        
        realtime_config = RealtimeBacktestConfig(
            strategy_code=strategy_code,
            exchange=config["exchange"],
            product_type=config["product_type"],
            symbols=config["symbols"],
            timeframes=config["timeframes"],
            fee_rate=config["fee_rate"],
            initial_capital=config["initial_capital"],
            start_date=config["start_date"],
            end_date=config["end_date"],
            data_type=config["data_type"]
        )
        
        # 启动AI策略专用回测
        task_id = await self.backtest_manager.start_ai_strategy_backtest(
            realtime_config,
            user_id,
            membership_level,
            ai_session_id,
            strategy_name
        )
        
        logger.info(f"AI策略回测已启动: task_id={task_id}, strategy_id={strategy_id}")
        return task_id
    
    async def _get_strategy_backtest_tasks(self, strategy_id: int) -> List[Dict[str, Any]]:
        """获取策略的回测任务列表"""
        from app.api.v1.realtime_backtest import active_backtests
        
        strategy_tasks = []
        
        for task_id, status in active_backtests.items():
            # 检查是否为该策略的回测任务（通过AI会话ID或其他标识）
            if hasattr(status, 'strategy_name') and status.strategy_name:
                strategy_tasks.append({
                    "task_id": task_id,
                    "status": status.status,
                    "progress": status.progress,
                    "started_at": status.started_at.isoformat() if status.started_at else None,
                    "completed_at": status.completed_at.isoformat() if status.completed_at else None,
                    "is_ai_strategy": getattr(status, 'is_ai_strategy', False)
                })
        
        return strategy_tasks
    
    async def _log_integration_action(
        self,
        db: AsyncSession,
        user_id: int,
        ai_session_id: str,
        strategy_id: int,
        task_id: str,
        action: str
    ):
        """记录集成操作日志"""
        try:
            log_data = {
                "action": action,
                "user_id": user_id,
                "ai_session_id": ai_session_id,
                "strategy_id": strategy_id,
                "backtest_task_id": task_id,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"AI策略回测集成操作: {json.dumps(log_data, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"记录集成操作日志失败: {e}")


# 全局服务实例
ai_strategy_backtest_integration = AIStrategyBacktestIntegrationService()