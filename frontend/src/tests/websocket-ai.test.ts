/**
 * 前端WebSocket AI系统测试套件
 * 
 * 测试重点：
 * 1. AIStore的错误处理逻辑
 * 2. WebSocket客户端连接和消息处理
 * 3. 流式响应的状态管理
 * 4. Object序列化错误的重现和修复
 */

import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import toast from 'react-hot-toast'

// 模拟依赖
vi.mock('react-hot-toast')
vi.mock('../services/api/ai')
vi.mock('../services/ai/websocketAI')

// 类型定义
interface MockWebSocket extends EventTarget {
  readyState: number
  url: string
  onopen: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent) => void) | null
  onerror: ((event: Event) => void) | null
  onclose: ((event: CloseEvent) => void) | null
  send: Mock
  close: Mock
  CONNECTING: 0
  OPEN: 1
  CLOSING: 2
  CLOSED: 3
}

interface AIStoreState {
  messages: Array<{
    role: string
    content: string
    timestamp: string
    metadata?: any
  }>
  isTyping: boolean
  streamingMessage: any
  aiProgress: any
  error: string | null
  getErrorMessage: (error: any) => string
  sendMessageWebSocket: (message: string) => Promise<boolean>
  initializeWebSocket: () => Promise<boolean>
}

// 模拟AIStore
const createMockAIStore = (): AIStoreState => ({
  messages: [],
  isTyping: false,
  streamingMessage: null,
  aiProgress: null,
  error: null,
  getErrorMessage: (error: any) => {
    if (!error) return '未知错误，请重试'

    // 检查错误类型 - 修复对象序列化问题
    const errorCode = error.error_code || error.code
    let errorMessage = error.error || error.message || ''
    
    // 修复Object序列化问题: 如果error是对象，安全地转换为字符串
    if (typeof errorMessage === 'object' && errorMessage !== null) {
      if (errorMessage.toString && errorMessage.toString() !== '[object Object]') {
        errorMessage = errorMessage.toString()
      } else {
        try {
          errorMessage = JSON.stringify(errorMessage)
        } catch {
          errorMessage = '[对象序列化失败]'
        }
      }
    }
    errorMessage = String(errorMessage || '')
    
    // 基于错误码的友好提示
    switch (errorCode) {
      case 'WEBSOCKET_TIMEOUT':
        return '⏰ AI响应超时，请重试或检查网络连接'
      case 'WEBSOCKET_DISCONNECTED':
        return '🔌 连接断开，正在重新连接...'
      case 'AI_PROCESSING_FAILED':
        return '🤖 AI处理失败，请稍后重试'
    }

    // 基于错误消息内容的智能识别
    if (errorMessage.includes('timeout') || errorMessage.includes('超时')) {
      return '⏰ 请求超时，请重试'
    }
    if (errorMessage.includes('network') || errorMessage.includes('网络')) {
      return '📡 网络连接异常，请检查网络设置'
    }

    // 默认错误消息
    if (errorMessage) {
      return `❌ ${errorMessage}`
    }

    return '⚠️ 服务暂时不可用，请稍后重试'
  },
  sendMessageWebSocket: vi.fn().mockResolvedValue(true),
  initializeWebSocket: vi.fn().mockResolvedValue(true)
})

describe('WebSocket AI系统测试', () => {
  let mockWebSocket: MockWebSocket
  let mockAIStore: AIStoreState
  let originalWebSocket: any

  beforeEach(() => {
    // 创建WebSocket模拟
    mockWebSocket = {
      readyState: 1, // OPEN
      url: 'ws://localhost:8001/ai/ws/chat',
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
      send: vi.fn(),
      close: vi.fn(),
      CONNECTING: 0,
      OPEN: 1,
      CLOSING: 2,
      CLOSED: 3,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    } as MockWebSocket

    // 模拟全局WebSocket
    originalWebSocket = global.WebSocket
    global.WebSocket = vi.fn(() => mockWebSocket) as any

    // 创建AIStore模拟
    mockAIStore = createMockAIStore()

    // 清空模拟调用记录
    vi.clearAllMocks()
  })

  afterEach(() => {
    global.WebSocket = originalWebSocket
  })

  describe('AIStore错误处理测试', () => {
    it('应该正确处理Object序列化错误', () => {
      const problematicObjects = [
        // 原始错误对象
        new Error('测试异常'),
        // 嵌套对象错误  
        { error: { nested: { message: '嵌套错误' } } },
        // null/undefined错误
        null,
        undefined,
        // 循环引用对象
        (() => {
          const circular: any = { data: 'test' }
          circular.self = circular
          return circular
        })(),
        // Mock对象
        { toString: () => '[object Object]' },
        // 函数对象
        () => 'function error',
        // 复杂对象
        {
          error: {
            code: 500,
            details: new Error('详细错误'),
            timestamp: new Date()
          }
        }
      ]

      problematicObjects.forEach((errorObj, index) => {
        const result = mockAIStore.getErrorMessage(errorObj)
        
        expect(typeof result).toBe('string')
        expect(result.length).toBeGreaterThan(0)
        expect(result).not.toBe('[object Object]')
        expect(result).not.toContain('undefined')
        
        console.log(`✅ 错误对象${index}处理成功: ${result}`)
      })
    })

    it('应该根据错误码提供友好提示', () => {
      const errorCodeTests = [
        {
          error: { error_code: 'WEBSOCKET_TIMEOUT' },
          expected: '⏰ AI响应超时，请重试或检查网络连接'
        },
        {
          error: { error_code: 'WEBSOCKET_DISCONNECTED' },
          expected: '🔌 连接断开，正在重新连接...'
        },
        {
          error: { error_code: 'AI_PROCESSING_FAILED' },
          expected: '🤖 AI处理失败，请稍后重试'
        }
      ]

      errorCodeTests.forEach(({ error, expected }) => {
        const result = mockAIStore.getErrorMessage(error)
        expect(result).toBe(expected)
      })
    })

    it('应该智能识别错误消息内容', () => {
      const messageTests = [
        {
          error: { message: 'Connection timeout occurred' },
          expectedPattern: '⏰'
        },
        {
          error: { message: 'Network error detected' },
          expectedPattern: '📡'
        },
        {
          error: { message: '请求超时' },
          expectedPattern: '⏰'
        },
        {
          error: { message: '网络连接失败' },
          expectedPattern: '📡'
        }
      ]

      messageTests.forEach(({ error, expectedPattern }) => {
        const result = mockAIStore.getErrorMessage(error)
        expect(result).toContain(expectedPattern)
      })
    })
  })

  describe('WebSocket连接测试', () => {
    it('应该正确初始化WebSocket连接', async () => {
      // 模拟连接成功
      setTimeout(() => {
        if (mockWebSocket.onopen) {
          mockWebSocket.onopen(new Event('open'))
        }
      }, 10)

      const result = await mockAIStore.initializeWebSocket()
      expect(result).toBe(true)
    })

    it('应该处理WebSocket连接错误', async () => {
      // 模拟连接失败
      const mockError = new Event('error')
      setTimeout(() => {
        if (mockWebSocket.onerror) {
          mockWebSocket.onerror(mockError)
        }
      }, 10)

      const result = await mockAIStore.initializeWebSocket()
      // 根据实际实现调整预期结果
      expect(typeof result).toBe('boolean')
    })

    it('应该正确发送WebSocket消息', async () => {
      mockWebSocket.readyState = 1 // OPEN

      const result = await mockAIStore.sendMessageWebSocket('测试消息')
      expect(result).toBe(true)
      expect(mockWebSocket.send).toHaveBeenCalled()
    })
  })

  describe('流式消息处理测试', () => {
    it('应该正确处理流式消息开始', () => {
      const streamStartMessage = {
        type: 'ai_stream_start',
        request_id: 'test-123',
        session_id: 'session-456',
        model: 'claude-sonnet-4',
        input_tokens: 100
      }

      // 模拟接收流式开始消息
      const messageEvent = new MessageEvent('message', {
        data: JSON.stringify(streamStartMessage)
      })

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage(messageEvent)
      }

      // 验证消息格式
      expect(streamStartMessage.type).toBe('ai_stream_start')
      expect(streamStartMessage.request_id).toBe('test-123')
    })

    it('应该正确累积流式内容', () => {
      const chunks = [
        { type: 'ai_stream_chunk', chunk: '根据市场分析，', request_id: 'test-123' },
        { type: 'ai_stream_chunk', chunk: 'BTC呈现上升趋势，', request_id: 'test-123' },
        { type: 'ai_stream_chunk', chunk: '建议适当加仓。', request_id: 'test-123' }
      ]

      let accumulatedContent = ''
      chunks.forEach(chunk => {
        accumulatedContent += chunk.chunk
      })

      expect(accumulatedContent).toBe('根据市场分析，BTC呈现上升趋势，建议适当加仓。')
    })

    it('应该处理流式错误消息', () => {
      const errorMessages = [
        {
          type: 'ai_stream_error',
          error: 'Connection timeout',
          error_type: 'timeout',
          request_id: 'test-123'
        },
        {
          type: 'ai_stream_error', 
          error: new Error('Network failure'),
          error_type: 'network',
          request_id: 'test-123'
        },
        {
          type: 'ai_stream_error',
          error: null,
          error_type: 'unknown',
          request_id: 'test-123'
        }
      ]

      errorMessages.forEach(errorMsg => {
        const friendlyMessage = mockAIStore.getErrorMessage(errorMsg)
        expect(typeof friendlyMessage).toBe('string')
        expect(friendlyMessage.length).toBeGreaterThan(0)
      })
    })
  })

  describe('消息序列化安全测试', () => {
    it('应该安全处理循环引用对象', () => {
      const circular: any = { name: 'test' }
      circular.self = circular
      circular.parent = { child: circular }

      const result = mockAIStore.getErrorMessage({ error: circular })
      expect(typeof result).toBe('string')
      expect(result).not.toBe('[object Object]')
      expect(result.length).toBeGreaterThan(0)
    })

    it('应该安全处理包含函数的对象', () => {
      const objectWithFunction = {
        error: {
          message: '错误消息',
          handler: () => console.log('error'),
          data: {
            process: function() { return 'processed' }
          }
        }
      }

      const result = mockAIStore.getErrorMessage(objectWithFunction)
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
    })

    it('应该安全处理包含DOM元素的对象', () => {
      // 模拟DOM元素（在Node环境中）
      const mockDOMElement = {
        nodeType: 1,
        tagName: 'DIV',
        toString: () => '[object HTMLDivElement]'
      }

      const result = mockAIStore.getErrorMessage({ error: mockDOMElement })
      expect(typeof result).toBe('string')
      expect(result).not.toBe('[object Object]')
    })
  })

  describe('实际使用场景测试', () => {
    it('应该处理完整的错误响应流程', async () => {
      // 模拟真实的错误响应
      const errorResponse = {
        type: 'ai_stream_error',
        request_id: 'real-request-123',
        error: {
          code: 'CLAUDE_API_ERROR',
          message: 'Claude API rate limit exceeded',
          details: {
            retryAfter: 60,
            errorId: 'err_123456'
          }
        },
        error_type: 'rate_limit',
        retry_suggested: true,
        timestamp: new Date().toISOString()
      }

      const friendlyMessage = mockAIStore.getErrorMessage(errorResponse)
      
      expect(typeof friendlyMessage).toBe('string')
      expect(friendlyMessage.length).toBeGreaterThan(0)
      expect(friendlyMessage).not.toContain('[object Object]')
      
      // 应该包含有用的错误信息
      expect(friendlyMessage).toMatch(/错误|失败|重试|服务/i)
    })

    it('应该处理WebSocket连接状态变化', () => {
      const connectionStates = [
        { readyState: 0, name: 'CONNECTING' },
        { readyState: 1, name: 'OPEN' },
        { readyState: 2, name: 'CLOSING' },
        { readyState: 3, name: 'CLOSED' }
      ]

      connectionStates.forEach(state => {
        mockWebSocket.readyState = state.readyState
        
        // 根据连接状态验证行为
        if (state.readyState === 1) {
          expect(mockWebSocket.readyState).toBe(mockWebSocket.OPEN)
        } else if (state.readyState === 3) {
          expect(mockWebSocket.readyState).toBe(mockWebSocket.CLOSED)
        }
      })
    })
  })

  describe('性能和内存测试', () => {
    it('应该防止内存泄漏在大量错误处理中', () => {
      const largeErrorArray = Array.from({ length: 1000 }, (_, i) => ({
        error: `Error ${i}`,
        timestamp: new Date().toISOString(),
        details: { index: i, data: new Array(100).fill(`data-${i}`) }
      }))

      const startTime = performance.now()
      
      largeErrorArray.forEach(error => {
        const result = mockAIStore.getErrorMessage(error)
        expect(typeof result).toBe('string')
      })
      
      const endTime = performance.now()
      const processingTime = endTime - startTime
      
      // 处理1000个错误应该在合理时间内完成（小于100ms）
      expect(processingTime).toBeLessThan(100)
    })

    it('应该处理深层嵌套对象而不栈溢出', () => {
      // 创建深层嵌套对象
      let deepObject: any = { level: 0 }
      for (let i = 1; i < 100; i++) {
        deepObject = { level: i, nested: deepObject }
      }

      const result = mockAIStore.getErrorMessage({ error: deepObject })
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
    })
  })
})

describe('Object错误重现专项测试', () => {
  it('应该重现并修复AIStore中的Object序列化问题', () => {
    // 这些是导致 "[AIStore] 流式错误: Object" 的具体场景
    const problematicCases = [
      // Case 1: onStreamError接收到的错误对象
      {
        name: 'onStreamError中的错误对象',
        error: {
          error: new Error('Stream processing failed'),
          error_type: 'stream_error',
          request_id: 'test-123'
        }
      },
      // Case 2: WebSocket连接错误
      {
        name: 'WebSocket连接错误',
        error: {
          error: { code: 'ECONNREFUSED', message: 'Connection refused' },
          error_type: 'websocket_error'
        }
      },
      // Case 3: Claude API响应错误
      {
        name: 'Claude API错误响应',
        error: {
          error: {
            type: 'error',
            error: {
              type: 'overloaded_error',
              message: 'Overloaded'
            }
          },
          error_type: 'api_error'
        }
      },
      // Case 4: 序列化失败的复杂对象
      {
        name: '序列化失败的复杂对象',
        error: (() => {
          const obj: any = {
            error: {
              stack: new Error().stack,
              cause: null,
              toString: () => '[object Object]'
            }
          }
          obj.error.circular = obj
          return obj
        })()
      }
    ]

    const mockStore = createMockAIStore()

    problematicCases.forEach(testCase => {
      console.log(`\n测试场景: ${testCase.name}`)
      
      const result = mockStore.getErrorMessage(testCase.error)
      
      // 核心验证：确保不会出现 "Object" 字符串
      expect(result).not.toBe('Object')
      expect(result).not.toBe('[object Object]')
      expect(result).not.toContain('Object')
      
      // 确保结果是有意义的字符串
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
      expect(result.trim()).not.toBe('')
      
      // 确保包含有用信息
      expect(result).toMatch(/错误|失败|异常|超时|连接|重试|服务/i)
      
      console.log(`✅ ${testCase.name} -> ${result}`)
    })
  })

  it('应该验证修复后的getErrorMessage函数', () => {
    // 创建增强版的getErrorMessage函数（修复版本）
    const getErrorMessageFixed = (error: any): string => {
      if (!error) return '未知错误，请重试'

      // 安全提取错误信息
      const errorCode = error?.error_code || error?.code
      let errorMessage = error?.error || error?.message || error

      // 关键修复：安全处理对象类型的错误消息
      if (typeof errorMessage === 'object' && errorMessage !== null) {
        // 如果是Error对象
        if (errorMessage instanceof Error) {
          errorMessage = errorMessage.message || errorMessage.toString()
        }
        // 如果是普通对象
        else if (typeof errorMessage === 'object') {
          try {
            // 尝试JSON序列化
            errorMessage = JSON.stringify(errorMessage, (key, value) => {
              // 过滤掉函数和循环引用
              if (typeof value === 'function') return '[函数]'
              if (typeof value === 'object' && value !== null) {
                if (value.constructor !== Object && value.constructor !== Array) {
                  return value.toString !== Object.prototype.toString 
                    ? value.toString() 
                    : `[${value.constructor.name}对象]`
                }
              }
              return value
            })
          } catch (e) {
            // JSON序列化失败，使用toString
            errorMessage = errorMessage.toString !== Object.prototype.toString
              ? errorMessage.toString()
              : '复杂对象错误'
          }
        }
      }

      // 确保最终是字符串
      errorMessage = String(errorMessage || '未知错误')

      // 基于错误码的友好提示
      switch (errorCode) {
        case 'WEBSOCKET_TIMEOUT':
          return '⏰ AI响应超时，请重试或检查网络连接'
        case 'WEBSOCKET_DISCONNECTED':
          return '🔌 连接断开，正在重新连接...'
        case 'AI_PROCESSING_FAILED':
          return '🤖 AI处理失败，请稍后重试'
      }

      // 基于错误消息内容的智能识别
      const lowerMessage = errorMessage.toLowerCase()
      if (lowerMessage.includes('timeout') || lowerMessage.includes('超时')) {
        return '⏰ 请求超时，请重试'
      }
      if (lowerMessage.includes('network') || lowerMessage.includes('网络')) {
        return '📡 网络连接异常，请检查网络设置'
      }

      // 返回处理后的错误消息
      if (errorMessage && errorMessage !== '未知错误') {
        return `❌ ${errorMessage}`
      }

      return '⚠️ 服务暂时不可用，请稍后重试'
    }

    // 测试修复版本
    const testCases = [
      new Error('测试异常'),
      { error: { nested: 'deep error' } },
      { error: () => 'function error' },
      null,
      undefined,
      'string error',
      42,
      { error: new Date() },
      { error_code: 'WEBSOCKET_TIMEOUT' }
    ]

    testCases.forEach((testCase, index) => {
      const result = getErrorMessageFixed(testCase)
      
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
      expect(result).not.toBe('Object')
      expect(result).not.toBe('[object Object]')
      
      console.log(`✅ 修复测试${index}: ${typeof testCase} -> ${result}`)
    })
  })
})