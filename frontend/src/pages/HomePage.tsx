import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { useLanguageStore } from '../store/languageStore'
import { Card, Button } from '../components/common'
import { ProfitCurveChart } from '../components/charts'
import { dashboardApi, DashboardStats, ProfitCurveData } from '../services/api/dashboard'
import toast from 'react-hot-toast'

const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuthStore()
  const { theme } = useThemeStore()
  const { t } = useLanguageStore()
  
  // 仪表板数据状态
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null)
  const [profitCurveData, setProfitCurveData] = useState<ProfitCurveData[]>([])
  const [isLoadingStats, setIsLoadingStats] = useState(false)
  const [isLoadingProfitCurve, setIsLoadingProfitCurve] = useState(false)
  const [selectedTimeframe, setSelectedTimeframe] = useState<'7' | '30' | '90'>('90')

  // 如果用户已登录，重定向到AI助手页面
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/ai-chat', { replace: true })
    }
  }, [isAuthenticated, navigate])

  // 移除仪表板数据加载，直接重定向到AI助手
  // useEffect 已在上面处理重定向逻辑

  // 移除仪表板数据加载函数

  // 移除收益曲线数据加载函数

  const generateDefaultData = (days: number): ProfitCurveData[] => {
    const data: ProfitCurveData[] = []
    const now = new Date()
    
    for (let i = days; i >= 0; i -= Math.max(1, Math.floor(days / 10))) {
      const date = new Date(now)
      date.setDate(date.getDate() - i)
      
      const progress = 1 - (i / days)
      const value = progress * 12.3 + (Math.random() - 0.5) * 2
      
      data.push({
        timestamp: date.toISOString().split('T')[0],
        value: Math.round(value * 100) / 100
      })
    }
    
    return data
  }

  // 主题现在在 App.tsx 中全局处理

  if (!isAuthenticated) {
    // 未登录用户看到的欢迎页面
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center transition-colors">
        <div className="max-w-4xl mx-auto text-center px-4">
          <div className="mb-8">
            <div className="w-16 h-16 mx-auto bg-brand-500 rounded-full flex items-center justify-center mb-4">
              <span className="text-white font-bold text-xl">T</span>
            </div>
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4 transition-colors">
              欢迎使用 <span className="text-brand-500">Trademe</span>
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-300 mb-8 transition-colors">
              专业的数字货币策略交易平台，集成AI智能分析
            </p>
          </div>

          {/* 核心功能展示 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            {/* AI策略回测 */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-gray-700 transition-colors">
              <div className="w-16 h-16 mx-auto bg-gradient-to-r from-blue-500 to-cyan-500 rounded-2xl flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white text-center">AI策略回测</h3>
              <p className="text-gray-600 dark:text-gray-300 mb-6 leading-relaxed">
                使用Claude 4先进AI技术，将您的交易想法智能转化为专业策略代码。平台提供tick级别的高精度历史数据回测，
                确保策略验证的准确性。回测完成后，可一键部署至实盘交易，实现从想法到盈利的完整闭环。
              </p>
              <div className="space-y-2 mb-6">
                <div className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                  <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  Claude 4智能策略生成
                </div>
                <div className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                  <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  Tick级别高精度回测
                </div>
                <div className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                  <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  一键转实盘运行
                </div>
              </div>
              <Link to="/ai-backtest-intro" className="block">
                <button className="w-full py-3 px-6 bg-gradient-to-r from-blue-500 to-cyan-500 text-white font-medium rounded-lg hover:from-blue-600 hover:to-cyan-600 transition-all transform hover:scale-105">
                  了解详情
                </button>
              </Link>
            </div>

            {/* AI智能分析 */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-gray-700 transition-colors">
              <div className="w-16 h-16 mx-auto bg-gradient-to-r from-green-500 to-emerald-500 rounded-2xl flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white text-center">AI智能分析</h3>
              <p className="text-gray-600 dark:text-gray-300 mb-6 leading-relaxed">
                通过深度记录和分析您的策略开单情况及手动交易行为，AI助手能够学习您的交易逻辑和风格偏好。
                与AI进行深度对话，共同构建个性化的智能交易系统，让AI成为您24小时不间断的专业交易顾问。
              </p>
              <div className="space-y-2 mb-6">
                <div className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                  <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  智能交易行为分析
                </div>
                <div className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                  <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  个性化交易逻辑学习
                </div>
                <div className="flex items-center text-sm text-gray-600 dark:text-gray-300">
                  <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  24/7智能交易助手
                </div>
              </div>
              <Link to="/ai-analysis-intro" className="block">
                <button className="w-full py-3 px-6 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-medium rounded-lg hover:from-green-600 hover:to-emerald-600 transition-all transform hover:scale-105">
                  了解详情
                </button>
              </Link>
            </div>
          </div>

          {/* 其他特性 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 border border-gray-200 dark:border-gray-700 text-center transition-colors">
              <div className="w-12 h-12 mx-auto bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">多交易所支持</h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm">支持币安、OKX等主流交易所API，统一管理多个账户</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 border border-gray-200 dark:border-gray-700 text-center transition-colors">
              <div className="w-12 h-12 mx-auto bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">安全可靠</h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm">银行级别的安全加密，API密钥本地加密存储</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 border border-gray-200 dark:border-gray-700 text-center transition-colors">
              <div className="w-12 h-12 mx-auto bg-indigo-100 dark:bg-indigo-900 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-indigo-600 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">实时监控</h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm">实时监控策略表现，智能风控保护您的资金安全</p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-8">
            <Link to="/login" className="w-full sm:w-auto">
              <button className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-xl hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-105 shadow-lg">
                免费开始使用
              </button>
            </Link>
            <Link to="/pricing" className="w-full sm:w-auto">
              <button className="w-full sm:w-auto px-8 py-4 bg-transparent border-2 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-semibold rounded-xl hover:border-blue-500 dark:hover:border-blue-400 transition-colors">
                查看会员方案
              </button>
            </Link>
          </div>

          {/* AI策略回测详细介绍 */}
          <div className="mt-20 mb-16">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">AI策略回测 - 让想法变成盈利</h2>
              <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
                使用Claude 4先进AI技术，将您的交易想法智能转化为专业策略代码
              </p>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              <div className="space-y-6">
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-blue-600 dark:text-blue-400 font-bold">1</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">描述您的策略想法</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      用自然语言描述您的交易策略思路，比如"当RSI超卖且价格触及支撑位时买入"。
                      Claude 4能够理解复杂的交易逻辑和技术指标组合。
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-green-600 dark:text-green-400 font-bold">2</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">AI智能策略生成</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      AI自动将您的想法转换为专业的Python交易策略代码，包含完整的开仓、平仓、止损止盈逻辑，
                      支持多种技术指标和风控机制。
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-purple-600 dark:text-purple-400 font-bold">3</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">Tick级别精确回测</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      使用真实的tick级别历史数据进行回测，精确模拟每一笔交易的执行过程，
                      包含滑点、手续费等真实交易成本，确保回测结果的可靠性。
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-orange-600 dark:text-orange-400 font-bold">4</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">一键转实盘运行</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      回测验证策略有效性后，一键部署到实盘交易环境。
                      平台自动处理API连接、订单执行、风险控制等技术细节，让您专注于策略优化。
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl p-8 text-white">
                <h3 className="text-2xl font-bold mb-6">策略回测报告示例</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span>总收益率</span>
                    <span className="font-bold text-green-300">+156.8%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>夏普比率</span>
                    <span className="font-bold">2.34</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>最大回撤</span>
                    <span className="font-bold text-red-300">-8.5%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>胜率</span>
                    <span className="font-bold">68.2%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>盈亏比</span>
                    <span className="font-bold">2.1:1</span>
                  </div>
                </div>
                <div className="mt-6 p-4 bg-white/10 rounded-lg">
                  <p className="text-sm">
                    "该策略在过去12个月的回测中表现优异，具有较低的风险和稳定的收益。建议配置20%的资金进行实盘交易。"
                  </p>
                  <p className="text-xs mt-2 opacity-80">— AI策略分析师</p>
                </div>
              </div>
            </div>
          </div>

          {/* AI智能分析详细介绍 */}
          <div className="mt-20 mb-16">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">AI智能分析 - 您的24/7交易顾问</h2>
              <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
                通过深度学习您的交易行为，构建个性化的智能交易系统
              </p>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              <div className="bg-gradient-to-r from-green-500 to-teal-600 rounded-2xl p-8 text-white">
                <h3 className="text-2xl font-bold mb-6">AI学习您的交易模式</h3>
                <div className="space-y-4">
                  <div className="p-4 bg-white/10 rounded-lg">
                    <h4 className="font-semibold mb-2">交易心得记录</h4>
                    <p className="text-sm opacity-90">
                      "今天在BTCUSDT 45000附近看到双底形态，结合RSI超卖信号，
                      决定建立多头仓位。设置止损在44500，目标位46500。"
                    </p>
                  </div>
                  <div className="p-4 bg-white/10 rounded-lg">
                    <h4 className="font-semibold mb-2">AI分析反馈</h4>
                    <p className="text-sm opacity-90">
                      "您偏好在技术形态确认后进场，风险控制意识较强。
                      建议在类似条件下可以适当加大仓位，历史胜率达72%。"
                    </p>
                  </div>
                  <div className="p-4 bg-white/10 rounded-lg">
                    <h4 className="font-semibold mb-2">交易建议</h4>
                    <p className="text-sm opacity-90">
                      "当前ETHUSDT出现类似的双底+RSI超卖组合，
                      基于您的交易风格，建议关注入场机会。"
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="space-y-6">
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-green-600 dark:text-green-400 font-bold">1</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">记录交易心得</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      详细记录每次交易的思路、进场逻辑、情绪状态等。
                      平台支持文字、图片、语音等多种形式，让记录更加便捷真实。
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-blue-600 dark:text-blue-400 font-bold">2</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">AI深度学习</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      AI分析您的交易记录，识别成功和失败的交易模式，
                      学习您的风险偏好、时间习惯、技术分析方法等个性化特征。
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-purple-600 dark:text-purple-400 font-bold">3</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">智能对话分析</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      与AI进行深度对话，讨论市场观点、交易策略、风险控制等。
                      AI会根据您的历史表现和当前市况，提供个性化的交易建议。
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-10 h-10 bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center mr-4 flex-shrink-0">
                    <span className="text-orange-600 dark:text-orange-400 font-bold">4</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">构建专属交易系统</h3>
                    <p className="text-gray-600 dark:text-gray-300">
                      基于学习结果，AI帮助构建符合您交易风格的智能系统，
                      包括自动监控、风险提醒、交易机会推送等功能。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 会员方案 */}
          <div className="mt-20 mb-16">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">会员方案</h2>
              <p className="text-xl text-gray-600 dark:text-gray-300">
                选择适合您的专业交易方案，开启AI助力的量化交易之旅
              </p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* 免费用户 */}
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 border border-gray-200 dark:border-gray-700 transition-colors">
                <div className="text-center mb-6">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">免费用户</h3>
                  <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">$0<span className="text-lg text-gray-500 dark:text-gray-400">/月</span></div>
                  <p className="text-gray-600 dark:text-gray-300 mt-2">体验基础功能</p>
                </div>
                
                <ul className="space-y-2 mb-8 text-sm">
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    绑定 1 个API密钥
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    $10 AI对话额度 (总额)
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    无限次K线级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    1KB 交易心得存储
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    1个策略/1个指标
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    1个实盘交易
                  </li>
                </ul>
                
                <button className="w-full py-3 px-6 bg-gray-600 hover:bg-gray-700 text-white font-medium rounded-lg transition-colors">
                  免费开始
                </button>
              </div>

              {/* 初级会员 */}
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 border border-gray-200 dark:border-gray-700 transition-colors">
                <div className="text-center mb-6">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">初级会员</h3>
                  <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">$19<span className="text-lg text-gray-500 dark:text-gray-400">/月</span></div>
                  <p className="text-gray-600 dark:text-gray-300 mt-2">个人交易者首选</p>
                </div>
                
                <ul className="space-y-2 mb-8 text-sm">
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    绑定 1 个API密钥
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    每日 $100 AI助手额度
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    每日 5次 Tick级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    无限次K线级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    1MB 交易心得存储
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    2个策略/2个指标
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    2个实盘交易
                  </li>
                </ul>
                
                <button className="w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                  选择初级会员
                </button>
              </div>

              {/* 高级会员 */}
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 border-2 border-blue-500 relative transition-colors">
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                  <span className="bg-blue-500 text-white px-4 py-1 rounded-full text-sm font-medium">推荐</span>
                </div>
                
                <div className="text-center mb-6">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">高级会员</h3>
                  <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">$99<span className="text-lg text-gray-500 dark:text-gray-400">/月</span></div>
                  <p className="text-gray-600 dark:text-gray-300 mt-2">专业交易团队</p>
                </div>
                
                <ul className="space-y-2 mb-8 text-sm">
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    绑定 5 个API密钥
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    每日 $100 AI助手额度
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    每月 30次 Tick级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    无限次K线级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    20MB 交易心得存储
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    10个策略/10个指标
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    10个实盘交易
                  </li>
                </ul>
                
                <button className="w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                  选择高级会员
                </button>
              </div>

              {/* 专业会员 */}
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 border border-gray-200 dark:border-gray-700 transition-colors">
                <div className="text-center mb-6">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">专业会员</h3>
                  <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">$199<span className="text-lg text-gray-500 dark:text-gray-400">/月</span></div>
                  <p className="text-gray-600 dark:text-gray-300 mt-2">机构投资者</p>
                </div>
                
                <ul className="space-y-2 mb-8 text-sm">
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    绑定 10 个API密钥
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    每日 $200 AI对话额度
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    每月 100次 Tick级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    无限次K线级回测
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    50MB 交易心得存储
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    20个策略/20个指标
                  </li>
                  <li className="flex items-center text-gray-600 dark:text-gray-300">
                    <svg className="w-4 h-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    20个实盘交易
                  </li>
                </ul>
                
                <button className="w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                  选择专业会员
                </button>
              </div>
            </div>
            
            <div className="text-center mt-8">
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                💡 AI额度已优化至最佳性价比 • 所有方案包含无限K线回测 • 免费用户可体验完整功能
              </p>
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 inline-block">
                <p className="text-blue-600 dark:text-blue-400 text-sm font-medium">
                  🎯 推荐：先使用免费账户体验，再根据需要升级付费方案
                </p>
              </div>
            </div>
          </div>

          {/* 联系方式 */}
          <div className="text-center">
            <p className="text-gray-600 dark:text-gray-300 mb-4">遇到问题？联系我们的专业团队</p>
            <a 
              href="https://t.me/+K2JBhvnMW2AwNGZl" 
              target="_blank" 
              rel="noopener noreferrer"
              className="inline-flex items-center px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg transition-colors"
            >
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.374 0 0 5.373 0 12s5.374 12 12 12 12-5.373 12-12S18.626 0 12 0zm5.568 8.16l-1.61 7.59c-.12.54-.44.67-.9.42l-2.47-1.82-1.19 1.14c-.13.13-.24.24-.5.24l.18-2.51 4.62-4.18c.2-.18-.04-.28-.32-.1L10.42 13l-2.42-.76c-.53-.16-.54-.53.11-.78l9.46-3.64c.44-.16.82.1.68.78z"/>
              </svg>
              加入 Telegram 群聊
            </a>
          </div>
        </div>
      </div>
    )
  }

  // 已登录用户看到的仪表板 - 采用原型布局
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      {/* 页面容器 */}
      <div className="w-full max-w-6xl min-h-screen bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 mx-auto transition-colors">
        {/* 头部导航 */}
        <header className="py-4 px-8 flex justify-between items-center border-b border-gray-200 dark:border-gray-700 transition-colors">
          <div className="flex items-center">
            <svg
              className="w-7 h-7 mr-3 text-blue-600 dark:text-blue-400"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <h1 className="text-xl font-bold text-blue-600 dark:text-blue-400 transition-colors">
              Trademe
            </h1>
          </div>
          
          <nav className="flex gap-2">
            <div className="px-4 py-2 rounded-lg text-white font-medium bg-blue-600 dark:bg-blue-600 transition-colors">
              首页
            </div>
            <Link to="/strategies" className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              策略交易
            </Link>
            <Link to="/trading" className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              图表交易
            </Link>
            <Link to="/trading-notes" className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              交易心得
            </Link>
            <Link to="/api-keys" className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              API管理
            </Link>
            <Link to="/profile" className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              账户中心
            </Link>
          </nav>
          
          <div className="flex items-center">
            <div className="w-9 h-9 rounded-full bg-gray-200 overflow-hidden">
              <div className="w-full h-full bg-gradient-to-r from-blue-400 to-blue-600 flex items-center justify-center text-white font-semibold">
                {user?.username?.charAt(0).toUpperCase()}
              </div>
            </div>
          </div>
        </header>

        {/* 主要内容 */}
        <main className="p-8">
          {/* 统计卡片 */}
          <section className="grid grid-cols-3 gap-6 mb-8">
            <div className="bg-white dark:bg-gray-700 rounded-xl shadow-sm border border-gray-100 dark:border-gray-600 p-6 flex items-center transition-colors">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4 bg-blue-100 dark:bg-blue-900">
                <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1721 9z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 dark:text-gray-400 mb-1">APIKEY数量</h3>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {isLoadingStats ? (
                    <span className="animate-pulse bg-gray-200 dark:bg-gray-600 rounded h-8 w-16 inline-block"></span>
                  ) : (
                    <>
                      {dashboardStats?.api_keys.current || 0}
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        /{dashboardStats?.api_keys.limit || 10}
                      </span>
                    </>
                  )}
                </p>
              </div>
            </div>
            
            <div className="bg-white dark:bg-gray-700 rounded-xl shadow-sm border border-gray-100 dark:border-gray-600 p-6 flex items-center transition-colors">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4 bg-green-100 dark:bg-green-900">
                <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 dark:text-gray-400 mb-1">实盘策略数</h3>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {isLoadingStats ? (
                    <span className="animate-pulse bg-gray-200 dark:bg-gray-600 rounded h-8 w-12 inline-block"></span>
                  ) : (
                    dashboardStats?.live_strategies.current || 0
                  )}
                </p>
              </div>
            </div>
            
            <div className="bg-white dark:bg-gray-700 rounded-xl shadow-sm border border-gray-100 dark:border-gray-600 p-6 flex items-center transition-colors">
              <div className="w-12 h-12 rounded-lg flex items-center justify-center mr-4 bg-yellow-100 dark:bg-yellow-900">
                <svg className="w-6 h-6 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm text-gray-500 dark:text-gray-400 mb-1">本月收益率</h3>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {isLoadingStats ? (
                    <span className="animate-pulse bg-gray-200 dark:bg-gray-600 rounded h-8 w-20 inline-block"></span>
                  ) : (
                    <span className={`px-2 py-1 rounded-md ${
                      (dashboardStats?.monthly_return || 0) >= 0 
                        ? 'bg-green-100 dark:bg-green-900 text-green-600 dark:text-green-400' 
                        : 'bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-400'
                    }`}>
                      {(dashboardStats?.monthly_return || 0) >= 0 ? '+' : ''}{(dashboardStats?.monthly_return || 0).toFixed(1)}%
                    </span>
                  )}
                </p>
              </div>
            </div>
          </section>

          {/* 收益率曲线 - 全宽显示 */}
          <section className="mb-8">
            <div className="bg-white dark:bg-gray-700 rounded-xl shadow-sm border border-gray-100 dark:border-gray-600 p-6 transition-colors">
              <div className="flex justify-between items-start mb-6">
                <h2 className="text-xl font-bold text-blue-600 dark:text-blue-400">当前收益率曲线</h2>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setSelectedTimeframe('7')}
                    className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                      selectedTimeframe === '7' 
                        ? 'bg-blue-600 text-white hover:bg-blue-700' 
                        : 'bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-500'
                    }`}
                  >
                    近7天
                  </button>
                  <button 
                    onClick={() => setSelectedTimeframe('30')}
                    className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                      selectedTimeframe === '30' 
                        ? 'bg-blue-600 text-white hover:bg-blue-700' 
                        : 'bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-500'
                    }`}
                  >
                    本月
                  </button>
                  <button 
                    onClick={() => setSelectedTimeframe('90')}
                    className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                      selectedTimeframe === '90' 
                        ? 'bg-blue-600 text-white hover:bg-blue-700' 
                        : 'bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-500'
                    }`}
                  >
                    近3月
                  </button>
                </div>
              </div>
              {isLoadingProfitCurve ? (
                <div className="flex items-center justify-center h-64">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-2 text-gray-500 dark:text-gray-400">加载收益数据...</span>
                </div>
              ) : (
                <ProfitCurveChart 
                  data={profitCurveData}
                  title=""
                  height={250}
                  className="mt-2"
                />
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

export default HomePage