import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserInfo, useWebSocketStatus, useGlobalLoading } from '../store'
import { liveTradingApi, LiveStrategy, LiveStrategyStats, StrategyActionRequest } from '../services/api'
import toast from 'react-hot-toast'

const LiveStrategiesPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()
  const { isConnected } = useWebSocketStatus()
  const { isLoading } = useGlobalLoading()

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null)
  const [showParametersModal, setShowParametersModal] = useState(false)
  const [liveStrategies, setLiveStrategies] = useState<LiveStrategy[]>([])
  const [strategyStats, setStrategyStats] = useState<LiveStrategyStats | null>(null)
  const [loading, setLoading] = useState(true)

  // 加载实盘策略数据
  useEffect(() => {
    const loadLiveStrategiesData = async () => {
      try {
        setLoading(true)
        
        // 并行加载策略列表和统计数据
        const [strategiesResponse, statsResponse] = await Promise.all([
          liveTradingApi.getLiveStrategies({ per_page: 100 }),
          liveTradingApi.getLiveStrategyStats()
        ])
        
        setLiveStrategies(strategiesResponse.strategies)
        setStrategyStats(statsResponse)
        
      } catch (error) {
        console.error('加载实盘策略数据失败:', error)
        toast.error('加载实盘策略数据失败，使用模拟数据')
        
        // 加载失败时使用模拟数据
        setLiveStrategies([
          {
            id: '1',
            name: 'EMA交叉策略',
            trading_pair: 'BTC/USDT',
            exchange: 'binance',
            status: 'running',
            profit_rate: 8.2,
            signal_count: 16,
            created_at: '2024-05-10',
            win_rate: 68.4,
            total_trades: 16
          },
          {
            id: '2',
            name: 'RSI超买超卖策略',
            trading_pair: 'ETH/USDT',
            exchange: 'okx',
            status: 'paused',
            profit_rate: 5.7,
            signal_count: 12,
            created_at: '2024-05-12'
          }
        ])
        setStrategyStats({
          active_strategies: 1,
          total_return: 15.8,
          max_drawdown: -6.3,
          last_trade_time: '2小时前',
          total_trades: 28,
          win_rate: 65.2
        })
      } finally {
        setLoading(false)
      }
    }

    loadLiveStrategiesData()
  }, [])

  // 策略操作处理
  const handleStrategyAction = async (strategyId: string, action: 'pause' | 'stop' | 'start') => {
    try {
      const actionRequest: StrategyActionRequest = { action: action === 'start' ? 'start' : action }
      const response = await liveTradingApi.executeStrategyAction(strategyId, actionRequest)
      
      if (response.success) {
        toast.success(`策略${action === 'pause' ? '已暂停' : action === 'stop' ? '已停止' : '已启动'}`)
        
        // 更新本地状态
        setLiveStrategies(prev => prev.map(strategy => 
          strategy.id === strategyId 
            ? { ...strategy, status: response.new_status as any || action }
            : strategy
        ))
      } else {
        toast.error(response.message || '操作失败')
      }
    } catch (error) {
      console.error('策略操作失败:', error)
      toast.error('策略操作失败，请稍后重试')
    }
  }

  // 获取状态样式
  const getStatusBadge = (status: string) => {
    const styles = {
      running: 'bg-green-50 text-green-700 border-green-200',
      paused: 'bg-yellow-50 text-yellow-700 border-yellow-200',
      stopped: 'bg-gray-50 text-gray-700 border-gray-200'
    }
    const labels = {
      running: '运行中',
      paused: '已暂停',
      stopped: '已停止'
    }
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${styles[status as keyof typeof styles]}`}>
        {labels[status as keyof typeof labels]}
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 页面容器 - 基于原型设计 */}
      <div className="w-full max-w-7xl min-h-screen bg-white rounded-xl shadow-xl border border-gray-200 mx-auto">
        
        {/* 头部导航 */}
        <header className="py-4 px-8 flex justify-between border-b border-gray-200">
          <div className="flex items-center">
            <div className="w-7 h-7 mr-3 flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-full h-full" style={{color: '#1a3d7c'}}>
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2"/>
                <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="2"/>
              </svg>
            </div>
            <h1 className="text-xl font-bold" style={{ color: '#1a3d7c' }}>Trademe</h1>
          </div>
          
          <nav className="flex gap-2">
            <button onClick={() => navigate('/')} className="px-4 py-2 text-blue-600 font-medium hover:bg-blue-50 rounded-lg">首页</button>
            <button className="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg">策略交易</button>
            <button onClick={() => navigate('/trading')} className="px-4 py-2 text-blue-600 font-medium hover:bg-blue-50 rounded-lg">图表交易</button>
            <button onClick={() => navigate('/api-keys')} className="px-4 py-2 text-blue-600 font-medium hover:bg-blue-50 rounded-lg">API管理</button>
            <button className="px-4 py-2 text-blue-600 font-medium hover:bg-blue-50 rounded-lg">交易心得</button>
            <button onClick={() => navigate('/profile')} className="px-4 py-2 text-blue-600 font-medium hover:bg-blue-50 rounded-lg">账户中心</button>
          </nav>
          
          <div className="flex items-center">
            <div className="w-9 h-9 rounded-full bg-gray-200 overflow-hidden">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="User avatar" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-blue-100 text-blue-600 font-medium">
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="p-8">
          {/* 加载状态 */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-2 text-gray-600">加载实盘策略数据中...</span>
            </div>
          )}
          
          {!loading && (
            <>
          {/* 面包屑导航 - 基于原型 */}
          <div className="flex items-center mb-6">
            <button onClick={() => navigate('/strategies')} className="text-blue-600 hover:underline flex items-center mr-2">
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              返回策略列表
            </button>
            <span className="text-gray-500">/ 实盘管理</span>
          </div>

          <div className="mb-6">
            <h2 className="text-2xl font-bold mb-2" style={{ color: '#1a3d7c' }}>实盘策略管理</h2>
            <p className="text-gray-500">管理您当前运行中的实盘策略</p>
          </div>
          
          {/* 策略概览卡片 - 基于原型的4列布局 */}
          <div className="grid grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex items-center">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4" style={{backgroundColor: '#e9f1fe'}}>
                <svg className="w-6 h-6" style={{color: '#1a3d7c'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 mb-1">活跃策略</h3>
                <p className="text-2xl font-bold">{strategyStats?.active_strategies || 0}</p>
              </div>
            </div>
            
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex items-center">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4" style={{backgroundColor: '#e9faf3'}}>
                <svg className="w-6 h-6" style={{color: '#21ce90'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 mb-1">总收益率</h3>
                <p className="text-2xl font-bold">
                  <span className="bg-green-50 text-green-600 px-2 py-1 rounded">+{strategyStats?.total_return || 0}%</span>
                </p>
              </div>
            </div>
            
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex items-center">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4" style={{backgroundColor: '#f8f3d6'}}>
                <svg className="w-6 h-6" style={{color: '#f0b90b'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 mb-1">最大回撤</h3>
                <p className="text-2xl font-bold">
                  <span className="bg-red-50 text-red-600 px-2 py-1 rounded">{strategyStats?.max_drawdown || 0}%</span>
                </p>
              </div>
            </div>
            
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex items-center">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4" style={{backgroundColor: '#fef1f1'}}>
                <svg className="w-6 h-6" style={{color: '#f53d3d'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 mb-1">上次交易</h3>
                <p className="text-lg font-bold">{strategyStats?.last_trade_time || '暂无'}</p>
              </div>
            </div>
          </div>
          
          {/* 实盘策略表格 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold" style={{ color: '#1a3d7c' }}>实盘策略列表</h2>
              <div className="flex">
                <button className="bg-blue-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-blue-700 transition-colors flex items-center mr-2">
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  添加策略
                </button>
                <input 
                  type="text" 
                  className="border border-gray-200 bg-gray-50 rounded-lg px-4 py-2 w-64 text-sm focus:border-blue-600 focus:outline-none focus:bg-white" 
                  placeholder="搜索策略..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">策略名称</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">交易对</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">交易所</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">状态</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">收益率</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">信号数量</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">创建时间</th>
                    <th className="bg-gray-50 border-b border-gray-200 px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {liveStrategies.filter(strategy => 
                    strategy.name.toLowerCase().includes(searchQuery.toLowerCase())
                  ).map((strategy) => (
                    <tr 
                      key={strategy.id} 
                      className="cursor-pointer hover:bg-blue-50 border-b border-gray-100"
                      onClick={() => setSelectedStrategy(selectedStrategy === strategy.id ? null : strategy.id)}
                    >
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{strategy.name}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{strategy.trading_pair}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{strategy.exchange}</td>
                      <td className="px-4 py-3 text-sm">{getStatusBadge(strategy.status)}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`px-2 py-1 rounded ${
                          strategy.profit_rate > 0 ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'
                        }`}>
                          {strategy.profit_rate > 0 ? '+' : ''}{strategy.profit_rate}%
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{strategy.signal_count}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{strategy.created_at}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex space-x-2">
                          {strategy.status === 'running' ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleStrategyAction(strategy.id, 'pause')
                              }}
                              className="text-blue-600 hover:text-blue-800"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6" />
                              </svg>
                            </button>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleStrategyAction(strategy.id, 'start')
                              }}
                              className="text-green-600 hover:text-green-800"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1.586a1 1 0 01.707.293l2.414 2.414a1 1 0 00.707.293H15" />
                              </svg>
                            </button>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleStrategyAction(strategy.id, 'stop')
                            }}
                            className="text-red-600 hover:text-red-800"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10h6v4H9z" />
                            </svg>
                          </button>
                          <button className="text-gray-600 hover:text-gray-800">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 策略详情区域 - 当选中策略时显示 */}
          {selectedStrategy && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="text-xl font-bold mb-2" style={{ color: '#1a3d7c' }}>
                    {liveStrategies.find(s => s.id === selectedStrategy)?.name} 详情
                  </h2>
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-gray-600">
                      {liveStrategies.find(s => s.id === selectedStrategy)?.trading_pair}
                    </span>
                    <span className="text-sm text-gray-600">
                      {liveStrategies.find(s => s.id === selectedStrategy)?.exchange}
                    </span>
                    {getStatusBadge(liveStrategies.find(s => s.id === selectedStrategy)?.status || 'stopped')}
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button className="border border-blue-600 text-blue-600 rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-50">
                    暂停
                  </button>
                  <button className="border border-red-600 text-red-600 rounded-lg px-4 py-2 text-sm font-medium hover:bg-red-50">
                    终止
                  </button>
                </div>
              </div>
              
              {/* 策略统计卡片 */}
              <div className="grid grid-cols-3 gap-6 mb-6">
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-gray-500 mb-2 text-sm">总收益率</p>
                  <p className="text-2xl font-bold">
                    <span className="bg-green-50 text-green-600 px-2 py-1 rounded">
                      +{liveStrategies.find(s => s.id === selectedStrategy)?.profit_rate}%
                    </span>
                  </p>
                </div>
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-gray-500 mb-2 text-sm">胜率</p>
                  <p className="text-2xl font-bold">
                    {liveStrategies.find(s => s.id === selectedStrategy)?.win_rate || 0}%
                  </p>
                </div>
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="text-gray-500 mb-2 text-sm">交易次数</p>
                  <p className="text-2xl font-bold">
                    {liveStrategies.find(s => s.id === selectedStrategy)?.total_trades || 0}
                  </p>
                </div>
              </div>
              
              {/* 策略收益图表占位符 */}
              <div className="mb-6">
                <h3 className="font-bold mb-4">策略收益曲线</h3>
                <div className="h-64 bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-center">
                  <p className="text-gray-500">📈 收益曲线图表（需要ECharts集成）</p>
                </div>
              </div>
            </div>
          )}
          
          {/* 策略参数设置 */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-xl font-bold mb-6" style={{ color: '#1a3d7c' }}>策略参数设置</h2>
            
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">策略类型</label>
                  <select className="w-full border border-gray-200 bg-gray-50 rounded-lg px-4 py-3 text-sm focus:border-blue-600 focus:outline-none focus:bg-white">
                    <option>EMA交叉策略</option>
                    <option>RSI超买超卖策略</option>
                    <option>布林带突破策略</option>
                    <option>MACD背离策略</option>
                  </select>
                </div>
                
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">交易对</label>
                  <select className="w-full border border-gray-200 bg-gray-50 rounded-lg px-4 py-3 text-sm focus:border-blue-600 focus:outline-none focus:bg-white">
                    <option>BTC/USDT</option>
                    <option>ETH/USDT</option>
                    <option>SOL/USDT</option>
                    <option>DOGE/USDT</option>
                  </select>
                </div>
                
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">交易所</label>
                  <select className="w-full border border-gray-200 bg-gray-50 rounded-lg px-4 py-3 text-sm focus:border-blue-600 focus:outline-none focus:bg-white">
                    <option>币安</option>
                    <option>OKX</option>
                    <option>火币</option>
                  </select>
                </div>
              </div>
              
              <div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">EMA短周期</label>
                  <input 
                    type="number" 
                    className="w-full border border-gray-200 bg-gray-50 rounded-lg px-4 py-3 text-sm focus:border-blue-600 focus:outline-none focus:bg-white" 
                    defaultValue="10"
                  />
                </div>
                
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">EMA长周期</label>
                  <input 
                    type="number" 
                    className="w-full border border-gray-200 bg-gray-50 rounded-lg px-4 py-3 text-sm focus:border-blue-600 focus:outline-none focus:bg-white" 
                    defaultValue="50"
                  />
                </div>
                
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">止损比例</label>
                  <div className="relative">
                    <input 
                      type="number" 
                      className="w-full border border-gray-200 bg-gray-50 rounded-lg px-4 py-3 pr-8 text-sm focus:border-blue-600 focus:outline-none focus:bg-white" 
                      defaultValue="1.5"
                    />
                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">%</span>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="border-t border-gray-200 pt-6 mt-6 flex justify-end">
              <button className="border border-gray-300 rounded-lg px-4 py-2 text-gray-700 font-medium mr-3 hover:bg-gray-50">
                取消
              </button>
              <button className="bg-blue-600 text-white rounded-lg px-4 py-2 font-medium hover:bg-blue-700 transition-colors">
                更新策略参数
              </button>
            </div>
          </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default LiveStrategiesPage