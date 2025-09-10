"""
WebSocket连接管理器
- 管理用户WebSocket连接池
- 提供断线重连机制
- 同步会话状态
- 支持实时消息广播
"""

import asyncio
import json
import time
import uuid
import gc
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect, status
from websockets.exceptions import ConnectionClosed
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态枚举"""
    CONNECTING = "connecting"    # 连接中
    CONNECTED = "connected"      # 已连接
    AUTHENTICATING = "authenticating"  # 认证中
    AUTHENTICATED = "authenticated"    # 已认证
    DISCONNECTING = "disconnecting"    # 断开中
    DISCONNECTED = "disconnected"      # 已断开
    ERROR = "error"             # 错误状态


@dataclass
class ConnectionStats:
    """连接统计信息"""
    total_messages_sent: int = 0
    total_messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    reconnect_attempts: int = 0


class WebSocketConnection:
    """WebSocket连接实例 - 增强版本"""
    
    def __init__(self, websocket: WebSocket, user_id: int, connection_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.connection_id = connection_id
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.session_data: Dict[str, Any] = {}
        
        # 增强的状态管理
        self.state = ConnectionState.CONNECTED
        self.is_active = True
        self.stats = ConnectionStats()
        
        # 重连相关
        self.client_info: Dict[str, Any] = {}
        self.subscription_channels: List[str] = []
        
        # 错误跟踪
        self.consecutive_errors = 0
        self.last_successful_message = datetime.utcnow()
        
    async def send_json(self, data: dict) -> bool:
        """发送JSON消息 - 增强版本"""
        if not self.is_active or self.state in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
            return False
            
        try:
            # 添加元数据
            if isinstance(data, dict):
                data['_meta'] = {
                    'connection_id': self.connection_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'message_id': str(uuid.uuid4())[:8]
                }
            
            message_text = json.dumps(data)
            await self.websocket.send_text(message_text)
            
            # 更新统计
            self.stats.total_messages_sent += 1
            self.stats.bytes_sent += len(message_text.encode('utf-8'))
            self.last_successful_message = datetime.utcnow()
            self.last_activity = datetime.utcnow()
            self.consecutive_errors = 0
            
            return True
            
        except ConnectionClosed:
            logger.warning(f"连接已关闭: {self.connection_id}")
            await self._handle_connection_error("连接已关闭")
            return False
        except Exception as e:
            logger.error(f"发送JSON消息失败: {e}")
            await self._handle_connection_error(str(e))
            return False
            
    async def send_text(self, text: str) -> bool:
        """发送文本消息 - 增强版本"""
        if not self.is_active or self.state in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
            return False
            
        try:
            await self.websocket.send_text(text)
            
            # 更新统计
            self.stats.total_messages_sent += 1
            self.stats.bytes_sent += len(text.encode('utf-8'))
            self.last_successful_message = datetime.utcnow()
            self.last_activity = datetime.utcnow()
            self.consecutive_errors = 0
            
            return True
            
        except ConnectionClosed:
            logger.warning(f"连接已关闭: {self.connection_id}")
            await self._handle_connection_error("连接已关闭")
            return False
        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            await self._handle_connection_error(str(e))
            return False
    
    async def _handle_connection_error(self, error: str):
        """处理连接错误"""
        self.consecutive_errors += 1
        self.stats.error_count += 1
        self.stats.last_error = error
        
        if self.consecutive_errors >= 3:
            logger.error(f"连续错误次数过多，标记连接为非活跃: {self.connection_id}")
            self.state = ConnectionState.ERROR
            self.is_active = False
    
    def update_ping(self):
        """更新心跳时间"""
        self.last_ping = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def is_alive(self, timeout_seconds: int = 300) -> bool:
        """检查连接是否存活 - 增强版本"""
        now = datetime.utcnow()
        
        # 基本存活检查
        ping_alive = (now - self.last_ping).total_seconds() < timeout_seconds
        state_alive = self.is_active and self.state not in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]
        
        # 活动超时检查 (更严格)
        activity_alive = (now - self.last_activity).total_seconds() < (timeout_seconds * 2)
        
        # 连续错误检查
        error_healthy = self.consecutive_errors < 5
        
        return ping_alive and state_alive and activity_alive and error_healthy
    
    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接详细信息"""
        now = datetime.utcnow()
        return {
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "is_active": self.is_active,
            "connected_at": self.connected_at.isoformat(),
            "last_ping": self.last_ping.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "connection_age_seconds": (now - self.connected_at).total_seconds(),
            "inactive_seconds": (now - self.last_activity).total_seconds(),
            "stats": {
                "messages_sent": self.stats.total_messages_sent,
                "messages_received": self.stats.total_messages_received,
                "bytes_sent": self.stats.bytes_sent,
                "bytes_received": self.stats.bytes_received,
                "error_count": self.stats.error_count,
                "consecutive_errors": self.consecutive_errors,
                "last_error": self.stats.last_error
            },
            "client_info": self.client_info,
            "subscription_channels": self.subscription_channels
        }
    
    async def graceful_close(self, code: int = 1000, reason: str = "服务端关闭"):
        """优雅关闭连接"""
        try:
            self.state = ConnectionState.DISCONNECTING
            await self.websocket.close(code, reason)
            self.state = ConnectionState.DISCONNECTED
            self.is_active = False
            logger.info(f"连接已优雅关闭: {self.connection_id}")
        except Exception as e:
            logger.error(f"关闭连接时出错: {e}")
            self.state = ConnectionState.ERROR
            self.is_active = False


class WebSocketManager:
    """WebSocket连接管理器 - 增强版本"""
    
    def __init__(self):
        # 活跃连接池: {connection_id: WebSocketConnection}
        self.active_connections: Dict[str, WebSocketConnection] = {}
        
        # 用户连接映射: {user_id: [connection_id1, connection_id2, ...]}
        self.user_connections: Dict[int, List[str]] = defaultdict(list)
        
        # 会话连接映射: {session_id: connection_id}
        self.session_connections: Dict[str, str] = {}
        
        # 连接池统计
        self.pool_stats = {
            'total_connections_created': 0,
            'total_connections_closed': 0,
            'total_messages_sent': 0,
            'total_messages_received': 0,
            'total_errors': 0,
            'peak_concurrent_connections': 0,
            'average_connection_duration': 0.0
        }
        
        # 后台任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        
        # 配置参数
        self.config = {
            'heartbeat_interval': 30,  # 心跳间隔(秒)
            'cleanup_interval': 60,    # 清理间隔(秒)
            'connection_timeout': 300, # 连接超时(秒)
            'max_connections_per_user': 5,  # 每用户最大连接数
            'max_total_connections': 1000,   # 系统最大连接数
            'stats_interval': 300      # 统计间隔(秒)
        }
        
    async def start_monitoring(self):
        """启动所有监控任务"""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            logger.info("💓 WebSocket心跳监控已启动")
            
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_monitor())
            logger.info("🧹 WebSocket清理监控已启动")
            
        if self._stats_task is None:
            self._stats_task = asyncio.create_task(self._stats_monitor())
            logger.info("📊 WebSocket统计监控已启动")
    
    async def stop_monitoring(self):
        """停止所有监控任务"""
        tasks_to_cancel = [
            (self._heartbeat_task, "心跳监控"),
            (self._cleanup_task, "清理监控"),
            (self._stats_task, "统计监控")
        ]
        
        for task, name in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"💔 WebSocket{name}已停止")
                except Exception as e:
                    logger.error(f"停止{name}时出错: {e}")
        
        self._heartbeat_task = None
        self._cleanup_task = None
        self._stats_task = None
    
    # 保持向后兼容性
    async def start_heartbeat_monitor(self):
        """启动心跳监控任务 - 兼容方法"""
        await self.start_monitoring()
    
    async def stop_heartbeat_monitor(self):
        """停止心跳监控任务 - 兼容方法"""
        await self.stop_monitoring()
    
    async def _heartbeat_monitor(self):
        """心跳监控循环 - 增强版本"""
        while True:
            try:
                await asyncio.sleep(self.config['heartbeat_interval'])
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳监控异常: {e}")
                
    async def _cleanup_monitor(self):
        """清理监控循环"""
        while True:
            try:
                await asyncio.sleep(self.config['cleanup_interval'])
                await self._cleanup_dead_connections()
                await self._cleanup_memory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理监控异常: {e}")
                
    async def _stats_monitor(self):
        """统计监控循环"""
        while True:
            try:
                await asyncio.sleep(self.config['stats_interval'])
                await self._update_pool_stats()
                await self._log_connection_stats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"统计监控异常: {e}")
    
    async def _cleanup_dead_connections(self):
        """清理死连接 - 增强版本"""
        dead_connections = []
        
        for connection_id, connection in self.active_connections.items():
            if not connection.is_alive(self.config['connection_timeout']):
                dead_connections.append((connection_id, connection))
        
        for connection_id, connection in dead_connections:
            # 记录连接统计
            duration = (datetime.utcnow() - connection.connected_at).total_seconds()
            self.pool_stats['total_connections_closed'] += 1
            
            # 确定断开原因
            if connection.consecutive_errors >= 3:
                reason = f"连续错误过多({connection.consecutive_errors})"
            elif not connection.is_active:
                reason = "连接已标记为非活跃"
            else:
                reason = "心跳超时"
            
            await self.disconnect(connection_id, reason)
            
        if dead_connections:
            logger.info(f"🧹 清理了 {len(dead_connections)} 个死连接")
    
    async def _cleanup_memory(self):
        """内存清理"""
        try:
            # 清理空的用户连接列表
            empty_users = [user_id for user_id, connections in self.user_connections.items() 
                          if not connections]
            for user_id in empty_users:
                del self.user_connections[user_id]
                
            # 清理无效的会话映射
            invalid_sessions = [session_id for session_id, connection_id in self.session_connections.items()
                               if connection_id not in self.active_connections]
            for session_id in invalid_sessions:
                del self.session_connections[session_id]
            
            # 触发垃圾回收
            collected = gc.collect()
            
            if empty_users or invalid_sessions or collected > 0:
                logger.debug(f"内存清理完成: 空用户列表={len(empty_users)}, 无效会话={len(invalid_sessions)}, 垃圾回收={collected}")
                
        except Exception as e:
            logger.error(f"内存清理异常: {e}")
    
    async def _update_pool_stats(self):
        """更新连接池统计"""
        try:
            current_count = len(self.active_connections)
            if current_count > self.pool_stats['peak_concurrent_connections']:
                self.pool_stats['peak_concurrent_connections'] = current_count
            
            # 计算总消息数和错误数
            total_messages = 0
            total_errors = 0
            total_duration = 0.0
            
            for connection in self.active_connections.values():
                total_messages += connection.stats.total_messages_sent
                total_errors += connection.stats.error_count
                total_duration += (datetime.utcnow() - connection.connected_at).total_seconds()
            
            self.pool_stats['total_messages_sent'] = total_messages
            self.pool_stats['total_errors'] = total_errors
            
            if current_count > 0:
                self.pool_stats['average_connection_duration'] = total_duration / current_count
                
        except Exception as e:
            logger.error(f"更新连接池统计异常: {e}")
    
    async def _log_connection_stats(self):
        """记录连接统计信息"""
        try:
            current_count = len(self.active_connections)
            user_count = len(self.user_connections)
            
            logger.info(
                f"📊 WebSocket连接池状态: "
                f"活跃连接={current_count}, "
                f"在线用户={user_count}, "
                f"峰值连接={self.pool_stats['peak_concurrent_connections']}, "
                f"总消息={self.pool_stats['total_messages_sent']}, "
                f"总错误={self.pool_stats['total_errors']}"
            )
            
            # 检查是否接近限制
            if current_count > self.config['max_total_connections'] * 0.8:
                logger.warning(f"⚠️ 连接数接近限制: {current_count}/{self.config['max_total_connections']}")
            
        except Exception as e:
            logger.error(f"记录连接统计异常: {e}")
    
    async def _send_heartbeat(self):
        """发送心跳包"""
        heartbeat_message = {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
            "server_time": int(time.time())
        }
        
        for connection in self.active_connections.values():
            if connection.is_active:
                await connection.send_json(heartbeat_message)
    
    async def connect(self, websocket: WebSocket, user_id: int, session_id: Optional[str] = None, 
                      client_info: Optional[Dict[str, Any]] = None) -> str:
        """
        建立WebSocket连接 - 增强版本
        
        Args:
            websocket: WebSocket实例
            user_id: 用户ID
            session_id: 会话ID (可选)
            client_info: 客户端信息 (可选)
            
        Returns:
            连接ID
            
        Raises:
            ValueError: 连接数超过限制时抛出
        """
        # 检查系统总连接数限制
        if len(self.active_connections) >= self.config['max_total_connections']:
            raise ValueError(f"系统连接数已达到限制: {self.config['max_total_connections']}")
        
        # 检查用户连接数限制
        user_current_connections = len(self.user_connections.get(user_id, []))
        if user_current_connections >= self.config['max_connections_per_user']:
            # 自动断开最旧的连接
            oldest_connection_id = self.user_connections[user_id][0]
            await self.disconnect(oldest_connection_id, "用户连接数达到限制，断开最旧连接")
            logger.warning(f"用户 {user_id} 连接数达到限制，自动断开最旧连接")
        
        connection_id = str(uuid.uuid4())
        
        # 创建连接实例
        connection = WebSocketConnection(websocket, user_id, connection_id)
        
        # 设置客户端信息
        if client_info:
            connection.client_info = client_info
        
        # 添加到连接池
        self.active_connections[connection_id] = connection
        
        # 添加到用户连接映射
        self.user_connections[user_id].append(connection_id)
        
        # 如果有会话ID，添加到会话映射
        if session_id:
            self.session_connections[session_id] = connection_id
            connection.session_data["session_id"] = session_id
        
        # 更新统计
        self.pool_stats['total_connections_created'] += 1
        
        # 启动监控(如果尚未启动)
        await self.start_monitoring()
        
        # 发送连接成功消息
        welcome_message = {
            "type": "connection_established",
            "connection_id": connection_id,
            "user_id": user_id,
            "session_id": session_id,
            "server_time": datetime.utcnow().isoformat(),
            "config": {
                "heartbeat_interval": self.config['heartbeat_interval'],
                "connection_timeout": self.config['connection_timeout']
            }
        }
        
        success = await connection.send_json(welcome_message)
        if not success:
            # 如果发送欢迎消息失败，立即清理连接
            await self.disconnect(connection_id, "发送欢迎消息失败")
            raise ValueError("建立连接失败：无法发送欢迎消息")
        
        logger.info(f"🔗 用户 {user_id} 建立WebSocket连接: {connection_id} (总连接数: {len(self.active_connections)})")
        
        return connection_id
    
    async def disconnect(self, connection_id: str, reason: str = "正常断开"):
        """
        断开WebSocket连接
        
        Args:
            connection_id: 连接ID
            reason: 断开原因
        """
        if connection_id not in self.active_connections:
            return
        
        connection = self.active_connections[connection_id]
        user_id = connection.user_id
        
        # 从活跃连接池移除
        del self.active_connections[connection_id]
        
        # 从用户连接映射移除
        if user_id in self.user_connections:
            if connection_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(connection_id)
            
            # 如果用户没有其他连接，移除用户映射
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # 从会话映射移除
        session_id = connection.session_data.get("session_id")
        if session_id and session_id in self.session_connections:
            del self.session_connections[session_id]
        
        # 标记连接为非活跃
        connection.is_active = False
        
        logger.info(f"❌ 用户 {user_id} 断开WebSocket连接: {connection_id} (原因: {reason})")
        
        # 如果没有活跃连接，停止心跳监控
        if not self.active_connections:
            await self.stop_heartbeat_monitor()
    
    async def send_to_user(self, user_id: int, message: dict):
        """
        向指定用户的所有连接发送消息
        
        Args:
            user_id: 用户ID
            message: 消息内容
        """
        if user_id not in self.user_connections:
            logger.warning(f"用户 {user_id} 没有活跃的WebSocket连接")
            return False
        
        message["timestamp"] = datetime.utcnow().isoformat()
        
        sent_count = 0
        for connection_id in self.user_connections[user_id].copy():  # 使用副本避免迭代时修改
            if connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
                await connection.send_json(message)
                sent_count += 1
        
        logger.info(f"📤 向用户 {user_id} 的 {sent_count} 个连接发送消息")
        return sent_count > 0
    
    async def send_to_session(self, session_id: str, message: dict):
        """
        向指定会话发送消息
        
        Args:
            session_id: 会话ID
            message: 消息内容
        """
        if session_id not in self.session_connections:
            logger.warning(f"会话 {session_id} 没有活跃的WebSocket连接")
            return False
        
        connection_id = self.session_connections[session_id]
        if connection_id in self.active_connections:
            connection = self.active_connections[connection_id]
            message["timestamp"] = datetime.utcnow().isoformat()
            await connection.send_json(message)
            logger.info(f"📤 向会话 {session_id} 发送消息")
            return True
        
        return False
    
    async def broadcast_to_all(self, message: dict):
        """
        广播消息到所有活跃连接
        
        Args:
            message: 消息内容
        """
        if not self.active_connections:
            return
        
        message["timestamp"] = datetime.utcnow().isoformat()
        
        for connection in self.active_connections.values():
            if connection.is_active:
                await connection.send_json(message)
        
        logger.info(f"📻 广播消息到 {len(self.active_connections)} 个连接")
    
    async def handle_ping(self, connection_id: str):
        """
        处理客户端ping
        
        Args:
            connection_id: 连接ID
        """
        if connection_id in self.active_connections:
            connection = self.active_connections[connection_id]
            connection.update_ping()
            
            # 发送pong响应
            pong_message = {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }
            await connection.send_json(pong_message)
    
    def get_connection_stats(self) -> dict:
        """
        获取连接统计信息
        
        Returns:
            连接统计字典
        """
        total_connections = len(self.active_connections)
        total_users = len(self.user_connections)
        total_sessions = len(self.session_connections)
        
        # 按用户统计连接数
        user_connection_counts = {
            user_id: len(connections) 
            for user_id, connections in self.user_connections.items()
        }
        
        # 连接存活时间统计
        now = datetime.utcnow()
        connection_durations = []
        for connection in self.active_connections.values():
            duration = (now - connection.connected_at).total_seconds()
            connection_durations.append(duration)
        
        avg_duration = sum(connection_durations) / len(connection_durations) if connection_durations else 0
        
        return {
            "total_connections": total_connections,
            "total_users": total_users,
            "total_sessions": total_sessions,
            "user_connection_counts": user_connection_counts,
            "average_connection_duration_seconds": round(avg_duration, 2),
            "heartbeat_monitor_active": self._heartbeat_task is not None and not self._heartbeat_task.done()
        }
    
    async def get_user_connections(self, user_id: int) -> List[dict]:
        """
        获取用户的所有连接信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            连接信息列表
        """
        if user_id not in self.user_connections:
            return []
        
        connections_info = []
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
                connections_info.append({
                    "connection_id": connection_id,
                    "connected_at": connection.connected_at.isoformat(),
                    "last_ping": connection.last_ping.isoformat(),
                    "is_active": connection.is_active,
                    "session_data": connection.session_data
                })
        
        return connections_info


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()


async def get_websocket_manager() -> WebSocketManager:
    """获取WebSocket管理器实例"""
    return websocket_manager