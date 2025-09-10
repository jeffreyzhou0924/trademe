import React, { useState } from 'react'
import type { TradingOpportunity, StrategySuggestion } from '@/store/tradingPageStore'

interface AIAnalysisOverlayProps {
  opportunities: TradingOpportunity[]
  recommendations: StrategySuggestion[]
  onOpportunityClick: (opportunity: TradingOpportunity) => void
  className?: string
}

const AIAnalysisOverlay: React.FC<AIAnalysisOverlayProps> = ({
  opportunities,
  recommendations,
  onOpportunityClick,
  className = ''
}) => {
  const [selectedOpportunity, setSelectedOpportunity] = useState<TradingOpportunity | null>(null)
  const [showDetails, setShowDetails] = useState(false)

  // 根据信号类型获取颜色
  const getSignalColor = (signal: 'buy' | 'sell' | 'watch') => {
    switch (signal) {
      case 'buy':
        return 'text-green-600 bg-green-50 border-green-200'
      case 'sell':
        return 'text-red-600 bg-red-50 border-red-200'
      case 'watch':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  // 根据置信度获取样式
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100'
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  // 处理机会点击
  const handleOpportunityClick = (opportunity: TradingOpportunity) => {
    setSelectedOpportunity(opportunity)
    setShowDetails(true)
    onOpportunityClick(opportunity)
  }

  return (
    <div className={`absolute inset-0 pointer-events-none ${className}`}>
      {/* 交易机会标记 */}
      {opportunities.map((opportunity, index) => (
        <div
          key={opportunity.id}
          className={`absolute pointer-events-auto cursor-pointer transform -translate-x-1/2 -translate-y-1/2 z-20`}
          style={{
            left: `${20 + index * 15}%`, // 简化定位，实际应根据价格和时间计算
            top: `${30 + Math.random() * 40}%` // 简化定位
          }}
          onClick={() => handleOpportunityClick(opportunity)}
        >
          {/* 机会标记点 */}
          <div className={`relative w-4 h-4 rounded-full border-2 ${getSignalColor(opportunity.signal)} flex items-center justify-center`}>
            <div className="w-2 h-2 rounded-full bg-current animate-pulse" />
            
            {/* 信号类型指示器 */}
            <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 whitespace-nowrap">
              <div className={`px-1.5 py-0.5 rounded text-xs font-medium ${getSignalColor(opportunity.signal)} border`}>
                {opportunity.signal.toUpperCase()}
              </div>
            </div>
          </div>

          {/* 悬浮详情 */}
          <div className="absolute top-6 left-1/2 transform -translate-x-1/2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg p-3 min-w-48 opacity-0 hover:opacity-100 transition-opacity z-30">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {opportunity.type === 'breakout' && '突破'}
                  {opportunity.type === 'support' && '支撑'}
                  {opportunity.type === 'resistance' && '阻力'}
                  {opportunity.type === 'pattern' && '形态'}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${getConfidenceColor(opportunity.confidence)}`}>
                  {(opportunity.confidence * 100).toFixed(0)}%
                </span>
              </div>
              
              <div className="text-sm text-gray-600 dark:text-gray-300">
                价格: ${opportunity.price.toFixed(2)}
              </div>
              
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {opportunity.description}
              </div>
              
              {opportunity.suggestedStrategy && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-600">
                  <div className="text-xs text-blue-600 dark:text-blue-400">
                    推荐策略: {opportunity.suggestedStrategy}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}

      {/* 趋势线和支撑阻力线 (AI识别的关键价位) */}
      {opportunities.filter(op => ['support', 'resistance'].includes(op.type)).map((opportunity, index) => (
        <div
          key={`line-${opportunity.id}`}
          className="absolute pointer-events-none z-10"
          style={{
            left: '10%',
            right: '10%',
            top: `${30 + index * 5}%`, // 简化定位
            height: '1px'
          }}
        >
          <div 
            className={`w-full h-full ${
              opportunity.type === 'support' 
                ? 'bg-green-400 border-green-400' 
                : 'bg-red-400 border-red-400'
            } opacity-60`}
            style={{
              borderTop: `1px dashed ${opportunity.type === 'support' ? '#4ade80' : '#f87171'}`
            }}
          />
          
          {/* 价位标签 */}
          <div className={`absolute right-0 -top-2 px-1.5 py-0.5 rounded text-xs font-medium ${
            opportunity.type === 'support'
              ? 'text-green-700 bg-green-100'
              : 'text-red-700 bg-red-100'
          }`}>
            ${opportunity.price.toFixed(2)}
          </div>
        </div>
      ))}

      {/* 机会详情弹窗 */}
      {showDetails && selectedOpportunity && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 pointer-events-auto">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-600">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                交易机会详情
              </h3>
              <button
                onClick={() => setShowDetails(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-500 dark:text-gray-400">机会类型</label>
                  <div className="font-medium text-gray-900 dark:text-white">
                    {selectedOpportunity.type === 'breakout' && '价格突破'}
                    {selectedOpportunity.type === 'support' && '支撑位'}
                    {selectedOpportunity.type === 'resistance' && '阻力位'}
                    {selectedOpportunity.type === 'pattern' && '技术形态'}
                  </div>
                </div>
                
                <div>
                  <label className="text-sm text-gray-500 dark:text-gray-400">信号强度</label>
                  <div className={`inline-block px-2 py-1 rounded text-sm font-medium ${getSignalColor(selectedOpportunity.signal)}`}>
                    {selectedOpportunity.signal === 'buy' && '买入信号'}
                    {selectedOpportunity.signal === 'sell' && '卖出信号'}
                    {selectedOpportunity.signal === 'watch' && '观察信号'}
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-500 dark:text-gray-400">目标价格</label>
                  <div className="font-medium text-gray-900 dark:text-white">
                    ${selectedOpportunity.price.toFixed(2)}
                  </div>
                </div>
                
                <div>
                  <label className="text-sm text-gray-500 dark:text-gray-400">置信度</label>
                  <div className={`inline-block px-2 py-1 rounded text-sm font-medium ${getConfidenceColor(selectedOpportunity.confidence)}`}>
                    {(selectedOpportunity.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              
              <div>
                <label className="text-sm text-gray-500 dark:text-gray-400">分析描述</label>
                <p className="text-gray-900 dark:text-white mt-1">
                  {selectedOpportunity.description}
                </p>
              </div>
              
              {selectedOpportunity.suggestedStrategy && (
                <div>
                  <label className="text-sm text-gray-500 dark:text-gray-400">推荐策略</label>
                  <div className="mt-1 p-3 bg-blue-50 dark:bg-blue-900 rounded-lg">
                    <p className="text-blue-700 dark:text-blue-300 text-sm">
                      {selectedOpportunity.suggestedStrategy}
                    </p>
                  </div>
                </div>
              )}
              
              <div className="text-xs text-gray-400">
                发现时间: {new Date(selectedOpportunity.timestamp).toLocaleString()}
              </div>
            </div>
            
            <div className="flex space-x-2 p-4 border-t border-gray-200 dark:border-gray-600">
              <button className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                创建策略
              </button>
              <button 
                onClick={() => setShowDetails(false)}
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI实时扫描状态 */}
      {opportunities.length > 0 && (
        <div className="absolute top-4 left-4 pointer-events-auto">
          <div className="bg-blue-50 dark:bg-blue-900 border border-blue-200 dark:border-blue-700 rounded-lg px-3 py-2 flex items-center space-x-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            <span className="text-xs text-blue-700 dark:text-blue-300 font-medium">
              AI实时扫描中...
            </span>
            <span className="text-xs text-blue-600 dark:text-blue-400">
              {opportunities.length}个机会
            </span>
          </div>
        </div>
      )}

      {/* 推荐策略快捷入口 */}
      {recommendations.length > 0 && (
        <div className="absolute bottom-4 left-4 pointer-events-auto max-w-xs">
          <div className="bg-green-50 dark:bg-green-900 border border-green-200 dark:border-green-700 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-green-800 dark:text-green-200">
                AI策略推荐
              </h4>
              <span className="text-xs text-green-600 dark:text-green-400">
                {recommendations.length}个
              </span>
            </div>
            
            <div className="space-y-2">
              {recommendations.slice(0, 2).map((rec) => (
                <div key={rec.id} className="bg-white dark:bg-gray-800 rounded p-2">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-medium text-gray-900 dark:text-white">
                      {rec.strategyName}
                    </span>
                    <span className="text-xs text-green-600 dark:text-green-400">
                      {(rec.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2">
                    {rec.reason}
                  </p>
                </div>
              ))}
            </div>
            
            {recommendations.length > 2 && (
              <button className="w-full mt-2 text-xs text-green-700 dark:text-green-300 hover:text-green-800 dark:hover:text-green-200">
                查看全部 ({recommendations.length}个)
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default AIAnalysisOverlay