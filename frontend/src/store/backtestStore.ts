import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { backtestApi, BacktestConfig, BacktestResult } from '../services/api/backtest'

// 回测配置表单状态
interface BacktestConfigForm {
  strategy_id: string
  symbol: string
  exchange: string
  start_date: string
  end_date: string
  initial_capital: number
  commission_rate: number
  timeframe: string
}

// 回测状态接口
interface BacktestState {
  // 回测列表相关状态
  backtests: BacktestResult[]
  currentBacktest: BacktestResult | null
  loading: boolean
  error: string | null
  
  // 回测配置表单状态
  configForm: BacktestConfigForm
  isCreatingBacktest: boolean
  
  // 实时回测状态
  runningBacktests: Map<string, { status: string; progress?: number }>
  
  // 回测比较功能
  selectedForComparison: string[]
  comparisonResult: any | null
  
  // 分页和筛选
  pagination: {
    page: number
    per_page: number
    total: number
    total_pages: number
  }
  filters: {
    strategy_id?: string
    status?: string
  }
  
  // Actions - 回测列表管理
  fetchBacktests: (params?: { page?: number; per_page?: number }) => Promise<void>
  fetchBacktest: (id: string) => Promise<void>
  refreshBacktest: (id: string) => Promise<void>
  deleteBacktest: (id: string) => Promise<void>
  
  // Actions - 回测创建和控制
  createBacktest: (config: BacktestConfig) => Promise<BacktestResult | null>
  stopBacktest: (id: string) => Promise<void>
  updateBacktestForm: (field: keyof BacktestConfigForm, value: any) => void
  resetBacktestForm: () => void
  
  // Actions - 实时状态监控
  updateBacktestStatus: (id: string, status: string, progress?: number) => void
  pollBacktestStatus: (id: string) => Promise<void>
  
  // Actions - 回测比较
  toggleComparisonSelection: (id: string) => void
  compareBacktests: () => Promise<void>
  clearComparison: () => void
  
  // Actions - 报告下载
  downloadReport: (id: string, format?: 'pdf' | 'html' | 'csv') => Promise<void>
  
  // Actions - 状态管理
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearError: () => void
  reset: () => void
}

// 默认配置表单状态
const defaultConfigForm: BacktestConfigForm = {
  strategy_id: '',
  symbol: 'BTC/USDT',
  exchange: 'okx',
  start_date: '2024-01-01',
  end_date: '2024-03-31',
  initial_capital: 10000,
  commission_rate: 0.001,
  timeframe: '1h'
}

// 创建回测状态管理
export const useBacktestStore = create<BacktestState>()(
  persist(
    (set, get) => ({
      // 初始状态
      backtests: [],
      currentBacktest: null,
      loading: false,
      error: null,
      
      configForm: defaultConfigForm,
      isCreatingBacktest: false,
      
      runningBacktests: new Map(),
      
      selectedForComparison: [],
      comparisonResult: null,
      
      pagination: {
        page: 1,
        per_page: 10,
        total: 0,
        total_pages: 0
      },
      filters: {},
      
      // 回测列表管理
      fetchBacktests: async (params) => {
        set({ loading: true, error: null })
        try {
          const { page = 1, per_page = 10 } = params || {}
          const response = await backtestApi.getBacktests({
            page,
            per_page,
            ...get().filters
          })
          
          // 确保response是数组，如果不是则包装成数组或使用空数组
          const backtestsArray = Array.isArray(response) ? response : []
          
          set({
            backtests: backtestsArray,
            pagination: {
              page,
              per_page,
              total: backtestsArray.length,
              total_pages: Math.ceil(backtestsArray.length / per_page)
            },
            loading: false
          })
        } catch (error) {
          console.error('Error fetching backtests:', error)
          set({ 
            backtests: [], // 确保错误时也是数组
            error: error instanceof Error ? error.message : 'Failed to fetch backtests',
            loading: false 
          })
        }
      },
      
      fetchBacktest: async (id) => {
        set({ loading: true, error: null })
        try {
          const result = await backtestApi.getBacktest(id)
          set({ currentBacktest: result, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to fetch backtest',
            loading: false 
          })
        }
      },
      
      refreshBacktest: async (id) => {
        try {
          const result = await backtestApi.getBacktest(id)
          set(state => ({
            backtests: state.backtests.map(bt => bt.id === id ? result : bt),
            currentBacktest: state.currentBacktest?.id === id ? result : state.currentBacktest
          }))
        } catch (error) {
          console.error('Failed to refresh backtest:', error)
        }
      },
      
      deleteBacktest: async (id) => {
        set({ loading: true, error: null })
        try {
          await backtestApi.deleteBacktest(id)
          set(state => ({
            backtests: state.backtests.filter(bt => bt.id !== id),
            currentBacktest: state.currentBacktest?.id === id ? null : state.currentBacktest,
            loading: false
          }))
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to delete backtest',
            loading: false 
          })
        }
      },
      
      // 回测创建和控制
      createBacktest: async (config) => {
        set({ isCreatingBacktest: true, error: null })
        try {
          const result = await backtestApi.createBacktest(config)
          set(state => ({
            backtests: [result, ...state.backtests],
            currentBacktest: result,
            isCreatingBacktest: false
          }))
          
          // 开始轮询状态
          if (result.status === 'running') {
            get().pollBacktestStatus(result.id)
          }
          
          return result
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to create backtest',
            isCreatingBacktest: false 
          })
          return null
        }
      },
      
      stopBacktest: async (id) => {
        try {
          await backtestApi.stopBacktest(id)
          // 更新本地状态
          set(state => ({
            backtests: state.backtests.map(bt => 
              bt.id === id ? { ...bt, status: 'failed' as const } : bt
            ),
            currentBacktest: state.currentBacktest?.id === id 
              ? { ...state.currentBacktest, status: 'failed' as const }
              : state.currentBacktest
          }))
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to stop backtest'
          })
        }
      },
      
      updateBacktestForm: (field, value) => {
        set(state => ({
          configForm: { ...state.configForm, [field]: value }
        }))
      },
      
      resetBacktestForm: () => {
        set({ configForm: defaultConfigForm })
      },
      
      // 实时状态监控
      updateBacktestStatus: (id, status, progress) => {
        set(state => ({
          runningBacktests: new Map(state.runningBacktests).set(id, { status, progress })
        }))
      },
      
      pollBacktestStatus: async (id) => {
        const pollInterval = 3000 // 3秒轮询一次
        
        const poll = async () => {
          try {
            const statusInfo = await backtestApi.getBacktestStatus(id)
            get().updateBacktestStatus(id, statusInfo.status, statusInfo.progress)
            
            // 如果回测完成，获取完整结果并停止轮询
            if (statusInfo.status === 'completed' || statusInfo.status === 'failed') {
              get().refreshBacktest(id)
              return
            }
            
            // 继续轮询
            setTimeout(poll, pollInterval)
          } catch (error) {
            console.error('Failed to poll backtest status:', error)
            // 出错后停止轮询
          }
        }
        
        poll()
      },
      
      // 回测比较功能
      toggleComparisonSelection: (id) => {
        set(state => ({
          selectedForComparison: state.selectedForComparison.includes(id)
            ? state.selectedForComparison.filter(selectedId => selectedId !== id)
            : [...state.selectedForComparison, id].slice(0, 5) // 最多选择5个
        }))
      },
      
      compareBacktests: async () => {
        const { selectedForComparison } = get()
        if (selectedForComparison.length < 2) return
        
        set({ loading: true, error: null })
        try {
          const result = await backtestApi.compareBacktests(selectedForComparison)
          set({ comparisonResult: result, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to compare backtests',
            loading: false 
          })
        }
      },
      
      clearComparison: () => {
        set({ selectedForComparison: [], comparisonResult: null })
      },
      
      // 报告下载
      downloadReport: async (id, format = 'html') => {
        try {
          const blob = await backtestApi.downloadBacktestReport(id, format)
          
          // 创建下载链接
          const url = window.URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = `backtest-report-${id}.${format}`
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          window.URL.revokeObjectURL(url)
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to download report'
          })
        }
      },
      
      // 状态管理
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),
      reset: () => set({
        backtests: [],
        currentBacktest: null,
        loading: false,
        error: null,
        configForm: defaultConfigForm,
        isCreatingBacktest: false,
        runningBacktests: new Map(),
        selectedForComparison: [],
        comparisonResult: null,
        pagination: {
          page: 1,
          per_page: 10,
          total: 0,
          total_pages: 0
        },
        filters: {}
      })
    }),
    {
      name: 'backtest-store',
      // 只持久化配置表单和选择状态，其他状态每次重新加载
      partialize: (state) => ({
        configForm: state.configForm,
        selectedForComparison: state.selectedForComparison
      })
    }
  )
)

// 便捷的选择器hooks
export const useBacktestList = () => useBacktestStore(state => ({
  backtests: state.backtests,
  loading: state.loading,
  error: state.error,
  pagination: state.pagination,
  fetchBacktests: state.fetchBacktests,
  deleteBacktest: state.deleteBacktest,
  downloadReport: state.downloadReport
}))

export const useBacktestCreation = () => useBacktestStore(state => ({
  configForm: state.configForm,
  isCreatingBacktest: state.isCreatingBacktest,
  createBacktest: state.createBacktest,
  updateBacktestForm: state.updateBacktestForm,
  resetBacktestForm: state.resetBacktestForm
}))

export const useBacktestComparison = () => useBacktestStore(state => ({
  selectedForComparison: state.selectedForComparison,
  comparisonResult: state.comparisonResult,
  toggleComparisonSelection: state.toggleComparisonSelection,
  compareBacktests: state.compareBacktests,
  clearComparison: state.clearComparison
}))

export const useCurrentBacktest = () => useBacktestStore(state => ({
  currentBacktest: state.currentBacktest,
  loading: state.loading,
  error: state.error,
  fetchBacktest: state.fetchBacktest,
  refreshBacktest: state.refreshBacktest,
  stopBacktest: state.stopBacktest,
  runningBacktests: state.runningBacktests
}))