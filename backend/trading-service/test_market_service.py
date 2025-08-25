"""
直接测试MarketService的真实数据获取
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.market_service import MarketService

async def test_market_service():
    """测试MarketService真实数据获取"""
    try:
        print("🔄 测试MarketService获取真实K线数据...")
        
        # 测试不同的交易对格式
        test_symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
        
        for symbol in test_symbols:
            print(f"\n📊 测试交易对: {symbol}")
            
            try:
                # 获取K线数据
                klines = await MarketService.get_klines(
                    exchange='okx',
                    symbol=symbol,
                    timeframe='1h',
                    limit=5
                )
                
                if klines:
                    print(f"✅ 成功获取 {len(klines)} 条K线数据")
                    # 显示最新一条数据
                    latest = klines[-1]
                    print(f"   最新K线: 时间戳={latest[0]}, 开盘={latest[1]}, 最高={latest[2]}, 最低={latest[3]}, 收盘={latest[4]}, 成交量={latest[5]}")
                else:
                    print(f"❌ 未获取到K线数据")
                    
                # 测试市场统计
                stats = await MarketService.get_market_stats('okx', symbol)
                if stats and 'current_price' in stats:
                    print(f"📈 市场统计: 当前价格={stats['current_price']}, 24h最高={stats.get('high_24h', 'N/A')}")
                    
            except Exception as e:
                print(f"❌ {symbol} 测试失败: {str(e)}")
        
        print(f"\n🎉 MarketService测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ MarketService测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_market_service())
    if success:
        print("\n✅ MarketService真实数据集成成功！")
    else:
        print("\n❌ MarketService集成需要调试")