import { tradingServiceClient, handleApiResponse, handleApiError } from './client'
import type { 
  Strategy, 
  CreateStrategyData, 
  BacktestConfig, 
  BacktestResult,
  TradeRecord
} from '@/types/strategy'
import type { PaginatedResponse } from '@/types/api'

export const strategyApi = {
  // 获取策略列表
  async getStrategies(params?: {
    page?: number
    per_page?: number
    status?: string
    search?: string
    active_only?: boolean
  }): Promise<{
    strategies: Strategy[]
    total: number
    skip: number
    limit: number
  }> {
    try {
      const response = await tradingServiceClient.get('/strategies', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取单个策略详情
  async getStrategy(id: string): Promise<Strategy> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 创建策略
  async createStrategy(data: CreateStrategyData): Promise<Strategy> {
    try {
      const response = await tradingServiceClient.post('/strategies', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 更新策略
  async updateStrategy(id: string, data: Partial<Strategy>): Promise<Strategy> {
    try {
      const response = await tradingServiceClient.put(`/strategies/${id}`, data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 删除策略
  async deleteStrategy(id: string): Promise<{ message: string }> {
    try {
      const response = await tradingServiceClient.delete(`/strategies/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 启动策略
  async startStrategy(id: string): Promise<{ message: string }> {
    try {
      const response = await tradingServiceClient.post(`/strategies/${id}/start`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 停止策略
  async stopStrategy(id: string): Promise<{ message: string }> {
    try {
      const response = await tradingServiceClient.post(`/strategies/${id}/stop`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 暂停策略
  async pauseStrategy(id: string): Promise<{ message: string }> {
    try {
      const response = await tradingServiceClient.post(`/strategies/${id}/pause`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 运行回测
  async runBacktest(strategyId: string, config: BacktestConfig): Promise<BacktestResult> {
    try {
      const response = await tradingServiceClient.post(`/strategies/${strategyId}/backtest`, config)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取回测结果列表
  async getBacktestResults(strategyId: string): Promise<BacktestResult[]> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/backtests`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取单个回测结果
  async getBacktestResult(strategyId: string, backtestId: string): Promise<BacktestResult> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/backtests/${backtestId}`)
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
  }): Promise<PaginatedResponse<TradeRecord>> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/trades`, { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取策略性能统计
  async getStrategyPerformance(strategyId: string, period?: string): Promise<{
    total_return: number
    max_drawdown: number
    sharpe_ratio: number
    win_rate: number
    total_trades: number
    avg_trade_duration: number
    profit_factor: number
    equity_curve: Array<{ date: string; value: number }>
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

  // 复制策略
  async cloneStrategy(id: string, name: string): Promise<Strategy> {
    try {
      const response = await tradingServiceClient.post(`/strategies/${id}/clone`, { name })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 导出策略代码
  async exportStrategy(id: string): Promise<{ code: string; name: string }> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${id}/export`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 导入策略代码
  async importStrategy(data: { name: string; code: string; description?: string }): Promise<Strategy> {
    try {
      const response = await tradingServiceClient.post('/strategies/import', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取策略实盘详情
  async getStrategyLiveDetails(strategyId: number): Promise<{
    strategy: Strategy
    live_stats: {
      total_trades: number
      buy_volume: number
      sell_volume: number
      total_fees: number
      profit_loss: number
      profit_percentage: number
      avg_price: number
      first_trade: string | null
      last_trade: string | null
    }
    trades: any[]
    performance: {
      total_return: number
      win_rate: number
      max_drawdown: number
      sharpe_ratio: number
    }
    status: string
  }> {
    try {
      const response = await tradingServiceClient.get(`/strategies/${strategyId}/live-details`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 从AI会话创建策略/指标
  async createStrategyFromAI(data: {
    name: string
    description?: string
    code: string
    parameters?: any
    strategy_type: 'strategy' | 'indicator'
    ai_session_id: string
  }): Promise<Strategy> {
    try {
      const response = await tradingServiceClient.post('/strategies/from-ai', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 根据类型获取策略/指标列表
  async getStrategiesByType(type: 'strategy' | 'indicator', params?: {
    skip?: number
    limit?: number
  }): Promise<{
    strategies: Strategy[]
    total: number
    skip: number
    limit: number
  }> {
    try {
      const response = await tradingServiceClient.get(`/strategies/by-type/${type}`, { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}