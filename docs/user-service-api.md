# 用户服务 API 接口文档

## 服务概述

用户服务负责处理用户认证、权限管理、用户信息管理等核心功能，是整个平台的基础服务。

- **服务名称**: user-service
- **端口**: 3001
- **技术栈**: Node.js + TypeScript + Express + Prisma
- **数据库**: MySQL + Redis

## 通用信息

### 基础URL
```
开发环境: http://localhost:3001/api/v1
生产环境: https://api.trademe.com/v1
```

### 通用请求头
```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer {jwt_token}  # 需要认证的接口
```

### 统一响应格式
```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {},
  "timestamp": "2024-05-20T10:30:00Z",
  "request_id": "uuid-string"
}
```

### 错误码定义
```json
{
  "200": "请求成功",
  "400": "请求参数错误",
  "401": "未授权访问",
  "403": "权限不足",
  "404": "资源不存在",
  "409": "资源冲突",
  "422": "请求格式正确但数据无效",
  "429": "请求频率过高",
  "500": "服务器内部错误"
}
```

## 认证相关接口

### 1. 用户注册

**接口地址**: `POST /auth/register`

**接口描述**: 用户邮箱注册账号

**请求参数**:
```json
{
  "username": "string",      // 用户名 (3-20字符，字母数字下划线)
  "email": "string",         // 邮箱地址
  "password": "string",      // 密码 (8-50字符，包含字母和数字)
  "confirm_password": "string" // 确认密码
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "注册成功，请查收邮箱验证码",
  "data": {
    "user_id": 12345,
    "email": "user@example.com",
    "verification_required": true
  }
}
```

**错误响应**:
```json
{
  "success": false,
  "code": 409,
  "message": "邮箱已被注册",
  "errors": [
    {
      "field": "email",
      "code": "DUPLICATE_EMAIL",
      "message": "该邮箱已被注册"
    }
  ]
}
```

### 2. 邮箱验证码发送

**接口地址**: `POST /auth/send-verification`

**接口描述**: 发送邮箱验证码

**请求参数**:
```json
{
  "email": "string",         // 邮箱地址
  "type": "register|login|reset_password"  // 验证码类型
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "验证码已发送",
  "data": {
    "expires_at": "2024-05-20T10:35:00Z",
    "resend_after": 60  // 秒数
  }
}
```

### 3. 邮箱验证

**接口地址**: `POST /auth/verify-email`

**接口描述**: 验证邮箱验证码

**请求参数**:
```json
{
  "email": "string",
  "code": "string"      // 6位验证码
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "邮箱验证成功",
  "data": {
    "verified": true
  }
}
```

### 4. 邮箱登录

**接口地址**: `POST /auth/login`

**接口描述**: 用户邮箱登录

**请求参数**:
```json
{
  "email": "string",
  "password": "string"
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 86400,  // 秒数
    "user": {
      "id": 12345,
      "username": "testuser",
      "email": "user@example.com",
      "avatar_url": "https://example.com/avatar.jpg",
      "membership_level": "premium",
      "membership_expires_at": "2024-08-20T00:00:00Z",
      "created_at": "2024-01-20T10:00:00Z"
    }
  }
}
```

### 5. Google OAuth登录

**接口地址**: `POST /auth/google`

**接口描述**: Google账号登录

**请求参数**:
```json
{
  "google_token": "string"   // Google OAuth返回的id_token
}
```

**响应示例**: 与邮箱登录相同

### 6. 刷新令牌

**接口地址**: `POST /auth/refresh`

**接口描述**: 使用刷新令牌获取新的访问令牌

**请求参数**:
```json
{
  "refresh_token": "string"
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "令牌刷新成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 86400
  }
}
```

### 7. 用户登出

**接口地址**: `POST /auth/logout`

**接口描述**: 用户登出，使令牌失效

**请求头**: `Authorization: Bearer {access_token}`

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "登出成功"
}
```

### 8. 密码重置

**接口地址**: `POST /auth/reset-password`

**接口描述**: 重置用户密码

**请求参数**:
```json
{
  "email": "string",
  "code": "string",         // 邮箱验证码
  "new_password": "string",
  "confirm_password": "string"
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "密码重置成功"
}
```

## 用户信息接口

### 1. 获取用户信息

**接口地址**: `GET /user/profile`

**接口描述**: 获取当前登录用户的详细信息

**请求头**: `Authorization: Bearer {access_token}`

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "获取成功",
  "data": {
    "id": 12345,
    "username": "testuser",
    "email": "user@example.com",
    "phone": "+8613812345678",
    "avatar_url": "https://example.com/avatar.jpg",
    "membership_level": "premium",
    "membership_expires_at": "2024-08-20T00:00:00Z",
    "email_verified": true,
    "is_active": true,
    "last_login_at": "2024-05-20T09:30:00Z",
    "created_at": "2024-01-20T10:00:00Z",
    "updated_at": "2024-05-20T08:00:00Z",
    "preferences": {
      "language": "zh-CN",
      "timezone": "Asia/Shanghai",
      "theme": "light"
    }
  }
}
```

### 2. 更新用户信息

**接口地址**: `PUT /user/profile`

**接口描述**: 更新用户基本信息

**请求头**: `Authorization: Bearer {access_token}`

**请求参数**:
```json
{
  "username": "string",      // 可选
  "phone": "string",         // 可选
  "avatar_url": "string",    // 可选
  "preferences": {           // 可选
    "language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "theme": "light"
  }
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "更新成功",
  "data": {
    "id": 12345,
    "username": "newusername",
    // ... 其他用户信息
  }
}
```

### 3. 修改密码

**接口地址**: `PUT /user/change-password`

**接口描述**: 用户修改密码

**请求头**: `Authorization: Bearer {access_token}`

**请求参数**:
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_password": "string"
}
```

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "密码修改成功"
}
```

### 4. 绑定/解绑Google账号

**接口地址**: `POST /user/bind-google`

**接口描述**: 绑定Google账号

**请求头**: `Authorization: Bearer {access_token}`

**请求参数**:
```json
{
  "google_token": "string"
}
```

**接口地址**: `DELETE /user/unbind-google`

**接口描述**: 解绑Google账号

## 会员系统接口

### 1. 获取会员信息

**接口地址**: `GET /user/membership`

**接口描述**: 获取用户会员信息和权益

**请求头**: `Authorization: Bearer {access_token}`

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "获取成功",
  "data": {
    "level": "premium",
    "expires_at": "2024-08-20T00:00:00Z",
    "days_remaining": 92,
    "features": {
      "api_keys_limit": -1,  // -1表示无限制
      "ai_queries_daily": 30,
      "ai_strategy_optimization_daily": 5,
      "advanced_charts": true,
      "priority_support": true
    },
    "usage": {
      "api_keys_count": 3,
      "ai_queries_today": 12,
      "ai_optimizations_today": 2
    }
  }
}
```

### 2. 获取会员套餐列表

**接口地址**: `GET /membership/plans`

**接口描述**: 获取所有可用的会员套餐

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "获取成功",
  "data": [
    {
      "id": 1,
      "name": "基础版",
      "level": "basic",
      "duration_months": 0,
      "price": "0.00",
      "features": {
        "api_keys_limit": 5,
        "ai_queries_daily": 2,
        "ai_strategy_optimization_daily": 0,
        "advanced_charts": false,
        "priority_support": false
      },
      "is_active": true
    },
    {
      "id": 2,
      "name": "高级版(月付)",
      "level": "premium",
      "duration_months": 1,
      "price": "19.99",
      "original_price": "19.99",
      "discount": 0,
      "features": {
        "api_keys_limit": -1,
        "ai_queries_daily": 30,
        "ai_strategy_optimization_daily": 5,
        "advanced_charts": true,
        "priority_support": true
      },
      "is_active": true,
      "popular": false
    },
    {
      "id": 3,
      "name": "高级版(季付)",
      "level": "premium",
      "duration_months": 3,
      "price": "53.99",
      "original_price": "59.97",
      "discount": 10,
      "features": {
        "api_keys_limit": -1,
        "ai_queries_daily": 30,
        "ai_strategy_optimization_daily": 5,
        "advanced_charts": true,
        "priority_support": true
      },
      "is_active": true,
      "popular": true
    }
  ]
}
```

### 3. 使用量统计

**接口地址**: `GET /user/usage-stats`

**接口描述**: 获取用户功能使用统计

**请求头**: `Authorization: Bearer {access_token}`

**查询参数**:
- `period`: `day|week|month` (默认: day)

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "获取成功",
  "data": {
    "period": "day",
    "date": "2024-05-20",
    "stats": {
      "ai_queries": {
        "used": 12,
        "limit": 30,
        "remaining": 18
      },
      "ai_optimizations": {
        "used": 2,
        "limit": 5,
        "remaining": 3
      },
      "api_requests": 1543,
      "strategies_created": 2,
      "backtests_run": 5
    },
    "weekly_trend": [
      {"date": "2024-05-14", "ai_queries": 8},
      {"date": "2024-05-15", "ai_queries": 15},
      {"date": "2024-05-16", "ai_queries": 22},
      {"date": "2024-05-17", "ai_queries": 18},
      {"date": "2024-05-18", "ai_queries": 25},
      {"date": "2024-05-19", "ai_queries": 20},
      {"date": "2024-05-20", "ai_queries": 12}
    ]
  }
}
```

## 系统配置接口

### 1. 获取系统配置

**接口地址**: `GET /config`

**接口描述**: 获取系统公共配置信息

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "获取成功",
  "data": {
    "app": {
      "name": "Trademe",
      "version": "1.0.0",
      "description": "数字货币策略交易平台"
    },
    "features": {
      "google_oauth_enabled": true,
      "email_verification_required": true,
      "maintenance_mode": false
    },
    "limits": {
      "file_upload_max_size": 5242880,  // 5MB
      "api_rate_limit": 100  // 每分钟
    },
    "supported_languages": ["zh-CN", "en-US"],
    "supported_timezones": [
      "Asia/Shanghai",
      "Asia/Hong_Kong",
      "UTC"
    ]
  }
}
```

## 文件上传接口

### 1. 上传头像

**接口地址**: `POST /user/upload-avatar`

**接口描述**: 上传用户头像

**请求头**: 
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**请求参数**:
- `file`: 图片文件 (支持jpg, png, gif, 最大5MB)

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "上传成功",
  "data": {
    "url": "https://cdn.trademe.com/avatars/12345/avatar.jpg",
    "size": 1024000,
    "mime_type": "image/jpeg"
  }
}
```

## 管理员接口

### 1. 获取用户列表 (管理员)

**接口地址**: `GET /admin/users`

**接口描述**: 获取用户列表 (需要管理员权限)

**请求头**: `Authorization: Bearer {admin_access_token}`

**查询参数**:
- `page`: 页码 (默认: 1)
- `limit`: 每页数量 (默认: 20, 最大: 100)
- `search`: 搜索关键字 (用户名或邮箱)
- `membership_level`: 会员等级筛选
- `is_active`: 状态筛选

**响应示例**:
```json
{
  "success": true,
  "code": 200,
  "message": "获取成功",
  "data": {
    "users": [
      {
        "id": 12345,
        "username": "testuser",
        "email": "user@example.com",
        "membership_level": "premium",
        "is_active": true,
        "last_login_at": "2024-05-20T09:30:00Z",
        "created_at": "2024-01-20T10:00:00Z"
      }
    ],
    "pagination": {
      "current_page": 1,
      "per_page": 20,
      "total": 150,
      "total_pages": 8,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

## 错误处理示例

### 参数验证错误
```json
{
  "success": false,
  "code": 422,
  "message": "请求参数验证失败",
  "errors": [
    {
      "field": "email",
      "code": "INVALID_EMAIL",
      "message": "邮箱格式不正确"
    },
    {
      "field": "password",
      "code": "PASSWORD_TOO_SHORT",
      "message": "密码长度至少8位"
    }
  ]
}
```

### 认证错误
```json
{
  "success": false,
  "code": 401,
  "message": "访问令牌无效或已过期",
  "error_code": "INVALID_TOKEN"
}
```

### 权限错误
```json
{
  "success": false,
  "code": 403,
  "message": "权限不足，需要高级会员权限",
  "error_code": "INSUFFICIENT_PERMISSION"
}
```

### 限频错误
```json
{
  "success": false,
  "code": 429,
  "message": "请求过于频繁，请稍后再试",
  "retry_after": 60,  // 秒数
  "error_code": "RATE_LIMIT_EXCEEDED"
}
```

## 接口安全说明

### 认证机制
- 使用JWT (JSON Web Token) 进行用户认证
- Access Token 有效期: 24小时
- Refresh Token 有效期: 30天
- 支持令牌刷新机制

### 权限控制
- 基于会员等级的功能权限控制
- API调用频率限制
- 敏感操作需要额外验证

### 数据安全
- 密码使用bcrypt加密存储
- API密钥使用AES256加密
- 敏感数据传输HTTPS加密
- 请求参数严格验证

### 日志记录
- 记录所有认证相关操作
- 记录敏感操作日志
- 异常访问监控告警