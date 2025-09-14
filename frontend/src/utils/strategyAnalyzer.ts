/**
 * 智能策略代码结构分析器
 * 基于代码AST结构分析，替代硬编码关键词匹配
 */

export interface StrategyAnalysisResult {
  isStrategy: boolean;
  confidence: number;
  strategyType: string;
  indicators: string[];
  className?: string;
  methods: string[];
  errors: string[];
}

export interface AnalysisCache {
  [codeHash: string]: StrategyAnalysisResult;
}

class StrategyCodeAnalyzer {
  private cache: AnalysisCache = {};
  
  // 必需的策略基类和方法
  private readonly REQUIRED_BASE_CLASSES = [
    'BaseStrategy',
    'EnhancedBaseStrategy', 
    'UserStrategy',
    'TradingStrategy'
  ];
  
  private readonly REQUIRED_METHODS = [
    'on_data_update',
    'get_data_requirements'
  ];
  
  // 策略特征标识符
  private readonly STRATEGY_PATTERNS = {
    imports: [
      /from.*BaseStrategy.*import/i,
      /from.*EnhancedBaseStrategy.*import/i,
      /import.*TradingSignal/i,
      /import.*SignalType/i,
      /import.*DataRequest/i,
      /import.*DataType/i
    ],
    
    classes: [
      /class\s+(\w*Strategy)\s*\(/i,
      /class\s+(\w+)\s*\(\s*(BaseStrategy|EnhancedBaseStrategy|UserStrategy)/i
    ],
    
    methods: [
      /def\s+(on_data_update)\s*\(/i,
      /def\s+(get_data_requirements)\s*\(/i,
      /def\s+(calculate_\w+)\s*\(/i,
      /def\s+(execute_trade)\s*\(/i
    ],
    
    signals: [
      /TradingSignal\s*\(/i,
      /SignalType\./i,
      /return\s+TradingSignal/i,
      /signal\s*=\s*TradingSignal/i
    ],
    
    indicators: {
      MACD: [/macd/i, /ema12|ema26/i, /signal.*line/i, /histogram/i],
      MA: [/sma|simple.*moving/i, /ema|exponential.*moving/i, /ma_short|ma_long/i, /golden_cross|death_cross/i],
      RSI: [/rsi/i, /relative.*strength/i, /overbought|oversold/i],
      BOLL: [/bollinger/i, /upper.*band|lower.*band/i, /std.*dev/i],
      KDJ: [/kdj/i, /%k.*%d.*%j/i, /stochastic/i],
      CCI: [/cci/i, /commodity.*channel/i]
    },
    
    tradingFeatures: [
      /position\s*=|position\./i,
      /trades\s*=\s*\[\]/i,
      /fee_rate\s*=/i,
      /stop_loss|take_profit/i,
      /buy.*signal|sell.*signal/i
    ]
  };
  
  /**
   * 分析消息中的代码块是否为有效策略
   */
  analyzeMessage(content: string): StrategyAnalysisResult {
    const codeBlock = this.extractCodeBlock(content);
    if (!codeBlock) {
      return {
        isStrategy: false,
        confidence: 0,
        strategyType: 'none',
        indicators: [],
        methods: [],
        errors: ['No Python code block found']
      };
    }
    
    return this.analyzeCode(codeBlock);
  }
  
  /**
   * 核心代码结构分析函数
   */
  analyzeCode(code: string): StrategyAnalysisResult {
    // 使用代码哈希进行缓存
    const codeHash = this.hashCode(code);
    if (this.cache[codeHash]) {
      return this.cache[codeHash];
    }
    
    const result: StrategyAnalysisResult = {
      isStrategy: false,
      confidence: 0,
      strategyType: 'unknown',
      indicators: [],
      methods: [],
      errors: []
    };
    
    try {
      // 1. 基础结构分析
      const structureScore = this.analyzeStructure(code, result);
      
      // 2. 技术指标识别
      const indicatorScore = this.analyzeIndicators(code, result);
      
      // 3. 交易功能分析
      const tradingScore = this.analyzeTradingFeatures(code, result);
      
      // 4. 语法完整性检查
      const syntaxScore = this.analyzeSyntax(code, result);
      
      // 计算综合置信度
      result.confidence = this.calculateConfidence(
        structureScore,
        indicatorScore, 
        tradingScore,
        syntaxScore
      );
      
      // 判断是否为有效策略（置信度 >= 0.6）
      result.isStrategy = result.confidence >= 0.6;
      
      // 确定策略类型
      result.strategyType = this.determineStrategyType(result.indicators);
      
    } catch (error) {
      result.errors.push(`Analysis error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
    
    // 缓存结果
    this.cache[codeHash] = result;
    return result;
  }
  
  /**
   * 分析代码基础结构
   */
  private analyzeStructure(code: string, result: StrategyAnalysisResult): number {
    let score = 0;
    
    // 检查导入语句 (权重: 0.2)
    const hasImports = this.STRATEGY_PATTERNS.imports.some(pattern => pattern.test(code));
    if (hasImports) score += 0.2;
    
    // 检查类定义 (权重: 0.4)
    for (const pattern of this.STRATEGY_PATTERNS.classes) {
      const match = code.match(pattern);
      if (match) {
        result.className = match[1];
        score += 0.4;
        break;
      }
    }
    
    // 检查必需方法 (权重: 0.3)
    for (const pattern of this.STRATEGY_PATTERNS.methods) {
      const match = code.match(pattern);
      if (match) {
        result.methods.push(match[1]);
        score += 0.1;
      }
    }
    
    // 检查交易信号 (权重: 0.1)
    const hasSignals = this.STRATEGY_PATTERNS.signals.some(pattern => pattern.test(code));
    if (hasSignals) score += 0.1;
    
    return Math.min(score, 1.0);
  }
  
  /**
   * 识别技术指标
   */
  private analyzeIndicators(code: string, result: StrategyAnalysisResult): number {
    let score = 0;
    
    for (const [indicator, patterns] of Object.entries(this.STRATEGY_PATTERNS.indicators)) {
      const hasIndicator = patterns.some(pattern => pattern.test(code));
      if (hasIndicator) {
        result.indicators.push(indicator);
        score += 0.2; // 每个指标加0.2分
      }
    }
    
    return Math.min(score, 1.0);
  }
  
  /**
   * 分析交易功能特征
   */
  private analyzeTradingFeatures(code: string, result: StrategyAnalysisResult): number {
    let score = 0;
    
    for (const pattern of this.STRATEGY_PATTERNS.tradingFeatures) {
      if (pattern.test(code)) {
        score += 0.15; // 每个交易特征加0.15分
      }
    }
    
    return Math.min(score, 1.0);
  }
  
  /**
   * 语法完整性分析
   */
  private analyzeSyntax(code: string, result: StrategyAnalysisResult): number {
    let score = 0;
    
    // 检查基本Python语法特征
    const syntaxChecks = [
      /class\s+\w+.*:/i,  // 类定义
      /def\s+\w+.*:/i,    // 方法定义
      /return\s+/i,       // 返回语句
      /if\s+.*:/i         // 条件语句
    ];
    
    for (const check of syntaxChecks) {
      if (check.test(code)) {
        score += 0.2;
      }
    }
    
    // 检查代码长度合理性
    if (code.length > 500 && code.length < 10000) {
      score += 0.2;
    }
    
    return Math.min(score, 1.0);
  }
  
  /**
   * 计算综合置信度
   */
  private calculateConfidence(
    structure: number,
    indicator: number, 
    trading: number,
    syntax: number
  ): number {
    // 加权平均：结构40%，指标25%，交易25%，语法10%
    return structure * 0.4 + indicator * 0.25 + trading * 0.25 + syntax * 0.1;
  }
  
  /**
   * 确定策略类型
   */
  private determineStrategyType(indicators: string[]): string {
    if (indicators.length === 0) return 'generic';
    if (indicators.length === 1) return indicators[0].toLowerCase();
    if (indicators.includes('MACD') && indicators.includes('RSI')) return 'macd-rsi';
    if (indicators.includes('MA') && indicators.includes('KDJ')) return 'ma-kdj';
    if (indicators.includes('BOLL') && indicators.includes('CCI')) return 'boll-cci';
    return 'multi-indicator';
  }
  
  /**
   * 提取Python代码块
   */
  private extractCodeBlock(content: string): string | null {
    // 支持多种代码块格式
    const patterns = [
      /```python\s*([\s\S]*?)\s*```/i,
      /```\s*(class.*?[\s\S]*?)\s*```/i,
      /```\s*(def.*?[\s\S]*?)\s*```/i,
      /```\s*([\s\S]*?)\s*```/i
    ];
    
    for (const pattern of patterns) {
      const match = content.match(pattern);
      if (match && match[1].trim().length > 100) { // 最小代码长度检查
        return match[1].trim();
      }
    }
    
    return null;
  }
  
  /**
   * 简单哈希函数用于缓存
   */
  private hashCode(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 转换为32位整数
    }
    return hash.toString();
  }
  
  /**
   * 清理缓存
   */
  clearCache(): void {
    this.cache = {};
  }
  
  /**
   * 获取缓存统计
   */
  getCacheStats(): { size: number; hitRate: number } {
    return {
      size: Object.keys(this.cache).length,
      hitRate: 0 // 可以添加命中率统计
    };
  }
}

// 单例实例
export const strategyAnalyzer = new StrategyCodeAnalyzer();

// 便捷函数
export const analyzeStrategyCode = (code: string): StrategyAnalysisResult => {
  return strategyAnalyzer.analyzeCode(code);
};

export const analyzeStrategyMessage = (content: string): StrategyAnalysisResult => {
  return strategyAnalyzer.analyzeMessage(content);
};