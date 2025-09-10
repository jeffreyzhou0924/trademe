import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'

const WatchList: React.FC = () => {
  const {
    watchList,
    selectedSymbol,
    selectedExchange,
    setSelectedSymbol,
    setSelectedExchange,
    removeFromWatchList,
    updateWatchListPrices
  } = useTradingPageStore()

  const [sortBy, setSortBy] = useState<'symbol' | 'price' | 'change' | 'volume'>('symbol')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  // 排序自选列表
  const sortedWatchList = [...watchList].sort((a, b) => {
    let aValue: number | string
    let bValue: number | string

    switch (sortBy) {
      case 'price':
        aValue = a.price
        bValue = b.price
        break
      case 'change':
        aValue = a.changePercent24h
        bValue = b.changePercent24h
        break
      case 'volume':
        aValue = a.volume24h
        bValue = b.volume24h
        break
      default:
        aValue = a.symbol
        bValue = b.symbol
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortOrder === 'asc' 
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue)
    } else {
      return sortOrder === 'asc' 
        ? (aValue as number) - (bValue as number)
        : (bValue as number) - (aValue as number)
    }
  })

  // 处理排序
  const handleSort = (field: typeof sortBy) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  // 处理品种选择
  const handleSymbolSelect = (symbol: string, exchange: string) => {
    setSelectedSymbol(symbol)
    setSelectedExchange(exchange)
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

  // 获取排序图标
  const getSortIcon = (field: typeof sortBy) => {
    if (sortBy !== field) {
      return (
        <svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      )
    }
    
    return sortOrder === 'asc' ? (
      <svg className="w-3 h-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="w-3 h-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    )
  }

  if (watchList.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-gray-400 dark:text-gray-500 mb-3">
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                      d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              暂无自选品种
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">
              在市场列表中点击❤️图标添加自选品种
            </p>
            <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
              浏览市场
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* 排序头部 */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 dark:text-gray-400">
          <button
            onClick={() => handleSort('symbol')}
            className="col-span-4 flex items-center space-x-1 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <span>品种</span>
            {getSortIcon('symbol')}
          </button>
          
          <button
            onClick={() => handleSort('price')}
            className="col-span-3 flex items-center space-x-1 justify-end hover:text-gray-700 dark:hover:text-gray-300"
          >
            <span>价格</span>
            {getSortIcon('price')}
          </button>
          
          <button
            onClick={() => handleSort('change')}
            className="col-span-3 flex items-center space-x-1 justify-end hover:text-gray-700 dark:hover:text-gray-300"
          >
            <span>涨跌幅</span>
            {getSortIcon('change')}
          </button>
          
          <button
            onClick={() => handleSort('volume')}
            className="col-span-2 flex items-center space-x-1 justify-end hover:text-gray-700 dark:hover:text-gray-300"
          >
            <span>量</span>
            {getSortIcon('volume')}
          </button>
        </div>
      </div>

      {/* 自选列表 */}
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-1 p-2">
          {sortedWatchList.map((item, index) => {
            const isSelected = selectedSymbol === item.symbol && selectedExchange === item.exchange
            const isPositive = item.changePercent24h >= 0
            const timeSinceUpdate = Date.now() - item.lastUpdated
            const isStale = timeSinceUpdate > 60000 // 超过1分钟算陈旧
            
            return (
              <div
                key={`${item.exchange}-${item.symbol}-${index}`}
                className={`grid grid-cols-12 gap-2 p-2 rounded-lg cursor-pointer transition-all group ${
                  isSelected
                    ? 'bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700'
                    : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
                onClick={() => handleSymbolSelect(item.symbol, item.exchange)}
              >
                {/* 品种信息 */}
                <div className="col-span-4 flex flex-col justify-center">
                  <div className="flex items-center space-x-1">
                    <span className="font-medium text-gray-900 dark:text-white text-sm">
                      {item.symbol.split('/')[0]}
                    </span>
                    {isStale && (
                      <div className="w-1.5 h-1.5 bg-yellow-400 rounded-full" title="数据可能不是最新" />
                    )}
                  </div>
                  <div className="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-400">
                    <span>{item.exchange}</span>
                    <span>/{item.symbol.split('/')[1]}</span>
                  </div>
                </div>

                {/* 价格 */}
                <div className="col-span-3 flex flex-col justify-center items-end">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    ${formatPrice(item.price)}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    ${formatPrice(Math.abs(item.change24h))}
                  </span>
                </div>

                {/* 涨跌幅 */}
                <div className="col-span-3 flex flex-col justify-center items-end">
                  <span className={`text-sm font-medium ${
                    isPositive 
                      ? 'text-green-600 dark:text-green-400' 
                      : 'text-red-600 dark:text-red-400'
                  }`}>
                    {isPositive ? '+' : ''}{item.changePercent24h.toFixed(2)}%
                  </span>
                </div>

                {/* 成交量和删除按钮 */}
                <div className="col-span-2 flex items-center justify-end space-x-1">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {formatVolume(item.volume24h)}
                  </div>
                  
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFromWatchList(item.symbol, item.exchange)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900 transition-all"
                    title="从自选中移除"
                  >
                    <svg className="w-3 h-3 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 底部操作栏 */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>共{watchList.length}个品种</span>
          
          <div className="flex items-center space-x-3">
            <button 
              onClick={() => {
                // 模拟更新价格
                const updates = watchList.map(item => ({
                  ...item,
                  price: item.price * (1 + (Math.random() - 0.5) * 0.02),
                  change24h: item.change24h * (1 + (Math.random() - 0.5) * 0.1),
                  changePercent24h: item.changePercent24h * (1 + (Math.random() - 0.5) * 0.1),
                  lastUpdated: Date.now()
                }))
                updateWatchListPrices(updates)
              }}
              className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              刷新
            </button>
            
            <button 
              onClick={() => {
                // 清空自选列表
                watchList.forEach(item => {
                  removeFromWatchList(item.symbol, item.exchange)
                })
              }}
              className="hover:text-red-600 dark:hover:text-red-400 transition-colors"
            >
              清空
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default WatchList