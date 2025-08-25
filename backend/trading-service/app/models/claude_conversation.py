"""
Claude对话数据模型

存储用户与Claude AI的对话历史和上下文信息
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ClaudeConversation(Base):
    """Claude对话记录表"""
    
    __tablename__ = "claude_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # 关联用户服务的用户ID
    session_id = Column(String(100), nullable=False, index=True)  # 会话ID
    message_type = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)  # 消息内容
    context = Column(Text, nullable=True)  # JSON格式的上下文信息
    tokens_used = Column(Integer, default=0)  # 使用的token数量
    model = Column(String(50), default="claude-3-5-sonnet-20241022")  # 使用的模型
    response_time_ms = Column(Integer, default=0)  # 响应时间(毫秒)
    success = Column(Boolean, default=True)  # 请求是否成功
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ClaudeConversation(id={self.id}, user_id={self.user_id}, session_id='{self.session_id}', type='{self.message_type}')>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "message_type": self.message_type,
            "content": self.content,
            "context": self.context,
            "tokens_used": self.tokens_used,
            "model": self.model,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ClaudeUsage(Base):
    """Claude使用统计表"""
    
    __tablename__ = "claude_usage_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # 关联用户服务的用户ID
    feature_type = Column(String(50), nullable=False, index=True)  # 功能类型: 'chat', 'strategy_gen', 'analysis'
    input_tokens = Column(Integer, nullable=False, default=0)  # 输入token数
    output_tokens = Column(Integer, nullable=False, default=0)  # 输出token数
    api_cost = Column(String(20), default="0.000000")  # API成本 (存储为字符串保持精度)
    model_used = Column(String(50), default="claude-3-5-sonnet-20241022")  # 使用的模型
    response_time_ms = Column(Integer, default=0)  # 响应时间
    success = Column(Boolean, default=True)  # 是否成功
    request_date = Column(DateTime(timezone=True), server_default=func.now())  # 请求日期
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ClaudeUsage(id={self.id}, user_id={self.user_id}, feature='{self.feature_type}', tokens={self.input_tokens + self.output_tokens})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "feature_type": self.feature_type,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "api_cost": self.api_cost,
            "model_used": self.model_used,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "request_date": self.request_date.isoformat() if self.request_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class GeneratedStrategy(Base):
    """AI生成的策略表"""
    
    __tablename__ = "generated_strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # 关联用户服务的用户ID
    prompt = Column(Text, nullable=False)  # 用户的原始请求
    generated_code = Column(Text, nullable=False)  # 生成的策略代码
    explanation = Column(Text, nullable=True)  # 策略说明
    parameters = Column(Text, nullable=True)  # JSON格式的参数配置
    safety_check_passed = Column(Boolean, default=False)  # 安全检查是否通过
    is_used = Column(Boolean, default=False)  # 是否被用户使用
    performance_rating = Column(Integer, nullable=True)  # 用户评分 (1-5)
    tokens_used = Column(Integer, default=0)  # 生成时使用的token数
    generation_time_ms = Column(Integer, default=0)  # 生成耗时
    model_used = Column(String(50), default="claude-3-5-sonnet-20241022")  # 使用的模型
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<GeneratedStrategy(id={self.id}, user_id={self.user_id}, used={self.is_used})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "prompt": self.prompt,
            "generated_code": self.generated_code,
            "explanation": self.explanation,
            "parameters": self.parameters,
            "safety_check_passed": self.safety_check_passed,
            "is_used": self.is_used,
            "performance_rating": self.performance_rating,
            "tokens_used": self.tokens_used,
            "generation_time_ms": self.generation_time_ms,
            "model_used": self.model_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AIChatSession(Base):
    """AI聊天会话表"""
    
    __tablename__ = "ai_chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, unique=True, index=True)  # UUID会话ID
    user_id = Column(Integer, nullable=False, index=True)  # 关联用户服务的用户ID
    name = Column(String(100), nullable=False)  # 会话名称
    description = Column(Text, nullable=True)  # 会话描述
    ai_mode = Column(String(20), nullable=False, index=True)  # 'developer', 'trader'
    session_type = Column(String(20), nullable=False, index=True)  # 'strategy', 'indicator', 'general'
    status = Column(String(20), default="active", index=True)  # 'active', 'completed', 'archived'
    progress = Column(Integer, default=0)  # 完成进度百分比 (0-100)
    message_count = Column(Integer, default=0)  # 消息数量
    total_tokens = Column(Integer, default=0)  # 总token使用量
    total_cost = Column(Float, default=0.0)  # 总消耗金额
    last_message_content = Column(Text, nullable=True)  # 最后一条消息内容 (用于预览)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())  # 最后活动时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AIChatSession(id={self.id}, session_id='{self.session_id}', name='{self.name}', mode='{self.ai_mode}')>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "ai_mode": self.ai_mode,
            "session_type": self.session_type,
            "status": self.status,
            "progress": self.progress,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "last_message": self.last_message_content,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }