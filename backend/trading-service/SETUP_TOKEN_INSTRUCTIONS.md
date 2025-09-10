# Claude Setup Token 添加指南

## 重要说明
Setup Token 不是 OAuth 流程，而是直接的 API 密钥。系统已更新为正确处理 Setup Token。

## 如何添加 Setup Token

### 步骤 1: 获取 Setup Token
1. 登录 Claude Console: https://console.anthropic.com/
2. 创建新的 API 密钥
3. 复制生成的密钥（格式: `sk-ant-api03-xxxxx...`）

### 步骤 2: 在系统中添加
1. 点击"生成授权链接"按钮
2. 在"授权码"输入框中直接粘贴您的 API 密钥
   - **重要**: 直接粘贴 API 密钥本身，不是 URL
   - 格式应该是: `sk-ant-api03-xxxxx...`
3. 填写账户名称和其他设置
4. 点击"交换Setup Token"

### 常见问题

#### Q: 为什么显示"403 错误"？
A: 之前的实现尝试进行 OAuth 交换，但 Setup Token 不需要交换。现已修复。

#### Q: 授权码应该填什么？
A: 直接填写您的 Anthropic API 密钥（sk-ant-开头的字符串）

#### Q: 为什么要生成授权链接？
A: 这是为了创建会话 ID 用于安全验证，即使 Setup Token 本身不需要 OAuth 流程。

## 技术细节

Setup Token 的处理流程：
1. 用户提供 API 密钥
2. 系统验证密钥有效性（通过测试 API 调用）
3. 密钥直接存储在 `api_key` 字段
4. 使用时通过 `X-API-Key` header 发送

## 测试账户连接

添加账户后，可以点击"测试连接"按钮验证 Setup Token 是否有效。