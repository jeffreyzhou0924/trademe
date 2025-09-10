import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import LoadingSpinner from '@/components/common/LoadingSpinner';

// 数据可用性接口
interface DataAvailability {
  exchange?: string;
  symbol: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  total_records?: number;
  missing_periods?: string[];
  completeness_percent?: number;
  // 新增查询API返回字段
  record_count?: number;
  timeframes_count?: number;
  earliest_date?: string;
  latest_date?: string;
}

// OKX统计信息接口
interface OKXStatistics {
  download_statistics: {
    total_downloads: number;
    successful_downloads: number;
    failed_downloads: number;
    total_files_processed: number;
    total_records_downloaded: number;
  };
  supported_symbols: {
    tick_data: string[];
    kline_data: string[];
  };
  supported_timeframes: string[];
}

interface DataStats {
  kline_statistics: Array<{
    exchange: string;
    symbol_count: number;
    timeframe_count: number;
    total_records: number;
  }>;
}

interface OKXDownloadRequest {
  data_type: 'kline' | 'tick';
  market_type: 'spot' | 'futures';
  symbols: string[];
  timeframes: string[];
  start_date: string;
  end_date: string;
  custom_symbol?: string;
}

interface OKXDownloadTask {
  task_id: string;
  data_type: 'tick' | 'kline';
  exchange: string;
  symbols: string[];
  date_range: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  total_files: number;
  processed_files: number;
  downloaded_records: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string;
  timeframes?: string[];
}

// 质量监控接口
interface QualityMetrics {
  completeness: {
    kline_completeness: number;
    tick_completeness: number;
    missing_dates: string[];
  };
  accuracy: {
    price_anomalies: number;
    volume_anomalies: number;
  };
}

interface MissingDataRecord {
  symbol: string;
  data_type: string;
  timeframe: string;
  missing_period: string;
  missing_count: number;
  severity: 'critical' | 'warning';
}

const DataManagementPageReal = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const [stats, setStats] = useState<DataStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'okx-download' | 'quality'>('overview');
  
  // OKX数据下载状态  
  const [okxDownloadType, setOkxDownloadType] = useState<'tick' | 'kline'>('kline');
  const [marketType, setMarketType] = useState<'spot' | 'futures'>('spot');
  const [customSymbol, setCustomSymbol] = useState('');
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(['BTC/USDT']);
  const [okxTasks, setOkxTasks] = useState<OKXDownloadTask[]>([]);
  const [okxDownloading, setOkxDownloading] = useState(false);
  
  // 安全的日期初始化
  const [startDate, setStartDate] = useState<string>(() => {
    try {
      return new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().substring(0, 10);
    } catch {
      return '2025-08-24';
    }
  });
  const [endDate, setEndDate] = useState<string>(() => {
    try {
      return new Date().toISOString().substring(0, 10);
    } catch {
      return '2025-08-31';
    }
  });

  // 真实数据状态
  const [dataAvailability, setDataAvailability] = useState<DataAvailability[]>([]);
  const [dataSummary, setDataSummary] = useState<any>(null); // 查询数据统计摘要
  const [okxStatistics, setOKXStatistics] = useState<OKXStatistics | null>(null);
  const [loadingOverview, setLoadingOverview] = useState(false);

  // 质量监控状态
  const [qualityMetrics, setQualityMetrics] = useState<QualityMetrics | null>(null);
  const [missingData, setMissingData] = useState<MissingDataRecord[]>([]);
  const [checkingQuality, setCheckingQuality] = useState(false);

  // 新的交易对配置
  const getSymbolsByMarketType = (marketType: 'spot' | 'futures', dataType: 'kline' | 'tick') => {
    if (marketType === 'spot') {
      if (dataType === 'tick') {
        return ['BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'SOL', 'ADA', 'AVAX', 'MATIC', 'DOGE'];
      } else {
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT', 'LINK/USDT', 'MATIC/USDT', 'AVAX/USDT', 'XRP/USDT', 'DOGE/USDT'];
      }
    } else {
      if (dataType === 'tick') {
        return ['BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'SOL', 'ADA', 'AVAX'];
      } else {
        return ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP', 'ADA-USDT-SWAP', 'DOT-USDT-SWAP', 'LINK-USDT-SWAP'];
      }
    }
  };

  const okxTimeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w'];

  // 检查管理员权限
  useEffect(() => {
    if (!token || !user) {
      navigate('/login');
      return;
    }

    if (user.membership_level !== 'professional') {
      setError('需要专业版权限才能访问数据管理中心');
      setLoading(false);
      return;
    }
  }, [token, user, navigate]);

  // 获取数据统计
  const fetchDataStats = async () => {
    try {
      const response = await fetch('/api/v1/data/storage/stats', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        setStats(result.data);
      } else {
        throw new Error(result.detail || '数据获取失败');
      }
      
      setLoading(false);
    } catch (error) {
      console.error('获取数据统计失败:', error);
      setError(error instanceof Error ? error.message : '数据获取失败');
      setLoading(false);
    }
  };

  // 获取OKX统计信息
  const fetchOKXStatistics = async () => {
    try {
      const response = await fetch('/api/v1/data/okx/statistics', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const result = await response.json();
      if (result.success) {
        setOKXStatistics(result.data);
      }
    } catch (error) {
      console.error('获取OKX统计失败:', error);
    }
  };

  // 获取数据可用性信息 - 修复版本，使用相对路径避免跨域问题
  const fetchDataAvailability = async () => {
    setLoadingOverview(true);
    try {
      // 使用相对路径，通过nginx代理到后端
      const apiUrl = `/api/v1/data/query?data_type=kline&exchange=okx&symbol=BTC-USDT-SWAP`;
      
      const response = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`数据查询失败: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success && result.data.query_result) {
        // 转换查询结果为显示格式，现在返回的已经是详细的timeframe数据
        const converted = result.data.query_result.map((item: any) => ({
          exchange: 'OKX',
          symbol: item.symbol,
          timeframe: item.timeframe,
          record_count: item.record_count,
          earliest_date: item.start_date,
          latest_date: item.end_date,
          timeframes_count: 1
        }));
        setDataAvailability(converted);
      } else {
        setDataAvailability([]);
      }
      
    } catch (error) {
      console.error('获取数据可用性失败:', error);
      setDataAvailability([]);
    } finally {
      setLoadingOverview(false);
    }
  };

  // 获取OKX任务列表
  const fetchOkxTasks = async () => {
    try {
      const response = await fetch('/api/v1/data/okx/tasks', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const result = await response.json();
      if (result.success && Array.isArray(result.data)) {
        setOkxTasks(result.data);
      } else {
        console.warn('OKX tasks data is not an array:', result.data);
        setOkxTasks([]);
      }
    } catch (error) {
      console.error('获取OKX任务列表失败:', error);
    }
  };

  // 启动OKX数据下载
  const startOkxDownload = async () => {
    if (!Array.isArray(selectedSymbols) || selectedSymbols.length === 0) {
      alert('请选择至少一个交易对');
      return;
    }

    setOkxDownloading(true);
    try {
      const endpoint = okxDownloadType === 'tick' 
        ? '/api/v1/data/okx/tick/download' 
        : '/api/v1/data/okx/kline/download';

      // 安全的日期格式化函数
      const formatDate = (date: string) => {
        try {
          if (typeof date !== 'string' || !date) {
            return new Date().toISOString().substring(0, 10).replace(/-/g, '');
          }
          return date.replace(/-/g, '');
        } catch (error) {
          console.error('Date formatting error:', error);
          return '20250831';
        }
      };
      
      const requestBody = okxDownloadType === 'tick' 
        ? {
            symbols: selectedSymbols.filter(s => typeof s === 'string' && s.length > 0),
            start_date: formatDate(startDate),
            end_date: formatDate(endDate)
          }
        : {
            symbols: selectedSymbols.filter(s => typeof s === 'string' && s.length > 0),
            timeframes: okxTimeframes,
            start_date: formatDate(startDate),
            end_date: formatDate(endDate)
          };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      });
      
      const result = await response.json();
      
      if (result.success) {
        alert(`OKX ${okxDownloadType === 'tick' ? 'Tick' : 'K线'}数据下载任务已启动！任务ID: ${result.data.task_id}`);
        await fetchOkxTasks();
      } else {
        throw new Error(result.detail || '下载启动失败');
      }
    } catch (error) {
      alert(error instanceof Error ? error.message : 'OKX下载启动失败');
    } finally {
      setOkxDownloading(false);
    }
  };

  // 数据质量检查 - 使用真实API
  const runQualityCheck = async () => {
    setCheckingQuality(true);
    try {
      const symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];
      const timeframes = ['1h', '1d'];
      const checkDays = 7;
      
      const qualityPromises = [];
      let allMissingData: MissingDataRecord[] = [];
      
      for (const symbol of symbols) {
        for (const timeframe of timeframes) {
          qualityPromises.push(
            fetch(`/api/v1/data/quality/check/okx/${symbol}/${timeframe}?check_days=${checkDays}`, {
              headers: { 'Authorization': `Bearer ${token}` }
            }).then(res => res.json()).then(result => {
              if (result.success && result.data) {
                // 收集缺失数据
                if (result.data.missing_periods && result.data.missing_periods.length > 0) {
                  result.data.missing_periods.forEach((period: any) => {
                    allMissingData.push({
                      symbol,
                      data_type: 'K线',
                      timeframe,
                      missing_period: period.period || period,
                      missing_count: period.count || 0,
                      severity: period.count > 100 ? 'critical' : 'warning'
                    });
                  });
                }
                return result.data;
              }
              return null;
            }).catch(() => null)
          );
        }
      }
      
      const results = await Promise.all(qualityPromises);
      const validResults = results.filter(r => r !== null);
      
      if (validResults.length > 0) {
        // 计算总体完整性
        const totalChecked = validResults.length;
        const completeResults = validResults.filter(r => r.completeness_percent >= 95).length;
        const overallCompleteness = totalChecked > 0 ? (completeResults / totalChecked) * 100 : 0;
        
        setQualityMetrics({
          completeness: {
            kline_completeness: overallCompleteness,
            tick_completeness: 0, // Tick数据需要单独检查
            missing_dates: []
          },
          accuracy: {
            price_anomalies: validResults.reduce((sum, r) => sum + (r.anomalies?.price_anomalies || 0), 0),
            volume_anomalies: validResults.reduce((sum, r) => sum + (r.anomalies?.volume_anomalies || 0), 0)
          }
        });
      } else {
        // 如果没有返回数据，使用默认值
        setQualityMetrics({
          completeness: {
            kline_completeness: 0,
            tick_completeness: 0,
            missing_dates: []
          },
          accuracy: {
            price_anomalies: 0,
            volume_anomalies: 0
          }
        });
      }
      
      setMissingData(allMissingData);
      
    } catch (error) {
      console.error('质量检查失败:', error);
      alert('质量检查失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setCheckingQuality(false);
    }
  };

  // 当进入概览页面时自动加载数据
  useEffect(() => {
    if (activeTab === 'overview' && token) {
      fetchOKXStatistics();
      fetchDataAvailability();
    }
  }, [activeTab, token]);

  // 组件挂载时获取数据
  useEffect(() => {
    if (token && user) {
      fetchDataStats();
      fetchOkxTasks();
    }
  }, [token, user]);

  // 定期刷新OKX任务状态
  useEffect(() => {
    if (activeTab === 'okx-download') {
      const interval = setInterval(fetchOkxTasks, 3000);
      return () => clearInterval(interval);
    }
  }, [activeTab, token]);

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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">数据管理中心</h1>
                <p className="text-sm text-gray-600">完全集成后端API的数据管理系统</p>
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
              { id: 'overview', name: '数据概览', icon: '📊' },
              { id: 'okx-download', name: 'OKX数据下载', icon: '🚀' },
              { id: 'quality', name: '质量监控', icon: '🔍' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200 ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
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
        {/* 数据概览 - 使用真实API */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">真实API数据统计概览</h2>
              <button
                onClick={() => {
                  fetchDataStats();
                  fetchOKXStatistics();
                  fetchDataAvailability();
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200 flex items-center space-x-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>刷新数据</span>
              </button>
            </div>

            {/* 数据库现有数据概览 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">数据库真实数据概览</h3>
              <p className="text-sm text-gray-600 mb-6">显示我们后台现有的所有数据，按交易所、数据类型、市场类型分组</p>
              
              {/* 加载状态 */}
              {loadingOverview ? (
                <div className="flex justify-center items-center py-8">
                  <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="ml-2 text-gray-600">加载数据中...</span>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* OKX 统计信息 */}
                  {okxStatistics && (
                    <div className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center mb-4">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-3">
                          <span className="text-blue-600 font-bold text-sm">OKX</span>
                        </div>
                        <h4 className="text-lg font-semibold text-gray-900">OKX 交易所数据统计</h4>
                      </div>

                      {/* 下载统计 */}
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
                        <h5 className="font-semibold text-gray-800 mb-3">📊 下载统计</h5>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold text-blue-600">{okxStatistics.download_statistics.total_downloads}</div>
                            <div className="text-sm text-gray-600">总下载次数</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-green-600">{okxStatistics.download_statistics.successful_downloads}</div>
                            <div className="text-sm text-gray-600">成功下载</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-red-600">{okxStatistics.download_statistics.failed_downloads}</div>
                            <div className="text-sm text-gray-600">失败次数</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-purple-600">{okxStatistics.download_statistics.total_files_processed}</div>
                            <div className="text-sm text-gray-600">处理文件数</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-orange-600">{(okxStatistics.download_statistics.total_records_downloaded / 1000000).toFixed(1)}M</div>
                            <div className="text-sm text-gray-600">下载记录数</div>
                          </div>
                        </div>
                      </div>

                      {/* 支持的交易对 */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                          <h5 className="font-semibold text-blue-800 mb-2">📈 K线数据支持的交易对</h5>
                          <div className="text-sm">
                            <div className="mb-1">总计: <span className="font-medium text-blue-700">{okxStatistics.supported_symbols.kline_data.length}个</span></div>
                            <div className="text-gray-600 max-h-20 overflow-y-auto">
                              {okxStatistics.supported_symbols.kline_data.slice(0, 10).join(', ')}
                              {okxStatistics.supported_symbols.kline_data.length > 10 && '...'}
                            </div>
                          </div>
                        </div>

                        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                          <h5 className="font-semibold text-green-800 mb-2">⚡ Tick数据支持的交易对</h5>
                          <div className="text-sm">
                            <div className="mb-1">总计: <span className="font-medium text-green-700">{okxStatistics.supported_symbols.tick_data.length}个</span></div>
                            <div className="text-gray-600 max-h-20 overflow-y-auto">
                              {okxStatistics.supported_symbols.tick_data.slice(0, 10).join(', ')}
                              {okxStatistics.supported_symbols.tick_data.length > 10 && '...'}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* 支持的时间框架 */}
                      <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <h5 className="font-semibold text-yellow-800 mb-2">⏰ 支持的时间框架</h5>
                        <div className="flex flex-wrap gap-2">
                          {okxStatistics.supported_timeframes.map(tf => (
                            <span key={tf} className="px-2 py-1 bg-yellow-200 text-yellow-800 rounded text-sm font-medium">
                              {tf}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}


                  {/* 数据加载提示 */}
                  {!okxStatistics && !loadingOverview && (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
                      <div className="text-4xl mb-4">📊</div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">数据统计信息</h3>
                      <p className="text-gray-600 mb-4">请点击上方"刷新数据"按钮加载最新数据</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 数据查询面板 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">🔍 数据查询工具</h3>
              <p className="text-sm text-gray-600 mb-6">查询数据库中的真实数据情况，了解具体的数据日期范围</p>
              
              {/* 查询选择器 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">数据类型</label>
                  <select 
                    value={okxDownloadType}
                    onChange={(e) => setOkxDownloadType(e.target.value as 'tick' | 'kline')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="kline">K线数据</option>
                    <option value="tick">Tick数据</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">市场类型</label>
                  <select 
                    value={marketType}
                    onChange={(e) => setMarketType(e.target.value as 'spot' | 'futures')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="spot">现货市场</option>
                    <option value="futures">合约市场</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">交易对</label>
                  <select 
                    value={selectedSymbols[0] || ''}
                    onChange={(e) => setSelectedSymbols(e.target.value ? [e.target.value] : [])}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">全部</option>
                    {getSymbolsByMarketType(marketType, okxDownloadType).map(symbol => (
                      <option key={symbol} value={symbol}>{symbol}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center space-x-4 mb-6">
                <button
                  onClick={async () => {
                    setLoadingOverview(true);
                    try {
                      const symbol = selectedSymbols[0] || null;
                      const apiUrl = symbol 
                        ? `/api/v1/data/query?data_type=${okxDownloadType}&exchange=okx&symbol=${encodeURIComponent(symbol)}`
                        : `/api/v1/data/query?data_type=${okxDownloadType}&exchange=okx`;
                      
                      // 正确获取token
                      const authData = localStorage.getItem('auth-storage');
                      const token = authData ? JSON.parse(authData).state.token : null;
                      
                      if (!token) {
                        throw new Error('未找到认证令牌，请重新登录');
                      }
                      
                      const response = await fetch(apiUrl, {
                        headers: {
                          'Authorization': `Bearer ${token}`,
                          'Content-Type': 'application/json'
                        }
                      });

                      if (!response.ok) {
                        throw new Error(`HTTP错误: ${response.status}`);
                      }

                      const result = await response.json();
                      if (result.success) {
                        setDataAvailability(result.data.query_result || []);
                        setDataSummary(result.data.summary || null);
                      } else {
                        console.error('查询失败:', result);
                      }
                    } catch (error) {
                      console.error('查询数据失败:', error);
                    } finally {
                      setLoadingOverview(false);
                    }
                  }}
                  disabled={loadingOverview}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors duration-200 flex items-center space-x-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <span>查询数据</span>
                </button>

                <button
                  onClick={() => {
                    setDataAvailability([]);
                  }}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors duration-200"
                >
                  清除结果
                </button>
              </div>

              {/* 查询结果 */}
              {loadingOverview && (
                <div className="flex justify-center items-center py-8">
                  <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="ml-2 text-gray-600">查询中...</span>
                </div>
              )}

              {dataAvailability.length > 0 && !loadingOverview && (
                <div className="border border-gray-200 rounded-lg p-4">
                  <h4 className="text-lg font-semibold text-gray-900 mb-4">📊 查询结果</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {dataAvailability.map((data, index) => (
                      <div key={index} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <h5 className="font-semibold text-gray-800">{data.symbol}</h5>
                          {data.timeframe && (
                            <span className="text-sm text-blue-600 bg-blue-100 px-2 py-1 rounded">{data.timeframe}</span>
                          )}
                        </div>
                        <div className="space-y-1 text-sm">
                          {data.start_date && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">开始日期:</span>
                              <span className="font-medium">{new Date(data.start_date).toLocaleDateString()}</span>
                            </div>
                          )}
                          {data.end_date && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">结束日期:</span>
                              <span className="font-medium">{new Date(data.end_date).toLocaleDateString()}</span>
                            </div>
                          )}
                          {data.record_count && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">记录数:</span>
                              <span className="font-medium text-blue-600">{data.record_count.toLocaleString()}</span>
                            </div>
                          )}
                          {data.total_records && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">总记录:</span>
                              <span className="font-medium text-green-600">{data.total_records.toLocaleString()}</span>
                            </div>
                          )}
                          {data.timeframes_count && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">时间框架数:</span>
                              <span className="font-medium text-purple-600">{data.timeframes_count}</span>
                            </div>
                          )}
                          {data.earliest_date && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">最早数据:</span>
                              <span className="font-medium">{new Date(data.earliest_date).toLocaleDateString()}</span>
                            </div>
                          )}
                          {data.latest_date && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">最新数据:</span>
                              <span className="font-medium">{new Date(data.latest_date).toLocaleDateString()}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 统计摘要显示 */}
              {dataSummary && !loadingOverview && (
                <div className="bg-gradient-to-r from-blue-50 to-green-50 border border-blue-200 rounded-lg p-6 mt-4">
                  <h4 className="text-lg font-semibold text-gray-900 mb-4">📈 数据统计摘要</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                    {dataSummary.total_records && (
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">{dataSummary.total_records.toLocaleString()}</div>
                        <div className="text-sm text-gray-600">总记录数</div>
                      </div>
                    )}
                    {dataSummary.data_completeness_percent !== undefined && (
                      <div className="text-center">
                        <div className={`text-2xl font-bold ${dataSummary.data_completeness_percent >= 95 ? 'text-green-600' : 'text-yellow-600'}`}>
                          {dataSummary.data_completeness_percent}%
                        </div>
                        <div className="text-sm text-gray-600">数据完整度</div>
                      </div>
                    )}
                    {dataSummary.timeframes_available && (
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">{dataSummary.timeframes_available}</div>
                        <div className="text-sm text-gray-600">时间框架</div>
                      </div>
                    )}
                    {dataSummary.days_span && (
                      <div className="text-center">
                        <div className="text-2xl font-bold text-orange-600">{dataSummary.days_span}</div>
                        <div className="text-sm text-gray-600">天数跨度</div>
                      </div>
                    )}
                    {dataSummary.earliest_date && (
                      <div className="text-center">
                        <div className="text-sm font-medium text-gray-800">{new Date(dataSummary.earliest_date).toLocaleDateString()}</div>
                        <div className="text-sm text-gray-600">最早日期</div>
                      </div>
                    )}
                    {dataSummary.latest_date && (
                      <div className="text-center">
                        <div className="text-sm font-medium text-gray-800">{new Date(dataSummary.latest_date).toLocaleDateString()}</div>
                        <div className="text-sm text-gray-600">最新日期</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!loadingOverview && dataAvailability.length === 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
                  <div className="text-4xl mb-4">📊</div>
                  <h4 className="text-lg font-semibold text-gray-900 mb-2">暂无查询结果</h4>
                  <p className="text-gray-600">请点击"查询数据"按钮来查看数据库中的真实数据情况</p>
                </div>
              )}
            </div>

          </div>
        )}

        {/* OKX数据下载保持原样 */}
        {activeTab === 'okx-download' && (
          <div className="space-y-6">
            {/* 数据类型选择 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-6">OKX 数据下载中心</h2>
              
              <div className="space-y-6">
                {/* 数据类型选择 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">数据类型</label>
                  <div className="flex space-x-4">
                    <button 
                      onClick={() => setOkxDownloadType('kline')}
                      className={`px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                        okxDownloadType === 'kline' 
                          ? 'bg-blue-600 text-white shadow-md' 
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      📈 K线数据
                    </button>
                    <button 
                      onClick={() => setOkxDownloadType('tick')}
                      className={`px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                        okxDownloadType === 'tick' 
                          ? 'bg-blue-600 text-white shadow-md' 
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      ⚡ Tick数据
                    </button>
                  </div>
                </div>

                {/* 市场类型选择 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">市场类型</label>
                  <div className="flex space-x-4">
                    <button 
                      onClick={() => setMarketType('spot')}
                      className={`px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                        marketType === 'spot' 
                          ? 'bg-green-600 text-white shadow-md' 
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      💰 现货市场
                    </button>
                    <button 
                      onClick={() => setMarketType('futures')}
                      className={`px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                        marketType === 'futures' 
                          ? 'bg-orange-600 text-white shadow-md' 
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      📈 合约市场 (永续)
                    </button>
                  </div>
                </div>

                {/* 交易对选择 */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium text-gray-700">交易对选择</label>
                    <button 
                      onClick={() => {
                        try {
                          const symbols = getSymbolsByMarketType(marketType, okxDownloadType);
                          if (Array.isArray(symbols)) {
                            setSelectedSymbols(symbols);
                          }
                        } catch (error) {
                          console.error('Error selecting all symbols:', error);
                          setSelectedSymbols([]);
                        }
                      }}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      全选所有
                    </button>
                  </div>
                  
                  {/* 交易对网格 */}
                  <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2 mb-4">
                    {getSymbolsByMarketType(marketType, okxDownloadType).map(symbol => (
                      <label key={symbol} className="flex items-center space-x-2 p-2 border rounded cursor-pointer hover:bg-gray-50">
                        <input 
                          type="checkbox" 
                          checked={Array.isArray(selectedSymbols) && selectedSymbols.includes(symbol)}
                          onChange={(e) => {
                            if (!Array.isArray(selectedSymbols)) {
                              setSelectedSymbols([]);
                              return;
                            }
                            if (e.target.checked) {
                              setSelectedSymbols([...selectedSymbols, symbol]);
                            } else {
                              setSelectedSymbols(selectedSymbols.filter(s => s !== symbol));
                            }
                          }}
                          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                        <span className="text-sm font-medium text-gray-700">{symbol}</span>
                      </label>
                    ))}
                  </div>

                  {/* 自定义交易对输入 */}
                  <div className="flex items-center space-x-2">
                    <input 
                      type="text" 
                      value={customSymbol}
                      onChange={(e) => setCustomSymbol(e.target.value)}
                      placeholder={marketType === 'spot' 
                        ? (okxDownloadType === 'tick' ? "输入现货Tick交易对 (如: DOGE)" : "输入现货K线交易对 (如: DOGE/USDT)") 
                        : (okxDownloadType === 'tick' ? "输入合约Tick交易对 (如: DOGE)" : "输入合约K线交易对 (如: DOGE-USDT-SWAP)")}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button 
                      onClick={() => {
                        if (customSymbol && customSymbol.trim() && Array.isArray(selectedSymbols) && !selectedSymbols.includes(customSymbol.trim())) {
                          setSelectedSymbols([...selectedSymbols, customSymbol.trim()]);
                          setCustomSymbol('');
                        }
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200"
                    >
                      添加
                    </button>
                  </div>

                  {/* 已选交易对显示 */}
                  <div className="mt-3">
                    <div className="text-sm text-gray-600 mb-2">已选择 {Array.isArray(selectedSymbols) ? selectedSymbols.length : 0} 个交易对：</div>
                    <div className="flex flex-wrap gap-2">
                      {Array.isArray(selectedSymbols) && selectedSymbols.map(symbol => (
                        <span key={symbol} className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm flex items-center space-x-1">
                          <span>{symbol}</span>
                          <button 
                            onClick={() => {
                              if (Array.isArray(selectedSymbols)) {
                                setSelectedSymbols(selectedSymbols.filter(s => s !== symbol));
                              }
                            }}
                            className="text-blue-600 hover:text-blue-800"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 时间范围选择 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">时间范围选择</label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">开始日期</label>
                      <input 
                        type="date" 
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">结束日期</label>
                      <input 
                        type="date" 
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-3">
                    <div className="text-sm text-gray-600">
                      选择的时间范围: {startDate} 到 {endDate}
                    </div>
                    <div className="flex space-x-2">
                      <button 
                        onClick={() => {
                          const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().substring(0, 10);
                          const today = new Date().toISOString().substring(0, 10);
                          setStartDate(sevenDaysAgo);
                          setEndDate(today);
                        }}
                        className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200 transition-colors"
                      >
                        最近7天
                      </button>
                      <button 
                        onClick={() => {
                          const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().substring(0, 10);
                          const today = new Date().toISOString().substring(0, 10);
                          setStartDate(thirtyDaysAgo);
                          setEndDate(today);
                        }}
                        className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200 transition-colors"
                      >
                        最近30天
                      </button>
                      <button 
                        onClick={() => {
                          const threeMonthsAgo = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().substring(0, 10);
                          const today = new Date().toISOString().substring(0, 10);
                          setStartDate(threeMonthsAgo);
                          setEndDate(today);
                        }}
                        className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200 transition-colors"
                      >
                        最近3个月
                      </button>
                    </div>
                  </div>
                </div>

                {/* 时间框架 - 默认全选 */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h3 className="font-semibold mb-2 text-gray-900">时间框架 (自动全选)</h3>
                  <div className="flex flex-wrap gap-2">
                    {okxTimeframes.map(tf => (
                      <span key={tf} className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                        ✓ {tf}
                      </span>
                    ))}
                  </div>
                  <p className="text-sm text-gray-600 mt-2">所有时间框架将自动下载，无需手动选择</p>
                </div>

                {/* 下载按钮 */}
                <div className="flex justify-center pt-4">
                  <button
                    onClick={startOkxDownload}
                    disabled={okxDownloading || !Array.isArray(selectedSymbols) || selectedSymbols.length === 0}
                    className={`px-8 py-3 rounded-lg font-semibold transition-all duration-200 ${
                      okxDownloading || !Array.isArray(selectedSymbols) || selectedSymbols.length === 0
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-700 hover:to-blue-800 shadow-lg hover:shadow-xl'
                    }`}
                  >
                    {okxDownloading ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        正在启动下载...
                      </>
                    ) : (
                      <>
                        🚀 开始下载 {okxDownloadType === 'tick' ? 'Tick' : 'K线'}数据 
                        ({Array.isArray(selectedSymbols) ? selectedSymbols.length : 0} 个交易对)
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* OKX任务列表 */}
            <div className="bg-white rounded-xl shadow-sm border">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold">下载任务列表</h3>
              </div>
              <div className="p-6">
                {!Array.isArray(okxTasks) || okxTasks.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    暂无下载任务
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Array.isArray(okxTasks) && okxTasks.slice(0, 5).map((task) => (
                      <div key={task.task_id} className="border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-3">
                            <div className={`w-3 h-3 rounded-full ${
                              task.status === 'completed' ? 'bg-green-500' :
                              task.status === 'running' ? 'bg-blue-500' :
                              task.status === 'failed' ? 'bg-red-500' : 'bg-gray-400'
                            }`}></div>
                            <span className="font-medium">{task.data_type.toUpperCase()} - {task.symbols.join(', ')}</span>
                          </div>
                          <span className={`px-3 py-1 rounded-full text-sm ${
                            task.status === 'completed' ? 'bg-green-100 text-green-800' :
                            task.status === 'running' ? 'bg-blue-100 text-blue-800' :
                            task.status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                          }`}>
                            {task.status}
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                            style={{ width: `${task.progress}%` }}
                          ></div>
                        </div>
                        <div className="text-sm text-gray-600 mt-1">
                          {task.progress}% - {task.processed_files}/{task.total_files} 文件
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 质量监控 - 使用真实API */}
        {activeTab === 'quality' && (
          <div className="space-y-6">
            {/* 检测控制面板 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">数据完整性检测 (真实API)</h2>
                <div className="flex space-x-3">
                  <button 
                    onClick={runQualityCheck}
                    disabled={checkingQuality}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
                  >
                    🔍 开始检测
                  </button>
                  <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
                    📊 生成报告
                  </button>
                </div>
              </div>

              <p className="text-sm text-gray-600">使用真实API检测数据完整性，精确定位每个缺失时段</p>
            </div>

            {/* 完整性概览仪表板 */}
            {qualityMetrics && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* K线数据完整性 */}
                <div className="bg-white rounded-xl p-6 shadow-sm border">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-900">K线数据完整性</h3>
                    <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
                      <span className="text-lg font-bold text-green-600">{qualityMetrics.completeness.kline_completeness.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">检查结果:</span>
                      <span className="font-medium">真实API数据</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">完整性:</span>
                      <span className="font-medium">{qualityMetrics.completeness.kline_completeness.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-red-600">异常数据:</span>
                      <span className="font-medium text-red-600">{qualityMetrics.accuracy.price_anomalies} 处</span>
                    </div>
                  </div>
                </div>

                {/* Tick数据完整性 */}  
                <div className="bg-white rounded-xl p-6 shadow-sm border">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-900">Tick数据完整性</h3>
                    <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
                      <span className="text-lg font-bold text-blue-600">{qualityMetrics.completeness.tick_completeness.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">检查结果:</span>
                      <span className="font-medium">待实现</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">完整性:</span>
                      <span className="font-medium">{qualityMetrics.completeness.tick_completeness.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-red-600">成交量异常:</span>
                      <span className="font-medium text-red-600">{qualityMetrics.accuracy.volume_anomalies} 处</span>
                    </div>
                  </div>
                </div>

                {/* 数据异常检测 */}
                <div className="bg-white rounded-xl p-6 shadow-sm border">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-900">数据异常检测</h3>
                    <div className="w-16 h-16 rounded-full bg-yellow-100 flex items-center justify-center">
                      <span className="text-2xl">⚠️</span>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">价格异常:</span>
                      <span className="font-medium text-yellow-600">{qualityMetrics.accuracy.price_anomalies} 处</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">成交量异常:</span>
                      <span className="font-medium text-yellow-600">{qualityMetrics.accuracy.volume_anomalies} 处</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 详细缺失分析表 */}
            {missingData.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm border">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h3 className="text-lg font-semibold">详细缺失分析 (真实API数据)</h3>
                  <p className="text-sm text-gray-600">基于真实API检测结果，精确定位每个缺失时段</p>
                </div>
                <div className="p-6">
                  <div className="overflow-x-auto">
                    <table className="min-w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">交易对</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">数据类型</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">时间框架</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">缺失时段</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">缺失数量</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">严重程度</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {missingData.map((record, index) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium">{record.symbol}</td>
                            <td className="px-4 py-3 text-sm">{record.data_type}</td>
                            <td className="px-4 py-3 text-sm">{record.timeframe}</td>
                            <td className="px-4 py-3 text-sm">{record.missing_period}</td>
                            <td className="px-4 py-3 text-sm text-red-600">{record.missing_count === 0 ? '全时段' : `${record.missing_count}条`}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 text-xs rounded ${
                                record.severity === 'critical' 
                                  ? 'bg-red-100 text-red-800' 
                                  : 'bg-yellow-100 text-yellow-800'
                              }`}>
                                {record.severity === 'critical' ? 'Critical' : 'Warning'}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <button className="text-blue-600 hover:text-blue-800 text-sm">补全下载</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {!qualityMetrics && !checkingQuality && (
              <div className="bg-white rounded-xl p-12 shadow-sm border text-center">
                <div className="text-6xl mb-4">🔍</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">数据质量检测 (真实API)</h3>
                <p className="text-gray-600 mb-4">点击"开始检测"按钮运行真实API数据完整性分析</p>
                <button 
                  onClick={runQualityCheck}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  🚀 开始质量检测
                </button>
              </div>
            )}

            {checkingQuality && (
              <div className="bg-white rounded-xl p-12 shadow-sm border text-center">
                <div className="flex justify-center items-center mb-4">
                  <svg className="animate-spin h-12 w-12 text-blue-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">正在执行质量检测...</h3>
                <p className="text-gray-600">调用真实API检测数据完整性，请稍候</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DataManagementPageReal;