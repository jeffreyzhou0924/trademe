"""
批量操作服务 - 高效的用户批量操作处理
提供用户批量更新、标签分配、通知发送等批量操作功能，支持异步处理和进度跟踪
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_management import (
    UserTag, UserTagAssignment, UserActivityLog, ActivityType
)
from app.services.user_management_service import UserManagementService
from app.services.notification_service import NotificationService, NotificationRecipient, NotificationChannel
from app.services.smart_tagging_service import SmartTaggingService
from app.services.user_behavior_analysis_service import UserBehaviorAnalysisService
from app.core.exceptions import UserManagementError

logger = logging.getLogger(__name__)


class BatchOperationType(Enum):
    """批量操作类型"""
    UPDATE_USERS = "update_users"
    ASSIGN_TAGS = "assign_tags"
    REMOVE_TAGS = "remove_tags"
    SEND_NOTIFICATIONS = "send_notifications"
    AUTO_TAG_ANALYSIS = "auto_tag_analysis"
    BEHAVIOR_ANALYSIS = "behavior_analysis"
    DEACTIVATE_USERS = "deactivate_users"
    EXPORT_USERS = "export_users"


class BatchOperationStatus(Enum):
    """批量操作状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchOperationProgress:
    """批量操作进度"""
    operation_id: str
    operation_type: BatchOperationType
    status: BatchOperationStatus
    total_items: int
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    current_item: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    progress_percentage: float = 0.0
    logs: List[str] = field(default_factory=list)


@dataclass
class BatchOperationConfig:
    """批量操作配置"""
    batch_size: int = 50
    max_concurrent: int = 10
    delay_between_batches: float = 0.1
    timeout_per_item: int = 30
    retry_failed_items: bool = True
    max_retries: int = 3
    enable_progress_callback: bool = True
    send_completion_notification: bool = True


class BatchOperationsService:
    """批量操作服务"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.user_management_service = UserManagementService(db_session)
        self.notification_service = NotificationService(db_session)
        self.smart_tagging_service = SmartTaggingService(db_session)
        self.behavior_analysis_service = UserBehaviorAnalysisService(db_session)
        
        # 操作进度跟踪
        self.active_operations: Dict[str, BatchOperationProgress] = {}
        
    async def batch_update_users(
        self,
        user_ids: List[int],
        updates: Dict[str, Any],
        admin_id: Optional[int] = None,
        config: Optional[BatchOperationConfig] = None
    ) -> str:
        """批量更新用户信息"""
        
        operation_id = str(uuid4())
        config = config or BatchOperationConfig()
        
        # 创建进度跟踪
        progress = BatchOperationProgress(
            operation_id=operation_id,
            operation_type=BatchOperationType.UPDATE_USERS,
            status=BatchOperationStatus.PENDING,
            total_items=len(user_ids),
            started_at=datetime.utcnow()
        )
        self.active_operations[operation_id] = progress
        
        # 启动异步任务
        asyncio.create_task(
            self._execute_batch_user_updates(operation_id, user_ids, updates, admin_id, config)
        )
        
        return operation_id
    
    async def _execute_batch_user_updates(
        self,
        operation_id: str,
        user_ids: List[int],
        updates: Dict[str, Any],
        admin_id: Optional[int],
        config: BatchOperationConfig
    ):
        """执行批量用户更新"""
        
        progress = self.active_operations[operation_id]
        progress.status = BatchOperationStatus.RUNNING
        
        try:
            successful_updates = []
            failed_updates = []
            
            # 分批处理用户
            for i in range(0, len(user_ids), config.batch_size):
                if progress.status == BatchOperationStatus.CANCELLED:
                    break
                    
                batch_user_ids = user_ids[i:i + config.batch_size]
                progress.current_item = f"处理用户批次 {i//config.batch_size + 1}"
                
                try:
                    # 执行批量更新
                    batch_result = await self.user_management_service.batch_update_users(
                        user_ids=batch_user_ids,
                        updates=updates,
                        updated_by=admin_id
                    )
                    
                    successful_updates.extend(batch_result['successful_user_ids'])
                    failed_updates.extend(batch_result['failed_updates'])
                    
                    # 更新进度
                    progress.processed_items += len(batch_user_ids)
                    progress.successful_items = len(successful_updates)
                    progress.failed_items = len(failed_updates)
                    progress.progress_percentage = (progress.processed_items / progress.total_items) * 100
                    
                    progress.logs.append(
                        f"批次 {i//config.batch_size + 1}: 成功 {batch_result['successful_count']}, 失败 {batch_result['failed_count']}"
                    )
                    
                    # 批次间延迟
                    if config.delay_between_batches > 0:
                        await asyncio.sleep(config.delay_between_batches)
                        
                except Exception as e:
                    error_msg = f"批次 {i//config.batch_size + 1} 处理失败: {str(e)}"
                    progress.logs.append(error_msg)
                    logger.error(error_msg)
                    
                    # 将整个批次标记为失败
                    for user_id in batch_user_ids:
                        failed_updates.append({
                            "user_id": user_id,
                            "error": str(e)
                        })
                    
                    progress.processed_items += len(batch_user_ids)
                    progress.failed_items = len(failed_updates)
            
            # 完成操作
            progress.status = BatchOperationStatus.COMPLETED
            progress.completed_at = datetime.utcnow()
            progress.progress_percentage = 100.0
            
            final_log = f"批量更新完成: 总计 {len(user_ids)}, 成功 {len(successful_updates)}, 失败 {len(failed_updates)}"
            progress.logs.append(final_log)
            
            logger.info(f"批量操作完成: {operation_id} - {final_log}")
            
            # 发送完成通知 (如果配置了管理员ID)
            if config.send_completion_notification and admin_id:
                await self._send_operation_completion_notification(operation_id, admin_id)
                
        except Exception as e:
            progress.status = BatchOperationStatus.FAILED
            progress.error_message = str(e)
            progress.completed_at = datetime.utcnow()
            progress.logs.append(f"操作失败: {str(e)}")
            logger.error(f"批量操作失败: {operation_id} - {str(e)}")
    
    async def batch_assign_tags(
        self,
        user_ids: List[int],
        tag_ids: List[int],
        admin_id: Optional[int] = None,
        assigned_reason: Optional[str] = None,
        config: Optional[BatchOperationConfig] = None
    ) -> str:
        """批量分配标签"""
        
        operation_id = str(uuid4())
        config = config or BatchOperationConfig()
        
        progress = BatchOperationProgress(
            operation_id=operation_id,
            operation_type=BatchOperationType.ASSIGN_TAGS,
            status=BatchOperationStatus.PENDING,
            total_items=len(user_ids) * len(tag_ids),
            started_at=datetime.utcnow()
        )
        self.active_operations[operation_id] = progress
        
        asyncio.create_task(
            self._execute_batch_tag_assignment(operation_id, user_ids, tag_ids, admin_id, assigned_reason, config)
        )
        
        return operation_id
    
    async def _execute_batch_tag_assignment(
        self,
        operation_id: str,
        user_ids: List[int],
        tag_ids: List[int],
        admin_id: Optional[int],
        assigned_reason: Optional[str],
        config: BatchOperationConfig
    ):
        """执行批量标签分配"""
        
        progress = self.active_operations[operation_id]
        progress.status = BatchOperationStatus.RUNNING
        
        try:
            # 使用现有的批量分配方法
            result = await self.user_management_service.batch_assign_tags(
                user_ids=user_ids,
                tag_ids=tag_ids,
                assigned_by=admin_id,
                assigned_reason=assigned_reason
            )
            
            # 更新进度
            progress.processed_items = result['total_requested']
            progress.successful_items = result['successful_count']
            progress.failed_items = result['failed_count']
            progress.progress_percentage = 100.0
            progress.status = BatchOperationStatus.COMPLETED
            progress.completed_at = datetime.utcnow()
            
            final_log = f"批量标签分配完成: 总计 {result['total_requested']}, 成功 {result['successful_count']}, 失败 {result['failed_count']}"
            progress.logs.append(final_log)
            
            logger.info(f"批量标签分配完成: {operation_id} - {final_log}")
            
        except Exception as e:
            progress.status = BatchOperationStatus.FAILED
            progress.error_message = str(e)
            progress.completed_at = datetime.utcnow()
            progress.logs.append(f"操作失败: {str(e)}")
            logger.error(f"批量标签分配失败: {operation_id} - {str(e)}")
    
    async def batch_send_notifications(
        self,
        user_ids: List[int],
        template_name: str,
        template_vars: Union[Dict[str, Any], List[Dict[str, Any]]],
        channel: Optional[NotificationChannel] = None,
        config: Optional[BatchOperationConfig] = None
    ) -> str:
        """批量发送通知"""
        
        operation_id = str(uuid4())
        config = config or BatchOperationConfig()
        
        progress = BatchOperationProgress(
            operation_id=operation_id,
            operation_type=BatchOperationType.SEND_NOTIFICATIONS,
            status=BatchOperationStatus.PENDING,
            total_items=len(user_ids),
            started_at=datetime.utcnow()
        )
        self.active_operations[operation_id] = progress
        
        asyncio.create_task(
            self._execute_batch_notifications(operation_id, user_ids, template_name, template_vars, channel, config)
        )
        
        return operation_id
    
    async def _execute_batch_notifications(
        self,
        operation_id: str,
        user_ids: List[int],
        template_name: str,
        template_vars: Union[Dict[str, Any], List[Dict[str, Any]]],
        channel: Optional[NotificationChannel],
        config: BatchOperationConfig
    ):
        """执行批量通知发送"""
        
        progress = self.active_operations[operation_id]
        progress.status = BatchOperationStatus.RUNNING
        
        try:
            # 获取用户信息和通知接收者列表
            users_query = select(User).where(User.id.in_(user_ids))
            result = await self.db.execute(users_query)
            users = result.scalars().all()
            
            # 创建接收者列表
            recipients = []
            for user in users:
                recipient = NotificationRecipient(
                    user_id=user.id,
                    email=user.email,
                    phone=user.phone,
                    preferred_channels=[channel] if channel else [NotificationChannel.IN_APP, NotificationChannel.EMAIL]
                )
                recipients.append(recipient)
            
            progress.current_item = f"准备发送通知给 {len(recipients)} 个用户"
            progress.logs.append(progress.current_item)
            
            # 使用通知服务批量发送
            notification_result = await self.notification_service.send_batch_notifications(
                template_name=template_name,
                recipients=recipients,
                template_vars=template_vars,
                channel=channel,
                batch_size=config.batch_size
            )
            
            # 更新进度
            progress.processed_items = notification_result['total_recipients']
            progress.successful_items = notification_result['successful_count']
            progress.failed_items = notification_result['failed_count']
            progress.progress_percentage = 100.0
            progress.status = BatchOperationStatus.COMPLETED
            progress.completed_at = datetime.utcnow()
            
            final_log = f"批量通知发送完成: 总计 {notification_result['total_recipients']}, 成功 {notification_result['successful_count']}, 失败 {notification_result['failed_count']}"
            progress.logs.append(final_log)
            
            logger.info(f"批量通知发送完成: {operation_id} - {final_log}")
            
        except Exception as e:
            progress.status = BatchOperationStatus.FAILED
            progress.error_message = str(e)
            progress.completed_at = datetime.utcnow()
            progress.logs.append(f"操作失败: {str(e)}")
            logger.error(f"批量通知发送失败: {operation_id} - {str(e)}")
    
    async def batch_auto_tag_analysis(
        self,
        user_ids: Optional[List[int]] = None,
        admin_id: Optional[int] = None,
        config: Optional[BatchOperationConfig] = None
    ) -> str:
        """批量智能标签分析"""
        
        operation_id = str(uuid4())
        config = config or BatchOperationConfig()
        
        # 如果没有指定用户，获取所有活跃用户
        if not user_ids:
            users_query = select(User.id).where(User.is_active == True)
            result = await self.db.execute(users_query)
            user_ids = [row[0] for row in result.fetchall()]
        
        progress = BatchOperationProgress(
            operation_id=operation_id,
            operation_type=BatchOperationType.AUTO_TAG_ANALYSIS,
            status=BatchOperationStatus.PENDING,
            total_items=len(user_ids),
            started_at=datetime.utcnow()
        )
        self.active_operations[operation_id] = progress
        
        asyncio.create_task(
            self._execute_batch_auto_tagging(operation_id, user_ids, admin_id, config)
        )
        
        return operation_id
    
    async def _execute_batch_auto_tagging(
        self,
        operation_id: str,
        user_ids: List[int],
        admin_id: Optional[int],
        config: BatchOperationConfig
    ):
        """执行批量智能标签分析"""
        
        progress = self.active_operations[operation_id]
        progress.status = BatchOperationStatus.RUNNING
        
        try:
            progress.current_item = "开始智能标签分析"
            progress.logs.append(progress.current_item)
            
            # 使用智能标签服务的批量分析
            analysis_result = await self.smart_tagging_service.batch_auto_tag_users(
                user_ids=user_ids,
                admin_id=admin_id
            )
            
            # 更新进度
            progress.processed_items = analysis_result['total_users_processed']
            progress.successful_items = analysis_result['total_tag_assignments']
            progress.failed_items = analysis_result['total_failures']
            progress.progress_percentage = 100.0
            progress.status = BatchOperationStatus.COMPLETED
            progress.completed_at = datetime.utcnow()
            
            final_log = f"智能标签分析完成: 处理用户 {analysis_result['total_users_processed']}, 分配标签 {analysis_result['total_tag_assignments']}, 失败 {analysis_result['total_failures']}"
            progress.logs.append(final_log)
            
            logger.info(f"批量智能标签分析完成: {operation_id} - {final_log}")
            
        except Exception as e:
            progress.status = BatchOperationStatus.FAILED
            progress.error_message = str(e)
            progress.completed_at = datetime.utcnow()
            progress.logs.append(f"操作失败: {str(e)}")
            logger.error(f"批量智能标签分析失败: {operation_id} - {str(e)}")
    
    async def batch_behavior_analysis(
        self,
        user_ids: Optional[List[int]] = None,
        days_back: int = 30,
        config: Optional[BatchOperationConfig] = None
    ) -> str:
        """批量用户行为分析"""
        
        operation_id = str(uuid4())
        config = config or BatchOperationConfig()
        
        # 如果没有指定用户，获取所有活跃用户
        if not user_ids:
            users_query = select(User.id).where(User.is_active == True)
            result = await self.db.execute(users_query)
            user_ids = [row[0] for row in result.fetchall()]
        
        progress = BatchOperationProgress(
            operation_id=operation_id,
            operation_type=BatchOperationType.BEHAVIOR_ANALYSIS,
            status=BatchOperationStatus.PENDING,
            total_items=len(user_ids),
            started_at=datetime.utcnow()
        )
        self.active_operations[operation_id] = progress
        
        asyncio.create_task(
            self._execute_batch_behavior_analysis(operation_id, user_ids, days_back, config)
        )
        
        return operation_id
    
    async def _execute_batch_behavior_analysis(
        self,
        operation_id: str,
        user_ids: List[int],
        days_back: int,
        config: BatchOperationConfig
    ):
        """执行批量行为分析"""
        
        progress = self.active_operations[operation_id]
        progress.status = BatchOperationStatus.RUNNING
        
        try:
            progress.current_item = "开始批量用户行为分析"
            progress.logs.append(progress.current_item)
            
            # 使用行为分析服务的批量分析
            analysis_result = await self.behavior_analysis_service.batch_analyze_user_behavior(
                user_ids=user_ids,
                days_back=days_back
            )
            
            # 更新进度
            progress.processed_items = analysis_result['total_users']
            progress.successful_items = analysis_result['successful_count']
            progress.failed_items = analysis_result['failed_count']
            progress.progress_percentage = 100.0
            progress.status = BatchOperationStatus.COMPLETED
            progress.completed_at = datetime.utcnow()
            
            final_log = f"批量行为分析完成: 处理用户 {analysis_result['total_users']}, 成功 {analysis_result['successful_count']}, 失败 {analysis_result['failed_count']}"
            progress.logs.append(final_log)
            
            logger.info(f"批量用户行为分析完成: {operation_id} - {final_log}")
            
        except Exception as e:
            progress.status = BatchOperationStatus.FAILED
            progress.error_message = str(e)
            progress.completed_at = datetime.utcnow()
            progress.logs.append(f"操作失败: {str(e)}")
            logger.error(f"批量用户行为分析失败: {operation_id} - {str(e)}")
    
    async def get_operation_progress(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """获取批量操作进度"""
        
        progress = self.active_operations.get(operation_id)
        if not progress:
            return None
        
        # 估算剩余时间
        estimated_completion = None
        if progress.status == BatchOperationStatus.RUNNING and progress.processed_items > 0:
            elapsed_time = (datetime.utcnow() - progress.started_at).total_seconds()
            items_per_second = progress.processed_items / elapsed_time
            remaining_items = progress.total_items - progress.processed_items
            
            if items_per_second > 0:
                remaining_seconds = remaining_items / items_per_second
                estimated_completion = datetime.utcnow() + timedelta(seconds=remaining_seconds)
        
        return {
            "operation_id": progress.operation_id,
            "operation_type": progress.operation_type.value,
            "status": progress.status.value,
            "total_items": progress.total_items,
            "processed_items": progress.processed_items,
            "successful_items": progress.successful_items,
            "failed_items": progress.failed_items,
            "current_item": progress.current_item,
            "progress_percentage": round(progress.progress_percentage, 2),
            "error_message": progress.error_message,
            "started_at": progress.started_at.isoformat() if progress.started_at else None,
            "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
            "estimated_completion": estimated_completion.isoformat() if estimated_completion else None,
            "logs": progress.logs[-10:],  # 最近10条日志
            "total_logs": len(progress.logs)
        }
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """取消批量操作"""
        
        progress = self.active_operations.get(operation_id)
        if not progress or progress.status not in [BatchOperationStatus.PENDING, BatchOperationStatus.RUNNING]:
            return False
        
        progress.status = BatchOperationStatus.CANCELLED
        progress.completed_at = datetime.utcnow()
        progress.logs.append("操作已被取消")
        
        logger.info(f"批量操作已取消: {operation_id}")
        return True
    
    async def cleanup_completed_operations(self, hours_old: int = 24) -> int:
        """清理已完成的操作记录"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        cleaned_count = 0
        
        operations_to_remove = []
        for operation_id, progress in self.active_operations.items():
            if (progress.status in [BatchOperationStatus.COMPLETED, BatchOperationStatus.FAILED, BatchOperationStatus.CANCELLED] 
                and progress.completed_at 
                and progress.completed_at < cutoff_time):
                operations_to_remove.append(operation_id)
        
        for operation_id in operations_to_remove:
            del self.active_operations[operation_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个已完成的批量操作记录")
        
        return cleaned_count
    
    async def get_active_operations_summary(self) -> Dict[str, Any]:
        """获取活跃操作摘要"""
        
        summary = {
            "total_operations": len(self.active_operations),
            "pending_operations": 0,
            "running_operations": 0,
            "completed_operations": 0,
            "failed_operations": 0,
            "cancelled_operations": 0,
            "operations_by_type": {},
            "recent_operations": []
        }
        
        for progress in self.active_operations.values():
            # 状态统计
            if progress.status == BatchOperationStatus.PENDING:
                summary["pending_operations"] += 1
            elif progress.status == BatchOperationStatus.RUNNING:
                summary["running_operations"] += 1
            elif progress.status == BatchOperationStatus.COMPLETED:
                summary["completed_operations"] += 1
            elif progress.status == BatchOperationStatus.FAILED:
                summary["failed_operations"] += 1
            elif progress.status == BatchOperationStatus.CANCELLED:
                summary["cancelled_operations"] += 1
            
            # 类型统计
            op_type = progress.operation_type.value
            if op_type not in summary["operations_by_type"]:
                summary["operations_by_type"][op_type] = 0
            summary["operations_by_type"][op_type] += 1
        
        # 最近的操作 (按开始时间排序)
        recent_ops = sorted(
            self.active_operations.values(),
            key=lambda x: x.started_at or datetime.min,
            reverse=True
        )[:10]
        
        for progress in recent_ops:
            summary["recent_operations"].append({
                "operation_id": progress.operation_id,
                "operation_type": progress.operation_type.value,
                "status": progress.status.value,
                "progress_percentage": round(progress.progress_percentage, 2),
                "started_at": progress.started_at.isoformat() if progress.started_at else None
            })
        
        return summary
    
    async def _send_operation_completion_notification(self, operation_id: str, admin_id: int):
        """发送操作完成通知"""
        
        try:
            progress = self.active_operations.get(operation_id)
            if not progress:
                return
            
            # 获取管理员用户信息
            admin_query = select(User).where(User.id == admin_id)
            result = await self.db.execute(admin_query)
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                return
            
            # 准备通知内容
            operation_name = {
                BatchOperationType.UPDATE_USERS: "用户批量更新",
                BatchOperationType.ASSIGN_TAGS: "批量标签分配", 
                BatchOperationType.SEND_NOTIFICATIONS: "批量通知发送",
                BatchOperationType.AUTO_TAG_ANALYSIS: "智能标签分析",
                BatchOperationType.BEHAVIOR_ANALYSIS: "用户行为分析"
            }.get(progress.operation_type, "批量操作")
            
            status_text = "成功完成" if progress.status == BatchOperationStatus.COMPLETED else "执行失败"
            
            template_vars = {
                "operation_name": operation_name,
                "operation_id": operation_id[:8],  # 短ID
                "status_text": status_text,
                "total_items": progress.total_items,
                "successful_items": progress.successful_items,
                "failed_items": progress.failed_items,
                "duration": str(progress.completed_at - progress.started_at) if progress.completed_at and progress.started_at else "未知"
            }
            
            # 发送应用内通知
            recipient = NotificationRecipient(
                user_id=admin_id,
                email=admin_user.email,
                preferred_channels=[NotificationChannel.IN_APP]
            )
            
            await self.notification_service.send_notification(
                template_name="batch_operation_completed",  # 需要在通知服务中添加这个模板
                recipient=recipient,
                template_vars=template_vars,
                channel=NotificationChannel.IN_APP,
                priority=6
            )
            
        except Exception as e:
            logger.error(f"发送操作完成通知失败: {e}")
            # 不抛出异常，避免影响主流程