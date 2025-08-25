// 导出所有API服务
export { authApi } from './auth'
export { strategyApi } from './strategy'
export { marketApi } from './market'
export { backtestApi } from './backtest'
export { aiApi } from './ai'
export { tradingApi } from './trading'
export { liveTradingApi } from './liveTrading'

// 导出HTTP客户端
export { userServiceClient, tradingServiceClient } from './client'

// 导出工具函数
export { handleApiResponse, handleApiError } from './client'

// 导出类型
export type { BacktestConfig, BacktestResult } from './backtest'
export type { 
  ChatMessage, 
  ChatSession, 
  StrategyGenerationRequest, 
  GeneratedStrategy, 
  MarketAnalysis 
} from './ai'
export type {
  TradingAccount,
  OrderRequest,
  Order,
  Position,
  TradingSummary,
  DailyPnL,
  TradingSession,
  OrderStatistics,
  RiskAssessment
} from './trading'
export type {
  LiveStrategy,
  LiveStrategyStats,
  LiveStrategyDetails,
  TradeRecord,
  DailyStats,
  StrategyActionRequest
} from './liveTrading'