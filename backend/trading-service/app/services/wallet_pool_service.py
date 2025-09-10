"""
钱包池管理服务 - USDT钱包池的生命周期管理
"""

import asyncio
import secrets
from typing import List, Optional, Dict, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.payment import USDTWallet, USDTPaymentOrder, WalletBalance
from app.models.admin import AdminOperationLog
from app.services.wallet_generator import MultiChainWalletGenerator, WalletInfo as GeneratorWalletInfo
from app.security.crypto_manager import get_security_manager
from app.core.exceptions import WalletError, SecurityError, ValidationError
import logging

logger = logging.getLogger(__name__)


class WalletInfo:
    """钱包信息数据类"""
    
    def __init__(self, id: int, name: str, network: str, address: str, 
                 balance: Decimal, status: str, created_at: datetime):
        self.id = id
        self.name = name
        self.network = network
        self.address = address
        self.balance = balance
        self.status = status
        self.created_at = created_at


class WalletPoolService:
    """钱包池核心管理服务"""
    
    # 钱包状态常量
    STATUS_AVAILABLE = "available"      # 可用
    STATUS_OCCUPIED = "occupied"        # 已分配
    STATUS_MAINTENANCE = "maintenance"  # 维护中
    STATUS_DISABLED = "disabled"        # 已禁用
    STATUS_ERROR = "error"             # 错误状态
    
    # 网络类型常量
    NETWORK_TRC20 = "TRC20"
    NETWORK_ERC20 = "ERC20" 
    NETWORK_BEP20 = "BEP20"
    SUPPORTED_NETWORKS = [NETWORK_TRC20, NETWORK_ERC20, NETWORK_BEP20]
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_generator = MultiChainWalletGenerator()
        self.security_manager = get_security_manager()
        logger.info("WalletPoolService初始化完成")
    
    async def generate_wallets(
        self, 
        network: str, 
        count: int, 
        name_prefix: str = "wallet",
        admin_id: Optional[int] = None
    ) -> List[WalletInfo]:
        """
        批量生成钱包
        
        Args:
            network: 网络类型 (TRC20/ERC20/BEP20)
            count: 生成数量
            name_prefix: 钱包名称前缀
            admin_id: 操作管理员ID
            
        Returns:
            生成的钱包信息列表
        """
        if network not in self.SUPPORTED_NETWORKS:
            raise ValidationError(f"不支持的网络类型: {network}")
        
        if count <= 0 or count > 1000:
            raise ValidationError("钱包数量必须在1-1000之间")
        
        logger.info(f"开始生成 {count} 个 {network} 钱包")
        
        generated_wallets = []
        failed_count = 0
        
        try:
            # 使用新的钱包生成器批量生成
            generator_wallets = self.wallet_generator.batch_generate_wallets(
                network=network,
                count=count,
                name_prefix=name_prefix
            )
            
            # 处理生成的钱包
            for i, gen_wallet in enumerate(generator_wallets):
                try:
                    # 安全存储私钥
                    wallet_id_temp = f"temp_{i}_{secrets.token_hex(4)}"
                    storage_result = self.security_manager.secure_store_private_key(
                        wallet_id=wallet_id_temp,
                        private_key=gen_wallet.private_key,
                        network=network
                    )
                    
                    if not storage_result['success']:
                        raise SecurityError(f"私钥加密失败: {storage_result.get('error')}")
                    
                    # 创建数据库记录
                    wallet = USDTWallet(
                        wallet_name=gen_wallet.name,
                        network=gen_wallet.network,
                        address=gen_wallet.address,
                        private_key=storage_result['encrypted_private_key'],
                        public_key=gen_wallet.public_key,
                        balance=Decimal('0'),
                        status=self.STATUS_AVAILABLE,
                        total_received=Decimal('0'),
                        total_sent=Decimal('0'),
                        transaction_count=0
                    )
                    
                    self.db.add(wallet)
                    await self.db.flush()  # 获取生成的ID
                    
                    generated_wallets.append(WalletInfo(
                        id=wallet.id,
                        name=gen_wallet.name,
                        network=gen_wallet.network,
                        address=gen_wallet.address,
                        balance=Decimal('0'),
                        status=self.STATUS_AVAILABLE,
                        created_at=wallet.created_at
                    ))
                    
                    # 每100个钱包提交一次
                    if (i + 1) % 100 == 0:
                        await self.db.commit()
                        logger.info(f"已生成 {i+1}/{count} 个钱包")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"生成第 {i+1} 个钱包失败: {e}")
                    continue
            
            # 最终提交
            await self.db.commit()
            
            # 记录操作日志
            if admin_id:
                await self._log_operation(
                    admin_id=admin_id,
                    operation="GENERATE_WALLETS",
                    details={
                        "network": network,
                        "requested_count": count,
                        "success_count": len(generated_wallets),
                        "failed_count": failed_count
                    }
                )
            
            logger.info(f"钱包生成完成: {len(generated_wallets)}个成功, {failed_count}个失败")
            return generated_wallets
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"批量生成钱包失败: {e}")
            raise WalletError(f"钱包生成失败: {str(e)}")
    
    async def import_wallet(
        self, 
        network: str, 
        private_key: str, 
        wallet_name: str,
        admin_id: Optional[int] = None
    ) -> WalletInfo:
        """
        导入现有钱包
        
        Args:
            network: 网络类型
            private_key: 私钥
            wallet_name: 钱包名称
            admin_id: 操作管理员ID
            
        Returns:
            导入的钱包信息
        """
        if network not in self.SUPPORTED_NETWORKS:
            raise ValidationError(f"不支持的网络类型: {network}")
        
        try:
            # 使用钱包生成器导入钱包
            imported_wallet = self.wallet_generator.import_wallet(
                network=network,
                private_key=private_key,
                wallet_name=wallet_name
            )
            
            # 检查地址是否已存在
            existing_wallet = await self.db.execute(
                select(USDTWallet).where(USDTWallet.address == imported_wallet.address)
            )
            if existing_wallet.scalar_one_or_none():
                raise ValidationError(f"钱包地址已存在: {imported_wallet.address}")
            
            # 安全存储私钥
            storage_result = self.security_manager.secure_store_private_key(
                wallet_id=f"import_{secrets.token_hex(8)}",
                private_key=imported_wallet.private_key,
                network=network
            )
            
            if not storage_result['success']:
                raise SecurityError(f"私钥加密失败: {storage_result.get('error')}")
            
            # 创建钱包记录
            wallet = USDTWallet(
                wallet_name=wallet_name,
                network=imported_wallet.network,
                address=imported_wallet.address,
                private_key=storage_result['encrypted_private_key'],
                public_key=imported_wallet.public_key,
                balance=Decimal('0'),
                status=self.STATUS_AVAILABLE,
                total_received=Decimal('0'),
                total_sent=Decimal('0'),
                transaction_count=0
            )
            
            self.db.add(wallet)
            await self.db.commit()
            
            # 记录操作日志
            if admin_id:
                await self._log_operation(
                    admin_id=admin_id,
                    operation="IMPORT_WALLET",
                    resource_id=wallet.id,
                    details={
                        "network": imported_wallet.network,
                        "wallet_name": wallet_name,
                        "address": imported_wallet.address
                    }
                )
            
            logger.info(f"成功导入钱包: {wallet_name} ({imported_wallet.address})")
            
            return WalletInfo(
                id=wallet.id,
                name=wallet_name,
                network=imported_wallet.network,
                address=imported_wallet.address,
                balance=Decimal('0'),
                status=self.STATUS_AVAILABLE,
                created_at=wallet.created_at
            )
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"导入钱包失败: {e}")
            raise WalletError(f"钱包导入失败: {str(e)}")
    
    async def allocate_wallet(self, order_id: str, network: str) -> Optional[WalletInfo]:
        """
        为订单分配可用钱包
        
        Args:
            order_id: 订单ID
            network: 网络类型
            
        Returns:
            分配的钱包信息，如果无可用钱包则返回None
        """
        try:
            # 查找可用钱包（优先分配使用次数少的钱包）
            wallet_query = select(USDTWallet).where(
                and_(
                    USDTWallet.network == network,
                    USDTWallet.status == self.STATUS_AVAILABLE
                )
            ).order_by(USDTWallet.transaction_count.asc()).limit(1)
            
            result = await self.db.execute(wallet_query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                logger.warning(f"没有可用的 {network} 钱包")
                return None
            
            # 原子性更新钱包状态
            update_result = await self.db.execute(
                update(USDTWallet)
                .where(
                    and_(
                        USDTWallet.id == wallet.id,
                        USDTWallet.status == self.STATUS_AVAILABLE
                    )
                )
                .values(
                    status=self.STATUS_OCCUPIED,
                    current_order_id=order_id,
                    allocated_at=func.now(),
                    updated_at=func.now()
                )
            )
            
            if update_result.rowcount == 0:
                # 钱包已被其他进程分配
                logger.warning(f"钱包 {wallet.id} 已被其他进程分配")
                return None
            
            await self.db.commit()
            
            logger.info(f"成功分配钱包 {wallet.address} 给订单 {order_id}")
            
            return WalletInfo(
                id=wallet.id,
                name=wallet.wallet_name,
                network=network,
                address=wallet.address,
                balance=wallet.balance,
                status=self.STATUS_OCCUPIED,
                created_at=wallet.created_at
            )
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"分配钱包失败: {e}")
            raise WalletError(f"钱包分配失败: {str(e)}")
    
    async def release_wallet(self, wallet_id: int, admin_id: Optional[int] = None) -> bool:
        """
        释放钱包回池中
        
        Args:
            wallet_id: 钱包ID
            admin_id: 操作管理员ID
            
        Returns:
            是否释放成功
        """
        try:
            # 更新钱包状态
            update_result = await self.db.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(
                    status=self.STATUS_AVAILABLE,
                    current_order_id=None,
                    allocated_at=None,
                    updated_at=func.now()
                )
            )
            
            if update_result.rowcount == 0:
                return False
            
            await self.db.commit()
            
            # 记录操作日志
            if admin_id:
                await self._log_operation(
                    admin_id=admin_id,
                    operation="RELEASE_WALLET",
                    resource_id=wallet_id,
                    details={"action": "release_to_pool"}
                )
            
            logger.info(f"成功释放钱包 {wallet_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"释放钱包失败: {e}")
            return False
    
    async def update_wallet_status(
        self, 
        wallet_id: int, 
        new_status: str,
        admin_id: Optional[int] = None
    ) -> bool:
        """
        更新钱包状态
        
        Args:
            wallet_id: 钱包ID
            new_status: 新状态
            admin_id: 操作管理员ID
            
        Returns:
            是否更新成功
        """
        valid_statuses = [
            self.STATUS_AVAILABLE, self.STATUS_OCCUPIED,
            self.STATUS_MAINTENANCE, self.STATUS_DISABLED, self.STATUS_ERROR
        ]
        
        if new_status not in valid_statuses:
            raise ValidationError(f"无效的钱包状态: {new_status}")
        
        try:
            # 获取当前钱包信息
            wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
            result = await self.db.execute(wallet_query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                raise ValidationError(f"钱包不存在: {wallet_id}")
            
            old_status = wallet.status
            
            # 更新状态
            await self.db.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(
                    status=new_status,
                    updated_at=func.now()
                )
            )
            
            await self.db.commit()
            
            # 记录操作日志
            if admin_id:
                await self._log_operation(
                    admin_id=admin_id,
                    operation="UPDATE_WALLET_STATUS",
                    resource_id=wallet_id,
                    details={
                        "old_status": old_status,
                        "new_status": new_status,
                        "wallet_address": wallet.address
                    }
                )
            
            logger.info(f"钱包 {wallet_id} 状态更新: {old_status} -> {new_status}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"更新钱包状态失败: {e}")
            return False
    
    async def get_pool_statistics(self, network: Optional[str] = None) -> Dict:
        """
        获取钱包池统计信息
        
        Args:
            network: 网络类型筛选
            
        Returns:
            统计信息字典
        """
        try:
            # 构建基础查询
            base_query = select(USDTWallet.status, func.count().label('count'))
            
            if network:
                base_query = base_query.where(USDTWallet.network == network)
            
            # 按状态分组统计
            status_query = base_query.group_by(USDTWallet.status)
            status_result = await self.db.execute(status_query)
            status_stats = {row.status: row.count for row in status_result}
            
            # 按网络分组统计
            network_query = select(
                USDTWallet.network, 
                func.count().label('count')
            ).group_by(USDTWallet.network)
            
            if network:
                network_query = network_query.where(USDTWallet.network == network)
            
            network_result = await self.db.execute(network_query)
            network_stats = {row.network: row.count for row in network_result}
            
            # 余额统计
            balance_query = select(
                func.count().label('total_wallets'),
                func.sum(USDTWallet.balance).label('total_balance'),
                func.avg(USDTWallet.balance).label('avg_balance'),
                func.sum(USDTWallet.total_received).label('total_received')
            )
            
            if network:
                balance_query = balance_query.where(USDTWallet.network == network)
            
            balance_result = await self.db.execute(balance_query)
            balance_row = balance_result.first()
            
            return {
                "status_distribution": status_stats,
                "network_distribution": network_stats,
                "total_wallets": balance_row.total_wallets or 0,
                "total_balance": float(balance_row.total_balance or 0),
                "average_balance": float(balance_row.avg_balance or 0),
                "total_received": float(balance_row.total_received or 0),
                "utilization_rate": (
                    status_stats.get(self.STATUS_OCCUPIED, 0) / 
                    max(balance_row.total_wallets or 1, 1) * 100
                )
            }
            
        except Exception as e:
            logger.error(f"获取钱包池统计失败: {e}")
            raise WalletError(f"统计信息获取失败: {str(e)}")
    
    async def get_private_key(self, wallet_id: int, network: str) -> str:
        """
        安全获取钱包私钥 (仅供内部服务使用)
        
        Args:
            wallet_id: 钱包ID
            network: 网络类型
            
        Returns:
            解密后的私钥
            
        Raises:
            SecurityError: 私钥解密失败
        """
        try:
            # 查询钱包
            wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
            result = await self.db.execute(wallet_query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                raise ValidationError(f"钱包不存在: {wallet_id}")
            
            if wallet.network != network:
                raise ValidationError(f"网络类型不匹配: 期望{network}, 实际{wallet.network}")
            
            # 安全获取私钥
            retrieval_result = self.security_manager.secure_retrieve_private_key(
                wallet_id=str(wallet_id),
                encrypted_key=wallet.private_key,
                network=network
            )
            
            if not retrieval_result['success']:
                raise SecurityError(f"私钥解密失败: {retrieval_result.get('error')}")
            
            return retrieval_result['private_key']
            
        except Exception as e:
            logger.error(f"获取钱包私钥失败 - 钱包ID: {wallet_id}, 错误: {e}")
            raise SecurityError(f"私钥获取失败: {str(e)}")
    
    async def validate_wallet_integrity(self, wallet_id: int) -> Dict[str, Any]:
        """
        验证钱包完整性
        
        Args:
            wallet_id: 钱包ID
            
        Returns:
            验证结果字典
        """
        try:
            # 查询钱包
            wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
            result = await self.db.execute(wallet_query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                return {"valid": False, "error": "钱包不存在"}
            
            try:
                # 获取私钥
                private_key = await self.get_private_key(wallet_id, wallet.network)
                
                # 使用钱包生成器验证地址
                is_valid = self.wallet_generator.validate_address(wallet.address, wallet.network)
                
                # 验证私钥和地址的匹配性
                imported_test = self.wallet_generator.import_wallet(
                    network=wallet.network,
                    private_key=private_key,
                    wallet_name="test"
                )
                
                address_match = imported_test.address == wallet.address
                
                return {
                    "valid": is_valid and address_match,
                    "address_valid": is_valid,
                    "address_match": address_match,
                    "wallet_id": wallet_id,
                    "network": wallet.network,
                    "address": wallet.address
                }
                
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"验证过程失败: {str(e)}",
                    "wallet_id": wallet_id
                }
            
        except Exception as e:
            logger.error(f"钱包完整性验证失败: {e}")
            return {"valid": False, "error": str(e)}
    
    def get_supported_networks(self) -> List[str]:
        """获取支持的网络类型"""
        return self.SUPPORTED_NETWORKS.copy()
    
    async def get_wallet_by_address(self, address: str, network: Optional[str] = None) -> Optional[WalletInfo]:
        """
        根据地址查找钱包
        
        Args:
            address: 钱包地址
            network: 网络类型 (可选)
            
        Returns:
            钱包信息或None
        """
        try:
            query = select(USDTWallet).where(USDTWallet.address == address)
            
            if network:
                query = query.where(USDTWallet.network == network)
            
            result = await self.db.execute(query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                return None
            
            return WalletInfo(
                id=wallet.id,
                name=wallet.wallet_name,
                network=wallet.network,
                address=wallet.address,
                balance=wallet.balance,
                status=wallet.status,
                created_at=wallet.created_at
            )
            
        except Exception as e:
            logger.error(f"根据地址查找钱包失败: {e}")
            return None
    
    async def _log_operation(
        self, 
        admin_id: int, 
        operation: str,
        resource_id: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """记录操作日志"""
        try:
            import json
            
            log_entry = AdminOperationLog(
                admin_id=admin_id,
                operation=operation,
                resource_type="wallet",
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                result="success"
            )
            
            self.db.add(log_entry)
            await self.db.flush()  # 不需要提交，由调用者决定
            
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}")