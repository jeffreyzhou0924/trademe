import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useLanguageStore } from '../store/languageStore'
import { useBacktestStore, useBacktestList, useBacktestCreation, useBacktestComparison } from '../store/backtestStore'
import { BacktestResultChart } from '../components/charts'
import { LoadingSpinner, Button } from '../components/common'
import { formatDateTime, formatCurrency, formatPercent } from '../utils/format'
import { strategyApi } from '../services/api/strategy'

const BacktestPage: React.FC = () => {
  const { user } = useAuthStore()
  const { t } = useLanguageStore()
  const [activeTab, setActiveTab] = useState<'create' | 'history'>('create')
  
  // 使用状态管理hooks
  const { backtests, loading, error, fetchBacktests, deleteBacktest, downloadReport } = useBacktestList()
  const { configForm, isCreatingBacktest, createBacktest, updateBacktestForm, resetBacktestForm } = useBacktestCreation()
  const { selectedForComparison, toggleComparisonSelection, compareBacktests, clearComparison } = useBacktestComparison()
  
  // 策略列表状态
  const [strategies, setStrategies] = useState<any[]>([])
  const [strategiesLoading, setStrategiesLoading] = useState(false)
  
  // 确保backtests始终是数组
  const backtestsArray = Array.isArray(backtests) ? backtests : []
  
  // 获取策略列表
  const fetchStrategies = async () => {
    try {
      setStrategiesLoading(true)
      const response = await strategyApi.getStrategies({ active_only: true })
      if (response && response.strategies) {
        setStrategies(response.strategies)
      }
    } catch (error) {
      console.error(t('getStrategiesError'), error)
    } finally {
      setStrategiesLoading(false)
    }
  }

  // 加载数据
  useEffect(() => {
    fetchBacktests()
    fetchStrategies()
  }, [])
  
  // 处理回测创建
  const handleCreateBacktest = async () => {
    if (!configForm.strategy_id) {
      alert(t('strategyRequired'))
      return
    }
    
    const result = await createBacktest(configForm)
    if (result) {
      setActiveTab('history') // 创建成功后切换到历史记录
    }
  }
  
  // 处理删除回测
  const handleDeleteBacktest = async (id: string) => {
    if (confirm(t('confirmDeleteBacktest'))) {
      await deleteBacktest(id)
    }
  }
  
  // 状态样式映射
  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'running':
        return 'bg-yellow-100 text-yellow-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }
  
  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed': return t('completed')
      case 'running': return t('running')
      case 'failed': return t('failed')
      default: return t('unknown')
    }
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('strategyBacktest')}</h1>
          <p className="text-gray-600 mt-1">{t('verifyTradingStrategy')}</p>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-all duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">{t('totalBacktests')}</p>
              <p className="text-2xl font-bold text-gray-900">{backtestsArray.length}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-all duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">{t('completedSuccessfully')}</p>
              <p className="text-2xl font-bold text-green-600">{backtestsArray.filter(b => b.status === 'completed').length}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-all duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">{t('running')}</p>
              <p className="text-2xl font-bold text-yellow-600">{backtestsArray.filter(b => b.status === 'running').length}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-yellow-50 flex items-center justify-center">
              <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-all duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">{t('executionFailed')}</p>
              <p className="text-2xl font-bold text-red-600">{backtestsArray.filter(b => b.status === 'failed').length}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-red-50 flex items-center justify-center">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* 选项卡 */}
      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm">
        <div className="flex border-b border-gray-100">
          <button 
            onClick={() => setActiveTab('create')}
            className={`flex-1 px-6 py-4 font-medium transition-all duration-200 relative ${
              activeTab === 'create' 
                ? 'text-blue-600 bg-blue-50' 
                : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            {t('createBacktest')}
            {activeTab === 'create' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full"></div>
            )}
          </button>
          <button 
            onClick={() => setActiveTab('history')}
            className={`flex-1 px-6 py-4 font-medium transition-all duration-200 relative ${
              activeTab === 'history' 
                ? 'text-blue-600 bg-blue-50' 
                : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            {t('backtestHistory')}
            {activeTab === 'history' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full"></div>
            )}
          </button>
        </div>

        <div className="p-6">
          {activeTab === 'create' ? (
            // 创建回测
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-gray-900">{t('backtestConfig')}</h2>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {t('selectStrategy')} *
                    </label>
                    <select 
                      value={configForm.strategy_id}
                      onChange={(e) => updateBacktestForm('strategy_id', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                      required
                      disabled={strategiesLoading}
                    >
                      <option value="">
                        {strategiesLoading ? '加载策略中...' : '请选择策略'}
                      </option>
                      {strategies.map((strategy) => (
                        <option key={strategy.id} value={strategy.id}>
                          {strategy.name} - {strategy.parameters?.symbol || 'N/A'}
                        </option>
                      ))}
                    </select>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        开始日期 *
                      </label>
                      <input
                        type="date"
                        value={configForm.start_date}
                        onChange={(e) => updateBacktestForm('start_date', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        结束日期 *
                      </label>
                      <input
                        type="date"
                        value={configForm.end_date}
                        onChange={(e) => updateBacktestForm('end_date', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        required
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        交易对 *
                      </label>
                      <select
                        value={configForm.symbol}
                        onChange={(e) => updateBacktestForm('symbol', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        required
                      >
                        <option value="">请选择交易对</option>
                        <option value="BTC/USDT">BTC/USDT</option>
                        <option value="ETH/USDT">ETH/USDT</option>
                        <option value="BNB/USDT">BNB/USDT</option>
                        <option value="ADA/USDT">ADA/USDT</option>
                        <option value="SOL/USDT">SOL/USDT</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        交易所 *
                      </label>
                      <select
                        value={configForm.exchange}
                        onChange={(e) => updateBacktestForm('exchange', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        required
                      >
                        <option value="">请选择交易所</option>
                        <option value="binance">Binance</option>
                        <option value="okx">OKX</option>
                        <option value="huobi">Huobi</option>
                        <option value="kraken">Kraken</option>
                      </select>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        时间周期 *
                      </label>
                      <select
                        value={configForm.timeframe}
                        onChange={(e) => updateBacktestForm('timeframe', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        required
                      >
                        <option value="">请选择时间周期</option>
                        <option value="1m">1分钟</option>
                        <option value="5m">5分钟</option>
                        <option value="15m">15分钟</option>
                        <option value="1h">1小时</option>
                        <option value="4h">4小时</option>
                        <option value="1d">1天</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        手续费率 *
                      </label>
                      <input
                        type="number"
                        value={configForm.commission_rate}
                        onChange={(e) => updateBacktestForm('commission_rate', parseFloat(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        placeholder="0.001"
                        min="0"
                        max="0.01"
                        step="0.0001"
                        required
                      />
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      初始资金 *
                    </label>
                    <input
                      type="number"
                      value={configForm.initial_capital}
                      onChange={(e) => updateBacktestForm('initial_capital', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                      placeholder="10000"
                      min="1000"
                      step="1000"
                      required
                    />
                  </div>

                  <button
                    onClick={handleCreateBacktest}
                    disabled={isCreatingBacktest}
                    className={`w-full py-3 px-4 rounded-xl font-medium transition-all duration-200 ${
                      isCreatingBacktest
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-lg transform hover:scale-[1.02]'
                    }`}
                  >
                    {isCreatingBacktest ? '创建中...' : '开始回测'}
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-gray-900">回测说明</h2>
                <div className="bg-gray-50 rounded-xl p-6 space-y-4">
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-blue-600 text-sm font-bold">1</span>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">选择策略</h3>
                      <p className="text-sm text-gray-600">选择您要回测的交易策略</p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-blue-600 text-sm font-bold">2</span>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">设定回测周期</h3>
                      <p className="text-sm text-gray-600">选择回测的开始和结束日期</p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-blue-600 text-sm font-bold">3</span>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">设定初始资金</h3>
                      <p className="text-sm text-gray-600">设定回测使用的初始资金金额</p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-blue-600 text-sm font-bold">4</span>
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">开始回测</h3>
                      <p className="text-sm text-gray-600">点击开始回测，查看策略历史表现</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            // 回测历史
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">回测历史</h2>
                {selectedForComparison.length >= 2 && (
                  <div className="flex space-x-2">
                    <button 
                      onClick={compareBacktests}
                      className="px-4 py-2 bg-blue-600 text-white text-sm rounded-xl hover:bg-blue-700 hover:shadow-lg transform hover:scale-[1.02] transition-all duration-200"
                    >
                      比较回测 ({selectedForComparison.length})
                    </button>
                    <button 
                      onClick={clearComparison}
                      className="px-4 py-2 bg-gray-500 text-white text-sm rounded-xl hover:bg-gray-600 hover:shadow-lg transform hover:scale-[1.02] transition-all duration-200"
                    >
                      清除选择
                    </button>
                  </div>
                )}
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <LoadingSpinner />
                  <span className="ml-2 text-gray-600">加载回测数据...</span>
                </div>
              ) : backtestsArray.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                    <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">暂无回测记录</h3>
                  <p className="text-gray-500 mb-4">开始您的第一次策略回测</p>
                  <button
                    onClick={() => setActiveTab('create')}
                    className="inline-flex items-center px-6 py-3 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 hover:shadow-lg transform hover:scale-[1.02] transition-all duration-200"
                  >
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    创建回测
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-6">
                  {backtestsArray.map((backtest) => (
                    <div key={backtest.id} className="bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <input
                              type="checkbox"
                              checked={selectedForComparison.includes(backtest.id)}
                              onChange={() => toggleComparisonSelection(backtest.id)}
                              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                            />
                            <h3 className="font-semibold text-gray-900">{backtest.strategy_name || '未知策略'}</h3>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusStyle(backtest.status)}`}>
                              {getStatusText(backtest.status)}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <span className="text-gray-500">回测周期:</span>
                              <p className="font-medium">{backtest.start_date} - {backtest.end_date}</p>
                            </div>
                            <div>
                              <span className="text-gray-500">初始资金:</span>
                              <p className="font-medium">{formatCurrency(backtest.initial_capital)}</p>
                            </div>
                            <div>
                              <span className="text-gray-500">总收益:</span>
                              <p className={`font-medium ${backtest.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {formatPercent(backtest.total_return)}
                              </p>
                            </div>
                            <div>
                              <span className="text-gray-500">创建时间:</span>
                              <p className="font-medium">{formatDateTime(backtest.created_at, 'short')}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                        <div className="flex items-center space-x-2">
                          {backtest.status === 'completed' && (
                            <>
                              <button
                                onClick={() => downloadReport(backtest.id)}
                                className="px-4 py-2 text-sm text-blue-600 border border-blue-200 rounded-xl hover:bg-blue-50 hover:border-blue-300 transition-all duration-200"
                              >
                                下载报告
                              </button>
                              <Link
                                to={`/backtest/${backtest.id}/details`}
                                className="px-4 py-2 text-sm text-green-600 border border-green-200 rounded-xl hover:bg-green-50 hover:border-green-300 transition-all duration-200"
                              >
                                查看详情
                              </Link>
                            </>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteBacktest(backtest.id)}
                          className="text-gray-500 hover:text-red-500 transition-colors"
                          title="删除回测"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default BacktestPage