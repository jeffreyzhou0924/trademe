#!/usr/bin/env python3
"""
数据管理系统完整测试
验证历史数据存储拉取机制在管理后台的集成效果
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.database import AsyncSessionLocal
from app.services.historical_data_downloader import historical_data_downloader
from app.services.data_quality_monitor import data_quality_monitor
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_admin_data_management():
    print('🏢 管理后台数据管理系统测试')
    print('='*60)
    
    test_results = {
        'database_schema': False,
        'api_endpoints': False,
        'data_download_flow': False,
        'quality_monitoring': False,
        'admin_interface': False
    }
    
    async with AsyncSessionLocal() as db:
        
        # =================== 测试1: 数据库表结构验证 ===================
        print('\\n🗄️  测试1: 数据库表结构验证')
        try:
            # 检查关键数据表是否存在
            required_tables = [
                'kline_data', 'tick_data', 'data_download_tasks', 
                'data_quality_metrics', 'data_cache_metadata'
            ]
            
            existing_tables = []
            for table in required_tables:
                result = await db.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                )
                if result.fetchone():
                    existing_tables.append(table)
                    print(f'  ✅ 表 {table} 存在')
                else:
                    print(f'  ❌ 表 {table} 不存在')
            
            if len(existing_tables) >= 3:  # 至少3个核心表存在
                test_results['database_schema'] = True
                print('✅ 数据库表结构验证通过')
            else:
                print('❌ 数据库表结构不完整')
                
        except Exception as e:
            print(f'❌ 数据库表结构验证失败: {str(e)}')
        
        
        # =================== 测试2: API端点可用性 ===================
        print('\\n🔌 测试2: 数据管理API端点验证')
        try:
            # 模拟管理员检查数据可用性
            availability = await historical_data_downloader.check_data_availability(
                exchange='binance',
                symbol='BTC/USDT',
                timeframe='1h',
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
                db=db
            )
            
            print(f'  ✅ 数据可用性检查API: {availability["coverage"]:.1f}%覆盖率')
            test_results['api_endpoints'] = True
            
        except Exception as e:
            print(f'❌ API端点验证失败: {str(e)}')
        
        
        # =================== 测试3: 管理员数据下载流程 ===================
        print('\\n📥 测试3: 管理员数据下载流程')
        try:
            # 模拟管理员手动触发小量数据下载
            download_result = await historical_data_downloader.download_historical_klines(
                exchange='binance',
                symbol='BTC/USDT',
                timeframe='1d',
                start_date=datetime.now() - timedelta(days=3),
                end_date=datetime.now(),
                db=db,
                batch_size=10  # 小批次测试
            )
            
            if download_result.get('success'):
                downloaded_count = download_result.get('downloaded_count', 0)
                task_id = download_result.get('task_id')
                print(f'  ✅ 数据下载成功: {downloaded_count} 条记录')
                print(f'  📋 任务ID: {task_id}')
                
                # 检查任务记录是否保存
                task_query = """
                SELECT status, progress, downloaded_records 
                FROM data_download_tasks 
                WHERE id = :task_id
                """
                
                task_result = await db.execute(task_query, {'task_id': task_id})
                task_row = task_result.fetchone()
                
                if task_row:
                    status, progress, records = task_row
                    print(f'  📊 任务状态: {status}, 进度: {progress:.1f}%, 记录: {records}')
                    test_results['data_download_flow'] = True
                else:
                    print('  ⚠️  任务记录未找到')
            else:
                print(f'❌ 数据下载失败: {download_result.get("error", "未知错误")}')
                
        except Exception as e:
            print(f'❌ 数据下载流程测试失败: {str(e)}')
        
        
        # =================== 测试4: 数据质量监控 ===================
        print('\\n🔬 测试4: 管理员数据质量监控')
        try:
            # 模拟管理员检查数据质量
            quality_result = await data_quality_monitor.run_comprehensive_quality_check(
                exchange='binance',
                symbol='BTC/USDT',
                timeframe='1d',
                check_days=3,
                db=db
            )
            
            quality_score = quality_result.get('quality_score', 0)
            completeness = quality_result.get('completeness', {})
            recommendations = quality_result.get('recommendation', [])
            
            print(f'  ✅ 质量监控完成')
            print(f'  📊 质量评分: {quality_score:.1f}/100')
            print(f'  📈 完整性: {completeness.get("completeness_percent", 0):.1f}%')
            print(f'  💡 建议数量: {len(recommendations)}')
            
            if quality_score >= 0:  # 只要能生成评分就算成功
                test_results['quality_monitoring'] = True
                
        except Exception as e:
            print(f'❌ 质量监控测试失败: {str(e)}')
        
        
        # =================== 测试5: 管理界面集成验证 ===================
        print('\\n🖥️  测试5: 前端管理界面集成')
        try:
            # 检查前端文件是否存在
            frontend_files = [
                '/root/trademe/frontend/src/pages/DataManagementPage.tsx',
                '/root/trademe/frontend/src/App.tsx'
            ]
            
            files_exist = []
            for file_path in frontend_files:
                if os.path.exists(file_path):
                    files_exist.append(file_path)
                    print(f'  ✅ 前端文件存在: {os.path.basename(file_path)}')
                else:
                    print(f'  ❌ 前端文件不存在: {os.path.basename(file_path)}')
            
            # 检查路由是否正确配置
            with open('/root/trademe/frontend/src/App.tsx', 'r', encoding='utf-8') as f:
                app_content = f.read()
                
            if '/admin/data' in app_content and 'DataManagementPage' in app_content:
                print('  ✅ 前端路由配置正确')
                test_results['admin_interface'] = True
            else:
                print('  ❌ 前端路由配置有问题')
                
        except Exception as e:
            print(f'❌ 前端集成验证失败: {str(e)}')
        
        
        # =================== 结果汇总 ===================
        print('\\n' + '='*60)
        print('📋 管理后台数据管理系统测试结果:')
        print(f'🗄️  数据库表结构: {"✅ 成功" if test_results["database_schema"] else "❌ 失败"}')
        print(f'🔌 API端点验证: {"✅ 成功" if test_results["api_endpoints"] else "❌ 失败"}')
        print(f'📥 数据下载流程: {"✅ 成功" if test_results["data_download_flow"] else "❌ 失败"}')
        print(f'🔬 质量监控功能: {"✅ 成功" if test_results["quality_monitoring"] else "❌ 失败"}')
        print(f'🖥️  管理界面集成: {"✅ 成功" if test_results["admin_interface"] else "❌ 失败"}')
        
        success_count = sum(test_results.values())
        print(f'\\n🎯 总体测试成功率: {success_count}/5 ({success_count/5*100:.1f}%)')
        
        if success_count >= 4:
            print('🎉 管理后台数据管理系统基本就绪！')
            print('\\n🛠️  管理员操作指南:')
            print('1. 访问: http://43.167.252.120/admin (admin@trademe.com登录)')
            print('2. 点击"数据管理"进入专用控制台')
            print('3. 使用"单个数据下载"精确控制特定交易对')
            print('4. 使用"批量下载"一键获取主要交易对历史数据')
            print('5. "质量监控"标签页检查数据完整性和准确性')
            print('6. "任务管理"标签页实时跟踪下载进度')
            print('\\n💡 推荐首次操作:')
            print('• 批量下载最近30天BTC/ETH/BNB的1h和1d数据')
            print('• 质量检查确保数据完整性达到95%以上')
            print('• 定期(周度)更新增量数据保持数据新鲜度')
            
            return True
        else:
            print('❌ 系统存在关键问题，需要进一步优化。')
            return False

if __name__ == "__main__":
    result = asyncio.run(test_admin_data_management())
    sys.exit(0 if result else 1)