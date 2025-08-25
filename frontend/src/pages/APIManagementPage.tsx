import React, { useState, useEffect } from 'react'
import { useUserInfo } from '../store'
import { useLanguageStore } from '../store/languageStore'
import toast from 'react-hot-toast'
import { getAuthToken } from '../utils/auth'

interface APIKey {
  id: number
  name: string
  exchange: string
  api_key: string
  permissions: string
  status: 'active' | 'inactive' | 'error'
  created_at: string
}

const APIManagementPage: React.FC = () => {
  const { user, isPremium } = useUserInfo()
  const { t } = useLanguageStore()
  
  // 表单状态
  const [formData, setFormData] = useState({
    name: '',
    exchange: 'okx',
    api_key: '',
    secret_key: '',
    passphrase: ''
  })
  
  // API密钥列表
  const [apiKeys, setApiKeys] = useState<APIKey[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  
  // 显示状态
  const [showSecrets, setShowSecrets] = useState<{[key: number]: boolean}>({})

  // 支持的交易所
  const exchanges = [
    { value: 'okx', label: 'OKX', icon: '🟢' },
    { value: 'binance', label: 'Binance', icon: '🟡' },
    { value: 'huobi', label: 'Huobi', icon: '🔴' },
    { value: 'bybit', label: 'Bybit', icon: '🟠' },
    { value: 'kraken', label: 'Kraken', icon: '🟣' },
    { value: 'coinbase', label: 'Coinbase', icon: '🔵' }
  ]

  // 加载API密钥列表
  const loadAPIKeys = async () => {
    if (!isPremium) return
    
    try {
      setLoading(true)
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/api-keys/`, {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        let data = { api_keys: [] }
        try {
          const text = await response.text()
          data = text ? JSON.parse(text) : { api_keys: [] }
        } catch (e) {
          console.log('Response is not JSON, using empty array')
        }
        setApiKeys(data.api_keys || [])
      } else {
        let errorMessage = 'Failed to load API keys'
        try {
          const text = await response.text()
          const errorData = text ? JSON.parse(text) : null
          errorMessage = errorData?.detail || `HTTP ${response.status}: ${response.statusText}`
        } catch (e) {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`
        }
        throw new Error(errorMessage)
      }
    } catch (error) {
      console.error('Error loading API keys:', error)
      toast.error('加载API密钥失败')
    } finally {
      setLoading(false)
    }
  }

  // 添加API密钥
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!isPremium) {
      toast.error('添加API密钥需要高级版本')
      return
    }
    
    if (!formData.api_key || !formData.secret_key || !formData.name) {
      toast.error('请填写完整的信息')
      return
    }
    
    try {
      setSubmitting(true)
      
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/api-keys/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify({
          name: formData.name,
          exchange: formData.exchange,
          api_key: formData.api_key,
          secret_key: formData.secret_key,
          passphrase: formData.passphrase || undefined
        })
      })
      
      if (response.ok) {
        let data = null
        try {
          const text = await response.text()
          data = text ? JSON.parse(text) : {}
        } catch (e) {
          console.log('Response is not JSON, treating as success')
        }
        toast.success('API密钥添加成功')
        
        // 重置表单
        setFormData({
          name: '',
          exchange: 'okx',
          api_key: '',
          secret_key: '',
          passphrase: ''
        })
        
        // 重新加载列表
        loadAPIKeys()
      } else {
        let errorData = { detail: 'Unknown error' }
        try {
          const text = await response.text()
          errorData = text ? JSON.parse(text) : { detail: `HTTP ${response.status}: ${response.statusText}` }
        } catch (e) {
          errorData = { detail: `HTTP ${response.status}: ${response.statusText}` }
        }
        throw new Error(errorData.detail || 'Failed to add API key')
      }
    } catch (error) {
      console.error('Error adding API key:', error)
      toast.error(`添加API密钥失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setSubmitting(false)
    }
  }

  // 删除API密钥
  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`确定要删除API密钥 "${name}" 吗？`)) {
      return
    }
    
    try {
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/api-keys/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        toast.success('API密钥删除成功')
        loadAPIKeys()
      } else {
        throw new Error('Failed to delete API key')
      }
    } catch (error) {
      console.error('Error deleting API key:', error)
      toast.error('删除API密钥失败')
    }
  }

  // 测试API密钥连接
  const handleTest = async (id: number, name: string) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/api-keys/${id}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        toast.success(`${name} 连接测试成功`)
      } else {
        const errorData = await response.json()
        toast.error(`${name} 连接测试失败: ${errorData.detail}`)
      }
    } catch (error) {
      console.error('Error testing API key:', error)
      toast.error('连接测试失败')
    }
  }

  // 切换密钥显示
  const toggleShowSecret = (id: number) => {
    setShowSecrets(prev => ({
      ...prev,
      [id]: !prev[id]
    }))
  }

  // 获取状态标识
  const getStatusIndicator = (status: string) => {
    switch (status) {
      case 'active':
        return <div className="w-2 h-2 bg-green-500 rounded-full"></div>
      case 'inactive':
        return <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
      case 'error':
        return <div className="w-2 h-2 bg-red-500 rounded-full"></div>
      default:
        return <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '有效'
      case 'inactive': return '无效'
      case 'error': return '错误'
      default: return '未知'
    }
  }

  // 填充测试数据
  const fillTestData = () => {
    setFormData({
      name: 'OKX测试账户',
      exchange: 'okx',
      api_key: '76ba9b3a-38b6-4ed3-9ce7-44d603188b13',
      secret_key: '4021858325F5A3BEC3F64B6D0533E412',
      passphrase: 'Woaiziji..123'
    })
    toast.info('已填充OKX测试数据')
  }

  useEffect(() => {
    loadAPIKeys()
  }, [isPremium])

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API密钥管理</h1>
          <p className="text-gray-600 mt-1">管理您的交易所API密钥，确保安全可靠的交易连接</p>
        </div>
        <div className="text-sm text-gray-500">
          {isPremium ? `高级版最多可添加5个API密钥 (已使用${apiKeys.length}/5)` : '升级到高级版以添加API密钥'}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：添加API密钥 */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">新增API密钥</h2>
            <button
              onClick={fillTestData}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium px-3 py-1 rounded-md hover:bg-blue-50 transition-colors"
            >
              填充测试数据
            </button>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">交易所</label>
              <select
                value={formData.exchange}
                onChange={(e) => setFormData({...formData, exchange: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white text-sm"
              >
                {exchanges.map(exchange => (
                  <option key={exchange.value} value={exchange.value}>
                    {exchange.icon} {exchange.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">API名称</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                placeholder="例如：OKX现货账户"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">公钥 (API KEY)</label>
              <input
                type="text"
                value={formData.api_key}
                onChange={(e) => setFormData({...formData, api_key: e.target.value})}
                placeholder="输入API公钥"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm font-mono"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">密钥 (SECRET KEY)</label>
              <input
                type="password"
                value={formData.secret_key}
                onChange={(e) => setFormData({...formData, secret_key: e.target.value})}
                placeholder="输入API密钥"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm font-mono"
              />
            </div>

            {(formData.exchange === 'okx' || formData.exchange === 'bybit') && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  密码短语 {formData.exchange === 'okx' ? '(Passphrase)' : '(可选)'}
                </label>
                <input
                  type="password"
                  value={formData.passphrase}
                  onChange={(e) => setFormData({...formData, passphrase: e.target.value})}
                  placeholder={formData.exchange === 'okx' ? '输入Passphrase密码' : '输入密码短语(可选)'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={!isPremium || submitting}
              className={`w-full py-3 rounded-lg font-medium transition-colors ${
                isPremium
                  ? 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-400'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              {submitting ? '添加中...' : isPremium ? '添加API密钥' : '升级后可添加'}
            </button>
          </form>
        </div>

        {/* 右侧：API密钥列表 */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6 backdrop-blur-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">已添加API密钥</h2>
          
          {loading ? (
            <div className="text-center py-12">
              <div className="w-12 h-12 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <p className="text-gray-500">加载API密钥中...</p>
            </div>
          ) : apiKeys.length > 0 ? (
            <div className="space-y-4">
              {apiKeys.map((apiKey) => (
                <div key={apiKey.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <span className="text-lg">
                        {exchanges.find(e => e.value === apiKey.exchange)?.icon || '🔧'}
                      </span>
                      <div>
                        <h3 className="font-medium text-gray-900">{apiKey.name}</h3>
                        <p className="text-sm text-gray-500">{apiKey.exchange.toUpperCase()}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {getStatusIndicator(apiKey.status)}
                      <span className="text-sm text-gray-600">{getStatusText(apiKey.status)}</span>
                    </div>
                  </div>
                  
                  <div className="space-y-2 mb-3">
                    <div>
                      <span className="text-xs text-gray-500">API KEY:</span>
                      <div className="flex items-center space-x-2">
                        <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">
                          {showSecrets[apiKey.id] 
                            ? apiKey.api_key 
                            : `${apiKey.api_key.slice(0, 8)}...${apiKey.api_key.slice(-4)}`
                          }
                        </code>
                        <button
                          onClick={() => toggleShowSecret(apiKey.id)}
                          className="text-xs text-blue-600 hover:text-blue-700"
                        >
                          {showSecrets[apiKey.id] ? '隐藏' : '显示'}
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span>权限: {apiKey.permissions || '交易权限'}</span>
                      <span>添加时间: {new Date(apiKey.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleTest(apiKey.id, apiKey.name)}
                      className="px-3 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors"
                    >
                      测试连接
                    </button>
                    <button
                      onClick={() => handleDelete(apiKey.id, apiKey.name)}
                      className="px-3 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 transition-colors"
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">暂无API密钥</h3>
              <p className="text-gray-500">添加您的第一个交易所API密钥以开始交易</p>
            </div>
          )}
        </div>
      </div>

      {/* 安全提示 */}
      <div className="bg-gradient-to-r from-yellow-50 to-orange-50 border border-yellow-200 rounded-xl p-4">
        <div className="flex items-start space-x-3">
          <div className="w-5 h-5 text-yellow-600 mt-0.5">
            <svg fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <div>
            <h4 className="font-medium text-yellow-800 mb-1">安全提示</h4>
            <ul className="text-sm text-yellow-700 space-y-1">
              <li>• API密钥采用安全加密存储，但请确保您的账户安全</li>
              <li>• 建议为API密钥设置最小必要权限（仅交易权限，禁用提现）</li>
              <li>• 定期检查API密钥状态，及时更新或删除不用的密钥</li>
              <li>• 不要在公共场所或他人面前输入API密钥信息</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default APIManagementPage