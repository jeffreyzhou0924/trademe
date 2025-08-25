import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import toast from 'react-hot-toast'
import { aiApi } from '../services/api/ai'
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

interface AIState {
  // 双模式会话管理
  currentAIMode: AIMode
  chatSessions: Record<AIMode, ChatSession[]>  // 按模式分组的会话
  currentSession: ChatSession | null
  messages: ChatMessage[]
  isTyping: boolean
  
  // 策略生成
  generatedStrategies: GeneratedStrategy[]
  isGenerating: boolean
  currentGeneratedStrategy: GeneratedStrategy | null
  
  // 市场分析
  marketAnalyses: Record<string, MarketAnalysis> // key: symbol-timeframe
  isAnalyzing: boolean
  
  // 使用统计
  usageStats: UsageStats | null
  
  // 加载状态
  isLoading: boolean
  error: string | null
  
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
  
  // 策略生成操作
  generateStrategy: (request: StrategyGenerationRequest) => Promise<GeneratedStrategy | null>
  optimizeStrategy: (code: string, objectives: string[]) => Promise<any>
  explainStrategy: (code: string) => Promise<any>
  clearGeneratedStrategies: () => void
  
  // 市场分析操作
  analyzeMarket: (symbol: string, exchange: string, timeframe: string) => Promise<MarketAnalysis | null>
  getTradingSignals: (symbol: string, exchange: string, timeframes: string[]) => Promise<any>
  assessRisk: (strategyCode?: string, portfolio?: any) => Promise<any>
  
  // 工具方法
  clearError: () => void
  reset: () => void
  checkNetworkStatus: () => Promise<boolean>
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
      
      generatedStrategies: [],
      isGenerating: false,
      currentGeneratedStrategy: null,
      
      marketAnalyses: {},
      isAnalyzing: false,
      
      usageStats: null,
      
      isLoading: false,
      error: null,

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
          const message = error.response?.data?.message || '创建会话失败'
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
          const message = error.response?.data?.message || '加载会话列表失败'
          set({ error: message, isLoading: false })
          console.error('Load chat sessions error:', error)
        }
      },

      // 选择聊天会话
      selectChatSession: (session: ChatSession | null) => {
        set({ 
          currentSession: session,
          messages: [],
          error: null
        })

        // 如果选择了会话，异步加载聊天历史（不阻塞UI）
        if (session) {
          // 使用setTimeout确保不阻塞UI
          setTimeout(async () => {
            try {
              const response = await aiApi.getChatHistory(session.session_id, 20)
              const messages = (response?.messages || []).map((msg: any) => ({
                role: msg.message_type || msg.role,
                content: msg.content,
                timestamp: msg.created_at || msg.timestamp
              } as ChatMessage))
              
              // 只有当前会话仍然是选中的会话时才更新消息
              const currentState = get()
              if (currentState.currentSession?.session_id === session.session_id) {
                set({ 
                  messages: messages.reverse() // 确保消息按时间顺序显示
                })
              }
            } catch (error: any) {
              console.error('Load chat history failed:', error)
              // 静默失败，不阻塞UI
            }
          }, 0)
        }
      },

      // 发送消息 - 增强错误处理和重试机制
      sendMessage: async (message: string) => {
        const { currentSession, currentAIMode, retryCount } = get()
        if (!currentSession) {
          toast.error('请先选择或创建聊天会话')
          return false
        }

        // 立即添加用户消息到界面
        const userMessage: ChatMessage = {
          role: 'user',
          content: message,
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
            content: aiResponse.response,
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
          
          // 显示消耗信息
          if (aiResponse.cost_usd > 0) {
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
          const message = error.response?.data?.message || '获取使用统计失败'
          set({ error: message, isLoading: false })
          console.error('Load usage stats error:', error)
        }
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
          const strategy = await aiApi.generateStrategy(request)
          set(state => ({
            generatedStrategies: [strategy, ...state.generatedStrategies],
            currentGeneratedStrategy: strategy,
            isGenerating: false
          }))
          toast.success('策略生成成功')
          return strategy
        } catch (error: any) {
          const message = error.response?.data?.message || '策略生成失败'
          set({ error: message, isGenerating: false })
          toast.error(message)
          return null
        }
      },

      // 优化策略代码
      optimizeStrategy: async (code: string, objectives: string[]) => {
        set({ isLoading: true, error: null })
        try {
          const result = await aiApi.optimizeStrategy(code, objectives)
          set({ isLoading: false })
          toast.success('策略优化完成')
          return result
        } catch (error: any) {
          const message = error.response?.data?.message || '策略优化失败'
          set({ error: message, isLoading: false })
          toast.error(message)
          throw error
        }
      },

      // 解释策略代码
      explainStrategy: async (code: string) => {
        set({ isLoading: true, error: null })
        try {
          const result = await aiApi.explainStrategy(code)
          set({ isLoading: false })
          return result
        } catch (error: any) {
          const message = error.response?.data?.message || '策略解释失败'
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
          const analysis = await aiApi.analyzeMarket(symbol, exchange, timeframe)
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
          const message = error.response?.data?.message || '市场分析失败'
          set({ error: message, isAnalyzing: false })
          toast.error(message)
          return null
        }
      },

      // 获取交易信号
      getTradingSignals: async (symbol: string, exchange: string, timeframes: string[]) => {
        set({ isLoading: true, error: null })
        try {
          const signals = await aiApi.getTradingSignals(symbol, exchange, timeframes)
          set({ isLoading: false })
          toast.success(`${symbol} 交易信号获取成功`)
          return signals
        } catch (error: any) {
          const message = error.response?.data?.message || '获取交易信号失败'
          set({ error: message, isLoading: false })
          toast.error(message)
          throw error
        }
      },

      // 风险评估
      assessRisk: async (strategyCode?: string, portfolio?: any) => {
        set({ isLoading: true, error: null })
        try {
          const assessment = await aiApi.assessRisk(strategyCode, portfolio)
          set({ isLoading: false })
          toast.success('风险评估完成')
          return assessment
        } catch (error: any) {
          const message = error.response?.data?.message || '风险评估失败'
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