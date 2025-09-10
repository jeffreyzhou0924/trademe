import React, { useState, useEffect, useMemo } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'

const OrderBook: React.FC = () => {
  const {
    selectedSymbol,
    selectedExchange,
    orderBookData,
    updateOrderBook
  } = useTradingPageStore()

  const [precision, setPrecision] = useState(2)
  const [depthSize, setDepthSize] = useState<10 | 20 | 50>(20)

  // 模拟订单薄数据
  useEffect(() => {
    if (!selectedSymbol || !selectedExchange) return

    const generateOrderBook = () => {
      const basePrice = 42500 + Math.random() * 1000 // 模拟基准价格
      const spread = 1 + Math.random() * 5 // 点差
      
      const bids: [number, number][] = []
      const asks: [number, number][] = []
      
      // 生成买单 (价格递减)
      for (let i = 0; i < depthSize; i++) {
        const price = basePrice - spread / 2 - i * (0.5 + Math.random() * 2)
        const quantity = 0.1 + Math.random() * 5
        bids.push([price, quantity])
      }
      
      // 生成卖单 (价格递增)
      for (let i = 0; i < depthSize; i++) {
        const price = basePrice + spread / 2 + i * (0.5 + Math.random() * 2)
        const quantity = 0.1 + Math.random() * 5
        asks.push([price, quantity])
      }
      
      updateOrderBook({
        symbol: selectedSymbol,
        bids: bids.sort((a, b) => b[0] - a[0]), // 价格降序
        asks: asks.sort((a, b) => a[0] - b[0]), // 价格升序
        timestamp: Date.now()
      })
    }

    generateOrderBook()
    const interval = setInterval(generateOrderBook, 1000) // 每秒更新

    return () => clearInterval(interval)
  }, [selectedSymbol, selectedExchange, depthSize, updateOrderBook])

  // 计算汇总数据
  const summaryData = useMemo(() => {
    if (!orderBookData) return null

    const totalBidVolume = orderBookData.bids.reduce((sum, [, quantity]) => sum + quantity, 0)
    const totalAskVolume = orderBookData.asks.reduce((sum, [, quantity]) => sum + quantity, 0)
    const bestBid = orderBookData.bids[0]?.[0] || 0
    const bestAsk = orderBookData.asks[0]?.[0] || 0
    const spread = bestAsk - bestBid
    const spreadPercent = bestBid > 0 ? (spread / bestBid) * 100 : 0

    return {
      totalBidVolume,
      totalAskVolume,
      bestBid,
      bestAsk,
      spread,
      spreadPercent,
      midPrice: (bestBid + bestAsk) / 2
    }
  }, [orderBookData])

  // 格式化价格
  const formatPrice = (price: number) => {
    return price.toFixed(precision)
  }

  // 格式化数量
  const formatQuantity = (quantity: number) => {
    if (quantity >= 1000) return (quantity / 1000).toFixed(2) + 'K'
    if (quantity >= 1) return quantity.toFixed(3)
    return quantity.toFixed(4)
  }

  // 计算累积量
  const calculateCumulative = (orders: [number, number][], reverse = false) => {
    let cumulative = 0
    const result = []
    
    const processedOrders = reverse ? [...orders].reverse() : orders
    
    for (const [price, quantity] of processedOrders) {
      cumulative += quantity
      result.push([price, quantity, cumulative])
    }
    
    return reverse ? result.reverse() : result
  }

  if (!selectedSymbol) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="text-gray-400 dark:text-gray-500 mb-2">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                    d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
            </svg>
          </div>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            请选择交易品种查看深度数据
          </p>
        </div>
      </div>
    )
  }

  if (!orderBookData) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            加载订单薄数据...
          </p>
        </div>
      </div>
    )
  }

  const cumulativeBids = calculateCumulative(orderBookData.bids.slice(0, depthSize))
  const cumulativeAsks = calculateCumulative(orderBookData.asks.slice(0, depthSize))
  const maxCumulative = Math.max(
    cumulativeBids[cumulativeBids.length - 1]?.[2] || 0,
    cumulativeAsks[cumulativeAsks.length - 1]?.[2] || 0
  )

  return (
    <div className="h-full flex flex-col">
      {/* 控制栏 */}
      <div className="p-3 border-b border-gray-200 dark:border-gray-700 space-y-2">
        {/* 品种信息 */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900 dark:text-white text-sm">
              {selectedSymbol}
            </h3>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {selectedExchange} · 深度
            </div>
          </div>
          
          {summaryData && (
            <div className="text-right">
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                ${formatPrice(summaryData.midPrice)}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                点差 {summaryData.spreadPercent.toFixed(3)}%
              </div>
            </div>
          )}
        </div>

        {/* 设置选项 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">精度:</label>
            <select
              value={precision}
              onChange={(e) => setPrecision(Number(e.target.value))}
              className="text-xs border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value={0}>1</option>
              <option value={1}>0.1</option>
              <option value={2}>0.01</option>
              <option value={3}>0.001</option>
            </select>
          </div>
          
          <div className="flex items-center space-x-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">深度:</label>
            <select
              value={depthSize}
              onChange={(e) => setDepthSize(Number(e.target.value) as 10 | 20 | 50)}
              className="text-xs border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value={10}>10档</option>
              <option value={20}>20档</option>
              <option value={50}>50档</option>
            </select>
          </div>
        </div>
      </div>

      {/* 表头 */}
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700">
        <div className="grid grid-cols-3 gap-2 text-xs font-medium text-gray-500 dark:text-gray-400">
          <div>价格({selectedSymbol.split('/')[1]})</div>
          <div className="text-right">数量({selectedSymbol.split('/')[0]})</div>
          <div className="text-right">累计</div>
        </div>
      </div>

      {/* 订单薄内容 */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* 卖单区域 (ask) */}
        <div className="flex-1 overflow-y-auto">
          <div className="space-y-0.5 p-2">
            {cumulativeAsks.slice(0, Math.floor(depthSize / 2)).reverse().map(([price, quantity, cumulative], index) => (
              <div
                key={`ask-${price}-${index}`}
                className="relative grid grid-cols-3 gap-2 text-xs py-1 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors group"
              >
                {/* 背景条 */}
                <div 
                  className="absolute inset-y-0 right-0 bg-red-100 dark:bg-red-900/30 opacity-30"
                  style={{ width: `${(cumulative / maxCumulative) * 100}%` }}
                />
                
                <div className="text-red-600 dark:text-red-400 font-medium relative z-10">
                  {formatPrice(price)}
                </div>
                <div className="text-right text-gray-900 dark:text-white relative z-10">
                  {formatQuantity(quantity)}
                </div>
                <div className="text-right text-gray-500 dark:text-gray-400 relative z-10">
                  {formatQuantity(cumulative)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 中间价格区域 */}
        {summaryData && (
          <div className="px-3 py-2 bg-gray-50 dark:bg-gray-800 border-y border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <div className="text-xs text-gray-500 dark:text-gray-400">
                点差: ${formatPrice(summaryData.spread)}
              </div>
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                ${formatPrice(summaryData.midPrice)}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {summaryData.spreadPercent.toFixed(3)}%
              </div>
            </div>
          </div>
        )}

        {/* 买单区域 (bid) */}
        <div className="flex-1 overflow-y-auto">
          <div className="space-y-0.5 p-2">
            {cumulativeBids.slice(0, Math.floor(depthSize / 2)).map(([price, quantity, cumulative], index) => (
              <div
                key={`bid-${price}-${index}`}
                className="relative grid grid-cols-3 gap-2 text-xs py-1 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors group"
              >
                {/* 背景条 */}
                <div 
                  className="absolute inset-y-0 right-0 bg-green-100 dark:bg-green-900/30 opacity-30"
                  style={{ width: `${(cumulative / maxCumulative) * 100}%` }}
                />
                
                <div className="text-green-600 dark:text-green-400 font-medium relative z-10">
                  {formatPrice(price)}
                </div>
                <div className="text-right text-gray-900 dark:text-white relative z-10">
                  {formatQuantity(quantity)}
                </div>
                <div className="text-right text-gray-500 dark:text-gray-400 relative z-10">
                  {formatQuantity(cumulative)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 底部统计 */}
      {summaryData && (
        <div className="p-3 border-t border-gray-200 dark:border-gray-700">
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <div className="text-gray-500 dark:text-gray-400 mb-1">买单总量</div>
              <div className="text-green-600 dark:text-green-400 font-medium">
                {formatQuantity(summaryData.totalBidVolume)}
              </div>
            </div>
            <div>
              <div className="text-gray-500 dark:text-gray-400 mb-1">卖单总量</div>
              <div className="text-red-600 dark:text-red-400 font-medium">
                {formatQuantity(summaryData.totalAskVolume)}
              </div>
            </div>
          </div>
          
          <div className="mt-2 text-xs text-gray-400 dark:text-gray-500 text-center">
            更新时间: {new Date(orderBookData.timestamp).toLocaleTimeString()}
          </div>
        </div>
      )}
    </div>
  )
}

export default OrderBook