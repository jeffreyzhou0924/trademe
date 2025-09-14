#!/bin/bash

# 🔍 Trademe系统快速诊断脚本
echo "🚀 ==================================="
echo "🔍 Trademe系统快速诊断开始"
echo "🕐 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "🚀 ==================================="

# 1. 服务状态检查
echo ""
echo "📊 1. 服务状态检查"
echo "-----------------------------------"
echo "前端服务 (3000端口):"
if pgrep -f "npm.*dev.*3000" > /dev/null; then
    echo "✅ 前端服务运行正常 (PID: $(pgrep -f 'npm.*dev.*3000'))"
else
    echo "❌ 前端服务未运行"
fi

echo ""
echo "交易服务 (8001端口):"
if pgrep -f "uvicorn.*8001" > /dev/null; then
    echo "✅ 交易服务运行正常 (PID: $(pgrep -f 'uvicorn.*8001'))"
    echo "   内存使用: $(ps -o pid,ppid,rss,vsize,pcpu,pmem,cmd -p $(pgrep -f 'uvicorn.*8001') | tail -1 | awk '{print $6"%"}')"
else
    echo "❌ 交易服务未运行"
fi

echo ""
echo "用户服务 (3001端口):"
if pgrep -f "node.*3001" > /dev/null; then
    echo "✅ 用户服务运行正常 (PID: $(pgrep -f 'node.*3001'))"
else
    echo "❌ 用户服务未运行"
fi

echo ""
echo "Nginx服务:"
if systemctl is-active nginx > /dev/null 2>&1; then
    echo "✅ Nginx运行正常"
else
    echo "❌ Nginx服务异常"
fi

# 2. 端口监听状态
echo ""
echo "🌐 2. 端口监听状态"
echo "-----------------------------------"
netstat -tlnp 2>/dev/null | grep -E "(3000|3001|8001|80|443)" | while read line; do
    port=$(echo $line | awk '{print $4}' | cut -d: -f2)
    case $port in
        3000) echo "✅ 前端开发服务: $line" ;;
        3001) echo "✅ 用户服务: $line" ;;
        8001) echo "✅ 交易服务: $line" ;;
        80|443) echo "✅ Nginx服务: $line" ;;
        *) echo "ℹ️  其他服务: $line" ;;
    esac
done

# 3. 数据库连接测试
echo ""
echo "💾 3. 数据库连接测试"
echo "-----------------------------------"
if [ -f "/root/trademe/data/trademe.db" ]; then
    echo "✅ 主数据库文件存在: $(ls -lh /root/trademe/data/trademe.db | awk '{print $5}')"
    
    # 测试关键表
    tables=("claude_conversations" "strategies" "users" "usdt_wallets")
    for table in "${tables[@]}"; do
        count=$(sqlite3 /root/trademe/data/trademe.db "SELECT COUNT(*) FROM $table;" 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo "✅ $table 表: $count 条记录"
        else
            echo "❌ $table 表查询失败"
        fi
    done
else
    echo "❌ 主数据库文件不存在"
fi

if [ -f "/root/trademe/backend/trading-service/data/trademe.db" ]; then
    echo "✅ 交易服务数据库存在: $(ls -lh /root/trademe/backend/trading-service/data/trademe.db | awk '{print $5}')"
else
    echo "⚠️  交易服务数据库不存在"
fi

# 4. 最近错误日志
echo ""
echo "📝 4. 最近错误日志 (最近10条)"
echo "-----------------------------------"
if [ -f "/root/trademe/backend/trading-service/logs/trading-service.error.log" ]; then
    echo "交易服务错误:"
    tail -10 /root/trademe/backend/trading-service/logs/trading-service.error.log | grep -E "(ERROR|CRITICAL|Failed)" | tail -5
else
    echo "⚠️  交易服务错误日志不存在"
fi

if [ -f "/root/trademe/backend/user-service/logs/error.log" ]; then
    echo ""
    echo "用户服务错误:"
    tail -10 /root/trademe/backend/user-service/logs/error.log | tail -5
else
    echo "⚠️  用户服务错误日志不存在"
fi

# 5. 系统资源使用
echo ""
echo "📊 5. 系统资源使用"
echo "-----------------------------------"
echo "内存使用:"
free -h | grep -E "(Mem|Swap)"

echo ""
echo "磁盘使用:"
df -h / | tail -1 | awk '{print "根分区: " $3 " / " $2 " (" $5 ")"}'

echo ""
echo "负载平均:"
uptime | awk -F'load average:' '{print "系统负载:" $2}'

# 6. WebSocket连接测试
echo ""
echo "🔌 6. WebSocket连接测试"
echo "-----------------------------------"
if command -v curl > /dev/null; then
    # 测试AI会话API
    echo "测试AI会话API..."
    response=$(curl -s -w "%{http_code}" -o /tmp/api_test_output "http://localhost:8001/api/v1/ai/sessions?limit=1" 2>/dev/null)
    if [ "$response" = "200" ]; then
        echo "✅ AI会话API响应正常"
    elif [ "$response" = "401" ]; then
        echo "⚠️  AI会话API需要认证 (正常)"
    else
        echo "❌ AI会话API异常 (状态码: $response)"
    fi
else
    echo "⚠️  curl未安装，跳过API测试"
fi

# 7. 配置文件检查
echo ""
echo "⚙️  7. 关键配置检查"
echo "-----------------------------------"
echo "前端配置:"
if [ -f "/root/trademe/frontend/vite.config.ts" ]; then
    echo "✅ Vite配置存在"
else
    echo "❌ Vite配置缺失"
fi

echo "后端配置:"
if [ -f "/root/trademe/backend/trading-service/app/core/config.py" ]; then
    echo "✅ 交易服务配置存在"
else
    echo "❌ 交易服务配置缺失"
fi

# 8. 总结建议
echo ""
echo "🎯 8. 诊断总结和建议"
echo "-----------------------------------"

# 检查关键问题
issues=0

if ! pgrep -f "uvicorn.*8001" > /dev/null; then
    echo "🚨 关键问题: 交易服务未运行，请启动: cd /root/trademe/backend/trading-service && uvicorn app.main:app --host 0.0.0.0 --port 8001"
    ((issues++))
fi

if ! pgrep -f "npm.*dev.*3000" > /dev/null; then
    echo "🚨 关键问题: 前端服务未运行，请启动: cd /root/trademe/frontend && npm run dev"
    ((issues++))
fi

if [ ! -f "/root/trademe/data/trademe.db" ]; then
    echo "🚨 关键问题: 主数据库文件缺失"
    ((issues++))
fi

if [ $issues -eq 0 ]; then
    echo "✅ 系统整体状态良好，未发现严重问题"
    echo "💡 建议: 定期运行此脚本进行健康检查"
else
    echo "⚠️  发现 $issues 个关键问题，请优先处理"
fi

echo ""
echo "🚀 ==================================="
echo "🔍 诊断完成 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "📋 完整报告已保存到: /tmp/trademe_diagnosis_$(date +%Y%m%d_%H%M%S).log"
echo "🚀 ==================================="

# 保存完整报告
exec > >(tee -a "/tmp/trademe_diagnosis_$(date +%Y%m%d_%H%M%S).log")