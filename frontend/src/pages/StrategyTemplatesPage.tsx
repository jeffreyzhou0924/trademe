import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  useTemplatesList, 
  useTemplateDetail, 
  useTemplateCustomization, 
  useTemplateApplication 
} from '../store/strategyTemplatesStore'
import { strategyTemplatesApi, StrategyTemplate } from '../services/api/strategyTemplates'
import { Button, LoadingSpinner } from '../components/common'
import { formatDateTime } from '../utils/format'
import toast from 'react-hot-toast'

const StrategyTemplatesPage: React.FC = () => {
  const navigate = useNavigate()
  
  // Store hooks
  const {
    templates,
    categories,
    difficulties,
    timeframes,
    loading,
    error,
    filters,
    fetchTemplates,
    setFilter,
    clearFilters,
    searchTemplates
  } = useTemplatesList()
  
  const {
    currentTemplate,
    fetchTemplateDetail,
    fetchTemplateCode
  } = useTemplateDetail()
  
  const {
    customParameters,
    customizationResult,
    previewResult,
    customizeParameters,
    previewBacktest,
    setCustomParameter,
    resetCustomParameters
  } = useTemplateCustomization()
  
  const {
    isApplying,
    appliedTemplates,
    applyTemplate
  } = useTemplateApplication()
  
  // Local state
  const [selectedTemplate, setSelectedTemplate] = useState<StrategyTemplate | null>(null)
  const [showTemplateDetail, setShowTemplateDetail] = useState(false)
  const [showCustomization, setShowCustomization] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [customName, setCustomName] = useState('')
  const [customDescription, setCustomDescription] = useState('')

  // Load templates on mount
  useEffect(() => {
    fetchTemplates()
  }, [])

  // Handle template selection
  const handleTemplateSelect = async (template: StrategyTemplate) => {
    setSelectedTemplate(template)
    await fetchTemplateDetail(template.id, false)
    setShowTemplateDetail(true)
  }

  // Handle search
  const handleSearch = async () => {
    if (searchQuery.trim()) {
      await searchTemplates(searchQuery.trim())
    } else {
      await fetchTemplates()
    }
  }

  // Handle filter change
  const handleFilterChange = (filterType: string, value: string) => {
    if (value === 'all') {
      setFilter(filterType, undefined)
    } else {
      setFilter(filterType, value)
    }
  }

  // Handle template application
  const handleApplyTemplate = async () => {
    if (!selectedTemplate) return
    
    const success = await applyTemplate(
      selectedTemplate.id,
      customName || `${selectedTemplate.name} - 我的版本`,
      customDescription || selectedTemplate.description
    )
    
    if (success) {
      toast.success('策略模板应用成功！')
      setShowCustomization(false)
      setShowTemplateDetail(false)
      setSelectedTemplate(null)
      resetCustomParameters()
      setCustomName('')
      setCustomDescription('')
      // 跳转到策略管理页面
      navigate('/strategies')
    }
  }

  // Handle customization
  const handleStartCustomization = () => {
    if (!selectedTemplate) return
    
    setShowCustomization(true)
    setCustomName(`${selectedTemplate.name} - 自定义`)
    setCustomDescription(selectedTemplate.description)
    
    // 初始化自定义参数
    Object.entries(selectedTemplate.parameters || {}).forEach(([key, value]) => {
      setCustomParameter(key, value)
    })
  }

  // Handle parameter customization
  const handleCustomizeParameters = async () => {
    if (!selectedTemplate) return
    
    await customizeParameters(selectedTemplate.id, customParameters)
  }

  // Handle preview
  const handlePreviewBacktest = async () => {
    if (!selectedTemplate) return
    
    await previewBacktest(selectedTemplate.id, customParameters)
  }

  // Get difficulty color
  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case '入门': return 'bg-green-100 text-green-800'
      case '中级': return 'bg-yellow-100 text-yellow-800' 
      case '高级': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  // Get risk level color
  const getRiskLevelColor = (riskLevel: string) => {
    if (riskLevel?.includes('低')) return 'text-green-600'
    if (riskLevel?.includes('中')) return 'text-yellow-600'
    if (riskLevel?.includes('高')) return 'text-red-600'
    return 'text-gray-600'
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">策略模板库</h1>
          <p className="text-gray-600 mt-1">选择并自定义专业的交易策略模板</p>
        </div>
        <Button
          onClick={() => navigate('/strategies')}
          variant="outline"
          className="px-4 py-2"
        >
          我的策略
        </Button>
      </div>

      {/* 搜索和筛选 */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {/* 搜索框 */}
          <div className="md:col-span-2">
            <div className="flex space-x-2">
              <input
                type="text"
                placeholder="搜索策略模板..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <Button
                onClick={handleSearch}
                variant="primary"
                size="sm"
              >
                搜索
              </Button>
            </div>
          </div>

          {/* 分类筛选 */}
          <div>
            <select
              value={filters.category || 'all'}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">所有分类</option>
              {categories.map(category => (
                <option key={category.id} value={category.name}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>

          {/* 难度筛选 */}
          <div>
            <select
              value={filters.difficulty || 'all'}
              onChange={(e) => handleFilterChange('difficulty', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">所有难度</option>
              {difficulties.map(difficulty => (
                <option key={difficulty.id} value={difficulty.name}>
                  {difficulty.name}
                </option>
              ))}
            </select>
          </div>

          {/* 清除筛选 */}
          <div>
            <Button
              onClick={clearFilters}
              variant="outline"
              className="w-full"
            >
              清除筛选
            </Button>
          </div>
        </div>
      </div>

      {/* 模板列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <div className="col-span-full flex items-center justify-center py-12">
            <LoadingSpinner />
            <span className="ml-2 text-gray-600">加载模板中...</span>
          </div>
        ) : templates.length === 0 ? (
          <div className="col-span-full text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">暂无模板</h3>
            <p className="text-gray-500">没有找到符合条件的策略模板</p>
          </div>
        ) : (
          templates.map((template) => (
            <div
              key={template.id}
              className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-200 cursor-pointer"
              onClick={() => handleTemplateSelect(template)}
            >
              {/* 模板头部 */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 mb-1">{template.name}</h3>
                  <p className="text-sm text-gray-600 line-clamp-2">{template.description}</p>
                </div>
                {appliedTemplates.includes(template.id) && (
                  <span className="ml-2 inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    已应用
                  </span>
                )}
              </div>

              {/* 标签 */}
              <div className="flex flex-wrap gap-2 mb-4">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getDifficultyColor(template.difficulty)}`}>
                  {template.difficulty}
                </span>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                  {template.category}
                </span>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                  {template.timeframe}
                </span>
              </div>

              {/* 性能指标 */}
              <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                <div>
                  <span className="text-gray-500">预期收益:</span>
                  <p className="font-medium text-green-600">{template.expected_return}</p>
                </div>
                <div>
                  <span className="text-gray-500">最大回撤:</span>
                  <p className="font-medium text-red-600">{template.max_drawdown}</p>
                </div>
                <div>
                  <span className="text-gray-500">风险级别:</span>
                  <p className={`font-medium ${getRiskLevelColor(template.risk_level)}`}>{template.risk_level}</p>
                </div>
                <div>
                  <span className="text-gray-500">作者:</span>
                  <p className="font-medium text-gray-900">{template.author}</p>
                </div>
              </div>

              {/* 标签列表 */}
              <div className="flex flex-wrap gap-1">
                {template.tags?.slice(0, 3).map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2 py-1 rounded text-xs bg-blue-50 text-blue-600"
                  >
                    {tag}
                  </span>
                ))}
                {(template.tags?.length || 0) > 3 && (
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-50 text-gray-600">
                    +{(template.tags?.length || 0) - 3}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 模板详情弹窗 */}
      {showTemplateDetail && selectedTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            {/* 弹窗头部 */}
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900">{selectedTemplate.name}</h2>
                <p className="text-gray-600 mt-1">{selectedTemplate.description}</p>
              </div>
              <button
                onClick={() => {
                  setShowTemplateDetail(false)
                  setSelectedTemplate(null)
                  resetCustomParameters()
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* 弹窗内容 */}
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 左侧：模板信息 */}
                <div className="space-y-4">
                  {/* 基本信息 */}
                  <div className="bg-gray-50 rounded-xl p-4">
                    <h3 className="font-medium text-gray-900 mb-3">基本信息</h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">分类:</span>
                        <p className="font-medium">{selectedTemplate.category}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">难度:</span>
                        <p className="font-medium">{selectedTemplate.difficulty}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">时间周期:</span>
                        <p className="font-medium">{selectedTemplate.timeframe}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">风险级别:</span>
                        <p className={`font-medium ${getRiskLevelColor(selectedTemplate.risk_level)}`}>
                          {selectedTemplate.risk_level}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 性能预期 */}
                  <div className="bg-gray-50 rounded-xl p-4">
                    <h3 className="font-medium text-gray-900 mb-3">性能预期</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">预期年化收益:</span>
                        <span className="font-medium text-green-600">{selectedTemplate.expected_return}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">最大回撤:</span>
                        <span className="font-medium text-red-600">{selectedTemplate.max_drawdown}</span>
                      </div>
                    </div>
                  </div>

                  {/* 标签 */}
                  <div>
                    <h3 className="font-medium text-gray-900 mb-3">标签</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedTemplate.tags?.map((tag, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 右侧：参数配置 */}
                <div className="space-y-4">
                  <div className="bg-gray-50 rounded-xl p-4">
                    <h3 className="font-medium text-gray-900 mb-3">默认参数</h3>
                    <div className="space-y-2 text-sm">
                      {Object.entries(selectedTemplate.parameters || {}).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-gray-500">{key}:</span>
                          <span className="font-medium">{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 弹窗底部 */}
            <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-100">
              <Button
                onClick={() => {
                  setShowTemplateDetail(false)
                  setSelectedTemplate(null)
                }}
                variant="outline"
              >
                取消
              </Button>
              <Button
                onClick={handleStartCustomization}
                variant="primary"
              >
                自定义应用
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 自定义参数弹窗 */}
      {showCustomization && selectedTemplate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            {/* 弹窗头部 */}
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <div>
                <h2 className="text-xl font-bold text-gray-900">自定义策略模板</h2>
                <p className="text-gray-600 mt-1">{selectedTemplate.name}</p>
              </div>
              <button
                onClick={() => {
                  setShowCustomization(false)
                  resetCustomParameters()
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* 自定义表单 */}
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 左侧：基本设置 */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      策略名称
                    </label>
                    <input
                      type="text"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="输入自定义策略名称"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      策略描述
                    </label>
                    <textarea
                      value={customDescription}
                      onChange={(e) => setCustomDescription(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="输入策略描述"
                    />
                  </div>

                  {/* 参数配置 */}
                  <div>
                    <h3 className="font-medium text-gray-900 mb-3">参数配置</h3>
                    <div className="space-y-3">
                      {Object.entries(selectedTemplate.parameters || {}).map(([key, defaultValue]) => (
                        <div key={key}>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            {key}
                          </label>
                          <input
                            type={typeof defaultValue === 'number' ? 'number' : 'text'}
                            value={customParameters[key] ?? defaultValue}
                            onChange={(e) => {
                              const value = typeof defaultValue === 'number' 
                                ? parseFloat(e.target.value) || 0
                                : e.target.value
                              setCustomParameter(key, value)
                            }}
                            step={typeof defaultValue === 'number' ? 'any' : undefined}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 右侧：预览和验证 */}
                <div className="space-y-4">
                  {/* 参数验证结果 */}
                  {customizationResult && (
                    <div className="bg-gray-50 rounded-xl p-4">
                      <h3 className="font-medium text-gray-900 mb-3">参数验证</h3>
                      {customizationResult.is_valid ? (
                        <div className="text-green-600 text-sm">
                          <svg className="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          参数验证通过
                        </div>
                      ) : (
                        <div className="text-red-600 text-sm space-y-1">
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                            参数验证失败
                          </div>
                          {customizationResult.validation_errors.map((error, index) => (
                            <div key={index} className="ml-5 text-xs">{error}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 预览结果 */}
                  {previewResult && (
                    <div className="bg-gray-50 rounded-xl p-4">
                      <h3 className="font-medium text-gray-900 mb-3">回测预览</h3>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500">预期年化收益:</span>
                          <span className="font-medium text-green-600">
                            {previewResult.theoretical_metrics.expected_annual_return}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">胜率:</span>
                          <span className="font-medium">
                            {previewResult.theoretical_metrics.win_rate}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">夏普比率:</span>
                          <span className="font-medium">
                            {previewResult.theoretical_metrics.sharpe_ratio}
                          </span>
                        </div>
                      </div>

                      {/* 警告信息 */}
                      {previewResult.warnings.length > 0 && (
                        <div className="mt-3 p-3 bg-yellow-50 rounded-lg">
                          <h4 className="text-sm font-medium text-yellow-800 mb-1">注意事项</h4>
                          <ul className="text-xs text-yellow-700 space-y-1">
                            {previewResult.warnings.map((warning, index) => (
                              <li key={index}>• {warning}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* 建议信息 */}
                      {previewResult.recommendations.length > 0 && (
                        <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                          <h4 className="text-sm font-medium text-blue-800 mb-1">优化建议</h4>
                          <ul className="text-xs text-blue-700 space-y-1">
                            {previewResult.recommendations.slice(0, 3).map((rec, index) => (
                              <li key={index}>• {rec}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 操作按钮 */}
                  <div className="space-y-2">
                    <Button
                      onClick={handleCustomizeParameters}
                      variant="outline"
                      className="w-full"
                      disabled={loading}
                    >
                      验证参数
                    </Button>
                    <Button
                      onClick={handlePreviewBacktest}
                      variant="outline"
                      className="w-full"
                      disabled={loading}
                    >
                      预览回测
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {/* 弹窗底部 */}
            <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-100">
              <Button
                onClick={() => {
                  setShowCustomization(false)
                  resetCustomParameters()
                }}
                variant="outline"
              >
                取消
              </Button>
              <Button
                onClick={handleApplyTemplate}
                variant="primary"
                disabled={isApplying || !customName.trim()}
              >
                {isApplying ? '应用中...' : '创建策略'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-50 border border-red-200 rounded-lg p-4 max-w-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                操作失败
              </h3>
              <div className="mt-2 text-sm text-red-700">
                {error}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default StrategyTemplatesPage