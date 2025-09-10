import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import StrategyLibrary from './StrategyLibrary'
import IndicatorLibrary from './IndicatorLibrary'
import AnalysisLibrary from './AnalysisLibrary'

interface StrategyPanelProps {
  className?: string
}

const StrategyPanel: React.FC<StrategyPanelProps> = ({ className = '' }) => {
  const {
    activeLeftTab,
    setActiveLeftTab,
    strategyLibrary,
    indicatorLibrary,
    analysisLibrary,
    activeStrategies,
    leftPanelCollapsed,
    toggleLeftPanel
  } = useTradingPageStore()

  const tabs = [
    {
      id: 'strategies' as const,
      name: '策略库',
      count: strategyLibrary.length,
      activeCount: activeStrategies.length,
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      )
    },
    {
      id: 'indicators' as const,
      name: '指标库',
      count: indicatorLibrary.length,
      activeCount: indicatorLibrary.filter(i => i.isActive).length,
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      )
    },
    {
      id: 'analysis' as const,
      name: '分析库',
      count: analysisLibrary.length,
      activeCount: 0, // 分析库没有激活状态概念
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
        </svg>
      )
    }
  ]

  if (leftPanelCollapsed) {
    return (
      <div className={`w-16 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 ${className}`}>
        <div className="p-2">
          <button
            onClick={toggleLeftPanel}
            className="w-full p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="展开面板"
          >
            <svg className="w-5 h-5 mx-auto text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
          
          <div className="mt-4 space-y-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveLeftTab(tab.id)}
                className={`w-full p-3 rounded-lg transition-colors relative ${
                  activeLeftTab === tab.id
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
    <div className={`w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col ${className}`}>
      {/* 头部 */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          交易工具
        </h2>
        <button
          onClick={toggleLeftPanel}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="收起面板"
        >
          <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* 标签页导航 */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-1 p-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveLeftTab(tab.id)}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeLeftTab === tab.id
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {tab.icon}
              <span>{tab.name}</span>
              {tab.count > 0 && (
                <span className={`px-2 py-0.5 rounded-full text-xs ${
                  activeLeftTab === tab.id
                    ? 'bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200'
                    : 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                }`}>
                  {tab.count}
                  {tab.activeCount > 0 && (
                    <span className="ml-1 text-green-600 dark:text-green-400">
                      ({tab.activeCount})
                    </span>
                  )}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-hidden">
        {activeLeftTab === 'strategies' && <StrategyLibrary />}
        {activeLeftTab === 'indicators' && <IndicatorLibrary />}
        {activeLeftTab === 'analysis' && <AnalysisLibrary />}
      </div>

      {/* AI生成状态 */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-2 p-2 bg-blue-50 dark:bg-blue-900 rounded-lg">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
          <span className="text-xs text-blue-700 dark:text-blue-300">
            AI工具库持续更新中
          </span>
        </div>
      </div>
    </div>
  )
}

export default StrategyPanel