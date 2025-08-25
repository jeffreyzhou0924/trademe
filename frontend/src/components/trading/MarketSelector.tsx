import React, { useState, useEffect } from 'react'
import { useMarketStore } from '../../store/marketStore'
import type { TickerData } from '../../types/market'

const MarketSelector: React.FC = () => {
  const {
    selectedSymbol,
    selectedTimeframe,
    selectedExchange,
    currentPrices,
    setSelectedSymbol,
    setSelectedTimeframe,
    setSelectedExchange,
    subscribeToTicker,
    unsubscribeFromTicker
  } = useMarketStore()

  const [searchQuery, setSearchQuery] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)

  // 预定义的热门交易对
  const popularPairs = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT',
    'XRP/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT'
  ]

  // 支持的交易所
  const exchanges = [
    { id: 'binance', name: '币安', icon: '🔶' },
    { id: 'okx', name: 'OKX', icon: '🔵' },
    { id: 'huobi', name: '火币', icon: '🔴' },
    { id: 'gate', name: 'Gate.io', icon: '🟢' }
  ]

  // 时间周期选项
  const timeframes = [
    { value: '1m', label: '1分钟' },
    { value: '5m', label: '5分钟' },
    { value: '15m', label: '15分钟' },
    { value: '30m', label: '30分钟' },
    { value: '1h', label: '1小时' },
    { value: '4h', label: '4小时' },
    { value: '1d', label: '1天' },
    { value: '1w', label: '1周' }
  ]

  // 过滤交易对
  const filteredPairs = popularPairs.filter(pair =>
    pair.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 获取当前价格数据
  const currentPrice = currentPrices[selectedSymbol]

  // 订阅价格推送
  useEffect(() => {
    subscribeToTicker(selectedSymbol, selectedExchange)
    
    return () => {
      unsubscribeFromTicker(selectedSymbol, selectedExchange)
    }
  }, [selectedSymbol, selectedExchange, subscribeToTicker, unsubscribeFromTicker])

  const handleSymbolChange = (symbol: string) => {
    setSelectedSymbol(symbol)
    setShowDropdown(false)
    setSearchQuery('')
  }

  const handleExchangeChange = (exchange: string) => {
    setSelectedExchange(exchange)
  }

  const handleTimeframeChange = (timeframe: string) => {
    setSelectedTimeframe(timeframe)
  }

  const formatPrice = (price: number) => {
    return price?.toLocaleString('en-US', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 8 
    })
  }

  const formatChange = (change: number) => {
    const sign = change >= 0 ? '+' : ''
    return `${sign}${change?.toFixed(2)}%`
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      {/* 交易对选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          交易对
        </label>
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="w-full px-3 py-2 text-left border border-gray-300 rounded-md bg-white hover:border-gray-400 focus:outline-none focus:border-brand-500"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="font-medium">{selectedSymbol}</span>
                {currentPrice && (
                  <div className="flex items-center space-x-2">
                    <span className="text-sm text-gray-500">
                      ${formatPrice(currentPrice.price)}
                    </span>
                    <span className={`text-sm ${
                      currentPrice.change >= 0 ? 'text-success-500' : 'text-danger-500'
                    }`}>
                      {formatChange(currentPrice.change_percent)}
                    </span>
                  </div>
                )}
              </div>
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </button>

          {showDropdown && (
            <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg">
              {/* 搜索框 */}
              <div className="p-3 border-b border-gray-200">
                <input
                  type="text"
                  placeholder="搜索交易对..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:border-brand-500"
                />
              </div>

              {/* 交易对列表 */}
              <div className="max-h-60 overflow-y-auto">
                {filteredPairs.map((pair) => (
                  <button
                    key={pair}
                    onClick={() => handleSymbolChange(pair)}
                    className={`w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center justify-between ${
                      pair === selectedSymbol ? 'bg-brand-50 text-brand-600' : ''
                    }`}
                  >
                    <span className="font-medium">{pair}</span>
                    {currentPrices[pair] && (
                      <div className="flex items-center space-x-2 text-sm">
                        <span className="text-gray-500">
                          ${formatPrice(currentPrices[pair].price)}
                        </span>
                        <span className={
                          currentPrices[pair].change >= 0 ? 'text-success-500' : 'text-danger-500'
                        }>
                          {formatChange(currentPrices[pair].change_percent)}
                        </span>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 交易所选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          交易所
        </label>
        <div className="flex flex-wrap gap-2">
          {exchanges.map((exchange) => (
            <button
              key={exchange.id}
              onClick={() => handleExchangeChange(exchange.id)}
              className={`flex items-center space-x-1 px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                selectedExchange === exchange.id
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <span>{exchange.icon}</span>
              <span>{exchange.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 时间周期选择 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          时间周期
        </label>
        <div className="grid grid-cols-4 gap-2">
          {timeframes.map((timeframe) => (
            <button
              key={timeframe.value}
              onClick={() => handleTimeframeChange(timeframe.value)}
              className={`px-2 py-1 text-sm font-medium rounded transition-colors ${
                selectedTimeframe === timeframe.value
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {timeframe.label}
            </button>
          ))}
        </div>
      </div>

      {/* 市场数据统计 */}
      {currentPrice && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">24H最高:</span>
              <div className="font-medium">${formatPrice(currentPrice.high_24h)}</div>
            </div>
            <div>
              <span className="text-gray-500">24H最低:</span>
              <div className="font-medium">${formatPrice(currentPrice.low_24h)}</div>
            </div>
            <div>
              <span className="text-gray-500">24H成交量:</span>
              <div className="font-medium">{currentPrice.volume_24h?.toLocaleString()}</div>
            </div>
            <div>
              <span className="text-gray-500">涨跌幅:</span>
              <div className={`font-medium ${
                currentPrice.change >= 0 ? 'text-success-500' : 'text-danger-500'
              }`}>
                {formatChange(currentPrice.change_percent)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MarketSelector