# OKX Tick数据拉取优化方案

> **基于现有工具设计**: 基于 `/root/Tradebot/tools` 现有架构的tick数据拉取优化方案
> **设计时间**: 2025-08-24
> **状态**: 方案设计完成，待实施

## 🎯 方案概述

基于对现有 `/root/Tradebot/tools` 系统的深入分析，设计一套完整的OKX tick数据拉取优化方案，充分利用现有成熟架构，扩展多交易对支持，提升数据质量和集成能力。

### 核心目标
- **扩展资产覆盖**: 从单一BTC扩展到50+主流USDT交易对
- **优化调度策略**: 基于现有6小时cron系统的智能分层调度
- **提升数据质量**: 增强现有去重逻辑和完整性检查
- **系统集成**: 与Trademe交易系统无缝对接

## 🏗️ 现有架构分析

### 优势识别
- ✅ **成熟的OKX CDN数据源**: `https://static.okx.com/cdn/okex/traderecords/trades/daily/`
- ✅ **验证的数据去重逻辑**: 移除相邻同价交易，确保数据质量
- ✅ **完整的下载机制**: aria2c并发下载 + ZIP自动解压处理
- ✅ **PostgreSQL存储集成**: 标准化`spider_trade`表结构

### 当前限制
- ❌ **单交易对限制**: 仅支持BTC-USDT
- ❌ **固定调度策略**: 每6小时拉取所有数据，无优先级
- ❌ **基础去重逻辑**: 仅基于价格相邻性，可进一步优化
- ❌ **缺少质量检查**: 无数据完整性验证和自动补缺机制

## 🚀 优化方案设计

### 1. 多资产支持扩展

#### 1.1 分层资产配置
```bash
# 基于现有spider.trades.okex.sh的扩展配置

# 高优先级交易对 - 每日拉取 (核心主流币)
HIGH_PRIORITY_ASSETS=(
    BTC ETH BNB ADA XRP SOL DOGE MATIC LTC AVAX
)

# 中优先级交易对 - 每周拉取 (主要DeFi币)
MID_PRIORITY_ASSETS=(
    LINK DOT UNI ATOM FTM NEAR ALGO ICP AAVE SAND
    MANA CRV COMP YFI SNX BAL REN SUSHI 1INCH MKR
)

# 低优先级交易对 - 按需拉取 (新兴币种)
LOW_PRIORITY_ASSETS=(
    GRT ALPHA ROSE KAVA AUDIO CHZ ENJ BAT ZRX STORJ
    ANKR CTSI RLC NMR LRC OMG SKL CELR BAND REQ
)

# 动态配置函数
get_assets_by_priority() {
    local priority=$1
    case $priority in
        "high")   echo "${HIGH_PRIORITY_ASSETS[@]}" ;;
        "mid")    echo "${MID_PRIORITY_ASSETS[@]}" ;;
        "low")    echo "${LOW_PRIORITY_ASSETS[@]}" ;;
        *)        echo "${HIGH_PRIORITY_ASSETS[@]}" ;;
    esac
}
```

#### 1.2 URL模式扩展
```bash
# 基于现有URL模式的多资产支持
generate_okx_tick_url() {
    local asset=$1
    local day=$2
    local formatted_day=$3
    
    echo "https://static.okx.com/cdn/okex/traderecords/trades/daily/$day/${asset}-USDT-trades-${formatted_day}.zip"
}

# 支持多交易所扩展 (未来)
generate_multi_exchange_url() {
    local exchange=$1
    local asset=$2
    local day=$3
    
    case $exchange in
        "okx")     generate_okx_tick_url $asset $day ;;
        "binance") generate_binance_tick_url $asset $day ;;
        *)         generate_okx_tick_url $asset $day ;;
    esac
}
```

### 2. 智能调度策略优化

#### 2.1 分时段调度设计
```bash
# 基于现有tradebot-crontask.sh的增强版调度

# 优化的调度策略 (基于现有6小时周期)
# 00:00 - 高优先级交易对拉取 (10个币种)
# 06:00 - 中优先级交易对拉取 (20个币种)  
# 12:00 - 低优先级交易对拉取 (20个币种)
# 18:00 - 数据质量检查和缺失补充

enhanced_crontask_strategy() {
    local current_hour=$(date +%H)
    local current_date=$1
    local lookback_days=$2
    
    case $current_hour in
        00) 
            echo "执行高优先级资产tick数据拉取"
            process_tick_data "high" $current_date $lookback_days
            ;;
        06) 
            echo "执行中优先级资产tick数据拉取"
            process_tick_data "mid" $current_date $lookback_days
            ;;
        12) 
            echo "执行低优先级资产tick数据拉取"  
            process_tick_data "low" $current_date $lookback_days
            ;;
        18)
            echo "执行数据质量检查和补充"
            data_quality_check_and_backfill $current_date
            ;;
        *)
            echo "默认执行高优先级资产拉取"
            process_tick_data "high" $current_date $lookback_days
            ;;
    esac
}

# 并发控制优化
MAX_CONCURRENT_DOWNLOADS=5  # 基于现有aria2c配置
DOWNLOAD_RETRY_COUNT=3
DOWNLOAD_TIMEOUT=300
```

#### 2.2 动态优先级调整
```bash
# 基于数据使用频率的动态优先级调整
adjust_priority_by_usage() {
    local asset=$1
    local usage_count=$(get_asset_usage_count $asset)
    
    if [ $usage_count -gt 100 ]; then
        echo "high"
    elif [ $usage_count -gt 20 ]; then
        echo "mid"  
    else
        echo "low"
    fi
}

# 市场热度感知调度
adjust_priority_by_volatility() {
    local asset=$1
    local volatility=$(calculate_24h_volatility $asset)
    
    # 高波动率资产提升优先级
    if (( $(echo "$volatility > 0.1" | bc -l) )); then
        echo "high"
    else
        echo "normal"
    fi
}
```

### 3. 数据质量保障机制

#### 3.1 增强去重逻辑
```bash
# 基于现有awk去重的增强版本
enhanced_tick_deduplication() {
    local csv_file=$1
    local asset=$2
    
    awk -F, -v asset="$asset" '
    BEGIN {
        last_price = 0
        last_timestamp = 0  
        last_volume = 0
        min_time_diff = 10  # 最小时间间隔10ms
        min_price_diff = 0.0001  # 最小价格变化
    }
    {
        if (NR == 1) {
            print "id","tick","price","base_asset","quote_asset","volume","side","timestamp"
        } else {
            current_price = $2
            current_timestamp = $5
            current_volume = $3
            current_side = $4
            
            # 多维度去重检查
            time_diff = current_timestamp - last_timestamp
            price_diff = sqrt((current_price - last_price)^2) / last_price
            volume_significant = current_volume > 0.001
            
            # 保留条件：时间间隔足够 OR 价格变化显著 OR 交易量显著
            if (time_diff > min_time_diff || 
                price_diff > min_price_diff || 
                volume_significant) {
                
                print $1, $5, $2, asset, "USDT", $3, current_side, $5
                
                last_price = current_price
                last_timestamp = current_timestamp  
                last_volume = current_volume
            }
        }
    }' $csv_file > "${csv_file}.processed"
}
```

#### 3.2 数据完整性检查
```bash
# 数据质量检查和验证
data_quality_validator() {
    local asset=$1
    local date=$2
    local csv_file=$3
    
    # 检查数据基本统计
    local record_count=$(wc -l < $csv_file)
    local price_range=$(awk -F, 'NR>1 {if(min==""){min=max=$2}; if($2>max) max=$2; if($2<min) min=$2} END {print max-min}' $csv_file)
    local time_span=$(awk -F, 'NR>1 {if(start==""){start=end=$5}; if($5>end) end=$5; if($5<start) start=$5} END {print (end-start)/1000/3600}' $csv_file)
    
    echo "=== 数据质量报告 ==="
    echo "资产: $asset"
    echo "日期: $date"  
    echo "记录数: $record_count"
    echo "价格波动范围: $price_range USDT"
    echo "时间跨度: $time_span 小时"
    
    # 质量检查标准
    if [ $record_count -lt 1000 ]; then
        echo "警告: 数据量可能不足 (<1000条)"
        return 1
    fi
    
    if (( $(echo "$time_span < 20" | bc -l) )); then
        echo "警告: 时间跨度不完整 (<20小时)"
        return 1  
    fi
    
    echo "✅ 数据质量检查通过"
    return 0
}

# 缺失数据自动补充
data_backfill_mechanism() {
    local asset=$1
    local start_date=$2
    local end_date=$3
    
    echo "检查 $asset 从 $start_date 到 $end_date 的数据完整性"
    
    current_date=$start_date
    while [ "$current_date" != "$end_date" ]; do
        formatted_date=$(date -d "$current_date" +%Y-%m-%d)
        day_folder=$(date -d "$current_date" +%Y%m%d)
        
        # 检查数据是否存在
        if ! check_data_exists $asset $formatted_date; then
            echo "发现缺失数据: $asset $formatted_date，开始补充..."
            
            # 调用原有下载逻辑补充数据
            download_single_asset_data $asset $day_folder $formatted_date
        fi
        
        current_date=$(date -d "$current_date + 1 day" +%Y-%m-%d)
    done
}
```

### 4. PostgreSQL存储优化

#### 4.1 表结构增强
```sql
-- 基于现有spider_trade表的优化

-- 添加性能优化索引
CREATE INDEX IF NOT EXISTS idx_spider_trade_asset_time_perf 
ON spider_trade(base_asset, tick DESC) 
WHERE tick > EXTRACT(EPOCH FROM NOW() - INTERVAL '90 days') * 1000;

CREATE INDEX IF NOT EXISTS idx_spider_trade_price_analysis
ON spider_trade(base_asset, price, tick) 
WHERE tick > EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days') * 1000;

CREATE INDEX IF NOT EXISTS idx_spider_trade_volume_filter
ON spider_trade(base_asset, tick) 
WHERE tick > EXTRACT(EPOCH FROM NOW() - INTERVAL '7 days') * 1000;

-- 数据分区策略 (提升查询性能)
CREATE TABLE spider_trade_2025_01 PARTITION OF spider_trade 
FOR VALUES FROM ('1735689600000') TO ('1738368000000');  -- 2025-01-01 to 2025-02-01 (timestamp format)

CREATE TABLE spider_trade_2025_02 PARTITION OF spider_trade 
FOR VALUES FROM ('1738368000000') TO ('1740787200000');  -- 2025-02-01 to 2025-03-01

-- 数据压缩和归档策略
CREATE TABLE spider_trade_archive AS
SELECT * FROM spider_trade WHERE tick < EXTRACT(EPOCH FROM NOW() - INTERVAL '365 days') * 1000;

-- 定期清理旧数据 (保留1年)
DELETE FROM spider_trade WHERE tick < EXTRACT(EPOCH FROM NOW() - INTERVAL '365 days') * 1000;
```

#### 4.2 查询优化
```sql
-- 高效查询模板

-- 1. 获取指定资产指定时间范围的tick数据
SELECT tick, price, id, base_asset, quote_asset 
FROM spider_trade 
WHERE base_asset = 'BTC' 
  AND tick BETWEEN 1735689600000 AND 1735776000000  -- 指定时间范围
ORDER BY tick ASC
LIMIT 10000;

-- 2. 计算指定时间窗口内的聚合统计
SELECT 
    base_asset,
    COUNT(*) as tick_count,
    MIN(price) as min_price,
    MAX(price) as max_price,
    AVG(price) as avg_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price
FROM spider_trade 
WHERE base_asset = 'ETH'
  AND tick BETWEEN 1735689600000 AND 1735776000000
GROUP BY base_asset;

-- 3. 获取多资产的最新tick数据
WITH latest_ticks AS (
    SELECT base_asset, MAX(tick) as latest_tick
    FROM spider_trade 
    WHERE base_asset IN ('BTC', 'ETH', 'BNB')
    GROUP BY base_asset
)
SELECT st.base_asset, st.tick, st.price, st.id
FROM spider_trade st
JOIN latest_ticks lt ON st.base_asset = lt.base_asset AND st.tick = lt.latest_tick;
```

### 5. Trademe系统集成设计

#### 5.1 数据同步架构
```python
# PostgreSQL到SQLite的数据同步服务
import asyncio
import asyncpg  
import aiosqlite
from typing import List, Dict, Tuple
from datetime import datetime, timedelta

class OKXTickDataSyncer:
    """OKX Tick数据同步器 - 连接PostgreSQL和SQLite"""
    
    def __init__(self, pg_conn_str: str, sqlite_path: str):
        self.pg_conn_str = pg_conn_str
        self.sqlite_path = sqlite_path
        
    async def sync_tick_data_to_trademe(self, 
                                       symbol: str, 
                                       date_range: Tuple[datetime, datetime]) -> Dict:
        """将PostgreSQL中的tick数据同步到Trademe SQLite"""
        
        start_ts = int(date_range[0].timestamp() * 1000)
        end_ts = int(date_range[1].timestamp() * 1000)
        
        # 1. 从PostgreSQL读取tick数据
        tick_data = await self._fetch_from_postgres(symbol, start_ts, end_ts)
        
        # 2. 数据格式转换和清洗
        cleaned_data = await self._clean_and_transform(tick_data)
        
        # 3. 存储到Trademe SQLite
        result = await self._store_to_trademe_sqlite(cleaned_data)
        
        return {
            'symbol': symbol,
            'date_range': date_range,
            'records_synced': len(cleaned_data),
            'sync_status': 'completed',
            'timestamp': datetime.now()
        }
    
    async def _fetch_from_postgres(self, symbol: str, start_ts: int, end_ts: int) -> List[Dict]:
        """从PostgreSQL spider_trade表读取数据"""
        conn = await asyncpg.connect(self.pg_conn_str)
        try:
            query = """
                SELECT tick, price, id, base_asset, quote_asset
                FROM spider_trade 
                WHERE base_asset = $1 
                  AND tick BETWEEN $2 AND $3
                ORDER BY tick ASC
            """
            rows = await conn.fetch(query, symbol, start_ts, end_ts)
            return [dict(row) for row in rows]
        finally:
            await conn.close()
    
    async def _store_to_trademe_sqlite(self, tick_data: List[Dict]) -> bool:
        """存储到Trademe SQLite数据库"""
        async with aiosqlite.connect(self.sqlite_path) as db:
            # 确保表存在
            await db.execute("""
                CREATE TABLE IF NOT EXISTS market_data_ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange VARCHAR(50) DEFAULT 'okx',
                    symbol VARCHAR(20) NOT NULL,
                    price DECIMAL(18,8) NOT NULL,
                    volume DECIMAL(18,8),
                    side VARCHAR(10),
                    timestamp BIGINT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 批量插入数据
            insert_query = """
                INSERT INTO market_data_ticks (symbol, price, timestamp)
                VALUES (?, ?, ?)
            """
            
            data_to_insert = [
                (f"{tick['base_asset']}/USDT", tick['price'], tick['tick'])
                for tick in tick_data
            ]
            
            await db.executemany(insert_query, data_to_insert)
            await db.commit()
            
            return True

# FastAPI集成端点
from fastapi import APIRouter, Depends
from app.core.deps import get_current_user

router = APIRouter()

@router.post("/api/v1/market-data/sync-tick-data")
async def sync_tick_data(
    symbol: str,
    start_date: str,  # "2025-01-01"
    end_date: str,    # "2025-01-02" 
    current_user = Depends(get_current_user)
):
    """同步指定资产的tick数据到Trademe"""
    
    syncer = OKXTickDataSyncer(
        pg_conn_str=settings.POSTGRES_URL,
        sqlite_path=settings.SQLITE_PATH
    )
    
    date_range = (
        datetime.strptime(start_date, "%Y-%m-%d"),
        datetime.strptime(end_date, "%Y-%m-%d")
    )
    
    result = await syncer.sync_tick_data_to_trademe(symbol, date_range)
    return result

@router.get("/api/v1/market-data/tick-data/{symbol}")
async def get_tick_data(
    symbol: str,
    start_timestamp: int,
    end_timestamp: int,
    limit: int = 1000,
    current_user = Depends(get_current_user)
):
    """获取tick数据用于策略回测"""
    
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        cursor = await db.execute("""
            SELECT timestamp, price, volume, side
            FROM market_data_ticks
            WHERE symbol = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (symbol, start_timestamp, end_timestamp, limit))
        
        rows = await cursor.fetchall()
        
        return {
            'symbol': symbol,
            'data': [
                {
                    'timestamp': row[0],
                    'price': float(row[1]),
                    'volume': float(row[2]) if row[2] else 0,
                    'side': row[3]
                }
                for row in rows
            ],
            'count': len(rows)
        }
```

#### 5.2 实时数据集成
```python
# 基于现有utils.py的实时tick数据流
class OKXRealtimeTickStream:
    """OKX实时tick数据流 (基于现有WebSocket机制)"""
    
    def __init__(self):
        # 利用现有utils.py中的API初始化
        self.market_api = None
        
    async def start_tick_stream(self, symbols: List[str]):
        """启动多资产实时tick数据流"""
        
        # 基于现有get_ticker函数的增强版
        for symbol in symbols:
            await self._subscribe_symbol_ticks(f"{symbol}-USDT")
    
    async def _subscribe_symbol_ticks(self, symbol: str):
        """订阅单个资产的tick数据"""
        
        # 结合现有utils.py中的市场API
        if not self.market_api:
            self.market_api = initMarket(
                settings.OKX_API_KEY,
                settings.OKX_SECRET_KEY, 
                settings.OKX_PASSPHRASE
            )
        
        # 持续获取最新ticker数据
        while True:
            try:
                ticker_data = await get_ticker(symbol, self.market_api)
                
                # 转换为统一格式并推送到Trademe
                await self._process_realtime_tick(symbol, ticker_data)
                
                await asyncio.sleep(0.1)  # 100ms间隔
                
            except Exception as e:
                print(f"实时数据获取错误 {symbol}: {e}")
                await asyncio.sleep(1)
    
    async def _process_realtime_tick(self, symbol: str, ticker_data: Dict):
        """处理实时tick数据并存储"""
        
        if ticker_data.get('code') == '0':
            data = ticker_data['data'][0]
            
            tick_record = {
                'symbol': symbol,
                'price': float(data['last']),
                'volume': float(data['vol24h']),
                'timestamp': int(data['ts']),
                'bid_price': float(data['bidPx']),
                'ask_price': float(data['askPx']),
            }
            
            # 推送到Redis缓存供实时使用
            await self._cache_realtime_tick(tick_record)
            
            # 可选：存储到SQLite用于历史分析
            await self._store_realtime_tick(tick_record)
```

## 📋 实施计划

### 第一阶段: 脚本扩展优化 (3天)

**Day 1: 多资产配置扩展**
- 修改 `spider.trades.okex.sh` 支持动态资产列表
- 实现分优先级资产配置
- 测试多资产URL生成和下载

**Day 2: 数据质量增强**  
- 实现增强版去重逻辑 (`enhanced_tick_deduplication`)
- 添加数据完整性检查 (`data_quality_validator`)
- 实现缺失数据自动补充机制

**Day 3: 存储优化**
- 优化PostgreSQL索引和分区
- 测试批量数据插入性能
- 验证数据查询效率

### 第二阶段: 调度系统优化 (2天)

**Day 4: 智能调度实现**
- 增强 `tradebot-crontask.sh` 支持分时段调度
- 实现优先级动态调整逻辑
- 测试并发下载控制

**Day 5: 监控和告警**
- 添加数据拉取状态监控
- 实现异常情况告警机制  
- 建立数据质量报告

### 第三阶段: 系统集成 (2天)

**Day 6: 数据同步服务**
- 实现PostgreSQL到SQLite同步 (`OKXTickDataSyncer`)
- 创建Trademe API端点
- 测试数据格式转换

**Day 7: 实时数据集成**
- 基于现有utils.py实现实时tick流 (`OKXRealtimeTickStream`) 
- 集成WebSocket数据推送
- 完整系统联调测试

## 🎯 预期性能指标

### 数据覆盖能力
- **tick数据资产**: 50个主流USDT交易对
- **历史深度**: 365天完整历史数据
- **数据新鲜度**: < 6小时延迟 (基于现有调度周期)
- **数据完整性**: > 99.5% (基于增强的质量检查)

### 系统性能
- **下载性能**: 5个并发连接，平均50MB/分钟
- **存储效率**: 60%压缩率 (ZIP + 去重优化)
- **查询性能**: 
  - 单日tick数据查询 < 500ms
  - 聚合统计查询 < 200ms
  - 实时数据延迟 < 100ms

### 资源使用
- **磁盘空间**: 约2GB/月 (50个资产 × 平均40MB/天)
- **内存使用**: 峰值500MB (批量处理时)
- **CPU使用**: 平均10% (4核系统)
- **网络带宽**: 峰值100Mbps (并发下载时)

## 🔄 维护和监控

### 数据质量监控
```bash
# 每日数据质量报告生成
generate_daily_quality_report() {
    local date=$(date -d "1 day ago" +%Y-%m-%d)
    
    echo "=== OKX Tick数据质量报告 $date ==="
    
    for asset in "${HIGH_PRIORITY_ASSETS[@]}"; do
        local record_count=$(get_daily_tick_count $asset $date)
        local completeness=$(calculate_data_completeness $asset $date)
        
        echo "$asset: $record_count 条记录, 完整性: $completeness%"
        
        if (( $(echo "$completeness < 95" | bc -l) )); then
            echo "⚠️  $asset 数据完整性低于95%，需要检查"
        fi
    done
}

# 自动化数据修复
auto_data_repair() {
    local problematic_assets=($(find_incomplete_data_assets))
    
    for asset in "${problematic_assets[@]}"; do
        echo "开始修复 $asset 的数据缺失"
        
        # 重新拉取最近7天数据
        repair_asset_data $asset 7
        
        # 验证修复结果
        if validate_repair_result $asset; then
            echo "✅ $asset 数据修复成功"
        else
            echo "❌ $asset 数据修复失败，需要人工介入"
        fi
    done
}
```

### 性能监控
```bash
# 系统性能监控
monitor_system_performance() {
    echo "=== OKX数据拉取系统性能监控 ==="
    
    # 磁盘使用情况
    local disk_usage=$(df -h /path/to/okex_data | tail -1 | awk '{print $5}')
    echo "磁盘使用率: $disk_usage"
    
    # PostgreSQL连接数
    local pg_connections=$(get_postgres_connection_count)
    echo "数据库连接数: $pg_connections"
    
    # 最近24小时拉取统计
    local successful_downloads=$(count_recent_successful_downloads)
    local failed_downloads=$(count_recent_failed_downloads)
    
    echo "成功下载: $successful_downloads"
    echo "失败下载: $failed_downloads"
    echo "成功率: $(calculate_success_rate $successful_downloads $failed_downloads)%"
}
```

## 🚀 扩展路线图

### 短期增强 (1-2个月)
- **多交易所支持**: 扩展Binance、Coinbase等主流交易所
- **数据压缩优化**: 实现更高效的数据压缩算法
- **API限流优化**: 智能API调用频率控制

### 中期规划 (3-6个月)  
- **机器学习集成**: 基于tick数据的价格预测模型
- **实时流处理**: Apache Kafka + Spark Streaming架构
- **云端存储**: S3/OSS对象存储集成

### 长期愿景 (6-12个月)
- **多维度数据**: 整合社交媒体、新闻、链上数据
- **全球部署**: 多地区数据中心部署
- **商业化API**: 面向第三方开发者的数据API服务

---

## 📚 相关文档

- **现有工具文档**: `/root/Tradebot/tools/readme.md`
- **数据库架构**: `/root/trademe/docs/database_schema.md`  
- **API设计文档**: `/root/trademe/docs/api_specification.md`
- **部署指南**: `/root/trademe/docs/deployment.md`

---

**注意**: 此方案基于现有成熟工具设计，风险最低，可操作性强。建议按照实施计划分阶段推进，确保每个阶段都有可验证的成果。