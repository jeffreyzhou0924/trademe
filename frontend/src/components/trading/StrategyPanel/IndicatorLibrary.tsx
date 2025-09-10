import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'

const IndicatorLibrary: React.FC = () => {
  const {
    indicatorLibrary,
    addIndicator,
    removeIndicator,
    toggleIndicator
  } = useTradingPageStore()

  const [searchTerm, setSearchTerm] = useState('')
  const [selectedType, setSelectedType] = useState<'all' | 'technical' | 'custom' | 'ai_enhanced'>('all')
  const [showAddForm, setShowAddForm] = useState(false)

  // 预定义的常用技术指标
  const builtinIndicators = [
    { 
      id: 'ma_5', 
      name: 'MA(5)', 
      description: '5日移动平均线', 
      type: 'technical',
      parameters: { period: 5 },
      category: 'trend'
    },
    { 
      id: 'ma_10', 
      name: 'MA(10)', 
      description: '10日移动平均线', 
      type: 'technical',
      parameters: { period: 10 },
      category: 'trend'
    },
    { 
      id: 'ma_20', 
      name: 'MA(20)', 
      description: '20日移动平均线', 
      type: 'technical',
      parameters: { period: 20 },
      category: 'trend'
    },
    { 
      id: 'ma_60', 
      name: 'MA(60)', 
      description: '60日移动平均线', 
      type: 'technical',
      parameters: { period: 60 },
      category: 'trend'
    },
    { 
      id: 'boll', 
      name: 'BOLL', 
      description: '布林带指标', 
      type: 'technical',
      parameters: { period: 20, multiplier: 2 },
      category: 'volatility'
    },
    { 
      id: 'volume', 
      name: 'VOL', 
      description: '成交量指标', 
      type: 'technical',
      parameters: {},
      category: 'volume'
    },
    { 
      id: 'macd', 
      name: 'MACD', 
      description: 'MACD指标', 
      type: 'technical',
      parameters: { fast: 12, slow: 26, signal: 9 },
      category: 'momentum'
    },
    { 
      id: 'rsi', 
      name: 'RSI', 
      description: 'RSI相对强弱指标', 
      type: 'technical',
      parameters: { period: 14 },
      category: 'momentum'
    },
    { 
      id: 'kdj', 
      name: 'KDJ', 
      description: 'KDJ随机指标', 
      type: 'technical',
      parameters: { period: 9 },
      category: 'momentum'
    },
    { 
      id: 'cci', 
      name: 'CCI', 
      description: 'CCI顺势指标', 
      type: 'technical',
      parameters: { period: 14 },
      category: 'momentum'
    }
  ]

  // 合并内置指标和用户指标
  const allIndicators = [
    ...builtinIndicators.map(indicator => ({
      ...indicator,
      isActive: false, // 内置指标通过chartConfig.indicators控制
      createdAt: Date.now()
    })),
    ...indicatorLibrary
  ]

  // 过滤指标
  const filteredIndicators = allIndicators.filter(indicator => {
    const matchesSearch = indicator.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         indicator.description.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesType = selectedType === 'all' || indicator.type === selectedType
    return matchesSearch && matchesType
  })

  // 按类别分组
  const groupedIndicators = filteredIndicators.reduce((groups, indicator) => {
    const category = (indicator as any).category || 'other'
    if (!groups[category]) {
      groups[category] = []
    }
    groups[category].push(indicator)
    return groups
  }, {} as Record<string, typeof filteredIndicators>)

  // 获取指标类型颜色
  const getTypeColor = (type: string) => {
    switch (type) {
      case 'technical':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'custom':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'ai_enhanced':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  // 获取类别名称
  const getCategoryName = (category: string) => {
    switch (category) {
      case 'trend':
        return '趋势指标'
      case 'momentum':
        return '动量指标'
      case 'volatility':
        return '波动率指标'
      case 'volume':
        return '成交量指标'
      default:
        return '其他指标'
    }
  }

  // 获取类别图标
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'trend':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        )
      case 'momentum':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707" />
          </svg>
        )
      case 'volatility':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l3-3 3 3v13M9 19h6M9 19H7a2 2 0 01-2-2V9a2 2 0 012-2h2M15 19h2a2 2 0 002-2V9a2 2 0 00-2-2h-2" />
          </svg>
        )
      case 'volume':
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        )
      default:
        return (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        )
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 搜索和过滤 */}
      <div className="p-4 space-y-3">
        {/* 搜索框 */}
        <div className="relative">
          <input
            type="text"
            placeholder="搜索指标..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {/* 类型过滤 */}
        <div className="flex space-x-1 overflow-x-auto">
          {[
            { key: 'all' as const, label: '全部' },
            { key: 'technical' as const, label: '技术指标' },
            { key: 'custom' as const, label: '自定义' },
            { key: 'ai_enhanced' as const, label: 'AI增强' }
          ].map((type) => (
            <button
              key={type.key}
              onClick={() => setSelectedType(type.key)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                selectedType === type.key
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>

        {/* 添加指标按钮 */}
        <button 
          onClick={() => setShowAddForm(true)}
          className="w-full px-3 py-2 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg text-gray-600 dark:text-gray-400 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors text-sm"
        >
          <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          添加自定义指标
        </button>
      </div>

      {/* 指标列表 */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {Object.keys(groupedIndicators).length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-400 dark:text-gray-500 mb-2">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              未找到匹配的指标
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedIndicators).map(([category, indicators]) => (
              <div key={category}>
                {/* 类别标题 */}
                <div className="flex items-center space-x-2 mb-2 px-2">
                  <div className="text-blue-600 dark:text-blue-400">
                    {getCategoryIcon(category)}
                  </div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                    {getCategoryName(category)}
                  </h3>
                  <div className="flex-1 border-t border-gray-200 dark:border-gray-600"></div>
                </div>

                {/* 指标列表 */}
                <div className="space-y-2">
                  {indicators.map((indicator) => (
                    <div
                      key={indicator.id}
                      className={`p-3 border rounded-lg transition-all ${
                        indicator.isActive
                          ? 'border-green-300 dark:border-green-600 bg-green-50 dark:bg-green-900/20'
                          : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 hover:shadow-sm'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="font-medium text-gray-900 dark:text-white text-sm">
                            {indicator.name}
                          </h4>
                          <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                            {indicator.description}
                          </p>
                        </div>
                        
                        <div className="flex items-center space-x-2 ml-2">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getTypeColor(indicator.type)}`}>
                            {indicator.type === 'technical' && '技术'}
                            {indicator.type === 'custom' && '自定义'}
                            {indicator.type === 'ai_enhanced' && 'AI增强'}
                          </span>
                          
                          <button
                            onClick={() => toggleIndicator(indicator.id)}
                            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                              indicator.isActive
                                ? 'bg-green-600 text-white hover:bg-green-700'
                                : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                            }`}
                          >
                            {indicator.isActive ? '已启用' : '启用'}
                          </button>
                        </div>
                      </div>
                      
                      {/* 参数显示 */}
                      {Object.keys(indicator.parameters).length > 0 && (
                        <div className="mb-2">
                          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">参数:</div>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(indicator.parameters).map(([key, value]) => (
                              <span key={key} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-600 rounded text-xs text-gray-600 dark:text-gray-300">
                                {key}: {String(value)}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {/* 公式显示 (如果有) */}
                      {(indicator as any).formula && (
                        <div className="mb-2">
                          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">公式:</div>
                          <code className="text-xs bg-gray-100 dark:bg-gray-600 p-1 rounded text-gray-600 dark:text-gray-300">
                            {(indicator as any).formula}
                          </code>
                        </div>
                      )}
                      
                      {/* 操作按钮 */}
                      {indicator.type !== 'technical' && (
                        <div className="flex space-x-2 mt-2">
                          <button className="flex-1 px-3 py-1 text-xs text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900 rounded transition-colors">
                            编辑
                          </button>
                          <button 
                            onClick={() => removeIndicator(indicator.id)}
                            className="flex-1 px-3 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900 rounded transition-colors"
                          >
                            删除
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default IndicatorLibrary