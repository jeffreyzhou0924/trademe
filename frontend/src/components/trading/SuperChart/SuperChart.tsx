import React, { useRef, useEffect, useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import { useDrawingTools } from '@/hooks/useDrawingTools'
import KlineChart from './KlineChart'
import TechnicalIndicators from './TechnicalIndicators'
import AIAnalysisOverlay from './AIAnalysisOverlay'
import ChartControls from './ChartControls'
import ChartSettings from './ChartSettings'
import DrawingToolbar from './DrawingToolbar'

interface SuperChartProps {
  className?: string
}

const SuperChart: React.FC<SuperChartProps> = ({ className = '' }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartInstanceRef = useRef<any>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  
  const {
    chartConfig,
    selectedSymbol,
    selectedTimeframe,
    selectedExchange,
    aiAnalysisEnabled,
    tradingOpportunities,
    aiRecommendations,
    updateChartConfig
  } = useTradingPageStore()

  // 初始化绘图工具
  const drawingTools = useDrawingTools({
    chartInstance: chartInstanceRef,
    symbol: selectedSymbol,
    timeframe: selectedTimeframe
  })

  // 处理全屏切换
  const handleFullscreenToggle = () => {
    if (!chartContainerRef.current) return
    
    if (!isFullscreen) {
      if (chartContainerRef.current.requestFullscreen) {
        chartContainerRef.current.requestFullscreen()
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen()
      }
    }
  }

  // 监听全屏状态变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  // 处理主题切换
  const handleThemeToggle = () => {
    const newTheme = chartConfig.theme === 'light' ? 'dark' : 'light'
    updateChartConfig({ theme: newTheme })
  }

  return (
    <div 
      ref={chartContainerRef}
      className={`relative w-full h-full bg-gray-900 overflow-hidden ${className}`}
    >
      {/* 主要布局区域：工具栏 + 图表 */}
      <div className="flex w-full h-full">
        {/* TradingView风格绘图工具栏 */}
        <DrawingToolbar 
          className="w-10 flex-shrink-0" 
          drawingTools={drawingTools}
        />
        
        {/* K线图表核心区域 */}
        <div className="relative flex-1 h-full">
        {/* K线图表 */}
        <KlineChart
          symbol={selectedSymbol}
          timeframe={selectedTimeframe}
          exchange={selectedExchange}
          config={chartConfig}
          className="w-full h-full"
          chartRef={chartInstanceRef}
          drawingTools={drawingTools}
        />

        {/* AI分析叠加层 */}
        {aiAnalysisEnabled && (
          <AIAnalysisOverlay
            opportunities={tradingOpportunities}
            recommendations={aiRecommendations}
            onOpportunityClick={(opportunity) => {
              console.log('Opportunity clicked:', opportunity)
              // TODO: 显示机会详情
            }}
          />
        )}

        {/* 技术指标面板 - 左上角 */}
        <TechnicalIndicators
          activeIndicators={chartConfig.indicators}
          className="absolute top-2 left-2 z-10"
        />
        
        {/* AI分析状态指示 - 右上角 */}
        {aiAnalysisEnabled && (
          <div className="absolute top-2 right-20 flex items-center space-x-2 bg-gray-800/80 backdrop-blur-sm rounded px-3 py-1.5 z-10">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-green-400">AI分析</span>
          </div>
        )}
        
        {/* 图表控制按钮 - 右上角 */}
        <div className="absolute top-2 right-2 z-10">
          <ChartControls
            isFullscreen={isFullscreen}
            theme={chartConfig.theme}
            onFullscreenToggle={handleFullscreenToggle}
            onThemeToggle={handleThemeToggle}
            onSettingsClick={() => setShowSettings(true)}
          />
          
          {/* 图表设置面板 */}
          <ChartSettings
            isOpen={showSettings}
            config={chartConfig}
            onClose={() => setShowSettings(false)}
            onConfigChange={updateChartConfig}
          />
        </div>
        </div> {/* 关闭K线图表核心区域 */}
      </div> {/* 关闭主要布局区域 */}

      {/* AI推荐浮窗 */}
      {aiRecommendations.length > 0 && (
        <div className="absolute bottom-14 right-4 max-w-sm z-20">
          <div className="bg-blue-900/90 backdrop-blur-sm border border-blue-700 rounded-lg p-4 shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-medium text-blue-100 flex items-center">
                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                AI策略推荐
              </h4>
              <button
                onClick={() => {/* TODO: 关闭推荐 */}}
                className="text-blue-400 hover:text-blue-200"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-2">
              {aiRecommendations.slice(0, 2).map((recommendation) => (
                <div key={recommendation.id} className="p-2 bg-gray-800/80 rounded border border-gray-700">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium text-sm text-white">
                      {recommendation.strategyName}
                    </span>
                    <span className="text-xs text-green-400">
                      {(recommendation.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-300">
                    {recommendation.reason}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SuperChart