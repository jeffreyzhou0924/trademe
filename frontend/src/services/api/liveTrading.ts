import { tradingServiceClient, handleApiResponse, handleApiError } from './client'

// 实盘策略接口
export interface LiveStrategy {
  id: string
  name: string
  description?: string
  trading_pair: string
  exchange: string
  status: 'running' | 'paused' | 'stopped'
  profit_rate: number
  signal_count: number
  created_at: string
  updated_at?: string
  win_rate?: number
  total_trades?: number
  max_drawdown?: number
  sharpe_ratio?: number
  parameters?: Record<string, any>
}

// 实盘策略统计
export interface LiveStrategyStats {
  active_strategies: number
  total_return: number
  max_drawdown: number
  last_trade_time: string
  total_trades: number
  win_rate: number
}

// 实盘策略详情
export interface LiveStrategyDetails extends LiveStrategy {
  total_return: number
  trades: TradeRecord[]
  equity_curve: { date: string; value: number }[]
  daily_stats: DailyStats[]
}

// 交易记录
export interface TradeRecord {
  id: string
  timestamp: string
  side: 'buy' | 'sell'
  price: number
  quantity: number
  profit_rate?: number
  signal: string
  pnl?: number
}

// 日统计
export interface DailyStats {
  date: string
  profit: number
  trades: number
  win_rate: number
}

// 实盘策略操作请求
export interface StrategyActionRequest {
  action: 'start' | 'pause' | 'stop' | 'restart'
  parameters?: Record<string, any>
}

export const liveTradingApi = {
  // 获取实盘策略列表
  async getLiveStrategies(params?: {
    page?: number
    per_page?: number
    status?: string
    exchange?: string
  }): Promise<{
    strategies: LiveStrategy[]
    total: number
    page: number
    per_page: number
  }> {
    try {
      const response = await tradingServiceClient.get('/strategies', { params })
      const data = handleApiResponse(response)
      
      // 将后端数据格式转换为前端格式
      const convertedStrategies: LiveStrategy[] = data.strategies.map((strategy: any) => ({
        id: strategy.id.toString(),
        name: strategy.name,
        description: strategy.description,
        trading_pair: strategy.parameters?.symbol || 'BTC/USDT',
        exchange: strategy.parameters?.exchange || 'binance',
        status: strategy.is_active ? 'running' : 'stopped',
        profit_rate: Math.random() * 20 - 5, // 模拟收益率
        signal_count: Math.floor(Math.random() * 50),
        created_at: strategy.created_at,
        win_rate: Math.random() * 100,
        total_trades: Math.floor(Math.random() * 100),
        parameters: strategy.parameters
      }))
      
      return {
        strategies: convertedStrategies,
        total: data.total,
        page: params?.page || 1,
        per_page: params?.per_page || 20
      }
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取实盘策略统计
  async getLiveStrategyStats(): Promise<LiveStrategyStats> {
    try {
      const response = await tradingServiceClient.get('/trading/stats')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取实盘策略详情
  async getLiveStrategyDetails(strategyId: string): Promise<LiveStrategyDetails> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/live-details`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 执行策略操作
  async executeStrategyAction(strategyId: string, actionRequest: StrategyActionRequest): Promise<{
    success: boolean
    message: string
    new_status?: string
  }> {
    try {
      const response = await tradingServiceClient.post(`/strategies/${strategyId}/action`, actionRequest)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 创建实盘策略
  async createLiveStrategy(strategyData: {
    name: string
    description?: string
    code: string
    trading_pair: string
    exchange: string
    parameters: Record<string, any>
  }): Promise<LiveStrategy> {
    try {
      const response = await tradingServiceClient.post('/strategies', {
        ...strategyData,
        type: 'live'
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 更新策略参数
  async updateStrategyParameters(strategyId: string, parameters: Record<string, any>): Promise<{
    success: boolean
    message: string
  }> {
    try {
      const response = await tradingServiceClient.put(`/strategies/${strategyId}/parameters`, { parameters })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取策略交易记录
  async getStrategyTrades(strategyId: string, params?: {
    page?: number
    per_page?: number
    start_date?: string
    end_date?: string
  }): Promise<{
    trades: TradeRecord[]
    total: number
    page: number
    per_page: number
  }> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/trades`, { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取实盘策略性能
  async getStrategyPerformance(strategyId: string, period?: string): Promise<{
    profit_rate: number
    win_rate: number
    max_drawdown: number
    sharpe_ratio: number
    total_trades: number
    avg_trade_size: number
  }> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/performance`, {
        params: { period }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取用户的实盘策略列表 (新API)
  async getUserLiveStrategies(params?: {
    status?: 'running' | 'paused' | 'stopped'
  }): Promise<LiveStrategy[]> {
    try {
      const response = await tradingServiceClient.get('/trading/live-strategies', { params })
      const strategies = handleApiResponse(response)
      
      // 转换后端数据格式为前端格式
      return strategies.map((strategy: any) => ({
        id: strategy.id.toString(),
        name: strategy.name,
        description: strategy.description || '',
        trading_pair: strategy.parameters?.symbol || 'BTC/USDT',
        exchange: strategy.parameters?.exchange || 'binance',
        status: strategy.status,
        profit_rate: strategy.profit_loss || 0,
        signal_count: strategy.total_trades || 0,
        created_at: strategy.created_at,
        total_trades: strategy.total_trades || 0,
        win_rate: Math.random() * 100, // 模拟胜率，待后端提供
        parameters: strategy.parameters
      }))
    } catch (error) {
      handleApiError(error)
    }
  },

  // 删除已停止的实盘策略
  async deleteLiveStrategy(liveStrategyId: string): Promise<{
    success: boolean
    message: string
    deleted_id: number
  }> {
    try {
      const response = await tradingServiceClient.delete(`/trading/live-strategies/${liveStrategyId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}