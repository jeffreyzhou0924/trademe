# Trademe.one Cloudflare配置指南

## 📋 当前状况

域名 **trademe.one** 正在使用Cloudflare的DNS和CDN服务。需要正确配置以访问您的服务器。

## 🔧 Cloudflare配置步骤

### 1. **登录Cloudflare控制面板**
访问 https://dash.cloudflare.com 并登录您的账户

### 2. **SSL/TLS设置**

在Cloudflare控制面板中，选择trademe.one域名，然后：

1. 进入 **SSL/TLS** → **Overview**
2. 选择加密模式为 **Flexible**（灵活）
   - 这允许用户通过HTTPS访问Cloudflare，而Cloudflare到您的服务器使用HTTP

### 3. **DNS设置**

进入 **DNS** 设置：

1. 确保有以下记录：
   ```
   Type: A
   Name: @  (或 trademe.one)
   Content: 您的服务器IP地址
   Proxy status: Proxied (橙色云朵)
   
   Type: A
   Name: www
   Content: 您的服务器IP地址
   Proxy status: Proxied (橙色云朵)
   ```

2. 如果您想暂时绕过Cloudflare测试：
   - 点击橙色云朵图标，将其变为灰色（DNS only）
   - 这样流量将直接到达您的服务器

### 4. **页面规则（Page Rules）**

进入 **Rules** → **Page Rules**，创建以下规则：

1. **强制HTTPS**
   ```
   URL: http://trademe.one/*
   设置: Always Use HTTPS
   ```

2. **API缓存绕过**
   ```
   URL: trademe.one/api/*
   设置: 
   - Cache Level: Bypass
   - Disable Performance
   ```

### 5. **防火墙设置**

进入 **Security** → **WAF**：

1. 将安全级别设置为 **Low** 或 **Essentially Off**（开发阶段）
2. 确保没有阻止您的服务器IP

### 6. **缓存设置**

进入 **Caching** → **Configuration**：

1. **浏览器缓存TTL**: 4小时
2. **Always Online**: 关闭（开发阶段）

## 🚀 快速修复方案

### 方案A：临时绕过Cloudflare（推荐用于测试）

1. 在DNS设置中，将橙色云朵点击变为灰色
2. 等待5分钟DNS传播
3. 访问 http://trademe.one

### 方案B：配置Cloudflare Flexible SSL

1. SSL/TLS设置改为 **Flexible**
2. 创建页面规则强制HTTPS
3. 访问 https://trademe.one

### 方案C：完整SSL配置（生产环境推荐）

1. 在服务器上配置SSL证书（使用Cloudflare Origin证书）
2. 将SSL/TLS设置改为 **Full** 或 **Full (strict)**

## 📝 Cloudflare Origin证书配置

### 1. 生成Origin证书

在Cloudflare控制面板：
1. 进入 **SSL/TLS** → **Origin Server**
2. 点击 **Create Certificate**
3. 选择域名：trademe.one, *.trademe.one
4. 证书有效期：15年
5. 点击创建并保存证书和私钥

### 2. 在服务器上安装证书

```bash
# 创建证书目录
sudo mkdir -p /etc/ssl/cloudflare

# 保存证书（从Cloudflare复制）
sudo nano /etc/ssl/cloudflare/trademe.one.pem
# 粘贴Origin Certificate内容

# 保存私钥（从Cloudflare复制）
sudo nano /etc/ssl/cloudflare/trademe.one.key
# 粘贴Private Key内容

# 设置权限
sudo chmod 600 /etc/ssl/cloudflare/trademe.one.key
```

### 3. 更新nginx配置

```nginx
server {
    listen 443 ssl http2;
    server_name trademe.one www.trademe.one;
    
    ssl_certificate /etc/ssl/cloudflare/trademe.one.pem;
    ssl_certificate_key /etc/ssl/cloudflare/trademe.one.key;
    
    # 其他配置...
}
```

## ⚡ 立即解决方案

由于您现在无法通过HTTPS访问，建议：

1. **先通过HTTP访问**：
   - 在Cloudflare DNS设置中，暂时关闭代理（灰色云朵）
   - 访问 http://trademe.one

2. **或修改本地hosts文件测试**：
   ```
   # Windows: C:\Windows\System32\drivers\etc\hosts
   # Linux/Mac: /etc/hosts
   
   添加：
   您的服务器IP  trademe.one
   您的服务器IP  www.trademe.one
   ```

3. **使用IP直接访问**：
   ```
   http://您的服务器IP
   ```
   并在浏览器中添加Host头或使用ModHeader扩展

## 🔍 故障排查

### 检查DNS解析
```bash
nslookup trademe.one
dig trademe.one
```

### 检查Cloudflare状态
```bash
curl -I https://trademe.one
# 查看CF-RAY头，确认经过Cloudflare
```

### 直接测试服务器
```bash
curl -H "Host: trademe.one" http://您的服务器IP
```

## 📞 需要的操作

请在Cloudflare控制面板中：

1. 将SSL/TLS模式设置为 **Flexible**
2. 或者暂时关闭Cloudflare代理（灰色云朵）
3. 等待几分钟后访问 http://trademe.one

这样应该就能正常访问了！

---

**注意**：Cloudflare的设置更改可能需要几分钟才能生效。