"""
简单的K线数据HTTP服务器
"""
import asyncio
import json
import sys
sys.path.append('/root/trademe/backend/trading-service')

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from app.services.market_service import MarketService

class KlineHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 解析URL
            parsed_url = urlparse(self.path)
            path_parts = parsed_url.path.strip('/').split('/')
            query_params = parse_qs(parsed_url.query)
            
            # 跨域设置
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            self.end_headers()
            
            if len(path_parts) >= 2 and path_parts[0] == 'klines':
                # 获取K线数据 - 处理可能的多级路径
                if len(path_parts) >= 3:
                    # 如果是 /klines/BTC/USDT 格式
                    symbol = f"{path_parts[1]}/{path_parts[2]}"
                else:
                    # 如果是 /klines/BTC%2FUSDT 格式  
                    symbol = path_parts[1].replace('%2F', '/')  # 解码URL编码的斜杠
                exchange = query_params.get('exchange', ['okx'])[0]
                timeframe = query_params.get('timeframe', ['1h'])[0]
                limit = int(query_params.get('limit', ['100'])[0])
                
                print(f"🔄 获取K线: {symbol}, 交易所: {exchange}, 周期: {timeframe}")
                
                # 异步获取数据
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    klines = loop.run_until_complete(
                        MarketService.get_klines(exchange, symbol, timeframe, limit)
                    )
                    
                    result = {"klines": klines, "symbol": symbol, "count": len(klines)}
                    self.wfile.write(json.dumps(result).encode())
                    print(f"✅ 成功返回 {len(klines)} 条K线数据")
                    
                finally:
                    loop.close()
                    
            elif len(path_parts) >= 2 and path_parts[0] == 'stats':
                # 获取市场统计 - 处理可能的多级路径
                if len(path_parts) >= 3:
                    # 如果是 /stats/BTC/USDT 格式
                    symbol = f"{path_parts[1]}/{path_parts[2]}"
                else:
                    # 如果是 /stats/BTC%2FUSDT 格式
                    symbol = path_parts[1].replace('%2F', '/')
                exchange = query_params.get('exchange', ['okx'])[0]
                
                print(f"🔄 获取统计: {symbol}, 交易所: {exchange}")
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    stats = loop.run_until_complete(
                        MarketService.get_market_stats(exchange, symbol)
                    )
                    
                    self.wfile.write(json.dumps(stats).encode())
                    print(f"✅ 成功返回市场统计数据")
                    
                finally:
                    loop.close()
            else:
                # 默认响应
                response = {"message": "简单K线服务器", "endpoints": ["/klines/{symbol}", "/stats/{symbol}"]}
                self.wfile.write(json.dumps(response).encode())
                
        except Exception as e:
            print(f"❌ 请求处理失败: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {"error": str(e)}
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_OPTIONS(self):
        # 处理预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

def run_server():
    server_address = ('', 8002)
    httpd = HTTPServer(server_address, KlineHandler)
    print("🚀 简单K线服务器启动在 http://localhost:8002")
    print("📊 测试端点:")
    print("   GET /klines/BTC%2FUSDT?exchange=okx&timeframe=1h&limit=5")
    print("   GET /stats/BTC%2FUSDT?exchange=okx")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()