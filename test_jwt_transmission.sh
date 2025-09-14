#!/bin/bash

# JWT传输测试脚本
echo "🔐 测试JWT token传输..."

# 1. 先获取JWT token
echo "1. 获取JWT token..."
LOGIN_RESPONSE=$(curl -s -X POST "http://43.167.252.120/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{"email":"publictest@example.com","password":"PublicTest123!"}')

# 提取token
TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ 获取JWT token失败"
    echo "响应: $LOGIN_RESPONSE"
    exit 1
fi

echo "✅ JWT token获取成功: ${TOKEN:0:20}..."

# 2. 测试实时回测API
echo "2. 测试实时回测API..."
BACKTEST_RESPONSE=$(curl -s -X POST "http://43.167.252.120/api/v1/realtime-backtest/start" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $TOKEN" \
-d '{
    "strategy_code": "// 测试策略代码\nclass TestStrategy {\n  // 测试\n}",
    "exchange": "okx",
    "product_type": "perpetual", 
    "symbols": ["BTC/USDT"],
    "timeframes": ["1h"],
    "fee_rate": "vip3",
    "initial_capital": 10000,
    "start_date": "2025-07-01",
    "end_date": "2025-08-31",
    "data_type": "kline"
}')

echo "回测API响应: $BACKTEST_RESPONSE"

# 3. 检查响应状态
if echo "$BACKTEST_RESPONSE" | grep -q "401\|Unauthorized"; then
    echo "❌ 仍然收到401未授权错误，JWT传输失败"
else
    echo "✅ JWT传输成功，没有收到401错误"
fi

# 4. 测试策略创建API
echo "3. 测试策略创建API..."
STRATEGY_RESPONSE=$(curl -s -X POST "http://43.167.252.120/api/v1/strategies/from-ai" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $TOKEN" \
-d '{
    "name": "测试策略",
    "description": "JWT传输测试",
    "code": "// 测试代码",
    "parameters": {},
    "strategy_type": "strategy",
    "ai_session_id": "test-session"
}')

echo "策略API响应: $STRATEGY_RESPONSE"

if echo "$STRATEGY_RESPONSE" | grep -q "401\|Unauthorized"; then
    echo "❌ 策略API收到401未授权错误"
else
    echo "✅ 策略API JWT传输成功"
fi

echo "🔍 JWT传输测试完成"