/**
 * 回测结果卡片组件 - 在AI对话中展示回测摘要
 * 支持展开/收起查看详细结果
 */
import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { BacktestResult } from '../../types/backtest';

interface BacktestResultCardProps {
  result: BacktestResult;
  className?: string;
}

export const BacktestResultCard: React.FC<BacktestResultCardProps> = ({
  result,
  className = ''
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // 计算关键指标
  const totalReturn = ((result.final_value - result.initial_capital) / result.initial_capital * 100);
  const isProfit = totalReturn > 0;
  
  // 获取风险等级颜色
  const getRiskColor = (risk: string) => {
    switch (risk?.toLowerCase()) {
      case 'low': return 'text-green-600';
      case 'medium': return 'text-yellow-600';
      case 'high': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };
  
  // 获取收益率颜色
  const getReturnColor = (returnRate: number) => {
    if (returnRate > 10) return 'text-green-600';
    if (returnRate > 0) return 'text-green-500';
    return 'text-red-500';
  };

  return (
    <div className={`bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg shadow-sm ${className}`}>
      {/* 回测结果头部摘要 */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <span className="text-sm font-medium text-gray-700">📊 回测结果</span>
            <span className={`text-xs px-2 py-1 rounded-full ${
              result.performance_grade === 'A' ? 'bg-green-100 text-green-700' :
              result.performance_grade === 'B' ? 'bg-blue-100 text-blue-700' :
              result.performance_grade === 'C' ? 'bg-yellow-100 text-yellow-700' :
              'bg-red-100 text-red-700'
            }`}>
              {result.performance_grade} 级
            </span>
          </div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center text-sm text-blue-600 hover:text-blue-800"
          >
            {isExpanded ? '收起详情' : '查看详情'}
            {isExpanded ? (
              <ChevronUpIcon className="w-4 h-4 ml-1" />
            ) : (
              <ChevronDownIcon className="w-4 h-4 ml-1" />
            )}
          </button>
        </div>
        
        {/* 关键指标摘要 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="text-center">
            <div className={`text-lg font-bold ${getReturnColor(totalReturn)}`}>
              {totalReturn.toFixed(2)}%
            </div>
            <div className="text-xs text-gray-500">总收益率</div>
          </div>
          
          <div className="text-center">
            <div className="text-lg font-bold text-gray-800">
              {result.sharpe_ratio?.toFixed(2) || 'N/A'}
            </div>
            <div className="text-xs text-gray-500">夏普比率</div>
          </div>
          
          <div className="text-center">
            <div className="text-lg font-bold text-red-600">
              -{result.max_drawdown?.toFixed(2) || 'N/A'}%
            </div>
            <div className="text-xs text-gray-500">最大回撤</div>
          </div>
          
          <div className="text-center">
            <div className="text-lg font-bold text-blue-600">
              {result.win_rate?.toFixed(1) || 'N/A'}%
            </div>
            <div className="text-xs text-gray-500">胜率</div>
          </div>
        </div>
        
        {/* 简要总结 */}
        <div className="mt-3 p-2 bg-white rounded border-l-4 border-blue-400">
          <p className="text-sm text-gray-700">
            {result.meets_expectations ? 
              `✅ 策略表现达到预期，建议关注${result.optimization_suggestions?.[0] || '风险管理'}` :
              `⚠️ 策略需要优化，主要问题：${result.optimization_suggestions?.[0] || '收益不稳定'}`
            }
          </p>
        </div>
      </div>
      
      {/* 展开的详细信息 */}
      {isExpanded && (
        <div className="border-t border-blue-200 bg-white">
          <div className="p-4 space-y-4">
            {/* 详细性能指标 */}
            <div>
              <h4 className="text-sm font-semibold text-gray-800 mb-2">📈 详细性能指标</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">初始资金：</span>
                  <span className="font-medium">${result.initial_capital?.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-gray-600">最终价值：</span>
                  <span className={`font-medium ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                    ${result.final_value?.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600">交易次数：</span>
                  <span className="font-medium">{result.total_trades || 0}</span>
                </div>
                <div>
                  <span className="text-gray-600">盈利交易：</span>
                  <span className="font-medium text-green-600">{result.winning_trades || 0}</span>
                </div>
                <div>
                  <span className="text-gray-600">亏损交易：</span>
                  <span className="font-medium text-red-600">{result.losing_trades || 0}</span>
                </div>
                <div>
                  <span className="text-gray-600">平均收益：</span>
                  <span className="font-medium">{result.avg_profit?.toFixed(2) || 'N/A'}%</span>
                </div>
              </div>
            </div>
            
            {/* 优化建议 */}
            {result.optimization_suggestions && result.optimization_suggestions.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-800 mb-2">💡 优化建议</h4>
                <ul className="text-sm space-y-1">
                  {result.optimization_suggestions.slice(0, 3).map((suggestion, index) => (
                    <li key={index} className="flex items-start">
                      <span className="text-blue-500 mr-2">•</span>
                      <span className="text-gray-700">{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* 风险分析 */}
            <div>
              <h4 className="text-sm font-semibold text-gray-800 mb-2">⚠️ 风险分析</h4>
              <div className="flex items-center space-x-4 text-sm">
                <div>
                  <span className="text-gray-600">风险等级：</span>
                  <span className={`font-medium ${getRiskColor(result.risk_level)}`}>
                    {result.risk_level || '未评估'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600">波动率：</span>
                  <span className="font-medium">{result.volatility?.toFixed(2) || 'N/A'}%</span>
                </div>
                <div>
                  <span className="text-gray-600">VaR(95%)：</span>
                  <span className="font-medium text-red-600">
                    {result.var_95 ? `${result.var_95.toFixed(2)}%` : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
            
            {/* 操作按钮 */}
            <div className="flex space-x-3 pt-2 border-t border-gray-100">
              <button className="flex-1 bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 transition-colors">
                查看完整报告
              </button>
              <button className="flex-1 bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 transition-colors">
                启动实盘交易
              </button>
              <button className="flex-1 bg-yellow-600 text-white px-4 py-2 rounded text-sm hover:bg-yellow-700 transition-colors">
                优化策略
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BacktestResultCard;