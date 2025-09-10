import { tradingServiceClient, handleApiResponse, handleApiError } from './client'
import type { 
  KlineData, 
  TickerData, 
  OrderBook, 
  TradingPair, 
  Exchange 
} from '@/types/market'

export const marketApi = {
  // 获取K线数据 - 使用真实OKX数据服务
  async getKlineData(
    symbol: string, 
    timeframe: string, 
    exchange: string = 'okx', 
    limit: number = 500
  ): Promise<KlineData[]> {
    try {
      // 直接调用我们的K线数据服务
      const response = await fetch(`/klines/${symbol}?timeframe=${timeframe}&limit=${limit}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      // 转换OKX格式到KlineData格式
      return data.klines.map((kline: number[]) => ({
        timestamp: kline[0],
        open: kline[1],
        high: kline[2], 
        low: kline[3],
        close: kline[4],
        volume: kline[5]
      }))
    } catch (error) {
      console.error('获取K线数据失败:', error)
      throw error
    }
  },

  // 获取实时价格数据 - 使用真实OKX数据服务
  async getTicker(symbol: string, exchange: string = 'okx'): Promise<TickerData> {
    try {
      // 直接调用我们的价格统计服务
      const response = await fetch(`/stats/${symbol}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      // 转换格式到TickerData
      return {
        symbol: data.symbol,
        price: data.price,
        change: data.change_24h,
        change_percent: data.change_percent || 0,
        high_24h: data.high_24h,
        low_24h: data.low_24h,
        volume_24h: data.volume_24h,
        timestamp: data.timestamp
      }
    } catch (error) {
      console.error('获取价格数据失败:', error)
      throw error
    }
  },

  // 获取多个交易对的实时价格
  async getTickers(symbols: string[], exchange: string): Promise<TickerData[]> {
    try {
      const response = await tradingServiceClient.post('/market/tickers', {
        symbols,
        exchange
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取订单簿数据
  async getOrderBook(symbol: string, exchange: string, depth: number = 20): Promise<OrderBook> {
    try {
      const response = await tradingServiceClient.get('/market/orderbook', {
        params: { symbol, exchange, depth }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取交易所信息
  async getExchanges(): Promise<Exchange[]> {
    try {
      const response = await tradingServiceClient.get('/market/exchanges')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取交易对信息
  async getTradingPairs(exchange: string): Promise<TradingPair[]> {
    try {
      const response = await tradingServiceClient.get('/market/pairs', {
        params: { exchange }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 搜索交易对
  async searchTradingPairs(query: string, exchange?: string): Promise<TradingPair[]> {
    try {
      const response = await tradingServiceClient.get('/market/pairs/search', {
        params: { query, exchange }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取历史价格数据
  async getHistoricalData(
    symbol: string,
    exchange: string,
    startDate: string,
    endDate: string,
    timeframe: string = '1d'
  ): Promise<KlineData[]> {
    try {
      const response = await tradingServiceClient.get('/market/historical', {
        params: { 
          symbol, 
          exchange, 
          start_date: startDate, 
          end_date: endDate, 
          timeframe 
        }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取市场统计信息
  async getMarketStats(exchange: string): Promise<{
    total_pairs: number
    total_volume_24h: number
    top_gainers: TickerData[]
    top_losers: TickerData[]
    most_active: TickerData[]
  }> {
    try {
      const response = await tradingServiceClient.get('/market/stats', {
        params: { exchange }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取技术指标数据
  async getTechnicalIndicators(
    symbol: string,
    exchange: string,
    timeframe: string,
    indicators: string[],
    period: number = 20
  ): Promise<Record<string, number[]>> {
    try {
      const response = await tradingServiceClient.post('/market/indicators', {
        symbol,
        exchange,
        timeframe,
        indicators,
        period
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}