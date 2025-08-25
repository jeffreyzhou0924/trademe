import { userServiceClient, tradingServiceClient, handleApiResponse, handleApiError } from './client'

// Dashboard数据类型
export interface DashboardStats {
  api_keys: {
    current: number
    limit: number
  }
  live_strategies: {
    current: number
    limit: number
  }
  trading_stats: {
    total_trades: number
    net_amount: number
    avg_trade_size: number
    realized_pnl: number
  }
  monthly_return: number
  membership: {
    level: string
    expires_at: string | null
  }
}

export interface ProfitCurveData {
  timestamp: string
  value: number
}

export interface RecentActivity {
  id: string
  type: 'strategy_created' | 'backtest_completed' | 'trade_executed' | 'ai_chat'
  title: string
  description: string
  timestamp: string
  status: 'success' | 'error' | 'pending'
}

export interface MarketSummary {
  symbol: string
  price: number
  change24h: number
  changePercent24h: number
  volume24h: number
}

export const dashboardApi = {
  // 获取用户统计数据
  async getStats(): Promise<DashboardStats> {
    try {
      const response = await userServiceClient.get('/dashboard/stats')
      return handleApiResponse(response).data
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取最近活动
  async getRecentActivity(): Promise<RecentActivity[]> {
    try {
      const response = await tradingServiceClient.get('/dashboard/activity')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取市场概览
  async getMarketSummary(): Promise<MarketSummary[]> {
    try {
      const response = await tradingServiceClient.get('/dashboard/market-summary')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取资产分布数据
  async getAssetAllocation(): Promise<{ asset: string; value: number; percentage: number }[]> {
    try {
      const response = await tradingServiceClient.get('/dashboard/asset-allocation')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取收益曲线数据
  async getProfitCurve(days: number = 90): Promise<{
    data: ProfitCurveData[]
    is_demo: boolean
    note?: string
  }> {
    try {
      const response = await userServiceClient.get(`/dashboard/profit-curve?days=${days}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },
}