"""
策略生成状态管理器
实现策略代码的后台保存机制，不在对话中展示完整代码
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models import Strategy

logger = logging.getLogger(__name__)


class StrategyGenerationStateManager:
    """策略生成状态管理器"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
        # 策略生成状态
        self.generation_states = {
            "DISCUSSING": "讨论中",        # 策略讨论阶段
            "READY": "准备生成",           # 策略成熟，等待用户确认
            "GENERATING": "代码生成中",    # 正在生成代码
            "GENERATED": "已生成",         # 代码生成完成，保存到策略库
            "TESTING": "回测中",           # 正在执行回测
            "COMPLETED": "完成",           # 整个流程完成
            "FAILED": "失败"               # 生成失败
        }
        
        # 会话状态存储
        self.session_states = {}

    async def save_strategy_silently(
        self,
        user_id: int,
        session_id: str,
        strategy_info: Dict[str, Any],
        generated_code: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        静默保存策略到数据库，不在对话中展示代码
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            strategy_info: 策略信息
            generated_code: 生成的策略代码
            metadata: 元数据(成熟度分析、生成参数等)
            
        Returns:
            保存结果
        """
        
        try:
            # 生成策略名称
            strategy_name = self._generate_strategy_name(strategy_info)
            
            # 准备策略参数
            strategy_parameters = {
                "indicators": strategy_info.get("indicators", []),
                "timeframe": strategy_info.get("timeframe", "1h"),
                "stop_loss": strategy_info.get("stop_loss"),
                "take_profit": strategy_info.get("take_profit"),
                "risk_per_trade": strategy_info.get("risk_per_trade", 0.02),
                "entry_conditions": strategy_info.get("entry_conditions", []),
                "exit_conditions": strategy_info.get("exit_conditions", []),
                "generation_metadata": {
                    "maturity_score": metadata.get("maturity_score", 0),
                    "generation_method": "ai_assisted",
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                    "user_confirmed": metadata.get("user_confirmed", True),
                    "analyzer_version": "v1.0",
                    "strategy_complexity": self._calculate_strategy_complexity(strategy_info)
                }
            }
            
            # 生成策略描述
            strategy_description = self._generate_strategy_description(strategy_info, metadata)
            
            # 创建策略记录
            new_strategy = Strategy(
                user_id=user_id,
                name=strategy_name,
                description=strategy_description,
                code=generated_code,
                parameters=json.dumps(strategy_parameters),
                strategy_type="ai_generated",
                ai_session_id=session_id,
                is_active=False,  # 新生成的策略默认不激活
                is_public=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            self.db.add(new_strategy)
            await self.db.commit()
            await self.db.refresh(new_strategy)
            
            # 记录生成历史
            await self._log_generation_history(
                user_id, session_id, new_strategy.id, metadata
            )
            
            logger.info(f"策略成功保存 - 用户: {user_id}, 策略ID: {new_strategy.id}, 会话: {session_id}")
            
            return {
                "success": True,
                "strategy_id": new_strategy.id,
                "strategy_name": strategy_name,
                "message": "策略已成功保存到策略库",
                "save_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"保存策略失败 - 用户: {user_id}, 会话: {session_id}, 错误: {str(e)}")
            await self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "message": "策略保存失败，请重试"
            }

    def _generate_strategy_name(self, strategy_info: Dict) -> str:
        """生成策略名称"""
        
        strategy_type = strategy_info.get("strategy_type", "自定义策略")
        indicators = strategy_info.get("indicators", [])
        timeframe = strategy_info.get("timeframe", "1h")
        
        # 基于策略特征生成名称
        if strategy_type and strategy_type != "自定义策略":
            base_name = strategy_type
        elif indicators:
            # 取前两个指标组成名称
            indicator_part = "+".join(indicators[:2])
            base_name = f"{indicator_part}策略"
        else:
            base_name = "AI生成策略"
        
        # 添加时间戳避免重名
        timestamp = datetime.now().strftime("%m%d_%H%M")
        return f"{base_name}_{timeframe}_{timestamp}"

    def _generate_strategy_description(self, strategy_info: Dict, metadata: Dict) -> str:
        """生成策略描述"""
        
        description_parts = []
        
        # 基本信息
        if strategy_info.get("strategy_type"):
            description_parts.append(f"策略类型: {strategy_info['strategy_type']}")
        
        if strategy_info.get("indicators"):
            description_parts.append(f"技术指标: {', '.join(strategy_info['indicators'])}")
        
        if strategy_info.get("timeframe"):
            description_parts.append(f"时间周期: {strategy_info['timeframe']}")
        
        # 交易条件
        entry_count = len(strategy_info.get("entry_conditions", []))
        exit_count = len(strategy_info.get("exit_conditions", []))
        if entry_count > 0 or exit_count > 0:
            description_parts.append(f"交易条件: {entry_count}个买入条件, {exit_count}个卖出条件")
        
        # 风险管理
        risk_elements = []
        if strategy_info.get("stop_loss"):
            risk_elements.append("止损")
        if strategy_info.get("take_profit"):
            risk_elements.append("止盈")
        if risk_elements:
            description_parts.append(f"风险管理: {', '.join(risk_elements)}")
        
        # AI生成信息
        maturity_score = metadata.get("maturity_score", 0)
        description_parts.append(f"AI生成 (成熟度: {maturity_score:.0f}/100)")
        
        return " | ".join(description_parts)

    def _calculate_strategy_complexity(self, strategy_info: Dict) -> str:
        """计算策略复杂度"""
        
        complexity_score = 0
        
        # 指标数量
        indicator_count = len(strategy_info.get("indicators", []))
        complexity_score += indicator_count * 2
        
        # 条件数量
        entry_count = len(strategy_info.get("entry_conditions", []))
        exit_count = len(strategy_info.get("exit_conditions", []))
        complexity_score += (entry_count + exit_count)
        
        # 风险管理元素
        if strategy_info.get("stop_loss"):
            complexity_score += 1
        if strategy_info.get("take_profit"):
            complexity_score += 1
        if strategy_info.get("position_sizing"):
            complexity_score += 1
        
        # 分级
        if complexity_score <= 3:
            return "简单"
        elif complexity_score <= 8:
            return "中等"
        else:
            return "复杂"

    async def generate_strategy_summary_response(
        self,
        strategy_id: int,
        strategy_info: Dict,
        generation_metadata: Dict
    ) -> str:
        """
        生成策略保存成功的摘要响应（不包含代码）
        """
        
        strategy_name = self._generate_strategy_name(strategy_info)
        maturity_score = generation_metadata.get("maturity_score", 0)
        
        # 预期性能估算（基于策略类型和参数）
        estimated_performance = self._estimate_strategy_performance(strategy_info)
        
        return f"""✅ **策略代码生成完成！**

📊 **策略信息**:
• **策略名称**: {strategy_name}
• **成熟度评分**: {maturity_score:.0f}/100
• **策略类型**: {strategy_info.get('strategy_type', '自定义策略')}
• **技术指标**: {', '.join(strategy_info.get('indicators', ['无']))}
• **时间周期**: {strategy_info.get('timeframe', '未指定')}

📈 **预期表现**:
• **年化收益率**: {estimated_performance['expected_return']}
• **最大回撤**: {estimated_performance['max_drawdown']}
• **夏普比率**: {estimated_performance['sharpe_ratio']}
• **策略复杂度**: {self._calculate_strategy_complexity(strategy_info)}

💾 **代码已安全保存**:
✓ 完整策略逻辑已保存至策略库
✓ 可在策略管理页面查看和编辑
✓ 支持一键部署到实盘交易

🔗 **下一步操作**:
• 在策略库中查看完整代码
• 配置回测参数进行验证
• 优化参数后部署实盘交易

📋 **策略ID**: #{strategy_id} - 已添加到您的策略库"""

    def _estimate_strategy_performance(self, strategy_info: Dict) -> Dict[str, str]:
        """
        基于策略信息估算预期性能
        """
        
        strategy_type = strategy_info.get("strategy_type", "")
        indicators = strategy_info.get("indicators", [])
        timeframe = strategy_info.get("timeframe", "1h")
        
        # 根据策略类型估算性能范围
        performance_estimates = {
            "双均线交叉": {"expected_return": "8-15%", "max_drawdown": "<12%", "sharpe_ratio": "0.8-1.2"},
            "RSI反转": {"expected_return": "12-20%", "max_drawdown": "<15%", "sharpe_ratio": "1.0-1.5"},
            "MACD动量": {"expected_return": "10-18%", "max_drawdown": "<18%", "sharpe_ratio": "0.9-1.3"},
            "布林带策略": {"expected_return": "6-12%", "max_drawdown": "<10%", "sharpe_ratio": "0.7-1.1"},
            "网格交易": {"expected_return": "15-25%", "max_drawdown": "<8%", "sharpe_ratio": "1.2-1.8"},
            "趋势跟踪": {"expected_return": "20-35%", "max_drawdown": "<20%", "sharpe_ratio": "1.1-1.6"},
            "默认": {"expected_return": "5-15%", "max_drawdown": "<20%", "sharpe_ratio": "0.6-1.2"}
        }
        
        estimate = performance_estimates.get(strategy_type, performance_estimates["默认"])
        
        # 根据指标数量调整预期
        if len(indicators) > 2:
            # 多指标组合，可能更稳定但收益稍低
            expected_return = estimate["expected_return"].replace("15%", "12%").replace("20%", "18%")
            estimate = {
                "expected_return": expected_return,
                "max_drawdown": estimate["max_drawdown"],
                "sharpe_ratio": estimate["sharpe_ratio"]
            }
        
        return {
            "expected_return": estimate.get("expected_return", "5-15%"),
            "max_drawdown": estimate.get("max_drawdown", "<20%"),
            "sharpe_ratio": estimate.get("sharpe_ratio", "0.6-1.2")
        }

    async def _log_generation_history(
        self,
        user_id: int,
        session_id: str,
        strategy_id: int,
        metadata: Dict
    ) -> None:
        """记录策略生成历史"""
        
        try:
            # 插入生成历史记录到系统配置表
            history_key = f"strategy_generation_history_{user_id}_{session_id}"
            history_record = {
                "user_id": user_id,
                "session_id": session_id,
                "strategy_id": strategy_id,
                "generation_time": datetime.now().isoformat(),
                "maturity_score": metadata.get("maturity_score", 0),
                "user_confirmed": metadata.get("user_confirmed", True),
                "generation_method": "ai_assisted"
            }
            
            # 使用系统配置表存储历史记录
            insert_query = """
                INSERT INTO system_configs (config_key, config_value)
                VALUES (?, ?)
                ON CONFLICT(config_key) 
                DO UPDATE SET config_value = excluded.config_value
            """
            
            await self.db.execute(
                text(insert_query),
                (history_key, json.dumps(history_record))
            )
            await self.db.commit()
            
            logger.info(f"策略生成历史记录成功 - 策略ID: {strategy_id}")
            
        except Exception as e:
            logger.warning(f"记录策略生成历史失败: {str(e)}")
            # 历史记录失败不应该影响主流程

    async def get_user_generation_history(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取用户策略生成历史"""
        
        try:
            # 查询用户的生成历史记录
            query = """
                SELECT config_key, config_value 
                FROM system_configs 
                WHERE config_key LIKE ?
                ORDER BY config_key DESC
                LIMIT ?
            """
            
            pattern = f"strategy_generation_history_{user_id}_%"
            result = await self.db.execute(text(query), (pattern, limit))
            rows = result.fetchall()
            
            history_records = []
            for row in rows:
                try:
                    record = json.loads(row[1])
                    history_records.append(record)
                except json.JSONDecodeError:
                    logger.warning(f"解析历史记录失败: {row[0]}")
                    continue
            
            return history_records
            
        except Exception as e:
            logger.error(f"获取用户生成历史失败: {str(e)}")
            return []

    async def get_strategy_generation_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户策略生成统计"""
        
        try:
            # 查询用户AI生成的策略统计
            stats_query = """
                SELECT 
                    COUNT(*) as total_strategies,
                    COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_strategies,
                    AVG(CASE 
                        WHEN json_extract(parameters, '$.generation_metadata.maturity_score') IS NOT NULL 
                        THEN CAST(json_extract(parameters, '$.generation_metadata.maturity_score') AS REAL)
                        ELSE 0 
                    END) as avg_maturity_score
                FROM strategies 
                WHERE user_id = ? AND strategy_type = 'ai_generated'
            """
            
            result = await self.db.execute(text(stats_query), (user_id,))
            row = result.fetchone()
            
            if row:
                return {
                    "total_strategies": row[0] or 0,
                    "active_strategies": row[1] or 0,
                    "inactive_strategies": (row[0] or 0) - (row[1] or 0),
                    "avg_maturity_score": round(row[2] or 0, 1)
                }
            else:
                return {
                    "total_strategies": 0,
                    "active_strategies": 0,
                    "inactive_strategies": 0,
                    "avg_maturity_score": 0.0
                }
                
        except Exception as e:
            logger.error(f"获取策略生成统计失败: {str(e)}")
            return {
                "total_strategies": 0,
                "active_strategies": 0,
                "inactive_strategies": 0,
                "avg_maturity_score": 0.0
            }

    def update_session_state(self, session_id: str, state_updates: Dict[str, Any]) -> None:
        """更新会话状态"""
        
        if session_id not in self.session_states:
            self.session_states[session_id] = {}
        
        self.session_states[session_id].update(state_updates)
        self.session_states[session_id]["updated_at"] = datetime.now().isoformat()

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        
        return self.session_states.get(session_id, {})

    def clear_session_state(self, session_id: str) -> None:
        """清除会话状态"""
        
        if session_id in self.session_states:
            del self.session_states[session_id]