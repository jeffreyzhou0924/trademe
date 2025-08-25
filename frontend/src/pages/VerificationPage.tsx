import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

const VerificationPage: React.FC = () => {
  const [verificationCode, setVerificationCode] = useState('')
  const [countdown, setCountdown] = useState(59)
  const [canResend, setCanResend] = useState(false)
  const navigate = useNavigate()

  // 倒计时逻辑
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          setCanResend(true)
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  const handleResendCode = () => {
    if (!canResend) return
    
    // TODO: 调用重新发送验证码API
    toast.success('验证码已重新发送')
    setCountdown(59)
    setCanResend(false)
    
    // 重新启动倒计时
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          setCanResend(true)
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const handleVerification = () => {
    if (verificationCode.length !== 6) {
      toast.error('请输入6位验证码')
      return
    }

    // TODO: 调用验证码验证API
    // 模拟验证成功
    toast.success('验证成功！')
    navigate('/')
  }

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6)
    setVerificationCode(value)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 页面容器 */}
      <div className="w-full max-w-6xl min-h-screen bg-white rounded-xl shadow-xl border border-gray-200 mx-auto flex flex-col">
        {/* 头部 */}
        <header className="py-6 px-8 flex justify-center border-b border-gray-200">
          <div className="flex items-center">
            <svg
              className="w-9 h-9 mr-3"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="12" cy="12" r="10" stroke="#1a3d7c" strokeWidth="2" fill="none"/>
              <path d="M8 12h8M12 8v8" stroke="#1a3d7c" strokeWidth="2"/>
            </svg>
            <h1 className="text-2xl font-bold" style={{ color: '#1a3d7c' }}>
              Trademe
            </h1>
          </div>
        </header>

        {/* 语言和主题切换按钮 */}
        <div className="absolute top-4 right-8 flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <button className="px-2 py-1 text-sm rounded-md bg-gray-100 hover:bg-gray-200">
              中
            </button>
            <button className="px-2 py-1 text-sm rounded-md hover:bg-gray-200">
              EN
            </button>
          </div>
          <div className="border-l border-gray-300 h-6"></div>
          <button className="p-2 rounded-full hover:bg-gray-200">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </button>
        </div>

        {/* 主要内容 */}
        <main className="flex flex-col items-center justify-center flex-1 py-16">
          <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-8 w-full max-w-md">
            <h2 className="text-center text-2xl font-bold mb-8" style={{ color: '#1a3d7c' }}>
              验证码确认
            </h2>
            
            <div className="text-center mb-8">
              <p className="mb-1 text-gray-600">验证码已发送至</p>
              <p className="font-semibold text-gray-800">134****7890@qq.com</p>
            </div>
            
            <div className="mb-8">
              <input
                type="text"
                value={verificationCode}
                onChange={handleCodeChange}
                placeholder="输入验证码"
                maxLength={6}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 text-center text-2xl tracking-wide font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors"
                style={{ letterSpacing: '0.2em' }}
              />
            </div>
            
            <div className="flex justify-between items-center mb-8">
              <button
                onClick={handleResendCode}
                disabled={!canResend}
                className="text-blue-600 text-sm flex items-center hover:underline disabled:text-gray-400 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                重新发送
              </button>
              <span className="text-gray-500 text-sm">
                {canResend ? '可重新发送' : `${countdown}s后可重发`}
              </span>
            </div>
            
            <button
              onClick={handleVerification}
              className="w-full py-3 rounded-lg text-white font-medium hover:opacity-90 transition-opacity mb-6"
              style={{ backgroundColor: '#1a3d7c' }}
            >
              验证并登录
            </button>
            
            <div className="text-center">
              <a href="#" className="text-gray-500 text-sm hover:text-blue-600">
                遇到问题? 联系客服
              </a>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default VerificationPage