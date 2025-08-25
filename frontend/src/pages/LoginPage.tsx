import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/authStore'
import { GoogleLogin } from '@react-oauth/google'

// 表单验证模式
const registerSchema = z.object({
  username: z.string().min(2, '用户名至少2位字符'),
  email: z.string().email('请输入有效的邮箱地址'),
  password: z.string().min(6, '密码至少6位字符'),
  confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
  message: '两次输入的密码不一致',
  path: ['confirmPassword']
})

const loginSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址'),
  password: z.string().min(6, '密码至少6位字符'),
})

type RegisterFormData = z.infer<typeof registerSchema>
type LoginFormData = z.infer<typeof loginSchema>

const LoginPage: React.FC = () => {
  const [isRegisterMode, setIsRegisterMode] = useState(true) // 默认注册模式，符合原型图
  const navigate = useNavigate()
  const location = useLocation()
  const { login, register: registerUser, loginWithGoogle, isLoading } = useAuthStore()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset
  } = useForm<RegisterFormData | LoginFormData>({
    resolver: zodResolver(isRegisterMode ? registerSchema : loginSchema)
  })

  // 从location state获取重定向路径
  const from = (location.state as any)?.from?.pathname || '/'

  const onSubmit = async (data: RegisterFormData | LoginFormData) => {
    try {
      let success = false
      let errorMessage = ''
      
      if (isRegisterMode) {
        const registerData = data as RegisterFormData
        const result = await registerUser({
          username: registerData.username,
          email: registerData.email,
          password: registerData.password,
          confirmPassword: registerData.confirmPassword
        })
        success = result.success
        errorMessage = result.message || ''
      } else {
        const loginData = data as LoginFormData
        const result = await login({
          email: loginData.email,
          password: loginData.password
        })
        success = result.success
        errorMessage = result.message || ''
      }

      if (success) {
        toast.success(isRegisterMode ? '注册成功！' : '登录成功！')
        navigate(from, { replace: true })
      } else {
        toast.error(errorMessage || (isRegisterMode ? '注册失败' : '登录失败'))
      }
    } catch (error) {
      console.error('Authentication error:', error)
      toast.error('操作失败，请重试')
    }
  }

  const handleGoogleLogin = async (credentialResponse: any) => {
    try {
      const success = await loginWithGoogle(credentialResponse.credential)
      if (success) {
        toast.success('Google登录成功！')
        navigate(from, { replace: true })
      } else {
        toast.error('Google登录失败')
      }
    } catch (error) {
      console.error('Google login error:', error)
      toast.error('Google登录出错')
    }
  }

  const toggleMode = () => {
    setIsRegisterMode(!isRegisterMode)
    reset()
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8 flex items-center justify-center">
      {/* 主容器，完全按原型图设计 */}
      <div className="w-full max-w-5xl min-h-[800px] bg-white rounded-xl shadow-lg border border-gray-200 relative">
        {/* 语言和主题切换按钮 */}
        <div className="absolute top-4 right-8 flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <button className="px-2 py-1 text-sm rounded-md bg-gray-100 hover:bg-gray-200">中</button>
            <button className="px-2 py-1 text-sm rounded-md hover:bg-gray-200">EN</button>
          </div>
          <div className="border-l border-gray-300 h-6"></div>
          <button className="p-2 rounded-full hover:bg-gray-200">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5"/>
              <path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>
            </svg>
          </button>
        </div>

        {/* 顶部Logo */}
        <header className="py-6 px-8 flex justify-center border-b border-gray-200">
          <div className="flex items-center">
            <svg viewBox="0 0 24 24" className="w-9 h-9 mr-3" style={{ color: '#1a3d7c' }}>
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2"/>
              <path d="M7 12h10M12 7v10" stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
            <h1 className="text-2xl font-bold" style={{ color: '#1a3d7c' }}>Trademe</h1>
          </div>
        </header>

        {/* 主要内容区域 */}
        <main className="flex flex-col items-center justify-center py-16">
          <div className="w-full max-w-md mx-auto">
            {/* 页面标题 */}
            <h2 className="text-center text-2xl font-bold mb-8" style={{ color: '#1a3d7c' }}>
              账户登录
            </h2>

            {/* Google 登录按钮 */}
            <button 
              onClick={() => handleGoogleLogin({ credential: 'mock-credential' })}
              className="w-full flex items-center justify-center py-3 mb-6 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              style={{ backgroundColor: '#1a3d7c', color: 'white' }}
            >
              <svg className="w-6 h-6 mr-2" viewBox="0 0 24 24">
                <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span className="ml-2">通过Google账号登录</span>
            </button>

            {/* 分隔线 */}
            <div className="relative flex justify-center mb-6">
              <hr className="w-full border-gray-300" />
              <span className="absolute px-4 bg-white -top-3 text-gray-500">
                {isRegisterMode ? '或通过邮箱注册' : '或通过邮箱登录'}
              </span>
            </div>

            {/* 表单 */}
            <form onSubmit={handleSubmit(onSubmit)}>
              {isRegisterMode && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                  <input
                    type="text"
                    placeholder="输入用户名"
                    {...register('username')}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                  />
                  {isRegisterMode && (errors as any).username && (
                    <p className="text-red-500 text-sm mt-1">{(errors as any).username?.message}</p>
                  )}
                </div>
              )}

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">邮箱地址</label>
                <input
                  type="email"
                  placeholder="输入邮箱"
                  {...register('email')}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                />
                {errors.email && (
                  <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>
                )}
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
                <input
                  type="password"
                  placeholder="输入密码"
                  {...register('password')}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                />
                {errors.password && (
                  <p className="text-red-500 text-sm mt-1">{errors.password.message}</p>
                )}
              </div>

              {isRegisterMode && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
                  <input
                    type="password"
                    placeholder="再次输入密码"
                    {...register('confirmPassword')}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                  />
                  {isRegisterMode && (errors as any).confirmPassword && (
                    <p className="text-red-500 text-sm mt-1">{(errors as any).confirmPassword?.message}</p>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 mb-6 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
                style={{ backgroundColor: '#1a3d7c' }}
              >
                {isLoading ? '处理中...' : (isRegisterMode ? '创建账户' : '登录')}
              </button>
            </form>

            {/* 底部链接 */}
            <div className="text-center mb-4">
              <p className="text-sm text-gray-500">
                {isRegisterMode ? '已有账户? ' : '没有账户? '}
                <button
                  type="button"
                  onClick={toggleMode}
                  className="text-blue-600 hover:underline"
                >
                  {isRegisterMode ? '立即登录' : '立即注册'}
                </button>
              </p>
            </div>

            {/* 服务条款 */}
            {isRegisterMode && (
              <div className="text-center text-xs text-gray-500">
                <p>
                  注册即表示您同意我们的
                  <Link to="/terms" className="text-blue-600 hover:underline">服务条款</Link>
                  和隐私政策
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default LoginPage