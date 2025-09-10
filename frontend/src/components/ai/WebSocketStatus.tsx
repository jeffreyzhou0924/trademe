/**
 * WebSocket连接状态指示器
 * 显示WebSocket连接状态和AI处理进度
 */

import React, { useState } from 'react'
import { useAIStore } from '../../store/aiStore'
import { useAuthStore } from '../../store/authStore'
import { getWebSocketAIService } from '../../services/ai/websocketAI'
import toast from 'react-hot-toast'

const WebSocketStatus: React.FC = () => {
  const { 
    useWebSocket,
    wsConnected,
    wsConnectionId,
    aiProgress,
    toggleWebSocket,
    initializeWebSocket
  } = useAIStore()
  
  const { token } = useAuthStore()
  const [isConnecting, setIsConnecting] = useState(false)

  // 处理WebSocket模式切换 - 仅切换模式，不自动初始化
  const handleToggleWebSocket = () => {
    toggleWebSocket()
  }

  // 使用Store的初始化方法，确保状态同步
  const handleInitializeWebSocket = async () => {
    if (wsConnected || isConnecting) return
    
    setIsConnecting(true)
    
    try {
      // 调用Store的initializeWebSocket方法，确保状态正确更新
      const success = await initializeWebSocket()
      
      if (success) {
        // 连接成功，Store中的wsConnected已更新
        toast.success('WebSocket连接成功!')
      } else {
        toast.error('WebSocket连接建立失败，请检查网络后重试')
      }
      
    } catch (error: any) {
      console.warn('WebSocket初始化失败:', error)
      const errorMessage = String(error?.message || error || 'WebSocket连接异常')
      toast.error(errorMessage)
    } finally {
      setIsConnecting(false)
    }
  }

  const getConnectionStatusColor = () => {
    if (!useWebSocket) return 'gray'
    return wsConnected ? 'green' : 'red'
  }

  const getConnectionStatusText = () => {
    if (!useWebSocket) return 'HTTP模式'
    return wsConnected ? '已连接' : '未连接'
  }

  return (
    <div className="flex items-center space-x-4 p-3 bg-gray-50 rounded-lg border">
      {/* 连接模式切换 */}
      <div className="flex items-center space-x-2">
        <span className="text-sm font-medium text-gray-700">通信模式:</span>
        <button
          onClick={handleToggleWebSocket}
          className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
            useWebSocket 
              ? 'bg-blue-100 text-blue-800 border border-blue-200' 
              : 'bg-gray-100 text-gray-600 border border-gray-200'
          }`}
        >
          {useWebSocket ? '🚀 WebSocket' : '📡 HTTP'}
        </button>
      </div>

      {/* 连接状态 */}
      {useWebSocket && (
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${
            wsConnected ? 'bg-green-500' : 'bg-red-500'
          }`} />
          <span className={`text-sm ${
            wsConnected ? 'text-green-700' : 'text-red-700'
          }`}>
            {getConnectionStatusText()}
          </span>
          {!wsConnected && (
            <button
              onClick={handleInitializeWebSocket}
              disabled={isConnecting}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                isConnecting
                  ? 'bg-gray-400 text-white cursor-not-allowed'
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              }`}
            >
              {isConnecting ? '连接中...' : '连接'}
            </button>
          )}
          {wsConnectionId && (
            <span className="text-xs text-gray-500">
              (ID: {wsConnectionId.slice(0, 8)})
            </span>
          )}
        </div>
      )}

      {/* AI处理进度 */}
      {aiProgress && aiProgress.isProcessing && (
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            {aiProgress.status === 'stream_waiting' ? (
              <div className="flex items-center space-x-2">
                <div className="animate-pulse w-4 h-4 bg-orange-400 rounded-full" />
                <span className="text-sm font-medium text-orange-700">
                  等待AI响应
                </span>
              </div>
            ) : aiProgress.status === 'streaming_active' ? (
              <div className="flex items-center space-x-2">
                <div className="animate-bounce w-4 h-4 bg-green-500 rounded-full" />
                <span className="text-sm font-medium text-green-700">
                  实时流式生成中
                </span>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                <span className="text-sm font-medium text-blue-700">
                  AI处理中
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <div className="w-32 bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${
                    aiProgress.status === 'streaming_active' ? 'bg-green-500 animate-pulse' :
                    aiProgress.status === 'stream_waiting' ? 'bg-orange-400' : 
                    'bg-blue-500'
                  }`}
                  style={{ 
                    width: `${(aiProgress.step / aiProgress.totalSteps) * 100}%` 
                  }}
                />
              </div>
              <span className="text-xs text-gray-600">
                {aiProgress.step}/{aiProgress.totalSteps}
              </span>
            </div>
            
            <div className="flex items-center space-x-2 mt-1">
              <span className="text-xs text-gray-600">
                {aiProgress.message}
              </span>
              
              {aiProgress.complexity && (
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  aiProgress.complexity === 'simple' ? 'bg-green-100 text-green-700' :
                  aiProgress.complexity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {aiProgress.complexity}
                </span>
              )}
              
              {aiProgress.estimatedTime && (
                <span className="text-xs text-gray-500">
                  (~{aiProgress.estimatedTime}s)
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* WebSocket模式提示 */}
      {!useWebSocket && (
        <div className="text-xs text-gray-500">
          💡 WebSocket模式支持实时进度和超时保护
        </div>
      )}
      
      {/* WebSocket连接状态提示 */}
      {useWebSocket && wsConnected && (
        <div className="text-xs text-green-600">
          ✅ WebSocket已就绪，支持实时AI对话
        </div>
      )}
      
      {/* WebSocket连接失败或问题提示 */}
      {useWebSocket && !wsConnected && !isConnecting && (
        <div className="text-xs text-orange-600">
          ⚠️ 点击"连接"建立WebSocket连接
        </div>
      )}
    </div>
  )
}

export default WebSocketStatus