import React from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/common/Button'

const VerificationPage: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 transition-colors">
      <div className="max-w-md w-full space-y-8 p-6">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900 dark:text-white">
            邮箱验证
          </h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            请检查您的邮箱以完成账户验证
          </p>
        </div>
        
        <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.2a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            
            <div>
              <p className="text-gray-700 dark:text-gray-300">
                我们已向您的邮箱发送了验证链接，请点击链接完成账户激活。
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                如果您没有收到邮件，请检查垃圾邮件箱或稍后重试。
              </p>
            </div>
            
            <div className="space-y-3">
              <Button
                onClick={() => window.location.reload()}
                variant="outline"
                className="w-full"
              >
                重新发送验证邮件
              </Button>
              
              <Button
                onClick={() => navigate('/login')}
                variant="primary"
                className="w-full"
              >
                返回登录
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default VerificationPage