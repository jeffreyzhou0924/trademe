"""
Webhook回调API端点 - 接收和处理各种webhook通知
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.core.rbac import require_auth, get_current_user_from_token
from app.services.webhook_handler import (
    webhook_handler,
    WebhookType,
    process_incoming_webhook,
    start_webhook_handler,
    stop_webhook_handler
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic模型定义
class WebhookStatusResponse(BaseModel):
    """Webhook状态响应模型"""
    event_id: str
    type: str
    status: str
    message: str
    created_at: str
    processed_at: Optional[str]
    processing_time: Optional[float]
    error: Optional[str]
    retry_count: int


# Webhook接收端点 - 不需要认证，公开接收
@router.post("/tron/transaction", summary="接收TRON交易Webhook")
async def receive_tron_webhook(request: Request):
    """
    接收TRON网络的交易通知Webhook
    
    **用途**: TronGrid等服务推送交易确认通知
    **格式**: TRON标准webhook数据格式
    **验证**: HMAC-SHA256签名验证
    """
    try:
        result = await process_incoming_webhook(request, WebhookType.TRON_TRANSACTION)
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except HTTPException as e:
        logger.warning(f"TRON Webhook处理失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"TRON Webhook异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


@router.post("/ethereum/transaction", summary="接收Ethereum交易Webhook")
async def receive_ethereum_webhook(request: Request):
    """
    接收Ethereum网络的交易通知Webhook
    
    **用途**: Infura、Alchemy等服务推送交易确认通知
    **格式**: Ethereum标准webhook数据格式
    **验证**: HMAC-SHA256签名验证
    """
    try:
        result = await process_incoming_webhook(request, WebhookType.ETHEREUM_TRANSACTION)
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except HTTPException as e:
        logger.warning(f"Ethereum Webhook处理失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Ethereum Webhook异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


@router.post("/binance/payment", summary="接收Binance支付Webhook")
async def receive_binance_webhook(request: Request):
    """
    接收Binance支付服务的Webhook通知
    
    **用途**: Binance Pay等支付服务状态更新
    **格式**: Binance标准webhook数据格式
    **验证**: Binance签名验证
    """
    try:
        result = await process_incoming_webhook(request, WebhookType.BINANCE_PAYMENT)
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except HTTPException as e:
        logger.warning(f"Binance Webhook处理失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Binance Webhook异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


@router.post("/custom/callback", summary="接收自定义回调Webhook")
async def receive_custom_webhook(request: Request):
    """
    接收自定义回调Webhook
    
    **用途**: 第三方服务或内部系统的回调通知
    **格式**: 自定义JSON格式
    **验证**: 自定义签名验证
    """
    try:
        result = await process_incoming_webhook(request, WebhookType.CUSTOM_CALLBACK)
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except HTTPException as e:
        logger.warning(f"自定义Webhook处理失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"自定义Webhook异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


@router.post("/system/notification", summary="接收系统通知Webhook")
async def receive_system_webhook(request: Request):
    """
    接收系统通知Webhook
    
    **用途**: 内部系统间通知，监控告警等
    **格式**: 标准系统通知格式
    **验证**: 系统内部签名验证
    """
    try:
        result = await process_incoming_webhook(request, WebhookType.SYSTEM_NOTIFICATION)
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except HTTPException as e:
        logger.warning(f"系统Webhook处理失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"系统Webhook异常: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


# 管理和查询端点 - 需要认证
@router.get("/status/{event_id}", response_model=Dict[str, Any], summary="查询Webhook事件状态")
async def get_webhook_status(
    event_id: str,
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    查询指定Webhook事件的处理状态
    
    - **event_id**: Webhook事件ID
    
    **返回**: 事件的详细状态信息
    """
    try:
        status = await webhook_handler.get_webhook_status(event_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Webhook事件不存在")
        
        return {
            "success": True,
            "data": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询Webhook状态失败: {e}")
        raise HTTPException(status_code=500, detail="查询失败")


@router.get("/statistics", response_model=Dict[str, Any], summary="获取Webhook处理统计")
@require_auth(roles=['admin'])
async def get_webhook_statistics(
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    获取Webhook处理器的统计信息 (管理员专用)
    
    **返回**: 详细的处理统计数据
    """
    try:
        stats = await webhook_handler.get_handler_statistics()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取Webhook统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计失败")


@router.post("/admin/start", response_model=Dict[str, Any], summary="启动Webhook处理器")
@require_auth(roles=['admin'])
async def start_webhook_handler_api(
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    手动启动Webhook处理器 (管理员专用)
    
    **用途**: 系统维护后重新启动处理器
    """
    try:
        await start_webhook_handler()
        
        logger.info(f"管理员 {current_user['user_id']} 启动了Webhook处理器")
        
        return {
            "success": True,
            "message": "Webhook处理器已启动",
            "timestamp": "2024-01-01T00:00:00Z"  # 实际时间戳
        }
        
    except Exception as e:
        logger.error(f"启动Webhook处理器失败: {e}")
        raise HTTPException(status_code=500, detail="启动失败")


@router.post("/admin/stop", response_model=Dict[str, Any], summary="停止Webhook处理器")
@require_auth(roles=['admin'])
async def stop_webhook_handler_api(
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    手动停止Webhook处理器 (管理员专用)
    
    **用途**: 系统维护前停止处理器
    """
    try:
        await stop_webhook_handler()
        
        logger.info(f"管理员 {current_user['user_id']} 停止了Webhook处理器")
        
        return {
            "success": True,
            "message": "Webhook处理器已停止",
            "timestamp": "2024-01-01T00:00:00Z"  # 实际时间戳
        }
        
    except Exception as e:
        logger.error(f"停止Webhook处理器失败: {e}")
        raise HTTPException(status_code=500, detail="停止失败")


@router.get("/health", response_model=Dict[str, Any], summary="Webhook系统健康检查")
async def webhook_health_check():
    """
    Webhook系统健康检查
    
    **返回**: 处理器运行状态和队列信息
    """
    try:
        stats = await webhook_handler.get_handler_statistics()
        
        # 简单的健康判断
        is_healthy = (
            stats.get("is_running", False) and
            stats.get("queue_size", 0) < 800  # 队列不超过80%
        )
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "details": {
                "handler_running": stats.get("is_running", False),
                "queue_size": stats.get("queue_size", 0),
                "queue_capacity": 1000,
                "success_rate": f"{stats.get('success_rate', 0):.2f}%",
                "today_events": stats.get("today_events", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Webhook健康检查失败: {e}")
        return {
            "status": "error",
            "timestamp": "2024-01-01T00:00:00Z",
            "error": str(e)
        }


# 测试端点 - 仅开发环境使用
@router.post("/test/send", response_model=Dict[str, Any], summary="发送测试Webhook")
@require_auth(roles=['admin'])
async def send_test_webhook(
    webhook_type: str,
    test_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    发送测试Webhook事件 (管理员专用，仅开发环境)
    
    - **webhook_type**: Webhook类型
    - **test_data**: 测试数据
    
    **用途**: 测试Webhook处理逻辑
    """
    try:
        # 仅在开发环境允许
        from app.config import settings
        if settings.environment != "development":
            raise HTTPException(status_code=403, detail="仅在开发环境可用")
        
        # 验证webhook类型
        try:
            webhook_type_enum = WebhookType(webhook_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的webhook类型: {webhook_type}")
        
        # 创建测试事件
        from app.services.webhook_handler import WebhookEvent
        from datetime import datetime
        
        test_event = WebhookEvent(
            type=webhook_type_enum,
            source="test_api",
            event_id=f"test_{datetime.utcnow().isoformat()}",
            timestamp=datetime.utcnow(),
            data=test_data
        )
        
        # 添加到处理队列
        webhook_handler.processing_queue.put_nowait(test_event)
        
        logger.info(f"管理员 {current_user['user_id']} 发送测试Webhook: {test_event.event_id}")
        
        return {
            "success": True,
            "message": "测试Webhook已发送",
            "data": {
                "event_id": test_event.event_id,
                "type": webhook_type,
                "queued_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送测试Webhook失败: {e}")
        raise HTTPException(status_code=500, detail="发送失败")