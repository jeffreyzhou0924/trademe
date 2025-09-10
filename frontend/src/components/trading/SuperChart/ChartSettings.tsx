import React from 'react'
import { ChartConfig } from '@/store/tradingPageStore'

interface ChartSettingsProps {
  isOpen: boolean
  config: ChartConfig
  onClose: () => void
  onConfigChange: (config: Partial<ChartConfig>) => void
}

const ChartSettings: React.FC<ChartSettingsProps> = ({
  isOpen,
  config,
  onClose,
  onConfigChange
}) => {
  if (!isOpen) return null

  const handlePriceAxisModeChange = (mode: 'linear' | 'percentage' | 'logarithmic') => {
    onConfigChange({ priceAxisMode: mode })
  }

  const handleChartStyleChange = (style: 'candlestick' | 'line' | 'area' | 'heikin-ashi') => {
    onConfigChange({ chartStyle: style })
  }

  const handleDisplayModeChange = (mode: 'normal' | 'percentage') => {
    onConfigChange({ displayMode: mode })
  }

  const handleAutoScaleToggle = () => {
    onConfigChange({ autoScale: !config.autoScale })
  }

  return (
    <div className="absolute top-12 right-2 z-20 bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-4 min-w-64">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">图表设置</h3>
        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded text-gray-400 hover:text-white hover:bg-gray-700"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="space-y-6">
        {/* K线图样式 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            图表样式
          </label>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: 'candlestick', label: '蜡烛图', icon: '📊' },
              { key: 'line', label: '线图', icon: '📈' },
              { key: 'area', label: '面积图', icon: '🌊' },
              { key: 'heikin-ashi', label: '平均蜡烛', icon: '🕯️' }
            ].map((style) => (
              <button
                key={style.key}
                onClick={() => handleChartStyleChange(style.key as any)}
                className={`p-2 rounded text-xs transition-colors ${
                  config.chartStyle === style.key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <span className="mr-1">{style.icon}</span>
                {style.label}
              </button>
            ))}
          </div>
        </div>

        {/* 坐标轴模式 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            价格轴模式
          </label>
          <div className="space-y-2">
            {[
              { key: 'linear', label: '线性', desc: '常规价格轴' },
              { key: 'percentage', label: '百分比', desc: '相对于基准价格的百分比' },
              { key: 'logarithmic', label: '对数', desc: '对数坐标轴，适合大幅价格变化' }
            ].map((mode) => (
              <button
                key={mode.key}
                onClick={() => handlePriceAxisModeChange(mode.key as any)}
                className={`w-full p-2 rounded text-left text-xs transition-colors ${
                  config.priceAxisMode === mode.key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <div className="font-medium">{mode.label}</div>
                <div className="text-xs opacity-80">{mode.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* 数据显示模式 */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            数据显示模式
          </label>
          <div className="space-y-2">
            {[
              { key: 'normal', label: '正常', desc: '显示实际价格' },
              { key: 'percentage', label: '百分比', desc: '显示相对第一根K线的百分比变化' }
            ].map((mode) => (
              <button
                key={mode.key}
                onClick={() => handleDisplayModeChange(mode.key as any)}
                className={`w-full p-2 rounded text-left text-xs transition-colors ${
                  config.displayMode === mode.key
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <div className="font-medium">{mode.label}</div>
                <div className="text-xs opacity-80">{mode.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* 自适应缩放 */}
        <div>
          <div className="flex items-center justify-between">
            <div>
              <label className="block text-sm font-medium text-gray-300">
                自适应缩放
              </label>
              <p className="text-xs text-gray-400">
                自动调整图表范围以适应屏幕
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only"
                checked={config.autoScale}
                onChange={handleAutoScaleToggle}
              />
              <div className={`w-10 h-6 rounded-full transition-colors ${
                config.autoScale ? 'bg-blue-600' : 'bg-gray-600'
              }`}>
                <div className={`w-4 h-4 bg-white rounded-full mt-1 transition-transform ${
                  config.autoScale ? 'translate-x-5' : 'translate-x-1'
                }`} />
              </div>
            </label>
          </div>
        </div>

        {/* 恢复默认 */}
        <div className="pt-4 border-t border-gray-600">
          <button
            onClick={() => onConfigChange({
              chartStyle: 'candlestick',
              priceAxisMode: 'linear',
              displayMode: 'normal',
              autoScale: true
            })}
            className="w-full py-2 px-3 bg-gray-600 hover:bg-gray-500 text-white text-sm rounded transition-colors"
          >
            恢复默认设置
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChartSettings