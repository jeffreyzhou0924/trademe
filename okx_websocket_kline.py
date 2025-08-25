#!/usr/bin/env python3
"""
OKX WebSocket 真实K线数据服务
直接从OKX获取实时K线数据，替代模拟数据
"""

import asyncio
import websockets
import json
import time
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread
import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OKXKlineService:
    def __init__(self):
        self.websocket = None
        self.kline_data = {}  # 存储K线数据 {symbol_timeframe: [klines]}
        self.price_data = {}  # 存储实时价格数据
        self.is_connected = False
        
        # OKX WebSocket配置
        self.ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.rest_url = "https://www.okx.com/api/v5"
        
        # 支持的交易对和时间周期
        self.symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        self.timeframes = ["1m", "5m", "15m", "1H", "4H", "1D"]
        
        # OKX时间周期映射
        self.timeframe_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "2h": "2H", "4h": "4H", 
            "1d": "1D", "1w": "1W"
        }
    
    async def connect_websocket(self):
        """连接OKX WebSocket"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True
            logger.info("✅ 成功连接OKX WebSocket")
            
            # 订阅K线数据
            await self.subscribe_klines()
            
            # 订阅ticker数据获取实时价格
            await self.subscribe_tickers()
            
            # 开始监听数据
            await self.listen_messages()
            
        except Exception as e:
            logger.error(f"❌ WebSocket连接失败: {e}")
            self.is_connected = False
    
    async def subscribe_klines(self):
        """订阅K线数据"""
        channels = []
        for symbol in self.symbols:
            for timeframe in ["1m", "5m", "15m", "1H", "4H", "1D"]:
                channels.append({
                    "channel": "candle" + timeframe,
                    "instId": symbol
                })
        
        subscribe_msg = {
            "op": "subscribe",
            "args": channels
        }
        
        await self.websocket.send(json.dumps(subscribe_msg))
        logger.info(f"📊 已订阅 {len(channels)} 个K线频道")
    
    async def subscribe_tickers(self):
        """订阅实时价格数据"""
        channels = []
        for symbol in self.symbols:
            channels.append({
                "channel": "tickers",
                "instId": symbol
            })
        
        subscribe_msg = {
            "op": "subscribe", 
            "args": channels
        }
        
        await self.websocket.send(json.dumps(subscribe_msg))
        logger.info(f"💰 已订阅 {len(channels)} 个价格频道")
    
    async def listen_messages(self):
        """监听WebSocket消息"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_message(data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket连接关闭")
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ 处理WebSocket消息失败: {e}")
    
    async def handle_message(self, data):
        """处理WebSocket消息"""
        try:
            if data.get("event") == "subscribe":
                logger.info(f"✅ 订阅成功: {data.get('arg', {}).get('channel')}")
                return
            
            if "data" not in data or not data["data"]:
                return
            
            arg = data.get("arg", {})
            channel = arg.get("channel", "")
            inst_id = arg.get("instId", "")
            
            # 处理K线数据
            if channel.startswith("candle"):
                timeframe = channel.replace("candle", "")
                await self.handle_kline_data(inst_id, timeframe, data["data"])
            
            # 处理实时价格数据
            elif channel == "tickers":
                await self.handle_ticker_data(inst_id, data["data"])
                
        except Exception as e:
            logger.error(f"❌ 处理消息失败: {e}")
    
    async def handle_kline_data(self, symbol, timeframe, klines):
        """处理K线数据"""
        key = f"{symbol}_{timeframe}"
        
        if key not in self.kline_data:
            self.kline_data[key] = []
        
        for kline in klines:
            # OKX K线数据格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            timestamp = int(kline[0])  # 时间戳
            open_price = float(kline[1])    # 开盘价
            high_price = float(kline[2])    # 最高价  
            low_price = float(kline[3])     # 最低价
            close_price = float(kline[4])   # 收盘价
            volume = float(kline[5])        # 成交量
            
            # 转换为标准OHLCV格式
            formatted_kline = [
                timestamp,
                open_price,
                high_price, 
                low_price,
                close_price,
                volume
            ]
            
            # 更新或添加K线数据
            self.update_kline_data(key, formatted_kline)
        
        logger.debug(f"📊 更新K线数据: {symbol} {timeframe}")
    
    def update_kline_data(self, key, new_kline):
        """更新K线数据"""
        if key not in self.kline_data:
            self.kline_data[key] = []
        
        klines = self.kline_data[key]
        timestamp = new_kline[0]
        
        # 查找是否已存在相同时间戳的数据
        updated = False
        for i, existing_kline in enumerate(klines):
            if existing_kline[0] == timestamp:
                # 更新现有数据
                klines[i] = new_kline
                updated = True
                break
        
        # 如果是新数据，添加到列表并保持时间顺序
        if not updated:
            klines.append(new_kline)
            klines.sort(key=lambda x: x[0])
        
        # 保持最新的1000条数据
        if len(klines) > 1000:
            self.kline_data[key] = klines[-1000:]
    
    async def handle_ticker_data(self, symbol, tickers):
        """处理实时价格数据"""
        for ticker in tickers:
            price_info = {
                "symbol": symbol.replace("-", "/"),
                "price": float(ticker["last"]),
                "change_24h": float(ticker.get("changeUtc", ticker.get("chg24h", "0"))),
                "high_24h": float(ticker["high24h"]),
                "low_24h": float(ticker["low24h"]),
                "volume_24h": float(ticker.get("vol24h", ticker.get("volUtc", "0"))),
                "timestamp": int(ticker["ts"])
            }
            
            self.price_data[symbol] = price_info
            logger.debug(f"💰 更新价格: {symbol} = {price_info['price']}")
    
    def get_klines(self, symbol, timeframe, limit=100):
        """获取K线数据"""
        # 转换符号格式 BTC/USDT -> BTC-USDT
        okx_symbol = symbol.replace("/", "-")
        
        # 转换时间周期
        okx_timeframe = self.timeframe_map.get(timeframe.lower(), timeframe)
        
        key = f"{okx_symbol}_{okx_timeframe}"
        
        if key in self.kline_data:
            klines = self.kline_data[key][-limit:]  # 获取最新的limit条数据
            return {
                "klines": klines,
                "symbol": symbol,
                "exchange": "okx",
                "timeframe": timeframe,
                "count": len(klines),
                "timestamp": int(time.time() * 1000),
                "source": "websocket"
            }
        else:
            # 如果WebSocket数据不可用，尝试从REST API获取
            return self.get_klines_rest(symbol, timeframe, limit)
    
    def get_klines_rest(self, symbol, timeframe, limit):
        """从REST API获取K线数据作为备用"""
        try:
            okx_symbol = symbol.replace("/", "-")
            okx_timeframe = self.timeframe_map.get(timeframe.lower(), timeframe)
            
            url = f"{self.rest_url}/market/candles"
            params = {
                "instId": okx_symbol,
                "bar": okx_timeframe,
                "limit": min(limit, 300)
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data["code"] == "0" and data["data"]:
                # 转换数据格式
                klines = []
                for candle in data["data"]:
                    klines.append([
                        int(candle[0]),      # timestamp
                        float(candle[1]),    # open
                        float(candle[2]),    # high  
                        float(candle[3]),    # low
                        float(candle[4]),    # close
                        float(candle[5])     # volume
                    ])
                
                # 按时间排序（OKX返回数据是降序的）
                klines.reverse()
                
                return {
                    "klines": klines,
                    "symbol": symbol,
                    "exchange": "okx", 
                    "timeframe": timeframe,
                    "count": len(klines),
                    "timestamp": int(time.time() * 1000),
                    "source": "rest_api"
                }
            
        except Exception as e:
            logger.error(f"❌ REST API获取K线失败: {e}")
        
        # 返回空数据
        return {
            "klines": [],
            "symbol": symbol,
            "exchange": "okx",
            "timeframe": timeframe, 
            "count": 0,
            "timestamp": int(time.time() * 1000),
            "source": "error"
        }
    
    def get_ticker(self, symbol):
        """获取实时价格数据"""
        okx_symbol = symbol.replace("/", "-")
        
        if okx_symbol in self.price_data:
            return self.price_data[okx_symbol]
        else:
            # WebSocket数据不可用时，从REST API获取
            return self.get_ticker_rest(symbol)
    
    def get_ticker_rest(self, symbol):
        """从REST API获取价格数据作为备用"""
        try:
            okx_symbol = symbol.replace("/", "-")
            
            url = f"{self.rest_url}/market/ticker"
            params = {"instId": okx_symbol}
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data["code"] == "0" and data["data"]:
                ticker = data["data"][0]
                return {
                    "symbol": symbol,
                    "price": float(ticker["last"]),
                    "change_24h": float(ticker["chg24h"]) * 100,  # 转换为百分比
                    "high_24h": float(ticker["high24h"]),
                    "low_24h": float(ticker["low24h"]),
                    "volume_24h": float(ticker["vol24h"]),
                    "timestamp": int(ticker["ts"])
                }
        except Exception as e:
            logger.error(f"❌ REST API获取价格失败: {e}")
        
        # 返回默认数据
        return {
            "symbol": symbol,
            "price": 0,
            "change_24h": 0,
            "high_24h": 0,
            "low_24h": 0,
            "volume_24h": 0,
            "timestamp": int(time.time() * 1000)
        }


# HTTP服务器，提供REST API接口
class KlineHttpHandler(BaseHTTPRequestHandler):
    okx_service = None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip('/').split('/')
        query_params = parse_qs(parsed.query)
        
        try:
            if len(path_parts) >= 3 and path_parts[0] == 'klines':
                # /klines/BTC/USDT
                symbol = f"{path_parts[1]}/{path_parts[2]}"
                timeframe = query_params.get('timeframe', ['1h'])[0]
                limit = int(query_params.get('limit', ['100'])[0])
                
                data = self.okx_service.get_klines(symbol, timeframe, limit)
                self.send_json_response(data)
                
            elif len(path_parts) >= 3 and path_parts[0] == 'stats':
                # /stats/BTC/USDT
                symbol = f"{path_parts[1]}/{path_parts[2]}"
                data = self.okx_service.get_ticker(symbol)
                self.send_json_response(data)
                
            elif path_parts[0] == 'health':
                # /health - 健康检查
                data = {
                    "status": "ok",
                    "websocket_connected": self.okx_service.is_connected,
                    "timestamp": int(time.time() * 1000)
                }
                self.send_json_response(data)
                
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            logger.error(f"❌ 处理HTTP请求失败: {e}")
            self.send_error(500, str(e))
    
    def send_json_response(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """处理跨域预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def log_message(self, format, *args):
        """简化日志输出"""
        if any(keyword in args[0] for keyword in ['klines', 'stats', 'health']):
            logger.info(f"HTTP: {format % args}")


async def main():
    """主函数"""
    logger.info("🚀 启动OKX WebSocket K线数据服务")
    
    # 创建OKX服务实例
    okx_service = OKXKlineService()
    KlineHttpHandler.okx_service = okx_service
    
    # 启动HTTP服务器
    def start_http_server():
        server = HTTPServer(('0.0.0.0', 8002), KlineHttpHandler)
        logger.info("🌐 HTTP服务器启动在端口8002")
        server.serve_forever()
    
    http_thread = Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # 连接WebSocket并保持运行
    while True:
        try:
            await okx_service.connect_websocket()
        except Exception as e:
            logger.error(f"❌ WebSocket连接错误: {e}")
        
        logger.info("⏳ 10秒后重新连接...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 服务已停止")