"""
AI策略进化系统
基于历史回测结果和市场表现，智能优化策略参数和逻辑
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from loguru import logger

from app.models.strategies import Strategy
from app.models.backtests import Backtest
from app.models.claude_conversation import ClaudeConversation
from app.services.claude_account_service import claude_account_service
from app.core.claude_client import ClaudeClient


class AIStrategyEvolutionService:
    """AI策略进化服务 - 让AI学习策略表现并自动优化"""
    
    def __init__(self):
        self.evolution_prompt = """
你是一位专业的量化交易策略优化专家。基于以下策略的历史表现数据，
请分析策略的优缺点，并提出具体的改进建议。

策略基本信息：
- 策略名称: {strategy_name}
- 策略类型: {strategy_type}
- 创建时间: {created_at}

历史回测结果分析：
{backtest_results}

市场环境分析：
{market_conditions}

请提供以下分析：
1. **性能问题诊断**: 识别策略在什么市场条件下表现不佳
2. **参数优化建议**: 具体的参数调整方案
3. **逻辑改进方案**: 信号生成逻辑的改进建议
4. **风险控制增强**: 风险管理机制的优化
5. **适应性增强**: 如何让策略更好适应不同市场环境

请提供具体可执行的优化方案，包括代码修改建议。
"""

    async def analyze_strategy_performance(
        self, 
        strategy_id: int,
        db: AsyncSession,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """分析策略历史表现"""
        try:
            # 获取策略信息
            strategy_query = select(Strategy).where(Strategy.id == strategy_id)
            strategy_result = await db.execute(strategy_query)
            strategy = strategy_result.scalar_one_or_none()
            
            if not strategy:
                return {"error": "策略不存在"}
            
            # 获取历史回测结果
            cutoff_date = datetime.now() - timedelta(days=lookback_days)
            backtest_query = select(Backtest).where(
                and_(
                    Backtest.strategy_id == strategy_id,
                    Backtest.created_at >= cutoff_date
                )
            ).order_by(desc(Backtest.created_at)).limit(10)
            
            backtest_result = await db.execute(backtest_query)
            backtests = backtest_result.scalars().all()
            
            # 分析回测结果
            performance_data = self._analyze_backtest_results(backtests)
            
            return {
                "strategy": {
                    "id": strategy.id,
                    "name": strategy.name,
                    "type": strategy.strategy_type,
                    "created_at": strategy.created_at
                },
                "performance_analysis": performance_data,
                "backtest_count": len(backtests),
                "analysis_period": f"{lookback_days}天"
            }
            
        except Exception as e:
            logger.error(f"策略性能分析失败: {e}")
            return {"error": str(e)}
    
    def _analyze_backtest_results(self, backtests: List[Backtest]) -> Dict[str, Any]:
        """分析回测结果数据"""
        if not backtests:
            return {"message": "暂无回测数据"}
        
        total_returns = []
        max_drawdowns = []
        sharpe_ratios = []
        win_rates = []
        
        for backtest in backtests:
            if backtest.results:
                results = json.loads(backtest.results)
                total_returns.append(results.get('total_return', 0))
                max_drawdowns.append(abs(results.get('max_drawdown', 0)))
                sharpe_ratios.append(results.get('sharpe_ratio', 0))
                win_rates.append(results.get('win_rate', 0))
        
        # 计算性能指标
        avg_return = sum(total_returns) / len(total_returns) if total_returns else 0
        avg_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
        avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0
        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0
        
        # 性能稳定性分析
        return_volatility = self._calculate_volatility(total_returns)
        
        return {
            "avg_return": round(avg_return, 2),
            "avg_drawdown": round(avg_drawdown, 2),
            "avg_sharpe_ratio": round(avg_sharpe, 2),
            "avg_win_rate": round(avg_win_rate, 2),
            "return_volatility": round(return_volatility, 2),
            "performance_trend": self._analyze_performance_trend(total_returns),
            "risk_level": self._assess_risk_level(avg_drawdown, return_volatility)
        }
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """计算收益率波动性"""
        if len(returns) < 2:
            return 0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        return variance ** 0.5
    
    def _analyze_performance_trend(self, returns: List[float]) -> str:
        """分析性能趋势"""
        if len(returns) < 3:
            return "数据不足"
        
        recent_avg = sum(returns[:3]) / 3  # 最近3次
        older_avg = sum(returns[3:]) / len(returns[3:]) if len(returns) > 3 else recent_avg
        
        if recent_avg > older_avg * 1.1:
            return "改善中"
        elif recent_avg < older_avg * 0.9:
            return "恶化中"
        else:
            return "稳定"
    
    def _assess_risk_level(self, avg_drawdown: float, volatility: float) -> str:
        """评估风险等级"""
        risk_score = avg_drawdown * 0.6 + volatility * 0.4
        
        if risk_score > 15:
            return "高风险"
        elif risk_score > 8:
            return "中等风险"
        else:
            return "低风险"
    
    async def generate_optimization_suggestions(
        self,
        strategy_id: int,
        performance_data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """使用AI生成优化建议"""
        try:
            claude_client = await self._get_claude_client()
            if not claude_client:
                return {"error": "AI服务不可用"}
            
            # 构建分析提示
            strategy_info = performance_data.get('strategy', {})
            perf_analysis = performance_data.get('performance_analysis', {})
            
            # 获取市场环境数据
            market_conditions = await self._get_market_conditions(db)
            
            prompt = self.evolution_prompt.format(
                strategy_name=strategy_info.get('name', '未知策略'),
                strategy_type=strategy_info.get('type', '未知类型'),
                created_at=strategy_info.get('created_at', '未知时间'),
                backtest_results=json.dumps(perf_analysis, indent=2, ensure_ascii=False),
                market_conditions=json.dumps(market_conditions, indent=2, ensure_ascii=False)
            )
            
            # 调用Claude分析
            response = await claude_client.chat_completion([{
                "role": "user",
                "content": prompt
            }])
            
            optimization_suggestions = response.get('content', '')
            
            # 保存分析结果
            await self._save_evolution_analysis(
                strategy_id, 
                performance_data,
                optimization_suggestions,
                db
            )
            
            return {
                "suggestions": optimization_suggestions,
                "analysis_timestamp": datetime.now(),
                "performance_summary": perf_analysis
            }
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            return {"error": str(e)}
    
    async def _get_claude_client(self) -> Optional[ClaudeClient]:
        """获取Claude客户端"""
        try:
            account = await claude_account_service.select_best_account()
            if not account:
                return None
            
            decrypted_api_key = await claude_account_service.get_decrypted_api_key(account.id)
            if not decrypted_api_key:
                return None
            
            return ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120
            )
        except Exception as e:
            logger.error(f"获取Claude客户端失败: {e}")
            return None
    
    async def _get_market_conditions(self, db: AsyncSession) -> Dict[str, Any]:
        """获取当前市场环境数据"""
        # 这里可以集成实时市场数据分析
        # 暂时返回模拟数据结构
        return {
            "market_trend": "震荡",
            "volatility_level": "中等",
            "volume_profile": "正常",
            "recent_events": "无重大事件"
        }
    
    async def _save_evolution_analysis(
        self,
        strategy_id: int,
        performance_data: Dict[str, Any],
        suggestions: str,
        db: AsyncSession
    ):
        """保存进化分析结果"""
        try:
            # 创建进化分析记录
            evolution_record = ClaudeConversation(
                user_id=1,  # 系统用户
                session_id=f"evolution_{strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                message_type="evolution_analysis",
                content=json.dumps({
                    "strategy_id": strategy_id,
                    "performance_data": performance_data,
                    "optimization_suggestions": suggestions,
                    "analysis_type": "strategy_evolution"
                }, ensure_ascii=False),
                ai_mode="evolution",
                session_type="optimization"
            )
            
            db.add(evolution_record)
            await db.commit()
            
        except Exception as e:
            logger.error(f"保存进化分析失败: {e}")


# 全局实例
ai_strategy_evolution_service = AIStrategyEvolutionService()