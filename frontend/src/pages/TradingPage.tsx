import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  useUserInfo, 
  useWebSocketStatus, 
  useGlobalLoading
} from '../store'
import {
  useTradingAccounts
} from '../store/tradingStore'
import useRealTimeData from '../hooks/useRealTimeData'
import { strategyApi } from '../services/api/strategy'
import { aiApi } from '../services/api'
import * as echarts from 'echarts'
import toast from 'react-hot-toast'

const TradingPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()
  
  // 页面错误状态
  const [pageError, setPageError] = useState<string | null>(null)
  
  const { 
    selectedExchange,
    supportedExchanges,
    switchExchange,
    loadSupportedExchanges 
  } = useTradingAccounts()
  
  // UI状态 (保留为本地状态)
  const [selectedMarket, setSelectedMarket] = useState('BTC/USDT')
  
  // 图表数据状态
  const [klineData, setKlineData] = useState<any[]>([])
  const [loadingKline, setLoadingKline] = useState(false)
  
  // 自定义周期状态
  const [customTimeframes, setCustomTimeframes] = useState<string[]>([])
  const [showCustomTimeframeModal, setShowCustomTimeframeModal] = useState(false)
  const [newTimeframe, setNewTimeframe] = useState('')
  
  // 实时数据连接
  const { 
    isConnected: realTimeConnected, 
    subscribeToSymbol, 
    unsubscribeFromSymbol 
  } = useRealTimeData({
    enableMarketData: true,
    enableTradingUpdates: isPremium,
    enableOrderUpdates: isPremium,
    enablePositionUpdates: isPremium,
    symbols: [selectedMarket]
  })
  
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  const [selectedTimeframe, setSelectedTimeframe] = useState('15m')
  const [currentPrice, setCurrentPrice] = useState('43,250.00')
  const [priceChange, setPriceChange] = useState('+2.34%')
  const [priceChangePercent, setPriceChangePercent] = useState(2.34)
  
  // 策略数据状态
  const [strategies, setStrategies] = useState<any[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState<any>(null)
  const [loadingStrategies, setLoadingStrategies] = useState(false)
  
  // 绘图工具状态
  const [activeDrawingTool, setActiveDrawingTool] = useState<string | null>(null)
  const [showAIAssistant, setShowAIAssistant] = useState(false)
  const [aiMessage, setAiMessage] = useState('')
  
  // AI对话状态
  const [aiMessages, setAiMessages] = useState<Array<{
    id: string
    content: string
    role: 'user' | 'assistant'
    timestamp: Date
  }>>([
    {
      id: '1',
      content: `欢迎使用AI图表分析助手！我可以帮助您：\n• 分析技术指标（RSI、MACD、布林带等）\n• 识别支撑阻力位\n• 解读价格走势\n• 提供交易建议\n\n当前正在分析：${selectedMarket}`,
      role: 'assistant',
      timestamp: new Date()
    }
  ])
  const [aiLoading, setAiLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => Date.now().toString())

  // 新增AI模式状态
  const [aiMode, setAiMode] = useState<'indicator' | 'strategy'>('indicator')
  
  // 指标管理状态 (从API获取真实用户指标数据)
  const [indicators, setIndicators] = useState<Array<{
    id: string
    name: string
    type: string
    parameters: any
    visible: boolean
    code: string
  }>>([])
  
  // 加载用户指标数据 (使用新的按类型获取API)
  const loadIndicators = async () => {
    try {
      const response = await strategyApi.getStrategiesByType('indicator')
      
      if (response && response.strategies) {
        // 转换为指标显示格式
        const indicators = response.strategies.map(strategy => ({
          id: strategy.id.toString(),
          name: strategy.name,
          type: strategy.name.includes('RSI') ? 'RSI(14)' : 
                strategy.name.includes('MACD') ? 'MACD(12,26,9)' : 
                strategy.name.includes('MA') ? 'MA' :
                '自定义指标',
          parameters: strategy.parameters || {},
          visible: strategy.is_active,
          code: strategy.code
        }))
        
        setIndicators(indicators)
        console.log('✅ 加载用户指标数据:', indicators.length, '个指标')
      }
    } catch (error) {
      console.error('❌ 加载指标数据失败:', error)
    }
  }
  
  // AI策略管理状态 (从API获取真实用户策略数据)
  const [aiStrategies, setAiStrategies] = useState<Array<{
    id: string
    name: string
    description: string
    parameters: any
    code: string
    status: 'draft' | 'testing' | 'live'
  }>>([])
  
  // 加载用户AI策略数据 (使用新的按类型获取API)
  const loadAiStrategies = async () => {
    try {
      const response = await strategyApi.getStrategiesByType('strategy')
      
      if (response && response.strategies) {
        // 转换为AI策略显示格式
        const aiStrategies = response.strategies.map(strategy => ({
          id: strategy.id.toString(),
          name: strategy.name,
          description: strategy.description || '用户自定义策略',
          parameters: strategy.parameters || {},
          code: strategy.code,
          status: strategy.is_active ? 'live' as const : 'draft' as const
        }))
        
        setAiStrategies(aiStrategies)
        console.log('✅ 加载用户AI策略数据:', aiStrategies.length, '个策略')
      }
    } catch (error) {
      console.error('❌ 加载AI策略数据失败:', error)
    }
  }
  
  // 删除策略函数
  const deleteStrategy = async (strategyId: string, strategyName: string) => {
    const confirmed = window.confirm(`确定要删除策略「${strategyName}」吗？此操作无法撤销。`)
    if (!confirmed) return
    
    try {
      await strategyApi.deleteStrategy(strategyId)
      
      // 更新本地状态
      setAiStrategies(prev => prev.filter(strategy => strategy.id !== strategyId))
      
      // 显示成功提示
      toast.success(`策略「${strategyName}」已成功删除`)
      
      // 重新加载数据
      loadAiStrategies()
      
    } catch (error: any) {
      console.error('❌ 删除策略失败:', error)
      
      // 检查是否是运行中策略错误
      if (error.response?.status === 409) {
        // 显示友好的错误弹窗
        alert(`⚠️ 无法删除策略「${strategyName}」\n\n当前策略有实盘正在运行中，请先停止所有实盘交易后再删除。\n\n如需管理实盘交易，请前往策略管理页面。`)
      } else if (error.response?.data?.detail) {
        toast.error(error.response.data.detail)
      } else {
        toast.error('删除策略失败，请重试')
      }
    }
  }

  // 删除指标函数
  const deleteIndicator = async (indicatorId: string, indicatorName: string) => {
    const confirmed = window.confirm(`确定要删除指标「${indicatorName}」吗？此操作无法撤销。`)
    if (!confirmed) return
    
    try {
      await strategyApi.deleteStrategy(indicatorId)
      
      // 更新本地状态
      setIndicators(prev => prev.filter(indicator => indicator.id !== indicatorId))
      
      // 显示成功提示
      toast.success(`指标「${indicatorName}」已成功删除`)
      
      // 重新加载数据
      loadIndicators()
      
    } catch (error) {
      console.error('❌ 删除指标失败:', error)
      toast.error('删除指标失败，请重试')
    }
  }

  // 功能区切换状态
  const [functionalAreaMode, setFunctionalAreaMode] = useState<'indicators' | 'strategies'>('indicators')

  // 加载策略数据 (同时加载指标和AI策略显示数据)
  const loadStrategies = async () => {
    if (!isPremium) return
    
    try {
      setLoadingStrategies(true)
      const response = await strategyApi.getStrategies()
      
      // 处理API响应格式
      if (response && typeof response === 'object') {
        const strategiesList = Array.isArray(response) ? response : response.strategies || []
        setStrategies(strategiesList)
        
        if (strategiesList.length > 0) {
          setSelectedStrategy(strategiesList[0])
        }
        
        toast.success(`加载了 ${strategiesList.length} 个实盘`)
      }
      
      // 同时加载AI显示区域的指标和策略数据
      await Promise.all([
        loadIndicators(),
        loadAiStrategies()
      ])
      
    } catch (error) {
      console.error('Failed to load strategies:', error)
      toast.error('加载实盘失败')
    } finally {
      setLoadingStrategies(false)
    }
  }

  // 时间周期转换为分钟数
  const timeframeToMinutes = (timeframe: string): number => {
    const match = timeframe.match(/^(\d+)([mhd])$/)
    if (!match) return 0
    
    const value = parseInt(match[1])
    const unit = match[2]
    
    switch (unit) {
      case 'm': return value
      case 'h': return value * 60
      case 'd': return value * 24 * 60
      default: return 0
    }
  }

  // 组合K线数据生成自定义周期
  const combineKlineData = (baseKlines: any[], baseTimeframe: string, targetTimeframe: string) => {
    const baseMinutes = timeframeToMinutes(baseTimeframe)
    const targetMinutes = timeframeToMinutes(targetTimeframe)
    
    if (targetMinutes <= baseMinutes || targetMinutes % baseMinutes !== 0) {
      throw new Error(`无法从${baseTimeframe}组合生成${targetTimeframe}`)
    }
    
    const combineRatio = targetMinutes / baseMinutes
    const combinedKlines = []
    
    for (let i = 0; i < baseKlines.length; i += combineRatio) {
      const batch = baseKlines.slice(i, i + combineRatio)
      if (batch.length < combineRatio) break
      
      // 组合OHLCV数据
      const timestamp = batch[0][0] // 使用第一根K线的时间戳
      const open = batch[0][1]      // 开盘价
      const high = Math.max(...batch.map(k => parseFloat(k[2]))) // 最高价
      const low = Math.min(...batch.map(k => parseFloat(k[3])))  // 最低价
      const close = batch[batch.length - 1][4]                   // 收盘价
      const volume = batch.reduce((sum, k) => sum + parseFloat(k[5]), 0) // 成交量累加
      
      combinedKlines.push([timestamp, open, high, low, close, volume])
    }
    
    return combinedKlines
  }

  // 获取真实K线数据 (支持自定义周期组合)
  const loadKlineData = async (symbol: string, exchange: string, timeframe: string) => {
    try {
      setLoadingKline(true)
      
      // 标准周期直接获取
      const standardTimeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
      
      if (standardTimeframes.includes(timeframe)) {
        // 直接获取标准周期数据
        const apiUrl = `/klines/${symbol}?exchange=${exchange}&timeframe=${timeframe}&limit=100`
        
        console.log('🔄 正在获取真实K线数据:', { symbol, exchange, timeframe, apiUrl })
        
        const response = await fetch(apiUrl, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json'
          }
        })
        
        if (response.ok) {
          const data = await response.json()
          console.log('✅ 成功获取K线数据:', data)
          
          if (data.klines && Array.isArray(data.klines)) {
            console.log('📊 设置K线数据:', data.klines.length, '条数据', data.klines[0])
            setKlineData(data.klines)
            updatePriceInfo(data.klines)
            toast.success(`✅ 获取到${data.klines.length}条真实K线数据`)
          } else {
            throw new Error('Invalid kline data format')
          }
        } else {
          throw new Error(`API error: ${response.status}`)
        }
      } else {
        // 自定义周期，需要组合生成
        console.log('🔧 自定义周期，尝试组合生成:', timeframe)
        
        // 选择合适的基础周期进行组合
        const targetMinutes = timeframeToMinutes(timeframe)
        let baseTimeframe = '1m'
        
        // 选择最大的可整除基础周期以减少数据量
        for (const tf of ['1d', '4h', '1h', '15m', '5m', '1m']) {
          const baseMinutes = timeframeToMinutes(tf)
          if (targetMinutes % baseMinutes === 0) {
            baseTimeframe = tf
            break
          }
        }
        
        // 获取基础周期数据（需要更多数据以便组合）
        const combineRatio = targetMinutes / timeframeToMinutes(baseTimeframe)
        const requiredKlines = Math.ceil(100 * combineRatio) // 确保有足够数据组合出100条目标周期K线
        
        const apiUrl = `/klines/${symbol}?exchange=${exchange}&timeframe=${baseTimeframe}&limit=${requiredKlines}`
        
        console.log(`🔄 获取基础周期${baseTimeframe}数据，用于组合${timeframe}:`, apiUrl)
        
        const response = await fetch(apiUrl, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json'
          }
        })
        
        if (response.ok) {
          const data = await response.json()
          
          if (data.klines && Array.isArray(data.klines)) {
            // 组合K线数据
            const combinedKlines = combineKlineData(data.klines, baseTimeframe, timeframe)
            console.log(`✅ 成功组合生成${timeframe}周期K线:`, combinedKlines.length, '条数据')
            
            setKlineData(combinedKlines)
            updatePriceInfo(combinedKlines)
            toast.success(`✅ 通过${baseTimeframe}周期组合生成${timeframe}周期K线数据，共${combinedKlines.length}条`)
          } else {
            throw new Error('Invalid base kline data format')
          }
        } else {
          throw new Error(`Base API error: ${response.status}`)
        }
      }
    } catch (error) {
      console.error('❌ K线数据获取/组合失败:', error)
      // 回退到模拟数据
      setKlineData(generateMockKlineData())
      toast.error(`K线数据失败: ${error instanceof Error ? error.message : '未知错误'}，使用模拟数据`)
    } finally {
      setLoadingKline(false)
    }
  }

  // 更新价格信息的辅助函数
  const updatePriceInfo = (klines: any[]) => {
    if (klines.length > 0) {
      const latestKline = klines[klines.length - 1]
      const previousKline = klines[klines.length - 2]
      
      if (latestKline && latestKline.length >= 6) {
        const currentPrice = parseFloat(latestKline[4]) // close price
        const previousPrice = previousKline && previousKline.length >= 6 ? parseFloat(previousKline[4]) : currentPrice
        const changePercent = previousPrice ? ((currentPrice - previousPrice) / previousPrice * 100) : 0
        
        setCurrentPrice(currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2 }))
        setPriceChangePercent(changePercent)
        setPriceChange(`${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%`)
      }
    }
  }


  // AI对话功能
  const sendAIMessage = async (message: string) => {
    if (!message.trim() || !isPremium) return
    
    setAiLoading(true)
    
    // 添加用户消息
    const userMessage = {
      id: Date.now().toString(),
      content: message.trim(),
      role: 'user' as const,
      timestamp: new Date()
    }
    setAiMessages(prev => [...prev, userMessage])
    setAiMessage('')
    
    try {
      // 构建上下文信息
      const context = {
        symbol: selectedMarket,
        exchange: selectedExchange,
        timeframe: selectedTimeframe,
        current_price: currentPrice,
        price_change: priceChange,
        ai_mode: aiMode,
        page: 'trading_chart'
      }
      
      // 使用AI API服务
      const data = await aiApi.sendChatMessage(
        message.trim(),
        sessionId,
        context
      )
      
      const aiResponse = {
        id: (Date.now() + 1).toString(),
        content: data.response || '抱歉，我现在无法回答这个问题。',
        role: 'assistant' as const,
        timestamp: new Date()
      }
      setAiMessages(prev => [...prev, aiResponse])
      
      // 更新会话ID
      if (data.session_id) {
        setSessionId(data.session_id)
      }
      
      toast.success('AI分析完成')
    } catch (error) {
      console.error('AI chat error:', error)
      
      // 添加错误消息
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        content: '抱歉，AI服务暂时不可用。请稍后再试或使用模拟分析功能。',
        role: 'assistant' as const,
        timestamp: new Date()
      }
      setAiMessages(prev => [...prev, errorMessage])
      
      toast.error('AI服务连接失败')
    } finally {
      setAiLoading(false)
    }
  }

  // 测试真实数据连接
  const testRealDataConnection = async () => {
    try {
      const apiUrl = `/klines/BTC/USDT?exchange=okx&timeframe=1h&limit=3`
      console.log('🧪 测试API连接:', apiUrl)
      
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      console.log('📡 API响应状态:', response.status, response.statusText)
      
      if (response.ok) {
        const data = await response.json()
        console.log('📊 真实数据:', data)
        toast.success(`✅ 真实数据连接成功，获取${data.count}条K线`)
        return data
      } else {
        const errorText = await response.text()
        console.error('❌ API错误响应:', errorText)
        toast.error(`API错误: ${response.status}`)
      }
    } catch (error) {
      console.error('❌ 网络连接错误:', error)
      toast.error(`连接错误: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  // 快速AI分析功能
  const triggerQuickAnalysis = async (analysisType: string) => {
    if (!isPremium) {
      toast.error('AI分析需要高级版本')
      return
    }
    
    const analysisMessages: { [key: string]: string } = {
      'rsi': `请分析${selectedMarket}的RSI指标，当前价格${currentPrice}，判断是否存在超买或超卖信号`,
      'macd': `分析${selectedMarket}的MACD指标走势，提供买卖信号建议`,
      'boll': `分析${selectedMarket}的布林带指标，当前价格相对于布林带的位置和交易机会`,
      'support_resistance': `识别${selectedMarket}的关键支撑和阻力位，当前价格${currentPrice}`,
      'trend': `分析${selectedMarket}在${selectedTimeframe}时间框架下的趋势方向和强度`,
      'signal': `基于多个技术指标，为${selectedMarket}提供综合交易信号分析`
    }
    
    const message = analysisMessages[analysisType] || `请分析${selectedMarket}的技术面情况`
    await sendAIMessage(message)
  }

  // 初始化交易数据
  useEffect(() => {
    const initializeTradingData = async () => {
      console.log('🚀 初始化交易数据:', { isPremium, user: !!user })
      
      // 先加载K线数据（无需会员权限）
      loadKlineData(selectedMarket, 'okx', selectedTimeframe)
      
      if (isPremium && user) {
        try {
          await Promise.allSettled([
            loadSupportedExchanges(),
            loadStrategies() // 添加策略数据加载
          ])
        } catch (error) {
          console.error('Failed to initialize trading data:', error)
          setPageError('交易数据加载失败，请刷新页面重试')
        }
      }
    }

    // 添加延迟避免快速连续调用
    const timeoutId = setTimeout(initializeTradingData, 100)
    
    return () => clearTimeout(timeoutId)
  }, [isPremium, selectedExchange, user])


  // 初始化和更新ECharts图表
  useEffect(() => {
    if (!chartRef.current) {
      console.log('⚠️ 图表容器未找到')
      return
    }
    
    if (!chartInstance.current) {
      console.log('🎨 初始化ECharts图表')
      chartInstance.current = echarts.init(chartRef.current)
    }
    
    // 使用真实或模拟K线数据
    const currentKlineData = klineData.length > 0 ? klineData : generateMockKlineData()
    console.log('📈 更新图表数据:', currentKlineData.length, '条K线')
    
    const option: echarts.EChartsOption = {
      backgroundColor: '#ffffff',
      animation: true,
      grid: {
        top: '10%',
        left: '8%',
        right: '8%',
        bottom: '15%'
      },
      xAxis: {
        type: 'category',
        data: currentKlineData.map((item: any) => {
          if (Array.isArray(item) && item.length >= 6) {
            // API格式 [timestamp, open, high, low, close, volume] - timestamp是毫秒
            const date = new Date(item[0])
            return `${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
          } else if (item.timestamp) {
            // API返回格式
            const date = new Date(item.timestamp)
            return `${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
          }
          return '00:00'
        }),
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#8392A5' } },
        axisLabel: { color: '#8392A5' }
      },
      yAxis: {
        scale: true,
        axisLine: { lineStyle: { color: '#8392A5' } },
        axisLabel: { color: '#8392A5' },
        splitLine: {
          show: true,
          lineStyle: { color: '#f0f0f0' }
        }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(245, 245, 245, 0.9)',
        borderWidth: 1,
        borderColor: '#ccc',
        textStyle: { color: '#000' },
        formatter: function(params: any) {
          const dataIndex = params[0].dataIndex
          const kline = currentKlineData[dataIndex]
          
          let open, high, low, close, volume, time
          
          if (Array.isArray(kline)) {
            [time, open, high, low, close, volume] = kline
          } else {
            time = new Date(kline.timestamp).toLocaleString()
            open = kline.open
            high = kline.high
            low = kline.low
            close = kline.close
            volume = kline.volume
          }
          
          return `
            <div style="padding: 10px;">
              <div style="font-weight: bold; margin-bottom: 5px;">${selectedMarket} - ${time}</div>
              <div>开盘: ${open}</div>
              <div>收盘: ${close}</div>
              <div>最低: ${low}</div>
              <div>最高: ${high}</div>
              <div>成交量: ${volume}</div>
            </div>
          `
        }
      },
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: currentKlineData.map((item: any) => {
            if (Array.isArray(item) && item.length >= 6) {
              // API格式 [timestamp, open, high, low, close, volume] -> [open, close, low, high]
              return [item[1], item[4], item[3], item[2]]
            } else if (item.open !== undefined) {
              // API返回格式
              return [item.open, item.close, item.low, item.high]
            }
            return [0, 0, 0, 0]
          }),
          itemStyle: {
            color: '#00da3c',
            color0: '#ec0000',
            borderColor: '#00da3c',
            borderColor0: '#ec0000'
          }
        }
      ]
    }
    
    chartInstance.current.setOption(option)
    console.log('🎯 图表配置已更新，数据点数:', currentKlineData.length)
    
    // 处理窗口大小变化
    const handleResize = () => {
      chartInstance.current?.resize()
    }
    
    window.addEventListener('resize', handleResize)
    
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [selectedMarket, selectedTimeframe, klineData])
  
  // 当交易对或时间周期变化时，加载K线数据
  useEffect(() => {
    console.log('🔄 useEffect触发:', { selectedMarket, selectedExchange, selectedTimeframe })
    if (selectedExchange) {
      loadKlineData(selectedMarket, selectedExchange, selectedTimeframe)
    } else {
      console.log('⚠️ selectedExchange为空，使用默认okx')
      loadKlineData(selectedMarket, 'okx', selectedTimeframe)
    }
  }, [selectedMarket, selectedExchange, selectedTimeframe])
  
  // 生成模拟K线数据
  const generateMockKlineData = () => {
    const data = []
    let basePrice = 43250
    const now = new Date()
    
    for (let i = 100; i >= 0; i--) {
      const date = new Date(now.getTime() - i * 15 * 60 * 1000)
      const timeStr = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
      
      const open = basePrice + (Math.random() - 0.5) * 100
      const close = open + (Math.random() - 0.5) * 200
      const high = Math.max(open, close) + Math.random() * 50
      const low = Math.min(open, close) - Math.random() * 50
      const volume = Math.random() * 100 + 50
      
      data.push([timeStr, open.toFixed(2), close.toFixed(2), low.toFixed(2), high.toFixed(2), volume.toFixed(2)])
      basePrice = close
    }
    
    return data
  }
  
  // 处理交易所切换
  const handleExchangeSwitch = (exchange: string) => {
    switchExchange(exchange)
  }

  // 处理交易对变化
  const handleSymbolChange = (symbol: string) => {
    // 取消旧的订阅
    unsubscribeFromSymbol(selectedMarket)
    
    // 更新选择的交易对
    setSelectedMarket(symbol)
    
    // 订阅新的交易对
    if (realTimeConnected) {
      subscribeToSymbol(symbol)
    }
  }

  // 错误状态显示
  if (pageError) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">{pageError}</h3>
          <p className="text-gray-500 mb-4">交易服务可能暂时不可用</p>
          <button 
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* 简化的头部栏 */}
      <div className="px-6 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between">
          {/* 左侧：交易所和交易对选择 */}
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-3">
              <span className="text-sm font-medium text-gray-700">交易所:</span>
              <select
                value={selectedExchange || 'okx'}
                onChange={(e) => handleExchangeSwitch(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white text-sm"
              >
                {supportedExchanges.length > 0 ? (
                  supportedExchanges.map(exchange => (
                    <option key={exchange} value={exchange}>
                      {exchange.toUpperCase()}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="okx">OKX</option>
                    <option value="binance">Binance</option>
                    <option value="huobi">Huobi</option>
                    <option value="bybit">Bybit</option>
                  </>
                )}
              </select>
            </div>
            
            <div className="flex items-center space-x-3">
              <span className="text-sm font-medium text-gray-700">交易对:</span>
              <select 
                value={selectedMarket}
                onChange={(e) => handleSymbolChange(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white text-sm font-medium"
              >
                <option value="BTC/USDT">BTC/USDT</option>
                <option value="ETH/USDT">ETH/USDT</option>
                <option value="BNB/USDT">BNB/USDT</option>
                <option value="SOL/USDT">SOL/USDT</option>
                <option value="ADA/USDT">ADA/USDT</option>
                <option value="DOGE/USDT">DOGE/USDT</option>
                <option value="MATIC/USDT">MATIC/USDT</option>
                <option value="DOT/USDT">DOT/USDT</option>
              </select>
            </div>
          </div>
          
          {/* 中间：当前价格 */}
          <div className="flex items-center space-x-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-gray-900">{currentPrice}</div>
              <div className={`text-sm font-semibold ${
                priceChangePercent >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {priceChange}
                {loadingKline && <span className="text-xs text-blue-600 ml-2">更新中...</span>}
              </div>
            </div>
          </div>
          
          {/* 右侧：时间周期选择 */}
          <div className="flex items-center space-x-2">
            {['1m', '5m', '15m', '1h', '4h', '1d', ...customTimeframes].map((tf) => (
              <button 
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  selectedTimeframe === tf
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-md transform scale-105' 
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:scale-105'
                }`}
              >
                {tf === '1m' ? '1分钟' : tf === '5m' ? '5分钟' : tf === '15m' ? '15分钟' : 
                 tf === '1h' ? '1小时' : tf === '4h' ? '4小时' : tf === '1d' ? '1天' : tf}
              </button>
            ))}
            <button
              onClick={() => setShowCustomTimeframeModal(true)}
              className="px-3 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 transition-all duration-200 hover:scale-105 shadow-md"
              title="添加自定义周期"
            >
              + 自定义
            </button>
          </div>
        </div>
      </div>

        {/* 主要交易界面 */}
        <div className="p-6">
          <div className="grid grid-cols-12 gap-6 mb-6">
            {/* 左侧：K线图表 */}
            <div className="col-span-9">
              <div className="h-[600px] bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden backdrop-blur-sm">
                {/* 图表工具栏 */}
                <div className="p-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <h3 className="font-semibold text-gray-900">{selectedMarket} K线图</h3>
                    <div className="flex items-center space-x-2 text-sm text-gray-600">
                      <span>时间周期:</span>
                      <span className="font-medium text-brand-600">{selectedTimeframe}</span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button 
                      className="p-1 rounded hover:bg-gray-200 transition-colors"
                      title="全屏"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                      </svg>
                    </button>
                    <button 
                      className="p-1 rounded hover:bg-gray-200 transition-colors"
                      title="设置"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37-2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    </button>
                  </div>
                </div>
                
                {/* 绘图工具栏 - 基于原型设计 */}
                <div className="px-3 py-2 bg-white border-b border-gray-100 flex items-center justify-between">
                  <div className="flex items-center space-x-1">
                    <div className="flex items-center space-x-1 mr-4">
                      <span className="text-xs text-gray-500">绘图工具：</span>
                      <button
                        onClick={() => setActiveDrawingTool(activeDrawingTool === 'cursor' ? null : 'cursor')}
                        className={`p-1 rounded text-xs hover:bg-gray-100 ${activeDrawingTool === 'cursor' ? 'bg-blue-100 text-blue-600' : 'text-gray-600'}`}
                        title="光标"
                      >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M6.672 1.911a1 1 0 10-1.932.518l.259.966a1 1 0 001.932-.518l-.26-.966zM2.429 4.74a1 1 0 10-.517 1.932l.966.259a1 1 0 00.517-1.932l-.966-.26zm8.814-.569a1 1 0 00-1.415-1.414l-.707.707a1 1 0 101.415 1.415l.707-.708zm-7.071 7.072l.707-.707A1 1 0 003.465 9.12l-.708.707a1 1 0 001.415 1.415zm3.2-5.171a1 1 0 00-1.3 1.3l4 10a1 1 0 001.823.075l1.38-2.759 3.018 3.02a1 1 0 001.414-1.415l-3.019-3.02 2.76-1.379a1 1 0 00-.076-1.822l-10-4z" clipRule="evenodd" />
                        </svg>
                      </button>
                      
                      <button
                        onClick={() => setActiveDrawingTool(activeDrawingTool === 'line' ? null : 'line')}
                        className={`p-1 rounded text-xs hover:bg-gray-100 ${activeDrawingTool === 'line' ? 'bg-blue-100 text-blue-600' : 'text-gray-600'}`}
                        title="直线"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 20l16-16" />
                        </svg>
                      </button>
                      
                      <button
                        onClick={() => setActiveDrawingTool(activeDrawingTool === 'rectangle' ? null : 'rectangle')}
                        className={`p-1 rounded text-xs hover:bg-gray-100 ${activeDrawingTool === 'rectangle' ? 'bg-blue-100 text-blue-600' : 'text-gray-600'}`}
                        title="矩形"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16v12H4z" />
                        </svg>
                      </button>
                      
                      <button
                        onClick={() => setActiveDrawingTool(activeDrawingTool === 'circle' ? null : 'circle')}
                        className={`p-1 rounded text-xs hover:bg-gray-100 ${activeDrawingTool === 'circle' ? 'bg-blue-100 text-blue-600' : 'text-gray-600'}`}
                        title="圆形"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <circle cx="12" cy="12" r="8" />
                        </svg>
                      </button>
                      
                      <button
                        onClick={() => setActiveDrawingTool(activeDrawingTool === 'fibonacci' ? null : 'fibonacci')}
                        className={`p-1 rounded text-xs hover:bg-gray-100 ${activeDrawingTool === 'fibonacci' ? 'bg-blue-100 text-blue-600' : 'text-gray-600'}`}
                        title="斐波那契回调"
                      >
                        <span className="text-xs font-mono">Fib</span>
                      </button>
                      
                      <button
                        onClick={() => setActiveDrawingTool(activeDrawingTool === 'text' ? null : 'text')}
                        className={`p-1 rounded text-xs hover:bg-gray-100 ${activeDrawingTool === 'text' ? 'bg-blue-100 text-blue-600' : 'text-gray-600'}`}
                        title="文本"
                      >
                        <span className="text-xs font-bold">T</span>
                      </button>
                    </div>
                    
                    <div className="flex items-center space-x-1 text-xs">
                      <span className="text-gray-500">指标：</span>
                      <button className="px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 text-gray-600">MA</button>
                      <button className="px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 text-gray-600">MACD</button>
                      <button className="px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 text-gray-600">RSI</button>
                      <button className="px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 text-gray-600">BOLL</button>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setActiveDrawingTool(null)}
                      className="px-2 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 text-gray-600"
                      title="清除绘图"
                    >
                      清除
                    </button>
                    <button
                      className="px-2 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 text-gray-600"
                      title="撤销"
                    >
                      撤销
                    </button>
                  </div>
                </div>
                
                {/* K线图表容器 */}
                <div ref={chartRef} className="w-full h-[520px]" />
              </div>
            </div>

            {/* 右侧：AI对话窗口 */}
            <div className="col-span-3">
              <div className="bg-white border border-gray-200 rounded-xl shadow-lg h-[600px] flex flex-col backdrop-blur-sm">
                <div className="p-4 border-b border-gray-100">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-900">🤖 AI助手</h3>
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => setAiMode('indicator')}
                        className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-all duration-200 ${
                          aiMode === 'indicator'
                            ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-sm'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        📊 AI指标
                      </button>
                      <button
                        onClick={() => setAiMode('strategy')}
                        className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-all duration-200 ${
                          aiMode === 'strategy'
                            ? 'bg-gradient-to-r from-green-500 to-green-600 text-white shadow-sm'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        ⚡ AI策略
                      </button>
                    </div>
                  </div>
                </div>
                
                <div className="p-4 flex flex-col flex-1">
                  {/* AI对话区域 */}
                  <div className="flex-1 bg-gray-50 rounded-lg p-3 mb-3 overflow-y-auto">
                    <div className="space-y-3">
                      {aiMessages.map((msg) => (
                        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : ''}`}>
                          {msg.role === 'assistant' && (
                            <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
                              <span className="text-blue-600 text-sm">🤖</span>
                            </div>
                          )}
                          <div className={`rounded-lg px-3 py-2 max-w-xs ${
                            msg.role === 'assistant' 
                              ? 'bg-white shadow-sm border' 
                              : 'bg-blue-600 text-white'
                          }`}>
                            <p className={`text-sm ${msg.role === 'assistant' ? 'text-gray-800' : 'text-white'}`}>
                              {msg.content.split('\n').map((line, i) => (
                                <span key={i}>
                                  {line}
                                  {i < msg.content.split('\n').length - 1 && <br />}
                                </span>
                              ))}
                            </p>
                            <div className={`text-xs mt-1 ${
                              msg.role === 'assistant' ? 'text-gray-500' : 'text-blue-200'
                            }`}>
                              {msg.timestamp.toLocaleTimeString()}
                            </div>
                          </div>
                        </div>
                      ))}
                      
                      {/* 加载状态 */}
                      {aiLoading && (
                        <div className="flex">
                          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3 flex-shrink-0">
                            <span className="text-blue-600 text-sm">🤖</span>
                          </div>
                          <div className="bg-white rounded-lg px-3 py-2 shadow-sm border">
                            <div className="flex items-center space-x-2">
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                              <span className="text-sm text-gray-600">AI正在分析中...</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* 快速分析按钮 */}
                  {isPremium && (
                    <div className="mb-3">
                      <div className="text-xs text-gray-500 mb-2">快速分析：</div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => triggerQuickAnalysis('rsi')}
                          disabled={aiLoading}
                          className="px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors disabled:opacity-50 font-medium"
                        >
                          📊 RSI指标
                        </button>
                        <button
                          onClick={() => triggerQuickAnalysis('macd')}
                          disabled={aiLoading}
                          className="px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-colors disabled:opacity-50 font-medium"
                        >
                          📈 MACD指标
                        </button>
                        <button
                          onClick={() => triggerQuickAnalysis('boll')}
                          disabled={aiLoading}
                          className="px-3 py-1.5 text-xs bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-colors disabled:opacity-50 font-medium"
                        >
                          🎯 布林带
                        </button>
                        <button
                          onClick={() => triggerQuickAnalysis('support_resistance')}
                          disabled={aiLoading}
                          className="px-3 py-1.5 text-xs bg-yellow-50 text-yellow-700 rounded-lg hover:bg-yellow-100 transition-colors disabled:opacity-50 font-medium"
                        >
                          🔹 支撑阻力
                        </button>
                        <button
                          onClick={() => triggerQuickAnalysis('trend')}
                          disabled={aiLoading}
                          className="px-3 py-1.5 text-xs bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 transition-colors disabled:opacity-50 font-medium"
                        >
                          📊 趋势分析
                        </button>
                        <button
                          onClick={() => triggerQuickAnalysis('signal')}
                          disabled={aiLoading}
                          className="px-3 py-1.5 text-xs bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50 font-medium"
                        >
                          🚀 综合信号
                        </button>
                      </div>
                    </div>
                  )}
                  
                  {/* 输入区域 */}
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      value={aiMessage}
                      onChange={(e) => setAiMessage(e.target.value)}
                      placeholder={
                        !isPremium ? "升级到高级版以使用AI分析" :
                        aiMode === 'indicator' ? "请描述需要生成的技术指标..." : "请描述需要生成的交易策略..."
                      }
                      disabled={!isPremium || aiLoading}
                      className="flex-1 border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 text-sm focus:border-blue-600 focus:outline-none focus:bg-white disabled:opacity-50"
                      onKeyPress={(e) => {
                        if (e.key === 'Enter' && !aiLoading) {
                          sendAIMessage(aiMessage)
                        }
                      }}
                    />
                    <button
                      onClick={() => sendAIMessage(aiMessage)}
                      disabled={!isPremium || aiLoading || !aiMessage.trim()}
                      className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {aiLoading ? '生成中...' : '生成'}
                    </button>
                  </div>
                </div>
              </div>

            </div>
          </div>
          
          {/* AI指标和策略管理区域 - K线图下方 */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-lg mb-6 backdrop-blur-sm">
            <div className="p-4 border-b border-gray-100">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  {functionalAreaMode === 'indicators' ? '📊 AI生成的技术指标' : '⚡ AI生成的交易策略'}
                </h3>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setFunctionalAreaMode('indicators')}
                    className={`px-4 py-2 text-sm rounded-lg font-medium transition-all duration-300 ${
                      functionalAreaMode === 'indicators'
                        ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg transform scale-105'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:scale-105'
                    }`}
                  >
                    📊 技术指标
                  </button>
                  <button
                    onClick={() => setFunctionalAreaMode('strategies')}
                    className={`px-4 py-2 text-sm rounded-lg font-medium transition-all duration-300 ${
                      functionalAreaMode === 'strategies'
                        ? 'bg-gradient-to-r from-green-500 to-green-600 text-white shadow-lg transform scale-105'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:scale-105'
                    }`}
                  >
                    ⚡ 交易策略
                  </button>
                </div>
              </div>
            </div>
            
            <div className="p-6">
              {functionalAreaMode === 'indicators' ? (
                /* 指标管理区域 */
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {indicators.length > 0 ? (
                    indicators.map((indicator) => (
                      <div key={indicator.id} className="group bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl p-4 hover:shadow-md transition-all duration-200">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="font-semibold text-gray-900 mb-1">{indicator.name}</div>
                            <div className="text-sm text-blue-600 font-medium">{indicator.type}</div>
                          </div>
                          <div className={`w-3 h-3 rounded-full ${
                            indicator.visible ? 'bg-green-400' : 'bg-gray-300'
                          }`}></div>
                        </div>
                        
                        <div className="text-xs text-gray-600 mb-3">
                          参数: {Object.entries(indicator.parameters).map(([key, value]) => 
                            `${key}=${value}`
                          ).join(', ')}
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => {
                              const updatedIndicators = indicators.map(ind => 
                                ind.id === indicator.id ? {...ind, visible: !ind.visible} : ind
                              )
                              setIndicators(updatedIndicators)
                            }}
                            className={`flex-1 py-2 px-3 text-sm rounded-lg font-medium transition-all duration-200 ${
                              indicator.visible 
                                ? 'bg-green-500 text-white hover:bg-green-600 shadow-sm'
                                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                            }`}
                          >
                            {indicator.visible ? '✅ 已显示' : '👁️ 显示'}
                          </button>
                          <button
                            onClick={() => toast.info('参数修改功能开发中...')}
                            className="py-2 px-3 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
                          >
                            ⚙️
                          </button>
                          <button
                            onClick={() => deleteIndicator(indicator.id, indicator.name)}
                            className="py-2 px-3 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-full text-center py-12 text-gray-400">
                      <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center">
                        <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                      </div>
                      <p className="text-lg font-medium mb-2">暂无AI指标</p>
                      <p className="text-gray-500">使用右侧AI助手生成技术指标，指标将在此处显示</p>
                    </div>
                  )}
                </div>
              ) : (
                /* 策略管理区域 */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {aiStrategies.length > 0 ? (
                    aiStrategies.map((strategy) => (
                      <div key={strategy.id} className="group bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-xl p-4 hover:shadow-md transition-all duration-200">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="font-semibold text-gray-900 mb-1">{strategy.name}</div>
                            <div className="text-sm text-gray-600">{strategy.description}</div>
                          </div>
                          <div className={`text-xs px-2 py-1 rounded-full font-medium ${
                            strategy.status === 'live' ? 'bg-green-200 text-green-800' :
                            strategy.status === 'testing' ? 'bg-yellow-200 text-yellow-800' :
                            'bg-gray-200 text-gray-700'
                          }`}>
                            {strategy.status === 'live' ? '🟢 实盘中' : 
                             strategy.status === 'testing' ? '🟡 测试中' : '⚪ 草稿'}
                          </div>
                        </div>
                        
                        <div className="text-xs text-gray-600 mb-4">
                          参数: {Object.entries(strategy.parameters).map(([key, value]) => 
                            `${key}=${value}`
                          ).join(', ')}
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          <button
                            className="flex-1 py-2 px-3 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
                            onClick={() => toast.info('参数修改功能开发中...')}
                          >
                            ⚙️ 参数
                          </button>
                          <button
                            className="flex-1 py-2 px-3 text-sm bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors font-medium"
                            onClick={() => toast.info('回测功能开发中...')}
                          >
                            📈 回测
                          </button>
                          <button
                            className="flex-1 py-2 px-3 text-sm bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors font-medium"
                            onClick={() => toast.info('创建实盘功能开发中...')}
                          >
                            🚀 实盘
                          </button>
                          <button
                            onClick={() => deleteStrategy(strategy.id, strategy.name)}
                            className="py-2 px-3 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-full text-center py-12 text-gray-400">
                      <div className="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
                        <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </div>
                      <p className="text-lg font-medium mb-2">暂无AI策略</p>
                      <p className="text-gray-500">使用右侧AI助手生成交易策略，策略将在此处显示</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* 自定义周期模态框 */}
        {showCustomTimeframeModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-96 max-w-md">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">添加自定义K线周期</h3>
                <button
                  onClick={() => setShowCustomTimeframeModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    周期格式 (例如: 2h, 3m, 12h, 2d)
                  </label>
                  <input
                    type="text"
                    value={newTimeframe}
                    onChange={(e) => setNewTimeframe(e.target.value)}
                    placeholder="如: 2h, 30m, 6h, 2d"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    支持格式: m(分钟), h(小时), d(天)。如果交易所不支持，将通过较小周期组合生成。
                  </p>
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={() => {
                      if (newTimeframe.trim() && !customTimeframes.includes(newTimeframe.trim())) {
                        setCustomTimeframes(prev => [...prev, newTimeframe.trim()])
                        setNewTimeframe('')
                        setShowCustomTimeframeModal(false)
                        toast.success(`已添加自定义周期: ${newTimeframe.trim()}`)
                      } else if (customTimeframes.includes(newTimeframe.trim())) {
                        toast.error('该周期已存在')
                      } else {
                        toast.error('请输入有效的周期格式')
                      }
                    }}
                    className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
                  >
                    添加周期
                  </button>
                  <button
                    onClick={() => {
                      setNewTimeframe('')
                      setShowCustomTimeframeModal(false)
                    }}
                    className="flex-1 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors font-medium"
                  >
                    取消
                  </button>
                </div>
                
                {/* 已添加的自定义周期 */}
                {customTimeframes.length > 0 && (
                  <div className="pt-4 border-t border-gray-200">
                    <h4 className="text-sm font-medium text-gray-700 mb-2">已添加的自定义周期:</h4>
                    <div className="flex flex-wrap gap-2">
                      {customTimeframes.map((tf) => (
                        <div key={tf} className="flex items-center bg-gray-100 rounded px-2 py-1">
                          <span className="text-sm">{tf}</span>
                          <button
                            onClick={() => {
                              setCustomTimeframes(prev => prev.filter(t => t !== tf))
                              if (selectedTimeframe === tf) {
                                setSelectedTimeframe('15m') // 回退到默认周期
                              }
                              toast.success(`已移除周期: ${tf}`)
                            }}
                            className="ml-1 text-gray-400 hover:text-red-500"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
    </div>
  )
}

export default TradingPage