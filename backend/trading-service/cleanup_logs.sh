#!/bin/bash

# 日志清理脚本 - 定期清理过大的日志文件

LOG_DIR="/root/trademe/backend/trading-service/logs"
MAX_LOG_SIZE="100M"  # 最大日志大小
MAX_TOTAL_SIZE="500M"  # 日志目录总大小限制

echo "=== 日志清理任务开始 ==="
echo "时间: $(date)"

# 1. 删除超过7天的日志
echo "删除7天前的日志..."
find $LOG_DIR -name "*.log" -type f -mtime +7 -delete
find $LOG_DIR -name "*.gz" -type f -mtime +30 -delete

# 2. 压缩超过100MB的日志
echo "压缩大日志文件..."
find $LOG_DIR -name "*.log" -type f -size +$MAX_LOG_SIZE -exec gzip {} \;

# 3. 截断正在写入的超大日志
for logfile in $LOG_DIR/*.log; do
    if [ -f "$logfile" ]; then
        size=$(du -h "$logfile" | cut -f1)
        if [[ "$size" =~ G$ ]] || [[ "${size%M}" -gt 500 ]]; then
            echo "截断超大日志: $logfile (当前大小: $size)"
            # 保留最后1000行
            tail -n 1000 "$logfile" > "$logfile.tmp"
            mv "$logfile.tmp" "$logfile"
        fi
    fi
done

# 4. 检查总大小
total_size=$(du -sh $LOG_DIR 2>/dev/null | cut -f1)
echo "日志目录总大小: $total_size"

# 5. 如果总大小超过限制，删除最老的文件
if [[ "$total_size" =~ G$ ]]; then
    echo "警告: 日志目录过大，删除最老的文件..."
    cd $LOG_DIR
    ls -t *.gz 2>/dev/null | tail -n +10 | xargs -r rm -f
fi

echo "=== 日志清理完成 ==="
echo ""