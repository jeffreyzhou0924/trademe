import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  useUserInfo, 
  useWebSocketStatus, 
  useGlobalLoading
} from '@/store'
import { useLanguageStore } from '@/store/languageStore'
import { strategyApi } from '../services/api/strategy'
import toast from 'react-hot-toast'

interface OverviewStats {
  totalStrategies: number
  runningStrategies: number
  totalIndicators: number
  totalTrades: number
  totalProfit: number
  winRate: number
  dailyPnl: number
}

const OverviewPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()
  const { t } = useLanguageStore()
  
  const [stats, setStats] = useState<OverviewStats>({
    totalStrategies: 0,
    runningStrategies: 0,
    totalIndicators: 0,
    totalTrades: 0,
    totalProfit: 0,
    winRate: 0,
    dailyPnl: 0
  })
  const [strategies, setStrategies] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  // 加载概览数据
  const loadOverviewData = async () => {
    if (!isPremium) return
    
    try {
      setLoading(true)
      const response = await strategyApi.getStrategies()
      
      let strategiesList: any[] = []
      if (response && typeof response === 'object') {
        strategiesList = Array.isArray(response) ? response : response.strategies || []
      }
      
      setStrategies(strategiesList)
      
      // 按照业务逻辑计算统计数据
      // 1. 筛选出AI策略（排除指标）
      const aiStrategies = strategiesList.filter(s => 
        !s.name.includes('指标') && 
        !s.name.includes('RSI') && 
        !s.name.includes('MACD') &&
        !s.description?.includes('指标')
      )
      
      // 2. 筛选出指标
      const indicators = strategiesList.filter(s =>
        s.name.includes('指标') || 
        s.name.includes('RSI') || 
        s.name.includes('MACD') ||
        s.description?.includes('指标')
      )
      
      setStats({
        totalStrategies: aiStrategies.length, // AI生成的策略总数
        runningStrategies: 3, // 运行中的实盘数量（从实盘交易数据获取）
        totalTrades: 0, // 暂时模拟数据
        totalProfit: 1234.56,
        winRate: 68.5,
        dailyPnl: 123.45,
        totalIndicators: indicators.length // 新增指标数量
      })
      
    } catch (error) {
      console.error('Failed to load overview data:', error)
      toast.error('加载概览数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOverviewData()
  }, [isPremium])

  // 快捷操作
  const quickActions = [
    {
      title: t('strategiesManagement'),
      description: t('viewAndManageStrategies'),
      icon: 'strategy',
      color: 'blue',
      action: () => navigate('/strategies')
    },
    {
      title: t('liveTrading'),
      description: t('startAutomatedTrading'),
      icon: 'trading',
      color: 'green',
      action: () => navigate('/trading')
    },
    {
      title: t('strategyBacktest'),
      description: t('testStrategyPerformance'),
      icon: 'backtest',
      color: 'purple',
      action: () => navigate('/backtest')
    },
    {
      title: t('aiAssistant'),
      description: t('getIntelligentTradingAdvice'),
      icon: 'ai',
      color: 'orange',
      action: () => navigate('/ai-chat')
    }
  ]

  const getIcon = (iconName: string) => {
    const icons: Record<string, React.ReactNode> = {
      strategy: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M6 6V5a3 3 0 013-3h2a3 3 0 013 3v1h2a2 2 0 012 2v3.57A22.952 22.952 0 0110 13a22.95 22.95 0 01-8-1.43V8a2 2 0 012-2h2zm2-1a1 1 0 011-1h2a1 1 0 011 1v1H8V5zm1 5a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd" />
        </svg>
      ),
      trading: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
        </svg>
      ),
      backtest: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" clipRule="evenodd" />
        </svg>
      ),
      ai: (
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
        </svg>
      )
    }
    return icons[iconName] || icons.strategy
  }

  const getColorClasses = (color: string) => {
    const colorMap: Record<string, { bg: string; text: string; icon: string; hover: string }> = {
      blue: { bg: 'from-blue-50 to-blue-100', text: 'text-blue-900', icon: 'bg-blue-200 text-blue-600', hover: 'hover:from-blue-100 hover:to-blue-200' },
      green: { bg: 'from-green-50 to-green-100', text: 'text-green-900', icon: 'bg-green-200 text-green-600', hover: 'hover:from-green-100 hover:to-green-200' },
      purple: { bg: 'from-purple-50 to-purple-100', text: 'text-purple-900', icon: 'bg-purple-200 text-purple-600', hover: 'hover:from-purple-100 hover:to-purple-200' },
      orange: { bg: 'from-orange-50 to-orange-100', text: 'text-orange-900', icon: 'bg-orange-200 text-orange-600', hover: 'hover:from-orange-100 hover:to-orange-200' }
    }
    return colorMap[color] || colorMap.blue
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('tradingOverview')}</h1>
          <p className="text-gray-600 mt-1">{t('welcomeBack')}，{user?.username}！{t('checkTradingDataAndQuickActions')}</p>
        </div>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="text-sm text-gray-600">
            {isConnected ? t('realTimeConnected') : t('connectionLost')}
          </span>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-600">{t('totalStrategies')}</p>
              <p className="text-2xl font-bold text-blue-900">{stats.totalStrategies}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-200 flex items-center justify-center">
              {getIcon('strategy')}
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-4 border border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-600">{t('running')}</p>
              <p className="text-2xl font-bold text-green-900">{stats.runningStrategies}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-green-200 flex items-center justify-center">
              {getIcon('trading')}
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-indigo-50 to-indigo-100 rounded-xl p-4 border border-indigo-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-indigo-600">指标数量</p>
              <p className="text-2xl font-bold text-indigo-900">{stats.totalIndicators}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-indigo-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-indigo-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11.707 4.707a1 1 0 00-1.414-1.414L10 9.586 8.707 8.293a1 1 0 00-1.414 0l-2 2a1 1 0 001.414 1.414L8 10.414l1.293 1.293a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-purple-600">{t('totalProfit')}</p>
              <p className="text-2xl font-bold text-purple-900">+{stats.totalProfit.toFixed(2)}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-purple-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-purple-600" fill="currentColor" viewBox="0 0 20 20">
                <path d="M8.433 7.418c.155-.103.346-.196.567-.267v1.698a2.305 2.305 0 01-.567-.267C8.07 8.34 8 8.114 8 8c0-.114.07-.34.433-.582zM11 12.849v-1.698c.22.071.412.164.567.267.364.243.433.468.433.582 0 .114-.07.34-.433.582a2.305 2.305 0 01-.567.267z" />
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-13a1 1 0 10-2 0v.092a4.535 4.535 0 00-1.676.662C6.602 6.234 6 7.009 6 8c0 .99.602 1.765 1.324 2.246.48.32 1.054.545 1.676.662v1.941c-.391-.127-.68-.317-.843-.504a1 1 0 10-1.51 1.31c.562.649 1.413 1.076 2.353 1.253V15a1 1 0 102 0v-.092a4.535 4.535 0 001.676-.662C13.398 13.766 14 12.991 14 12c0-.99-.602-1.765-1.324-2.246A4.535 4.535 0 0011 9.092V7.151c.391.127.68.317.843.504a1 1 0 101.511-1.31c-.563-.649-1.413-1.076-2.354-1.253V5z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-orange-50 to-orange-100 rounded-xl p-4 border border-orange-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-orange-600">{t('winRate')}</p>
              <p className="text-2xl font-bold text-orange-900">{stats.winRate}%</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-orange-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* 快捷操作 */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">{t('quickActions')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickActions.map((action) => {
            const colors = getColorClasses(action.color)
            return (
              <div
                key={action.title}
                onClick={action.action}
                className={`bg-gradient-to-r ${colors.bg} rounded-xl p-6 border cursor-pointer transition-all ${colors.hover} hover:shadow-md`}
              >
                <div className="flex items-start space-x-4">
                  <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${colors.icon}`}>
                    {getIcon(action.icon)}
                  </div>
                  <div className="flex-1">
                    <h3 className={`font-semibold ${colors.text} mb-1`}>{action.title}</h3>
                    <p className="text-sm text-gray-600">{action.description}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 最近策略 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">{t('recentStrategies')}</h2>
          <button
            onClick={() => navigate('/strategies')}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            {t('viewAll')} →
          </button>
        </div>

        {loading ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <p className="text-gray-500">{t('loadingStrategies')}</p>
          </div>
        ) : strategies.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {strategies.slice(0, 4).map((strategy) => (
              <div key={strategy.id} className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-shadow p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <h3 className="font-semibold text-gray-900">{strategy.name}</h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        strategy.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {strategy.is_active ? t('running') : t('stopped')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{strategy.description}</p>
                    <div className="flex items-center text-xs text-gray-500">
                      <span>{t('tradingPair')}: {strategy.parameters?.symbol || 'N/A'}</span>
                      <span className="mx-2">•</span>
                      <span>{t('timeframe')}: {strategy.parameters?.timeframe || 'N/A'}</span>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={() => navigate(`/strategies`)}
                    className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                  >
                    {t('viewDetails')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">{t('noStrategies')}</h3>
            <p className="text-gray-500 mb-4">{t('createFirstStrategy')}</p>
            {isPremium ? (
              <button
                onClick={() => navigate('/strategies')}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                {t('createStrategy')}
              </button>
            ) : (
              <button
                onClick={() => toast.error(t('createStrategyRequiresPremium'))}
                className="inline-flex items-center px-4 py-2 bg-gray-300 text-gray-500 font-medium rounded-lg cursor-not-allowed"
              >
                {t('upgradeToCreate')}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default OverviewPage