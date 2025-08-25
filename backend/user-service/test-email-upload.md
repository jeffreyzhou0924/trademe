# 邮件服务和文件上传功能测试指南

## 环境准备

### 1. 安装依赖
```bash
cd /root/trademe/backend/user-service
npm install
```

### 2. 配置环境变量
复制并编辑环境变量文件：
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下必要参数：

**邮件服务配置（Gmail示例）**：
```env
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587" 
SMTP_SECURE="false"
SMTP_USER="your-gmail@gmail.com"
SMTP_PASS="your-app-password"  # 使用应用专用密码，不是账户密码
EMAIL_FROM="Trademe <noreply@trademe.com>"
```

**文件上传配置**：
```env
UPLOAD_DIR="./uploads"
UPLOAD_BASE_URL="http://localhost:3001/uploads"
```

### 3. 启动服务
```bash
npm run dev
```

## 功能测试

### 1. 邮件服务测试

#### 测试用户注册（会发送验证码邮件）
```bash
curl -X POST http://localhost:3001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "your-test-email@gmail.com",
    "password": "Password123!",
    "confirm_password": "Password123!"
  }'
```

#### 测试发送验证码邮件
```bash
curl -X POST http://localhost:3001/api/v1/auth/send-verification \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-test-email@gmail.com",
    "type": "register"
  }'
```

#### 测试密码重置（会发送重置成功通知邮件）
```bash
# 1. 先发送重置验证码
curl -X POST http://localhost:3001/api/v1/auth/send-verification \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-test-email@gmail.com",
    "type": "reset_password"
  }'

# 2. 使用验证码重置密码
curl -X POST http://localhost:3001/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-test-email@gmail.com",
    "code": "123456",
    "new_password": "NewPassword123!",
    "confirm_password": "NewPassword123!"
  }'
```

### 2. 文件上传测试

#### 测试头像上传

**步骤1：先登录获取Token**
```bash
curl -X POST http://localhost:3001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-test-email@gmail.com",
    "password": "Password123!"
  }'
```

**步骤2：使用Token上传头像**
```bash
# 替换 YOUR_ACCESS_TOKEN 为实际的token
curl -X POST http://localhost:3001/api/v1/user/upload-avatar \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "avatar=@/path/to/your/test-image.jpg"
```

### 3. 健康检查测试

```bash
curl http://localhost:3001/health
```

期望响应包含：
```json
{
  "status": "ok",
  "services": {
    "database": "healthy",
    "redis": "healthy", 
    "upload": "healthy",
    "email": "healthy"
  }
}
```

## 测试图片文件示例

可以创建一个测试图片：
```bash
# 创建一个简单的测试图片（需要安装ImageMagick）
convert -size 100x100 xc:red test-avatar.png

# 或者下载一个测试图片
wget https://via.placeholder.com/150 -O test-avatar.png
```

## 预期结果

### 邮件测试成功标志：
1. **注册邮件**：收到包含6位验证码的注册邮件
2. **验证成功**：收到欢迎邮件
3. **密码重置**：收到密码重置成功通知邮件

### 文件上传测试成功标志：
1. **上传成功**：返回文件URL和信息
2. **文件存在**：可以通过URL访问上传的图片
3. **数据库更新**：用户头像URL已更新

### 错误测试：
1. **无效图片格式**：上传.txt文件应该返回错误
2. **文件过大**：上传超过5MB的图片应该返回错误
3. **无效邮箱**：使用错误邮箱格式应该返回错误

## 故障排除

### 邮件发送失败：
1. 检查SMTP配置是否正确
2. 确认Gmail应用专用密码设置
3. 查看服务器日志：`tail -f logs/combined.log`

### 文件上传失败：
1. 检查uploads目录是否存在且有写入权限
2. 确认文件大小和格式符合要求
3. 检查Token是否有效

### 服务启动失败：
1. 检查MySQL和Redis服务是否运行
2. 确认环境变量配置正确
3. 检查端口3001是否被占用