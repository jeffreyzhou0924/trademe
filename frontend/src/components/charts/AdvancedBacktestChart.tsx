import React, { useRef, useEffect } from 'react'
import * as echarts from 'echarts'

interface AdvancedMetrics {
  // 基础指标
  total_return: number
  annual_return: number
  max_drawdown: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  
  // 风险指标
  volatility: number
  var_95: number
  cvar_95: number
  
  // 交易指标
  win_rate: number
  profit_factor: number
  total_trades: number
  avg_win: number
  avg_loss: number
  max_consecutive_wins: number
  max_consecutive_losses: number
  
  // 时间指标
  avg_trade_duration: number
  max_trade_duration: number
}

interface MonthlyReturn {
  year: number
  month: number
  return: number
}

interface EquityPoint {
  timestamp: string
  equity: number
  drawdown: number
  rolling_max: number
}

interface AdvancedBacktestChartProps {
  metrics: AdvancedMetrics
  equityCurve: EquityPoint[]
  monthlyReturns: MonthlyReturn[]
  className?: string
}

const AdvancedBacktestChart: React.FC<AdvancedBacktestChartProps> = ({
  metrics,
  equityCurve = [],
  monthlyReturns = [],
  className = ''
}) => {
  const equityChartRef = useRef<HTMLDivElement>(null)
  const heatmapChartRef = useRef<HTMLDivElement>(null)
  const metricsChartRef = useRef<HTMLDivElement>(null)
  const equityChart = useRef<echarts.ECharts | null>(null)
  const heatmapChart = useRef<echarts.ECharts | null>(null)
  const metricsChart = useRef<echarts.ECharts | null>(null)

  // 初始化图表
  useEffect(() => {
    if (equityChartRef.current) {
      equityChart.current = echarts.init(equityChartRef.current)
    }
    if (heatmapChartRef.current) {
      heatmapChart.current = echarts.init(heatmapChartRef.current)
    }
    if (metricsChartRef.current) {
      metricsChart.current = echarts.init(metricsChartRef.current)
    }

    return () => {
      equityChart.current?.dispose()
      heatmapChart.current?.dispose()
      metricsChart.current?.dispose()
    }
  }, [])

  // 权益曲线和回撤图表
  useEffect(() => {
    if (!equityChart.current || equityCurve.length === 0) return

    const times = equityCurve.map(point => new Date(point.timestamp).toLocaleDateString())
    const equity = equityCurve.map(point => point.equity)
    const drawdown = equityCurve.map(point => -Math.abs(point.drawdown))
    const rollingMax = equityCurve.map(point => point.rolling_max)

    const option = {
      title: {
        text: '权益曲线与回撤分析',
        left: 0,
        textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1f2937' }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          const timeIndex = params[0].dataIndex
          return `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">${times[timeIndex]}</div>
              <div style="color: #1e40af;">权益: $${equity[timeIndex].toLocaleString()}</div>
              <div style="color: #dc2626;">回撤: ${drawdown[timeIndex].toFixed(2)}%</div>
              <div style="color: #059669;">历史最高: $${rollingMax[timeIndex].toLocaleString()}</div>
            </div>
          `
        }
      },
      legend: {
        data: ['权益曲线', '历史最高', '回撤'],
        top: 25
      },
      grid: [
        { left: '8%', right: '8%', top: '15%', height: '50%' },
        { left: '8%', right: '8%', top: '70%', height: '20%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: times,
          axisLine: { lineStyle: { color: '#e5e7eb' } },
          axisTick: { show: false },
          axisLabel: { color: '#6b7280', interval: 'auto' }
        },
        {
          type: 'category',
          data: times,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#e5e7eb' } },
          axisTick: { show: false },
          axisLabel: { show: false }
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
            formatter: (value: number) => '$' + value.toLocaleString()
          },
          splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }
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
          max: 0,
          min: Math.min(...drawdown) * 1.1
        }
      ],
      series: [
        {
          name: '权益曲线',
          type: 'line',
          data: equity,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#1e40af', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(30, 64, 175, 0.3)' },
              { offset: 1, color: 'rgba(30, 64, 175, 0.05)' }
            ])
          }
        },
        {
          name: '历史最高',
          type: 'line',
          data: rollingMax,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#059669', width: 1, type: 'dashed' }
        },
        {
          name: '回撤',
          type: 'line',
          data: drawdown,
          xAxisIndex: 1,
          yAxisIndex: 1,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#dc2626', width: 1 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(220, 38, 38, 0.2)' },
              { offset: 1, color: 'rgba(220, 38, 38, 0.05)' }
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

    equityChart.current.setOption(option, true)
  }, [equityCurve])

  // 月度收益热力图
  useEffect(() => {
    if (!heatmapChart.current || monthlyReturns.length === 0) return

    const years = [...new Set(monthlyReturns.map(item => item.year))].sort()
    const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    
    const data = monthlyReturns.map(item => [
      item.month - 1, // x轴：月份（0-11）
      years.indexOf(item.year), // y轴：年份索引
      item.return // 值：收益率
    ])

    const option = {
      title: {
        text: '月度收益热力图',
        left: 0,
        textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1f2937' }
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const [month, yearIndex, returnValue] = params.data
          const year = years[yearIndex]
          const monthName = months[month]
          const color = returnValue >= 0 ? '#059669' : '#dc2626'
          return `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">${year}年${monthName}</div>
              <div style="color: ${color};">收益率: ${returnValue.toFixed(2)}%</div>
            </div>
          `
        }
      },
      grid: {
        height: '60%',
        top: '15%',
        left: '10%',
        right: '10%'
      },
      xAxis: {
        type: 'category',
        data: months,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisTick: { show: false },
        axisLabel: { color: '#6b7280' }
      },
      yAxis: {
        type: 'category',
        data: years.map(year => year.toString()),
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisTick: { show: false },
        axisLabel: { color: '#6b7280' }
      },
      visualMap: {
        min: Math.min(...monthlyReturns.map(item => item.return)),
        max: Math.max(...monthlyReturns.map(item => item.return)),
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '5%',
        inRange: {
          color: ['#dc2626', '#ffffff', '#059669']
        },
        text: ['高收益', '低收益'],
        textStyle: { color: '#6b7280' }
      },
      series: [{
        name: '月度收益',
        type: 'heatmap',
        data: data,
        label: {
          show: true,
          formatter: (params: any) => params.data[2].toFixed(1) + '%',
          color: '#1f2937',
          fontSize: 10
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    }

    heatmapChart.current.setOption(option, true)
  }, [monthlyReturns])

  // 性能指标雷达图
  useEffect(() => {
    if (!metricsChart.current) return

    const option = {
      title: {
        text: '策略性能雷达图',
        left: 0,
        textStyle: { fontSize: 16, fontWeight: 'bold', color: '#1f2937' }
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const { name, value } = params
          return `<div style="padding: 8px;"><b>${name}</b><br/>评分: ${value}</div>`
        }
      },
      radar: {
        radius: '70%',
        center: ['50%', '55%'],
        indicator: [
          { name: '收益能力', max: 100 },
          { name: '风险控制', max: 100 },
          { name: '稳定性', max: 100 },
          { name: '交易效率', max: 100 },
          { name: '回撤控制', max: 100 },
          { name: '风险收益比', max: 100 }
        ],
        axisName: {
          color: '#6b7280',
          fontSize: 12
        },
        splitArea: {
          areaStyle: {
            color: ['rgba(59, 130, 246, 0.05)', 'rgba(59, 130, 246, 0.1)']
          }
        },
        axisLine: {
          lineStyle: { color: '#e5e7eb' }
        },
        splitLine: {
          lineStyle: { color: '#e5e7eb' }
        }
      },
      series: [{
        name: '策略性能',
        type: 'radar',
        data: [{
          value: [
            Math.min(Math.max((metrics.annual_return + 50) * 2, 0), 100), // 收益能力
            Math.min(Math.max(100 - metrics.volatility * 2, 0), 100), // 风险控制
            Math.min(Math.max(metrics.sharpe_ratio * 30, 0), 100), // 稳定性
            Math.min(Math.max(metrics.win_rate, 0), 100), // 交易效率
            Math.min(Math.max(100 - Math.abs(metrics.max_drawdown) * 2, 0), 100), // 回撤控制
            Math.min(Math.max(metrics.profit_factor * 20, 0), 100) // 风险收益比
          ],
          name: '当前策略',
          areaStyle: {
            color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0.1)' }
            ])
          },
          lineStyle: {
            color: '#3b82f6',
            width: 2
          },
          symbol: 'circle',
          symbolSize: 6
        }]
      }]
    }

    metricsChart.current.setOption(option, true)
  }, [metrics])

  // 响应式调整
  useEffect(() => {
    const handleResize = () => {
      equityChart.current?.resize()
      heatmapChart.current?.resize()
      metricsChart.current?.resize()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className={`space-y-6 ${className}`}>
      {/* 核心指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 text-center">
          <div className={`text-2xl font-bold ${metrics.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {metrics.total_return >= 0 ? '+' : ''}{metrics.total_return.toFixed(2)}%
          </div>
          <div className="text-sm text-gray-500">总收益率</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-2xl font-bold text-red-600">
            {metrics.max_drawdown.toFixed(2)}%
          </div>
          <div className="text-sm text-gray-500">最大回撤</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 text-center">
          <div className={`text-2xl font-bold ${metrics.sharpe_ratio >= 1 ? 'text-green-600' : 'text-orange-600'}`}>
            {metrics.sharpe_ratio.toFixed(2)}
          </div>
          <div className="text-sm text-gray-500">夏普比率</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">
            {metrics.win_rate.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-500">胜率</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">
            {metrics.sortino_ratio.toFixed(2)}
          </div>
          <div className="text-sm text-gray-500">索提诺比率</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 text-center">
          <div className="text-2xl font-bold text-indigo-600">
            {metrics.calmar_ratio.toFixed(2)}
          </div>
          <div className="text-sm text-gray-500">卡尔玛比率</div>
        </div>
      </div>

      {/* 图表区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 权益曲线图 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div ref={equityChartRef} style={{ width: '100%', height: '400px' }} />
        </div>

        {/* 性能雷达图 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div ref={metricsChartRef} style={{ width: '100%', height: '400px' }} />
        </div>
      </div>

      {/* 月度收益热力图 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div ref={heatmapChartRef} style={{ width: '100%', height: '300px' }} />
      </div>

      {/* 详细统计表格 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">详细统计</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3">收益指标</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">年化收益率:</span>
                <span className={metrics.annual_return >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {metrics.annual_return.toFixed(2)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">总交易次数:</span>
                <span className="text-gray-900">{metrics.total_trades}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">盈亏比:</span>
                <span className="text-gray-900">{metrics.profit_factor.toFixed(2)}</span>
              </div>
            </div>
          </div>
          
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3">风险指标</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">波动率:</span>
                <span className="text-gray-900">{metrics.volatility.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">VaR (95%):</span>
                <span className="text-red-600">{metrics.var_95.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">CVaR (95%):</span>
                <span className="text-red-600">{metrics.cvar_95.toFixed(2)}%</span>
              </div>
            </div>
          </div>
          
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3">交易指标</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">平均盈利:</span>
                <span className="text-green-600">{metrics.avg_win.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">平均亏损:</span>
                <span className="text-red-600">{metrics.avg_loss.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">最大连胜:</span>
                <span className="text-green-600">{metrics.max_consecutive_wins}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdvancedBacktestChart

// 导出类型定义
export type { AdvancedMetrics, MonthlyReturn }