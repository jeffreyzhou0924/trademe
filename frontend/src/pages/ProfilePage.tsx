import React, { useState, useEffect } from 'react'
import { useUserInfo, useAuthStore } from '../store'
import { useLanguageStore } from '../store/languageStore'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

// 会员套餐配置
const membershipPlans = [
  {
    level: 'basic',
    name: '初级会员',
    price: 19,
    period: '月',
    color: 'green',
    description: '入门级功能套餐',
    highlight: '适合刚开始量化交易的新手用户',
    features: [
      'AI交易员模式/AI开发者模式',
      'AI交易心得功能',
      '每天使用$20额度的AI助手',
      '绑定1个交易所API KEY',
      '包含1个免费实盘'
    ],
    benefits: [
      '✅ AI交易员模式',
      '✅ AI开发者模式',
      '✅ AI交易心得功能',
      '✅ 每日$20 AI助手额度',
      '✅ 1个交易所API密钥',
      '✅ 1个免费实盘交易',
      '✅ 基础策略模板库',
      '✅ 邮件技术支持'
    ],
    limitations: [
      '❌ 无Tick级别数据回测',
      '❌ 多API密钥管理',
      '❌ 大量AI对话额度',
      '❌ 高级策略优化'
    ]
  },
  {
    level: 'premium',
    name: '高级会员',
    price: 99,
    period: '月',
    color: 'blue',
    popular: true,
    description: '全功能专业套餐',
    highlight: '热门选择，功能全面且性价比高',
    features: [
      '初级会员所有功能',
      '每天使用$100额度的AI助手',
      '每月可使用Tick级别数据回测30次',
      '绑定5个API交易所API KEY',
      '包含5个免费实盘'
    ],
    benefits: [
      '✅ 初级会员所有功能',
      '✅ 每日$100 AI助手额度',
      '✅ 每月30次Tick级别回测',
      '✅ 5个交易所API密钥',
      '✅ 5个免费实盘交易',
      '✅ 高级技术指标',
      '✅ 策略性能分析',
      '✅ 7×24小时技术支持'
    ],
    limitations: [
      '❌ AI图表交易模式',
      '❌ 企业定制服务',
      '❌ 专属客户经理'
    ]
  },
  {
    level: 'professional',
    name: '专业会员',
    price: 199,
    period: '月',
    color: 'purple',
    popular: false,
    description: '专业交易者首选',
    highlight: '专业交易者和机构用户的完整解决方案',
    features: [
      '高级会员所有功能',
      'AI图表交易模式',
      '每天使用$200额度的AI对话',
      '每月可使用Tick级别数据回测100次',
      '绑定10个交易所API KEY',
      '包含10个免费实盘'
    ],
    benefits: [
      '✅ 高级会员所有功能',
      '✅ AI图表交易模式',
      '✅ 每日$200 AI对话额度',
      '✅ 每月100次Tick级别回测',
      '✅ 10个交易所API密钥',
      '✅ 10个免费实盘交易',
      '✅ 定制化策略开发',
      '✅ 专属客户经理',
      '✅ 7×24小时VIP支持',
      '✅ 优先技术服务'
    ],
    limitations: []
  }
]

interface UserStats {
  api_keys_count: number
  api_keys_limit: number
  ai_usage_today: number
  ai_daily_limit: number
  tick_backtest_today: number
  tick_backtest_limit: number
  storage_used: number
  storage_limit: number
  indicators_count: number
  indicators_limit: number
  strategies_count: number
  strategies_limit: number
  live_trading_count: number
  live_trading_limit: number
}

interface APIKey {
  id: number
  name: string
  exchange: string
  api_key: string
  status: 'active' | 'inactive' | 'error'
  created_at: string
  balance?: {
    total: number
    available: number
    currency: string
  }
  performance?: {
    total_return: number
    daily_return: number
    win_rate: number
    created_days: number
  }
}

const ProfilePage: React.FC = () => {
  const { user, isPremium } = useUserInfo()
  const { token, logout } = useAuthStore()
  const { t } = useLanguageStore()
  const navigate = useNavigate()
  const [stats, setStats] = useState<UserStats | null>(null)
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingApiKeys, setLoadingApiKeys] = useState(false)
  const [showPayment, setShowPayment] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState<string>('')

  // 获取用户使用统计
  const loadUserStats = async () => {
    try {
      setLoading(true)
      console.log('🔍 ProfilePage - 获取token:', token ? '已获取' : '未获取')
      console.log('🔍 ProfilePage - API URL:', `${import.meta.env.VITE_TRADING_API_URL}/membership/usage-stats`)
      
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/membership/usage-stats`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      console.log('🔍 ProfilePage - 响应状态:', response.status)
      
      if (response.ok) {
        const data = await response.json()
        console.log('🔍 ProfilePage - 获取数据成功:', data)
        setStats(data.data)
      } else {
        const errorText = await response.text()
        console.error('🔍 ProfilePage - 请求失败:', response.status, errorText)
        // 显示更友好的错误提示
        if (response.status === 401) {
          console.warn('Token已过期，需要重新登录')
        } else if (response.status === 500) {
          console.error('服务器内部错误，请稍后重试')
        }
      }
    } catch (error) {
      console.error('Load usage stats error:', error)
      // 网络错误或其他异常
      if (error instanceof Error) {
        console.error('网络连接异常:', error.message)
      }
    } finally {
      setLoading(false)
    }
  }

  // 获取API密钥列表
  const loadAPIKeys = async () => {
    if (!token) return
    
    try {
      setLoadingApiKeys(true)
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/api-keys/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        let data = { api_keys: [] }
        try {
          const text = await response.text()
          data = text ? JSON.parse(text) : { api_keys: [] }
        } catch (e) {
          console.log('Response is not JSON, using empty array')
        }
        
        // 模拟添加余额和收益率数据
        const enrichedApiKeys = (data.api_keys || []).map((key: any, index: number) => ({
          ...key,
          balance: {
            total: 10000 + index * 5000,
            available: 8000 + index * 4000,
            currency: 'USDT'
          },
          performance: {
            total_return: 15.6 + index * 8.2,
            daily_return: 0.8 + index * 0.3,
            win_rate: 68.5 + index * 5.1,
            created_days: Math.floor(Math.random() * 90) + 30
          }
        }))
        
        setApiKeys(enrichedApiKeys)
      } else {
        console.error('Failed to load API keys:', response.status)
      }
    } catch (error) {
      console.error('Error loading API keys:', error)
    } finally {
      setLoadingApiKeys(false)
    }
  }

  // 获取会员套餐颜色样式
  const getPlanColorClass = (color: string, type: 'bg' | 'text' | 'border') => {
    const colorMap = {
      gray: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
      blue: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
      purple: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
      gold: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' }
    }
    return colorMap[color]?.[type] || colorMap.gray[type]
  }

  // 计算使用百分比
  const getUsagePercentage = (used: number, limit: number) => {
    if (limit === 0) return 0
    return Math.min((used / limit) * 100, 100)
  }

  // 获取当前用户的套餐信息
  const getCurrentPlan = () => {
    return membershipPlans.find(plan => plan.level === user?.membership_level) || membershipPlans[0]
  }

  // 处理套餐升级
  const handleUpgrade = (planLevel: string) => {
    setSelectedPlan(planLevel)
    setShowPayment(true)
  }

  // 模拟支付处理
  const handlePayment = async () => {
    try {
      // 这里应该调用实际的支付API
      toast.success('支付成功！会员权益已更新')
      setShowPayment(false)
      setSelectedPlan('')
      // 重新加载用户信息和统计
      loadUserStats()
    } catch (error) {
      toast.error('支付失败，请重试')
    }
  }

  // 处理用户退出登录
  const handleLogout = () => {
    if (window.confirm('确定要退出登录吗？')) {
      logout()
      navigate('/login')
    }
  }

  // 跳转到API创建页面
  const handleAddAPIKey = () => {
    navigate('/api-keys')
  }

  // 删除API密钥
  const handleDeleteAPIKey = async (id: number, name: string) => {
    if (!window.confirm(`确定要删除API密钥 "${name}" 吗？`)) {
      return
    }
    
    try {
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/api-keys/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (response.ok) {
        toast.success('API密钥删除成功')
        loadAPIKeys()
      } else {
        throw new Error('Failed to delete API key')
      }
    } catch (error) {
      console.error('Error deleting API key:', error)
      toast.error('删除API密钥失败')
    }
  }

  // 获取状态指示器
  const getStatusIndicator = (status: string) => {
    switch (status) {
      case 'active':
        return <div className="w-2 h-2 bg-green-500 rounded-full"></div>
      case 'inactive':
        return <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
      case 'error':
        return <div className="w-2 h-2 bg-red-500 rounded-full"></div>
      default:
        return <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '正常'
      case 'inactive': return '无效'
      case 'error': return '错误'
      default: return '未知'
    }
  }

  // 获取交易所图标
  const getExchangeIcon = (exchange: string) => {
    const icons: {[key: string]: string} = {
      'okx': '🟢',
      'binance': '🟡', 
      'huobi': '🔴',
      'bybit': '🟠',
      'kraken': '🟣',
      'coinbase': '🔵'
    }
    return icons[exchange.toLowerCase()] || '🔧'
  }

  useEffect(() => {
    if (token && user) {
      loadUserStats()
      loadAPIKeys()
    }
  }, [token, user])

  const currentPlan = getCurrentPlan()
  const selectedPlanInfo = membershipPlans.find(plan => plan.level === selectedPlan)

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">账户中心</h1>
          <p className="text-gray-600 mt-1">管理您的账户信息、会员权益和使用状况</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：用户信息和当前套餐 */}
        <div className="lg:col-span-1 space-y-6">
          {/* 用户信息卡片 */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
            <div className="text-center">
              <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                {user?.avatar_url ? (
                  <img src={user.avatar_url} alt="Avatar" className="w-full h-full rounded-full object-cover" />
                ) : (
                  <span className="text-2xl font-bold text-white">
                    {user?.username?.charAt(0).toUpperCase() || 'U'}
                  </span>
                )}
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-1">{user?.username}</h3>
              <p className="text-gray-500 mb-4">{user?.email}</p>
              
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getPlanColorClass(currentPlan.color, 'bg')} ${getPlanColorClass(currentPlan.color, 'text')}`}>
                <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732L14.146 12.8l-1.179 4.456a1 1 0 01-1.934 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732L9.854 7.2l1.179-4.456A1 1 0 0112 2z" clipRule="evenodd" />
                </svg>
                {currentPlan.name}
              </div>

              {user?.membership_expires_at && (
                <p className="text-xs text-gray-500 mt-2">
                  到期时间: {new Date(user.membership_expires_at).toLocaleDateString()}
                </p>
              )}

              {/* 退出登录按钮 */}
              <button
                onClick={handleLogout}
                className="mt-4 w-full py-2 px-4 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center justify-center space-x-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>退出登录</span>
              </button>
            </div>
          </div>

          {/* 当前套餐详情 */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">当前套餐权益</h3>
            <div className="space-y-2">
              {currentPlan.features.map((feature, index) => (
                <div key={index} className="flex items-start">
                  <svg className="w-4 h-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm text-gray-700">{feature}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：使用统计和套餐选择 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 使用统计 */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-6">使用情况统计</h3>
            
            {loading ? (
              <div className="text-center py-8">
                <div className="w-8 h-8 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
                  <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </div>
                <p className="text-gray-500">加载统计数据中...</p>
              </div>
            ) : stats ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* API密钥使用 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">API密钥</span>
                    <span className="text-sm text-gray-500">{stats.api_keys_count}/{stats.api_keys_limit}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.api_keys_count, stats.api_keys_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* AI对话额度 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">今日AI对话</span>
                    <span className="text-sm text-gray-500">${stats.ai_usage_today}/${stats.ai_daily_limit}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-green-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.ai_usage_today, stats.ai_daily_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* Tick级别回测 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">本月Tick回测</span>
                    <span className="text-sm text-gray-500">{stats.tick_backtest_today}/{stats.tick_backtest_limit}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.tick_backtest_today, stats.tick_backtest_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* 存储空间 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">存储空间</span>
                    <span className="text-sm text-gray-500">{stats.storage_used}MB/{stats.storage_limit}MB</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-yellow-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.storage_used, stats.storage_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* 指标数量 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">指标数量</span>
                    <span className="text-sm text-gray-500">{stats.indicators_count}/{stats.indicators_limit}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.indicators_count, stats.indicators_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* 策略数量 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">策略数量</span>
                    <span className="text-sm text-gray-500">{stats.strategies_count}/{stats.strategies_limit}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-pink-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.strategies_count, stats.strategies_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* 实盘交易数量 */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">实盘交易</span>
                    <span className="text-sm text-gray-500">{stats.live_trading_count}/{stats.live_trading_limit}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-red-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${getUsagePercentage(stats.live_trading_count, stats.live_trading_limit)}%` }}
                    ></div>
                  </div>
                </div>

                {/* K线回测（无限制的显示为无限） */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">K线回测</span>
                    <span className="text-sm text-gray-500">无限制</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className="bg-green-600 h-2 rounded-full w-full"></div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                无法加载统计数据
              </div>
            )}
          </div>

          {/* API密钥管理 */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-gray-900">API密钥管理</h3>
              <button
                onClick={handleAddAPIKey}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-medium hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-105 shadow-lg text-sm"
              >
                + 添加API密钥
              </button>
            </div>
            
            {loadingApiKeys ? (
              <div className="text-center py-8">
                <div className="w-8 h-8 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
                  <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </div>
                <p className="text-gray-500 text-sm">加载API密钥中...</p>
              </div>
            ) : apiKeys.length > 0 ? (
              <div className="space-y-4">
                {apiKeys.map((apiKey) => (
                  <div key={apiKey.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <span className="text-lg">
                          {getExchangeIcon(apiKey.exchange)}
                        </span>
                        <div>
                          <h4 className="font-medium text-gray-900">{apiKey.name}</h4>
                          <p className="text-sm text-gray-500">{apiKey.exchange.toUpperCase()}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        {getStatusIndicator(apiKey.status)}
                        <span className="text-sm text-gray-600">{getStatusText(apiKey.status)}</span>
                      </div>
                    </div>
                    
                    {/* 余额信息 */}
                    <div className="grid grid-cols-2 gap-4 mb-3">
                      <div className="bg-gray-50 rounded-lg p-3">
                        <div className="text-xs text-gray-500 mb-1">账户余额</div>
                        <div className="font-semibold text-gray-900">
                          {apiKey.balance?.total?.toLocaleString() || '0'} {apiKey.balance?.currency || 'USDT'}
                        </div>
                        <div className="text-xs text-gray-500">
                          可用: {apiKey.balance?.available?.toLocaleString() || '0'}
                        </div>
                      </div>
                      <div className="bg-green-50 rounded-lg p-3">
                        <div className="text-xs text-gray-500 mb-1">总收益率</div>
                        <div className="font-semibold text-green-600">
                          +{apiKey.performance?.total_return?.toFixed(2) || '0.00'}%
                        </div>
                        <div className="text-xs text-gray-500">
                          日收益: +{apiKey.performance?.daily_return?.toFixed(2) || '0.00'}%
                        </div>
                      </div>
                    </div>

                    {/* 性能统计 */}
                    <div className="grid grid-cols-3 gap-4 mb-3 text-xs">
                      <div className="text-center">
                        <div className="text-gray-500">胜率</div>
                        <div className="font-medium text-gray-900">
                          {apiKey.performance?.win_rate?.toFixed(1) || '0.0'}%
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-gray-500">运行天数</div>
                        <div className="font-medium text-gray-900">
                          {apiKey.performance?.created_days || '0'}天
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-gray-500">创建时间</div>
                        <div className="font-medium text-gray-900">
                          {new Date(apiKey.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                    
                    {/* 操作按钮 */}
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => navigate('/trading')}
                        className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                      >
                        查看交易
                      </button>
                      <button
                        onClick={() => handleDeleteAPIKey(apiKey.id, apiKey.name)}
                        className="px-3 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 transition-colors"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                </div>
                <h4 className="text-lg font-medium text-gray-900 mb-2">暂无API密钥</h4>
                <p className="text-gray-500 mb-4">添加您的第一个交易所API密钥以开始自动交易</p>
                <button
                  onClick={handleAddAPIKey}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  添加API密钥
                </button>
              </div>
            )}
          </div>

          {/* 套餐升级 */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-6">升级套餐</h3>
            <div className="space-y-6">
              {membershipPlans.map((plan) => (
                <div
                  key={plan.level}
                  className={`relative border-2 rounded-xl p-6 transition-all duration-200 hover:shadow-md ${
                    plan.level === user?.membership_level 
                      ? `${getPlanColorClass(plan.color, 'border')} ${getPlanColorClass(plan.color, 'bg')}` 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {plan.popular && (
                    <div className="absolute -top-2 left-6">
                      <span className="bg-purple-600 text-white text-xs font-medium px-3 py-1 rounded-full">
                        推荐
                      </span>
                    </div>
                  )}
                  
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* 套餐基本信息 */}
                    <div className="lg:col-span-1">
                      <div className="text-center lg:text-left">
                        <h4 className="text-xl font-bold text-gray-900 mb-2">{plan.name}</h4>
                        <p className="text-sm text-gray-600 mb-3">{plan.description}</p>
                        <div className="mb-4">
                          {plan.price === 0 ? (
                            <span className="text-3xl font-bold text-gray-900">免费</span>
                          ) : (
                            <>
                              <span className="text-3xl font-bold text-gray-900">${plan.price}</span>
                              <span className="text-gray-500 text-base">/{plan.period}</span>
                            </>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mb-4 italic">{plan.highlight}</p>
                        
                        {plan.level === user?.membership_level ? (
                          <button
                            disabled
                            className="w-full py-3 px-4 bg-gray-300 text-gray-500 rounded-lg font-medium cursor-not-allowed"
                          >
                            当前套餐
                          </button>
                        ) : plan.price === 0 ? (
                          <button
                            disabled
                            className="w-full py-3 px-4 bg-gray-300 text-gray-500 rounded-lg font-medium cursor-not-allowed"
                          >
                            免费套餐
                          </button>
                        ) : (
                          <button
                            onClick={() => handleUpgrade(plan.level)}
                            className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-medium hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-105 shadow-lg"
                          >
                            立即升级
                          </button>
                        )}
                      </div>
                    </div>

                    {/* 功能特性 */}
                    <div className="lg:col-span-1">
                      <h5 className="font-semibold text-gray-900 mb-3">核心功能</h5>
                      <div className="space-y-2">
                        {plan.features.map((feature, index) => (
                          <div key={index} className="flex items-start">
                            <svg className="w-4 h-4 text-blue-500 mr-2 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            <span className="text-sm text-gray-700 font-medium">{feature}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* 升级提示 */}
            <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-blue-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="text-sm text-blue-800">
                  <p className="font-medium mb-1">💡 会员计划说明</p>
                  <p className="text-blue-700">
                    • <strong>初级会员($19/月)</strong>: AI交易员/开发者模式、AI交易心得、每日$20 AI额度、1个API、1个实盘<br/>
                    • <strong>高级会员($99/月)</strong>: 初级所有功能 + 每日$100 AI额度 + 30次/月Tick回测 + 5个API + 5个实盘<br/>
                    • <strong>专业会员($199/月)</strong>: 高级所有功能 + AI图表交易模式 + 每日$200 AI额度 + 100次/月Tick回测 + 10个API + 10个实盘<br/>
                  </p>
                  <p className="text-xs text-blue-600 mt-2">
                    🎯 推荐：初级会员适合新手，高级会员性价比最高，专业会员提供完整解决方案
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 支付模态框 */}
      {showPayment && selectedPlanInfo && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-gray-900">升级到 {selectedPlanInfo.name}</h2>
              <button
                onClick={() => setShowPayment(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="mb-6">
              <div className="text-center mb-4">
                <p className="text-3xl font-bold text-gray-900">${selectedPlanInfo.price}</p>
                <p className="text-gray-500">/{selectedPlanInfo.period}</p>
              </div>
              
              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <h4 className="font-medium text-gray-900 mb-2">套餐包含：</h4>
                <ul className="space-y-1">
                  {selectedPlanInfo.features.slice(0, 3).map((feature, index) => (
                    <li key={index} className="text-sm text-gray-600 flex items-start">
                      <svg className="w-3 h-3 text-green-500 mr-2 mt-1 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {feature}
                    </li>
                  ))}
                  {selectedPlanInfo.features.length > 3 && (
                    <li className="text-sm text-gray-500">+ {selectedPlanInfo.features.length - 3} 项更多权益</li>
                  )}
                </ul>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h4 className="font-medium text-blue-900 mb-2">USDT收款地址</h4>
                <div className="bg-white border border-blue-200 rounded p-3 mb-2">
                  <code className="text-sm text-gray-800 break-all">
                    TQrZ8ZwgQx4Y9FpN8H3rK7LmVx9Rt2NcE8
                  </code>
                </div>
                <p className="text-xs text-blue-700">
                  请向此地址转账 ${selectedPlanInfo.price} USDT，转账完成后点击"确认支付"
                </p>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => setShowPayment(false)}
                className="flex-1 py-2 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handlePayment}
                className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                确认支付
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProfilePage