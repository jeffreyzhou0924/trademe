#!/bin/bash

# Trademe User Service 生产环境启动脚本

set -e

echo "🚀 启动 Trademe 用户服务..."

# 检查必要的服务
echo "📋 检查系统服务..."

#（已弃用）MySQL 检查已移除：统一使用 SQLite

# 检查Redis  
if ! systemctl is-active --quiet redis-server; then
    echo "🔄 启动 Redis..."
    sudo systemctl start redis-server
fi

# 检查Nginx
if ! systemctl is-active --quiet nginx; then
    echo "🔄 启动 Nginx..."
    sudo systemctl start nginx
fi

cd /root/trademe/backend/user-service

# 安装依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm ci --production
fi

# 生成Prisma客户端
echo "🔧 生成 Prisma 客户端..."
npx prisma generate

# 构建应用
echo "🔨 构建应用..."
npm run build

# 停止现有的PM2进程（如果存在）
echo "🛑 停止现有进程..."
pm2 delete trademe-user-service 2>/dev/null || true

# 使用PM2启动服务
echo "▶️  启动用户服务..."
pm2 start ecosystem.config.js --env production

# 保存PM2进程列表
pm2 save

# 设置开机自启动
pm2 startup || true

echo "✅ 用户服务已启动!"
echo ""
echo "📊 服务状态:"
pm2 status

echo ""
echo "🌐 访问地址:"
echo "  - 公网地址: http://43.167.252.120"
echo "  - API文档: http://43.167.252.120/docs"
echo "  - 健康检查: http://43.167.252.120/health"
echo ""
echo "📝 查看日志:"
echo "  pm2 logs trademe-user-service"
echo ""
echo "🔧 管理命令:"
echo "  pm2 restart trademe-user-service"
echo "  pm2 stop trademe-user-service"
echo "  pm2 reload trademe-user-service"
