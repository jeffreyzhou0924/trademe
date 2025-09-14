/**
 * WebSocket AI服务集成
 * 替代HTTP AI API，解决超时问题
 */

import WebSocketAIClient, { 
  type WebSocketConfig, 
  type AIChatSuccess, 
  type AIChatError, 
  type AIProgressUpdate,
  type AIComplexityAnalysis,
  type AIStreamStart,
  type AIStreamChunk,
  type AIStreamEnd,
  type AIStreamError
} from './websocketClient'

export interface WebSocketAIConfig {
  baseUrl: string
  token: string
}

export interface AIProgressCallback {
  onStart?: (data: any) => void
  onComplexityAnalysis?: (data: AIComplexityAnalysis) => void  
  onProgress?: (data: AIProgressUpdate) => void
  onSuccess?: (data: AIChatSuccess) => void
  onError?: (data: AIChatError) => void
  // 🌊 流式AI回调
  onStreamStart?: (data: AIStreamStart) => void
  onStreamChunk?: (data: AIStreamChunk) => void
  onStreamEnd?: (data: AIStreamEnd) => void
  onStreamError?: (data: AIStreamError) => void
}

export interface PendingRequest {
  requestId: string
  resolve: (data: AIChatSuccess) => void
  reject: (error: AIChatError) => void
  callbacks?: AIProgressCallback
}

export class WebSocketAIService {
  private client: WebSocketAIClient
  private pendingRequests = new Map<string, PendingRequest>()
  private isInitialized = false

  constructor(config: WebSocketAIConfig) {
    // 使用正确的WebSocket端点 - 处理不同的URL格式
    let baseUrl = config.baseUrl
    
    // 移除/api/v1路径（如果存在）
    baseUrl = baseUrl.replace(/\/api\/v1$/, '')
    
    // 确保baseURL格式正确
    if (!baseUrl.match(/^https?:\/\//)) {
      // 如果没有协议，添加默认协议
      baseUrl = window.location.protocol + '//' + baseUrl
    }
    
    // 构建WebSocket URL - 修复端点匹配问题，需要包含API版本前缀
    const wsUrl = baseUrl.replace(/^http/, 'ws') + '/api/v1/ai/ws/chat'
    
    console.log('🔗 [WebSocketAI] 构建的WebSocket URL:', wsUrl)
    
    this.client = new WebSocketAIClient({
      url: wsUrl,
      token: config.token,
      reconnectInterval: 3000,
      maxReconnectAttempts: 5, // 增加重连尝试次数
      heartbeatInterval: 30000  // 心跳间隔30秒
    })

    this.setupEventHandlers()
  }

  /**
   * 初始化连接
   */
  public async initialize(): Promise<boolean> {
    if (this.isInitialized) {
      return true
    }

    try {
      await this.client.connect()
      this.isInitialized = true
      return true
    } catch (error) {
      console.error('❌ WebSocket AI服务初始化失败:', error)
      return false
    }
  }

  /**
   * 发送AI对话消息 (WebSocket版本)
   */
  public async sendChatMessage(
    content: string,
    sessionId?: string,
    aiMode: string = 'trader',
    sessionType: string = 'strategy',
    callbacks?: AIProgressCallback
  ): Promise<AIChatSuccess> {
    // 确保已连接
    if (!this.isInitialized) {
      const connected = await this.initialize()
      if (!connected) {
        throw new Error('WebSocket连接失败')
      }
    }

    return new Promise(async (resolve, reject) => {
      try {
        const requestId = await this.client.sendAIChat(
          content,
          aiMode,
          sessionType,
          sessionId
        )

        // 保存请求信息
        this.pendingRequests.set(requestId, {
          requestId,
          resolve,
          reject,
          callbacks
        })

        // 设置超时（4分钟，给后端Claude客户端足够时间）
        setTimeout(() => {
          if (this.pendingRequests.has(requestId)) {
            this.pendingRequests.delete(requestId)
            reject({
              type: 'ai_chat_error',
              request_id: requestId,
              error: 'WebSocket请求超时',
              error_code: 'WEBSOCKET_TIMEOUT',
              message: 'WebSocket请求超时，请重试'
            } as AIChatError)
          }
        }, 600000) // 增加到10分钟，适应Claude AI长响应时间

      } catch (error) {
        console.error('❌ [WebSocketAI] sendChatMessage异常:', error)
        reject({
          type: 'ai_chat_error',
          error: error instanceof Error ? error.message : '未知错误',
          error_code: 'WEBSOCKET_ERROR',
          message: 'WebSocket发送失败'
        } as AIChatError)
      }
    })
  }

  /**
   * 取消请求
   */
  public cancelRequest(requestId: string): void {
    this.client.cancelAIRequest(requestId)
    if (this.pendingRequests.has(requestId)) {
      this.pendingRequests.delete(requestId)
    }
  }

  /**
   * 获取连接状态
   */
  public getConnectionStatus() {
    return this.client.getConnectionInfo()
  }

  /**
   * 断开连接
   */
  public disconnect(): void {
    this.client.disconnect()
    this.isInitialized = false
    this.pendingRequests.clear()
  }

  /**
   * 重新连接
   */
  public async reconnect(): Promise<boolean> {
    this.disconnect()
    return this.initialize()
  }

  // ========== 私有方法 ==========

  private setupEventHandlers(): void {
    this.client.on({
      onOpen: () => {
        console.log('🔗 WebSocket AI服务已连接')
      },

      onClose: (event) => {
        console.log('❌ WebSocket AI服务已断开:', event.code, event.reason)
        this.isInitialized = false
        
        // 清理所有pending请求
        this.pendingRequests.forEach(({ reject, requestId }) => {
          reject({
            type: 'ai_chat_error',
            request_id: requestId,
            error: 'WebSocket连接断开',
            error_code: 'WEBSOCKET_DISCONNECTED',
            message: 'WebSocket连接断开，请重试'
          } as AIChatError)
        })
        this.pendingRequests.clear()
      },

      onError: (event) => {
        console.error('❌ WebSocket AI服务错误:', event)
      },

      onAuthenticated: (data) => {
        console.log('✅ WebSocket AI服务认证成功:', data)
      },

      onAIStart: (data) => {
        const request = this.findRequestById(data.request_id)
        request?.callbacks?.onStart?.(data)
      },

      onComplexityAnalysis: (data) => {
        const request = this.findRequestById(data.request_id)
        request?.callbacks?.onComplexityAnalysis?.(data)
      },

      onProgressUpdate: (data) => {
        const request = this.findRequestById(data.request_id)
        request?.callbacks?.onProgress?.(data)
      },

      onAISuccess: (data) => {
        const request = this.findRequestById(data.request_id)
        if (request) {
          this.pendingRequests.delete(request.requestId)
          request.callbacks?.onSuccess?.(data)
          request.resolve(data)
        }
      },

      onAIError: (data) => {
        const request = this.findRequestById(data.request_id)
        if (request) {
          this.pendingRequests.delete(request.requestId)
          request.callbacks?.onError?.(data)
          request.reject(data)
        }
      },

      // 🌊 流式AI事件处理
      onStreamStart: (data) => {
        const request = this.findRequestById(data.request_id)
        request?.callbacks?.onStreamStart?.(data)
      },

      onStreamChunk: (data) => {
        const request = this.findRequestById(data.request_id)
        request?.callbacks?.onStreamChunk?.(data)
      },

      onStreamEnd: (data) => {
        const request = this.findRequestById(data.request_id)
        if (request) {
          this.pendingRequests.delete(request.requestId)
          request.callbacks?.onStreamEnd?.(data)
          // 流式结束时，解析Promise（将流式结束数据转换为成功数据格式）
          const successData: AIChatSuccess = {
            type: 'ai_chat_success',
            request_id: data.request_id,
            response: data.content,  // 修复字段名
            session_id: data.session_id,
            tokens_used: data.tokens_used,
            model: 'claude-3-5-sonnet-20241022',
            cost_usd: data.cost_usd,
            message: '对话成功'
          }
          request.resolve(successData)
        }
      },

      onStreamError: (data) => {
        const request = this.findRequestById(data.request_id)
        if (request) {
          this.pendingRequests.delete(request.requestId)
          request.callbacks?.onStreamError?.(data)
          // 将流式错误转换为标准错误格式
          const errorData: AIChatError = {
            type: 'ai_chat_error',
            request_id: data.request_id,
            error: data.error,
            message: data.message
          }
          request.reject(errorData)
        }
      },

      onHeartbeat: () => {
        // 心跳正常时不输出日志，减少噪音
      }
    })
  }

  private findRequestById(requestId?: string): PendingRequest | undefined {
    if (!requestId) return undefined
    return this.pendingRequests.get(requestId)
  }
}

// 创建单例实例
let wsAIService: WebSocketAIService | null = null

/**
 * 获取WebSocket AI服务实例
 */
export function getWebSocketAIService(config?: WebSocketAIConfig): WebSocketAIService {
  if (!wsAIService && config) {
    wsAIService = new WebSocketAIService(config)
  }
  
  if (!wsAIService) {
    throw new Error('WebSocket AI服务未初始化，请提供配置')
  }
  
  return wsAIService
}

/**
 * 销毁WebSocket AI服务实例  
 */
export function destroyWebSocketAIService(): void {
  if (wsAIService) {
    wsAIService.disconnect()
    wsAIService = null
  }
}

export default WebSocketAIService