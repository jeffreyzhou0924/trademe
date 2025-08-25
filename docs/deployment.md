# Trademe 平台部署指南

> **更新时间**: 2025-08-21  
> **部署环境**: 公网云服务器 (43.167.252.120)  
> **架构**: 简化双服务架构 + Nginx反向代理

## 🌍 部署环境说明

### 公网测试环境 (推荐)
- **服务器**: 腾讯云 43.167.252.120 (4核8GB)
- **操作系统**: Ubuntu 22.04 LTS
- **访问地址**: http://43.167.252.120
- **用途**: 测试、演示、集成开发

### 本地开发环境
- **用途**: 本地代码开发和调试
- **要求**: Node.js 20+, Python 3.12+, Redis, SQLite

## 🚀 快速部署 (公网环境)

### 1. 服务器准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础依赖
sudo apt install -y curl wget git vim nginx redis-server sqlite3

# 安装Node.js 20+
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 安装Python 3.12+
sudo apt install -y python3.12 python3.12-pip python3.12-venv

# 配置防火墙
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 3001/tcp
sudo ufw allow 8001/tcp
```

### 2. 克隆项目代码

```bash
cd /root
git clone <YOUR_REPO_URL> trademe
cd trademe
```

### 3. 部署用户服务 (Node.js)

```bash
cd /root/trademe/backend/user-service

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件配置数据库路径等

# 构建项目
npm run build

# 使用ts-node启动 (推荐)
npx ts-node -r tsconfig-paths/register src/app.ts &

# 或使用编译后的代码启动
# npm start &
```

### 4. 部署交易服务 (Python)

```bash
cd /root/trademe/backend/trading-service

# 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件配置Claude API等

# 启动服务
PYTHONPATH=/root/trademe/backend/trading-service uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload &
```

### 5. 部署前端服务 (React)

```bash
cd /root/trademe/frontend

# 安装依赖
npm install

# 公网环境启动
npm run dev:public &

# 本地环境启动
# npm run dev:local &
```

### 6. 配置Nginx反向代理

```bash
# 使用已有配置
sudo cp /etc/nginx/sites-enabled/trademe /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/trademe /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl reload nginx
```

## 📋 环境配置详解

### 用户服务环境变量 (.env)

```bash
# 数据库配置
DATABASE_URL="file:/root/trademe/data/trademe.db"

# JWT配置
JWT_SECRET="your-super-secret-jwt-key-here"
JWT_SECRET_KEY="your-super-secret-jwt-key-here"  # 兼容性配置
JWT_ALGORITHM="HS256"
JWT_EXPIRES_IN="24h"

# Redis配置
REDIS_URL="redis://localhost:6379"

# 应用配置
NODE_ENV="development"
PORT=3001
HOST="0.0.0.0"

# 邮件配置
EMAIL_HOST="smtp.qq.com"
EMAIL_PORT=587
EMAIL_USER="your-email@qq.com"
EMAIL_PASS="your-email-password"
```

### 交易服务环境变量 (.env)

```bash
# 数据库配置
DATABASE_URL="sqlite+aiosqlite:////root/trademe/data/trademe.db"

# JWT配置 (与用户服务保持一致)
JWT_SECRET="your-super-secret-jwt-key-here"
JWT_SECRET_KEY="your-super-secret-jwt-key-here"
JWT_ALGORITHM="HS256"

# Claude API配置
ANTHROPIC_API_KEY="your-claude-api-key"
CLAUDE_API_ENDPOINT="https://claude.cloudcdn7.com/api"

# Redis配置
REDIS_URL="redis://localhost:6379"

# 应用配置
ENVIRONMENT="development"
HOST="0.0.0.0"
PORT=8001
```

### 前端环境配置

#### 公网测试环境 (.env.public)
```bash
VITE_PUBLIC_TEST=true
VITE_API_BASE_URL=http://43.167.252.120/api/v1
VITE_WS_BASE_URL=ws://43.167.252.120/ws
VITE_APP_ENV=public-test
VITE_APP_TITLE=Trademe - 公网测试环境
```

#### 本地开发环境 (.env.local)
```bash
VITE_PUBLIC_TEST=false
VITE_API_BASE_URL=http://localhost:3001/api/v1
VITE_WS_BASE_URL=ws://localhost:8001/ws
VITE_APP_ENV=development
VITE_APP_TITLE=Trademe - 本地开发环境
```

## 🔧 服务管理

### 启动脚本

创建 `/root/trademe/start-services.sh`:

```bash
#!/bin/bash

# 启动用户服务
cd /root/trademe/backend/user-service
npx ts-node -r tsconfig-paths/register src/app.ts &
USER_SERVICE_PID=$!

# 启动交易服务
cd /root/trademe/backend/trading-service
source venv/bin/activate
PYTHONPATH=/root/trademe/backend/trading-service uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload &
TRADING_SERVICE_PID=$!

# 启动前端服务
cd /root/trademe/frontend
npm run dev:public &
FRONTEND_PID=$!

echo "Services started:"
echo "User Service PID: $USER_SERVICE_PID"
echo "Trading Service PID: $TRADING_SERVICE_PID"
echo "Frontend PID: $FRONTEND_PID"

# 保存PID到文件
echo $USER_SERVICE_PID > /tmp/user-service.pid
echo $TRADING_SERVICE_PID > /tmp/trading-service.pid
echo $FRONTEND_PID > /tmp/frontend.pid
```

### 停止脚本

创建 `/root/trademe/stop-services.sh`:

```bash
#!/bin/bash

# 停止服务
if [ -f /tmp/user-service.pid ]; then
    kill $(cat /tmp/user-service.pid)
    rm /tmp/user-service.pid
fi

if [ -f /tmp/trading-service.pid ]; then
    kill $(cat /tmp/trading-service.pid)
    rm /tmp/trading-service.pid
fi

if [ -f /tmp/frontend.pid ]; then
    kill $(cat /tmp/frontend.pid)
    rm /tmp/frontend.pid
fi

echo "All services stopped"
```

### 设置可执行权限

```bash
chmod +x /root/trademe/start-services.sh
chmod +x /root/trademe/stop-services.sh
```

## 🔍 健康检查

### 服务状态检查

```bash
# 检查所有服务
curl http://43.167.252.120/health
curl http://43.167.252.120:3001/health
curl http://43.167.252.120:8001/health

# 检查前端
curl http://43.167.252.120:3000
curl http://43.167.252.120  # 通过Nginx
```

### 端口检查

```bash
# 检查服务端口
netstat -tlnp | grep -E "(3000|3001|8001|80)"

# 检查进程
ps aux | grep -E "(node|python|nginx)"
```

## 📊 监控和日志

### 日志位置

```bash
# 用户服务日志
tail -f /root/trademe/backend/user-service/logs/combined.log

# 交易服务日志
tail -f /root/trademe/backend/trading-service/logs/trading-service.log

# Nginx日志
tail -f /var/log/nginx/trademe_access.log
tail -f /var/log/nginx/trademe_error.log
```

### 系统监控

```bash
# 内存使用
free -h

# 磁盘使用
df -h

# CPU使用
top

# 网络连接
ss -tulpn
```

## 🛡️ 安全配置

### 防火墙配置

```bash
# 基础安全配置
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 允许必要端口
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 3000/tcp # 前端 (可选)
sudo ufw allow 3001/tcp # 用户服务 (可选)
sudo ufw allow 8001/tcp # 交易服务 (可选)
```

### SSL/HTTPS配置 (可选)

```bash
# 安装Certbot
sudo apt install snapd
sudo snap install --classic certbot

# 获取SSL证书 (需要域名)
# sudo certbot --nginx -d yourdomain.com

# 自动续期
# sudo crontab -e
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🚨 故障排除

### 常见问题

1. **端口占用**
```bash
# 查找占用端口的进程
sudo lsof -i :3001
sudo lsof -i :8001

# 杀死进程
sudo kill -9 <PID>
```

2. **权限问题**
```bash
# 确保文件权限正确
sudo chown -R root:root /root/trademe
chmod +x /root/trademe/*.sh
```

3. **依赖问题**
```bash
# 重新安装Node.js依赖
cd /root/trademe/backend/user-service
rm -rf node_modules package-lock.json
npm install

# 重新安装Python依赖
cd /root/trademe/backend/trading-service
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

4. **数据库问题**
```bash
# 检查SQLite数据库
sqlite3 /root/trademe/data/trademe.db ".tables"
sqlite3 /root/trademe/data/trademe.db ".schema users"
```

### 性能优化

1. **数据库优化**
```bash
# 定期VACUUM优化
sqlite3 /root/trademe/data/trademe.db "VACUUM;"

# 分析查询性能
sqlite3 /root/trademe/data/trademe.db "EXPLAIN QUERY PLAN SELECT * FROM users;"
```

2. **Redis优化**
```bash
# 检查Redis状态
redis-cli ping
redis-cli info memory
```

## 📝 部署检查清单

- [ ] 服务器环境准备完成
- [ ] 所有依赖软件安装
- [ ] 项目代码克隆到服务器
- [ ] 环境变量配置正确
- [ ] 数据库文件存在且可访问
- [ ] 用户服务启动正常 (端口3001)
- [ ] 交易服务启动正常 (端口8001)
- [ ] 前端服务启动正常 (端口3000)
- [ ] Nginx反向代理配置正确
- [ ] 防火墙规则配置完成
- [ ] 健康检查接口正常响应
- [ ] 前端页面可以正常访问
- [ ] API接口可以正常调用
- [ ] WebSocket连接正常
- [ ] 测试账户可以正常登录

## 🎯 下一步

部署完成后，建议进行以下操作：

1. **功能测试**: 使用测试账户验证各项功能
2. **性能测试**: 进行压力测试确保系统稳定性
3. **监控配置**: 设置系统监控和告警
4. **备份策略**: 配置数据库定期备份
5. **CI/CD**: 配置自动化部署流水线

---

**💡 提示**: 如遇到问题，请查看各服务的日志文件进行诊断，或参考故障排除章节。