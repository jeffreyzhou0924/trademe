"""
Webhook回调处理系统 - 处理区块链和第三方服务的回调通知
"""

import asyncio
import json
import hashlib
import hmac
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request, HTTPException

from app.database import AsyncSessionLocal
from app.config import settings
from app.models.payment import USDTPaymentOrder, BlockchainTransaction, WebhookLog
from app.services.payment_order_processor import payment_order_processor
from app.services.blockchain_monitor_service import blockchain_monitor_service
import logging

logger = logging.getLogger(__name__)


class WebhookType(str, Enum):
    """Webhook类型枚举"""
    TRON_TRANSACTION = "tron_transaction"          # TRON交易通知
    ETHEREUM_TRANSACTION = "ethereum_transaction"  # Ethereum交易通知
    BINANCE_PAYMENT = "binance_payment"           # Binance支付通知
    CUSTOM_CALLBACK = "custom_callback"           # 自定义回调
    SYSTEM_NOTIFICATION = "system_notification"   # 系统通知


class WebhookStatus(str, Enum):
    """Webhook处理状态"""
    RECEIVED = "received"      # 已接收
    PROCESSING = "processing"  # 处理中
    PROCESSED = "processed"    # 已处理
    FAILED = "failed"         # 处理失败
    IGNORED = "ignored"       # 已忽略


@dataclass
class WebhookEvent:
    """Webhook事件数据"""
    type: WebhookType
    source: str
    event_id: str
    timestamp: datetime
    data: Dict[str, Any]
    signature: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class WebhookResult:
    """Webhook处理结果"""
    event_id: str
    status: WebhookStatus
    message: str
    processing_time: float
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class WebhookSecurityValidator:
    """Webhook安全验证器"""
    
    def __init__(self):
        self.tron_webhook_secret = settings.tron_api_key  # 使用TRON API密钥作为签名密钥
        self.ethereum_webhook_secret = settings.ethereum_api_key  # 使用Ethereum API密钥
        self.custom_webhook_secret = "trademe_webhook_secret_2024"  # 自定义webhook密钥
    
    def verify_tron_signature(self, payload: str, signature: str) -> bool:
        """验证TRON webhook签名"""
        try:
            if not self.tron_webhook_secret:
                logger.warning("TRON webhook密钥未配置，跳过签名验证")
                return True
            
            expected_signature = hmac.new(
                self.tron_webhook_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"TRON签名验证失败: {e}")
            return False
    
    def verify_ethereum_signature(self, payload: str, signature: str) -> bool:
        """验证Ethereum webhook签名"""
        try:
            if not self.ethereum_webhook_secret:
                logger.warning("Ethereum webhook密钥未配置，跳过签名验证")
                return True
            
            expected_signature = hmac.new(
                self.ethereum_webhook_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Ethereum签名验证失败: {e}")
            return False
    
    def verify_custom_signature(self, payload: str, signature: str) -> bool:
        """验证自定义webhook签名"""
        try:
            expected_signature = hmac.new(
                self.custom_webhook_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"自定义签名验证失败: {e}")
            return False


class WebhookHandler:
    """Webhook处理器 - 统一处理各种回调通知"""
    
    def __init__(self):
        self.security_validator = WebhookSecurityValidator()
        self.event_handlers: Dict[WebhookType, Callable] = {}
        self.processing_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.is_running = False
        
        # 处理统计
        self.total_received = 0
        self.total_processed = 0
        self.total_failed = 0
        
        # 注册默认处理器
        self._register_default_handlers()
        
        logger.info("Webhook处理器初始化完成")
    
    def _register_default_handlers(self):
        """注册默认事件处理器"""
        self.event_handlers[WebhookType.TRON_TRANSACTION] = self._handle_tron_transaction
        self.event_handlers[WebhookType.ETHEREUM_TRANSACTION] = self._handle_ethereum_transaction
        self.event_handlers[WebhookType.BINANCE_PAYMENT] = self._handle_binance_payment
        self.event_handlers[WebhookType.CUSTOM_CALLBACK] = self._handle_custom_callback
        self.event_handlers[WebhookType.SYSTEM_NOTIFICATION] = self._handle_system_notification
    
    async def start_handler(self):
        """启动Webhook处理器"""
        if self.is_running:
            logger.warning("Webhook处理器已在运行中")
            return
        
        self.is_running = True
        logger.info("启动Webhook处理器")
        
        # 启动处理循环
        asyncio.create_task(self._processing_loop())
    
    async def stop_handler(self):
        """停止Webhook处理器"""
        self.is_running = False
        logger.info("Webhook处理器已停止")
    
    async def process_webhook(self, request: Request, webhook_type: WebhookType) -> Dict[str, Any]:
        """处理incoming webhook请求"""
        start_time = datetime.utcnow()
        
        try:
            # 获取请求数据
            body = await request.body()
            payload = body.decode('utf-8')
            headers = dict(request.headers)
            
            # 解析JSON数据
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")
            
            # 生成事件ID
            event_id = self._generate_event_id(webhook_type, data)
            
            # 安全验证
            signature = headers.get('x-signature') or headers.get('signature')
            if not self._verify_webhook_signature(webhook_type, payload, signature):
                logger.warning(f"Webhook签名验证失败: {event_id}")
                raise HTTPException(status_code=403, detail="Invalid signature")
            
            # 创建事件对象
            event = WebhookEvent(
                type=webhook_type,
                source=headers.get('user-agent', 'unknown'),
                event_id=event_id,
                timestamp=start_time,
                data=data,
                signature=signature,
                headers=headers
            )
            
            # 添加到处理队列
            try:
                self.processing_queue.put_nowait(event)
                self.total_received += 1
            except asyncio.QueueFull:
                logger.error("Webhook处理队列已满，丢弃事件")
                raise HTTPException(status_code=503, detail="Processing queue is full")
            
            # 记录Webhook日志
            await self._log_webhook_event(event, WebhookStatus.RECEIVED)
            
            logger.info(f"接收Webhook事件: {event_id} ({webhook_type.value})")
            
            return {
                "status": "received",
                "event_id": event_id,
                "timestamp": start_time.isoformat(),
                "message": "Webhook event queued for processing"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理Webhook请求失败: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def get_webhook_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取Webhook事件处理状态"""
        try:
            async with AsyncSessionLocal() as session:
                query = select(WebhookLog).where(WebhookLog.event_id == event_id)
                result = await session.execute(query)
                log = result.scalar_one_or_none()
                
                if not log:
                    return None
                
                return {
                    "event_id": log.event_id,
                    "type": log.webhook_type,
                    "status": log.status,
                    "message": log.message,
                    "created_at": log.created_at.isoformat(),
                    "processed_at": log.processed_at.isoformat() if log.processed_at else None,
                    "processing_time": log.processing_time,
                    "error": log.error,
                    "retry_count": log.retry_count
                }
                
        except Exception as e:
            logger.error(f"获取Webhook状态失败 {event_id}: {e}")
            return None
    
    async def get_handler_statistics(self) -> Dict[str, Any]:
        """获取处理器统计信息"""
        async with AsyncSessionLocal() as session:
            # 统计各种状态的事件数量
            status_stats = {}
            for status in WebhookStatus:
                query = select(func.count(WebhookLog.id)).where(
                    WebhookLog.status == status.value
                )
                result = await session.execute(query)
                count = result.scalar()
                status_stats[status.value] = count
            
            # 统计今日事件
            today = datetime.utcnow().date()
            today_query = select(func.count(WebhookLog.id)).where(
                func.date(WebhookLog.created_at) == today
            )
            today_result = await session.execute(today_query)
            today_events = today_result.scalar()
        
        return {
            "status_distribution": status_stats,
            "queue_size": self.processing_queue.qsize(),
            "today_events": today_events,
            "total_received": self.total_received,
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "success_rate": (
                (self.total_processed / max(self.total_received, 1)) * 100
                if self.total_received > 0 else 0
            ),
            "is_running": self.is_running
        }
    
    async def _processing_loop(self):
        """事件处理主循环"""
        while self.is_running:
            try:
                # 等待事件 (超时2秒继续循环)
                try:
                    event = await asyncio.wait_for(
                        self.processing_queue.get(),
                        timeout=2.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 处理事件
                await self._process_webhook_event(event)
                
            except Exception as e:
                logger.error(f"事件处理循环错误: {e}")
                await asyncio.sleep(1)
    
    async def _process_webhook_event(self, event: WebhookEvent):
        """处理单个Webhook事件"""
        start_time = datetime.utcnow()
        
        try:
            # 更新状态为处理中
            await self._update_webhook_status(
                event.event_id,
                WebhookStatus.PROCESSING,
                "开始处理事件"
            )
            
            # 获取对应的处理器
            handler = self.event_handlers.get(event.type)
            if not handler:
                await self._update_webhook_status(
                    event.event_id,
                    WebhookStatus.FAILED,
                    f"未找到类型 {event.type.value} 的处理器"
                )
                return
            
            # 执行处理器
            result = await handler(event)
            
            # 计算处理时间
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # 更新处理结果
            if result.get('success', False):
                await self._update_webhook_status(
                    event.event_id,
                    WebhookStatus.PROCESSED,
                    result.get('message', '处理成功'),
                    processing_time,
                    result.get('data')
                )
                self.total_processed += 1
                logger.info(f"Webhook事件处理成功: {event.event_id}")
            else:
                await self._update_webhook_status(
                    event.event_id,
                    WebhookStatus.FAILED,
                    result.get('message', '处理失败'),
                    processing_time,
                    error=result.get('error')
                )
                self.total_failed += 1
                logger.warning(f"Webhook事件处理失败: {event.event_id} - {result.get('error')}")
                
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            await self._update_webhook_status(
                event.event_id,
                WebhookStatus.FAILED,
                "处理过程中发生异常",
                processing_time,
                error=str(e)
            )
            self.total_failed += 1
            logger.error(f"Webhook事件处理异常 {event.event_id}: {e}")
    
    # 具体事件处理器
    async def _handle_tron_transaction(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理TRON交易通知"""
        try:
            data = event.data
            
            # 解析TRON交易数据
            transaction_hash = data.get('transaction_id') or data.get('txid')
            to_address = data.get('to_address') or data.get('to')
            from_address = data.get('from_address') or data.get('from')
            amount_str = data.get('value') or data.get('amount')
            contract_address = data.get('contract_address')
            
            if not all([transaction_hash, to_address, amount_str]):
                return {
                    "success": False,
                    "message": "TRON交易数据不完整",
                    "error": "Missing required fields: transaction_id, to_address, amount"
                }
            
            # 验证是否是USDT合约
            if contract_address != settings.tron_usdt_contract:
                return {
                    "success": False,
                    "message": "非USDT合约交易，忽略处理",
                    "error": f"Contract address mismatch: {contract_address}"
                }
            
            # 转换金额 (TRON USDT使用6位小数)
            amount = Decimal(amount_str) / (10 ** 6)
            
            # 处理交易
            success = await payment_order_processor.process_blockchain_transaction(
                transaction_hash=transaction_hash,
                to_address=to_address,
                amount=amount,
                network="TRC20"
            )
            
            return {
                "success": success,
                "message": "TRON交易处理完成" if success else "未找到匹配的订单",
                "data": {
                    "transaction_hash": transaction_hash,
                    "amount": float(amount),
                    "network": "TRC20"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": "TRON交易处理失败",
                "error": str(e)
            }
    
    async def _handle_ethereum_transaction(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理Ethereum交易通知"""
        try:
            data = event.data
            
            # 解析Ethereum交易数据
            transaction_hash = data.get('hash') or data.get('transactionHash')
            to_address = data.get('to') or data.get('toAddress')
            from_address = data.get('from') or data.get('fromAddress')
            amount_str = data.get('value') or data.get('amount')
            contract_address = data.get('contractAddress')
            
            if not all([transaction_hash, to_address, amount_str]):
                return {
                    "success": False,
                    "message": "Ethereum交易数据不完整",
                    "error": "Missing required fields: hash, to, amount"
                }
            
            # 验证是否是USDT合约
            if contract_address and contract_address.lower() != settings.ethereum_usdt_contract.lower():
                return {
                    "success": False,
                    "message": "非USDT合约交易，忽略处理",
                    "error": f"Contract address mismatch: {contract_address}"
                }
            
            # 转换金额 (Ethereum USDT使用6位小数)
            amount = Decimal(amount_str) / (10 ** 6)
            
            # 处理交易
            success = await payment_order_processor.process_blockchain_transaction(
                transaction_hash=transaction_hash,
                to_address=to_address,
                amount=amount,
                network="ERC20"
            )
            
            return {
                "success": success,
                "message": "Ethereum交易处理完成" if success else "未找到匹配的订单",
                "data": {
                    "transaction_hash": transaction_hash,
                    "amount": float(amount),
                    "network": "ERC20"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": "Ethereum交易处理失败",
                "error": str(e)
            }
    
    async def _handle_binance_payment(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理Binance支付通知"""
        # TODO: 实现Binance支付处理逻辑
        return {
            "success": False,
            "message": "Binance支付处理暂未实现",
            "error": "Handler not implemented"
        }
    
    async def _handle_custom_callback(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理自定义回调"""
        try:
            data = event.data
            callback_type = data.get('type')
            
            if callback_type == 'payment_confirmation':
                # 处理支付确认回调
                order_no = data.get('order_no')
                status = data.get('status')
                
                if order_no and status:
                    # 可以在这里添加自定义的订单状态更新逻辑
                    logger.info(f"接收到订单 {order_no} 的状态更新: {status}")
            
            return {
                "success": True,
                "message": "自定义回调处理完成",
                "data": data
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": "自定义回调处理失败",
                "error": str(e)
            }
    
    async def _handle_system_notification(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理系统通知"""
        try:
            data = event.data
            
            # 可以在这里添加系统通知处理逻辑
            notification_type = data.get('type')
            message = data.get('message')
            
            logger.info(f"系统通知: {notification_type} - {message}")
            
            return {
                "success": True,
                "message": "系统通知处理完成",
                "data": data
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": "系统通知处理失败",
                "error": str(e)
            }
    
    def _verify_webhook_signature(
        self, 
        webhook_type: WebhookType, 
        payload: str, 
        signature: Optional[str]
    ) -> bool:
        """验证Webhook签名"""
        if not signature:
            logger.warning(f"缺少签名，跳过验证: {webhook_type.value}")
            return True  # 在开发环境可以跳过签名验证
        
        if webhook_type == WebhookType.TRON_TRANSACTION:
            return self.security_validator.verify_tron_signature(payload, signature)
        elif webhook_type == WebhookType.ETHEREUM_TRANSACTION:
            return self.security_validator.verify_ethereum_signature(payload, signature)
        else:
            return self.security_validator.verify_custom_signature(payload, signature)
    
    def _generate_event_id(self, webhook_type: WebhookType, data: Dict[str, Any]) -> str:
        """生成事件ID"""
        # 基于webhook类型、时间戳和数据哈希生成唯一ID
        timestamp = datetime.utcnow().isoformat()
        data_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return f"{webhook_type.value}_{timestamp}_{data_hash[:8]}"
    
    async def _log_webhook_event(self, event: WebhookEvent, status: WebhookStatus):
        """记录Webhook事件日志"""
        try:
            async with AsyncSessionLocal() as session:
                webhook_log = WebhookLog(
                    event_id=event.event_id,
                    webhook_type=event.type.value,
                    source=event.source,
                    status=status.value,
                    payload=json.dumps(event.data),
                    headers=json.dumps(event.headers) if event.headers else None,
                    signature=event.signature,
                    created_at=event.timestamp
                )
                
                session.add(webhook_log)
                await session.commit()
                
        except Exception as e:
            logger.error(f"记录Webhook日志失败: {e}")
    
    async def _update_webhook_status(
        self, 
        event_id: str, 
        status: WebhookStatus,
        message: str,
        processing_time: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """更新Webhook状态"""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(WebhookLog)
                    .where(WebhookLog.event_id == event_id)
                    .values(
                        status=status.value,
                        message=message,
                        processing_time=processing_time,
                        processed_at=datetime.utcnow() if status in [WebhookStatus.PROCESSED, WebhookStatus.FAILED] else None,
                        result_data=json.dumps(data) if data else None,
                        error=error,
                        updated_at=datetime.utcnow()
                    )
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"更新Webhook状态失败: {e}")


# 全局Webhook处理器实例
webhook_handler = WebhookHandler()


# 便捷函数
async def start_webhook_handler():
    """启动Webhook处理器"""
    await webhook_handler.start_handler()


async def stop_webhook_handler():
    """停止Webhook处理器"""
    await webhook_handler.stop_handler()


async def process_incoming_webhook(request: Request, webhook_type: WebhookType) -> Dict[str, Any]:
    """处理incoming webhook"""
    return await webhook_handler.process_webhook(request, webhook_type)


if __name__ == "__main__":
    """测试代码"""
    import asyncio
    
    async def test_webhook_handler():
        """测试Webhook处理器"""
        print("=== 测试Webhook处理器 ===")
        
        try:
            # 创建测试事件
            test_event = WebhookEvent(
                type=WebhookType.CUSTOM_CALLBACK,
                source="test",
                event_id="test_event_001",
                timestamp=datetime.utcnow(),
                data={
                    "type": "payment_confirmation",
                    "order_no": "TEST123456789",
                    "status": "confirmed"
                }
            )
            
            print(f"测试事件: {test_event.event_id}")
            
            # 测试处理器统计
            stats = await webhook_handler.get_handler_statistics()
            print(f"处理器统计: {stats}")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    # 运行测试
    asyncio.run(test_webhook_handler())