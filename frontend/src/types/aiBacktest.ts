/**
 * AI策略回测相关的TypeScript类型定义
 */

// 自动回测配置
export interface AutoBacktestConfig {
  ai_session_id: string
  strategy_code: string
  strategy_name?: string
  auto_config?: boolean
  exchange?: string
  symbols?: string[]
  timeframes?: string[]
  initial_capital?: number
  start_date?: string
  end_date?: string
  fee_rate?: string
}

// 回测进度信息
export interface BacktestProgress {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_step: string
  logs: string[]
  error_message?: string
  started_at: string
  completed_at?: string
  ai_session_id?: string
  strategy_name?: string
  is_ai_strategy: boolean
  estimated_time_remaining?: number
}

// 回测结果
export interface BacktestResults {
  task_id: string
  status: string
  backtest_results: {
    performance_metrics: {
      total_return: number
      sharpe_ratio: number
      max_drawdown: number
      win_rate: number
      total_trades: number
      profit_factor: number
      annual_return?: number
      volatility?: number
    }
    ai_analysis?: {
      score: number
      grade: 'A' | 'B' | 'C' | 'D' | 'F'
      recommendations: string[]
      strengths: string[]
      weaknesses: string[]
      summary: string
    }
    trade_details?: {
      trades: any[]
      daily_returns: number[]
      cumulative_returns: number[]
    }
  }
  strategy_info: {
    strategy_id: number
    strategy_name: string
    ai_session_id: string
  }
}

// AI生成的策略信息（从后端API返回）
export interface AIGeneratedStrategy {
  strategy_id: number
  name: string
  description: string
  code: string
  parameters: Record<string, any>
  strategy_type: string
  ai_session_id: string
  suggested_backtest_params: Record<string, any>
  created_at: string
}

// 回测历史记录项
export interface BacktestHistoryItem {
  strategy_id: number
  strategy_name: string
  backtest_id?: number
  task_id?: string
  status: string
  performance_metrics?: Record<string, any>
  ai_analysis?: Record<string, any>
  created_at: string
}

// AI会话回测历史
export interface AISessionBacktestHistory {
  success: boolean
  ai_session_id: string
  backtest_history: BacktestHistoryItem[]
  total_strategies: number
}