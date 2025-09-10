import React, { useEffect, useState } from 'react';
import SimpleChart from '../charts/SimpleChart';

interface ClaudeAccount {
  id: string;
  account_name: string;
  status: 'active' | 'inactive' | 'error' | 'suspended';
  daily_limit: number;
  current_usage: number;
  avg_response_time: number;
  success_rate: number;
  total_requests: number;
  failed_requests: number;
  last_used_at?: string;
}

interface DashboardStats {
  totalAccounts: number;
  activeAccounts: number;
  totalRequests: number;
  totalFailedRequests: number;
  averageResponseTime: number;
  averageSuccessRate: number;
  dailyUsagePercent: number;
}

interface ClaudeDashboardProps {
  accounts: ClaudeAccount[];
  usageStats: any;
  onRefresh?: () => void;
}

const ClaudeDashboard: React.FC<ClaudeDashboardProps> = ({ 
  accounts, 
  usageStats, 
  onRefresh 
}) => {
  const [stats, setStats] = useState<DashboardStats>({
    totalAccounts: 0,
    activeAccounts: 0,
    totalRequests: 0,
    totalFailedRequests: 0,
    averageResponseTime: 0,
    averageSuccessRate: 0,
    dailyUsagePercent: 0
  });

  // 计算仪表盘统计数据
  useEffect(() => {
    if (accounts.length === 0) return;

    const totalAccounts = accounts.length;
    const activeAccounts = accounts.filter(acc => acc.status === 'active').length;
    const totalRequests = accounts.reduce((sum, acc) => sum + acc.total_requests, 0);
    const totalFailedRequests = accounts.reduce((sum, acc) => sum + acc.failed_requests, 0);
    const averageResponseTime = accounts.length > 0 
      ? accounts.reduce((sum, acc) => sum + acc.avg_response_time, 0) / accounts.length 
      : 0;
    const averageSuccessRate = accounts.length > 0
      ? accounts.reduce((sum, acc) => sum + acc.success_rate, 0) / accounts.length
      : 0;
    
    // 计算每日使用率
    const totalDailyLimit = accounts.reduce((sum, acc) => sum + acc.daily_limit, 0);
    const totalDailyUsage = accounts.reduce((sum, acc) => sum + acc.current_usage, 0);
    const dailyUsagePercent = totalDailyLimit > 0 ? (totalDailyUsage / totalDailyLimit) * 100 : 0;

    setStats({
      totalAccounts,
      activeAccounts,
      totalRequests,
      totalFailedRequests,
      averageResponseTime,
      averageSuccessRate,
      dailyUsagePercent
    });
  }, [accounts]);

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'inactive': return 'text-gray-600 bg-gray-100';
      case 'error': return 'text-red-600 bg-red-100';
      case 'suspended': return 'text-yellow-600 bg-yellow-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  // 获取使用率颜色
  const getUsageColor = (percent: number) => {
    if (percent < 50) return 'bg-green-500';
    if (percent < 80) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const formatTime = (timestamp: string | undefined) => {
    if (!timestamp) return '从未使用';
    return new Date(timestamp).toLocaleDateString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="space-y-6">
      {/* 总览统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 总账户数 */}
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
          <div className="flex items-center">
            <div>
              <p className="text-sm font-medium text-gray-600">总账户数</p>
              <p className="text-3xl font-semibold text-gray-900">{stats.totalAccounts}</p>
              <p className="text-sm text-green-600 mt-1">
                {stats.activeAccounts} 个活跃
              </p>
            </div>
            <div className="ml-auto">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* 总请求数 */}
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-500">
          <div className="flex items-center">
            <div>
              <p className="text-sm font-medium text-gray-600">总请求数</p>
              <p className="text-3xl font-semibold text-gray-900">{stats.totalRequests.toLocaleString()}</p>
              <p className="text-sm text-red-600 mt-1">
                {stats.totalFailedRequests} 失败
              </p>
            </div>
            <div className="ml-auto">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* 平均响应时间 */}
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-yellow-500">
          <div className="flex items-center">
            <div>
              <p className="text-sm font-medium text-gray-600">平均响应时间</p>
              <p className="text-3xl font-semibold text-gray-900">{Math.round(stats.averageResponseTime)}ms</p>
              <p className="text-sm text-gray-600 mt-1">
                全部账户平均
              </p>
            </div>
            <div className="ml-auto">
              <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* 平均成功率 */}
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-purple-500">
          <div className="flex items-center">
            <div>
              <p className="text-sm font-medium text-gray-600">平均成功率</p>
              <p className="text-3xl font-semibold text-gray-900">{stats.averageSuccessRate.toFixed(1)}%</p>
              <p className="text-sm text-gray-600 mt-1">
                全部账户平均
              </p>
            </div>
            <div className="ml-auto">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 每日使用情况 */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">每日使用情况</h3>
          <span className="text-sm text-gray-600">
            总使用率: {stats.dailyUsagePercent.toFixed(1)}%
          </span>
        </div>
        
        <div className="mb-4">
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div 
              className={`h-3 rounded-full transition-all duration-300 ${getUsageColor(stats.dailyUsagePercent)}`}
              style={{ width: `${Math.min(stats.dailyUsagePercent, 100)}%` }}
            ></div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((account) => {
            const usagePercent = account.daily_limit > 0 
              ? (account.current_usage / account.daily_limit) * 100 
              : 0;
            
            return (
              <div key={account.id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-gray-900 truncate">{account.account_name}</h4>
                  <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(account.status)}`}>
                    {account.status}
                  </span>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">使用量</span>
                    <span className="font-medium">
                      {account.current_usage}/{account.daily_limit} ({usagePercent.toFixed(1)}%)
                    </span>
                  </div>
                  
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-300 ${getUsageColor(usagePercent)}`}
                      style={{ width: `${Math.min(usagePercent, 100)}%` }}
                    ></div>
                  </div>
                  
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>总请求: {account.total_requests}</span>
                    <span>成功率: {account.success_rate.toFixed(1)}%</span>
                  </div>
                  
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>响应时间: {account.avg_response_time}ms</span>
                    <span>最后使用: {formatTime(account.last_used_at)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 图表分析区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 账户请求量排行 */}
        <SimpleChart
          type="bar"
          title="账户请求量排行"
          data={accounts
            .sort((a, b) => b.total_requests - a.total_requests)
            .slice(0, 5)
            .map(account => ({
              label: account.account_name.length > 10 
                ? account.account_name.substring(0, 10) + '...' 
                : account.account_name,
              value: account.total_requests,
              color: account.status === 'active' ? '#10B981' : '#6B7280'
            }))
          }
          height={250}
        />
        
        {/* 账户状态分布 */}
        <SimpleChart
          type="donut"
          title="账户状态分布"
          data={[
            { 
              label: '活跃账户', 
              value: accounts.filter(acc => acc.status === 'active').length, 
              color: '#10B981' 
            },
            { 
              label: '非活跃账户', 
              value: accounts.filter(acc => acc.status === 'inactive').length, 
              color: '#6B7280' 
            },
            { 
              label: '错误状态', 
              value: accounts.filter(acc => acc.status === 'error').length, 
              color: '#EF4444' 
            },
            { 
              label: '暂停状态', 
              value: accounts.filter(acc => acc.status === 'suspended').length, 
              color: '#F59E0B' 
            }
          ].filter(item => item.value > 0)}
          height={250}
        />
      </div>

      {/* 成本分析 */}
      {usageStats && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">成本分析</h3>
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
              >
                刷新数据
              </button>
            )}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-blue-600">${usageStats.daily_cost_usd?.toFixed(2) || '0.00'}</p>
              <p className="text-sm text-gray-600">今日成本</p>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-green-600">${usageStats.monthly_cost_usd?.toFixed(2) || '0.00'}</p>
              <p className="text-sm text-gray-600">本月成本</p>
            </div>
            
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-purple-600">${usageStats.total_cost_usd?.toFixed(2) || '0.00'}</p>
              <p className="text-sm text-gray-600">总成本</p>
            </div>
          </div>
        </div>
      )}

      {/* 性能分析 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 响应时间分布 */}
        <SimpleChart
          type="bar"
          title="账户响应时间 (ms)"
          data={accounts
            .filter(account => account.avg_response_time > 0)
            .sort((a, b) => b.avg_response_time - a.avg_response_time)
            .slice(0, 5)
            .map(account => ({
              label: account.account_name.length > 10 
                ? account.account_name.substring(0, 10) + '...' 
                : account.account_name,
              value: account.avg_response_time,
              color: account.avg_response_time > 3000 ? '#EF4444' : 
                     account.avg_response_time > 2000 ? '#F59E0B' : '#10B981'
            }))
          }
          height={250}
        />
        
        {/* 成功率分布 */}
        <SimpleChart
          type="bar"
          title="账户成功率 (%)"
          data={accounts
            .sort((a, b) => a.success_rate - b.success_rate)
            .slice(0, 5)
            .map(account => ({
              label: account.account_name.length > 10 
                ? account.account_name.substring(0, 10) + '...' 
                : account.account_name,
              value: account.success_rate,
              color: account.success_rate >= 95 ? '#10B981' : 
                     account.success_rate >= 80 ? '#F59E0B' : '#EF4444'
            }))
          }
          height={250}
        />
      </div>
    </div>
  );
};

export default ClaudeDashboard;