/**
 * Trading页面市场数据服务
 * 专门为Trading页面提供实时市场数据集成
 */

import { tradingServiceClient } from '@/services/api/client'
import type { KlineData, TickerData } from '@/types/market'

export interface MarketDataResponse {
  success: boolean
  data: any
  message: string
}

export interface KlineResponse {
  klines: number[][]
  count: number
  symbol: string
  timeframe: string
  last_updated: number
}

export interface TickerResponse {
  symbol: string
  price: number
  change_24h: number
  change_percent_24h: number
  high_24h: number
  low_24h: number
  volume_24h: number
  timestamp: number
}

export interface TradingPairInfo {
  symbol: string
  price: number
  change_24h: number
  change_percent_24h: number
  volume_24h: number
  exchange: string
}

export class MarketDataService {
  private static instance: MarketDataService
  private cache: Map<string, { data: any; timestamp: number }> = new Map()
  private readonly CACHE_TTL = 5000 // 5秒缓存

  static getInstance(): MarketDataService {
    if (!MarketDataService.instance) {
      MarketDataService.instance = new MarketDataService()
    }
    return MarketDataService.instance
  }

  /**
   * 获取K线数据 - 临时使用模拟数据避免阻塞Trading页面
   */
  async getKlineData(
    symbol: string,
    timeframe: string,
    limit: number = 100
  ): Promise<KlineData[]> {
    try {
      console.log(`🔍 获取K线数据: ${symbol} ${timeframe} (${limit}条) - 使用模拟数据`)
      
      // 生成模拟K线数据
      const mockKlineData = this.generateMockKlineData(symbol, timeframe, limit)
      
      console.log(`✅ 模拟K线数据生成成功: ${mockKlineData.length}条记录`)
      return mockKlineData

    } catch (error) {
      console.error('❌ K线数据获取失败:', error)
      throw new Error(`获取K线数据失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 生成模拟K线数据
   */
  private generateMockKlineData(symbol: string, timeframe: string, limit: number): KlineData[] {
    const data: KlineData[] = []
    let basePrice = 43250.00 // BTC基础价格
    
    // 根据symbol调整基础价格
    if (symbol.includes('ETH')) basePrice = 2800.00
    else if (symbol.includes('ADA')) basePrice = 0.45
    else if (symbol.includes('SOL')) basePrice = 125.00
    
    const now = Date.now()
    const timeframeMs = this.getTimeframeMilliseconds(timeframe)
    
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

  /**
   * 获取时间框架对应的毫秒数
   */
  private getTimeframeMilliseconds(timeframe: string): number {
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

  /**
   * 获取实时价格数据 - 临时使用模拟数据
   */
  async getTickerData(symbol: string): Promise<TickerData> {
    try {
      console.log(`🔍 获取价格数据: ${symbol} - 使用模拟数据`)
      
      // 生成模拟价格数据
      const mockTickerData = this.generateMockTickerData(symbol)
      
      console.log(`✅ 模拟价格数据生成成功: ${symbol} = $${mockTickerData.price}`)
      return mockTickerData

    } catch (error) {
      console.error('❌ 价格数据获取失败:', error)
      throw new Error(`获取价格数据失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 生成模拟价格数据
   */
  private generateMockTickerData(symbol: string): TickerData {
    let basePrice = 43250.00 // BTC基础价格
    
    // 根据symbol调整基础价格
    if (symbol.includes('ETH')) basePrice = 2800.00
    else if (symbol.includes('ADA')) basePrice = 0.45
    else if (symbol.includes('SOL')) basePrice = 125.00
    else if (symbol.includes('DOT')) basePrice = 7.50
    else if (symbol.includes('MATIC')) basePrice = 0.85
    
    // 生成随机价格变动
    const priceVariation = (Math.random() - 0.5) * 0.02 // ±1%变动
    const price = basePrice * (1 + priceVariation)
    
    const change24h = basePrice * ((Math.random() - 0.5) * 0.08) // ±4%变动
    const changePercent24h = (change24h / basePrice) * 100
    
    const high24h = price + (price * Math.random() * 0.03) // 0-3%向上
    const low24h = price - (price * Math.random() * 0.03) // 0-3%向下
    const volume24h = Math.random() * 1000000 + 100000 // 10万-110万交易量
    
    return {
      symbol: symbol,
      price: parseFloat(price.toFixed(2)),
      change: parseFloat(change24h.toFixed(2)),
      change_percent: parseFloat(changePercent24h.toFixed(2)),
      high_24h: parseFloat(high24h.toFixed(2)),
      low_24h: parseFloat(low24h.toFixed(2)),
      volume_24h: parseFloat(volume24h.toFixed(2)),
      timestamp: Date.now()
    }
  }

  /**
   * 批量获取多个交易对价格
   */
  async getMultipleTickerData(symbols: string[]): Promise<TickerData[]> {
    try {
      console.log(`🔍 批量获取价格数据: ${symbols.length}个交易对`)
      
      const symbolsParam = symbols.join(',')
      const response = await tradingServiceClient.get<MarketDataResponse>(
        '/api/v1/market-data/tickers',
        {
          params: { symbols: symbolsParam }
        }
      )

      if (!response.data.success) {
        throw new Error(response.data.message || '批量价格数据获取失败')
      }

      const tickers = response.data.data as Record<string, TickerResponse>
      const result: TickerData[] = []

      for (const symbol of symbols) {
        if (tickers[symbol]) {
          const ticker = tickers[symbol]
          result.push({
            symbol: ticker.symbol,
            price: ticker.price,
            change: ticker.change_24h,
            change_percent: ticker.change_percent_24h,
            high_24h: ticker.high_24h,
            low_24h: ticker.low_24h,
            volume_24h: ticker.volume_24h,
            timestamp: ticker.timestamp
          })
        }
      }

      console.log(`✅ 批量价格数据获取成功: ${result.length}个交易对`)
      return result

    } catch (error) {
      console.error('❌ 批量价格数据获取失败:', error)
      throw new Error(`批量获取价格数据失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取支持的交易对列表
   */
  async getSupportedSymbols(): Promise<string[]> {
    const cacheKey = 'supported_symbols'
    const cached = this.getFromCache(cacheKey)
    if (cached) return cached

    try {
      console.log('🔍 获取支持的交易对列表')
      
      const response = await tradingServiceClient.get<MarketDataResponse>(
        '/api/v1/market-data/supported-symbols'
      )

      if (!response.data.success) {
        throw new Error(response.data.message || '获取交易对列表失败')
      }

      const symbols = response.data.data.symbols as string[]
      this.setCache(cacheKey, symbols)

      console.log(`✅ 支持的交易对获取成功: ${symbols.length}个`)
      return symbols

    } catch (error) {
      console.error('❌ 获取交易对列表失败:', error)
      throw new Error(`获取交易对列表失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取热门交易对及其价格信息
   */
  async getPopularTradingPairs(limit: number = 8): Promise<TradingPairInfo[]> {
    try {
      console.log(`🔍 获取热门交易对: ${limit}个`)
      
      const response = await tradingServiceClient.get<MarketDataResponse>(
        '/api/v1/market-data/trading-pairs',
        {
          params: { limit }
        }
      )

      if (!response.data.success) {
        throw new Error(response.data.message || '获取热门交易对失败')
      }

      const tradingPairs = response.data.data.trading_pairs.map((pair: any) => ({
        symbol: pair.symbol,
        price: pair.price,
        change_24h: pair.change_24h,
        change_percent_24h: pair.change_percent_24h,
        volume_24h: pair.volume_24h,
        exchange: 'OKX' // 当前主要使用OKX数据源
      }))

      console.log(`✅ 热门交易对获取成功: ${tradingPairs.length}个`)
      return tradingPairs

    } catch (error) {
      console.error('❌ 获取热门交易对失败:', error)
      throw new Error(`获取热门交易对失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 缓存管理
   */
  private getFromCache(key: string): any {
    const cached = this.cache.get(key)
    if (!cached) return null
    
    const now = Date.now()
    if (now - cached.timestamp > this.CACHE_TTL) {
      this.cache.delete(key)
      return null
    }
    
    return cached.data
  }

  private setCache(key: string, data: any): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    })
  }

  /**
   * 清空缓存
   */
  clearCache(): void {
    this.cache.clear()
  }
}

// 导出单例实例
export const marketDataService = MarketDataService.getInstance()