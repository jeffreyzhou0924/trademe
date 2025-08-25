import React, { useRef, useEffect } from 'react'
import * as echarts from 'echarts'

interface BacktestMetrics {
  total_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  profit_factor: number
  annual_return: number
  volatility: number
  total_trades: number
}

interface EquityPoint {
  timestamp: string
  equity: number
  drawdown: number
}

interface TradeRecord {
  timestamp: string
  side: 'buy' | 'sell'
  price: number
  quantity: number
  pnl: number
}

interface BacktestResultChartProps {
  metrics: BacktestMetrics
  equityCurve: EquityPoint[]
  trades: TradeRecord[]
  className?: string
  height?: number
}

const BacktestResultChart: React.FC<BacktestResultChartProps> = ({
  metrics,
  equityCurve = [],
  trades = [],
  className = '',
  height = 400
}) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    chartInstance.current = echarts.init(chartRef.current)
    
    return () => {
      chartInstance.current?.dispose()
    }
  }, [])

  useEffect(() => {
    if (!chartInstance.current) return

    if (equityCurve.length === 0) {
      chartInstance.current.clear()
      return
    }

    const times = equityCurve.map(point => new Date(point.timestamp).toLocaleDateString())
    const equity = equityCurve.map(point => point.equity)
    const drawdown = equityCurve.map(point => -Math.abs(point.drawdown))
    
    // 标记买卖点
    const buyPoints = []
    const sellPoints = []
    
    for (const trade of trades) {
      const timeIndex = equityCurve.findIndex(point => 
        new Date(point.timestamp).getTime() >= new Date(trade.timestamp).getTime()
      )
      
      if (timeIndex !== -1) {
        const point = {
          coord: [timeIndex, equity[timeIndex]],
          value: trade.pnl > 0 ? '盈利' : '亏损',
          itemStyle: {
            color: trade.side === 'buy' ? '#21ce90' : '#f53d3d'
          }
        }
        
        if (trade.side === 'buy') {
          buyPoints.push(point)
        } else {
          sellPoints.push(point)
        }
      }
    }

    const option = {
      title: {
        text: '回测结果分析',
        left: 0,
        textStyle: {
          color: '#1a3d7c',
          fontSize: 18,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          animation: false
        }
      },
      legend: {
        data: ['资金曲线', '回撤'],
        top: 35,
        textStyle: { color: '#666' }
      },
      grid: [
        {
          left: '8%',
          right: '8%',
          top: '15%',
          height: '65%'
        },
        {
          left: '8%',
          right: '8%',
          top: '85%',
          height: '10%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: times,
          axisLine: { lineStyle: { color: '#e5e7eb' } },
          axisTick: { show: false },
          axisLabel: { color: '#6b7280' },
          splitLine: { show: false }
        },
        {
          type: 'category',
          data: times,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#e5e7eb' } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false }
        }
      ],
      yAxis: [
        {
          type: 'value',
          position: 'right',
          axisLine: { lineStyle: { color: '#e5e7eb' } },
          axisTick: { show: false },
          axisLabel: { 
            color: '#6b7280',
            formatter: '{value}'
          },
          splitLine: { 
            lineStyle: { color: '#f3f4f6', type: 'dashed' }
          }
        },
        {
          type: 'value',
          gridIndex: 1,
          position: 'right',
          axisLine: { lineStyle: { color: '#e5e7eb' } },
          axisTick: { show: false },
          axisLabel: { 
            color: '#6b7280',
            formatter: '{value}%'
          },
          splitLine: { show: false },
          max: 0,
          min: function(value: any) {
            return Math.min(value.min, -20)
          }
        }
      ],
      series: [
        {
          name: '资金曲线',
          type: 'line',
          data: equity,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#1a3d7c',
            width: 2
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(26, 61, 124, 0.3)' },
              { offset: 1, color: 'rgba(26, 61, 124, 0.05)' }
            ])
          },
          markPoint: {
            data: [
              ...buyPoints.map(point => ({
                ...point,
                symbol: 'triangle',
                symbolSize: 8,
                label: { show: false }
              })),
              ...sellPoints.map(point => ({
                ...point,
                symbol: 'triangle',
                symbolSize: 8,
                symbolRotate: 180,
                label: { show: false }
              }))
            ]
          }
        },
        {
          name: '回撤',
          type: 'line',
          data: drawdown,
          xAxisIndex: 1,
          yAxisIndex: 1,
          smooth: true,
          symbol: 'none',
          lineStyle: {
            color: '#f53d3d',
            width: 1
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(245, 61, 61, 0.2)' },
              { offset: 1, color: 'rgba(245, 61, 61, 0.05)' }
            ])
          }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 0,
          end: 100
        }
      ]
    }

    chartInstance.current.setOption(option, true)
  }, [metrics, equityCurve, trades])

  // 响应式调整
  useEffect(() => {
    const handleResize = () => {
      chartInstance.current?.resize()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 p-6 ${className}`}>
      {/* 关键指标 */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className={`text-2xl font-bold ${metrics.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {metrics.total_return >= 0 ? '+' : ''}{metrics.total_return.toFixed(2)}%
          </div>
          <div className="text-sm text-gray-500">总收益率</div>
        </div>
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-red-600">
            {metrics.max_drawdown.toFixed(2)}%
          </div>
          <div className="text-sm text-gray-500">最大回撤</div>
        </div>
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className={`text-2xl font-bold ${metrics.sharpe_ratio >= 1 ? 'text-green-600' : 'text-orange-600'}`}>
            {metrics.sharpe_ratio.toFixed(2)}
          </div>
          <div className="text-sm text-gray-500">夏普比率</div>
        </div>
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-blue-600">
            {metrics.win_rate.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-500">胜率</div>
        </div>
      </div>

      {/* 详细指标 */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-3">风险指标</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">年化收益率:</span>
              <span className={metrics.annual_return >= 0 ? 'text-green-600' : 'text-red-600'}>
                {metrics.annual_return.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">波动率:</span>
              <span className="text-gray-900">{metrics.volatility.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">盈亏比:</span>
              <span className="text-gray-900">{metrics.profit_factor.toFixed(2)}</span>
            </div>
          </div>
        </div>
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-3">交易统计</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">总交易次数:</span>
              <span className="text-gray-900">{metrics.total_trades}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">盈利交易:</span>
              <span className="text-green-600">
                {Math.round(metrics.total_trades * metrics.win_rate / 100)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">亏损交易:</span>
              <span className="text-red-600">
                {metrics.total_trades - Math.round(metrics.total_trades * metrics.win_rate / 100)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 图表 */}
      <div 
        ref={chartRef} 
        style={{ width: '100%', height: height }}
        className="bg-white"
      />
    </div>
  )
}

export default BacktestResultChart

// 导出类型定义
export type { BacktestMetrics, EquityPoint, TradeRecord }