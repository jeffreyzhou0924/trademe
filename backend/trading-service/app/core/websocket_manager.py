"""
WebSocket连接管理器

专门处理OKX交易所的WebSocket连接和实时数据流
支持重连、心跳、错误处理等功能
"""

import asyncio
import json
import time
import websockets
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum
import uuid
from loguru import logger
from dataclasses import dataclass

from app.core.market_data_collector import TickData, KlineData


class ChannelType(Enum):
    """频道类型枚举"""
    TICKER = "tickers"
    KLINE = "candle"
    TRADES = "trades"
    ORDER_BOOK = "books"


@dataclass
class Subscription:
    """订阅信息"""
    channel: ChannelType
    symbol: str
    timeframe: Optional[str] = None
    callback: Optional[Callable] = None
    
    def to_okx_channel(self) -> str:
        """转换为OKX频道格式"""
        if self.channel == ChannelType.TICKER:
            return f"tickers:{self.symbol}"
        elif self.channel == ChannelType.KLINE:
            return f"candle{self.timeframe}:{self.symbol}"
        elif self.channel == ChannelType.TRADES:
            return f"trades:{self.symbol}"
        elif self.channel == ChannelType.ORDER_BOOK:
            return f"books:{self.symbol}"
        else:
            raise ValueError(f"不支持的频道类型: {self.channel}")


class OKXWebSocketManager:
    """OKX WebSocket管理器"""
    
    def __init__(self):
        # WebSocket连接
        self.ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        
        # 订阅管理
        self.subscriptions: Dict[str, Subscription] = {}
        self.active_channels: List[str] = []
        
        # 重连配置
        self.reconnect_interval = 5  # 秒
        self.max_reconnect_attempts = 10
        self.reconnect_count = 0
        
        # 心跳配置
        self.ping_interval = 30  # 秒
        self.last_pong_time = time.time()
        
        # 回调函数
        self.message_callbacks: Dict[ChannelType, List[Callable]] = {
            ChannelType.TICKER: [],
            ChannelType.KLINE: [],
            ChannelType.TRADES: [],
            ChannelType.ORDER_BOOK: []
        }
        
        # 错误回调
        self.error_callbacks: List[Callable] = []
        
        # 统计信息
        self.stats = {
            "messages_received": 0,
            "last_message_time": None,
            "connection_start_time": None,
            "reconnect_count": 0
        }
    
    async def connect(self) -> bool:
        """建立WebSocket连接"""
        try:
            logger.info(f"正在连接OKX WebSocket: {self.ws_url}")
            
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,  # 我们自己处理ping
                ping_timeout=None,
                close_timeout=10
            )
            
            self.is_connected = True
            self.is_running = True
            self.reconnect_count = 0
            self.stats["connection_start_time"] = datetime.now()
            
            # 启动消息处理循环
            asyncio.create_task(self._message_loop())
            
            # 启动心跳
            asyncio.create_task(self._heartbeat_loop())
            
            logger.info("OKX WebSocket连接成功")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """断开WebSocket连接"""
        self.is_running = False
        
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            logger.info("WebSocket连接已断开")
        
        self.is_connected = False
        self.websocket = None
    
    async def subscribe(self, subscription: Subscription) -> bool:
        """订阅频道"""
        try:
            if not self.is_connected:
                await self.connect()
            
            channel = subscription.to_okx_channel()
            
            # 构建订阅消息
            subscribe_msg = {
                "op": "subscribe",
                "args": [{"channel": channel.split(':')[0], "instId": subscription.symbol}]
            }
            
            # 如果是K线数据，需要特殊处理
            if subscription.channel == ChannelType.KLINE:
                subscribe_msg["args"] = [{
                    "channel": f"candle{subscription.timeframe}",
                    "instId": subscription.symbol
                }]
            
            # 发送订阅消息
            await self.websocket.send(json.dumps(subscribe_msg))
            
            # 保存订阅信息
            sub_id = f"{subscription.channel.value}_{subscription.symbol}_{subscription.timeframe or ''}"
            self.subscriptions[sub_id] = subscription
            self.active_channels.append(channel)
            
            logger.info(f"订阅成功: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"订阅失败: {str(e)}")
            return False
    
    async def unsubscribe(self, subscription: Subscription) -> bool:
        """取消订阅"""
        try:
            if not self.is_connected:
                return False
            
            channel = subscription.to_okx_channel()
            
            # 构建取消订阅消息
            unsubscribe_msg = {
                "op": "unsubscribe",
                "args": [{"channel": channel.split(':')[0], "instId": subscription.symbol}]
            }
            
            await self.websocket.send(json.dumps(unsubscribe_msg))
            
            # 移除订阅信息
            sub_id = f"{subscription.channel.value}_{subscription.symbol}_{subscription.timeframe or ''}"
            if sub_id in self.subscriptions:
                del self.subscriptions[sub_id]
            
            if channel in self.active_channels:
                self.active_channels.remove(channel)
            
            logger.info(f"取消订阅成功: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"取消订阅失败: {str(e)}")
            return False
    
    def register_callback(self, channel_type: ChannelType, callback: Callable):
        """注册回调函数"""
        if channel_type in self.message_callbacks:
            self.message_callbacks[channel_type].append(callback)
    
    def register_error_callback(self, callback: Callable):
        """注册错误回调函数"""
        self.error_callbacks.append(callback)
    
    async def _message_loop(self):
        """消息处理循环"""
        while self.is_running and self.is_connected:
            try:
                # 接收消息
                message = await asyncio.wait_for(
                    self.websocket.recv(), 
                    timeout=60  # 60秒超时
                )
                
                self.stats["messages_received"] += 1
                self.stats["last_message_time"] = datetime.now()
                
                # 解析消息
                await self._process_message(message)
                
            except asyncio.TimeoutError:
                logger.warning("WebSocket消息接收超时")
                # 检查连接状态
                if not await self._check_connection():
                    await self._reconnect()
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket连接已关闭")
                self.is_connected = False
                if self.is_running:
                    await self._reconnect()
                break
                
            except Exception as e:
                logger.error(f"消息处理错误: {str(e)}")
                await self._trigger_error_callbacks(str(e))
                await asyncio.sleep(1)
    
    async def _process_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            
            # 处理不同类型的消息
            if "event" in data:
                await self._handle_event_message(data)
            elif "data" in data:
                await self._handle_data_message(data)
            elif "op" in data:
                await self._handle_operation_response(data)
            
        except Exception as e:
            logger.error(f"消息解析失败: {str(e)}")
    
    async def _handle_event_message(self, data: Dict[str, Any]):
        """处理事件消息"""
        event = data.get("event")
        
        if event == "subscribe":
            channel = data.get("arg", {}).get("channel", "")
            logger.info(f"订阅确认: {channel}")
            
        elif event == "unsubscribe":
            channel = data.get("arg", {}).get("channel", "")
            logger.info(f"取消订阅确认: {channel}")
            
        elif event == "error":
            error_msg = data.get("msg", "未知错误")
            logger.error(f"WebSocket错误: {error_msg}")
            await self._trigger_error_callbacks(error_msg)
    
    async def _handle_data_message(self, data: Dict[str, Any]):
        """处理数据消息"""
        try:
            arg = data.get("arg", {})
            channel = arg.get("channel", "")
            inst_id = arg.get("instId", "")
            message_data = data.get("data", [])
            
            # 根据频道类型处理数据
            if channel.startswith("tickers"):
                await self._process_ticker_data(inst_id, message_data)
            elif channel.startswith("candle"):
                timeframe = channel.replace("candle", "")
                await self._process_kline_data(inst_id, timeframe, message_data)
            elif channel.startswith("trades"):
                await self._process_trades_data(inst_id, message_data)
            elif channel.startswith("books"):
                await self._process_orderbook_data(inst_id, message_data)
                
        except Exception as e:
            logger.error(f"数据消息处理失败: {str(e)}")
    
    async def _process_ticker_data(self, symbol: str, data: List[Dict]):
        """处理ticker数据"""
        for item in data:
            try:
                tick_data = TickData(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(int(item["ts"]) / 1000),
                    bid=float(item.get("bidPx", 0)),
                    ask=float(item.get("askPx", 0)),
                    price=float(item.get("last", 0)),
                    volume=float(item.get("vol24h", 0)),
                    exchange="okx"
                )
                
                # 触发回调
                for callback in self.message_callbacks[ChannelType.TICKER]:
                    try:
                        await callback(tick_data)
                    except Exception as e:
                        logger.error(f"Ticker回调失败: {str(e)}")
                        
            except Exception as e:
                logger.error(f"Ticker数据解析失败: {str(e)}")
    
    async def _process_kline_data(self, symbol: str, timeframe: str, data: List[List]):
        """处理K线数据"""
        for item in data:
            try:
                # OKX K线数据格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                timestamp = datetime.fromtimestamp(int(item[0]) / 1000)
                
                kline_data = KlineData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=float(item[5]),
                    exchange="okx"
                )
                
                # 触发回调
                for callback in self.message_callbacks[ChannelType.KLINE]:
                    try:
                        await callback(kline_data)
                    except Exception as e:
                        logger.error(f"K线回调失败: {str(e)}")
                        
            except Exception as e:
                logger.error(f"K线数据解析失败: {str(e)}")
    
    async def _process_trades_data(self, symbol: str, data: List[Dict]):
        """处理交易数据"""
        # 交易数据处理逻辑
        pass
    
    async def _process_orderbook_data(self, symbol: str, data: List[Dict]):
        """处理订单簿数据"""
        # 订单簿数据处理逻辑
        pass
    
    async def _handle_operation_response(self, data: Dict[str, Any]):
        """处理操作响应"""
        op = data.get("op")
        code = data.get("code", "0")
        msg = data.get("msg", "")
        
        if code != "0":
            logger.error(f"操作失败 {op}: {msg}")
            await self._trigger_error_callbacks(f"{op}: {msg}")
        else:
            logger.debug(f"操作成功 {op}: {msg}")
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.is_running and self.is_connected:
            try:
                # 发送ping
                ping_msg = {"op": "ping"}
                await self.websocket.send(json.dumps(ping_msg))
                
                await asyncio.sleep(self.ping_interval)
                
            except Exception as e:
                logger.error(f"心跳发送失败: {str(e)}")
                break
    
    async def _check_connection(self) -> bool:
        """检查连接状态"""
        try:
            if not self.websocket or self.websocket.closed:
                return False
            
            # 发送ping测试连接
            ping_msg = {"op": "ping"}
            await asyncio.wait_for(
                self.websocket.send(json.dumps(ping_msg)), 
                timeout=5
            )
            
            return True
            
        except Exception:
            return False
    
    async def _reconnect(self):
        """重连"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error("达到最大重连次数，停止重连")
            await self._trigger_error_callbacks("达到最大重连次数")
            return
        
        self.reconnect_count += 1
        self.stats["reconnect_count"] += 1
        
        logger.info(f"开始重连 (第{self.reconnect_count}次)")
        
        # 等待一段时间后重连
        await asyncio.sleep(self.reconnect_interval)
        
        try:
            # 重新连接
            await self.disconnect()
            await asyncio.sleep(1)
            
            if await self.connect():
                # 重新订阅所有频道
                await self._resubscribe_all()
                logger.info("重连成功")
            else:
                logger.error("重连失败")
                await self._reconnect()  # 递归重连
                
        except Exception as e:
            logger.error(f"重连过程中出错: {str(e)}")
            await self._reconnect()
    
    async def _resubscribe_all(self):
        """重新订阅所有频道"""
        subscriptions_copy = self.subscriptions.copy()
        self.subscriptions.clear()
        self.active_channels.clear()
        
        for sub_id, subscription in subscriptions_copy.items():
            await self.subscribe(subscription)
            await asyncio.sleep(0.1)  # 避免订阅过快
    
    async def _trigger_error_callbacks(self, error_message: str):
        """触发错误回调"""
        for callback in self.error_callbacks:
            try:
                await callback(error_message)
            except Exception as e:
                logger.error(f"错误回调失败: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "active_subscriptions": len(self.subscriptions),
            "active_channels": len(self.active_channels),
            "uptime": (
                datetime.now() - self.stats["connection_start_time"]
            ).total_seconds() if self.stats["connection_start_time"] else 0
        }


# 全局WebSocket管理器实例
websocket_manager = OKXWebSocketManager()