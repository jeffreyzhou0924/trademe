"""
钱包池管理服务 - USDT钱包池的生命周期管理
"""

import asyncio
import secrets
from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.payment import USDTWallet, USDTPaymentOrder, WalletBalance
from app.models.admin import AdminOperationLog
from app.services.wallet_encryption import wallet_encryption
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
        self.encryption = wallet_encryption
    
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
            # 批量生成钱包
            for i in range(count):
                try:
                    # 生成钱包密钥对
                    private_key, address = self._generate_wallet_keypair(network)
                    
                    # 加密私钥
                    encrypted_private_key = self.encryption.encrypt_private_key(
                        private_key, address
                    )
                    
                    # 验证私钥正确性
                    if not self.encryption.verify_private_key(private_key, address, network):
                        raise WalletError(f"生成的私钥验证失败: {address}")
                    
                    # 创建钱包记录
                    wallet_name = f"{name_prefix}_{i+1:04d}"
                    wallet = USDTWallet(
                        wallet_name=wallet_name,
                        network=network,
                        address=address,
                        private_key=encrypted_private_key,
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
                        name=wallet_name,
                        network=network,
                        address=address,
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
            # 从私钥计算地址
            address = self._get_address_from_private_key(private_key, network)
            
            # 验证私钥正确性
            if not self.encryption.verify_private_key(private_key, address, network):
                raise SecurityError("私钥验证失败")
            
            # 检查地址是否已存在
            existing_wallet = await self.db.execute(
                select(USDTWallet).where(USDTWallet.address == address)
            )
            if existing_wallet.scalar_one_or_none():
                raise ValidationError(f"钱包地址已存在: {address}")
            
            # 加密私钥
            encrypted_private_key = self.encryption.encrypt_private_key(private_key, address)
            
            # 创建钱包记录
            wallet = USDTWallet(
                wallet_name=wallet_name,
                network=network,
                address=address,
                private_key=encrypted_private_key,
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
                        "network": network,
                        "wallet_name": wallet_name,
                        "address": address
                    }
                )
            
            logger.info(f"成功导入钱包: {wallet_name} ({address})")
            
            return WalletInfo(
                id=wallet.id,
                name=wallet_name,
                network=network,
                address=address,
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
    
    def _generate_wallet_keypair(self, network: str) -> Tuple[str, str]:
        """生成钱包密钥对"""
        if network == self.NETWORK_TRC20:
            return self._generate_tron_wallet()
        elif network in [self.NETWORK_ERC20, self.NETWORK_BEP20]:
            return self._generate_ethereum_wallet()
        else:
            raise ValidationError(f"不支持的网络类型: {network}")
    
    def _generate_tron_wallet(self) -> Tuple[str, str]:
        """生成TRON钱包"""
        try:
            from tronpy.keys import PrivateKey
            
            # 生成私钥
            private_key = PrivateKey.random()
            # 获取地址
            address = private_key.public_key.to_base58check_address()
            
            return private_key.hex(), address
        except ImportError:
            # 如果没有安装tronpy，使用备用方案
            logger.warning("tronpy not available, using fallback method")
            return self._generate_tron_wallet_fallback()
    
    def _generate_ethereum_wallet(self) -> Tuple[str, str]:
        """生成Ethereum/BSC钱包"""
        try:
            from eth_account import Account
            
            # 生成账户
            account = Account.create()
            
            return account.key.hex(), account.address
        except ImportError:
            # 如果没有安装eth_account，使用备用方案
            logger.warning("eth_account not available, using fallback method")
            return self._generate_ethereum_wallet_fallback()
    
    def _generate_tron_wallet_fallback(self) -> Tuple[str, str]:
        """TRON钱包生成备用方案"""
        # 生成32字节随机私钥
        private_key_bytes = secrets.randbits(256).to_bytes(32, 'big')
        private_key = private_key_bytes.hex()
        
        # 简化的地址生成（实际应用中需要完整实现）
        address = f"T{secrets.token_hex(16)}"
        
        logger.warning("Using fallback TRON wallet generation - not for production")
        return private_key, address
    
    def _generate_ethereum_wallet_fallback(self) -> Tuple[str, str]:
        """Ethereum钱包生成备用方案"""
        # 生成32字节随机私钥
        private_key_bytes = secrets.randbits(256).to_bytes(32, 'big')
        private_key = private_key_bytes.hex()
        
        # 简化的地址生成（实际应用中需要完整实现）
        address = f"0x{secrets.token_hex(20)}"
        
        logger.warning("Using fallback Ethereum wallet generation - not for production")
        return private_key, address
    
    def _get_address_from_private_key(self, private_key: str, network: str) -> str:
        """从私钥计算地址"""
        if network == self.NETWORK_TRC20:
            return self._get_tron_address_from_private_key(private_key)
        elif network in [self.NETWORK_ERC20, self.NETWORK_BEP20]:
            return self._get_ethereum_address_from_private_key(private_key)
        else:
            raise ValidationError(f"不支持的网络类型: {network}")
    
    def _get_tron_address_from_private_key(self, private_key: str) -> str:
        """从TRON私钥计算地址"""
        try:
            from tronpy.keys import PrivateKey
            
            pk = PrivateKey(bytes.fromhex(private_key))
            return pk.public_key.to_base58check_address()
        except ImportError:
            raise WalletError("TRON库未安装，无法验证私钥")
    
    def _get_ethereum_address_from_private_key(self, private_key: str) -> str:
        """从Ethereum私钥计算地址"""
        try:
            from eth_account import Account
            
            account = Account.from_key(private_key)
            return account.address
        except ImportError:
            raise WalletError("Ethereum库未安装，无法验证私钥")
    
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