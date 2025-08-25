import React, { ReactNode } from 'react'

interface AuthLayoutProps {
  children: ReactNode
}

const AuthLayout: React.FC<AuthLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      {/* 页面容器 */}
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
        {/* Header */}
        <header className="py-6 px-8 flex justify-center border-b border-gray-200">
          <div className="flex items-center">
            <div className="w-9 h-9 rounded-full bg-brand-500 flex items-center justify-center mr-3">
              <span className="text-white font-bold">T</span>
            </div>
            <h1 className="text-2xl font-bold text-brand-500">Trademe</h1>
          </div>
        </header>
        
        {/* 语言和主题切换按钮 */}
        <div className="absolute top-4 right-4 flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <button 
              className="lang-toggle px-2 py-1 text-sm rounded-md bg-gray-100 hover:bg-gray-200"
              data-lang="zh"
            >
              中
            </button>
            <button 
              className="lang-toggle px-2 py-1 text-sm rounded-md hover:bg-gray-200"
              data-lang="en"
            >
              EN
            </button>
          </div>
          <div className="border-l border-gray-300 h-6"></div>
          <button 
            id="theme-toggle" 
            className="p-2 rounded-full hover:bg-gray-200"
            title="切换主题"
          >
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path 
                fill="currentColor" 
                d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.757a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z"
              />
            </svg>
          </button>
        </div>
        
        {/* Main Content */}
        <main className="p-8">
          {children}
        </main>
        
        {/* Footer */}
        <footer className="px-8 pb-6 text-center">
          <p className="text-xs text-gray-500">
            © 2024 Trademe. 专业的数字货币策略交易平台
          </p>
        </footer>
      </div>
    </div>
  )
}

export default AuthLayout