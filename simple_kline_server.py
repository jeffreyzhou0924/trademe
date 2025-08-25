#!/usr/bin/env python3
import json
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import random

class KlineHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip('/').split('/')
        query_params = parse_qs(parsed.query)
        
        try:
            if len(path_parts) >= 3 and path_parts[0] == 'klines':
                # /klines/BTC/USDT
                symbol = f"{path_parts[1]}/{path_parts[2]}"
                exchange = query_params.get('exchange', ['okx'])[0]
                timeframe = query_params.get('timeframe', ['1h'])[0]
                limit = int(query_params.get('limit', ['100'])[0])
                
                # Generate mock data
                klines = self.generate_mock_klines(symbol, timeframe, limit)
                data = {
                    'klines': klines,
                    'symbol': symbol,
                    'exchange': exchange,
                    'timeframe': timeframe,
                    'count': len(klines),
                    'timestamp': int(time.time() * 1000)
                }
                self.send_json_response(data)
                
            elif len(path_parts) >= 3 and path_parts[0] == 'stats':
                # /stats/BTC/USDT
                symbol = f"{path_parts[1]}/{path_parts[2]}"
                data = self.generate_mock_stats(symbol)
                self.send_json_response(data)
                
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            print(f"Error handling request: {e}")
            self.send_error(500, str(e))
    
    def generate_mock_klines(self, symbol, timeframe, limit):
        """Generate mock OHLCV data with realistic 2025 prices"""
        # Updated base prices for 2025 market conditions
        if 'BTC' in symbol:
            base_price = 98000  # BTC around $98k (realistic for 2025)
        elif 'ETH' in symbol:
            base_price = 3500   # ETH around $3.5k
        elif 'SOL' in symbol:
            base_price = 200    # SOL around $200
        else:
            base_price = 1      # Default for other tokens
        
        # Time intervals
        interval_minutes = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '1d': 1440
        }.get(timeframe, 60)
        
        klines = []
        current_time = datetime.now()
        current_price = base_price
        
        for i in range(limit):
            timestamp = current_time - timedelta(minutes=interval_minutes * (limit - i))
            timestamp_ms = int(timestamp.timestamp() * 1000)
            
            # Generate realistic OHLCV data
            open_price = current_price
            high_price = open_price * (1 + random.uniform(0, 0.02))
            low_price = open_price * (1 - random.uniform(0, 0.02))
            close_price = open_price + random.uniform(-open_price*0.01, open_price*0.01)
            volume = random.uniform(10, 1000)
            
            klines.append([
                timestamp_ms,
                round(open_price, 2),
                round(high_price, 2),
                round(low_price, 2),
                round(close_price, 2),
                round(volume, 4)
            ])
            
            current_price = close_price
            
        return klines
    
    def generate_mock_stats(self, symbol):
        """Generate mock market statistics with realistic 2025 prices"""
        if 'BTC' in symbol:
            base_price = 98000  # BTC around $98k (realistic for 2025)
        elif 'ETH' in symbol:
            base_price = 3500   # ETH around $3.5k
        elif 'SOL' in symbol:
            base_price = 200    # SOL around $200
        else:
            base_price = 1      # Default for other tokens
        current_price = base_price + random.uniform(-base_price*0.05, base_price*0.05)
        
        return {
            'symbol': symbol,
            'price': round(current_price, 2),
            'change_24h': round(random.uniform(-5, 5), 2),
            'volume_24h': round(random.uniform(1000000, 10000000), 2),
            'high_24h': round(current_price * 1.05, 2),
            'low_24h': round(current_price * 0.95, 2),
            'timestamp': int(time.time() * 1000)
        }
    
    def send_json_response(self, data):
        """Send JSON response with CORS headers"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to reduce logging noise"""
        if 'klines' in args[0] or 'stats' in args[0]:
            print(f"{datetime.now()}: {format % args}")

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8002), KlineHandler)
    print(f"🚀 K-line server starting on port 8002...")
    print(f"📊 Test URL: http://localhost:8002/klines/BTC/USDT?timeframe=1h&limit=10")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped")
        server.shutdown()
