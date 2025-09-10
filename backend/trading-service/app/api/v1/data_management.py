"""
数据管理API接口
提供历史数据下载、质量监控、性能分析的管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import asyncio
import json

from app.database import get_db
from app.middleware.auth import get_current_active_user
from app.models.data_collection import DataCollectionTask
from app.services.historical_data_downloader import historical_data_downloader, data_sync_scheduler
from app.services.tick_data_manager import tick_data_manager, tick_to_kline_aggregator
from app.services.data_quality_monitor import data_quality_monitor, data_completeness_service
from app.services.okx_data_downloader import okx_data_downloader, DataType, TaskStatus, ResourceMonitor
from app.services.okx_data_downloader_enhanced import enhanced_okx_downloader, EnhancedDownloadTask
from app.services.ccxt_historical_downloader import CCXTHistoricalDownloader, CCXTDownloadTaskManager

router = APIRouter(prefix="/data", tags=["数据管理"])
logger = logging.getLogger(__name__)

@router.get("/test")
async def test_route():
    """测试路由是否工作"""
    return {"success": True, "message": "Data management API is working"}



@router.get("/timeframes")
async def get_available_timeframes(
    symbol: str,
    exchange: str = 'okx',
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定交易对的可用时间框架"""
    try:
        query = text("""
        SELECT 
            timeframe,
            MIN(timestamp) as start_date,
            MAX(timestamp) as end_date,
            COUNT(*) as record_count
        FROM market_data 
        WHERE exchange = :exchange AND symbol = :symbol
        GROUP BY timeframe
        ORDER BY 
            CASE timeframe 
                WHEN '1m' THEN 1 WHEN '5m' THEN 2 WHEN '15m' THEN 3 
                WHEN '30m' THEN 4 WHEN '1h' THEN 5 WHEN '2h' THEN 6 
                WHEN '4h' THEN 7 WHEN '1d' THEN 8 WHEN '1w' THEN 9 
                ELSE 99 END
        """)
        
        result = await db.execute(query, {"exchange": exchange, "symbol": symbol})
        rows = result.fetchall()
        
        timeframes_data = []
        for row in rows:
            timeframes_data.append({
                "timeframe": row.timeframe,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "end_date": row.end_date.isoformat() if row.end_date else None,
                "record_count": row.record_count
            })
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "exchange": exchange,
                "timeframes": timeframes_data
            }
        }
        
    except Exception as e:
        logger.error(f"获取时间框架失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quality/check/{exchange}/{symbol}/{timeframe}")
async def check_data_quality(
    exchange: str,
    symbol: str,
    timeframe: str,
    check_days: int = 7,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """检查数据质量"""
    try:
        result = await data_quality_monitor.run_comprehensive_quality_check(
            exchange, symbol, timeframe, check_days, db
        )
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"数据质量检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/availability/{exchange}/{symbol}/{timeframe}")
async def check_data_availability(
    exchange: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """检查数据可用性"""
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        availability = await historical_data_downloader.check_data_availability(
            exchange, symbol, timeframe, start_dt, end_dt, db
        )
        
        return {"success": True, "data": availability}
        
    except Exception as e:
        logger.error(f"数据可用性检查失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/download/historical")
async def download_historical_data(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """下载历史数据"""
    try:
        exchange = request.get('exchange')
        symbol = request.get('symbol')
        timeframe = request.get('timeframe')
        start_date = datetime.fromisoformat(request.get('start_date').replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.get('end_date').replace('Z', '+00:00'))
        
        # 后台任务下载
        background_tasks.add_task(
            _background_download_task,
            exchange, symbol, timeframe, start_date, end_date
        )
        
        return {
            "success": True,
            "message": f"历史数据下载任务已启动: {exchange} {symbol} {timeframe}",
            "estimated_duration": "5-30分钟"
        }
        
    except Exception as e:
        logger.error(f"启动历史数据下载失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/storage/stats")
async def get_storage_statistics(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取存储统计信息"""
    try:
        # K线数据统计
        kline_query = text("""
        SELECT 
            exchange,
            COUNT(DISTINCT symbol) as symbol_count,
            COUNT(DISTINCT timeframe) as timeframe_count,
            COUNT(*) as total_records
        FROM market_data
        GROUP BY exchange
        """)
        
        kline_result = await db.execute(kline_query)
        kline_stats = []
        
        for row in kline_result.fetchall():
            kline_stats.append({
                'exchange': row[0],
                'symbol_count': row[1],
                'timeframe_count': row[2],
                'total_records': row[3]
            })
        
        return {
            "success": True,
            "data": {
                "kline_statistics": kline_stats
            }
        }
        
    except Exception as e:
        logger.error(f"获取存储统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# 后台任务函数
# ================================

async def _background_download_task(
    exchange: str,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime
):
    """后台下载任务"""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            result = await historical_data_downloader.download_historical_klines(
                exchange, symbol, timeframe, start_date, end_date, db
            )
            logger.info(f"后台下载完成: {result}")
        except Exception as e:
            logger.error(f"后台下载失败: {str(e)}")

async def _background_repair_task(
    exchange: str,
    symbol: str,
    timeframe: str
):
    """后台数据修复任务"""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            result = await data_completeness_service.auto_repair_missing_data(
                exchange, symbol, timeframe, db
            )
            logger.info(f"数据修复完成: {result}")
        except Exception as e:
            logger.error(f"数据修复失败: {str(e)}")

async def _background_ccxt_download_task(
    task_id: str,
    exchange_id: str,
    symbols: List[str],
    timeframes: List[str],
    days_back: int
):
    """CCXT后台下载任务"""
    logger.info(f"🚀 开始CCXT下载任务: {task_id}")
    try:
        # 使用CCXTDownloadTaskManager简化接口
        result = await CCXTDownloadTaskManager.download_okx_historical_data(
            symbols=symbols,
            timeframes=timeframes,
            days_back=days_back
        )
        
        logger.info(f"✅ CCXT下载任务完成 {task_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ CCXT下载任务失败 {task_id}: {str(e)}")
        raise

async def _background_ccxt_bulk_download_task(
    task_id: str,
    exchange_id: str,
    symbols: List[str],
    timeframes: List[str],
    years_back: int
):
    """CCXT批量后台下载任务"""
    logger.info(f"🚀 开始CCXT批量下载任务: {task_id}")
    try:
        all_results = []
        total_symbols = len(symbols)
        
        # 逐个下载交易对以避免过载
        for i, symbol in enumerate(symbols):
            logger.info(f"📊 批量下载进度: {i+1}/{total_symbols} - {symbol}")
            
            # 使用CCXTDownloadTaskManager的长期数据下载接口
            result = await CCXTDownloadTaskManager.download_long_term_data(
                symbol=symbol,
                timeframe=timeframes[0] if timeframes else '1h',  # 选择第一个时间框架
                years_back=years_back,
                exchange_id=exchange_id
            )
            
            all_results.append({
                'symbol': symbol,
                'result': result
            })
            
            # 给其他任务让出CPU时间
            await asyncio.sleep(0.5)
        
        summary = {
            'total_symbols': total_symbols,
            'completed_symbols': len([r for r in all_results if r['result'].get('success', False)]),
            'failed_symbols': len([r for r in all_results if not r['result'].get('success', False)]),
            'results': all_results
        }
        
        logger.info(f"✅ CCXT批量下载完成 {task_id}: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"❌ CCXT批量下载失败 {task_id}: {str(e)}")
        raise

async def _create_ccxt_task_record_async(
    task_id: str, 
    symbols: List[str],
    timeframes: List[str],
    start_date: str,
    end_date: str
):
    """在数据库中创建CCXT下载任务记录 (独立会话)"""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            task_record = DataCollectionTask(
                task_name=f"CCXT历史数据下载_{task_id[-8:]}",
                exchange="okx",
                data_type="ccxt_kline",
                symbols=json.dumps(symbols),
                timeframes=json.dumps(timeframes),
                status="running",
                schedule_type="manual",
                config=json.dumps({
                    "task_id": task_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "method": "ccxt_fallback",
                    "description": "历史数据CCXT智能下载"
                })
            )
            
            db.add(task_record)
            await db.commit()
            await db.refresh(task_record)
            
            logger.info(f"✅ CCXT任务记录已创建: {task_id} (数据库ID: {task_record.id})")
            return task_record.id
            
        except Exception as e:
            logger.error(f"❌ 创建CCXT任务记录失败 {task_id}: {str(e)}")
            await db.rollback()
            raise

async def _update_ccxt_task_status_async(
    task_id: str,
    status: str,
    result_data: Dict[str, Any] = None
):
    """更新CCXT任务状态 (独立会话)"""
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            # 通过config字段中的task_id查找任务
            stmt = select(DataCollectionTask).where(
                DataCollectionTask.config.like(f'%"task_id": "{task_id}"%')
            )
            result = await db.execute(stmt)
            task_record = result.scalar_one_or_none()
            
            if task_record:
                task_record.status = status
                task_record.updated_at = datetime.now()
                
                if status == "completed" and result_data:
                    task_record.success_count = task_record.success_count + 1
                    task_record.total_records = result_data.get('total_records_downloaded', result_data.get('total_records', 0))
                elif status == "failed":
                    task_record.error_count = task_record.error_count + 1
                    if result_data and result_data.get('error'):
                        task_record.last_error_message = str(result_data['error'])
                        task_record.last_error_at = datetime.now()
                
                await db.commit()
                logger.info(f"✅ CCXT任务状态已更新: {task_id} -> {status}")
            else:
                logger.warning(f"⚠️ 未找到CCXT任务记录: {task_id}")
                
        except Exception as e:
            logger.error(f"❌ 更新CCXT任务状态失败 {task_id}: {str(e)}")
            await db.rollback()

async def _background_ccxt_fallback_task(
    task_id: str,
    exchange_id: str,
    ccxt_symbols: List[str],
    timeframes: List[str],
    days_back: int
):
    """CCXT回退任务 - 当OKX API失败时的智能回退"""
    logger.info(f"🔄 开始CCXT回退任务: {task_id} ({days_back}天历史数据)")
    
    try:
        result = await CCXTDownloadTaskManager.download_okx_historical_data(
            symbols=ccxt_symbols,
            timeframes=timeframes,
            days_back=days_back
        )
        
        # 更新任务状态为完成
        await _update_ccxt_task_status_async(task_id, "completed", result)
        
        logger.info(f"✅ CCXT回退任务完成 {task_id}: {result}")
        return result
        
    except Exception as e:
        # 更新任务状态为失败
        await _update_ccxt_task_status_async(task_id, "failed", {"error": str(e)})
        
        logger.error(f"❌ CCXT回退任务失败 {task_id}: {str(e)}")
        raise

# ================================
# OKX数据下载API (新增真实下载功能)
# ================================

@router.get("/system/resources")
async def get_system_resources(
    current_user = Depends(get_current_active_user)
):
    """获取系统资源状态"""
    try:
        monitor = ResourceMonitor()
        available, message = monitor.is_resource_available()
        
        return {
            "success": True,
            "data": {
                "resources_available": available,
                "status_message": message,
                "memory_usage_percent": monitor.get_memory_usage(),
                "cpu_usage_percent": monitor.get_cpu_usage(),
                "process_memory_mb": monitor.get_process_memory_mb(),
                "limits": {
                    "max_memory_percent": monitor.max_memory_percent,
                    "max_cpu_percent": monitor.max_cpu_percent
                }
            }
        }
    except Exception as e:
        logger.error(f"获取系统资源状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/okx/tick/download")
async def download_okx_tick_data(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """下载OKX Tick数据 - 优化版本，智能分批处理"""
    try:
        symbols = request.get('symbols', ['BTC'])
        start_date = request.get('start_date')  # 格式: 20240101
        end_date = request.get('end_date')      # 格式: 20240131
        
        if not all([symbols, start_date, end_date]):
            raise HTTPException(status_code=400, detail="缺少必要参数: symbols, start_date, end_date")
        
        # 检查系统资源状态
        monitor = ResourceMonitor()
        available, resource_message = monitor.is_resource_available()
        
        if not available:
            raise HTTPException(status_code=503, detail=f"系统资源不足，无法启动下载任务: {resource_message}")
        
        # 检查运行中的任务数量
        active_tasks = await okx_data_downloader.list_active_tasks()
        running_tasks = [task for task in active_tasks if task.status == TaskStatus.RUNNING]
        
        if len(running_tasks) >= 1:  # 限制同时运行的任务数
            raise HTTPException(
                status_code=429, 
                detail=f"已有 {len(running_tasks)} 个下载任务正在运行，请稍后再试。提示：建议等待当前任务完成或使用更短的时间范围"
            )
        
        # 检查时间范围合理性
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        days_span = (end_dt - start_dt).days + 1
        total_files_estimate = len(symbols) * days_span
        
        # 提供智能建议
        optimization_tips = []
        if total_files_estimate > 10:
            optimization_tips.append(f"建议分批下载：当前需下载 {total_files_estimate} 个文件")
            # 自动调整到合理范围
            max_days = 10 // len(symbols)
            if max_days < 1:
                max_days = 1
            suggested_end = start_dt + timedelta(days=max_days-1)
            if suggested_end < end_dt:
                optimization_tips.append(f"本次任务将自动限制到 {suggested_end.strftime('%Y%m%d')}")
        
        if days_span > 7:
            optimization_tips.append("建议每次下载不超过7天数据，以提高成功率")
            
        # 创建下载任务 (内部会自动限制文件数量)
        task = await okx_data_downloader.create_tick_download_task(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
        # 后台执行任务
        background_tasks.add_task(
            okx_data_downloader.execute_tick_download_task,
            task.task_id
        )
        
        return {
            "success": True,
            "data": {
                "task_id": task.task_id,
                "data_type": "tick",
                "symbols": symbols,
                "date_range": f"{start_date} - {end_date}",
                "total_files": task.total_files,
                "message": "OKX Tick数据下载任务已启动 (智能优化版)",
                "optimization_applied": {
                    "file_limit": task.total_files <= 10,
                    "batch_processing": True,
                    "memory_optimization": True,
                    "resource_monitoring": True
                },
                "tips": optimization_tips if optimization_tips else ["任务配置合理，无需额外优化"],
                "resource_status": {
                    "memory_usage": f"{monitor.get_memory_usage():.1f}%",
                    "cpu_usage": f"{monitor.get_cpu_usage():.1f}%",
                    "process_memory": f"{monitor.get_process_memory_mb():.1f}MB"
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动OKX Tick数据下载失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/okx/tick/download-quick")
async def download_okx_tick_data_quick(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """快速下载OKX Tick数据 - 限制3天内，单交易对"""
    try:
        symbol = request.get('symbol', 'BTC')  # 单个交易对
        start_date = request.get('start_date')  # 格式: 20240101
        days = min(request.get('days', 1), 3)  # 最多3天
        
        if not start_date:
            raise HTTPException(status_code=400, detail="缺少必要参数: start_date")
        
        # 计算结束日期
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = start_dt + timedelta(days=days-1)
        end_date = end_dt.strftime('%Y%m%d')
        
        # 检查系统资源
        monitor = ResourceMonitor()
        available, resource_message = monitor.is_resource_available()
        
        if not available:
            raise HTTPException(status_code=503, detail=f"系统资源不足: {resource_message}")
        
        # 检查是否有运行中的任务
        active_tasks = await okx_data_downloader.list_active_tasks()
        running_tasks = [task for task in active_tasks if task.status == TaskStatus.RUNNING]
        
        if len(running_tasks) >= 1:
            raise HTTPException(
                status_code=429, 
                detail="有其他下载任务正在运行，快速下载功能暂时不可用"
            )
        
        # 创建快速下载任务
        task = await okx_data_downloader.create_tick_download_task(
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date
        )
        
        # 后台执行任务
        background_tasks.add_task(
            okx_data_downloader.execute_tick_download_task,
            task.task_id
        )
        
        return {
            "success": True,
            "data": {
                "task_id": task.task_id,
                "data_type": "tick_quick",
                "symbol": symbol,
                "date_range": f"{start_date} - {end_date}",
                "days": days,
                "total_files": task.total_files,
                "message": f"快速Tick数据下载已启动 ({symbol}, {days}天)",
                "estimated_time": f"{task.total_files * 30}秒 - {task.total_files * 60}秒",
                "features": [
                    "单交易对快速下载",
                    "最多3天数据",
                    "优先级处理",
                    "资源优化"
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"快速下载启动失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/okx/tick/download-batch")
async def download_okx_tick_data_batch(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """OKX Tick数据批量下载 - 按日维度自动分割任务"""
    try:
        symbols = request.get('symbols', ['BTC'])
        start_date = request.get('start_date')  # 格式: 20240701
        end_date = request.get('end_date')      # 格式: 20240730
        max_concurrent = request.get('max_concurrent', 3)  # 最大并发任务数
        
        if not all([symbols, start_date, end_date]):
            raise HTTPException(status_code=400, detail="缺少必要参数: symbols, start_date, end_date")
        
        # 解析日期范围
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        days_span = (end_dt - start_dt).days + 1
        
        if days_span <= 0:
            raise HTTPException(status_code=400, detail="结束日期必须大于或等于开始日期")
        
        if days_span > 31:
            raise HTTPException(status_code=400, detail="单次批量下载不能超过31天，建议分批处理")
        
        # 检查系统资源状态
        monitor = ResourceMonitor()
        available, resource_message = monitor.is_resource_available()
        
        if not available:
            raise HTTPException(status_code=503, detail=f"系统资源不足: {resource_message}")
        
        # 检查当前运行的任务
        active_tasks = await okx_data_downloader.list_active_tasks()
        running_tasks = [task for task in active_tasks if task.status == TaskStatus.RUNNING]
        
        if len(running_tasks) >= max_concurrent:
            raise HTTPException(
                status_code=429, 
                detail=f"当前有 {len(running_tasks)} 个任务在运行，超过最大并发数 {max_concurrent}"
            )
        
        # 按日期分割任务
        batch_tasks = []
        current_dt = start_dt
        task_count = 0
        
        while current_dt <= end_dt:
            date_str = current_dt.strftime('%Y%m%d')
            
            # 为每个交易对和每个日期创建独立任务
            for symbol in symbols:
                # 创建单日任务
                task = await okx_data_downloader.create_tick_download_task(
                    symbols=[symbol],
                    start_date=date_str,
                    end_date=date_str
                )
                
                batch_tasks.append({
                    "task_id": task.task_id,
                    "symbol": symbol,
                    "date": date_str,
                    "status": "pending",
                    "estimated_files": 1
                })
                
                task_count += 1
                
                # 控制并发数量，避免创建太多任务
                if task_count >= max_concurrent:
                    break
            
            if task_count >= max_concurrent:
                break
                
            current_dt += timedelta(days=1)
        
        # 启动前几个任务（并发执行）
        started_tasks = 0
        for task_info in batch_tasks[:max_concurrent]:
            background_tasks.add_task(
                okx_data_downloader.execute_tick_download_task,
                task_info["task_id"]
            )
            task_info["status"] = "running"
            started_tasks += 1
        
        # 计算任务统计
        total_files_estimate = len(symbols) * days_span
        estimated_time_minutes = days_span * len(symbols) * 2  # 每个文件大约2分钟
        
        return {
            "success": True,
            "data": {
                "batch_id": f"batch_{int(datetime.now().timestamp())}",
                "batch_type": "tick_daily_split",
                "date_range": f"{start_date} - {end_date}",
                "symbols": symbols,
                "total_days": days_span,
                "total_tasks_created": len(batch_tasks),
                "tasks_started": started_tasks,
                "tasks_pending": len(batch_tasks) - started_tasks,
                "max_concurrent": max_concurrent,
                "estimated_files": total_files_estimate,
                "estimated_time": f"{estimated_time_minutes} 分钟",
                "tasks": batch_tasks,
                "message": f"已创建 {len(batch_tasks)} 个日维度下载任务，启动了 {started_tasks} 个任务",
                "recommendations": [
                    "任务将按日期自动分割执行",
                    "每个任务独立跟踪状态",
                    "失败的任务不影响其他日期",
                    f"建议每 {max_concurrent * 2} 分钟检查一次进度"
                ],
                "resource_status": {
                    "memory_usage": f"{monitor.get_memory_usage():.1f}%",
                    "cpu_usage": f"{monitor.get_cpu_usage():.1f}%",
                    "available": available
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量下载启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/okx/batch/status/{date_range}")
async def get_batch_download_status(
    date_range: str,  # 格式: 20240701-20240730
    symbols: str = Query(default="BTC", description="交易对，多个用逗号分隔"),
    current_user = Depends(get_current_active_user)
):
    """查询批量下载任务状态 - 按日期范围汇总所有相关任务"""
    try:
        # 解析日期范围
        if '-' not in date_range:
            raise HTTPException(status_code=400, detail="日期范围格式错误，应为: 20240701-20240730")
            
        start_date, end_date = date_range.split('-')
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        
        # 解析交易对
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
        
        # 获取所有活跃任务
        all_tasks = await okx_data_downloader.list_active_tasks()
        
        # 筛选匹配的任务（按日期和交易对）
        matching_tasks = []
        current_dt = start_dt
        
        while current_dt <= end_dt:
            date_str = current_dt.strftime('%Y%m%d')
            
            for symbol in symbol_list:
                # 查找匹配这个日期和交易对的任务
                for task in all_tasks:
                    # 检查任务是否匹配当前日期和交易对
                    if (hasattr(task, 'task_id') and 
                        date_str in task.task_id and 
                        any(symbol.lower() in task.task_id.lower() for symbol in [symbol])):
                        
                        matching_tasks.append({
                            "task_id": task.task_id,
                            "symbol": symbol,
                            "date": date_str,
                            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                            "progress": task.progress,
                            "downloaded_records": task.downloaded_records,
                            "total_files": task.total_files,
                            "processed_files": task.processed_files,
                            "created_at": task.created_at.isoformat() if task.created_at else None,
                            "started_at": task.started_at.isoformat() if task.started_at else None,
                            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                            "error_message": task.error_message or ""
                        })
            
            current_dt += timedelta(days=1)
        
        # 计算统计信息
        total_tasks = len(matching_tasks)
        completed_tasks = len([t for t in matching_tasks if t["status"] == "completed"])
        running_tasks = len([t for t in matching_tasks if t["status"] == "running"])
        failed_tasks = len([t for t in matching_tasks if t["status"] == "failed"])
        pending_tasks = len([t for t in matching_tasks if t["status"] == "pending"])
        
        total_records = sum(t["downloaded_records"] for t in matching_tasks)
        overall_progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # 按日期分组统计
        daily_stats = {}
        current_dt = start_dt
        while current_dt <= end_dt:
            date_str = current_dt.strftime('%Y%m%d')
            date_tasks = [t for t in matching_tasks if t["date"] == date_str]
            
            daily_stats[date_str] = {
                "date": date_str,
                "total_symbols": len(symbol_list),
                "completed_symbols": len([t for t in date_tasks if t["status"] == "completed"]),
                "running_symbols": len([t for t in date_tasks if t["status"] == "running"]),
                "failed_symbols": len([t for t in date_tasks if t["status"] == "failed"]),
                "total_records": sum(t["downloaded_records"] for t in date_tasks),
                "tasks": date_tasks
            }
            
            current_dt += timedelta(days=1)
        
        return {
            "success": True,
            "data": {
                "batch_info": {
                    "date_range": date_range,
                    "symbols": symbol_list,
                    "total_days": (end_dt - start_dt).days + 1
                },
                "summary": {
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "running_tasks": running_tasks,
                    "failed_tasks": failed_tasks,
                    "pending_tasks": pending_tasks,
                    "overall_progress": round(overall_progress, 2),
                    "total_downloaded_records": total_records
                },
                "daily_breakdown": daily_stats,
                "all_tasks": matching_tasks,
                "recommendations": [
                    f"整体进度: {completed_tasks}/{total_tasks} 任务完成",
                    f"已下载 {total_records:,} 条记录" if total_records > 0 else "暂无数据下载完成",
                    "失败的任务可以单独重新执行" if failed_tasks > 0 else "所有任务运行正常",
                    "建议等待运行中的任务完成" if running_tasks > 0 else "当前没有运行中的任务"
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询批量任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/okx/kline/download")
async def download_okx_kline_data(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """下载OKX K线数据 - 优化版本，支持资源检查"""
    try:
        symbols = request.get('symbols', ['BTC/USDT'])
        timeframes = request.get('timeframes', ['1h'])
        start_date = request.get('start_date')  # 格式: 20240101
        end_date = request.get('end_date')      # 格式: 20240131
        use_enhanced = request.get('use_enhanced', True)  # 新增：是否使用增强版下载器
        
        if not all([symbols, timeframes, start_date, end_date]):
            raise HTTPException(status_code=400, detail="缺少必要参数: symbols, timeframes, start_date, end_date")
        
        # 检查系统资源状态
        monitor = ResourceMonitor()
        available, resource_message = monitor.is_resource_available()
        
        if not available:
            raise HTTPException(status_code=503, detail=f"系统资源不足，无法启动下载任务: {resource_message}")
        
        # 检查是否有其他下载任务正在运行
        active_tasks = await okx_data_downloader.list_active_tasks()
        running_tasks = [task for task in active_tasks if task.status == TaskStatus.RUNNING]
        
        if len(running_tasks) >= 1:  # 限制同时运行的任务数
            raise HTTPException(
                status_code=429, 
                detail=f"已有 {len(running_tasks)} 个下载任务正在运行，请稍后再试"
            )
        
        if use_enhanced:
            # 🆕 智能选择：对于历史数据使用CCXT，对于实时数据使用增强版
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            current_time = datetime.now()
            days_ago = (current_time - start_dt).days
            
            if days_ago > 7:  # 7天前的数据用CCXT下载
                logger.info(f"🔄 历史数据 ({days_ago}天前)，使用CCXT下载器")
                
                # 转换为CCXT格式
                ccxt_symbols = []
                for symbol in symbols:
                    if 'USDT-SWAP' in symbol:
                        ccxt_symbols.append(symbol.replace('-USDT-SWAP', '/USDT:USDT'))
                    else:
                        ccxt_symbols.append(symbol.replace('-', '/'))
                
                # 创建CCXT任务
                task_id = f"ccxt_fallback_okx_{'-'.join(symbols[0].split('-'))[:10]}_{int(datetime.now().timestamp())}"
                
                # 在数据库中创建任务记录（使用独立会话避免冲突）
                await _create_ccxt_task_record_async(task_id, symbols, timeframes, start_date, end_date)
                
                background_tasks.add_task(
                    _background_ccxt_fallback_task,
                    task_id, 'okx', ccxt_symbols, timeframes, days_ago
                )
                
                return {
                    "success": True,
                    "data": {
                        "task_id": task_id,
                        "data_type": "ccxt_fallback",
                        "symbols": symbols,
                        "timeframes": timeframes,
                        "date_range": f"{start_date} - {end_date}",
                        "message": f"历史数据使用CCXT下载器 ({days_ago}天前)",
                        "method": "ccxt_fallback",
                        "features": [
                            "自动切换到CCXT解决历史数据问题",
                            "智能端点选择",
                            "生产级错误处理"
                        ]
                    }
                }
            else:
                # 使用增强版下载器处理近期数据
                task = await enhanced_okx_downloader.create_enhanced_kline_task(
                    symbols=symbols,
                    timeframes=timeframes,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # 后台执行增强任务
                background_tasks.add_task(
                    enhanced_okx_downloader.execute_enhanced_kline_task,
                    task.task_id
                )
            
            return {
                "success": True,
                "data": {
                    "task_id": task.task_id,
                    "data_type": "enhanced_kline",
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "date_range": f"{start_date} - {end_date}",
                    "total_files": task.total_files,
                    "expected_records": task.expected_records,
                    "subtasks_count": len(task.subtasks),
                    "message": "OKX 增强K线数据下载任务已启动",
                    "features": ["数据完整性验证", "智能重试机制", "质量评分", "分阶段下载"],
                    "resource_status": {
                        "memory_usage": f"{monitor.get_memory_usage():.1f}%",
                        "cpu_usage": f"{monitor.get_cpu_usage():.1f}%",
                        "process_memory": f"{monitor.get_process_memory_mb():.1f}MB"
                    }
                }
            }
        else:
            # 使用原版下载器
            task = await okx_data_downloader.create_kline_download_task(
                symbols=symbols,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date
            )
            
            # 后台执行任务
            background_tasks.add_task(
                okx_data_downloader.execute_kline_download_task,
                task.task_id
            )
            
            return {
                "success": True,
                "data": {
                    "task_id": task.task_id,
                    "data_type": "kline",
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "date_range": f"{start_date} - {end_date}",
                    "total_files": task.total_files,
                    "message": "OKX K线数据下载任务已启动",
                    "resource_status": {
                        "memory_usage": f"{monitor.get_memory_usage():.1f}%",
                        "cpu_usage": f"{monitor.get_cpu_usage():.1f}%",
                        "process_memory": f"{monitor.get_process_memory_mb():.1f}MB"
                    }
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动OKX K线数据下载失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# ================================
# CCXT历史数据下载API (新增)
# ================================

@router.post("/ccxt/download")
async def download_ccxt_historical_data(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user)
):
    """使用CCXT下载历史数据 - 支持1-2年长期数据"""
    try:
        exchange_id = request.get('exchange', 'okx')
        symbols = request.get('symbols', ['BTC/USDT:USDT'])
        timeframes = request.get('timeframes', ['1h'])
        days_back = request.get('days_back', 30)
        
        # 输入验证
        if not all([symbols, timeframes]):
            raise HTTPException(status_code=400, detail="缺少必要参数: symbols, timeframes")
        
        if days_back > 730:  # 限制最多2年
            raise HTTPException(status_code=400, detail="days_back不能超过730天")
        
        # 创建任务ID
        task_id = f"ccxt_{exchange_id}_{'-'.join(symbols[0].split('/'))[:10]}_{int(datetime.now().timestamp())}"
        
        # 启动后台任务
        background_tasks.add_task(
            _background_ccxt_download_task,
            task_id, exchange_id, symbols, timeframes, days_back
        )
        
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "exchange": exchange_id,
                "symbols": symbols,
                "timeframes": timeframes,
                "days_back": days_back,
                "message": f"CCXT历史数据下载任务已启动 ({days_back}天数据)",
                "estimated_duration": f"{days_back // 30 * 5}-{days_back // 30 * 15}分钟",
                "features": [
                    "支持1-2年历史数据", 
                    "自动端点选择(Candles/HistoryCandles)",
                    "智能分页和重试机制",
                    "生产级错误处理"
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动CCXT下载失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ccxt/download/bulk")
async def download_ccxt_bulk_data(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user)
):
    """批量下载多交易对长期历史数据"""
    try:
        exchange_id = request.get('exchange', 'okx')
        symbols = request.get('symbols', [])
        timeframes = request.get('timeframes', ['1h'])
        years_back = request.get('years_back', 1)
        
        if not symbols:
            raise HTTPException(status_code=400, detail="symbols列表不能为空")
        
        if years_back > 2:
            raise HTTPException(status_code=400, detail="years_back不能超过2年")
        
        # 创建批量任务ID
        task_id = f"ccxt_bulk_{exchange_id}_{len(symbols)}symbols_{int(datetime.now().timestamp())}"
        
        # 启动批量后台任务
        background_tasks.add_task(
            _background_ccxt_bulk_download_task,
            task_id, exchange_id, symbols, timeframes, years_back
        )
        
        estimated_records = len(symbols) * len(timeframes) * years_back * 365 * 24  # 粗略估算
        
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "exchange": exchange_id,
                "symbols": symbols,
                "timeframes": timeframes,
                "years_back": years_back,
                "estimated_records": estimated_records,
                "message": f"批量CCXT下载任务已启动 ({len(symbols)}个交易对, {years_back}年数据)",
                "estimated_duration": f"{years_back * len(symbols) * 10}-{years_back * len(symbols) * 30}分钟"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动批量CCXT下载失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/okx/tasks")
async def list_okx_download_tasks(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取OKX下载任务列表"""
    try:
        # 从数据库获取OKX任务（最近50条）
        query = text("""
        SELECT task_name, exchange, data_type, symbols, timeframes, status, 
               success_count, error_count, total_records, config, created_at,
               last_run_at, last_error_message
        FROM data_collection_tasks 
        WHERE exchange = 'okx' 
        ORDER BY created_at DESC 
        LIMIT 50
        """)
        
        result = await db.execute(query)
        task_list = []
        
        for row in result.fetchall():
            # 解析配置信息
            import json
            config = json.loads(row[9]) if row[9] else {}
            
            # 计算进度
            progress = 100.0 if row[5] == 'completed' else (
                50.0 if row[5] == 'running' else 0.0
            )
            
            task_info = {
                "task_id": row[0],  # task_name
                "data_type": row[2],  # data_type
                "exchange": row[1],   # exchange
                "symbols": [row[3]] if row[3] else [],  # symbols (stored as string)
                "date_range": f"{config.get('start_date', 'N/A')} - {config.get('end_date', 'N/A')}",
                "status": row[5],     # status
                "progress": progress,
                "total_files": config.get('total_files', 1),
                "processed_files": row[6],  # success_count
                "downloaded_records": row[8],  # total_records
                "created_at": row[10],  # created_at
                "started_at": row[11],  # last_run_at
                "completed_at": row[11] if row[5] == 'completed' else None,
                "error_message": row[12]  # last_error_message
            }
            
            # 添加时间框架信息（如果是K线数据）
            if row[2] == 'kline' and row[4]:  # data_type == 'kline' and timeframes
                task_info["timeframes"] = [row[4]]  # timeframes stored as string
            
            task_list.append(task_info)
        
        return {
            "success": True,
            "data": task_list,
            "total_tasks": len(task_list)
        }
        
    except Exception as e:
        logger.error(f"获取OKX任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/okx/tasks/{task_id}")
async def get_okx_task_status(
    task_id: str,
    current_user = Depends(get_current_active_user)
):
    """获取OKX下载任务状态"""
    try:
        # 先尝试增强版下载器
        enhanced_task_status = await enhanced_okx_downloader.get_enhanced_task_status(task_id)
        
        if enhanced_task_status:
            return {
                "success": True,
                "data": enhanced_task_status,
                "enhanced": True
            }
        
        # 回退到原版下载器
        task = await okx_data_downloader.get_task_status(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "success": True,
            "data": {
                "task_id": task.task_id,
                "data_type": task.data_type.value,
                "exchange": task.exchange,
                "symbols": task.symbols,
                "status": task.status.value,
                "progress": round(task.progress, 1),
                "total_files": task.total_files,
                "processed_files": task.processed_files,
                "downloaded_records": task.downloaded_records,
                "date_range": f"{task.start_date} - {task.end_date}",
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message,
                "estimated_completion": _estimate_completion_time(task) if task.status == TaskStatus.RUNNING else None
            },
            "enhanced": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/okx/tasks/{task_id}")
async def cancel_okx_task(
    task_id: str,
    current_user = Depends(get_current_active_user)
):
    """取消OKX下载任务"""
    try:
        success = await okx_data_downloader.cancel_task(task_id)
        
        if success:
            return {
                "success": True,
                "message": f"任务 {task_id} 已取消"
            }
        else:
            raise HTTPException(status_code=400, detail="无法取消该任务（可能已完成或不存在）")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/okx/statistics")
async def get_okx_download_statistics(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取OKX下载统计信息"""
    try:
        # 从数据库获取真实的统计数据
        query = text("""
        SELECT 
            COUNT(*) as total_downloads,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_downloads,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_downloads,
            SUM(success_count) as total_files_processed,
            SUM(total_records) as total_records_downloaded
        FROM data_collection_tasks 
        WHERE exchange = 'okx'
        """)
        
        result = await db.execute(query)
        row = result.fetchone()
        
        download_statistics = {
            "total_downloads": row[0] or 0,
            "successful_downloads": row[1] or 0,
            "failed_downloads": row[2] or 0,
            "total_files_processed": row[3] or 0,
            "total_records_downloaded": row[4] or 0
        }
        
        return {
            "success": True,
            "data": {
                "download_statistics": download_statistics,
                "supported_symbols": {
                    "tick_data": okx_data_downloader.supported_tick_symbols,
                    "kline_data": okx_data_downloader.supported_kline_symbols
                },
                "supported_timeframes": okx_data_downloader.supported_timeframes,
                "data_directories": {
                    "tick_data": str(okx_data_downloader.okx_tick_dir),
                    "kline_data": str(okx_data_downloader.okx_kline_dir)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取下载统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/okx/cleanup")
async def cleanup_okx_completed_tasks(
    days_old: int = 7,
    current_user = Depends(get_current_active_user)
):
    """清理完成的OKX下载任务"""
    try:
        await okx_data_downloader.clean_completed_tasks(days_old)
        
        return {
            "success": True,
            "message": f"已清理 {days_old} 天前的完成任务"
        }
        
    except Exception as e:
        logger.error(f"清理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# 增强版数据质量检查API
# ================================

@router.post("/okx/quality/check")
async def check_data_quality(
    request: Dict[str, Any],
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """数据质量检查 - 增强版"""
    try:
        symbol = request.get('symbol')
        timeframe = request.get('timeframe')
        start_date = request.get('start_date')  # 格式: 20240101
        end_date = request.get('end_date')      # 格式: 20240131
        
        if not all([symbol, timeframe, start_date, end_date]):
            raise HTTPException(status_code=400, detail="缺少必要参数: symbol, timeframe, start_date, end_date")
        
        # 转换日期格式
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        
        # 使用增强版质量检查器
        from app.services.okx_data_downloader_enhanced import DataQualityChecker
        
        quality_score, quality_issues = await DataQualityChecker.check_kline_data_quality(
            db, symbol, timeframe, start_dt, end_dt
        )
        
        # 查询数据基本统计
        result = await db.execute(
            select(
                func.count(MarketData.id).label('total_records'),
                func.min(MarketData.timestamp).label('earliest_date'),
                func.max(MarketData.timestamp).label('latest_date'),
                func.avg(MarketData.volume).label('avg_volume')
            ).where(
                and_(
                    MarketData.exchange == "okx",
                    MarketData.symbol == symbol,
                    MarketData.timeframe == timeframe,
                    MarketData.timestamp >= start_dt,
                    MarketData.timestamp <= end_dt
                )
            )
        )
        
        stats = result.first()
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "timeframe": timeframe,
                "date_range": f"{start_date} - {end_date}",
                "quality_score": round(quality_score, 1),
                "quality_grade": _get_quality_grade(quality_score),
                "quality_issues": quality_issues,
                "statistics": {
                    "total_records": stats.total_records or 0,
                    "earliest_date": stats.earliest_date.isoformat() if stats.earliest_date else None,
                    "latest_date": stats.latest_date.isoformat() if stats.latest_date else None,
                    "average_volume": float(stats.avg_volume) if stats.avg_volume else 0
                },
                "recommendations": _get_quality_recommendations(quality_score, quality_issues),
                "checked_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"数据质量检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/okx/repair/missing")
async def repair_missing_data(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user)
):
    """修复缺失数据 - 智能补全"""
    try:
        symbol = request.get('symbol')
        timeframe = request.get('timeframe')
        start_date = request.get('start_date')
        end_date = request.get('end_date')
        
        if not all([symbol, timeframe, start_date, end_date]):
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        # 使用增强版下载器进行修复
        repair_task = await enhanced_okx_downloader.create_enhanced_kline_task(
            symbols=[symbol],
            timeframes=[timeframe],
            start_date=start_date,
            end_date=end_date
        )
        
        # 后台执行修复任务
        background_tasks.add_task(
            enhanced_okx_downloader.execute_enhanced_kline_task,
            repair_task.task_id
        )
        
        return {
            "success": True,
            "data": {
                "repair_task_id": repair_task.task_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "date_range": f"{start_date} - {end_date}",
                "message": "数据修复任务已启动",
                "estimated_time": "5-15分钟"
            }
        }
        
    except Exception as e:
        logger.error(f"启动数据修复失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _normalize_symbol_for_query(symbol: str) -> str:
    """
    将前端查询的符号格式转换为数据库中存储的格式
    前端格式示例:
    - Tick数据: "BTC" -> 数据库格式: "BTC/USDT"
    - Tick数据: "BTC/USDT" -> 数据库格式: "BTC/USDT" (不变)
    - K线数据: "BTC-USDT-SWAP" -> 数据库格式: "BTCUSDTUSDT"
    """
    if not symbol:
        return symbol
    
    # 如果是期货合约格式 BTC-USDT-SWAP
    if '-SWAP' in symbol:
        # BTC-USDT-SWAP -> BTC/USDT:USDT -> BTCUSDTUSDT
        base_symbol = symbol.replace('-SWAP', '').replace('-', '/')
        ccxt_format = base_symbol + ':USDT'  # BTC/USDT:USDT
        normalized = ccxt_format.replace('/', '').replace(':', '')  # BTCUSDTUSDT
    elif '-' in symbol:
        # 包含短横线的格式: BTC-USDT -> BTCUSDT
        normalized = symbol.replace('-', '').replace('/', '').replace(':', '')
    elif '/' in symbol and 'USDT' in symbol:
        # 已经是标准格式: BTC/USDT -> BTC/USDT (不变)
        normalized = symbol
    else:
        # 简单格式 (主要是tick数据): BTC -> BTC/USDT
        # 这是针对tick数据查询的特殊处理，因为tick数据存储格式是 BTC/USDT
        normalized = f"{symbol}/USDT"
    
    logger.info(f"🔄 符号转换: {symbol} -> {normalized}")
    print(f"DEBUG: 符号转换: {symbol} -> {normalized}")
    return normalized

def _calculate_summary_statistics(data_info: List[Dict], data_type: str, symbol: str = None) -> Dict[str, Any]:
    """
    计算数据汇总统计信息
    包括：总记录数、数据完整度、时间范围、可用时间框架等
    """
    if not data_info:
        return {
            "total_records": 0,
            "data_completeness_percent": 0,
            "timeframes_available": 0,
            "earliest_date": None,
            "latest_date": None,
            "days_span": 0
        }
    
    summary = {
        "total_records": 0,
        "data_completeness_percent": 0,
        "timeframes_available": 0,
        "earliest_date": None,
        "latest_date": None,
        "days_span": 0
    }
    
    if data_type == 'kline':
        if symbol:
            # 特定交易对的详细统计
            total_records = sum(row.get('record_count', 0) for row in data_info)
            timeframes = len(data_info)
            
            # 获取时间范围
            all_start_dates = [row.get('start_date') for row in data_info if row.get('start_date')]
            all_end_dates = [row.get('end_date') for row in data_info if row.get('end_date')]
            
            if all_start_dates and all_end_dates:
                earliest_date = min(all_start_dates)
                latest_date = max(all_end_dates)
                
                # 计算天数范围（基于字符串日期）
                try:
                    if isinstance(earliest_date, str) and isinstance(latest_date, str):
                        earliest_dt = datetime.fromisoformat(earliest_date.replace('Z', '+00:00'))
                        latest_dt = datetime.fromisoformat(latest_date.replace('Z', '+00:00'))
                        days_span = (latest_dt - earliest_dt).days + 1
                    else:
                        days_span = 0
                except:
                    days_span = 0
                
                # 基于1分钟数据估算完整度
                expected_records_per_day = 1440  # 1440分钟/天
                expected_total = days_span * expected_records_per_day
                
                # 查找1分钟时间框架的记录数
                one_min_records = 0
                for row in data_info:
                    if row.get('timeframe') == '1m':
                        one_min_records = row.get('record_count', 0)
                        break
                
                if expected_total > 0 and one_min_records > 0:
                    completeness = min(100, (one_min_records / expected_total) * 100)
                else:
                    completeness = 100  # 假设其他时间框架是完整的
                
                summary.update({
                    "total_records": total_records,
                    "data_completeness_percent": round(completeness, 2),
                    "timeframes_available": timeframes,
                    "earliest_date": earliest_date,
                    "latest_date": latest_date,
                    "days_span": days_span
                })
        else:
            # 所有交易对的概览统计
            total_records = sum(row.get('total_records', 0) for row in data_info)
            total_symbols = len(data_info)
            
            # 获取全部时间范围
            all_earliest = [row.get('earliest_date') for row in data_info if row.get('earliest_date')]
            all_latest = [row.get('latest_date') for row in data_info if row.get('latest_date')]
            
            if all_earliest and all_latest:
                earliest_date = min(all_earliest)
                latest_date = max(all_latest)
            else:
                earliest_date = latest_date = None
            
            summary.update({
                "total_records": total_records,
                "total_symbols": total_symbols,
                "data_completeness_percent": 95,  # 预估值
                "earliest_date": earliest_date,
                "latest_date": latest_date
            })
    
    elif data_type == 'tick':
        # Tick数据统计
        total_records = sum(row.get('record_count', 0) for row in data_info)
        
        summary.update({
            "total_records": total_records,
            "data_completeness_percent": 100,  # Tick数据通常是完整的
            "data_type": "tick"
        })
    
    logger.info(f"📊 统计摘要: {summary}")
    return summary

# 数据查询API
@router.get("/query")
async def query_data_availability(
    data_type: str,  # 'kline' or 'tick'
    exchange: str = 'okx',
    symbol: str = None,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """查询数据库中的真实数据情况"""
    try:
        # 🔄 转换符号格式为数据库存储格式
        normalized_symbol = _normalize_symbol_for_query(symbol) if symbol else None
        logger.info(f"🔍 查询数据: data_type={data_type}, original_symbol={symbol}, normalized_symbol={normalized_symbol}")
        print(f"DEBUG: 查询数据 - data_type={data_type}, original_symbol={symbol}, normalized_symbol={normalized_symbol}")
        
        if data_type == 'kline':
            # 查询K线数据
            if symbol:
                # 查询特定交易对的数据
                query = text("""
                SELECT 
                    symbol,
                    timeframe,
                    MIN(timestamp) as start_date,
                    MAX(timestamp) as end_date,
                    COUNT(*) as record_count
                FROM market_data 
                WHERE exchange = :exchange AND symbol = :symbol
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
                """)
                result = await db.execute(query, {"exchange": exchange, "symbol": normalized_symbol})
            else:
                # 查询所有交易对的数据概览
                query = text("""
                SELECT 
                    symbol,
                    COUNT(DISTINCT timeframe) as timeframes_count,
                    MIN(timestamp) as earliest_date,
                    MAX(timestamp) as latest_date,
                    COUNT(*) as total_records
                FROM market_data 
                WHERE exchange = :exchange
                GROUP BY symbol
                ORDER BY symbol
                """)
                result = await db.execute(query, {"exchange": exchange})
                
        elif data_type == 'tick':
            # 查询Tick数据
            if symbol:
                query = text("""
                SELECT 
                    symbol,
                    MIN(timestamp) as start_timestamp,
                    MAX(timestamp) as end_timestamp,
                    COUNT(*) as record_count,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM tick_data 
                WHERE exchange = :exchange AND symbol = :symbol
                GROUP BY symbol
                """)
                # 添加详细的调试信息
                query_params = {"exchange": exchange, "symbol": normalized_symbol}
                logger.info(f"🔍 执行Tick数据查询: exchange={exchange}, symbol={normalized_symbol}")
                logger.info(f"🔍 查询SQL: {query.text}")
                logger.info(f"🔍 查询参数: {query_params}")
                result = await db.execute(query, query_params)
                logger.info(f"🔍 查询执行完成，准备获取结果...")
            else:
                query = text("""
                SELECT 
                    symbol,
                    MIN(timestamp) as earliest_timestamp,
                    MAX(timestamp) as latest_timestamp,
                    COUNT(*) as total_records
                FROM tick_data 
                WHERE exchange = :exchange
                GROUP BY symbol
                ORDER BY symbol
                """)
                result = await db.execute(query, {"exchange": exchange})
        else:
            raise HTTPException(status_code=400, detail="data_type必须是'kline'或'tick'")
        
        rows = result.fetchall()
        logger.info(f"🔍 查询结果rows数量: {len(rows)}")
        print(f"DEBUG: 查询结果rows数量: {len(rows)}")
        if rows:
            logger.info(f"🔍 第一行数据: {dict(rows[0]._mapping)}")
            print(f"DEBUG: 第一行数据: {dict(rows[0]._mapping)}")
        else:
            logger.info(f"🔍 没有找到匹配的数据行")
            print(f"DEBUG: 没有找到匹配的数据行")
        
        # 格式化返回数据
        data_info = []
        for row in rows:
            row_dict = dict(row._mapping)
            
            # 转换时间戳格式
            if data_type == 'kline':
                if row_dict.get('start_date'):
                    row_dict['start_date'] = row_dict['start_date'].isoformat() if hasattr(row_dict['start_date'], 'isoformat') else str(row_dict['start_date'])
                if row_dict.get('end_date'):
                    row_dict['end_date'] = row_dict['end_date'].isoformat() if hasattr(row_dict['end_date'], 'isoformat') else str(row_dict['end_date'])
                if row_dict.get('earliest_date'):
                    row_dict['earliest_date'] = row_dict['earliest_date'].isoformat() if hasattr(row_dict['earliest_date'], 'isoformat') else str(row_dict['earliest_date'])
                if row_dict.get('latest_date'):
                    row_dict['latest_date'] = row_dict['latest_date'].isoformat() if hasattr(row_dict['latest_date'], 'isoformat') else str(row_dict['latest_date'])
            
            elif data_type == 'tick':
                # Tick数据时间戳是BIGINT，需要转换
                if row_dict.get('start_timestamp'):
                    row_dict['start_date'] = datetime.fromtimestamp(row_dict['start_timestamp']/1000).isoformat() if row_dict['start_timestamp'] else None
                if row_dict.get('end_timestamp'):
                    row_dict['end_date'] = datetime.fromtimestamp(row_dict['end_timestamp']/1000).isoformat() if row_dict['end_timestamp'] else None
                if row_dict.get('earliest_timestamp'):
                    row_dict['earliest_date'] = datetime.fromtimestamp(row_dict['earliest_timestamp']/1000).isoformat() if row_dict['earliest_timestamp'] else None
                if row_dict.get('latest_timestamp'):
                    row_dict['latest_date'] = datetime.fromtimestamp(row_dict['latest_timestamp']/1000).isoformat() if row_dict['latest_timestamp'] else None
            
            data_info.append(row_dict)
        
        # 🔢 计算汇总统计信息
        summary_stats = _calculate_summary_statistics(data_info, data_type, symbol)
        
        return {
            "success": True,
            "data": {
                "data_type": data_type,
                "exchange": exchange,
                "symbol": symbol,
                "query_result": data_info,
                "total_symbols": len(data_info) if not symbol else 1,
                "summary": summary_stats
            }
        }
        
    except Exception as e:
        logger.error(f"查询数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeframes")
async def get_available_timeframes(
    symbol: str,
    exchange: str = 'okx',
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定交易对的可用时间框架"""
    try:
        query = text("""
        SELECT 
            timeframe,
            MIN(timestamp) as start_date,
            MAX(timestamp) as end_date,
            COUNT(*) as record_count
        FROM market_data 
        WHERE exchange = :exchange AND symbol = :symbol
        GROUP BY timeframe
        ORDER BY 
            CASE timeframe 
                WHEN '1m' THEN 1 WHEN '5m' THEN 2 WHEN '15m' THEN 3 
                WHEN '30m' THEN 4 WHEN '1h' THEN 5 WHEN '2h' THEN 6 
                WHEN '4h' THEN 7 WHEN '1d' THEN 8 WHEN '1w' THEN 9 
                ELSE 99 END
        """)
        
        result = await db.execute(query, {"exchange": exchange, "symbol": symbol})
        rows = result.fetchall()
        
        timeframes_data = []
        for row in rows:
            timeframes_data.append({
                "timeframe": row.timeframe,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "end_date": row.end_date.isoformat() if row.end_date else None,
                "record_count": row.record_count
            })
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "exchange": exchange,
                "timeframes": timeframes_data
            }
        }
        
    except Exception as e:
        logger.error(f"获取时间框架失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _estimate_completion_time(task) -> Optional[str]:
    """估算任务完成时间"""
    try:
        if task.status != TaskStatus.RUNNING or task.progress <= 0:
            return None
        
        elapsed_time = (datetime.now() - task.started_at).total_seconds()
        remaining_progress = 100 - task.progress
        estimated_remaining_seconds = (elapsed_time / task.progress) * remaining_progress
        
        estimated_completion = datetime.now() + timedelta(seconds=estimated_remaining_seconds)
        return estimated_completion.isoformat()
        
    except Exception:
        return None

def _get_quality_grade(quality_score: float) -> str:
    """根据质量评分获取等级"""
    if quality_score >= 95:
        return "优秀"
    elif quality_score >= 85:
        return "良好"
    elif quality_score >= 70:
        return "一般"
    elif quality_score >= 50:
        return "较差"
    else:
        return "很差"

def _get_quality_recommendations(quality_score: float, quality_issues: List[str]) -> List[str]:
    """根据质量评分和问题生成建议"""
    recommendations = []
    
    if quality_score < 95:
        recommendations.append("建议使用增强版下载器重新下载数据")
    
    if "数据不完整" in str(quality_issues):
        recommendations.append("使用数据修复功能补全缺失的数据")
    
    if "时间间隙" in str(quality_issues):
        recommendations.append("检查网络连接和API限流设置")
    
    if "价格异常" in str(quality_issues):
        recommendations.append("验证数据源和格式转换逻辑")
    
    if not recommendations:
        recommendations.append("数据质量良好，无需特殊处理")
    
    return recommendations