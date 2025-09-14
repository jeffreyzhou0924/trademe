import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import toast from 'react-hot-toast'
import { aiApi } from '../services/api/ai'
import { errorHandler, createRetryHandler, ErrorType } from '../utils/errorHandler'
import { getWebSocketAIService, type AIProgressCallback, type WebSocketAIService } from '../services/ai/websocketAI'
import type { 
  ChatSession, 
  ChatMessage, 
  StrategyGenerationRequest, 
  GeneratedStrategy,
  MarketAnalysis,
  AIMode,
  SessionType,
  SessionStatus,
  CreateSessionRequest,
  UsageStats
} from '../services/api/ai'
import type {
  AutoBacktestConfig,
  BacktestProgress,
  BacktestResults,
  AIGeneratedStrategy,
  BacktestHistoryItem
} from '../types/aiBacktest'

interface AIState {
  // 双模式会话管理
  currentAIMode: AIMode
  chatSessions: Record<AIMode, ChatSession[]>  // 按模式分组的会话
  currentSession: ChatSession | null
  messages: ChatMessage[]
  isTyping: boolean
  
  // 消息加载状态管理 - 解决异步竞态条件
  messagesLoading: boolean
  messagesLoaded: boolean
  
  // WebSocket状态
  useWebSocket: boolean
  wsConnected: boolean
  wsConnectionId: string | null
  
  // AI进度状态
  aiProgress: {
    isProcessing: boolean
    step: number
    totalSteps: number
    status: string
    message: string
    complexity?: 'simple' | 'medium' | 'complex'
    estimatedTime?: number
  } | null
  
  // 🌊 流式响应状态
  streamingMessage: {
    isStreaming: boolean
    requestId?: string
    accumulatedContent: string
    messageIndex?: number  // 当前正在更新的消息索引
  } | null
  
  // 策略生成
  generatedStrategies: GeneratedStrategy[]
  isGenerating: boolean
  currentGeneratedStrategy: GeneratedStrategy | null
  
  // 市场分析
  marketAnalyses: Record<string, MarketAnalysis> // key: symbol-timeframe
  isAnalyzing: boolean
  
  // 使用统计
  usageStats: UsageStats | null
  
  // 新增：回测相关状态
  generatedStrategy: AIGeneratedStrategy | null
  showBacktestPrompt: boolean
  backtestProgress: BacktestProgress | null
  backtestResults: BacktestResults | null
  showBacktestResults: boolean
  isBacktestRunning: boolean
  
  // 加载状态
  isLoading: boolean
  error: string | null
  
  // 网络状态和重试管理
  networkStatus: 'checking' | 'connected' | 'disconnected'
  retryCount: number
  
  // 模式和会话操作
  setAIMode: (mode: AIMode) => void
  createChatSession: (request: CreateSessionRequest) => Promise<boolean>
  loadChatSessions: (mode: AIMode) => Promise<void>
  selectChatSession: (session: ChatSession | null) => void
  sendMessage: (message: string) => Promise<boolean>
  deleteChatSession: (sessionId: string) => Promise<boolean>
  updateSessionStatus: (sessionId: string, status: SessionStatus, progress?: number) => Promise<boolean>
  clearCurrentMessages: () => void
  
  // 使用统计
  loadUsageStats: (days?: number) => Promise<void>
  updateUsageStatsRealtime: (costUsd: number, tokensUsed: number) => void
  
  // 策略生成操作
  generateStrategy: (request: StrategyGenerationRequest) => Promise<GeneratedStrategy | null>
  optimizeStrategy: (code: string, objectives: string[]) => Promise<any>
  explainStrategy: (code: string) => Promise<any>
  clearGeneratedStrategies: () => void
  
  // 市场分析操作
  analyzeMarket: (symbol: string, exchange: string, timeframe: string) => Promise<MarketAnalysis | null>
  getTradingSignals: (symbol: string, exchange: string, timeframes: string[]) => Promise<any>
  assessRisk: (strategyCode?: string, portfolio?: any) => Promise<any>
  
  // WebSocket方法
  toggleWebSocket: () => void
  initializeWebSocket: () => Promise<boolean>
  sendMessageWebSocket: (message: string) => Promise<boolean>
  
  // 新增：回测相关方法
  getLatestAIStrategy: (sessionId: string) => Promise<AIGeneratedStrategy | null>
  autoBacktest: (config: AutoBacktestConfig) => Promise<boolean>
  getBacktestProgress: (taskId: string) => Promise<BacktestProgress | null>
  getBacktestResults: (taskId: string) => Promise<BacktestResults | null>
  startBacktestMonitoring: (taskId: string) => void
  stopBacktestMonitoring: () => void
  handleStrategyGenerated: (sessionId: string) => Promise<void>
  handleQuickBacktest: (config: Partial<AutoBacktestConfig>) => Promise<void>
  setShowBacktestPrompt: (show: boolean) => void
  setShowBacktestResults: (show: boolean) => void
  
  // 工具方法
  clearError: () => void
  reset: () => void
  checkNetworkStatus: () => Promise<boolean>
  getErrorMessage: (error: any) => string
}

export const useAIStore = create<AIState>()(
  persist(
    (set, get) => ({
      // 初始状态
      currentAIMode: 'trader' as AIMode,
      chatSessions: {
        developer: [],
        trader: []
      },
      currentSession: null,
      messages: [],
      isTyping: false,
      messagesLoading: false,
      messagesLoaded: false,
      
      // WebSocket状态初始值
      useWebSocket: true, // 默认启用WebSocket
      wsConnected: false,
      wsConnectionId: null,
      
      // AI进度状态初始值  
      aiProgress: null,
      
      // 🌊 流式响应状态初始值
      streamingMessage: null,
      
      generatedStrategies: [],
      isGenerating: false,
      currentGeneratedStrategy: null,
      
      marketAnalyses: {},
      isAnalyzing: false,
      
      usageStats: null,
      
      // 回测相关状态初始值
      generatedStrategy: null,
      showBacktestPrompt: false,
      backtestProgress: null,
      backtestResults: null,
      showBacktestResults: false,
      isBacktestRunning: false,
      
      isLoading: false,
      error: null,
      
      // 网络状态和重试管理初始值
      networkStatus: 'connected',
      retryCount: 0,

      // =============== 模式和会话管理 ===============
      
      // 切换AI模式
      setAIMode: (mode: AIMode) => {
        set({ 
          currentAIMode: mode,
          currentSession: null,
          messages: [],
          error: null 
        })
      },

      // 创建新的聊天会话
      createChatSession: async (request: CreateSessionRequest) => {
        set({ isLoading: true, error: null })
        try {
          const response = await aiApi.createSession(request)
          
          // 构建新的会话对象
          const newSession: ChatSession = {
            session_id: response.session_id,
            name: request.name,
            description: request.description,
            ai_mode: request.ai_mode,
            session_type: request.session_type,
            status: 'active' as SessionStatus,
            progress: 0,
            message_count: 0,
            cost_total: 0,
            created_at: response.created_at,
            updated_at: response.created_at,
            last_activity_at: response.created_at
          }
          
          set(state => ({
            chatSessions: {
              ...state.chatSessions,
              [request.ai_mode]: [newSession, ...state.chatSessions[request.ai_mode]]
            },
            currentSession: newSession,
            messages: [],
            isLoading: false
          }))
          
          // 如果有描述，自动发送作为第一条消息
          if (request.description && request.description.trim()) {
            // 使用get()获取最新状态，然后发送消息
            const { sendMessage } = get()
            await sendMessage(request.description.trim())
          }
          
          toast.success(`创建${request.session_type === 'strategy' ? '策略' : request.session_type === 'indicator' ? '指标' : ''}会话成功`)
          return true
        } catch (error: any) {
          const message = String(error.response?.data?.message || '创建会话失败')
          set({ error: message, isLoading: false })
          toast.error(message)
          return false
        }
      },

      // 加载聊天会话列表
      loadChatSessions: async (mode: AIMode) => {
        set({ isLoading: true, error: null })
        try {
          const response = await aiApi.getSessions(mode)
          set(state => ({ 
            chatSessions: {
              ...state.chatSessions,
              [mode]: response.sessions
            },
            isLoading: false 
          }))
        } catch (error: any) {
          const message = String(error.response?.data?.message || '加载会话列表失败')
          set({ error: message, isLoading: false })
          console.error('Load chat sessions error:', error)
        }
      },

      // 选择聊天会话 - 修复异步竞态条件 ✅
      selectChatSession: async (session: ChatSession | null) => {
        // 立即设置基础状态，包含加载状态管理
        set({ 
          currentSession: session,
          messages: [],
          error: null,
          messagesLoading: !!session,  // 🔧 如果有会话则开始加载
          messagesLoaded: false
        })

        // 如果选择了会话，立即开始异步加载聊天历史
        if (session) {
          try {
            console.log('📥 [AIStore] 开始加载聊天历史:', session.session_id)
            const response = await aiApi.getChatHistory(session.session_id, 20)
            
            // API返回的消息格式转换
            const historyMessages = (response?.messages || []).map((msg: any) => ({
              role: msg.message_type || msg.role, // 保持兼容性
              content: String(msg.content || ''), // 确保content是字符串
              timestamp: msg.created_at || msg.timestamp // 保持兼容性
            } as ChatMessage))
            
            // API返回的消息已经是按时间倒序排列，需要反转为正序
            const orderedHistoryMessages = historyMessages.reverse()
            
            // 只有当前会话仍然是选中的会话时才更新消息
            const currentState = get()
            if (currentState.currentSession?.session_id === session.session_id) {
              console.log('✅ [AIStore] 聊天历史加载完成:', {
                sessionId: session.session_id,
                messageCount: orderedHistoryMessages.length
              })
              
              set({ 
                messages: orderedHistoryMessages,
                messagesLoading: false,  // 🔧 标记加载完成
                messagesLoaded: true     // 🔧 标记已加载
              })
            } else {
              console.log('⚠️ [AIStore] 会话已切换，忽略历史消息加载')
              set({ messagesLoading: false, messagesLoaded: true })
            }
          } catch (error: any) {
            console.error('❌ [AIStore] 加载聊天历史失败:', error)
            set({ 
              error: '加载聊天历史失败，请刷新重试',
              messagesLoading: false,  // 🔧 标记加载完成（即使失败）
              messagesLoaded: true     // 🔧 标记已尝试加载
            })
          }
        } else {
          // 没有选择会话，直接标记为加载完成
          set({ messagesLoading: false, messagesLoaded: true })
        }
      },

      // 发送消息 - 支持WebSocket/HTTP双模式
      sendMessage: async (message: string) => {
        const { useWebSocket } = get()
        
        // 如果启用WebSocket，使用WebSocket发送
        if (useWebSocket) {
          return get().sendMessageWebSocket(message)
        }
        
        // 原有HTTP发送逻辑
        let { currentSession, currentAIMode, retryCount } = get()
        
        // console.log('🚀 [DEBUG] sendMessage called:', { 
        //   message, 
        //   currentSession: currentSession?.session_id || 'null',
        //   currentAIMode 
        // })
        
        // 如果没有当前会话，自动创建一个默认会话
        if (!currentSession) {
          console.log('❌ [DEBUG] No currentSession, creating default session')
          try {
            const defaultSessionName = currentAIMode === 'trader' ? '市场分析对话' : '策略开发对话'
            const success = await get().createChatSession({
              name: defaultSessionName,
              ai_mode: currentAIMode,
              session_type: 'strategy',
              description: '自动创建的对话会话'
            })
            
            if (!success) {
              toast.error('创建对话会话失败')
              return false
            }
            
            // 重新获取当前会话
            currentSession = get().currentSession
            if (!currentSession) {
              toast.error('会话创建失败')
              return false
            }
            
            console.log('✅ [DEBUG] Auto-created session:', currentSession.session_id)
            toast.success('已自动创建新对话')
          } catch (error) {
            console.log('❌ [DEBUG] Exception in session creation:', error)
            toast.error('创建对话会话失败')
            return false
          }
        } else {
          console.log('✅ [DEBUG] Using existing currentSession:', currentSession.session_id)
        }

        // 立即添加用户消息到界面
        const userMessage: ChatMessage = {
          role: 'user',
          content: String(message || ''), // 确保content是字符串
          timestamp: new Date().toISOString()
        }

        set(state => ({
          messages: [...state.messages, userMessage],
          isTyping: true,
          error: null,
          networkStatus: 'checking',
          retryCount: 0
        }))

        // 创建重试处理器 - 最多重试2次，网络错误时重试
        const retryHandler = createRetryHandler(2, 1500)
        
        try {
          const sendMessageWithRetry = async () => {
            // 添加超时机制，45秒后超时 (给重试留出时间)
            const timeoutPromise = new Promise((_, reject) => {
              setTimeout(() => reject(new Error('TIMEOUT')), 45000)
            })
            
            // 发送消息到后端
            console.log('📤 [DEBUG] Calling aiApi.sendChatMessage with:', {
              message,
              sessionId: currentSession.session_id,
              aiMode: currentSession.ai_mode,
              sessionType: currentSession.session_type
            })
            
            const messagePromise = aiApi.sendChatMessage(
              message,
              currentSession.session_id,
              currentSession.ai_mode,
              currentSession.session_type
            )
            
            return await Promise.race([messagePromise, timeoutPromise]) as any
          }
          
          const aiResponse = await retryHandler(sendMessageWithRetry, 'ai-chat')
          
          // 构建AI回复消息
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: String(aiResponse.response || ''), // 确保content是字符串
            timestamp: new Date().toISOString()
          }
          
          // 成功后重置状态
          set(state => ({
            messages: [...state.messages, assistantMessage],
            isTyping: false,
            error: null,
            networkStatus: 'connected',
            retryCount: 0
          }))
          
          // 实时更新统计数据
          if (aiResponse.cost_usd > 0) {
            get().updateUsageStatsRealtime(aiResponse.cost_usd, aiResponse.tokens_used || 0)
            
            // 显示消耗信息
            toast.success(`AI回复完成 (消耗 $${aiResponse.cost_usd.toFixed(4)})`, {
              icon: '🧠',
              duration: 3000
            })
          }
          
          return true
        } catch (error: any) {
          // 确保UI状态总是被正确重置
          const resetUIState = () => {
            set(state => ({ 
              isTyping: false,
              networkStatus: 'disconnected',
              retryCount: state.retryCount + 1
            }))
          }

          // 处理不同类型的错误
          const appError = errorHandler.handle(error, 'ai-chat-send', false)
          
          let userFriendlyMessage = ''
          let shouldShowRetryOption = false
          
          switch (appError.type) {
            case ErrorType.NETWORK:
              userFriendlyMessage = 'AI服务暂时不可用，请检查网络连接'
              shouldShowRetryOption = true
              break
              
            case ErrorType.SERVER:
              if (appError.code === 504) {
                userFriendlyMessage = 'Claude AI服务繁忙，请稍后重试'
                shouldShowRetryOption = true
              } else {
                userFriendlyMessage = 'AI服务器错误，请稍后再试'
              }
              break
              
            case ErrorType.AUTH:
              userFriendlyMessage = 'AI使用权限不足，请检查会员状态'
              break
              
            default:
              if (error.message === 'TIMEOUT') {
                userFriendlyMessage = 'AI响应超时，服务可能繁忙'
                shouldShowRetryOption = true
              } else if (error.message?.includes('AI回复超时')) {
                userFriendlyMessage = 'AI回复超时，请稍后重试'
                shouldShowRetryOption = true
              } else {
                userFriendlyMessage = appError.message || '发送消息失败'
              }
          }
          
          // 重置UI状态
          resetUIState()
          
          // 设置错误状态
          set({ error: userFriendlyMessage })
          
          // 显示错误提示
          toast.error(userFriendlyMessage, {
            duration: shouldShowRetryOption ? 8000 : 5000,
            icon: shouldShowRetryOption ? '🔄' : '❌',
            id: `ai-error-${Date.now()}`
          })
          
          // 如果支持重试，显示额外的重试提示
          if (shouldShowRetryOption) {
            setTimeout(() => {
              toast('可尝试重新发送消息或检查网络连接', {
                icon: '💡',
                duration: 6000,
                style: {
                  background: '#FEF3C7',
                  color: '#92400E',
                  border: '1px solid #FCD34D'
                }
              })
            }, 1000)
          }
          
          return false
        }
      },

      // 更新会话状态
      updateSessionStatus: async (sessionId: string, status: SessionStatus, progress?: number) => {
        try {
          await aiApi.updateSessionStatus(sessionId, status, progress)
          
          // 更新本地状态
          set(state => {
            const updatedSessions = { ...state.chatSessions }
            Object.keys(updatedSessions).forEach(mode => {
              updatedSessions[mode as AIMode] = updatedSessions[mode as AIMode].map(session => 
                session.session_id === sessionId 
                  ? { ...session, status, progress: progress ?? session.progress }
                  : session
              )
            })
            
            return {
              chatSessions: updatedSessions,
              currentSession: state.currentSession?.session_id === sessionId
                ? { ...state.currentSession, status, progress: progress ?? state.currentSession.progress }
                : state.currentSession
            }
          })
          
          toast.success('会话状态更新成功')
          return true
        } catch (error: any) {
          const message = error.response?.data?.message || '更新会话状态失败'
          toast.error(message)
          return false
        }
      },

      // 删除聊天会话
      deleteChatSession: async (sessionId: string) => {
        try {
          await aiApi.deleteSession(sessionId)
          
          set(state => {
            const updatedSessions = { ...state.chatSessions }
            Object.keys(updatedSessions).forEach(mode => {
              updatedSessions[mode as AIMode] = updatedSessions[mode as AIMode].filter(s => s.session_id !== sessionId)
            })
            
            return {
              chatSessions: updatedSessions,
              currentSession: state.currentSession?.session_id === sessionId ? null : state.currentSession,
              messages: state.currentSession?.session_id === sessionId ? [] : state.messages
            }
          })
          
          toast.success('会话删除成功')
          return true
        } catch (error: any) {
          const message = error.response?.data?.message || '删除会话失败'
          toast.error(message)
          return false
        }
      },

      // 加载使用统计
      loadUsageStats: async (days: number = 30) => {
        set({ isLoading: true, error: null })
        try {
          const stats = await aiApi.getUsageStats(days)
          set({ 
            usageStats: stats,
            isLoading: false 
          })
        } catch (error: any) {
          const message = String(error.response?.data?.message || '获取使用统计失败')
          set({ error: message, isLoading: false })
          console.error('Load usage stats error:', error)
        }
      },

      // 实时更新使用统计
      updateUsageStatsRealtime: (costUsd: number, tokensUsed: number) => {
        set(state => {
          if (!state.usageStats) {
            // 如果还没有统计数据，创建初始结构
            return {
              usageStats: {
                period_days: 1,
                total_requests: 1,
                total_cost_usd: costUsd,
                daily_cost_usd: costUsd,
                monthly_cost_usd: costUsd,
                remaining_daily_quota: 1000,
                remaining_monthly_quota: 30000,
                by_feature: {},
                by_session: {}
              }
            }
          }

          // 更新现有统计数据
          return {
            usageStats: {
              ...state.usageStats,
              total_requests: (state.usageStats.total_requests || 0) + 1,
              total_cost_usd: (state.usageStats.total_cost_usd || 0) + costUsd,
              daily_cost_usd: (state.usageStats.daily_cost_usd || 0) + costUsd,
              monthly_cost_usd: (state.usageStats.monthly_cost_usd || 0) + costUsd
            }
          }
        })

        console.log(`💰 [AIStore] 实时更新统计: +$${costUsd.toFixed(4)}, +${tokensUsed} tokens`)
      },

      // 清空当前消息
      clearCurrentMessages: () => {
        set({ messages: [], currentSession: null })
      },

      // =============== 策略生成功能 ===============

      // 生成交易策略
      generateStrategy: async (request: StrategyGenerationRequest) => {
        set({ isGenerating: true, error: null })
        try {
          const apiResponse = await aiApi.generateStrategy(request)
          
          // Transform API response to GeneratedStrategy interface
          const strategy: GeneratedStrategy = {
            name: request.description.split(' ').slice(0, 3).join(' ') + ' Strategy',
            description: request.description,
            code: apiResponse.code,
            explanation: apiResponse.explanation,
            parameters: apiResponse.parameters,
            risk_assessment: {
              level: request.risk_level || 'medium',
              factors: apiResponse.warnings || [],
              recommendations: ['Review and test thoroughly before live trading']
            }
          }
          
          set(state => ({
            generatedStrategies: [strategy, ...state.generatedStrategies],
            currentGeneratedStrategy: strategy,
            isGenerating: false
          }))
          toast.success('策略生成成功')
          return strategy
        } catch (error: any) {
          const message = String(error.response?.data?.message || '策略生成失败')
          set({ error: message, isGenerating: false })
          toast.error(message)
          return null
        }
      },

      // 优化策略代码 - 使用Chat API实现
      optimizeStrategy: async (code: string, objectives: string[]) => {
        set({ isLoading: true, error: null })
        try {
          const prompt = `请优化以下策略代码，优化目标：${objectives.join(', ')}\n\n代码：\n${code}`
          const result = await aiApi.sendChatMessage(prompt, undefined, 'developer', 'strategy')
          set({ isLoading: false })
          toast.success('策略优化完成')
          return {
            code: result.response,
            explanation: '通过AI聊天优化生成',
            improvements: objectives
          }
        } catch (error: any) {
          const message = String(error.response?.data?.message || '策略优化失败')
          set({ error: message, isLoading: false })
          toast.error(message)
          throw error
        }
      },

      // 解释策略代码 - 使用Chat API实现
      explainStrategy: async (code: string) => {
        set({ isLoading: true, error: null })
        try {
          const prompt = `请详细解释以下策略代码的逻辑和功能：\n\n${code}`
          const result = await aiApi.sendChatMessage(prompt, undefined, 'developer', 'strategy')
          set({ isLoading: false })
          return {
            explanation: result.response,
            complexity: 'medium',
            features: []
          }
        } catch (error: any) {
          const message = String(error.response?.data?.message || '策略解释失败')
          set({ error: message, isLoading: false })
          toast.error(message)
          throw error
        }
      },

      // 清空生成的策略
      clearGeneratedStrategies: () => {
        set({ 
          generatedStrategies: [], 
          currentGeneratedStrategy: null 
        })
      },

      // =============== 市场分析功能 ===============

      // 分析市场数据
      analyzeMarket: async (symbol: string, exchange: string, timeframe: string) => {
        const key = `${symbol}-${timeframe}`
        set({ isAnalyzing: true, error: null })
        
        try {
          const apiResponse = await aiApi.analyzeMarket({
            symbols: [symbol],
            timeframe: timeframe,
            analysis_type: 'technical'
          })
          
          // Transform API response to MarketAnalysis format
          const analysis: MarketAnalysis = {
            symbol: symbol,
            timeframe: timeframe,
            trend_direction: 'neutral', // Default, could be parsed from summary
            strength: 0.5, // Default, could be calculated from signals
            support_levels: [],
            resistance_levels: [],
            technical_indicators: apiResponse.risk_assessment || {},
            summary: apiResponse.summary,
            recommendations: apiResponse.recommendations,
            confidence: 0.75 // Default confidence
          }
          
          set(state => ({
            marketAnalyses: {
              ...state.marketAnalyses,
              [key]: analysis
            },
            isAnalyzing: false
          }))
          toast.success(`${symbol} 市场分析完成`)
          return analysis
        } catch (error: any) {
          const message = String(error.response?.data?.message || '市场分析失败')
          set({ error: message, isAnalyzing: false })
          toast.error(message)
          return null
        }
      },

      // 获取交易信号 - 使用市场分析API实现
      getTradingSignals: async (symbol: string, exchange: string, timeframes: string[]) => {
        set({ isLoading: true, error: null })
        try {
          const signals = []
          for (const timeframe of timeframes) {
            const analysis = await aiApi.analyzeMarket({
              symbols: [symbol],
              timeframe: timeframe,
              analysis_type: 'technical'
            })
            signals.push({
              symbol,
              timeframe,
              signals: analysis.signals || [],
              summary: analysis.summary,
              recommendations: analysis.recommendations
            })
          }
          set({ isLoading: false })
          toast.success(`${symbol} 交易信号获取成功`)
          return signals
        } catch (error: any) {
          const message = String(error.response?.data?.message || '获取交易信号失败')
          set({ error: message, isLoading: false })
          toast.error(message)
          throw error
        }
      },

      // 风险评估 - 使用市场分析API实现
      assessRisk: async (strategyCode?: string, portfolio?: any) => {
        set({ isLoading: true, error: null })
        try {
          const prompt = strategyCode ? 
            `请评估以下策略代码的风险：\n${strategyCode}` :
            `请评估以下投资组合的风险：\n${JSON.stringify(portfolio, null, 2)}`
          
          const result = await aiApi.sendChatMessage(prompt, undefined, 'trader', 'strategy')
          const assessment = {
            riskLevel: 'medium',
            riskFactors: ['市场波动风险', '流动性风险'],
            recommendations: result.response.split('\n').filter(line => line.trim()),
            score: 0.6
          }
          set({ isLoading: false })
          toast.success('风险评估完成')
          return assessment
        } catch (error: any) {
          const message = String(error.response?.data?.message || '风险评估失败')
          set({ error: message, isLoading: false })
          toast.error(message)
          throw error
        }
      },

      // =============== 工具方法 ===============

      // 清空错误
      clearError: () => {
        set({ error: null })
      },

      // 重置所有状态
      reset: () => {
        set({
          currentAIMode: 'developer' as AIMode,
          chatSessions: {
            developer: [],
            trader: []
          },
          currentSession: null,
          messages: [],
          isTyping: false,
          generatedStrategies: [],
          isGenerating: false,
          currentGeneratedStrategy: null,
          marketAnalyses: {},
          isAnalyzing: false,
          usageStats: null,
          isLoading: false,
          error: null,
          networkStatus: 'connected',
          retryCount: 0
        })
      },

      // =============== WebSocket方法 ===============

      // 切换WebSocket/HTTP模式
      toggleWebSocket: () => {
        set(state => ({ 
          useWebSocket: !state.useWebSocket,
          aiProgress: null
        }))
        
        const { useWebSocket } = get()
        toast.success(useWebSocket ? '已切换到WebSocket模式 (实时对话)' : '已切换到HTTP模式')
      },

      // 初始化WebSocket连接
      initializeWebSocket: async () => {
        const { useWebSocket } = get()
        if (!useWebSocket) {
          console.log('🔄 [AIStore] WebSocket未启用，跳过初始化')
          return false
        }

        try {
          set({ isLoading: true, error: null })
          
          // 从authStore获取token - 修复键名问题
          const authData = localStorage.getItem('auth-storage')
          if (!authData) {
            throw new Error('未找到认证信息，请重新登录')
          }
          
          const authStore = JSON.parse(authData)
          const token = authStore?.state?.token || ''
          const isAuthenticated = authStore?.state?.isAuthenticated || false
          
          if (!token || !isAuthenticated) {
            throw new Error('认证token无效或已过期，请重新登录')
          }
          
          console.log('🔗 [AIStore] 开始初始化WebSocket连接...')
          console.log('🔑 [AIStore] 使用token:', token.substring(0, 20) + '...')
          
          // 使用当前域名作为baseUrl，不需要协议转换
          const wsService = getWebSocketAIService({
            baseUrl: window.location.origin, // 保持http/https协议
            token
          })
          
          console.log('🔄 [AIStore] WebSocket服务实例已创建，开始连接...')
          
          const connected = await wsService.initialize()
          
          if (connected) {
            const status = wsService.getConnectionStatus()
            console.log('✅ [AIStore] WebSocket连接成功:', status)
            
            set({ 
              wsConnected: true,
              wsConnectionId: status.connectionId,
              isLoading: false,
              networkStatus: 'connected'
            })
            
            toast.success('🌊 WebSocket AI服务连接成功!', { 
              icon: '🔗',
              duration: 3000
            })
            return true
          } else {
            throw new Error('WebSocket连接失败')
          }
        } catch (error: any) {
          const errorMessage = String(error?.message || error || 'WebSocket连接失败')
          console.error('❌ [AIStore] WebSocket初始化失败:', error)
          
          set({ 
            wsConnected: false,
            wsConnectionId: null,
            error: errorMessage,
            isLoading: false,
            networkStatus: 'disconnected'
          })
          
          // 如果是认证相关错误，提供更友好的提示
          if (errorMessage.includes('认证') || errorMessage.includes('登录')) {
            toast.error(`🔐 ${errorMessage}`, {
              icon: '🔑',
              duration: 6000
            })
          } else {
            toast.error(`🔌 WebSocket连接失败: ${errorMessage}`, {
              icon: '❌',
              duration: 5000
            })
          }
          return false
        }
      },

      // WebSocket发送消息
      sendMessageWebSocket: async (message: string) => {
        const { currentSession, currentAIMode, useWebSocket, wsConnected } = get()
        
        if (!useWebSocket) {
          // 回退到HTTP模式
          return get().sendMessage(message)
        }
        
        if (!wsConnected) {
          // 尝试重新连接
          const connected = await get().initializeWebSocket()
          if (!connected) {
            toast.error('WebSocket未连接，请检查网络连接')
            return false
          }
        }

        // 确保有会话
        if (!currentSession) {
          const defaultSessionName = currentAIMode === 'trader' ? '市场分析对话' : '策略开发对话'
          const success = await get().createChatSession({
            name: defaultSessionName,
            ai_mode: currentAIMode,
            session_type: 'strategy',
            description: '自动创建的WebSocket对话会话'
          })
          
          if (!success) {
            toast.error('创建对话会话失败')
            return false
          }
        }

        // 立即添加用户消息
        set(state => {
          const safeUserMessage: ChatMessage = {
            role: 'user',
            content: String(message || ''), // 确保content是字符串
            timestamp: new Date().toISOString()
          }

          return {
            messages: [...state.messages, safeUserMessage],
            isTyping: true,
            error: null,
            aiProgress: {
              isProcessing: true,
              step: 0,
              totalSteps: 4,
              status: 'preparing',
              message: '正在准备发送...'
            }
          }
        })

        try {
          // 从authStore获取token - 使用正确的键名
          const authData = localStorage.getItem('auth-storage')
          if (!authData) {
            throw new Error('认证信息丢失，请重新登录')
          }
          
          const authStore = JSON.parse(authData)
          const token = authStore?.state?.token || ''
          if (!token) {
            throw new Error('认证token无效，请重新登录')
          }
          
          const wsService = getWebSocketAIService({
            baseUrl: window.location.origin,
            token
          })

          const session = get().currentSession!
          
          // 发送WebSocket消息并处理回调
          await wsService.sendChatMessage(
            message,
            session.session_id,
            session.ai_mode,
            session.session_type,
            {
              onStart: (data) => {
                set(state => ({
                  aiProgress: {
                    ...state.aiProgress!,
                    status: 'started',
                    message: data.message || 'AI开始处理...'
                  }
                }))
              },

              onComplexityAnalysis: (data) => {
                set(state => ({
                  aiProgress: {
                    ...state.aiProgress!,
                    complexity: data.complexity,
                    estimatedTime: data.estimated_time_seconds,
                    message: data.message
                  }
                }))
              },

              onProgress: (data) => {
                set(state => ({
                  aiProgress: {
                    ...state.aiProgress!,
                    step: data.step,
                    totalSteps: data.total_steps,
                    status: data.status,
                    message: data.message
                  }
                }))
              },

              onSuccess: (data) => {
                // 确保response是字符串
                let responseContent: string;
                if (typeof data.response === 'string' && data.response) {
                  responseContent = data.response;
                } else if (data.response && typeof data.response === 'object') {
                  // 安全地访问对象属性
                  const responseObj = data.response as any;
                  responseContent = responseObj.content || responseObj.message || JSON.stringify(responseObj);
                } else if (data.message) {
                  responseContent = String(data.message);
                } else {
                  responseContent = 'AI响应错误';
                }
                
                // 确保responseContent始终是字符串
                responseContent = String(responseContent || 'AI响应为空');
                
                const assistantMessage: ChatMessage = {
                  role: 'assistant', 
                  content: responseContent,
                  timestamp: new Date().toISOString()
                }
                
                // 只有在有代码块时才添加metadata
                if (responseContent && responseContent.includes('```')) {
                  assistantMessage.metadata = {
                    codeBlock: responseContent
                  }
                }

                set(state => {
                  // 确保assistantMessage是纯粹的对象，没有循环引用
                  const safeMessage: ChatMessage = {
                    role: 'assistant',
                    content: String(assistantMessage.content),
                    timestamp: String(assistantMessage.timestamp)
                  }
                  
                  if (assistantMessage.metadata) {
                    safeMessage.metadata = {
                      codeBlock: String(assistantMessage.metadata.codeBlock || '')
                    }
                  }
                  
                  return {
                    messages: [...state.messages, safeMessage],
                    isTyping: false,
                    aiProgress: null
                  }
                })

                // 实时更新统计数据
                if (data.cost_usd > 0) {
                  get().updateUsageStatsRealtime(data.cost_usd, data.tokens_used || 0)
                  
                  toast.success(`AI回复完成 (消耗 $${data.cost_usd.toFixed(4)}, ${data.tokens_used} tokens)`, {
                    icon: '🚀',
                    duration: 4000
                  })
                }
              },

              // 🌊 流式AI回调处理
              onStreamStart: (data) => {
                console.log('🌊 [AIStore] 流式开始:', data)
                
                // 添加一个包含等待提示的assistant消息，准备接收流式内容
                set(state => {
                  const streamingMessage: ChatMessage = {
                    role: 'assistant',
                    content: '🤔 AI正在深度思考中，马上开始回复...',  // 给用户友好的等待提示
                    timestamp: new Date().toISOString(),
                    metadata: {
                      isStreaming: true,
                      isWaitingFirstChunk: true  // 标记为等待第一个数据块
                    }
                  }
                  
                  return {
                    messages: [...state.messages, streamingMessage],
                    isTyping: false,  // 不显示传统的"正在思考"
                    streamingMessage: {
                      isStreaming: true,
                      requestId: data.request_id,
                      accumulatedContent: '',
                      messageIndex: state.messages.length  // 新消息的索引
                    },
                    aiProgress: {
                      ...state.aiProgress!,
                      status: 'stream_waiting',
                      message: '🌊 AI正在深度分析，即将开始流式回复...'
                    }
                  }
                })
              },
              
              onStreamChunk: (data) => {
                console.log('📝 [AIStore] 流式数据块:', data.chunk)
                
                set(state => {
                  const { streamingMessage } = state
                  if (!streamingMessage?.isStreaming || streamingMessage.messageIndex === undefined) {
                    return state
                  }
                  
                  // 更新消息数组中对应的消息
                  const updatedMessages = [...state.messages]
                  let newAccumulatedContent = streamingMessage.accumulatedContent
                  
                  if (updatedMessages[streamingMessage.messageIndex]) {
                    const currentMessage = updatedMessages[streamingMessage.messageIndex]
                    const isFirstChunk = currentMessage.metadata?.isWaitingFirstChunk
                    
                    // 更新累积内容 - 如果是第一个chunk，替换等待提示；否则追加内容
                    newAccumulatedContent = isFirstChunk ? 
                      data.chunk : 
                      streamingMessage.accumulatedContent + data.chunk
                    
                    updatedMessages[streamingMessage.messageIndex] = {
                      ...currentMessage,
                      content: newAccumulatedContent,
                      metadata: {
                        isStreaming: true,
                        isWaitingFirstChunk: false  // 清除等待标记
                      }
                    }
                  }
                  
                  return {
                    messages: updatedMessages,
                    streamingMessage: {
                      ...streamingMessage,
                      accumulatedContent: newAccumulatedContent
                    },
                    aiProgress: {
                      ...state.aiProgress!,
                      status: 'streaming_active',
                      message: '✍️ AI正在实时生成回复...'
                    }
                  }
                })
              },
              
              onStreamEnd: (data) => {
                console.log('✅ [AIStore] 流式结束:', data)
                
                // 🚨 立即强制触发React组件更新，绕过复杂的状态检查
                set(state => {
                  console.log('🚀 [AIStore] 立即强制更新messages数组以触发React重新渲染')
                  const newMessage = {
                    role: 'assistant' as const,
                    content: data.content || '流式消息完成',
                    timestamp: new Date().toISOString(),
                    metadata: {
                      streamCompleted: true,
                      completedAt: Date.now(),
                      forceRender: Math.random() // 强制引用变化
                    }
                  }
                  
                  return {
                    ...state,
                    messages: [...state.messages, newMessage],
                    isTyping: false,
                    streamingMessage: null,
                    aiProgress: null
                  }
                })
                
                // 实时更新统计数据
                if (data.cost_usd > 0) {
                  get().updateUsageStatsRealtime(data.cost_usd, data.tokens_used || 0)
                  
                  toast.success(`🌊 流式AI回复完成 (消耗 $${data.cost_usd.toFixed(4)}, ${data.tokens_used} tokens)`, {
                    icon: '🚀',
                    duration: 4000
                  })
                }
              },
              
              onStreamError: (data) => {
                // 安全的错误对象序列化
                const safeStringifyError = (error: any): string => {
                  if (!error) return 'undefined'
                  if (typeof error === 'string') return error
                  if (typeof error === 'number' || typeof error === 'boolean') return String(error)
                  if (typeof error === 'object') {
                    try {
                      // 尝试提取常见的错误属性
                      if (error.message) return error.message
                      if (error.error) return String(error.error)
                      if (error.toString && typeof error.toString === 'function') {
                        const str = error.toString()
                        if (str !== '[object Object]') return str
                      }
                      // 最后尝试JSON.stringify，如果失败则返回默认消息
                      return JSON.stringify(error, null, 2)
                    } catch {
                      return '[Complex Error Object]'
                    }
                  }
                  return String(error)
                }
                
                console.log('❌ [AIStore] 流式错误:', {
                  error: safeStringifyError(data?.error),
                  error_type: data?.error_type,
                  message: data?.message,
                  request_id: data?.request_id
                })
                
                // 预处理错误数据，确保错误字段是字符串
                const processedErrorData = {
                  ...data,
                  error: safeStringifyError(data?.error),
                  message: data?.message || safeStringifyError(data?.error) || '流式处理失败'
                }
                
                // 清理流式状态，但不添加错误消息到聊天记录
                set(state => ({
                  ...state,
                  isTyping: false,
                  streamingMessage: null,  // 清除流式状态
                  aiProgress: null,
                  error: processedErrorData.message
                }))
                
                // 使用预处理后的数据生成友好的错误消息
                const friendlyMessage = get().getErrorMessage(processedErrorData);
                
                // 显示用户友好的错误提示
                toast.error(friendlyMessage, {
                  duration: 6000,
                  id: `stream-error-${Date.now()}` // 防止重复toast
                })
              },

              onError: (data) => {
                console.log('❌ [AIStore] onError - 处理AI对话错误:', data);
                
                // 安全的错误对象序列化 - 与onStreamError保持一致
                const safeStringifyError = (error: any): string => {
                  if (!error) return 'undefined'
                  if (typeof error === 'string') return error
                  if (typeof error === 'number' || typeof error === 'boolean') return String(error)
                  if (typeof error === 'object') {
                    try {
                      // 尝试提取常见的错误属性
                      if (error.message) return error.message
                      if (error.error) return String(error.error)
                      if (error.toString && typeof error.toString === 'function') {
                        const str = error.toString()
                        if (str !== '[object Object]') return str
                      }
                      // 最后尝试JSON.stringify，如果失败则返回默认消息
                      return JSON.stringify(error, null, 2)
                    } catch {
                      return '[Complex Error Object]'
                    }
                  }
                  return String(error)
                }
                
                // 预处理错误数据，确保错误字段是字符串
                const processedErrorData = {
                  ...data,
                  error: safeStringifyError(data?.error),
                  message: data?.message || safeStringifyError(data?.error) || 'AI处理失败'
                }
                
                // 使用预处理后的数据生成友好的错误消息
                const friendlyMessage = get().getErrorMessage(processedErrorData);
                
                // 添加错误消息到聊天记录
                const errorMessage_content = `抱歉，${friendlyMessage}`;
                
                set(state => {
                  const safeErrorMessage: ChatMessage = {
                    role: 'assistant',
                    content: String(errorMessage_content),
                    timestamp: new Date().toISOString(),
                    metadata: {
                      isError: true
                    }
                  }
                  
                  return {
                    messages: [...state.messages, safeErrorMessage],
                    isTyping: false,
                    error: String(errorMessage_content),
                    aiProgress: null
                  }
                })

                const errorMsg = data.retry_suggested 
                  ? `${friendlyMessage} (可以重试)` 
                  : friendlyMessage
                  
                toast.error(errorMsg, {
                  duration: data.retry_suggested ? 8000 : 5000,
                  icon: data.retry_suggested ? '🔄' : '❌'
                })
              }
            }
          )

          return true
        } catch (error: any) {
          console.error('❌ [DEBUG] WebSocket发送异常:', error)
          console.error('❌ [DEBUG] Error stack:', error.stack)
          console.error('❌ [DEBUG] Error details:', {
            message: error.message,
            name: error.name,
            type: typeof error,
            error
          })
          
          set({
            isTyping: false,
            error: error.message || 'WebSocket发送失败',
            aiProgress: null
          })
          
          toast.error(`WebSocket发送失败: ${error.message}`)
          return false
        }
      },
      
      // 检查网络连接状态
      checkNetworkStatus: async () => {
        try {
          set({ networkStatus: 'checking' })
          
          // 简单的网络连通性检查
          const controller = new AbortController()
          const timeoutId = setTimeout(() => controller.abort(), 5000)
          
          await fetch('/api/v1/health', {
            method: 'HEAD',
            signal: controller.signal
          })
          
          clearTimeout(timeoutId)
          set({ networkStatus: 'connected' })
          return true
        } catch (error) {
          set({ networkStatus: 'disconnected' })
          return false
        }
      },

      // 生成用户友好的错误消息
      getErrorMessage: (error: any) => {
        if (!error) return '未知错误，请重试'

        // 检查错误类型 - 修复对象序列化问题
        const errorCode = error.error_code || error.code
        let errorMessage = error.error || error.message || ''
        
        // 增强的安全对象序列化函数
        const safeStringify = (obj: any): string => {
          if (!obj) return ''
          if (typeof obj === 'string') return obj
          if (typeof obj === 'number' || typeof obj === 'boolean') return String(obj)
          if (typeof obj === 'object') {
            try {
              // 优先级1: 提取常见的错误属性
              if (obj.message && typeof obj.message === 'string') return obj.message
              if (obj.error && typeof obj.error === 'string') return obj.error
              if (obj.detail && typeof obj.detail === 'string') return obj.detail
              if (obj.description && typeof obj.description === 'string') return obj.description
              
              // 优先级2: 尝试toString方法
              if (obj.toString && typeof obj.toString === 'function') {
                const str = obj.toString()
                if (str !== '[object Object]' && str !== '[object Error]') return str
              }
              
              // 优先级3: 如果是Error对象，尝试提取name和message
              if (obj instanceof Error) {
                return obj.name ? `${obj.name}: ${obj.message}` : obj.message
              }
              
              // 优先级4: 尝试JSON.stringify
              const jsonStr = JSON.stringify(obj, Object.getOwnPropertyNames(obj), 2)
              if (jsonStr && jsonStr !== '{}' && jsonStr !== 'null' && jsonStr !== '[]') {
                return jsonStr
              }
              
              // 最后的fallback - 空对象或无有效信息的对象
              return ''
            } catch {
              return '[Serialization Error]'
            }
          }
          return String(obj)
        }
        
        errorMessage = safeStringify(errorMessage)
        
        // 基于错误码的友好提示
        switch (errorCode) {
          case 'WEBSOCKET_TIMEOUT':
            return '⏰ AI响应超时，请重试或检查网络连接'
          case 'WEBSOCKET_DISCONNECTED':
            return '🔌 连接断开，正在重新连接...'
          case 'WEBSOCKET_ERROR':
            return '📡 网络连接出现问题，请检查网络设置'
          case 'AI_PROCESSING_FAILED':
            return '🤖 AI处理失败，请稍后重试'
          case 'RATE_LIMIT_EXCEEDED':
            return '⚡ 请求过于频繁，请稍等片刻再试'
          case 'INSUFFICIENT_CREDITS':
            return '💳 AI对话额度不足，请升级会员'
          case 'INVALID_SESSION':
            return '🔄 会话已过期，将为您创建新会话'
        }

        // 基于错误消息内容的智能识别
        if (errorMessage.includes('timeout') || errorMessage.includes('超时')) {
          return '⏰ 请求超时，请重试'
        }
        if (errorMessage.includes('network') || errorMessage.includes('网络')) {
          return '📡 网络连接异常，请检查网络设置'
        }
        if (errorMessage.includes('quota') || errorMessage.includes('额度')) {
          return '💳 AI对话额度已用尽，请明日再试或升级会员'
        }
        if (errorMessage.includes('session') || errorMessage.includes('会话')) {
          return '🔄 会话异常，请刷新页面重试'
        }
        if (errorMessage.includes('auth') || errorMessage.includes('认证')) {
          return '🔐 身份认证失败，请重新登录'
        }
        if (errorMessage.includes('busy') || errorMessage.includes('繁忙') || errorMessage.includes('服务繁忙')) {
          return '🚀 AI服务繁忙，请稍后重试'
        }
        if (errorMessage.includes('unavailable') || errorMessage.includes('不可用')) {
          return '⚠️ AI服务暂时不可用，请稍后重试'
        }

        // 检查是否是空错误或无用信息
        if (!errorMessage || errorMessage.trim() === '' || 
            errorMessage === 'undefined' || errorMessage === 'null' ||
            errorMessage === '[object Object]' || errorMessage === '[object Error]') {
          return '⚠️ 服务暂时不可用，请稍后重试'
        }

        // 返回清理后的错误消息
        const cleanErrorMessage = errorMessage.replace(/^(Error:|ERROR:|错误:)\s*/i, '').trim()
        if (cleanErrorMessage) {
          return `❌ ${cleanErrorMessage}`
        }

        return '⚠️ 服务暂时不可用，请稍后重试'
      },

      // =============== 新增：回测相关方法 ===============

      // 获取AI会话最新生成的策略
      getLatestAIStrategy: async (sessionId: string) => {
        set({ isLoading: true, error: null })
        try {
          const strategy = await aiApi.getLatestAIStrategy(sessionId)
          set({ 
            generatedStrategy: strategy,
            isLoading: false 
          })
          return strategy
        } catch (error: any) {
          const message = get().getErrorMessage(error)
          set({ error: message, isLoading: false })
          toast.error(`获取策略失败: ${message}`)
          return null
        }
      },

      // 自动触发回测
      autoBacktest: async (config: AutoBacktestConfig) => {
        set({ isBacktestRunning: true, backtestProgress: null, error: null })
        try {
          const result = await aiApi.autoBacktest(config)
          
          if (result.success && result.task_id) {
            // 开始监控回测进度
            get().startBacktestMonitoring(result.task_id)
            
            toast.success('回测已启动，正在后台运行...', {
              icon: '🚀',
              duration: 4000
            })
            return true
          } else {
            throw new Error(result.message || '回测启动失败')
          }
        } catch (error: any) {
          const message = get().getErrorMessage(error)
          set({ 
            isBacktestRunning: false, 
            error: message 
          })
          toast.error(`回测启动失败: ${message}`)
          return false
        }
      },

      // 获取回测进度
      getBacktestProgress: async (taskId: string) => {
        try {
          const progress = await aiApi.getBacktestProgress(taskId)
          set({ backtestProgress: progress })
          return progress
        } catch (error: any) {
          const message = get().getErrorMessage(error)
          console.error('获取回测进度失败:', message)
          return null
        }
      },

      // 获取回测结果
      getBacktestResults: async (taskId: string) => {
        try {
          const results = await aiApi.getBacktestResults(taskId)
          set({ 
            backtestResults: results,
            showBacktestResults: true,
            isBacktestRunning: false
          })
          return results
        } catch (error: any) {
          const message = get().getErrorMessage(error)
          set({ error: message, isBacktestRunning: false })
          toast.error(`获取回测结果失败: ${message}`)
          return null
        }
      },

      // 开始回测进度监控
      startBacktestMonitoring: (taskId: string) => {
        // 清除之前的定时器
        const state = get()
        if ((state as any).backtestMonitorInterval) {
          clearInterval((state as any).backtestMonitorInterval)
        }

        const monitorInterval = setInterval(async () => {
          try {
            const progress = await get().getBacktestProgress(taskId)
            
            if (progress) {
              if (progress.status === 'completed') {
                clearInterval(monitorInterval)
                await get().getBacktestResults(taskId)
                toast.success('🎉 回测完成！', {
                  icon: '✅',
                  duration: 5000
                })
              } else if (progress.status === 'failed') {
                clearInterval(monitorInterval)
                set({ 
                  isBacktestRunning: false,
                  error: progress.error_message || '回测执行失败'
                })
                toast.error(`回测失败: ${progress.error_message || '未知错误'}`)
              }
            }
          } catch (error) {
            console.error('监控回测进度时出错:', error)
            // 不中断监控，继续尝试
          }
        }, 3000) // 每3秒检查一次

        // 保存定时器引用以便清理
        ;(get() as any).backtestMonitorInterval = monitorInterval

        // 设置超时清理（30分钟后停止监控）
        setTimeout(() => {
          clearInterval(monitorInterval)
          const currentState = get()
          if (currentState.isBacktestRunning) {
            set({ 
              isBacktestRunning: false,
              error: '回测监控超时，请手动刷新查看结果'
            })
            toast.error('回测监控超时，请刷新页面查看结果')
          }
        }, 30 * 60 * 1000) // 30分钟
      },

      // 停止回测监控
      stopBacktestMonitoring: () => {
        const state = get() as any
        if (state.backtestMonitorInterval) {
          clearInterval(state.backtestMonitorInterval)
          delete state.backtestMonitorInterval
        }
        set({ isBacktestRunning: false })
      },

      // 处理策略生成后的逻辑
      handleStrategyGenerated: async (sessionId: string) => {
        try {
          // 获取最新生成的策略
          const strategy = await get().getLatestAIStrategy(sessionId)
          
          if (strategy) {
            // 显示回测提示
            set({ showBacktestPrompt: true })
            
            toast.success('🎯 策略生成完成！现在可以配置回测参数了', {
              icon: '🚀',
              duration: 6000
            })
          }
        } catch (error: any) {
          console.error('处理策略生成后逻辑失败:', error)
        }
      },

      // 处理快速回测
      handleQuickBacktest: async (config: Partial<AutoBacktestConfig>) => {
        const { currentSession, generatedStrategy } = get()
        
        if (!currentSession || !generatedStrategy) {
          toast.error('缺少会话或策略信息，无法启动回测')
          return
        }

        // 构建完整的回测配置
        const fullConfig: AutoBacktestConfig = {
          ai_session_id: currentSession.session_id,
          strategy_code: generatedStrategy.code,
          strategy_name: generatedStrategy.name,
          auto_config: true,
          exchange: 'binance',
          symbols: ['BTC/USDT'],
          timeframes: ['1h'],
          initial_capital: 10000,
          start_date: '2024-01-01',
          end_date: '2024-12-31',
          fee_rate: 'vip0',
          ...config // 覆盖用户自定义配置
        }

        // 启动回测
        const success = await get().autoBacktest(fullConfig)
        
        if (success) {
          // 隐藏回测提示，显示进度
          set({ showBacktestPrompt: false })
        }
      },

      // 设置回测提示显示状态
      setShowBacktestPrompt: (show: boolean) => {
        set({ showBacktestPrompt: show })
      },

      // 设置回测结果显示状态
      setShowBacktestResults: (show: boolean) => {
        set({ showBacktestResults: show })
      }
    }),
    {
      name: 'ai-storage',
      // 只持久化需要的数据，避免存储过多临时状态
      partialize: (state) => ({
        currentAIMode: state.currentAIMode,
        chatSessions: state.chatSessions,
        generatedStrategies: state.generatedStrategies,
        marketAnalyses: state.marketAnalyses,
        usageStats: state.usageStats
      }),
    }
  )
)