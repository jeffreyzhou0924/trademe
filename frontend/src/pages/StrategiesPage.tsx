import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserInfo, useWebSocketStatus, useGlobalLoading } from '../store'
import { useLanguageStore } from '../store/languageStore'
import { strategyApi } from '../services/api/strategy'
import { liveTradingApi } from '../services/api/liveTrading'
import toast from 'react-hot-toast'

interface Strategy {
  id: number
  name: string
  description: string
  code: string
  parameters: {
    symbol?: string
    timeframe?: string
    [key: string]: any
  }
  is_active: boolean
  user_id: number
  created_at: string
  // 派生属性（用于显示）
  status?: 'running' | 'stopped' | 'paused'
  profit?: string
  profitPercent?: number
  lastUpdate?: string
  runningTime?: string
  totalTrades?: number
  winRate?: number
}

const StrategiesPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()
  const { t } = useLanguageStore()
  
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'running' | 'stopped' | 'paused'>('all')
  
  // 真实策略数据
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(false)

  // 加载策略数据
  const loadStrategies = async () => {
    if (!isPremium) return
    
    try {
      setLoading(true)
      // 使用新的实盘交易API
      const liveStrategies = await liveTradingApi.getUserLiveStrategies()
      
      // 转换为策略页面所需的数据格式
      const processedStrategies: Strategy[] = liveStrategies.map(liveStrategy => {
        const profitPercent = (liveStrategy.profit_rate / 1000) || 0 // 转换为百分比
        
        return {
          id: parseInt(liveStrategy.id),
          name: liveStrategy.name,
          description: liveStrategy.description,
          code: '', // 实盘策略不需要显示代码
          parameters: {
            symbol: liveStrategy.trading_pair,
            exchange: liveStrategy.exchange,
            ...liveStrategy.parameters
          },
          is_active: liveStrategy.status !== 'stopped',
          user_id: 9, // 当前用户ID
          created_at: liveStrategy.created_at,
          status: liveStrategy.status,
          profit: profitPercent >= 0 ? `+${profitPercent.toFixed(2)}` : profitPercent.toFixed(2),
          profitPercent,
          lastUpdate: liveStrategy.created_at,
          runningTime: liveStrategy.status === 'running' ? '运行中' : 
                      liveStrategy.status === 'paused' ? '已暂停' : '已停止',
          totalTrades: liveStrategy.total_trades || 0,
          winRate: liveStrategy.win_rate || 0
        }
      })
      
      setStrategies(processedStrategies)
      toast.success(`加载了 ${processedStrategies.length} 个实盘策略`)
    } catch (error) {
      console.error('Failed to load live strategies:', error)
      toast.error('加载实盘策略失败')
    } finally {
      setLoading(false)
    }
  }

  // 页面加载时获取数据
  useEffect(() => {
    loadStrategies()
  }, [isPremium])

  // 计算统计信息
  const stats = {
    total: strategies.length,
    running: strategies.filter(s => s.status === 'running').length,
    stopped: strategies.filter(s => s.status === 'stopped').length,
    paused: strategies.filter(s => s.status === 'paused').length,
  }

  // 过滤策略
  const filteredStrategies = strategies.filter(strategy => {
    const symbol = strategy.parameters?.symbol || ''
    const matchesSearch = strategy.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         strategy.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         symbol.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === 'all' || strategy.status === statusFilter
    return matchesSearch && matchesStatus
  })


  const handleStartStrategy = (strategy: Strategy) => {
    if (!isPremium) {
      toast.error(t('startStrategyRequiresPremium'))
      return
    }
    
    setStrategies(prev => prev.map(s => 
      s.id === strategy.id 
        ? { ...s, status: 'running' as const, lastUpdate: new Date().toLocaleString('zh-CN') }
        : s
    ))
    toast.success(`${strategy.name} ${t('strategyStarted')}`)
  }

  const handleStopStrategy = (strategy: Strategy) => {
    setStrategies(prev => prev.map(s => 
      s.id === strategy.id 
        ? { ...s, status: 'stopped' as const, lastUpdate: new Date().toLocaleString('zh-CN') }
        : s
    ))
    toast.success(`${strategy.name} ${t('strategyStopped')}`)
  }

  const handlePauseStrategy = (strategy: Strategy) => {
    setStrategies(prev => prev.map(s => 
      s.id === strategy.id 
        ? { ...s, status: 'paused' as const, lastUpdate: new Date().toLocaleString('zh-CN') }
        : s
    ))
    toast.success(`${strategy.name} ${t('strategyPaused')}`)
  }

  const handleDeleteStrategy = async (strategy: Strategy) => {
    // 只允许删除已停止的实盘
    if (strategy.status !== 'stopped') {
      toast.error('只能删除已停止的实盘策略')
      return
    }

    if (window.confirm(`确认删除实盘策略 "${strategy.name}"?\n此操作不可撤销。`)) {
      try {
        await liveTradingApi.deleteLiveStrategy(strategy.id.toString())
        setStrategies(prev => prev.filter(s => s.id !== strategy.id))
        toast.success(`实盘策略 "${strategy.name}" 删除成功`)
      } catch (error) {
        console.error('Delete strategy failed:', error)
        toast.error('删除实盘策略失败')
      }
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'running': return t('runningLive')
      case 'stopped': return t('stoppedLive')
      case 'paused': return t('pausedLive')
      default: return 'Unknown'
    }
  }


  const handleViewLiveDetails = (strategy: Strategy) => {
    // 跳转到实盘详情页面
    navigate(`/strategy/${strategy.id}/live`)
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('liveTrading')}</h1>
        <p className="text-gray-600">{t('monitorRunningStrategies')}</p>
      </div>

      {/* 实盘运行区域 */}
      <div className="space-y-6">

        {/* 实盘统计卡片 */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div 
            className={`bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200 cursor-pointer transition-all hover:shadow-md ${
              statusFilter === 'all' ? 'ring-2 ring-blue-500 shadow-md' : ''
            }`}
            onClick={() => setStatusFilter('all')}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-600">{t('totalLiveStrategies')}</p>
                <p className="text-2xl font-bold text-blue-900">{stats.total}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-200 flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            {statusFilter === 'all' && (
              <div className="mt-2">
                <p className="text-xs text-blue-600 font-medium">{t('selected')}</p>
              </div>
            )}
          </div>

          <div 
            className={`bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-4 border border-green-200 cursor-pointer transition-all hover:shadow-md ${
              statusFilter === 'running' ? 'ring-2 ring-green-500 shadow-md' : ''
            }`}
            onClick={() => setStatusFilter('running')}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">{t('runningLive')}</p>
                <p className="text-2xl font-bold text-green-900">{stats.running}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-green-200 flex items-center justify-center">
                <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            {statusFilter === 'running' && (
              <div className="mt-2">
                <p className="text-xs text-green-600 font-medium">{t('selected')}</p>
              </div>
            )}
          </div>

          <div 
            className={`bg-gradient-to-r from-yellow-50 to-yellow-100 rounded-xl p-4 border border-yellow-200 cursor-pointer transition-all hover:shadow-md ${
              statusFilter === 'paused' ? 'ring-2 ring-yellow-500 shadow-md' : ''
            }`}
            onClick={() => setStatusFilter('paused')}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-yellow-600">{t('pausedLive')}</p>
                <p className="text-2xl font-bold text-yellow-900">{stats.paused}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-yellow-200 flex items-center justify-center">
                <svg className="w-5 h-5 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            {statusFilter === 'paused' && (
              <div className="mt-2">
                <p className="text-xs text-yellow-600 font-medium">{t('selected')}</p>
              </div>
            )}
          </div>

          <div 
            className={`bg-gradient-to-r from-red-50 to-red-100 rounded-xl p-4 border border-red-200 cursor-pointer transition-all hover:shadow-md ${
              statusFilter === 'stopped' ? 'ring-2 ring-red-500 shadow-md' : ''
            }`}
            onClick={() => setStatusFilter('stopped')}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-600">{t('stoppedLive')}</p>
                <p className="text-2xl font-bold text-red-900">{stats.stopped}</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-red-200 flex items-center justify-center">
                <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            {statusFilter === 'stopped' && (
              <div className="mt-2">
                <p className="text-xs text-red-600 font-medium">{t('selected')}</p>
              </div>
            )}
          </div>
        </div>

        {/* 实盘搜索和筛选 */}
        <div className="flex items-center space-x-4">
          <div className="relative flex-1">
            <input
              type="text"
              placeholder={t('searchStrategies')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
            <svg className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          >
            <option value="all">{t('allStatus')}</option>
            <option value="running">{t('runningLive')}</option>
            <option value="paused">{t('pausedLive')}</option>
            <option value="stopped">{t('stoppedLive')}</option>
          </select>
        </div>

        {/* 当前筛选状态显示 */}
        {statusFilter !== 'all' && (
          <div className="mb-4">
            <div className="inline-flex items-center px-3 py-2 rounded-lg bg-gray-100 text-gray-700">
              <span className="text-sm">{t('currentFilter')}: </span>
              <span className={`ml-2 px-2 py-1 rounded text-xs font-medium ${
                statusFilter === 'running' ? 'bg-green-100 text-green-800' :
                statusFilter === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {statusFilter === 'running' ? t('runningLive') : 
                 statusFilter === 'paused' ? t('pausedLive') : t('stoppedLive')}
              </span>
              <button
                onClick={() => setStatusFilter('all')}
                className="ml-2 text-gray-500 hover:text-gray-700"
                title={t('clearFilter')}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* 实盘列表 */}
        <div>
          {loading ? (
            <div className="text-center py-12">
              <div className="w-20 h-20 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
                <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">{t('loadingStrategies')}</h3>
              <p className="text-gray-500">{t('monitorRunningStrategies')}</p>
            </div>
          ) : filteredStrategies.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-20 h-20 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">{t('noStrategiesMessage')}</h3>
              <p className="text-gray-500 mb-6">{t('createFirstStrategyMessage')}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {filteredStrategies.map((strategy) => (
                <div 
                  key={strategy.id} 
                  className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => handleViewLiveDetails(strategy)}
                >
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h3 className="text-lg font-semibold text-gray-900">{strategy.name}</h3>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            strategy.status === 'running' ? 'bg-green-100 text-green-800' :
                            strategy.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {getStatusText(strategy.status)}
                          </span>
                        </div>
                        <p className="text-gray-600 text-sm mb-3">{strategy.description}</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-xs text-gray-500 mb-1">{t('tradingPair')}</p>
                        <p className="font-medium">{strategy.parameters?.symbol || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 mb-1">{t('profitLoss')}</p>
                        <p className={`font-medium ${strategy.profitPercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {strategy.profit} ({strategy.profitPercent >= 0 ? '+' : ''}{strategy.profitPercent}%)
                        </p>
                      </div>
                      {strategy.runningTime && (
                        <div>
                          <p className="text-xs text-gray-500 mb-1">{t('runningTime')}</p>
                          <p className="font-medium">{strategy.runningTime}</p>
                        </div>
                      )}
                      {strategy.totalTrades !== undefined && (
                        <div>
                          <p className="text-xs text-gray-500 mb-1">{t('totalTrades')}</p>
                          <p className="font-medium">{strategy.totalTrades}次</p>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                      <div className="flex items-center space-x-2">
                        {strategy.status === 'stopped' ? (
                          <>
                            <button
                              onClick={(e) => {e.stopPropagation(); handleStartStrategy(strategy)}}
                              disabled={!isPremium}
                              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                                isPremium
                                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              }`}
                            >
                              {t('start')}
                            </button>
                            <button
                              onClick={(e) => {e.stopPropagation(); handleDeleteStrategy(strategy)}}
                              className="px-3 py-1.5 bg-red-100 text-red-700 rounded text-sm font-medium hover:bg-red-200 transition-colors"
                              title="删除实盘策略"
                            >
                              删除
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={(e) => {e.stopPropagation(); handleStopStrategy(strategy)}}
                              className="px-3 py-1.5 bg-red-100 text-red-700 rounded text-sm font-medium hover:bg-red-200 transition-colors"
                            >
                              {t('stop')}
                            </button>
                            {strategy.status === 'running' && (
                              <button
                                onClick={(e) => {e.stopPropagation(); handlePauseStrategy(strategy)}}
                                className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded text-sm font-medium hover:bg-yellow-200 transition-colors"
                              >
                                {t('pause')}
                              </button>
                            )}
                            {strategy.status === 'paused' && (
                              <button
                                onClick={(e) => {e.stopPropagation(); handleStartStrategy(strategy)}}
                                disabled={!isPremium}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                                  isPremium
                                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                }`}
                              >
                                {t('start')}
                              </button>
                            )}
                          </>
                        )}
                      </div>
                      <div className="text-xs text-gray-500">
                        {t('viewDetails')}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategiesPage