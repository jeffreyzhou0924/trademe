"""
Claude API智能缓存服务
- 避免重复的API调用，提升响应速度
- 基于内容哈希的智能缓存策略
- 支持TTL和容量限制的高效缓存管理
"""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CacheLevel(str, Enum):
    """缓存级别"""
    NONE = "none"           # 不缓存
    SHORT = "short"         # 短期缓存 (5分钟)
    MEDIUM = "medium"       # 中期缓存 (30分钟)
    LONG = "long"          # 长期缓存 (2小时)
    PERSISTENT = "persistent"  # 持久缓存 (24小时)


class ContentType(str, Enum):
    """内容类型"""
    CHAT = "chat"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    STRATEGY = "strategy"
    INDICATOR = "indicator"


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    content_hash: str
    response: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    content_type: ContentType = ContentType.CHAT
    user_id: Optional[int] = None
    account_id: Optional[int] = None
    
    def is_expired(self) -> bool:
        """检查是否已过期"""
        return datetime.utcnow() > self.expires_at
    
    def is_stale(self, staleness_threshold: timedelta = timedelta(minutes=5)) -> bool:
        """检查是否已经陈旧（但未过期）"""
        return datetime.utcnow() > self.created_at + staleness_threshold


class ClaudeCacheService:
    """Claude API智能缓存服务"""
    
    def __init__(self, max_cache_size: int = 10000):
        """
        初始化缓存服务
        
        Args:
            max_cache_size: 最大缓存条目数
        """
        self.max_cache_size = max_cache_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # 缓存统计
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_requests": 0,
            "cache_size": 0
        }
        
        # 缓存配置
        self.cache_ttl_config = {
            CacheLevel.SHORT: timedelta(minutes=5),
            CacheLevel.MEDIUM: timedelta(minutes=30), 
            CacheLevel.LONG: timedelta(hours=2),
            CacheLevel.PERSISTENT: timedelta(hours=24)
        }
        
        # 内容类型缓存策略
        self.content_cache_strategy = {
            ContentType.CHAT: CacheLevel.SHORT,           # 聊天内容变化较快
            ContentType.ANALYSIS: CacheLevel.MEDIUM,       # 分析结果相对稳定
            ContentType.GENERATION: CacheLevel.SHORT,      # 生成内容需要多样性
            ContentType.STRATEGY: CacheLevel.LONG,         # 策略代码可以长期缓存
            ContentType.INDICATOR: CacheLevel.LONG         # 技术指标计算可以长期缓存
        }
        
        # 后台清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动后台清理任务"""
        try:
            # 只有在事件循环运行时才启动清理任务
            loop = asyncio.get_running_loop()
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        except RuntimeError:
            # 没有运行中的事件循环，跳过后台任务
            logger.warning("没有运行中的事件循环，跳过缓存清理任务启动")
            pass
    
    async def _periodic_cleanup(self):
        """定期清理过期缓存"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"缓存清理任务异常: {e}")
    
    def generate_cache_key(self, 
                          request_data: Dict[str, Any], 
                          user_id: Optional[int] = None,
                          content_type: ContentType = ContentType.CHAT) -> Tuple[str, str]:
        """
        生成缓存键和内容哈希
        
        Args:
            request_data: 请求数据
            user_id: 用户ID (某些缓存可能需要用户隔离)
            content_type: 内容类型
            
        Returns:
            (cache_key, content_hash) 元组
        """
        # 提取用于缓存的关键信息
        cache_content = {
            "content_type": content_type.value,
            "request_data": self._normalize_request_data(request_data)
        }
        
        # 对于某些内容类型，不需要用户隔离
        if content_type in [ContentType.STRATEGY, ContentType.INDICATOR]:
            # 策略和指标可以跨用户共享
            cache_content["scope"] = "global"
        else:
            # 聊天和分析内容需要用户隔离
            cache_content["user_id"] = user_id
            cache_content["scope"] = "user"
        
        # 生成内容哈希
        content_json = json.dumps(cache_content, sort_keys=True)
        content_hash = hashlib.sha256(content_json.encode()).hexdigest()
        
        # 生成缓存键 (更短，便于存储)
        cache_key = f"{content_type.value}:{content_hash[:16]}"
        
        return cache_key, content_hash
    
    def _normalize_request_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化请求数据，移除不影响响应的字段
        
        Args:
            request_data: 原始请求数据
            
        Returns:
            标准化后的请求数据
        """
        # 创建副本避免修改原数据
        normalized = {}
        
        # 需要用于缓存的关键字段
        cache_relevant_fields = [
            "messages", "content", "prompt", "model", 
            "temperature", "max_tokens", "system",
            "analysis_type", "content_type", "parameters"
        ]
        
        for field in cache_relevant_fields:
            if field in request_data:
                value = request_data[field]
                
                # 对于某些字段进行特殊处理
                if field == "messages" and isinstance(value, list):
                    # 提取消息内容，忽略时间戳等元数据
                    normalized_messages = []
                    for msg in value:
                        if isinstance(msg, dict):
                            normalized_messages.append({
                                "role": msg.get("role", ""),
                                "content": msg.get("content", "")
                            })
                    normalized[field] = normalized_messages
                elif field == "temperature" and isinstance(value, (int, float)):
                    # 温度参数保留2位小数
                    normalized[field] = round(float(value), 2)
                else:
                    normalized[field] = value
        
        return normalized
    
    def determine_cache_level(self, 
                            request_data: Dict[str, Any], 
                            content_type: ContentType) -> CacheLevel:
        """
        根据请求内容确定缓存级别
        
        Args:
            request_data: 请求数据
            content_type: 内容类型
            
        Returns:
            推荐的缓存级别
        """
        # 基础策略
        base_level = self.content_cache_strategy.get(content_type, CacheLevel.SHORT)
        
        # 根据请求特征调整
        if content_type == ContentType.CHAT:
            # 聊天请求：检查是否包含时间敏感信息
            content = self._extract_text_content(request_data)
            time_sensitive_keywords = ["今天", "现在", "当前", "最新", "real-time", "now", "today"]
            
            if any(keyword in content.lower() for keyword in time_sensitive_keywords):
                return CacheLevel.NONE  # 时间敏感内容不缓存
            else:
                return CacheLevel.SHORT
                
        elif content_type == ContentType.GENERATION:
            # 生成请求：检查是否要求创意性
            temperature = request_data.get("temperature", 0.7)
            if temperature > 0.8:
                return CacheLevel.NONE  # 高创意性要求不缓存
            else:
                return CacheLevel.SHORT
                
        elif content_type in [ContentType.STRATEGY, ContentType.INDICATOR]:
            # 策略和指标：相对稳定，可以长期缓存
            return CacheLevel.LONG
            
        return base_level
    
    def _extract_text_content(self, request_data: Dict[str, Any]) -> str:
        """从请求数据中提取文本内容"""
        content_parts = []
        
        if "messages" in request_data:
            for msg in request_data["messages"]:
                if isinstance(msg, dict):
                    content_parts.append(msg.get("content", ""))
        elif "content" in request_data:
            content_parts.append(str(request_data["content"]))
        elif "prompt" in request_data:
            content_parts.append(str(request_data["prompt"]))
        
        return " ".join(content_parts)
    
    async def get_cached_response(self, 
                                cache_key: str, 
                                content_hash: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的响应
        
        Args:
            cache_key: 缓存键
            content_hash: 内容哈希
            
        Returns:
            缓存的响应数据，如果没有则返回None
        """
        self.stats["total_requests"] += 1
        
        if cache_key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        entry = self.cache[cache_key]
        
        # 检查内容哈希是否匹配（防止哈希冲突）
        if entry.content_hash != content_hash:
            logger.warning(f"缓存哈希冲突: {cache_key}")
            del self.cache[cache_key]
            self.stats["misses"] += 1
            return None
        
        # 检查是否过期
        if entry.is_expired():
            del self.cache[cache_key]
            self.stats["misses"] += 1
            logger.debug(f"缓存过期: {cache_key}")
            return None
        
        # 更新访问统计
        entry.access_count += 1
        entry.last_accessed = datetime.utcnow()
        
        # 移到最后（LRU）
        self.cache.move_to_end(cache_key)
        
        self.stats["hits"] += 1
        logger.debug(f"缓存命中: {cache_key} (访问次数: {entry.access_count})")
        
        # 添加缓存标识到响应中
        response = entry.response.copy()
        response["_cache_info"] = {
            "cached": True,
            "cache_key": cache_key,
            "created_at": entry.created_at.isoformat(),
            "access_count": entry.access_count,
            "content_type": entry.content_type.value
        }
        
        return response
    
    async def cache_response(self, 
                           cache_key: str,
                           content_hash: str,
                           response: Dict[str, Any],
                           cache_level: CacheLevel,
                           content_type: ContentType = ContentType.CHAT,
                           user_id: Optional[int] = None,
                           account_id: Optional[int] = None):
        """
        缓存API响应
        
        Args:
            cache_key: 缓存键
            content_hash: 内容哈希
            response: API响应数据
            cache_level: 缓存级别
            content_type: 内容类型
            user_id: 用户ID
            account_id: Claude账号ID
        """
        if cache_level == CacheLevel.NONE:
            return
        
        # 检查响应是否适合缓存
        if not self._is_cacheable_response(response):
            return
        
        # 计算过期时间
        ttl = self.cache_ttl_config.get(cache_level, timedelta(minutes=5))
        expires_at = datetime.utcnow() + ttl
        
        # 创建缓存条目
        entry = CacheEntry(
            key=cache_key,
            content_hash=content_hash,
            response=self._sanitize_response_for_cache(response),
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            content_type=content_type,
            user_id=user_id,
            account_id=account_id
        )
        
        # 容量管理
        await self._ensure_cache_capacity()
        
        # 添加到缓存
        self.cache[cache_key] = entry
        self.stats["cache_size"] = len(self.cache)
        
        logger.debug(f"缓存响应: {cache_key} (TTL: {ttl}, 类型: {content_type.value})")
    
    def _is_cacheable_response(self, response: Dict[str, Any]) -> bool:
        """检查响应是否适合缓存"""
        # 不缓存错误响应
        if "error" in response:
            return False
        
        # 不缓存空响应
        if not response or len(str(response)) < 10:
            return False
        
        # 检查响应中是否包含时间敏感信息
        response_text = str(response).lower()
        time_sensitive_indicators = ["当前时间", "现在是", "today is", "current time"]
        if any(indicator in response_text for indicator in time_sensitive_indicators):
            return False
        
        return True
    
    def _sanitize_response_for_cache(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """清理响应数据用于缓存"""
        sanitized = response.copy()
        
        # 移除不应该缓存的字段
        fields_to_remove = ["_cache_info", "request_id", "created_at", "timestamp"]
        for field in fields_to_remove:
            sanitized.pop(field, None)
        
        return sanitized
    
    async def _ensure_cache_capacity(self):
        """确保缓存容量不超限"""
        while len(self.cache) >= self.max_cache_size:
            # 移除最久未访问的条目（LRU）
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats["evictions"] += 1
    
    def _cleanup_expired_entries(self):
        """清理过期的缓存条目"""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"清理了{len(expired_keys)}个过期缓存条目")
            self.stats["cache_size"] = len(self.cache)
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self.stats["total_requests"]
        hit_rate = (self.stats["hits"] / total_requests) if total_requests > 0 else 0
        
        # 按内容类型统计
        content_type_stats = {}
        for entry in self.cache.values():
            content_type = entry.content_type.value
            if content_type not in content_type_stats:
                content_type_stats[content_type] = {
                    "count": 0,
                    "total_access": 0
                }
            content_type_stats[content_type]["count"] += 1
            content_type_stats[content_type]["total_access"] += entry.access_count
        
        return {
            "cache_size": len(self.cache),
            "max_cache_size": self.max_cache_size,
            "total_requests": total_requests,
            "cache_hits": self.stats["hits"],
            "cache_misses": self.stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self.stats["evictions"],
            "content_type_distribution": content_type_stats,
            "memory_usage_estimate": self._estimate_memory_usage(),
            "last_cleanup": datetime.utcnow().isoformat()
        }
    
    def _estimate_memory_usage(self) -> Dict[str, Any]:
        """估算内存使用量"""
        total_size = 0
        entry_count = len(self.cache)
        
        if entry_count > 0:
            # 采样计算平均大小
            sample_size = min(100, entry_count)
            sample_entries = list(self.cache.values())[:sample_size]
            
            sample_total = sum(len(str(entry.response)) for entry in sample_entries)
            avg_entry_size = sample_total / sample_size
            total_size = int(avg_entry_size * entry_count)
        
        return {
            "estimated_total_bytes": total_size,
            "estimated_total_mb": round(total_size / 1024 / 1024, 2),
            "average_entry_size_bytes": int(total_size / entry_count) if entry_count > 0 else 0,
            "entry_count": entry_count
        }
    
    def invalidate_user_cache(self, user_id: int):
        """使特定用户的缓存失效"""
        keys_to_remove = []
        
        for key, entry in self.cache.items():
            if entry.user_id == user_id:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.info(f"清理用户{user_id}的{len(keys_to_remove)}个缓存条目")
            self.stats["cache_size"] = len(self.cache)
    
    def invalidate_account_cache(self, account_id: int):
        """使特定账号的缓存失效"""
        keys_to_remove = []
        
        for key, entry in self.cache.items():
            if entry.account_id == account_id:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.info(f"清理账号{account_id}的{len(keys_to_remove)}个缓存条目")
            self.stats["cache_size"] = len(self.cache)
    
    def clear_all_cache(self):
        """清空所有缓存"""
        cache_size = len(self.cache)
        self.cache.clear()
        self.stats["cache_size"] = 0
        self.stats["evictions"] += cache_size
        logger.info(f"清空了所有缓存（{cache_size}个条目）")
    
    async def close(self):
        """关闭缓存服务"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.clear_all_cache()


# 全局缓存服务实例
claude_cache_service = ClaudeCacheService()