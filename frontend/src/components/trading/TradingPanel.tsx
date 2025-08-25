import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { useMarketStore } from '../../store/marketStore'
import { useAuthStore } from '../../store/authStore'
import { Button, Input } from '../common'
import type { TickerData } from '../../types/market'

// 交易表单验证
const tradeSchema = z.object({
  price: z.string().min(1, '请输入价格'),
  quantity: z.string().min(1, '请输入数量'),
  orderType: z.enum(['limit', 'market']),
})

type TradeFormData = z.infer<typeof tradeSchema>

interface TradingPanelProps {
  className?: string
}

const TradingPanel: React.FC<TradingPanelProps> = ({ className = '' }) => {
  const [activeTab, setActiveTab] = useState<'buy' | 'sell'>('buy')
  const [orderType, setOrderType] = useState<'limit' | 'market'>('limit')
  const [balances] = useState({
    'USDT': 10000,
    'BTC': 0.5,
    'ETH': 2.3
  })

  const { 
    selectedSymbol, 
    selectedExchange, 
    currentPrices 
  } = useMarketStore()
  
  const { user } = useAuthStore()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
    watch,
    reset
  } = useForm<TradeFormData>({
    resolver: zodResolver(tradeSchema),
    defaultValues: {
      orderType: 'limit',
      price: '',
      quantity: ''
    }
  })

  const watchedPrice = watch('price')
  const watchedQuantity = watch('quantity')
  
  // 获取当前价格
  const currentPrice = currentPrices[selectedSymbol]
  
  // 计算交易金额
  const calculateTotal = () => {
    const price = parseFloat(watchedPrice) || 0
    const quantity = parseFloat(watchedQuantity) || 0
    return price * quantity
  }

  // 获取资产余额
  const getBalance = (asset: string) => {
    return balances[asset as keyof typeof balances] || 0
  }

  // 自动填充市价
  useEffect(() => {
    if (orderType === 'market' && currentPrice) {
      setValue('price', currentPrice.price.toString())
    }
  }, [orderType, currentPrice, setValue])

  // 处理订单类型切换
  const handleOrderTypeChange = (type: 'limit' | 'market') => {
    setOrderType(type)
    setValue('orderType', type)
    
    if (type === 'market' && currentPrice) {
      setValue('price', currentPrice.price.toString())
    }
  }

  // 处理百分比选择
  const handlePercentageSelect = (percentage: number) => {
    if (!currentPrice) return

    const baseAsset = selectedSymbol.split('/')[0]
    const quoteAsset = selectedSymbol.split('/')[1]
    
    if (activeTab === 'buy') {
      const availableBalance = getBalance(quoteAsset)
      const price = parseFloat(watchedPrice) || currentPrice.price
      const maxQuantity = availableBalance / price
      const quantity = (maxQuantity * percentage / 100).toFixed(8)
      setValue('quantity', quantity)
    } else {
      const availableBalance = getBalance(baseAsset)
      const quantity = (availableBalance * percentage / 100).toFixed(8)
      setValue('quantity', quantity)
    }
  }

  // 提交交易订单
  const onSubmit = async (data: TradeFormData) => {
    try {
      // 模拟API调用
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      const orderData = {
        symbol: selectedSymbol,
        exchange: selectedExchange,
        side: activeTab.toUpperCase(),
        type: data.orderType.toUpperCase(),
        quantity: parseFloat(data.quantity),
        price: data.orderType === 'limit' ? parseFloat(data.price) : undefined,
        total: calculateTotal()
      }

      console.log('提交订单:', orderData)
      toast.success(`${activeTab === 'buy' ? '买入' : '卖出'}订单提交成功`)
      
      // 重置表单
      reset()
    } catch (error) {
      toast.error('订单提交失败')
    }
  }

  const baseAsset = selectedSymbol?.split('/')[0] || ''
  const quoteAsset = selectedSymbol?.split('/')[1] || ''
  const total = calculateTotal()

  return (
    <div className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`}>
      {/* 买卖切换 */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('buy')}
          className={`flex-1 py-3 text-sm font-medium ${
            activeTab === 'buy'
              ? 'text-success-600 border-b-2 border-success-500 bg-success-50'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          买入 {baseAsset}
        </button>
        <button
          onClick={() => setActiveTab('sell')}
          className={`flex-1 py-3 text-sm font-medium ${
            activeTab === 'sell'
              ? 'text-danger-600 border-b-2 border-danger-500 bg-danger-50'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          卖出 {baseAsset}
        </button>
      </div>

      <div className="p-4">
        {/* 订单类型选择 */}
        <div className="mb-4">
          <div className="flex space-x-2">
            <button
              onClick={() => handleOrderTypeChange('limit')}
              className={`px-3 py-1 text-sm rounded ${
                orderType === 'limit'
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              限价单
            </button>
            <button
              onClick={() => handleOrderTypeChange('market')}
              className={`px-3 py-1 text-sm rounded ${
                orderType === 'market'
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              市价单
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* 价格输入 */}
          <div>
            <Input
              label={`价格 (${quoteAsset})`}
              type="number"
              step="0.00000001"
              placeholder={orderType === 'market' ? '市价' : '输入价格'}
              disabled={orderType === 'market'}
              {...register('price')}
              error={errors.price?.message}
              iconPosition="right"
              icon={
                <span className="text-xs text-gray-400">{quoteAsset}</span>
              }
            />
            {currentPrice && orderType === 'limit' && (
              <div className="mt-1 text-xs text-gray-500">
                当前价格: ${currentPrice.price.toFixed(8)}
              </div>
            )}
          </div>

          {/* 数量输入 */}
          <div>
            <Input
              label={`数量 (${baseAsset})`}
              type="number"
              step="0.00000001"
              placeholder="输入数量"
              {...register('quantity')}
              error={errors.quantity?.message}
              iconPosition="right"
              icon={
                <span className="text-xs text-gray-400">{baseAsset}</span>
              }
            />
          </div>

          {/* 百分比选择 */}
          <div>
            <div className="flex justify-between text-xs text-gray-500 mb-2">
              <span>可用余额</span>
              <span>
                {activeTab === 'buy' 
                  ? `${getBalance(quoteAsset).toLocaleString()} ${quoteAsset}`
                  : `${getBalance(baseAsset).toLocaleString()} ${baseAsset}`
                }
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {[25, 50, 75, 100].map((percentage) => (
                <button
                  key={percentage}
                  type="button"
                  onClick={() => handlePercentageSelect(percentage)}
                  className="py-1 text-xs border border-gray-300 rounded hover:border-brand-500 hover:text-brand-500"
                >
                  {percentage}%
                </button>
              ))}
            </div>
          </div>

          {/* 交易金额 */}
          {total > 0 && (
            <div className="p-3 bg-gray-50 rounded">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">交易金额:</span>
                <span className="font-medium">
                  {total.toFixed(8)} {quoteAsset}
                </span>
              </div>
              {activeTab === 'buy' && (
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>手续费 (0.1%):</span>
                  <span>{(total * 0.001).toFixed(8)} {quoteAsset}</span>
                </div>
              )}
            </div>
          )}

          {/* 提交按钮 */}
          <Button
            type="submit"
            loading={isSubmitting}
            className={`w-full ${
              activeTab === 'buy'
                ? 'bg-success-500 hover:bg-success-600'
                : 'bg-danger-500 hover:bg-danger-600'
            }`}
          >
            {isSubmitting 
              ? '提交中...' 
              : `${activeTab === 'buy' ? '买入' : '卖出'} ${baseAsset}`
            }
          </Button>
        </form>

        {/* 余额信息 */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">资产余额</h4>
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">{baseAsset}:</span>
              <span className="font-medium">
                {getBalance(baseAsset).toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">{quoteAsset}:</span>
              <span className="font-medium">
                {getBalance(quoteAsset).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* 会员提示 */}
        {user?.membership_level === 'basic' && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
            <div className="flex items-center">
              <svg className="w-4 h-4 text-yellow-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs text-yellow-700">
                升级会员可享受更低手续费和高级功能
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TradingPanel