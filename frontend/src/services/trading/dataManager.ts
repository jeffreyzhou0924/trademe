/**
 * Trading页面数据管理器
 * 统一管理市场数据、策略数据、WebSocket连接等
 */

import { marketDataService } from './marketDataService'
import { strategyDataService } from './strategyDataService'
import { websocketService, WebSocketEventHandler } from './websocketService'
import type { KlineData, TickerData } from '@/types/market'
import type { StrategyLibraryItem, AnalysisLibraryItem } from '@/store/tradingPageStore'

export interface DataUpdateCallbacks {
  onKlineUpdate?: (symbol: string, timeframe: string, data: KlineData[]) => void
  onTickerUpdate?: (ticker: TickerData) => void
  onStrategyUpdate?: (strategies: StrategyLibraryItem[]) => void
  onAnalysisUpdate?: (analyses: AnalysisLibraryItem[]) => void
  onConnectionUpdate?: (connected: boolean) => void
  onError?: (error: string) => void
}

export class TradingDataManager {
  private static instance: TradingDataManager
  private callbacks: DataUpdateCallbacks = {}
  private isConnected = false
  private currentSymbol = 'BTC/USDT'
  private currentTimeframe = '15m'
  private dataRefreshInterval: NodeJS.Timeout | null = null

  static getInstance(): TradingDataManager {
    if (!TradingDataManager.instance) {
      TradingDataManager.instance = new TradingDataManager()
    }
    return TradingDataManager.instance
  }

  /**
   * 初始化数据管理器
   */
  initialize(callbacks: DataUpdateCallbacks): void {
    console.log('🚀 初始化Trading数据管理器')
    this.callbacks = callbacks
    
    // 初始化WebSocket连接
    this.initializeWebSocket()
    
    // 加载初始数据
    this.loadInitialData()
    
    // 启动定时数据刷新
    this.startDataRefresh()
  }

  /**
   * 初始化WebSocket连接
   */
  private initializeWebSocket(): void {
    const wsHandlers: WebSocketEventHandler = {
      onConnect: () => {
        console.log('✅ WebSocket连接成功')
        this.isConnected = true
        this.callbacks.onConnectionUpdate?.(true)
        
        // 订阅当前symbol的实时价格
        websocketService.subscribeToSymbol(this.currentSymbol)
      },
      
      onDisconnect: () => {
        console.log('❌ WebSocket连接断开')
        this.isConnected = false
        this.callbacks.onConnectionUpdate?.(false)
      },
      
      onTicker: (ticker) => {
        console.log(`💰 实时价格更新: ${ticker.symbol} = $${ticker.price}`)
        
        // 转换格式并通知UI更新
        const tickerData: TickerData = {
          symbol: ticker.symbol,
          price: ticker.price,
          change: ticker.change_24h,
          change_percent: ticker.change_percent_24h,
          high_24h: 0, // WebSocket可能不包含这些数据
          low_24h: 0,
          volume_24h: ticker.volume_24h,
          timestamp: ticker.timestamp
        }
        
        this.callbacks.onTickerUpdate?.(tickerData)
      },
      
      onAnalysis: (analysis) => {
        console.log(`📊 分析结果更新: ${analysis.analysis_id}`)
        // 这里可以更新分析库的状态
        this.loadAnalysisLibrary()
      },
      
      onError: (error) => {
        console.error('❌ WebSocket错误:', error)
        this.callbacks.onError?.(error)
      }
    }
    
    websocketService.connect(wsHandlers)
  }

  /**
   * 加载初始数据
   */
  private async loadInitialData(): Promise<void> {
    try {
      console.log('📊 加载初始数据...')
      
      // 并发加载各种数据
      await Promise.all([
        this.loadKlineData(this.currentSymbol, this.currentTimeframe),
        this.loadTickerData(this.currentSymbol),
        this.loadStrategies(),
        this.loadAnalysisLibrary()
      ])
      
      console.log('✅ 初始数据加载完成')
    } catch (error) {
      console.error('❌ 初始数据加载失败:', error)
      this.callbacks.onError?.(`初始数据加载失败: ${error}`)
    }
  }

  /**
   * 加载K线数据
   */
  async loadKlineData(symbol: string, timeframe: string, limit: number = 100): Promise<void> {
    try {
      console.log(`📊 加载K线数据: ${symbol} ${timeframe}`)
      
      const klineData = await marketDataService.getKlineData(symbol, timeframe, limit)
      this.callbacks.onKlineUpdate?.(symbol, timeframe, klineData)
      
      console.log(`✅ K线数据加载完成: ${klineData.length}条`)
    } catch (error) {
      console.error('❌ K线数据加载失败:', error)
      this.callbacks.onError?.(`K线数据加载失败: ${error}`)
    }
  }

  /**
   * 加载价格数据
   */
  async loadTickerData(symbol: string): Promise<void> {
    try {
      console.log(`💰 加载价格数据: ${symbol}`)
      
      const tickerData = await marketDataService.getTickerData(symbol)
      this.callbacks.onTickerUpdate?.(tickerData)
      
      console.log(`✅ 价格数据加载完成: $${tickerData.price}`)
    } catch (error) {
      console.error('❌ 价格数据加载失败:', error)
      this.callbacks.onError?.(`价格数据加载失败: ${error}`)
    }
  }

  /**
   * 加载策略库
   */
  async loadStrategies(): Promise<void> {
    try {
      console.log('🎯 加载策略库...')
      
      const strategies = await strategyDataService.getStrategies()
      this.callbacks.onStrategyUpdate?.(strategies)
      
      console.log(`✅ 策略库加载完成: ${strategies.length}个策略`)
    } catch (error) {
      console.error('❌ 策略库加载失败:', error)
      this.callbacks.onError?.(`策略库加载失败: ${error}`)
    }
  }

  /**
   * 加载分析库
   */
  async loadAnalysisLibrary(): Promise<void> {
    try {
      console.log('📊 加载分析库...')
      
      const analyses = await strategyDataService.getAnalysisLibrary()
      this.callbacks.onAnalysisUpdate?.(analyses)
      
      console.log(`✅ 分析库加载完成: ${analyses.length}个分析`)
    } catch (error) {
      console.error('❌ 分析库加载失败:', error)
      this.callbacks.onError?.(`分析库加载失败: ${error}`)
    }
  }

  /**
   * 切换交易对
   */
  async switchSymbol(symbol: string, timeframe?: string): Promise<void> {
    console.log(`🔄 切换交易对: ${symbol} ${timeframe || this.currentTimeframe}`)
    
    // 取消订阅当前symbol
    if (this.isConnected) {
      websocketService.unsubscribeFromSymbol(this.currentSymbol)
    }
    
    // 更新当前symbol
    this.currentSymbol = symbol
    if (timeframe) {
      this.currentTimeframe = timeframe
    }
    
    // 订阅新symbol
    if (this.isConnected) {
      websocketService.subscribeToSymbol(this.currentSymbol)
    }
    
    // 加载新数据
    await Promise.all([
      this.loadKlineData(symbol, this.currentTimeframe),
      this.loadTickerData(symbol)
    ])
  }

  /**
   * 切换时间框架
   */
  async switchTimeframe(timeframe: string): Promise<void> {
    console.log(`🔄 切换时间框架: ${this.currentSymbol} ${timeframe}`)
    this.currentTimeframe = timeframe
    
    await this.loadKlineData(this.currentSymbol, timeframe)
  }

  /**
   * 运行策略回测
   */
  async runStrategyBacktest(strategyId: string): Promise<void> {
    try {
      console.log(`🎯 运行策略回测: ${strategyId}`)
      
      const performance = await strategyDataService.runBacktest(
        strategyId,
        this.currentSymbol,
        this.currentTimeframe
      )
      
      console.log(`✅ 策略回测完成:`, performance)
      
      // 重新加载策略库以获取更新的性能数据
      await this.loadStrategies()
      
    } catch (error) {
      console.error('❌ 策略回测失败:', error)
      this.callbacks.onError?.(`策略回测失败: ${error}`)
    }
  }

  /**
   * 运行AI分析
   */
  async runAIAnalysis(analysisId: string): Promise<void> {
    try {
      console.log(`🤖 运行AI分析: ${analysisId}`)
      
      if (this.isConnected) {
        // 使用WebSocket启动实时分析
        websocketService.startAnalysis(analysisId, this.currentSymbol)
      } else {
        // 使用HTTP API运行分析
        const result = await strategyDataService.runAnalysis(analysisId, this.currentSymbol)
        console.log(`✅ AI分析完成:`, result)
        
        // 重新加载分析库以获取更新结果
        await this.loadAnalysisLibrary()
      }
      
    } catch (error) {
      console.error('❌ AI分析失败:', error)
      this.callbacks.onError?.(`AI分析失败: ${error}`)
    }
  }

  /**
   * AI对话
   */
  async chatWithAI(message: string, sessionType: 'strategy' | 'indicator' | 'analysis' = 'strategy'): Promise<string> {
    try {
      console.log(`🤖 AI对话: ${sessionType}`)
      
      const response = await strategyDataService.chatWithAI(message, sessionType)
      console.log(`✅ AI对话完成`)
      
      return response
      
    } catch (error) {
      console.error('❌ AI对话失败:', error)
      throw error
    }
  }

  /**
   * 启动定时数据刷新
   */
  private startDataRefresh(): void {
    // 每30秒刷新一次价格数据 (如果WebSocket未连接)
    this.dataRefreshInterval = setInterval(() => {
      if (!this.isConnected) {
        console.log('🔄 定时刷新价格数据 (WebSocket未连接)')
        this.loadTickerData(this.currentSymbol)
      }
    }, 30000)
  }

  /**
   * 获取连接状态
   */
  getConnectionStatus(): {
    websocket: boolean
    api: boolean
  } {
    return {
      websocket: this.isConnected,
      api: true // API连接通常是即时的
    }
  }

  /**
   * 获取当前交易对和时间框架
   */
  getCurrentSettings(): {
    symbol: string
    timeframe: string
  } {
    return {
      symbol: this.currentSymbol,
      timeframe: this.currentTimeframe
    }
  }

  /**
   * 清理资源
   */
  destroy(): void {
    console.log('🧹 清理Trading数据管理器资源')
    
    // 清理WebSocket连接
    websocketService.disconnect()
    
    // 清理定时器
    if (this.dataRefreshInterval) {
      clearInterval(this.dataRefreshInterval)
      this.dataRefreshInterval = null
    }
    
    // 清理缓存
    marketDataService.clearCache()
  }
}

// 导出单例实例
export const tradingDataManager = TradingDataManager.getInstance()