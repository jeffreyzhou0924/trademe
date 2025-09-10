import React, { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { useMarketStore } from '@/store/marketStore'
import { useTradingPageStore, type ChartConfig, type DrawingTool } from '@/store/tradingPageStore'
import type { KlineData } from '@/types/market'
import { 
  calculateSMA, 
  calculateMACD, 
  calculateRSI, 
  calculateBOLL, 
  calculateKDJ 
} from '@/utils/technicalIndicators'

interface KlineChartProps {
  symbol: string
  timeframe: string
  exchange: string
  config: ChartConfig
  className?: string
  chartRef?: React.MutableRefObject<echarts.ECharts | null>
  drawingTools?: {
    drawingState: any
    handleChartClick: (params: any) => void
    updateChartDrawings: (drawings: any[], klineData?: any[]) => void
    loadDrawingsFromStorage: () => any[]
  }
}

const KlineChart: React.FC<KlineChartProps> = ({
  symbol,
  timeframe,
  exchange,
  config,
  className = '',
  chartRef,
  drawingTools
}) => {
  const chartDomRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  
  // 处理数据显示模式
  const processDataForDisplayMode = (data: KlineData[], config: ChartConfig) => {
    if (!data || data.length === 0) {
      return { processedOhlc: [], processedVolumes: [] }
    }
    
    const basePrice = data[0].close // 基准价格（第一根K线收盘价）
    
    let processedOhlc = data.map(item => [item.open, item.close, item.low, item.high])
    let processedVolumes = data.map(item => item.volume)
    
    // 百分比显示模式
    if (config.displayMode === 'percentage') {
      processedOhlc = data.map(item => [
        ((item.open - basePrice) / basePrice * 100),
        ((item.close - basePrice) / basePrice * 100), 
        ((item.low - basePrice) / basePrice * 100),
        ((item.high - basePrice) / basePrice * 100)
      ])
    }
    
    return { processedOhlc, processedVolumes }
  }
  
  // 计算自动缩放范围
  const calculateAutoZoomRange = (data: KlineData[]) => {
    if (!data || data.length < 50) return { start: 0, end: 100 }
    
    // 显示最近50-100根K线
    const visibleBars = Math.min(100, Math.max(50, data.length * 0.8))
    const start = Math.max(0, ((data.length - visibleBars) / data.length) * 100)
    
    return { start: Math.round(start), end: 100 }
  }
  
  // 使用trading page store获取配置、绘图工具和实时K线数据
  const { 
    chartConfig, 
    klineDataStore,
    isDataLoading
  } = useTradingPageStore()
  
  // 备用：如果TradingPageStore没有数据，使用市场数据store
  const { 
    klineData: fallbackKlineData, 
    isLoading: fallbackLoading,
    fetchKlineData 
  } = useMarketStore()
  
  // 优先使用TradingPageStore的实时数据，备用MarketStore数据
  const dataKey = `${exchange}:${symbol}:${timeframe}`
  const klineData = klineDataStore[dataKey] || fallbackKlineData
  const isLoading = isDataLoading || fallbackLoading

  console.log('🔍 KlineChart调试信息:', {
    symbol,
    timeframe,
    exchange,
    dataKey,
    storeData: klineDataStore[dataKey],
    fallbackData: fallbackKlineData,
    klineDataKeys: Object.keys(klineDataStore),
    isLoading
  })

  // 初始化图表
  useEffect(() => {
    if (!chartDomRef.current) return

    console.log('📏 图表容器尺寸信息:', {
      width: chartDomRef.current.offsetWidth,
      height: chartDomRef.current.offsetHeight,
      clientWidth: chartDomRef.current.clientWidth,
      clientHeight: chartDomRef.current.clientHeight,
      scrollHeight: chartDomRef.current.scrollHeight
    })

    chartInstance.current = echarts.init(
      chartDomRef.current, 
      config.theme === 'dark' ? 'dark' : null
    )
    
    // 设置外部chartRef引用
    if (chartRef) {
      chartRef.current = chartInstance.current
    }
    
    // 添加点击事件监听以支持绘图工具
    if (drawingTools) {
      chartInstance.current.on('click', drawingTools.handleChartClick)
    }

    // 配置主题
    if (config.theme === 'dark') {
      chartInstance.current.setOption({
        backgroundColor: '#1f2937'
      })
    }
    
    return () => {
      chartInstance.current?.dispose()
    }
  }, [config.theme])

  // 获取K线数据
  useEffect(() => {
    fetchKlineData(symbol, timeframe, exchange)
  }, [symbol, timeframe, exchange, fetchKlineData])

  // 更新图表数据和配置
  useEffect(() => {
    if (!chartInstance.current) return
    
    // 获取数据，如果没有则生成模拟数据
    let data: KlineData[] = klineDataStore[dataKey] || (Array.isArray(fallbackKlineData) ? fallbackKlineData : [])
    
    // 如果仍然没有数据，生成模拟数据
    if (!data || data.length === 0) {
      console.log('🔧 生成模拟K线数据用于图表显示')
      data = generateMockKlineData(symbol, timeframe, 100)
    }

    console.log(`📊 使用的K线数据: ${data?.length || 0}条记录`)

    if (!data || data.length === 0) {
      console.warn('⚠️ 仍然没有可用的K线数据')
      return
    }

    const option = getChartOption(data, config)
    chartInstance.current.setOption(option, true)
    
    // 渲染绘图工具
    renderDrawingTools(config.drawingTools || [])
  }, [klineDataStore, fallbackKlineData, symbol, timeframe, exchange, config, dataKey])

  // 响应式更新和配置变更重绘
  useEffect(() => {
    const handleResize = () => {
      if (chartInstance.current) {
        // 延迟重绘，确保DOM更新完成
        setTimeout(() => {
          chartInstance.current?.resize()
        }, 100)
      }
    }

    window.addEventListener('resize', handleResize)
    
    // 配置变更时也要重绘
    handleResize()
    
    return () => window.removeEventListener('resize', handleResize)
  }, [config.priceAxisMode, config.chartStyle, config.theme])

  // 强制图表重绘 - 当价格轴模式变更时
  useEffect(() => {
    if (chartInstance.current) {
      setTimeout(() => {
        chartInstance.current?.resize()
      }, 50)
    }
  }, [config.priceAxisMode, config.autoScale])

  // 渲染绘图工具
  const renderDrawingTools = (drawingTools: DrawingTool[]) => {
    if (!chartInstance.current) return

    // TODO: 实现绘图工具渲染逻辑
    // 这里需要将drawingTools转换为ECharts的graphic元素
    drawingTools.forEach(tool => {
      // 根据工具类型渲染对应的图形
      switch (tool.type) {
        case 'trendline':
          renderTrendLine(tool)
          break
        case 'rectangle':
          renderRectangle(tool)
          break
        case 'horizontal':
          renderHorizontalLine(tool)
          break
        case 'vertical':
          renderVerticalLine(tool)
          break
        case 'fibonacci':
          renderFibonacci(tool)
          break
      }
    })
  }

  // 绘制趋势线
  const renderTrendLine = (tool: DrawingTool) => {
    // TODO: 实现趋势线绘制
  }

  // 绘制矩形
  const renderRectangle = (tool: DrawingTool) => {
    // TODO: 实现矩形绘制
  }

  // 绘制水平线
  const renderHorizontalLine = (tool: DrawingTool) => {
    // TODO: 实现水平线绘制
  }

  // 绘制垂直线
  const renderVerticalLine = (tool: DrawingTool) => {
    // TODO: 实现垂直线绘制
  }

  // 绘制斐波那契回调线
  const renderFibonacci = (tool: DrawingTool) => {
    // TODO: 实现斐波那契线绘制
  }

  // 生成模拟K线数据
  const generateMockKlineData = (symbol: string, timeframe: string, limit: number): KlineData[] => {
    const data: KlineData[] = []
    let basePrice = 43250.00 // BTC基础价格
    
    // 根据symbol调整基础价格
    if (symbol.includes('ETH')) basePrice = 2800.00
    else if (symbol.includes('ADA')) basePrice = 0.45
    else if (symbol.includes('SOL')) basePrice = 125.00
    
    const now = Date.now()
    const timeframeMs = getTimeframeMilliseconds(timeframe)
    
    for (let i = limit - 1; i >= 0; i--) {
      const timestamp = now - (i * timeframeMs)
      
      // 生成随机价格变动
      const variation = (Math.random() - 0.5) * 0.02 // ±1%变动
      const open = basePrice * (1 + variation)
      
      const highVariation = Math.random() * 0.01 // 0-1%向上
      const lowVariation = Math.random() * 0.01 // 0-1%向下
      const closeVariation = (Math.random() - 0.5) * 0.015 // ±0.75%变动
      
      const high = open + (open * highVariation)
      const low = open - (open * lowVariation)
      const close = open + (open * closeVariation)
      const volume = Math.random() * 50 + 10 // 10-60的随机交易量
      
      data.push({
        timestamp,
        open: parseFloat(open.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
        volume: parseFloat(volume.toFixed(4))
      })
      
      // 更新基础价格，形成趋势
      basePrice = close
    }
    
    return data
  }

  // 获取时间框架对应的毫秒数
  const getTimeframeMilliseconds = (timeframe: string): number => {
    const timeframeMap: Record<string, number> = {
      '1m': 60 * 1000,
      '5m': 5 * 60 * 1000,
      '15m': 15 * 60 * 1000,
      '30m': 30 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '2h': 2 * 60 * 60 * 1000,
      '4h': 4 * 60 * 60 * 1000,
      '6h': 6 * 60 * 60 * 1000,
      '12h': 12 * 60 * 60 * 1000,
      '1d': 24 * 60 * 60 * 1000,
      '3d': 3 * 24 * 60 * 60 * 1000,
      '1w': 7 * 24 * 60 * 60 * 1000,
      '1M': 30 * 24 * 60 * 60 * 1000
    }
    
    return timeframeMap[timeframe] || timeframeMap['15m']
  }

  // 计算Heikin-Ashi蜡烛图数据
  const calculateHeikinAshi = (klineData: KlineData[]): number[][] => {
    if (!klineData || klineData.length === 0) return []
    
    const result: number[][] = []
    let prevHA = { open: 0, close: 0 }
    
    klineData.forEach((candle, index) => {
      let haOpen, haClose, haHigh, haLow
      
      // Heikin-Ashi Close = (Open + High + Low + Close) / 4
      haClose = (candle.open + candle.high + candle.low + candle.close) / 4
      
      if (index === 0) {
        // 第一根蜡烛的开盘价 = (Open + Close) / 2
        haOpen = (candle.open + candle.close) / 2
      } else {
        // Heikin-Ashi Open = (前一根HA Open + 前一根HA Close) / 2
        haOpen = (prevHA.open + prevHA.close) / 2
      }
      
      // Heikin-Ashi High = Max(High, HA Open, HA Close)
      haHigh = Math.max(candle.high, haOpen, haClose)
      
      // Heikin-Ashi Low = Min(Low, HA Open, HA Close)
      haLow = Math.min(candle.low, haOpen, haClose)
      
      // ECharts蜡烛图数据格式: [open, close, low, high]
      result.push([
        parseFloat(haOpen.toFixed(2)),
        parseFloat(haClose.toFixed(2)),
        parseFloat(haLow.toFixed(2)),
        parseFloat(haHigh.toFixed(2))
      ])
      
      // 保存当前HA值供下一根蜡烛使用
      prevHA = { open: haOpen, close: haClose }
    })
    
    return result
  }

  // 生成图表配置 - 基于现有实现，适配新的配置系统
  const getChartOption = (data: KlineData[], config: ChartConfig) => {
    const times = data.map(item => new Date(item.timestamp).toLocaleString())
    
    // 根据显示模式处理数据
    const { processedOhlc, processedVolumes } = processDataForDisplayMode(data, config)
    const ohlc = processedOhlc
    const volumes = processedVolumes
    const closePrices = data.map(item => item.close)
    
    // 根据激活的指标计算技术指标数据
    const activeIndicators = config.indicators
    const indicators = {
      ma: { enabled: activeIndicators.some(id => id.startsWith('ma_')), periods: [5, 10, 20, 60] },
      volume: { enabled: activeIndicators.includes('volume') },
      macd: { enabled: activeIndicators.includes('macd'), params: { fast: 12, slow: 26, signal: 9 } },
      rsi: { enabled: activeIndicators.includes('rsi'), params: { period: 14 } },
      boll: { enabled: activeIndicators.includes('boll'), params: { period: 20, multiplier: 2 } },
      kdj: { enabled: activeIndicators.includes('kdj'), params: { period: 9 } }
    }
    
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

    // 根据图表样式生成不同的主图系列
    const series: any[] = []
    let legendData: string[] = []
    
    // 生成主图数据系列
    if (config.chartStyle === 'line') {
      // 线图模式 - 只显示收盘价线
      series.push({
        name: '收盘价',
        type: 'line',
        data: closePrices,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: { 
          color: '#4f46e5', 
          width: 2 
        },
        showSymbol: false,
        smooth: false
      })
      legendData.push('收盘价')
    } else if (config.chartStyle === 'area') {
      // 面积图模式 - 收盘价填充面积
      series.push({
        name: '收盘价',
        type: 'line',
        data: closePrices,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: { 
          color: '#4f46e5', 
          width: 2 
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(79, 70, 229, 0.4)' },
              { offset: 1, color: 'rgba(79, 70, 229, 0.1)' }
            ]
          }
        },
        showSymbol: false,
        smooth: true
      })
      legendData.push('收盘价')
    } else if (config.chartStyle === 'heikin-ashi') {
      // 平均蜡烛图模式 - 计算Heikin-Ashi值
      const heikinAshiData = calculateHeikinAshi(data)
      series.push({
        name: 'Heikin-Ashi',
        type: 'candlestick',
        data: heikinAshiData,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#21ce90', // 阳线颜色（绿色）
          color0: '#f53d3d', // 阴线颜色（红色）
          borderColor: '#21ce90',
          borderColor0: '#f53d3d',
          opacity: 0.8
        }
      })
      legendData.push('Heikin-Ashi')
    } else {
      // 默认蜡烛图模式
      series.push({
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
      })
      legendData.push('K线')
    }

    // 添加移动平均线
    if (indicators.ma.enabled) {
      const activeMAPeriods = activeIndicators
        .filter(id => id.startsWith('ma_'))
        .map(id => parseInt(id.split('_')[1]))
        .filter(period => indicators.ma.periods.includes(period))
      
      activeMAPeriods.forEach((period: number, index: number) => {
        const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#ffa726']
        const maName = `MA${period}`
        series.push({
          name: maName,
          type: 'line',
          data: calculateMA(period),
          smooth: true,
          lineStyle: {
            color: colors[index % colors.length],
            width: 2
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
      legendData.push('K', 'D', 'J')
      currentGridIndex++
    }

    // 主题适配
    const isDark = config.theme === 'dark'
    const backgroundColor = isDark ? '#1f2937' : '#ffffff'
    const textColor = isDark ? '#e5e7eb' : '#666666'
    const gridLineColor = isDark ? '#374151' : '#f5f5f5'
    const borderColor = isDark ? '#4b5563' : '#ddd'

    return {
      animation: false,
      backgroundColor,
      legend: {
        data: legendData,
        top: 10,
        left: 'center',
        textStyle: { color: textColor, fontSize: 11 },
        type: 'scroll',
        itemWidth: 12,
        itemHeight: 8
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: { color: textColor }
        },
        backgroundColor: isDark ? 'rgba(31, 41, 55, 0.95)' : 'rgba(0, 0, 0, 0.8)',
        borderColor: borderColor,
        textStyle: { color: isDark ? '#e5e7eb' : '#fff', fontSize: 12 },
        formatter: function(params: any) {
          if (!params || params.length === 0) return ''
          
          let tooltip = `<div style="text-align: left; min-width: 200px;">`
          tooltip += `<div style="margin-bottom: 8px; font-weight: bold;">${symbol}</div>`
          tooltip += `<div style="margin-bottom: 8px; color: ${isDark ? '#9ca3af' : '#ccc'};">${params[0].name}</div>`
          
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
          
          tooltip += `</div>`
          return tooltip
        }
      },
      axisPointer: {
        link: { xAxisIndex: 'all' }
      },
      grid: (() => {
        const grids = []
        
        // 优化高度分配算法，确保图表充分利用空间
        const legendHeight = 5 // 图例占用5%
        const sliderHeight = 8 // 滑块占用8%
        const availableSpace = 100 - legendHeight - sliderHeight - 2 // 可用空间，预留2%边距
        
        let currentTop = legendHeight + 2
        
        // 根据图表数量动态分配高度
        let mainChartHeight, subChartHeight
        
        if (gridCount === 1) {
          // 只有K线主图时，占用最大空间
          mainChartHeight = availableSpace - 2
        } else if (gridCount === 2) {
          // K线主图 + 1个指标图
          mainChartHeight = Math.floor(availableSpace * 0.7) // 70%给主图
          subChartHeight = Math.floor(availableSpace * 0.28) // 28%给副图，留2%间距
        } else if (gridCount === 3) {
          // K线主图 + 2个指标图
          mainChartHeight = Math.floor(availableSpace * 0.6) // 60%给主图
          subChartHeight = Math.floor((availableSpace * 0.38) / 2) // 38%平分给副图
        } else {
          // K线主图 + 3+个指标图
          mainChartHeight = Math.floor(availableSpace * 0.5) // 50%给主图
          subChartHeight = Math.floor((availableSpace * 0.48) / (gridCount - 1)) // 48%平分给副图
        }
        
        // K线主图
        grids.push({
          left: '6%',
          right: '6%', 
          top: `${currentTop}%`,
          height: `${mainChartHeight}%`,
          backgroundColor: 'transparent'
        })
        currentTop += mainChartHeight + 1
        
        // 其他指标图
        for (let i = 1; i < gridCount; i++) {
          grids.push({
            left: '6%',
            right: '6%',
            top: `${currentTop}%`,
            height: `${subChartHeight}%`,
            backgroundColor: 'transparent'
          })
          currentTop += subChartHeight + 1
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
            axisLine: { lineStyle: { color: borderColor } },
            axisTick: { show: false },
            axisLabel: {
              show: i === gridCount - 1, // 只在最后一个图显示时间
              color: textColor,
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
        
        for (let i = 0; i < gridCount; i++) {
          const baseConfig = {
            gridIndex: i,
            position: 'right',
            axisLine: { lineStyle: { color: borderColor } },
            axisTick: { show: false },
            axisLabel: { 
              color: textColor, 
              fontSize: 11
            },
            splitLine: { lineStyle: { color: gridLineColor, width: 1 } }
          }
          
          if (i === 0) {
            // 主图Y轴 - 价格轴，根据不同模式配置
            const mainAxisConfig = {
              ...baseConfig,
              scale: config.autoScale,
              axisLabel: {
                ...baseConfig.axisLabel,
                formatter: (value: number) => {
                  if (config.priceAxisMode === 'percentage') {
                    const firstPrice = data.length > 0 ? data[0].close : value
                    const percentage = ((value - firstPrice) / firstPrice * 100).toFixed(2)
                    return `${percentage}%`
                  }
                  return value.toFixed(2)
                }
              }
            }
            
            if (config.priceAxisMode === 'logarithmic') {
              // 对数模式
              yAxes.push({
                ...mainAxisConfig,
                type: 'log',
                logBase: 10
              })
            } else if (config.priceAxisMode === 'percentage') {
              // 百分比模式 - 坐标轴显示百分比
              yAxes.push({
                ...mainAxisConfig,
                type: 'value',
                axisLabel: {
                  ...mainAxisConfig.axisLabel,
                  formatter: (value: number) => `${value.toFixed(2)}%`
                }
              })
            } else {
              // 线性模式（默认）
              yAxes.push({
                ...mainAxisConfig,
                type: 'value'
              })
            }
          } else {
            // 副图Y轴 - 指标轴
            yAxes.push({
              ...baseConfig,
              type: 'value',
              scale: true
            })
          }
        }
        
        return yAxes
      })(),
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: Array.from({ length: gridCount }, (_, i) => i),
          start: config.autoScale ? calculateAutoZoomRange(data).start : 80,
          end: config.autoScale ? calculateAutoZoomRange(data).end : 100
        },
        {
          show: true,
          xAxisIndex: Array.from({ length: gridCount }, (_, i) => i),
          type: 'slider',
          bottom: 10,
          start: config.autoScale ? calculateAutoZoomRange(data).start : 80,
          end: config.autoScale ? calculateAutoZoomRange(data).end : 100,
          textStyle: { color: textColor },
          borderColor: borderColor,
          backgroundColor: isDark ? '#374151' : '#f8f9fa'
        }
      ],
      series
    }
  }

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* 图表容器 */}
      <div 
        ref={chartDomRef} 
        className={`w-full h-full min-h-[500px] ${config.theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}
        style={{ height: '100%', minHeight: '500px' }}
      />
      
      {/* 加载状态 */}
      {isLoading && (
        <div className={`absolute inset-0 flex items-center justify-center ${
          config.theme === 'dark' ? 'bg-gray-800 bg-opacity-75' : 'bg-white bg-opacity-75'
        }`}>
          <div className={`${
            config.theme === 'dark' ? 'text-gray-300' : 'text-gray-500'
          }`}>
            加载中...
          </div>
        </div>
      )}
    </div>
  )
}

export default KlineChart