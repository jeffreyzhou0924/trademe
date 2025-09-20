# ⚡ Trademe 快速开始指南

## 🎯 立即体验

### 1. 在线演示页面
直接在浏览器中打开以下链接：

- **🔐 登录演示页面:** http://43.167.252.120/login
- **📚 API文档页面:** http://43.167.252.120/docs
- **❤️ 健康检查:** http://43.167.252.120/health

### 2. 测试账户 (开箱即用)

| 用户类型 | 邮箱 | 密码 | 会员等级 |
|---------|------|------|----------|
| 🔧 管理员 | admin@trademe.com | admin123456 | PROFESSIONAL |
| 👨‍💼 演示用户 | demo@trademe.com | password123 | PREMIUM |
| 🧪 测试用户 | test@trademe.com | password123 | BASIC |

## 🚀 前端开发者 - 5分钟接入

### Step 1: 基础配置
```javascript
const API_BASE_URL = 'http://43.167.252.120';
```

### Step 2: 用户登录
```javascript
const loginUser = async (email, password) => {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  return response.json();
};

// 使用测试账户登录
loginUser('admin@trademe.com', 'admin123456')
  .then(data => console.log('登录成功:', data))
  .catch(err => console.log('登录失败:', err));
```

### Step 3: 获取用户资料
```javascript
const getUserProfile = async (token) => {
  const response = await fetch(`${API_BASE_URL}/api/v1/user/profile`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return response.json();
};
```

## 🔧 后端开发者 - 服务管理

### 开发模式
```bash
cd /root/trademe/backend/user-service
npm run dev
```

### 生产模式
```bash
/root/trademe/start-production.sh
```

### 常用命令
```bash
# 查看服务状态
pm2 status

# 查看日志
pm2 logs trademe-user-service

# 重启服务
pm2 restart trademe-user-service

# 数据库访问（SQLite）
sqlite3 /root/trademe/data/trademe.db
```

## 📱 移动端开发者

所有API支持CORS，可直接调用：

```javascript
// React Native 示例
const login = async (email, password) => {
  try {
    const response = await fetch('http://43.167.252.120/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return await response.json();
  } catch (error) {
    console.error('登录失败:', error);
    throw error;
  }
};
```

## 📊 核心API端点

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/login` | 用户登录 | ❌ |
| POST | `/api/v1/auth/register` | 用户注册 | ❌ |
| GET | `/api/v1/user/profile` | 用户资料 | ✅ |
| GET | `/api/v1/membership/plans` | 会员套餐 | ❌ |
| GET | `/api/v1/config/` | 系统配置 | ❌ |

## 🛠️ 故障排除

### 问题1: API连接失败
**解决方案:** 检查服务器状态
```bash
curl http://43.167.252.120/health
```

### 问题2: 登录失败
**检查项:**
- 使用正确的测试账户
- 邮箱和密码格式正确
- 网络连接正常

### 问题3: 认证错误  
**解决方案:** 检查JWT令牌
```javascript
// 检查令牌是否存在和有效
const token = localStorage.getItem('access_token');
console.log('当前令牌:', token);
```

## 📞 获取帮助

### 在线资源
- **API测试:** http://43.167.252.120/login (点击测试按钮)
- **完整文档:** `/root/trademe/PROJECT-SUMMARY.md`
- **集成指南:** `/root/trademe/frontend-integration-guide.md`

### 服务器日志
```bash
# 查看实时日志
tail -f /root/trademe/logs/user-service.log

# 查看错误日志  
tail -f /root/trademe/logs/user-service-error.log
```

---

🎉 **60秒内即可开始开发！** 所有服务已就绪，测试账户可立即使用！
