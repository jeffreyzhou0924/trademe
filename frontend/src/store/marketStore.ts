import { create } from 'zustand'
import toast from 'react-hot-toast'
import { marketApi } from '../services/api/market'
import { wsManager } from '../utils/websocketManager'
import type { MarketData, KlineData, TickerData } from '../types/market'

interface MarketState {
  // 市场数据
  currentPrices: Record<string, TickerData>
  klineData: Record<string, KlineData[]>
  selectedSymbol: string
  selectedTimeframe: string
  selectedExchange: string
  
  // 加载状态
  isLoading: boolean
  isConnected: boolean
  lastUpdate: Date | null
  error: string | null
  
  // 订阅状态
  subscribedTickers: Set<string>
  connectionStats: any
  
  // 操作方法
  setSelectedSymbol: (symbol: string) => void
  setSelectedTimeframe: (timeframe: string) => void
  setSelectedExchange: (exchange: string) => void
  
  // 数据获取
  fetchKlineData: (symbol: string, timeframe: string, exchange: string) => Promise<void>
  subscribeToTicker: (symbol: string, exchange: string) => void
  unsubscribeFromTicker: (symbol: string, exchange: string) => void
  
  // WebSocket管理
  connectWebSocket: () => void
  disconnectWebSocket: () => void
  updatePrice: (symbol: string, data: TickerData) => void
  
  // 工具方法
  clearError: () => void
  getConnectionStats: () => any
  reset: () => void
}

export const useMarketStore = create<MarketState>((set, get) => ({
  // 初始状态
  currentPrices: {},
  klineData: {},
  selectedSymbol: 'BTC/USDT',
  selectedTimeframe: '1h',
  selectedExchange: 'okx',
  isLoading: false,
  isConnected: false,
  lastUpdate: null,
  error: null,
  subscribedTickers: new Set(),
  connectionStats: null,

  // 设置选中的交易对
  setSelectedSymbol: (symbol: string) => {
    set({ selectedSymbol: symbol })
    // 自动获取新的K线数据
    const { selectedTimeframe, selectedExchange, fetchKlineData } = get()
    fetchKlineData(symbol, selectedTimeframe, selectedExchange)
  },

  // 设置选中的时间周期
  setSelectedTimeframe: (timeframe: string) => {
    set({ selectedTimeframe: timeframe })
    // 自动获取新的K线数据
    const { selectedSymbol, selectedExchange, fetchKlineData } = get()
    fetchKlineData(selectedSymbol, timeframe, selectedExchange)
  },

  // 设置选中的交易所
  setSelectedExchange: (exchange: string) => {
    set({ selectedExchange: exchange })
    // 自动获取新的K线数据
    const { selectedSymbol, selectedTimeframe, fetchKlineData } = get()
    fetchKlineData(selectedSymbol, selectedTimeframe, exchange)
  },

  // 获取K线数据
  fetchKlineData: async (symbol: string, timeframe: string, exchange: string) => {
    set({ isLoading: true })
    try {
      const data = await marketApi.getKlineData(symbol, timeframe, exchange)
      set(state => ({
        klineData: {
          ...state.klineData,
          [`${exchange}:${symbol}:${timeframe}`]: data
        },
        isLoading: false,
        lastUpdate: new Date()
      }))
    } catch (error: any) {
      set({ isLoading: false })
      const message = error.response?.data?.message || '获取K线数据失败'
      toast.error(message)
    }
  },

  // 订阅实时价格
  subscribeToTicker: (symbol: string, exchange: string) => {
    const key = `${exchange}:${symbol}`
    const endpoint = `/market/${exchange}/${symbol}/ticker`
    
    const success = wsManager.connect(key, endpoint, {
      onOpen: () => {
        set(state => ({
          isConnected: true,
          subscribedTickers: new Set([...state.subscribedTickers, key]),
          error: null
        }))
        console.log(`Subscribed to ticker: ${key}`)
      },
      onMessage: (data: TickerData) => {
        get().updatePrice(symbol, data)
      },
      onError: (error) => {
        console.error(`WebSocket error for ${key}:`, error)
        set({ error: `${symbol} 价格订阅失败` })
        toast.error(`${symbol} 价格订阅失败`)
      },
      onClose: () => {
        set(state => {
          const newSubscribed = new Set(state.subscribedTickers)
          newSubscribed.delete(key)
          return {
            subscribedTickers: newSubscribed,
            isConnected: newSubscribed.size > 0
          }
        })
        console.log(`Unsubscribed from ticker: ${key}`)
      }
    })

    if (!success) {
      toast.error(`无法连接到 ${symbol} 价格推送`)
      set({ error: `WebSocket连接失败: ${symbol}` })
    }
  },

  // 取消订阅实时价格
  unsubscribeFromTicker: (symbol: string, exchange: string) => {
    const key = `${exchange}:${symbol}`
    const success = wsManager.disconnect(key)
    
    if (success) {
      set(state => {
        const newSubscribed = new Set(state.subscribedTickers)
        newSubscribed.delete(key)
        return {
          subscribedTickers: newSubscribed,
          isConnected: newSubscribed.size > 0
        }
      })
    }
  },

  // 连接WebSocket
  connectWebSocket: () => {
    const { selectedSymbol, selectedExchange } = get()
    get().subscribeToTicker(selectedSymbol, selectedExchange)
  },

  // 断开WebSocket
  disconnectWebSocket: () => {
    wsManager.disconnectAll()
    set({ 
      subscribedTickers: new Set(),
      isConnected: false,
      connectionStats: null
    })
  },

  // 更新价格数据
  updatePrice: (symbol: string, data: TickerData) => {
    set(state => ({
      currentPrices: {
        ...state.currentPrices,
        [symbol]: data
      },
      lastUpdate: new Date(),
      error: null
    }))
  },

  // 清空错误
  clearError: () => {
    set({ error: null })
  },

  // 获取连接统计
  getConnectionStats: () => {
    const stats = wsManager.getStats()
    set({ connectionStats: stats })
    return stats
  },

  // 重置所有状态
  reset: () => {
    // 先断开所有连接
    wsManager.disconnectAll()
    
    // 重置状态
    set({
      currentPrices: {},
      klineData: {},
      selectedSymbol: 'BTC/USDT',
      selectedTimeframe: '1h',
      selectedExchange: 'okx',
      isLoading: false,
      isConnected: false,
      lastUpdate: null,
      error: null,
      subscribedTickers: new Set(),
      connectionStats: null
    })
  }
}))