import { tradingServiceClient, handleApiResponse, handleApiError } from './client'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: {
    codeBlock?: string
    analysis?: string  // 改为string避免渲染对象
    suggestions?: string[]
    isError?: boolean
    isStreaming?: boolean  // 支持流式消息标记
    isWaitingFirstChunk?: boolean  // 等待第一个数据块的标记
    streamCompleted?: boolean  // 流式消息完成标记
    completedAt?: number  // 完成时间戳
    forceRender?: number  // 强制渲染标记
  }
}

// 支持双模式的会话类型
export type AIMode = 'developer' | 'trader'
export type SessionType = 'strategy' | 'indicator' | 'trading_system'
export type SessionStatus = 'active' | 'completed' | 'archived'

export interface ChatSession {
  session_id: string
  name: string
  description?: string
  ai_mode: AIMode
  session_type: SessionType
  status: SessionStatus
  progress: number
  message_count: number
  last_message?: string
  cost_total: number
  created_at: string
  updated_at: string
  last_activity_at?: string
}

export interface CreateSessionRequest {
  name: string
  ai_mode: AIMode
  session_type: SessionType
  description?: string
}

export interface UsageStats {
  period_days: number
  total_requests: number
  total_cost_usd: number
  daily_cost_usd: number
  monthly_cost_usd: number
  remaining_daily_quota: number
  remaining_monthly_quota: number
  by_feature: Record<string, any>
  by_session: Record<string, any>
}

export interface StrategyGenerationRequest {
  description: string
  market_type: string
  risk_level: 'low' | 'medium' | 'high'
  timeframe: string
  indicators?: string[]
}

export interface GeneratedStrategy {
  name: string
  description: string
  code: string
  explanation: string
  parameters: Record<string, any>
  risk_assessment: {
    level: 'low' | 'medium' | 'high'
    factors: string[]
    recommendations: string[]
  }
}

export interface MarketAnalysis {
  symbol: string
  timeframe: string
  trend_direction: 'bullish' | 'bearish' | 'neutral'
  strength: number
  support_levels: number[]
  resistance_levels: number[]
  technical_indicators: Record<string, any>
  summary: string
  recommendations: string[]
  confidence: number
}

export const aiApi = {
  // ========== 会话管理功能 ==========
  
  // 创建新的聊天会话 (匹配后端 /ai/sessions 端点)
  async createSession(request: CreateSessionRequest): Promise<{
    session_id: string
    name: string
    ai_mode: string
    session_type: string
    status: string
    created_at: string
  }> {
    try {
      const response = await tradingServiceClient.post('/ai/sessions', request)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
      throw error // 确保错误被正确抛出
    }
  },

  // 获取用户的聊天会话列表 (匹配后端 /ai/sessions 端点)
  async getSessions(aiMode: AIMode): Promise<{
    sessions: ChatSession[]
    total_count: number
    ai_mode: string
  }> {
    try {
      const response = await tradingServiceClient.get(`/ai/sessions?ai_mode=${aiMode}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 更新会话状态 (匹配后端 /ai/sessions/{session_id}/status 端点)
  async updateSessionStatus(sessionId: string, status: SessionStatus, progress?: number): Promise<{
    message: string
    session_id: string
  }> {
    try {
      const params = progress !== undefined ? `?progress=${progress}` : ''
      const response = await tradingServiceClient.put(`/ai/sessions/${sessionId}/status${params}`, { status })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 删除聊天会话 (匹配后端 /ai/sessions/{session_id} 端点)
  async deleteSession(sessionId: string): Promise<{
    message: string
    session_id: string
  }> {
    try {
      const response = await tradingServiceClient.delete(`/ai/sessions/${sessionId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // ========== 对话功能 ==========

  // 发送AI聊天消息 (匹配后端 /ai/chat 端点，支持双模式)
  async sendChatMessage(
    message: string, 
    sessionId?: string, 
    aiMode: AIMode = 'developer',
    sessionType: SessionType = 'strategy',
    context?: Record<string, any>
  ): Promise<{
    response: string
    session_id: string
    tokens_used: number
    model: string
    cost_usd: number
  }> {
    try {
      const response = await tradingServiceClient.post('/ai/chat', {
        content: message,
        session_id: sessionId,
        ai_mode: aiMode,
        session_type: sessionType,
        context: context || {}
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取聊天历史 (匹配后端 /ai/chat/history 端点)
  async getChatHistory(sessionId?: string, limit: number = 50): Promise<{ messages: any[] }> {
    try {
      const params = new URLSearchParams()
      if (sessionId) params.append('session_id', sessionId)
      params.append('limit', limit.toString())
      
      const response = await tradingServiceClient.get(`/ai/chat/history?${params}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 清除聊天会话 (匹配后端 /ai/chat/{session_id} 端点)
  async clearChatSession(sessionId: string): Promise<{ message: string; cleared: boolean }> {
    try {
      const response = await tradingServiceClient.delete(`/ai/chat/${sessionId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 生成交易策略 (匹配后端 /ai/strategy/generate 端点)
  async generateStrategy(request: {
    description: string
    indicators?: string[]
    timeframe?: string
    risk_level?: 'low' | 'medium' | 'high'
  }): Promise<{
    code: string
    explanation: string
    parameters: Record<string, any>
    warnings: string[]
  }> {
    try {
      const response = await tradingServiceClient.post('/ai/strategy/generate', {
        description: request.description,
        indicators: request.indicators || [],
        timeframe: request.timeframe || '1h',
        risk_level: request.risk_level || 'medium'
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取AI使用统计 (匹配后端 /ai/usage/stats 端点)
  async getUsageStats(days: number = 30): Promise<UsageStats> {
    try {
      const response = await tradingServiceClient.get(`/ai/usage/stats?days=${days}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 生成交易洞察 (匹配后端 /ai/insights/generate 端点)
  async generateTradingInsights(symbol: string, timeframe: string = '1d'): Promise<{
    symbol: string
    insights: string
    confidence: number
    key_factors: string[]
    timestamp: string
  }> {
    try {
      const response = await tradingServiceClient.post(`/ai/insights/generate?symbol=${symbol}&timeframe=${timeframe}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 市场分析 (匹配后端 /ai/market/analyze 端点)
  async analyzeMarket(request: {
    symbols: string[]
    timeframe?: string
    analysis_type?: string
  }): Promise<{
    summary: string
    signals: Array<Record<string, any>>
    risk_assessment: Record<string, any>
    recommendations: string[]
  }> {
    try {
      const response = await tradingServiceClient.post('/ai/market/analyze', {
        symbols: request.symbols,
        timeframe: request.timeframe || '1d',
        analysis_type: request.analysis_type || 'technical'
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 分析回测结果 (匹配后端 /ai/backtest/analyze 端点)
  async analyzeBacktestResults(backtestId: number): Promise<{
    performance_summary: string
    strengths: string[]
    weaknesses: string[]
    improvement_suggestions: string[]
    risk_analysis: Record<string, any>
  }> {
    try {
      const response = await tradingServiceClient.post(`/ai/backtest/analyze?backtest_id=${backtestId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // ========== 新增AI策略回测集成功能 ==========
  
  // 获取AI会话最新生成的策略
  async getLatestAIStrategy(sessionId: string): Promise<{
    strategy_id: number
    name: string
    description: string
    code: string
    parameters: Record<string, any>
    strategy_type: string
    ai_session_id: string
    suggested_backtest_params: Record<string, any>
    created_at: string
  }> {
    try {
      const response = await tradingServiceClient.get(`/strategies/latest-ai-strategy/${sessionId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
      throw error
    }
  },

  // 自动触发AI策略回测
  async autoBacktest(config: {
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
  }): Promise<{
    success: boolean
    task_id: string
    strategy_id?: number
    backtest_id?: number
    message: string
  }> {
    try {
      const response = await tradingServiceClient.post('/ai/strategy/auto-backtest', config)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
      throw error
    }
  },

  // 获取AI策略回测进度
  async getBacktestProgress(taskId: string): Promise<{
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
  }> {
    try {
      const response = await tradingServiceClient.get(`/realtime-backtest/ai-strategy/progress/${taskId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
      throw error
    }
  },

  // 获取AI策略回测结果
  async getBacktestResults(taskId: string): Promise<{
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
  }> {
    try {
      const response = await tradingServiceClient.get(`/realtime-backtest/ai-strategy/results/${taskId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
      throw error
    }
  },

  // 获取AI会话的回测历史记录
  async getAISessionBacktestHistory(sessionId: string): Promise<{
    success: boolean
    ai_session_id: string
    backtest_history: Array<{
      strategy_id: number
      strategy_name: string
      backtest_id?: number
      task_id?: string
      status: string
      performance_metrics?: Record<string, any>
      ai_analysis?: Record<string, any>
      created_at: string
    }>
    total_strategies: number
  }> {
    try {
      const response = await tradingServiceClient.get(`/ai/strategy/backtest-history/${sessionId}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
      throw error
    }
  }
}