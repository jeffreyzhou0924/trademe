import React, { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { useMarketStore } from '../../store/marketStore'
import type { KlineData } from '../../types/market'
import { 
  calculateSMA, 
  calculateMACD, 
  calculateRSI, 
  calculateBOLL, 
  calculateKDJ 
} from '../../utils/technicalIndicators'

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
    macd: { enabled: false, params: { fast: 12, slow: 26, signal: 9 } },
    rsi: { enabled: false, params: { period: 14 } },
    boll: { enabled: false, params: { period: 20, multiplier: 2 } },
    kdj: { enabled: false, params: { period: 9 } }
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
    const closePrices = data.map(item => item.close)
    
    // 计算各种技术指标
    const macdData = calculateMACD(data, indicators.macd.params.fast, indicators.macd.params.slow, indicators.macd.params.signal)
    const rsiData = calculateRSI(data, indicators.rsi.params.period)
    const bollData = calculateBOLL(data, indicators.boll.params.period, indicators.boll.params.multiplier)
    const kdjData = calculateKDJ(data, indicators.kdj.params.period)
    
    // 确定需要的图表网格数
    let gridCount = 1 // K线主图
    let currentGridIndex = 1
    
    if (indicators.volume.enabled) gridCount++
    if (indicators.macd.enabled) gridCount++
    if (indicators.rsi.enabled) gridCount++
    if (indicators.kdj.enabled) gridCount++
    
    // 计算移动平均线
    const calculateMA = (period: number) => {
      const sma = calculateSMA(closePrices, period)
      return sma.map(val => val === null ? '-' : val.toFixed(2))
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
    
    const legendData = ['K线']

    // 添加移动平均线
    if (indicators.ma.enabled) {
      indicators.ma.periods.forEach((period: number, index: number) => {
        const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#ffa726']
        const maName = `MA${period}`
        series.push({
          name: maName,
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
        legendData.push(maName)
      })
    }
    
    // 添加布林带
    if (indicators.boll.enabled) {
      series.push(
        {
          name: 'BOLL上轨',
          type: 'line',
          data: bollData.upper.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#ff9800', width: 1, type: 'dashed' },
          showSymbol: false,
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: 'BOLL中轨',
          type: 'line',
          data: bollData.middle.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#9c27b0', width: 1 },
          showSymbol: false,
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: 'BOLL下轨',
          type: 'line',
          data: bollData.lower.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#ff9800', width: 1, type: 'dashed' },
          showSymbol: false,
          xAxisIndex: 0,
          yAxisIndex: 0,
        }
      )
      legendData.push('BOLL上轨', 'BOLL中轨', 'BOLL下轨')
    }

    // 添加成交量
    if (indicators.volume.enabled) {
      series.push({
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: currentGridIndex,
        yAxisIndex: currentGridIndex,
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
      legendData.push('成交量')
      currentGridIndex++
    }
    
    // 添加MACD指标
    if (indicators.macd.enabled) {
      series.push(
        {
          name: 'MACD',
          type: 'line',
          data: macdData.macd.map(val => val === null ? '-' : val.toFixed(4)),
          lineStyle: { color: '#2196f3', width: 2 },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
        },
        {
          name: 'SIGNAL',
          type: 'line',
          data: macdData.signal.map(val => val === null ? '-' : val.toFixed(4)),
          lineStyle: { color: '#ff9800', width: 2 },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
        },
        {
          name: 'HISTOGRAM',
          type: 'bar',
          data: macdData.histogram.map(val => val === null ? 0 : val),
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
          itemStyle: {
            color: function(params: any) {
              return params.data >= 0 ? '#21ce90' : '#f53d3d'
            }
          }
        }
      )
      legendData.push('MACD', 'SIGNAL', 'HISTOGRAM')
      currentGridIndex++
    }
    
    // 添加RSI指标
    if (indicators.rsi.enabled) {
      series.push(
        {
          name: 'RSI',
          type: 'line',
          data: rsiData.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#9c27b0', width: 2 },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
        }
      )
      // RSI超买超卖线
      series.push(
        {
          name: 'RSI-70',
          type: 'line',
          data: new Array(data.length).fill(70),
          lineStyle: { color: '#f44336', width: 1, type: 'dashed' },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
          silent: true
        },
        {
          name: 'RSI-30',
          type: 'line',
          data: new Array(data.length).fill(30),
          lineStyle: { color: '#4caf50', width: 1, type: 'dashed' },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
          silent: true
        }
      )
      legendData.push('RSI')
      currentGridIndex++
    }
    
    // 添加KDJ指标
    if (indicators.kdj.enabled) {
      series.push(
        {
          name: 'K',
          type: 'line',
          data: kdjData.k.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#2196f3', width: 1 },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
        },
        {
          name: 'D',
          type: 'line',
          data: kdjData.d.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#ff9800', width: 1 },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
        },
        {
          name: 'J',
          type: 'line',
          data: kdjData.j.map(val => val === null ? '-' : val.toFixed(2)),
          lineStyle: { color: '#9c27b0', width: 1 },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
        }
      )
      // KDJ超买超卖线
      series.push(
        {
          name: 'KDJ-80',
          type: 'line',
          data: new Array(data.length).fill(80),
          lineStyle: { color: '#f44336', width: 1, type: 'dashed' },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
          silent: true
        },
        {
          name: 'KDJ-20',
          type: 'line',
          data: new Array(data.length).fill(20),
          lineStyle: { color: '#4caf50', width: 1, type: 'dashed' },
          showSymbol: false,
          xAxisIndex: currentGridIndex,
          yAxisIndex: currentGridIndex,
          silent: true
        }
      )
      legendData.push('K', 'D', 'J')
      currentGridIndex++
    }

    return {
      animation: false,
      backgroundColor: '#ffffff',
      legend: {
        data: legendData,
        top: 10,
        left: 'center',
        textStyle: { color: '#666', fontSize: 11 },
        type: 'scroll',
        itemWidth: 12,
        itemHeight: 8
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: { color: '#666' }
        },
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        borderColor: '#666',
        textStyle: { color: '#fff', fontSize: 12 },
        formatter: function(params: any) {
          if (!params || params.length === 0) return ''
          
          let tooltip = `<div style="text-align: left; min-width: 200px;">`
          tooltip += `<div style="margin-bottom: 8px; font-weight: bold; color: #fff;">${selectedSymbol}</div>`
          tooltip += `<div style="margin-bottom: 8px; color: #ccc;">${params[0].name}</div>`
          
          // K线数据
          const klineData = params.find((p: any) => p.seriesName === 'K线')
          if (klineData && klineData.data) {
            const [open, close, low, high] = klineData.data
            const changePercent = ((close - open) / open * 100).toFixed(2)
            const changeColor = close >= open ? '#21ce90' : '#f53d3d'
            
            tooltip += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">`
            tooltip += `<span>开盘:</span><span>${open}</span></div>`
            tooltip += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">`
            tooltip += `<span>收盘:</span><span style="color: ${changeColor}">${close} (${changePercent}%)</span></div>`
            tooltip += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">`
            tooltip += `<span>最高:</span><span>${high}</span></div>`
            tooltip += `<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">`
            tooltip += `<span>最低:</span><span>${low}</span></div>`
          }
          
          // 成交量
          const volumeData = params.find((p: any) => p.seriesName === '成交量')
          if (volumeData) {
            const volume = volumeData.data
            const volumeStr = volume >= 1e9 ? (volume / 1e9).toFixed(2) + 'B' :
                             volume >= 1e6 ? (volume / 1e6).toFixed(2) + 'M' :
                             volume >= 1e3 ? (volume / 1e3).toFixed(2) + 'K' :
                             volume.toFixed(0)
            tooltip += `<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">`
            tooltip += `<span>成交量:</span><span>${volumeStr}</span></div>`
          }
          
          // 技术指标
          const indicators = params.filter((p: any) => 
            ['MACD', 'SIGNAL', 'RSI', 'K', 'D', 'J'].includes(p.seriesName)
          )
          if (indicators.length > 0) {
            tooltip += `<div style="border-top: 1px solid #666; padding-top: 8px; margin-top: 8px;">`
            indicators.forEach((indicator: any) => {
              if (indicator.data !== '-' && indicator.data != null) {
                tooltip += `<div style="display: flex; justify-content: space-between; margin-bottom: 2px;">`
                tooltip += `<span>${indicator.seriesName}:</span><span>${parseFloat(indicator.data).toFixed(2)}</span></div>`
              }
            })
            tooltip += `</div>`
          }
          
          tooltip += `</div>`
          return tooltip
        }
      },
      axisPointer: {
        link: { xAxisIndex: 'all' }
      },
      grid: (() => {
        const grids = []
        let currentTop = 15
        
        // K线主图占据大部分空间
        const mainChartHeight = gridCount === 1 ? 75 : 
                               gridCount === 2 ? 60 : 
                               gridCount === 3 ? 50 : 45
        
        // K线主图
        grids.push({
          left: '8%',
          right: '8%', 
          top: `${currentTop}%`,
          height: `${mainChartHeight}%`
        })
        currentTop += mainChartHeight + 2
        
        // 计算剩余空间给其他指标
        const remainingSpace = 85 - mainChartHeight - 2 * (gridCount - 1)
        const subChartHeight = gridCount > 1 ? Math.floor(remainingSpace / (gridCount - 1)) : 0
        
        // 成交量图 (相对较小)
        if (indicators.volume.enabled) {
          grids.push({
            left: '8%',
            right: '8%',
            top: `${currentTop}%`,
            height: `${Math.min(subChartHeight, 15)}%`  // 成交量最多卅15%
          })
          currentTop += Math.min(subChartHeight, 15) + 2
        }
        
        // MACD指标
        if (indicators.macd.enabled) {
          grids.push({
            left: '8%',
            right: '8%',
            top: `${currentTop}%`,
            height: `${subChartHeight}%`
          })
          currentTop += subChartHeight + 2
        }
        
        // RSI指标
        if (indicators.rsi.enabled) {
          grids.push({
            left: '8%',
            right: '8%',
            top: `${currentTop}%`,
            height: `${subChartHeight}%`
          })
          currentTop += subChartHeight + 2
        }
        
        // KDJ指标
        if (indicators.kdj.enabled) {
          grids.push({
            left: '8%',
            right: '8%',
            top: `${currentTop}%`,
            height: `${subChartHeight}%`
          })
          currentTop += subChartHeight + 2
        }
        
        return grids
      })(),
      xAxis: (() => {
        const xAxes = []
        for (let i = 0; i < gridCount; i++) {
          xAxes.push({
            type: 'category',
            data: times,
            gridIndex: i,
            axisLine: { lineStyle: { color: '#ddd' } },
            axisTick: { show: false },
            axisLabel: {
              show: i === gridCount - 1, // 只在最后一个图显示时间
              color: '#666',
              formatter: function(value: string) {
                return new Date(value).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
              }
            },
            splitLine: { show: false }
          })
        }
        return xAxes
      })(),
      yAxis: (() => {
        const yAxes = []
        let currentYAxisIndex = 0
        
        // K线主图 Y轴 - 更大的标签字体
        yAxes.push({
          type: 'value',
          gridIndex: currentYAxisIndex,
          position: 'right',
          axisLine: { lineStyle: { color: '#ddd' } },
          axisTick: { show: false },
          axisLabel: { color: '#666', fontSize: 11 },
          splitLine: { lineStyle: { color: '#f5f5f5', width: 1 } }
        })
        currentYAxisIndex++
        
        // 成交量Y轴 - 简化显示
        if (indicators.volume.enabled) {
          yAxes.push({
            type: 'value',
            gridIndex: currentYAxisIndex,
            position: 'right',
            axisLine: { lineStyle: { color: '#ddd' } },
            axisTick: { show: false },
            axisLabel: { 
              color: '#666', 
              fontSize: 10,
              formatter: function(value: number) {
                if (value >= 1e9) return (value / 1e9).toFixed(1) + 'B'
                if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M'
                if (value >= 1e3) return (value / 1e3).toFixed(1) + 'K'
                return value.toFixed(0)
              }
            },
            splitLine: { show: false }
          })
          currentYAxisIndex++
        }
        
        // MACD Y轴
        if (indicators.macd.enabled) {
          yAxes.push({
            type: 'value',
            gridIndex: currentYAxisIndex,
            position: 'right',
            axisLine: { lineStyle: { color: '#ddd' } },
            axisTick: { show: false },
            axisLabel: { color: '#666', fontSize: 10 },
            splitLine: { lineStyle: { color: '#f5f5f5', width: 1, opacity: 0.3 } }
          })
          currentYAxisIndex++
        }
        
        // RSI Y轴 - 固定范围 0-100
        if (indicators.rsi.enabled) {
          yAxes.push({
            type: 'value',
            gridIndex: currentYAxisIndex,
            position: 'right',
            min: 0,
            max: 100,
            interval: 20,  // 每20个单位一个刻度
            axisLine: { lineStyle: { color: '#ddd' } },
            axisTick: { show: false },
            axisLabel: { color: '#666', fontSize: 10 },
            splitLine: { lineStyle: { color: '#f5f5f5', width: 1, opacity: 0.3 } }
          })
          currentYAxisIndex++
        }
        
        // KDJ Y轴 - 固定范围 0-100
        if (indicators.kdj.enabled) {
          yAxes.push({
            type: 'value',
            gridIndex: currentYAxisIndex,
            position: 'right',
            min: 0,
            max: 100,
            interval: 20,  // 每20个单位一个刻度
            axisLine: { lineStyle: { color: '#ddd' } },
            axisTick: { show: false },
            axisLabel: { color: '#666', fontSize: 10 },
            splitLine: { lineStyle: { color: '#f5f5f5', width: 1, opacity: 0.3 } }
          })
          currentYAxisIndex++
        }
        
        return yAxes
      })(),
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: Array.from({ length: gridCount }, (_, i) => i),
          start: 80,
          end: 100
        },
        {
          show: true,
          xAxisIndex: Array.from({ length: gridCount }, (_, i) => i),
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
      [type]: { ...prev[type as keyof typeof prev], enabled: !prev[type as keyof typeof prev].enabled }
    }))
  }

  return (
    <div className={`relative ${className}`}>
      {/* 技术指标工具栏 */}
      <div className="absolute top-2 left-2 z-10 flex flex-wrap gap-1 max-w-xs">
        <button
          onClick={() => toggleIndicator('ma')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            indicators.ma.enabled 
              ? 'bg-blue-500 text-white shadow-sm' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
          title="移动平均线"
        >
          MA
        </button>
        <button
          onClick={() => toggleIndicator('boll')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            indicators.boll.enabled 
              ? 'bg-purple-500 text-white shadow-sm' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
          title="布林带"
        >
          BOLL
        </button>
        <button
          onClick={() => toggleIndicator('volume')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            indicators.volume.enabled 
              ? 'bg-green-500 text-white shadow-sm' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
          title="成交量"
        >
          成交量
        </button>
        <button
          onClick={() => toggleIndicator('macd')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            indicators.macd.enabled 
              ? 'bg-orange-500 text-white shadow-sm' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
          title="MACD指标"
        >
          MACD
        </button>
        <button
          onClick={() => toggleIndicator('rsi')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            indicators.rsi.enabled 
              ? 'bg-red-500 text-white shadow-sm' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
          title="RSI相对强弱指标"
        >
          RSI
        </button>
        <button
          onClick={() => toggleIndicator('kdj')}
          className={`px-2 py-1 text-xs rounded transition-colors ${
            indicators.kdj.enabled 
              ? 'bg-indigo-500 text-white shadow-sm' 
              : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
          }`}
          title="KDJ随机指标"
        >
          KDJ
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