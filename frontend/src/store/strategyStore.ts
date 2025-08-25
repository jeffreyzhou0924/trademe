import { create } from 'zustand'
import toast from 'react-hot-toast'
import { strategyApi } from '../services/api/strategy'
import type { Strategy, CreateStrategyData, BacktestResult } from '../types/strategy'

interface StrategyState {
  // 策略列表
  strategies: Strategy[]
  selectedStrategy: Strategy | null
  isLoading: boolean
  
  // 回测相关
  backtestResults: BacktestResult[]
  isBacktesting: boolean
  
  // 操作方法
  fetchStrategies: () => Promise<void>
  createStrategy: (data: CreateStrategyData) => Promise<boolean>
  updateStrategy: (id: string, data: Partial<Strategy>) => Promise<boolean>
  deleteStrategy: (id: string) => Promise<boolean>
  selectStrategy: (strategy: Strategy | null) => void
  
  // 回测相关方法
  runBacktest: (strategyId: string, config: any) => Promise<boolean>
  fetchBacktestResults: (strategyId: string) => Promise<void>
  
  // 策略执行
  startStrategy: (id: string) => Promise<boolean>
  stopStrategy: (id: string) => Promise<boolean>
}

export const useStrategyStore = create<StrategyState>((set, get) => ({
  // 初始状态
  strategies: [],
  selectedStrategy: null,
  isLoading: false,
  backtestResults: [],
  isBacktesting: false,

  // 获取策略列表
  fetchStrategies: async () => {
    set({ isLoading: true })
    try {
      const strategies = await strategyApi.getStrategies()
      set({ strategies, isLoading: false })
    } catch (error: any) {
      set({ isLoading: false })
      const message = error.response?.data?.message || '获取策略列表失败'
      toast.error(message)
    }
  },

  // 创建策略
  createStrategy: async (data: CreateStrategyData) => {
    try {
      const strategy = await strategyApi.createStrategy(data)
      set(state => ({
        strategies: [...state.strategies, strategy]
      }))
      toast.success('策略创建成功')
      return true
    } catch (error: any) {
      const message = error.response?.data?.message || '创建策略失败'
      toast.error(message)
      return false
    }
  },

  // 更新策略
  updateStrategy: async (id: string, data: Partial<Strategy>) => {
    try {
      const updatedStrategy = await strategyApi.updateStrategy(id, data)
      set(state => ({
        strategies: state.strategies.map(s => 
          s.id === id ? updatedStrategy : s
        ),
        selectedStrategy: state.selectedStrategy?.id === id 
          ? updatedStrategy 
          : state.selectedStrategy
      }))
      toast.success('策略更新成功')
      return true
    } catch (error: any) {
      const message = error.response?.data?.message || '更新策略失败'
      toast.error(message)
      return false
    }
  },

  // 删除策略
  deleteStrategy: async (id: string) => {
    try {
      await strategyApi.deleteStrategy(id)
      set(state => ({
        strategies: state.strategies.filter(s => s.id !== id),
        selectedStrategy: state.selectedStrategy?.id === id 
          ? null 
          : state.selectedStrategy
      }))
      toast.success('策略删除成功')
      return true
    } catch (error: any) {
      const message = error.response?.data?.message || '删除策略失败'
      toast.error(message)
      return false
    }
  },

  // 选择策略
  selectStrategy: (strategy: Strategy | null) => {
    set({ selectedStrategy: strategy })
  },

  // 运行回测
  runBacktest: async (strategyId: string, config: any) => {
    set({ isBacktesting: true })
    try {
      const result = await strategyApi.runBacktest(strategyId, config)
      set(state => ({
        backtestResults: [...state.backtestResults, result],
        isBacktesting: false
      }))
      toast.success('回测完成')
      return true
    } catch (error: any) {
      set({ isBacktesting: false })
      const message = error.response?.data?.message || '回测失败'
      toast.error(message)
      return false
    }
  },

  // 获取回测结果
  fetchBacktestResults: async (strategyId: string) => {
    try {
      const results = await strategyApi.getBacktestResults(strategyId)
      set({ backtestResults: results })
    } catch (error: any) {
      const message = error.response?.data?.message || '获取回测结果失败'
      toast.error(message)
    }
  },

  // 启动策略
  startStrategy: async (id: string) => {
    try {
      await strategyApi.startStrategy(id)
      set(state => ({
        strategies: state.strategies.map(s =>
          s.id === id ? { ...s, status: 'running' } : s
        ),
        selectedStrategy: state.selectedStrategy?.id === id
          ? { ...state.selectedStrategy, status: 'running' }
          : state.selectedStrategy
      }))
      toast.success('策略已启动')
      return true
    } catch (error: any) {
      const message = error.response?.data?.message || '启动策略失败'
      toast.error(message)
      return false
    }
  },

  // 停止策略
  stopStrategy: async (id: string) => {
    try {
      await strategyApi.stopStrategy(id)
      set(state => ({
        strategies: state.strategies.map(s =>
          s.id === id ? { ...s, status: 'stopped' } : s
        ),
        selectedStrategy: state.selectedStrategy?.id === id
          ? { ...state.selectedStrategy, status: 'stopped' }
          : state.selectedStrategy
      }))
      toast.success('策略已停止')
      return true
    } catch (error: any) {
      const message = error.response?.data?.message || '停止策略失败'
      toast.error(message)
      return false
    }
  },
}))