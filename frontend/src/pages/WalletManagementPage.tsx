import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface WalletStats {
  total_wallets: number;
  available_wallets: number;
  occupied_wallets: number;
  maintenance_wallets: number;
  disabled_wallets: number;
  utilization_rate: number;
  total_balance: number;
  network_distribution: {
    TRC20: number;
    ERC20: number;
    BEP20: number;
  };
  status_distribution: {
    available: number;
    occupied: number;
    maintenance: number;
    disabled: number;
  };
  risk_distribution: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
  };
}

interface Wallet {
  id: number;
  wallet_name: string;
  network: string;
  address: string;
  balance: number;
  status: string;
  risk_level: string;
  transaction_count: number;
  total_received: number;
  current_order_id?: string;
  allocated_at?: string;
  last_sync_at?: string;
  created_at: string;
}

interface GenerateWalletsForm {
  network: string;
  count: number;
  name_prefix: string;
}

interface ImportWalletForm {
  network: string;
  private_key: string;
  wallet_name: string;
}

const WalletManagementPage = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const [stats, setStats] = useState<WalletStats | null>(null);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'wallets' | 'generate' | 'import' | 'allocator'>('dashboard');

  // 生成钱包表单状态
  const [generateForm, setGenerateForm] = useState<GenerateWalletsForm>({
    network: 'TRC20',
    count: 10,
    name_prefix: 'wallet'
  });
  const [generating, setGenerating] = useState(false);

  // 导入钱包表单状态
  const [importForm, setImportForm] = useState<ImportWalletForm>({
    network: 'TRC20',
    private_key: '',
    wallet_name: ''
  });
  const [importing, setImporting] = useState(false);

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [walletsPerPage] = useState(20);
  const [totalWallets, setTotalWallets] = useState(0);

  // 筛选状态
  const [filterNetwork, setFilterNetwork] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  // 检查管理员权限
  useEffect(() => {
    if (!user || user.email !== 'admin@trademe.com') {
      navigate('/');
      return;
    }
  }, [user, navigate]);

  // 获取钱包统计信息
  const fetchWalletStats = async () => {
    try {
      const response = await fetch('/api/v1/admin/usdt-wallets/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data.data);
      } else {
        throw new Error('获取钱包统计失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取钱包统计失败');
    }
  };

  // 获取钱包列表
  const fetchWallets = async () => {
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: walletsPerPage.toString(),
      });
      
      if (filterNetwork) params.append('network', filterNetwork);
      if (filterStatus) params.append('status', filterStatus);

      const response = await fetch(`/api/v1/admin/usdt-wallets?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setWallets(data.data.wallets);
        setTotalWallets(data.data.total);
      } else {
        throw new Error('获取钱包列表失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取钱包列表失败');
    }
  };

  // 初始数据加载
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchWalletStats(), fetchWallets()]);
      setLoading(false);
    };

    if (token) {
      loadData();
    }
  }, [token, currentPage, filterNetwork, filterStatus]);

  // 生成钱包
  const handleGenerateWallets = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);

    try {
      const response = await fetch('/api/v1/admin/usdt-wallets/generate', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(generateForm),
      });

      if (response.ok) {
        const data = await response.json();
        alert(`成功生成 ${data.data.success_count} 个钱包`);
        await Promise.all([fetchWalletStats(), fetchWallets()]);
        setGenerateForm({ network: 'TRC20', count: 10, name_prefix: 'wallet' });
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || '生成钱包失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '生成钱包失败');
    } finally {
      setGenerating(false);
    }
  };

  // 导入钱包
  const handleImportWallet = async (e: React.FormEvent) => {
    e.preventDefault();
    setImporting(true);

    try {
      const response = await fetch('/api/v1/admin/usdt-wallets/import', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(importForm),
      });

      if (response.ok) {
        alert('钱包导入成功');
        await Promise.all([fetchWalletStats(), fetchWallets()]);
        setImportForm({ network: 'TRC20', private_key: '', wallet_name: '' });
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || '导入钱包失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '导入钱包失败');
    } finally {
      setImporting(false);
    }
  };

  // 更新钱包状态
  const handleUpdateWalletStatus = async (walletId: number, newStatus: string) => {
    try {
      const response = await fetch(`/api/v1/admin/usdt-wallets/${walletId}/status`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (response.ok) {
        alert('钱包状态更新成功');
        await fetchWallets();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || '更新钱包状态失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '更新钱包状态失败');
    }
  };

  // 释放钱包
  const handleReleaseWallet = async (walletId: number) => {
    if (!confirm('确定要释放此钱包吗？')) return;

    try {
      const response = await fetch(`/api/v1/admin/usdt-wallets/${walletId}/release`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        alert('钱包释放成功');
        await Promise.all([fetchWalletStats(), fetchWallets()]);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || '释放钱包失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '释放钱包失败');
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '无';
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available': return 'text-green-700 bg-green-100 border-green-200';
      case 'occupied': return 'text-blue-700 bg-blue-100 border-blue-200';
      case 'maintenance': return 'text-yellow-700 bg-yellow-100 border-yellow-200';
      case 'disabled': return 'text-red-700 bg-red-100 border-red-200';
      default: return 'text-gray-700 bg-gray-100 border-gray-200';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'available': return '可用';
      case 'occupied': return '已分配';
      case 'maintenance': return '维护中';
      case 'disabled': return '已禁用';
      default: return status;
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'LOW': return 'text-green-700 bg-green-100';
      case 'MEDIUM': return 'text-yellow-700 bg-yellow-100';
      case 'HIGH': return 'text-red-700 bg-red-100';
      default: return 'text-gray-700 bg-gray-100';
    }
  };

  const getRiskText = (risk: string) => {
    switch (risk) {
      case 'LOW': return '低风险';
      case 'MEDIUM': return '中风险';
      case 'HIGH': return '高风险';
      default: return risk;
    }
  };

  // 计算分页
  const totalPages = Math.ceil(totalWallets / walletsPerPage);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-red-600 text-lg mb-4">⚠️ {error}</div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">USDT钱包池管理</h1>
                <p className="text-sm text-gray-600">企业级多网络钱包管理中心</p>
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
                <span>返回控制台</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 标签导航 */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-6">
          <nav className="flex space-x-8">
            {[
              { id: 'dashboard', name: '概览面板', icon: '📊' },
              { id: 'wallets', name: '钱包列表', icon: '💰' },
              { id: 'generate', name: '生成钱包', icon: '⚡' },
              { id: 'import', name: '导入钱包', icon: '📥' },
              { id: 'allocator', name: '智能分配', icon: '🧠' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200 ${
                  activeTab === tab.id
                    ? 'border-green-500 text-green-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.name}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* 主要内容 */}
      <div className="p-6">
        {/* 概览面板 */}
        {activeTab === 'dashboard' && stats && (
          <div className="space-y-6">
            {/* 统计卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* 总钱包数 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{stats.total_wallets}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">总钱包数</h3>
                  <p className="text-gray-600 text-sm">
                    可用钱包 {stats.available_wallets} 个
                  </p>
                </div>
                <div className="mt-4">
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full transition-all duration-1000"
                      style={{ width: `${Math.min(100, (stats.available_wallets / stats.total_wallets) * 100)}%` }}
                    ></div>
                  </div>
                </div>
              </div>

              {/* 利用率 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{stats.utilization_rate.toFixed(1)}%</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">利用率</h3>
                  <p className="text-gray-600 text-sm">
                    已占用 {stats.occupied_wallets} 个钱包
                  </p>
                </div>
              </div>

              {/* 总余额 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-amber-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{stats.total_balance.toFixed(2)}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">总余额</h3>
                  <p className="text-gray-600 text-sm">USDT</p>
                </div>
              </div>

              {/* 网络分布 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-purple-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">
                      {Object.keys(stats.network_distribution).length}
                    </p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">支持网络</h3>
                  <div className="flex items-center space-x-4 text-gray-600 text-sm">
                    {Object.entries(stats.network_distribution).map(([network, count]) => (
                      <span key={network}>{network}: {count}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 分布图表 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 状态分布 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">状态分布</h3>
                <div className="space-y-3">
                  {Object.entries(stats.status_distribution).map(([status, count]) => (
                    <div key={status} className="flex items-center justify-between">
                      <span className={`px-3 py-1 text-xs font-medium rounded-full ${getStatusColor(status)}`}>
                        {getStatusText(status)}
                      </span>
                      <span className="font-semibold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 风险分布 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">风险分布</h3>
                <div className="space-y-3">
                  {Object.entries(stats.risk_distribution).map(([risk, count]) => (
                    <div key={risk} className="flex items-center justify-between">
                      <span className={`px-3 py-1 text-xs font-medium rounded-full ${getRiskColor(risk)}`}>
                        {getRiskText(risk)}
                      </span>
                      <span className="font-semibold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 网络分布 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">网络分布</h3>
                <div className="space-y-3">
                  {Object.entries(stats.network_distribution).map(([network, count]) => (
                    <div key={network} className="flex items-center justify-between">
                      <span className="px-3 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700">
                        {network}
                      </span>
                      <span className="font-semibold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 钱包列表 */}
        {activeTab === 'wallets' && (
          <div className="space-y-6">
            {/* 筛选器 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">筛选条件</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">网络类型</label>
                  <select
                    value={filterNetwork}
                    onChange={(e) => setFilterNetwork(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="">全部网络</option>
                    <option value="TRC20">TRC20</option>
                    <option value="ERC20">ERC20</option>
                    <option value="BEP20">BEP20</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">钱包状态</label>
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="">全部状态</option>
                    <option value="available">可用</option>
                    <option value="occupied">已分配</option>
                    <option value="maintenance">维护中</option>
                    <option value="disabled">已禁用</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    onClick={() => {
                      setFilterNetwork('');
                      setFilterStatus('');
                      setCurrentPage(1);
                    }}
                    className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                  >
                    重置筛选
                  </button>
                </div>
              </div>
            </div>

            {/* 钱包表格 */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">
                  钱包列表 (共 {totalWallets} 个)
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        钱包信息
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        网络/状态
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        余额/交易
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        分配信息
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        操作
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {wallets.map((wallet) => (
                      <tr key={wallet.id} className="hover:bg-gray-50 transition-colors duration-200">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {wallet.wallet_name}
                            </div>
                            <div className="text-sm text-gray-500 font-mono">
                              {wallet.address.substring(0, 10)}...{wallet.address.substring(wallet.address.length - 6)}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="space-y-1">
                            <span className="inline-flex px-2 py-1 text-xs font-semibold rounded bg-gray-100 text-gray-700">
                              {wallet.network}
                            </span>
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded ${getStatusColor(wallet.status)}`}>
                              {getStatusText(wallet.status)}
                            </span>
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded ${getRiskColor(wallet.risk_level)}`}>
                              {getRiskText(wallet.risk_level)}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            余额: {wallet.balance.toFixed(8)} USDT
                          </div>
                          <div className="text-sm text-gray-500">
                            交易次数: {wallet.transaction_count}
                          </div>
                          <div className="text-sm text-gray-500">
                            总收到: {wallet.total_received.toFixed(8)} USDT
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {wallet.current_order_id ? (
                              <>
                                <div>订单: {wallet.current_order_id}</div>
                                <div className="text-xs text-gray-500">
                                  分配时间: {formatDate(wallet.allocated_at)}
                                </div>
                              </>
                            ) : (
                              <span className="text-gray-500">未分配</span>
                            )}
                          </div>
                          <div className="text-xs text-gray-500">
                            最后同步: {formatDate(wallet.last_sync_at)}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex space-x-2">
                            {wallet.status === 'occupied' && (
                              <button
                                onClick={() => handleReleaseWallet(wallet.id)}
                                className="text-green-600 hover:text-green-800 text-sm font-medium"
                              >
                                释放
                              </button>
                            )}
                            <select
                              value={wallet.status}
                              onChange={(e) => handleUpdateWalletStatus(wallet.id, e.target.value)}
                              className="text-sm border border-gray-300 rounded px-2 py-1"
                            >
                              <option value="available">可用</option>
                              <option value="maintenance">维护</option>
                              <option value="disabled">禁用</option>
                            </select>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {/* 分页 */}
              {totalPages > 1 && (
                <div className="px-6 py-4 border-t border-gray-200">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-700">
                      显示第 {(currentPage - 1) * walletsPerPage + 1} 到{' '}
                      {Math.min(currentPage * walletsPerPage, totalWallets)} 个，共 {totalWallets} 个钱包
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                        disabled={currentPage === 1}
                        className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200"
                      >
                        上一页
                      </button>
                      <span className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded">
                        第 {currentPage} / {totalPages} 页
                      </span>
                      <button
                        onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                        disabled={currentPage === totalPages}
                        className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200"
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 生成钱包 */}
        {activeTab === 'generate' && (
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                  <span className="text-2xl">⚡</span>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">批量生成钱包</h3>
                  <p className="text-gray-600">自动生成新的USDT钱包到池中</p>
                </div>
              </div>

              <form onSubmit={handleGenerateWallets} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    网络类型 <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={generateForm.network}
                    onChange={(e) => setGenerateForm(prev => ({ ...prev, network: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                    required
                  >
                    <option value="TRC20">TRC20 (Tron)</option>
                    <option value="ERC20">ERC20 (Ethereum)</option>
                    <option value="BEP20">BEP20 (Binance Smart Chain)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    生成数量 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={generateForm.count}
                    onChange={(e) => setGenerateForm(prev => ({ ...prev, count: parseInt(e.target.value) }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="请输入生成数量 (1-1000)"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    钱包名称前缀
                  </label>
                  <input
                    type="text"
                    value={generateForm.name_prefix}
                    onChange={(e) => setGenerateForm(prev => ({ ...prev, name_prefix: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="例如: mainnet_wallet"
                  />
                  <p className="text-sm text-gray-500 mt-2">
                    钱包将命名为: {generateForm.name_prefix}_0001, {generateForm.name_prefix}_0002, ...
                  </p>
                </div>

                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <svg className="w-5 h-5 text-yellow-400 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <div>
                      <h4 className="text-sm font-medium text-yellow-800">注意事项</h4>
                      <div className="mt-2 text-sm text-yellow-700">
                        <ul className="list-disc list-inside space-y-1">
                          <li>生成的钱包私钥将被自动加密存储</li>
                          <li>请确保服务器有足够的随机熵源</li>
                          <li>大量生成时可能需要较长时间</li>
                          <li>建议单次生成数量不超过100个</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={generating}
                  className="w-full px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
                >
                  {generating ? (
                    <div className="flex items-center justify-center space-x-2">
                      <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>生成中...</span>
                    </div>
                  ) : (
                    '开始生成钱包'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* 导入钱包 */}
        {activeTab === 'import' && (
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <span className="text-2xl">📥</span>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">导入现有钱包</h3>
                  <p className="text-gray-600">通过私钥导入现有钱包到池中</p>
                </div>
              </div>

              <form onSubmit={handleImportWallet} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    网络类型 <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={importForm.network}
                    onChange={(e) => setImportForm(prev => ({ ...prev, network: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    <option value="TRC20">TRC20 (Tron)</option>
                    <option value="ERC20">ERC20 (Ethereum)</option>
                    <option value="BEP20">BEP20 (Binance Smart Chain)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    私钥 <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={importForm.private_key}
                    onChange={(e) => setImportForm(prev => ({ ...prev, private_key: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                    placeholder="请输入钱包私钥（64字符十六进制字符串）"
                    rows={3}
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    钱包名称 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={importForm.wallet_name}
                    onChange={(e) => setImportForm(prev => ({ ...prev, wallet_name: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="例如: imported_wallet_001"
                    required
                  />
                </div>

                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <svg className="w-5 h-5 text-red-400 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <div>
                      <h4 className="text-sm font-medium text-red-800">安全警告</h4>
                      <div className="mt-2 text-sm text-red-700">
                        <ul className="list-disc list-inside space-y-1">
                          <li>私钥信息极其敏感，请确保在安全环境下操作</li>
                          <li>私钥将被AES-256加密后存储</li>
                          <li>请确认私钥格式正确（64字符十六进制）</li>
                          <li>导入前请验证该钱包尚未在池中</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={importing}
                  className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
                >
                  {importing ? (
                    <div className="flex items-center justify-center space-x-2">
                      <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>导入中...</span>
                    </div>
                  ) : (
                    '导入钱包'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* 智能分配 */}
        {activeTab === 'allocator' && (
          <div className="max-w-4xl mx-auto">
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                  <span className="text-2xl">🧠</span>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">智能分配算法</h3>
                  <p className="text-gray-600">企业级多策略钱包分配系统</p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 分配策略说明 */}
                <div className="space-y-6">
                  <h4 className="text-lg font-semibold text-gray-900">分配策略</h4>
                  <div className="space-y-4">
                    {[
                      {
                        name: '均衡分配',
                        description: '综合考虑风险、性能、可用性等因素',
                        icon: '⚖️',
                        color: 'bg-blue-50 border-blue-200 text-blue-800'
                      },
                      {
                        name: '风险最小化',
                        description: '优先选择低风险、高安全性的钱包',
                        icon: '🛡️',
                        color: 'bg-green-50 border-green-200 text-green-800'
                      },
                      {
                        name: '性能优化',
                        description: '优先选择响应快、成功率高的钱包',
                        icon: '⚡',
                        color: 'bg-yellow-50 border-yellow-200 text-yellow-800'
                      },
                      {
                        name: '成本优化',
                        description: '优先选择交易手续费低的网络',
                        icon: '💰',
                        color: 'bg-purple-50 border-purple-200 text-purple-800'
                      },
                      {
                        name: '高可用性',
                        description: '优先选择可用性高、稳定性强的钱包',
                        icon: '🔗',
                        color: 'bg-indigo-50 border-indigo-200 text-indigo-800'
                      }
                    ].map((strategy, index) => (
                      <div key={index} className={`p-4 rounded-lg border ${strategy.color}`}>
                        <div className="flex items-center space-x-3">
                          <span className="text-2xl">{strategy.icon}</span>
                          <div>
                            <h5 className="font-semibold">{strategy.name}</h5>
                            <p className="text-sm opacity-90">{strategy.description}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 评分因子说明 */}
                <div className="space-y-6">
                  <h4 className="text-lg font-semibold text-gray-900">评分因子</h4>
                  <div className="space-y-4">
                    {[
                      {
                        name: '风险评分',
                        description: '基于历史失败率和风险等级',
                        weight: '0-50%',
                        color: 'text-red-600'
                      },
                      {
                        name: '性能评分',
                        description: '基于响应时间和成功率',
                        weight: '15-40%',
                        color: 'text-green-600'
                      },
                      {
                        name: '可用性评分',
                        description: '基于钱包状态和使用频率',
                        weight: '15-45%',
                        color: 'text-blue-600'
                      },
                      {
                        name: '负载评分',
                        description: '基于当前使用量和限额',
                        weight: '5-20%',
                        color: 'text-yellow-600'
                      },
                      {
                        name: '成本评分',
                        description: '基于网络手续费成本',
                        weight: '5-35%',
                        color: 'text-purple-600'
                      }
                    ].map((factor, index) => (
                      <div key={index} className="p-4 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                          <h5 className={`font-semibold ${factor.color}`}>{factor.name}</h5>
                          <span className="text-sm text-gray-500 font-mono">{factor.weight}</span>
                        </div>
                        <p className="text-sm text-gray-600">{factor.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-8 p-6 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">算法特性</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm">原子性分配保证</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm">并发安全处理</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm">智能决策日志</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm">多因子综合评分</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WalletManagementPage;