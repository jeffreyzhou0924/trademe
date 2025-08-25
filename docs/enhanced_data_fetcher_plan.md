# 基于现有工具的USDT历史数据拉取优化方案

## 🎯 核心目标

基于现有的 `/root/Tradebot/tools` 系统，设计一套完整的USDT结算历史数据拉取方案：

### 现货市场数据
- **K线数据**: 日级OHLCV，用于现货策略回测
- **交易数据**: 日级聚合tick数据，用于现货策略高精度回测

### 合约市场数据  
- **K线数据**: 日级OHLCV + 资金费率 + 持仓量，用于合约策略回测
- **交易数据**: 日级聚合tick数据，用于合约策略高精度回测

## 🏗️ 系统架构升级

### 1. 现有工具分析

#### 优势
- ✅ 已有OKX交易数据抓取脚本 (spider.trades.okex*.sh)
- ✅ 已有Binance K线数据抓取脚本 (spider.klines.binance.sh)
- ✅ 支持多交易对并发抓取
- ✅ 内置SHA256校验机制
- ✅ PostgreSQL数据存储

#### 不足
- ❌ 缺少OKX K线数据抓取
- ❌ 缺少现货交易数据抓取
- ❌ 缺少合约市场数据支持
- ❌ 缺少日级数据聚合逻辑
- ❌ 未集成到Trademe系统

### 2. 架构升级设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data Sources   │    │  Enhanced Tools │    │  Trademe System │
│                 │    │                 │    │                 │
│ • OKX CDN       │◄───┤• okx_klines.sh  │◄───┤• Python Service│
│ • Binance CDN   │    │• okx_trades.sh  │    │• SQLite Storage │  
│ • API Fallback  │    │• data_aggregator│    │• Redis Cache    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 具体实现方案

### 阶段1: 扩展现有脚本

#### 1.1 创建OKX K线数据抓取脚本
```bash
# 文件: spider.klines.okx.sh
# 功能: 抓取OKX现货和合约的日K线数据
# URL模式: https://static.okx.com/cdn/okex/traderecords/klines/daily/$day/${asset}-USDT-1d-${formatted_day}.zip
```

#### 1.2 扩展交易数据脚本
```bash  
# 改进: spider.trades.okx.sh
# 新增: 现货交易数据支持
# 新增: 合约交易数据支持
# 新增: 数据质量检查
```

#### 1.3 创建数据聚合脚本
```bash
# 文件: data_aggregator.sh
# 功能: 将tick数据聚合为日级统计数据
# 输出: 成交量分布、价格波动率、买卖比例等
```

### 阶段2: 数据存储优化

#### 2.1 SQLite集成
```sql
-- 现货日K线表
CREATE TABLE spot_daily_klines (
    symbol VARCHAR(20),
    trade_date DATE,
    open_price DECIMAL(18,8),
    high_price DECIMAL(18,8), 
    low_price DECIMAL(18,8),
    close_price DECIMAL(18,8),
    volume DECIMAL(18,8),
    quote_volume DECIMAL(18,8),
    PRIMARY KEY(symbol, trade_date)
);

-- 现货日交易聚合表
CREATE TABLE spot_daily_trades (
    symbol VARCHAR(20),
    trade_date DATE,
    total_trades INTEGER,
    avg_trade_size DECIMAL(18,8),
    price_volatility DECIMAL(8,6),
    tick_data BLOB,  -- 压缩的tick数据
    PRIMARY KEY(symbol, trade_date)
);

-- 合约日K线表  
CREATE TABLE futures_daily_klines (
    symbol VARCHAR(30),
    trade_date DATE,
    open_price DECIMAL(18,8),
    high_price DECIMAL(18,8),
    low_price DECIMAL(18,8), 
    close_price DECIMAL(18,8),
    volume DECIMAL(18,8),
    open_interest DECIMAL(18,8),
    funding_rate DECIMAL(12,8),
    PRIMARY KEY(symbol, trade_date)
);

-- 合约日交易聚合表
CREATE TABLE futures_daily_trades (
    symbol VARCHAR(30),
    trade_date DATE,
    total_trades INTEGER,
    liquidation_trades INTEGER,
    avg_trade_size DECIMAL(18,8),
    price_volatility DECIMAL(8,6),
    tick_data BLOB,
    PRIMARY KEY(symbol, trade_date)
);
```

#### 2.2 数据转换层
```python
# 文件: data_converter.py
# 功能: PostgreSQL → SQLite 数据迁移
# 功能: CSV → SQLite 数据导入
# 功能: 数据格式标准化
```

### 阶段3: 智能调度系统

#### 3.1 增强版调度器
```bash
# 文件: enhanced_crontask.sh
# 功能: 智能数据拉取调度
# 策略: 
# - 高优先级交易对优先拉取
# - 失败重试机制
# - 数据完整性检查
# - 增量更新优化
```

#### 3.2 数据质量保障
```python
# 文件: data_quality_checker.py
# 功能:
# - 数据完整性检查
# - 异常值检测
# - 缺失数据自动补充
# - 数据一致性验证
```

## 📋 实施时间线

### Week 1: 脚本扩展
- [ ] 创建 `spider.klines.okx.sh`
- [ ] 改进 `spider.trades.okx.sh`
- [ ] 测试OKX数据下载URL

### Week 2: 数据处理
- [ ] 创建 `data_aggregator.sh`
- [ ] 实现 `data_converter.py`
- [ ] SQLite表结构创建

### Week 3: 系统集成
- [ ] 集成到Trademe交易服务
- [ ] 创建数据API接口
- [ ] 实施数据质量检查

### Week 4: 测试优化
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 生产环境部署

## 🎯 具体交易对配置

### 现货优先级列表
```bash
# 高优先级 (每日拉取)
SPOT_HIGH_PRIORITY=(BTC-USDT ETH-USDT BNB-USDT ADA-USDT XRP-USDT)

# 中优先级 (每周拉取)  
SPOT_MID_PRIORITY=(SOL-USDT DOGE-USDT MATIC-USDT LTC-USDT AVAX-USDT)

# 低优先级 (按需拉取)
SPOT_LOW_PRIORITY=(LINK-USDT DOT-USDT UNI-USDT ATOM-USDT FTM-USDT)
```

### 合约优先级列表
```bash
# 永续合约 (高优先级)
FUTURES_HIGH_PRIORITY=(BTC-USDT-SWAP ETH-USDT-SWAP BNB-USDT-SWAP)

# 永续合约 (中优先级)
FUTURES_MID_PRIORITY=(ADA-USDT-SWAP XRP-USDT-SWAP SOL-USDT-SWAP)
```

## 🔍 数据验证策略

### 1. 实时验证
- K线数据OHLC关系检查
- 交易量合理性验证
- 时间序列连续性检查

### 2. 跨源验证
- OKX vs Binance价格对比
- 成交量数据交叉验证
- 异常值自动标记

### 3. 历史一致性
- 数据回填完整性
- 历史数据修正机制
- 版本控制和变更记录

## 🚀 性能优化

### 1. 并发优化
```bash
# 并发下载配置
MAX_CONCURRENT_DOWNLOADS=5
DOWNLOAD_RETRY_COUNT=3
DOWNLOAD_TIMEOUT=300
```

### 2. 存储优化  
```python
# 数据压缩
COMPRESSION_LEVEL = 6  # gzip压缩级别
TICK_DATA_BATCH_SIZE = 10000  # 批量处理大小
```

### 3. 缓存策略
```python
# Redis缓存配置
DAILY_DATA_TTL = 86400  # 24小时
AGGREGATED_DATA_TTL = 3600  # 1小时
```

## 📊 预期收益

### 数据覆盖
- **现货K线**: 100+ USDT交易对，365天历史
- **现货交易**: 50+ 核心交易对，100天高精度数据
- **合约K线**: 50+ 永续合约，365天历史  
- **合约交易**: 20+ 核心合约，100天高精度数据

### 性能指标
- **数据新鲜度**: < 6小时延迟
- **数据完整性**: > 99.5%
- **查询性能**: < 100ms (日级数据)
- **存储效率**: 70% 压缩率

这个方案充分利用了现有的工具基础，同时针对Trademe系统的需求进行了优化。你觉得这个设计如何？我们可以开始实施吗？