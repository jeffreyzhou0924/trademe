#!/bin/bash

# Trademe 开发环境启动脚本 (公网热更新版本)
# 创建时间: 2025-08-21
# 更新时间: 2025-08-23 (增加K线数据服务)
# 用途: 一键启动完整开发环境，支持公网IP热更新调试
# 公网地址: http://43.167.252.120
#
# 服务架构:
# - 交易服务 (FastAPI): 端口 8001, Python + uvicorn + 热重载
# - 用户服务 (Node.js): 端口 3001, TypeScript + ts-node + 热重载  
# - 前端界面 (React): 端口 3000, Vite + HMR + 热更新
# - K线数据 (Python): 端口 8002, HTTP Server + CCXT + OKX真实数据
# - Nginx代理: 端口 80, 统一入口 + 反向代理 + CORS配置

set -e

echo "🚀 启动 Trademe 开发环境 (公网热更新版本)..."

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/root/trademe"
cd "$PROJECT_ROOT"

# 系统信息
PUBLIC_IP="43.167.252.120"
NGINX_CONFIG="/etc/nginx/sites-available/trademe.one"

echo -e "${BLUE}🌐 开发环境配置信息:${NC}"
echo -e "${BLUE}  📍 公网IP: ${PUBLIC_IP}${NC}"
echo -e "${BLUE}  🏠 项目路径: ${PROJECT_ROOT}${NC}"
echo -e "${BLUE}  🔧 Nginx配置: ${NGINX_CONFIG}${NC}"
echo ""

# 清理可能的端口占用
echo -e "${YELLOW}🧹 清理端口占用...${NC}"
lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3001 | xargs -r kill -9 2>/dev/null || true
lsof -ti:8001 | xargs -r kill -9 2>/dev/null || true
lsof -ti:8002 | xargs -r kill -9 2>/dev/null || true
sleep 2

# 创建日志目录
mkdir -p logs

# 验证Nginx配置
echo -e "${YELLOW}🔍 验证Nginx配置...${NC}"
if nginx -t 2>/dev/null; then
    echo -e "${GREEN}✅ Nginx配置正常${NC}"
else
    echo -e "${RED}❌ Nginx配置有误，请检查${NC}"
    nginx -t
    exit 1
fi

# 1. 启动交易服务 (Python FastAPI) - 端口 8001
echo -e "${GREEN}📊 启动交易服务 (FastAPI)...${NC}"
cd "$PROJECT_ROOT/backend/trading-service"
PYTHONPATH="$PROJECT_ROOT/backend/trading-service" \
nohup uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-config=logging.yaml \
> "$PROJECT_ROOT/logs/trading-service.log" 2>&1 &
TRADING_PID=$!
echo "交易服务 PID: $TRADING_PID"

# 等待交易服务启动
echo "等待交易服务启动..."
sleep 5
if curl -s http://localhost:8001/health > /dev/null; then
    echo -e "${GREEN}✅ 交易服务启动成功 (端口 8001)${NC}"
else
    echo -e "${RED}❌ 交易服务启动失败${NC}"
    tail -20 "$PROJECT_ROOT/logs/trading-service.log"
fi

# 2. 启动用户服务 (Node.js) - 端口 3001
echo -e "${GREEN}👤 启动用户服务 (Node.js)...${NC}"
cd "$PROJECT_ROOT/backend/user-service"
nohup npm run dev > "$PROJECT_ROOT/logs/user-service.log" 2>&1 &
USER_PID=$!
echo "用户服务 PID: $USER_PID"

# 等待用户服务启动
echo "等待用户服务启动..."
sleep 5
if curl -s http://localhost:3001/health > /dev/null; then
    echo -e "${GREEN}✅ 用户服务启动成功 (端口 3001)${NC}"
else
    echo -e "${RED}❌ 用户服务启动失败${NC}"
    tail -20 "$PROJECT_ROOT/logs/user-service.log"
fi

# 3. 启动前端服务 (React + Vite) - 端口 3000 (支持热更新)
echo -e "${GREEN}🌐 启动前端服务 (React + Vite + HMR)...${NC}"
cd "$PROJECT_ROOT/frontend"
echo -e "${BLUE}📝 前端配置信息:${NC}"
echo -e "${BLUE}  🔄 热更新: 启用 (HMR + Fast Refresh)${NC}"
echo -e "${BLUE}  🌐 网络绑定: 0.0.0.0:3000 (IPv4)${NC}"
echo -e "${BLUE}  🔗 代理配置: Nginx -> 127.0.0.1:3000${NC}"

nohup npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "前端服务 PID: $FRONTEND_PID"

# 等待前端服务启动
echo "等待前端服务启动..."
sleep 8
if curl -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}✅ 前端服务启动成功 (端口 3000)${NC}"
else
    echo -e "${RED}❌ 前端服务启动失败${NC}"
    tail -20 "$PROJECT_ROOT/logs/frontend.log"
fi

# 4. 启动K线数据服务 (Python HTTP Server) - 端口 8002
echo -e "${GREEN}📈 启动K线数据服务 (Python HTTP)...${NC}"
cd "$PROJECT_ROOT"
nohup python3 backend/trading-service/simple_kline_server.py > "$PROJECT_ROOT/logs/kline-service.log" 2>&1 &
KLINE_PID=$!
echo "K线服务 PID: $KLINE_PID"

# 等待K线服务启动
echo "等待K线服务启动..."
sleep 3
if curl -s http://localhost:8002 > /dev/null; then
    echo -e "${GREEN}✅ K线服务启动成功 (端口 8002)${NC}"
else
    echo -e "${RED}❌ K线服务启动失败${NC}"
    tail -20 "$PROJECT_ROOT/logs/kline-service.log"
fi

# 5. 重新加载Nginx配置
echo -e "${YELLOW}🔄 重新加载Nginx配置...${NC}"
if systemctl reload nginx; then
    echo -e "${GREEN}✅ Nginx配置重新加载成功${NC}"
else
    echo -e "${RED}❌ Nginx配置重新加载失败${NC}"
fi

# 保存PID到文件
echo "$TRADING_PID" > "$PROJECT_ROOT/logs/trading-service.pid"
echo "$USER_PID" > "$PROJECT_ROOT/logs/user-service.pid"
echo "$FRONTEND_PID" > "$PROJECT_ROOT/logs/frontend.pid"
echo "$KLINE_PID" > "$PROJECT_ROOT/logs/kline-service.pid"

# 服务状态检查
echo -e "${YELLOW}📋 服务状态检查...${NC}"
echo "🔹 交易服务: http://localhost:8001/health"
echo "🔹 用户服务: http://localhost:3001/health"  
echo "🔹 前端界面: http://localhost:3000"
echo "🔹 K线数据: http://localhost:8002"
echo "🔹 公网代理: http://${PUBLIC_IP}/health"

# 热更新验证
echo -e "${YELLOW}🔥 验证热更新功能...${NC}"
sleep 3
if curl -s "http://${PUBLIC_IP}" | grep -q "Trademe"; then
    echo -e "${GREEN}✅ 公网访问正常${NC}"
    if curl -s "http://${PUBLIC_IP}" | grep -q "/@vite/client"; then
        echo -e "${GREEN}✅ Vite热更新客户端已加载${NC}"
    else
        echo -e "${YELLOW}⚠️  Vite客户端可能未正确加载${NC}"
    fi
else
    echo -e "${RED}❌ 公网访问失败${NC}"
fi

# 最终状态检查
sleep 3
if curl -s http://localhost:8001/health > /dev/null && \
   curl -s http://localhost:3001/health > /dev/null && \
   curl -s http://localhost:3000 > /dev/null && \
   curl -s http://localhost:8002 > /dev/null && \
   curl -s "http://${PUBLIC_IP}/health" > /dev/null; then
    echo ""
    echo -e "${GREEN}🎉 所有服务启动成功！${NC}"
    echo ""
    echo -e "${PURPLE}🌍 公网访问地址 (支持热更新):${NC}"
    echo -e "${PURPLE}  📱 前端界面: http://${PUBLIC_IP}${NC}"
    echo -e "${PURPLE}  🔧 用户API: http://${PUBLIC_IP}/api/v1${NC}"
    echo -e "${PURPLE}  📊 交易API: http://${PUBLIC_IP}/trading/api/v1${NC}"
    echo ""
    echo -e "${BLUE}🏠 本地访问地址:${NC}"
    echo -e "${BLUE}  📱 前端界面: http://localhost:3000${NC}"
    echo -e "${BLUE}  🔧 用户API: http://localhost:3001${NC}"
    echo -e "${BLUE}  📊 交易API: http://localhost:8001${NC}"
    echo -e "${BLUE}  📈 K线API: http://localhost:8002${NC}"
    echo ""
    echo -e "${GREEN}🔥 开发特性:${NC}"
    echo -e "${GREEN}  ✅ 热模块替换 (HMR) - 前端代码修改实时生效${NC}"
    echo -e "${GREEN}  ✅ 自动重载 - 后端代码修改自动重启${NC}"
    echo -e "${GREEN}  ✅ 公网访问 - 远程测试和调试${NC}"
    echo -e "${GREEN}  ✅ 跨服务认证 - 用户JWT在交易服务中验证${NC}"
    echo ""
    echo -e "${YELLOW}🛠 调试工具:${NC}"
    echo -e "${YELLOW}  📁 日志文件: $PROJECT_ROOT/logs/${NC}"
    echo -e "${YELLOW}  🔍 前端日志: tail -f $PROJECT_ROOT/logs/frontend.log${NC}"
    echo -e "${YELLOW}  📈 K线日志: tail -f $PROJECT_ROOT/logs/kline-service.log${NC}"
    echo -e "${YELLOW}  🛑 停止服务: ./stop-dev.sh${NC}"
    echo ""
    echo -e "${YELLOW}🧪 测试账户:${NC}"
    echo -e "${YELLOW}  📧 邮箱: publictest@example.com${NC}"
    echo -e "${YELLOW}  🔑 密码: PublicTest123!${NC}"
    echo -e "${YELLOW}  💎 权限: 高级版 (premium)${NC}"
else
    echo -e "${RED}❌ 某些服务启动失败，请检查日志${NC}"
    echo ""
    echo -e "${YELLOW}🔍 故障排除步骤:${NC}"
    echo "1. 检查端口占用: lsof -i:3000,3001,8001,8002"
    echo "2. 查看服务日志: tail -f $PROJECT_ROOT/logs/*.log"
    echo "3. 验证Nginx状态: systemctl status nginx"
    echo "4. 检查防火墙: ufw status"
    echo "5. 测试K线服务: curl http://localhost:8002/klines/BTC%2FUSDT?exchange=okx&timeframe=1h&limit=5"
    exit 1
fi