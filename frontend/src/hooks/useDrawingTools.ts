import { useState, useCallback, useRef } from 'react'
import { 
  DrawingObject, 
  DrawingPoint, 
  DrawingState, 
  DrawingToolType, 
  DEFAULT_DRAWING_STYLES,
  DRAWING_TOOL_CONFIGS,
  FIBONACCI_LEVELS
} from '../types/drawing'
import * as echarts from 'echarts'

interface UseDrawingToolsProps {
  chartInstance: React.MutableRefObject<echarts.ECharts | null>
  symbol: string
  timeframe: string
}

export const useDrawingTools = ({ chartInstance, symbol, timeframe }: UseDrawingToolsProps) => {
  const [drawingState, setDrawingState] = useState<DrawingState>({
    drawings: [],
    selectedDrawing: null,
    isDrawing: false,
    currentPoints: [],
    activeTool: null
  })

  // 保存绘图数据到本地存储
  const saveDrawingsToStorage = useCallback((drawings: DrawingObject[]) => {
    const storageKey = `drawings_${symbol}_${timeframe}`
    localStorage.setItem(storageKey, JSON.stringify(drawings))
  }, [symbol, timeframe])

  // 从本地存储加载绘图数据
  const loadDrawingsFromStorage = useCallback(() => {
    const storageKey = `drawings_${symbol}_${timeframe}`
    const stored = localStorage.getItem(storageKey)
    if (stored) {
      try {
        const drawings = JSON.parse(stored) as DrawingObject[]
        setDrawingState(prev => ({ ...prev, drawings }))
        return drawings
      } catch (error) {
        console.error('Failed to load drawings from storage:', error)
      }
    }
    return []
  }, [symbol, timeframe])

  // 设置激活的绘图工具
  const setActiveTool = useCallback((tool: DrawingToolType | null) => {
    setDrawingState(prev => ({
      ...prev,
      activeTool: tool,
      isDrawing: false,
      currentPoints: [],
      selectedDrawing: null
    }))
  }, [])

  // 开始绘图
  const startDrawing = useCallback((point: DrawingPoint) => {
    if (!drawingState.activeTool || drawingState.activeTool === 'cursor') return

    const config = DRAWING_TOOL_CONFIGS[drawingState.activeTool]
    
    setDrawingState(prev => ({
      ...prev,
      isDrawing: true,
      currentPoints: [point]
    }))
  }, [drawingState.activeTool])

  // 添加绘图点
  const addDrawingPoint = useCallback((point: DrawingPoint) => {
    if (!drawingState.isDrawing || !drawingState.activeTool) return

    const config = DRAWING_TOOL_CONFIGS[drawingState.activeTool]
    const newPoints = [...drawingState.currentPoints, point]

    setDrawingState(prev => ({
      ...prev,
      currentPoints: newPoints
    }))

    // 如果达到所需点数，完成绘图
    if (newPoints.length >= config.requiresPoints) {
      finishDrawing(newPoints)
    }
  }, [drawingState.isDrawing, drawingState.activeTool, drawingState.currentPoints])

  // 完成绘图
  const finishDrawing = useCallback((points: DrawingPoint[]) => {
    if (!drawingState.activeTool) return

    const newDrawing: DrawingObject = {
      id: `drawing_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type: drawingState.activeTool,
      points,
      style: DEFAULT_DRAWING_STYLES[drawingState.activeTool],
      created: Date.now(),
      modified: Date.now(),
      visible: true,
      locked: false
    }

    const newDrawings = [...drawingState.drawings, newDrawing]
    
    setDrawingState(prev => ({
      ...prev,
      drawings: newDrawings,
      isDrawing: false,
      currentPoints: [],
      selectedDrawing: newDrawing.id
    }))

    // 保存到本地存储
    saveDrawingsToStorage(newDrawings)
    
    // 更新图表显示
    updateChartDrawings(newDrawings)
  }, [drawingState.activeTool, drawingState.drawings, saveDrawingsToStorage])

  // 取消当前绘图
  const cancelDrawing = useCallback(() => {
    setDrawingState(prev => ({
      ...prev,
      isDrawing: false,
      currentPoints: []
    }))
  }, [])

  // 删除选中的绘图对象
  const deleteDrawing = useCallback((drawingId: string) => {
    const newDrawings = drawingState.drawings.filter(d => d.id !== drawingId)
    
    setDrawingState(prev => ({
      ...prev,
      drawings: newDrawings,
      selectedDrawing: prev.selectedDrawing === drawingId ? null : prev.selectedDrawing
    }))

    saveDrawingsToStorage(newDrawings)
    updateChartDrawings(newDrawings)
  }, [drawingState.drawings, saveDrawingsToStorage])

  // 清除所有绘图
  const clearAllDrawings = useCallback(() => {
    setDrawingState(prev => ({
      ...prev,
      drawings: [],
      selectedDrawing: null,
      isDrawing: false,
      currentPoints: []
    }))

    saveDrawingsToStorage([])
    updateChartDrawings([])
  }, [saveDrawingsToStorage])


  // 更新图表绘图显示
  const updateChartDrawings = useCallback((drawings: DrawingObject[], klineData?: any[]) => {
    if (!chartInstance.current) return

    // 获取当前图表数据
    const option = chartInstance.current.getOption()
    const currentKlineData = klineData || option.series?.[0]?.data || []

    // 生成markLine数据用于显示直线
    const markLineData: any[] = []
    const markAreaData: any[] = []
    const markPointData: any[] = []

    drawings.forEach(drawing => {
      if (!drawing.visible) return

      switch (drawing.type) {
        case 'line':
          if (drawing.points.length >= 2) {
            const [start, end] = drawing.points
            markLineData.push({
              name: `Line_${drawing.id}`,
              lineStyle: {
                color: drawing.style.color,
                width: drawing.style.lineWidth,
                type: drawing.style.lineType === 'dashed' ? 'dashed' : 'solid'
              },
              data: [
                { coord: [start.dataIndex, start.y] },
                { coord: [end.dataIndex, end.y] }
              ]
            })
          }
          break
        
        case 'rectangle':
          if (drawing.points.length >= 2) {
            const [start, end] = drawing.points
            markAreaData.push({
              name: `Rect_${drawing.id}`,
              itemStyle: {
                color: drawing.style.fill || drawing.style.color,
                opacity: drawing.style.fillOpacity || 0.2,
                borderColor: drawing.style.color,
                borderWidth: drawing.style.lineWidth
              },
              data: [
                [{ coord: [start.dataIndex, start.y] }, { coord: [end.dataIndex, end.y] }]
              ]
            })
          }
          break
          
        case 'text':
          if (drawing.points.length >= 1) {
            const point = drawing.points[0]
            markPointData.push({
              name: `Text_${drawing.id}`,
              coord: [point.dataIndex, point.y],
              value: drawing.label || 'Text',
              itemStyle: {
                color: drawing.style.color,
                borderWidth: 0
              },
              label: {
                show: true,
                formatter: drawing.label || 'Text',
                color: drawing.style.fontColor || drawing.style.color,
                fontSize: drawing.style.fontSize || 12
              }
            })
          }
          break

        case 'fibonacci':
          if (drawing.points.length >= 2) {
            const [start, end] = drawing.points
            const startY = start.y
            const endY = end.y
            const range = endY - startY

            FIBONACCI_LEVELS.forEach(level => {
              const y = startY + range * level
              markLineData.push({
                name: `Fib_${drawing.id}_${level}`,
                lineStyle: {
                  color: drawing.style.color,
                  width: 1,
                  type: 'dashed',
                  opacity: 0.7
                },
                label: {
                  show: true,
                  formatter: `${(level * 100).toFixed(1)}%`,
                  position: 'end'
                },
                data: [
                  { coord: [start.dataIndex, y] },
                  { coord: [end.dataIndex, y] }
                ]
              })
            })
          }
          break
      }
    })

    // 更新K线系列的标记
    chartInstance.current.setOption({
      series: [{
        markLine: {
          data: markLineData,
          symbol: 'none',
          animation: false
        },
        markArea: {
          data: markAreaData,
          animation: false
        },
        markPoint: {
          data: markPointData,
          animation: false
        }
      }]
    }, false)
  }, [chartInstance])

  // 处理图表点击事件
  const handleChartClick = useCallback((params: any) => {
    if (!drawingState.activeTool || drawingState.activeTool === 'cursor') {
      // 光标模式：选择绘图对象
      // TODO: 实现选择逻辑
      return
    }

    // 计算绘图点坐标
    const point: DrawingPoint = {
      x: params.dataIndex,
      y: params.value?.[4] || params.value, // 收盘价或直接值
      timestamp: params.value?.[0],
      dataIndex: params.dataIndex
    }

    if (!drawingState.isDrawing) {
      startDrawing(point)
    } else {
      addDrawingPoint(point)
    }
  }, [drawingState.activeTool, drawingState.isDrawing, startDrawing, addDrawingPoint])

  return {
    drawingState,
    setActiveTool,
    handleChartClick,
    deleteDrawing,
    clearAllDrawings,
    cancelDrawing,
    loadDrawingsFromStorage,
    updateChartDrawings
  }
}