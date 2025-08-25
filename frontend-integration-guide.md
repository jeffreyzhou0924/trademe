# 🚀 Trademe 前端集成指南

## 📍 服务器访问地址

**公网地址:** `http://43.167.252.120`

## 🔐 测试账户信息

| 账户类型 | 邮箱 | 密码 | 会员级别 | 说明 |
|---------|------|------|----------|------|
| 管理员 | admin@trademe.com | admin123456 | PROFESSIONAL | 专业版权限 |
| 演示用户 | demo@trademe.com | password123 | PREMIUM | 高级版权限 |
| 测试用户 | test@trademe.com | password123 | BASIC | 基础版权限 |

## 🌐 前端访问页面

### 1. API文档页面
**地址:** http://43.167.252.120/docs
- 完整的API接口文档
- 实时状态监控
- 交互式测试功能

### 2. 登录演示页面
**地址:** http://43.167.252.120/login
- 完整的登录界面演示
- 一键测试登录功能
- API测试中心
- 实时响应展示

### 3. 健康检查
**地址:** http://43.167.252.120/health
- 服务器运行状态
- 数据库连接状态
- Redis连接状态

## 🔌 API 集成示例

### 基础配置
```javascript
const API_BASE_URL = 'http://43.167.252.120';
```

### 1. 用户登录
```javascript
const loginUser = async (email, password) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 保存访问令牌
      localStorage.setItem('access_token', data.data.access_token);
      localStorage.setItem('refresh_token', data.data.refresh_token);
      localStorage.setItem('user_info', JSON.stringify(data.data.user));
      
      return data.data;
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('登录失败:', error);
    throw error;
  }
};

// 使用示例
loginUser('admin@trademe.com', 'admin123456')
  .then(userData => {
    console.log('登录成功:', userData);
    // 跳转到主页面
  })
  .catch(error => {
    console.error('登录失败:', error.message);
  });
```

### 2. 用户注册
```javascript
const registerUser = async (userData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: userData.username,
        email: userData.email,
        password: userData.password,
        confirm_password: userData.confirmPassword
      })
    });
    
    return await response.json();
  } catch (error) {
    console.error('注册失败:', error);
    throw error;
  }
};
```

### 3. 获取用户资料（需要认证）
```javascript
const getUserProfile = async () => {
  try {
    const token = localStorage.getItem('access_token');
    
    if (!token) {
      throw new Error('未登录');
    }
    
    const response = await fetch(`${API_BASE_URL}/api/v1/user/profile`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      return data.data;
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('获取用户资料失败:', error);
    throw error;
  }
};
```

### 4. 获取系统配置
```javascript
const getSystemConfig = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/config/`);
    const data = await response.json();
    
    if (data.success) {
      return data.data;
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('获取系统配置失败:', error);
    throw error;
  }
};
```

### 5. 获取会员套餐
```javascript
const getMembershipPlans = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/membership/plans`);
    const data = await response.json();
    
    if (data.success) {
      return data.data;
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('获取会员套餐失败:', error);
    throw error;
  }
};
```

## 🔄 自动令牌刷新
```javascript
const refreshAccessToken = async () => {
  try {
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (!refreshToken) {
      throw new Error('无刷新令牌');
    }
    
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    
    const data = await response.json();
    
    if (data.success) {
      localStorage.setItem('access_token', data.data.access_token);
      return data.data.access_token;
    } else {
      // 刷新令牌失效，需要重新登录
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_info');
      throw new Error('需要重新登录');
    }
  } catch (error) {
    console.error('令牌刷新失败:', error);
    throw error;
  }
};
```

## 🛡️ 错误处理和拦截器
```javascript
// 通用请求处理函数
const apiRequest = async (url, options = {}) => {
  const token = localStorage.getItem('access_token');
  
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` })
    }
  };
  
  const finalOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...options.headers
    }
  };
  
  try {
    const response = await fetch(`${API_BASE_URL}${url}`, finalOptions);
    const data = await response.json();
    
    // 检查是否是认证错误
    if (response.status === 401 && data.error_code === 'TOKEN_EXPIRED') {
      // 尝试刷新令牌
      const newToken = await refreshAccessToken();
      
      // 重新发起请求
      finalOptions.headers.Authorization = `Bearer ${newToken}`;
      const retryResponse = await fetch(`${API_BASE_URL}${url}`, finalOptions);
      return await retryResponse.json();
    }
    
    return data;
  } catch (error) {
    console.error('API请求失败:', error);
    throw error;
  }
};
```

## 🎯 React Hook 示例
```javascript
import { useState, useEffect } from 'react';

// 登录Hook
const useAuth = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const login = async (email, password) => {
    setLoading(true);
    setError(null);
    
    try {
      const userData = await loginUser(email, password);
      setUser(userData.user);
      return userData;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };
  
  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_info');
    setUser(null);
  };
  
  useEffect(() => {
    // 检查本地存储中的用户信息
    const userInfo = localStorage.getItem('user_info');
    if (userInfo) {
      setUser(JSON.parse(userInfo));
    }
  }, []);
  
  return { user, login, logout, loading, error };
};
```

## 📱 移动端适配

所有API都支持跨域访问，移动端应用可以直接调用：

```javascript
// React Native 示例
const login = async (email, password) => {
  try {
    const response = await fetch('http://43.167.252.120/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });
    
    return await response.json();
  } catch (error) {
    console.error('登录失败:', error);
    throw error;
  }
};
```

## 🚀 快速开始

1. **测试连接**
   ```bash
   curl http://43.167.252.120/health
   ```

2. **测试登录**
   ```bash
   curl -X POST http://43.167.252.120/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@trademe.com","password":"admin123456"}'
   ```

3. **访问登录演示页面**
   - 在浏览器中打开: http://43.167.252.120/login
   - 点击快速登录按钮测试功能

## 📞 技术支持

- **API文档:** http://43.167.252.120/docs
- **登录演示:** http://43.167.252.120/login  
- **服务状态:** http://43.167.252.120/health

所有接口都已配置CORS，前端可以直接调用，无需代理配置！🎉