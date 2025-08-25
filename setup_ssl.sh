#!/bin/bash

# Trademe.one SSL证书配置脚本
# 使用Let's Encrypt免费SSL证书

set -e

echo "==================================="
echo "🔒 Trademe.one SSL证书配置"
echo "==================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 域名
DOMAIN="trademe.one"
WWW_DOMAIN="www.trademe.one"
EMAIL="admin@trademe.one"  # 修改为您的邮箱

# 1. 安装Certbot
echo -e "\n${YELLOW}📦 安装Certbot...${NC}"
if ! command -v certbot &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y certbot python3-certbot-nginx
    echo -e "${GREEN}✅ Certbot安装成功${NC}"
else
    echo -e "${GREEN}✅ Certbot已安装${NC}"
fi

# 2. 获取SSL证书
echo -e "\n${YELLOW}🔐 获取SSL证书...${NC}"
echo "将为以下域名申请证书："
echo "  - $DOMAIN"
echo "  - $WWW_DOMAIN"
echo ""
echo "请确保："
echo "1. 域名DNS已正确指向此服务器"
echo "2. 80端口可以从外网访问"
echo "3. nginx正在运行"
echo ""
read -p "是否继续? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 申请证书
    sudo certbot --nginx \
        -d $DOMAIN \
        -d $WWW_DOMAIN \
        --non-interactive \
        --agree-tos \
        --email $EMAIL \
        --redirect
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ SSL证书获取成功${NC}"
    else
        echo -e "${RED}❌ SSL证书获取失败${NC}"
        exit 1
    fi
else
    echo "已取消"
    exit 0
fi

# 3. 更新nginx配置支持HTTPS
echo -e "\n${YELLOW}🔧 更新nginx配置...${NC}"

cat > /etc/nginx/sites-available/trademe.one.ssl <<'EOF'
# Trademe.one - HTTPS配置

upstream user_service {
    server localhost:3001;
    keepalive 32;
}

upstream trading_service {
    server localhost:8001;
    keepalive 32;
}

# HTTP重定向到HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name trademe.one www.trademe.one;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS配置
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name trademe.one www.trademe.one;

    # SSL证书（由Certbot自动配置）
    ssl_certificate /etc/letsencrypt/live/trademe.one/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trademe.one/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # 其他安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self' https: wss:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; style-src 'self' 'unsafe-inline' https:;" always;

    # 日志
    access_log /var/log/nginx/trademe.one.ssl.access.log;
    error_log /var/log/nginx/trademe.one.ssl.error.log;

    # 配置
    client_max_body_size 10M;
    
    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript application/json;

    # 根目录
    root /root/trademe/frontend/dist;
    index index.html;

    # 前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API代理
    location ~ ^/api/v1/(auth|users|membership) {
        proxy_pass http://user_service;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_buffering off;
    }

    location ~ ^/api/v1/(strategies|backtests|trading|ai|market) {
        proxy_pass http://trading_service;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }

    # WebSocket (WSS)
    location /ws {
        proxy_pass http://trading_service;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 3600s;
    }

    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
    }
}
EOF

# 4. 设置自动续期
echo -e "\n${YELLOW}⏰ 设置证书自动续期...${NC}"

# 添加cron任务
(crontab -l 2>/dev/null; echo "0 0,12 * * * /usr/bin/certbot renew --quiet && /usr/bin/nginx -s reload") | crontab -

echo -e "${GREEN}✅ 自动续期已设置${NC}"

# 5. 重载nginx
echo -e "\n${YELLOW}♻️  重载nginx...${NC}"
sudo nginx -s reload

# 6. 测试HTTPS
echo -e "\n${YELLOW}🧪 测试HTTPS连接...${NC}"
sleep 2

if curl -Is https://$DOMAIN | head -n 1 | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✅ HTTPS连接正常${NC}"
else
    echo -e "${YELLOW}⚠️  HTTPS连接测试失败，请手动检查${NC}"
fi

echo -e "\n${GREEN}==================================="
echo "✨ SSL配置完成！"
echo "==================================="
echo -e "${NC}"
echo "访问地址："
echo "  🔒 https://trademe.one"
echo "  🔒 https://www.trademe.one"
echo ""
echo "证书信息："
echo "  证书路径: /etc/letsencrypt/live/trademe.one/"
echo "  有效期: 90天"
echo "  自动续期: 已启用（每天0点和12点检查）"
echo ""
echo "安全评级测试："
echo "  访问 https://www.ssllabs.com/ssltest/analyze.html?d=trademe.one"
echo ""