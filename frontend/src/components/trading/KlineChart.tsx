import React, { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { useMarketStore } from '../../store/marketStore'
import type { KlineData } from '../../types/market'

interface KlineChartProps {
  width?: string | number
  height?: string | number
  className?: string
}

const KlineChart: React.FC<KlineChartProps> = ({ 
  width = '100%', 
  height = 400,
  className = '' 
}) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  const { 
    klineData, 
    selectedSymbol, 
    selectedTimeframe, 
    selectedExchange,
    isLoading,
    fetchKlineData 
  } = useMarketStore()
  
  const [indicators, setIndicators] = useState({
    ma: { enabled: true, periods: [5, 10, 20, 60] },
    volume: { enabled: true },
    macd: { enabled: false },
    rsi: { enabled: false }
  })

  // 初始化图表
  useEffect(() => {
    if (!chartRef.current) return

    chartInstance.current = echarts.init(chartRef.current)
    
    return () => {
      chartInstance.current?.dispose()
    }
  }, [])

  // 获取数据
  useEffect(() => {
    fetchKlineData(selectedSymbol, selectedTimeframe, selectedExchange)
  }, [selectedSymbol, selectedTimeframe, selectedExchange, fetchKlineData])

  // 更新图表数据
  useEffect(() => {
    if (!chartInstance.current || isLoading) return
    
    const dataKey = `${selectedExchange}:${selectedSymbol}:${selectedTimeframe}`
    const data = klineData[dataKey] || []
    
    if (data.length === 0) return

    const option = getChartOption(data, indicators)
    chartInstance.current.setOption(option, true)
  }, [klineData, selectedSymbol, selectedTimeframe, selectedExchange, indicators, isLoading])

  // 响应式更新
  useEffect(() => {
    const handleResize = () => {
      chartInstance.current?.resize()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // 生成图表配置
  const getChartOption = (data: KlineData[], indicators: any) => {
    const times = data.map(item => new Date(item.timestamp).toLocaleString())
    const ohlc = data.map(item => [item.open, item.close, item.low, item.high])
    const volumes = data.map(item => item.volume)
    
    // 计算移动平均线
    const calculateMA = (period: number) => {
      const ma = []
      for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
          ma.push('-')
        } else {
          const sum = data.slice(i - period + 1, i + 1).reduce((acc, item) => acc + item.close, 0)
          ma.push((sum / period).toFixed(2))
        }
      }
      return ma
    }

    const series: any[] = [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#21ce90', // 阳线颜色（绿色）
          color0: '#f53d3d', // 阴线颜色（红色）
          borderColor: '#21ce90',
          borderColor0: '#f53d3d',
        }
      }
    ]

    // 添加移动平均线
    if (indicators.ma.enabled) {
      indicators.ma.periods.forEach((period: number, index: number) => {
        const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#ffa726']
        series.push({
          name: `MA${period}`,
          type: 'line',
          data: calculateMA(period),
          smooth: true,
          lineStyle: {
            color: colors[index % colors.length],
            width: 1
          },
          showSymbol: false,
          xAxisIndex: 0,
          yAxisIndex: 0,
        })
      })
    }

    // 添加成交量
    if (indicators.volume.enabled) {
      series.push({
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: function(params: any) {
            const index = params.dataIndex
            if (index === 0) return '#21ce90'
            const current = ohlc[index]
            const prev = ohlc[index - 1]
            return current[1] >= prev[1] ? '#21ce90' : '#f53d3d'
          }
        }
      })
    }

    return {
      animation: false,
      backgroundColor: '#ffffff',
      legend: {
        data: ['K线', ...indicators.ma.periods.map((p: number) => `MA${p}`)],
        top: 10,
        left: 'center',
        textStyle: { color: '#666' }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: { color: '#999' }
        },
        formatter: function(params: any) {
          const data = params[0]
          if (!data) return ''
          
          const ohlcData = data.data
          if (!ohlcData) return ''
          
          return `
            <div style="text-align: left;">
              <strong>${selectedSymbol}</strong><br/>
              时间: ${data.name}<br/>
              开盘: ${ohlcData[0]}<br/>
              收盘: ${ohlcData[1]}<br/>
              最低: ${ohlcData[2]}<br/>
              最高: ${ohlcData[3]}<br/>
              ${params.length > 1 ? `成交量: ${params[params.length - 1].data}` : ''}
            </div>
          `
        }
      },
      axisPointer: {
        link: { xAxisIndex: 'all' }
      },
      grid: [
        {
          left: '8%',
          right: '8%',
          top: '15%',
          height: indicators.volume.enabled ? '60%' : '70%'
        },
        {
          left: '8%',
          right: '8%',
          top: '80%',
          height: '15%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: times,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: { 
            color: '#666',
            formatter: function(value: string) {
              return new Date(value).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
            }
          },
          splitLine: { show: false }
        },
        {
          type: 'category',
          data: times,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false }
        }
      ],
      yAxis: [
        {
          type: 'value',
          position: 'right',
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: { color: '#666' },
          splitLine: { 
            lineStyle: { color: '#f5f5f5', width: 1 }
          }
        },
        {
          type: 'value',
          gridIndex: 1,
          position: 'right',
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 80,
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          bottom: 10,
          start: 80,
          end: 100
        }
      ],
      series
    }
  }

  const toggleIndicator = (type: string) => {
    setIndicators(prev => ({
      ...prev,
      [type]: { ...prev[type], enabled: !prev[type].enabled }
    }))
  }

  return (
    <div className={`relative ${className}`}>
      {/* 工具栏 */}
      <div className="absolute top-2 left-2 z-10 flex space-x-2">
        <button
          onClick={() => toggleIndicator('ma')}
          className={`px-3 py-1 text-xs rounded ${
            indicators.ma.enabled 
              ? 'bg-brand-500 text-white' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          MA
        </button>
        <button
          onClick={() => toggleIndicator('volume')}
          className={`px-3 py-1 text-xs rounded ${
            indicators.volume.enabled 
              ? 'bg-brand-500 text-white' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          成交量
        </button>
        <button
          onClick={() => toggleIndicator('macd')}
          className={`px-3 py-1 text-xs rounded ${
            indicators.macd.enabled 
              ? 'bg-brand-500 text-white' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          MACD
        </button>
        <button
          onClick={() => toggleIndicator('rsi')}
          className={`px-3 py-1 text-xs rounded ${
            indicators.rsi.enabled 
              ? 'bg-brand-500 text-white' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
        >
          RSI
        </button>
      </div>

      {/* 图表容器 */}
      <div 
        ref={chartRef} 
        style={{ width, height }}
        className="bg-white"
      />
      
      {/* 加载状态 */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75">
          <div className="text-gray-500">加载中...</div>
        </div>
      )}
    </div>
  )
}

export default KlineChart