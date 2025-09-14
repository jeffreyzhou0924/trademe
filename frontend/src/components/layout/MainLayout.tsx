import React, { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useThemeStore } from '../../store/themeStore'
import { useLanguageStore } from '../../store/languageStore'

interface MainLayoutProps {
  children: ReactNode
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const { language, setLanguage, t } = useLanguageStore()

  const navItems = [
    { path: '/ai-chat', label: 'AI助手', key: 'ai-chat' },
    // 仪表盘功能暂时隐藏
    // { path: '/overview', label: t('dashboard'), key: 'home' },
    { path: '/strategies', label: t('liveTrading'), key: 'strategies' },
    // 策略模板功能暂时隐藏 - 项目初期未考虑此功能
    // { path: '/strategy-templates', label: '策略模板', key: 'strategy-templates' },
    { path: '/backtest', label: t('backtest'), key: 'backtest' },
    // 移除图表交易和交易心得 - 不作为生产环境1.0功能
    // { path: '/trading', label: t('chartTrading'), key: 'trading' },
    // { path: '/trading-notes', label: t('tradingNotes'), key: 'trading-notes' },
    // API管理已移至账户中心入口 - 从导航栏删除
    // { path: '/api-keys', label: t('apiManagement'), key: 'api' },
    { path: '/profile', label: t('accountCenter'), key: 'profile' },
  ]

  const isActiveRoute = (path: string) => {
    if (path === '/ai-chat') {
      return location.pathname === '/ai-chat'
    }
    // 精确匹配，避免 /trading-notes 激活 /trading
    if (path === '/trading') {
      return location.pathname === '/trading'
    }
    return location.pathname.startsWith(path)
  }

  const handleLogout = () => {
    logout()
    window.location.href = '/login'
  }

  const handleLanguageChange = (lang: 'zh' | 'en') => {
    setLanguage(lang)
  }

  const handleThemeToggle = () => {
    toggleTheme()
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* 页面容器 */}
      <div className="max-w-[1440px] mx-auto bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden relative transition-colors">
        {/* Header */}
        <header className="py-4 px-8 flex justify-between border-b border-gray-200 dark:border-gray-700">
          {/* Logo */}
          <div className="flex items-center">
            <div className="w-7 h-7 rounded-full bg-brand-500 flex items-center justify-center mr-3">
              <span className="text-white font-bold text-sm">T</span>
            </div>
            <h1 className="text-xl font-bold text-brand-500 dark:text-brand-400">Trademe</h1>
          </div>
          
          {/* Navigation */}
          <nav className="flex gap-2">
            {navItems.map((item) => (
              <Link
                key={item.key}
                to={item.path}
                className={`nav-item ${
                  isActiveRoute(item.path) ? 'active' : ''
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          
          {/* User Profile */}
          <div className="flex items-center relative group">
            <div className="w-9 h-9 rounded-full bg-gray-200 overflow-hidden cursor-pointer">
              {user?.avatar_url ? (
                <img 
                  src={user.avatar_url} 
                  alt="User avatar" 
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-brand-100 text-brand-600 font-medium">
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </div>
              )}
            </div>
            
            {/* 用户下拉菜单 */}
            <div className="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
              <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                <p className="font-medium text-gray-900 dark:text-gray-100">{user?.username}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{user?.email}</p>
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-200 mt-1">
                  {user?.membership_level === 'basic' && '基础版'}
                  {user?.membership_level === 'premium' && '高级版'}
                  {user?.membership_level === 'professional' && '专业版'}
                </span>
              </div>
              <Link
                to="/profile"
                className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                {t('settings')}
              </Link>
              <Link
                to="/profile/membership"
                className="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                {t('membershipManagement')}
              </Link>
              <button
                onClick={handleLogout}
                className="block w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
              >
                {t('logout')}
              </button>
            </div>
          </div>
        </header>
        
        {/* 语言和主题切换按钮 */}
        <div className="absolute top-4 right-8 flex items-center space-x-4 z-40">
          <div className="flex items-center space-x-2">
            <button 
              onClick={() => handleLanguageChange('zh')}
              className={`px-2 py-1 text-sm rounded-md transition-colors ${
                language === 'zh' 
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200' 
                  : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300'
              }`}
            >
              中
            </button>
            <button 
              onClick={() => handleLanguageChange('en')}
              className={`px-2 py-1 text-sm rounded-md transition-colors ${
                language === 'en' 
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-800 dark:text-blue-200' 
                  : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300'
              }`}
            >
              EN
            </button>
          </div>
          <div className="border-l border-gray-300 dark:border-gray-600 h-6"></div>
          <button 
            onClick={handleThemeToggle}
            className="p-2 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            title={theme === 'light' ? t('darkMode') : t('lightMode')}
          >
            {theme === 'light' ? (
              // Sun icon for light mode
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="5"/>
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
              </svg>
            ) : (
              // Moon icon for dark mode
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>
        </div>
        
        {/* Main Content */}
        <main className="p-8">
          {children}
        </main>
      </div>
    </div>
  )
}

export default MainLayout