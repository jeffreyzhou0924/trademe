"""
策略模板库 - 预置交易策略模板

包含常用的量化交易策略模板，供用户快速创建和自定义策略
"""

from typing import Dict, List, Any

# 策略模板定义
STRATEGY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "rsi_mean_reversion",
        "name": "RSI均值回归策略",
        "description": "基于RSI指标的超买超卖判断，在极值区域进行反向操作",
        "category": "均值回归",
        "difficulty": "入门",
        "timeframe": "1h",
        "parameters": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "position_size": 0.5,
            "stop_loss": 0.05,
            "take_profit": 0.03
        },
        "code": '''
class RSIMeanReversionStrategy(BaseStrategy):
    """RSI均值回归策略"""
    
    def __init__(self, **params):
        super().__init__(**params)
        self.rsi_period = params.get('rsi_period', 14)
        self.oversold = params.get('oversold_threshold', 30)
        self.overbought = params.get('overbought_threshold', 70)
        self.position_size = params.get('position_size', 0.5)
        self.stop_loss = params.get('stop_loss', 0.05)
        self.take_profit = params.get('take_profit', 0.03)
        
    def on_bar(self, bar):
        # 计算RSI指标
        rsi = self.rsi(period=self.rsi_period)
        
        # 获取当前价格
        current_price = bar.close
        
        # RSI超卖时买入
        if rsi < self.oversold and self.position == 0:
            self.buy(size=self.position_size, 
                    stop_loss=current_price * (1 - self.stop_loss),
                    take_profit=current_price * (1 + self.take_profit))
            
        # RSI超买时卖出
        elif rsi > self.overbought and self.position > 0:
            self.sell(size=self.position)
''',
        "tags": ["RSI", "均值回归", "反向交易", "入门"],
        "risk_level": "中等",
        "expected_return": "10-15%",
        "max_drawdown": "8-12%",
        "author": "Trademe AI",
        "created_at": "2024-01-15"
    },
    
    {
        "id": "macd_trend_following",
        "name": "MACD趋势跟踪策略",
        "description": "利用MACD指标的金叉死叉信号进行趋势跟踪交易",
        "category": "趋势跟踪",
        "difficulty": "入门",
        "timeframe": "4h",
        "parameters": {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "position_size": 0.6,
            "stop_loss": 0.08,
            "trailing_stop": 0.05
        },
        "code": '''
class MACDTrendStrategy(BaseStrategy):
    """MACD趋势跟踪策略"""
    
    def __init__(self, **params):
        super().__init__(**params)
        self.fast_period = params.get('fast_period', 12)
        self.slow_period = params.get('slow_period', 26)
        self.signal_period = params.get('signal_period', 9)
        self.position_size = params.get('position_size', 0.6)
        self.stop_loss = params.get('stop_loss', 0.08)
        self.trailing_stop = params.get('trailing_stop', 0.05)
        
    def on_bar(self, bar):
        # 计算MACD指标
        macd_line, signal_line = self.macd(
            fast=self.fast_period, 
            slow=self.slow_period, 
            signal=self.signal_period
        )
        
        current_price = bar.close
        
        # MACD金叉买入信号
        if macd_line > signal_line and self.prev_macd <= self.prev_signal and self.position == 0:
            self.buy(size=self.position_size,
                    stop_loss=current_price * (1 - self.stop_loss),
                    trailing_stop=self.trailing_stop)
            
        # MACD死叉卖出信号
        elif macd_line < signal_line and self.prev_macd >= self.prev_signal and self.position > 0:
            self.sell(size=self.position)
        
        # 保存上一期MACD值
        self.prev_macd = macd_line
        self.prev_signal = signal_line
''',
        "tags": ["MACD", "趋势跟踪", "金叉死叉", "入门"],
        "risk_level": "中等",
        "expected_return": "12-18%",
        "max_drawdown": "10-15%",
        "author": "Trademe AI",
        "created_at": "2024-01-15"
    },
    
    {
        "id": "bollinger_breakout",
        "name": "布林带突破策略",
        "description": "基于布林带的突破交易，在价格突破上下轨时进行交易",
        "category": "突破策略",
        "difficulty": "中级",
        "timeframe": "2h",
        "parameters": {
            "bb_period": 20,
            "bb_std": 2.0,
            "volume_threshold": 1.2,
            "position_size": 0.4,
            "stop_loss": 0.06,
            "take_profit": 0.08
        },
        "code": '''
class BollingerBreakoutStrategy(BaseStrategy):
    """布林带突破策略"""
    
    def __init__(self, **params):
        super().__init__(**params)
        self.bb_period = params.get('bb_period', 20)
        self.bb_std = params.get('bb_std', 2.0)
        self.volume_threshold = params.get('volume_threshold', 1.2)
        self.position_size = params.get('position_size', 0.4)
        self.stop_loss = params.get('stop_loss', 0.06)
        self.take_profit = params.get('take_profit', 0.08)
        
    def on_bar(self, bar):
        # 计算布林带
        upper_band, middle_band, lower_band = self.bollinger_bands(
            period=self.bb_period, 
            std=self.bb_std
        )
        
        current_price = bar.close
        volume = bar.volume
        avg_volume = self.sma(volume, period=20)
        
        # 上轨突破 + 成交量放大 = 买入信号
        if (current_price > upper_band and 
            volume > avg_volume * self.volume_threshold and 
            self.position == 0):
            
            self.buy(size=self.position_size,
                    stop_loss=lower_band,
                    take_profit=current_price * (1 + self.take_profit))
            
        # 下轨突破 + 成交量放大 = 卖空信号
        elif (current_price < lower_band and 
              volume > avg_volume * self.volume_threshold and 
              self.position == 0):
            
            self.sell_short(size=self.position_size,
                           stop_loss=upper_band,
                           take_profit=current_price * (1 - self.take_profit))
        
        # 回到中轨平仓
        elif abs(current_price - middle_band) < 0.01 * middle_band:
            if self.position != 0:
                self.close_position()
''',
        "tags": ["布林带", "突破策略", "成交量", "中级"],
        "risk_level": "中高",
        "expected_return": "15-25%",
        "max_drawdown": "12-18%",
        "author": "Trademe AI",
        "created_at": "2024-01-15"
    },
    
    {
        "id": "grid_trading",
        "name": "网格交易策略",
        "description": "在震荡市场中通过网格化交易获取价差收益",
        "category": "网格交易",
        "difficulty": "中级",
        "timeframe": "1h",
        "parameters": {
            "grid_size": 0.02,
            "grid_levels": 10,
            "base_position": 0.1,
            "center_price": None,  # 自动计算
            "max_position": 1.0,
            "profit_ratio": 0.015
        },
        "code": '''
class GridTradingStrategy(BaseStrategy):
    """网格交易策略"""
    
    def __init__(self, **params):
        super().__init__(**params)
        self.grid_size = params.get('grid_size', 0.02)
        self.grid_levels = params.get('grid_levels', 10)
        self.base_position = params.get('base_position', 0.1)
        self.center_price = params.get('center_price')
        self.max_position = params.get('max_position', 1.0)
        self.profit_ratio = params.get('profit_ratio', 0.015)
        self.grid_orders = {}  # 网格订单记录
        
    def setup(self):
        """初始化网格"""
        if not self.center_price:
            # 使用最近20期平均价作为中心价格
            self.center_price = self.sma(period=20)
            
        # 创建买入网格
        for i in range(1, self.grid_levels + 1):
            buy_price = self.center_price * (1 - i * self.grid_size)
            self.grid_orders[f'buy_{i}'] = {
                'price': buy_price,
                'size': self.base_position,
                'type': 'buy',
                'active': True
            }
            
        # 创建卖出网格
        for i in range(1, self.grid_levels + 1):
            sell_price = self.center_price * (1 + i * self.grid_size)
            self.grid_orders[f'sell_{i}'] = {
                'price': sell_price,
                'size': self.base_position,
                'type': 'sell',
                'active': True
            }
    
    def on_bar(self, bar):
        current_price = bar.close
        
        # 检查买入网格
        for order_id, order in self.grid_orders.items():
            if not order['active']:
                continue
                
            if order['type'] == 'buy' and current_price <= order['price']:
                if self.position < self.max_position:
                    self.buy(size=order['size'])
                    order['active'] = False
                    # 设置对应的卖出订单
                    sell_price = current_price * (1 + self.profit_ratio)
                    self.set_take_profit(sell_price)
                    
            elif order['type'] == 'sell' and current_price >= order['price']:
                if self.position > -self.max_position:
                    self.sell(size=order['size'])
                    order['active'] = False
                    # 设置对应的买入订单
                    buy_price = current_price * (1 - self.profit_ratio)
                    self.set_take_profit(buy_price)
''',
        "tags": ["网格交易", "震荡市场", "套利", "中级"],
        "risk_level": "中等",
        "expected_return": "8-15%",
        "max_drawdown": "6-10%",
        "author": "Trademe AI",
        "created_at": "2024-01-15"
    },
    
    {
        "id": "momentum_breakout",
        "name": "动量突破策略",
        "description": "基于价格动量和成交量的突破策略，捕捉强势趋势",
        "category": "动量策略",
        "difficulty": "高级",
        "timeframe": "6h",
        "parameters": {
            "lookback_period": 20,
            "momentum_threshold": 0.05,
            "volume_ma_period": 10,
            "volume_multiplier": 1.5,
            "position_size": 0.7,
            "stop_loss": 0.1,
            "trailing_stop": 0.08,
            "atr_period": 14,
            "atr_multiplier": 2.0
        },
        "code": '''
class MomentumBreakoutStrategy(BaseStrategy):
    """动量突破策略"""
    
    def __init__(self, **params):
        super().__init__(**params)
        self.lookback_period = params.get('lookback_period', 20)
        self.momentum_threshold = params.get('momentum_threshold', 0.05)
        self.volume_ma_period = params.get('volume_ma_period', 10)
        self.volume_multiplier = params.get('volume_multiplier', 1.5)
        self.position_size = params.get('position_size', 0.7)
        self.stop_loss = params.get('stop_loss', 0.1)
        self.trailing_stop = params.get('trailing_stop', 0.08)
        self.atr_period = params.get('atr_period', 14)
        self.atr_multiplier = params.get('atr_multiplier', 2.0)
        
    def on_bar(self, bar):
        current_price = bar.close
        volume = bar.volume
        
        # 计算动量指标
        highest_high = self.highest_high(period=self.lookback_period)
        lowest_low = self.lowest_low(period=self.lookback_period)
        price_range = highest_high - lowest_low
        momentum = (current_price - lowest_low) / price_range if price_range > 0 else 0
        
        # 计算成交量指标
        volume_ma = self.sma(volume, period=self.volume_ma_period)
        volume_surge = volume > volume_ma * self.volume_multiplier
        
        # 计算ATR用于动态止损
        atr = self.atr(period=self.atr_period)
        dynamic_stop = atr * self.atr_multiplier
        
        # 向上突破信号
        if (momentum > self.momentum_threshold and 
            volume_surge and 
            current_price > highest_high * 0.99 and 
            self.position == 0):
            
            self.buy(size=self.position_size,
                    stop_loss=current_price - dynamic_stop,
                    trailing_stop=self.trailing_stop)
            
        # 向下突破信号  
        elif (momentum < (1 - self.momentum_threshold) and
              volume_surge and
              current_price < lowest_low * 1.01 and
              self.position == 0):
            
            self.sell_short(size=self.position_size,
                           stop_loss=current_price + dynamic_stop,
                           trailing_stop=self.trailing_stop)
        
        # 动量衰竭退出信号
        elif self.position > 0 and momentum < 0.3:
            self.sell(size=self.position)
            
        elif self.position < 0 and momentum > 0.7:
            self.cover(size=abs(self.position))
''',
        "tags": ["动量", "突破", "ATR", "高级"],
        "risk_level": "高",
        "expected_return": "20-35%",
        "max_drawdown": "15-25%",
        "author": "Trademe AI",
        "created_at": "2024-01-15"
    },
    
    {
        "id": "pair_trading",
        "name": "配对交易策略",
        "description": "基于两个相关资产价差的均值回归策略",
        "category": "套利策略",
        "difficulty": "高级",
        "timeframe": "1d",
        "parameters": {
            "symbol_a": "BTC/USDT",
            "symbol_b": "ETH/USDT",
            "lookback_period": 30,
            "entry_threshold": 2.0,
            "exit_threshold": 0.5,
            "position_size": 0.3,
            "correlation_threshold": 0.7,
            "max_holding_period": 14
        },
        "code": '''
class PairTradingStrategy(BaseStrategy):
    """配对交易策略"""
    
    def __init__(self, **params):
        super().__init__(**params)
        self.symbol_a = params.get('symbol_a', 'BTC/USDT')
        self.symbol_b = params.get('symbol_b', 'ETH/USDT')
        self.lookback_period = params.get('lookback_period', 30)
        self.entry_threshold = params.get('entry_threshold', 2.0)
        self.exit_threshold = params.get('exit_threshold', 0.5)
        self.position_size = params.get('position_size', 0.3)
        self.correlation_threshold = params.get('correlation_threshold', 0.7)
        self.max_holding_period = params.get('max_holding_period', 14)
        self.entry_date = None
        
    def on_bar(self, bar):
        # 获取两个资产的价格
        price_a = self.get_price(self.symbol_a)
        price_b = self.get_price(self.symbol_b)
        
        # 计算价差比率
        ratio = price_a / price_b
        ratio_sma = self.sma(ratio, period=self.lookback_period)
        ratio_std = self.std(ratio, period=self.lookback_period)
        
        # 计算Z分数
        z_score = (ratio - ratio_sma) / ratio_std if ratio_std > 0 else 0
        
        # 计算相关性
        correlation = self.correlation(price_a, price_b, period=self.lookback_period)
        
        # 检查相关性是否足够高
        if abs(correlation) < self.correlation_threshold:
            return
        
        current_date = self.current_date()
        
        # 入场条件：价差过大
        if abs(z_score) > self.entry_threshold and self.position == 0:
            if z_score > 0:  # 价差过高，做空价差
                self.sell(self.symbol_a, size=self.position_size)
                self.buy(self.symbol_b, size=self.position_size)
            else:  # 价差过低，做多价差
                self.buy(self.symbol_a, size=self.position_size)
                self.sell(self.symbol_b, size=self.position_size)
                
            self.entry_date = current_date
            
        # 出场条件：价差收敛或最大持仓期
        elif self.position != 0:
            holding_period = (current_date - self.entry_date).days if self.entry_date else 0
            
            if (abs(z_score) < self.exit_threshold or 
                holding_period > self.max_holding_period):
                self.close_all_positions()
                self.entry_date = None
''',
        "tags": ["配对交易", "套利", "均值回归", "高级"],
        "risk_level": "中等",
        "expected_return": "10-20%",
        "max_drawdown": "8-12%",
        "author": "Trademe AI",
        "created_at": "2024-01-15"
    }
]

# 策略分类
STRATEGY_CATEGORIES = [
    {"id": "mean_reversion", "name": "均值回归", "description": "基于价格回归均值的策略"},
    {"id": "trend_following", "name": "趋势跟踪", "description": "跟踪市场趋势的策略"},
    {"id": "breakout", "name": "突破策略", "description": "基于价格突破的策略"},
    {"id": "grid_trading", "name": "网格交易", "description": "在震荡市场中的网格化交易"},
    {"id": "momentum", "name": "动量策略", "description": "基于价格动量的策略"},
    {"id": "arbitrage", "name": "套利策略", "description": "利用价差获利的策略"}
]

# 难度级别
DIFFICULTY_LEVELS = [
    {"id": "beginner", "name": "入门", "description": "适合初学者的简单策略"},
    {"id": "intermediate", "name": "中级", "description": "需要一定经验的策略"},
    {"id": "advanced", "name": "高级", "description": "复杂的专业策略"}
]

# 时间周期选项
TIMEFRAME_OPTIONS = [
    {"id": "1m", "name": "1分钟", "description": "高频交易"},
    {"id": "5m", "name": "5分钟", "description": "短线交易"},
    {"id": "15m", "name": "15分钟", "description": "短线交易"},
    {"id": "1h", "name": "1小时", "description": "中短线交易"},
    {"id": "2h", "name": "2小时", "description": "中线交易"},
    {"id": "4h", "name": "4小时", "description": "中线交易"},
    {"id": "6h", "name": "6小时", "description": "中长线交易"},
    {"id": "1d", "name": "1天", "description": "长线交易"}
]

def get_strategy_templates() -> List[Dict[str, Any]]:
    """获取所有策略模板"""
    return STRATEGY_TEMPLATES

def get_strategy_template_by_id(template_id: str) -> Dict[str, Any]:
    """根据ID获取策略模板"""
    for template in STRATEGY_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None

def get_templates_by_category(category: str) -> List[Dict[str, Any]]:
    """根据分类获取策略模板"""
    return [t for t in STRATEGY_TEMPLATES if t.get("category") == category]

def get_templates_by_difficulty(difficulty: str) -> List[Dict[str, Any]]:
    """根据难度获取策略模板"""
    return [t for t in STRATEGY_TEMPLATES if t.get("difficulty") == difficulty]

def search_templates(keyword: str) -> List[Dict[str, Any]]:
    """搜索策略模板"""
    keyword = keyword.lower()
    results = []
    
    for template in STRATEGY_TEMPLATES:
        # 搜索名称、描述、标签
        if (keyword in template["name"].lower() or 
            keyword in template["description"].lower() or
            any(keyword in tag.lower() for tag in template.get("tags", []))):
            results.append(template)
    
    return results