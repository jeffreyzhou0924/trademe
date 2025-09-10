/**
 * Trading页面策略数据服务
 * 专门处理策略库、指标库、分析库的数据集成
 */

import { tradingServiceClient } from '@/services/api/client'
import type { StrategyLibraryItem, IndicatorLibraryItem, AnalysisLibraryItem } from '@/store/tradingPageStore'

export interface ApiResponse<T> {
  success: boolean
  data: T
  message: string
}

export interface BackendStrategy {
  id: string
  name: string
  description: string
  code: string
  parameters: Record<string, any>
  performance_metrics?: {
    total_return: number
    sharpe_ratio: number
    max_drawdown: number
    win_rate: number
  }
  created_at: string
  updated_at: string
  user_id: number
  is_active: boolean
}

export interface BackendAnalysis {
  id: string
  name: string
  description: string
  analysis_type: 'pattern' | 'trend' | 'volume' | 'comprehensive'
  rules: Record<string, any>
  confidence_threshold: number
  created_at: string
  is_active: boolean
}

export class StrategyDataService {
  private static instance: StrategyDataService

  static getInstance(): StrategyDataService {
    if (!StrategyDataService.instance) {
      StrategyDataService.instance = new StrategyDataService()
    }
    return StrategyDataService.instance
  }

  /**
   * 获取用户的策略列表
   */
  async getStrategies(): Promise<StrategyLibraryItem[]> {
    try {
      console.log('🔍 获取用户策略列表')
      
      const response = await tradingServiceClient.get<any>('/strategies/')
      
      console.log('🔍 后端策略原始响应:', response.data)

      // 检查响应格式 - 后端返回 {strategies: [], total: 0, skip: 0, limit: 20} 格式
      let backendStrategies = []
      
      if (response.data && Array.isArray(response.data.strategies)) {
        backendStrategies = response.data.strategies
      } else if (Array.isArray(response.data)) {
        backendStrategies = response.data
      } else if (response.data && response.data.data && Array.isArray(response.data.data)) {
        backendStrategies = response.data.data
      }
      
      console.log(`🔍 解析后的策略数组:`, backendStrategies)

      // 转换后端数据格式到前端格式
      const strategies: StrategyLibraryItem[] = backendStrategies.map(strategy => ({
        id: strategy.id,
        name: strategy.name,
        description: strategy.description,
        code: strategy.code,
        parameters: strategy.parameters,
        type: 'custom',
        source: 'user',
        performance: strategy.performance_metrics ? {
          returns: strategy.performance_metrics.total_return,
          winRate: strategy.performance_metrics.win_rate,
          maxDrawdown: strategy.performance_metrics.max_drawdown
        } : {
          returns: 0,
          winRate: 0,
          maxDrawdown: 0
        },
        createdAt: new Date(strategy.created_at).getTime(),
        lastUsed: strategy.updated_at ? new Date(strategy.updated_at).getTime() : undefined
      }))

      console.log(`✅ 策略列表获取成功: ${strategies.length}个策略`)
      return strategies

    } catch (error) {
      console.error('❌ 获取策略列表失败:', error)
      throw new Error(`获取策略列表失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 创建新策略
   */
  async createStrategy(strategy: Omit<StrategyLibraryItem, 'id' | 'createdAt' | 'lastBacktest'>): Promise<StrategyLibraryItem> {
    try {
      console.log(`🔍 创建新策略: ${strategy.name}`)
      
      const requestData = {
        name: strategy.name,
        description: strategy.description,
        code: strategy.code,
        parameters: strategy.parameters
      }

      const response = await tradingServiceClient.post<ApiResponse<BackendStrategy>>('/strategies/', requestData)

      if (!response.data.success) {
        throw new Error(response.data.message || '创建策略失败')
      }

      const backendStrategy = response.data.data
      const newStrategy: StrategyLibraryItem = {
        id: backendStrategy.id,
        name: backendStrategy.name,
        description: backendStrategy.description,
        code: backendStrategy.code,
        parameters: backendStrategy.parameters,
        type: 'custom',
        source: 'user',
        performance: strategy.performance,
        createdAt: new Date(backendStrategy.created_at).getTime()
      }

      console.log(`✅ 策略创建成功: ${newStrategy.name}`)
      return newStrategy

    } catch (error) {
      console.error('❌ 创建策略失败:', error)
      throw new Error(`创建策略失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 更新策略状态
   */
  async updateStrategyStatus(strategyId: string, isActive: boolean): Promise<void> {
    try {
      console.log(`🔍 更新策略状态: ${strategyId} -> ${isActive}`)
      
      const response = await tradingServiceClient.patch<ApiResponse<any>>(`/strategies/${strategyId}`, {
        is_active: isActive
      })

      if (!response.data.success) {
        throw new Error(response.data.message || '更新策略状态失败')
      }

      console.log(`✅ 策略状态更新成功: ${strategyId}`)

    } catch (error) {
      console.error('❌ 更新策略状态失败:', error)
      throw new Error(`更新策略状态失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 删除策略
   */
  async deleteStrategy(strategyId: string): Promise<void> {
    try {
      console.log(`🔍 删除策略: ${strategyId}`)
      
      const response = await tradingServiceClient.delete<ApiResponse<any>>(`/strategies/${strategyId}`)

      if (!response.data.success) {
        throw new Error(response.data.message || '删除策略失败')
      }

      console.log(`✅ 策略删除成功: ${strategyId}`)

    } catch (error) {
      console.error('❌ 删除策略失败:', error)
      throw new Error(`删除策略失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 运行策略回测
   */
  async runBacktest(strategyId: string, symbol: string, timeframe: string, days: number = 30): Promise<{
    total_return: number
    sharpe_ratio: number
    max_drawdown: number
    win_rate: number
  }> {
    try {
      console.log(`🔍 运行策略回测: ${strategyId} on ${symbol} ${timeframe}`)
      
      const response = await tradingServiceClient.post<ApiResponse<any>>('/backtests/', {
        strategy_id: strategyId,
        symbol,
        timeframe,
        days
      })

      if (!response.data.success) {
        throw new Error(response.data.message || '策略回测失败')
      }

      console.log(`✅ 策略回测完成: ${strategyId}`)
      return response.data.data.performance_metrics

    } catch (error) {
      console.error('❌ 策略回测失败:', error)
      throw new Error(`策略回测失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * AI聊天 - 策略生成
   */
  async chatWithAI(message: string, sessionType: 'strategy' | 'indicator' | 'analysis' = 'strategy'): Promise<string> {
    try {
      console.log(`🤖 AI策略对话: ${sessionType}`)
      
      const response = await tradingServiceClient.post<ApiResponse<any>>('/ai/chat', {
        content: message,
        session_type: sessionType,
        ai_mode: 'trader'
      })

      if (!response.data.success) {
        throw new Error(response.data.message || 'AI对话失败')
      }

      console.log(`✅ AI对话成功`)
      return response.data.data.response || response.data.data.content

    } catch (error) {
      console.error('❌ AI对话失败:', error)
      throw new Error(`AI对话失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 获取分析库列表 - 使用模拟数据，因为后端可能还没有这个API
   */
  async getAnalysisLibrary(): Promise<AnalysisLibraryItem[]> {
    // 暂时返回模拟数据，待后端完善后替换
    console.log('📊 获取分析库 (使用模拟数据)')
    
    return [
      {
        id: 'breakout_pattern',
        name: '突破形态分析',
        description: '识别价格突破关键支撑或阻力位的形态',
        type: 'pattern',
        criteria: {
          volume_spike: true,
          price_breakout: true,
          momentum_confirm: true
        },
        confidence: 0.85,
        lastAnalysis: {
          result: '发现2个潜在突破机会',
          timestamp: Date.now() - 3600000, // 1小时前
          opportunities: []
        }
      },
      {
        id: 'trend_reversal',
        name: '趋势反转分析',
        description: '检测趋势可能发生反转的信号',
        type: 'trend',
        criteria: {
          divergence: true,
          support_resistance: true,
          candlestick_patterns: true
        },
        confidence: 0.78,
        lastAnalysis: {
          result: '发现1个反转信号',
          timestamp: Date.now() - 1800000, // 30分钟前
          opportunities: []
        }
      }
    ]
  }

  /**
   * 运行分析
   */
  async runAnalysis(analysisId: string, symbol: string): Promise<{
    result: string
    opportunities: any[]
    confidence: number
  }> {
    // 模拟分析运行，返回结果
    console.log(`📊 运行分析: ${analysisId} on ${symbol}`)
    
    await new Promise(resolve => setTimeout(resolve, 2000)) // 模拟分析时间
    
    return {
      result: `基于${analysisId}分析${symbol}，发现3个交易机会`,
      opportunities: [
        { type: 'buy', confidence: 0.82, price: 43200, reason: '突破上升趋势线' },
        { type: 'sell', confidence: 0.75, price: 43800, reason: '遇到阻力位' }
      ],
      confidence: 0.78
    }
  }
}

// 导出单例实例
export const strategyDataService = StrategyDataService.getInstance()