import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { 
  strategyTemplatesApi, 
  StrategyTemplate, 
  TemplateListResponse, 
  TemplateCategory, 
  TemplateDifficulty, 
  TemplateTimeframe,
  TemplatePreview,
  CustomizationResult
} from '../services/api/strategyTemplates'

interface StrategyTemplatesState {
  // 模板列表
  templates: StrategyTemplate[]
  currentTemplate: StrategyTemplate | null
  loading: boolean
  error: string | null

  // 分类和筛选
  categories: TemplateCategory[]
  difficulties: TemplateDifficulty[]
  timeframes: TemplateTimeframe[]
  
  // 筛选条件
  filters: {
    category?: string
    difficulty?: string
    search?: string
  }

  // 预览和自定义
  previewResult: TemplatePreview | null
  customizationResult: CustomizationResult | null
  customParameters: Record<string, any>

  // 模板应用
  isApplying: boolean
  appliedTemplates: string[] // 已应用的模板ID

  // Actions - 基础操作
  fetchTemplates: (params?: { category?: string; difficulty?: string; search?: string }) => Promise<void>
  fetchTemplateDetail: (templateId: string, includeCode?: boolean) => Promise<void>
  fetchTemplateCode: (templateId: string) => Promise<string>

  // Actions - 筛选和搜索
  setFilter: (key: string, value: string | undefined) => void
  clearFilters: () => void
  searchTemplates: (keyword: string) => Promise<void>

  // Actions - 自定义和预览
  customizeParameters: (templateId: string, parameters: Record<string, any>) => Promise<void>
  previewBacktest: (templateId: string, parameters?: Record<string, any>, symbol?: string, timeframe?: string) => Promise<void>
  setCustomParameter: (key: string, value: any) => void
  resetCustomParameters: () => void

  // Actions - 应用模板
  applyTemplate: (templateId: string, customName?: string, customDescription?: string) => Promise<boolean>
  
  // Actions - 状态管理
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearError: () => void
  reset: () => void
}

export const useStrategyTemplatesStore = create<StrategyTemplatesState>()(
  persist(
    (set, get) => ({
      // 初始状态
      templates: [],
      currentTemplate: null,
      loading: false,
      error: null,
      
      categories: [],
      difficulties: [],
      timeframes: [],
      
      filters: {},
      
      previewResult: null,
      customizationResult: null,
      customParameters: {},
      
      isApplying: false,
      appliedTemplates: [],

      // 基础操作
      fetchTemplates: async (params) => {
        set({ loading: true, error: null })
        try {
          const response: TemplateListResponse = await strategyTemplatesApi.getTemplates(params)
          set({
            templates: response.templates,
            categories: response.categories,
            difficulties: response.difficulties,
            timeframes: response.timeframes,
            loading: false
          })
          
          // 更新筛选条件
          if (params) {
            set(state => ({
              filters: { ...state.filters, ...params }
            }))
          }
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch templates',
            loading: false
          })
        }
      },

      fetchTemplateDetail: async (templateId, includeCode = false) => {
        set({ loading: true, error: null })
        try {
          const response = await strategyTemplatesApi.getTemplateDetail(templateId, includeCode)
          set({
            currentTemplate: response.template,
            loading: false
          })
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch template detail',
            loading: false
          })
        }
      },

      fetchTemplateCode: async (templateId) => {
        try {
          const response = await strategyTemplatesApi.getTemplateCode(templateId)
          return response.code
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch template code'
          })
          return ''
        }
      },

      // 筛选和搜索
      setFilter: (key, value) => {
        set(state => ({
          filters: { ...state.filters, [key]: value }
        }))
        
        // 自动重新获取数据
        get().fetchTemplates(get().filters)
      },

      clearFilters: () => {
        set({ filters: {} })
        get().fetchTemplates()
      },

      searchTemplates: async (keyword) => {
        set({ loading: true, error: null })
        try {
          const response = await strategyTemplatesApi.searchTemplates(keyword)
          set({
            templates: response.templates,
            loading: false,
            filters: { search: keyword }
          })
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Search failed',
            loading: false
          })
        }
      },

      // 自定义和预览
      customizeParameters: async (templateId, parameters) => {
        set({ loading: true, error: null })
        try {
          const result = await strategyTemplatesApi.customizeParameters(templateId, parameters)
          set({
            customizationResult: result,
            customParameters: result.parameters,
            loading: false
          })
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Parameter customization failed',
            loading: false
          })
        }
      },

      previewBacktest: async (templateId, parameters, symbol, timeframe) => {
        set({ loading: true, error: null })
        try {
          const result = await strategyTemplatesApi.previewBacktest(templateId, parameters, symbol, timeframe)
          set({
            previewResult: result,
            loading: false
          })
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Preview failed',
            loading: false
          })
        }
      },

      setCustomParameter: (key, value) => {
        set(state => ({
          customParameters: { ...state.customParameters, [key]: value }
        }))
      },

      resetCustomParameters: () => {
        set({ customParameters: {}, customizationResult: null, previewResult: null })
      },

      // 应用模板
      applyTemplate: async (templateId, customName, customDescription) => {
        set({ isApplying: true, error: null })
        try {
          const response = await strategyTemplatesApi.applyTemplate(
            templateId, 
            customName, 
            customDescription, 
            get().customParameters
          )
          
          if (response.success) {
            set(state => ({
              appliedTemplates: [...state.appliedTemplates, templateId],
              isApplying: false
            }))
            return true
          } else {
            set({ 
              error: response.message || 'Failed to apply template',
              isApplying: false 
            })
            return false
          }
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to apply template',
            isApplying: false
          })
          return false
        }
      },

      // 状态管理
      setLoading: (loading) => set({ loading }),
      
      setError: (error) => set({ error }),
      
      clearError: () => set({ error: null }),
      
      reset: () => set({
        templates: [],
        currentTemplate: null,
        loading: false,
        error: null,
        filters: {},
        previewResult: null,
        customizationResult: null,
        customParameters: {},
        isApplying: false
      })
    }),
    {
      name: 'strategy-templates-store',
      // 只持久化已应用的模板和自定义参数
      partialize: (state) => ({
        appliedTemplates: state.appliedTemplates,
        customParameters: state.customParameters,
        filters: state.filters
      })
    }
  )
)

// 便捷选择器 hooks
export const useTemplatesList = () => useStrategyTemplatesStore(state => ({
  templates: state.templates,
  categories: state.categories,
  difficulties: state.difficulties,
  timeframes: state.timeframes,
  loading: state.loading,
  error: state.error,
  filters: state.filters,
  fetchTemplates: state.fetchTemplates,
  setFilter: state.setFilter,
  clearFilters: state.clearFilters,
  searchTemplates: state.searchTemplates
}))

export const useTemplateDetail = () => useStrategyTemplatesStore(state => ({
  currentTemplate: state.currentTemplate,
  loading: state.loading,
  error: state.error,
  fetchTemplateDetail: state.fetchTemplateDetail,
  fetchTemplateCode: state.fetchTemplateCode
}))

export const useTemplateCustomization = () => useStrategyTemplatesStore(state => ({
  customParameters: state.customParameters,
  customizationResult: state.customizationResult,
  previewResult: state.previewResult,
  loading: state.loading,
  error: state.error,
  customizeParameters: state.customizeParameters,
  previewBacktest: state.previewBacktest,
  setCustomParameter: state.setCustomParameter,
  resetCustomParameters: state.resetCustomParameters
}))

export const useTemplateApplication = () => useStrategyTemplatesStore(state => ({
  isApplying: state.isApplying,
  appliedTemplates: state.appliedTemplates,
  error: state.error,
  applyTemplate: state.applyTemplate
}))