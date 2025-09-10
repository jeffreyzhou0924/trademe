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
          const { state } = JSON.parse(authData)
          if (state?.token) {
            config.headers.Authorization = `Bearer ${state.token}`
          }
        } catch (error) {
          console.error('Failed to parse auth data:', error)
        }
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
              const { state } = JSON.parse(authData)
              if (state?.token) {
                // 调用refresh token API
                const refreshResponse = await client.post('/auth/refresh', {
                  token: state.token
                })
                
                const newToken = refreshResponse.data.token
                
                // 更新localStorage中的token
                const updatedState = { ...state, token: newToken }
                localStorage.setItem('auth-storage', JSON.stringify({ state: updatedState }))
                
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