import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { useLanguageStore } from '../store/languageStore'
import { GoogleLogin } from '@react-oauth/google'

// 表单验证模式
const loginSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址'),
  password: z.string().min(6, '密码至少6位字符'),
  username: z.string().min(2, '用户名至少2位字符').optional(),
  confirmPassword: z.string().optional()
}).refine((data) => {
  if (data.confirmPassword !== undefined) {
    return data.password === data.confirmPassword
  }
  return true
}, {
  message: '两次输入的密码不一致',
  path: ['confirmPassword']
})

type LoginFormData = z.infer<typeof loginSchema>

const LoginPageNew: React.FC = () => {
  const [isRegisterMode, setIsRegisterMode] = useState(true) // 默认注册模式，符合原型图
  const navigate = useNavigate()
  const location = useLocation()
  const { login, register: registerUser, isLoading } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const { language, setLanguage, t } = useLanguageStore()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema)
  })

  const from = (location.state as any)?.from?.pathname || '/'

  // 主题现在在 App.tsx 中全局处理

  // Google 登录处理函数
  const handleGoogleSuccess = async (credentialResponse: any) => {
    try {
      const result = await useAuthStore.getState().loginWithGoogle(credentialResponse.credential)
      if (result.success) {
        toast.success('Google登录成功！')
        navigate(from, { replace: true })
      } else {
        toast.error(result.message || 'Google登录失败')
      }
    } catch (error) {
      console.error('Google login error:', error)
      toast.error('Google登录出错，请重试')
    }
  }

  const handleGoogleError = () => {
    console.error('Google登录失败')
    toast.error('Google登录失败，请重试')
  }

  const onSubmit = async (data: LoginFormData) => {
    try {
      let success = false
      
      if (isRegisterMode) {
        const result = await registerUser({
          username: data.username || data.email.split('@')[0],
          email: data.email,
          password: data.password,
          confirmPassword: data.confirmPassword || data.password
        })
        success = result.success
        if (!success) {
          toast.error(result.message || '注册失败')
          return
        }
      } else {
        const result = await login({
          email: data.email,
          password: data.password
        })
        success = result.success
        if (!success) {
          toast.error(result.message || '登录失败')
          return
        }
      }

      if (success) {
        toast.success(isRegisterMode ? '注册成功！' : '登录成功！')
        navigate(from, { replace: true })
      }
    } catch (error) {
      console.error('Authentication error:', error)
      toast.error('操作失败，请重试')
    }
  }

  const toggleMode = () => {
    setIsRegisterMode(!isRegisterMode)
    reset()
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8 flex items-center justify-center transition-colors">
      {/* 主容器，完全按原型图设计 */}
      <div className="w-full max-w-5xl min-h-[800px] bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 relative transition-colors">
        {/* 语言和主题切换按钮 */}
        <div className="absolute top-4 right-8 flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <button 
              onClick={() => setLanguage('zh')}
              className={`px-2 py-1 text-sm rounded-md transition-colors ${
                language === 'zh' 
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200' 
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
              }`}
            >
              中
            </button>
            <button 
              onClick={() => setLanguage('en')}
              className={`px-2 py-1 text-sm rounded-md transition-colors ${
                language === 'en' 
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200' 
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
              }`}
            >
              EN
            </button>
          </div>
          <div className="border-l border-gray-300 dark:border-gray-600 h-6"></div>
          <button 
            onClick={toggleTheme} 
            className="p-2 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 transition-colors"
          >
            {theme === 'light' ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="5"/>
                <path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>
              </svg>
            )}
          </button>
        </div>

        {/* 顶部Logo */}
        <header className="py-6 px-8 flex justify-center border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center">
            <svg viewBox="0 0 24 24" className="w-9 h-9 mr-3 text-blue-600 dark:text-blue-400">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2"/>
              <path d="M7 12h10M12 7v10" stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
            <h1 className="text-2xl font-bold text-blue-600 dark:text-blue-400">Trademe</h1>
          </div>
        </header>

        {/* 主要内容区域 */}
        <main className="flex flex-col items-center justify-center py-16">
          <div className="w-full max-w-md mx-auto">
            {/* 页面标题 */}
            <h2 className="text-center text-2xl font-bold mb-8 text-gray-800 dark:text-white">
              {t('accountLogin')}
            </h2>

            {/* Google 登录按钮 */}
            <div className="mb-6">
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={handleGoogleError}
                useOneTap={false}
                theme={theme === 'dark' ? 'filled_black' : 'outline'}
                size="large"
                width="100%"
                text={isRegisterMode ? 'signup_with' : 'signin_with'}
                shape="rectangular"
              />
            </div>

            {/* 分隔线 */}
            <div className="relative flex justify-center mb-6">
              <hr className="w-full border-gray-300 dark:border-gray-600" />
              <span className="absolute px-4 bg-white dark:bg-gray-800 -top-3 text-gray-500 dark:text-gray-400">
                {isRegisterMode ? t('orContinueWith') : t('orContinueWith')}
              </span>
            </div>

            {/* 表单 */}
            <form onSubmit={handleSubmit(onSubmit)}>
              {isRegisterMode && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('username')}</label>
                  <input
                    type="text"
                    placeholder={t('enterUsername')}
                    {...register('username')}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50 dark:bg-gray-700 dark:text-white transition-colors"
                  />
                  {errors.username && (
                    <p className="text-red-500 dark:text-red-400 text-sm mt-1">{errors.username.message}</p>
                  )}
                </div>
              )}

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('email')}</label>
                <input
                  type="email"
                  placeholder={t('enterEmail')}
                  {...register('email')}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50 dark:bg-gray-700 dark:text-white transition-colors"
                />
                {errors.email && (
                  <p className="text-red-500 dark:text-red-400 text-sm mt-1">{errors.email.message}</p>
                )}
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('password')}</label>
                <input
                  type="password"
                  placeholder={t('enterPassword')}
                  {...register('password')}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50 dark:bg-gray-700 dark:text-white transition-colors"
                />
                {errors.password && (
                  <p className="text-red-500 dark:text-red-400 text-sm mt-1">{errors.password.message}</p>
                )}
              </div>

              {isRegisterMode && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('confirmPassword')}</label>
                  <input
                    type="password"
                    placeholder={t('enterPasswordAgain')}
                    {...register('confirmPassword')}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50 dark:bg-gray-700 dark:text-white transition-colors"
                  />
                  {errors.confirmPassword && (
                    <p className="text-red-500 dark:text-red-400 text-sm mt-1">{errors.confirmPassword.message}</p>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 mb-6 text-white font-medium rounded-lg transition-colors disabled:opacity-50 bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700"
              >
                {isLoading ? t('processing') : (isRegisterMode ? t('createAccount') : t('login'))}
              </button>
            </form>

            {/* 底部链接 */}
            <div className="text-center mb-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {isRegisterMode ? t('haveAccount') : t('noAccount')}
                <button
                  type="button"
                  onClick={toggleMode}
                  className="text-blue-600 dark:text-blue-400 hover:underline ml-1"
                >
                  {isRegisterMode ? t('loginNow') : t('registerNow')}
                </button>
              </p>
            </div>

            {/* 服务条款 */}
            {isRegisterMode && (
              <div className="text-center text-xs text-gray-500 dark:text-gray-400">
                <p>
                  {t('byRegisteringAgree')}
                  <a href="/terms" className="text-blue-600 dark:text-blue-400 hover:underline">{t('termsOfService')}</a>
                  {t('and')}
                  <a href="/privacy" className="text-blue-600 dark:text-blue-400 hover:underline">{t('privacyPolicy')}</a>
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default LoginPageNew