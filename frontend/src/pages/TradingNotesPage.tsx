import React, { useState, useEffect } from 'react'
import { useUserInfo } from '../store'
import { useLanguageStore } from '../store/languageStore'
import toast from 'react-hot-toast'
import { getAuthToken } from '../utils/auth'

// 交易心得类型定义
interface TradingNote {
  id: number
  title: string
  content: string
  category: 'technical_analysis' | 'fundamental' | 'strategy_summary' | 'error_review' | 'market_view'
  symbol?: string
  entry_price?: string
  exit_price?: string
  stop_loss?: string
  take_profit?: string
  position_size?: string
  result?: string
  tags: string[]
  likes_count: number
  comments_count: number
  is_public: boolean
  is_liked?: boolean
  created_at: string
  updated_at: string
}

interface TradingNoteCreate {
  title: string
  content: string
  category: string
  symbol?: string
  entry_price?: string
  exit_price?: string
  stop_loss?: string
  take_profit?: string
  position_size?: string
  result?: string
  tags: string[]
  is_public: boolean
}

interface TradingNoteStats {
  total_notes: number
  notes_by_category: Record<string, number>
  storage_used: number
  storage_limit: number
}

const TradingNotesPage: React.FC = () => {
  const { user, isPremium } = useUserInfo()
  const { t } = useLanguageStore()
  
  // 筛选状态
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedTimeRange, setSelectedTimeRange] = useState('all')
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([])
  const [newSymbol, setNewSymbol] = useState('')
  
  // 数据状态
  const [notes, setNotes] = useState<TradingNote[]>([])
  const [stats, setStats] = useState<TradingNoteStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  
  // 选择状态（用于AI分析）
  const [selectedForComparison, setSelectedForComparison] = useState<number[]>([])
  
  // 表单状态
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingNote, setEditingNote] = useState<TradingNote | null>(null)
  const [formData, setFormData] = useState<TradingNoteCreate>({
    title: '',
    content: '',
    category: 'technical_analysis',
    symbol: '',
    entry_price: '',
    exit_price: '',
    stop_loss: '',
    take_profit: '',
    position_size: '',
    result: '',
    tags: [],
    is_public: false
  })

  // 分类选项
  const categories = [
    { value: 'all', label: '所有分类' },
    { value: 'technical_analysis', label: '技术分析' },
    { value: 'fundamental', label: '基本面' },
    { value: 'strategy_summary', label: '策略总结' },
    { value: 'error_review', label: '错误复盘' },
    { value: 'market_view', label: '市场观点' }
  ]

  // 时间范围选项
  const timeRanges = [
    { value: 'all', label: '全部时间' },
    { value: 'today', label: '今天' },
    { value: 'week', label: '本周' },
    { value: 'month', label: '本月' },
    { value: 'quarter', label: '过去3个月' }
  ]

  // 获取分类显示样式
  const getCategoryStyle = (category: string) => {
    switch (category) {
      case 'technical_analysis':
        return 'bg-blue-100 text-blue-800'
      case 'fundamental':
        return 'bg-green-100 text-green-800'
      case 'strategy_summary':
        return 'bg-purple-100 text-purple-800'
      case 'error_review':
        return 'bg-red-100 text-red-800'
      case 'market_view':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  // 获取分类显示名称
  const getCategoryLabel = (category: string) => {
    const categoryObj = categories.find(c => c.value === category)
    return categoryObj?.label || category
  }

  // 加载交易心得列表
  const loadTradingNotes = async () => {
    try {
      setLoading(true)
      
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '10'
      })
      
      if (searchTerm) params.append('search', searchTerm)
      if (selectedCategory !== 'all') params.append('category', selectedCategory)
      if (selectedSymbols.length > 0) params.append('tags', selectedSymbols.join(','))
      
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/trading-notes/?${params}`, {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setNotes(data.notes || [])
        setTotalPages(data.total_pages || 1)
      } else {
        throw new Error('Failed to load trading notes')
      }
    } catch (error) {
      console.error('Error loading trading notes:', error)
      toast.error('加载交易心得失败')
    } finally {
      setLoading(false)
    }
  }

  // 加载统计信息
  const loadStats = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/trading-notes/stats/summary`, {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }

  // 创建或更新心得
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.title || !formData.content) {
      toast.error('请填写标题和内容')
      return
    }
    
    try {
      const url = editingNote 
        ? `${import.meta.env.VITE_TRADING_API_URL}/trading-notes/${editingNote.id}`
        : `${import.meta.env.VITE_TRADING_API_URL}/trading-notes/`
      
      const method = editingNote ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(formData)
      })
      
      if (response.ok) {
        toast.success(editingNote ? '心得更新成功' : '心得创建成功')
        setShowCreateForm(false)
        setEditingNote(null)
        resetForm()
        loadTradingNotes()
        loadStats()
      } else {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to save note')
      }
    } catch (error) {
      console.error('Error saving note:', error)
      toast.error(`保存失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  // 删除心得
  const handleDelete = async (id: number, title: string) => {
    if (!window.confirm(`确定要删除心得 "${title}" 吗？`)) {
      return
    }
    
    try {
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/trading-notes/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        toast.success('心得删除成功')
        loadTradingNotes()
        loadStats()
      } else {
        throw new Error('Failed to delete note')
      }
    } catch (error) {
      console.error('Error deleting note:', error)
      toast.error('删除失败')
    }
  }

  // 点赞切换
  const handleLike = async (id: number) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/trading-notes/${id}/like`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        setNotes(notes.map(note => 
          note.id === id 
            ? { ...note, likes_count: data.likes_count, is_liked: data.is_liked }
            : note
        ))
      }
    } catch (error) {
      console.error('Error toggling like:', error)
      toast.error('操作失败')
    }
  }

  // AI分析功能
  const handleAIAnalysis = async () => {
    if (notes.length === 0) {
      toast.error('没有交易心得可分析')
      return
    }
    
    try {
      const selectedNoteIds = selectedForComparison.length > 0 
        ? selectedForComparison 
        : notes.slice(0, 10).map(note => note.id) // 默认分析最新的10条
      
      const response = await fetch(`${import.meta.env.VITE_TRADING_API_URL}/trading-notes/ai-analysis`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        
        // 显示分析结果
        const analysisWindow = window.open('', '_blank', 'width=800,height=600,scrollbars=yes')
        if (analysisWindow) {
          analysisWindow.document.write(`
            <html>
              <head>
                <title>AI交易心得分析报告</title>
                <meta charset="utf-8">
                <style>
                  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; margin: 40px; }
                  .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #3b82f6; padding-bottom: 20px; }
                  .content { white-space: pre-wrap; }
                  .stats { background: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
                </style>
              </head>
              <body>
                <div class="header">
                  <h1>🤖 AI交易心得分析报告</h1>
                  <p>分析了 ${data.analyzed_notes_count} 条交易记录</p>
                </div>
                <div class="stats">
                  <strong>分析类型：</strong>综合交易分析<br>
                  <strong>生成时间：</strong>${new Date().toLocaleString()}
                </div>
                <div class="content">${data.analysis}</div>
              </body>
            </html>
          `)
          analysisWindow.document.close()
        }
        
        toast.success(`AI分析完成！分析了 ${data.analyzed_notes_count} 条记录`)
      } else {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'AI分析失败')
      }
    } catch (error) {
      console.error('AI分析失败:', error)
      toast.error(`AI分析失败: ${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  // 添加币种标签
  const addSymbol = () => {
    if (newSymbol && !selectedSymbols.includes(newSymbol.toUpperCase())) {
      setSelectedSymbols([...selectedSymbols, newSymbol.toUpperCase()])
      setNewSymbol('')
    }
  }

  // 移除币种标签
  const removeSymbol = (symbol: string) => {
    setSelectedSymbols(selectedSymbols.filter(s => s !== symbol))
  }

  // 重置表单
  const resetForm = () => {
    setFormData({
      title: '',
      content: '',
      category: 'technical_analysis',
      symbol: '',
      entry_price: '',
      exit_price: '',
      stop_loss: '',
      take_profit: '',
      position_size: '',
      result: '',
      tags: [],
      is_public: false
    })
  }

  // 切换选择心得（用于AI分析）
  const toggleNoteSelection = (noteId: number) => {
    setSelectedForComparison(prev => 
      prev.includes(noteId) 
        ? prev.filter(id => id !== noteId)
        : [...prev, noteId]
    )
  }
  
  // 清除所有选择
  const clearSelection = () => {
    setSelectedForComparison([])
  }

  // 开始编辑
  const startEdit = (note: TradingNote) => {
    setEditingNote(note)
    setFormData({
      title: note.title,
      content: note.content,
      category: note.category,
      symbol: note.symbol || '',
      entry_price: note.entry_price || '',
      exit_price: note.exit_price || '',
      stop_loss: note.stop_loss || '',
      take_profit: note.take_profit || '',
      position_size: note.position_size || '',
      result: note.result || '',
      tags: note.tags,
      is_public: note.is_public
    })
    setShowCreateForm(true)
  }

  useEffect(() => {
    loadTradingNotes()
    loadStats()
  }, [page, searchTerm, selectedCategory, selectedSymbols])

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">交易心得</h1>
          <p className="text-gray-600 mt-1">记录和分析您的交易经验，提升交易技能</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center"
        >
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          记录心得
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧筛选面板 */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">筛选条件</h2>
          
          {/* 搜索框 */}
          <div className="mb-4">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="搜索心得记录..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            />
          </div>

          {/* 分类筛选 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">分类筛选</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
              {categories.map(category => (
                <option key={category.value} value={category.value}>
                  {category.label}
                </option>
              ))}
            </select>
          </div>

          {/* 时间范围 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">时间范围</label>
            <select
              value={selectedTimeRange}
              onChange={(e) => setSelectedTimeRange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
              {timeRanges.map(range => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>

          {/* 币种标签 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">币种</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {selectedSymbols.map((symbol) => (
                <span
                  key={symbol}
                  className="bg-blue-50 text-blue-700 px-2 py-1 rounded-md text-sm flex items-center"
                >
                  {symbol}
                  <button
                    onClick={() => removeSymbol(symbol)}
                    className="ml-1 text-blue-500 hover:text-blue-700"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="flex">
              <input
                type="text"
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value)}
                placeholder="添加币种"
                className="flex-1 px-2 py-1 border border-gray-300 rounded-l-md text-sm"
                onKeyPress={(e) => e.key === 'Enter' && addSymbol()}
              />
              <button
                onClick={addSymbol}
                className="px-3 py-1 bg-gray-100 text-gray-700 rounded-r-md text-sm hover:bg-gray-200"
              >
                +
              </button>
            </div>
          </div>

          {/* AI分析按钮 */}
          <button 
            onClick={handleAIAnalysis}
            disabled={loading || notes.length === 0}
            className="w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center mb-2 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {notes.length === 0 ? 'AI分析（无数据）' : `AI分析交易记录${selectedForComparison.length > 0 ? `（已选${selectedForComparison.length}条）` : '（最新10条）'}`}
          </button>
          
          {/* 清除选择按钮 */}
          {selectedForComparison.length > 0 && (
            <button 
              onClick={clearSelection}
              className="w-full bg-gray-500 text-white py-2 rounded-lg hover:bg-gray-600 transition-colors flex items-center justify-center mb-4 text-sm"
            >
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              清除选择（{selectedForComparison.length}条）
            </button>
          )}

          {/* 统计信息 */}
          {stats && (
            <div className="border-t border-gray-200 pt-4">
              <div className="text-sm text-gray-500 space-y-1">
                <div className="flex justify-between">
                  <span>共有心得记录</span>
                  <span className="font-medium">{stats.total_notes}条</span>
                </div>
                <div className="flex justify-between">
                  <span>存储空间</span>
                  <span className="font-medium">
                    {stats.storage_used.toFixed(1)}GB/{stats.storage_limit}GB
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 右侧心得列表 */}
        <div className="lg:col-span-3 bg-white border border-gray-200 rounded-xl shadow-lg p-6">
          {loading ? (
            <div className="text-center py-12">
              <div className="w-12 h-12 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center animate-spin">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <p className="text-gray-500">加载交易心得中...</p>
            </div>
          ) : notes.length > 0 ? (
            <div className="space-y-6">
              {notes.map((note) => (
                <div key={note.id} className="border-b border-gray-200 pb-6 last:border-b-0">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-start space-x-3 flex-1">
                      <input
                        type="checkbox"
                        checked={selectedForComparison.includes(note.id)}
                        onChange={() => toggleNoteSelection(note.id)}
                        className="mt-2 w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
                      />
                      <h3 className="text-xl font-bold text-gray-900 flex-1">{note.title}</h3>
                    </div>
                    <span className={`px-2 py-1 rounded text-sm ${getCategoryStyle(note.category)}`}>
                      {getCategoryLabel(note.category)}
                    </span>
                  </div>
                  
                  <div className="text-sm text-gray-500 mb-4">
                    {new Date(note.created_at).toLocaleString()} 
                    {note.symbol && ` · ${note.symbol}`}
                  </div>
                  
                  <div className="mb-4 text-gray-700">
                    <p>{note.content}</p>
                    
                    {/* 交易数据 */}
                    {(note.entry_price || note.exit_price || note.stop_loss || note.take_profit) && (
                      <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                          {note.entry_price && (
                            <div>
                              <span className="text-gray-500">入场：</span>
                              <span className="font-medium">{note.entry_price}</span>
                            </div>
                          )}
                          {note.exit_price && (
                            <div>
                              <span className="text-gray-500">出场：</span>
                              <span className="font-medium">{note.exit_price}</span>
                            </div>
                          )}
                          {note.stop_loss && (
                            <div>
                              <span className="text-gray-500">止损：</span>
                              <span className="font-medium">{note.stop_loss}</span>
                            </div>
                          )}
                          {note.take_profit && (
                            <div>
                              <span className="text-gray-500">止盈：</span>
                              <span className="font-medium">{note.take_profit}</span>
                            </div>
                          )}
                        </div>
                        {note.result && (
                          <div className="mt-2">
                            <span className="text-gray-500">结果：</span>
                            <span className="font-medium">{note.result}</span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* 标签 */}
                    {note.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1">
                        {note.tags.map((tag, index) => (
                          <span key={index} className="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <button
                        onClick={() => handleLike(note.id)}
                        className={`flex items-center text-sm ${
                          note.is_liked ? 'text-blue-600' : 'text-gray-500 hover:text-blue-600'
                        }`}
                      >
                        <svg className="w-4 h-4 mr-1" fill={note.is_liked ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                        </svg>
                        {note.likes_count}
                      </button>
                      <span className="flex items-center text-sm text-gray-500">
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                        {note.comments_count}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => startEdit(note)}
                        className="text-blue-600 text-sm flex items-center hover:text-blue-700"
                      >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        编辑
                      </button>
                      <button
                        onClick={() => handleDelete(note.id, note.title)}
                        className="text-red-600 text-sm flex items-center hover:text-red-700"
                      >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              
              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex justify-center mt-8">
                  <nav className="inline-flex rounded-md shadow">
                    <button
                      onClick={() => setPage(Math.max(1, page - 1))}
                      disabled={page === 1}
                      className="py-2 px-4 bg-white border border-gray-300 text-sm rounded-l-md hover:bg-gray-100 disabled:bg-gray-50 disabled:text-gray-400"
                    >
                      上一页
                    </button>
                    
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                      <button
                        key={pageNum}
                        onClick={() => setPage(pageNum)}
                        className={`py-2 px-4 border border-gray-300 text-sm hover:bg-gray-100 ${
                          page === pageNum ? 'bg-blue-50 text-blue-700 border-blue-500' : 'bg-white'
                        }`}
                      >
                        {pageNum}
                      </button>
                    ))}
                    
                    <button
                      onClick={() => setPage(Math.min(totalPages, page + 1))}
                      disabled={page === totalPages}
                      className="py-2 px-4 bg-white border border-gray-300 text-sm rounded-r-md hover:bg-gray-100 disabled:bg-gray-50 disabled:text-gray-400"
                    >
                      下一页
                    </button>
                  </nav>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">暂无交易心得</h3>
              <p className="text-gray-500 mb-4">开始记录您的第一个交易心得</p>
              <button
                onClick={() => setShowCreateForm(true)}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                记录心得
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 创建/编辑心得模态框 */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-gray-900">
                {editingNote ? '编辑交易心得' : '记录交易心得'}
              </h2>
              <button
                onClick={() => {
                  setShowCreateForm(false)
                  setEditingNote(null)
                  resetForm()
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">标题</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({...formData, title: e.target.value})}
                  placeholder="输入心得标题..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">分类</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({...formData, category: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {categories.slice(1).map(category => (
                      <option key={category.value} value={category.value}>
                        {category.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">交易对</label>
                  <input
                    type="text"
                    value={formData.symbol}
                    onChange={(e) => setFormData({...formData, symbol: e.target.value})}
                    placeholder="如：BTC/USDT"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">心得内容</label>
                <textarea
                  value={formData.content}
                  onChange={(e) => setFormData({...formData, content: e.target.value})}
                  placeholder="分享您的交易心得、策略分析或经验总结..."
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">入场价格</label>
                  <input
                    type="text"
                    value={formData.entry_price}
                    onChange={(e) => setFormData({...formData, entry_price: e.target.value})}
                    placeholder="63600"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">出场价格</label>
                  <input
                    type="text"
                    value={formData.exit_price}
                    onChange={(e) => setFormData({...formData, exit_price: e.target.value})}
                    placeholder="64800"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">止损价格</label>
                  <input
                    type="text"
                    value={formData.stop_loss}
                    onChange={(e) => setFormData({...formData, stop_loss: e.target.value})}
                    placeholder="62900"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">止盈价格</label>
                  <input
                    type="text"
                    value={formData.take_profit}
                    onChange={(e) => setFormData({...formData, take_profit: e.target.value})}
                    placeholder="65200"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">仓位大小</label>
                  <input
                    type="text"
                    value={formData.position_size}
                    onChange={(e) => setFormData({...formData, position_size: e.target.value})}
                    placeholder="0.1 BTC"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">交易结果</label>
                  <input
                    type="text"
                    value={formData.result}
                    onChange={(e) => setFormData({...formData, result: e.target.value})}
                    placeholder="获利1.9%"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_public"
                  checked={formData.is_public}
                  onChange={(e) => setFormData({...formData, is_public: e.target.checked})}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="is_public" className="ml-2 block text-sm text-gray-700">
                  公开分享（其他用户可以查看）
                </label>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false)
                    setEditingNote(null)
                    resetForm()
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  {editingNote ? '更新心得' : '保存心得'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default TradingNotesPage