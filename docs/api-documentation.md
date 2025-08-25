# Trademe API 接口文档

> **版本**: v1.0  
> **更新时间**: 2025-08-21  
> **环境**: 公网测试环境 (43.167.252.120)

## 🌍 API访问地址

### 公网测试环境 (推荐)
- **基础URL**: http://43.167.252.120/api/v1
- **Swagger文档**: http://43.167.252.120/docs
- **健康检查**: http://43.167.252.120/health

### 本地开发环境
- **用户服务**: http://localhost:3001/api/v1
- **交易服务**: http://localhost:8001/api/v1
- **Swagger文档**: http://localhost:8001/docs

## 🔐 认证机制

### JWT令牌认证
所有需要认证的接口都需要在请求头中包含JWT令牌：

```http
Authorization: Bearer <access_token>
```

### 获取访问令牌
通过用户登录接口获取JWT令牌：

```bash
curl -X POST "http://43.167.252.120/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "publictest@example.com",
    "password": "PublicTest123!"
  }'
```

响应示例：
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "user": {
      "id": "9",
      "username": "publictest",
      "email": "publictest@example.com",
      "membership_level": "premium"
    }
  }
}
```

## 👤 用户服务接口

### 1. 用户认证

#### 用户注册
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "TestPassword123!",
  "confirm_password": "TestPassword123!",
  "phone": "+8613800138000"
}
```

#### 用户登录
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "test@example.com",
  "password": "TestPassword123!"
}
```

#### 刷新令牌
```http
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

#### 用户登出
```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

### 2. 用户信息管理

#### 获取用户信息
```http
GET /api/v1/user/profile
Authorization: Bearer <access_token>
```

#### 更新用户信息
```http
PUT /api/v1/user/profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "username": "newusername",
  "phone": "+8613800138001"
}
```

#### 上传头像
```http
POST /api/v1/user/avatar
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

avatar: <file>
```

### 3. 会员系统

#### 获取会员信息
```http
GET /api/v1/membership/info
Authorization: Bearer <access_token>
```

#### 获取会员计划
```http
GET /api/v1/membership/plans
```

## 💼 交易服务接口

### 1. 策略管理

#### 获取策略列表
```http
GET /api/v1/strategies/
Authorization: Bearer <access_token>

# 查询参数
skip=0&limit=20&is_active=true
```

响应示例：
```json
{
  "strategies": [],
  "total": 0,
  "skip": 0,
  "limit": 20
}
```

#### 创建策略
```http
POST /api/v1/strategies/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "EMA交叉策略",
  "description": "基于EMA均线交叉的趋势跟踪策略",
  "code": "# 策略代码",
  "parameters": {
    "fast_period": 12,
    "slow_period": 26
  }
}
```

#### 获取策略详情
```http
GET /api/v1/strategies/{strategy_id}
Authorization: Bearer <access_token>
```

#### 更新策略
```http
PUT /api/v1/strategies/{strategy_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "更新的策略名称",
  "description": "更新的描述",
  "parameters": {
    "fast_period": 10,
    "slow_period": 30
  }
}
```

#### 删除策略
```http
DELETE /api/v1/strategies/{strategy_id}
Authorization: Bearer <access_token>
```

### 2. 回测分析

#### 创建回测任务
```http
POST /api/v1/backtests/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "strategy_id": 1,
  "symbol": "BTC/USDT",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 10000,
  "parameters": {
    "fast_period": 12,
    "slow_period": 26
  }
}
```

#### 获取回测列表
```http
GET /api/v1/backtests/
Authorization: Bearer <access_token>

# 查询参数
skip=0&limit=20&strategy_id=1
```

#### 获取回测详情
```http
GET /api/v1/backtests/{backtest_id}
Authorization: Bearer <access_token>
```

#### 获取回测分析报告
```http
GET /api/v1/backtests/{backtest_id}/analysis
Authorization: Bearer <access_token>
```

#### 停止回测任务
```http
POST /api/v1/backtests/{backtest_id}/stop
Authorization: Bearer <access_token>
```

### 3. AI智能分析

#### AI对话接口
```http
POST /api/v1/ai/chat
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "请分析一下BTC当前的市场趋势",
  "session_id": "session_001"
}
```

#### 获取对话历史
```http
GET /api/v1/ai/chat/history
Authorization: Bearer <access_token>

# 查询参数
session_id=session_001&limit=50
```

#### 市场分析
```http
POST /api/v1/ai/market/analyze
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "symbol": "BTC/USDT",
  "timeframe": "1d",
  "analysis_type": "technical"
}
```

#### 策略生成
```http
POST /api/v1/ai/strategy/generate
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "market_condition": "trending",
  "risk_level": "medium",
  "capital": 10000,
  "requirements": "基于技术指标的趋势跟踪策略"
}
```

#### 策略优化
```http
POST /api/v1/ai/strategy/optimize
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "strategy_id": 1,
  "backtest_results": {
    "total_return": 0.15,
    "sharpe_ratio": 1.2,
    "max_drawdown": 0.08
  },
  "optimization_goal": "sharpe_ratio"
}
```

#### AI使用统计
```http
GET /api/v1/ai/usage/stats
Authorization: Bearer <access_token>

# 查询参数  
period_days=30
```

响应示例：
```json
{
  "period_days": 30,
  "total_requests": 0,
  "total_input_tokens": 0,
  "total_output_tokens": 0,
  "total_tokens": 0,
  "total_cost_usd": 0,
  "by_feature": {},
  "claude_client_stats": {
    "total_requests": 0,
    "successful_requests": 0,
    "error_count": 0,
    "success_rate": 0.0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "average_response_time_ms": 0.0,
    "cost_per_request": 0.0
  }
}
```

### 4. API密钥管理

#### 获取API密钥列表
```http
GET /api/v1/api-keys/
Authorization: Bearer <access_token>
```

#### 添加API密钥
```http
POST /api/v1/api-keys/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "exchange": "binance",
  "api_key": "your_api_key",
  "secret_key": "your_secret_key",
  "passphrase": "your_passphrase"
}
```

#### 测试API密钥
```http
POST /api/v1/api-keys/{api_key_id}/test
Authorization: Bearer <access_token>
```

#### 删除API密钥
```http
DELETE /api/v1/api-keys/{api_key_id}
Authorization: Bearer <access_token>
```

### 5. 实盘交易

#### 获取交易所余额
```http
GET /api/v1/trading/balance
Authorization: Bearer <access_token>

# 查询参数
exchange=binance
```

#### 获取支持的交易对
```http
GET /api/v1/trading/symbols
Authorization: Bearer <access_token>

# 查询参数
exchange=binance
```

#### 下单交易
```http
POST /api/v1/trading/order
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "side": "buy",
  "type": "limit",
  "amount": 0.001,
  "price": 45000
}
```

#### 获取订单历史
```http
GET /api/v1/trading/orders
Authorization: Bearer <access_token>

# 查询参数
exchange=binance&symbol=BTC/USDT&status=filled
```

#### 取消订单
```http
DELETE /api/v1/trading/orders/{order_id}
Authorization: Bearer <access_token>
```

### 6. 市场数据

#### 获取K线数据
```http
GET /api/v1/market/klines
Authorization: Bearer <access_token>

# 查询参数
symbol=BTC/USDT&timeframe=1h&limit=100
```

#### 获取实时价格
```http
GET /api/v1/market/ticker
Authorization: Bearer <access_token>

# 查询参数
symbol=BTC/USDT
```

## 🔔 WebSocket接口

### 连接地址
- **公网环境**: ws://43.167.252.120/ws
- **本地环境**: ws://localhost:8001/ws

### 认证
连接建立后需要发送认证消息：

```json
{
  "type": "auth",
  "token": "your_jwt_token",
  "user_id": "user_id"
}
```

### 订阅市场数据
```json
{
  "type": "subscribe_market",
  "symbol": "BTC/USDT",
  "interval": "1m"
}
```

### 订阅交易更新
```json
{
  "type": "subscribe_trading",
  "user_id": "user_id"
}
```

### 消息格式

#### 市场数据推送
```json
{
  "type": "market_data",
  "payload": {
    "symbol": "BTC/USDT",
    "kline": {
      "open": "45000.00",
      "high": "45500.00",
      "low": "44800.00",
      "close": "45200.00",
      "volume": "123.45"
    },
    "timestamp": 1755745800
  }
}
```

#### 价格更新推送
```json
{
  "type": "ticker_update",
  "payload": {
    "symbol": "BTC/USDT",
    "price": "45200.00",
    "change": "200.00",
    "changePercent": "0.44",
    "volume24h": "1234567.89"
  }
}
```

#### 订单状态推送
```json
{
  "type": "order_update",
  "payload": {
    "order_id": "12345",
    "status": "filled",
    "filled_quantity": "0.001",
    "remaining_quantity": "0.000"
  }
}
```

## 📊 错误处理

### 标准错误响应
```json
{
  "success": false,
  "code": 400,
  "message": "请求参数错误",
  "error_code": "INVALID_PARAMETERS",
  "timestamp": "2025-08-21T03:10:00.000Z",
  "request_id": "req_1755745800_abc123"
}
```

### 常见错误码

| HTTP状态码 | 错误代码 | 描述 |
|------------|----------|------|
| 400 | INVALID_PARAMETERS | 请求参数错误 |
| 401 | UNAUTHORIZED | 未授权，需要登录 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 资源冲突 |
| 422 | VALIDATION_ERROR | 数据验证失败 |
| 429 | RATE_LIMIT_EXCEEDED | 请求频率超限 |
| 500 | INTERNAL_SERVER_ERROR | 服务器内部错误 |

## 🔒 API限制

### 请求频率限制
- **基础版用户**: 100次/分钟
- **高级版用户**: 1000次/分钟
- **WebSocket连接**: 同时最多5个连接

### 数据限制
- **K线数据**: 单次最多1000条
- **订单历史**: 单次最多100条
- **AI对话**: 每日最多100次对话

## 🧪 测试用例

### 完整测试流程

```bash
# 1. 用户登录
TOKEN=$(curl -X POST "http://43.167.252.120/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"publictest@example.com","password":"PublicTest123!"}' \
  | jq -r '.data.access_token')

# 2. 获取用户信息
curl -X GET "http://43.167.252.120/api/v1/user/profile" \
  -H "Authorization: Bearer $TOKEN"

# 3. 获取策略列表
curl -X GET "http://43.167.252.120/api/v1/strategies/" \
  -H "Authorization: Bearer $TOKEN"

# 4. AI使用统计
curl -X GET "http://43.167.252.120/api/v1/ai/usage/stats" \
  -H "Authorization: Bearer $TOKEN"

# 5. 健康检查
curl -X GET "http://43.167.252.120/health"
```

## 📚 SDK和工具

### Python SDK 示例
```python
import requests

class TrademeAPI:
    def __init__(self, base_url, email, password):
        self.base_url = base_url
        self.token = self._login(email, password)
    
    def _login(self, email, password):
        response = requests.post(f"{self.base_url}/auth/login", json={
            "email": email,
            "password": password
        })
        return response.json()["data"]["access_token"]
    
    def get_strategies(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/strategies/", headers=headers)
        return response.json()

# 使用示例
api = TrademeAPI("http://43.167.252.120/api/v1", "publictest@example.com", "PublicTest123!")
strategies = api.get_strategies()
print(strategies)
```

### JavaScript SDK 示例
```javascript
class TrademeAPI {
  constructor(baseUrl, email, password) {
    this.baseUrl = baseUrl;
    this.login(email, password);
  }
  
  async login(email, password) {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await response.json();
    this.token = data.data.access_token;
  }
  
  async getStrategies() {
    const response = await fetch(`${this.baseUrl}/strategies/`, {
      headers: { 'Authorization': `Bearer ${this.token}` }
    });
    return response.json();
  }
}

// 使用示例
const api = new TrademeAPI('http://43.167.252.120/api/v1', 'publictest@example.com', 'PublicTest123!');
const strategies = await api.getStrategies();
console.log(strategies);
```

## 📞 技术支持

- **API文档**: http://43.167.252.120/docs (Swagger)
- **用户指南**: [docs/user-guide.md](./user-guide.md)
- **部署文档**: [docs/deployment.md](./deployment.md)
- **问题反馈**: 通过GitHub Issues提交

---

**💡 提示**: 建议使用Postman或其他API测试工具进行接口调试。所有接口都支持CORS跨域请求。