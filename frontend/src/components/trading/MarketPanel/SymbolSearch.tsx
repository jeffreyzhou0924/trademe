import React, { useState, useMemo } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import type { WatchlistItem } from '@/store/tradingPageStore'

const SymbolSearch: React.FC = () => {
  const {
    selectedSymbol,
    selectedExchange,
    setSelectedSymbol,
    setSelectedExchange,
    addToWatchList
  } = useTradingPageStore()

  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  // 模拟市场数据 - 实际应该从API获取
  const marketData = useMemo(() => [
    // BTC交易对
    { symbol: 'BTC/USDT', exchange: 'OKX', price: 42580.5, change24h: 1280.3, changePercent24h: 3.1, volume24h: 2450000000, category: 'spot', baseAsset: 'BTC', quoteAsset: 'USDT' },
    { symbol: 'BTC/USDT', exchange: 'Binance', price: 42575.2, change24h: 1275.1, changePercent24h: 3.09, volume24h: 2380000000, category: 'spot', baseAsset: 'BTC', quoteAsset: 'USDT' },
    { symbol: 'BTC/ETH', exchange: 'OKX', price: 18.45, change24h: 0.32, changePercent24h: 1.77, volume24h: 145000000, category: 'spot', baseAsset: 'BTC', quoteAsset: 'ETH' },
    
    // ETH交易对
    { symbol: 'ETH/USDT', exchange: 'OKX', price: 2310.8, change24h: 45.2, changePercent24h: 2.0, volume24h: 1850000000, category: 'spot', baseAsset: 'ETH', quoteAsset: 'USDT' },
    { symbol: 'ETH/USDT', exchange: 'Binance', price: 2308.5, change24h: 42.8, changePercent24h: 1.89, volume24h: 1720000000, category: 'spot', baseAsset: 'ETH', quoteAsset: 'USDT' },
    { symbol: 'ETH/BTC', exchange: 'OKX', price: 0.0542, change24h: -0.0008, changePercent24h: -1.45, volume24h: 89000000, category: 'spot', baseAsset: 'ETH', quoteAsset: 'BTC' },
    
    // 其他主流币
    { symbol: 'SOL/USDT', exchange: 'OKX', price: 98.45, change24h: 5.23, changePercent24h: 5.6, volume24h: 650000000, category: 'spot', baseAsset: 'SOL', quoteAsset: 'USDT' },
    { symbol: 'ADA/USDT', exchange: 'OKX', price: 0.485, change24h: 0.018, changePercent24h: 3.85, volume24h: 280000000, category: 'spot', baseAsset: 'ADA', quoteAsset: 'USDT' },
    { symbol: 'DOT/USDT', exchange: 'OKX', price: 6.78, change24h: -0.15, changePercent24h: -2.17, volume24h: 180000000, category: 'spot', baseAsset: 'DOT', quoteAsset: 'USDT' },
    { symbol: 'LINK/USDT', exchange: 'OKX', price: 14.52, change24h: 0.68, changePercent24h: 4.91, volume24h: 320000000, category: 'spot', baseAsset: 'LINK', quoteAsset: 'USDT' },
    
    // 合约
    { symbol: 'BTC-PERPETUAL', exchange: 'OKX', price: 42585.0, change24h: 1285.0, changePercent24h: 3.12, volume24h: 5200000000, category: 'futures', baseAsset: 'BTC', quoteAsset: 'USD' },
    { symbol: 'ETH-PERPETUAL', exchange: 'OKX', price: 2312.5, change24h: 46.8, changePercent24h: 2.07, volume24h: 3100000000, category: 'futures', baseAsset: 'ETH', quoteAsset: 'USD' }
  ], [])

  // 交易所列表
  const exchanges = ['OKX', 'Binance', 'Huobi', 'Bybit', 'Gate.io']
  
  // 分类列表
  const categories = [
    { key: 'all', name: '全部', icon: '📊' },
    { key: 'spot', name: '现货', icon: '💰' },
    { key: 'futures', name: '合约', icon: '📈' },
    { key: 'favorites', name: '热门', icon: '🔥' }
  ]

  // 过滤市场数据
  const filteredData = useMemo(() => {
    return marketData.filter(item => {
      const matchesSearch = item.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           item.baseAsset.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           item.quoteAsset.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesCategory = selectedCategory === 'all' || 
                             item.category === selectedCategory ||
                             (selectedCategory === 'favorites' && ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'].includes(item.symbol))
      return matchesSearch && matchesCategory
    })
  }, [marketData, searchTerm, selectedCategory])

  // 按交易所分组
  const groupedData = useMemo(() => {
    return filteredData.reduce((groups, item) => {
      if (!groups[item.exchange]) {
        groups[item.exchange] = []
      }
      groups[item.exchange].push(item)
      return groups
    }, {} as Record<string, typeof filteredData>)
  }, [filteredData])

  // 处理品种选择
  const handleSymbolSelect = (symbol: string, exchange: string) => {
    setSelectedSymbol(symbol)
    setSelectedExchange(exchange)
  }

  // 添加到自选
  const handleAddToWatchlist = (item: typeof marketData[0]) => {
    const watchlistItem: WatchlistItem = {
      symbol: item.symbol,
      exchange: item.exchange,
      price: item.price,
      change24h: item.change24h,
      changePercent24h: item.changePercent24h,
      volume24h: item.volume24h,
      lastUpdated: Date.now()
    }
    addToWatchList(watchlistItem)
  }

  // 格式化价格
  const formatPrice = (price: number) => {
    if (price >= 1000) return price.toLocaleString()
    if (price >= 1) return price.toFixed(2)
    if (price >= 0.01) return price.toFixed(4)
    return price.toFixed(6)
  }

  // 格式化成交量
  const formatVolume = (volume: number) => {
    if (volume >= 1e9) return (volume / 1e9).toFixed(1) + 'B'
    if (volume >= 1e6) return (volume / 1e6).toFixed(1) + 'M'
    if (volume >= 1e3) return (volume / 1e3).toFixed(1) + 'K'
    return volume.toFixed(0)
  }

  return (
    <div className="h-full flex flex-col">
      {/* 搜索框 */}
      <div className="p-4 space-y-3">
        <div className="relative">
          <input
            type="text"
            placeholder="搜索交易对..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {/* 分类过滤 */}
        <div className="flex space-x-1">
          {categories.map((category) => (
            <button
              key={category.key}
              onClick={() => setSelectedCategory(category.key)}
              className={`flex items-center space-x-1 px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedCategory === category.key
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              <span>{category.icon}</span>
              <span>{category.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 市场列表 */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {Object.keys(groupedData).length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-400 dark:text-gray-500 mb-2">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              未找到匹配的交易对
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedData).map(([exchange, items]) => (
              <div key={exchange}>
                {/* 交易所标题 */}
                <div className="flex items-center space-x-2 mb-2">
                  <div className="w-6 h-6 bg-blue-100 dark:bg-blue-900 rounded flex items-center justify-center">
                    <span className="text-xs font-bold text-blue-600 dark:text-blue-400">
                      {exchange[0]}
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                    {exchange}
                  </h3>
                  <div className="flex-1 border-t border-gray-200 dark:border-gray-600"></div>
                </div>

                {/* 交易对列表 */}
                <div className="space-y-1">
                  {items.map((item, index) => {
                    const isSelected = selectedSymbol === item.symbol && selectedExchange === item.exchange
                    const isPositive = item.changePercent24h >= 0
                    
                    return (
                      <div
                        key={`${item.exchange}-${item.symbol}-${index}`}
                        className={`p-3 rounded-lg cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                        }`}
                        onClick={() => handleSymbolSelect(item.symbol, item.exchange)}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-medium text-gray-900 dark:text-white text-sm">
                              {item.symbol}
                            </span>
                            {item.category === 'futures' && (
                              <span className="px-1.5 py-0.5 bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200 text-xs rounded">
                                合约
                              </span>
                            )}
                          </div>
                          
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleAddToWatchlist(item)
                            }}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                            title="添加到自选"
                          >
                            <svg className="w-3 h-3 text-gray-400 hover:text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                          </button>
                        </div>
                        
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-900 dark:text-white font-medium">
                            ${formatPrice(item.price)}
                          </span>
                          <span className={`font-medium ${
                            isPositive 
                              ? 'text-green-600 dark:text-green-400' 
                              : 'text-red-600 dark:text-red-400'
                          }`}>
                            {isPositive ? '+' : ''}{item.changePercent24h.toFixed(2)}%
                          </span>
                        </div>
                        
                        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                          <span>24h量: {formatVolume(item.volume24h)}</span>
                          <span className={isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                            {isPositive ? '+' : ''}{formatPrice(Math.abs(item.change24h))}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SymbolSearch