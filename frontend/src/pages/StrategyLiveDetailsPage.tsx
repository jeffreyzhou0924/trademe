import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useUserInfo } from '../store'
import { strategyApi } from '../services/api/strategy'
import type { TradeRecord, Strategy as ApiStrategy } from '@/types/strategy'
import toast from 'react-hot-toast'

// Using TradeRecord from types/strategy.ts directly

interface LiveStats {
  total_trades: number
  buy_volume: number
  sell_volume: number
  total_fees: number
  profit_loss: number
  profit_percentage: number
  avg_price: number
  first_trade: string | null
  last_trade: string | null
}

interface Performance {
  total_return: number
  win_rate: number
  max_drawdown: number
  sharpe_ratio: number
}

// Using ApiStrategy from types/strategy.ts

interface LiveDetails {
  strategy: ApiStrategy
  live_stats: LiveStats
  trades: TradeRecord[]
  performance: Performance
  status: string
}

const StrategyLiveDetailsPage: React.FC = () => {
  const { strategyId } = useParams<{ strategyId: string }>()
  const navigate = useNavigate()
  const { user, isPremium } = useUserInfo()

  const [liveDetails, setLiveDetails] = useState<LiveDetails | null>(null)
  const [allTrades, setAllTrades] = useState<TradeRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [tradesLoading, setTradesLoading] = useState(false)
  const [currentPage, setCurrentPage] = useState(0)
  const [hasMoreTrades, setHasMoreTrades] = useState(true)

  const pageSize = 20

  // 加载实盘详情
  const loadLiveDetails = async () => {
    if (!strategyId) return

    try {
      setLoading(true)
      const response = await strategyApi.getStrategyLiveDetails(parseInt(strategyId))
      setLiveDetails(response)
    } catch (error) {
      console.error('Failed to load live details:', error)
      toast.error('加载实盘详情失败')
    } finally {
      setLoading(false)
    }
  }

  // 加载交易记录
  const loadTrades = async (page: number = 0, append: boolean = false) => {
    if (!strategyId) return

    try {
      setTradesLoading(true)
      const response = await strategyApi.getStrategyTrades(
        strategyId,
        {
          page: page + 1, // API expects 1-based pagination
          per_page: pageSize
        }
      )
      
      if (append) {
        setAllTrades(prev => [...prev, ...response.items])
      } else {
        setAllTrades(response.items)
      }
      
      // Handle pagination response structure
      const hasMore = response.items ? response.items.length === pageSize : false
      setHasMoreTrades(hasMore)
    } catch (error) {
      console.error('Failed to load trades:', error)
      toast.error('加载交易记录失败')
    } finally {
      setTradesLoading(false)
    }
  }

  useEffect(() => {
    if (!isPremium) {
      toast.error('查看实盘详情需要高级版本')
      navigate('/strategies')
      return
    }

    loadLiveDetails()
    loadTrades()
  }, [strategyId, isPremium, navigate])

  // 加载更多交易记录
  const handleLoadMoreTrades = () => {
    const nextPage = currentPage + 1
    setCurrentPage(nextPage)
    loadTrades(nextPage, true)
  }

  // 格式化数字
  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toFixed(decimals)
  }

  // 格式化时间
  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN')
  }

  // 获取交易类型样式
  const getTradeSideStyle = (side: string) => {
    return side === 'BUY' 
      ? 'bg-green-100 text-green-800'
      : 'bg-red-100 text-red-800'
  }

  // 获取收益样式
  const getProfitStyle = (profit: number) => {
    return profit >= 0 
      ? 'text-green-600'
      : 'text-red-600'
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
          <p className="text-gray-500">正在获取策略运行数据</p>
        </div>
      </div>
    )
  }

  if (!liveDetails) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <h3 className="text-lg font-medium text-gray-900 mb-2">实盘详情不存在</h3>
          <button
            onClick={() => navigate('/strategies')}
            className="text-blue-600 hover:text-blue-800"
          >
            返回策略列表
          </button>
        </div>
      </div>
    )
  }

  const { strategy, live_stats, performance, status } = liveDetails

  return (
    <div className="container mx-auto px-4 py-8">
      {/* 页面标题和导航 */}
      <div className="mb-8">
        <div className="flex items-center space-x-4 mb-4">
          <button
            onClick={() => navigate('/strategies')}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{strategy.name}</h1>
            <p className="text-gray-600">实盘运行详情</p>
          </div>
          <div className="flex-1"></div>
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
            status === 'running' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {status === 'running' ? '运行中' : '已停止'}
          </span>
        </div>
        <p className="text-gray-600">{strategy.description}</p>
      </div>

      {/* 统计数据卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">总收益</p>
              <p className={`text-2xl font-bold ${getProfitStyle(live_stats.profit_loss)}`}>
                {formatNumber(live_stats.profit_loss, 4)}
              </p>
              <p className={`text-sm ${getProfitStyle(live_stats.profit_percentage)}`}>
                {live_stats.profit_percentage >= 0 ? '+' : ''}{formatNumber(live_stats.profit_percentage)}%
              </p>
            </div>
            <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">交易次数</p>
              <p className="text-2xl font-bold text-gray-900">{live_stats.total_trades}</p>
              <p className="text-sm text-gray-500">总成交量</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">买入量</p>
              <p className="text-2xl font-bold text-gray-900">{formatNumber(live_stats.buy_volume, 4)}</p>
              <p className="text-sm text-gray-500">总买入金额</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-yellow-100 flex items-center justify-center">
              <svg className="w-6 h-6 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
                <path d="M8.433 7.418c.155-.103.346-.196.567-.267v1.698a2.305 2.305 0 01-.567-.267C8.07 8.34 8 8.114 8 8c0-.114.07-.34.433-.582zM11 12.849v-1.698c.22.071.412.164.567.267.364.243.433.468.433.582 0 .114-.07.34-.433.582a2.305 2.305 0 01-.567.267z" />
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-13a1 1 0 10-2 0v.092a4.535 4.535 0 00-1.676.662C6.602 6.234 6 7.009 6 8c0 .99.602 1.765 1.324 2.246.48.32 1.054.545 1.676.662v1.941c-.391-.127-.68-.317-.843-.504a1 1 0 10-1.51 1.31c.562.649 1.413 1.076 2.353 1.253V15a1 1 0 102 0v-.092a4.535 4.535 0 001.676-.662C13.398 13.766 14 12.991 14 12c0-.99-.602-1.765-1.324-2.246A4.535 4.535 0 0011 9.092V7.151c.391.127.68.317.843.504a1 1 0 101.511-1.31c-.563-.649-1.413-1.076-2.354-1.253V5z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">手续费</p>
              <p className="text-2xl font-bold text-red-600">{formatNumber(live_stats.total_fees, 4)}</p>
              <p className="text-sm text-gray-500">总费用</p>
            </div>
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
              <svg className="w-6 h-6 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v4a2 2 0 002 2V6h10a2 2 0 00-2-2H4zm2 6a2 2 0 012-2h8a2 2 0 012 2v4a2 2 0 01-2 2H8a2 2 0 01-2-2v-4zm6 4a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* 性能指标 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">性能指标</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div>
            <p className="text-sm text-gray-600 mb-1">总回报率</p>
            <p className={`text-xl font-bold ${getProfitStyle(performance.total_return)}`}>
              {performance.total_return >= 0 ? '+' : ''}{formatNumber(performance.total_return)}%
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600 mb-1">胜率</p>
            <p className="text-xl font-bold text-gray-900">{formatNumber(performance.win_rate)}%</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 mb-1">最大回撤</p>
            <p className="text-xl font-bold text-red-600">{formatNumber(performance.max_drawdown)}%</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 mb-1">夏普比率</p>
            <p className="text-xl font-bold text-gray-900">{formatNumber(performance.sharpe_ratio, 3)}</p>
          </div>
        </div>
      </div>

      {/* 交易记录 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">交易记录</h3>
          <p className="text-sm text-gray-600">最近的实盘交易明细</p>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  时间
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  交易对
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  方向
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  数量
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  价格
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  总额
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  手续费
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  订单ID
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {allTrades.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-gray-500">
                    暂无交易记录
                  </td>
                </tr>
              ) : (
                allTrades.map((trade) => (
                  <tr key={trade.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatTime(trade.timestamp)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {trade.symbol}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getTradeSideStyle(trade.side)}`}>
                        {trade.side}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatNumber(trade.quantity, 6)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatNumber(trade.price, 4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatNumber(trade.total_amount, 4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600">
                      {formatNumber(trade.fee, 6)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {trade.order_id || 'N/A'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 加载更多按钮 */}
        {hasMoreTrades && allTrades.length > 0 && (
          <div className="p-6 border-t border-gray-200 text-center">
            <button
              onClick={handleLoadMoreTrades}
              disabled={tradesLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed"
            >
              {tradesLoading ? '加载中...' : '加载更多'}
            </button>
          </div>
        )}
      </div>

      {/* 策略信息 */}
      {live_stats.first_trade && (
        <div className="mt-8 bg-gray-50 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">运行信息</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-600">首次交易</p>
              <p className="font-medium">{formatTime(live_stats.first_trade)}</p>
            </div>
            {live_stats.last_trade && (
              <div>
                <p className="text-sm text-gray-600">最新交易</p>
                <p className="font-medium">{formatTime(live_stats.last_trade)}</p>
              </div>
            )}
            <div>
              <p className="text-sm text-gray-600">平均成交价</p>
              <p className="font-medium">{formatNumber(live_stats.avg_price, 4)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default StrategyLiveDetailsPage