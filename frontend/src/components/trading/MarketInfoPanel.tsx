import React from 'react'

interface MarketInfoPanelProps {
  symbol: string
  currentPrice: string
  className?: string
}

// 模拟行情数据
const MARKET_DATA = {
  'BTC/USDT': {
    price: '43,250.00',
    change24h: '+1,234.56',
    changePercent: '+2.95%',
    high24h: '43,890.00',
    low24h: '41,560.00',
    volume24h: '2.1B USDT',
    marketCap: '847.5B',
    rank: '#1'
  },
  'ETH/USDT': {
    price: '2,680.50',
    change24h: '+86.25',
    changePercent: '+3.32%',
    high24h: '2,720.80',
    low24h: '2,590.00',
    volume24h: '1.8B USDT',
    marketCap: '322.1B',
    rank: '#2'
  }
}

// 热门交易品种
const TRENDING_SYMBOLS = [
  { symbol: 'BTC/USDT', price: '43,250.00', change: '+2.95%', isUp: true },
  { symbol: 'ETH/USDT', price: '2,680.50', change: '+3.32%', isUp: true },
  { symbol: 'BNB/USDT', price: '645.80', change: '-1.15%', isUp: false },
  { symbol: 'SOL/USDT', price: '98.45', change: '+5.67%', isUp: true },
  { symbol: 'ADA/USDT', price: '0.4521', change: '+1.89%', isUp: true },
  { symbol: 'XRP/USDT', price: '0.6234', change: '-0.78%', isUp: false }
]

const MarketInfoPanel: React.FC<MarketInfoPanelProps> = ({
  symbol,
  currentPrice,
  className = ''
}) => {
  const marketData = MARKET_DATA[symbol as keyof typeof MARKET_DATA] || MARKET_DATA['BTC/USDT']
  const isPositive = marketData.changePercent.startsWith('+')

  return (
    <div className={`bg-white border-l border-gray-200 ${className}`}>
      {/* 主要价格信息 */}
      <div className="p-4 border-b border-gray-100">
        <div className="mb-3">
          <h3 className="text-lg font-bold text-gray-900 mb-1">{symbol}</h3>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-gray-900">
              ${marketData.price}
            </span>
            <span className={`text-sm font-medium ${
              isPositive ? 'text-green-600' : 'text-red-600'
            }`}>
              {marketData.changePercent}
            </span>
          </div>
          <div className={`text-sm ${
            isPositive ? 'text-green-600' : 'text-red-600'
          }`}>
            {isPositive ? '+' : ''}{marketData.change24h}
          </div>
        </div>
      </div>

      {/* 24小时统计 */}
      <div className="p-4 border-b border-gray-100">
        <h4 className="text-sm font-medium text-gray-700 mb-3">24小时统计</h4>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">最高价</span>
            <span className="text-sm font-medium text-gray-900">${marketData.high24h}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">最低价</span>
            <span className="text-sm font-medium text-gray-900">${marketData.low24h}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">成交量</span>
            <span className="text-sm font-medium text-gray-900">{marketData.volume24h}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">市值</span>
            <span className="text-sm font-medium text-gray-900">${marketData.marketCap}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">市值排名</span>
            <span className="text-sm font-medium text-blue-600">{marketData.rank}</span>
          </div>
        </div>
      </div>

      {/* 价格区间指示器 */}
      <div className="p-4 border-b border-gray-100">
        <h4 className="text-sm font-medium text-gray-700 mb-3">24小时价格区间</h4>
        <div className="relative">
          {/* 价格区间条 */}
          <div className="h-2 bg-gradient-to-r from-red-200 via-yellow-200 to-green-200 rounded-full mb-2"></div>
          {/* 当前价格指示器 */}
          <div 
            className="absolute top-0 w-3 h-2 bg-gray-800 rounded-full transform -translate-x-1/2"
            style={{ left: '65%' }} // 根据当前价格在区间中的位置
          ></div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>${marketData.low24h}</span>
            <span>${marketData.high24h}</span>
          </div>
        </div>
      </div>

      {/* 热门交易品种 */}
      <div className="p-4">
        <h4 className="text-sm font-medium text-gray-700 mb-3">热门品种</h4>
        <div className="space-y-2">
          {TRENDING_SYMBOLS.slice(0, 6).map((item, index) => (
            <div 
              key={index} 
              className="flex justify-between items-center py-2 px-2 hover:bg-gray-50 rounded cursor-pointer transition-colors"
            >
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-900">
                  {item.symbol.split('/')[0]}
                </span>
                <span className="text-xs text-gray-500">/USDT</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium text-gray-900">
                  ${item.price}
                </div>
                <div className={`text-xs ${
                  item.isUp ? 'text-green-600' : 'text-red-600'
                }`}>
                  {item.change}
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <button className="w-full mt-3 py-2 text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors">
          查看更多 →
        </button>
      </div>

      {/* 快捷操作 */}
      <div className="p-4 border-t border-gray-100">
        <div className="grid grid-cols-2 gap-2">
          <button className="py-2 px-3 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-md transition-colors">
            买入
          </button>
          <button className="py-2 px-3 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-md transition-colors">
            卖出
          </button>
        </div>
        <button className="w-full mt-2 py-2 px-3 border border-gray-300 hover:border-gray-400 text-gray-700 text-sm font-medium rounded-md transition-colors">
          添加到观察列表
        </button>
      </div>
    </div>
  )
}

export default MarketInfoPanel