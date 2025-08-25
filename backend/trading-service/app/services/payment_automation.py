"""
支付自动化服务 - 集成区块链监控和支付处理的自动化系统
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.blockchain_monitor import BlockchainMonitorService
from app.services.payment_processor import PaymentProcessorService
from app.core.exceptions import PaymentError, BlockchainError

logger = logging.getLogger(__name__)


class PaymentAutomationService:
    """支付自动化服务 - 整合区块链监控和支付处理"""
    
    def __init__(self):
        self.blockchain_monitor = None
        self.payment_processor = None
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
    async def initialize(self, db: AsyncSession):
        """初始化服务"""
        try:
            self.blockchain_monitor = BlockchainMonitorService(db)
            self.payment_processor = PaymentProcessorService(db)
            logger.info("✅ 支付自动化服务初始化完成")
        except Exception as e:
            logger.error(f"❌ 支付自动化服务初始化失败: {e}")
            raise
    
    async def start_automation(self):
        """启动支付自动化处理"""
        if self.running:
            logger.warning("支付自动化已在运行")
            return
            
        try:
            self.running = True
            
            # 启动区块链网络监控
            networks = ["TRC20", "ERC20", "BEP20"]
            for network in networks:
                success = await self.blockchain_monitor.start_monitoring(network)
                if success:
                    logger.info(f"✅ {network} 网络监控已启动")
                else:
                    logger.error(f"❌ {network} 网络监控启动失败")
            
            # 启动支付处理器后台任务
            await self.payment_processor.start_background_tasks()
            
            # 启动主监控循环
            monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.tasks.append(monitoring_task)
            
            # 启动过期订单清理任务
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.tasks.append(cleanup_task)
            
            logger.info("🚀 支付自动化系统已启动")
            
        except Exception as e:
            logger.error(f"❌ 启动支付自动化失败: {e}")
            self.running = False
            raise
    
    async def stop_automation(self):
        """停止支付自动化处理"""
        if not self.running:
            return
            
        try:
            self.running = False
            
            # 停止所有任务
            for task in self.tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            self.tasks.clear()
            
            # 停止区块链监控
            networks = ["TRC20", "ERC20", "BEP20"]
            for network in networks:
                await self.blockchain_monitor.stop_monitoring(network)
                logger.info(f"⏹️ {network} 网络监控已停止")
            
            # 关闭服务
            if self.blockchain_monitor:
                await self.blockchain_monitor.close()
            
            logger.info("⏹️ 支付自动化系统已停止")
            
        except Exception as e:
            logger.error(f"❌ 停止支付自动化失败: {e}")
    
    async def _monitoring_loop(self):
        """主监控循环 - 处理新发现的交易"""
        while self.running:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                # 这里可以添加额外的监控逻辑
                # 比如检查pending订单状态、处理确认数更新等
                
            except asyncio.CancelledError:
                logger.info("📊 监控循环已取消")
                break
            except Exception as e:
                logger.error(f"❌ 监控循环错误: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
    
    async def _cleanup_loop(self):
        """清理循环 - 处理过期订单"""
        while self.running:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                # 清理过期订单
                cleaned_count = await self.payment_processor.cleanup_expired_orders()
                if cleaned_count > 0:
                    logger.info(f"🧹 已清理 {cleaned_count} 个过期订单")
                    
            except asyncio.CancelledError:
                logger.info("🧹 清理循环已取消")
                break
            except Exception as e:
                logger.error(f"❌ 清理循环错误: {e}")
                await asyncio.sleep(300)  # 出错后等待5分钟再重试
    
    async def process_transaction_confirmation(
        self, 
        tx_hash: str,
        network: str,
        from_address: str,
        to_address: str,
        amount: float,
        confirmations: int
    ) -> bool:
        """处理交易确认（回调接口）"""
        try:
            from decimal import Decimal
            
            success = await self.payment_processor.process_payment_confirmation(
                tx_hash=tx_hash,
                network=network,
                from_address=from_address,
                to_address=to_address,
                amount=Decimal(str(amount)),
                confirmations=confirmations
            )
            
            if success:
                logger.info(f"✅ 交易确认处理成功: {tx_hash}")
            else:
                logger.warning(f"⚠️ 交易确认处理失败: {tx_hash}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 处理交易确认时出错: {e}")
            return False
    
    async def manual_process_payment(
        self, 
        order_id: int,
        tx_hash: str,
        amount: float,
        admin_id: int
    ) -> bool:
        """手动处理支付（管理员操作）"""
        try:
            from decimal import Decimal
            
            # 这里可以添加手动支付处理逻辑
            # 比如直接标记订单为已确认，绕过区块链验证
            
            logger.info(f"🔧 管理员 {admin_id} 手动处理支付: 订单 {order_id}, 交易 {tx_hash}")
            
            # 实际实现需要调用支付处理器的相应方法
            return True
            
        except Exception as e:
            logger.error(f"❌ 手动处理支付失败: {e}")
            return False
    
    def get_automation_status(self) -> Dict:
        """获取自动化系统状态"""
        return {
            "running": self.running,
            "active_tasks": len(self.tasks),
            "blockchain_monitor_active": bool(self.blockchain_monitor),
            "payment_processor_active": bool(self.payment_processor),
            "timestamp": datetime.utcnow().isoformat()
        }


# 全局支付自动化服务实例
payment_automation = PaymentAutomationService()


async def initialize_payment_automation(db: AsyncSession):
    """初始化支付自动化服务"""
    await payment_automation.initialize(db)


async def start_payment_automation():
    """启动支付自动化服务"""
    await payment_automation.start_automation()


async def stop_payment_automation():
    """停止支付自动化服务"""
    await payment_automation.stop_automation()