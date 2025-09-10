# WebSocket连接修复总结

## 问题描述
前端显示"WebSocket连接建立失败，请检查网络后重试"
控制台错误: "WebSocket AI服务错误: Event {isTrusted: true, type: 'error'..."

## 问题原因
1. **错误的WebSocket端点**: 前端尝试连接 `/api/v1/ai/ws/chat`，但实际端点是 `/ws/realtime`
2. **认证消息格式不匹配**: 前端发送 `type: 'authenticate'`，但后端期望 `type: 'auth'`
3. **JWT token格式不一致**: 生成的token格式与后端验证期望的格式不匹配
4. **端口问题**: 前端直接连接到8001端口，但生产环境应该通过Nginx代理
5. **Nginx配置缺失**: 没有配置WebSocket代理支持

## 修复内容

### 1. 前端WebSocket端点修正
**文件**: `/root/trademe/frontend/src/services/ai/websocketAI.ts`
```typescript
// 修改前
const wsUrl = config.baseUrl.replace(/^http/, 'ws') + '/api/v1/ai/ws/chat'

// 修改后
const wsUrl = config.baseUrl.replace(/^http/, 'ws') + '/ws/realtime'
```

### 2. 认证消息类型修正
**文件**: `/root/trademe/frontend/src/services/ai/websocketClient.ts`
```typescript
// 修改前
this.send({
  type: 'authenticate',
  token: this.config.token
})

// 修改后
this.send({
  type: 'auth',  // 后端期望 'auth' 而不是 'authenticate'
  token: this.config.token
})
```

### 3. JWT Token格式修正
**文件**: `/root/trademe/backend/trading-service/generate_jwt_token.py`
```python
# 修改后的payload格式
payload = {
    "userId": user_id,  # 注意是 userId 而不是 user_id
    "email": email,
    "membershipLevel": membership_level,  # 注意是 membershipLevel
    "type": "access",  # 必须包含 type 字段
    "iat": now,
    "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    "aud": "trademe-app",  # 受众必须是 trademe-app
    "iss": "trademe-user-service",  # 签发者必须是 trademe-user-service
}
```

## 验证结果
✅ WebSocket连接测试通过
✅ 认证成功，User ID: 6
✅ 前端已重新构建

### 4. Nginx WebSocket代理配置
**文件**: `/etc/nginx/sites-available/trademe`
```nginx
# WebSocket support for realtime communication
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # WebSocket timeout settings
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_connect_timeout 120s;
    
    # Disable buffering for WebSocket
    proxy_buffering off;
}
```

### 5. 前端WebSocket URL配置
**文件**: `/root/trademe/frontend/src/components/ai/WebSocketStatus.tsx`
```typescript
// 使用当前origin，通过Nginx代理
const wsBaseUrl = window.location.origin.replace(/^http/, 'ws');
```

## 验证结果
✅ 本地WebSocket连接测试通过
✅ Nginx代理WebSocket测试通过
✅ 认证成功，User ID: 6
✅ 前端已重新构建并部署

## 使用说明
1. 前端现在会正确连接到 `ws://[host]/ws/realtime` 端点（通过Nginx代理）
2. 用户点击"连接"按钮后，WebSocket会自动完成认证
3. 认证成功后，可以进行实时通信
4. 支持生产环境和开发环境自动切换

## 注意事项
- WebSocket连接需要有效的JWT token
- Token必须包含正确的audience和issuer
- 认证消息必须使用 `type: 'auth'` 格式