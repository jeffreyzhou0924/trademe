import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import toast from 'react-hot-toast'
import { authApi } from '../services/api/auth'
import type { User, LoginCredentials, RegisterData } from '../types/auth'

interface AuthState {
  // 状态
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  
  // 操作方法
  login: (credentials: LoginCredentials) => Promise<{success: boolean, message?: string}>
  register: (data: RegisterData) => Promise<{success: boolean, message?: string}>
  loginWithGoogle: (credential: string) => Promise<{success: boolean, message?: string}>
  logout: () => void
  checkAuth: () => Promise<void>
  updateProfile: (data: Partial<User>) => Promise<boolean>
  refreshToken: () => Promise<boolean>
  clearError: () => void
  forgotPassword: (email: string) => Promise<boolean>
  resetPassword: (token: string, newPassword: string) => Promise<boolean>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // 初始状态
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // 登录
      login: async (credentials: LoginCredentials) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.login(credentials)
          
          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
            isLoading: false,
            error: null
          })
          
          return { success: true }
        } catch (error: any) {
          const message = error.response?.data?.message || error.message || '登录失败'
          let detailedMessage = message
          
          // 解析详细错误信息
          if (message.includes('not found') || message.includes('不存在')) {
            detailedMessage = '用户不存在'
          } else if (message.includes('password') || message.includes('密码')) {
            detailedMessage = '密码错误'
          }
          
          set({ 
            isLoading: false,
            error: detailedMessage
          })
          return { success: false, message: detailedMessage }
        }
      },

      // 注册
      register: async (data: RegisterData) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.register(data)
          
          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
            isLoading: false,
            error: null
          })
          
          return { success: true }
        } catch (error: any) {
          const message = error.response?.data?.message || '注册失败'
          set({ 
            isLoading: false,
            error: message
          })
          return { success: false, message }
        }
      },

      // Google登录
      loginWithGoogle: async (credential: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.loginWithGoogle(credential)
          
          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
            isLoading: false,
            error: null
          })
          
          return { success: true }
        } catch (error: any) {
          const message = error.response?.data?.message || 'Google登录失败'
          set({ 
            isLoading: false,
            error: message
          })
          return { success: false, message }
        }
      },

      // 忘记密码
      forgotPassword: async (email: string) => {
        try {
          await authApi.forgotPassword(email)
          return true
        } catch (error) {
          return false
        }
      },

      // 重置密码
      resetPassword: async (token: string, newPassword: string) => {
        try {
          await authApi.resetPassword(token, newPassword)
          return true
        } catch (error) {
          return false
        }
      },

      // 登出
      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
          error: null
        })
        toast.success('已退出登录')
      },

      // 检查认证状态
      checkAuth: async () => {
        const { token, isAuthenticated, user } = get()
        
        // 如果没有token，直接返回
        if (!token) return
        
        // 如果已经认证且有用户信息，避免重复验证
        if (isAuthenticated && user) return

        set({ isLoading: true, error: null })
        try {
          const userProfile = await authApi.getProfile()
          set({
            user: userProfile,
            isAuthenticated: true,
            isLoading: false,
            error: null
          })
        } catch (error) {
          // Token无效，清除认证状态
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: 'Token已失效，请重新登录'
          })
        }
      },

      // 更新个人资料
      updateProfile: async (data: Partial<User>) => {
        try {
          const updatedUser = await authApi.updateProfile(data)
          set(state => ({
            user: { ...state.user!, ...updatedUser },
            error: null
          }))
          toast.success('个人资料更新成功')
          return true
        } catch (error: any) {
          const message = error.response?.data?.message || '更新失败'
          set({ error: message })
          toast.error(message)
          return false
        }
      },

      // 刷新token
      refreshToken: async () => {
        try {
          const response = await authApi.refreshToken()
          set({ token: response.token, error: null })
          return true
        } catch (error) {
          // 刷新失败，清除认证状态
          get().logout()
          return false
        }
      },

      // 清空错误
      clearError: () => {
        set({ error: null })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)