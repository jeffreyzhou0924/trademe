interface WebSocketConnection {
  ws: WebSocket
  url: string
  key: string
  isActive: boolean
  reconnectAttempts: number
  maxReconnectAttempts: number
  reconnectDelay: number
  authToken?: string
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
  onClose?: () => void
  onOpen?: () => void
}

interface WebSocketManagerConfig {
  baseUrl: string
  maxReconnectAttempts: number
  reconnectDelay: number
  heartbeatInterval: number
}

export class WebSocketManager {
  private connections: Map<string, WebSocketConnection> = new Map()
  private config: WebSocketManagerConfig
  private heartbeatTimer: NodeJS.Timeout | null = null

  constructor(config: WebSocketManagerConfig) {
    this.config = config
    this.startHeartbeat()
  }

  /**
   * 创建WebSocket连接
   */
  connect(
    key: string,
    endpoint: string,
    handlers: {
      onMessage?: (data: any) => void
      onError?: (error: Event) => void
      onClose?: () => void
      onOpen?: () => void
    } = {},
    authToken?: string
  ): boolean {
    try {
      // 如果连接已存在，先关闭
      if (this.connections.has(key)) {
        this.disconnect(key)
      }

      const url = `${this.config.baseUrl}${endpoint}`
      const ws = new WebSocket(url)
      
      const connection: WebSocketConnection = {
        ws,
        url,
        key,
        isActive: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: this.config.maxReconnectAttempts,
        reconnectDelay: this.config.reconnectDelay,
        authToken, // 保存认证token
        ...handlers
      }

      this.setupWebSocketHandlers(connection)
      this.connections.set(key, connection)

      console.log(`WebSocket connecting: ${key} -> ${url}`)
      return true
    } catch (error) {
      console.error(`Failed to create WebSocket connection for ${key}:`, error)
      return false
    }
  }

  /**
   * 断开WebSocket连接
   */
  disconnect(key: string): boolean {
    const connection = this.connections.get(key)
    if (!connection) {
      return false
    }

    connection.isActive = false
    
    if (connection.ws.readyState === WebSocket.OPEN || 
        connection.ws.readyState === WebSocket.CONNECTING) {
      connection.ws.close(1000, 'Manual disconnect')
    }

    this.connections.delete(key)
    console.log(`WebSocket disconnected: ${key}`)
    return true
  }

  /**
   * 断开所有连接
   */
  disconnectAll(): void {
    for (const key of this.connections.keys()) {
      this.disconnect(key)
    }
    
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
   * 发送消息
   */
  send(key: string, message: any): boolean {
    const connection = this.connections.get(key)
    if (!connection || connection.ws.readyState !== WebSocket.OPEN) {
      console.warn(`WebSocket not ready for sending: ${key}`)
      return false
    }

    try {
      const data = typeof message === 'string' ? message : JSON.stringify(message)
      connection.ws.send(data)
      return true
    } catch (error) {
      console.error(`Failed to send message to ${key}:`, error)
      return false
    }
  }

  /**
   * 获取连接状态
   */
  getConnectionStatus(key: string): {
    isConnected: boolean
    readyState: number | null
    reconnectAttempts: number
  } {
    const connection = this.connections.get(key)
    if (!connection) {
      return { isConnected: false, readyState: null, reconnectAttempts: 0 }
    }

    return {
      isConnected: connection.ws.readyState === WebSocket.OPEN,
      readyState: connection.ws.readyState,
      reconnectAttempts: connection.reconnectAttempts
    }
  }

  /**
   * 获取所有连接状态
   */
  getAllConnectionStatus(): Record<string, any> {
    const status: Record<string, any> = {}
    for (const [key] of this.connections) {
      status[key] = this.getConnectionStatus(key)
    }
    return status
  }

  /**
   * 设置WebSocket事件处理器
   */
  private setupWebSocketHandlers(connection: WebSocketConnection): void {
    const { ws } = connection

    ws.onopen = (event) => {
      connection.isActive = true
      connection.reconnectAttempts = 0
      console.log(`WebSocket connected: ${connection.key}`)
      
      // 如果有认证token，先发送认证消息
      if (connection.authToken) {
        const authMessage = {
          type: 'auth',
          token: connection.authToken
        }
        ws.send(JSON.stringify(authMessage))
        console.log(`🔐 Sent auth message for connection: ${connection.key}`)
      }
      
      connection.onOpen?.()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        connection.onMessage?.(data)
      } catch (error) {
        console.error(`Failed to parse WebSocket message from ${connection.key}:`, error)
        // 如果不是JSON，直接传递原始数据
        connection.onMessage?.(event.data)
      }
    }

    ws.onerror = (error) => {
      console.error(`WebSocket error on ${connection.key}:`, error)
      connection.onError?.(error)
    }

    ws.onclose = (event) => {
      console.log(`WebSocket closed: ${connection.key}, code: ${event.code}, reason: ${event.reason}`)
      
      connection.onClose?.()
      
      // 自动重连（如果是意外断开）
      if (connection.isActive && 
          connection.reconnectAttempts < connection.maxReconnectAttempts &&
          event.code !== 1000) { // 1000 = 正常关闭
        this.scheduleReconnect(connection)
      } else if (connection.reconnectAttempts >= connection.maxReconnectAttempts) {
        console.warn(`Max reconnect attempts reached for ${connection.key}`)
        this.connections.delete(connection.key)
      }
    }
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(connection: WebSocketConnection): void {
    connection.reconnectAttempts++
    const delay = connection.reconnectDelay * Math.pow(2, connection.reconnectAttempts - 1) // 指数退避
    
    console.log(`Scheduling reconnect for ${connection.key} in ${delay}ms (attempt ${connection.reconnectAttempts})`)

    setTimeout(() => {
      if (connection.isActive) {
        console.log(`Attempting to reconnect ${connection.key}...`)
        const newWs = new WebSocket(connection.url)
        connection.ws = newWs
        this.setupWebSocketHandlers(connection)
      }
    }, delay)
  }

  /**
   * 心跳检测
   */
  private startHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
    }

    this.heartbeatTimer = setInterval(() => {
      for (const [key, connection] of this.connections) {
        if (connection.ws.readyState === WebSocket.OPEN) {
          // 发送心跳包
          this.send(key, { type: 'ping', timestamp: Date.now() })
        } else if (connection.ws.readyState === WebSocket.CLOSED && connection.isActive) {
          // 检测到连接已断开，尝试重连
          if (connection.reconnectAttempts < connection.maxReconnectAttempts) {
            console.log(`Heartbeat detected closed connection, triggering reconnect: ${key}`)
            this.scheduleReconnect(connection)
          }
        }
      }
    }, this.config.heartbeatInterval)
  }

  /**
   * 获取统计信息
   */
  getStats(): {
    totalConnections: number
    activeConnections: number
    connectionDetails: Array<{
      key: string
      url: string
      isActive: boolean
      readyState: string
      reconnectAttempts: number
    }>
  } {
    const connectionDetails = Array.from(this.connections.values()).map(conn => ({
      key: conn.key,
      url: conn.url,
      isActive: conn.isActive,
      readyState: this.getReadyStateString(conn.ws.readyState),
      reconnectAttempts: conn.reconnectAttempts
    }))

    return {
      totalConnections: this.connections.size,
      activeConnections: connectionDetails.filter(c => c.readyState === 'OPEN').length,
      connectionDetails
    }
  }

  /**
   * 获取连接状态字符串
   */
  private getReadyStateString(state: number): string {
    switch (state) {
      case WebSocket.CONNECTING: return 'CONNECTING'
      case WebSocket.OPEN: return 'OPEN'
      case WebSocket.CLOSING: return 'CLOSING'
      case WebSocket.CLOSED: return 'CLOSED'
      default: return 'UNKNOWN'
    }
  }
}

// 创建全局WebSocket管理器实例
const isPublicTest = import.meta.env.VITE_PUBLIC_TEST === 'true'
const publicWsBase = 'ws://43.167.252.120/ws'

export const wsManager = new WebSocketManager({
  baseUrl: import.meta.env.MODE === 'production' 
    ? 'wss://api.trademe.app/ws'
    : isPublicTest
      ? publicWsBase
      : 'ws://localhost:8001/ws',
  maxReconnectAttempts: 5,
  reconnectDelay: 1000, // 1秒
  heartbeatInterval: 30000 // 30秒
})

// 在应用卸载时清理连接
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    wsManager.disconnectAll()
  })
}