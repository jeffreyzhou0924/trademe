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
import { useTradingPageStore } from '../store/tradingPageStore'
import { tradingDataManager } from '../services/trading/dataManager'
import SymbolSearchBar from '../components/trading/SymbolSearchBar'
import MarketInfoPanel from '../components/trading/MarketInfoPanel'
import SuperChart from '../components/trading/SuperChart/SuperChart'
import MarketPanel from '../components/trading/MarketPanel/MarketPanel'
import toast from 'react-hot-toast'

const TradingPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()
  
  const { 
    selectedExchange,
    switchExchange
  } = useTradingAccounts()
  
  const {
    selectedSymbol,
    selectedTimeframe,
    chartConfig,
    setSelectedSymbol,
    setSelectedTimeframe,
    updateChartConfig,
    leftPanelCollapsed,
    rightPanelCollapsed,
    toggleLeftPanel,
    toggleRightPanel,
    updateKlineData,
    updateCurrentPrice,
    updateStrategyLibrary,
    updateAnalysisLibrary
  } = useTradingPageStore()
  
  // 数据连接状态
  const [dataConnectionStatus, setDataConnectionStatus] = useState({
    websocket: false,
    api: false
  })
  const [currentPrice, setCurrentPrice] = useState('43,250.00')
  const [priceChange, setPriceChange] = useState('+2.34%')
  const [priceChangePercent, setPriceChangePercent] = useState(2.34)
  const dataManagerInitialized = useRef(false)

  // 初始化数据管理器
  useEffect(() => {
    if (!dataManagerInitialized.current) {
      console.log('🚀 初始化Trading页面数据管理器')
      
      // 设置数据更新回调
      tradingDataManager.initialize({
        onKlineUpdate: (symbol, timeframe, data) => {
          console.log(`📊 K线数据更新: ${symbol} ${timeframe} - ${data.length}条`)
          updateKlineData(symbol, timeframe, data)
        },
        
        onTickerUpdate: (ticker) => {
          console.log(`💰 价格更新: ${ticker.symbol} = $${ticker.price}`)
          setCurrentPrice(ticker.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
          const changePercent = ticker.change_percent || 0
          setPriceChangePercent(changePercent)
          setPriceChange(`${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%`)
          updateCurrentPrice(ticker.price.toString())
          
          // 同时更新自选列表中的实时价格
          const watchListUpdate = {
            symbol: ticker.symbol,
            exchange: selectedExchange || 'OKX',
            price: ticker.price,
            change24h: ticker.change || 0,
            changePercent24h: ticker.change_percent || 0,
            volume24h: ticker.volume_24h || 0,
            high24h: ticker.high_24h || ticker.price,
            low24h: ticker.low_24h || ticker.price,
            lastUpdated: ticker.timestamp || Date.now()
          }
          
          // 更新自选列表中对应品种的价格
          const { watchList, updateWatchListPrices } = useTradingPageStore.getState()
          const existingItem = watchList.find(item => 
            item.symbol === ticker.symbol && item.exchange === (selectedExchange || 'OKX')
          )
          
          if (existingItem) {
            updateWatchListPrices([watchListUpdate])
          }
        },
        
        onStrategyUpdate: (strategies) => {
          console.log(`🎯 策略库更新: ${strategies.length}个策略`)
          updateStrategyLibrary(strategies)
        },
        
        onAnalysisUpdate: (analyses) => {
          console.log(`📊 分析库更新: ${analyses.length}个分析`)
          updateAnalysisLibrary(analyses)
        },
        
        onConnectionUpdate: (connected) => {
          console.log(`🔌 连接状态更新: ${connected ? '已连接' : '已断开'}`)
          setDataConnectionStatus(prev => ({
            ...prev,
            websocket: connected,
            api: true // API连接状态通过成功回调来判断
          }))
        },
        
        onError: (error) => {
          console.error('❌ 数据管理器错误:', error)
          toast.error(`数据加载错误: ${error}`)
          setPageError(`数据加载失败: ${error}`)
        }
      })
      
      dataManagerInitialized.current = true
    }
  }, [updateKlineData, updateCurrentPrice, updateStrategyLibrary, updateAnalysisLibrary])

  // 处理交易所切换
  const handleExchangeSwitch = (exchange: string) => {
    switchExchange(exchange)
    toast.success(`已切换到 ${exchange.toUpperCase()}`)
  }

  // 处理交易对变化
  const handleSymbolChange = async (symbol: string) => {
    setSelectedSymbol(symbol)
    toast.success(`已切换到 ${symbol}`)
    
    // 通知数据管理器切换交易对
    try {
      await tradingDataManager.switchSymbol(symbol, selectedTimeframe)
    } catch (error) {
      console.error('❌ 切换交易对失败:', error)
      toast.error(`切换交易对失败: ${error}`)
    }
  }

  // 处理时间周期变化
  const handleTimeframeChange = async (timeframe: string) => {
    setSelectedTimeframe(timeframe)
    toast.success(`已切换到 ${timeframe}`)
    
    // 通知数据管理器切换时间周期
    try {
      await tradingDataManager.switchTimeframe(timeframe)
    } catch (error) {
      console.error('❌ 切换时间周期失败:', error)
      toast.error(`切换时间周期失败: ${error}`)
    }
  }

  // 清理资源
  useEffect(() => {
    return () => {
      if (dataManagerInitialized.current) {
        console.log('🧹 清理Trading页面数据管理器资源')
        tradingDataManager.destroy()
        dataManagerInitialized.current = false
      }
    }
  }, [])

  // 页面错误状态处理
  const [pageError, setPageError] = useState<string | null>(null)

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
    <div className="fixed inset-0 w-screen h-screen bg-gray-900 flex flex-col overflow-hidden">
      {/* 专业交易顶部栏 */}
      <div className="h-14 bg-gradient-to-r from-gray-800 via-gray-800 to-gray-750 border-b border-gray-700 flex items-center justify-between px-6 flex-shrink-0 shadow-lg">
        {/* 左侧：Logo和返回导航 */}
        <div className="flex items-center space-x-6">
          {/* Logo和返回按钮 */}
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/overview')}
              className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-gray-700/50 hover:bg-gray-600 transition-all duration-200 group"
              title="返回主页"
            >
              <svg className="w-4 h-4 text-gray-300 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              <span className="text-sm font-medium text-gray-300 group-hover:text-white">Trademe</span>
            </button>
            
            {/* 页面标题 */}
            <div className="flex items-center space-x-2">
              <div className="w-px h-6 bg-gray-600"></div>
              <h1 className="text-lg font-bold text-white flex items-center space-x-2">
                <svg className="w-5 h-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>专业交易</span>
              </h1>
            </div>
          </div>
          
          {/* 功能标签 */}
          <div className="flex items-center space-x-1">
            <button className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-md transition-all duration-200">
              策略库
            </button>
            <button className="px-4 py-2 text-sm font-medium rounded-lg text-gray-300 hover:text-white hover:bg-gray-700 transition-all duration-200">
              指标库
            </button>
            <button className="px-4 py-2 text-sm font-medium rounded-lg text-gray-300 hover:text-white hover:bg-gray-700 transition-all duration-200">
              交易系统
            </button>
          </div>
        </div>
        
        {/* 中央：品种信息卡片 */}
        <div className="flex items-center space-x-6">
          <div className="bg-gray-700/50 backdrop-blur-sm rounded-xl px-6 py-3 border border-gray-600/50 shadow-lg">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-6 h-6 bg-orange-500 rounded-full flex items-center justify-center">
                  <span className="text-xs font-bold text-white">B</span>
                </div>
                <div>
                  <span className="text-lg font-bold text-white">{selectedSymbol}</span>
                  <span className="text-xs text-gray-400 ml-2">{selectedExchange || 'OKX'}</span>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <div className="text-right">
                  <div className="text-xl font-bold text-white">${currentPrice}</div>
                  <div className={`text-sm font-medium ${
                    priceChangePercent >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {priceChange}
                  </div>
                </div>
                
                {/* 24h统计 */}
                <div className="text-xs text-gray-400 space-y-1">
                  <div>成交量: 1.2B</div>
                  <div>振幅: 3.2%</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* 右侧：用户信息和连接状态 */}
        <div className="flex items-center space-x-4">
          {/* 连接状态 */}
          <div className="flex items-center space-x-3 bg-gray-700/50 rounded-lg px-3 py-2">
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${
                dataConnectionStatus.websocket ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="text-xs text-gray-300">WebSocket</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${
                dataConnectionStatus.api ? 'bg-green-500' : 'bg-red-500'
              }`} />
              <span className="text-xs text-gray-300">API</span>
            </div>
          </div>
          
          {/* 用户信息 */}
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-xs font-bold text-white">{user?.email?.[0]?.toUpperCase() || 'U'}</span>
            </div>
            <div className="text-sm">
              <div className="text-white font-medium">{user?.email?.split('@')[0] || 'User'}</div>
              <div className="text-xs text-gray-400">{isPremium ? 'Premium' : 'Basic'}</div>
            </div>
          </div>
        </div>
      </div>
      
      {/* TradingView风格主要交易区域 */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* 中央图表主区域 */}
        <div className="flex-1 flex flex-col">
          {/* 图表容器 */}
          <div className="flex-1 bg-gray-900">
            <SuperChart className="w-full h-full" />
          </div>
          
          {/* 专业底部控制栏 - 重新设计为水平滚动布局 */}
          <div className="h-16 bg-gradient-to-r from-gray-800 to-gray-750 border-t border-gray-700 flex items-center px-4 flex-shrink-0 shadow-lg overflow-x-auto">
            <div className="flex items-center space-x-6 min-w-max">
              {/* 时间周期选择 */}
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-gray-400 mr-2">时间周期:</span>
                <div className="flex items-center space-x-1 bg-gray-700/50 rounded-lg p-1">
                  {['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w'].map(tf => (
                    <button
                      key={tf}
                      onClick={() => handleTimeframeChange(tf)}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-all duration-200 ${
                        selectedTimeframe === tf
                          ? 'bg-blue-600 text-white shadow-md'
                          : 'text-gray-300 hover:text-white hover:bg-gray-600'
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* 分隔线 */}
              <div className="w-px h-8 bg-gray-600"></div>
              
              {/* 图表样式选择 */}
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-gray-400 mr-2">图表样式:</span>
                <div className="flex items-center space-x-1 bg-gray-700/50 rounded-lg p-1">
                  {[
                    { value: 'candlestick', label: 'K线', icon: '📊' },
                    { value: 'line', label: '线图', icon: '📈' },
                    { value: 'area', label: '面积', icon: '🏔️' },
                    { value: 'heikin-ashi', label: 'HA', icon: '🕯️' }
                  ].map(style => (
                    <button
                      key={style.value}
                      onClick={() => updateChartConfig({ chartStyle: style.value as any })}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-all duration-200 flex items-center space-x-1 ${
                        chartConfig.chartStyle === style.value
                          ? 'bg-blue-600 text-white shadow-md'
                          : 'text-gray-300 hover:text-white hover:bg-gray-600'
                      }`}
                      title={style.label}
                    >
                      <span className="text-xs">{style.icon}</span>
                      <span>{style.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              
              {/* 分隔线 */}
              <div className="w-px h-8 bg-gray-600"></div>
              
              {/* 价格轴模式选择 */}
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-gray-400 mr-2">价格轴:</span>
                <div className="flex items-center space-x-1 bg-gray-700/50 rounded-lg p-1">
                  {[
                    { value: 'linear', label: '线性', desc: '线性价格坐标' },
                    { value: 'percentage', label: '百分比', desc: '百分比变化显示' },
                    { value: 'logarithmic', label: '对数', desc: '对数价格坐标' }
                  ].map(mode => (
                    <button
                      key={mode.value}
                      onClick={() => updateChartConfig({ priceAxisMode: mode.value as any })}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-all duration-200 ${
                        chartConfig.priceAxisMode === mode.value
                          ? 'bg-green-600 text-white shadow-md'
                          : 'text-gray-300 hover:text-white hover:bg-gray-600'
                      }`}
                      title={mode.desc}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* 分隔线 */}
              <div className="w-px h-8 bg-gray-600"></div>
              
              {/* 图表工具 */}
              <div className="flex items-center space-x-2">
                <button className="px-2 py-1 text-xs font-medium text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-all duration-200 flex items-center space-x-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>指标</span>
                </button>
                <button className="px-2 py-1 text-xs font-medium text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-all duration-200 flex items-center space-x-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>设置</span>
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* 专业右侧市场面板 */}
        <div className="w-80 bg-gradient-to-b from-gray-800 to-gray-850 border-l border-gray-700 flex flex-col flex-shrink-0 shadow-lg">
          {/* 面板头部 */}
          <div className="h-12 bg-gray-750 border-b border-gray-600 flex items-center justify-between px-4">
            <div className="flex items-center space-x-2">
              <svg className="w-5 h-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
              </svg>
              <span className="text-sm font-bold text-white">市场数据</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-xs text-gray-400">实时</span>
            </div>
          </div>
          
          {/* 标签页导航 */}
          <div className="border-b border-gray-700">
            <div className="flex">
              <button className="flex-1 px-4 py-3 text-sm font-medium bg-blue-600/20 text-blue-400 border-b-2 border-blue-600">
                自选
              </button>
              <button className="flex-1 px-4 py-3 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-700 transition-colors">
                热门
              </button>
              <button className="flex-1 px-4 py-3 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-700 transition-colors">
                涨幅榜
              </button>
            </div>
          </div>
          
          {/* 搜索框 */}
          <div className="p-4 border-b border-gray-700">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <SymbolSearchBar
                selectedSymbol={selectedSymbol}
                selectedExchange={selectedExchange || 'OKX'}
                onSymbolChange={handleSymbolChange}
                onExchangeChange={handleExchangeSwitch}
              />
            </div>
          </div>
          
          {/* 市场数据内容 */}
          <div className="flex-1 overflow-hidden">
            <MarketPanel className="w-full h-full" />
          </div>
          
          {/* 底部数据统计 */}
          <div className="border-t border-gray-700 p-4 bg-gray-800/50">
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <div className="text-gray-400">市值</div>
                <div className="text-white font-bold">$1.2T</div>
              </div>
              <div>
                <div className="text-gray-400">24h成交</div>
                <div className="text-white font-bold">$89.2B</div>
              </div>
              <div>
                <div className="text-gray-400">恐惧指数</div>
                <div className="text-green-400 font-bold">72</div>
              </div>
              <div>
                <div className="text-gray-400">BTC占比</div>
                <div className="text-white font-bold">52.3%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TradingPage