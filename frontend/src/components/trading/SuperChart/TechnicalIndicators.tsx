import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'

interface TechnicalIndicatorsProps {
  activeIndicators: string[]
  className?: string
}

const TechnicalIndicators: React.FC<TechnicalIndicatorsProps> = ({ 
  activeIndicators, 
  className = '' 
}) => {
  const [showIndicatorPanel, setShowIndicatorPanel] = useState(false)
  
  const { 
    indicatorLibrary, 
    toggleIndicator 
  } = useTradingPageStore()

  // 预定义常用指标
  const commonIndicators = [
    { id: 'ma_5', name: 'MA(5)', description: '5日移动平均线', type: 'overlay', color: '#ff6b6b' },
    { id: 'ma_10', name: 'MA(10)', description: '10日移动平均线', type: 'overlay', color: '#4ecdc4' },
    { id: 'ma_20', name: 'MA(20)', description: '20日移动平均线', type: 'overlay', color: '#45b7d1' },
    { id: 'ma_60', name: 'MA(60)', description: '60日移动平均线', type: 'overlay', color: '#f9ca24' },
    { id: 'boll', name: 'BOLL', description: '布林带', type: 'overlay', color: '#6c5ce7' },
    { id: 'volume', name: 'VOL', description: '成交量', type: 'sub', color: '#a29bfe' },
    { id: 'macd', name: 'MACD', description: 'MACD指标', type: 'sub', color: '#fd79a8' },
    { id: 'rsi', name: 'RSI', description: 'RSI指标', type: 'sub', color: '#00b894' },
    { id: 'kdj', name: 'KDJ', description: 'KDJ指标', type: 'sub', color: '#e17055' },
    { id: 'cci', name: 'CCI', description: 'CCI指标', type: 'sub', color: '#00cec9' },
  ]

  const overlayIndicators = commonIndicators.filter(i => i.type === 'overlay')
  const subIndicators = commonIndicators.filter(i => i.type === 'sub')

  return (
    <div className={`relative ${className}`}>
      {/* 指标控制按钮 */}
      <button
        onClick={() => setShowIndicatorPanel(!showIndicatorPanel)}
        className="px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm hover:shadow-md transition-shadow"
        title="技术指标"
      >
        <div className="flex items-center space-x-2">
          <svg className="w-4 h-4 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">指标</span>
          <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs rounded-full">
            {activeIndicators.length}
          </span>
        </div>
      </button>

      {/* 指标选择面板 */}
      {showIndicatorPanel && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
          {/* 头部 */}
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white">技术指标</h3>
              <button
                onClick={() => setShowIndicatorPanel(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* 主图指标 */}
          <div className="p-4">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">主图指标</h4>
            <div className="space-y-2">
              {overlayIndicators.map((indicator) => (
                <div key={indicator.id} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: indicator.color }}
                    />
                    <div>
                      <div className="font-medium text-sm text-white">
                        {indicator.name}
                      </div>
                      <div className="text-xs text-gray-400">
                        {indicator.description}
                      </div>
                    </div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={activeIndicators.includes(indicator.id)}
                      onChange={() => toggleIndicator(indicator.id)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* 分图指标 */}
          <div className="p-4 border-t border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">分图指标</h4>
            <div className="space-y-2">
              {subIndicators.map((indicator) => (
                <div key={indicator.id} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: indicator.color }}
                    />
                    <div>
                      <div className="font-medium text-sm text-white">
                        {indicator.name}
                      </div>
                      <div className="text-xs text-gray-400">
                        {indicator.description}
                      </div>
                    </div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={activeIndicators.includes(indicator.id)}
                      onChange={() => toggleIndicator(indicator.id)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* 自定义指标 */}
          <div className="p-4 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">自定义指标</h4>
              <button className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200">
                添加指标
              </button>
            </div>
            {indicatorLibrary.length === 0 ? (
              <div className="text-xs text-gray-500 dark:text-gray-400 text-center py-4">
                暂无自定义指标
              </div>
            ) : (
              <div className="space-y-2">
                {indicatorLibrary.map((indicator) => (
                  <div key={indicator.id} className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-3 h-3 bg-purple-500 rounded-full" />
                      <div>
                        <div className="font-medium text-sm text-gray-900 dark:text-white">
                          {indicator.name}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {indicator.description}
                        </div>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={indicator.isActive}
                        onChange={() => toggleIndicator(indicator.id)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default TechnicalIndicators