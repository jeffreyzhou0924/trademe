import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserInfo, useWebSocketStatus, useGlobalLoading } from '../store'
import { strategyApi } from '../services/api/strategy'
import { Strategy, StrategyWithDisplayInfo } from '../types/strategy'
import toast from 'react-hot-toast'

const StrategiesPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()
  
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'running' | 'stopped' | 'paused'>('all')
  
  // 真实策略数据
  const [strategies, setStrategies] = useState<StrategyWithDisplayInfo[]>([])
  const [loading, setLoading] = useState(false)

  // 加载策略数据
  const loadStrategies = async () => {
    if (!isPremium) return
    
    try {
      setLoading(true)
      const response = await strategyApi.getStrategies()
      
      // 处理API响应格式 
      let strategiesList: Strategy[] = []
      if (response && typeof response === 'object') {
        strategiesList = Array.isArray(response) ? response : response.strategies || []
      }
      
      // 为每个策略添加显示状态（从is_active派生）
      const processedStrategies = strategiesList.map(strategy => ({
        ...strategy,
        status: strategy.is_active ? ('running' as const) : ('stopped' as const),
        profit: '+0.00', // 暂时使用模拟数据，后续可以添加真实盈亏计算
        profitPercent: 0,
        lastUpdate: strategy.created_at,
        runningTime: strategy.is_active ? '运行中' : '已停止',
        totalTrades: 0,
        winRate: 0
      }))
      
      setStrategies(processedStrategies)
      toast.success(`加载了 ${processedStrategies.length} 个实盘`)
    } catch (error) {
      console.error('Failed to load strategies:', error)
      toast.error('加载实盘失败')
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

  const handleCreateStrategy = () => {
    if (!isPremium) {
      toast.error('创建策略需要升级到高级版本')
      return
    }
    setShowCreateModal(true)
  }

  const handleStartStrategy = (strategy: Strategy) => {
    if (!isPremium) {
      toast.error('启动策略需要高级版本')
      return
    }
    
    setStrategies(prev => prev.map(s => 
      s.id === strategy.id 
        ? { ...s, status: 'running' as const, lastUpdate: new Date().toLocaleString('zh-CN') }
        : s
    ))
    toast.success(`策略 "${strategy.name}" 已启动`)
  }

  const handleStopStrategy = (strategy: Strategy) => {
    setStrategies(prev => prev.map(s => 
      s.id === strategy.id 
        ? { ...s, status: 'stopped' as const, lastUpdate: new Date().toLocaleString('zh-CN') }
        : s
    ))
    toast.success(`策略 "${strategy.name}" 已停止`)
  }

  const handlePauseStrategy = (strategy: Strategy) => {
    setStrategies(prev => prev.map(s => 
      s.id === strategy.id 
        ? { ...s, status: 'paused' as const, lastUpdate: new Date().toLocaleString('zh-CN') }
        : s
    ))
    toast.success(`策略 "${strategy.name}" 已暂停`)
  }

  const handleDeleteStrategy = (strategy: Strategy) => {
    if (window.confirm(`确定要删除策略 "${strategy.name}" 吗？`)) {
      setStrategies(prev => prev.filter(s => s.id !== strategy.id))
      toast.success('策略已删除')
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'running': return '运行中'
      case 'stopped': return '已停止'
      case 'paused': return '已暂停'
      default: return '未知'
    }
  }

  // 新增处理函数
  const handleEditParameters = (strategy: Strategy) => {
    toast(`编辑策略参数功能开发中... (策略: ${strategy.name})`, {
      icon: 'ℹ️',
      style: {
        background: '#3b82f6',
        color: 'white',
      },
    })
  }

  const handleCreateLive = (strategy: Strategy) => {
    if (!isPremium) {
      toast.error('创建实盘需要高级版本')
      return
    }
    toast(`基于策略"${strategy.name}"创建实盘功能开发中...`, {
      icon: 'ℹ️',
      style: {
        background: '#3b82f6',
        color: 'white',
      },
    })
  }

  const handleViewLiveDetails = (strategy: Strategy) => {
    // 跳转到实盘详情页面
    navigate(`/strategy/${strategy.id}/live`)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="space-y-8">
        {/* 统计卡片 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4 sm:p-6 border border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-600">策略总数</p>
              <p className="text-xl sm:text-2xl font-bold text-blue-900">{stats.total}</p>
            </div>
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-blue-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M6 6V5a3 3 0 013-3h2a3 3 0 013 3v1h2a2 2 0 012 2v3.57A22.952 22.952 0 0110 13a22.95 22.95 0 01-8-1.43V8a2 2 0 012-2h2zm2-1a1 1 0 011-1h2a1 1 0 011 1v1H8V5zm1 5a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd" />
                <path d="M2 13.692V16a2 2 0 002 2h12a2 2 0 002-2v-2.308A24.974 24.974 0 0110 15c-2.796 0-5.487-.46-8-1.308z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-4 sm:p-6 border border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-600">运行中</p>
              <p className="text-xl sm:text-2xl font-bold text-green-900">{stats.running}</p>
            </div>
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-green-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-yellow-50 to-yellow-100 rounded-xl p-4 sm:p-6 border border-yellow-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-yellow-600">已暂停</p>
              <p className="text-xl sm:text-2xl font-bold text-yellow-900">{stats.paused}</p>
            </div>
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-yellow-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-red-50 to-red-100 rounded-xl p-4 sm:p-6 border border-red-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-red-600">已停止</p>
              <p className="text-xl sm:text-2xl font-bold text-red-900">{stats.stopped}</p>
            </div>
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-red-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center space-y-3 sm:space-y-0 sm:space-x-4">
          <div className="relative">
            <input
              type="text"
              placeholder="搜索策略名称、描述或交易对..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent w-full sm:w-80"
            />
            <svg className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent w-full sm:w-auto"
          >
            <option value="all">全部状态</option>
            <option value="running">运行中</option>
            <option value="paused">已暂停</option>
            <option value="stopped">已停止</option>
          </select>
        </div>

        <button
          onClick={handleCreateStrategy}
          className={`px-4 py-2 rounded-lg font-medium transition-colors w-full sm:w-auto ${
            isPremium
              ? 'bg-brand-500 text-white hover:bg-brand-600'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          {isPremium ? '创建策略' : '升级后创建'}
        </button>
      </div>

      {/* 策略列表 */}
      <div>
        {loading ? (
          <div className="text-center py-12">
            <div className="w-20 h-20 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
              <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">加载策略中...</h3>
            <p className="text-gray-500">正在获取您的策略列表</p>
          </div>
        ) : filteredStrategies.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-20 h-20 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">暂无策略</h3>
            <p className="text-gray-500 mb-6">创建您的第一个交易策略开始自动化交易</p>
            {isPremium ? (
              <button
                onClick={handleCreateStrategy}
                className="inline-flex items-center px-6 py-3 bg-brand-500 text-white font-medium rounded-lg hover:bg-brand-600 transition-colors"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                创建策略
              </button>
            ) : (
              <button
                onClick={() => toast.error('创建策略需要升级到高级版本')}
                className="inline-flex items-center px-6 py-3 bg-gray-300 text-gray-500 font-medium rounded-lg cursor-not-allowed"
              >
                {isPremium ? '创建策略' : '升级后创建'}
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {filteredStrategies.map((strategy) => (
              <div key={strategy.id} className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-shadow">
                <div className="p-4 sm:p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-3 mb-2 flex-wrap">
                        <h3 className="text-base sm:text-lg font-semibold text-gray-900 truncate">{strategy.name}</h3>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          strategy.status === 'running' ? 'bg-green-100 text-green-800' :
                          strategy.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {getStatusText(strategy.status)}
                        </span>
                      </div>
                      <p className="text-gray-600 text-xs sm:text-sm mb-3 line-clamp-2">{strategy.description}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-3 sm:gap-4 mb-4">
                    <div>
                      <p className="text-xs text-gray-500 mb-1">交易对</p>
                      <p className="font-medium">{strategy.parameters?.symbol || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">收益</p>
                      <p className={`font-medium ${(strategy.total_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(strategy.total_return || 0) >= 0 ? '+' : ''}{((strategy.total_return || 0) * 100).toFixed(2)}%
                      </p>
                    </div>
                    {strategy.total_trades && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">交易次数</p>
                        <p className="font-medium">{strategy.total_trades}次</p>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-3 sm:space-y-0 pt-4 border-t border-gray-100">
                    <div className="flex items-center space-x-2 flex-wrap">
                      {strategy.status === 'stopped' ? (
                        <button
                          onClick={() => handleStartStrategy(strategy)}
                          disabled={!isPremium}
                          className={`px-3 py-1.5 rounded text-xs sm:text-sm font-medium transition-colors ${
                            isPremium
                              ? 'bg-green-100 text-green-700 hover:bg-green-200'
                              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          }`}
                        >
                          启动
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => handleStopStrategy(strategy)}
                            className="px-3 py-1.5 bg-red-100 text-red-700 rounded text-xs sm:text-sm font-medium hover:bg-red-200 transition-colors"
                          >
                            停止
                          </button>
                          {strategy.status === 'running' && (
                            <button
                              onClick={() => handlePauseStrategy(strategy)}
                              className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded text-xs sm:text-sm font-medium hover:bg-yellow-200 transition-colors"
                            >
                              暂停
                            </button>
                          )}
                          {strategy.status === 'paused' && (
                            <button
                              onClick={() => handleStartStrategy(strategy)}
                              disabled={!isPremium}
                              className={`px-3 py-1.5 rounded text-xs sm:text-sm font-medium transition-colors ${
                                isPremium
                                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              }`}
                            >
                              继续
                            </button>
                          )}
                        </>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 justify-end">
                      <button
                        onClick={() => setSelectedStrategy(strategy)}
                        className="text-gray-500 hover:text-gray-700 transition-colors"
                        title="查看详情"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleDeleteStrategy(strategy)}
                        className="text-gray-500 hover:text-red-500 transition-colors"
                        title="删除策略"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
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