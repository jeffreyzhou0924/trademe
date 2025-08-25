import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface ClaudeAccount {
  id: string;
  account_name: string;
  api_key: string;
  organization_id?: string;
  project_id?: string;
  daily_limit: number;
  current_usage: number;
  remaining_balance?: number;
  status: 'active' | 'inactive' | 'error' | 'suspended';
  proxy_id?: string;
  avg_response_time: number;
  success_rate: number;
  total_requests: number;
  failed_requests: number;
  last_used_at?: string;
  last_check_at?: string;
  created_at: string;
  updated_at: string;
}

interface Proxy {
  id: string;
  name: string;
  proxy_type: string;
  host: string;
  port: number;
  username?: string;
  country?: string;
  region?: string;
  status: 'active' | 'inactive' | 'error' | 'banned';
  response_time?: number;
  success_rate: number;
  total_requests: number;
  failed_requests: number;
  created_at: string;
}

interface UsageStats {
  total_requests: number;
  total_cost_usd: number;
  daily_cost_usd: number;
  monthly_cost_usd: number;
  by_account: Record<string, {
    requests: number;
    cost: number;
    tokens: number;
  }>;
  period_days: number;
}

interface SchedulerConfig {
  id: string;
  config_name: string;
  config_type: string;
  config_data: Record<string, any>;
  is_active: boolean;
  priority: number;
  description?: string;
  created_at: string;
  updated_at: string;
}

interface AnomalyDetection {
  anomalies: Array<{
    type: 'high_failure_rate' | 'slow_response' | 'quota_exceeded' | 'cost_spike';
    account_id: string;
    account_name: string;
    severity: 'low' | 'medium' | 'high';
    description: string;
    detected_at: string;
    current_value: number;
    threshold: number;
  }>;
  recommendations: string[];
  last_check: string;
}

const ClaudeManagementPage = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const [accounts, setAccounts] = useState<ClaudeAccount[]>([]);
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [schedulerConfig, setSchedulerConfig] = useState<SchedulerConfig[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyDetection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 状态管理
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [showAccountDetail, setShowAccountDetail] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<ClaudeAccount | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  
  // 新账号表单数据
  const [newAccount, setNewAccount] = useState({
    account_name: '',
    api_key: '',
    organization_id: '',
    project_id: '',
    daily_limit: 100,
    proxy_id: ''
  });

  // 检查管理员权限
  useEffect(() => {
    if (!user || user.email !== 'admin@trademe.com') {
      navigate('/');
      return;
    }
  }, [user, navigate]);

  // 获取Claude账号列表
  const fetchClaudeAccounts = async () => {
    try {
      const response = await fetch('/api/v1/admin/claude/accounts', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAccounts(data.data.accounts || []);
      } else {
        throw new Error('获取Claude账号失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取Claude账号失败');
    }
  };

  // 获取代理服务器列表
  const fetchProxies = async () => {
    try {
      const response = await fetch('/api/v1/admin/proxies', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setProxies(data.data.proxies || []);
      }
    } catch (err) {
      console.error('获取代理列表失败:', err);
    }
  };

  // 获取使用统计
  const fetchUsageStats = async () => {
    try {
      const response = await fetch('/api/v1/admin/claude/usage-stats?days=30', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setUsageStats(data.data);
      }
    } catch (err) {
      console.error('获取使用统计失败:', err);
    }
  };

  // 获取异常检测报告
  const fetchAnomalyDetection = async () => {
    try {
      const response = await fetch('/api/v1/admin/claude/anomaly-detection', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAnomalies(data.data);
      }
    } catch (err) {
      console.error('获取异常检测失败:', err);
    }
  };

  // 添加新账号
  const addClaudeAccount = async () => {
    try {
      const response = await fetch('/api/v1/admin/claude/accounts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(newAccount),
      });

      if (response.ok) {
        const data = await response.json();
        alert('Claude账号添加成功');
        setShowAddAccount(false);
        setNewAccount({
          account_name: '',
          api_key: '',
          organization_id: '',
          project_id: '',
          daily_limit: 100,
          proxy_id: ''
        });
        await fetchClaudeAccounts();
      } else {
        throw new Error('添加Claude账号失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '添加Claude账号失败');
    }
  };

  // 测试账号连接
  const testAccount = async (accountId: string) => {
    try {
      const response = await fetch(`/api/v1/admin/claude/accounts/${accountId}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        alert(`测试结果: ${data.data.status === 'success' ? '连接成功' : '连接失败'}`);
        await fetchClaudeAccounts();
      } else {
        throw new Error('账号连接测试失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '账号连接测试失败');
    }
  };

  // 删除账号
  const deleteAccount = async (accountId: string) => {
    if (!confirm('确定要删除这个Claude账号吗？')) return;

    try {
      const response = await fetch(`/api/v1/admin/claude/accounts/${accountId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        alert('Claude账号删除成功');
        await fetchClaudeAccounts();
      } else {
        throw new Error('删除Claude账号失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '删除Claude账号失败');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchClaudeAccounts(),
        fetchProxies(),
        fetchUsageStats(),
        fetchAnomalyDetection()
      ]);
      setLoading(false);
    };

    if (token) {
      loadData();
    }
  }, [token]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-700 border-green-200';
      case 'inactive': return 'bg-gray-100 text-gray-700 border-gray-200';
      case 'error': return 'bg-red-100 text-red-700 border-red-200';
      case 'suspended': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default: return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '活跃';
      case 'inactive': return '非活跃';
      case 'error': return '错误';
      case 'suspended': return '暂停';
      default: return status;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const formatCurrency = (amount: number) => {
    return `$${amount.toFixed(4)}`;
  };

  // 筛选账号
  const filteredAccounts = accounts.filter(account => {
    const matchesSearch = account.account_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         account.api_key.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || account.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="text-red-600 text-lg mb-4">⚠️ {error}</div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            重新加载
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航栏 */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-green-600 to-green-700 flex items-center justify-center shadow-lg">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Claude AI 服务管理</h1>
                <p className="text-sm text-gray-600">AI账号池与智能调度管理平台</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3 px-4 py-2 bg-green-50 rounded-lg border border-green-200">
                <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                  <span className="text-green-700 text-sm font-semibold">{user?.username?.charAt(0).toUpperCase()}</span>
                </div>
                <span className="text-sm font-medium text-green-700">管理员: {user?.username}</span>
              </div>
              <button
                onClick={() => navigate('/admin')}
                className="px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-all duration-200 flex items-center space-x-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                <span>返回仪表板</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* KPI指标面板 */}
        {usageStats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* 总请求数 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                      <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-600">总请求数</p>
                      <p className="text-3xl font-bold text-gray-900">{usageStats.total_requests.toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="text-sm text-green-600 font-medium">
                    30天统计
                  </div>
                </div>
              </div>
            </div>

            {/* 总成本 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-600">总成本</p>
                  <p className="text-3xl font-bold text-gray-900">{formatCurrency(usageStats.total_cost_usd)}</p>
                </div>
              </div>
              <div className="text-sm text-gray-500">
                今日: {formatCurrency(usageStats.daily_cost_usd)}
              </div>
            </div>

            {/* 活跃账号数 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-600">活跃账号</p>
                  <p className="text-3xl font-bold text-gray-900">
                    {accounts.filter(a => a.status === 'active').length}
                  </p>
                </div>
              </div>
              <div className="text-sm text-gray-500">
                总账号: {accounts.length}
              </div>
            </div>

            {/* 异常数量 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.99-.833-2.75 0L4.058 18.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-600">异常警告</p>
                  <p className="text-3xl font-bold text-gray-900">
                    {anomalies?.anomalies.length || 0}
                  </p>
                </div>
              </div>
              <div className="text-sm text-red-500">
                需要关注
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* 主要数据表格 */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              {/* 表格头部控制 */}
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
                  <div className="flex items-center space-x-4">
                    <h2 className="text-lg font-semibold text-gray-900">Claude 账号池</h2>
                    {selectedAccounts.length > 0 && (
                      <span className="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded-full font-medium">
                        已选中 {selectedAccounts.length} 个账号
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    {/* 搜索框 */}
                    <div className="relative">
                      <input
                        type="text"
                        placeholder="搜索账号..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                      />
                      <svg className="w-4 h-4 text-gray-400 absolute left-3 top-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>

                    {/* 状态筛选 */}
                    <select
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                    >
                      <option value="all">全部状态</option>
                      <option value="active">活跃</option>
                      <option value="inactive">非活跃</option>
                      <option value="error">错误</option>
                      <option value="suspended">暂停</option>
                    </select>

                    {/* 添加账号按钮 */}
                    <button
                      onClick={() => setShowAddAccount(true)}
                      className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                      </svg>
                      添加账号
                    </button>
                  </div>
                </div>
              </div>

              {/* 数据表格 */}
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 text-left">
                        <input
                          type="checkbox"
                          className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedAccounts(filteredAccounts.map(a => a.id));
                            } else {
                              setSelectedAccounts([]);
                            }
                          }}
                          checked={selectedAccounts.length === filteredAccounts.length && filteredAccounts.length > 0}
                        />
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">账号信息</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">使用情况</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">性能</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredAccounts.map((account) => (
                      <tr key={account.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <input
                            type="checkbox"
                            className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                            checked={selectedAccounts.includes(account.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedAccounts([...selectedAccounts, account.id]);
                              } else {
                                setSelectedAccounts(selectedAccounts.filter(id => id !== account.id));
                              }
                            }}
                          />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-green-500 to-blue-600 flex items-center justify-center text-white font-semibold text-sm">
                              {account.account_name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="text-sm font-medium text-gray-900">{account.account_name}</div>
                              <div className="text-sm text-gray-500">
                                {account.api_key.substring(0, 8)}...{account.api_key.substring(account.api_key.length - 4)}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm">
                            <div className="font-medium text-gray-900">{formatCurrency(account.current_usage)} / {formatCurrency(account.daily_limit)}</div>
                            <div className="text-gray-500">
                              使用率: {account.daily_limit > 0 ? ((account.current_usage / account.daily_limit) * 100).toFixed(1) : 0}%
                            </div>
                          </div>
                          <div className="mt-2">
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className={`h-2 rounded-full transition-all duration-300 ${
                                  account.current_usage / account.daily_limit > 0.8 ? 'bg-red-500' :
                                  account.current_usage / account.daily_limit > 0.6 ? 'bg-yellow-500' :
                                  'bg-green-500'
                                }`}
                                style={{ 
                                  width: `${Math.min(100, (account.current_usage / account.daily_limit) * 100)}%` 
                                }}
                              ></div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(account.status)}`}>
                            {getStatusText(account.status)}
                          </span>
                          <div className="text-xs text-gray-500 mt-1">
                            {account.last_used_at ? formatDate(account.last_used_at) : '从未使用'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm">
                            <div className="flex items-center space-x-2">
                              <span className="text-gray-600">响应:</span>
                              <span className={`font-medium ${
                                account.avg_response_time > 3000 ? 'text-red-600' :
                                account.avg_response_time > 1500 ? 'text-yellow-600' :
                                'text-green-600'
                              }`}>
                                {account.avg_response_time}ms
                              </span>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="text-gray-600">成功率:</span>
                              <span className={`font-medium ${
                                account.success_rate > 95 ? 'text-green-600' :
                                account.success_rate > 85 ? 'text-yellow-600' :
                                'text-red-600'
                              }`}>
                                {account.success_rate.toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                          <button
                            onClick={() => testAccount(account.id)}
                            className="inline-flex items-center px-2 py-1 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors"
                          >
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                            测试
                          </button>
                          <button
                            onClick={() => {
                              setSelectedAccount(account);
                              setShowAccountDetail(true);
                            }}
                            className="inline-flex items-center px-2 py-1 text-xs text-green-600 hover:text-green-800 hover:bg-green-50 rounded transition-colors"
                          >
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            详情
                          </button>
                          <button
                            onClick={() => deleteAccount(account.id)}
                            className="inline-flex items-center px-2 py-1 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
                          >
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            删除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredAccounts.length === 0 && (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900">没有找到Claude账号</h3>
                  <p className="mt-1 text-sm text-gray-500">请尝试调整搜索条件或筛选器。</p>
                </div>
              )}
            </div>
          </div>

          {/* 右侧统计面板 */}
          <div className="space-y-6">
            {/* 异常警告 */}
            {anomalies && anomalies.anomalies.length > 0 && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center space-x-2 mb-4">
                  <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.99-.833-2.75 0L4.058 18.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">异常警告</h3>
                  <span className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded-full font-medium">
                    {anomalies.anomalies.length}
                  </span>
                </div>
                <div className="space-y-3">
                  {anomalies.anomalies.slice(0, 5).map((anomaly, index) => (
                    <div key={index} className="flex items-start space-x-3 p-3 bg-red-50 border border-red-100 rounded-lg">
                      <div className={`w-2 h-2 rounded-full mt-2 ${
                        anomaly.severity === 'high' ? 'bg-red-500' :
                        anomaly.severity === 'medium' ? 'bg-yellow-500' :
                        'bg-blue-500'
                      }`}></div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900">{anomaly.account_name}</div>
                        <div className="text-xs text-gray-600">{anomaly.description}</div>
                        <div className="text-xs text-gray-500 mt-1">
                          {formatDate(anomaly.detected_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                {anomalies.recommendations.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-red-100">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">建议</h4>
                    <ul className="space-y-1">
                      {anomalies.recommendations.slice(0, 3).map((rec, index) => (
                        <li key={index} className="text-xs text-gray-600 flex items-start">
                          <span className="w-1 h-1 bg-gray-400 rounded-full mt-2 mr-2 flex-shrink-0"></span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* 代理服务器状态 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">代理状态</h3>
              </div>
              <div className="space-y-3">
                {proxies.slice(0, 5).map((proxy) => (
                  <div key={proxy.id} className="flex items-center justify-between p-3 bg-purple-50 border border-purple-100 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${
                        proxy.status === 'active' ? 'bg-green-400' :
                        proxy.status === 'error' ? 'bg-red-400' :
                        'bg-gray-400'
                      }`}></div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">{proxy.name}</div>
                        <div className="text-xs text-gray-600">{proxy.host}:{proxy.port}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-gray-900">
                        {proxy.success_rate.toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-600">成功率</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 快速统计 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">快速统计</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">今日请求</span>
                  <span className="text-sm font-semibold text-gray-900">1,234</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">平均响应时间</span>
                  <span className="text-sm font-semibold text-green-600">1.2s</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">错误率</span>
                  <span className="text-sm font-semibold text-red-600">0.3%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">成本效率</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-16 bg-gray-200 rounded-full h-1">
                      <div className="bg-green-500 h-1 rounded-full" style={{ width: '85%' }}></div>
                    </div>
                    <span className="text-xs text-gray-500">85%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 添加账号模态框 */}
      {showAddAccount && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div 
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => setShowAddAccount(false)}
            ></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h3 className="text-lg font-bold text-gray-900">添加Claude账号</h3>
                  <p className="text-sm text-gray-500">添加新的Claude API账号到账号池</p>
                </div>
                <button
                  onClick={() => setShowAddAccount(false)}
                  className="bg-gray-100 hover:bg-gray-200 rounded-lg p-2 transition-colors"
                >
                  <svg className="h-5 w-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">账号名称</label>
                  <input
                    type="text"
                    value={newAccount.account_name}
                    onChange={(e) => setNewAccount({...newAccount, account_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="例如: Claude-Account-001"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
                  <input
                    type="password"
                    value={newAccount.api_key}
                    onChange={(e) => setNewAccount({...newAccount, api_key: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="sk-ant-api..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">每日限额 ($)</label>
                  <input
                    type="number"
                    value={newAccount.daily_limit}
                    onChange={(e) => setNewAccount({...newAccount, daily_limit: parseFloat(e.target.value) || 0})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">代理服务器 (可选)</label>
                  <select
                    value={newAccount.proxy_id}
                    onChange={(e) => setNewAccount({...newAccount, proxy_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">不使用代理</option>
                    {proxies.map(proxy => (
                      <option key={proxy.id} value={proxy.id}>{proxy.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  onClick={() => setShowAddAccount(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={addClaudeAccount}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  添加账号
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 账号详情模态框 */}
      {showAccountDetail && selectedAccount && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div 
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => setShowAccountDetail(false)}
            ></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full sm:p-6">
              <div className="flex items-start justify-between mb-6">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-green-500 to-blue-600 flex items-center justify-center text-white font-bold text-lg">
                    {selectedAccount.account_name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">{selectedAccount.account_name} 详细信息</h3>
                    <p className="text-sm text-gray-500">Claude账号使用详情和性能监控</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowAccountDetail(false)}
                  className="bg-gray-100 hover:bg-gray-200 rounded-lg p-2 transition-colors"
                >
                  <svg className="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 基本信息 */}
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <h4 className="text-lg font-semibold text-gray-900">基本信息</h4>
                  </div>
                  <div className="space-y-4">
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">API密钥</span>
                      <span className="text-sm font-medium text-gray-900 font-mono">
                        {selectedAccount.api_key.substring(0, 12)}...{selectedAccount.api_key.substring(selectedAccount.api_key.length - 8)}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">状态</span>
                      <span className={`px-3 py-1 text-xs font-medium rounded-full ${getStatusColor(selectedAccount.status)}`}>
                        {getStatusText(selectedAccount.status)}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">每日限额</span>
                      <span className="text-sm font-medium text-gray-900">{formatCurrency(selectedAccount.daily_limit)}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">当前使用</span>
                      <span className="text-sm font-medium text-gray-900">{formatCurrency(selectedAccount.current_usage)}</span>
                    </div>
                    {selectedAccount.remaining_balance && (
                      <div className="flex justify-between py-2 border-b border-blue-100">
                        <span className="text-sm text-gray-600">剩余余额</span>
                        <span className="text-sm font-medium text-gray-900">{formatCurrency(selectedAccount.remaining_balance)}</span>
                      </div>
                    )}
                    <div className="flex justify-between py-2">
                      <span className="text-sm text-gray-600">创建时间</span>
                      <span className="text-sm font-medium text-gray-900">{formatDate(selectedAccount.created_at)}</span>
                    </div>
                  </div>
                </div>

                {/* 性能统计 */}
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    </div>
                    <h4 className="text-lg font-semibold text-gray-900">性能统计</h4>
                  </div>
                  <div className="space-y-4">
                    <div className="flex justify-between py-2 border-b border-green-100">
                      <span className="text-sm text-gray-600">总请求数</span>
                      <span className="text-sm font-medium text-gray-900">{selectedAccount.total_requests.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-green-100">
                      <span className="text-sm text-gray-600">失败请求数</span>
                      <span className="text-sm font-medium text-gray-900">{selectedAccount.failed_requests.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-green-100">
                      <span className="text-sm text-gray-600">成功率</span>
                      <span className={`text-sm font-medium ${
                        selectedAccount.success_rate > 95 ? 'text-green-600' :
                        selectedAccount.success_rate > 85 ? 'text-yellow-600' :
                        'text-red-600'
                      }`}>
                        {selectedAccount.success_rate.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-green-100">
                      <span className="text-sm text-gray-600">平均响应时间</span>
                      <span className={`text-sm font-medium ${
                        selectedAccount.avg_response_time > 3000 ? 'text-red-600' :
                        selectedAccount.avg_response_time > 1500 ? 'text-yellow-600' :
                        'text-green-600'
                      }`}>
                        {selectedAccount.avg_response_time}ms
                      </span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-sm text-gray-600">最后使用</span>
                      <span className="text-sm font-medium text-gray-900">
                        {selectedAccount.last_used_at ? formatDate(selectedAccount.last_used_at) : '从未使用'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  onClick={() => setShowAccountDetail(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  关闭
                </button>
                <button
                  onClick={() => testAccount(selectedAccount.id)}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  测试连接
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClaudeManagementPage;