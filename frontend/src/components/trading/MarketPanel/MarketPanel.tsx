import React from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import SymbolSearch from './SymbolSearch'
import WatchList from './WatchList'
import OrderBook from './OrderBook'

interface MarketPanelProps {
  className?: string
}

const MarketPanel: React.FC<MarketPanelProps> = ({ className = '' }) => {
  const {
    activeRightTab,
    setActiveRightTab,
    watchList,
    orderBookData,
    rightPanelCollapsed,
    toggleRightPanel
  } = useTradingPageStore()

  const tabs = [
    {
      id: 'market' as const,
      name: '市场',
      count: 0, // 交易对数量
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      )
    },
    {
      id: 'watchlist' as const,
      name: '自选',
      count: watchList.length,
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
        </svg>
      )
    },
    {
      id: 'orderbook' as const,
      name: '深度',
      count: 0, // 订单数量
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
        </svg>
      )
    }
  ]

  if (rightPanelCollapsed) {
    return (
      <div className={`w-16 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 ${className}`}>
        <div className="p-2">
          <button
            onClick={toggleRightPanel}
            className="w-full p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="展开面板"
          >
            <svg className="w-5 h-5 mx-auto text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          
          <div className="mt-4 space-y-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveRightTab(tab.id)}
                className={`w-full p-3 rounded-lg transition-colors relative ${
                  activeRightTab === tab.id
                    ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title={tab.name}
              >
                {tab.icon}
                {tab.count > 0 && (
                  <div className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 text-white text-xs rounded-full flex items-center justify-center">
                    {tab.count > 99 ? '99+' : tab.count}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 flex flex-col ${className}`}>
      {/* 头部 */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          市场数据
        </h2>
        <button
          onClick={toggleRightPanel}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="收起面板"
        >
          <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* 标签页导航 */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-1 p-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveRightTab(tab.id)}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeRightTab === tab.id
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {tab.icon}
              <span>{tab.name}</span>
              {tab.count > 0 && (
                <span className={`px-2 py-0.5 rounded-full text-xs ${
                  activeRightTab === tab.id
                    ? 'bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200'
                    : 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-hidden">
        {activeRightTab === 'market' && <SymbolSearch />}
        {activeRightTab === 'watchlist' && <WatchList />}
        {activeRightTab === 'orderbook' && <OrderBook />}
      </div>

      {/* 实时数据状态 */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-2 p-2 bg-green-50 dark:bg-green-900 rounded-lg">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-xs text-green-700 dark:text-green-300">
            实时数据连接正常
          </span>
          {orderBookData && (
            <span className="text-xs text-green-600 dark:text-green-400 ml-auto">
              {new Date(orderBookData.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default MarketPanel