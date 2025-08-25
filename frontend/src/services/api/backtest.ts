import { tradingServiceClient, handleApiResponse, handleApiError } from './client'

export interface BacktestConfig {
  strategy_id: string
  symbol: string
  exchange: string
  start_date: string
  end_date: string
  initial_capital: number
  commission_rate: number
  timeframe: string
}

export interface BacktestResult {
  id: string
  strategy_id: string
  config: BacktestConfig
  status: 'running' | 'completed' | 'failed'
  results?: {
    total_return: number
    max_drawdown: number
    sharpe_ratio: number
    win_rate: number
    total_trades: number
    profit_factor: number
    annual_return: number
    volatility: number
    final_capital: number
    equity_curve: Array<{ timestamp: string; value: number }>
    trade_history: Array<{
      timestamp: string
      side: 'buy' | 'sell'
      price: number
      quantity: number
      pnl: number
    }>
  }
  error_message?: string
  created_at: string
  completed_at?: string
}

export const backtestApi = {
  // 创建回测
  async createBacktest(config: BacktestConfig): Promise<BacktestResult> {
    try {
      const response = await tradingServiceClient.post('/backtests', config)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取回测列表
  async getBacktests(params?: {
    page?: number
    per_page?: number
    strategy_id?: string
    status?: string
  }): Promise<BacktestResult[]> {
    try {
      const response = await tradingServiceClient.get('/backtests', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取单个回测详情
  async getBacktest(id: string): Promise<BacktestResult> {
    try {
      const response = await tradingServiceClient.get(`/backtests/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取回测状态
  async getBacktestStatus(id: string): Promise<{ status: string; progress?: number }> {
    try {
      const response = await tradingServiceClient.get(`/backtests/${id}/status`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 停止运行中的回测
  async stopBacktest(id: string): Promise<{ message: string }> {
    try {
      const response = await tradingServiceClient.post(`/backtests/${id}/stop`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 删除回测
  async deleteBacktest(id: string): Promise<{ message: string }> {
    try {
      const response = await tradingServiceClient.delete(`/backtests/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 下载回测报告
  async downloadBacktestReport(id: string, format: 'pdf' | 'html' | 'csv' = 'html'): Promise<Blob> {
    try {
      const response = await tradingServiceClient.get(`/backtests/${id}/report`, {
        params: { format },
        responseType: 'blob'
      })
      return response.data
    } catch (error) {
      handleApiError(error)
    }
  },

  // 比较多个回测结果
  async compareBacktests(backtestIds: string[]): Promise<{
    comparison: {
      metrics: Record<string, number[]>
      equity_curves: Array<{
        backtest_id: string
        name: string
        data: Array<{ timestamp: string; value: number }>
      }>
    }
  }> {
    try {
      const response = await tradingServiceClient.post('/backtests/compare', {
        backtest_ids: backtestIds
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}