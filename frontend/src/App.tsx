import { Routes, Route } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { useEffect } from 'react'
import { GoogleOAuthProvider } from '@react-oauth/google'

// 页面组件
import HomePage from './pages/HomePage'
import LoginPageNew from './pages/LoginPageNew'
import VerificationPage from './pages/VerificationPage'
import OverviewPage from './pages/OverviewPage'
import StrategiesPage from './pages/StrategiesPage'
// 策略模板功能暂时隐藏 - 项目初期未考虑此功能
// import StrategyTemplatesPage from './pages/StrategyTemplatesPage'
import StrategyLiveDetailsPage from './pages/StrategyLiveDetailsPage'
import LiveStrategiesPage from './pages/LiveStrategiesPage'
import BacktestPage from './pages/BacktestPage'
import BacktestDetailsPage from './pages/BacktestDetailsPage'
import TradingPage from './pages/TradingPage'
import AIChatPage from './pages/AIChatPage'
import APIManagementPage from './pages/APIManagementPage'
import TradingNotesPage from './pages/TradingNotesPage'
import ProfilePage from './pages/ProfilePage'
import AdminDashboardPage from './pages/AdminDashboardPage'
import UserManagementPage from './pages/UserManagementPage'
import ClaudeManagementPage from './pages/ClaudeManagementPage'
import WalletManagementPage from './pages/WalletManagementPage'
import DataManagementPageReal from './pages/DataManagementPageReal'
import NotFoundPage from './pages/NotFoundPage'

// 布局组件
import MainLayout from './components/layout/MainLayout'
import AuthLayout from './components/layout/AuthLayout'

// 路由保护组件
import ProtectedRoute from './components/common/ProtectedRoute'
import LoadingSpinner from './components/common/LoadingSpinner'

function App() {
  const { isLoading, checkAuth, token, isAuthenticated } = useAuthStore()
  const { theme } = useThemeStore()

  // 应用启动时检查认证状态
  useEffect(() => {
    // 只有在有token但未认证的情况下才调用checkAuth
    // 这样可以避免每次热更新都重新验证token
    if (token && !isAuthenticated) {
      checkAuth()
    }
  }, [checkAuth, token, isAuthenticated])

  // 全局应用主题效果
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  // 显示加载状态
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 transition-colors">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID || "temp_client_id_for_development"}>
      <Routes>
        {/* 公开路由 - 登录页面不使用AuthLayout */}
        <Route path="/login" element={<LoginPageNew />} />
      
      <Route path="/verification" element={
        <AuthLayout>
          <VerificationPage />
        </AuthLayout>
      } />

      {/* 主页 - 已登录用户重定向到AI助手，未登录显示欢迎页 */}
      <Route path="/" element={<HomePage />} />

      {/* 受保护路由 - 使用主布局 */}
      <Route path="/overview" element={
        <ProtectedRoute>
          <MainLayout>
            <OverviewPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/strategies" element={
        <ProtectedRoute>
          <MainLayout>
            <StrategiesPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      {/* 策略模板功能暂时隐藏 - 项目初期未考虑此功能 */}
      {/* <Route path="/strategy-templates" element={
        <ProtectedRoute>
          <MainLayout>
            <StrategyTemplatesPage />
          </MainLayout>
        </ProtectedRoute>
      } /> */}

      <Route path="/strategy/:strategyId/live" element={
        <ProtectedRoute>
          <MainLayout>
            <StrategyLiveDetailsPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/live-strategies" element={
        <ProtectedRoute>
          <LiveStrategiesPage />
        </ProtectedRoute>
      } />

      <Route path="/backtest" element={
        <ProtectedRoute>
          <MainLayout>
            <BacktestPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/backtest/:id/details" element={
        <ProtectedRoute>
          <MainLayout>
            <BacktestDetailsPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/trading" element={
        <ProtectedRoute>
          <TradingPage />
        </ProtectedRoute>
      } />

      <Route path="/ai-chat" element={
        <ProtectedRoute>
          <MainLayout>
            <AIChatPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/api-keys" element={
        <ProtectedRoute>
          <MainLayout>
            <APIManagementPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      {/* 兼容旧路径 */}
      <Route path="/api-management" element={
        <ProtectedRoute>
          <MainLayout>
            <APIManagementPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/trading-notes" element={
        <ProtectedRoute>
          <MainLayout>
            <TradingNotesPage />
          </MainLayout>
        </ProtectedRoute>
      } />

      <Route path="/profile" element={
        <ProtectedRoute>
          <MainLayout>
            <ProfilePage />
          </MainLayout>
        </ProtectedRoute>
      } />

      {/* 管理员后台 - 不使用MainLayout */}
      <Route path="/admin" element={
        <ProtectedRoute>
          <AdminDashboardPage />
        </ProtectedRoute>
      } />

      {/* 用户管理页面 */}
      <Route path="/admin/users" element={
        <ProtectedRoute>
          <UserManagementPage />
        </ProtectedRoute>
      } />

      {/* Claude AI服务管理页面 */}
      <Route path="/admin/claude" element={
        <ProtectedRoute>
          <ClaudeManagementPage />
        </ProtectedRoute>
      } />

      {/* USDT钱包池管理页面 */}
      <Route path="/admin/wallets" element={
        <ProtectedRoute>
          <WalletManagementPage />
        </ProtectedRoute>
      } />
      
      {/* 数据管理页面 */}
      <Route path="/admin/data" element={
        <ProtectedRoute>
          <DataManagementPageReal />
        </ProtectedRoute>
      } />

      {/* 404页面 */}
      <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </GoogleOAuthProvider>
  )
}

export default App