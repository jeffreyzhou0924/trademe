/**
 * 实盘交易API接口
 * 对接后端交易服务的完整API
 */

import { tradingServiceClient, handleApiResponse, handleApiError } from './client'

// 交易相关类型定义
export interface TradingAccount {
  user_id: number
  exchange: string
  api_key_configured: boolean
  balance: {
    [currency: string]: {
      total: number
      free: number
      used: number
    }
  }
  last_updated: string
}

export interface OrderRequest {
  exchange: string
  symbol: string
  order_type: 'market' | 'limit'
  side: 'buy' | 'sell'
  amount: number
  price?: number
}

export interface Order {
  id: string
  user_id: number
  exchange: string
  symbol: string
  side: 'buy' | 'sell'
  order_type: 'market' | 'limit'
  quantity: number
  price?: number
  filled_quantity: number
  remaining_quantity: number
  avg_fill_price: number
  status: 'pending' | 'submitted' | 'open' | 'filled' | 'canceled' | 'rejected' | 'failed'
  exchange_order_id?: string
  created_at: string
  updated_at: string
  fees: number
  error_message?: string
}

export interface Position {
  symbol: string
  exchange: string
  quantity: number
  avg_cost: number
  total_cost: number
  current_value: number
  unrealized_pnl: number
  realized_pnl: number
  total_pnl: number
  pnl_percent: number
  trade_count: number
  first_trade_at: string
  last_trade_at: string
}

export interface TradingSummary {
  period_days: number
  total_trades: number
  buy_trades: number
  sell_trades: number
  total_volume: number
  total_fees: number
  profit_trades: number
  loss_trades: number
  win_rate: number
  total_pnl: number
  avg_trade_size: number
  largest_win: number
  largest_loss: number
  trading_symbols: string[]
  exchanges_used: string[]
}

export interface DailyPnL {
  date: string
  trades_count: number
  volume: number
  fees: number
  pnl: number
  cumulative_pnl: number
}

export interface TradingSession {
  id: string
  user_id: number
  strategy_id?: number
  exchange: string
  symbols: string[]
  status: 'inactive' | 'active' | 'paused' | 'stopping' | 'stopped' | 'error'
  execution_mode: 'manual' | 'semi_auto' | 'full_auto'
  max_daily_trades: number
  max_open_positions: number
  total_trades: number
  daily_pnl: number
  created_at: string
  started_at?: string
  error_message?: string
}

export interface OrderStatistics {
  period_days: number
  active_orders_count: number
  total_orders: number
  filled_orders: number
  canceled_orders: number
  failed_orders: number
  fill_rate: number
  total_volume: number
  total_fees: number
  symbols_traded: string[]
  exchanges_used: string[]
  avg_order_size: number
}

export interface RiskAssessment {
  approved: boolean
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  violations: string[]
  warnings: string[]
  suggested_position_size?: number
  max_allowed_size?: number
}

/**
 * 实盘交易API服务类
 */
export const tradingApi = {
  // 账户管理
  async getAccountBalance(exchange: string): Promise<TradingAccount> {
    try {
      const response = await tradingServiceClient.get(`/trading/accounts/${exchange}/balance`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getSupportedExchanges(): Promise<string[]> {
    try {
      const response = await tradingServiceClient.get('/trading/exchanges')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getSymbols(exchange: string): Promise<string[]> {
    try {
      const response = await tradingServiceClient.get(`/trading/exchanges/${exchange}/symbols`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 订单管理
  async createOrder(orderData: OrderRequest): Promise<Order> {
    try {
      const response = await tradingServiceClient.post('/trading/orders', orderData)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getOrders(params?: {
    exchange?: string
    symbol?: string
    status?: string
    limit?: number
    offset?: number
  }): Promise<Order[]> {
    try {
      const response = await tradingServiceClient.get('/trading/orders', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getOrder(orderId: string): Promise<Order> {
    try {
      const response = await tradingServiceClient.get(`/trading/orders/${orderId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async cancelOrder(orderId: string): Promise<boolean> {
    try {
      const response = await tradingServiceClient.delete(`/trading/orders/${orderId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getOrderStatistics(days: number = 30): Promise<OrderStatistics> {
    try {
      const response = await tradingServiceClient.get(`/trading/orders/statistics?days=${days}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 持仓管理
  async getPositions(exchange?: string): Promise<Position[]> {
    try {
      const url = exchange ? `/trading/positions?exchange=${exchange}` : '/trading/positions'
      const response = await tradingServiceClient.get(url)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getPositionPnL(symbol: string, exchange: string, currentPrice: number): Promise<Position> {
    try {
      const response = await tradingServiceClient.get(`/trading/positions/${exchange}/${symbol}/pnl`, {
        params: { current_price: currentPrice }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 交易统计
  async getTradingSummary(days: number = 30): Promise<TradingSummary> {
    try {
      const response = await tradingServiceClient.get(`/trading/summary?days=${days}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getDailyPnL(days: number = 30): Promise<DailyPnL[]> {
    try {
      const response = await tradingServiceClient.get(`/trading/daily-pnl?days=${days}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getTrades(params?: {
    exchange?: string
    symbol?: string
    trade_type?: string
    start_date?: string
    end_date?: string
    limit?: number
    offset?: number
  }): Promise<any[]> {
    try {
      const response = await tradingServiceClient.get('/trading/trades', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 交易会话管理
  async createTradingSession(sessionData: {
    exchange: string
    symbols: string[]
    strategy_id?: number
    execution_mode?: 'manual' | 'semi_auto' | 'full_auto'
    max_daily_trades?: number
    max_open_positions?: number
  }): Promise<TradingSession> {
    try {
      const response = await tradingServiceClient.post('/trading/sessions', sessionData)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getTradingSessions(): Promise<TradingSession[]> {
    try {
      const response = await tradingServiceClient.get('/trading/sessions')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async startTradingSession(sessionId: string): Promise<boolean> {
    try {
      const response = await tradingServiceClient.post(`/trading/sessions/${sessionId}/start`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async stopTradingSession(sessionId: string): Promise<boolean> {
    try {
      const response = await tradingServiceClient.post(`/trading/sessions/${sessionId}/stop`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 风险管理
  async validateOrder(orderData: OrderRequest): Promise<RiskAssessment> {
    try {
      const response = await tradingServiceClient.post('/trading/risk/validate-order', orderData)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getPortfolioRisk(): Promise<{
    total_value: number
    unrealized_pnl: number
    daily_pnl: number
    var_95: number
    max_drawdown: number
    position_count: number
    risk_score: number
    concentration_risk: number
  }> {
    try {
      const response = await tradingServiceClient.get('/trading/risk/portfolio')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 实时数据
  async getMarketData(exchange: string, symbol: string, timeframe: string, limit: number = 100): Promise<any[]> {
    try {
      const response = await tradingServiceClient.get('/trading/market-data', {
        params: { exchange, symbol, timeframe, limit }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  async getTradingFees(exchange: string): Promise<{
    exchange: string
    maker: number
    taker: number
    percentage: boolean
    tierBased: boolean
  }> {
    try {
      const response = await tradingServiceClient.get(`/trading/fees/${exchange}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}