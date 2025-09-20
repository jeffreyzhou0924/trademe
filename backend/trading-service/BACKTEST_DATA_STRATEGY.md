# 📊 Trademe 分层回测数据策略设计方案

## 🎯 产品定位与用户分层

### 用户群体分析
```yaml
初级用户 (Basic):
  - 特征: 量化交易新手，学习阶段
  - 需求: 简单策略验证，成本敏感
  - 占比: 60-70%
  - 付费意愿: $10-30/月

中级用户 (Pro):
  - 特征: 有一定经验，追求更好精度
  - 需求: 中等频率策略，平衡精度与成本
  - 占比: 25-30%
  - 付费意愿: $50-100/月

高级用户 (Elite):
  - 特征: 专业交易员，机构用户
  - 需求: 高频策略，极致精度
  - 占比: 5-10%
  - 付费意愿: $200-500/月
```

## 🏗️ 三层回测架构设计

### 1️⃣ 初级用户 - K线级回测 (Basic Tier)

#### 数据特征
- **精度**: 分钟级K线数据 (OHLCV)
- **时间框架**: 1m, 5m, 15m, 1h, 4h, 1d
- **历史深度**: 6个月免费，2年付费
- **更新频率**: 实时更新 (1分钟延迟)

#### 技术实现
```python
class BasicBacktestEngine:
    """基础K线回测引擎"""
    
    def __init__(self):
        self.data_type = "kline"
        self.supported_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        self.max_history_days = 180  # 6个月
        
    async def run_backtest(self, strategy, symbol, timeframe, start_date, end_date):
        """运行K线级回测"""
        # 获取K线数据
        kline_data = await self._get_kline_data(symbol, timeframe, start_date, end_date)
        
        # 执行回测逻辑
        results = await self._execute_basic_backtest(strategy, kline_data)
        
        return {
            "data_type": "kline",
            "precision": timeframe,
            "trade_count": len(results.trades),
            "performance": results.metrics
        }
```

#### 功能限制
- 最大并发回测: 3个
- 策略复杂度: 基础技术指标
- 报告格式: 标准JSON
- API调用限制: 1000次/天

---

### 2️⃣ 中级用户 - 混合回测模式 (Pro Tier)

#### 数据特征
- **基础数据**: 秒级聚合数据 (1s, 5s, 15s, 30s)
- **关键时刻**: Tick级精确模拟
- **智能切换**: 根据策略需求动态选择精度
- **历史深度**: 2年完整数据

#### 核心创新 - 混合回测算法
```python
class HybridBacktestEngine:
    """混合精度回测引擎"""
    
    def __init__(self):
        self.data_type = "hybrid"
        self.precision_modes = {
            "low_volatility": "1m_kline",      # 低波动期用K线
            "medium_volatility": "1s_agg",     # 中等波动用秒级聚合
            "high_volatility": "tick_sim",     # 高波动期用tick模拟
            "trade_execution": "tick_sim"      # 交易执行时用tick模拟
        }
    
    async def run_hybrid_backtest(self, strategy, symbol, start_date, end_date):
        """运行混合精度回测"""
        
        # 1. 市场状态分析
        market_states = await self._analyze_market_volatility(symbol, start_date, end_date)
        
        # 2. 动态精度切换
        for period in market_states:
            if period.volatility < 0.01:
                # 低波动期 - 使用K线数据
                data = await self._get_kline_data(symbol, "1m", period.start, period.end)
                results = await self._execute_kline_backtest(strategy, data)
                
            elif period.volatility < 0.05:
                # 中等波动期 - 使用秒级聚合数据
                data = await self._get_second_data(symbol, "1s", period.start, period.end)
                results = await self._execute_second_backtest(strategy, data)
                
            else:
                # 高波动期 - 使用tick级模拟
                tick_data = await self._simulate_tick_data(symbol, period.start, period.end)
                results = await self._execute_tick_backtest(strategy, tick_data)
        
        return self._aggregate_hybrid_results(results)
    
    async def _simulate_tick_data(self, symbol, start_time, end_time):
        """基于秒级数据模拟tick数据"""
        second_data = await self._get_second_data(symbol, "1s", start_time, end_time)
        
        simulated_ticks = []
        for candle in second_data:
            # 使用布朗运动模拟tick轨迹
            ticks = self._generate_tick_path(
                open_price=candle['open'],
                close_price=candle['close'],
                high_price=candle['high'],
                low_price=candle['low'],
                volume=candle['volume'],
                duration_ms=1000  # 1秒
            )
            simulated_ticks.extend(ticks)
        
        return simulated_ticks
    
    def _generate_tick_path(self, open_price, close_price, high_price, low_price, volume, duration_ms):
        """生成符合OHLC约束的tick路径"""
        import numpy as np
        
        tick_count = min(int(volume / 10), 100)  # 根据成交量确定tick数量
        timestamps = np.linspace(0, duration_ms, tick_count)
        
        # 使用几何布朗运动，确保路径经过high和low
        prices = self._constrained_brownian_path(
            start=open_price,
            end=close_price,
            high=high_price,
            low=low_price,
            steps=tick_count
        )
        
        ticks = []
        for i, (timestamp, price) in enumerate(zip(timestamps, prices)):
            ticks.append({
                'timestamp': timestamp,
                'price': price,
                'volume': volume / tick_count,
                'side': 'buy' if i % 2 == 0 else 'sell'
            })
        
        return ticks
```

#### 智能切换策略
```python
class MarketStateAnalyzer:
    """市场状态分析器"""
    
    def __init__(self):
        self.volatility_thresholds = {
            "low": 0.01,     # 1%以下日波动率
            "medium": 0.05,  # 1-5%日波动率
            "high": 0.05     # 5%以上日波动率
        }
    
    async def analyze_market_volatility(self, symbol, start_date, end_date):
        """分析市场波动状态"""
        # 获取分钟级数据计算波动率
        minute_data = await self._get_minute_data(symbol, start_date, end_date)
        
        periods = []
        for day_data in self._group_by_day(minute_data):
            volatility = self._calculate_intraday_volatility(day_data)
            
            if volatility < self.volatility_thresholds["low"]:
                precision_mode = "kline"
            elif volatility < self.volatility_thresholds["medium"]:
                precision_mode = "second"
            else:
                precision_mode = "tick_simulation"
            
            periods.append({
                'start': day_data[0]['timestamp'],
                'end': day_data[-1]['timestamp'],
                'volatility': volatility,
                'precision_mode': precision_mode,
                'trade_volume': sum(candle['volume'] for candle in day_data)
            })
        
        return periods
```

---

### 3️⃣ 高级用户 - Tick级回测 (Elite Tier)

#### 数据特征
- **精度**: 真实tick级数据 (毫秒级)
- **深度**: 完整订单簿数据 (Level 2)
- **延迟**: 超低延迟数据获取 (<50ms)
- **历史深度**: 5年完整tick数据

#### 技术实现
```python
class TickBacktestEngine:
    """Tick级高精度回测引擎"""
    
    def __init__(self):
        self.data_type = "tick"
        self.precision = "millisecond"
        self.orderbook_depth = 20  # L2数据深度
        
    async def run_tick_backtest(self, strategy, symbol, start_date, end_date):
        """运行tick级回测"""
        
        # 1. 获取完整tick数据
        tick_stream = await self._get_tick_stream(symbol, start_date, end_date)
        
        # 2. 构建实时订单簿
        orderbook = OrderBookSimulator()
        
        # 3. 逐tick执行策略
        portfolio = PortfolioSimulator()
        execution_engine = TickExecutionEngine()
        
        async for tick in tick_stream:
            # 更新订单簿
            orderbook.update(tick)
            
            # 策略决策
            signals = await strategy.on_tick(tick, orderbook, portfolio)
            
            # 精确成交模拟
            for signal in signals:
                execution_result = await execution_engine.execute_order(
                    signal, orderbook, tick.timestamp
                )
                portfolio.update(execution_result)
        
        return {
            "data_type": "tick",
            "precision": "millisecond",
            "total_ticks": len(tick_stream),
            "execution_details": execution_engine.get_execution_analytics(),
            "slippage_analysis": execution_engine.calculate_slippage(),
            "market_impact": execution_engine.calculate_market_impact()
        }

class OrderBookSimulator:
    """订单簿模拟器"""
    
    def __init__(self, depth=20):
        self.bids = []  # [(price, volume), ...]
        self.asks = []  # [(price, volume), ...]
        self.depth = depth
        
    def update(self, tick):
        """更新订单簿状态"""
        if tick.type == "trade":
            self._process_trade(tick)
        elif tick.type == "orderbook":
            self._update_levels(tick)
    
    def get_best_bid_ask(self):
        """获取最优买卖价"""
        best_bid = self.bids[0][0] if self.bids else None
        best_ask = self.asks[0][0] if self.asks else None
        return best_bid, best_ask
    
    def get_market_depth(self, side, volume):
        """计算大单成交的平均价格"""
        levels = self.bids if side == "sell" else self.asks
        
        total_volume = 0
        weighted_price = 0
        
        for price, available_volume in levels:
            if total_volume >= volume:
                break
                
            take_volume = min(available_volume, volume - total_volume)
            weighted_price += price * take_volume
            total_volume += take_volume
        
        return weighted_price / total_volume if total_volume > 0 else None

class TickExecutionEngine:
    """Tick级成交引擎"""
    
    def __init__(self):
        self.executions = []
        self.slippage_model = SlippageModel()
        
    async def execute_order(self, order, orderbook, timestamp):
        """执行订单，考虑滑点和市场冲击"""
        
        # 1. 计算理论成交价
        theoretical_price = orderbook.get_mid_price()
        
        # 2. 计算实际成交价(考虑滑点)
        actual_price = self.slippage_model.calculate_execution_price(
            order, orderbook, timestamp
        )
        
        # 3. 模拟市场冲击
        market_impact = self.slippage_model.calculate_market_impact(
            order.volume, orderbook.get_liquidity()
        )
        
        # 4. 记录成交
        execution = {
            'timestamp': timestamp,
            'symbol': order.symbol,
            'side': order.side,
            'volume': order.volume,
            'theoretical_price': theoretical_price,
            'actual_price': actual_price,
            'slippage': actual_price - theoretical_price,
            'market_impact': market_impact,
            'commission': self._calculate_commission(order)
        }
        
        self.executions.append(execution)
        return execution
```

## 💾 数据存储架构

### 分层存储策略
```python
class TieredDataStorage:
    """分层数据存储系统"""
    
    def __init__(self):
        self.storage_layers = {
            "hot": RedisTimeSeriesStorage(),      # 热数据：最近7天tick
            "warm": OptionalTimeSeriesStorage(),  # 温数据（可选，默认禁用 InfluxDB）
            "cold": S3ArchiveStorage(),           # 冷数据：历史K线数据
            "archive": GlacierStorage()           # 归档：长期tick数据
        }
    
    async def get_data(self, symbol, data_type, start_date, end_date, user_tier):
        """根据用户等级获取相应精度数据"""
        
        if user_tier == "basic":
            return await self._get_kline_data(symbol, start_date, end_date)
        elif user_tier == "pro":
            return await self._get_hybrid_data(symbol, start_date, end_date)
        elif user_tier == "elite":
            return await self._get_tick_data(symbol, start_date, end_date)
    
    async def _get_tick_data(self, symbol, start_date, end_date):
        """获取tick级数据"""
        # 优先从热存储获取
        recent_data = await self.storage_layers["hot"].get_ticks(symbol, start_date, end_date)
        
        # 从温存储补充
        if not recent_data:
            warm_data = await self.storage_layers["warm"].get_ticks(symbol, start_date, end_date)
            return warm_data
        
        # 从冷存储获取历史数据
        if start_date < datetime.now() - timedelta(days=30):
            cold_data = await self.storage_layers["cold"].get_ticks(symbol, start_date, end_date)
            return recent_data + cold_data
        
        return recent_data
```

### 存储成本优化
```yaml
数据压缩策略:
  tick数据: 
    - 压缩率: 10:1 (时间戳差分压缩)
    - 存储格式: Parquet + ZSTD
    - 索引策略: 时间 + 交易对分区
  
  秒级数据:
    - 压缩率: 5:1 (OHLCV聚合)
    - 存储格式: （可选）时序存储协议（默认不启用）
    - 保留策略: 6个月热存储
  
  K线数据:
    - 压缩率: 100:1 (相对tick数据)
    - 存储格式: SQLite + 压缩
    - 保留策略: 永久存储

成本分析:
  tick数据存储: $100/TB/月
  秒级数据存储: $50/TB/月  
  K线数据存储: $20/TB/月
  
  单用户月度存储成本:
  - Basic用户: $0.50/月
  - Pro用户: $5.00/月
  - Elite用户: $25.00/月
```

## 🔧 技术实现方案

### 1. 数据采集层
```python
class DataCollectionPipeline:
    """多层次数据采集管道"""
    
    def __init__(self):
        self.collectors = {
            "tick": TickDataCollector(),
            "second": SecondAggregator(),
            "minute": MinuteAggregator()
        }
    
    async def start_collection(self, symbols):
        """启动多层次数据采集"""
        tasks = []
        
        for symbol in symbols:
            # Tick级数据采集
            tasks.append(self.collectors["tick"].collect(symbol))
            
            # 实时聚合为秒级数据
            tasks.append(self.collectors["second"].aggregate(symbol))
            
            # 实时聚合为分钟级数据
            tasks.append(self.collectors["minute"].aggregate(symbol))
        
        await asyncio.gather(*tasks)

class TickDataCollector:
    """Tick数据采集器"""
    
    async def collect(self, symbol):
        """采集tick数据"""
        async with websocket.connect(f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade") as ws:
            async for message in ws:
                tick = self._parse_tick(message)
                
                # 存储到热存储
                await self._store_hot(tick)
                
                # 触发实时聚合
                await self._trigger_aggregation(tick)
    
    def _parse_tick(self, raw_message):
        """解析tick数据"""
        data = json.loads(raw_message)
        return {
            'timestamp': data['T'],
            'symbol': data['s'],
            'price': float(data['p']),
            'volume': float(data['q']),
            'side': 'buy' if data['m'] else 'sell',
            'trade_id': data['t']
        }
```

### 2. 回测引擎统一接口
```python
class UnifiedBacktestEngine:
    """统一回测引擎接口"""
    
    def __init__(self):
        self.engines = {
            "basic": BasicBacktestEngine(),
            "pro": HybridBacktestEngine(),
            "elite": TickBacktestEngine()
        }
    
    async def run_backtest(self, user_tier, strategy, params):
        """根据用户等级运行相应回测"""
        
        # 选择合适的回测引擎
        engine = self.engines[user_tier]
        
        # 设置资源限制
        limits = self._get_user_limits(user_tier)
        engine.set_limits(limits)
        
        # 执行回测
        result = await engine.run_backtest(strategy, params)
        
        # 添加用户等级标识
        result['user_tier'] = user_tier
        result['data_precision'] = engine.data_type
        
        return result
    
    def _get_user_limits(self, user_tier):
        """获取用户资源限制"""
        limits = {
            "basic": {
                "max_concurrent_backtests": 3,
                "max_backtest_duration": 6,  # 月
                "max_strategy_complexity": "basic",
                "api_calls_per_day": 1000
            },
            "pro": {
                "max_concurrent_backtests": 10,
                "max_backtest_duration": 24,  # 月
                "max_strategy_complexity": "advanced",
                "api_calls_per_day": 10000
            },
            "elite": {
                "max_concurrent_backtests": 50,
                "max_backtest_duration": 60,  # 月
                "max_strategy_complexity": "unlimited",
                "api_calls_per_day": 100000
            }
        }
        return limits[user_tier]
```

## 💰 商业化策略

### 定价方案
```yaml
Basic Plan ($19/月):
  数据精度: K线级 (1分钟最高)
  历史数据: 6个月
  并发回测: 3个
  策略复杂度: 基础技术指标
  报告格式: 标准JSON
  API限制: 1000次/天
  
Pro Plan ($79/月):
  数据精度: 混合模式 (秒级+tick模拟)
  历史数据: 2年
  并发回测: 10个
  策略复杂度: 高级算法
  报告格式: JSON + HTML + PDF
  API限制: 10000次/天
  智能精度切换: ✅
  
Elite Plan ($299/月):
  数据精度: 真实Tick级
  历史数据: 5年
  并发回测: 50个
  策略复杂度: 无限制
  报告格式: 全格式支持
  API限制: 100000次/天
  订单簿模拟: ✅
  滑点分析: ✅
  市场冲击分析: ✅
```

### 成本控制
```yaml
数据成本:
  - Tick数据采集: $500/月/交易对
  - 存储成本: $100-500/月 (根据用户规模)
  - 计算资源: $200-1000/月
  
收入模型:
  - Basic用户 (40人): $760/月
  - Pro用户 (8人): $632/月  
  - Elite用户 (2人): $598/月
  - 总收入: $1990/月
  - 成本: $1200/月
  - 利润率: 40%
```

## 🎯 分阶段实施计划

### Phase 1 (2周): 基础架构
- [x] 当前K线回测引擎 (已完成)
- [ ] 用户分层系统
- [ ] 统一回测接口
- [ ] 基础数据存储优化

### Phase 2 (3周): Pro层功能
- [ ] 秒级数据采集
- [ ] 混合回测引擎
- [ ] 智能精度切换
- [ ] Tick模拟算法

### Phase 3 (4周): Elite层功能
- [ ] 真实Tick数据采集
- [ ] 订单簿模拟
- [ ] 滑点分析引擎
- [ ] 高频策略支持

### Phase 4 (2周): 优化部署
- [ ] 性能优化
- [ ] 成本控制
- [ ] 监控告警
- [ ] 用户迁移

这个分层方案既满足了不同用户的需求，又实现了合理的商业化路径，同时保持了技术架构的可扩展性。
