// 绘图工具类型定义

export interface DrawingPoint {
  x: number  // 图表数据索引
  y: number  // 价格值
  timestamp?: number  // 时间戳
  dataIndex?: number  // ECharts数据索引
}

export interface DrawingStyle {
  color: string
  lineWidth: number
  lineType: 'solid' | 'dashed' | 'dotted'
  opacity: number
  fill?: string
  fillOpacity?: number
  fontSize?: number
  fontColor?: string
}

export type DrawingToolType = 'cursor' | 'line' | 'rectangle' | 'circle' | 'fibonacci' | 'text'

export interface DrawingObject {
  id: string
  type: DrawingToolType
  points: DrawingPoint[]
  style: DrawingStyle
  label?: string
  created: number
  modified: number
  visible: boolean
  locked: boolean
}

export interface FibonacciLevels {
  levels: number[]  // [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
  showLabels: boolean
  extendLines: boolean
}

export interface DrawingState {
  drawings: DrawingObject[]
  selectedDrawing: string | null
  isDrawing: boolean
  currentPoints: DrawingPoint[]
  activeTool: DrawingToolType | null
}

// 默认样式配置
export const DEFAULT_DRAWING_STYLES: Record<DrawingToolType, DrawingStyle> = {
  cursor: {
    color: '#666666',
    lineWidth: 1,
    lineType: 'solid',
    opacity: 1
  },
  line: {
    color: '#2563eb',
    lineWidth: 2,
    lineType: 'solid',
    opacity: 0.8
  },
  rectangle: {
    color: '#7c3aed',
    lineWidth: 2,
    lineType: 'solid',
    opacity: 0.8,
    fill: '#7c3aed',
    fillOpacity: 0.1
  },
  circle: {
    color: '#059669',
    lineWidth: 2,
    lineType: 'solid',
    opacity: 0.8,
    fill: '#059669',
    fillOpacity: 0.1
  },
  fibonacci: {
    color: '#dc2626',
    lineWidth: 1,
    lineType: 'dashed',
    opacity: 0.7,
    fill: '#dc2626',
    fillOpacity: 0.05
  },
  text: {
    color: '#1f2937',
    lineWidth: 1,
    lineType: 'solid',
    opacity: 1,
    fontSize: 12,
    fontColor: '#1f2937'
  }
}

// 斐波那契回调位
export const FIBONACCI_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

// 绘图工具配置
export interface DrawingToolConfig {
  requiresPoints: number  // 需要的点击点数
  allowsMultiPoint: boolean  // 是否允许多点绘制
  showWhileDrawing: boolean  // 绘制过程中是否显示预览
}

export const DRAWING_TOOL_CONFIGS: Record<DrawingToolType, DrawingToolConfig> = {
  cursor: { requiresPoints: 0, allowsMultiPoint: false, showWhileDrawing: false },
  line: { requiresPoints: 2, allowsMultiPoint: false, showWhileDrawing: true },
  rectangle: { requiresPoints: 2, allowsMultiPoint: false, showWhileDrawing: true },
  circle: { requiresPoints: 2, allowsMultiPoint: false, showWhileDrawing: true },
  fibonacci: { requiresPoints: 2, allowsMultiPoint: false, showWhileDrawing: true },
  text: { requiresPoints: 1, allowsMultiPoint: false, showWhileDrawing: false }
}