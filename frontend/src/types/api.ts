export interface ApiKey {
  id: string
  user_id: string
  name: string
  exchange: string
  api_key: string
  secret_key: string
  passphrase?: string
  permissions: 'read' | 'trade' | 'withdraw'
  is_active: boolean
  created_at: string
  updated_at: string
  last_used_at?: string
}

export interface CreateApiKeyData {
  name: string
  exchange: string
  api_key: string
  secret_key: string
  passphrase?: string
  permissions: 'read' | 'trade' | 'withdraw'
}

export interface TradingInsight {
  id: string
  user_id: string
  title: string
  content: string
  category: 'technical' | 'fundamental' | 'strategy' | 'error_review' | 'market_view'
  symbols: string[]
  profit_loss?: number
  profit_loss_percentage?: number
  is_public: boolean
  likes_count: number
  comments_count: number
  created_at: string
  updated_at: string
}

export interface CreateInsightData {
  title: string
  content: string
  category: 'technical' | 'fundamental' | 'strategy' | 'error_review' | 'market_view'
  symbols: string[]
  profit_loss?: number
  profit_loss_percentage?: number
  is_public: boolean
}

export interface AIAnalysisRequest {
  type: 'chat' | 'strategy_generation' | 'trade_analysis' | 'market_insight'
  content: string
  context?: {
    symbols?: string[]
    timeframe?: string
    strategy_id?: string
    trades?: any[]
  }
  generate_strategy?: boolean
}

export interface AIAnalysisResponse {
  id: string
  type: string
  content: string
  strategy_code?: string
  recommendations?: string[]
  risk_assessment?: {
    level: 'low' | 'medium' | 'high'
    factors: string[]
  }
  created_at: string
}

export interface ApiResponse<T> {
  success: boolean
  data: T
  message?: string
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  total_pages: number
}