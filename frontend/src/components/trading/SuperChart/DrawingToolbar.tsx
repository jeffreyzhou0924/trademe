import React, { useState } from 'react'
import { useTradingPageStore } from '@/store/tradingPageStore'
import { DrawingToolType } from '@/types/drawing'

interface DrawingToolbarProps {
  className?: string
  drawingTools?: {
    drawingState: any
    setActiveTool: (tool: DrawingToolType | null) => void
    clearAllDrawings: () => void
    cancelDrawing: () => void
  }
}

// 绘图工具定义 - 参考TradingView设计
const drawingToolsConfig = [
  {
    id: 'cursor' as DrawingToolType,
    name: '选择工具',
    icon: (active: boolean) => (
      <svg className="w-4 h-4" fill={active ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={active ? 0 : 1.5} 
              d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
      </svg>
    ),
    shortcut: 'Alt+S',
    category: 'basic'
  },
  // 分割线
  { id: 'separator-1', type: 'separator' },
  {
    id: 'line' as DrawingToolType,
    name: '趋势线',
    icon: (active: boolean) => (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={active ? 2 : 1.5} 
              d="M4 20L20 4" />
      </svg>
    ),
    shortcut: 'Alt+T',
    category: 'lines'
  },
  // 分割线
  { id: 'separator-2', type: 'separator' },
  {
    id: 'rectangle' as DrawingToolType,
    name: '矩形',
    icon: (active: boolean) => (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={active ? 2 : 1.5} 
              d="M4 6h16v12H4z" />
      </svg>
    ),
    shortcut: 'Alt+Shift+R',
    category: 'shapes'
  },
  {
    id: 'circle' as DrawingToolType,
    name: '圆形',
    icon: (active: boolean) => (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="8" strokeWidth={active ? 2 : 1.5} />
      </svg>
    ),
    shortcut: 'Alt+Shift+C',
    category: 'shapes'
  },
  // 分割线
  { id: 'separator-3', type: 'separator' },
  {
    id: 'fibonacci' as DrawingToolType,
    name: '斐波那契回调',
    icon: (active: boolean) => (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={active ? 2 : 1.5} 
              d="M4 20L20 4M4 16h16M4 12h16M4 8h16" />
      </svg>
    ),
    shortcut: 'Alt+F',
    category: 'fibonacci'
  },
  // 分割线
  { id: 'separator-4', type: 'separator' },
  {
    id: 'text' as DrawingToolType,
    name: '文本标注',
    icon: (active: boolean) => (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={active ? 2 : 1.5} 
              d="M7 8h10M7 12h4m-7-8V4a2 2 0 012-2h8a2 2 0 012 2v4M7 20h10" />
      </svg>
    ),
    shortcut: 'Alt+X',
    category: 'annotation'
  }
]

const DrawingToolbar: React.FC<DrawingToolbarProps> = ({ className = '', drawingTools }) => {
  const [showTooltip, setShowTooltip] = useState<string | null>(null)
  
  // 获取当前激活的工具
  const activeTool = drawingTools?.drawingState?.activeTool || 'cursor'

  const handleToolClick = (toolId: DrawingToolType) => {
    if (!drawingTools) return
    
    if (toolId === activeTool) {
      // 如果点击已激活的工具，回到默认选择工具
      drawingTools.setActiveTool('cursor')
    } else {
      drawingTools.setActiveTool(toolId)
    }
    
    console.log(`激活绘图工具: ${toolId}`)
  }

  // 过滤出实际的工具（排除分割线）
  const toolItems = drawingToolsConfig.filter(tool => tool.type !== 'separator')

  return (
    <div className={`flex flex-col bg-gray-900/95 backdrop-blur-sm border-r border-gray-700/50 ${className}`}>
      {/* 工具栏头部 */}
      <div className="px-1 py-2 border-b border-gray-700/30">
        <div className="text-xs font-medium text-gray-400 text-center">绘图工具</div>
      </div>

      {/* 工具按钮区域 */}
      <div className="flex flex-col flex-1 px-1 py-2 space-y-1 overflow-y-auto">
        {drawingToolsConfig.map((tool, index) => {
          // 渲染分割线
          if (tool.type === 'separator') {
            return (
              <div key={tool.id} className="h-px bg-gray-700/50 mx-2 my-1" />
            )
          }

          const isActive = activeTool === tool.id
          
          return (
            <div
              key={tool.id}
              className="relative"
              onMouseEnter={() => setShowTooltip(tool.id)}
              onMouseLeave={() => setShowTooltip(null)}
            >
              <button
                onClick={() => handleToolClick(tool.id as DrawingToolType)}
                className={`w-8 h-8 rounded-md flex items-center justify-center transition-all duration-200 relative group ${
                  isActive 
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25 ring-2 ring-blue-400/30' 
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/80'
                }`}
                title={`${tool.name} (${tool.shortcut})`}
              >
                {tool.icon(isActive)}
                
                {/* 激活状态指示器 */}
                {isActive && (
                  <div className="absolute -right-0.5 top-1/2 transform -translate-y-1/2 w-1 h-4 bg-blue-400 rounded-full" />
                )}
              </button>

              {/* 工具提示 */}
              {showTooltip === tool.id && (
                <div className="absolute left-full ml-2 top-1/2 transform -translate-y-1/2 z-50 px-2 py-1.5 bg-gray-800 text-white text-xs rounded shadow-lg border border-gray-600 whitespace-nowrap">
                  <div className="font-medium">{tool.name}</div>
                  <div className="text-gray-400 text-xs">{tool.shortcut}</div>
                  {/* 箭头指示器 */}
                  <div className="absolute right-full top-1/2 transform -translate-y-1/2 w-0 h-0 border-t-4 border-b-4 border-r-4 border-transparent border-r-gray-800" />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* 底部操作区域 */}
      <div className="px-1 py-2 border-t border-gray-700/30 space-y-1">
        {/* 清除所有绘图 */}
        <button 
          onClick={() => {
            drawingTools?.clearAllDrawings()
            console.log('清除所有绘图')
          }}
          className="w-8 h-8 rounded-md flex items-center justify-center text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200"
          title="清除所有绘图 (Alt+Del)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} 
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>

        {/* 锁定/解锁绘图 */}
        <button 
          className="w-8 h-8 rounded-md flex items-center justify-center text-gray-400 hover:text-yellow-400 hover:bg-yellow-500/10 transition-all duration-200"
          title="锁定/解锁绘图 (Alt+L)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} 
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </button>

        {/* 绘图样式设置 */}
        <button 
          className="w-8 h-8 rounded-md flex items-center justify-center text-gray-400 hover:text-blue-400 hover:bg-blue-500/10 transition-all duration-200"
          title="绘图样式 (Alt+Shift+S)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} 
                  d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zM7 21h16M7 5a2 2 0 012-2h10a2 2 0 012 2v12a4 4 0 01-4 4H9a4 4 0 01-4-4V5z" />
          </svg>
        </button>
      </div>
    </div>
  )
}

export default DrawingToolbar