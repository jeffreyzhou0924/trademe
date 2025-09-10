import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 交易机会类型
export interface TradingOpportunity {
  id: string
  type: 'breakout' | 'support' | 'resistance' | 'pattern'
  signal: 'buy' | 'sell' | 'watch'
  price: number
  confidence: number
  description: string
  suggestedStrategy?: string
  timestamp: number
}

// AI推荐策略
export interface StrategySuggestion {
  id: string
  strategyId: string
  strategyName: string
  reason: string
  confidence: number
  estimatedReturn: number
  riskLevel: 'low' | 'medium' | 'high'
}

// 画图工具
export interface DrawingTool {
  id: string
  type: 'trendline' | 'rectangle' | 'fibonacci' | 'horizontal' | 'vertical'
  points: { x: number; y: number }[]
  style: {
    color: string
    lineWidth: number
    lineDash?: number[]
  }
  symbol: string
  timeframe: string
}

// 自选品种
export interface WatchlistItem {
  symbol: string
  exchange: string
  price: number
  change24h: number
  changePercent24h: number
  volume24h: number
  lastUpdated: number
}

// 订单薄数据
export interface OrderBookData {
  symbol: string
  bids: [number, number][] // [price, quantity]
  asks: [number, number][]
  timestamp: number
}

// 策略库项目
export interface StrategyLibraryItem {
  id: string
  name: string
  description: string
  type: 'ai_generated' | 'custom' | 'template'
  source: 'ai_chat' | 'user' | 'system'
  code: string
  parameters: Record<string, any>
  performance?: {
    winRate: number
    returns: number
    maxDrawdown: number
  }
  createdAt: number
  lastUsed?: number
}

// 指标库项目
export interface IndicatorLibraryItem {
  id: string
  name: string
  description: string
  type: 'technical' | 'custom' | 'ai_enhanced'
  parameters: Record<string, any>
  formula?: string
  isActive: boolean
  createdAt: number
}

// 分析库项目
export interface AnalysisLibraryItem {
  id: string
  name: string
  description: string
  type: 'pattern' | 'trend' | 'volume' | 'comprehensive'
  criteria: Record<string, any>
  confidence: number
  lastAnalysis?: {
    result: string
    timestamp: number
    opportunities: TradingOpportunity[]
  }
}

// 图表配置
export interface ChartConfig {
  symbol: string
  timeframe: string
  exchange: string
  indicators: string[] // 激活的指标ID列表
  drawingTools: DrawingTool[]
  aiAnalysisEnabled: boolean
  theme: 'light' | 'dark'
  layout: 'single' | 'multi'
  priceAxisMode: 'linear' | 'percentage' | 'logarithmic' // 价格轴模式
  chartStyle: 'candlestick' | 'line' | 'area' | 'heikin-ashi' // 图表样式
  autoScale: boolean // 自适应缩放
  displayMode: 'normal' | 'percentage' // 数据显示模式
}

// TradingPage状态接口
interface TradingPageStore {
  // 基础状态
  selectedSymbol: string
  selectedTimeframe: string
  selectedExchange: string
  
  // 图表配置
  chartConfig: ChartConfig
  
  // 策略和分析
  strategyLibrary: StrategyLibraryItem[]
  indicatorLibrary: IndicatorLibraryItem[]
  analysisLibrary: AnalysisLibraryItem[]
  activeStrategies: string[] // 当前激活的策略ID
  
  // AI功能
  aiRecommendations: StrategySuggestion[]
  tradingOpportunities: TradingOpportunity[]
  aiAnalysisEnabled: boolean
  
  // 市场数据
  watchList: WatchlistItem[]
  orderBookData: OrderBookData | null
  klineDataStore: Record<string, any[]>
  isDataLoading: boolean
  currentPriceData: Record<string, number>
  
  // UI状态
  leftPanelCollapsed: boolean
  rightPanelCollapsed: boolean
  activeLeftTab: 'strategies' | 'indicators' | 'analysis'
  activeRightTab: 'market' | 'watchlist' | 'orderbook'
  
  // 动作方法
  setSelectedSymbol: (symbol: string) => void
  setSelectedTimeframe: (timeframe: string) => void
  setSelectedExchange: (exchange: string) => void
  
  // 图表配置方法
  updateChartConfig: (config: Partial<ChartConfig>) => void
  addDrawingTool: (tool: DrawingTool) => void
  removeDrawingTool: (toolId: string) => void
  clearDrawingTools: () => void
  
  // 策略库方法
  addStrategy: (strategy: StrategyLibraryItem) => void
  removeStrategy: (strategyId: string) => void
  activateStrategy: (strategyId: string) => void
  deactivateStrategy: (strategyId: string) => void
  
  // 指标库方法
  addIndicator: (indicator: IndicatorLibraryItem) => void
  removeIndicator: (indicatorId: string) => void
  toggleIndicator: (indicatorId: string) => void
  
  // 分析库方法
  addAnalysis: (analysis: AnalysisLibraryItem) => void
  removeAnalysis: (analysisId: string) => void
  runAnalysis: (analysisId: string) => Promise<void>
  
  // AI功能方法
  setAIAnalysisEnabled: (enabled: boolean) => void
  addAIRecommendation: (recommendation: StrategySuggestion) => void
  clearAIRecommendations: () => void
  addTradingOpportunity: (opportunity: TradingOpportunity) => void
  clearTradingOpportunities: () => void
  
  // 自选列表方法
  addToWatchList: (item: WatchlistItem) => void
  removeFromWatchList: (symbol: string, exchange: string) => void
  updateWatchListPrices: (updates: Partial<WatchlistItem>[]) => void
  
  // 订单薄方法
  updateOrderBook: (data: OrderBookData) => void
  
  // UI状态方法
  toggleLeftPanel: () => void
  toggleRightPanel: () => void
  setActiveLeftTab: (tab: 'strategies' | 'indicators' | 'analysis') => void
  setActiveRightTab: (tab: 'market' | 'watchlist' | 'orderbook') => void
  
  // 数据管理方法
  updateKlineData: (symbol: string, timeframe: string, data: any[]) => void
  updateCurrentPrice: (price: string) => void
  updateStrategyLibrary: (strategies: StrategyLibraryItem[]) => void
  updateAnalysisLibrary: (analyses: AnalysisLibraryItem[]) => void
  
  // 数据同步方法（与AI对话系统集成）
  syncFromAIChat: (strategies: StrategyLibraryItem[], indicators: IndicatorLibraryItem[]) => void
}

// 默认配置
const defaultChartConfig: ChartConfig = {
  symbol: 'BTC/USDT',
  timeframe: '15m',
  exchange: 'OKX',
  indicators: [],
  drawingTools: [],
  aiAnalysisEnabled: true,
  theme: 'dark',
  layout: 'single',
  priceAxisMode: 'linear',
  chartStyle: 'candlestick',
  autoScale: true,
  displayMode: 'normal'
}

export const useTradingPageStore = create<TradingPageStore>()(
  persist(
    (set, get) => ({
      // 初始状态
      selectedSymbol: 'BTC/USDT',
      selectedTimeframe: '15m',
      selectedExchange: 'OKX',
      
      chartConfig: defaultChartConfig,
      
      strategyLibrary: [],
      indicatorLibrary: [],
      analysisLibrary: [],
      activeStrategies: [],
      
      aiRecommendations: [],
      tradingOpportunities: [],
      aiAnalysisEnabled: true,
      
      watchList: [],
      orderBookData: null,
      klineDataStore: {},
      isDataLoading: false,
      currentPriceData: {},
      
      leftPanelCollapsed: false,
      rightPanelCollapsed: false,
      activeLeftTab: 'strategies',
      activeRightTab: 'market',
      
      // 基础操作方法
      setSelectedSymbol: (symbol) => {
        set((state) => ({
          selectedSymbol: symbol,
          chartConfig: { ...state.chartConfig, symbol }
        }))
      },
      
      setSelectedTimeframe: (timeframe) => {
        set((state) => ({
          selectedTimeframe: timeframe,
          chartConfig: { ...state.chartConfig, timeframe }
        }))
      },
      
      setSelectedExchange: (exchange) => {
        set((state) => ({
          selectedExchange: exchange,
          chartConfig: { ...state.chartConfig, exchange }
        }))
      },
      
      // 图表配置方法
      updateChartConfig: (config) => {
        set((state) => ({
          chartConfig: { ...state.chartConfig, ...config }
        }))
      },
      
      addDrawingTool: (tool) => {
        set((state) => ({
          chartConfig: {
            ...state.chartConfig,
            drawingTools: [...state.chartConfig.drawingTools, tool]
          }
        }))
      },
      
      removeDrawingTool: (toolId) => {
        set((state) => ({
          chartConfig: {
            ...state.chartConfig,
            drawingTools: state.chartConfig.drawingTools.filter(t => t.id !== toolId)
          }
        }))
      },
      
      clearDrawingTools: () => {
        set((state) => ({
          chartConfig: {
            ...state.chartConfig,
            drawingTools: []
          }
        }))
      },
      
      // 策略库方法
      addStrategy: (strategy) => {
        set((state) => ({
          strategyLibrary: [...state.strategyLibrary, strategy]
        }))
      },
      
      removeStrategy: (strategyId) => {
        set((state) => ({
          strategyLibrary: state.strategyLibrary.filter(s => s.id !== strategyId),
          activeStrategies: state.activeStrategies.filter(id => id !== strategyId)
        }))
      },
      
      activateStrategy: (strategyId) => {
        set((state) => ({
          activeStrategies: state.activeStrategies.includes(strategyId) 
            ? state.activeStrategies 
            : [...state.activeStrategies, strategyId]
        }))
      },
      
      deactivateStrategy: (strategyId) => {
        set((state) => ({
          activeStrategies: state.activeStrategies.filter(id => id !== strategyId)
        }))
      },
      
      // 指标库方法
      addIndicator: (indicator) => {
        set((state) => ({
          indicatorLibrary: [...state.indicatorLibrary, indicator]
        }))
      },
      
      removeIndicator: (indicatorId) => {
        set((state) => ({
          indicatorLibrary: state.indicatorLibrary.filter(i => i.id !== indicatorId),
          chartConfig: {
            ...state.chartConfig,
            indicators: state.chartConfig.indicators.filter(id => id !== indicatorId)
          }
        }))
      },
      
      toggleIndicator: (indicatorId) => {
        set((state) => {
          const isActive = state.chartConfig.indicators.includes(indicatorId)
          return {
            chartConfig: {
              ...state.chartConfig,
              indicators: isActive
                ? state.chartConfig.indicators.filter(id => id !== indicatorId)
                : [...state.chartConfig.indicators, indicatorId]
            },
            indicatorLibrary: state.indicatorLibrary.map(indicator =>
              indicator.id === indicatorId
                ? { ...indicator, isActive: !indicator.isActive }
                : indicator
            )
          }
        })
      },
      
      // 分析库方法
      addAnalysis: (analysis) => {
        set((state) => ({
          analysisLibrary: [...state.analysisLibrary, analysis]
        }))
      },
      
      removeAnalysis: (analysisId) => {
        set((state) => ({
          analysisLibrary: state.analysisLibrary.filter(a => a.id !== analysisId)
        }))
      },
      
      runAnalysis: async (analysisId) => {
        // TODO: 实现分析执行逻辑，调用AI服务
        console.log(`Running analysis: ${analysisId}`)
      },
      
      // AI功能方法
      setAIAnalysisEnabled: (enabled) => {
        set((state) => ({
          aiAnalysisEnabled: enabled,
          chartConfig: { ...state.chartConfig, aiAnalysisEnabled: enabled }
        }))
      },
      
      addAIRecommendation: (recommendation) => {
        set((state) => ({
          aiRecommendations: [...state.aiRecommendations, recommendation]
        }))
      },
      
      clearAIRecommendations: () => {
        set({ aiRecommendations: [] })
      },
      
      addTradingOpportunity: (opportunity) => {
        set((state) => ({
          tradingOpportunities: [...state.tradingOpportunities, opportunity]
        }))
      },
      
      clearTradingOpportunities: () => {
        set({ tradingOpportunities: [] })
      },
      
      // 自选列表方法
      addToWatchList: (item) => {
        set((state) => {
          const exists = state.watchList.find(w => 
            w.symbol === item.symbol && w.exchange === item.exchange
          )
          if (exists) return state
          return {
            watchList: [...state.watchList, item]
          }
        })
      },
      
      removeFromWatchList: (symbol, exchange) => {
        set((state) => ({
          watchList: state.watchList.filter(w => 
            !(w.symbol === symbol && w.exchange === exchange)
          )
        }))
      },
      
      updateWatchListPrices: (updates) => {
        set((state) => ({
          watchList: state.watchList.map(item => {
            const update = updates.find(u => 
              u.symbol === item.symbol && u.exchange === item.exchange
            )
            return update ? { ...item, ...update } : item
          })
        }))
      },
      
      // 订单薄方法
      updateOrderBook: (data) => {
        set({ orderBookData: data })
      },
      
      // UI状态方法
      toggleLeftPanel: () => {
        set((state) => ({
          leftPanelCollapsed: !state.leftPanelCollapsed
        }))
      },
      
      toggleRightPanel: () => {
        set((state) => ({
          rightPanelCollapsed: !state.rightPanelCollapsed
        }))
      },
      
      setActiveLeftTab: (tab) => {
        set({ activeLeftTab: tab })
      },
      
      setActiveRightTab: (tab) => {
        set({ activeRightTab: tab })
      },
      
      // 数据管理方法
      updateKlineData: (symbol, timeframe, data) => {
        const dataKey = `${get().selectedExchange}:${symbol}:${timeframe}`
        set((state) => ({
          klineDataStore: {
            ...state.klineDataStore,
            [dataKey]: data
          }
        }))
      },
      
      updateCurrentPrice: (price) => {
        const symbol = get().selectedSymbol
        set((state) => ({
          currentPriceData: {
            ...state.currentPriceData,
            [symbol]: parseFloat(price)
          }
        }))
      },
      
      updateStrategyLibrary: (strategies) => {
        set({ strategyLibrary: strategies })
      },
      
      updateAnalysisLibrary: (analyses) => {
        set({ analysisLibrary: analyses })
      },
      
      // 数据同步方法
      syncFromAIChat: (strategies, indicators) => {
        set((state) => ({
          strategyLibrary: [
            ...state.strategyLibrary.filter(s => s.source !== 'ai_chat'),
            ...strategies
          ],
          indicatorLibrary: [
            ...state.indicatorLibrary.filter(i => i.type !== 'ai_enhanced'),
            ...indicators
          ]
        }))
      }
    }),
    {
      name: 'trading-page-store',
      partialize: (state) => ({
        // 只持久化用户配置，不持久化实时数据
        chartConfig: state.chartConfig,
        strategyLibrary: state.strategyLibrary,
        indicatorLibrary: state.indicatorLibrary,
        analysisLibrary: state.analysisLibrary,
        watchList: state.watchList,
        leftPanelCollapsed: state.leftPanelCollapsed,
        rightPanelCollapsed: state.rightPanelCollapsed,
        activeLeftTab: state.activeLeftTab,
        activeRightTab: state.activeRightTab,
        aiAnalysisEnabled: state.aiAnalysisEnabled
      })
    }
  )
)