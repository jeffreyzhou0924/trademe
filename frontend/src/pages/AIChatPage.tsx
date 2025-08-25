import React, { useState, useEffect } from 'react'
import { useUserInfo } from '../store'
import { useAIStore } from '../store/aiStore'
import { strategyApi } from '../services/api/strategy'
import toast from 'react-hot-toast'
import type { AIMode, ChatSession, CreateSessionRequest } from '../services/api/ai'

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
  const [sessionType, setSessionType] = useState<'strategy' | 'indicator' | 'general'>('general')
  const [description, setDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sessionName.trim()) return

    setIsCreating(true)
    try {
      await onCreateSession({
        name: sessionName,
        ai_mode: aiMode,
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
              <option value="general">通用对话</option>
              {aiMode === 'developer' && (
                <>
                  <option value="strategy">策略开发</option>
                  <option value="indicator">指标开发</option>
                </>
              )}
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
  const { user, isPremium } = useUserInfo()
  const {
    currentAIMode,
    setAIMode,
    chatSessions,
    currentSession,
    messages,
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
    checkNetworkStatus
  } = useAIStore()
  
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isBacktestModalOpen, setIsBacktestModalOpen] = useState(false)
  const [messageInput, setMessageInput] = useState('')
  
  // 加载AI使用统计
  useEffect(() => {
    if (isPremium) {
      loadUsageStats(1) // 加载1天的统计数据（今天）
    }
  }, [isPremium])
  
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

  // 加载当前模式的会话列表
  useEffect(() => {
    if (isPremium) {
      loadChatSessions(currentAIMode)
    }
  }, [currentAIMode, isPremium])

  const currentModeSessions = chatSessions[currentAIMode] || []

  const handleCreateSession = async (request: CreateSessionRequest) => {
    await createChatSession(request)
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!messageInput.trim() || isTyping) return
    
    const success = await sendMessage(messageInput)
    if (success) {
      setMessageInput('')
    }
  }

  return (
    <div className="flex h-[calc(100vh-140px)]">
      {/* 左侧会话列表面板 */}
      <div className="w-80 border-r border-gray-200 bg-gray-50 flex flex-col">
        {/* 模式切换 */}
        <div className="p-4 border-b border-gray-200 bg-white">
          <div className="flex space-x-2 p-1 bg-gray-100 rounded-lg">
            <button
              onClick={() => setAIMode('trader')}
              className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                currentAIMode === 'trader'
                  ? 'bg-green-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
              }`}
            >
              📈 交易员
            </button>
            <button
              onClick={() => setAIMode('developer')}
              className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                currentAIMode === 'developer'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
              }`}
            >
              🛠️ 开发者
            </button>
          </div>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-gray-900">对话记录</h3>
              <button
                onClick={() => setIsCreateModalOpen(true)}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                + 新建
              </button>
            </div>
            
            {isLoading ? (
              <div className="text-center py-4 text-gray-500">
                加载中...
              </div>
            ) : currentModeSessions.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  💬
                </div>
                <p className="text-sm mb-3">还没有对话记录</p>
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                >
                  创建第一个对话
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {currentModeSessions.map((session) => (
                  <div
                    key={session.session_id}
                    onClick={() => selectChatSession(session)}
                    className={`group p-3 rounded-lg cursor-pointer transition-colors ${
                      currentSession?.session_id === session.session_id
                        ? 'bg-blue-50 border-blue-200 border'
                        : 'bg-white hover:bg-gray-50 border border-gray-200'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-sm text-gray-900 truncate">
                          {session.name}
                        </h4>
                        <p className="text-xs text-gray-500 mt-1">
                          {session.message_count} 条消息 · {session.session_type}
                        </p>
                        {session.last_message && (
                          <p className="text-xs text-gray-400 mt-1 truncate">
                            {session.last_message.slice(0, 30)}...
                          </p>
                        )}
                      </div>
                      <div className="flex items-center space-x-1">
                        <div className={`w-2 h-2 rounded-full ${
                          session.status === 'active' ? 'bg-green-400' : 'bg-gray-300'
                        }`} />
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
                      {currentAIMode === 'trader' ? '交易员AI助手' : '开发者AI助手'}
                    </p>
                    <span className="px-2 py-0.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white text-xs font-bold rounded-full">
                      Claude 4
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
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
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    {currentAIMode === 'trader' ? '📈' : '🛠️'}
                  </div>
                  <p>开始你的AI对话吧！</p>
                  {currentSession && (
                    <p className="text-xs text-gray-400 mt-2">历史消息加载中...</p>
                  )}
                </div>
              ) : (
                messages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex ${
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div className={`max-w-[80%] rounded-lg px-4 py-2 ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-900'
                    }`}>
                      <div className="whitespace-pre-wrap">{message.content}</div>
                      <div className={`text-xs mt-1 ${
                        message.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                      }`}>
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))
              )}
              
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                    <div className="flex items-center space-x-2">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                      </div>
                      <span className="text-sm text-gray-500">AI正在思考...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 快捷操作按钮 */}
            <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setIsBacktestModalOpen(true)}
                  className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-600 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 00-2-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>回测分析</span>
                </button>
                <button
                  onClick={async () => {
                    if (!currentSession) {
                      toast.error('请先选择会话')
                      return
                    }
                    
                    const isIndicatorSession = currentSession?.session_type === 'indicator'
                    const itemType = isIndicatorSession ? '指标' : '策略'
                    const libraryType = isIndicatorSession ? '指标库' : '策略库'
                    
                    // 从最近的AI消息中提取代码和名称
                    const lastAIMessage = messages.slice().reverse().find(m => m.role === 'assistant')
                    if (!lastAIMessage) {
                      toast.error('未找到AI生成的内容')
                      return
                    }
                    
                    // 简单的代码提取逻辑 - 查找代码块
                    const codeMatch = lastAIMessage.content.match(/```(?:python)?\s*([\s\S]*?)\s*```/)
                    if (!codeMatch) {
                      toast.error(`未在AI回复中找到${itemType}代码`)
                      return
                    }
                    
                    const code = codeMatch[1].trim()
                    
                    // 从代码或对话中提取名称
                    let strategyName = `AI生成的${itemType}_${Date.now()}`
                    const nameMatch = lastAIMessage.content.match(/(?:策略|指标)名称[:：]\s*([^\n]+)/i) ||
                                     lastAIMessage.content.match(/class\s+(\w+)/i) ||
                                     lastAIMessage.content.match(/def\s+(\w+)/i)
                    if (nameMatch) {
                      strategyName = nameMatch[1].trim()
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
                  className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-green-50 hover:border-green-200 hover:text-green-600 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <span>
                    {currentSession?.session_type === 'indicator' ? '添加到指标库' : '添加到策略库'}
                  </span>
                </button>
                <button
                  onClick={() => setMessageInput('请帮我启动实盘交易，使用我的策略库中表现最好的策略，初始资金设为1000USDT')}
                  className="flex items-center space-x-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-orange-50 hover:border-orange-200 hover:text-orange-600 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span>运行实盘</span>
                </button>
              </div>
            </div>

            {/* 消息输入框 */}
            <div className="p-4 border-t border-gray-200 bg-white">
              <form onSubmit={handleSendMessage} className="flex space-x-3">
                <div className="flex-1">
                  <input
                    type="text"
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    placeholder={`与${currentAIMode === 'trader' ? '交易员' : '开发者'}AI对话...`}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isTyping}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!messageInput.trim() || isTyping}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isTyping ? '发送中' : '发送'}
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                {currentAIMode === 'trader' ? '📈' : '🛠️'}
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                {currentAIMode === 'trader' ? '交易员AI助手' : '开发者AI助手'}
              </h2>
              <p className="text-gray-600 mb-6">
                {currentAIMode === 'trader' 
                  ? '准备开始智能市场分析对话'
                  : '选择或创建策略/指标对话开始开发'
                }
              </p>
              <button 
                onClick={() => setIsCreateModalOpen(true)}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                {currentAIMode === 'trader' ? '开始对话' : '创建新对话'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 右侧信息面板 */}
      <div className="w-80 border-l border-gray-200 bg-gray-50 p-4">
        <div className="bg-white rounded-lg p-4 shadow-sm mb-4">
          <div className="flex items-center space-x-2 mb-3">
            <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">
              {user?.membership_level === 'premium' ? 'P' : 'Pro'}
            </div>
            <h3 className="font-semibold text-gray-900">
              {user?.membership_level === 'premium' ? '高级版' : '专业版'}
            </h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">AI额度</span>
              <span className="font-medium">
                {user?.membership_level === 'premium' ? '$100/日' : '$200/日'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">今日已用</span>
              <span className="font-medium text-blue-600">
                ${usageStats?.daily_cost_usd?.toFixed(2) || '0.00'}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                style={{
                  width: `${usageStats ? Math.min(100, (usageStats.daily_cost_usd / (user?.membership_level === 'premium' ? 100 : 200)) * 100) : 0}%`
                }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>余额：${usageStats?.remaining_daily_quota?.toFixed(2) || '100.00'}</span>
              <span>{usageStats ? Math.round((usageStats.daily_cost_usd / (user?.membership_level === 'premium' ? 100 : 200)) * 100) : 0}%</span>
            </div>
          </div>
        </div>

        {/* 模式介绍 */}
        <div className="bg-white rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-medium">
              {currentAIMode === 'trader' ? '交易员模式' : '开发者模式'}
            </h3>
            <span className="px-2 py-1 bg-gradient-to-r from-blue-500 to-purple-500 text-white text-xs font-bold rounded-full">
              Claude 4
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-3">
            {currentAIMode === 'trader' 
              ? '基于Claude 4 Sonnet的实时市场分析和交易决策支持'
              : '基于Claude 4 Sonnet专注于策略和指标开发，支持多会话管理'
            }
          </p>
          <div className="text-xs text-gray-500 space-y-1">
            {currentAIMode === 'trader' ? (
              <>
                <div>• 实时市场分析</div>
                <div>• 交易时机建议</div>
                <div>• 风险评估</div>
                <div>• 仓位管理</div>
              </>
            ) : (
              <>
                <div>• 策略代码生成</div>
                <div>• 指标开发助手</div>
                <div>• 回测分析</div>
                <div>• 参数优化</div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 创建会话模态框 */}
      <CreateSessionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateSession={handleCreateSession}
        aiMode={currentAIMode}
      />

      {/* 回测配置模态框 */}
      <BacktestConfigModal
        isOpen={isBacktestModalOpen}
        onClose={() => setIsBacktestModalOpen(false)}
        onSubmit={async (config) => {
          const message = `请帮我进行回测分析，具体配置如下：
交易所：${config.exchange}
品种类型：${config.productType}
交易品种：${config.symbols.join(', ')}
时间周期：${config.timeframes.join(', ')}
数据类型：${config.dataType === 'tick' ? 'Tick数据回测（高精度）' : 'K线数据回测（标准）'}
手续费率：${config.feeRate}
初始资金：${config.initialCapital} USDT
回测时间：${config.startDate} 至 ${config.endDate}

请基于以上配置进行详细的回测分析，包括收益率、夏普比率、最大回撤等关键指标。`
          
          // 关闭弹窗
          setIsBacktestModalOpen(false)
          
          // 直接发送消息给AI，不需要用户点击发送
          const success = await sendMessage(message)
          if (!success) {
            // 如果发送失败，将消息填入输入框让用户可以重新发送
            setMessageInput(message)
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