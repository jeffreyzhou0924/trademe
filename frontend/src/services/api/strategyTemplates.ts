/**
 * ⚠️ 策略模板功能已暂时禁用
 * 
 * 原因：项目设计初期没有考虑这个功能，现已隐藏相关入口
 * 状态：代码保留但不使用，相关路由和导航已注释
 * 
 * 如需启用：
 * 1. 取消注释 App.tsx 中的路由配置
 * 2. 取消注释 MainLayout.tsx 中的导航菜单项
 * 3. 取消注释后端 API 路由注册
 */

import { tradingServiceClient, handleApiResponse, handleApiError } from './client'

// 策略模板相关接口定义
export interface StrategyTemplate {
  id: string
  name: string
  description: string
  category: string
  difficulty: string
  timeframe: string
  tags: string[]
  risk_level: string
  expected_return: string
  max_drawdown: string
  author: string
  created_at: string
  parameters: Record<string, any>
  code?: string
}

export interface TemplateCategory {
  id: string
  name: string
  description: string
}

export interface TemplateDifficulty {
  id: string
  name: string
  description: string
}

export interface TemplateTimeframe {
  id: string
  name: string
  description: string
}

export interface TemplateListResponse {
  templates: StrategyTemplate[]
  total: number
  categories: TemplateCategory[]
  difficulties: TemplateDifficulty[]
  timeframes: TemplateTimeframe[]
}

export interface TemplateDetailResponse {
  template: StrategyTemplate
  success: boolean
}

export interface TemplatePreview {
  template_id: string
  template_name: string
  symbol: string
  timeframe: string
  parameters: Record<string, any>
  theoretical_metrics: {
    expected_annual_return: string
    max_drawdown: string
    risk_level: string
    win_rate: string
    profit_factor: string
    sharpe_ratio: string
  }
  suitable_market: string[]
  warnings: string[]
  recommendations: string[]
}

export interface CustomizationResult {
  template_id: string
  parameters: Record<string, any>
  validation_errors: string[]
  is_valid: boolean
  estimated_performance: {
    risk_level: string
    expected_return: string
    max_drawdown: string
  }
}

// 策略模板API服务
export const strategyTemplatesApi = {
  // 获取策略模板列表
  async getTemplates(params?: {
    category?: string
    difficulty?: string
    search?: string
    limit?: number
  }): Promise<TemplateListResponse> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/', { 
        params 
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取策略模板详情
  async getTemplateDetail(
    templateId: string, 
    includeCode: boolean = false
  ): Promise<TemplateDetailResponse> {
    try {
      const response = await tradingServiceClient.get(`/strategy-templates/${templateId}`, {
        params: { include_code: includeCode }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取策略模板代码
  async getTemplateCode(templateId: string): Promise<{
    template_id: string
    name: string
    code: string
    parameters: Record<string, any>
    description: string
  }> {
    try {
      const response = await tradingServiceClient.get(`/strategy-templates/${templateId}/code`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 应用策略模板创建策略
  async applyTemplate(
    templateId: string,
    customName?: string,
    customDescription?: string,
    customParameters?: Record<string, any>
  ): Promise<{
    strategy: any
    template_id: string
    message: string
    success: boolean
  }> {
    try {
      const response = await tradingServiceClient.post(`/strategy-templates/${templateId}/apply`, {
        custom_name: customName,
        custom_description: customDescription,
        custom_parameters: customParameters
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取分类列表
  async getCategories(): Promise<{
    categories: TemplateCategory[]
    total: number
  }> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/categories/list')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取难度级别列表
  async getDifficulties(): Promise<{
    difficulties: TemplateDifficulty[]
    total: number
  }> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/difficulties/list')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 获取时间周期列表
  async getTimeframes(): Promise<{
    timeframes: TemplateTimeframe[]
    total: number
  }> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/timeframes/list')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 自定义模板参数
  async customizeParameters(
    templateId: string,
    parameters: Record<string, any>
  ): Promise<CustomizationResult> {
    try {
      const response = await tradingServiceClient.post(`/strategy-templates/${templateId}/customize`, parameters)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 预览模板回测效果
  async previewBacktest(
    templateId: string,
    parameters?: Record<string, any>,
    symbol: string = 'BTC/USDT',
    timeframe: string = '1h'
  ): Promise<TemplatePreview> {
    try {
      const params: any = { symbol, timeframe }
      if (parameters) {
        params.parameters = JSON.stringify(parameters)
      }
      
      const response = await tradingServiceClient.get(`/strategy-templates/${templateId}/backtest-preview`, {
        params
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 搜索模板
  async searchTemplates(keyword: string, limit: number = 10): Promise<TemplateListResponse> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/', {
        params: { search: keyword, limit }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 根据分类筛选
  async getTemplatesByCategory(category: string): Promise<TemplateListResponse> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/', {
        params: { category }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  },

  // 根据难度筛选
  async getTemplatesByDifficulty(difficulty: string): Promise<TemplateListResponse> {
    try {
      const response = await tradingServiceClient.get('/strategy-templates/', {
        params: { difficulty }
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error)
    }
  }
}