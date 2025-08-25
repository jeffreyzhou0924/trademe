/**
 * 实盘交易状态管理
 * 管理订单、持仓、交易统计等实盘交易相关状态
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { tradingApi } from '../services/api/trading'
import type { 
  Order, 
  Position, 
  TradingSummary, 
  DailyPnL, 
  TradingAccount,
  TradingSession,
  OrderRequest,
  OrderStatistics,
  RiskAssessment
} from '../services/api/trading'

// 交易面板表单状态
interface TradingForm {
  exchange: string
  symbol: string
  side: 'buy' | 'sell'
  order_type: 'market' | 'limit'
  price: string
  quantity: string
  amount: string
}

// 实盘交易状态接口
interface TradingState {
  // 账户相关
  accounts: Record<string, TradingAccount>
  selectedExchange: string
  supportedExchanges: string[]
  availableSymbols: string[]
  
  // 订单相关
  orders: Order[]
  activeOrders: Order[]
  orderHistory: Order[]
  orderStats: OrderStatistics | null
  
  // 持仓相关
  positions: Position[]
  totalPortfolioValue: number
  totalUnrealizedPnL: number
  totalRealizedPnL: number
  
  // 交易统计
  tradingSummary: TradingSummary | null
  dailyPnLData: DailyPnL[]
  recentTrades: any[]
  
  // 交易会话
  tradingSessions: TradingSession[]
  activeSessions: TradingSession[]
  
  // 交易表单
  tradingForm: TradingForm
  lastRiskAssessment: RiskAssessment | null
  
  // UI状态
  selectedTimeframe: string
  showAdvancedOptions: boolean
  
  // 加载状态
  isLoading: boolean
  isPlacingOrder: boolean
  isLoadingPositions: boolean
  isLoadingOrders: boolean
  error: string | null
  
  // Actions - 账户管理
  loadSupportedExchanges: () => Promise<void>
  loadAccountBalance: (exchange: string) => Promise<void>
  loadAvailableSymbols: (exchange: string) => Promise<void>
  switchExchange: (exchange: string) => void
  
  // Actions - 订单管理
  createOrder: (orderData: OrderRequest) => Promise<Order | null>
  loadOrders: (filters?: any) => Promise<void>
  cancelOrder: (orderId: string) => Promise<void>
  refreshOrder: (orderId: string) => Promise<void>
  loadOrderStatistics: (days?: number) => Promise<void>
  
  // Actions - 持仓管理
  loadPositions: (exchange?: string) => Promise<void>
  refreshPositions: () => Promise<void>
  calculatePositionPnL: (symbol: string, exchange: string, currentPrice: number) => Promise<void>
  
  // Actions - 交易统计
  loadTradingSummary: (days?: number) => Promise<void>
  loadDailyPnL: (days?: number) => Promise<void>
  loadRecentTrades: (filters?: any) => Promise<void>
  
  // Actions - 交易会话
  createTradingSession: (sessionData: any) => Promise<TradingSession | null>
  loadTradingSessions: () => Promise<void>
  startTradingSession: (sessionId: string) => Promise<void>
  stopTradingSession: (sessionId: string) => Promise<void>
  
  // Actions - 交易表单
  updateTradingForm: (field: keyof TradingForm, value: string) => void
  resetTradingForm: () => void
  calculateOrderAmount: () => void
  validateOrder: () => Promise<RiskAssessment | null>
  
  // Actions - UI控制
  setSelectedTimeframe: (timeframe: string) => void
  toggleAdvancedOptions: () => void
  
  // Actions - 状态管理
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearError: () => void
  reset: () => void
}

// 默认交易表单状态
const defaultTradingForm: TradingForm = {
  exchange: 'okx',
  symbol: 'BTC/USDT',
  side: 'buy',
  order_type: 'limit',
  price: '',
  quantity: '',
  amount: ''
}

// 创建交易状态管理
export const useTradingStore = create<TradingState>()(
  persist(
    (set, get) => ({
      // 初始状态
      accounts: {},
      selectedExchange: 'okx',
      supportedExchanges: [],
      availableSymbols: [],
      
      orders: [],
      activeOrders: [],
      orderHistory: [],
      orderStats: null,
      
      positions: [],
      totalPortfolioValue: 0,
      totalUnrealizedPnL: 0,
      totalRealizedPnL: 0,
      
      tradingSummary: null,
      dailyPnLData: [],
      recentTrades: [],
      
      tradingSessions: [],
      activeSessions: [],
      
      tradingForm: defaultTradingForm,
      lastRiskAssessment: null,
      
      selectedTimeframe: '15m',
      showAdvancedOptions: false,
      
      isLoading: false,
      isPlacingOrder: false,
      isLoadingPositions: false,
      isLoadingOrders: false,
      error: null,
      
      // 账户管理
      loadSupportedExchanges: async () => {
        try {
          set({ isLoading: true, error: null })
          const exchanges = await tradingApi.getSupportedExchanges()
          set({ supportedExchanges: exchanges, isLoading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load exchanges',
            isLoading: false 
          })
        }
      },
      
      loadAccountBalance: async (exchange: string) => {
        try {
          set({ isLoading: true, error: null })
          const account = await tradingApi.getAccountBalance(exchange)
          set(state => ({
            accounts: { ...state.accounts, [exchange]: account },
            isLoading: false
          }))
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load account balance',
            isLoading: false 
          })
        }
      },
      
      loadAvailableSymbols: async (exchange: string) => {
        try {
          const symbols = await tradingApi.getSymbols(exchange)
          set({ availableSymbols: symbols })
        } catch (error) {
          console.error('Failed to load symbols:', error)
        }
      },
      
      switchExchange: (exchange: string) => {
        set({ selectedExchange: exchange })
        // 自动加载新交易所的数据
        get().loadAccountBalance(exchange)
        get().loadAvailableSymbols(exchange)
        get().loadPositions(exchange)
      },
      
      // 订单管理
      createOrder: async (orderData: OrderRequest) => {
        try {
          set({ isPlacingOrder: true, error: null })
          const order = await tradingApi.createOrder(orderData)
          
          set(state => ({
            orders: [order, ...state.orders],
            activeOrders: order.status === 'filled' ? state.activeOrders : [order, ...state.activeOrders],
            isPlacingOrder: false
          }))
          
          // 刷新相关数据
          get().loadPositions()
          get().loadAccountBalance(orderData.exchange)
          
          return order
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to create order',
            isPlacingOrder: false 
          })
          return null
        }
      },
      
      loadOrders: async (filters = {}) => {
        try {
          set({ isLoadingOrders: true, error: null })
          const orders = await tradingApi.getOrders(filters)
          
          const activeOrders = orders.filter(order => 
            !['filled', 'canceled', 'rejected', 'failed'].includes(order.status)
          )
          const orderHistory = orders.filter(order => 
            ['filled', 'canceled', 'rejected', 'failed'].includes(order.status)
          )
          
          set({ 
            orders, 
            activeOrders, 
            orderHistory,
            isLoadingOrders: false 
          })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load orders',
            isLoadingOrders: false 
          })
        }
      },
      
      cancelOrder: async (orderId: string) => {
        try {
          set({ isLoading: true, error: null })
          await tradingApi.cancelOrder(orderId)
          
          // 更新本地订单状态
          set(state => ({
            orders: state.orders.map(order => 
              order.id === orderId ? { ...order, status: 'canceled' as const } : order
            ),
            activeOrders: state.activeOrders.filter(order => order.id !== orderId),
            isLoading: false
          }))
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to cancel order',
            isLoading: false 
          })
        }
      },
      
      refreshOrder: async (orderId: string) => {
        try {
          const order = await tradingApi.getOrder(orderId)
          set(state => ({
            orders: state.orders.map(o => o.id === orderId ? order : o),
            activeOrders: state.activeOrders.map(o => o.id === orderId ? order : o)
          }))
        } catch (error) {
          console.error('Failed to refresh order:', error)
        }
      },
      
      loadOrderStatistics: async (days = 30) => {
        try {
          const stats = await tradingApi.getOrderStatistics(days)
          set({ orderStats: stats })
        } catch (error) {
          console.error('Failed to load order statistics:', error)
        }
      },
      
      // 持仓管理
      loadPositions: async (exchange?: string) => {
        try {
          set({ isLoadingPositions: true, error: null })
          const positions = await tradingApi.getPositions(exchange)
          
          // 计算总投资组合价值和盈亏
          const totalPortfolioValue = positions.reduce((sum, pos) => sum + pos.current_value, 0)
          const totalUnrealizedPnL = positions.reduce((sum, pos) => sum + pos.unrealized_pnl, 0)
          const totalRealizedPnL = positions.reduce((sum, pos) => sum + pos.realized_pnl, 0)
          
          set({ 
            positions,
            totalPortfolioValue,
            totalUnrealizedPnL,
            totalRealizedPnL,
            isLoadingPositions: false 
          })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load positions',
            isLoadingPositions: false 
          })
        }
      },
      
      refreshPositions: async () => {
        const { selectedExchange } = get()
        await get().loadPositions(selectedExchange)
      },
      
      calculatePositionPnL: async (symbol: string, exchange: string, currentPrice: number) => {
        try {
          const positionPnL = await tradingApi.getPositionPnL(symbol, exchange, currentPrice)
          
          set(state => ({
            positions: state.positions.map(pos => 
              pos.symbol === symbol && pos.exchange === exchange ? positionPnL : pos
            )
          }))
        } catch (error) {
          console.error('Failed to calculate position PnL:', error)
        }
      },
      
      // 交易统计
      loadTradingSummary: async (days = 30) => {
        try {
          set({ isLoading: true, error: null })
          const summary = await tradingApi.getTradingSummary(days)
          set({ tradingSummary: summary, isLoading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load trading summary',
            isLoading: false 
          })
        }
      },
      
      loadDailyPnL: async (days = 30) => {
        try {
          const dailyPnL = await tradingApi.getDailyPnL(days)
          set({ dailyPnLData: dailyPnL })
        } catch (error) {
          console.error('Failed to load daily PnL:', error)
        }
      },
      
      loadRecentTrades: async (filters = {}) => {
        try {
          const trades = await tradingApi.getTrades({ ...filters, limit: 50 })
          set({ recentTrades: trades })
        } catch (error) {
          console.error('Failed to load recent trades:', error)
        }
      },
      
      // 交易会话
      createTradingSession: async (sessionData: any) => {
        try {
          set({ isLoading: true, error: null })
          const session = await tradingApi.createTradingSession(sessionData)
          
          set(state => ({
            tradingSessions: [session, ...state.tradingSessions],
            isLoading: false
          }))
          
          return session
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to create trading session',
            isLoading: false 
          })
          return null
        }
      },
      
      loadTradingSessions: async () => {
        try {
          const sessions = await tradingApi.getTradingSessions()
          const activeSessions = sessions.filter(s => s.status === 'active')
          
          set({ 
            tradingSessions: sessions,
            activeSessions
          })
        } catch (error) {
          console.error('Failed to load trading sessions:', error)
        }
      },
      
      startTradingSession: async (sessionId: string) => {
        try {
          set({ isLoading: true, error: null })
          await tradingApi.startTradingSession(sessionId)
          
          // 更新本地会话状态
          set(state => ({
            tradingSessions: state.tradingSessions.map(session =>
              session.id === sessionId ? { ...session, status: 'active' as const } : session
            ),
            isLoading: false
          }))
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to start trading session',
            isLoading: false 
          })
        }
      },
      
      stopTradingSession: async (sessionId: string) => {
        try {
          set({ isLoading: true, error: null })
          await tradingApi.stopTradingSession(sessionId)
          
          // 更新本地会话状态
          set(state => ({
            tradingSessions: state.tradingSessions.map(session =>
              session.id === sessionId ? { ...session, status: 'stopped' as const } : session
            ),
            isLoading: false
          }))
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to stop trading session',
            isLoading: false 
          })
        }
      },
      
      // 交易表单
      updateTradingForm: (field: keyof TradingForm, value: string) => {
        set(state => ({
          tradingForm: { ...state.tradingForm, [field]: value }
        }))
        
        // 自动计算金额
        if (field === 'price' || field === 'quantity') {
          get().calculateOrderAmount()
        }
      },
      
      resetTradingForm: () => {
        set({ tradingForm: defaultTradingForm, lastRiskAssessment: null })
      },
      
      calculateOrderAmount: () => {
        const { tradingForm } = get()
        const { price, quantity } = tradingForm
        
        if (price && quantity) {
          const amount = (parseFloat(price) * parseFloat(quantity)).toFixed(2)
          set(state => ({
            tradingForm: { ...state.tradingForm, amount }
          }))
        }
      },
      
      validateOrder: async () => {
        try {
          const { tradingForm } = get()
          
          if (!tradingForm.quantity || !tradingForm.price) {
            return null
          }
          
          const orderData: OrderRequest = {
            exchange: tradingForm.exchange,
            symbol: tradingForm.symbol,
            order_type: tradingForm.order_type,
            side: tradingForm.side,
            amount: parseFloat(tradingForm.quantity),
            price: tradingForm.order_type === 'limit' ? parseFloat(tradingForm.price) : undefined
          }
          
          const assessment = await tradingApi.validateOrder(orderData)
          set({ lastRiskAssessment: assessment })
          
          return assessment
        } catch (error) {
          console.error('Failed to validate order:', error)
          return null
        }
      },
      
      // UI控制
      setSelectedTimeframe: (timeframe: string) => {
        set({ selectedTimeframe: timeframe })
      },
      
      toggleAdvancedOptions: () => {
        set(state => ({ showAdvancedOptions: !state.showAdvancedOptions }))
      },
      
      // 状态管理
      setLoading: (loading: boolean) => set({ isLoading: loading }),
      setError: (error: string | null) => set({ error }),
      clearError: () => set({ error: null }),
      
      reset: () => set({
        accounts: {},
        orders: [],
        activeOrders: [],
        orderHistory: [],
        positions: [],
        tradingSessions: [],
        activeSessions: [],
        tradingForm: defaultTradingForm,
        lastRiskAssessment: null,
        isLoading: false,
        isPlacingOrder: false,
        isLoadingPositions: false,
        isLoadingOrders: false,
        error: null
      })
    }),
    {
      name: 'trading-store',
      // 只持久化表单状态和用户偏好
      partialize: (state) => ({
        selectedExchange: state.selectedExchange,
        tradingForm: state.tradingForm,
        selectedTimeframe: state.selectedTimeframe,
        showAdvancedOptions: state.showAdvancedOptions
      })
    }
  )
)

// 便捷的选择器hooks
export const useTradingAccounts = () => useTradingStore(state => ({
  accounts: state.accounts,
  selectedExchange: state.selectedExchange,
  supportedExchanges: state.supportedExchanges,
  switchExchange: state.switchExchange,
  loadAccountBalance: state.loadAccountBalance,
  loadSupportedExchanges: state.loadSupportedExchanges
}))

export const useTradingOrders = () => useTradingStore(state => ({
  orders: state.orders,
  activeOrders: state.activeOrders,
  orderHistory: state.orderHistory,
  orderStats: state.orderStats,
  isLoadingOrders: state.isLoadingOrders,
  isPlacingOrder: state.isPlacingOrder,
  createOrder: state.createOrder,
  loadOrders: state.loadOrders,
  cancelOrder: state.cancelOrder,
  loadOrderStatistics: state.loadOrderStatistics
}))

export const useTradingPositions = () => useTradingStore(state => ({
  positions: state.positions,
  totalPortfolioValue: state.totalPortfolioValue,
  totalUnrealizedPnL: state.totalUnrealizedPnL,
  totalRealizedPnL: state.totalRealizedPnL,
  isLoadingPositions: state.isLoadingPositions,
  loadPositions: state.loadPositions,
  refreshPositions: state.refreshPositions
}))

export const useTradingForm = () => useTradingStore(state => ({
  tradingForm: state.tradingForm,
  lastRiskAssessment: state.lastRiskAssessment,
  availableSymbols: state.availableSymbols,
  updateTradingForm: state.updateTradingForm,
  resetTradingForm: state.resetTradingForm,
  validateOrder: state.validateOrder,
  loadAvailableSymbols: state.loadAvailableSymbols
}))

export const useTradingStatistics = () => useTradingStore(state => ({
  tradingSummary: state.tradingSummary,
  dailyPnLData: state.dailyPnLData,
  recentTrades: state.recentTrades,
  loadTradingSummary: state.loadTradingSummary,
  loadDailyPnL: state.loadDailyPnL,
  loadRecentTrades: state.loadRecentTrades
}))

export const useTradingSessions = () => useTradingStore(state => ({
  tradingSessions: state.tradingSessions,
  activeSessions: state.activeSessions,
  createTradingSession: state.createTradingSession,
  loadTradingSessions: state.loadTradingSessions,
  startTradingSession: state.startTradingSession,
  stopTradingSession: state.stopTradingSession
}))