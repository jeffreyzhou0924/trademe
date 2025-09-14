"""
回测模型
"""

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Backtest(Base):
    """回测模型"""
    __tablename__ = "backtests"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Numeric(15, 2), nullable=False)
    final_capital = Column(Numeric(15, 2), nullable=True)
    total_return = Column(Numeric(8, 4), nullable=True)
    max_drawdown = Column(Numeric(8, 4), nullable=True)
    sharpe_ratio = Column(Numeric(6, 4), nullable=True)
    results = Column(Text, nullable=True)  # JSON string
    status = Column(String(20), default="RUNNING")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # AI策略回测专用字段
    ai_session_id = Column(String(100), nullable=True, index=True)  # AI会话ID
    is_ai_generated = Column(Boolean, default=False, index=True)     # 是否为AI生成策略的回测
    realtime_task_id = Column(String(100), nullable=True, index=True)  # 实时回测任务ID
    membership_level = Column(String(20), nullable=True)             # 用户会员级别
    ai_enhanced_results = Column(Text, nullable=True)                # AI增强的回测结果 (JSON)
    completed_at = Column(DateTime(timezone=True), nullable=True)    # 完成时间


class AIBacktestTask(Base):
    """AI回测任务表"""
    __tablename__ = "ai_backtest_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, nullable=False, index=True)  # UUID任务ID
    user_id = Column(Integer, nullable=False, index=True)
    ai_session_id = Column(String(100), nullable=True, index=True)  # AI会话ID
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)  # 关联的策略ID
    backtest_id = Column(Integer, ForeignKey("backtests.id"), nullable=True)   # 关联的回测ID
    
    # 任务配置信息
    strategy_name = Column(String(200), nullable=True)
    strategy_code = Column(Text, nullable=False)  # 策略代码
    config_data = Column(Text, nullable=True)     # 回测配置 (JSON)
    membership_level = Column(String(20), nullable=False)
    
    # 任务状态
    status = Column(String(20), default="running", index=True)  # running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100
    current_step = Column(String(200), nullable=True)
    logs = Column(Text, nullable=True)  # JSON格式的日志数组
    error_message = Column(Text, nullable=True)
    
    # 结果数据
    results_data = Column(Text, nullable=True)     # JSON格式的结果数据
    ai_score = Column(Numeric(5, 2), nullable=True)  # AI策略评分 (0-100)
    
    # 时间字段
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "ai_session_id": self.ai_session_id,
            "strategy_id": self.strategy_id,
            "backtest_id": self.backtest_id,
            "strategy_name": self.strategy_name,
            "status": self.status,
            "progress": self.progress,
            "current_step": self.current_step,
            "membership_level": self.membership_level,
            "ai_score": float(self.ai_score) if self.ai_score else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }