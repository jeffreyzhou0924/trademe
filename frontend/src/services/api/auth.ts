import { userServiceClient, handleApiResponse, handleApiError } from './client'
import type { 
  User, 
  LoginCredentials, 
  RegisterData, 
  LoginResponse 
} from '@/types/auth'

export const authApi = {
  // 用户登录
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    try {
      const response = await userServiceClient.post('/auth/login', credentials)
      const data = handleApiResponse(response)
      // 将后端的access_token字段映射为前端期望的token字段
      return {
        user: data.data.user,
        token: data.data.access_token,
        refresh_token: data.data.refresh_token
      }
    } catch (error) {
      handleApiError(error)
    }
  },

  // 用户注册
  async register(data: RegisterData): Promise<LoginResponse> {
    try {
      const response = await userServiceClient.post('/auth/register', data)
      const responseData = handleApiResponse(response)
      // 注册成功后通常需要验证邮箱，返回用户信息但不自动登录
      return {
        user: responseData.data.user || null,
        token: responseData.data.access_token || null,
        refresh_token: responseData.data.refresh_token || null
      }
    } catch (error) {
      handleApiError(error)
    }
  },

  // Google OAuth登录
  async loginWithGoogle(googleToken: string): Promise<LoginResponse> {
    try {
      const response = await userServiceClient.post('/auth/google', { 
        google_token: googleToken 
      })
      const data = handleApiResponse(response)
      return {
        user: data.data.user,
        token: data.data.access_token,
        refresh_token: data.data.refresh_token
      }
    } catch (error) {
      handleApiError(error)
    }
  },

  // 忘记密码
  async forgotPassword(email: string): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/forgot-password', { email })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取用户信息
  async getProfile(): Promise<User> {
    try {
      const response = await userServiceClient.get('/auth/profile')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 更新用户信息
  async updateProfile(data: Partial<User>): Promise<User> {
    try {
      const response = await userServiceClient.put('/auth/profile', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 刷新token
  async refreshToken(): Promise<{ token: string }> {
    try {
      const response = await userServiceClient.post('/auth/refresh')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 发送验证邮件
  async sendVerificationEmail(): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/send-verification')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 验证邮箱
  async verifyEmail(token: string): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/verify-email', { token })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 发送密码重置邮件
  async sendPasswordReset(email: string): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/password-reset', { email })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 重置密码
  async resetPassword(token: string, password: string): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/password-reset/confirm', {
        token,
        password
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 修改密码
  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 退出登录
  async logout(): Promise<{ message: string }> {
    try {
      const response = await userServiceClient.post('/auth/logout')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}