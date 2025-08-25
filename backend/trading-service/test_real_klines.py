"""
测试真实K线数据获取
"""
import asyncio
import ccxt.async_support as ccxt
from datetime import datetime

async def test_real_klines():
    """测试真实K线数据获取"""
    try:
        # 初始化OKX交易所
        exchange = ccxt.okx({
            'sandbox': False,  # 使用真实环境
            'timeout': 30000,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        
        print("🔄 正在连接OKX交易所...")
        
        # 加载市场信息
        await exchange.load_markets()
        print("✅ OKX交易所连接成功")
        
        # 获取支持的交易对
        symbols = list(exchange.markets.keys())
        btc_symbols = [s for s in symbols if 'BTC' in s and 'USDT' in s][:5]
        print(f"📊 支持的BTC交易对示例: {btc_symbols}")
        
        # 测试获取BTC/USDT的K线数据
        symbol = 'BTC/USDT'
        timeframe = '1h'
        limit = 5
        
        print(f"🔄 正在获取 {symbol} {timeframe} K线数据...")
        
        # 获取K线数据
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        print(f"✅ 成功获取{len(ohlcv)}条K线数据:")
        for i, candle in enumerate(ohlcv[-3:]):  # 显示最后3条
            timestamp, open_price, high, low, close, volume = candle
            dt = datetime.fromtimestamp(timestamp / 1000)
            print(f"  {i+1}. {dt.strftime('%Y-%m-%d %H:%M')} | "
                  f"开盘:{open_price:.2f} 最高:{high:.2f} 最低:{low:.2f} "
                  f"收盘:{close:.2f} 成交量:{volume:.2f}")
        
        # 测试其他热门交易对
        for test_symbol in ['ETH/USDT', 'BNB/USDT']:
            try:
                print(f"\n🔄 测试 {test_symbol}...")
                test_ohlcv = await exchange.fetch_ohlcv(test_symbol, '1h', limit=1)
                if test_ohlcv:
                    candle = test_ohlcv[0]
                    timestamp, open_price, high, low, close, volume = candle
                    print(f"✅ {test_symbol}: 收盘价 {close:.2f} USDT")
                else:
                    print(f"❌ {test_symbol}: 无数据")
            except Exception as e:
                print(f"❌ {test_symbol}: {str(e)}")
        
        print(f"\n🎉 真实K线数据测试完成！返回的数据格式:")
        print(f"   [timestamp_ms, open, high, low, close, volume]")
        print(f"   示例: {ohlcv[-1]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False
    finally:
        if 'exchange' in locals():
            await exchange.close()

if __name__ == "__main__":
    success = asyncio.run(test_real_klines())
    if success:
        print("\n✅ 真实K线数据测试通过，可以部署到生产环境！")
    else:
        print("\n❌ 真实K线数据测试失败，需要检查网络连接或API配置")