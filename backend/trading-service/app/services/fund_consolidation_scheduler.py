"""
资金归集定时调度器 - 定期执行用户钱包资金归集
"""

import asyncio
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.user_wallet_service import user_wallet_service
from app.database import get_db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class FundConsolidationScheduler:
    """资金归集定时调度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        
        # 配置参数
        self.min_consolidation_amount = Decimal('1.0')  # 最小归集金额
        self.consolidation_interval_hours = 6  # 归集间隔（小时）
        self.max_concurrent_tasks = 5  # 最大并发归集任务数
        
        # 运行状态
        self.active_consolidation_tasks = set()
        self.last_consolidation_time = None
        
    async def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("资金归集调度器已在运行")
            return
        
        # 添加定时任务
        await self._setup_scheduled_jobs()
        
        # 启动调度器
        self.scheduler.start()
        self.is_running = True
        
        logger.info("资金归集调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        
        logger.info("资金归集调度器已停止")
    
    async def _setup_scheduled_jobs(self):
        """设置定时任务"""
        
        # 每6小时执行一次自动归集
        self.scheduler.add_job(
            self.execute_auto_consolidation,
            trigger=IntervalTrigger(hours=self.consolidation_interval_hours),
            id='auto_consolidation',
            name='自动资金归集',
            max_instances=1,
            coalesce=True,
            replace_existing=True
        )
        
        # 每天凌晨2点执行深度归集（包括小额资金）
        self.scheduler.add_job(
            self.execute_deep_consolidation,
            trigger=CronTrigger(hour=2, minute=0),
            id='deep_consolidation',
            name='深度资金归集',
            max_instances=1,
            coalesce=True,
            replace_existing=True
        )
        
        # 每小时检查失败的归集任务
        self.scheduler.add_job(
            self.retry_failed_consolidations,
            trigger=IntervalTrigger(hours=1),
            id='retry_failed',
            name='重试失败归集',
            max_instances=1,
            coalesce=True,
            replace_existing=True
        )
        
        # 每10分钟检查pending状态的归集任务
        self.scheduler.add_job(
            self.check_pending_consolidations,
            trigger=IntervalTrigger(minutes=10),
            id='check_pending',
            name='检查待处理归集',
            max_instances=1,
            coalesce=True,
            replace_existing=True
        )
        
        logger.info("定时任务设置完成")
    
    async def execute_auto_consolidation(self):
        """执行自动归集任务"""
        logger.info("开始执行自动资金归集")
        
        try:
            # 获取有资金的用户列表
            eligible_users = await self._get_eligible_users_for_consolidation()
            
            if not eligible_users:
                logger.info("没有需要归集的用户钱包")
                return
            
            logger.info(f"找到 {len(eligible_users)} 个用户需要归集资金")
            
            # 批量处理归集任务
            consolidation_results = []
            for user_data in eligible_users:
                if len(self.active_consolidation_tasks) >= self.max_concurrent_tasks:
                    # 等待一些任务完成
                    await asyncio.sleep(1)
                    continue
                
                user_id = user_data['user_id']
                total_balance = user_data['total_balance']
                
                if user_id not in self.active_consolidation_tasks:
                    self.active_consolidation_tasks.add(user_id)
                    task = asyncio.create_task(
                        self._execute_user_consolidation(user_id, total_balance)
                    )
                    consolidation_results.append(task)
            
            # 等待所有任务完成
            if consolidation_results:
                completed_results = await asyncio.gather(*consolidation_results, return_exceptions=True)
                
                success_count = sum(1 for result in completed_results if result is True)
                fail_count = len(completed_results) - success_count
                
                logger.info(f"自动归集完成: 成功 {success_count}, 失败 {fail_count}")
            
            self.last_consolidation_time = datetime.now()
            
        except Exception as e:
            logger.error(f"自动归集执行失败: {e}")
    
    async def execute_deep_consolidation(self):
        """执行深度归集（包括小额资金）"""
        logger.info("开始执行深度资金归集")
        
        try:
            # 降低最小归集金额阈值
            original_min_amount = self.min_consolidation_amount
            self.min_consolidation_amount = Decimal('0.1')  # 临时降低到0.1 USDT
            
            await self.execute_auto_consolidation()
            
            # 恢复原始阈值
            self.min_consolidation_amount = original_min_amount
            
            logger.info("深度资金归集完成")
            
        except Exception as e:
            logger.error(f"深度归集执行失败: {e}")
    
    async def retry_failed_consolidations(self):
        """重试失败的归集任务"""
        logger.info("开始重试失败的归集任务")
        
        try:
            # 获取失败的归集任务（最近24小时内的）
            failed_tasks = await self._get_failed_consolidation_tasks()
            
            if not failed_tasks:
                logger.info("没有需要重试的失败归集任务")
                return
            
            logger.info(f"找到 {len(failed_tasks)} 个失败的归集任务需要重试")
            
            retry_count = 0
            for task in failed_tasks:
                try:
                    consolidation_id = task['id']
                    user_id = task['user_id']
                    
                    # 重新获取用户钱包信息
                    user_balances = await user_wallet_service.check_user_balances(user_id)
                    total_balance = sum(user_balances.values())
                    
                    if total_balance >= self.min_consolidation_amount:
                        # 标记任务为重试状态
                        await self._update_consolidation_status(consolidation_id, 'retrying')
                        
                        # 发起新的归集
                        result = await user_wallet_service.initiate_fund_consolidation(
                            user_id, self.min_consolidation_amount
                        )
                        
                        if result:
                            retry_count += 1
                            logger.info(f"重试归集任务 {consolidation_id} 成功")
                        
                except Exception as e:
                    logger.error(f"重试归集任务失败: {e}")
            
            logger.info(f"重试完成: {retry_count} 个任务重新发起")
            
        except Exception as e:
            logger.error(f"重试失败归集任务时出错: {e}")
    
    async def check_pending_consolidations(self):
        """检查pending状态的归集任务"""
        try:
            # 获取pending状态超过30分钟的任务
            stalled_tasks = await self._get_stalled_consolidation_tasks()
            
            if stalled_tasks:
                logger.warning(f"发现 {len(stalled_tasks)} 个可能停滞的归集任务")
                
                for task in stalled_tasks:
                    # 将停滞任务标记为失败，以便后续重试
                    await self._update_consolidation_status(
                        task['id'], 
                        'failed', 
                        '任务执行超时'
                    )
                
        except Exception as e:
            logger.error(f"检查pending归集任务时出错: {e}")
    
    async def _get_eligible_users_for_consolidation(self) -> List[Dict]:
        """获取符合归集条件的用户列表"""
        try:
            async for db in get_db():
                result = await db.execute(
                    text("""
                        SELECT 
                            uw.user_id,
                            SUM(w.balance) as total_balance,
                            COUNT(*) as wallet_count
                        FROM user_wallets uw
                        JOIN usdt_wallets w ON uw.wallet_id = w.id
                        WHERE w.balance >= :min_amount
                        GROUP BY uw.user_id
                        HAVING total_balance >= :total_min_amount
                        ORDER BY total_balance DESC
                    """),
                    {
                        "min_amount": float(self.min_consolidation_amount),
                        "total_min_amount": float(self.min_consolidation_amount)
                    }
                )
                
                users = []
                for row in result.fetchall():
                    users.append({
                        'user_id': row[0],
                        'total_balance': Decimal(str(row[1])),
                        'wallet_count': row[2]
                    })
                
                break
            
            return users
            
        except Exception as e:
            logger.error(f"获取符合归集条件的用户失败: {e}")
            return []
    
    async def _execute_user_consolidation(self, user_id: int, total_balance: Decimal) -> bool:
        """执行单个用户的资金归集"""
        try:
            logger.info(f"开始为用户 {user_id} 执行资金归集，总余额: {total_balance}")
            
            result = await user_wallet_service.initiate_fund_consolidation(
                user_id, self.min_consolidation_amount
            )
            
            if result:
                logger.info(f"用户 {user_id} 资金归集完成，处理了 {len(result)} 个钱包")
                return True
            else:
                logger.warning(f"用户 {user_id} 资金归集失败")
                return False
            
        except Exception as e:
            logger.error(f"用户 {user_id} 资金归集异常: {e}")
            return False
        
        finally:
            # 从活跃任务集合中移除
            self.active_consolidation_tasks.discard(user_id)
    
    async def _get_failed_consolidation_tasks(self) -> List[Dict]:
        """获取失败的归集任务"""
        try:
            async for db in get_db():
                # 获取最近24小时内失败的归集任务，且没有在最近1小时内重试过的
                result = await db.execute(
                    text("""
                        SELECT fc.id, uw.user_id, fc.amount, fc.created_at, fc.error_message
                        FROM fund_consolidations fc
                        JOIN user_wallets uw ON fc.user_wallet_id = uw.id
                        WHERE fc.status = 'failed'
                        AND fc.created_at >= datetime('now', '-24 hours')
                        AND NOT EXISTS (
                            SELECT 1 FROM fund_consolidations fc2 
                            WHERE fc2.user_wallet_id = fc.user_wallet_id 
                            AND fc2.created_at > fc.created_at
                            AND fc2.created_at >= datetime('now', '-1 hours')
                        )
                        ORDER BY fc.created_at DESC
                        LIMIT 10
                    """)
                )
                
                tasks = []
                for row in result.fetchall():
                    tasks.append({
                        'id': row[0],
                        'user_id': row[1],
                        'amount': row[2],
                        'created_at': row[3],
                        'error_message': row[4]
                    })
                
                break
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取失败归集任务失败: {e}")
            return []
    
    async def _get_stalled_consolidation_tasks(self) -> List[Dict]:
        """获取停滞的归集任务"""
        try:
            async for db in get_db():
                result = await db.execute(
                    text("""
                        SELECT id, user_wallet_id, amount, created_at
                        FROM fund_consolidations
                        WHERE status = 'pending'
                        AND created_at <= datetime('now', '-30 minutes')
                        ORDER BY created_at
                        LIMIT 20
                    """)
                )
                
                tasks = []
                for row in result.fetchall():
                    tasks.append({
                        'id': row[0],
                        'user_wallet_id': row[1],
                        'amount': row[2],
                        'created_at': row[3]
                    })
                
                break
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取停滞归集任务失败: {e}")
            return []
    
    async def _update_consolidation_status(self, consolidation_id: int, status: str, error_message: str = None):
        """更新归集任务状态"""
        try:
            async for db in get_db():
                if error_message:
                    await db.execute(
                        text("""
                            UPDATE fund_consolidations 
                            SET status = :status, error_message = :error_message, updated_at = :now
                            WHERE id = :consolidation_id
                        """),
                        {
                            "status": status,
                            "error_message": error_message,
                            "consolidation_id": consolidation_id,
                            "now": datetime.now()
                        }
                    )
                else:
                    await db.execute(
                        text("""
                            UPDATE fund_consolidations 
                            SET status = :status, updated_at = :now
                            WHERE id = :consolidation_id
                        """),
                        {
                            "status": status,
                            "consolidation_id": consolidation_id,
                            "now": datetime.now()
                        }
                    )
                
                await db.commit()
                break
                
        except Exception as e:
            logger.error(f"更新归集任务状态失败: {e}")
    
    def get_status(self) -> Dict:
        """获取调度器状态"""
        return {
            "is_running": self.is_running,
            "last_consolidation_time": self.last_consolidation_time,
            "active_tasks_count": len(self.active_consolidation_tasks),
            "min_consolidation_amount": float(self.min_consolidation_amount),
            "consolidation_interval_hours": self.consolidation_interval_hours,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "scheduled_jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ] if self.scheduler else []
        }
    
    async def manual_consolidation(self, user_id: Optional[int] = None, min_amount: Optional[Decimal] = None):
        """手动触发归集"""
        try:
            original_min_amount = self.min_consolidation_amount
            if min_amount:
                self.min_consolidation_amount = min_amount
            
            if user_id:
                # 单用户归集
                user_balances = await user_wallet_service.check_user_balances(user_id)
                total_balance = sum(user_balances.values())
                
                if total_balance >= self.min_consolidation_amount:
                    result = await self._execute_user_consolidation(user_id, total_balance)
                    return {"status": "success" if result else "failed", "user_id": user_id}
                else:
                    return {"status": "insufficient_balance", "user_id": user_id, "balance": float(total_balance)}
            else:
                # 全部用户归集
                await self.execute_auto_consolidation()
                return {"status": "completed", "message": "全部用户归集已触发"}
        
        finally:
            self.min_consolidation_amount = original_min_amount


# 全局实例
fund_consolidation_scheduler = FundConsolidationScheduler()