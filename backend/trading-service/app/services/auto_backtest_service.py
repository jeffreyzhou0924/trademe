"""
自动回测服务

为AI生成的策略提供自动化回测功能，集成现有回测引擎
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger

from app.services.backtest_service import BacktestEngine, BacktestService
from app.services.strategy_template_validator import StrategyTemplateValidator


def calculate_performance_grade(performance: Dict[str, Any]) -> str:
    """计算策略性能等级"""
    score = 0
    
    # 收益率评分 (30%)
    total_return = performance.get('total_return', 0)
    if total_return > 0.5:  # >50%
        score += 30
    elif total_return > 0.3:  # >30%
        score += 25
    elif total_return > 0.15:  # >15%
        score += 20
    elif total_return > 0.05:  # >5%
        score += 15
    elif total_return > 0:  # >0%
        score += 10
    
    # 夏普比率评分 (25%)
    sharpe_ratio = performance.get('sharpe_ratio', 0)
    if sharpe_ratio > 2:
        score += 25
    elif sharpe_ratio > 1.5:
        score += 20
    elif sharpe_ratio > 1:
        score += 15
    elif sharpe_ratio > 0.5:
        score += 10
    elif sharpe_ratio > 0:
        score += 5
    
    # 最大回撤评分 (25%)
    max_drawdown = abs(performance.get('max_drawdown', 1))
    if max_drawdown < 0.05:  # <5%
        score += 25
    elif max_drawdown < 0.1:  # <10%
        score += 20
    elif max_drawdown < 0.15:  # <15%
        score += 15
    elif max_drawdown < 0.2:  # <20%
        score += 10
    elif max_drawdown < 0.3:  # <30%
        score += 5
    
    # 胜率评分 (20%)
    win_rate = performance.get('win_rate', 0)
    if win_rate > 0.7:  # >70%
        score += 20
    elif win_rate > 0.6:  # >60%
        score += 15
    elif win_rate > 0.5:  # >50%
        score += 10
    elif win_rate > 0.4:  # >40%
        score += 5
    
    # 等级划分
    if score >= 85:
        return "A+"
    elif score >= 75:
        return "A"
    elif score >= 65:
        return "B+"
    elif score >= 55:
        return "B"
    elif score >= 45:
        return "C+"
    elif score >= 35:
        return "C"
    else:
        return "D"


def check_performance_targets(performance: Dict[str, Any], intent: Dict[str, Any]) -> bool:
    """检查性能是否达到预期目标"""
    try:
        # 基本合格标准
        basic_criteria = [
            performance.get('total_return', 0) > 0,  # 正收益
            performance.get('sharpe_ratio', 0) > 0.5,  # 夏普比率>0.5
            abs(performance.get('max_drawdown', 1)) < 0.3,  # 回撤<30%
        ]
        
        if not all(basic_criteria):
            return False
        
        # 根据用户期望检查
        expected_return = intent.get('expected_return', 10) / 100  # 转换为小数
        if performance.get('total_return', 0) < expected_return * 0.8:  # 允许20%偏差
            return False
        
        max_acceptable_drawdown = intent.get('max_drawdown', 20) / 100
        if abs(performance.get('max_drawdown', 1)) > max_acceptable_drawdown:
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"性能目标检查异常: {e}")
        return False


class AutoBacktestService:
    """自动回测服务"""
    
    DEFAULT_BACKTEST_CONFIG = {
        "initial_capital": 10000,
        "days_back": 30,
        "symbol": "BTC-USDT-SWAP",
        "exchange": "okx",
        "timeframe": "1h"
    }
    
    @staticmethod
    async def auto_backtest_strategy(
        strategy_code: str,
        intent: Dict[str, Any],
        user_id: int,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """自动执行策略回测"""
        
        backtest_id = str(uuid.uuid4())
        logger.info(f"开始自动回测 {backtest_id} for user {user_id}")
        
        try:
            # 合并配置
            backtest_config = {**AutoBacktestService.DEFAULT_BACKTEST_CONFIG}
            if config:
                backtest_config.update(config)
            
            # 从意图中提取配置
            if intent.get("target_assets"):
                backtest_config["symbol"] = intent["target_assets"][0]
            
            # 设置回测时间范围
            end_date = datetime.now() - timedelta(days=1)
            start_date = end_date - timedelta(days=backtest_config["days_back"])
            
            # 创建模拟策略记录用于回测
            mock_strategy = type('MockStrategy', (), {
                'id': 999999,  # 临时ID
                'user_id': user_id,
                'code': strategy_code,
                'parameters': '{}',
                'name': 'AI生成策略-回测中'
            })
            
            # 执行回测
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                engine = BacktestEngine()
                
                # 使用增强版回测执行
                results = await AutoBacktestService._execute_enhanced_backtest(
                    engine=engine,
                    strategy_code=strategy_code,
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=backtest_config["initial_capital"],
                    symbol=backtest_config["symbol"],
                    exchange=backtest_config["exchange"],
                    timeframe=backtest_config["timeframe"],
                    db=db
                )
            
            # 计算性能等级
            performance_grade = calculate_performance_grade(results["performance"])
            
            # 检查是否达到预期
            meets_expectations = check_performance_targets(results["performance"], intent)
            
            # 生成回测报告
            report = await AutoBacktestService._generate_backtest_report(results, intent)
            
            logger.info(f"自动回测完成 {backtest_id}: grade={performance_grade}, meets_expectations={meets_expectations}")
            
            return {
                "backtest_id": backtest_id,
                "results": results,
                "performance_grade": performance_grade,
                "meets_expectations": meets_expectations,
                "report": report,
                "config": backtest_config,
                "execution_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"自动回测失败 {backtest_id}: {e}")
            return {
                "backtest_id": backtest_id,
                "error": str(e),
                "performance_grade": "F",
                "meets_expectations": False,
                "results": None
            }
    
    @staticmethod
    async def _execute_enhanced_backtest(
        engine: BacktestEngine,
        strategy_code: str,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        symbol: str,
        exchange: str,
        timeframe: str,
        db
    ) -> Dict[str, Any]:
        """执行增强版回测"""
        
        # 模拟策略对象
        mock_strategy = type('Strategy', (), {
            'id': 999999,
            'user_id': user_id,
            'code': strategy_code,
            'parameters': '{}',
            'name': 'AI生成策略'
        })()
        
        # 运行回测
        results = await engine.run_backtest(
            strategy_id=999999,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            db=db
        )
        
        return results
    
    @staticmethod
    async def _generate_backtest_report(
        results: Dict[str, Any],
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成回测报告"""
        
        performance = results.get("performance", {})
        
        # 基础报告信息
        report = {
            "summary": {
                "total_return": performance.get("total_return", 0),
                "annualized_return": performance.get("annualized_return", 0),
                "max_drawdown": performance.get("max_drawdown", 0),
                "sharpe_ratio": performance.get("sharpe_ratio", 0),
                "win_rate": performance.get("win_rate", 0),
                "total_trades": performance.get("total_trades", 0)
            },
            "risk_metrics": {
                "volatility": performance.get("volatility", 0),
                "sortino_ratio": performance.get("sortino_ratio", 0),
                "calmar_ratio": performance.get("calmar_ratio", 0),
                "var_95": performance.get("var_95", 0),
                "max_drawdown_duration": performance.get("max_drawdown_duration", 0)
            },
            "trading_stats": {
                "winning_trades": performance.get("winning_trades", 0),
                "losing_trades": performance.get("losing_trades", 0),
                "avg_win": performance.get("avg_win", 0),
                "avg_loss": performance.get("avg_loss", 0),
                "profit_factor": performance.get("profit_factor", 0)
            }
        }
        
        # 生成评估结果
        report["evaluation"] = {
            "grade": calculate_performance_grade(performance),
            "strengths": AutoBacktestService._identify_strengths(performance),
            "weaknesses": AutoBacktestService._identify_weaknesses(performance),
            "meets_targets": check_performance_targets(performance, intent)
        }
        
        # 添加可视化数据
        report["charts"] = {
            "equity_curve": results.get("equity_curve", []),
            "drawdown_curve": results.get("drawdown_curve", []),
            "monthly_returns": results.get("monthly_returns", []),
            "trade_distribution": results.get("trade_distribution", [])
        }
        
        return report
    
    @staticmethod
    def _identify_strengths(performance: Dict[str, Any]) -> List[str]:
        """识别策略优势"""
        strengths = []
        
        if performance.get("total_return", 0) > 0.2:
            strengths.append("收益率表现优秀")
        
        if performance.get("sharpe_ratio", 0) > 1.5:
            strengths.append("风险调整收益良好")
        
        if abs(performance.get("max_drawdown", 1)) < 0.1:
            strengths.append("回撤控制出色")
        
        if performance.get("win_rate", 0) > 0.6:
            strengths.append("胜率较高")
        
        if performance.get("profit_factor", 0) > 1.5:
            strengths.append("盈亏比健康")
        
        if performance.get("sortino_ratio", 0) > 1:
            strengths.append("下行风险控制良好")
        
        return strengths or ["策略基础框架完整"]
    
    @staticmethod
    def _identify_weaknesses(performance: Dict[str, Any]) -> List[str]:
        """识别策略弱点"""
        weaknesses = []
        
        if performance.get("total_return", 0) < 0:
            weaknesses.append("总收益为负，需要优化交易逻辑")
        
        if performance.get("sharpe_ratio", 0) < 0.5:
            weaknesses.append("风险调整收益偏低")
        
        if abs(performance.get("max_drawdown", 0)) > 0.25:
            weaknesses.append("最大回撤过大，需要加强风控")
        
        if performance.get("win_rate", 0) < 0.4:
            weaknesses.append("胜率偏低，建议优化入场条件")
        
        if performance.get("total_trades", 0) < 5:
            weaknesses.append("交易次数过少，可能信号生成不足")
        
        if performance.get("profit_factor", 0) < 1:
            weaknesses.append("平均亏损大于平均盈利")
        
        return weaknesses
    
    @staticmethod
    async def batch_backtest_comparison(
        strategy_codes: List[str],
        intent: Dict[str, Any],
        user_id: int
    ) -> Dict[str, Any]:
        """批量回测对比多个策略版本"""
        
        logger.info(f"开始批量回测 {len(strategy_codes)} 个策略版本")
        
        results = []
        tasks = []
        
        # 并发执行多个回测
        for i, code in enumerate(strategy_codes):
            task = AutoBacktestService.auto_backtest_strategy(
                strategy_code=code,
                intent=intent,
                user_id=user_id,
                config={"days_back": 15}  # 缩短回测时间用于快速对比
            )
            tasks.append(task)
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        valid_results = []
        failed_count = 0
        
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                failed_count += 1
                logger.error(f"批量回测第{i+1}个策略失败: {result}")
            else:
                valid_results.append({
                    "version": i + 1,
                    "grade": result.get("performance_grade", "F"),
                    "total_return": result.get("results", {}).get("performance", {}).get("total_return", 0),
                    "sharpe_ratio": result.get("results", {}).get("performance", {}).get("sharpe_ratio", 0),
                    "max_drawdown": result.get("results", {}).get("performance", {}).get("max_drawdown", 0),
                    "meets_expectations": result.get("meets_expectations", False)
                })
        
        # 找出最佳策略
        if valid_results:
            best_strategy = max(valid_results, key=lambda x: (
                x["meets_expectations"],
                x["total_return"],
                -abs(x["max_drawdown"])
            ))
        else:
            best_strategy = None
        
        return {
            "total_tested": len(strategy_codes),
            "successful": len(valid_results),
            "failed": failed_count,
            "results": valid_results,
            "best_strategy": best_strategy,
            "comparison_summary": {
                "avg_return": sum(r["total_return"] for r in valid_results) / len(valid_results) if valid_results else 0,
                "best_return": max(r["total_return"] for r in valid_results) if valid_results else 0,
                "success_rate": len([r for r in valid_results if r["meets_expectations"]]) / len(valid_results) if valid_results else 0
            }
        }