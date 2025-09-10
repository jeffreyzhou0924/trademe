import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import LoadingSpinner from '@/components/common/LoadingSpinner';

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

interface User {
  id: string;
  username: string;
  email: string;
  membership_level: string;
  is_active: boolean;
  email_verified: boolean;
  last_login_at?: string;
  created_at: string;
}

const AdminDashboardPage = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [recentUsers, setRecentUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 检查管理员权限
  useEffect(() => {
    if (!user || user.email !== 'admin@trademe.com') {
      navigate('/');
      return;
    }
  }, [user, navigate]);

  // 获取系统统计信息
  const fetchSystemStats = async () => {
    try {
      const response = await fetch('/api/v1/admin/stats/system', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data.data);
      } else {
        throw new Error('获取系统统计失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取系统统计失败');
    }
  };

  // 获取最近用户列表
  const fetchRecentUsers = async () => {
    try {
      const response = await fetch('/api/v1/admin/users?limit=5', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setRecentUsers(data.data.users);
      } else {
        throw new Error('获取用户列表失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取用户列表失败');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchSystemStats(), fetchRecentUsers()]);
      setLoading(false);
    };

    if (token) {
      loadData();
    }
  }, [token]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

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
              <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 flex items-center justify-center shadow-lg">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Trademe 管理仪表板</h1>
                <p className="text-sm text-gray-600">数据化运营管理中心</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3 px-4 py-2 bg-blue-50 rounded-lg border border-blue-200">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                  <span className="text-blue-700 text-sm font-semibold">{user?.username?.charAt(0).toUpperCase()}</span>
                </div>
                <span className="text-sm font-medium text-blue-700">管理员: {user?.username}</span>
              </div>
              <button
                onClick={() => navigate('/')}
                className="px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-all duration-200 flex items-center space-x-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                <span>返回前台</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 主要内容 */}
      <div className="p-6">
        {/* 系统统计卡片 */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {/* 总用户数 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                  </svg>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-gray-900">
                    {stats.users.total.toLocaleString()}
                  </p>
                </div>
              </div>
              <div>
                <h3 className="text-gray-900 font-semibold mb-1">总用户数</h3>
                <p className="text-gray-600 text-sm">
                  活跃用户 {stats.users.active} ({stats.growth.active_rate}%)
                </p>
              </div>
              <div className="mt-4">
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-1000"
                    style={{ width: `${Math.min(100, (stats.users.active / stats.users.total) * 100)}%` }}
                  ></div>
                </div>
              </div>
            </div>

            {/* 新用户 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-gray-900">
                    {stats.users.recent_7days}
                  </p>
                </div>
              </div>
              <div>
                <h3 className="text-gray-900 font-semibold mb-1">7天新增</h3>
                <p className="text-gray-600 text-sm">
                  本周新用户注册数
                </p>
              </div>
              <div className="mt-4 flex justify-between items-end">
                {[...Array(7)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-4 rounded-sm transition-all duration-500 ${
                      i < Math.ceil((stats.users.recent_7days / 7) * 7)
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
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-amber-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-gray-900">
                    {stats.growth.verification_rate}%
                  </p>
                </div>
              </div>
              <div>
                <h3 className="text-gray-900 font-semibold mb-1">验证率</h3>
                <p className="text-gray-600 text-sm">
                  已验证: {stats.users.verified} / {stats.users.total}
                </p>
              </div>
              <div className="mt-4">
                <div className="flex mb-2 items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold inline-block text-amber-600">
                      已验证: {stats.users.verified}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-semibold inline-block text-gray-500">
                      待验证: {stats.users.unverified}
                    </span>
                  </div>
                </div>
                <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-amber-100">
                  <div
                    style={{ width: `${stats.growth.verification_rate}%` }}
                    className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-amber-500 transition-all duration-1000"
                  ></div>
                </div>
              </div>
            </div>

            {/* 付费用户 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-purple-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                  </svg>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-gray-900">
                    {stats.membership.premium + stats.membership.professional}
                  </p>
                </div>
              </div>
              <div>
                <h3 className="text-gray-900 font-semibold mb-1">付费用户</h3>
                <div className="flex items-center space-x-4 text-gray-600 text-sm">
                  <span>高级: {stats.membership.premium}</span>
                  <span>专业: {stats.membership.professional}</span>
                </div>
              </div>
              <div className="mt-4 flex space-x-1">
                <div 
                  className="h-2 bg-blue-500 rounded-sm flex-1"
                  style={{flexBasis: `${(stats.membership.premium / (stats.membership.premium + stats.membership.professional)) * 100}%`}}
                ></div>
                <div 
                  className="h-2 bg-purple-500 rounded-sm flex-1"
                  style={{flexBasis: `${(stats.membership.professional / (stats.membership.premium + stats.membership.professional)) * 100}%`}}
                ></div>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 最近用户 */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                      <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900">最近用户</h3>
                  </div>
                  <button
                    onClick={() => navigate('/admin/users')}
                    className="group flex items-center space-x-2 text-blue-600 hover:text-blue-800 text-sm font-medium transition-all duration-300 hover:scale-105"
                  >
                    <span>查看全部</span>
                    <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="overflow-hidden">
                <table className="min-w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        用户
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        会员等级
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        状态
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        注册时间
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {recentUsers.map((user, index) => (
                      <tr key={user.id} className="hover:bg-gray-50 transition-colors duration-200">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                              <span className="text-white text-sm font-semibold">{user.username.charAt(0).toUpperCase()}</span>
                            </div>
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                {user.username}
                              </div>
                              <div className="text-sm text-gray-500">
                                {user.email}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-3 py-1 text-xs font-semibold rounded-full ${getMembershipBadgeColor(user.membership_level)}`}>
                            {getMembershipText(user.membership_level)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-2">
                            <div className={`w-2 h-2 rounded-full ${user.is_active ? 'bg-green-400' : 'bg-red-400'}`}></div>
                            <span className={`text-sm font-medium ${
                              user.is_active ? 'text-green-700' : 'text-red-700'
                            }`}>
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
                          {formatDate(user.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* 快捷操作 */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
                  <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">快捷操作</h3>
              </div>
              <div className="space-y-3">
                <button 
                  onClick={() => navigate('/admin/users')}
                  className="group w-full text-left px-4 py-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 transition-all duration-300 hover:scale-[1.02]"
                >
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center mr-4 group-hover:shadow-lg group-hover:shadow-blue-100 transition-all duration-300">
                      <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900 group-hover:text-blue-700 transition-colors duration-300">用户管理</div>
                      <div className="text-sm text-gray-600">管理用户账户和会员权限</div>
                    </div>
                    <svg className="w-5 h-5 text-blue-600 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>

                <button 
                  onClick={() => navigate('/admin/claude')}
                  className="group w-full text-left px-4 py-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 transition-all duration-300 hover:scale-[1.02]"
                >
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center mr-4 group-hover:shadow-lg group-hover:shadow-green-100 transition-all duration-300">
                      <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900 group-hover:text-green-700 transition-colors duration-300">AI服务管理</div>
                      <div className="text-sm text-gray-600">Claude账号池和使用统计</div>
                    </div>
                    <svg className="w-5 h-5 text-green-600 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>

                <button 
                  onClick={() => navigate('/admin/wallets')}
                  className="group w-full text-left px-4 py-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 transition-all duration-300 hover:scale-[1.02]"
                >
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center mr-4 group-hover:shadow-lg group-hover:shadow-emerald-100 transition-all duration-300">
                      <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900 group-hover:text-emerald-700 transition-colors duration-300">钱包池管理</div>
                      <div className="text-sm text-gray-600">USDT钱包生成和智能分配</div>
                    </div>
                    <svg className="w-5 h-5 text-emerald-600 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>

                <button 
                  onClick={() => navigate('/admin/data')}
                  className="group w-full text-left px-4 py-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 transition-all duration-300 hover:scale-[1.02]"
                >
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center mr-4 group-hover:shadow-lg group-hover:shadow-orange-100 transition-all duration-300">
                      <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900 group-hover:text-orange-700 transition-colors duration-300">数据管理</div>
                      <div className="text-sm text-gray-600">历史数据下载和质量监控</div>
                    </div>
                    <svg className="w-5 h-5 text-orange-600 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>

                <button className="group w-full text-left px-4 py-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 transition-all duration-300 hover:scale-[1.02]">
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center mr-4 group-hover:shadow-lg group-hover:shadow-amber-100 transition-all duration-300">
                      <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900 group-hover:text-amber-700 transition-colors duration-300">支付管理</div>
                      <div className="text-sm text-gray-600">USDT钱包和订单管理</div>
                    </div>
                    <svg className="w-5 h-5 text-amber-600 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>

                <button className="group w-full text-left px-4 py-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 transition-all duration-300 hover:scale-[1.02]">
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-lg bg-pink-100 flex items-center justify-center mr-4 group-hover:shadow-lg group-hover:shadow-pink-100 transition-all duration-300">
                      <svg className="w-5 h-5 text-pink-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-gray-900 group-hover:text-pink-700 transition-colors duration-300">数据统计</div>
                      <div className="text-sm text-gray-600">系统运营数据和报表</div>
                    </div>
                    <svg className="w-5 h-5 text-pink-600 group-hover:translate-x-1 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              </div>
            </div>

            {/* 系统状态 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
                  <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">系统状态</h3>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 border border-blue-100">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                      <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <span className="text-sm font-medium text-gray-900">用户服务</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-sm font-medium text-green-700">运行中</span>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-purple-50 border border-purple-100">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
                      <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <span className="text-sm font-medium text-gray-900">交易服务</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-sm font-medium text-green-700">运行中</span>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-amber-50 border border-amber-100">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
                      <svg className="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                      </svg>
                    </div>
                    <span className="text-sm font-medium text-gray-900">数据服务</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-sm font-medium text-green-700">运行中</span>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50 border border-emerald-100">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
                      <svg className="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                      </svg>
                    </div>
                    <span className="text-sm font-medium text-gray-900">数据库</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-sm font-medium text-green-700">正常</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboardPage;