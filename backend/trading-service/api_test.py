"""
测试API端点
"""
import asyncio
import sys
sys.path.append('/root/trademe/backend/trading-service')

from app.api.v1.market import get_klines
from app.services.market_service import MarketService

async def test_api_endpoint():
    """测试API端点"""
    try:
        print("🔄 直接调用API端点函数...")
        
        # 模拟API调用
        result = await get_klines(
            symbol='BTC/USDT',
            timeframe='1h', 
            exchange='okx',
            limit=3
        )
        
        print(f"✅ API端点返回: {result}")
        return True
        
    except Exception as e:
        print(f"❌ API端点测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_api_endpoint())