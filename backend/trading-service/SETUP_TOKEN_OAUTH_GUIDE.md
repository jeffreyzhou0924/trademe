# Claude Setup Token OAuth 认证指南

## 重要说明
Setup Token 使用完整的 OAuth 2.0 + PKCE 流程，与 claude-relay-service 实现完全一致。
这不是简单的 API Key，而是通过 Claude OAuth 服务器授权获取的访问令牌。

## OAuth 工作流程

### 1. 生成授权链接
点击"生成授权链接"按钮时，系统会：
- 生成 PKCE code_verifier 和 code_challenge
- 创建 state 参数防止 CSRF 攻击
- 生成授权 URL：`https://claude.ai/oauth/authorize`

### 2. 用户授权
1. 复制生成的授权链接
2. 在浏览器中打开链接
3. 登录您的 Claude 账户
4. 授权应用访问（权限：user:inference）
5. 页面会重定向到回调 URL，带有授权码

### 3. 获取授权码
授权成功后，您会被重定向到类似这样的 URL：
```
https://console.anthropic.com/oauth/code/callback?code=XXXXX&state=YYYYY
```

复制完整的 URL 或仅复制 `code` 参数的值。

### 4. 交换访问令牌
1. 将授权码粘贴到"授权码"输入框
2. 填写账户名称和其他设置
3. 点击"交换 Setup Token"

系统会：
- 使用授权码 + code_verifier 向 OAuth 服务器请求
- 获取访问令牌（access_token）
- 将访问令牌安全存储

## 技术细节

### OAuth 配置
```javascript
{
  AUTHORIZE_URL: "https://claude.ai/oauth/authorize",
  TOKEN_URL: "https://console.anthropic.com/v1/oauth/token",
  CLIENT_ID: "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
  REDIRECT_URI: "https://console.anthropic.com/oauth/code/callback",
  SCOPES: "user:inference"
}
```

### PKCE (Proof Key for Code Exchange)
系统使用 PKCE 增强安全性：
1. 生成随机的 code_verifier
2. 计算 code_challenge = SHA256(code_verifier)
3. 授权请求带上 code_challenge
4. Token 交换时验证 code_verifier

### 访问令牌使用
获取的访问令牌通过 Authorization header 使用：
```
Authorization: Bearer <access_token>
```

## 与 API Key 的区别

| 特性 | Setup Token (OAuth) | API Key |
|------|-------------------|---------|
| 获取方式 | OAuth 授权流程 | Claude Console 直接创建 |
| 费用 | 免费（使用账户额度） | 需要单独付费 |
| 权限 | user:inference | 完整 API 权限 |
| 过期时间 | 有过期时间 | 长期有效 |
| 刷新机制 | 不支持刷新 | 无需刷新 |

## 常见问题

### Q: 为什么使用 OAuth 而不是 API Key？
A: OAuth Setup Token 不需要单独付费，使用账户的免费额度。API Key 需要绑定支付方式并按使用量付费。

### Q: 授权码在哪里找？
A: 完成授权后，浏览器会重定向到回调 URL，授权码在 URL 的 `code` 参数中。

### Q: Token 会过期吗？
A: 是的，OAuth 访问令牌有过期时间（通常较长）。过期后需要重新进行授权流程。

### Q: 可以刷新 Token 吗？
A: Setup Token 通常不提供 refresh_token，过期后需要重新授权。

## 故障排查

### 403 错误
确保：
1. 使用的是授权码，不是 API Key
2. 授权码没有过期（10分钟有效期）
3. 授权码只能使用一次

### 401 错误
可能原因：
1. 访问令牌已过期
2. 访问令牌无效
3. 账户被禁用

### 网络错误
检查：
1. 网络连接正常
2. 能访问 claude.ai 和 console.anthropic.com
3. 防火墙没有阻止 HTTPS 请求

## 参考实现
本实现基于 [claude-relay-service](https://github.com/username/claude-relay-service) 的 OAuth Helper，
确保与 Claude 官方 OAuth 流程完全兼容。