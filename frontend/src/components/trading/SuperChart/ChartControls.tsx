import React from 'react'

interface ChartControlsProps {
  isFullscreen: boolean
  theme: string
  onFullscreenToggle: () => void
  onThemeToggle: () => void
  onSettingsClick: () => void
}

const ChartControls: React.FC<ChartControlsProps> = ({
  isFullscreen,
  theme,
  onFullscreenToggle,
  onThemeToggle,
  onSettingsClick
}) => {
  return (
    <div className="flex items-center space-x-1">
      {/* 设置 */}
      <button
        onClick={onSettingsClick}
        className="w-8 h-8 flex items-center justify-center rounded hover:bg-gray-700 text-gray-300 transition-colors"
        title="图表设置"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {/* 全屏切换 */}
      <button
        onClick={onFullscreenToggle}
        className="w-8 h-8 flex items-center justify-center rounded hover:bg-gray-700 text-gray-300 transition-colors"
        title={isFullscreen ? '退出全屏' : '进入全屏'}
      >
        {isFullscreen ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        )}
      </button>
    </div>
  )
}

export default ChartControls