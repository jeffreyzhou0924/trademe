export interface Strategy {
  id: string
  user_id: string
  name: string
  description?: string
  code: string
  parameters: Record<string, any>
  status: 'stopped' | 'running' | 'paused'
  is_active: boolean
  created_at: string
  updated_at: string
  
  // 运行时统计
  total_return?: number
  win_rate?: number
  total_trades?: number
  last_trade_at?: string
}

export interface CreateStrategyData {
  name: string
  description?: string
  code: string
  parameters: Record<string, any>
}

export interface BacktestConfig {
  start_date: string
  end_date: string
  initial_capital: number
  commission_rate: number
  slippage: number
  data_granularity: '1m' | '5m' | '15m' | '1h' | '4h' | '1d'
}

export interface BacktestResult {
  id: string
  strategy_id: string
  user_id: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  avg_trade_duration: number
  profit_factor: number
  results: {
    equity_curve: Array<{ date: string; value: number }>
    trades: TradeRecord[]
    performance_metrics: Record<string, number>
  }
  status: 'RUNNING' | 'COMPLETED' | 'FAILED'
  created_at: string
}

export interface TradeRecord {
  id: string
  strategy_id?: string
  timestamp: string
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: number
  total_amount: number
  fee: number
  pnl?: number
  pnl_percentage?: number
  order_id?: string
  signal?: string
}