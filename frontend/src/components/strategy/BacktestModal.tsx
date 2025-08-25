import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useStrategyStore } from '../../store/strategyStore'
import { useAuthStore } from '../../store/authStore'
import { Button, Input } from '../common'
import type { Strategy } from '../../types/strategy'

// 回测配置验证模式
const backtestSchema = z.object({
  start_date: z.string().min(1, '请选择开始日期'),
  end_date: z.string().min(1, '请选择结束日期'),
  initial_capital: z.number().min(1, '初始资金必须大于0'),
  commission_rate: z.number().min(0).max(1, '手续费率应在0-100%之间'),
  slippage: z.number().min(0).max(1, '滑点应在0-100%之间'),
  data_granularity: z.enum(['1m', '5m', '15m', '1h', '4h', '1d'])
})

type BacktestFormData = z.infer<typeof backtestSchema>

interface BacktestModalProps {
  strategy: Strategy
  onClose: () => void
}

const BacktestModal: React.FC<BacktestModalProps> = ({
  strategy,
  onClose
}) => {
  const [isRunning, setIsRunning] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'config' | 'results'>('config')
  
  const { runBacktest } = useStrategyStore()
  const { user } = useAuthStore()

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch
  } = useForm<BacktestFormData>({
    resolver: zodResolver(backtestSchema),
    defaultValues: {
      start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
      initial_capital: 10000,
      commission_rate: 0.001,
      slippage: 0.0005,
      data_granularity: '1h'
    }
  })

  const watchedGranularity = watch('data_granularity')
  
  // 根据会员等级获取可用的数据粒度
  const getAvailableGranularities = () => {
    const all = [
      { value: '1d', label: '1天', free: true },
      { value: '4h', label: '4小时', free: true },
      { value: '1h', label: '1小时', free: true },
      { value: '15m', label: '15分钟', free: false },
      { value: '5m', label: '5分钟', free: false },
      { value: '1m', label: '1分钟', free: false }
    ]
    
    if (user?.membership_level === 'basic') {
      return all.filter(g => g.free)
    }
    return all
  }

  const getBacktestTier = (granularity: string) => {
    switch (granularity) {
      case '1d':
      case '4h':
      case '1h':
        return 'basic'
      case '15m':
      case '5m':
        return 'hybrid'
      case '1m':
        return 'tick'
      default:
        return 'basic'
    }
  }

  const onSubmit = async (data: BacktestFormData) => {
    setIsRunning(true)
    setActiveTab('results')
    
    try {
      const result = await runBacktest(strategy.id, {
        ...data,
        tier: getBacktestTier(data.data_granularity)
      })
      
      setResults(result)
    } catch (error) {
      console.error('Backtest error:', error)
    } finally {
      setIsRunning(false)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: 'USD'
    }).format(amount)
  }

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* 模态框标题 */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">策略回测</h2>
            <p className="text-sm text-gray-600 mt-1">{strategy.name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 选项卡 */}
        <div className="flex border-b border-gray-200">
          <button
            type="button"
            onClick={() => setActiveTab('config')}
            className={`px-6 py-3 text-sm font-medium ${
              activeTab === 'config'
                ? 'text-brand-600 border-b-2 border-brand-500'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            回测配置
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('results')}
            className={`px-6 py-3 text-sm font-medium ${
              activeTab === 'results'
                ? 'text-brand-600 border-b-2 border-brand-500'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            回测结果
          </button>
        </div>

        {/* 内容区域 */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {activeTab === 'config' && (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              {/* 时间范围 */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">时间范围</h3>
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="开始日期"
                    type="date"
                    {...register('start_date')}
                    error={errors.start_date?.message}
                  />
                  <Input
                    label="结束日期"
                    type="date"
                    {...register('end_date')}
                    error={errors.end_date?.message}
                  />
                </div>
              </div>

              {/* 回测参数 */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">回测参数</h3>
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="初始资金 (USD)"
                    type="number"
                    step="0.01"
                    {...register('initial_capital', { valueAsNumber: true })}
                    error={errors.initial_capital?.message}
                  />
                  <Input
                    label="手续费率 (%)"
                    type="number"
                    step="0.001"
                    {...register('commission_rate', { valueAsNumber: true })}
                    error={errors.commission_rate?.message}
                    helperText="每笔交易的手续费率"
                  />
                  <Input
                    label="滑点 (%)"
                    type="number"
                    step="0.0001"
                    {...register('slippage', { valueAsNumber: true })}
                    error={errors.slippage?.message}
                    helperText="交易时的价格滑点"
                  />
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      数据粒度
                    </label>
                    <select
                      {...register('data_granularity')}
                      className="input"
                    >
                      {getAvailableGranularities().map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                          {!option.free && user?.membership_level === 'basic' ? ' (需要升级)' : ''}
                        </option>
                      ))}
                    </select>
                    {errors.data_granularity && (
                      <p className="mt-1 text-sm text-red-600">{errors.data_granularity.message}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* 回测等级说明 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2">
                  回测等级: {
                    getBacktestTier(watchedGranularity) === 'basic' ? '基础回测' :
                    getBacktestTier(watchedGranularity) === 'hybrid' ? 'Pro回测' : 'Elite回测'
                  }
                </h4>
                <p className="text-sm text-gray-600">
                  {getBacktestTier(watchedGranularity) === 'basic' && '使用K线数据进行回测，适合长周期策略验证'}
                  {getBacktestTier(watchedGranularity) === 'hybrid' && '使用秒级数据进行回测，提供更精确的回测结果'}
                  {getBacktestTier(watchedGranularity) === 'tick' && '使用tick级数据进行回测，最高精度的回测体验'}
                </p>
              </div>

              {/* 会员限制提示 */}
              {user?.membership_level === 'basic' && getBacktestTier(watchedGranularity) !== 'basic' && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <div className="flex items-center">
                    <svg className="w-5 h-5 text-yellow-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    <div>
                      <h4 className="text-sm font-medium text-yellow-800">需要升级会员</h4>
                      <p className="text-sm text-yellow-700 mt-1">
                        该数据粒度需要高级会员权限。升级后可享受更精确的回测功能。
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <Button
                  type="submit"
                  loading={isRunning}
                  disabled={user?.membership_level === 'basic' && getBacktestTier(watchedGranularity) !== 'basic'}
                >
                  {isRunning ? '运行中...' : '开始回测'}
                </Button>
              </div>
            </form>
          )}

          {activeTab === 'results' && (
            <div>
              {isRunning ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500 mx-auto mb-4"></div>
                  <p className="text-gray-600">正在运行回测，请稍候...</p>
                  <div className="mt-4 text-sm text-gray-500">
                    这可能需要几分钟时间，具体取决于数据量和策略复杂度
                  </div>
                </div>
              ) : results ? (
                <div className="space-y-6">
                  {/* 关键指标 */}
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-4">关键指标</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">总收益</div>
                        <div className={`text-lg font-bold ${
                          results.total_return >= 0 ? 'text-success-600' : 'text-danger-600'
                        }`}>
                          {formatPercentage(results.total_return)}
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">最终资金</div>
                        <div className="text-lg font-bold text-gray-900">
                          {formatCurrency(results.final_capital)}
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">最大回撤</div>
                        <div className="text-lg font-bold text-danger-600">
                          {formatPercentage(results.max_drawdown)}
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">夏普比率</div>
                        <div className="text-lg font-bold text-gray-900">
                          {results.sharpe_ratio?.toFixed(2) || '-'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 交易统计 */}
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-4">交易统计</h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">总交易次数</div>
                        <div className="text-lg font-bold text-gray-900">
                          {results.total_trades || 0}
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">胜率</div>
                        <div className="text-lg font-bold text-gray-900">
                          {results.win_rate ? `${(results.win_rate * 100).toFixed(1)}%` : '-'}
                        </div>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="text-sm text-gray-500 mb-1">平均持仓时间</div>
                        <div className="text-lg font-bold text-gray-900">
                          {results.avg_trade_duration ? `${results.avg_trade_duration.toFixed(1)}h` : '-'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 权益曲线占位符 */}
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-4">权益曲线</h3>
                    <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
                      <p className="text-gray-500">权益曲线图表 (待实现)</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <h3 className="mt-4 text-lg font-medium text-gray-900">暂无回测结果</h3>
                  <p className="mt-2 text-gray-500">配置回测参数并运行以查看结果</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200">
          <Button
            variant="outline"
            onClick={onClose}
          >
            关闭
          </Button>
          {results && (
            <Button>
              导出报告
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export default BacktestModal