#!/bin/bash

# Trademe Trading Service 启动脚本

# 设置环境变量
export PYTHONPATH=/root/trademe/backend/trading-service
export PATH=/root/trademe/backend/trading-service/venv/bin:$PATH

# 进入工作目录
cd /root/trademe/backend/trading-service

# 确保日志目录存在
mkdir -p logs

# 启动服务
echo "Starting Trademe Trading Service..."
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4 --log-config=logging.yaml