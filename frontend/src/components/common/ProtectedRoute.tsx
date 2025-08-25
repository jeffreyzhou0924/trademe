import React, { ReactNode, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import LoadingSpinner from './LoadingSpinner'

interface ProtectedRouteProps {
  children: ReactNode
  requireMembership?: 'basic' | 'premium' | 'professional'
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requireMembership 
}) => {
  const location = useLocation()
  const { isAuthenticated, isLoading, user, checkAuth } = useAuthStore()

  useEffect(() => {
    // 如果没有认证状态，尝试检查认证
    if (!isAuthenticated && !isLoading) {
      checkAuth()
    }
  }, [isAuthenticated, isLoading, checkAuth])

  // 正在加载中
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // 未认证，重定向到登录页
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // 检查会员等级要求
  if (requireMembership && user) {
    const membershipLevels = {
      basic: 1,
      premium: 2,
      professional: 3
    }
    
    const userLevel = membershipLevels[user.membership_level] || 0
    const requiredLevel = membershipLevels[requireMembership] || 0
    
    if (userLevel < requiredLevel) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <div className="mb-4">
              <div className="w-16 h-16 mx-auto bg-yellow-100 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">需要升级会员</h3>
            <p className="text-gray-500 mb-4">
              此功能需要 {requireMembership === 'premium' ? '高级版' : '专业版'} 会员权限
            </p>
            <button 
              onClick={() => window.location.href = '/profile/membership'}
              className="btn btn-primary btn-md"
            >
              升级会员
            </button>
          </div>
        </div>
      )
    }
  }

  return <>{children}</>
}

export default ProtectedRoute