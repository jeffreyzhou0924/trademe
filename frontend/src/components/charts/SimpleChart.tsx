import React from 'react';

interface ChartData {
  label: string;
  value: number;
  color?: string;
}

interface SimpleChartProps {
  data: ChartData[];
  type: 'bar' | 'donut' | 'line';
  title?: string;
  height?: number;
}

const SimpleChart: React.FC<SimpleChartProps> = ({ 
  data, 
  type, 
  title, 
  height = 200 
}) => {
  const maxValue = Math.max(...data.map(d => d.value));

  // 颜色调色板
  const colors = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', 
    '#8B5CF6', '#06B6D4', '#84CC16', '#F97316'
  ];

  if (type === 'bar') {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        {title && <h3 className="text-lg font-medium text-gray-900 mb-4">{title}</h3>}
        <div className="space-y-3" style={{ height }}>
          {data.map((item, index) => (
            <div key={item.label} className="flex items-center">
              <div className="w-24 text-sm text-gray-600 truncate">{item.label}</div>
              <div className="flex-1 mx-3">
                <div className="w-full bg-gray-200 rounded-full h-6 relative">
                  <div
                    className="h-6 rounded-full transition-all duration-500 flex items-center justify-end pr-2"
                    style={{
                      width: `${(item.value / maxValue) * 100}%`,
                      backgroundColor: item.color || colors[index % colors.length]
                    }}
                  >
                    <span className="text-white text-xs font-medium">
                      {item.value.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === 'donut') {
    const total = data.reduce((sum, item) => sum + item.value, 0);
    let cumulativePercent = 0;

    return (
      <div className="bg-white rounded-lg shadow p-4">
        {title && <h3 className="text-lg font-medium text-gray-900 mb-4">{title}</h3>}
        <div className="flex items-center justify-center">
          <div className="relative" style={{ width: height, height: height }}>
            <svg width={height} height={height} className="transform -rotate-90">
              <circle
                cx={height / 2}
                cy={height / 2}
                r={height / 2 - 40}
                fill="none"
                stroke="#E5E7EB"
                strokeWidth="8"
              />
              {data.map((item, index) => {
                const percent = (item.value / total) * 100;
                const dashArray = `${percent} ${100 - percent}`;
                const dashOffset = -cumulativePercent;
                cumulativePercent += percent;

                return (
                  <circle
                    key={item.label}
                    cx={height / 2}
                    cy={height / 2}
                    r={height / 2 - 40}
                    fill="none"
                    stroke={item.color || colors[index % colors.length]}
                    strokeWidth="8"
                    strokeDasharray={dashArray}
                    strokeDashoffset={dashOffset}
                    className="transition-all duration-500"
                  />
                );
              })}
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{total.toLocaleString()}</div>
                <div className="text-sm text-gray-600">总计</div>
              </div>
            </div>
          </div>
          <div className="ml-6 space-y-2">
            {data.map((item, index) => (
              <div key={item.label} className="flex items-center">
                <div
                  className="w-3 h-3 rounded-full mr-2"
                  style={{ backgroundColor: item.color || colors[index % colors.length] }}
                ></div>
                <div className="text-sm">
                  <span className="text-gray-900 font-medium">{item.label}</span>
                  <span className="text-gray-600 ml-1">({item.value.toLocaleString()})</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (type === 'line') {
    const width = 300;
    const chartHeight = height - 60;
    const padding = 40;

    // 生成SVG路径
    const points = data.map((item, index) => {
      const x = padding + (index * (width - 2 * padding)) / (data.length - 1);
      const y = chartHeight + padding - ((item.value / maxValue) * chartHeight);
      return `${x},${y}`;
    }).join(' ');

    return (
      <div className="bg-white rounded-lg shadow p-4">
        {title && <h3 className="text-lg font-medium text-gray-900 mb-4">{title}</h3>}
        <div style={{ width, height }}>
          <svg width={width} height={height}>
            {/* 网格线 */}
            {[0, 0.25, 0.5, 0.75, 1].map(ratio => (
              <line
                key={ratio}
                x1={padding}
                y1={chartHeight * (1 - ratio) + padding}
                x2={width - padding}
                y2={chartHeight * (1 - ratio) + padding}
                stroke="#E5E7EB"
                strokeWidth="1"
              />
            ))}
            
            {/* 数据线 */}
            <polyline
              points={points}
              fill="none"
              stroke="#3B82F6"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            
            {/* 数据点 */}
            {data.map((item, index) => {
              const x = padding + (index * (width - 2 * padding)) / (data.length - 1);
              const y = chartHeight + padding - ((item.value / maxValue) * chartHeight);
              
              return (
                <circle
                  key={index}
                  cx={x}
                  cy={y}
                  r="4"
                  fill="#3B82F6"
                  stroke="white"
                  strokeWidth="2"
                />
              );
            })}
            
            {/* X轴标签 */}
            {data.map((item, index) => {
              const x = padding + (index * (width - 2 * padding)) / (data.length - 1);
              
              return (
                <text
                  key={index}
                  x={x}
                  y={height - 10}
                  textAnchor="middle"
                  className="fill-gray-600 text-xs"
                >
                  {item.label}
                </text>
              );
            })}
            
            {/* Y轴标签 */}
            {[0, 0.25, 0.5, 0.75, 1].map((ratio, index) => (
              <text
                key={index}
                x={padding - 10}
                y={chartHeight * (1 - ratio) + padding + 4}
                textAnchor="end"
                className="fill-gray-600 text-xs"
              >
                {Math.round(maxValue * ratio).toLocaleString()}
              </text>
            ))}
          </svg>
        </div>
      </div>
    );
  }

  return null;
};

export default SimpleChart;