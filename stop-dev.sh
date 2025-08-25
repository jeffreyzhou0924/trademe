#!/bin/bash

# Trademe 开发环境停止脚本
# 创建时间: 2025-08-21
# 用途: 一键停止所有开发服务

set -e

echo "🛑 停止 Trademe 开发环境..."

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/root/trademe"
cd "$PROJECT_ROOT"

# 从PID文件停止服务
if [[ -f "logs/trading-service.pid" ]]; then
    TRADING_PID=$(cat logs/trading-service.pid)
    echo -e "${YELLOW}🔹 停止交易服务 (PID: $TRADING_PID)${NC}"
    kill -15 $TRADING_PID 2>/dev/null || true
    rm -f logs/trading-service.pid
fi

if [[ -f "logs/user-service.pid" ]]; then
    USER_PID=$(cat logs/user-service.pid)
    echo -e "${YELLOW}🔹 停止用户服务 (PID: $USER_PID)${NC}"
    kill -15 $USER_PID 2>/dev/null || true
    rm -f logs/user-service.pid
fi

if [[ -f "logs/frontend.pid" ]]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    echo -e "${YELLOW}🔹 停止前端服务 (PID: $FRONTEND_PID)${NC}"
    kill -15 $FRONTEND_PID 2>/dev/null || true
    rm -f logs/frontend.pid
fi

# 强制清理端口占用
echo -e "${YELLOW}🧹 清理端口占用...${NC}"
lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3001 | xargs -r kill -9 2>/dev/null || true
lsof -ti:8001 | xargs -r kill -9 2>/dev/null || true

# 清理相关进程
pkill -f "vite.*3000" 2>/dev/null || true
pkill -f "uvicorn.*8001" 2>/dev/null || true
pkill -f "ts-node.*src/app.ts" 2>/dev/null || true
pkill -f "nodemon.*src/app.ts" 2>/dev/null || true

sleep 2

# 验证停止
echo -e "${GREEN}🔍 验证服务停止状态...${NC}"
if ! curl -s http://localhost:3000 > /dev/null 2>&1 && \
   ! curl -s http://localhost:3001 > /dev/null 2>&1 && \
   ! curl -s http://localhost:8001 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 所有服务已成功停止${NC}"
else
    echo -e "${YELLOW}⚠️  某些服务可能仍在运行，请手动检查${NC}"
fi

echo -e "${GREEN}🎯 开发环境已停止${NC}"