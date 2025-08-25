import React from 'react'
import { Card, Button } from '../common'
import type { Strategy } from '../../types/strategy'

interface StrategyListProps {
  strategies: Strategy[]
  onEdit: (strategy: Strategy) => void
  onBacktest: (strategy: Strategy) => void
  onStart: (strategyId: string) => void
  onStop: (strategyId: string) => void
  onDelete: (strategyId: string) => void
}

const StrategyList: React.FC<StrategyListProps> = ({
  strategies,
  onEdit,
  onBacktest,
  onStart,
  onStop,
  onDelete
}) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return (
          <span className="status-success">
            <div className="w-2 h-2 bg-success-500 rounded-full mr-1"></div>
            运行中
          </span>
        )
      case 'paused':
        return (
          <span className="status-warning">
            <div className="w-2 h-2 bg-warning-500 rounded-full mr-1"></div>
            已暂停
          </span>
        )
      case 'stopped':
        return (
          <span className="status-neutral">
            <div className="w-2 h-2 bg-gray-500 rounded-full mr-1"></div>
            已停止
          </span>
        )
      default:
        return (
          <span className="status-neutral">
            <div className="w-2 h-2 bg-gray-500 rounded-full mr-1"></div>
            未知
          </span>
        )
    }
  }

  const formatPercentage = (value?: number) => {
    if (typeof value !== 'number') return '-'
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value.toFixed(2)}%`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="space-y-4">
      {strategies.map((strategy) => (
        <Card key={strategy.id} padding="none" className="overflow-hidden">
          <div className="p-6">
            <div className="flex items-start justify-between">
              {/* 策略基本信息 */}
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {strategy.name}
                  </h3>
                  {getStatusBadge(strategy.status)}
                </div>
                
                {strategy.description && (
                  <p className="text-gray-600 text-sm mb-3 max-w-2xl">
                    {strategy.description}
                  </p>
                )}

                <div className="flex items-center text-sm text-gray-500 space-x-4">
                  <span>创建时间: {formatDate(strategy.created_at)}</span>
                  {strategy.last_trade_at && (
                    <span>最近交易: {formatDate(strategy.last_trade_at)}</span>
                  )}
                </div>
              </div>

              {/* 策略统计 */}
              <div className="flex items-center space-x-8 ml-6">
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">总收益</div>
                  <div className={`text-lg font-bold ${
                    (strategy.total_return || 0) >= 0 ? 'text-success-600' : 'text-danger-600'
                  }`}>
                    {formatPercentage(strategy.total_return)}
                  </div>
                </div>
                
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">胜率</div>
                  <div className="text-lg font-bold text-gray-900">
                    {strategy.win_rate ? `${strategy.win_rate.toFixed(1)}%` : '-'}
                  </div>
                </div>
                
                <div className="text-center">
                  <div className="text-xs text-gray-500 mb-1">交易次数</div>
                  <div className="text-lg font-bold text-gray-900">
                    {strategy.total_trades || 0}
                  </div>
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="flex items-center space-x-2 ml-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEdit(strategy)}
                  className="text-gray-600 hover:text-brand-600"
                >
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  编辑
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onBacktest(strategy)}
                  className="text-purple-600 hover:text-purple-700"
                >
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  回测
                </Button>

                {strategy.status === 'running' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onStop(strategy.id)}
                    className="text-warning-600 hover:text-warning-700"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                    </svg>
                    停止
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => onStart(strategy.id)}
                    className="bg-success-500 hover:bg-success-600"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-6 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    启动
                  </Button>
                )}

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(strategy.id)}
                  className="text-danger-600 hover:text-danger-700 hover:bg-danger-50"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </Button>
              </div>
            </div>
          </div>

          {/* 策略代码预览 */}
          {strategy.code && (
            <div className="border-t border-gray-200 bg-gray-50 px-6 py-3">
              <details className="group">
                <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-800 flex items-center">
                  <svg className="w-4 h-4 mr-2 transform group-open:rotate-90 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  查看策略代码
                </summary>
                <pre className="mt-3 p-4 bg-gray-900 text-gray-100 text-sm rounded-lg overflow-x-auto">
                  <code>{strategy.code.substring(0, 500)}{strategy.code.length > 500 ? '...' : ''}</code>
                </pre>
              </details>
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}

export default StrategyList