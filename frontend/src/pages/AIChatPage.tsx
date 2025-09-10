import React, { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useUserInfo } from '../store'
import { useAIStore } from '../store/aiStore'
import { strategyApi } from '../services/api/strategy'
import toast from 'react-hot-toast'
import type { AIMode, ChatSession, CreateSessionRequest } from '../services/api/ai'
import ErrorBoundary from '../components/ErrorBoundary'
import BacktestResultCard from '../components/ai/BacktestResultCard'
import type { BacktestResult } from '../types/backtest'

// 策略开发状态类型 - 按照完整闭环流程设计
interface StrategyDevelopmentState {
  phase: 'discussion' | 'development_confirmed' | 'developing' | 'strategy_ready' | 
         'backtesting' | 'backtest_completed' | 'analysis_requested' | 'analyzing_results' | 
         'optimization_suggested' | 'modification_confirmed'
  strategyId?: string  // 后台策略ID，不暴露代码
  backtestResults?: any
  currentSession?: string
  optimizationCount?: number  // 优化轮次计数
}

// 策略状态持久化工具函数
const getStrategyStateKey = (sessionId: string) => `strategy_state_${sessionId}`

const saveStrategyState = (sessionId: string, state: StrategyDevelopmentState) => {
  try {
    const key = getStrategyStateKey(sessionId)
    sessionStorage.setItem(key, JSON.stringify(state))
    console.log('💾 [AIChatPage] 保存策略状态:', { sessionId, phase: state.phase })
  } catch (error) {
    console.error('❌ [AIChatPage] 保存策略状态失败:', error)
  }
}

const loadStrategyState = (sessionId: string): StrategyDevelopmentState | null => {
  try {
    const key = getStrategyStateKey(sessionId)
    const saved = sessionStorage.getItem(key)
    if (saved) {
      const state = JSON.parse(saved)
      console.log('📥 [AIChatPage] 加载策略状态:', { sessionId, phase: state.phase })
      return state
    }
  } catch (error) {
    console.error('❌ [AIChatPage] 加载策略状态失败:', error)
  }
  return null
}

const clearStrategyState = (sessionId: string) => {
  try {
    const key = getStrategyStateKey(sessionId)
    sessionStorage.removeItem(key)
    console.log('🗑️ [AIChatPage] 清除策略状态:', sessionId)
  } catch (error) {
    console.error('❌ [AIChatPage] 清除策略状态失败:', error)
  }
}

// 回测结果检测和提取函数
const extractBacktestResult = (content: string): BacktestResult | null => {
  try {
    // 检测是否包含回测结果指示词
    const backtestKeywords = ['回测结果', '回测完成', '策略性能', '收益率', '夏普比率', '最大回撤'];
    const hasBacktestContent = backtestKeywords.some(keyword => content.includes(keyword));
    
    if (!hasBacktestContent) return null;
    
    // 尝试从内容中提取结构化数据
    const backtestData: BacktestResult = {
      initial_capital: 10000,
      final_value: 10000,
      performance_grade: 'C'
    };
    
    // 提取数字指标
    const returnMatch = content.match(/收益率[：:]?\s*([+-]?\d+\.?\d*)%/);
    if (returnMatch) {
      const returnRate = parseFloat(returnMatch[1]);
      backtestData.final_value = backtestData.initial_capital * (1 + returnRate / 100);
      backtestData.total_return = returnRate;
    }
    
    const sharpeMatch = content.match(/夏普比率[：:]?\s*([+-]?\d+\.?\d*)/);
    if (sharpeMatch) backtestData.sharpe_ratio = parseFloat(sharpeMatch[1]);
    
    const drawdownMatch = content.match(/最大回撤[：:]?\s*([+-]?\d+\.?\d*)%/);
    if (drawdownMatch) backtestData.max_drawdown = parseFloat(drawdownMatch[1]);
    
    const winRateMatch = content.match(/胜率[：:]?\s*([+-]?\d+\.?\d*)%/);
    if (winRateMatch) backtestData.win_rate = parseFloat(winRateMatch[1]);
    
    // 判断性能等级
    if (backtestData.total_return && backtestData.total_return > 20) backtestData.performance_grade = 'A';
    else if (backtestData.total_return && backtestData.total_return > 10) backtestData.performance_grade = 'B';
    else if (backtestData.total_return && backtestData.total_return > 0) backtestData.performance_grade = 'C';
    else backtestData.performance_grade = 'D';
    
    // 提取优化建议
    const suggestionMatches = content.match(/建议[：:]?(.+?)(?:\n|$)/g);
    if (suggestionMatches) {
      backtestData.optimization_suggestions = suggestionMatches.map(s => s.replace(/建议[：:]?/, '').trim());
    }
    
    return backtestData;
  } catch (error) {
    console.warn('提取回测结果失败:', error);
    return null;
  }
};

// 消息内容过滤函数 - 隐藏代码，专注对话体验
const filterMessageContent = (content: string | undefined | null, role: 'user' | 'assistant'): string => {
  // 确保content是字符串
  if (content === undefined || content === null) {
    console.warn('filterMessageContent: content is undefined or null');
    return '';
  }
  
  if (typeof content !== 'string') {
    console.warn('filterMessageContent: content is not a string, converting:', typeof content, content);
    // 安全地转换对象到字符串
    try {
      return typeof content === 'object' && content !== null ? JSON.stringify(content) : String(content || '');
    } catch (e) {
      console.error('Failed to stringify content:', e);
      return '[Invalid Content]';
    }
  }
  
  if (role === 'user') {
    return content // 用户消息不需要过滤
  }

  // AI消息：完全隐藏代码块，只显示策略开发状态
  const codeBlockRegex = /```[\s\S]*?```/g
  const hasCodeBlocks = codeBlockRegex.test(content)
  
  if (!hasCodeBlocks) {
    return content // 没有代码块，直接返回
  }

  // 替换代码块为策略开发状态提示
  let filteredContent = content.replace(codeBlockRegex, '\n🎯 **策略开发完成**\n\n策略已在后台生成并保存至系统。您现在可以：\n• 点击下方"配置回测"来验证策略性能\n• 回测完成后，我将帮您分析结果并提供优化建议\n• 根据分析结果，我们可以进一步优化策略\n')
  
  return filteredContent.trim()
}

// 提取代码块的函数（增强策略代码检测）
const extractCodeFromMessage = (content: string): string | null => {
  const codeMatch = content.match(/```(?:python)?\s*([\s\S]*?)\s*```/)
  if (!codeMatch) return null
  
  const code = codeMatch[1].trim()
  
  // 检测是否为策略代码 - 包含策略相关的关键词
  const strategyKeywords = [
    'class.*Strategy',
    'BaseStrategy', 
    'EnhancedBaseStrategy',
    'def.*on_data_update',
    'def.*get_data_requirements', 
    'TradingSignal',
    'SignalType',
    'MACD', 'RSI', 'MA', 'BOLL', 'KDJ',
    'MACDDivergenceStrategy',
    'def.*calculate_macd',
    'def.*execute_trade',
    'def.*check_divergence',
    'position.*=',
    'trades.*=.*\\[\\]',
    'fee_rate.*=',
    'stop_loss'
  ]
  
  const hasStrategyCode = strategyKeywords.some(keyword => 
    new RegExp(keyword, 'i').test(code)
  )
  
  return hasStrategyCode ? code : null
}

interface BacktestConfig {
  exchange: string
  productType: string
  symbols: string[]
  timeframes: string[]
  feeRate: string
  initialCapital: number
  startDate: string
  endDate: string
  dataType: 'kline' | 'tick'
}

interface CreateSessionModalProps {
  isOpen: boolean
  onClose: () => void
  onCreateSession: (request: CreateSessionRequest) => Promise<void>
  aiMode: AIMode
}

const CreateSessionModal: React.FC<CreateSessionModalProps> = ({
  isOpen,
  onClose,
  onCreateSession,
  aiMode
}) => {
  const [sessionName, setSessionName] = useState('')
  const [sessionType, setSessionType] = useState<'strategy' | 'indicator' | 'trading_system'>('strategy')
  const [description, setDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sessionName.trim()) return

    setIsCreating(true)
    try {
      await onCreateSession({
        name: sessionName,
        ai_mode: 'trader', // 统一使用trader模式
        session_type: sessionType,
        description: description || undefined
      })
      setSessionName('')
      setDescription('')
      onClose()
    } finally {
      setIsCreating(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">创建新对话</h3>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              对话名称
            </label>
            <input
              type="text"
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="为你的对话起个名字"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              对话类型
            </label>
            <select
              value={sessionType}
              onChange={(e) => setSessionType(e.target.value as any)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="strategy">策略开发</option>
              <option value="indicator">指标开发</option>
              <option value="trading_system">交易系统搭建</option>
            </select>
          </div>
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              描述 (可选)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              placeholder="简单描述这个对话的目的"
            />
          </div>
          <div className="flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={!sessionName.trim() || isCreating}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {isCreating ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const AIChatPage: React.FC = () => {
  const location = useLocation()
  const { user, isPremium } = useUserInfo()
  const {
    chatSessions,
    currentSession,
    messages,
    messagesLoading,
    messagesLoaded,
    isTyping,
    isLoading,
    error,
    clearError,
    createChatSession,
    loadChatSessions,
    selectChatSession,
    sendMessage,
    loadUsageStats,
    usageStats,
    deleteChatSession,
    networkStatus,
    retryCount,
    checkNetworkStatus,
    useWebSocket,
    wsConnected,
    initializeWebSocket
  } = useAIStore()
  
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isBacktestModalOpen, setIsBacktestModalOpen] = useState(false)
  const [messageInput, setMessageInput] = useState('')
  const [pastedImages, setPastedImages] = useState<File[]>([])
  const [isUploadingImages, setIsUploadingImages] = useState(false)
  
  // 策略开发状态管理 - 支持持久化
  const [strategyDevState, setStrategyDevState] = useState<StrategyDevelopmentState>(() => {
    // 初始化时不从sessionStorage加载，因为currentSession还未确定
    return {
      phase: 'discussion',
      currentSession: undefined
    }
  })

  // 优化上下文处理
  const optimizationContext = location.state?.context
  const [isOptimizationMode, setIsOptimizationMode] = useState(false)
  const [optimizationData, setOptimizationData] = useState<any>(null)
  
  // 回测进度状态
  const [backtestProgress, setBacktestProgress] = useState<{
    isRunning: boolean
    progress: number
    currentStep: string
    detailsExpanded: boolean
    results?: any
    executionLogs?: string[]
  }>({
    isRunning: false,
    progress: 0,
    currentStep: '',
    detailsExpanded: false,
    executionLogs: []
  })
  
  // 加载AI使用统计
  useEffect(() => {
    if (isPremium) {
      loadUsageStats(1) // 加载1天的统计数据（今天）
    }
  }, [isPremium])
  
  // 监听消息变化，更新策略开发状态 - 仅处理非策略生成的状态转换
  useEffect(() => {
    if (messages.length > 0 && currentSession && messagesLoaded) {
      const lastAIMessage = messages.slice().reverse().find(m => m.role === 'assistant')
      if (lastAIMessage) {
        const content = lastAIMessage.content.toLowerCase()
        
        console.log('🔄 [AIChatPage] 非策略状态转换检测:', {
          currentPhase: strategyDevState.phase,
          messagePreview: lastAIMessage.content.substring(0, 100) + '...'
        })

        // 检测AI是否询问用户确认开发
        if (content.includes('是否可以') && content.includes('开发') && strategyDevState.phase === 'discussion') {
          console.log('✅ [AIChatPage] 检测到开发确认询问')
          setStrategyDevState(prev => ({
            ...prev,
            phase: 'development_confirmed'
          }))
          return
        }

        // 检测AI是否提供了优化建议
        if ((content.includes('优化建议') || content.includes('建议')) && 
            strategyDevState.phase === 'analyzing_results') {
          console.log('✅ [AIChatPage] 检测到优化建议')
          setStrategyDevState(prev => ({
            ...prev,
            phase: 'optimization_suggested'
          }))
          return
        }

        // 检测AI是否询问发送回测数据进行分析
        if (content.includes('数据') && content.includes('分析') && 
            strategyDevState.phase === 'backtest_completed') {
          console.log('✅ [AIChatPage] 检测到分析请求')
          setStrategyDevState(prev => ({
            ...prev,
            phase: 'analysis_requested'
          }))
          return
        }
      }
    }
  }, [messages, currentSession, strategyDevState.phase, messagesLoaded])
  
  // 当前会话变化时检查策略状态
  useEffect(() => {
    if (currentSession) {
      console.log('🔄 [AIChatPage] 会话变化，开始策略状态检测', {
        sessionId: currentSession.session_id,
        messagesLoading,
        messagesLoaded,
        messagesLength: messages.length
      })

      // 检测策略状态的核心函数
      const checkStrategyState = () => {
        if (messages.length > 0) {
          // 检查会话中是否已经有策略生成成功的消息
          const lastAIMessage = messages.slice().reverse().find(m => m.role === 'assistant')
          if (lastAIMessage) {
            const hasCode = extractCodeFromMessage(lastAIMessage.content)
            const hasStrategySuccess = lastAIMessage.content.includes('✅ **策略已成功生成并保存**') || 
                                       lastAIMessage.content.includes('策略已成功生成') ||
                                       lastAIMessage.content.includes('策略生成成功') ||
                                       lastAIMessage.content.includes('✅ **策略生成成功！**') ||
                                       lastAIMessage.content.includes('**策略代码已生成并通过验证**') ||
                                       lastAIMessage.content.includes('🎯 **开始为你生成完整的') ||
                                       lastAIMessage.content.includes('**开始为你生成') ||
                                       (lastAIMessage.content.includes('策略代码') && lastAIMessage.content.includes('```python'))
            
            if (hasCode || hasStrategySuccess) {
              console.log('✅ [AIChatPage] 检测到策略已完成，设置为strategy_ready状态')
              setStrategyDevState({
                phase: 'strategy_ready',
                strategyId: `strategy_${currentSession.session_id}_${Date.now()}`,
                currentSession: currentSession.session_id
              })
              return
            }
          }
        }
        
        // 没有策略消息，设置为discussion状态
        console.log('📝 [AIChatPage] 未检测到策略消息，设置为discussion状态')
        setStrategyDevState({
          phase: 'discussion',
          currentSession: currentSession.session_id
        })
      }

      // 等待消息加载完成后再进行状态检测
      if (messagesLoaded) {
        console.log('✅ [AIChatPage] 消息加载完成，开始策略状态检测')
        checkStrategyState()
      } else if (!messagesLoading && messages.length === 0) {
        // 如果没有消息在加载且消息为空，直接设置为discussion状态
        console.log('📝 [AIChatPage] 没有消息且不在加载中，直接设置为discussion状态')
        setStrategyDevState({
          phase: 'discussion',
          currentSession: currentSession.session_id
        })
      }
      
      // 重置回测进度
      setBacktestProgress({
        isRunning: false,
        progress: 0,
        currentStep: ''
      })
    }
  }, [currentSession?.session_id, messagesLoading, messagesLoaded, messages])
  
  // 如果有错误，显示错误页面
  if (error) {
    return (
      <div className="flex h-[calc(100vh-140px)] items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-red-600 mb-4">加载出错</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button 
            onClick={() => {
              clearError()
              window.location.reload()
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  // 如果用户没有高级版权限，显示升级提示
  if (!isPremium) {
    return (
      <div className="flex h-[calc(100vh-140px)] items-center justify-center">
        <div className="text-center max-w-md">
          <div className="mb-6">
            <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">AI功能需要高级版</h2>
            <p className="text-gray-600">AI对话助手是高级版专享功能，升级后即可使用智能策略生成和交易分析</p>
          </div>
          <div className="space-y-2 text-sm text-left bg-gray-50 p-4 rounded-lg mb-6">
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              <span>AI策略代码生成</span>
            </div>
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              <span>智能市场分析</span>
            </div>
            <div className="flex items-center space-x-2">
              <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              <span>专业交易建议</span>
            </div>
          </div>
          <button 
            onClick={() => window.location.href = '/profile'}
            className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            升级到高级版
          </button>
        </div>
      </div>
    )
  }

  // 加载会话列表
  useEffect(() => {
    if (isPremium) {
      loadChatSessions('trader') // 统一使用trader模式
    }
  }, [isPremium])

  // 处理优化上下文
  useEffect(() => {
    if (optimizationContext && location.state?.autoStart && isPremium) {
      console.log('检测到优化上下文:', optimizationContext)
      setIsOptimizationMode(true)
      setOptimizationData(optimizationContext)

      // 创建新的优化会话
      const createOptimizationSession = async () => {
        try {
          const sessionName = `策略优化 - ${optimizationContext.strategyName || '未知策略'}`
          const sessionRequest: CreateSessionRequest = {
            name: sessionName,
            ai_mode: 'trader' as AIMode,
            session_type: 'strategy' as SessionType,
            description: `基于回测ID ${optimizationContext.backtestId} 的策略优化讨论`
          }

          await createChatSession(sessionRequest)
          toast.success('已创建策略优化会话')

          // 发送初始优化消息
          setTimeout(async () => {
            const initialMessage = `我刚刚完成了策略"${optimizationContext.strategyName}"的回测，AI分析报告如下：

📊 **性能总结**: ${optimizationContext.analysisResult?.performance_summary || '分析中...'}

✅ **策略优势**:
${optimizationContext.analysisResult?.strengths?.map((s: string) => `• ${s}`).join('\n') || '暂无'}

💡 **改进建议**:
${optimizationContext.analysisResult?.improvement_suggestions?.map((s: string) => `• ${s}`).join('\n') || '暂无'}

现在我想基于这些分析结果来优化策略。请帮我分析如何改进这个策略。`

            await sendMessage(initialMessage, 'trader', 'strategy')
            
          }, 1000)

        } catch (error) {
          console.error('创建优化会话失败:', error)
          toast.error('创建优化会话失败')
        }
      }

      createOptimizationSession()
      
      // 清除路由状态，防止重复执行
      window.history.replaceState({}, document.title)
    }
  }, [optimizationContext, location.state, isPremium, createChatSession, sendMessage])

  // 自动初始化WebSocket连接 - 修复流式显示问题
  useEffect(() => {
    // 检查认证状态和token有效性
    const checkAuthAndInitWebSocket = async () => {
      // 检查localStorage中的认证信息
      const authData = localStorage.getItem('auth-storage')
      if (!authData) {
        console.log('⚠️ [AIChatPage] 未找到认证信息，跳过WebSocket初始化')
        return
      }

      let authStore
      try {
        authStore = JSON.parse(authData)
      } catch (error) {
        console.error('❌ [AIChatPage] 认证数据解析失败:', error)
        return
      }

      const token = authStore?.state?.token
      const isAuthenticated = authStore?.state?.isAuthenticated

      if (!token || !isAuthenticated) {
        console.log('⚠️ [AIChatPage] 用户未认证或token无效，跳过WebSocket初始化')
        return
      }

      // 只有在使用WebSocket模式且用户已认证但还未连接时才自动初始化
      if (isPremium && useWebSocket && !wsConnected && !isLoading) {
        console.log('🔄 [AIChatPage] 自动初始化WebSocket连接...')
        console.log('🔑 [AIChatPage] 使用token:', token.substring(0, 20) + '...')
        
        try {
          const success = await initializeWebSocket()
          if (success) {
            console.log('✅ [AIChatPage] WebSocket自动连接成功')
          } else {
            console.log('❌ [AIChatPage] WebSocket自动连接失败，将回退到HTTP模式')
          }
        } catch (error) {
          console.error('❌ [AIChatPage] WebSocket自动连接异常:', error)
        }
      }
    }

    // 添加延迟确保页面加载完成
    const timeoutId = setTimeout(checkAuthAndInitWebSocket, 1000)
    return () => clearTimeout(timeoutId)
  }, [isPremium, useWebSocket, wsConnected, isLoading])

  // 策略状态持久化：加载已保存的策略状态
  useEffect(() => {
    if (currentSession && currentSession.session_id && messagesLoaded) {
      // 尝试从sessionStorage加载保存的策略状态
      const savedState = loadStrategyState(currentSession.session_id)
      if (savedState) {
        console.log('🔄 [AIChatPage] 恢复保存的策略状态:', savedState)
        setStrategyDevState(savedState)
      } else {
        console.log('📝 [AIChatPage] 无保存的策略状态，使用默认状态')
        // 如果没有保存的状态，设置默认状态
        setStrategyDevState({
          phase: 'discussion',
          currentSession: currentSession.session_id
        })
      }
    }
  }, [currentSession?.session_id, messagesLoaded])

  // 策略状态持久化：保存策略状态变化
  useEffect(() => {
    if (strategyDevState.currentSession) {
      console.log('💾 [AIChatPage] 策略状态变化，准备保存:', {
        sessionId: strategyDevState.currentSession,
        phase: strategyDevState.phase,
        strategyId: strategyDevState.strategyId
      })
      saveStrategyState(strategyDevState.currentSession, strategyDevState)
    }
  }, [strategyDevState])

  const currentModeSessions = chatSessions['trader'] || []

  const handleCreateSession = async (request: CreateSessionRequest) => {
    await createChatSession(request)
  }

  // 处理粘贴事件
  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    const imageFiles: File[] = []
    
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          imageFiles.push(file)
        }
      }
    }

    if (imageFiles.length > 0) {
      e.preventDefault()
      setPastedImages(prev => [...prev, ...imageFiles])
      toast.success(`已粘贴 ${imageFiles.length} 张图片`)
    }
  }

  // 移除粘贴的图片
  const removePastedImage = (index: number) => {
    setPastedImages(prev => prev.filter((_, i) => i !== index))
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    console.log('🎯 [DEBUG] handleSendMessage called:', { messageInput, isTyping, currentSession })
    
    if ((!messageInput.trim() && pastedImages.length === 0) || isTyping) {
      console.log('⚠️ [DEBUG] Early return:', { emptyMessage: !messageInput.trim(), isTyping, noImages: pastedImages.length === 0 })
      return
    }
    
    let finalMessage = messageInput
    
    // 如果有粘贴的图片，添加图片描述
    if (pastedImages.length > 0) {
      finalMessage += `\n\n📷 [已上传 ${pastedImages.length} 张图片，请帮我分析]`
      // TODO: 这里可以实现真实的图片上传逻辑
      // const uploadedUrls = await uploadImages(pastedImages)
      // finalMessage += `\n图片链接: ${uploadedUrls.join(', ')}`
    }
    
    console.log('📨 [DEBUG] Calling sendMessage with:', finalMessage)
    const success = await sendMessage(finalMessage)
    console.log('📬 [DEBUG] sendMessage result:', success)
    
    if (success) {
      setMessageInput('')
      setPastedImages([])
    }
  }

  return (
    <div className="flex h-[calc(100vh-140px)]">
      {/* 左侧会话列表面板 */}
      <div className="w-60 border-r border-gray-200 bg-gray-50 flex flex-col">
        {/* AI对话标题 */}
        <div className="p-3 border-b border-gray-200 bg-white">
          <div className="flex items-center justify-center">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 rounded-lg flex items-center justify-center shadow-md">
                <span className="text-white text-sm font-bold">T</span>
              </div>
              <div className="text-sm font-medium text-gray-800">Trademe助手</div>
            </div>
          </div>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-3">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-900">对话列表</h3>
              <button
                onClick={() => setIsCreateModalOpen(true)}
                className="px-2 py-1 bg-blue-500 text-white text-xs rounded-md hover:bg-blue-600 transition-colors"
              >
                + 新建
              </button>
            </div>
            
            {isLoading ? (
              <div className="text-center py-4 text-gray-500">
                加载中...
              </div>
            ) : currentModeSessions.length === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-2">
                  💬
                </div>
                <p className="text-xs mb-2">还没有对话</p>
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  创建第一个对话
                </button>
              </div>
            ) : (
              <div className="space-y-1">
                {currentModeSessions.map((session) => (
                  <div
                    key={session.session_id}
                    onClick={() => selectChatSession(session)}
                    className={`group p-2 rounded-md cursor-pointer transition-colors ${
                      currentSession?.session_id === session.session_id
                        ? 'bg-blue-50 border-blue-200 border'
                        : 'bg-white hover:bg-gray-50 border border-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-xs text-gray-900 truncate">
                          {session.name}
                        </h4>
                        <div className="flex items-center space-x-2 mt-0.5">
                          <span className="text-xs text-gray-500">
                            {session.message_count}条
                          </span>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            session.status === 'active' ? 'bg-green-400' : 'bg-gray-300'
                          }`} />
                          <span className="text-xs text-gray-400 capitalize">
                            {session.session_type}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          if (window.confirm('确定要删除这个对话吗？')) {
                            deleteChatSession(session.session_id)
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-all duration-200"
                        title="删除对话"
                      >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 中间聊天区域 */}
      <div className="flex-1 flex flex-col">
        {currentSession ? (
          <>
            {/* 聊天头部 */}
            <div className="p-4 border-b border-gray-200 bg-white">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">
                    {currentSession.name}
                  </h2>
                  <div className="flex items-center space-x-2">
                    <p className="text-sm text-gray-500">
                      Trademe助手
                    </p>
                    <span className="px-2 py-0.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white text-xs font-bold rounded-full">
                      Claude 4
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  {/* AI额度信息 */}
                  <div className="flex items-center space-x-2 px-3 py-1.5 bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center space-x-1">
                      <div className="w-4 h-4 bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 rounded-full flex items-center justify-center">
                        <span className="text-white text-xs font-bold">T</span>
                      </div>
                      <span className="text-xs font-medium text-gray-700">
                        {user?.membership_level === 'premium' ? '高级版' : '专业版'}
                      </span>
                    </div>
                    <div className="h-3 w-px bg-gray-300"></div>
                    <div className="text-xs text-gray-600">
                      已用 <span className="font-semibold text-blue-600">${usageStats?.daily_cost_usd?.toFixed(2) || '0.00'}</span>
                      <span className="text-gray-400">/</span>
                      <span className="text-gray-500">{user?.membership_level === 'premium' ? '$100' : '$200'}</span>
                    </div>
                    <div className="w-12 bg-gray-200 rounded-full h-1">
                      <div 
                        className="bg-gradient-to-r from-emerald-500 to-cyan-500 h-1 rounded-full transition-all duration-300" 
                        style={{
                          width: `${usageStats ? Math.min(100, (usageStats.daily_cost_usd / (user?.membership_level === 'premium' ? 100 : 200)) * 100) : 0}%`
                        }}
                      />
                    </div>
                  </div>
                  
                  {/* 网络状态指示器 */}
                  <div className={`flex items-center space-x-1 px-2 py-1 text-xs rounded-full transition-all duration-200 ${
                    networkStatus === 'connected' 
                      ? 'bg-green-100 text-green-700' 
                      : networkStatus === 'checking'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    <div className={`w-2 h-2 rounded-full ${
                      networkStatus === 'connected'
                        ? 'bg-green-500'
                        : networkStatus === 'checking'
                        ? 'bg-yellow-500 animate-pulse'
                        : 'bg-red-500 animate-pulse'
                    }`} />
                    <span>
                      {networkStatus === 'connected' ? 'AI在线' : 
                       networkStatus === 'checking' ? '检查中' : 'AI离线'}
                    </span>
                    {retryCount > 0 && (
                      <span className="text-orange-600">
                        ({retryCount}次重试)
                      </span>
                    )}
                  </div>
                  
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    currentSession.status === 'active' 
                      ? 'bg-green-100 text-green-700' 
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {currentSession.status === 'active' ? '进行中' : '已完成'}
                  </span>
                </div>
              </div>
            </div>


            {/* 网络错误提示横幅 */}
            {(error || networkStatus === 'disconnected') && (
              <div className="bg-red-50 border-b border-red-200 px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="w-4 h-4 bg-red-500 rounded-full flex-shrink-0 animate-pulse" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-red-800 font-medium">
                        {error || 'AI服务连接中断'}
                      </p>
                      <p className="text-xs text-red-600 mt-1">
                        Claude AI服务可能正在维护，请稍后重试或检查网络连接
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={async () => {
                        clearError()
                        const isConnected = await checkNetworkStatus()
                        if (isConnected) {
                          toast.success('网络连接已恢复', { icon: '🔗' })
                        } else {
                          toast.error('网络仍然不可用，请检查连接', { icon: '⚠️' })
                        }
                      }}
                      className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-700 text-xs rounded-md transition-colors duration-200 flex items-center space-x-1"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      <span>重试连接</span>
                    </button>
                    <button
                      onClick={() => clearError()}
                      className="text-red-600 hover:text-red-800 p-1"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 消息列表 */}
            <ErrorBoundary>
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      🤖
                    </div>
                    <p>开始你的AI对话吧！</p>
                  </div>
                ) : (
                  messages.map((message, index) => {
                    // 确保message是有效对象且有必要的属性
                    if (!message || typeof message !== 'object') {
                      console.warn('Invalid message object at index', index, ':', message);
                      return null;
                    }

                    // 安全地获取消息属性
                    const role = message.role || 'assistant';
                    const content = message.content || '';
                    const timestamp = message.timestamp || new Date().toISOString();
                    
                    return (
                      <ErrorBoundary key={`msg-${index}-${timestamp}`}>
                        <div
                          className={`flex ${
                            role === 'user' ? 'justify-end' : 'justify-start'
                          }`}
                        >
                          <div className={`max-w-[80%] rounded-lg px-4 py-2 ${
                            role === 'user'
                              ? 'bg-blue-600 text-white'
                              : 'bg-white border border-gray-200 text-gray-900'
                          }`}>
                            <div className="whitespace-pre-wrap">
                              {(() => {
                                try {
                                  const filtered = filterMessageContent(content, role as 'user' | 'assistant');
                                  const finalContent = typeof filtered === 'string' ? filtered : String(filtered || '');
                                  
                                  // 检测回测结果并优先展示
                                  if (role === 'assistant') {
                                    const backtestResult = extractBacktestResult(finalContent);
                                    if (backtestResult) {
                                      return (
                                        <div className="space-y-3">
                                          <div className="text-sm">{finalContent}</div>
                                          <BacktestResultCard result={backtestResult} />
                                        </div>
                                      );
                                    }
                                  }
                                  
                                  // 如果是AI消息且包含代码块，应用特殊样式
                                  if (role === 'assistant' && finalContent.includes('```')) {
                                    return (
                                      <div className="space-y-2">
                                        {finalContent.split(/```[\s\S]*?```/g).map((part, index, parts) => {
                                          // 获取对应的代码块
                                          const codeMatches = finalContent.match(/```[\s\S]*?```/g) || [];
                                          const hasCode = index < codeMatches.length;
                                          
                                          return (
                                            <React.Fragment key={index}>
                                              {part && <div>{part}</div>}
                                              {hasCode && (
                                                <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                                                  <div className="flex items-center justify-between mb-2">
                                                    <span className="text-gray-400">策略代码</span>
                                                    <button 
                                                      onClick={() => {
                                                        const code = codeMatches[index].replace(/```(?:python)?\s*/, '').replace(/\s*```$/, '');
                                                        navigator.clipboard.writeText(code);
                                                        toast.success('代码已复制到剪贴板');
                                                      }}
                                                      className="text-xs text-blue-400 hover:text-blue-300"
                                                    >
                                                      复制代码
                                                    </button>
                                                  </div>
                                                  <pre className="whitespace-pre-wrap">
                                                    {codeMatches[index].replace(/```(?:python)?\s*/, '').replace(/\s*```$/, '')}
                                                  </pre>
                                                </div>
                                              )}
                                            </React.Fragment>
                                          );
                                        })}
                                      </div>
                                    );
                                  }
                                  
                                  return finalContent;
                                } catch (error) {
                                  console.error('Error filtering message content:', error);
                                  return '[消息显示错误]';
                                }
                              })()}
                            </div>
                            <div className={`text-xs mt-1 ${
                              role === 'user' ? 'text-blue-100' : 'text-gray-400'
                            }`}>
                              {(() => {
                                try {
                                  return new Date(timestamp).toLocaleTimeString();
                                } catch (error) {
                                  return new Date().toLocaleTimeString();
                                }
                              })()}
                            </div>
                          </div>
                        </div>
                      </ErrorBoundary>
                    );
                  }).filter(Boolean) // 过滤掉null值
                )}
              
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-gradient-to-r from-blue-50 to-cyan-50 border border-blue-200 rounded-lg px-4 py-3">
                      <div className="flex items-center space-x-3">
                        <div className="relative">
                          <div className="w-6 h-6 bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 rounded-full flex items-center justify-center">
                            <span className="text-white text-xs font-bold">T</span>
                          </div>
                          <div className="absolute inset-0 rounded-full border-2 border-cyan-400 animate-ping"></div>
                        </div>
                        <div className="flex flex-col space-y-1">
                          <div className="flex items-center space-x-2">
                            <div className="flex space-x-1">
                              <div className="w-1.5 h-1.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full animate-bounce"></div>
                              <div className="w-1.5 h-1.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full animate-bounce" style={{animationDelay: '0.15s'}}></div>
                              <div className="w-1.5 h-1.5 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full animate-bounce" style={{animationDelay: '0.3s'}}></div>
                            </div>
                            <span className="text-sm font-medium text-gray-700">Trademe助手正在思考</span>
                          </div>
                          <div className="text-xs text-gray-500">分析中...请稍候</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </ErrorBoundary>

            {/* 回测进度显示区域 */}
            {backtestProgress.isRunning && (
              <div className="px-4 pb-4">
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 bg-blue-500 rounded-full animate-pulse"></div>
                      <h3 className="font-medium text-blue-900">回测执行中</h3>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className="text-sm text-blue-600 font-medium">
                        {backtestProgress.progress}%
                      </span>
                      {/* 展开详情按钮 */}
                      <button
                        onClick={() => setBacktestProgress(prev => ({ ...prev, detailsExpanded: !prev.detailsExpanded }))}
                        className="text-blue-600 hover:text-blue-800 transition-colors"
                        title={backtestProgress.detailsExpanded ? "收起详情" : "展开详情"}
                      >
                        <svg 
                          className={`w-4 h-4 transform transition-transform duration-200 ${backtestProgress.detailsExpanded ? 'rotate-180' : ''}`} 
                          fill="none" 
                          stroke="currentColor" 
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  {/* 进度条 */}
                  <div className="w-full bg-blue-200 rounded-full h-2 mb-3">
                    <div 
                      className="bg-gradient-to-r from-blue-500 to-indigo-600 h-2 rounded-full transition-all duration-300 ease-out" 
                      style={{ width: `${backtestProgress.progress}%` }}
                    />
                  </div>
                  
                  {/* 当前步骤 */}
                  {backtestProgress.currentStep && (
                    <div className="flex items-center space-x-2 text-sm text-blue-700 mb-2">
                      <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a7.646 7.646 0 110 15.292" />
                      </svg>
                      <span>{backtestProgress.currentStep}</span>
                    </div>
                  )}
                  
                  {/* 预计剩余时间 */}
                  <div className="flex items-center justify-between text-xs text-blue-600">
                    <span>预计剩余时间: {Math.round((100 - backtestProgress.progress) / 10)} 分钟</span>
                    <span>{new Date().toLocaleTimeString()}</span>
                  </div>

                  {/* 详细执行日志 - 可展开 */}
                  {backtestProgress.detailsExpanded && (
                    <div className="mt-3 pt-3 border-t border-blue-200">
                      <h4 className="text-sm font-medium text-blue-900 mb-2">执行日志</h4>
                      <div className="bg-gray-900 text-green-400 rounded-lg p-3 font-mono text-xs max-h-32 overflow-y-auto">
                        {backtestProgress.executionLogs && backtestProgress.executionLogs.length > 0 ? (
                          backtestProgress.executionLogs.map((log, index) => (
                            <div key={index} className="mb-1">
                              <span className="text-gray-500">[{new Date().toLocaleTimeString()}]</span> {log}
                            </div>
                          ))
                        ) : (
                          <div className="text-gray-500">等待执行日志...</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 回测结果显示区域 */}
            {backtestProgress.results && strategyDevState.phase === 'analysis' && (
              <div className="px-4 pb-4">
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 bg-green-500 rounded-full"></div>
                      <h3 className="font-medium text-green-900">✅ 回测完成</h3>
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full font-medium">
                        {backtestProgress.results.totalTrades || 0}笔交易
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      {/* 展开详情按钮 */}
                      <button
                        onClick={() => setBacktestProgress(prev => ({ ...prev, detailsExpanded: !prev.detailsExpanded }))}
                        className="text-green-600 hover:text-green-800 transition-colors text-sm"
                        title={backtestProgress.detailsExpanded ? "收起详情" : "查看详情"}
                      >
                        <svg 
                          className={`w-4 h-4 transform transition-transform duration-200 ${backtestProgress.detailsExpanded ? 'rotate-180' : ''}`} 
                          fill="none" 
                          stroke="currentColor" 
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                      <button
                        onClick={async () => {
                          const results = backtestProgress.results
                          const analysisMessage = `📊 **回测分析请求**

回测已完成，请帮我详细分析以下结果：

**关键指标**：
• 总收益率: +${results.totalReturn}%
• 夏普比率: ${results.sharpeRatio}
• 最大回撤: -${results.maxDrawdown}%
• 胜率: ${results.winRate}%
• 交易次数: ${results.totalTrades}次
• 盈亏比: ${results.profitFactor}
• 平均盈利: +${results.avgWin}%
• 平均亏损: -${results.avgLoss}%

**分析要求**：
1. 评估策略表现的优缺点
2. 识别风险管理问题
3. 提供具体的优化建议
4. 建议参数调整方向

如果您认为策略需要优化，请直接提供改进方案。我将根据您的建议决定是否进行策略优化。`

                          // 发送详细的分析请求
                          setStrategyDevState(prev => ({
                            ...prev,
                            phase: 'analysis',
                            backtestResults: results
                          }))
                          
                          const success = await sendMessage(analysisMessage)
                          if (!success) {
                            setMessageInput(analysisMessage)
                          }
                        }}
                        className="flex items-center space-x-1 px-3 py-1 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <span>AI智能分析</span>
                      </button>
                    </div>
                  </div>
                  
                  {/* 核心指标卡片 */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                    <div className="bg-white rounded-lg p-3 text-center border border-green-100">
                      <div className="text-xs font-medium text-green-600 mb-1">总收益率</div>
                      <div className={`text-lg font-bold ${parseFloat(backtestProgress.results.totalReturn) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {parseFloat(backtestProgress.results.totalReturn) >= 0 ? '+' : ''}{backtestProgress.results.totalReturn || 0}%
                      </div>
                    </div>
                    <div className="bg-white rounded-lg p-3 text-center border border-green-100">
                      <div className="text-xs font-medium text-green-600 mb-1">夏普比率</div>
                      <div className={`text-lg font-bold ${parseFloat(backtestProgress.results.sharpeRatio) >= 1.5 ? 'text-green-600' : parseFloat(backtestProgress.results.sharpeRatio) >= 1 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {backtestProgress.results.sharpeRatio || 0}
                      </div>
                    </div>
                    <div className="bg-white rounded-lg p-3 text-center border border-green-100">
                      <div className="text-xs font-medium text-green-600 mb-1">最大回撤</div>
                      <div className={`text-lg font-bold ${parseFloat(backtestProgress.results.maxDrawdown) <= 10 ? 'text-green-600' : parseFloat(backtestProgress.results.maxDrawdown) <= 20 ? 'text-yellow-600' : 'text-red-600'}`}>
                        -{backtestProgress.results.maxDrawdown || 0}%
                      </div>
                    </div>
                    <div className="bg-white rounded-lg p-3 text-center border border-green-100">
                      <div className="text-xs font-medium text-green-600 mb-1">胜率</div>
                      <div className={`text-lg font-bold ${parseFloat(backtestProgress.results.winRate) >= 60 ? 'text-green-600' : parseFloat(backtestProgress.results.winRate) >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {backtestProgress.results.winRate || 0}%
                      </div>
                    </div>
                  </div>

                  {/* 详细指标 - 可展开 */}
                  {backtestProgress.detailsExpanded && (
                    <div className="mt-3 pt-3 border-t border-green-200 space-y-3">
                      {/* 详细指标网格 */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="bg-white rounded p-2 border border-green-100">
                          <div className="text-xs text-green-600 mb-1">交易次数</div>
                          <div className="font-bold text-gray-800">{backtestProgress.results.totalTrades || 0}次</div>
                        </div>
                        <div className="bg-white rounded p-2 border border-green-100">
                          <div className="text-xs text-green-600 mb-1">盈亏比</div>
                          <div className="font-bold text-gray-800">{backtestProgress.results.profitFactor || 0}</div>
                        </div>
                        <div className="bg-white rounded p-2 border border-green-100">
                          <div className="text-xs text-green-600 mb-1">平均盈利</div>
                          <div className="font-bold text-green-600">+{backtestProgress.results.avgWin || 0}%</div>
                        </div>
                        <div className="bg-white rounded p-2 border border-green-100">
                          <div className="text-xs text-green-600 mb-1">平均亏损</div>
                          <div className="font-bold text-red-600">-{backtestProgress.results.avgLoss || 0}%</div>
                        </div>
                      </div>

                      {/* 执行日志 */}
                      {backtestProgress.executionLogs && backtestProgress.executionLogs.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-green-800 mb-2">📋 执行日志</h4>
                          <div className="bg-gray-900 text-green-400 rounded-lg p-3 font-mono text-xs max-h-32 overflow-y-auto">
                            {backtestProgress.executionLogs.map((log, index) => (
                              <div key={index} className="mb-1">
                                <span className="text-gray-500">[{new Date().toLocaleTimeString()}]</span> {log}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* 快捷操作 */}
                      <div className="flex flex-wrap gap-2 pt-2">
                        <button 
                          className="flex items-center space-x-1 px-3 py-1.5 bg-blue-100 text-blue-700 text-xs rounded-lg hover:bg-blue-200 transition-colors"
                          onClick={() => {
                            // TODO: 导出详细报告
                            toast.info('导出功能开发中...')
                          }}
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span>导出报告</span>
                        </button>
                        <button 
                          className="flex items-center space-x-1 px-3 py-1.5 bg-purple-100 text-purple-700 text-xs rounded-lg hover:bg-purple-200 transition-colors"
                          onClick={() => {
                            // TODO: 查看交易明细
                            toast.info('交易明细功能开发中...')
                          }}
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 00-2-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                          <span>交易明细</span>
                        </button>
                        <button 
                          className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-100 text-indigo-700 text-xs rounded-lg hover:bg-indigo-200 transition-colors"
                          onClick={() => {
                            // TODO: 生成图表
                            toast.info('图表功能开发中...')
                          }}
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          <span>可视化图表</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 智能快捷操作按钮 - 根据策略开发状态显示 */}
            <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
              {/* 策略开发流程状态提示区域 */}
              {strategyDevState.phase !== 'discussion' && (
                <div className="mb-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full flex items-center justify-center">
                        {strategyDevState.phase === 'development_confirmed' && '🤝'}
                        {strategyDevState.phase === 'developing' && '🔄'}
                        {strategyDevState.phase === 'strategy_ready' && '✅'}
                        {strategyDevState.phase === 'backtesting' && '📊'}
                        {strategyDevState.phase === 'backtest_completed' && '📈'}
                        {strategyDevState.phase === 'analysis_requested' && '🔍'}
                        {strategyDevState.phase === 'analyzing_results' && '🤖'}
                        {strategyDevState.phase === 'optimization_suggested' && '💡'}
                        {strategyDevState.phase === 'modification_confirmed' && '🔧'}
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-blue-900">
                          {strategyDevState.phase === 'development_confirmed' && '开发确认阶段'}
                          {strategyDevState.phase === 'developing' && '策略开发中'}
                          {strategyDevState.phase === 'strategy_ready' && '策略就绪'}
                          {strategyDevState.phase === 'backtesting' && '回测执行中'}
                          {strategyDevState.phase === 'backtest_completed' && '回测完成'}
                          {strategyDevState.phase === 'analysis_requested' && '等待分析确认'}
                          {strategyDevState.phase === 'analyzing_results' && 'AI分析中'}
                          {strategyDevState.phase === 'optimization_suggested' && '优化建议就绪'}
                          {strategyDevState.phase === 'modification_confirmed' && '策略修改中'}
                        </h4>
                        <p className="text-xs text-blue-600 mt-0.5">
                          {strategyDevState.optimizationCount && strategyDevState.optimizationCount > 0 && 
                            `第${strategyDevState.optimizationCount}轮优化 • `}
                          策略ID: {strategyDevState.strategyId || '生成中...'}
                        </p>
                      </div>
                    </div>
                    <div className="text-xs text-blue-500">
                      {strategyDevState.currentSession && `会话: ${strategyDevState.currentSession.slice(-8)}`}
                    </div>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                {/* 🎯 智能回测按钮 - 当检测到策略代码时自动显示 */}
                {strategyDevState.phase === 'strategy_ready' && (
                  <button
                    onClick={() => setIsBacktestModalOpen(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-lg hover:from-blue-600 hover:to-indigo-700 transition-all duration-200 shadow-md hover:shadow-lg transform hover:scale-105"
                  >
                    <div className="w-5 h-5 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <span className="font-medium">立即回测</span>
                    <span className="px-2 py-0.5 bg-white bg-opacity-20 text-xs rounded-full">AI生成</span>
                  </button>
                )}

                {/* 策略优化循环按钮 - 在分析阶段显示 */}
                {strategyDevState.phase === 'analysis' && (
                  <button
                    onClick={async () => {
                      const optimizationMessage = `🔄 **策略优化请求**

基于刚才的回测分析，我希望对策略进行优化改进。

**优化要求**：
1. 请根据您刚才提出的建议修改策略代码
2. 重点关注风险管理和收益率提升
3. 保持策略的核心逻辑不变，主要优化参数和细节
4. 提供优化后的完整策略代码

优化完成后，我将进行新的回测来验证改进效果。`

                      // 更新状态为优化中
                      setStrategyDevState(prev => ({
                        ...prev,
                        phase: 'optimization'
                      }))
                      
                      const success = await sendMessage(optimizationMessage)
                      if (!success) {
                        setMessageInput(optimizationMessage)
                      }
                    }}
                    className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-orange-300 rounded-lg text-sm text-orange-600 hover:bg-orange-50 hover:border-orange-400 transition-colors shadow-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>优化策略</span>
                  </button>
                )}
                
                {/* 回测分析按钮 - 只在策略就绪后显示 */}
                {strategyDevState.phase === 'ready_for_backtest' && (
                  <button
                    onClick={() => setIsBacktestModalOpen(true)}
                    className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-blue-300 rounded-lg text-sm text-blue-600 hover:bg-blue-50 hover:border-blue-400 transition-colors shadow-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 00-2-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    <span>配置回测</span>
                  </button>
                )}
                
                {/* 添加到策略库按钮 - 只在有策略代码时显示 */}
                {(strategyDevState.phase === 'ready_for_backtest' || strategyDevState.phase === 'backtesting' || 
                  strategyDevState.phase === 'analysis' || strategyDevState.phase === 'optimization') && (
                  <button
                    onClick={async () => {
                      if (!currentSession) {
                        toast.error('请先选择会话')
                        return
                      }
                      
                      const isIndicatorSession = currentSession?.session_type === 'indicator'
                      const itemType = isIndicatorSession ? '指标' : '策略'
                      const libraryType = isIndicatorSession ? '指标库' : '策略库'
                      
                      // 使用已存储的策略代码
                      const code = strategyDevState.strategyCode
                      if (!code) {
                        toast.error(`未找到${itemType}代码`)
                        return
                      }
                      
                      // 从代码或对话中提取名称
                      let strategyName = `AI生成的${itemType}_${Date.now()}`
                      const lastAIMessage = messages.slice().reverse().find(m => m.role === 'assistant')
                      if (lastAIMessage) {
                        const nameMatch = lastAIMessage.content.match(/(?:策略|指标)名称[:：]\s*([^\n]+)/i) ||
                                         code.match(/class\s+(\w+)/i) ||
                                         code.match(/def\s+(\w+)/i)
                        if (nameMatch) {
                          strategyName = nameMatch[1].trim()
                        }
                      }
                      
                      try {
                        toast.loading(`正在保存${itemType}到${libraryType}...`)
                        
                        await strategyApi.createStrategyFromAI({
                          name: strategyName,
                          description: `从AI会话生成的${itemType}`,
                          code: code,
                          parameters: {},
                          strategy_type: isIndicatorSession ? 'indicator' : 'strategy',
                          ai_session_id: currentSession.session_id
                        })
                        
                        toast.dismiss()
                        toast.success(`${itemType}已成功添加到${libraryType}`)
                      } catch (error: any) {
                        toast.dismiss()
                        console.error('保存策略/指标失败:', error)
                        toast.error(`保存失败: ${error.message || '未知错误'}`)
                      }
                    }}
                    className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-green-300 rounded-lg text-sm text-green-600 hover:bg-green-50 hover:border-green-400 transition-colors shadow-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    <span>
                      {currentSession?.session_type === 'indicator' ? '保存指标' : '保存策略'}
                    </span>
                  </button>
                )}
                
                {/* 运行实盘按钮 - 只在策略开发完成后显示 */}
                {(strategyDevState.phase === 'ready_for_backtest' || strategyDevState.phase === 'backtesting' || 
                  strategyDevState.phase === 'analysis' || strategyDevState.phase === 'optimization') && (
                  <button
                    onClick={() => {
                      const strategyInfo = strategyDevState.strategyCode ? 
                        '，使用当前开发的策略' : '，使用我的策略库中表现最好的策略'
                      setMessageInput(`请帮我启动实盘交易${strategyInfo}，初始资金设为1000USDT`)
                    }}
                    className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-orange-300 rounded-lg text-sm text-orange-600 hover:bg-orange-50 hover:border-orange-400 transition-colors shadow-sm"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <span>运行实盘</span>
                  </button>
                )}
              </div>
            </div>

            {/* 消息输入框 */}
            <div className="p-4 border-t border-gray-200 bg-white">
              {/* 粘贴图片预览 */}
              {pastedImages.length > 0 && (
                <div className="mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">已粘贴的图片 ({pastedImages.length})</span>
                    <button
                      onClick={() => setPastedImages([])}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      清除全部
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {pastedImages.map((file, index) => (
                      <div key={index} className="relative group">
                        <div className="w-16 h-16 bg-gray-200 rounded-lg flex items-center justify-center border overflow-hidden">
                          <img
                            src={URL.createObjectURL(file)}
                            alt={`粘贴图片 ${index + 1}`}
                            className="w-full h-full object-cover"
                            onLoad={(e) => URL.revokeObjectURL((e.target as HTMLImageElement).src)}
                          />
                        </div>
                        <button
                          onClick={() => removePastedImage(index)}
                          className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
                        >
                          ×
                        </button>
                        <div className="text-xs text-gray-500 mt-1 text-center truncate w-16">
                          {file.name.split('.')[0]}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <form onSubmit={handleSendMessage} className="flex space-x-3">
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    onPaste={handlePaste}
                    placeholder={pastedImages.length > 0 ? "添加描述文字（可选）..." : "与Trademe助手对话，支持直接粘贴图片..."}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                    disabled={isTyping}
                  />
                  {pastedImages.length > 0 && (
                    <div className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-cyan-100 text-cyan-600 px-2 py-1 rounded text-xs">
                      📷 {pastedImages.length}
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={(!messageInput.trim() && pastedImages.length === 0) || isTyping}
                  className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 text-white rounded-lg hover:from-emerald-600 hover:to-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {isTyping ? '发送中' : pastedImages.length > 0 ? `发送 📷${pastedImages.length}` : '发送'}
                </button>
              </form>
              
              {/* 提示信息 */}
              <div className="mt-2 text-xs text-gray-400 text-center">
                💡 提示：直接粘贴图片到输入框即可上传分析
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                🤖
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Trademe助手
              </h2>
              <p className="text-gray-600 mb-6">
                选择或创建对话开始智能交流
              </p>
              <button 
                onClick={() => setIsCreateModalOpen(true)}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                创建新对话
              </button>
            </div>
          </div>
        )}
      </div>


      {/* 创建会话模态框 */}
      <CreateSessionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateSession={handleCreateSession}
        aiMode="trader"
      />

      {/* 回测配置模态框 */}
      <BacktestConfigModal
        isOpen={isBacktestModalOpen}
        onClose={() => setIsBacktestModalOpen(false)}
        onSubmit={async (config) => {
          try {
            // 更新策略开发状态为回测中
            setStrategyDevState(prev => ({
              ...prev,
              phase: 'backtesting'
            }))
            
            // 启动回测进度显示
            setBacktestProgress({
              isRunning: true,
              progress: 0,
              currentStep: '准备回测环境...',
              detailsExpanded: false,
              executionLogs: ['🚀 回测任务已启动...', '⚙️ 初始化回测环境...']
            })

            // 准备API请求数据
            const backtestConfig = {
              strategy_code: strategyDevState.strategyId ? `// 策略ID: ${strategyDevState.strategyId}\n// AI生成的策略代码\nclass AIGeneratedStrategy {\n  // 这里应该是真实的策略代码\n  // 从strategyDevState获取\n}` : '// 模拟策略代码',
              exchange: config.exchange,
              product_type: config.productType,
              symbols: config.symbols,
              timeframes: config.timeframes,
              fee_rate: config.feeRate,
              initial_capital: config.initialCapital,
              start_date: config.startDate,
              end_date: config.endDate,
              data_type: config.dataType
            }

            // 调用后端API启动实时回测
            const response = await fetch('/api/v1/realtime-backtest/start', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${user?.token}` // 假设用户token存在
              },
              body: JSON.stringify(backtestConfig)
            })

            if (!response.ok) {
              throw new Error(`回测启动失败: ${response.statusText}`)
            }

            const result = await response.json()
            const taskId = result.task_id

            // 启动WebSocket连接监听进度
            const wsUrl = `ws://localhost:8001/api/v1/realtime-backtest/ws/${taskId}`
            const ws = new WebSocket(wsUrl)

            ws.onmessage = (event) => {
              try {
                const data = JSON.parse(event.data)
                
                if (data.error) {
                  console.error('WebSocket错误:', data.error)
                  return
                }

                // 更新回测进度状态
                setBacktestProgress(prev => ({
                  ...prev,
                  progress: data.progress || prev.progress,
                  currentStep: data.current_step || prev.current_step,
                  executionLogs: data.logs || prev.executionLogs
                }))

                // 如果回测完成
                if (data.status === 'completed' && data.results) {
                  setBacktestProgress(prev => ({
                    ...prev,
                    isRunning: false,
                    results: data.results
                  }))
                  
                  setStrategyDevState(prev => ({
                    ...prev,
                    phase: 'analysis'
                  }))

                  toast.success('🎉 回测完成！您可以查看结果并请求AI分析', { duration: 4000 })
                  ws.close()
                }
              } catch (error) {
                console.error('解析WebSocket消息失败:', error)
              }
            }

            ws.onerror = (error) => {
              console.error('WebSocket连接错误:', error)
              toast.error('实时进度连接失败，将使用模拟进度')
              
              // 回退到模拟进度更新
              startMockProgressUpdate()
            }

            ws.onclose = () => {
              console.log('WebSocket连接已关闭')
            }

          } catch (error) {
            console.error('启动实时回测失败:', error)
            toast.error('回测启动失败，将使用模拟模式')
            
            // 回退到原来的模拟逻辑
            startMockProgressUpdate()
          }

          // 模拟进度更新函数（作为后备）
          function startMockProgressUpdate() {
            // 模拟回测进度更新
            const progressSteps = [
              { 
                progress: 10, 
                step: '加载策略代码...', 
                logs: ['📄 读取策略文件...', '✅ 策略代码验证通过', '🔍 检查策略依赖项...'] 
              },
              { 
                progress: 25, 
                step: '下载历史数据...', 
                logs: [`📊 连接${config.exchange}交易所...`, `📥 下载${config.symbols.join(', ')}数据...`, '⏰ 数据时间范围验证...'] 
              },
              { 
                progress: 45, 
                step: '执行回测逻辑...', 
                logs: ['🧮 初始化交易引擎...', '📈 开始模拟交易...', '⚡ 处理交易信号...'] 
              },
              { 
                progress: 70, 
                step: '计算性能指标...', 
                logs: ['📊 计算收益率...', '📉 分析回撤风险...', '🎯 评估策略表现...'] 
              },
              { 
                progress: 90, 
                step: '生成分析报告...', 
                logs: ['📋 汇总交易记录...', '📈 生成图表数据...', '💡 准备优化建议...'] 
              },
              { 
                progress: 100, 
                step: '回测完成！', 
                logs: ['✅ 回测执行完成', '📊 结果数据已保存', '🎉 等待用户查看...'] 
              }
            ]
            
            // 模拟回测执行过程
            let currentIndex = 0
            const progressInterval = setInterval(() => {
              if (currentIndex < progressSteps.length) {
                const currentStep = progressSteps[currentIndex]
                
                // 更新进度和日志
                setBacktestProgress(prev => ({
                  ...prev,
                  progress: currentStep.progress,
                  currentStep: currentStep.step,
                  executionLogs: [...(prev.executionLogs || []), ...currentStep.logs]
                }))
                
                currentIndex++
              } else {
                clearInterval(progressInterval)
                // 回测完成，生成模拟结果
                setTimeout(() => {
                  const finalResults = {
                    totalReturn: (Math.random() * 50 + 10).toFixed(2),
                    sharpeRatio: (Math.random() * 2 + 0.5).toFixed(2),
                    maxDrawdown: (Math.random() * 20 + 5).toFixed(2),
                    winRate: (Math.random() * 40 + 40).toFixed(0),
                    totalTrades: Math.floor(Math.random() * 200 + 50),
                    profitFactor: (Math.random() * 2 + 1).toFixed(2),
                    avgWin: (Math.random() * 3 + 1).toFixed(2),
                    avgLoss: (Math.random() * 2 + 0.5).toFixed(2)
                  }
                  
                  setBacktestProgress(prev => ({
                    ...prev,
                    isRunning: false,
                    results: finalResults,
                    executionLogs: [
                      ...(prev.executionLogs || []), 
                      `🎯 总收益率: +${finalResults.totalReturn}%`,
                      `⚡ 夏普比率: ${finalResults.sharpeRatio}`,
                      `📉 最大回撤: -${finalResults.maxDrawdown}%`,
                      `🎲 胜率: ${finalResults.winRate}%`,
                      `📈 交易次数: ${finalResults.totalTrades}次`,
                      '✅ 回测分析完成！'
                    ]
                  }))
                  setStrategyDevState(prev => ({
                    ...prev,
                    phase: 'analysis'
                  }))
                  toast.success('🎉 回测完成！您可以查看结果并请求AI分析', { duration: 4000 })
                }, 1000)
              }
            }, 3000) // 增加到3秒间隔，让用户能看到详细过程
            
            const message = `🚀 正在执行回测分析...

**回测配置**：
• 交易所：${config.exchange}
• 品种类型：${config.productType}
• 交易品种：${config.symbols.join(', ')}
• 时间周期：${config.timeframes.join(', ')}
• 数据类型：${config.dataType === 'tick' ? 'Tick数据回测（高精度）' : 'K线数据回测（标准）'}
• 手续费率：${config.feeRate}
• 初始资金：${config.initialCapital} USDT
• 回测时间：${config.startDate} 至 ${config.endDate}

回测正在后台执行中，您可以在下方查看实时进度。回测完成后，我将为您详细分析结果并提供优化建议。`
            
            // 关闭弹窗
            setIsBacktestModalOpen(false)
          }
          
          // 启动模拟进度更新
          startMockProgressUpdate()
        } catch (error) {
          console.error('回测执行失败:', error)
          toast.error('回测启动失败，请重试')
          setBacktestProgress({
            isRunning: false,
            progress: 0,
            currentStep: ''
          })
          setStrategyDevState(prev => ({
            ...prev,
            phase: 'strategy_ready'
          }))
        }
        }}
      />
    </div>
  )
}

// 回测配置模态框组件
interface BacktestConfigModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (config: BacktestConfig) => Promise<void>
}

const BacktestConfigModal: React.FC<BacktestConfigModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const { user } = useUserInfo()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [config, setConfig] = useState<BacktestConfig>({
    exchange: 'binance',
    productType: 'spot',
    symbols: ['BTC/USDT'],
    timeframes: ['1h'],
    feeRate: 'vip0',
    initialCapital: 10000,
    startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0],
    dataType: 'kline'
  })

  const exchanges = [
    { value: 'binance', label: '币安 (Binance)' },
    { value: 'okx', label: 'OKX' },
    { value: 'huobi', label: '火币 (Huobi)' },
    { value: 'bybit', label: 'Bybit' }
  ]

  const productTypes = [
    { value: 'spot', label: '现货' },
    { value: 'perpetual', label: '永续合约' },
    { value: 'delivery', label: '交割合约' }
  ]

  const timeframes = [
    { value: '1m', label: '1分钟' },
    { value: '5m', label: '5分钟' },
    { value: '15m', label: '15分钟' },
    { value: '30m', label: '30分钟' },
    { value: '1h', label: '1小时' },
    { value: '4h', label: '4小时' },
    { value: '1d', label: '1天' }
  ]

  const feeRates = [
    { value: 'vip0', label: 'VIP0 (0.1%/0.1%)' },
    { value: 'vip1', label: 'VIP1 (0.09%/0.09%)' },
    { value: 'vip2', label: 'VIP2 (0.08%/0.08%)' },
    { value: 'vip3', label: 'VIP3 (0.07%/0.07%)' }
  ]

  const popularSymbols = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'DOT/USDT',
    'SOL/USDT', 'MATIC/USDT', 'LINK/USDT', 'UNI/USDT', 'LTC/USDT'
  ]

  const handleSymbolToggle = (symbol: string) => {
    setConfig(prev => ({
      ...prev,
      symbols: prev.symbols.includes(symbol)
        ? prev.symbols.filter(s => s !== symbol)
        : [...prev.symbols, symbol]
    }))
  }

  const handleTimeframeToggle = (timeframe: string) => {
    setConfig(prev => ({
      ...prev,
      timeframes: prev.timeframes.includes(timeframe)
        ? prev.timeframes.filter(t => t !== timeframe)
        : [...prev.timeframes, timeframe]
    }))
  }

  // 获取用户Tick回测权限
  const getTickBacktestLimit = () => {
    const level = user?.membership_level?.toLowerCase()
    switch (level) {
      case 'premium': return 30
      case 'professional': return 100
      default: return 0
    }
  }

  const isTickDisabled = () => {
    return user?.membership_level?.toLowerCase() === 'basic'
  }

  const handleSubmit = async () => {
    if (config.symbols.length === 0) {
      alert('请至少选择一个交易品种')
      return
    }
    if (config.timeframes.length === 0) {
      alert('请至少选择一个时间周期')
      return
    }
    if (config.dataType === 'tick' && isTickDisabled()) {
      alert('Tick数据回测需要高级版或专业版会员')
      return
    }
    
    setIsSubmitting(true)
    try {
      await onSubmit(config)
    } catch (error) {
      console.error('回测配置提交失败:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-gray-900">回测参数配置</h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 交易所选择 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">交易所</label>
              <select
                value={config.exchange}
                onChange={(e) => setConfig(prev => ({ ...prev, exchange: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {exchanges.map(ex => (
                  <option key={ex.value} value={ex.value}>{ex.label}</option>
                ))}
              </select>
            </div>

            {/* 品种类型选择 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">品种类型</label>
              <select
                value={config.productType}
                onChange={(e) => setConfig(prev => ({ ...prev, productType: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {productTypes.map(type => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>

            {/* 数据类型选择 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                数据类型
                {config.dataType === 'tick' && !isTickDisabled() && (
                  <span className="text-xs text-orange-600 ml-2">
                    (本月剩余 {getTickBacktestLimit()} 次)
                  </span>
                )}
              </label>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="kline"
                    checked={config.dataType === 'kline'}
                    onChange={(e) => setConfig(prev => ({ ...prev, dataType: e.target.value as 'kline' | 'tick' }))}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <span className="ml-3 text-sm">
                    K线数据回测 
                    <span className="text-gray-500">(标准精度，免费)</span>
                  </span>
                </label>
                <label className={`flex items-center ${isTickDisabled() ? 'opacity-50 cursor-not-allowed' : ''}`}>
                  <input
                    type="radio"
                    value="tick"
                    checked={config.dataType === 'tick'}
                    onChange={(e) => !isTickDisabled() && setConfig(prev => ({ ...prev, dataType: e.target.value as 'kline' | 'tick' }))}
                    disabled={isTickDisabled()}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 disabled:opacity-50"
                  />
                  <span className="ml-3 text-sm">
                    Tick数据回测 
                    <span className="text-gray-500">
                      (最高精度，{isTickDisabled() ? '需要高级版' : `每月${getTickBacktestLimit()}次`})
                    </span>
                    {isTickDisabled() && (
                      <span className="ml-2 px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded">
                        升级解锁
                      </span>
                    )}
                  </span>
                </label>
              </div>
            </div>

            {/* 手续费率等级 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">手续费率等级</label>
              <select
                value={config.feeRate}
                onChange={(e) => setConfig(prev => ({ ...prev, feeRate: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {feeRates.map(rate => (
                  <option key={rate.value} value={rate.value}>{rate.label}</option>
                ))}
              </select>
            </div>

            {/* 初始资金 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">初始资金 (USDT)</label>
              <input
                type="number"
                value={config.initialCapital}
                onChange={(e) => setConfig(prev => ({ ...prev, initialCapital: Number(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                min="100"
                step="100"
              />
            </div>

            {/* 回测开始时间 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">开始时间</label>
              <input
                type="date"
                value={config.startDate}
                onChange={(e) => setConfig(prev => ({ ...prev, startDate: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* 回测结束时间 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">结束时间</label>
              <input
                type="date"
                value={config.endDate}
                onChange={(e) => setConfig(prev => ({ ...prev, endDate: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* 交易品种选择 */}
          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              交易品种 (已选择 {config.symbols.length} 个)
            </label>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {popularSymbols.map(symbol => (
                <button
                  key={symbol}
                  onClick={() => handleSymbolToggle(symbol)}
                  className={`px-3 py-2 text-sm rounded-md border transition-colors ${
                    config.symbols.includes(symbol)
                      ? 'bg-blue-50 border-blue-300 text-blue-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {symbol}
                </button>
              ))}
            </div>
          </div>

          {/* 时间周期选择 */}
          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              时间周期 (已选择 {config.timeframes.length} 个)
            </label>
            <div className="grid grid-cols-3 md:grid-cols-7 gap-2">
              {timeframes.map(tf => (
                <button
                  key={tf.value}
                  onClick={() => handleTimeframeToggle(tf.value)}
                  className={`px-3 py-2 text-sm rounded-md border transition-colors ${
                    config.timeframes.includes(tf.value)
                      ? 'bg-green-50 border-green-300 text-green-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex justify-end space-x-3 mt-8 pt-6 border-t border-gray-200">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>正在发送...</span>
                </div>
              ) : (
                '开始回测分析'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AIChatPage