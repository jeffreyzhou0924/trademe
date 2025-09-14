/**
 * 策略代码分析相关类型定义
 */

// 策略分析结果接口
export interface StrategyAnalysisResult {
  isStrategy: boolean;
  confidence: number;
  strategyType: string;
  indicators: string[];
  className?: string;
  methods: string[];
  errors: string[];
}

// 分析缓存接口
export interface AnalysisCache {
  [codeHash: string]: StrategyAnalysisResult;
}

// 策略检测配置
export interface StrategyDetectionConfig {
  minConfidence: number;
  enableCache: boolean;
  maxCacheSize: number;
  analysisTimeout: number;
}

// 策略消息状态
export interface StrategyMessageState {
  hasStrategyCode: boolean;
  hasSuccessMessage: boolean;
  analysisResult?: StrategyAnalysisResult;
  showBacktestButton: boolean;
  extractedCode?: string;
}

// 智能检测结果
export interface SmartDetectionResult {
  messageState: StrategyMessageState;
  confidence: number;
  debugInfo: {
    codeExtracted: boolean;
    analysisTime: number;
    cacheHit: boolean;
    errors: string[];
  };
}

// 策略类型枚举
export enum StrategyType {
  MACD = 'macd',
  MA = 'ma', 
  RSI = 'rsi',
  BOLL = 'boll',
  KDJ = 'kdj',
  CCI = 'cci',
  MACD_RSI = 'macd-rsi',
  MA_KDJ = 'ma-kdj',
  BOLL_CCI = 'boll-cci',
  MULTI_INDICATOR = 'multi-indicator',
  GENERIC = 'generic',
  UNKNOWN = 'unknown'
}

// 技术指标枚举
export enum TechnicalIndicator {
  MACD = 'MACD',
  MA = 'MA',
  EMA = 'EMA',
  SMA = 'SMA', 
  RSI = 'RSI',
  BOLL = 'BOLL',
  KDJ = 'KDJ',
  CCI = 'CCI',
  STOCH = 'STOCH'
}