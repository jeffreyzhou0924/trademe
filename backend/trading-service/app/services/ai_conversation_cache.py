"""
AI对话缓存服务
专门处理Claude对话历史、上下文管理、智能摘要、会话恢复等缓存需求
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from enum import Enum

from .redis_cache_service import RedisCacheService, CacheConfig, CompressionType

logger = logging.getLogger(__name__)

class SessionType(Enum):
    """会话类型"""
    STRATEGY = "strategy"
    INDICATOR = "indicator"
    DEBUGGING = "debugging"
    GENERAL = "general"
    ANALYSIS = "analysis"

class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

@dataclass
class ConversationMessage:
    """对话消息"""
    role: MessageRole
    content: str
    timestamp: datetime
    message_id: str = None
    metadata: Dict[str, Any] = None
    token_count: Optional[int] = None
    
    def __post_init__(self):
        if self.message_id is None:
            self.message_id = hashlib.md5(
                f"{self.role.value}:{self.content}:{self.timestamp.isoformat()}".encode()
            ).hexdigest()[:12]
        
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    user_id: int
    session_type: SessionType
    messages: List[ConversationMessage]
    created_at: datetime
    last_updated: datetime
    total_tokens: int = 0
    compressed_history: Optional[str] = None
    context_summary: Optional[str] = None
    importance_score: float = 0.0
    
    def add_message(self, message: ConversationMessage):
        """添加消息"""
        self.messages.append(message)
        self.last_updated = datetime.utcnow()
        if message.token_count:
            self.total_tokens += message.token_count

@dataclass
class ContextSummary:
    """上下文摘要"""
    session_id: str
    summary_content: str
    original_message_count: int
    compressed_token_count: int
    compression_ratio: float
    created_at: datetime
    key_topics: List[str] = None
    important_decisions: List[str] = None
    
    def __post_init__(self):
        if self.key_topics is None:
            self.key_topics = []
        if self.important_decisions is None:
            self.important_decisions = []

class AIConversationCacheService:
    """AI对话缓存服务"""
    
    def __init__(self, cache_service: RedisCacheService):
        self.cache = cache_service
        self.max_context_messages = 50  # 最大上下文消息数量
        self.compression_threshold = 20  # 触发压缩的消息数量阈值
        
        # 设置缓存配置
        self._setup_cache_configs()
        
    def _setup_cache_configs(self):
        """设置缓存配置"""
        self.cache.cache_configs.update({
            "ai_conversations": CacheConfig(
                ttl=3600,  # 对话缓存1小时
                namespace="ai_conversation",
                compression=CompressionType.GZIP
            ),
            "conversation_context": CacheConfig(
                ttl=1800,  # 上下文缓存30分钟
                namespace="ai_context",
                compression=CompressionType.GZIP
            ),
            "ai_summaries": CacheConfig(
                ttl=7200,  # 摘要缓存2小时
                namespace="ai_summary"
            ),
            "ai_responses": CacheConfig(
                ttl=300,  # AI响应缓存5分钟
                namespace="ai_response",
                compression=CompressionType.JSON
            ),
            "user_ai_sessions": CacheConfig(
                ttl=86400,  # 用户AI会话列表24小时
                namespace="user_ai_sessions"
            ),
            "context_embeddings": CacheConfig(
                ttl=3600,  # 上下文向量1小时
                namespace="ai_embeddings",
                compression=CompressionType.PICKLE
            ),
            "ai_model_cache": CacheConfig(
                ttl=600,  # 模型响应缓存10分钟
                namespace="ai_model"
            )
        })
    
    async def create_conversation(self, user_id: int, session_type: SessionType,
                                initial_message: Optional[str] = None) -> ConversationContext:
        """创建新对话"""
        try:
            session_id = self._generate_session_id(user_id, session_type)
            current_time = datetime.utcnow()
            
            messages = []
            if initial_message:
                message = ConversationMessage(
                    role=MessageRole.USER,
                    content=initial_message,
                    timestamp=current_time
                )
                messages.append(message)
            
            context = ConversationContext(
                session_id=session_id,
                user_id=user_id,
                session_type=session_type,
                messages=messages,
                created_at=current_time,
                last_updated=current_time
            )
            
            await self._cache_conversation_context(context)
            
            # 更新用户AI会话列表
            await self._update_user_ai_sessions(user_id, session_id, session_type)
            
            logger.info(f"创建AI对话成功: user_id={user_id}, session_id={session_id}")
            return context
            
        except Exception as e:
            logger.error(f"创建AI对话失败: {e}")
            raise
    
    async def get_conversation_context(self, session_id: str, 
                                     include_full_history: bool = False) -> Optional[ConversationContext]:
        """获取对话上下文"""
        try:
            key = f"context:{session_id}"
            data = await self.cache.get(key, "conversation_context")
            
            if not data:
                return None
            
            # 转换数据
            data = self._deserialize_conversation_context(data)
            context = ConversationContext(**data)
            
            # 如果需要完整历史，加载压缩的历史消息
            if include_full_history and context.compressed_history:
                full_messages = await self._load_compressed_history(session_id)
                if full_messages:
                    context.messages = full_messages + context.messages
            
            return context
            
        except Exception as e:
            logger.error(f"获取对话上下文失败: {e}")
            return None
    
    async def add_message_to_conversation(self, session_id: str, 
                                        role: MessageRole, content: str,
                                        metadata: Optional[Dict[str, Any]] = None,
                                        token_count: Optional[int] = None) -> bool:
        """添加消息到对话"""
        try:
            context = await self.get_conversation_context(session_id)
            if not context:
                logger.warning(f"对话上下文不存在: {session_id}")
                return False
            
            message = ConversationMessage(
                role=role,
                content=content,
                timestamp=datetime.utcnow(),
                metadata=metadata or {},
                token_count=token_count
            )
            
            context.add_message(message)
            
            # 检查是否需要压缩历史
            if len(context.messages) > self.compression_threshold:
                await self._compress_conversation_history(context)
            
            await self._cache_conversation_context(context)
            
            # 缓存最新的AI响应（如果是助手消息）
            if role == MessageRole.ASSISTANT:
                await self._cache_ai_response(session_id, content, metadata)
            
            return True
            
        except Exception as e:
            logger.error(f"添加消息到对话失败: {e}")
            return False
    
    async def get_context_for_ai_request(self, session_id: str, 
                                       max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """获取用于AI请求的上下文"""
        try:
            context = await self.get_conversation_context(session_id)
            if not context:
                return []
            
            # 使用智能上下文管理
            optimized_context = await self._get_optimized_context(
                context, max_messages or self.max_context_messages
            )
            
            # 转换为AI API格式
            ai_context = []
            
            # 如果有上下文摘要，先添加系统消息
            if context.context_summary:
                ai_context.append({
                    "role": "system",
                    "content": f"上下文摘要：{context.context_summary}"
                })
            
            # 添加对话消息
            for message in optimized_context:
                ai_context.append({
                    "role": message.role.value,
                    "content": message.content
                })
            
            return ai_context
            
        except Exception as e:
            logger.error(f"获取AI请求上下文失败: {e}")
            return []
    
    async def cache_ai_response(self, session_id: str, user_query: str, 
                              ai_response: str, model_info: Dict[str, Any],
                              token_usage: Dict[str, int]) -> bool:
        """缓存AI响应"""
        try:
            # 生成查询哈希作为缓存键
            query_hash = hashlib.md5(user_query.encode()).hexdigest()
            cache_key = f"response:{session_id}:{query_hash}"
            
            response_data = {
                'user_query': user_query,
                'ai_response': ai_response,
                'model_info': model_info,
                'token_usage': token_usage,
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id
            }
            
            return await self.cache.set(cache_key, response_data, "ai_responses")
            
        except Exception as e:
            logger.error(f"缓存AI响应失败: {e}")
            return False
    
    async def get_cached_ai_response(self, session_id: str, user_query: str) -> Optional[Dict[str, Any]]:
        """获取缓存的AI响应"""
        try:
            query_hash = hashlib.md5(user_query.encode()).hexdigest()
            cache_key = f"response:{session_id}:{query_hash}"
            
            return await self.cache.get(cache_key, "ai_responses")
            
        except Exception as e:
            logger.error(f"获取缓存AI响应失败: {e}")
            return None
    
    async def create_conversation_summary(self, session_id: str, 
                                        summary_content: str,
                                        original_count: int,
                                        compressed_tokens: int) -> ContextSummary:
        """创建对话摘要"""
        try:
            compression_ratio = compressed_tokens / (original_count * 50) if original_count > 0 else 0
            
            summary = ContextSummary(
                session_id=session_id,
                summary_content=summary_content,
                original_message_count=original_count,
                compressed_token_count=compressed_tokens,
                compression_ratio=compression_ratio,
                created_at=datetime.utcnow()
            )
            
            # 提取关键主题和决策
            summary.key_topics = self._extract_key_topics(summary_content)
            summary.important_decisions = self._extract_important_decisions(summary_content)
            
            await self._cache_conversation_summary(summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"创建对话摘要失败: {e}")
            raise
    
    async def get_conversation_summary(self, session_id: str) -> Optional[ContextSummary]:
        """获取对话摘要"""
        try:
            key = f"summary:{session_id}"
            data = await self.cache.get(key, "ai_summaries")
            
            if not data:
                return None
            
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            return ContextSummary(**data)
            
        except Exception as e:
            logger.error(f"获取对话摘要失败: {e}")
            return None
    
    async def get_user_ai_sessions(self, user_id: int, 
                                 session_type: Optional[SessionType] = None) -> List[Dict[str, Any]]:
        """获取用户AI会话列表"""
        try:
            key = f"user_sessions:{user_id}"
            sessions = await self.cache.get(key, "user_ai_sessions") or []
            
            if session_type:
                sessions = [s for s in sessions if s.get('session_type') == session_type.value]
            
            return sessions
            
        except Exception as e:
            logger.error(f"获取用户AI会话列表失败: {e}")
            return []
    
    async def delete_conversation(self, session_id: str) -> bool:
        """删除对话"""
        try:
            # 删除对话上下文
            context_key = f"context:{session_id}"
            await self.cache.delete(context_key, "conversation_context")
            
            # 删除对话摘要
            summary_key = f"summary:{session_id}"
            await self.cache.delete(summary_key, "ai_summaries")
            
            # 删除压缩历史
            history_key = f"history:{session_id}"
            await self.cache.delete(history_key, "ai_conversations")
            
            logger.info(f"删除对话成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
            return False
    
    async def cleanup_expired_conversations(self, days: int = 7) -> int:
        """清理过期对话"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            cleaned_count = 0
            
            # 这里应该实现更智能的清理逻辑
            # 简化实现：清理所有AI对话相关的命名空间
            
            namespaces = [
                "ai_conversation",
                "ai_context", 
                "ai_summary",
                "ai_response"
            ]
            
            for namespace in namespaces:
                count = await self.cache.clear_namespace(namespace)
                cleaned_count += count
            
            logger.info(f"清理过期对话完成，共清理 {cleaned_count} 个缓存项")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理过期对话失败: {e}")
            return 0
    
    def _generate_session_id(self, user_id: int, session_type: SessionType) -> str:
        """生成会话ID"""
        timestamp = datetime.utcnow().timestamp()
        data = f"ai:{user_id}:{session_type.value}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _cache_conversation_context(self, context: ConversationContext):
        """缓存对话上下文"""
        key = f"context:{context.session_id}"
        data = self._serialize_conversation_context(context)
        
        await self.cache.set(key, data, "conversation_context")
    
    def _serialize_conversation_context(self, context: ConversationContext) -> Dict[str, Any]:
        """序列化对话上下文"""
        data = asdict(context)
        
        # 转换时间字段
        data['created_at'] = context.created_at.isoformat()
        data['last_updated'] = context.last_updated.isoformat()
        data['session_type'] = context.session_type.value
        
        # 序列化消息
        messages_data = []
        for message in context.messages:
            msg_data = asdict(message)
            msg_data['timestamp'] = message.timestamp.isoformat()
            msg_data['role'] = message.role.value
            messages_data.append(msg_data)
        
        data['messages'] = messages_data
        return data
    
    def _deserialize_conversation_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """反序列化对话上下文"""
        # 转换时间字段
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        data['session_type'] = SessionType(data['session_type'])
        
        # 反序列化消息
        messages = []
        for msg_data in data['messages']:
            msg_data['timestamp'] = datetime.fromisoformat(msg_data['timestamp'])
            msg_data['role'] = MessageRole(msg_data['role'])
            messages.append(ConversationMessage(**msg_data))
        
        data['messages'] = messages
        return data
    
    async def _compress_conversation_history(self, context: ConversationContext):
        """压缩对话历史"""
        try:
            if len(context.messages) <= self.compression_threshold:
                return
            
            # 保留最近的消息，压缩较早的消息
            recent_messages = context.messages[-10:]  # 保留最近10条
            old_messages = context.messages[:-10]     # 压缩更早的消息
            
            # 存储压缩历史
            history_key = f"history:{context.session_id}"
            compressed_data = self._serialize_messages(old_messages)
            await self.cache.set(history_key, compressed_data, "ai_conversations")
            
            # 更新上下文
            context.messages = recent_messages
            context.compressed_history = history_key
            
            logger.debug(f"压缩对话历史: {context.session_id}, 压缩消息数: {len(old_messages)}")
            
        except Exception as e:
            logger.error(f"压缩对话历史失败: {e}")
    
    async def _load_compressed_history(self, session_id: str) -> List[ConversationMessage]:
        """加载压缩的历史消息"""
        try:
            history_key = f"history:{session_id}"
            data = await self.cache.get(history_key, "ai_conversations")
            
            if not data:
                return []
            
            return self._deserialize_messages(data)
            
        except Exception as e:
            logger.error(f"加载压缩历史失败: {e}")
            return []
    
    def _serialize_messages(self, messages: List[ConversationMessage]) -> List[Dict[str, Any]]:
        """序列化消息列表"""
        return [
            {
                'role': msg.role.value,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'message_id': msg.message_id,
                'metadata': msg.metadata,
                'token_count': msg.token_count
            }
            for msg in messages
        ]
    
    def _deserialize_messages(self, data: List[Dict[str, Any]]) -> List[ConversationMessage]:
        """反序列化消息列表"""
        messages = []
        for msg_data in data:
            msg_data['role'] = MessageRole(msg_data['role'])
            msg_data['timestamp'] = datetime.fromisoformat(msg_data['timestamp'])
            messages.append(ConversationMessage(**msg_data))
        return messages
    
    async def _get_optimized_context(self, context: ConversationContext, 
                                   max_messages: int) -> List[ConversationMessage]:
        """获取优化的上下文"""
        if len(context.messages) <= max_messages:
            return context.messages
        
        # 智能上下文选择算法
        # 优先保留：
        # 1. 最近的消息
        # 2. 包含重要关键词的消息
        # 3. 用户的问题和AI的回答配对
        
        recent_messages = context.messages[-max_messages//2:]  # 一半是最近消息
        
        # 从较早的消息中选择重要的
        earlier_messages = context.messages[:-max_messages//2]
        important_messages = self._select_important_messages(
            earlier_messages, max_messages - len(recent_messages)
        )
        
        return important_messages + recent_messages
    
    def _select_important_messages(self, messages: List[ConversationMessage], 
                                 count: int) -> List[ConversationMessage]:
        """选择重要消息"""
        if len(messages) <= count:
            return messages
        
        # 简单的重要性评分
        scored_messages = []
        for msg in messages:
            score = self._calculate_message_importance(msg)
            scored_messages.append((score, msg))
        
        # 按分数排序，选择最重要的
        scored_messages.sort(key=lambda x: x[0], reverse=True)
        return [msg for score, msg in scored_messages[:count]]
    
    def _calculate_message_importance(self, message: ConversationMessage) -> float:
        """计算消息重要性"""
        score = 0.0
        content = message.content.lower()
        
        # 关键词权重
        important_keywords = [
            '策略', 'strategy', '交易', 'trading', '风险', 'risk',
            '回测', 'backtest', '指标', 'indicator', '错误', 'error',
            '问题', 'problem', '解决', 'solve'
        ]
        
        for keyword in important_keywords:
            if keyword in content:
                score += 1.0
        
        # 消息长度权重
        if len(content) > 100:
            score += 0.5
        
        # 用户问题权重更高
        if message.role == MessageRole.USER:
            score += 0.3
        
        return score
    
    async def _cache_conversation_summary(self, summary: ContextSummary):
        """缓存对话摘要"""
        key = f"summary:{summary.session_id}"
        data = asdict(summary)
        data['created_at'] = summary.created_at.isoformat()
        
        await self.cache.set(key, data, "ai_summaries")
    
    def _extract_key_topics(self, content: str) -> List[str]:
        """提取关键主题"""
        # 简单实现，实际应该使用NLP技术
        keywords = ['策略', '交易', '指标', '回测', '风险', '分析']
        topics = []
        
        for keyword in keywords:
            if keyword in content:
                topics.append(keyword)
        
        return topics
    
    def _extract_important_decisions(self, content: str) -> List[str]:
        """提取重要决策"""
        # 简单实现，寻找决策性语句
        decisions = []
        sentences = content.split('。')
        
        decision_markers = ['决定', '选择', '建议', '推荐', '应该']
        for sentence in sentences:
            for marker in decision_markers:
                if marker in sentence and len(sentence.strip()) > 10:
                    decisions.append(sentence.strip())
                    break
        
        return decisions[:5]  # 最多5个决策
    
    async def _cache_ai_response(self, session_id: str, content: str, 
                               metadata: Optional[Dict[str, Any]]):
        """缓存AI响应"""
        key = f"last_response:{session_id}"
        data = {
            'content': content,
            'metadata': metadata or {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.cache.set(key, data, "ai_responses")
    
    async def _update_user_ai_sessions(self, user_id: int, session_id: str, 
                                     session_type: SessionType):
        """更新用户AI会话列表"""
        try:
            key = f"user_sessions:{user_id}"
            sessions = await self.cache.get(key, "user_ai_sessions") or []
            
            session_info = {
                'session_id': session_id,
                'session_type': session_type.value,
                'created_at': datetime.utcnow().isoformat(),
                'last_active': datetime.utcnow().isoformat()
            }
            
            # 添加到列表开头
            sessions.insert(0, session_info)
            
            # 限制列表长度
            if len(sessions) > 50:
                sessions = sessions[:50]
            
            await self.cache.set(key, sessions, "user_ai_sessions")
            
        except Exception as e:
            logger.error(f"更新用户AI会话列表失败: {e}")
    
    async def get_ai_cache_statistics(self) -> Dict[str, Any]:
        """获取AI缓存统计信息"""
        try:
            stats = {
                "ai_cache_types": [
                    "ai_conversations",
                    "conversation_context",
                    "ai_summaries", 
                    "ai_responses",
                    "user_ai_sessions",
                    "context_embeddings",
                    "ai_model_cache"
                ],
                "cache_metrics": self.cache.get_metrics(),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取AI缓存统计失败: {e}")
            return {}