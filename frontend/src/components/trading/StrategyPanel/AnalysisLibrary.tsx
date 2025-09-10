import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import { tradingDataManager } from '@/services/trading/dataManager'
import type { AnalysisLibraryItem } from '@/store/tradingPageStore'
import toast from 'react-hot-toast'

const AnalysisLibrary: React.FC = () => {
  const {
    analysisLibrary,
    addAnalysis,
    removeAnalysis,
    runAnalysis
  } = useTradingPageStore()

  const [searchTerm, setSearchTerm] = useState('')
  const [selectedType, setSelectedType] = useState<'all' | 'pattern' | 'trend' | 'volume' | 'comprehensive'>('all')
  const [runningAnalysis, setRunningAnalysis] = useState<string | null>(null)

  // 预定义分析模板
  const analysisTemplates = [
    {
      id: 'breakout_pattern',
      name: '突破形态分析',
      description: '识别价格突破关键支撑或阻力位的形态',
      type: 'pattern' as const,
      criteria: {
        volume_spike: true,
        price_breakout: true,
        momentum_confirm: true
      }
    },
    {
      id: 'trend_reversal',
      name: '趋势反转分析',
      description: '检测趋势可能发生反转的信号',
      type: 'trend' as const,
      criteria: {
        divergence: true,
        support_resistance: true,
        candlestick_patterns: true
      }
    },
    {
      id: 'volume_analysis',
      name: '成交量异动分析',
      description: '分析成交量异常变化及其对价格的影响',
      type: 'volume' as const,
      criteria: {
        volume_spike: true,
        price_volume_correlation: true,
        accumulation_distribution: true
      }
    },
    {
      id: 'comprehensive_scan',
      name: '综合技术分析',
      description: '多维度综合分析市场状态和交易机会',
      type: 'comprehensive' as const,
      criteria: {
        technical_indicators: true,
        price_patterns: true,
        volume_analysis: true,
        market_structure: true
      }
    }
  ]

  // 过滤分析项目
  const filteredAnalysis = [
    ...analysisTemplates.map(template => ({
      ...template,
      confidence: Math.random() * 0.4 + 0.6, // 模拟置信度
      createdAt: Date.now() - Math.random() * 86400000 * 30, // 过去30天内随机时间
      lastAnalysis: Math.random() > 0.5 ? {
        result: '发现3个潜在交易机会',
        timestamp: Date.now() - Math.random() * 86400000,
        opportunities: []
      } : undefined
    })),
    ...analysisLibrary
  ].filter(analysis => {
    const matchesSearch = analysis.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         analysis.description.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesType = selectedType === 'all' || analysis.type === selectedType
    return matchesSearch && matchesType
  })

  // 获取分析类型颜色
  const getTypeColor = (type: string) => {
    switch (type) {
      case 'pattern':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'trend':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'volume':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      case 'comprehensive':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
    }
  }

  // 获取置信度颜色
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-300'
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-300'
    return 'text-red-600 bg-red-100 dark:bg-red-900 dark:text-red-300'
  }

  // 运行分析
  const handleRunAnalysis = async (analysisId: string) => {
    setRunningAnalysis(analysisId)
    try {
      toast.loading('正在运行AI分析...', { id: `analysis-${analysisId}` })
      console.log(`🤖 开始AI分析: ${analysisId}`)
      
      await tradingDataManager.runAIAnalysis(analysisId)
      
      toast.success('AI分析完成', { id: `analysis-${analysisId}` })
      setRunningAnalysis(null)
    } catch (error) {
      console.error('❌ AI分析失败:', error)
      toast.error(`分析失败: ${error}`, { id: `analysis-${analysisId}` })
      setRunningAnalysis(null)
    }
  }

  // 运行所有分析
  const handleRunAllAnalysis = async () => {
    try {
      toast.loading('正在运行所有AI分析...', { id: 'analysis-all' })
      console.log('🤖 开始运行所有AI分析')
      
      const analysisPromises = filteredAnalysis.map(analysis => 
        tradingDataManager.runAIAnalysis(analysis.id)
      )
      
      await Promise.allSettled(analysisPromises)
      
      toast.success('所有AI分析完成', { id: 'analysis-all' })
    } catch (error) {
      console.error('❌ 批量AI分析失败:', error)
      toast.error(`批量分析失败: ${error}`, { id: 'analysis-all' })
    }
  }

  // 获取分析状态
  const getAnalysisStatus = (analysis: AnalysisLibraryItem) => {
    if (runningAnalysis === analysis.id) {
      return { text: '运行中...', color: 'text-blue-600 bg-blue-100 dark:bg-blue-900 dark:text-blue-300' }
    }
    
    if (analysis.lastAnalysis) {
      const timeDiff = Date.now() - analysis.lastAnalysis.timestamp
      const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60))
      
      if (hoursAgo < 1) {
        return { text: '刚刚完成', color: 'text-green-600 bg-green-100 dark:bg-green-900 dark:text-green-300' }
      } else if (hoursAgo < 24) {
        return { text: `${hoursAgo}小时前`, color: 'text-gray-600 bg-gray-100 dark:bg-gray-700 dark:text-gray-300' }
      } else {
        const daysAgo = Math.floor(hoursAgo / 24)
        return { text: `${daysAgo}天前`, color: 'text-gray-500 bg-gray-100 dark:bg-gray-700 dark:text-gray-400' }
      }
    }
    
    return { text: '未运行', color: 'text-gray-400 bg-gray-100 dark:bg-gray-700 dark:text-gray-400' }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 搜索和过滤 */}
      <div className="p-4 space-y-3">
        {/* 搜索框 */}
        <div className="relative">
          <input
            type="text"
            placeholder="搜索分析..."
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
            { key: 'pattern' as const, label: '形态' },
            { key: 'trend' as const, label: '趋势' },
            { key: 'volume' as const, label: '成交量' },
            { key: 'comprehensive' as const, label: '综合' }
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

        {/* 快速运行所有分析 */}
        <button 
          onClick={handleRunAllAnalysis}
          className="w-full px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364-.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          运行所有分析
        </button>
      </div>

      {/* 分析列表 */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {filteredAnalysis.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-400 dark:text-gray-500 mb-2">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
              </svg>
            </div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              未找到匹配的分析
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredAnalysis.map((analysis) => {
              const status = getAnalysisStatus(analysis)
              const isRunning = runningAnalysis === analysis.id
              
              return (
                <div
                  key={analysis.id}
                  className="p-3 border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 hover:shadow-sm transition-all"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900 dark:text-white text-sm mb-1">
                        {analysis.name}
                      </h3>
                      <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2">
                        {analysis.description}
                      </p>
                    </div>
                    
                    <div className="flex flex-col items-end space-y-1 ml-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getTypeColor(analysis.type)}`}>
                        {analysis.type === 'pattern' && '形态'}
                        {analysis.type === 'trend' && '趋势'}
                        {analysis.type === 'volume' && '成交量'}
                        {analysis.type === 'comprehensive' && '综合'}
                      </span>
                      
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getConfidenceColor(analysis.confidence)}`}>
                        {(analysis.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  
                  {/* 分析条件 */}
                  <div className="mb-3">
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">分析条件:</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(analysis.criteria).map(([key, enabled]) => (
                        <span key={key} className={`px-2 py-0.5 rounded text-xs ${
                          enabled 
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-600 dark:text-gray-400'
                        }`}>
                          {key.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {/* 最后分析结果 */}
                  {analysis.lastAnalysis && (
                    <div className="mb-3 p-2 bg-gray-50 dark:bg-gray-600 rounded">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">上次结果:</div>
                      <div className="text-sm text-gray-900 dark:text-white">
                        {analysis.lastAnalysis.result}
                      </div>
                    </div>
                  )}
                  
                  {/* 状态和操作 */}
                  <div className="flex items-center justify-between">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${status.color}`}>
                      {isRunning && (
                        <svg className="w-3 h-3 inline mr-1 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
                          <path fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" className="opacity-75" />
                        </svg>
                      )}
                      {status.text}
                    </span>
                    
                    <div className="flex space-x-2">
                      <button 
                        onClick={() => handleRunAnalysis(analysis.id)}
                        disabled={isRunning}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          isRunning
                            ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                            : 'bg-blue-600 text-white hover:bg-blue-700'
                        }`}
                      >
                        {isRunning ? '运行中...' : '运行分析'}
                      </button>
                      
                      {analysis.lastAnalysis && (
                        <button className="px-3 py-1 text-xs text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900 rounded transition-colors">
                          查看详情
                        </button>
                      )}
                      
                      {/* 只有自定义分析才显示删除按钮 */}
                      {!analysisTemplates.find(t => t.id === analysis.id) && (
                        <button 
                          onClick={() => removeAnalysis(analysis.id)}
                          className="px-3 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900 rounded transition-colors"
                        >
                          删除
                        </button>
                      )}
                    </div>
                  </div>
                  
                  <div className="mt-2 text-xs text-gray-400 dark:text-gray-500">
                    创建于 {new Date((analysis as any).createdAt || Date.now()).toLocaleDateString()}
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

export default AnalysisLibrary