import toast from 'react-hot-toast'
import { AxiosError } from 'axios'

export enum ErrorType {
  NETWORK = 'network',
  AUTH = 'auth', 
  VALIDATION = 'validation',
  SERVER = 'server',
  WEBSOCKET = 'websocket',
  API = 'api',
  UNKNOWN = 'unknown'
}

export interface AppError {
  type: ErrorType
  code?: string | number
  message: string
  details?: any
  timestamp: number
  source?: string
}

export class ErrorHandler {
  private static instance: ErrorHandler
  private errorListeners: Array<(error: AppError) => void> = []

  static getInstance(): ErrorHandler {
    if (!ErrorHandler.instance) {
      ErrorHandler.instance = new ErrorHandler()
    }
    return ErrorHandler.instance
  }

  /**
   * 处理各种类型的错误
   */
  handle(error: any, source?: string, showToast: boolean = true): AppError {
    const appError = this.parseError(error, source)
    
    // 记录错误日志
    this.logError(appError)
    
    // 显示用户友好的错误消息
    if (showToast) {
      this.showErrorToast(appError)
    }
    
    // 通知错误监听器
    this.notifyListeners(appError)
    
    return appError
  }

  /**
   * 解析不同类型的错误
   */
  private parseError(error: any, source?: string): AppError {
    const timestamp = Date.now()
    
    // Axios HTTP错误
    if (error?.isAxiosError || error?.response) {
      return this.parseAxiosError(error, source, timestamp)
    }
    
    // WebSocket错误
    if (error?.type === 'websocket' || source === 'websocket') {
      return {
        type: ErrorType.WEBSOCKET,
        message: this.getWebSocketErrorMessage(error),
        details: error,
        timestamp,
        source
      }
    }
    
    // JavaScript原生错误
    if (error instanceof Error) {
      return {
        type: ErrorType.UNKNOWN,
        message: error.message,
        details: {
          name: error.name,
          stack: error.stack
        },
        timestamp,
        source
      }
    }
    
    // 字符串错误
    if (typeof error === 'string') {
      return {
        type: ErrorType.UNKNOWN,
        message: error,
        timestamp,
        source
      }
    }
    
    // 未知错误类型
    return {
      type: ErrorType.UNKNOWN,
      message: '发生未知错误',
      details: error,
      timestamp,
      source
    }
  }

  /**
   * 解析Axios错误
   */
  private parseAxiosError(error: AxiosError, source?: string, timestamp?: number): AppError {
    const { response, request, message } = error

    if (response) {
      // 服务器响应错误
      const status = response.status
      const data = response.data as any

      if (status === 401) {
        return {
          type: ErrorType.AUTH,
          code: status,
          message: data?.message || '认证失败，请重新登录',
          details: data,
          timestamp: timestamp || Date.now(),
          source
        }
      }

      if (status === 403) {
        return {
          type: ErrorType.AUTH,
          code: status,
          message: data?.message || '权限不足',
          details: data,
          timestamp: timestamp || Date.now(),
          source
        }
      }

      if (status === 422 || status === 400) {
        return {
          type: ErrorType.VALIDATION,
          code: status,
          message: data?.message || '请求参数错误',
          details: data,
          timestamp: timestamp || Date.now(),
          source
        }
      }

      if (status === 429) {
        return {
          type: ErrorType.API,
          code: status,
          message: data?.message || '请求过于频繁，请稍后再试',
          details: data,
          timestamp: timestamp || Date.now(),
          source
        }
      }

      if (status >= 500) {
        return {
          type: ErrorType.SERVER,
          code: status,
          message: data?.message || '服务器内部错误，请稍后再试',
          details: data,
          timestamp: timestamp || Date.now(),
          source
        }
      }

      return {
        type: ErrorType.API,
        code: status,
        message: data?.message || `请求失败 (${status})`,
        details: data,
        timestamp: timestamp || Date.now(),
        source
      }
    }

    if (request) {
      // 网络错误
      return {
        type: ErrorType.NETWORK,
        message: '网络连接失败，请检查网络设置',
        details: { message, request },
        timestamp: timestamp || Date.now(),
        source
      }
    }

    // 请求配置错误
    return {
      type: ErrorType.UNKNOWN,
      message: message || '请求配置错误',
      details: error,
      timestamp: timestamp || Date.now(),
      source
    }
  }

  /**
   * 获取WebSocket错误消息
   */
  private getWebSocketErrorMessage(error: any): string {
    if (error?.code) {
      switch (error.code) {
        case 1006:
          return '连接异常关闭，正在尝试重连...'
        case 1000:
          return '连接正常关闭'
        case 1001:
          return '服务器端点离线'
        case 1002:
          return '协议错误'
        case 1003:
          return '不支持的数据类型'
        case 1005:
          return '未收到关闭状态码'
        case 1011:
          return '服务器遇到意外情况'
        default:
          return `WebSocket连接错误 (${error.code})`
      }
    }
    
    return error?.message || 'WebSocket连接失败'
  }

  /**
   * 显示错误提示
   */
  private showErrorToast(error: AppError): void {
    const { type, message } = error

    switch (type) {
      case ErrorType.AUTH:
        toast.error(message, { 
          id: 'auth-error',
          duration: 5000,
          icon: '🔒'
        })
        break
        
      case ErrorType.NETWORK:
        toast.error(message, {
          id: 'network-error',
          duration: 6000,
          icon: '🌐'
        })
        break
        
      case ErrorType.VALIDATION:
        toast.error(message, {
          id: 'validation-error',
          duration: 4000,
          icon: '⚠️'
        })
        break
        
      case ErrorType.WEBSOCKET:
        toast.error(message, {
          id: 'websocket-error',
          duration: 3000,
          icon: '🔌'
        })
        break
        
      case ErrorType.SERVER:
        toast.error(message, {
          id: 'server-error',
          duration: 5000,
          icon: '🔥'
        })
        break
        
      default:
        toast.error(message, {
          duration: 4000,
          icon: '❌'
        })
    }
  }

  /**
   * 记录错误日志
   */
  private logError(error: AppError): void {
    const logLevel = this.getLogLevel(error.type)
    const logMessage = `[${error.type.toUpperCase()}] ${error.message}`
    
    if (import.meta.env.MODE === 'development') {
      // 开发环境详细日志
      console.group(`🔥 Error: ${logMessage}`)
      console.error('Details:', error)
      console.error('Timestamp:', new Date(error.timestamp).toISOString())
      if (error.source) console.error('Source:', error.source)
      console.groupEnd()
    } else {
      // 生产环境简化日志
      console.error(logMessage, {
        type: error.type,
        code: error.code,
        source: error.source,
        timestamp: error.timestamp
      })
    }

    // TODO: 发送错误到日志服务
    // this.sendToLoggingService(error)
  }

  /**
   * 获取日志级别
   */
  private getLogLevel(errorType: ErrorType): 'error' | 'warn' | 'info' {
    switch (errorType) {
      case ErrorType.AUTH:
      case ErrorType.SERVER:
        return 'error'
      case ErrorType.NETWORK:
      case ErrorType.WEBSOCKET:
        return 'warn'
      default:
        return 'info'
    }
  }

  /**
   * 添加错误监听器
   */
  addErrorListener(listener: (error: AppError) => void): void {
    this.errorListeners.push(listener)
  }

  /**
   * 移除错误监听器
   */
  removeErrorListener(listener: (error: AppError) => void): void {
    this.errorListeners = this.errorListeners.filter(l => l !== listener)
  }

  /**
   * 通知所有监听器
   */
  private notifyListeners(error: AppError): void {
    this.errorListeners.forEach(listener => {
      try {
        listener(error)
      } catch (err) {
        console.error('Error in error listener:', err)
      }
    })
  }

  /**
   * 创建可重试的错误处理器
   */
  createRetryableHandler(
    maxRetries: number = 3,
    retryDelay: number = 1000
  ) {
    return async (
      operation: () => Promise<any>,
      context?: string
    ): Promise<any> => {
      let lastError: any
      
      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          return await operation()
        } catch (error) {
          lastError = error
          const appError = this.parseError(error, context)
          
          // 某些错误不应该重试
          if (appError.type === ErrorType.AUTH || 
              appError.type === ErrorType.VALIDATION) {
            throw error
          }
          
          if (attempt === maxRetries) {
            this.handle(error, context)
            throw error
          }
          
          // 等待后重试
          await new Promise(resolve => 
            setTimeout(resolve, retryDelay * Math.pow(2, attempt - 1))
          )
        }
      }
      
      throw lastError
    }
  }
}

// 全局错误处理器实例
export const errorHandler = ErrorHandler.getInstance()

// 便捷的错误处理函数
export const handleError = (error: any, source?: string, showToast: boolean = true): AppError => {
  return errorHandler.handle(error, source, showToast)
}

// 创建重试处理器
export const createRetryHandler = (maxRetries?: number, retryDelay?: number) => {
  return errorHandler.createRetryableHandler(maxRetries, retryDelay)
}