/**
 * WebSocket AI客户端
 * 解决HTTP超时问题，提供实时AI对话体验
 */

export interface WebSocketMessage {
  type: string
  [key: string]: any
}

export interface AIProgressUpdate {
  type: 'ai_progress_update'
  request_id?: string
  step: number
  total_steps: number
  status: string
  message: string
  timestamp?: string
}

export interface AIComplexityAnalysis {
  type: 'ai_complexity_analysis'
  request_id?: string
  complexity: 'simple' | 'medium' | 'complex'
  estimated_time_seconds: number
  message: string
}

export interface AIChatSuccess {
  type: 'ai_chat_success'
  request_id?: string
  response: string
  session_id?: string
  tokens_used: number
  model: string
  cost_usd: number
  message: string
}

export interface AIChatError {
  type: 'ai_chat_error'
  request_id?: string
  error: string
  error_code?: string
  complexity?: string
  retry_suggested?: boolean
  message: string
}

// 🌊 流式AI消息类型定义 - 修复字段匹配
export interface AIStreamStart {
  type: 'ai_stream_start'
  request_id?: string
  session_id?: string
  model?: string
  input_tokens?: number
}

export interface AIStreamChunk {
  type: 'ai_stream_chunk'
  request_id?: string
  chunk: string
  content_so_far: string  // 匹配后端字段名
  session_id?: string
}

export interface AIStreamEnd {
  type: 'ai_stream_end'
  request_id?: string
  session_id?: string
  content: string  // 匹配后端字段名
  tokens_used: number
  cost_usd: number
}

export interface AIStreamError {
  type: 'ai_stream_error'
  request_id?: string
  error: string
  error_type?: string
  message: string
  retry_suggested?: boolean
  timestamp?: string
}

export interface WebSocketConfig {
  url: string
  token: string
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

export type WebSocketEventHandler = (data: WebSocketMessage) => void

export interface WebSocketEvents {
  onOpen?: () => void
  onClose?: (event: CloseEvent) => void
  onError?: (event: Event) => void
  onAuthenticated?: (data: any) => void
  onAIStart?: (data: any) => void
  onComplexityAnalysis?: (data: AIComplexityAnalysis) => void
  onProgressUpdate?: (data: AIProgressUpdate) => void
  onAISuccess?: (data: AIChatSuccess) => void
  onAIError?: (data: AIChatError) => void
  onHeartbeat?: (data: any) => void
  onMessage?: (data: WebSocketMessage) => void
  // 🌊 新增流式AI事件处理器
  onStreamStart?: (data: AIStreamStart) => void
  onStreamChunk?: (data: AIStreamChunk) => void
  onStreamEnd?: (data: AIStreamEnd) => void
  onStreamError?: (data: AIStreamError) => void
}

export class WebSocketAIClient {
  private ws: WebSocket | null = null
  private config: WebSocketConfig
  private events: WebSocketEvents = {}
  private isConnected = false
  private isAuthenticated = false
  private reconnectAttempts = 0
  private connectionId: string | null = null
  private userId: number | null = null
  private heartbeatTimer: NodeJS.Timeout | null = null
  private reconnectTimer: NodeJS.Timeout | null = null

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectInterval: 3000,
      maxReconnectAttempts: 5,
      heartbeatInterval: 30000,
      ...config
    }
  }

  /**
   * 设置事件监听器
   */
  public on(events: WebSocketEvents): void {
    this.events = { ...this.events, ...events }
  }

  /**
   * 连接WebSocket
   */
  public async connect(): Promise<boolean> {
    return new Promise((resolve, reject) => {
      try {
        console.log('🔗 正在连接WebSocket AI服务:', this.config.url)
        
        this.ws = new WebSocket(this.config.url)

        this.ws.onopen = () => {
          console.log('✅ WebSocket连接已建立')
          this.isConnected = true
          this.reconnectAttempts = 0
          this.events.onOpen?.()
          this.authenticate().then(resolve).catch(reject)
        }

        this.ws.onclose = (event) => {
          console.log('❌ WebSocket连接已断开:', event.code, event.reason)
          this.isConnected = false
          this.isAuthenticated = false
          this.connectionId = null
          this.userId = null
          this.clearTimers()
          this.events.onClose?.(event)
          
          // 只有在非正常关闭时才自动重连
          if (event.code !== 1000) {
            this.handleReconnect()
          }
          
          // 在初始连接时，如果失败则reject
          if (this.reconnectAttempts === 0) {
            reject(new Error(`WebSocket连接失败: ${event.reason || '未知原因'} (Code: ${event.code})`))
          }
        }

        this.ws.onerror = (event) => {
          console.error('❌ WebSocket错误:', event)
          this.events.onError?.(event)
          reject(event)
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            
            // 验证消息格式
            if (!data || typeof data !== 'object') {
              console.error('❌ WebSocket消息格式无效:', data)
              return
            }
            
            // 确保type字段存在
            if (!data.type) {
              console.error('❌ WebSocket消息缺少type字段:', data)
              return
            }
            
            this.handleMessage(data)
          } catch (error) {
            console.error('❌ 解析WebSocket消息失败:', error, 'Original data:', event.data)
          }
        }

      } catch (error) {
        console.error('❌ WebSocket连接失败:', error)
        reject(error)
      }
    })
  }

  /**
   * 认证
   */
  private async authenticate(): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket未连接'))
        return
      }

      // 设置认证超时（增加到30秒，给后端足够的时间处理）
      const authTimeout = setTimeout(() => {
        console.error('❌ [WebSocketClient] 认证超时，30秒内未收到认证响应')
        reject(new Error('认证超时'))
      }, 30000)

      // 监听认证结果
      const originalHandler = this.events.onAuthenticated
      console.log('🔐 [WebSocketClient] 设置临时认证处理器')
      
      // 设置临时认证处理器
      this.events.onAuthenticated = (data) => {
        console.log('🎉 [WebSocketClient] 认证回调被触发！', data)
        clearTimeout(authTimeout)
        this.isAuthenticated = true
        // 后端返回的是 user_id，而不是 connection_id
        this.connectionId = data.connection_id || `user_${data.user_id}_${Date.now()}`
        this.userId = data.user_id
        this.startHeartbeat()
        
        console.log('✅ WebSocket认证成功:', {
          connectionId: this.connectionId,
          userId: this.userId
        })
        
        // 恢复原始处理器
        this.events.onAuthenticated = originalHandler
        originalHandler?.(data)
        resolve(true)
      }

      // 发送认证消息（使用后端期望的格式）
      const authMessage = {
        type: 'auth',  // 后端期望 'auth' 而不是 'authenticate'
        token: this.config.token
      }
      console.log('📤 [WebSocketClient] 发送认证消息:', { type: authMessage.type, tokenLength: authMessage.token?.length })
      this.send(authMessage)
    })
  }

  /**
   * 发送AI对话消息
   */
  public async sendAIChat(
    content: string,
    aiMode: string = 'trader',
    sessionType: string = 'strategy',
    sessionId?: string
  ): Promise<string> {
    console.log('🚀 [WebSocketClient] sendAIChat called:', {
      content: content.substring(0, 100) + '...',
      aiMode,
      sessionType,
      sessionId,
      isConnected: this.isConnected,
      isAuthenticated: this.isAuthenticated
    })
    
    if (!this.isConnected || !this.isAuthenticated) {
      const errorMsg = `WebSocket状态异常 - 连接:${this.isConnected}, 认证:${this.isAuthenticated}`
      console.error('❌ [WebSocketClient]', errorMsg)
      throw new Error(errorMsg)
    }

    const requestId = this.generateRequestId()
    
    const message = {
      type: 'ai_chat',
      request_id: requestId,
      content,
      ai_mode: aiMode,
      session_type: sessionType,
      session_id: sessionId
    }
    
    console.log('📤 [WebSocketClient] 发送AI消息:', message)
    this.send(message)

    return requestId
  }

  /**
   * 取消AI请求
   */
  public cancelAIRequest(requestId: string): void {
    if (!this.isConnected || !this.isAuthenticated) return

    this.send({
      type: 'cancel_request',
      request_id: requestId
    })
  }

  /**
   * 发送心跳
   */
  public ping(): void {
    if (!this.isConnected) return

    this.send({
      type: 'ping'
    })
  }

  /**
   * 断开连接
   */
  public disconnect(): void {
    this.clearTimers()
    
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    
    this.isConnected = false
    this.isAuthenticated = false
    this.connectionId = null
    this.userId = null
  }

  /**
   * 获取连接状态
   */
  public getConnectionInfo() {
    return {
      isConnected: this.isConnected,
      isAuthenticated: this.isAuthenticated,
      connectionId: this.connectionId,
      userId: this.userId,
      reconnectAttempts: this.reconnectAttempts
    }
  }

  // ========== 私有方法 ==========

  private handleMessage(data: WebSocketMessage): void {
    // 智能消息日志 - 显示关键信息而非Object
    const logMessage = {
      type: data.type,
      request_id: data.request_id || 'N/A',
      ...(data.type === 'ai_progress_update' && {
        step: data.step,
        total_steps: data.total_steps,
        status: data.status,
        message: data.message
      }),
      ...(data.type === 'ai_stream_chunk' && {
        chunk_length: data.chunk?.length || 0
      }),
      ...(data.type === 'ai_stream_end' && {
        response_length: data.content?.length || 0,  // 修复字段名
        tokens_used: data.tokens_used,
        cost_usd: data.cost_usd
      })
    }
    console.log('📨 收到WebSocket消息:', logMessage)

    switch (data.type) {
      case 'connection_established':
        console.log('✅ [WebSocketClient] 连接已建立:', data)
        this.isAuthenticated = true  // 标记为已认证
        this.connectionId = data.connection_id || null
        this.userId = data.user_id || null
        // 触发认证成功回调
        if (this.events.onAuthenticated) {
          console.log('🎯 [WebSocketClient] 触发onAuthenticated回调 (connection_established)')
          this.events.onAuthenticated(data)
        }
        break
        
      case 'auth_success':
        console.log('✅ [WebSocketClient] 认证成功:', data)
        this.isAuthenticated = true
        this.connectionId = data.connection_id || null
        this.userId = data.user_id || null
        // 关键：调用认证成功回调
        if (this.events.onAuthenticated) {
          console.log('🎯 [WebSocketClient] 调用onAuthenticated回调')
          this.events.onAuthenticated(data)
        } else {
          console.warn('⚠️ [WebSocketClient] onAuthenticated回调未设置')
        }
        break
      
      case 'ai_chat_start':
        this.events.onAIStart?.(data)
        break
      
      case 'ai_complexity_analysis':
        this.events.onComplexityAnalysis?.(data as AIComplexityAnalysis)
        break
      
      case 'ai_progress_update':
        // 调用正确的进度更新回调
        this.events.onProgressUpdate?.(data as AIProgressUpdate)
        break
      
      case 'ai_chat_success':
        this.events.onAISuccess?.(data as AIChatSuccess)
        break
      
      case 'ai_chat_error':
        this.events.onAIError?.(data as AIChatError)
        break
      
      // 🌊 流式AI消息处理
      case 'ai_stream_start':
        console.log('🌊 [WebSocketClient] 流式AI开始:', data)
        this.events.onStreamStart?.(data as AIStreamStart)
        break
      
      case 'ai_stream_chunk':
        console.log('📝 [WebSocketClient] 流式AI数据块:', data?.chunk || '[chunk为空]')
        this.events.onStreamChunk?.(data as AIStreamChunk)
        break
      
      case 'ai_stream_end':
        console.log('✅ [WebSocketClient] 流式AI结束:', data)
        console.log('🔄 [WebSocketClient] 准备调用onStreamEnd回调')
        
        if (this.events.onStreamEnd) {
          console.log('🎯 [WebSocketClient] onStreamEnd回调存在，正在调用...')
          this.events.onStreamEnd(data as AIStreamEnd)
          console.log('✅ [WebSocketClient] onStreamEnd回调调用完成')
        } else {
          console.log('⚠️ [WebSocketClient] onStreamEnd回调不存在!')
        }
        break
      
      case 'ai_stream_error':
        // 安全的错误日志记录，防止 Object 显示问题
        const errorInfo = {
          error: data?.error || 'Unknown error',
          error_type: data?.error_type || 'UNKNOWN',
          message: data?.message || 'No error message',
          request_id: data?.request_id || 'No request ID'
        }
        console.log('❌ [WebSocketClient] 流式AI错误:', errorInfo)
        console.log('❌ [WebSocketClient] 原始错误数据:', JSON.stringify(data, null, 2))
        this.events.onStreamError?.(data as AIStreamError)
        break
      
      case 'heartbeat':
      case 'pong':
        this.events.onHeartbeat?.(data)
        break
      
      default:
        this.events.onMessage?.(data)
        break
    }
  }

  private send(data: any): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('⚠️ WebSocket未连接，无法发送消息:', data)
      return
    }

    try {
      this.ws.send(JSON.stringify(data))
      console.log('📤 发送WebSocket消息:', data.type)
    } catch (error) {
      console.error('❌ 发送WebSocket消息失败:', error)
    }
  }

  private startHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
    }

    this.heartbeatTimer = setInterval(() => {
      this.ping()
    }, this.config.heartbeatInterval!)
  }

  private clearTimers(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts!) {
      console.error('❌ 达到最大重连次数，停止重连')
      return
    }

    this.reconnectAttempts++
    console.log(`🔄 尝试重连 (${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`)

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch(console.error)
    }, this.config.reconnectInterval!)
  }

  private generateRequestId(): string {
    return Math.random().toString(36).substring(2) + Date.now().toString(36)
  }
}

export default WebSocketAIClient