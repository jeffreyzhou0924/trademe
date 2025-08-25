import React, { useState, useEffect } from 'react'
import { useMarketStore } from '../../store/marketStore'

interface OrderBookEntry {
  price: number
  quantity: number
  total: number
}

interface OrderBookProps {
  className?: string
}

const OrderBook: React.FC<OrderBookProps> = ({ className = '' }) => {
  const { selectedSymbol, selectedExchange, currentPrices } = useMarketStore()
  
  // 模拟订单簿数据
  const [orderBook, setOrderBook] = useState<{
    bids: OrderBookEntry[]
    asks: OrderBookEntry[]
    lastUpdate: number
  }>({
    bids: [],
    asks: [],
    lastUpdate: Date.now()
  })

  const [precision, setPrecision] = useState(2)
  const [displayCount, setDisplayCount] = useState(15)

  // 生成模拟订单簿数据
  useEffect(() => {
    const currentPrice = currentPrices[selectedSymbol]?.price || 50000

    const generateOrderBook = () => {
      const bids: OrderBookEntry[] = []
      const asks: OrderBookEntry[] = []
      
      // 生成买单数据 (价格递减)
      for (let i = 0; i < displayCount; i++) {
        const priceOffset = (i + 1) * (Math.random() * 50 + 10)
        const price = currentPrice - priceOffset
        const quantity = Math.random() * 10 + 0.1
        const total = i === 0 ? quantity : bids[i - 1].total + quantity
        
        bids.push({
          price: Number(price.toFixed(precision)),
          quantity: Number(quantity.toFixed(6)),
          total: Number(total.toFixed(6))
        })
      }

      // 生成卖单数据 (价格递增)
      for (let i = 0; i < displayCount; i++) {
        const priceOffset = (i + 1) * (Math.random() * 50 + 10)
        const price = currentPrice + priceOffset
        const quantity = Math.random() * 10 + 0.1
        const total = i === 0 ? quantity : asks[i - 1].total + quantity
        
        asks.push({
          price: Number(price.toFixed(precision)),
          quantity: Number(quantity.toFixed(6)),
          total: Number(total.toFixed(6))
        })
      }

      // 按价格排序
      asks.sort((a, b) => a.price - b.price)
      
      setOrderBook({
        bids,
        asks: asks.reverse(), // 卖单高价在上
        lastUpdate: Date.now()
      })
    }

    generateOrderBook()
    
    // 每2秒更新一次数据
    const interval = setInterval(generateOrderBook, 2000)
    
    return () => clearInterval(interval)
  }, [selectedSymbol, currentPrices, precision, displayCount])

  const formatPrice = (price: number) => {
    return price.toLocaleString('en-US', { 
      minimumFractionDigits: precision, 
      maximumFractionDigits: precision 
    })
  }

  const formatQuantity = (quantity: number) => {
    return quantity.toFixed(6)
  }

  const getMaxTotal = () => {
    const maxBidTotal = Math.max(...orderBook.bids.map(b => b.total))
    const maxAskTotal = Math.max(...orderBook.asks.map(a => a.total))
    return Math.max(maxBidTotal, maxAskTotal)
  }

  const maxTotal = getMaxTotal()
  const baseAsset = selectedSymbol?.split('/')[0] || ''
  const quoteAsset = selectedSymbol?.split('/')[1] || ''
  const currentPrice = currentPrices[selectedSymbol]

  return (
    <div className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`}>
      {/* 标题和控制 */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200">
        <h3 className="text-sm font-medium text-gray-900">订单簿</h3>
        <div className="flex items-center space-x-2">
          {/* 精度控制 */}
          <select
            value={precision}
            onChange={(e) => setPrecision(Number(e.target.value))}
            className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:border-brand-500"
          >
            <option value={0}>整数</option>
            <option value={1}>0.1</option>
            <option value={2}>0.01</option>
            <option value={4}>0.0001</option>
            <option value={6}>0.000001</option>
          </select>
          
          {/* 显示数量控制 */}
          <select
            value={displayCount}
            onChange={(e) => setDisplayCount(Number(e.target.value))}
            className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:border-brand-500"
          >
            <option value={10}>10档</option>
            <option value={15}>15档</option>
            <option value={20}>20档</option>
            <option value={30}>30档</option>
          </select>
        </div>
      </div>

      <div className="p-3">
        {/* 表头 */}
        <div className="grid grid-cols-3 text-xs text-gray-500 mb-2 pb-2 border-b border-gray-100">
          <div className="text-left">价格({quoteAsset})</div>
          <div className="text-right">数量({baseAsset})</div>
          <div className="text-right">累计({baseAsset})</div>
        </div>

        {/* 卖单区域 */}
        <div className="mb-3">
          {orderBook.asks.slice(0, Math.floor(displayCount / 2)).map((ask, index) => (
            <div
              key={`ask-${index}`}
              className="relative grid grid-cols-3 text-xs py-0.5 hover:bg-gray-50 cursor-pointer group"
            >
              {/* 深度背景条 */}
              <div
                className="absolute right-0 top-0 h-full bg-red-50 opacity-60"
                style={{ width: `${(ask.total / maxTotal) * 100}%` }}
              />
              
              <div className="relative text-danger-600 font-medium">
                {formatPrice(ask.price)}
              </div>
              <div className="relative text-right text-gray-700">
                {formatQuantity(ask.quantity)}
              </div>
              <div className="relative text-right text-gray-600">
                {formatQuantity(ask.total)}
              </div>
              
              {/* 悬停时显示详细信息 */}
              <div className="absolute left-0 top-full mt-1 p-2 bg-black text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                <div>总价值: {(ask.price * ask.quantity).toFixed(2)} {quoteAsset}</div>
                <div>平均价: {formatPrice(ask.price)}</div>
              </div>
            </div>
          ))}
        </div>

        {/* 当前价格 */}
        {currentPrice && (
          <div className="flex items-center justify-between py-2 mb-3 border-y border-gray-200 bg-gray-50">
            <div className="text-sm font-medium">
              <span className={`${
                currentPrice.change >= 0 ? 'text-success-600' : 'text-danger-600'
              }`}>
                ${formatPrice(currentPrice.price)}
              </span>
            </div>
            <div className={`text-xs ${
              currentPrice.change >= 0 ? 'text-success-600' : 'text-danger-600'
            }`}>
              {currentPrice.change >= 0 ? '+' : ''}{currentPrice.change_percent.toFixed(2)}%
            </div>
          </div>
        )}

        {/* 买单区域 */}
        <div>
          {orderBook.bids.slice(0, Math.floor(displayCount / 2)).map((bid, index) => (
            <div
              key={`bid-${index}`}
              className="relative grid grid-cols-3 text-xs py-0.5 hover:bg-gray-50 cursor-pointer group"
            >
              {/* 深度背景条 */}
              <div
                className="absolute right-0 top-0 h-full bg-green-50 opacity-60"
                style={{ width: `${(bid.total / maxTotal) * 100}%` }}
              />
              
              <div className="relative text-success-600 font-medium">
                {formatPrice(bid.price)}
              </div>
              <div className="relative text-right text-gray-700">
                {formatQuantity(bid.quantity)}
              </div>
              <div className="relative text-right text-gray-600">
                {formatQuantity(bid.total)}
              </div>
              
              {/* 悬停时显示详细信息 */}
              <div className="absolute left-0 top-full mt-1 p-2 bg-black text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                <div>总价值: {(bid.price * bid.quantity).toFixed(2)} {quoteAsset}</div>
                <div>平均价: {formatPrice(bid.price)}</div>
              </div>
            </div>
          ))}
        </div>

        {/* 统计信息 */}
        <div className="mt-4 pt-3 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <div className="text-gray-500">买单总量</div>
              <div className="text-success-600 font-medium">
                {orderBook.bids.reduce((sum, bid) => sum + bid.quantity, 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-gray-500">卖单总量</div>
              <div className="text-danger-600 font-medium">
                {orderBook.asks.reduce((sum, ask) => sum + ask.quantity, 0).toFixed(2)}
              </div>
            </div>
          </div>
          
          {/* 最后更新时间 */}
          <div className="text-center text-xs text-gray-400 mt-2">
            更新时间: {new Date(orderBook.lastUpdate).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  )
}

export default OrderBook