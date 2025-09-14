import axios, { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { handleError } from '@/utils/errorHandler'

// 创建axios实例
const createApiClient = (baseURL: string, serviceName = 'api'): AxiosInstance => {
  const client = axios.create({
    baseURL,
    timeout: 60000, // 增加超时时间到60秒，适应AI响应时间
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // 请求拦截器 - 添加认证token
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      // 从localStorage获取token
      const authData = localStorage.getItem('auth-storage')
      if (authData) {
        try {
          const parsedData = JSON.parse(authData)
          // 兼容两种数据格式：直接存储token或嵌套在state中
          const token = parsedData.state?.token || parsedData.token
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
            console.log(`🔑 [${serviceName}] Added token to request:`, token.substring(0, 20) + '...')
          } else {
            console.warn(`⚠️ [${serviceName}] No token found in auth data`)
          }
        } catch (error) {
          console.error(`❌ [${serviceName}] Failed to parse auth data:`, error)
        }
      } else {
        console.warn(`⚠️ [${serviceName}] No auth data in localStorage`)
      }
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  // 响应拦截器 - 处理错误和token刷新
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      return response
    },
    async (error) => {
      const originalRequest = error.config

      // 401错误处理 - token过期
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true

        // 只有用户服务才尝试刷新token，交易服务直接清除认证状态
        if (serviceName === 'user') {
          try {
            // 尝试刷新token
            const authData = localStorage.getItem('auth-storage')
            if (authData) {
              const parsedData = JSON.parse(authData)
              // 兼容两种数据格式：直接存储token或嵌套在state中
              const currentToken = parsedData.state?.token || parsedData.token
              if (currentToken) {
                // 调用refresh token API
                const refreshResponse = await client.post('/auth/refresh', {
                  token: currentToken
                })
                
                const newToken = refreshResponse.data.token
                
                // 更新localStorage中的token（保持原有格式）
                if (parsedData.state) {
                  // 如果原来是嵌套格式，保持嵌套
                  const updatedState = { ...parsedData.state, token: newToken }
                  localStorage.setItem('auth-storage', JSON.stringify({ state: updatedState }))
                } else {
                  // 如果原来是平级格式，保持平级
                  const updatedData = { ...parsedData, token: newToken }
                  localStorage.setItem('auth-storage', JSON.stringify(updatedData))
                }
                
                // 重新设置请求头
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                
                // 重试原请求
                return client(originalRequest)
              }
            }
          } catch (refreshError) {
            console.error('Token refresh failed:', refreshError)
          }
        }
        
        // 交易服务401错误或用户服务刷新失败，清除认证状态
        console.warn(`${serviceName} service returned 401, clearing auth state`)
        localStorage.removeItem('auth-storage')
        window.location.href = '/login'
        return Promise.reject(error)
      }

      // 使用统一错误处理机制
      const appError = handleError(error, 'api-client', false)
      
      // 返回处理后的错误对象，让上层可以获取更多信息
      return Promise.reject(appError)
    }
  )

  return client
}

// 创建不同的API客户端实例
// 根据环境变量决定使用哪个API地址
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const tradingApiUrl = import.meta.env.VITE_TRADING_API_URL || 'http://localhost:8001/api/v1'

export const userServiceClient = createApiClient(apiBaseUrl, 'user')
export const tradingServiceClient = createApiClient(tradingApiUrl, 'trading')

// 通用API响应处理
export const handleApiResponse = <T>(response: AxiosResponse<T>): T => {
  return response.data
}

// 通用API错误处理
export const handleApiError = (error: any): never => {
  // 如果已经是处理过的AppError，直接使用其消息
  if (error?.type && error?.message) {
    throw new Error(error.message)
  }
  
  // 否则进行标准错误解析
  const appError = handleError(error, 'api-error', true)
  throw new Error(appError.message)
}