"""
通知服务 - 多渠道用户通知管理
支持邮件、应用内、短信、推送等多种通知渠道，提供模板化消息和智能投递
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.user_management import (
    UserNotification, NotificationType, NotificationChannel, NotificationStatus
)
from app.core.exceptions import UserManagementError
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class NotificationTemplate:
    """通知模板"""
    title: str
    content: str
    variables: List[str]  # 模板变量
    channel: NotificationChannel
    notification_type: NotificationType
    priority: int = 5


@dataclass
class NotificationRecipient:
    """通知接收者"""
    user_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    preferred_channels: List[NotificationChannel] = None
    timezone: str = "UTC"
    language: str = "zh-CN"


@dataclass
class NotificationDeliveryResult:
    """通知投递结果"""
    notification_id: int
    user_id: int
    channel: NotificationChannel
    status: NotificationStatus
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None


class NotificationBatchStatus(Enum):
    """批量通知状态"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


class NotificationService:
    """通知服务"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.notification_templates = self._initialize_templates()
        self.max_retry_attempts = 3
        
    def _initialize_templates(self) -> Dict[str, NotificationTemplate]:
        """初始化通知模板"""
        templates = {
            "welcome": NotificationTemplate(
                title="欢迎加入 Trademe！",
                content="亲爱的 {username}，欢迎您加入 Trademe 量化交易平台！开始您的交易之旅吧。",
                variables=["username"],
                channel=NotificationChannel.EMAIL,
                notification_type=NotificationType.SYSTEM,
                priority=8
            ),
            "membership_upgrade": NotificationTemplate(
                title="会员升级成功通知",
                content="恭喜 {username}！您已成功升级到 {membership_level} 会员，享受更多专属权益。",
                variables=["username", "membership_level"],
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.MEMBERSHIP,
                priority=9
            ),
            "strategy_created": NotificationTemplate(
                title="策略创建成功",
                content="您的策略 '{strategy_name}' 已创建成功，可以开始回测了！",
                variables=["strategy_name"],
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.TRADING,
                priority=6
            ),
            "backtest_completed": NotificationTemplate(
                title="回测完成通知",
                content="您的策略 '{strategy_name}' 回测已完成，年化收益率: {annual_return}%",
                variables=["strategy_name", "annual_return"],
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.TRADING,
                priority=7
            ),
            "security_alert": NotificationTemplate(
                title="安全提醒",
                content="检测到您的账户有异常登录，登录IP: {ip_address}，时间: {login_time}",
                variables=["ip_address", "login_time"],
                channel=NotificationChannel.EMAIL,
                notification_type=NotificationType.SECURITY,
                priority=10
            ),
            "password_reset": NotificationTemplate(
                title="密码重置验证",
                content="您正在重置密码，验证码: {verification_code}，5分钟内有效。",
                variables=["verification_code"],
                channel=NotificationChannel.EMAIL,
                notification_type=NotificationType.SECURITY,
                priority=9
            ),
            "activity_reminder": NotificationTemplate(
                title="回来看看吧",
                content="{username}，您已经 {days_inactive} 天没有登录了，快来查看最新的交易策略！",
                variables=["username", "days_inactive"],
                channel=NotificationChannel.EMAIL,
                notification_type=NotificationType.MARKETING,
                priority=4
            ),
            "ai_quota_warning": NotificationTemplate(
                title="AI使用额度提醒",
                content="您本月的AI使用额度即将用完，剩余: ${remaining_quota}",
                variables=["remaining_quota"],
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.SYSTEM,
                priority=7
            ),
            "trade_alert": NotificationTemplate(
                title="交易提醒",
                content="您的策略 '{strategy_name}' 触发了交易信号: {signal_type} {symbol}",
                variables=["strategy_name", "signal_type", "symbol"],
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.TRADING,
                priority=8
            ),
            "system_maintenance": NotificationTemplate(
                title="系统维护通知",
                content="系统将于 {maintenance_time} 进行维护，预计持续 {duration} 小时，请提前安排。",
                variables=["maintenance_time", "duration"],
                channel=NotificationChannel.IN_APP,
                notification_type=NotificationType.SYSTEM,
                priority=8
            )
        }
        return templates
    
    async def send_notification(
        self,
        template_name: str,
        recipient: NotificationRecipient,
        template_vars: Dict[str, Any],
        channel: Optional[NotificationChannel] = None,
        priority: Optional[int] = None,
        expires_at: Optional[datetime] = None
    ) -> NotificationDeliveryResult:
        """发送单个通知"""
        
        try:
            # 获取模板
            template = self.notification_templates.get(template_name)
            if not template:
                raise UserManagementError(f"通知模板 '{template_name}' 不存在")
            
            # 确定发送渠道
            send_channel = channel or template.channel
            if recipient.preferred_channels and send_channel not in recipient.preferred_channels:
                # 如果指定渠道不在用户偏好中，选择用户偏好的第一个渠道
                send_channel = recipient.preferred_channels[0]
            
            # 渲染模板
            rendered_content = self._render_template(template.content, template_vars)
            rendered_title = self._render_template(template.title, template_vars)
            
            # 创建通知记录
            notification = UserNotification(
                user_id=recipient.user_id,
                title=rendered_title,
                content=rendered_content,
                notification_type=template.notification_type,
                channel=send_channel,
                priority=priority or template.priority,
                expires_at=expires_at,
                metadata=json.dumps({
                    'template_name': template_name,
                    'template_vars': template_vars
                })
            )
            
            self.db.add(notification)
            await self.db.flush()  # 获取ID
            
            # 发送通知
            delivery_result = await self._deliver_notification(notification, recipient)
            
            # 更新通知状态
            notification.status = delivery_result.status
            notification.sent_at = datetime.utcnow() if delivery_result.status == NotificationStatus.SENT else None
            notification.delivered_at = delivery_result.delivered_at
            notification.error_message = delivery_result.error_message
            
            await self.db.commit()
            
            delivery_result.notification_id = notification.id
            
            logger.info(f"通知发送完成: user_id={recipient.user_id}, template={template_name}, status={delivery_result.status.value}")
            
            return delivery_result
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"发送通知失败: user_id={recipient.user_id}, template={template_name}, error={e}")
            
            return NotificationDeliveryResult(
                notification_id=0,
                user_id=recipient.user_id,
                channel=channel or NotificationChannel.IN_APP,
                status=NotificationStatus.FAILED,
                error_message=str(e)
            )
    
    def _render_template(self, template_content: str, variables: Dict[str, Any]) -> str:
        """渲染模板内容"""
        try:
            return template_content.format(**variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            logger.warning(f"模板变量缺失: {missing_var}")
            return template_content.replace(f"{{{missing_var}}}", f"[{missing_var}]")
    
    async def _deliver_notification(
        self, 
        notification: UserNotification, 
        recipient: NotificationRecipient
    ) -> NotificationDeliveryResult:
        """实际投递通知"""
        
        try:
            if notification.channel == NotificationChannel.EMAIL:
                success = await self._send_email_notification(notification, recipient)
            elif notification.channel == NotificationChannel.IN_APP:
                success = await self._send_in_app_notification(notification, recipient)
            elif notification.channel == NotificationChannel.SMS:
                success = await self._send_sms_notification(notification, recipient)
            elif notification.channel == NotificationChannel.PUSH:
                success = await self._send_push_notification(notification, recipient)
            else:
                raise UserManagementError(f"不支持的通知渠道: {notification.channel}")
            
            if success:
                return NotificationDeliveryResult(
                    notification_id=notification.id,
                    user_id=recipient.user_id,
                    channel=notification.channel,
                    status=NotificationStatus.SENT,
                    delivered_at=datetime.utcnow()
                )
            else:
                return NotificationDeliveryResult(
                    notification_id=notification.id,
                    user_id=recipient.user_id,
                    channel=notification.channel,
                    status=NotificationStatus.FAILED,
                    error_message="发送失败"
                )
                
        except Exception as e:
            return NotificationDeliveryResult(
                notification_id=notification.id,
                user_id=recipient.user_id,
                channel=notification.channel,
                status=NotificationStatus.FAILED,
                error_message=str(e)
            )
    
    async def _send_email_notification(
        self, 
        notification: UserNotification, 
        recipient: NotificationRecipient
    ) -> bool:
        """发送邮件通知"""
        try:
            if not recipient.email:
                logger.warning(f"用户 {recipient.user_id} 没有邮箱地址")
                return False
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = getattr(settings, 'smtp_from_email', 'noreply@trademe.com')
            msg['To'] = recipient.email
            msg['Subject'] = notification.title
            
            # 添加HTML和纯文本内容
            html_content = f"""
            <html>
                <body>
                    <h2>{notification.title}</h2>
                    <p>{notification.content}</p>
                    <hr>
                    <p><small>Trademe 量化交易平台</small></p>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(notification.content, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 发送邮件 (生产环境需要配置SMTP服务器)
            # 这里是简化版本，实际需要配置真实的SMTP服务
            if hasattr(settings, 'smtp_host') and settings.smtp_host:
                smtp_server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                if hasattr(settings, 'smtp_username'):
                    smtp_server.login(settings.smtp_username, settings.smtp_password)
                smtp_server.send_message(msg)
                smtp_server.quit()
            else:
                # 开发环境：模拟发送成功
                logger.info(f"模拟邮件发送: {recipient.email} - {notification.title}")
            
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    async def _send_in_app_notification(
        self, 
        notification: UserNotification, 
        recipient: NotificationRecipient
    ) -> bool:
        """发送应用内通知"""
        try:
            # 应用内通知主要是数据库记录，前端轮询或WebSocket推送
            # 这里直接返回成功，因为通知已经保存到数据库
            logger.info(f"应用内通知已创建: user_id={recipient.user_id}, title={notification.title}")
            return True
            
        except Exception as e:
            logger.error(f"应用内通知创建失败: {e}")
            return False
    
    async def _send_sms_notification(
        self, 
        notification: UserNotification, 
        recipient: NotificationRecipient
    ) -> bool:
        """发送短信通知"""
        try:
            if not recipient.phone:
                logger.warning(f"用户 {recipient.user_id} 没有手机号")
                return False
            
            # 集成第三方短信服务 (如阿里云、腾讯云等)
            # 这里是简化版本
            logger.info(f"模拟短信发送: {recipient.phone} - {notification.content[:50]}")
            
            return True
            
        except Exception as e:
            logger.error(f"短信发送失败: {e}")
            return False
    
    async def _send_push_notification(
        self, 
        notification: UserNotification, 
        recipient: NotificationRecipient
    ) -> bool:
        """发送推送通知"""
        try:
            # 集成推送服务 (如Firebase、个推等)
            # 这里是简化版本
            logger.info(f"模拟推送通知: user_id={recipient.user_id} - {notification.title}")
            
            return True
            
        except Exception as e:
            logger.error(f"推送通知发送失败: {e}")
            return False
    
    async def send_batch_notifications(
        self,
        template_name: str,
        recipients: List[NotificationRecipient],
        template_vars: Union[Dict[str, Any], List[Dict[str, Any]]],
        channel: Optional[NotificationChannel] = None,
        priority: Optional[int] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """批量发送通知"""
        
        try:
            logger.info(f"开始批量发送通知: template={template_name}, recipients={len(recipients)}")
            
            successful_deliveries = []
            failed_deliveries = []
            
            # 准备模板变量
            if isinstance(template_vars, dict):
                # 所有用户使用相同的模板变量
                vars_list = [template_vars] * len(recipients)
            else:
                # 每个用户使用不同的模板变量
                vars_list = template_vars
                
            if len(vars_list) != len(recipients):
                raise UserManagementError("模板变量数量与接收者数量不匹配")
            
            # 分批处理
            for i in range(0, len(recipients), batch_size):
                batch_recipients = recipients[i:i + batch_size]
                batch_vars = vars_list[i:i + batch_size]
                
                # 创建批量任务
                batch_tasks = [
                    self.send_notification(
                        template_name=template_name,
                        recipient=recipient,
                        template_vars=vars_dict,
                        channel=channel,
                        priority=priority
                    )
                    for recipient, vars_dict in zip(batch_recipients, batch_vars)
                ]
                
                # 并发执行批量任务
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # 处理批量结果
                for recipient, result in zip(batch_recipients, batch_results):
                    if isinstance(result, Exception):
                        failed_deliveries.append({
                            "user_id": recipient.user_id,
                            "error": str(result)
                        })
                    elif result.status == NotificationStatus.SENT:
                        successful_deliveries.append({
                            "user_id": recipient.user_id,
                            "notification_id": result.notification_id,
                            "channel": result.channel.value,
                            "delivered_at": result.delivered_at.isoformat() if result.delivered_at else None
                        })
                    else:
                        failed_deliveries.append({
                            "user_id": recipient.user_id,
                            "error": result.error_message or "发送失败"
                        })
                
                # 每批处理后稍作延迟，避免过载
                if i + batch_size < len(recipients):
                    await asyncio.sleep(0.1)
            
            result_summary = {
                "template_name": template_name,
                "total_recipients": len(recipients),
                "successful_count": len(successful_deliveries),
                "failed_count": len(failed_deliveries),
                "success_rate": round(len(successful_deliveries) / len(recipients) * 100, 2),
                "successful_deliveries": successful_deliveries,
                "failed_deliveries": failed_deliveries,
                "sent_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"批量通知发送完成: 成功 {len(successful_deliveries)}, 失败 {len(failed_deliveries)}")
            
            return result_summary
            
        except Exception as e:
            logger.error(f"批量通知发送失败: {e}")
            raise UserManagementError(f"批量通知发送失败: {str(e)}")
    
    async def get_user_notifications(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None,
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """获取用户通知列表"""
        
        try:
            # 构建查询条件
            conditions = [UserNotification.user_id == user_id]
            
            if status:
                conditions.append(UserNotification.status == status)
            if notification_type:
                conditions.append(UserNotification.notification_type == notification_type)
            if unread_only:
                conditions.append(UserNotification.read_at.is_(None))
            
            # 查询通知
            query = select(UserNotification).where(and_(*conditions)).order_by(desc(UserNotification.created_at))
            count_query = select(func.count(UserNotification.id)).where(and_(*conditions))
            
            # 分页
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            # 执行查询
            notifications_result = await self.db.execute(query)
            count_result = await self.db.execute(count_query)
            
            notifications = notifications_result.scalars().all()
            total_count = count_result.scalar()
            
            # 格式化结果
            notifications_data = []
            for notification in notifications:
                notifications_data.append({
                    "id": notification.id,
                    "title": notification.title,
                    "content": notification.content,
                    "notification_type": notification.notification_type.value,
                    "channel": notification.channel.value,
                    "status": notification.status.value,
                    "priority": notification.priority,
                    "is_read": notification.read_at is not None,
                    "action_url": notification.action_url,
                    "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
                    "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at else None,
                    "read_at": notification.read_at.isoformat() if notification.read_at else None,
                    "created_at": notification.created_at.isoformat(),
                    "expires_at": notification.expires_at.isoformat() if notification.expires_at else None
                })
            
            return {
                "notifications": notifications_data,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": page * page_size < total_count,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"获取用户通知失败: user_id={user_id}, error={e}")
            raise UserManagementError(f"获取通知失败: {str(e)}")
    
    async def mark_notification_as_read(self, notification_id: int, user_id: int) -> bool:
        """标记通知为已读"""
        
        try:
            # 更新通知状态
            update_result = await self.db.execute(
                update(UserNotification)
                .where(and_(
                    UserNotification.id == notification_id,
                    UserNotification.user_id == user_id,
                    UserNotification.read_at.is_(None)
                ))
                .values(read_at=datetime.utcnow())
            )
            
            await self.db.commit()
            
            success = update_result.rowcount > 0
            
            if success:
                logger.info(f"通知标记为已读: notification_id={notification_id}, user_id={user_id}")
            else:
                logger.warning(f"通知标记失败: notification_id={notification_id}, user_id={user_id}")
            
            return success
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"标记通知已读失败: {e}")
            return False
    
    async def mark_all_notifications_as_read(self, user_id: int) -> int:
        """标记用户所有通知为已读"""
        
        try:
            # 批量更新所有未读通知
            update_result = await self.db.execute(
                update(UserNotification)
                .where(and_(
                    UserNotification.user_id == user_id,
                    UserNotification.read_at.is_(None)
                ))
                .values(read_at=datetime.utcnow())
            )
            
            await self.db.commit()
            
            updated_count = update_result.rowcount
            
            logger.info(f"批量标记通知为已读: user_id={user_id}, count={updated_count}")
            
            return updated_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"批量标记通知已读失败: {e}")
            return 0
    
    async def delete_expired_notifications(self, days_old: int = 30) -> int:
        """删除过期通知"""
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # 删除过期通知
            delete_result = await self.db.execute(
                delete(UserNotification)
                .where(or_(
                    UserNotification.expires_at < datetime.utcnow(),
                    and_(
                        UserNotification.created_at < cutoff_date,
                        UserNotification.status.in_([NotificationStatus.DELIVERED, NotificationStatus.READ])
                    )
                ))
            )
            
            await self.db.commit()
            
            deleted_count = delete_result.rowcount
            
            logger.info(f"删除过期通知: {deleted_count} 条")
            
            return deleted_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"删除过期通知失败: {e}")
            return 0
    
    async def get_notification_statistics(self, days_back: int = 7) -> Dict[str, Any]:
        """获取通知统计信息"""
        
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            # 统计查询
            stats_queries = [
                # 总通知数
                select(func.count(UserNotification.id)).where(
                    UserNotification.created_at >= start_date
                ),
                # 各渠道统计
                select(
                    UserNotification.channel,
                    func.count(UserNotification.id)
                ).where(
                    UserNotification.created_at >= start_date
                ).group_by(UserNotification.channel),
                # 各状态统计
                select(
                    UserNotification.status,
                    func.count(UserNotification.id)
                ).where(
                    UserNotification.created_at >= start_date
                ).group_by(UserNotification.status),
                # 各类型统计
                select(
                    UserNotification.notification_type,
                    func.count(UserNotification.id)
                ).where(
                    UserNotification.created_at >= start_date
                ).group_by(UserNotification.notification_type)
            ]
            
            results = await asyncio.gather(*[self.db.execute(query) for query in stats_queries])
            
            total_notifications = results[0].scalar()
            channel_stats = {channel.value: count for channel, count in results[1].fetchall()}
            status_stats = {status.value: count for status, count in results[2].fetchall()}
            type_stats = {notif_type.value: count for notif_type, count in results[3].fetchall()}
            
            # 计算成功率
            sent_count = status_stats.get('sent', 0) + status_stats.get('delivered', 0)
            success_rate = (sent_count / max(total_notifications, 1)) * 100
            
            return {
                "period": f"{days_back} 天",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_notifications": total_notifications,
                "success_rate": round(success_rate, 2),
                "channel_distribution": channel_stats,
                "status_distribution": status_stats,
                "type_distribution": type_stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取通知统计失败: {e}")
            raise UserManagementError(f"获取统计失败: {str(e)}")