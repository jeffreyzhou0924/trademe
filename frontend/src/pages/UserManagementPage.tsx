import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface User {
  id: string;
  username: string;
  email: string;
  membership_level: string;
  membership_expires_at?: string;
  is_active: boolean;
  email_verified: boolean;
  last_login_at?: string;
  created_at: string;
}

interface MembershipStats {
  user: {
    id: string;
    username: string;
    email: string;
    membership_level: string;
    membership_name: string;
    membership_expires_at?: string;
    email_verified: boolean;
    created_at: string;
  };
  limits: {
    name: string;
    api_keys: number;
    ai_daily: number;
    tick_backtest: number;
    storage: number;
    indicators: number;
    strategies: number;
    live_trading: number;
  };
  usage: {
    api_keys_count: number;
    ai_usage_today: number;
    tick_backtest_today: number;
    storage_used: number;
    indicators_count: number;
    strategies_count: number;
    live_trading_count: number;
  };
}

interface MembershipAnalytics {
  membership_distribution: Array<{
    level: string;
    count: number;
  }>;
  revenue: {
    monthly_revenue: number;
    yearly_revenue: number;
    active_subscriptions: number;
  };
  expiring_soon: Array<{
    id: string;
    username: string;
    email: string;
    membership_level: string;
    expires_at: string;
    days_remaining: number;
  }>;
}

interface SystemStats {
  users: {
    total: number;
    active: number;
    inactive: number;
    verified: number;
    unverified: number;
    recent_7days: number;
  };
  membership: {
    basic: number;
    premium: number;
    professional: number;
  };
  growth: {
    weekly_new_users: number;
    active_rate: string;
    verification_rate: string;
  };
}

const UserManagementPage = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [membershipStats, setMembershipStats] = useState<MembershipStats | null>(null);
  const [analytics, setAnalytics] = useState<MembershipAnalytics | null>(null);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [showUserDetail, setShowUserDetail] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  // 检查管理员权限
  useEffect(() => {
    if (!user || user.email !== 'admin@trademe.com') {
      navigate('/');
      return;
    }
  }, [user, navigate]);

  // 获取用户列表
  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/v1/admin/users?limit=50', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.data.users);
      } else {
        throw new Error('获取用户列表失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取用户列表失败');
    }
  };

  // 获取系统统计
  const fetchSystemStats = async () => {
    try {
      const response = await fetch('/api/v1/admin/stats/system', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSystemStats(data.data);
      }
    } catch (err) {
      console.error('获取系统统计失败:', err);
    }
  };

  // 获取会员分析数据
  const fetchAnalytics = async () => {
    try {
      const response = await fetch('/api/v1/admin/analytics/membership', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAnalytics(data.data);
      }
    } catch (err) {
      console.error('获取分析数据失败:', err);
    }
  };

  // 获取用户详细信息和使用统计
  const fetchUserDetails = async (userId: string) => {
    try {
      const response = await fetch(`/api/v1/admin/users/${userId}/membership-stats`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setMembershipStats(data.data);
        setShowUserDetail(true);
      } else {
        throw new Error('获取用户详情失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取用户详情失败');
    }
  };

  // 批量操作用户
  const batchUpdateUsers = async (action: string, data?: any) => {
    if (selectedUsers.length === 0) {
      alert('请选择要操作的用户');
      return;
    }

    try {
      const response = await fetch('/api/v1/admin/users/batch', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          user_ids: selectedUsers,
          action,
          data,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        alert(result.message);
        await fetchUsers();
        setSelectedUsers([]);
      } else {
        throw new Error('批量操作失败');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '批量操作失败');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchUsers(), fetchAnalytics(), fetchSystemStats()]);
      setLoading(false);
    };

    if (token) {
      loadData();
    }
  }, [token]);

  const getMembershipBadgeColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'basic': return 'bg-gray-100 text-gray-700 border border-gray-300';
      case 'premium': return 'bg-blue-50 text-blue-700 border border-blue-200';
      case 'professional': return 'bg-purple-50 text-purple-700 border border-purple-200';
      default: return 'bg-gray-100 text-gray-700 border border-gray-300';
    }
  };

  const getMembershipText = (level: string) => {
    switch (level.toLowerCase()) {
      case 'basic': return '基础版';
      case 'premium': return '高级版';
      case 'professional': return '专业版';
      default: return level;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const getDaysRemaining = (expiresAt?: string) => {
    if (!expiresAt) return null;
    const days = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / (24 * 60 * 60 * 1000));
    return days > 0 ? days : 0;
  };

  // 筛选用户
  const filteredUsers = users.filter(user => {
    const matchesSearch = user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || 
                         (filterStatus === 'active' && user.is_active) ||
                         (filterStatus === 'inactive' && !user.is_active) ||
                         (filterStatus === 'verified' && user.email_verified) ||
                         (filterStatus === 'unverified' && !user.email_verified);
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
              <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 flex items-center justify-center shadow-lg">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">用户管理中心</h1>
                <p className="text-sm text-gray-600">数据驱动的用户运营平台</p>
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
        {systemStats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* 总用户数 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-4">
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                      <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-600">总用户数</p>
                      <p className="text-3xl font-bold text-gray-900">{systemStats.users.total.toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4 text-sm">
                    <span className="text-green-600 font-medium">活跃: {systemStats.users.active}</span>
                    <span className="text-gray-500">({systemStats.growth.active_rate}%)</span>
                  </div>
                  <div className="mt-3">
                    <div className="w-full bg-gray-100 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all duration-1000"
                        style={{ width: `${Math.min(100, (systemStats.users.active / systemStats.users.total) * 100)}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 7天新增 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-600">7天新增</p>
                  <p className="text-3xl font-bold text-gray-900">{systemStats.users.recent_7days}</p>
                </div>
              </div>
              <div className="flex justify-between items-end mt-4">
                {[...Array(7)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-4 rounded-sm transition-all duration-500 ${
                      i < Math.ceil((systemStats.users.recent_7days / 7) * 7)
                        ? 'bg-green-500' 
                        : 'bg-gray-200'
                    }`}
                    style={{ 
                      height: `${20 + Math.random() * 30}px`,
                      animationDelay: `${i * 100}ms`
                    }}
                  ></div>
                ))}
              </div>
            </div>

            {/* 邮箱验证率 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-600">邮箱验证率</p>
                  <p className="text-3xl font-bold text-gray-900">{systemStats.growth.verification_rate}%</p>
                </div>
              </div>
              <div className="relative pt-1">
                <div className="flex mb-2 items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold inline-block text-amber-600">
                      已验证: {systemStats.users.verified}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-semibold inline-block text-gray-500">
                      待验证: {systemStats.users.unverified}
                    </span>
                  </div>
                </div>
                <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-amber-100">
                  <div
                    style={{ width: `${systemStats.growth.verification_rate}%` }}
                    className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-amber-500 transition-all duration-1000"
                  ></div>
                </div>
              </div>
            </div>

            {/* 付费用户 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-600">付费用户</p>
                  <p className="text-3xl font-bold text-gray-900">{systemStats.membership.premium + systemStats.membership.professional}</p>
                </div>
              </div>
              <div className="flex items-center space-x-4 text-sm">
                <span className="text-blue-600 font-medium">高级: {systemStats.membership.premium}</span>
                <span className="text-purple-600 font-medium">专业: {systemStats.membership.professional}</span>
              </div>
              <div className="flex mt-3 space-x-1">
                <div 
                  className="h-2 bg-blue-500 rounded-sm flex-1"
                  style={{flexBasis: `${(systemStats.membership.premium / (systemStats.membership.premium + systemStats.membership.professional)) * 100}%`}}
                ></div>
                <div 
                  className="h-2 bg-purple-500 rounded-sm flex-1"
                  style={{flexBasis: `${(systemStats.membership.professional / (systemStats.membership.premium + systemStats.membership.professional)) * 100}%`}}
                ></div>
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
                    <h2 className="text-lg font-semibold text-gray-900">用户列表</h2>
                    {selectedUsers.length > 0 && (
                      <span className="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded-full font-medium">
                        已选中 {selectedUsers.length} 个用户
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    {/* 搜索框 */}
                    <div className="relative">
                      <input
                        type="text"
                        placeholder="搜索用户..."
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
                      <option value="active">活跃用户</option>
                      <option value="inactive">非活跃</option>
                      <option value="verified">已验证</option>
                      <option value="unverified">未验证</option>
                    </select>
                  </div>
                </div>

                {/* 批量操作按钮 */}
                {selectedUsers.length > 0 && (
                  <div className="flex items-center space-x-2 mt-4">
                    <button
                      onClick={() => batchUpdateUsers('activate')}
                      className="inline-flex items-center px-3 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                    >
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      激活用户
                    </button>
                    <button
                      onClick={() => batchUpdateUsers('deactivate')}
                      className="inline-flex items-center px-3 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                    >
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      停用用户
                    </button>
                    <button
                      onClick={() => batchUpdateUsers('verify_email')}
                      className="inline-flex items-center px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                    >
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                      验证邮箱
                    </button>
                  </div>
                )}
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
                              setSelectedUsers(filteredUsers.map(u => u.id));
                            } else {
                              setSelectedUsers([]);
                            }
                          }}
                          checked={selectedUsers.length === filteredUsers.length && filteredUsers.length > 0}
                        />
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户信息</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">会员等级</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">最后登录</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredUsers.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <input
                            type="checkbox"
                            className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                            checked={selectedUsers.includes(user.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedUsers([...selectedUsers, user.id]);
                              } else {
                                setSelectedUsers(selectedUsers.filter(id => id !== user.id));
                              }
                            }}
                          />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                              {user.username.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="text-sm font-medium text-gray-900">{user.username}</div>
                              <div className="text-sm text-gray-500">{user.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${getMembershipBadgeColor(user.membership_level)}`}>
                            {getMembershipText(user.membership_level)}
                          </span>
                          {user.membership_expires_at && (
                            <div className="text-xs text-amber-600 mt-1">
                              {getDaysRemaining(user.membership_expires_at)} 天后到期
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-2">
                            <div className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-green-400' : 'bg-gray-400'}`}></div>
                            <span className={`text-sm font-medium ${user.is_active ? 'text-green-700' : 'text-gray-500'}`}>
                              {user.is_active ? '活跃' : '非活跃'}
                            </span>
                          </div>
                          <div className="flex items-center space-x-2 mt-1">
                            <div className={`w-2 h-2 rounded-full ${user.email_verified ? 'bg-blue-400' : 'bg-amber-400'}`}></div>
                            <span className={`text-xs ${user.email_verified ? 'text-blue-600' : 'text-amber-600'}`}>
                              {user.email_verified ? '已验证' : '待验证'}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.last_login_at ? formatDate(user.last_login_at) : '从未登录'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <button
                            onClick={() => {
                              setSelectedUser(user);
                              fetchUserDetails(user.id);
                            }}
                            className="inline-flex items-center px-3 py-1 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors"
                          >
                            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            详情
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredUsers.length === 0 && (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                  </svg>
                  <h3 className="mt-2 text-sm font-medium text-gray-900">没有找到用户</h3>
                  <p className="mt-1 text-sm text-gray-500">请尝试调整搜索条件或筛选器。</p>
                </div>
              )}
            </div>
          </div>

          {/* 右侧统计面板 */}
          <div className="space-y-6">
            {/* 即将到期的会员 */}
            {analytics && analytics.expiring_soon.length > 0 && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center space-x-2 mb-4">
                  <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">即将到期</h3>
                  <span className="px-2 py-1 text-xs bg-amber-100 text-amber-700 rounded-full font-medium">
                    {analytics.expiring_soon.length}
                  </span>
                </div>
                <div className="space-y-3">
                  {analytics.expiring_soon.map((user) => (
                    <div key={user.id} className="flex items-center justify-between p-3 bg-amber-50 border border-amber-100 rounded-lg hover:bg-amber-100 transition-colors">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-lg bg-amber-200 flex items-center justify-center text-amber-800 font-semibold text-xs">
                          {user.username.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium text-gray-900 text-sm">{user.username}</div>
                          <div className="text-xs text-gray-600">{getMembershipText(user.membership_level)}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-amber-700">
                          {user.days_remaining} 天
                        </div>
                        <div className="text-xs text-amber-600">剩余时间</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 会员级别分布 */}
            {analytics && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center space-x-2 mb-4">
                  <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">会员分布</h3>
                </div>
                <div className="space-y-4">
                  {analytics.membership_distribution.map((dist) => {
                    const total = analytics.membership_distribution.reduce((sum, d) => sum + d.count, 0);
                    const percentage = Math.round((dist.count / total) * 100);
                    const colors = {
                      basic: 'bg-gray-500',
                      premium: 'bg-blue-500',
                      professional: 'bg-purple-500'
                    };
                    
                    return (
                      <div key={dist.level} className="p-4 bg-gray-50 rounded-lg border border-gray-100 hover:bg-gray-100 transition-colors">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-900">{getMembershipText(dist.level)}</span>
                          <span className="text-sm font-bold text-gray-900">{dist.count} 人</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                          <div 
                            className={`h-2 ${colors[dist.level as keyof typeof colors] || colors.basic} rounded-full transition-all duration-1000`}
                            style={{ width: `${percentage}%` }}
                          ></div>
                        </div>
                        <div className="text-xs text-gray-600">{percentage}% 占比</div>
                      </div>
                    );
                  })}
                </div>

                {/* 收入统计 */}
                {analytics.revenue && (
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <h4 className="text-sm font-medium text-gray-900 mb-3">收入概览</h4>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600">月度收入</span>
                        <span className="font-semibold text-green-600">${analytics.revenue.monthly_revenue}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600">活跃订阅</span>
                        <span className="font-semibold text-blue-600">{analytics.revenue.active_subscriptions}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 快速统计 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">快速统计</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">今日注册</span>
                  <span className="text-sm font-semibold text-gray-900">12</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">在线用户</span>
                  <span className="text-sm font-semibold text-green-600">1,248</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">待处理</span>
                  <span className="text-sm font-semibold text-amber-600">3</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">系统负载</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-16 bg-gray-200 rounded-full h-1">
                      <div className="bg-green-500 h-1 rounded-full" style={{ width: '65%' }}></div>
                    </div>
                    <span className="text-xs text-gray-500">65%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 用户详情模态框 */}
      {showUserDetail && membershipStats && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            {/* 背景遮罩 */}
            <div 
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => setShowUserDetail(false)}
            ></div>

            {/* 居中对齐的 trick */}
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            {/* 模态框内容 */}
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full sm:p-6">
              <div className="flex items-start justify-between mb-6">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg">
                    {membershipStats.user.username.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">{membershipStats.user.username} 详细信息</h3>
                    <p className="text-sm text-gray-500">用户数据详情与使用统计</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowUserDetail(false)}
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
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    </div>
                    <h4 className="text-lg font-semibold text-gray-900">基本信息</h4>
                  </div>
                  <div className="space-y-4">
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">邮箱地址</span>
                      <span className="text-sm font-medium text-gray-900">{membershipStats.user.email}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">会员等级</span>
                      <span className={`px-3 py-1 text-xs font-medium rounded-full ${getMembershipBadgeColor(membershipStats.user.membership_level)}`}>
                        {membershipStats.limits.name}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">邮箱验证</span>
                      <div className="flex items-center space-x-2">
                        <div className={`w-2 h-2 rounded-full ${membershipStats.user.email_verified ? 'bg-green-400' : 'bg-amber-400'}`}></div>
                        <span className={`text-sm font-medium ${membershipStats.user.email_verified ? 'text-green-600' : 'text-amber-600'}`}>
                          {membershipStats.user.email_verified ? '已验证' : '待验证'}
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between py-2 border-b border-blue-100">
                      <span className="text-sm text-gray-600">注册时间</span>
                      <span className="text-sm font-medium text-gray-900">{formatDate(membershipStats.user.created_at)}</span>
                    </div>
                    {membershipStats.user.membership_expires_at && (
                      <div className="flex justify-between py-2">
                        <span className="text-sm text-gray-600">会员到期</span>
                        <div className="text-right">
                          <span className="text-sm font-medium text-gray-900">{formatDate(membershipStats.user.membership_expires_at)}</span>
                          <div className="text-xs text-amber-600">
                            {getDaysRemaining(membershipStats.user.membership_expires_at)} 天后到期
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* 使用统计 */}
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-6">
                  <div className="flex items-center space-x-2 mb-4">
                    <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
                      <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    </div>
                    <h4 className="text-lg font-semibold text-gray-900">使用统计</h4>
                  </div>
                  <div className="space-y-4">
                    {[
                      { label: 'API密钥', current: membershipStats.usage.api_keys_count, limit: membershipStats.limits.api_keys, color: 'blue' },
                      { label: '今日AI使用', current: membershipStats.usage.ai_usage_today, limit: membershipStats.limits.ai_daily, color: 'green', prefix: '$' },
                      { label: '策略数量', current: membershipStats.usage.strategies_count, limit: membershipStats.limits.strategies, color: 'purple' },
                      { label: '指标数量', current: membershipStats.usage.indicators_count, limit: membershipStats.limits.indicators, color: 'amber' },
                      { label: '实盘交易', current: membershipStats.usage.live_trading_count, limit: membershipStats.limits.live_trading, color: 'emerald' },
                      { label: 'Tick回测', current: membershipStats.usage.tick_backtest_today, limit: membershipStats.limits.tick_backtest, color: 'rose' }
                    ].map((item, index) => {
                      const percentage = item.limit > 0 ? Math.min(100, (item.current / item.limit) * 100) : 0;
                      const colorMap = {
                        blue: 'bg-blue-500',
                        green: 'bg-green-500',
                        purple: 'bg-purple-500',
                        amber: 'bg-amber-500',
                        emerald: 'bg-emerald-500',
                        rose: 'bg-rose-500'
                      };
                      
                      return (
                        <div key={index} className="py-2 border-b border-purple-100 last:border-b-0">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-sm text-gray-600">{item.label}</span>
                            <span className="text-sm font-medium text-gray-900">
                              {item.prefix}{item.current}/{item.limit}
                            </span>
                          </div>
                          <div className="w-full bg-purple-100 rounded-full h-2">
                            <div 
                              className={`h-2 ${colorMap[item.color as keyof typeof colorMap]} rounded-full transition-all duration-1000`}
                              style={{ width: `${percentage}%` }}
                            ></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  onClick={() => setShowUserDetail(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagementPage;