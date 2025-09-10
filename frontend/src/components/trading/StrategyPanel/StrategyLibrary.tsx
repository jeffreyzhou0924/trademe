import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import { tradingDataManager } from '@/services/trading/dataManager'
import { strategyDataService } from '@/services/trading/strategyDataService'
import toast from 'react-hot-toast'

const StrategyLibrary: React.FC = () => {
  const {
    strategyLibrary,
    activeStrategies,
    activateStrategy,
    deactivateStrategy,
    removeStrategy
  } = useTradingPageStore()

  const [searchTerm, setSearchTerm] = useState('')
  const [selectedType, setSelectedType] = useState<'all' | 'ai_generated' | 'custom' | 'template'>('all')

  // 过滤策略
  const filteredStrategies = strategyLibrary.filter(strategy => {
    const matchesSearch = strategy.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         strategy.description.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesType = selectedType === 'all' || strategy.type === selectedType
    return matchesSearch && matchesType
  })

  // 获取策略类型标签
  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'ai_generated':
        return 'AI生成'
      case 'custom':
        return '自定义'
      case 'template':
        return '模板'
      default:
        return type
    }
  }

  // 获取策略类型颜色
  const getTypeColor = (type: string) => {
    switch (type) {
      case 'ai_generated':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      case 'custom':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'template':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  // 获取数据源图标
  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'ai_chat':
        return (
          <svg className="w-4 h-4 text-purple-500" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9 12a1 1 0 01-1-1V8a1 1 0 112 0v3a1 1 0 01-1 1zM9 5a1 1 0 100 2 1 1 0 000-2z" />
          </svg>
        )
      case 'user':
        return (
          <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
          </svg>
        )
      case 'system':
        return (
          <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
          </svg>
        )
      default:
        return null
    }
  }

  // 处理策略激活/停用
  const handleToggleStrategy = (strategyId: string) => {
    if (activeStrategies.includes(strategyId)) {
      deactivateStrategy(strategyId)
    } else {
      activateStrategy(strategyId)
    }
  }

  // 处理策略回测
  const handleBacktest = async (strategyId: string) => {
    try {
      toast.loading('正在运行策略回测...', { id: `backtest-${strategyId}` })
      console.log(`🎯 开始策略回测: ${strategyId}`)
      
      await tradingDataManager.runStrategyBacktest(strategyId)
      
      toast.success('策略回测完成', { id: `backtest-${strategyId}` })
    } catch (error) {
      console.error('❌ 策略回测失败:', error)
      toast.error(`回测失败: ${error}`, { id: `backtest-${strategyId}` })
    }
  }

  // 处理策略删除
  const handleDelete = async (strategyId: string, strategyName: string) => {
    if (!confirm(`确定要删除策略 "${strategyName}" 吗？此操作不可撤销。`)) {
      return
    }
    
    try {
      toast.loading('正在删除策略...', { id: `delete-${strategyId}` })
      console.log(`🗑️ 删除策略: ${strategyId}`)
      
      await strategyDataService.deleteStrategy(strategyId)
      removeStrategy(strategyId)
      
      toast.success('策略删除成功', { id: `delete-${strategyId}` })
    } catch (error) {
      console.error('❌ 策略删除失败:', error)
      toast.error(`删除失败: ${error}`, { id: `delete-${strategyId}` })
    }
  }

  // 处理策略编辑 (暂时跳转到AI聊天页面)
  const handleEdit = (strategyId: string, strategyName: string) => {
    console.log(`✏️ 编辑策略: ${strategyId}`)
    toast.success(`即将打开 "${strategyName}" 的编辑界面`)
    // TODO: 实现策略编辑界面或跳转到AI对话
  }

  return (
    <div className="h-full flex flex-col">
      {/* 搜索和过滤 */}
      <div className="p-4 space-y-3">
        {/* 搜索框 */}
        <div className="relative">
          <input
            type="text"
            placeholder="搜索策略..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {/* 类型过滤 */}
        <div className="flex space-x-1">
          {[
            { key: 'all' as const, label: '全部' },
            { key: 'ai_generated' as const, label: 'AI生成' },
            { key: 'custom' as const, label: '自定义' },
            { key: 'template' as const, label: '模板' }
          ].map((type) => (
            <button
              key={type.key}
              onClick={() => setSelectedType(type.key)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedType === type.key
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>

      {/* 策略列表 */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {filteredStrategies.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-400 dark:text-gray-500 mb-2">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              {searchTerm ? '未找到匹配的策略' : '暂无策略，开始创建或从AI生成'}
            </p>
            <button className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm">
              创建新策略
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredStrategies.map((strategy) => {
              const isActive = activeStrategies.includes(strategy.id)
              
              return (
                <div
                  key={strategy.id}
                  className={`p-3 border rounded-lg transition-all hover:shadow-sm ${
                    isActive
                      ? 'border-green-300 dark:border-green-600 bg-green-50 dark:bg-green-900/20'
                      : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      {getSourceIcon(strategy.source)}
                      <h3 className="font-medium text-gray-900 dark:text-white text-sm">
                        {strategy.name}
                      </h3>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getTypeColor(strategy.type)}`}>
                        {getTypeLabel(strategy.type)}
                      </span>
                      
                      <button
                        onClick={() => handleToggleStrategy(strategy.id)}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          isActive
                            ? 'bg-green-600 text-white hover:bg-green-700'
                            : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                        }`}
                      >
                        {isActive ? '运行中' : '启用'}
                      </button>
                    </div>
                  </div>
                  
                  <p className="text-xs text-gray-600 dark:text-gray-300 mb-3 line-clamp-2">
                    {strategy.description}
                  </p>
                  
                  {/* 性能指标 */}
                  {strategy.performance && (
                    <div className="grid grid-cols-3 gap-2 mb-3">
                      <div className="text-center">
                        <div className="text-xs text-gray-500 dark:text-gray-400">胜率</div>
                        <div className="text-sm font-medium text-gray-900 dark:text-white">
                          {(strategy.performance.winRate * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-xs text-gray-500 dark:text-gray-400">收益</div>
                        <div className={`text-sm font-medium ${
                          strategy.performance.returns >= 0 
                            ? 'text-green-600 dark:text-green-400' 
                            : 'text-red-600 dark:text-red-400'
                        }`}>
                          {strategy.performance.returns >= 0 ? '+' : ''}{(strategy.performance.returns * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-xs text-gray-500 dark:text-gray-400">回撤</div>
                        <div className="text-sm font-medium text-red-600 dark:text-red-400">
                          {(strategy.performance.maxDrawdown * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* 操作按钮 */}
                  <div className="flex space-x-2">
                    <button 
                      onClick={() => handleEdit(strategy.id, strategy.name)}
                      className="flex-1 px-3 py-1 text-xs text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900 rounded transition-colors"
                    >
                      编辑
                    </button>
                    <button 
                      onClick={() => handleBacktest(strategy.id)}
                      className="flex-1 px-3 py-1 text-xs text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900 rounded transition-colors"
                    >
                      回测
                    </button>
                    <button 
                      onClick={() => handleDelete(strategy.id, strategy.name)}
                      className="flex-1 px-3 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900 rounded transition-colors"
                    >
                      删除
                    </button>
                  </div>
                  
                  <div className="mt-2 text-xs text-gray-400 dark:text-gray-500">
                    创建于 {new Date(strategy.createdAt).toLocaleDateString()}
                    {strategy.lastUsed && (
                      <span className="ml-2">
                        最后使用 {new Date(strategy.lastUsed).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default StrategyLibrary