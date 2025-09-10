import React, { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { AdvancedBacktestChart, AdvancedMetrics, MonthlyReturn } from '../components/charts'
import { LoadingSpinner, Button } from '../components/common'
import { backtestApi } from '../services/api/backtest'
import { aiApi } from '../services/api/ai'
import { formatDateTime, formatCurrency, formatPercent } from '../utils/format'
import toast from 'react-hot-toast'

interface BacktestDetails {
  id: string
  strategy_name: string
  symbol: string
  exchange: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return: number
  status: string
  created_at: string
  metrics: AdvancedMetrics
  equity_curve: any[]
  monthly_returns: MonthlyReturn[]
  trades: any[]
}

const BacktestDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [backtest, setBacktest] = useState<BacktestDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'analysis' | 'trades'>('overview')
  
  // AI分析相关状态
  const [aiAnalyzing, setAiAnalyzing] = useState(false)
  const [aiAnalysisResult, setAiAnalysisResult] = useState<any>(null)
  const [showSendToAiConfirm, setShowSendToAiConfirm] = useState(false)

  // 加载回测详情
  useEffect(() => {
    if (!id) return

    const fetchBacktestDetails = async () => {
      try {
        setLoading(true)
        const response = await backtestApi.getBacktest(id)
        
        // 模拟数据（实际应该从API获取）
        const mockBacktest: BacktestDetails = {
          id: id,
          strategy_name: 'BTC均线策略',
          symbol: 'BTC/USDT',
          exchange: 'binance',
          start_date: '2024-01-01',
          end_date: '2024-12-31',
          initial_capital: 10000,
          final_capital: 12500,
          total_return: 25.0,
          status: 'completed',
          created_at: '2024-01-01T00:00:00Z',
          metrics: {
            total_return: 25.0,
            annual_return: 22.3,
            max_drawdown: -8.5,
            sharpe_ratio: 1.35,
            sortino_ratio: 1.62,
            calmar_ratio: 2.63,
            volatility: 16.5,
            var_95: -3.2,
            cvar_95: -4.8,
            win_rate: 62.5,
            profit_factor: 1.45,
            total_trades: 156,
            avg_win: 2.8,
            avg_loss: -1.9,
            max_consecutive_wins: 8,
            max_consecutive_losses: 4,
            avg_trade_duration: 2.5,
            max_trade_duration: 12.0
          },
          equity_curve: generateMockEquityCurve(),
          monthly_returns: generateMockMonthlyReturns(),
          trades: generateMockTrades()
        }
        
        setBacktest(mockBacktest)
      } catch (err) {
        setError('加载回测详情失败')
        console.error('Failed to fetch backtest details:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchBacktestDetails()
  }, [id])

  // 生成模拟权益曲线数据
  const generateMockEquityCurve = () => {
    const data = []
    let equity = 10000
    let rollingMax = 10000
    const startDate = new Date('2024-01-01')
    
    for (let i = 0; i < 365; i++) {
      const date = new Date(startDate)
      date.setDate(date.getDate() + i)
      
      // 模拟波动
      const dailyReturn = (Math.random() - 0.45) * 0.02 // 稍微偏向正收益
      equity *= (1 + dailyReturn)
      rollingMax = Math.max(rollingMax, equity)
      const drawdown = ((equity - rollingMax) / rollingMax) * 100
      
      data.push({
        timestamp: date.toISOString(),
        equity: Math.round(equity),
        drawdown: drawdown,
        rolling_max: Math.round(rollingMax)
      })
    }
    
    return data
  }

  // 生成模拟月度收益数据
  const generateMockMonthlyReturns = (): MonthlyReturn[] => {
    const data = []
    for (let year = 2024; year <= 2024; year++) {
      for (let month = 1; month <= 12; month++) {
        data.push({
          year,
          month,
          return: (Math.random() - 0.4) * 10 // -6% 到 +6% 的月收益
        })
      }
    }
    return data
  }

  // 生成模拟交易数据
  const generateMockTrades = () => {
    const trades = []
    const startDate = new Date('2024-01-01')
    
    for (let i = 0; i < 156; i++) {
      const date = new Date(startDate)
      date.setDate(date.getDate() + Math.floor(i * 2.3))
      
      const side = Math.random() > 0.5 ? 'buy' : 'sell'
      const price = 45000 + Math.random() * 20000
      const quantity = 0.01 + Math.random() * 0.09
      const pnl = (Math.random() - 0.4) * 500
      
      trades.push({
        timestamp: date.toISOString(),
        side,
        price: Math.round(price),
        quantity: parseFloat(quantity.toFixed(4)),
        pnl: Math.round(pnl * 100) / 100
      })
    }
    
    return trades
  }

  // 发送回测结果给AI分析
  const handleSendToAiAnalysis = async () => {
    if (!backtest || !id) return

    try {
      setAiAnalyzing(true)
      toast.loading('正在发送回测结果给AI分析...', { id: 'ai-analysis' })

      // 调用AI分析API
      const analysisResult = await aiApi.analyzeBacktestResults(parseInt(id))
      
      setAiAnalysisResult(analysisResult)
      toast.success('AI分析完成！点击查看分析报告', { 
        id: 'ai-analysis',
        duration: 3000
      })

      // 显示AI分析结果
      setShowSendToAiConfirm(false)
      setActiveTab('analysis')
      
    } catch (error) {
      console.error('AI分析失败:', error)
      toast.error('AI分析失败，请稍后重试', { id: 'ai-analysis' })
    } finally {
      setAiAnalyzing(false)
    }
  }

  // 基于AI分析结果优化策略
  const handleOptimizeStrategy = () => {
    if (!aiAnalysisResult || !backtest) return
    
    // 跳转到AI对话页面，并传递优化上下文
    const optimizationContext = {
      backtestId: id,
      strategyName: backtest.strategy_name,
      analysisResult: aiAnalysisResult,
      action: 'optimize_strategy'
    }
    
    navigate('/ai-chat', { 
      state: { 
        context: optimizationContext,
        autoStart: true 
      }
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
        <span className="ml-3 text-gray-600">加载回测详情中...</span>
      </div>
    )
  }

  if (error || !backtest) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">加载失败</h3>
          <p className="text-gray-500 mb-4">{error || '回测不存在'}</p>
          <Link
            to="/backtest"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            返回回测页面
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <Link 
              to="/backtest"
              className="text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">回测详情</h1>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
              backtest.status === 'completed' ? 'bg-green-100 text-green-800' :
              backtest.status === 'running' ? 'bg-yellow-100 text-yellow-800' :
              'bg-red-100 text-red-800'
            }`}>
              {backtest.status === 'completed' ? '已完成' : 
               backtest.status === 'running' ? '运行中' : '已失败'}
            </span>
          </div>
          <p className="text-gray-600">
            {backtest.strategy_name} - {backtest.symbol} ({backtest.exchange})
          </p>
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            className="px-4 py-2"
          >
            下载报告
          </Button>
          <Button
            variant="outline"
            className="px-4 py-2"
          >
            复制配置
          </Button>
          {backtest.status === 'completed' && (
            <Button
              variant="primary"
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700"
              onClick={() => setShowSendToAiConfirm(true)}
              disabled={aiAnalyzing}
            >
              {aiAnalyzing ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  AI分析中...
                </>
              ) : (
                <>
                  🤖 发送结果给AI分析
                </>
              )}
            </Button>
          )}
          {aiAnalysisResult && (
            <Button
              variant="primary"
              className="px-4 py-2 bg-green-600 hover:bg-green-700"
              onClick={handleOptimizeStrategy}
            >
              🚀 基于分析优化策略
            </Button>
          )}
        </div>
      </div>

      {/* 基本信息卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
          <div>
            <div className="text-sm text-gray-500 mb-1">回测周期</div>
            <div className="font-medium">
              {backtest.start_date} 至 {backtest.end_date}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">初始资金</div>
            <div className="font-medium">{formatCurrency(backtest.initial_capital)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">最终资金</div>
            <div className="font-medium">{formatCurrency(backtest.final_capital)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">总收益</div>
            <div className={`font-medium ${backtest.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPercent(backtest.total_return / 100)}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">交易次数</div>
            <div className="font-medium">{backtest.metrics.total_trades}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 mb-1">创建时间</div>
            <div className="font-medium">{formatDateTime(backtest.created_at, 'short')}</div>
          </div>
        </div>
      </div>

      {/* 选项卡 */}
      <div className="bg-white border border-gray-100 rounded-xl shadow-sm">
        <div className="flex border-b border-gray-100">
          <button 
            onClick={() => setActiveTab('overview')}
            className={`flex-1 px-6 py-4 font-medium transition-all duration-200 relative ${
              activeTab === 'overview' 
                ? 'text-blue-600 bg-blue-50' 
                : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            概览分析
            {activeTab === 'overview' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full"></div>
            )}
          </button>
          <button 
            onClick={() => setActiveTab('analysis')}
            className={`flex-1 px-6 py-4 font-medium transition-all duration-200 relative ${
              activeTab === 'analysis' 
                ? 'text-blue-600 bg-blue-50' 
                : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            深度分析
            {activeTab === 'analysis' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full"></div>
            )}
          </button>
          <button 
            onClick={() => setActiveTab('trades')}
            className={`flex-1 px-6 py-4 font-medium transition-all duration-200 relative ${
              activeTab === 'trades' 
                ? 'text-blue-600 bg-blue-50' 
                : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            交易记录
            {activeTab === 'trades' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full"></div>
            )}
          </button>
        </div>

        <div className="p-6">
          {activeTab === 'overview' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">性能概览</h3>
              <AdvancedBacktestChart
                metrics={backtest.metrics}
                equityCurve={backtest.equity_curve}
                monthlyReturns={backtest.monthly_returns}
              />
            </div>
          )}

          {activeTab === 'analysis' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">深度分析</h3>
              
              {/* 风险分析 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-50 rounded-lg p-6">
                  <h4 className="font-medium text-gray-900 mb-4">风险指标分析</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">最大回撤</span>
                      <span className="font-medium text-red-600">{backtest.metrics.max_drawdown.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">VaR (95%)</span>
                      <span className="font-medium text-red-600">{backtest.metrics.var_95.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">CVaR (95%)</span>
                      <span className="font-medium text-red-600">{backtest.metrics.cvar_95.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">波动率</span>
                      <span className="font-medium">{backtest.metrics.volatility.toFixed(2)}%</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 rounded-lg p-6">
                  <h4 className="font-medium text-gray-900 mb-4">收益质量分析</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">夏普比率</span>
                      <span className={`font-medium ${backtest.metrics.sharpe_ratio >= 1 ? 'text-green-600' : 'text-orange-600'}`}>
                        {backtest.metrics.sharpe_ratio.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">索提诺比率</span>
                      <span className="font-medium text-blue-600">{backtest.metrics.sortino_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">卡尔玛比率</span>
                      <span className="font-medium text-purple-600">{backtest.metrics.calmar_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">盈亏比</span>
                      <span className="font-medium">{backtest.metrics.profit_factor.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 策略评估 */}
              <div className="bg-blue-50 rounded-lg p-6">
                <h4 className="font-medium text-blue-900 mb-3">策略评估总结</h4>
                <div className="text-sm text-blue-800 space-y-2">
                  <p>• 该策略在回测期间表现{backtest.metrics.sharpe_ratio >= 1 ? '优秀' : '一般'}，年化收益率达到 {backtest.metrics.annual_return.toFixed(1)}%</p>
                  <p>• 风险控制{Math.abs(backtest.metrics.max_drawdown) <= 10 ? '良好' : '需要改进'}，最大回撤控制在 {Math.abs(backtest.metrics.max_drawdown).toFixed(1)}% 以内</p>
                  <p>• 交易胜率为 {backtest.metrics.win_rate.toFixed(1)}%，{backtest.metrics.win_rate >= 60 ? '表现出色' : '有提升空间'}</p>
                  <p>• 建议在实盘交易前进一步优化参数，控制单笔交易风险</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'trades' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">交易记录</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">方向</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">价格</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">数量</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">盈亏</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {backtest.trades.slice(0, 50).map((trade, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatDateTime(trade.timestamp, 'short')}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            trade.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {trade.side === 'buy' ? '买入' : '卖出'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          ${trade.price.toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {trade.quantity}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}>
                            {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {backtest.trades.length > 50 && (
                <div className="mt-4 text-center">
                  <Button variant="outline" className="px-4 py-2">
                    加载更多交易记录
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* AI分析确认对话框 */}
      {showSendToAiConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-purple-100 rounded-full">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-center text-gray-900 mb-2">
              发送回测结果给AI分析？
            </h3>
            <p className="text-center text-gray-600 mb-6">
              AI将深度分析您的回测结果，识别策略的优势和改进空间，并提供具体的优化建议。
            </p>
            <div className="flex space-x-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowSendToAiConfirm(false)}
              >
                取消
              </Button>
              <Button
                variant="primary"
                className="flex-1 bg-purple-600 hover:bg-purple-700"
                onClick={handleSendToAiAnalysis}
              >
                确认发送
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* AI分析结果展示 */}
      {aiAnalysisResult && (
        <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-xl border border-purple-200 p-6">
          <div className="flex items-center mb-4">
            <div className="flex items-center justify-center w-10 h-10 bg-purple-600 rounded-full mr-3">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-900">🤖 AI深度分析报告</h3>
          </div>
          
          <div className="bg-white rounded-lg p-6 shadow-sm">
            <div className="space-y-6">
              {/* 性能总结 */}
              <div>
                <h4 className="font-semibold text-gray-900 mb-3 flex items-center">
                  📊 性能总结
                </h4>
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-blue-800 text-sm leading-relaxed">
                    {aiAnalysisResult.performance_summary || '正在生成性能分析...'}
                  </p>
                </div>
              </div>

              {/* 优势分析 */}
              {aiAnalysisResult.strengths && aiAnalysisResult.strengths.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-3 flex items-center">
                    ✅ 策略优势
                  </h4>
                  <div className="space-y-2">
                    {aiAnalysisResult.strengths.map((strength: string, index: number) => (
                      <div key={index} className="flex items-start">
                        <div className="flex-shrink-0 w-2 h-2 bg-green-500 rounded-full mt-2 mr-3"></div>
                        <p className="text-gray-700 text-sm">{strength}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 改进建议 */}
              {aiAnalysisResult.improvement_suggestions && aiAnalysisResult.improvement_suggestions.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-3 flex items-center">
                    💡 改进建议
                  </h4>
                  <div className="space-y-3">
                    {aiAnalysisResult.improvement_suggestions.map((suggestion: string, index: number) => (
                      <div key={index} className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r-lg">
                        <p className="text-amber-800 text-sm font-medium">{suggestion}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200">
                <Button
                  variant="outline"
                  onClick={() => setAiAnalysisResult(null)}
                >
                  关闭分析
                </Button>
                <Button
                  variant="primary"
                  className="bg-green-600 hover:bg-green-700"
                  onClick={handleOptimizeStrategy}
                >
                  🚀 基于分析优化策略
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default BacktestDetailsPage