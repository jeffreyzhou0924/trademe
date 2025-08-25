import React, { useRef, useEffect } from 'react'
import * as echarts from 'echarts'

interface DataPoint {
  timestamp: string
  value: number
  benchmark?: number
}

interface ProfitCurveChartProps {
  data: DataPoint[]
  title?: string
  width?: string | number
  height?: string | number
  className?: string
  showBenchmark?: boolean
  benchmarkName?: string
  loading?: boolean
}

const ProfitCurveChart: React.FC<ProfitCurveChartProps> = ({
  data = [],
  title = '收益率曲线',
  width = '100%',
  height = 300,
  className = '',
  showBenchmark = false,
  benchmarkName = '基准',
  loading = false
}) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  // 初始化图表
  useEffect(() => {
    if (!chartRef.current) return

    chartInstance.current = echarts.init(chartRef.current)
    
    return () => {
      chartInstance.current?.dispose()
    }
  }, [])

  // 更新图表数据
  useEffect(() => {
    if (!chartInstance.current || loading) return

    if (data.length === 0) {
      chartInstance.current.clear()
      return
    }

    const times = data.map(item => new Date(item.timestamp).toLocaleDateString())
    const values = data.map(item => item.value)
    const benchmarkValues = showBenchmark ? data.map(item => item.benchmark || 0) : []

    // 计算累计收益率
    const cumulativeReturns = []
    const cumulativeBenchmark = []
    let base = 100 // 初始值100%
    let benchmarkBase = 100

    for (let i = 0; i < values.length; i++) {
      if (i === 0) {
        cumulativeReturns.push(base)
        if (showBenchmark) cumulativeBenchmark.push(benchmarkBase)
      } else {
        base = base * (1 + values[i] / 100)
        cumulativeReturns.push(base)
        
        if (showBenchmark && benchmarkValues[i] !== undefined) {
          benchmarkBase = benchmarkBase * (1 + benchmarkValues[i] / 100)
          cumulativeBenchmark.push(benchmarkBase)
        }
      }
    }

    const series: any[] = [
      {
        name: '策略收益',
        type: 'line',
        data: cumulativeReturns,
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
        }
      }
    ]

    // 添加基准线
    if (showBenchmark && cumulativeBenchmark.length > 0) {
      series.push({
        name: benchmarkName,
        type: 'line',
        data: cumulativeBenchmark,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#94a3b8',
          width: 1,
          type: 'dashed'
        }
      })
    }

    const option = {
      title: {
        text: title,
        left: 0,
        textStyle: {
          color: '#1a3d7c',
          fontSize: 16,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e5e7eb',
        borderWidth: 1,
        textStyle: { color: '#374151' },
        formatter: function(params: any) {
          if (!params || params.length === 0) return ''
          
          const dataIndex = params[0].dataIndex
          const originalReturn = values[dataIndex]
          const cumulativeReturn = ((cumulativeReturns[dataIndex] - 100)).toFixed(2)
          
          let content = `
            <div style="padding: 8px;">
              <div style="margin-bottom: 4px; font-weight: bold;">${params[0].name}</div>
              <div style="color: #1a3d7c;">
                当日收益: ${originalReturn > 0 ? '+' : ''}${originalReturn.toFixed(2)}%
              </div>
              <div style="color: #1a3d7c;">
                累计收益: ${parseFloat(cumulativeReturn) > 0 ? '+' : ''}${cumulativeReturn}%
              </div>
          `
          
          if (showBenchmark && params.length > 1) {
            const benchmarkCumulative = ((cumulativeBenchmark[dataIndex] - 100)).toFixed(2)
            content += `
              <div style="color: #94a3b8;">
                ${benchmarkName}累计: ${parseFloat(benchmarkCumulative) > 0 ? '+' : ''}${benchmarkCumulative}%
              </div>
            `
          }
          
          content += '</div>'
          return content
        }
      },
      legend: {
        data: showBenchmark ? ['策略收益', benchmarkName] : ['策略收益'],
        top: 35,
        right: 0,
        textStyle: { color: '#666' }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '8%',
        top: showBenchmark ? '20%' : '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: times,
        boundaryGap: false,
        axisLine: {
          lineStyle: { color: '#e5e7eb' }
        },
        axisTick: { show: false },
        axisLabel: {
          color: '#6b7280',
          fontSize: 11
        },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLine: {
          lineStyle: { color: '#e5e7eb' }
        },
        axisTick: { show: false },
        axisLabel: {
          color: '#6b7280',
          fontSize: 11,
          formatter: '{value}%'
        },
        splitLine: {
          lineStyle: { 
            color: '#f3f4f6',
            type: 'dashed'
          }
        }
      },
      series
    }

    chartInstance.current.setOption(option, true)
  }, [data, title, showBenchmark, benchmarkName, loading])

  // 响应式调整
  useEffect(() => {
    const handleResize = () => {
      chartInstance.current?.resize()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className={`relative ${className}`}>
      <div 
        ref={chartRef} 
        style={{ width, height }}
        className="bg-white"
      />
      
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <div className="text-gray-500 text-sm">加载中...</div>
          </div>
        </div>
      )}
      
      {!loading && data.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <p className="text-gray-500">暂无数据</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProfitCurveChart