"""
优化的日志配置模块
防止日志文件过大，添加更严格的控制
"""

import sys
from loguru import logger
from app.config import settings

def setup_optimized_logger():
    """配置优化的日志系统"""
    # 移除默认配置
    logger.remove()
    
    # 控制台输出（开发环境）
    if settings.environment == "development":
        logger.add(
            sys.stdout,
            level="INFO",  # 避免DEBUG级别
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            filter=lambda record: "heartbeat" not in record["message"].lower()  # 过滤心跳日志
        )
    
    # 主日志文件 - 严格控制大小
    logger.add(
        settings.log_file,
        level="INFO",
        rotation="50 MB",      # 减小轮转大小到50MB
        retention="7 days",     # 只保留7天
        compression="gz",       # 压缩旧日志
        enqueue=True,          # 异步写入，防止阻塞
        serialize=False,       # 不使用JSON序列化（减小体积）
        backtrace=False,       # 不记录完整堆栈（减小体积）
        diagnose=False,        # 不记录诊断信息
        filter=lambda record: not any(skip in record["message"].lower() 
                                     for skip in ["heartbeat", "health check", "ping"])
    )
    
    # 错误日志文件
    error_log_file = settings.log_file.replace('.log', '.error.log')
    logger.add(
        error_log_file,
        level="ERROR",
        rotation="10 MB",      # 错误日志更小
        retention="30 days",   
        compression="gz",
        enqueue=True,
        filter=lambda record: record["level"].name in ["ERROR", "CRITICAL"]
    )
    
    # 添加日志数量限制器
    class LogRateLimiter:
        def __init__(self, max_logs_per_minute=1000):
            self.max_logs = max_logs_per_minute
            self.log_count = 0
            self.last_reset = time.time()
        
        def __call__(self, record):
            current_time = time.time()
            if current_time - self.last_reset > 60:
                self.log_count = 0
                self.last_reset = current_time
            
            self.log_count += 1
            if self.log_count > self.max_logs:
                if self.log_count == self.max_logs + 1:
                    logger.warning(f"Log rate limit exceeded ({self.max_logs} logs/min)")
                return False
            return True
    
    # 添加速率限制
    logger.add(
        sys.stderr,
        level="WARNING",
        filter=LogRateLimiter(max_logs_per_minute=1000)
    )
    
    return logger

import time

# 初始化优化的日志器
optimized_logger = setup_optimized_logger()