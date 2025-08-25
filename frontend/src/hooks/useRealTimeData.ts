/**
 * 实时数据同步Hook
 * 集成WebSocket与状态管理，提供实时数据更新
 */

import { useEffect, useCallback, useRef } from 'react'
import { wsManager } from '@/utils/websocketManager'
import { useTradingStore } from '@/store/tradingStore'
import { useMarketStore } from '@/store/marketStore'
import { useAuthStore } from '@/store/authStore'

interface RealTimeConfig {
  enableMarketData?: boolean
  enableTradingUpdates?: boolean
  enableOrderUpdates?: boolean
  enablePositionUpdates?: boolean
  symbols?: string[]
}

export const useRealTimeData = (config: RealTimeConfig = {}) => {
  const {
    enableMarketData = true,
    enableTradingUpdates = true,
    enableOrderUpdates = true,
    enablePositionUpdates = true,
    symbols = ['BTC/USDT', 'ETH/USDT']
  } = config

  const { user, token } = useAuthStore()
  const isConnectedRef = useRef(false)
  const subscriptionsRef = useRef<Set<string>>(new Set())

  // Trading store actions
  const {
    loadOrders,
    loadPositions,
    refreshPositions,
    selectedExchange
  } = useTradingStore()

  // Market store actions
  const { updatePrice } = useMarketStore()

  // WebSocket连接管理
  const connectWebSocket = useCallback(() => {
    if (!user || !token || isConnectedRef.current) {
      return
    }

    const handlers = {
      onOpen: () => {
        console.log('🟢 实时数据连接已建立')
        isConnectedRef.current = true

        // 注意：认证现在由WebSocketManager自动处理
        // 等待认证成功后再开始订阅
      },

      onMessage: (data: any) => {
        handleWebSocketMessage(data)
      },

      onError: (error: Event) => {
        console.error('❌ WebSocket连接错误:', error)
        isConnectedRef.current = false
      },

      onClose: () => {
        console.log('🔴 实时数据连接已断开')
        isConnectedRef.current = false
        subscriptionsRef.current.clear()
      }
    }

    // 使用新的认证方式连接，传入token参数
    wsManager.connect('main', '/realtime', handlers, token)
  }, [user, token, enableMarketData, enableTradingUpdates, symbols])

  // 消息处理
  const handleWebSocketMessage = useCallback((data: any) => {
    try {
      const { type, payload } = data

      switch (type) {
        case 'auth_success':
          console.log('✅ 实时数据认证成功')
          // 认证成功后开始订阅
          setTimeout(() => {
            // 订阅市场数据
            if (enableMarketData && symbols.length > 0) {
              symbols.forEach(symbol => {
                wsManager.send('main', {
                  type: 'subscribe_market',
                  symbol,
                  interval: '1m'
                })
                subscriptionsRef.current.add(`market_${symbol}`)
              })
            }

            // 订阅交易更新
            if (enableTradingUpdates) {
              wsManager.send('main', {
                type: 'subscribe_trading',
                user_id: user.id
              })
              subscriptionsRef.current.add('trading_updates')
            }
          }, 100) // 延迟100ms确保认证完全完成
          break

        case 'auth_failed':
          console.error('❌ 实时数据认证失败:', payload?.message || '未知错误')
          // 认证失败时断开连接
          wsManager.disconnect('main')
          isConnectedRef.current = false
          break

        case 'market_data':
          if (enableMarketData) {
            handleMarketDataUpdate(payload)
          }
          break

        case 'ticker_update':
          if (enableMarketData) {
            handleTickerUpdate(payload)
          }
          break

        case 'order_update':
          if (enableOrderUpdates) {
            handleOrderUpdate(payload)
          }
          break

        case 'position_update':
          if (enablePositionUpdates) {
            handlePositionUpdate(payload)
          }
          break

        case 'trade_executed':
          if (enableTradingUpdates) {
            handleTradeExecuted(payload)
          }
          break

        case 'account_update':
          if (enableTradingUpdates) {
            handleAccountUpdate(payload)
          }
          break

        case 'pong':
          // 心跳响应，不需要处理
          break

        default:
          console.log('未知消息类型:', type, payload)
      }
    } catch (error) {
      console.error('处理WebSocket消息失败:', error)
    }
  }, [enableMarketData, enableOrderUpdates, enablePositionUpdates, enableTradingUpdates])

  // 市场数据更新
  const handleMarketDataUpdate = useCallback((payload: any) => {
    const { symbol, kline, timestamp } = payload
    
    updatePrice(symbol, {
      symbol,
      price: parseFloat(kline.close),
      change: 0, // K线数据中没有变化信息
      change_percent: 0,
      high_24h: parseFloat(kline.high),
      low_24h: parseFloat(kline.low),
      volume_24h: parseFloat(kline.volume),
      timestamp
    })
  }, [updatePrice])

  // 价格更新
  const handleTickerUpdate = useCallback((payload: any) => {
    const { symbol, price, change, changePercent, volume24h } = payload
    
    updatePrice(symbol, {
      symbol,
      price: parseFloat(price),
      change: parseFloat(change),
      change_percent: parseFloat(changePercent),
      high_24h: 0, // ticker数据中没有这些信息，使用默认值
      low_24h: 0,
      volume_24h: parseFloat(volume24h),
      timestamp: Date.now()
    })
  }, [updatePrice])

  // 订单状态更新
  const handleOrderUpdate = useCallback((payload: any) => {
    const { order_id, status, filled_quantity, remaining_quantity } = payload
    
    // 更新本地订单状态
    useTradingStore.setState(state => ({
      orders: state.orders.map(order =>
        order.id === order_id
          ? {
              ...order,
              status,
              filled_quantity: parseFloat(filled_quantity),
              remaining_quantity: parseFloat(remaining_quantity),
              updated_at: new Date().toISOString()
            }
          : order
      ),
      activeOrders: state.activeOrders.map(order =>
        order.id === order_id
          ? {
              ...order,
              status,
              filled_quantity: parseFloat(filled_quantity),
              remaining_quantity: parseFloat(remaining_quantity),
              updated_at: new Date().toISOString()
            }
          : order
      ).filter(order => !['filled', 'canceled', 'rejected', 'failed'].includes(order.status))
    }))
  }, [])

  // 持仓更新
  const handlePositionUpdate = useCallback((payload: any) => {
    const { symbol, exchange, quantity, unrealized_pnl, avg_cost } = payload
    
    useTradingStore.setState(state => ({
      positions: state.positions.map(position =>
        position.symbol === symbol && position.exchange === exchange
          ? {
              ...position,
              quantity: parseFloat(quantity),
              unrealized_pnl: parseFloat(unrealized_pnl),
              avg_cost: parseFloat(avg_cost),
              current_value: parseFloat(quantity) * parseFloat(avg_cost) + parseFloat(unrealized_pnl)
            }
          : position
      )
    }))
  }, [])

  // 交易执行通知
  const handleTradeExecuted = useCallback((payload: any) => {
    const { trade } = payload
    
    // 刷新相关数据
    setTimeout(() => {
      loadOrders()
      refreshPositions()
    }, 1000)

    // 显示通知
    console.log('🎯 交易执行:', trade)
  }, [loadOrders, refreshPositions])

  // 账户更新
  const handleAccountUpdate = useCallback((payload: any) => {
    const { exchange, balance } = payload
    
    useTradingStore.setState(state => ({
      accounts: {
        ...state.accounts,
        [exchange]: {
          ...state.accounts[exchange],
          balance,
          last_updated: new Date().toISOString()
        }
      }
    }))
  }, [])

  // 订阅管理
  const subscribe = useCallback((channel: string, params?: any) => {
    if (!isConnectedRef.current) {
      console.warn('WebSocket未连接，无法订阅:', channel)
      return
    }

    wsManager.send('main', {
      type: 'subscribe',
      channel,
      ...params
    })
    
    subscriptionsRef.current.add(channel)
  }, [])

  const unsubscribe = useCallback((channel: string) => {
    if (!isConnectedRef.current) {
      return
    }

    wsManager.send('main', {
      type: 'unsubscribe',
      channel
    })
    
    subscriptionsRef.current.delete(channel)
  }, [])

  // 添加新交易对订阅
  const subscribeToSymbol = useCallback((symbol: string, interval: string = '1m') => {
    subscribe('market_data', { symbol, interval })
    subscribe('ticker', { symbol })
  }, [subscribe])

  // 移除交易对订阅
  const unsubscribeFromSymbol = useCallback((symbol: string) => {
    unsubscribe(`market_${symbol}`)
    unsubscribe(`ticker_${symbol}`)
  }, [unsubscribe])

  // 连接状态
  const isConnected = isConnectedRef.current

  // 初始化连接
  useEffect(() => {
    if (user && token) {
      connectWebSocket()
    }

    return () => {
      if (isConnectedRef.current) {
        wsManager.disconnect('main')
        isConnectedRef.current = false
        subscriptionsRef.current.clear()
      }
    }
  }, [connectWebSocket])

  // 监听交易所变化，重新订阅
  useEffect(() => {
    if (isConnected && enableTradingUpdates) {
      wsManager.send('main', {
        type: 'subscribe_trading',
        exchange: selectedExchange,
        user_id: user?.id
      })
    }
  }, [selectedExchange, isConnected, enableTradingUpdates, user?.id])

  return {
    isConnected,
    subscribe,
    unsubscribe,
    subscribeToSymbol,
    unsubscribeFromSymbol,
    subscriptions: Array.from(subscriptionsRef.current)
  }
}

export default useRealTimeData