import React, { useState, useRef, useEffect } from 'react'

interface SymbolSearchBarProps {
  selectedSymbol: string
  selectedExchange: string
  onSymbolChange: (symbol: string) => void
  onExchangeChange: (exchange: string) => void
}

// 模拟的交易品种数据
const TRADING_SYMBOLS = [
  { symbol: 'BTC/USDT', exchange: 'OKX', price: '43,250.00', change: '+2.45%', volume: '2.1B' },
  { symbol: 'ETH/USDT', exchange: 'OKX', price: '2,680.50', change: '+3.21%', volume: '1.8B' },
  { symbol: 'BNB/USDT', exchange: 'OKX', price: '645.80', change: '-1.15%', volume: '450M' },
  { symbol: 'SOL/USDT', exchange: 'OKX', price: '98.45', change: '+5.67%', volume: '680M' },
  { symbol: 'ADA/USDT', exchange: 'OKX', price: '0.4521', change: '+1.89%', volume: '320M' },
  { symbol: 'XRP/USDT', exchange: 'OKX', price: '0.6234', change: '-0.78%', volume: '560M' },
  { symbol: 'DOT/USDT', exchange: 'OKX', price: '7.89', change: '+2.34%', volume: '180M' },
  { symbol: 'LINK/USDT', exchange: 'OKX', price: '15.67', change: '+4.12%', volume: '210M' },
  { symbol: 'AVAX/USDT', exchange: 'OKX', price: '32.45', change: '-2.11%', volume: '150M' },
  { symbol: 'MATIC/USDT', exchange: 'OKX', price: '1.234', change: '+1.56%', volume: '290M' }
]

const EXCHANGES = ['OKX', 'Binance', 'Huobi', 'Bybit']

const SymbolSearchBar: React.FC<SymbolSearchBarProps> = ({
  selectedSymbol,
  selectedExchange,
  onSymbolChange,
  onExchangeChange
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [activeExchange, setActiveExchange] = useState(selectedExchange)
  const searchRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // 过滤交易品种
  const filteredSymbols = TRADING_SYMBOLS.filter(item => 
    item.exchange === activeExchange &&
    (item.symbol.toLowerCase().includes(searchTerm.toLowerCase()) || 
     searchTerm === '')
  )

  // 处理点击外部关闭
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSearchTerm('')
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 处理符号选择
  const handleSymbolSelect = (symbol: string, exchange: string) => {
    onSymbolChange(symbol)
    onExchangeChange(exchange)
    setIsOpen(false)
    setSearchTerm('')
  }

  // 处理交易所切换
  const handleExchangeSwitch = (exchange: string) => {
    setActiveExchange(exchange)
    onExchangeChange(exchange)
  }

  return (
    <div className="relative" ref={searchRef}>
      {/* 搜索框 */}
      <div 
        className="flex items-center bg-white border border-gray-300 rounded-lg px-3 py-2 cursor-pointer hover:border-blue-400 transition-colors min-w-[300px]"
        onClick={() => {
          setIsOpen(!isOpen)
          if (!isOpen) {
            setTimeout(() => inputRef.current?.focus(), 100)
          }
        }}
      >
        <div className="flex items-center space-x-2 flex-1">
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
            {selectedExchange}
          </span>
          <span className="font-medium text-gray-900">{selectedSymbol}</span>
        </div>
        <svg 
          className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* 下拉面板 */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-96 overflow-hidden">
          {/* 交易所选择标签 */}
          <div className="flex border-b border-gray-200">
            {EXCHANGES.map(exchange => (
              <button
                key={exchange}
                onClick={() => handleExchangeSwitch(exchange)}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  activeExchange === exchange
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                {exchange}
              </button>
            ))}
          </div>

          {/* 搜索输入框 */}
          <div className="p-3 border-b border-gray-100">
            <input
              ref={inputRef}
              type="text"
              placeholder="搜索交易品种..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* 交易品种列表 */}
          <div className="max-h-64 overflow-y-auto">
            {filteredSymbols.map((item, index) => (
              <div
                key={`${item.exchange}-${item.symbol}-${index}`}
                onClick={() => handleSymbolSelect(item.symbol, item.exchange)}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-b-0"
              >
                <div className="flex items-center space-x-3">
                  <div className="flex flex-col">
                    <span className="font-medium text-gray-900 text-sm">{item.symbol}</span>
                    <span className="text-xs text-gray-500">{item.exchange}</span>
                  </div>
                </div>
                <div className="flex items-center space-x-4 text-xs">
                  <div className="text-right">
                    <div className="font-medium text-gray-900">{item.price}</div>
                    <div className={`${
                      item.change.startsWith('+') ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {item.change}
                    </div>
                  </div>
                  <div className="text-gray-500 min-w-[50px] text-right">
                    {item.volume}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredSymbols.length === 0 && (
            <div className="p-4 text-center text-gray-500 text-sm">
              未找到匹配的交易品种
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default SymbolSearchBar