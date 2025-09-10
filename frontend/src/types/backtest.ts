/**
 * 回测相关类型定义
 */

export interface BacktestResult {
  backtest_id?: string;
  strategy_name?: string;
  symbol?: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  
  // 基础财务指标
  initial_capital: number;
  final_value: number;
  total_return?: number;
  annual_return?: number;
  
  // 风险指标
  max_drawdown?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  volatility?: number;
  var_95?: number;
  
  // 交易统计
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate?: number;
  avg_profit?: number;
  avg_loss?: number;
  profit_factor?: number;
  
  // 评估结果
  performance_grade?: 'A' | 'B' | 'C' | 'D' | 'F';
  risk_level?: 'Low' | 'Medium' | 'High';
  meets_expectations?: boolean;
  
  // 优化建议
  optimization_suggestions?: string[];
  
  // 时间序列数据
  equity_curve?: Array<{
    timestamp: string;
    value: number;
    drawdown: number;
  }>;
  
  trades?: Array<{
    entry_time: string;
    exit_time: string;
    type: 'long' | 'short';
    entry_price: number;
    exit_price: number;
    quantity: number;
    pnl: number;
    pnl_pct: number;
  }>;
}

export interface BacktestSummary {
  backtest_id: string;
  strategy_name: string;
  created_at: string;
  performance_grade: string;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  meets_expectations: boolean;
}