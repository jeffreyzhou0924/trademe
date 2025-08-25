/**
 * 认证工具函数 - 统一的认证相关操作
 */

/**
 * 获取认证token
 * @returns 认证token或null
 */
export const getAuthToken = (): string | null => {
  try {
    const authData = localStorage.getItem('auth-storage')
    if (authData) {
      const { state } = JSON.parse(authData)
      return state?.token || null
    }
  } catch (error) {
    console.error('Failed to parse auth data:', error)
  }
  return null
}

/**
 * 创建带认证的请求头
 * @returns 包含Authorization的请求头对象
 */
export const createAuthHeaders = () => {
  const token = getAuthToken()
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  }
}

/**
 * 检查用户是否已认证
 * @returns 是否已认证
 */
export const isAuthenticated = (): boolean => {
  return getAuthToken() !== null
}

/**
 * 清除认证状态
 */
export const clearAuthState = (): void => {
  localStorage.removeItem('auth-storage')
}