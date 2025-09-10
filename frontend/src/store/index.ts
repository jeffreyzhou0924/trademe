// Store统一入口文件
export { useAuthStore } from './authStore'
export { useMarketStore } from './marketStore'
export { useStrategyStore } from './strategyStore'
export { useAIStore } from './aiStore'
export { useThemeStore } from './themeStore'
export { useLanguageStore } from './languageStore'
export { 
  useTradingStore, 
  useTradingAccounts, 
  useTradingOrders, 
  useTradingPositions, 
  useTradingForm, 
  useTradingStatistics, 
  useTradingSessions 
} from './tradingStore'
export { 
  useBacktestStore, 
  useBacktestList, 
  useBacktestCreation, 
  useBacktestComparison, 
  useCurrentBacktest 
} from './backtestStore'

// 类型定义导出
export type { User, LoginCredentials, RegisterData, LoginResponse } from '../types/auth'
export type { MarketData, KlineData, TickerData, OrderBook, TradingPair, Exchange } from '../types/market'
export type { Strategy, CreateStrategyData, TradeRecord } from '../types/strategy'
export type { 
  ChatSession, 
  ChatMessage, 
  StrategyGenerationRequest, 
  GeneratedStrategy,
  MarketAnalysis 
} from '../services/api/ai'
export type {
  TradingAccount,
  OrderRequest,
  Order,
  Position,
  TradingSummary,
  DailyPnL,
  TradingSession,
  OrderStatistics,
  RiskAssessment
} from '../services/api/trading'
export type { BacktestConfig, BacktestResult } from '../services/api/backtest'

// 工具函数导出
export { wsManager } from '../utils/websocketManager'
export { errorHandler, handleError, createRetryHandler, ErrorType } from '../utils/errorHandler'
export type { AppError } from '../utils/errorHandler'

// 全局状态管理hooks
import { useAuthStore } from './authStore'
import { useMarketStore } from './marketStore'
import { useStrategyStore } from './strategyStore'
import { useAIStore } from './aiStore'
import { useTradingStore } from './tradingStore'
import { useBacktestStore } from './backtestStore'
import { wsManager } from '../utils/websocketManager'
import { errorHandler } from '../utils/errorHandler'
import { useEffect } from 'react'

/**
 * 初始化应用状态的Hook
 * 在App组件中调用，负责初始化各种状态和连接
 */
export const useAppInitialization = () => {
  const { checkAuth } = useAuthStore()
  const { loadChatSessions } = useAIStore()
  const { fetchStrategies } = useStrategyStore()
  const { loadSupportedExchanges } = useTradingStore()
  const { fetchBacktests } = useBacktestStore()
  
  useEffect(() => {
    // 应用启动时的初始化逻辑
    const initializeApp = async () => {
      try {
        // 1. 检查用户认证状态
        await checkAuth()
        
        // 2. 如果用户已登录，加载相关数据
        const { isAuthenticated } = useAuthStore.getState()
        if (isAuthenticated) {
          // 并行加载用户数据
          await Promise.allSettled([
            loadChatSessions('developer'),
            fetchStrategies(),
            loadSupportedExchanges(), // 加载支持的交易所
            fetchBacktests({ page: 1, per_page: 10 }) // 加载回测历史
          ])
        }
      } catch (error) {
        console.error('App initialization failed:', error)
      }
    }

    initializeApp()
  }, [checkAuth, loadChatSessions, fetchStrategies, loadSupportedExchanges, fetchBacktests])
}

/**
 * 清理应用状态的Hook
 * 用于用户登出或应用卸载时清理状态
 */
export const useAppCleanup = () => {
  const authStore = useAuthStore()
  const marketStore = useMarketStore()
  const strategyStore = useStrategyStore()
  const aiStore = useAIStore()
  const tradingStore = useTradingStore()
  const backtestStore = useBacktestStore()

  return () => {
    // 断开WebSocket连接
    marketStore.disconnectWebSocket()
    
    // 重置各个store状态
    marketStore.reset()
    aiStore.reset()
    tradingStore.reset()
    backtestStore.reset()
    
    // 不重置auth store，让它自己管理登出逻辑
  }
}

/**
 * 全局错误状态管理Hook
 */
export const useGlobalError = () => {
  const authError = useAuthStore(state => state.error)
  const marketError = useMarketStore(state => state.error)
  const aiError = useAIStore(state => state.error)
  const tradingError = useTradingStore(state => state.error)
  const backtestError = useBacktestStore(state => state.error)
  
  // 获取第一个非空错误
  const globalError = authError || marketError || aiError || tradingError || backtestError || null
  
  const clearGlobalError = () => {
    if (authError) useAuthStore.getState().clearError?.()
    if (marketError) useMarketStore.getState().clearError()
    if (aiError) useAIStore.getState().clearError()
    if (tradingError) useTradingStore.getState().clearError()
    if (backtestError) useBacktestStore.getState().clearError()
  }
  
  return {
    error: globalError,
    clearError: clearGlobalError,
    hasError: !!globalError
  }
}

/**
 * 全局加载状态管理Hook
 */
export const useGlobalLoading = () => {
  const authLoading = useAuthStore(state => state.isLoading)
  const marketLoading = useMarketStore(state => state.isLoading)
  const strategyLoading = useStrategyStore(state => state.isLoading)
  const aiLoading = useAIStore(state => state.isLoading)
  const aiGenerating = useAIStore(state => state.isGenerating)
  const aiAnalyzing = useAIStore(state => state.isAnalyzing)
  const tradingLoading = useTradingStore(state => state.isLoading)
  const placingOrder = useTradingStore(state => state.isPlacingOrder)
  const backtestLoading = useBacktestStore(state => state.loading)
  const creatingBacktest = useBacktestStore(state => state.isCreatingBacktest)
  
  return {
    isLoading: authLoading || marketLoading || strategyLoading || aiLoading || tradingLoading || backtestLoading,
    isGenerating: aiGenerating,
    isAnalyzing: aiAnalyzing,
    isPlacingOrder: placingOrder,
    isCreatingBacktest: creatingBacktest,
    loadingStates: {
      auth: authLoading,
      market: marketLoading,
      strategy: strategyLoading,
      ai: aiLoading,
      aiGenerating,
      aiAnalyzing,
      trading: tradingLoading,
      placingOrder,
      backtest: backtestLoading,
      creatingBacktest
    }
  }
}

/**
 * WebSocket连接状态管理Hook
 */
export const useWebSocketStatus = () => {
  const isConnected = useMarketStore(state => state.isConnected)
  const subscribedTickers = useMarketStore(state => state.subscribedTickers)
  const connectionStats = useMarketStore(state => state.connectionStats)
  
  return {
    isConnected,
    subscribedCount: subscribedTickers.size,
    subscribedTickers: Array.from(subscribedTickers),
    connectionStats,
    refreshStats: useMarketStore.getState().getConnectionStats
  }
}

/**
 * 用户状态快速访问Hook
 */
export const useUserInfo = () => {
  const user = useAuthStore(state => state.user)
  const isAuthenticated = useAuthStore(state => state.isAuthenticated)
  const membershipLevel = user?.membership_level || 'basic'
  
  return {
    user,
    isAuthenticated,
    membershipLevel,
    isPremium: membershipLevel === 'premium' || membershipLevel === 'professional',
    isProfessional: membershipLevel === 'professional'
  }
}

/**
 * AI功能状态快速访问Hook
 */
export const useAIStatus = () => {
  const currentSession = useAIStore(state => state.currentSession)
  const isTyping = useAIStore(state => state.isTyping)
  const isGenerating = useAIStore(state => state.isGenerating)
  const messagesCount = useAIStore(state => state.messages.length)
  const strategiesCount = useAIStore(state => state.generatedStrategies.length)
  
  return {
    hasActiveSession: !!currentSession,
    currentSessionId: currentSession?.session_id,
    isTyping,
    isGenerating,
    messagesCount,
    strategiesCount,
    isAIBusy: isTyping || isGenerating
  }
}

/**
 * 实盘交易状态快速访问Hook
 */
export const useTradingStatus = () => {
  const selectedExchange = useTradingStore(state => state.selectedExchange)
  const activeOrders = useTradingStore(state => state.activeOrders)
  const positions = useTradingStore(state => state.positions)
  const totalPortfolioValue = useTradingStore(state => state.totalPortfolioValue)
  const totalUnrealizedPnL = useTradingStore(state => state.totalUnrealizedPnL)
  const isPlacingOrder = useTradingStore(state => state.isPlacingOrder)
  const activeSessions = useTradingStore(state => state.activeSessions)
  
  return {
    selectedExchange,
    activeOrdersCount: activeOrders.length,
    positionsCount: positions.length,
    hasActivePositions: positions.length > 0,
    totalPortfolioValue,
    totalUnrealizedPnL,
    isPlacingOrder,
    hasActiveSessions: activeSessions.length > 0,
    isTradingActive: activeSessions.some(session => session.status === 'active')
  }
}

/**
 * 回测状态快速访问Hook
 */
export const useBacktestStatus = () => {
  const backtests = useBacktestStore(state => state.backtests)
  const currentBacktest = useBacktestStore(state => state.currentBacktest)
  const runningBacktests = useBacktestStore(state => state.runningBacktests)
  const selectedForComparison = useBacktestStore(state => state.selectedForComparison)
  const isCreatingBacktest = useBacktestStore(state => state.isCreatingBacktest)
  
  const runningCount = Array.from(runningBacktests.values()).filter(
    status => status.status === 'running'
  ).length
  
  return {
    totalBacktests: backtests.length,
    hasCurrentBacktest: !!currentBacktest,
    runningBacktestsCount: runningCount,
    isBacktestRunning: runningCount > 0,
    selectedForComparisonCount: selectedForComparison.length,
    canCompare: selectedForComparison.length >= 2,
    isCreatingBacktest
  }
}

/**
 * 开发模式下的store调试工具
 */
export const useStoreDebugger = () => {
  if (import.meta.env.MODE !== 'development') {
    return null
  }

  return {
    getAllStates: () => ({
      auth: useAuthStore.getState(),
      market: useMarketStore.getState(),
      strategy: useStrategyStore.getState(),
      ai: useAIStore.getState(),
      trading: useTradingStore.getState(),
      backtest: useBacktestStore.getState()
    }),
    resetAllStores: () => {
      useMarketStore.getState().reset()
      useAIStore.getState().reset()
      useTradingStore.getState().reset()
      useBacktestStore.getState().reset()
      // 不重置auth store，避免意外登出
    },
    logStoreStates: () => {
      console.group('📊 Store States')
      console.log('Auth:', useAuthStore.getState())
      console.log('Market:', useMarketStore.getState())
      console.log('Strategy:', useStrategyStore.getState())
      console.log('AI:', useAIStore.getState())
      console.log('Trading:', useTradingStore.getState())
      console.log('Backtest:', useBacktestStore.getState())
      console.groupEnd()
    }
  }
}

// 开发环境下暴露到window对象，便于调试
if (import.meta.env.MODE === 'development') {
  if (typeof window !== 'undefined') {
    ;(window as any).stores = {
      auth: useAuthStore,
      market: useMarketStore,
      strategy: useStrategyStore,
      ai: useAIStore,
      trading: useTradingStore,
      backtest: useBacktestStore,
      wsManager: wsManager,
      errorHandler: errorHandler
    }
  }
}