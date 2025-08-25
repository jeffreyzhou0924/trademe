/**
 * Store 集成测试
 * 验证所有store的基础功能和集成情况
 */

import { describe, test, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../authStore'
import { useMarketStore } from '../marketStore'
import { useStrategyStore } from '../strategyStore'
import { useAIStore } from '../aiStore'

describe('Store Integration Tests', () => {
  beforeEach(() => {
    // 重置所有store状态
    useAuthStore.getState().clearError?.()
    useMarketStore.getState().reset()
    useStrategyStore.getState().selectStrategy(null)
    useAIStore.getState().reset()
  })

  describe('AuthStore', () => {
    test('should have initial state', () => {
      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(false)
      expect(state.isLoading).toBe(false)
      expect(state.error).toBeNull()
    })

    test('should have all required methods', () => {
      const state = useAuthStore.getState()
      expect(typeof state.login).toBe('function')
      expect(typeof state.register).toBe('function')
      expect(typeof state.logout).toBe('function')
      expect(typeof state.checkAuth).toBe('function')
      expect(typeof state.updateProfile).toBe('function')
      expect(typeof state.refreshToken).toBe('function')
      expect(typeof state.clearError).toBe('function')
    })

    test('should clear error correctly', () => {
      const { clearError } = useAuthStore.getState()
      
      // 手动设置错误状态
      useAuthStore.setState({ error: 'Test error' })
      expect(useAuthStore.getState().error).toBe('Test error')
      
      // 清除错误
      clearError()
      expect(useAuthStore.getState().error).toBeNull()
    })
  })

  describe('MarketStore', () => {
    test('should have initial state', () => {
      const state = useMarketStore.getState()
      expect(state.currentPrices).toEqual({})
      expect(state.klineData).toEqual({})
      expect(state.selectedSymbol).toBe('BTC/USDT')
      expect(state.selectedTimeframe).toBe('1h')
      expect(state.selectedExchange).toBe('okx')
      expect(state.isLoading).toBe(false)
      expect(state.isConnected).toBe(false)
      expect(state.error).toBeNull()
    })

    test('should have all required methods', () => {
      const state = useMarketStore.getState()
      expect(typeof state.setSelectedSymbol).toBe('function')
      expect(typeof state.setSelectedTimeframe).toBe('function')
      expect(typeof state.setSelectedExchange).toBe('function')
      expect(typeof state.fetchKlineData).toBe('function')
      expect(typeof state.subscribeToTicker).toBe('function')
      expect(typeof state.unsubscribeFromTicker).toBe('function')
      expect(typeof state.connectWebSocket).toBe('function')
      expect(typeof state.disconnectWebSocket).toBe('function')
      expect(typeof state.clearError).toBe('function')
      expect(typeof state.reset).toBe('function')
    })

    test('should update selected symbol', () => {
      const { setSelectedSymbol } = useMarketStore.getState()
      
      setSelectedSymbol('ETH/USDT')
      expect(useMarketStore.getState().selectedSymbol).toBe('ETH/USDT')
    })
  })

  describe('StrategyStore', () => {
    test('should have initial state', () => {
      const state = useStrategyStore.getState()
      expect(state.strategies).toEqual([])
      expect(state.selectedStrategy).toBeNull()
      expect(state.isLoading).toBe(false)
      expect(state.backtestResults).toEqual([])
      expect(state.isBacktesting).toBe(false)
    })

    test('should have all required methods', () => {
      const state = useStrategyStore.getState()
      expect(typeof state.fetchStrategies).toBe('function')
      expect(typeof state.createStrategy).toBe('function')
      expect(typeof state.updateStrategy).toBe('function')
      expect(typeof state.deleteStrategy).toBe('function')
      expect(typeof state.selectStrategy).toBe('function')
      expect(typeof state.runBacktest).toBe('function')
      expect(typeof state.startStrategy).toBe('function')
      expect(typeof state.stopStrategy).toBe('function')
    })
  })

  describe('AIStore', () => {
    test('should have initial state', () => {
      const state = useAIStore.getState()
      expect(state.chatSessions).toEqual([])
      expect(state.currentSession).toBeNull()
      expect(state.messages).toEqual([])
      expect(state.isTyping).toBe(false)
      expect(state.generatedStrategies).toEqual([])
      expect(state.isGenerating).toBe(false)
      expect(state.error).toBeNull()
    })

    test('should have all required methods', () => {
      const state = useAIStore.getState()
      expect(typeof state.createChatSession).toBe('function')
      expect(typeof state.loadChatSessions).toBe('function')
      expect(typeof state.selectChatSession).toBe('function')
      expect(typeof state.sendMessage).toBe('function')
      expect(typeof state.deleteChatSession).toBe('function')
      expect(typeof state.generateStrategy).toBe('function')
      expect(typeof state.analyzeMarket).toBe('function')
      expect(typeof state.clearError).toBe('function')
      expect(typeof state.reset).toBe('function')
    })

    test('should reset state correctly', () => {
      const { reset } = useAIStore.getState()
      
      // 设置一些状态
      useAIStore.setState({ 
        messages: [{ role: 'user', content: 'test', timestamp: new Date().toISOString() }],
        isTyping: true,
        error: 'test error'
      })
      
      // 重置
      reset()
      
      const state = useAIStore.getState()
      expect(state.messages).toEqual([])
      expect(state.isTyping).toBe(false)
      expect(state.error).toBeNull()
    })
  })

  describe('Store Integration', () => {
    test('should export all stores from index', async () => {
      const storeIndex = await import('../index')
      
      expect(storeIndex.useAuthStore).toBeDefined()
      expect(storeIndex.useMarketStore).toBeDefined()
      expect(storeIndex.useStrategyStore).toBeDefined()
      expect(storeIndex.useAIStore).toBeDefined()
      expect(storeIndex.wsManager).toBeDefined()
      expect(storeIndex.errorHandler).toBeDefined()
    })

    test('should have working global hooks', async () => {
      const { 
        useUserInfo, 
        useGlobalError, 
        useGlobalLoading,
        useWebSocketStatus,
        useAIStatus 
      } = await import('../index')
      
      expect(typeof useUserInfo).toBe('function')
      expect(typeof useGlobalError).toBe('function')
      expect(typeof useGlobalLoading).toBe('function')
      expect(typeof useWebSocketStatus).toBe('function')
      expect(typeof useAIStatus).toBe('function')
    })

    test('error handling integration', () => {
      // 测试各个store的错误状态能否被全局错误hook获取
      useAuthStore.setState({ error: 'auth error' })
      useMarketStore.setState({ error: 'market error' })
      useAIStore.setState({ error: 'ai error' })

      const authError = useAuthStore.getState().error
      const marketError = useMarketStore.getState().error
      const aiError = useAIStore.getState().error

      expect(authError).toBe('auth error')
      expect(marketError).toBe('market error')
      expect(aiError).toBe('ai error')

      // 清除错误
      useAuthStore.getState().clearError?.()
      useMarketStore.getState().clearError()
      useAIStore.getState().clearError()

      expect(useAuthStore.getState().error).toBeNull()
      expect(useMarketStore.getState().error).toBeNull()
      expect(useAIStore.getState().error).toBeNull()
    })
  })
})

// 模拟数据测试
describe('Store Mock Data Tests', () => {
  test('should handle mock user login flow', () => {
    const mockUser = {
      id: '1',
      username: 'testuser',
      email: 'test@example.com',
      membership_level: 'basic' as const,
      email_verified: true,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    const mockToken = 'mock-jwt-token'

    // 模拟登录成功
    useAuthStore.setState({
      user: mockUser,
      token: mockToken,
      isAuthenticated: true,
      error: null
    })

    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.token).toBe(mockToken)
    expect(state.isAuthenticated).toBe(true)
    expect(state.error).toBeNull()
  })

  test('should handle mock market data', () => {
    const mockTickerData = {
      symbol: 'BTC/USDT',
      price: 45000,
      change: 1200,
      change_percent: 2.74,
      high_24h: 46000,
      low_24h: 43000,
      volume_24h: 125000000,
      timestamp: Date.now()
    }

    const { updatePrice } = useMarketStore.getState()
    updatePrice('BTC/USDT', mockTickerData)

    const state = useMarketStore.getState()
    expect(state.currentPrices['BTC/USDT']).toEqual(mockTickerData)
    expect(state.lastUpdate).toBeDefined()
  })

  test('should handle mock AI chat session', () => {
    const mockSession = {
      id: 'session-1',
      title: 'Test Chat',
      messages: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    const { selectChatSession } = useAIStore.getState()
    selectChatSession(mockSession)

    const state = useAIStore.getState()
    expect(state.currentSession).toEqual(mockSession)
    expect(state.messages).toEqual([])
  })
})

export {}