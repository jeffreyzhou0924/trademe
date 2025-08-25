import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useUserInfo } from '../store'
import { strategyApi } from '../services/api/strategy'
import toast from 'react-hot-toast'

interface Trade {
  id: number
  timestamp: string
  symbol: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  total_amount: number
  fee: number
  profit?: number
  profit_percent?: number
}

interface StrategyLiveDetail {
  id: number
  name: string
  description: string
  status: 'running' | 'stopped' | 'paused'
  symbol: string
  created_at: string
  start_time: string
  running_time: string
  
  // 收益统计
  initial_capital: number
  current_capital: number
  total_profit: number
  total_profit_percent: number
  max_drawdown: number
  max_drawdown_percent: number
  
  // 交易统计
  total_trades: number
  win_trades: number
  lose_trades: number
  win_rate: number
  avg_profit: number
  avg_loss: number
  profit_factor: number
  
  // 今日统计
  today_trades: number
  today_profit: number
  today_profit_percent: number
  
  // 最新交易记录
  recent_trades: Trade[]
}

const StrategyLiveDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  
  const [liveDetail, setLiveDetail] = useState<StrategyLiveDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'trades' | 'performance'>('overview')

  // 加载实盘详情
  const loadLiveDetail = async () => {
    if (!id || !isPremium) return
    
    try {
      setLoading(true)
      setError(null)
      
      // 这里调用后端API获取实盘详情
      // const response = await strategyApi.getLiveDetail(parseInt(id))
      
      // 暂时使用模拟数据
      const mockData: StrategyLiveDetail = {
        id: parseInt(id),
        name: 'BTC均线策略',
        description: '基于移动平均线的BTC交易策略',
        status: 'running',
        symbol: 'BTC/USDT',
        created_at: '2025-08-20T10:30:00Z',
        start_time: '2025-08-20T10:30:00Z',
        running_time: '1天6小时',
        
        initial_capital: 10000,
        current_capital: 10456.78,
        total_profit: 456.78,
        total_profit_percent: 4.57,
        max_drawdown: -234.56,
        max_drawdown_percent: -2.35,
        
        total_trades: 28,
        win_trades: 18,
        lose_trades: 10,
        win_rate: 64.29,
        avg_profit: 45.32,
        avg_loss: -23.45,
        profit_factor: 1.93,
        
        today_trades: 5,
        today_profit: 123.45,
        today_profit_percent: 1.18,
        
        recent_trades: [
          {
            id: 1,
            timestamp: '2025-08-21T13:45:00Z',
            symbol: 'BTC/USDT',
            side: 'sell',
            quantity: 0.001,
            price: 43250.00,
            total_amount: 43.25,
            fee: 0.043,
            profit: 12.34,
            profit_percent: 2.1
          },
          {
            id: 2,
            timestamp: '2025-08-21T12:30:00Z',
            symbol: 'BTC/USDT',
            side: 'buy',
            quantity: 0.001,
            price: 42800.00,
            total_amount: 42.80,
            fee: 0.043,
          },
          {
            id: 3,
            timestamp: '2025-08-21T11:15:00Z',
            symbol: 'BTC/USDT',
            side: 'sell',
            quantity: 0.0015,
            price: 42900.00,
            total_amount: 64.35,
            fee: 0.064,
            profit: -15.20,
            profit_percent: -1.8
          },
        ]
      }
      
      setLiveDetail(mockData)
    } catch (error) {
      console.error('Failed to load live detail:', error)
      setError('加载实盘详情失败')
      toast.error('加载实盘详情失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLiveDetail()
  }, [id, isPremium])

  // 控制实盘状态
  const handleControlLive = async (action: 'start' | 'pause' | 'stop') => {
    if (!liveDetail || !isPremium) return
    
    try {
      // 调用后端API控制实盘状态
      // await strategyApi.controlLive(liveDetail.id, action)
      
      // 暂时模拟状态更新
      const newStatus = action === 'start' ? 'running' : action === 'pause' ? 'paused' : 'stopped'
      setLiveDetail(prev => prev ? { ...prev, status: newStatus as any } : null)
      
      const actionText = action === 'start' ? '启动' : action === 'pause' ? '暂停' : '停止'
      toast.success(`实盘已${actionText}`)
    } catch (error) {
      toast.error(`实盘操作失败`)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount)
  }

  const formatPercent = (percent: number) => {
    const sign = percent >= 0 ? '+' : ''
    return `${sign}${percent.toFixed(2)}%`
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('zh-CN')
  }

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="w-20 h-20 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
            <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">加载实盘详情中...</h3>
          <p className="text-gray-500">正在获取实盘运行数据</p>
        </div>
      </div>
    )
  }

  if (error || !liveDetail) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="w-20 h-20 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
            <svg className="w-10 h-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">加载失败</h3>
          <p className="text-gray-500 mb-4">{error || '找不到指定的实盘'}</p>
          <button
            onClick={() => navigate('/strategies')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            返回实盘列表
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* 页面头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/strategies')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{liveDetail.name}</h1>
            <p className="text-gray-600">{liveDetail.description} · {liveDetail.symbol}</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium ${
            liveDetail.status === 'running' ? 'bg-green-100 text-green-800' :
            liveDetail.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
            'bg-red-100 text-red-800'
          }`}>
            {liveDetail.status === 'running' ? '运行中' : 
             liveDetail.status === 'paused' ? '已暂停' : '已停止'}
          </span>

          {liveDetail.status === 'stopped' ? (
            <button
              onClick={() => handleControlLive('start')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              启动
            </button>
          ) : (
            <div className="flex space-x-2">
              {liveDetail.status === 'running' && (
                <button
                  onClick={() => handleControlLive('pause')}
                  className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
                >
                  暂停
                </button>
              )}
              {liveDetail.status === 'paused' && (
                <button
                  onClick={() => handleControlLive('start')}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  继续
                </button>
              )}
              <button
                onClick={() => handleControlLive('stop')}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                停止
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 关键指标卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-6 border border-green-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-600">总收益</p>
              <p className="text-2xl font-bold text-green-900">{formatCurrency(liveDetail.total_profit)}</p>
              <p className="text-sm text-green-700">{formatPercent(liveDetail.total_profit_percent)}</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-green-200 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-6 border border-blue-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-600">当前资金</p>
              <p className="text-2xl font-bold text-blue-900">{formatCurrency(liveDetail.current_capital)}</p>
              <p className="text-sm text-blue-700">初始: {formatCurrency(liveDetail.initial_capital)}</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-blue-200 flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-purple-50 to-purple-100 rounded-xl p-6 border border-purple-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-purple-600">胜率</p>
              <p className="text-2xl font-bold text-purple-900">{formatPercent(liveDetail.win_rate)}</p>
              <p className="text-sm text-purple-700">{liveDetail.win_trades}胜 {liveDetail.lose_trades}负</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-purple-200 flex items-center justify-center">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-orange-50 to-orange-100 rounded-xl p-6 border border-orange-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-orange-600">今日收益</p>
              <p className="text-2xl font-bold text-orange-900">{formatCurrency(liveDetail.today_profit)}</p>
              <p className="text-sm text-orange-700">{formatPercent(liveDetail.today_profit_percent)}</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-orange-200 flex items-center justify-center">
              <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* 选项卡 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex">
            {[
              { id: 'overview', label: '总览', icon: '📊' },
              { id: 'trades', label: '交易记录', icon: '📋' },
              { id: 'performance', label: '性能分析', icon: '📈' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* 运行信息 */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">运行信息</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">开始时间</span>
                      <span className="font-medium">{formatTime(liveDetail.start_time)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">运行时长</span>
                      <span className="font-medium">{liveDetail.running_time}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">交易对</span>
                      <span className="font-medium">{liveDetail.symbol}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">交易统计</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">总交易次数</span>
                      <span className="font-medium">{liveDetail.total_trades}次</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">今日交易</span>
                      <span className="font-medium">{liveDetail.today_trades}次</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">盈利因子</span>
                      <span className="font-medium">{liveDetail.profit_factor.toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">风险控制</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">最大回撤</span>
                      <span className="font-medium text-red-600">{formatCurrency(liveDetail.max_drawdown)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">回撤比例</span>
                      <span className="font-medium text-red-600">{formatPercent(liveDetail.max_drawdown_percent)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">平均盈利</span>
                      <span className="font-medium text-green-600">{formatCurrency(liveDetail.avg_profit)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'trades' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">最近交易记录</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">方向</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">价格</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">数量</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">总额</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">手续费</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈亏</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {liveDetail.recent_trades.map((trade) => (
                      <tr key={trade.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatTime(trade.timestamp)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            trade.side === 'buy' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {trade.side === 'buy' ? '买入' : '卖出'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          ${trade.price.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {trade.quantity}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          ${trade.total_amount.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          ${trade.fee.toFixed(3)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {trade.profit !== undefined ? (
                            <div className={`font-medium ${trade.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {formatCurrency(trade.profit)}
                              <div className="text-xs">
                                ({formatPercent(trade.profit_percent || 0)})
                              </div>
                            </div>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'performance' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">性能分析</h3>
              <div className="text-center py-12 text-gray-500">
                <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p>性能图表功能开发中...</p>
                <p className="text-sm mt-2">将展示收益曲线、回撤分析、交易分布等图表</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategyLiveDetailPage