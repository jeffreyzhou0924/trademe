import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { 
  useUserInfo, 
  useMarketStore, 
  useStrategyStore, 
  useAIStore,
  useGlobalLoading,
  useWebSocketStatus,
  useAuthStore 
} from '@/store'
import { dashboardApi, DashboardStats, RecentActivity, MarketSummary } from '@/services/api/dashboard'
import { Card, LoadingSpinner } from '@/components/common'
import { formatCurrency, formatPercent, formatDateTime } from '@/utils/format'
import toast from 'react-hot-toast'

// 统计卡片组件 - 基于HTML原型重新设计
const StatCard: React.FC<{
  icon: string
  title: string
  value: string | number
  suffix?: string
  trend?: 'positive' | 'negative' | 'neutral'
  iconBg?: string
  iconColor?: string
  className?: string
}> = ({ 
  icon, 
  title, 
  value, 
  suffix = '', 
  trend = 'neutral', 
  iconBg = 'bg-blue-100', 
  iconColor = 'text-blue-600',
  className = '' 
}) => {
  // 图标映射
  const getIcon = (iconName: string) => {
    const icons: Record<string, React.ReactNode> = {
      key: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v-2H7v-2H4a1 1 0 01-1-1v-4c0-2.632 2.122-5.367 5.5-5.5L17 7z" />
        </svg>
      ),
      rocket: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      money: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
        </svg>
      ),
      library: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z" />
        </svg>
      ),
      chart: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      )
    }
    return icons[iconName] || icons.money
  }

  const formatValue = () => {
    if (trend === 'positive' && typeof value === 'number') {
      return <span className="text-green-600 bg-green-50 px-2 py-1 rounded">+{value}{suffix}</span>
    }
    if (trend === 'negative' && typeof value === 'number') {
      return <span className="text-red-600 bg-red-50 px-2 py-1 rounded">{value}{suffix}</span>
    }
    return <span>{value}{suffix}</span>
  }

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all ${className}`}>
      <div className="flex items-center">
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center mr-4 ${iconBg}`}>
          <div className={iconColor}>
            {getIcon(icon)}
          </div>
        </div>
        <div className="flex-1">
          <h3 className="text-sm text-gray-500 mb-1">{title}</h3>
          <p className="text-2xl font-bold">
            {formatValue()}
          </p>
        </div>
      </div>
    </div>
  )
}

// 快捷操作按钮组件 - 基于HTML原型设计
const QuickAction: React.FC<{
  icon: string
  title: string
  onClick: () => void
  variant?: 'primary' | 'secondary'
}> = ({ icon, title, onClick, variant = 'secondary' }) => {
  const getIcon = (iconName: string) => {
    const icons: Record<string, React.ReactNode> = {
      chart: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
      robot: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
      library: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z" />
        </svg>
      ),
      api: (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      )
    }
    return icons[iconName] || icons.chart
  }

  const baseClasses = "flex flex-col items-center justify-center p-6 rounded-xl font-medium transition-all duration-200 hover:transform hover:scale-105"
  const variantClasses = variant === 'primary' 
    ? "bg-blue-600 text-white hover:bg-blue-700 shadow-lg hover:shadow-xl"
    : "bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200"

  return (
    <button
      onClick={onClick}
      className={`${baseClasses} ${variantClasses}`}
    >
      <div className="mb-2">
        {getIcon(icon)}
      </div>
      <span className="text-sm">{title}</span>
    </button>
  )
}

// 收益曲线图表组件 - 基于HTML原型设计
const EarningsChart: React.FC = () => {
  const [timeRange, setTimeRange] = useState<'7d' | '1M' | '3M'>('3M')
  
  // 模拟数据
  const mockData = {
    '7d': [12.1, 11.8, 12.3, 12.7, 11.9, 12.5, 12.3],
    '1M': [8.2, 9.1, 10.5, 11.2, 11.8, 12.1, 12.3],
    '3M': [4.2, 5.7, 8.1, 9.5, 10.8, 11.5, 12.3]
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">✅ 当前收益率曲线 (公网热更新已成功)</h3>
        <div className="flex space-x-2">
          {(['7d', '1M', '3M'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                timeRange === range
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {range === '7d' ? '近7天' : range === '1M' ? '本月' : '近3月'}
            </button>
          ))}
        </div>
      </div>
      
      {/* 简化的图表展示 */}
      <div className="h-64 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg flex items-center justify-center relative overflow-hidden">
        {/* 模拟折线图 */}
        <div className="absolute inset-4 flex items-end space-x-1">
          {mockData[timeRange].map((value, index) => (
            <div
              key={index}
              className="bg-blue-500 rounded-t flex-1 opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
              style={{ height: `${(value / 15) * 100}%` }}
              title={`${value}%`}
            />
          ))}
        </div>
        <div className="text-center z-10">
          <p className="text-sm text-blue-600 mb-1">当前收益率</p>
          <p className="text-3xl font-bold text-blue-700">+{mockData[timeRange].slice(-1)[0]}%</p>
          <p className="text-xs text-blue-500 mt-1">🎉 ECharts图表集成开发中 - 热更新测试成功！</p>
        </div>
      </div>
    </div>
  )
}

// 活动项组件
const ActivityItem: React.FC<{ activity: RecentActivity }> = ({ activity }) => {
  const getActivityIcon = (type: RecentActivity['type']) => {
    switch (type) {
      case 'strategy_created':
        return <div className="w-2 h-2 bg-blue-500 rounded-full" />
      case 'backtest_completed':
        return <div className="w-2 h-2 bg-green-500 rounded-full" />
      case 'trade_executed':
        return <div className="w-2 h-2 bg-purple-500 rounded-full" />
      case 'ai_chat':
        return <div className="w-2 h-2 bg-orange-500 rounded-full" />
      default:
        return <div className="w-2 h-2 bg-gray-500 rounded-full" />
    }
  }

  return (
    <div className="flex items-center space-x-3 p-3 hover:bg-gray-50 rounded-lg">
      {getActivityIcon(activity.type)}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{activity.title}</p>
        <p className="text-sm text-gray-500 truncate">{activity.description}</p>
      </div>
      <div className="text-xs text-gray-400">
        {formatDateTime(activity.timestamp, 'short')}
      </div>
    </div>
  )
}

// 主仪表板页面 - 基于HTML原型重新设计
const DashboardPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isAuthenticated, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()
  const strategies = useStrategyStore(state => state.strategies)
  const activeStrategies = strategies.filter(s => s.status === 'running')

  // 使用静态模拟数据，不调用API
  const stats = null // 移除API调用
  const activities: RecentActivity[] = [] // 使用空数组
  const statsLoading = false
  const activitiesLoading = false

  // 使用静态展示数据，不依赖API
  const [dashboardStats] = useState({
    apiKeys: { current: 6, total: 10 },
    // 显示运行中的实盘策略数量
    activeStrategies: 3,
    // AI生成的策略总数
    strategiesTotal: 4,
    // AI生成的指标数量
    indicatorsCount: 2,
    monthlyReturn: 12.3,
    totalBalance: 56970,
    todayPnL: 1240
  })

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login')
      return
    }
  }, [isAuthenticated, navigate])

  const handleQuickAction = (action: string) => {
    switch (action) {
      case 'chart':
        navigate('/trading-chart')
        break
      case 'backtest':
        navigate('/strategy/backtest')
        break
      case 'library':
        navigate('/strategy/library')
        break
      case 'api':
        navigate('/api-keys')
        break
      default:
        toast('功能开发中...')
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在验证身份...</p>
        </div>
      </div>
    )
  }

  if (statsLoading) {
    return (
      <div className="min-h-96 flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 页面头部 - 基于HTML原型设计 */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                欢迎回来，{user?.username || '交易员'}！
              </h1>
              <p className="text-gray-600 mt-1">
                今日是 {new Date().toLocaleDateString('zh-CN', { 
                  year: 'numeric', 
                  month: 'long', 
                  day: 'numeric',
                  weekday: 'long'
                })}
              </p>
            </div>
            <div className="flex items-center space-x-4">
              {/* WebSocket状态指示器 */}
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-gray-500">
                  {isConnected ? '实时数据已连接' : '数据连接中断'}
                </span>
              </div>
              
              {/* 会员标识 */}
              {isPremium && (
                <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 text-white px-3 py-1 rounded-full text-xs font-medium">
                  高级会员
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 主要内容区域 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 统计卡片区域 - 按照新需求调整为策略/运行中/指标 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatCard
            icon="library"
            title="策略总数"
            value={dashboardStats.strategiesTotal}
            suffix="个"
            iconBg="bg-blue-100"
            iconColor="text-blue-600"
          />
          <StatCard
            icon="rocket"
            title="运行中实盘"
            value={dashboardStats.activeStrategies}
            suffix="个"
            iconBg="bg-green-100"
            iconColor="text-green-600"
          />
          <StatCard
            icon="chart"
            title="指标数量"
            value={dashboardStats.indicatorsCount}
            suffix="个"
            iconBg="bg-purple-100"
            iconColor="text-purple-600"
          />
        </div>

        {/* 收益率曲线图 - 全宽显示 */}
        <div className="mb-8">
          <EarningsChart />
        </div>

        {/* 最近活动区域 */}
        <div className="mt-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">最近活动</h3>
              <button 
                onClick={() => navigate('/trading/history')}
                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
              >
                查看全部 →
              </button>
            </div>
            
            {/* 活动列表 */}
            <div className="space-y-4">
              {activitiesLoading ? (
                <div className="h-32 flex items-center justify-center">
                  <LoadingSpinner />
                </div>
              ) : activities && activities.length > 0 ? (
                activities.slice(0, 3).map((activity) => (
                  <ActivityItem key={activity.id} activity={activity} />
                ))
              ) : (
                // 模拟数据展示
                [
                  { 
                    id: '1', 
                    type: 'trade_executed' as const, 
                    title: 'EMA交叉策略执行了一笔交易',
                    description: '2小时前 • BTC/USDT • +2.3% • $1,240',
                    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
                    status: 'success' as const
                  },
                  { 
                    id: '2', 
                    type: 'strategy_created' as const, 
                    title: 'RSI策略完成回测分析',
                    description: '4小时前 • ETH/USDT • 胜率68% • 年化收益15%',
                    timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
                    status: 'success' as const
                  },
                  { 
                    id: '3', 
                    type: 'ai_chat' as const, 
                    title: 'AI助手生成新策略建议',
                    description: '6小时前 • 布林带突破策略优化方案',
                    timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
                    status: 'success' as const
                  }
                ].map((activity) => (
                  <ActivityItem key={activity.id} activity={activity} />
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 全局加载状态覆盖 */}
      {isLoading && (
        <div className="fixed inset-0 bg-black bg-opacity-20 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 flex items-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <span className="text-gray-900">加载中...</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default DashboardPage