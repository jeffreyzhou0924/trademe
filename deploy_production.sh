#!/bin/bash

# Trademe.one 生产环境部署脚本
# 用于构建前端并配置nginx静态文件服务

set -e

echo "==================================="
echo "🚀 Trademe.one 生产环境部署"
echo "==================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_ROOT="/root/trademe"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_USER_SERVICE="$PROJECT_ROOT/backend/user-service"
BACKEND_TRADING_SERVICE="$PROJECT_ROOT/backend/trading-service"

# 1. 构建前端
echo -e "\n${YELLOW}📦 构建前端应用...${NC}"
cd $FRONTEND_DIR

# 安装依赖
echo "安装前端依赖..."
npm install

# 构建生产版本
echo "构建生产版本..."
npm run build

# 检查构建结果
if [ -d "$FRONTEND_DIR/dist" ]; then
    echo -e "${GREEN}✅ 前端构建成功${NC}"
else
    echo -e "${RED}❌ 前端构建失败${NC}"
    exit 1
fi

# 2. 更新nginx配置以使用静态文件
echo -e "\n${YELLOW}🔧 更新nginx配置...${NC}"

cat > /etc/nginx/sites-available/trademe.one.production <<'EOF'
# Trademe.one - 生产环境配置
# 使用静态文件服务前端

upstream user_service {
    server localhost:3001;
    keepalive 32;
}

upstream trading_service {
    server localhost:8001;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name trademe.one www.trademe.one;

    # 日志
    access_log /var/log/nginx/trademe.one.access.log;
    error_log /var/log/nginx/trademe.one.error.log;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # 文件上传大小
    client_max_body_size 10M;

    # Gzip压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json;
    gzip_disable "MSIE [1-6]\.";

    # 根目录 - 前端静态文件
    root /root/trademe/frontend/dist;
    index index.html;

    # 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API代理 - 用户服务
    location ~ ^/api/v1/(auth|users|membership) {
        proxy_pass http://user_service;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # API代理 - 交易服务
    location ~ ^/api/v1/(strategies|backtests|trading|ai|market) {
        proxy_pass http://trading_service;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }

    # WebSocket
    location /ws {
        proxy_pass http://trading_service;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
    }

    location /api/health/user {
        proxy_pass http://user_service/health;
        access_log off;
    }

    location /api/health/trading {
        proxy_pass http://trading_service/health;
        access_log off;
    }
}
EOF

# 3. 切换到生产配置
echo -e "\n${YELLOW}🔄 切换到生产配置...${NC}"
sudo rm -f /etc/nginx/sites-enabled/trademe.one
sudo ln -sf /etc/nginx/sites-available/trademe.one.production /etc/nginx/sites-enabled/trademe.one

# 4. 测试nginx配置
echo -e "\n${YELLOW}🧪 测试nginx配置...${NC}"
if sudo nginx -t; then
    echo -e "${GREEN}✅ nginx配置正确${NC}"
else
    echo -e "${RED}❌ nginx配置错误${NC}"
    exit 1
fi

# 5. 重载nginx
echo -e "\n${YELLOW}♻️  重载nginx...${NC}"
sudo nginx -s reload
echo -e "${GREEN}✅ nginx已重载${NC}"

# 6. 启动后端服务（如果未运行）
echo -e "\n${YELLOW}🔧 检查后端服务...${NC}"

# 检查用户服务
if ! lsof -i:3001 > /dev/null; then
    echo "启动用户服务..."
    cd $BACKEND_USER_SERVICE
    npm run start:prod &
    sleep 5
fi

# 检查交易服务
if ! lsof -i:8001 > /dev/null; then
    echo "启动交易服务..."
    cd $BACKEND_TRADING_SERVICE
    PYTHONPATH=$BACKEND_TRADING_SERVICE uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4 --log-config=logging.yaml &
    sleep 5
fi

# 7. 健康检查
echo -e "\n${YELLOW}🏥 执行健康检查...${NC}"

check_health() {
    local url=$1
    local name=$2
    
    if curl -s -o /dev/null -w "%{http_code}" -H "Host: trademe.one" "http://localhost$url" | grep -q "200"; then
        echo -e "${GREEN}✅ $name 正常${NC}"
        return 0
    else
        echo -e "${RED}❌ $name 异常${NC}"
        return 1
    fi
}

check_health "/health" "Nginx"
check_health "/api/health/user" "用户服务"
check_health "/api/health/trading" "交易服务"
check_health "/" "前端应用"

echo -e "\n${GREEN}==================================="
echo "✨ 部署完成！"
echo "==================================="
echo -e "${NC}"
echo "访问地址: http://trademe.one"
echo "API文档: http://trademe.one/api/docs"
echo ""
echo "提示："
echo "1. 确保域名DNS已正确指向服务器IP"
echo "2. 考虑配置SSL证书 (运行: certbot --nginx -d trademe.one)"
echo "3. 定期备份数据库文件"
echo ""