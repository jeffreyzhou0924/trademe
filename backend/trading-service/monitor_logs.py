#!/usr/bin/env python3
"""
日志监控脚本 - 实时监控日志增长并预警
"""

import os
import time
import psutil
from pathlib import Path

class LogMonitor:
    def __init__(self, log_dir="/root/trademe/backend/trading-service"):
        self.log_dir = Path(log_dir)
        self.warning_size = 100 * 1024 * 1024  # 100MB警告
        self.critical_size = 500 * 1024 * 1024  # 500MB严重警告
        self.check_interval = 60  # 每分钟检查一次
        
    def get_log_files(self):
        """获取所有日志文件"""
        log_files = []
        for pattern in ["*.log", "logs/*.log"]:
            log_files.extend(self.log_dir.glob(pattern))
        return log_files
    
    def check_log_sizes(self):
        """检查日志文件大小"""
        issues = []
        for log_file in self.get_log_files():
            if log_file.exists():
                size = log_file.stat().st_size
                if size > self.critical_size:
                    issues.append({
                        'file': str(log_file),
                        'size': size,
                        'level': 'CRITICAL',
                        'size_mb': size / (1024 * 1024)
                    })
                elif size > self.warning_size:
                    issues.append({
                        'file': str(log_file),
                        'size': size,
                        'level': 'WARNING',
                        'size_mb': size / (1024 * 1024)
                    })
        return issues
    
    def check_disk_space(self):
        """检查磁盘空间"""
        disk_usage = psutil.disk_usage('/')
        return {
            'total_gb': disk_usage.total / (1024**3),
            'used_gb': disk_usage.used / (1024**3),
            'free_gb': disk_usage.free / (1024**3),
            'percent': disk_usage.percent
        }
    
    def monitor_once(self):
        """执行一次监控"""
        print(f"\n=== 日志监控 {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        # 检查日志大小
        issues = self.check_log_sizes()
        if issues:
            print("\n⚠️  发现大日志文件:")
            for issue in issues:
                print(f"  [{issue['level']}] {issue['file']}: {issue['size_mb']:.1f}MB")
                
                # 自动处理超大文件
                if issue['level'] == 'CRITICAL':
                    print(f"    → 自动截断文件...")
                    self.truncate_log(issue['file'])
        else:
            print("✅ 所有日志文件大小正常")
        
        # 检查磁盘空间
        disk = self.check_disk_space()
        print(f"\n📊 磁盘使用: {disk['used_gb']:.1f}GB / {disk['total_gb']:.1f}GB ({disk['percent']:.1f}%)")
        
        if disk['percent'] > 90:
            print("  ⚠️  警告: 磁盘空间不足！")
            self.emergency_cleanup()
    
    def truncate_log(self, log_file):
        """截断超大日志文件"""
        try:
            # 保留最后1000行
            with open(log_file, 'r') as f:
                lines = f.readlines()
                last_lines = lines[-1000:] if len(lines) > 1000 else lines
            
            with open(log_file, 'w') as f:
                f.writelines(last_lines)
            
            print(f"    ✅ 已截断至最后1000行")
        except Exception as e:
            print(f"    ❌ 截断失败: {e}")
    
    def emergency_cleanup(self):
        """紧急清理"""
        print("  执行紧急清理...")
        os.system("/root/trademe/backend/trading-service/cleanup_logs.sh")
    
    def run(self):
        """持续监控"""
        print("🔍 日志监控服务启动")
        print(f"   监控目录: {self.log_dir}")
        print(f"   检查间隔: {self.check_interval}秒")
        print(f"   警告阈值: {self.warning_size / (1024*1024):.0f}MB")
        print(f"   严重阈值: {self.critical_size / (1024*1024):.0f}MB")
        
        while True:
            try:
                self.monitor_once()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                print("\n监控服务停止")
                break
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = LogMonitor()
    # 执行一次检查
    monitor.monitor_once()
    
    # 如果需要持续监控，取消下面的注释
    # monitor.run()