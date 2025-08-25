import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useStrategyStore } from '../../store/strategyStore'
import { Button, Input } from '../common'
import type { Strategy } from '../../types/strategy'

// 表单验证模式
const strategySchema = z.object({
  name: z.string().min(1, '请输入策略名称').max(50, '名称不能超过50个字符'),
  description: z.string().max(200, '描述不能超过200个字符').optional(),
  code: z.string().min(1, '请输入策略代码'),
  parameters: z.record(z.any()).optional()
})

type StrategyFormData = z.infer<typeof strategySchema>

interface CreateStrategyModalProps {
  strategy?: Strategy | null
  onClose: () => void
  onSuccess: () => void
}

const CreateStrategyModal: React.FC<CreateStrategyModalProps> = ({
  strategy,
  onClose,
  onSuccess
}) => {
  const [activeTab, setActiveTab] = useState<'basic' | 'code' | 'parameters'>('basic')
  const [codeTemplate, setCodeTemplate] = useState('')
  const { createStrategy, updateStrategy } = useStrategyStore()

  const isEditing = !!strategy

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
    watch
  } = useForm<StrategyFormData>({
    resolver: zodResolver(strategySchema),
    defaultValues: {
      name: strategy?.name || '',
      description: strategy?.description || '',
      code: strategy?.code || '',
      parameters: strategy?.parameters || {}
    }
  })

  const watchedCode = watch('code')

  // 策略模板
  const strategyTemplates = {
    moving_average: {
      name: '移动平均策略',
      description: '基于移动平均线的简单交易策略',
      code: `# 移动平均线策略
import pandas as pd
import numpy as np

class MovingAverageStrategy:
    def __init__(self, short_window=20, long_window=50):
        self.short_window = short_window
        self.long_window = long_window
    
    def generate_signals(self, data):
        """生成交易信号"""
        # 计算移动平均线
        data['MA_short'] = data['close'].rolling(window=self.short_window).mean()
        data['MA_long'] = data['close'].rolling(window=self.long_window).mean()
        
        # 生成信号
        data['signal'] = 0
        data['signal'][self.short_window:] = np.where(
            data['MA_short'][self.short_window:] > data['MA_long'][self.short_window:], 1, 0
        )
        
        # 生成交易点位
        data['positions'] = data['signal'].diff()
        
        return data
    
    def execute_trade(self, signal, price, quantity=1.0):
        """执行交易"""
        if signal == 1:  # 买入信号
            return {
                'action': 'BUY',
                'price': price,
                'quantity': quantity,
                'timestamp': pd.Timestamp.now()
            }
        elif signal == -1:  # 卖出信号
            return {
                'action': 'SELL',
                'price': price,
                'quantity': quantity,
                'timestamp': pd.Timestamp.now()
            }
        return None`
    },
    rsi: {
      name: 'RSI策略',
      description: '基于相对强弱指标的交易策略',
      code: `# RSI策略
import pandas as pd
import numpy as np

class RSIStrategy:
    def __init__(self, window=14, overbought=70, oversold=30):
        self.window = window
        self.overbought = overbought
        self.oversold = oversold
    
    def calculate_rsi(self, data):
        """计算RSI指标"""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, data):
        """生成交易信号"""
        data['RSI'] = self.calculate_rsi(data)
        
        # 生成信号
        data['signal'] = 0
        data['signal'] = np.where(data['RSI'] < self.oversold, 1, 0)  # 买入
        data['signal'] = np.where(data['RSI'] > self.overbought, -1, data['signal'])  # 卖出
        
        return data`
    },
    grid: {
      name: '网格策略',
      description: '网格交易策略，适合震荡行情',
      code: `# 网格交易策略
import pandas as pd
import numpy as np

class GridStrategy:
    def __init__(self, grid_size=0.01, num_grids=10):
        self.grid_size = grid_size  # 网格间距
        self.num_grids = num_grids  # 网格数量
        self.base_price = None
        self.grid_levels = []
    
    def initialize_grid(self, current_price):
        """初始化网格"""
        self.base_price = current_price
        self.grid_levels = []
        
        for i in range(-self.num_grids//2, self.num_grids//2 + 1):
            level = self.base_price * (1 + i * self.grid_size)
            self.grid_levels.append({
                'price': level,
                'type': 'BUY' if i < 0 else 'SELL',
                'executed': False
            })
    
    def check_grid_triggers(self, current_price):
        """检查网格触发"""
        triggered_orders = []
        
        for grid in self.grid_levels:
            if not grid['executed']:
                if grid['type'] == 'BUY' and current_price <= grid['price']:
                    triggered_orders.append(grid)
                    grid['executed'] = True
                elif grid['type'] == 'SELL' and current_price >= grid['price']:
                    triggered_orders.append(grid)
                    grid['executed'] = True
        
        return triggered_orders`
    }
  }

  const loadTemplate = (templateKey: string) => {
    const template = strategyTemplates[templateKey as keyof typeof strategyTemplates]
    if (template) {
      setValue('name', template.name)
      setValue('description', template.description)
      setValue('code', template.code)
      setActiveTab('code')
    }
  }

  const onSubmit = async (data: StrategyFormData) => {
    try {
      if (isEditing && strategy) {
        await updateStrategy(strategy.id, {
          name: data.name,
          description: data.description,
          code: data.code,
          parameters: data.parameters || {}
        })
      } else {
        await createStrategy({
          name: data.name,
          description: data.description || '',
          code: data.code,
          parameters: data.parameters || {}
        })
      }
      onSuccess()
    } catch (error) {
      console.error('Strategy save error:', error)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* 模态框标题 */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            {isEditing ? '编辑策略' : '创建新策略'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)}>
          {/* 选项卡 */}
          <div className="flex border-b border-gray-200">
            <button
              type="button"
              onClick={() => setActiveTab('basic')}
              className={`px-6 py-3 text-sm font-medium ${
                activeTab === 'basic'
                  ? 'text-brand-600 border-b-2 border-brand-500'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              基本信息
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('code')}
              className={`px-6 py-3 text-sm font-medium ${
                activeTab === 'code'
                  ? 'text-brand-600 border-b-2 border-brand-500'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              策略代码
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('parameters')}
              className={`px-6 py-3 text-sm font-medium ${
                activeTab === 'parameters'
                  ? 'text-brand-600 border-b-2 border-brand-500'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              参数设置
            </button>
          </div>

          {/* 内容区域 */}
          <div className="p-6 max-h-[60vh] overflow-y-auto">
            {activeTab === 'basic' && (
              <div className="space-y-4">
                <Input
                  label="策略名称"
                  placeholder="输入策略名称"
                  {...register('name')}
                  error={errors.name?.message}
                />
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    策略描述
                  </label>
                  <textarea
                    {...register('description')}
                    rows={3}
                    className="input resize-none"
                    placeholder="描述您的策略逻辑和适用场景..."
                  />
                  {errors.description && (
                    <p className="mt-1 text-sm text-red-600">{errors.description.message}</p>
                  )}
                </div>

                {!isEditing && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-3">
                      选择策略模板
                    </label>
                    <div className="grid grid-cols-1 gap-3">
                      {Object.entries(strategyTemplates).map(([key, template]) => (
                        <button
                          key={key}
                          type="button"
                          onClick={() => loadTemplate(key)}
                          className="text-left p-4 border border-gray-200 rounded-lg hover:border-brand-300 hover:bg-brand-50 transition-colors"
                        >
                          <h4 className="font-medium text-gray-900 mb-1">{template.name}</h4>
                          <p className="text-sm text-gray-600">{template.description}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'code' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    策略代码
                  </label>
                  <textarea
                    {...register('code')}
                    rows={20}
                    className="input font-mono text-sm resize-none"
                    placeholder="请输入Python策略代码..."
                    style={{ fontFamily: 'JetBrains Mono, monospace' }}
                  />
                  {errors.code && (
                    <p className="mt-1 text-sm text-red-600">{errors.code.message}</p>
                  )}
                </div>
                
                <div className="text-sm text-gray-500">
                  <p className="mb-2">代码要求：</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>必须包含策略类定义</li>
                    <li>实现 generate_signals() 方法</li>
                    <li>使用pandas处理数据</li>
                    <li>返回标准的信号格式</li>
                  </ul>
                </div>
              </div>
            )}

            {activeTab === 'parameters' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    策略参数 (JSON格式)
                  </label>
                  <textarea
                    rows={10}
                    className="input font-mono text-sm resize-none"
                    placeholder={`{
  "short_window": 20,
  "long_window": 50,
  "risk_ratio": 0.02,
  "stop_loss": 0.05,
  "take_profit": 0.1
}`}
                    defaultValue={JSON.stringify(strategy?.parameters || {}, null, 2)}
                    onChange={(e) => {
                      try {
                        const params = JSON.parse(e.target.value)
                        setValue('parameters', params)
                      } catch (error) {
                        // Invalid JSON, ignore
                      }
                    }}
                  />
                </div>
                
                <div className="text-sm text-gray-500">
                  <p className="mb-2">常用参数：</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>short_window: 短期移动平均窗口</li>
                    <li>long_window: 长期移动平均窗口</li>
                    <li>risk_ratio: 每次交易的风险比例</li>
                    <li>stop_loss: 止损百分比</li>
                    <li>take_profit: 止盈百分比</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* 底部按钮 */}
          <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
            >
              取消
            </Button>
            <Button
              type="submit"
              loading={isSubmitting}
            >
              {isEditing ? '保存修改' : '创建策略'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CreateStrategyModal