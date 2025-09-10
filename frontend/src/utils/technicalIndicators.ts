// 技术指标计算工具函数
import type { KlineData } from '../types/market'

// 简单移动平均线
export const calculateSMA = (data: number[], period: number): (number | null)[] => {
  const sma: (number | null)[] = []
  
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      sma.push(null)
    } else {
      const sum = data.slice(i - period + 1, i + 1).reduce((acc, val) => acc + val, 0)
      sma.push(sum / period)
    }
  }
  
  return sma
}

// 指数移动平均线
export const calculateEMA = (data: number[], period: number): (number | null)[] => {
  const ema: (number | null)[] = []
  const multiplier = 2 / (period + 1)
  
  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      ema.push(data[i])
    } else if (i < period - 1) {
      ema.push(null)
    } else {
      const currentEMA = (data[i] * multiplier) + ((ema[i - 1] ?? data[i]) * (1 - multiplier))
      ema.push(currentEMA)
    }
  }
  
  return ema
}

// MACD指标计算
export interface MACDResult {
  macd: (number | null)[]
  signal: (number | null)[]
  histogram: (number | null)[]
}

export const calculateMACD = (
  data: KlineData[], 
  fastPeriod: number = 12, 
  slowPeriod: number = 26, 
  signalPeriod: number = 9
): MACDResult => {
  const closePrices = data.map(item => item.close)
  
  // 计算快线EMA和慢线EMA
  const fastEMA = calculateEMA(closePrices, fastPeriod)
  const slowEMA = calculateEMA(closePrices, slowPeriod)
  
  // 计算MACD线
  const macd = fastEMA.map((fast, i) => {
    const slow = slowEMA[i]
    if (fast === null || slow === null) return null
    return fast - slow
  })
  
  // 计算信号线
  const macdValues = macd.filter((val): val is number => val !== null)
  const signalEMA = calculateEMA(macdValues, signalPeriod)
  
  // 补充null值以匹配原数组长度
  const signal: (number | null)[] = []
  let signalIndex = 0
  
  for (let i = 0; i < macd.length; i++) {
    if (macd[i] === null) {
      signal.push(null)
    } else {
      signal.push(signalEMA[signalIndex] ?? null)
      signalIndex++
    }
  }
  
  // 计算直方图
  const histogram = macd.map((macdVal, i) => {
    const signalVal = signal[i]
    if (macdVal === null || signalVal === null) return null
    return macdVal - signalVal
  })
  
  return { macd, signal, histogram }
}

// RSI指标计算
export const calculateRSI = (data: KlineData[], period: number = 14): (number | null)[] => {
  const closePrices = data.map(item => item.close)
  const rsi: (number | null)[] = []
  
  if (closePrices.length < period + 1) {
    return new Array(closePrices.length).fill(null)
  }
  
  // 计算价格变化
  const priceChanges = []
  for (let i = 1; i < closePrices.length; i++) {
    priceChanges.push(closePrices[i] - closePrices[i - 1])
  }
  
  rsi.push(null) // 第一个值无法计算RSI
  
  for (let i = 0; i < priceChanges.length; i++) {
    if (i < period - 1) {
      rsi.push(null)
    } else {
      const recentChanges = priceChanges.slice(i - period + 1, i + 1)
      
      const gains = recentChanges.filter(change => change > 0)
      const losses = recentChanges.filter(change => change < 0).map(loss => Math.abs(loss))
      
      const avgGain = gains.length > 0 ? gains.reduce((sum, gain) => sum + gain, 0) / period : 0
      const avgLoss = losses.length > 0 ? losses.reduce((sum, loss) => sum + loss, 0) / period : 0
      
      if (avgLoss === 0) {
        rsi.push(100)
      } else {
        const rs = avgGain / avgLoss
        const rsiValue = 100 - (100 / (1 + rs))
        rsi.push(rsiValue)
      }
    }
  }
  
  return rsi
}

// 布林带指标计算
export interface BOLLResult {
  upper: (number | null)[]
  middle: (number | null)[]
  lower: (number | null)[]
}

export const calculateBOLL = (
  data: KlineData[], 
  period: number = 20, 
  multiplier: number = 2
): BOLLResult => {
  const closePrices = data.map(item => item.close)
  const middle = calculateSMA(closePrices, period)
  const upper: (number | null)[] = []
  const lower: (number | null)[] = []
  
  for (let i = 0; i < closePrices.length; i++) {
    if (i < period - 1 || middle[i] === null) {
      upper.push(null)
      lower.push(null)
    } else {
      // 计算标准差
      const recentPrices = closePrices.slice(i - period + 1, i + 1)
      const avg = middle[i]!
      const squaredDiffs = recentPrices.map(price => Math.pow(price - avg, 2))
      const variance = squaredDiffs.reduce((sum, diff) => sum + diff, 0) / period
      const stdDev = Math.sqrt(variance)
      
      upper.push(avg + (multiplier * stdDev))
      lower.push(avg - (multiplier * stdDev))
    }
  }
  
  return { upper, middle, lower }
}

// 威廉指标计算
export const calculateWR = (data: KlineData[], period: number = 14): (number | null)[] => {
  const wr: (number | null)[] = []
  
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      wr.push(null)
    } else {
      const recentData = data.slice(i - period + 1, i + 1)
      const highestHigh = Math.max(...recentData.map(d => d.high))
      const lowestLow = Math.min(...recentData.map(d => d.low))
      const currentClose = data[i].close
      
      if (highestHigh === lowestLow) {
        wr.push(-50) // 避免除零
      } else {
        const wrValue = ((highestHigh - currentClose) / (highestHigh - lowestLow)) * -100
        wr.push(wrValue)
      }
    }
  }
  
  return wr
}

// KDJ指标计算
export interface KDJResult {
  k: (number | null)[]
  d: (number | null)[]
  j: (number | null)[]
}

export const calculateKDJ = (data: KlineData[], period: number = 9): KDJResult => {
  const k: (number | null)[] = []
  const d: (number | null)[] = []
  const j: (number | null)[] = []
  
  let prevK = 50 // K值初始值
  let prevD = 50 // D值初始值
  
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      k.push(null)
      d.push(null)
      j.push(null)
    } else {
      const recentData = data.slice(i - period + 1, i + 1)
      const highestHigh = Math.max(...recentData.map(d => d.high))
      const lowestLow = Math.min(...recentData.map(d => d.low))
      const currentClose = data[i].close
      
      // 计算RSV
      let rsv = 50
      if (highestHigh !== lowestLow) {
        rsv = ((currentClose - lowestLow) / (highestHigh - lowestLow)) * 100
      }
      
      // 计算K值
      const currentK = (2 * prevK + rsv) / 3
      
      // 计算D值
      const currentD = (2 * prevD + currentK) / 3
      
      // 计算J值
      const currentJ = 3 * currentK - 2 * currentD
      
      k.push(currentK)
      d.push(currentD)
      j.push(currentJ)
      
      prevK = currentK
      prevD = currentD
    }
  }
  
  return { k, d, j }
}