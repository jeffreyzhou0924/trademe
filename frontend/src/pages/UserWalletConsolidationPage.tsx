import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface UserWalletStats {
  summary: {
    total_users: number;
    total_user_wallets: number;
    funded_wallets: number;
    total_user_balance: number;
    networks_count: number;
  };
  network_distribution: {
    network: string;
    wallet_count: number;
    total_balance: number;
  }[];
  users: {
    user_id: number;
    email: string;
    username: string;
    wallet_count: number;
    total_balance: number;
    last_wallet_created: string;
  }[];
}

interface UserWallet {
  user_id: number;
  email: string;
  username: string;
  wallet_count: number;
  total_balance: number;
  last_wallet_created: string;
  wallets: {
    [network: string]: {
      address: string;
      balance: number;
      status: string;
      transaction_count: number;
      total_received: number;
      created_at: string;
    }
  };
}

interface ConsolidationStats {
  total_wallets_with_funds: number;
  total_consolidatable_amount: number;
  pending_consolidation_tasks: number;
  completed_consolidations_today: number;
  total_fees_saved: number;
  network_breakdown: {
    [network: string]: {
      wallets_count: number;
      total_balance: number;
      consolidation_threshold: number;
      master_wallet: string;
    }
  };
}

interface ConsolidationRequest {
  user_id?: number;
  min_amount: number;
  network?: string;
}

const UserWalletConsolidationPage = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const [stats, setStats] = useState<UserWalletStats | null>(null);
  const [consolidationStats, setConsolidationStats] = useState<ConsolidationStats | null>(null);
  const [users, setUsers] = useState<UserWallet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'users' | 'consolidation' | 'analytics'>('dashboard');

  // 资金归集表单状态
  const [consolidationForm, setConsolidationForm] = useState<ConsolidationRequest>({
    min_amount: 10.0,
    network: ''
  });
  const [consolidating, setConsolidating] = useState(false);

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [walletsPerPage] = useState(20);
  const [totalWallets, setTotalWallets] = useState(0);

  // 筛选状态
  const [filterNetwork, setFilterNetwork] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  // 检查管理员权限
  useEffect(() => {
    if (!user) {
      navigate('/');
      return;
    }
    // 检查用户是否有管理员权限（通过邮箱或用户名判断）
    const isAdmin = user.email === 'admin@trademe.com' || 
                   user.username === 'admin' || 
                   user.email?.includes('admin');
    
    if (!isAdmin) {
      setError('您没有访问用户钱包管理系统的权限');
      return;
    }
  }, [user, navigate]);

  // 获取用户钱包统计信息
  const fetchUserWalletStats = async () => {
    try {
      const response = await fetch('/api/v1/user-wallets/admin/overview', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          setStats(result.data);
        } else {
          throw new Error(result.message || '获取用户钱包统计失败');
        }
      } else {
        throw new Error('获取用户钱包统计失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取用户钱包统计失败');
    }
  };

  // 获取资金归集统计信息
  const fetchConsolidationStats = async () => {
    try {
      const response = await fetch('/api/v1/fund-consolidation/statistics', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          setConsolidationStats(result.data);
        }
      }
    } catch (err) {
      console.warn('获取归集统计失败:', err);
    }
  };

  // 获取用户列表和详细钱包信息
  const fetchUserWallets = async () => {
    try {
      if (!stats?.users) return;
      
      const userWallets = [];
      
      // 获取前20个用户的详细钱包信息
      const usersToFetch = stats.users.slice((currentPage - 1) * walletsPerPage, currentPage * walletsPerPage);
      
      for (const user of usersToFetch) {
        try {
          const response = await fetch(`/api/v1/user-wallets/admin/user/${user.user_id}/wallets`, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });
          
          if (response.ok) {
            const result = await response.json();
            if (result.success) {
              userWallets.push({
                ...user,
                wallets: result.data.wallets
              });
            }
          }
        } catch (err) {
          console.warn(`获取用户 ${user.user_id} 钱包失败:`, err);
        }
      }
      
      setUsers(userWallets);
      setTotalWallets(stats.users.length);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取用户钱包列表失败');
    }
  };

  // 初始数据加载
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchUserWalletStats();
      await fetchConsolidationStats();
      setLoading(false);
    };

    if (token) {
      loadData();
    }
  }, [token]);

  // 加载用户钱包列表
  useEffect(() => {
    if (stats && activeTab === 'users') {
      fetchUserWallets();
    }
  }, [stats, currentPage, activeTab]);

  // 发起资金归集
  const handleStartConsolidation = async (e: React.FormEvent) => {
    e.preventDefault();
    setConsolidating(true);

    try {
      const response = await fetch('/api/v1/fund-consolidation/scan', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success && result.data.length > 0) {
          // 过滤符合条件的任务
          const tasksToExecute = result.data
            .filter((task: any) => {
              if (consolidationForm.network && task.network !== consolidationForm.network) return false;
              if (parseFloat(task.amount) < consolidationForm.min_amount) return false;
              return true;
            })
            .slice(0, 10) // 限制最多10个任务
            .map((task: any) => task.task_id);

          if (tasksToExecute.length > 0) {
            // 执行归集任务
            const executeResponse = await fetch('/api/v1/fund-consolidation/execute', {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                task_ids: tasksToExecute,
                strategy: 'THRESHOLD'
              }),
            });

            if (executeResponse.ok) {
              const executeResult = await executeResponse.json();
              if (executeResult.success) {
                alert(`成功发起 ${executeResult.data.executed_tasks} 个归集任务`);
                await fetchConsolidationStats();
                await fetchUserWalletStats();
              }
            }
          } else {
            alert('没有符合条件的归集任务');
          }
        } else {
          alert('当前没有可归集的资金');
        }
      } else {
        throw new Error('扫描归集机会失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '发起归集失败');
    } finally {
      setConsolidating(false);
    }
  };

  // 为用户分配钱包
  const handleAllocateWalletsForUser = async (userId: number) => {
    try {
      const response = await fetch(`/api/v1/user-wallets/admin/user/${userId}/allocate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          alert(`成功为用户 ${userId} 分配钱包`);
          await fetchUserWallets();
        } else {
          throw new Error(result.message || '分配钱包失败');
        }
      } else {
        throw new Error('分配钱包失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '分配钱包失败');
    }
  };

  // 发起单个用户资金归集
  const handleConsolidateUserFunds = async (userId: number) => {
    try {
      const response = await fetch(`/api/v1/user-wallets/consolidate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ min_amount: 1.0 }),
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          alert(`成功发起用户 ${userId} 的资金归集`);
          await fetchUserWallets();
          await fetchConsolidationStats();
        } else {
          throw new Error(result.message || '发起归集失败');
        }
      } else {
        throw new Error('发起归集失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '发起归集失败');
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '无';
    return new Date(dateString).toLocaleString('zh-CN');
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 113 0m-3 0V2.25" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">用户钱包管理中心</h1>
                <p className="text-sm text-gray-600">用户钱包统计、资金归集和管理系统</p>
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
              { id: 'users', name: '用户钱包', icon: '💰' },
              { id: 'consolidation', name: '资金归集', icon: '⚡' },
              { id: 'analytics', name: '数据分析', icon: '📈' },
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
              {/* 总用户数 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 113 0m-3 0V2.25" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{stats.summary.total_users}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">注册用户</h3>
                  <p className="text-gray-600 text-sm">
                    已分配钱包 {stats.summary.total_user_wallets} 个
                  </p>
                </div>
              </div>

              {/* 有资金钱包 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{stats.summary.funded_wallets}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">有资金钱包</h3>
                  <p className="text-gray-600 text-sm">
                    占比 {stats.summary.total_user_wallets > 0 ? ((stats.summary.funded_wallets / stats.summary.total_user_wallets) * 100).toFixed(1) : 0}%
                  </p>
                </div>
              </div>

              {/* 用户总余额 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-amber-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{Number(stats.summary.total_user_balance).toFixed(2)}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">用户总余额</h3>
                  <p className="text-gray-600 text-sm">USDT</p>
                </div>
              </div>

              {/* 支持网络 */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-12 h-12 rounded-lg bg-purple-100 flex items-center justify-center">
                    <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                    </svg>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{stats.summary.networks_count}</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-gray-900 font-semibold mb-1">支持网络</h3>
                  <p className="text-gray-600 text-sm">
                    多网络支持
                  </p>
                </div>
              </div>
            </div>

            {/* 网络分布图表 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">网络分布统计</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {stats.network_distribution.map((network) => (
                  <div key={network.network} className="text-center p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-semibold text-lg text-gray-900">{network.network}</h4>
                    <p className="text-2xl font-bold text-blue-600">{network.wallet_count}</p>
                    <p className="text-sm text-gray-600">钱包数量</p>
                    <p className="text-lg font-semibold text-green-600 mt-2">{Number(network.total_balance).toFixed(2)} USDT</p>
                    <p className="text-sm text-gray-600">总余额</p>
                  </div>
                ))}
              </div>
            </div>

            {/* 资金归集统计 */}
            {consolidationStats && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">资金归集统计</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-blue-50 rounded-lg">
                    <h4 className="font-semibold text-gray-900">可归集钱包</h4>
                    <p className="text-2xl font-bold text-blue-600">{consolidationStats.total_wallets_with_funds}</p>
                    <p className="text-sm text-gray-600">个钱包有资金</p>
                  </div>
                  <div className="text-center p-4 bg-green-50 rounded-lg">
                    <h4 className="font-semibold text-gray-900">可归集金额</h4>
                    <p className="text-2xl font-bold text-green-600">{Number(consolidationStats.total_consolidatable_amount).toFixed(2)}</p>
                    <p className="text-sm text-gray-600">USDT</p>
                  </div>
                  <div className="text-center p-4 bg-purple-50 rounded-lg">
                    <h4 className="font-semibold text-gray-900">今日归集</h4>
                    <p className="text-2xl font-bold text-purple-600">{consolidationStats.completed_consolidations_today}</p>
                    <p className="text-sm text-gray-600">次归集操作</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 资金归集标签页 */}
        {activeTab === 'consolidation' && (
          <div className="space-y-6">
            {/* 资金归集控制面板 */}
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                  <span className="text-2xl">⚡</span>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">资金归集控制</h3>
                  <p className="text-gray-600">自动扫描用户钱包并归集资金到主钱包</p>
                </div>
              </div>

              <form onSubmit={handleStartConsolidation} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      最小归集金额 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      min="0.1"
                      max="10000"
                      step="0.1"
                      value={consolidationForm.min_amount}
                      onChange={(e) => setConsolidationForm(prev => ({ ...prev, min_amount: parseFloat(e.target.value) }))}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                      placeholder="最小归集金额 (USDT)"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      网络类型筛选
                    </label>
                    <select
                      value={consolidationForm.network}
                      onChange={(e) => setConsolidationForm(prev => ({ ...prev, network: e.target.value }))}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                    >
                      <option value="">所有网络</option>
                      <option value="TRC20">TRC20 (Tron)</option>
                      <option value="ERC20">ERC20 (Ethereum)</option>
                      <option value="BEP20">BEP20 (Binance Smart Chain)</option>
                    </select>
                  </div>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <svg className="w-5 h-5 text-blue-400 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                    </svg>
                    <div>
                      <h4 className="text-sm font-medium text-blue-800">归集说明</h4>
                      <div className="mt-2 text-sm text-blue-700">
                        <ul className="list-disc list-inside space-y-1">
                          <li>系统将自动扫描所有用户钱包的资金情况</li>
                          <li>只有达到最小金额阈值的钱包才会被归集</li>
                          <li>归集过程中会自动预留手续费</li>
                          <li>归集任务将在后台异步执行</li>
                          <li>单次最多执行10个归集任务</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={consolidating}
                  className="w-full px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 font-medium"
                >
                  {consolidating ? (
                    <div className="flex items-center justify-center space-x-2">
                      <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>扫描并执行归集中...</span>
                    </div>
                  ) : (
                    '开始资金归集'
                  )}
                </button>
              </form>
            </div>

            {/* 归集规则展示 */}
            {consolidationStats && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">归集规则配置</h3>
                <div className="space-y-4">
                  {Object.entries(consolidationStats.network_breakdown).map(([network, config]) => (
                    <div key={network} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-gray-900">{network} 网络</h4>
                        <span className="text-sm text-gray-500">
                          {config.wallets_count} 个钱包有资金
                        </span>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-gray-600">总余额:</span>
                          <span className="font-medium ml-1">{Number(config.total_balance).toFixed(2)} USDT</span>
                        </div>
                        <div>
                          <span className="text-gray-600">归集阈值:</span>
                          <span className="font-medium ml-1">{Number(config.consolidation_threshold).toFixed(2)} USDT</span>
                        </div>
                        <div className="md:col-span-2">
                          <span className="text-gray-600">主钱包:</span>
                          <span className="font-mono text-xs ml-1">{config.master_wallet || '未配置'}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default UserWalletConsolidationPage;