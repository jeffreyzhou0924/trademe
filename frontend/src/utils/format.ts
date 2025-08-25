/**
 * 格式化数字为货币格式
 * @param value 数字值
 * @param currency 货币符号，默认为空
 * @param decimals 小数位数，默认为2
 * @returns 格式化后的货币字符串
 */
export const formatCurrency = (
  value: number,
  currency = '',
  decimals = 2
): string => {
  const formatted = new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(value)
  
  return currency ? `${currency}${formatted}` : formatted
}

/**
 * 格式化数字为百分比
 * @param value 数字值（0-1之间或已经是百分比数值）
 * @param decimals 小数位数，默认为1
 * @param isAlreadyPercent 是否已经是百分比数值（如传入12.5表示12.5%）
 * @returns 格式化后的百分比字符串
 */
export const formatPercent = (
  value: number,
  decimals = 1,
  isAlreadyPercent = false
): string => {
  const percent = isAlreadyPercent ? value : value * 100
  const formatted = percent.toFixed(decimals)
  return `${formatted}%`
}

/**
 * 格式化大数字，使用K、M、B等单位
 * @param value 数字值
 * @param decimals 小数位数，默认为1
 * @returns 格式化后的字符串
 */
export const formatLargeNumber = (
  value: number,
  decimals = 1
): string => {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  
  if (abs >= 1e9) {
    return `${sign}${(abs / 1e9).toFixed(decimals)}B`
  }
  if (abs >= 1e6) {
    return `${sign}${(abs / 1e6).toFixed(decimals)}M`
  }
  if (abs >= 1e3) {
    return `${sign}${(abs / 1e3).toFixed(decimals)}K`
  }
  
  return value.toString()
}

/**
 * 格式化时间为相对时间（如：2分钟前、1小时前）
 * @param date 日期对象或时间戳
 * @returns 格式化后的相对时间字符串
 */
export const formatRelativeTime = (date: Date | number): string => {
  const now = new Date()
  const past = new Date(date)
  const diffInSeconds = Math.floor((now.getTime() - past.getTime()) / 1000)
  
  if (diffInSeconds < 60) {
    return '刚刚'
  }
  
  const diffInMinutes = Math.floor(diffInSeconds / 60)
  if (diffInMinutes < 60) {
    return `${diffInMinutes}分钟前`
  }
  
  const diffInHours = Math.floor(diffInMinutes / 60)
  if (diffInHours < 24) {
    return `${diffInHours}小时前`
  }
  
  const diffInDays = Math.floor(diffInHours / 24)
  if (diffInDays < 7) {
    return `${diffInDays}天前`
  }
  
  // 超过7天显示具体日期
  return past.toLocaleDateString('zh-CN')
}

/**
 * 格式化日期时间
 * @param date 日期对象或时间戳
 * @param format 格式类型
 * @returns 格式化后的日期字符串
 */
export const formatDateTime = (
  date: Date | number | string,
  format: 'date' | 'time' | 'datetime' | 'short' = 'datetime'
): string => {
  const d = new Date(date)
  
  if (isNaN(d.getTime())) {
    return '无效日期'
  }
  
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')
  
  switch (format) {
    case 'date':
      return `${year}-${month}-${day}`
    case 'time':
      return `${hours}:${minutes}:${seconds}`
    case 'short':
      return `${month}-${day} ${hours}:${minutes}`
    case 'datetime':
    default:
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  }
}

/**
 * 格式化文件大小
 * @param bytes 字节数
 * @param decimals 小数位数，默认为1
 * @returns 格式化后的文件大小字符串
 */
export const formatFileSize = (bytes: number, decimals = 1): string => {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
}

/**
 * 截断字符串并添加省略号
 * @param str 原始字符串
 * @param maxLength 最大长度
 * @param suffix 后缀，默认为'...'
 * @returns 截断后的字符串
 */
export const truncateString = (
  str: string,
  maxLength: number,
  suffix = '...'
): string => {
  if (str.length <= maxLength) {
    return str
  }
  
  return str.slice(0, maxLength - suffix.length) + suffix
}

/**
 * 格式化交易对显示
 * @param pair 交易对字符串，如'BTC/USDT'
 * @returns 格式化后的对象，包含base和quote
 */
export const formatTradingPair = (pair: string) => {
  const [base, quote] = pair.split('/')
  return {
    base: base || '',
    quote: quote || '',
    display: pair,
    formatted: `${base}/${quote}`
  }
}

/**
 * 格式化价格变化，带正负号和颜色类
 * @param value 价格变化值
 * @param isPercent 是否为百分比
 * @returns 包含格式化字符串和样式类的对象
 */
export const formatPriceChange = (value: number, isPercent = false) => {
  const isPositive = value >= 0
  const sign = isPositive ? '+' : ''
  const colorClass = isPositive ? 'text-green-600' : 'text-red-600'
  const bgColorClass = isPositive ? 'bg-green-100' : 'bg-red-100'
  
  const formatted = isPercent
    ? `${sign}${value.toFixed(2)}%`
    : `${sign}${formatCurrency(value)}`
  
  return {
    formatted,
    colorClass,
    bgColorClass,
    isPositive
  }
}