"""
区块链监控服务 - USDT支付系统核心组件
支持TRON (TRC20) 和 Ethereum (ERC20) 网络实时交易监控
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger
import aiohttp
import json

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.payment import USDTWallet, USDTPaymentOrder, BlockchainTransaction
from app.services.usdt_wallet_service import usdt_wallet_service
from app.core.config import settings


@dataclass
class TransactionInfo:
    """区块链交易信息"""
    tx_hash: str
    from_address: str
    to_address: str
    amount: Decimal
    network: str
    block_number: int
    confirmations: int
    timestamp: datetime
    status: str  # pending, confirmed, failed
    fee: Decimal = Decimal('0')


@dataclass
class MonitoringTask:
    """监控任务配置"""
    wallet_id: int
    address: str
    network: str
    is_active: bool = True
    last_block_checked: int = 0
    created_at: datetime = datetime.utcnow()


class BlockchainMonitorService:
    """区块链监控服务 - 支持TRON和Ethereum网络"""
    
    def __init__(self):
        # 网络配置
        self.tron_config = {
            'api_base': settings.tron_api_url,
            'api_key': settings.tron_api_key,
            'usdt_contract': settings.tron_usdt_contract,
            'decimals': 6
        }
        
        self.ethereum_config = {
            'api_base': settings.ethereum_rpc_url,
            'api_key': settings.ethereum_api_key,
            'usdt_contract': settings.ethereum_usdt_contract,
            'decimals': 6
        }
        
        # 监控配置
        self.monitoring_interval = settings.blockchain_monitor_interval
        self.confirmation_blocks = {
            'TRC20': 1,   # TRON确认块数
            'ERC20': 12,  # Ethereum确认块数
            'BEP20': 3    # BSC确认块数
        }
        
        # 监控任务列表
        self.monitoring_tasks: Dict[str, MonitoringTask] = {}
        self.is_monitoring = False
        
        # HTTP会话
        self._http_session: Optional[aiohttp.ClientSession] = None
    
    async def _get_http_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session
    
    async def start_monitoring(self):
        """启动区块链监控"""
        if self.is_monitoring:
            logger.warning("区块链监控已在运行中")
            return
        
        self.is_monitoring = True
        logger.info("启动区块链监控服务")
        
        # 加载现有监控任务
        await self._load_monitoring_tasks()
        
        # 启动监控循环
        asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """停止区块链监控"""
        self.is_monitoring = False
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        logger.info("区块链监控服务已停止")
    
    async def add_wallet_monitoring(
        self, 
        wallet_id: int, 
        address: str, 
        network: str
    ):
        """添加钱包监控"""
        task_key = f"{network}:{address}"
        
        if task_key in self.monitoring_tasks:
            logger.warning(f"钱包 {address} 已在监控列表中")
            return
        
        # 获取最新区块号作为起始点
        latest_block = await self._get_latest_block_number(network)
        
        task = MonitoringTask(
            wallet_id=wallet_id,
            address=address,
            network=network,
            last_block_checked=latest_block
        )
        
        self.monitoring_tasks[task_key] = task
        logger.info(f"添加钱包监控: {network} - {address}")
    
    async def remove_wallet_monitoring(self, address: str, network: str):
        """移除钱包监控"""
        task_key = f"{network}:{address}"
        if task_key in self.monitoring_tasks:
            del self.monitoring_tasks[task_key]
            logger.info(f"移除钱包监控: {network} - {address}")
    
    async def _load_monitoring_tasks(self):
        """从数据库加载监控任务"""
        async with AsyncSessionLocal() as session:
            # 加载所有活跃钱包
            query = select(USDTWallet).where(
                and_(
                    USDTWallet.status.in_(['available', 'occupied']),
                    USDTWallet.address.isnot(None)
                )
            )
            
            result = await session.execute(query)
            wallets = result.scalars().all()
            
            for wallet in wallets:
                await self.add_wallet_monitoring(
                    wallet.id, 
                    wallet.address, 
                    wallet.network
                )
    
    async def _monitoring_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                # 执行监控任务
                for task_key, task in self.monitoring_tasks.items():
                    if task.is_active:
                        await self._monitor_wallet_transactions(task)
                
                # 等待下一个监控周期
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}", exc_info=True)
                await asyncio.sleep(self.monitoring_interval)
    
    async def _monitor_wallet_transactions(self, task: MonitoringTask):
        """监控单个钱包的交易"""
        try:
            latest_block = await self._get_latest_block_number(task.network)
            
            if latest_block <= task.last_block_checked:
                return  # 没有新区块
            
            # 获取新交易
            transactions = await self._get_address_transactions(
                task.address,
                task.network,
                task.last_block_checked + 1,
                latest_block
            )
            
            # 处理交易
            for tx_info in transactions:
                await self._process_transaction(task, tx_info)
            
            # 更新最后检查的区块
            task.last_block_checked = latest_block
            
        except Exception as e:
            logger.error(f"监控钱包 {task.address} 错误: {e}")
    
    async def _process_transaction(self, task: MonitoringTask, tx_info: TransactionInfo):
        """处理交易信息"""
        async with AsyncSessionLocal() as session:
            try:
                # 检查交易是否已存在
                existing_tx = await session.execute(
                    select(BlockchainTransaction).where(
                        BlockchainTransaction.transaction_hash == tx_info.tx_hash
                    )
                )
                
                if existing_tx.scalar_one_or_none():
                    return  # 交易已处理
                
                # 创建交易记录
                blockchain_tx = BlockchainTransaction(
                    transaction_hash=tx_info.tx_hash,
                    network=tx_info.network,
                    from_address=tx_info.from_address,
                    to_address=tx_info.to_address,
                    amount=tx_info.amount,
                    fee=tx_info.fee,
                    block_number=tx_info.block_number,
                    confirmations=tx_info.confirmations,
                    status=tx_info.status,
                    transaction_time=tx_info.timestamp,
                    discovered_at=datetime.utcnow()
                )
                
                session.add(blockchain_tx)
                await session.commit()
                
                # 如果是入账交易，更新钱包余额
                if tx_info.to_address.lower() == task.address.lower():
                    await self._handle_incoming_transaction(task, tx_info)
                
                logger.info(f"处理交易: {tx_info.tx_hash}, 金额: {tx_info.amount}")
                
            except Exception as e:
                logger.error(f"处理交易 {tx_info.tx_hash} 错误: {e}")
                await session.rollback()
    
    async def _handle_incoming_transaction(
        self, 
        task: MonitoringTask, 
        tx_info: TransactionInfo
    ):
        """处理入账交易"""
        try:
            # 更新钱包余额
            await usdt_wallet_service.update_wallet_balance(
                task.wallet_id,
                tx_info.amount,  # 这里应该获取实际余额，而不是交易金额
                tx_info.block_number,
                'blockchain_monitor'
            )
            
            # 记录支付收到
            await usdt_wallet_service.record_payment_received(
                task.wallet_id,
                tx_info.amount,
                tx_info.tx_hash
            )
            
            # 检查是否有匹配的支付订单
            await self._match_payment_order(task, tx_info)
            
        except Exception as e:
            logger.error(f"处理入账交易 {tx_info.tx_hash} 错误: {e}")
    
    async def _match_payment_order(
        self, 
        task: MonitoringTask, 
        tx_info: TransactionInfo
    ):
        """匹配支付订单"""
        async with AsyncSessionLocal() as session:
            # 查找待确认的订单
            query = select(USDTPaymentOrder).where(
                and_(
                    USDTPaymentOrder.wallet_id == task.wallet_id,
                    USDTPaymentOrder.status == 'pending',
                    USDTPaymentOrder.to_address == tx_info.to_address,
                    USDTPaymentOrder.network == tx_info.network
                )
            )
            
            result = await session.execute(query)
            orders = result.scalars().all()
            
            for order in orders:
                # 检查金额匹配 (允许小幅误差)
                expected_amount = order.expected_amount
                received_amount = tx_info.amount
                tolerance = expected_amount * Decimal('0.01')  # 1%容差
                
                if abs(received_amount - expected_amount) <= tolerance:
                    # 匹配成功，更新订单状态
                    await session.execute(
                        update(USDTPaymentOrder)
                        .where(USDTPaymentOrder.id == order.id)
                        .values(
                            status='confirmed',
                            actual_amount=received_amount,
                            transaction_hash=tx_info.tx_hash,
                            confirmations=tx_info.confirmations,
                            confirmed_at=tx_info.timestamp
                        )
                    )
                    
                    await session.commit()
                    
                    logger.info(f"支付订单 {order.order_no} 确认成功: {tx_info.tx_hash}")
                    
                    # 释放钱包分配
                    await usdt_wallet_service.release_wallet(order.order_no)
    
    # TRON网络相关方法
    async def _get_tron_latest_block(self) -> int:
        """获取TRON最新区块号"""
        session = await self._get_http_session()
        url = f"{self.tron_config['api_base']}/wallet/getnowblock"
        
        headers = {}
        if self.tron_config['api_key']:
            headers['TRON-PRO-API-KEY'] = self.tron_config['api_key']
        
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            return data.get('block_header', {}).get('raw_data', {}).get('number', 0)
    
    async def _get_tron_transactions(
        self, 
        address: str, 
        start_block: int, 
        end_block: int
    ) -> List[TransactionInfo]:
        """获取TRON地址交易"""
        session = await self._get_http_session()
        transactions = []
        
        # 获取TRC20转账交易
        url = f"{self.tron_config['api_base']}/v1/accounts/{address}/transactions/trc20"
        params = {
            'limit': 200,
            'contract_address': self.tron_config['usdt_contract']
        }
        
        headers = {}
        if self.tron_config['api_key']:
            headers['TRON-PRO-API-KEY'] = self.tron_config['api_key']
        
        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            
            for tx in data.get('data', []):
                block_num = tx.get('block_timestamp', 0) // 1000  # 简化的区块号处理
                
                if start_block <= block_num <= end_block:
                    amount = Decimal(tx.get('value', '0')) / (10 ** self.tron_config['decimals'])
                    
                    tx_info = TransactionInfo(
                        tx_hash=tx.get('transaction_id', ''),
                        from_address=tx.get('from', ''),
                        to_address=tx.get('to', ''),
                        amount=amount,
                        network='TRC20',
                        block_number=block_num,
                        confirmations=1,  # TRON确认较快
                        timestamp=datetime.fromtimestamp(tx.get('block_timestamp', 0) / 1000),
                        status='confirmed'
                    )
                    
                    transactions.append(tx_info)
        
        return transactions
    
    # Ethereum网络相关方法
    async def _get_ethereum_latest_block(self) -> int:
        """获取Ethereum最新区块号"""
        session = await self._get_http_session()
        
        url = f"{self.ethereum_config['api_base']}/{self.ethereum_config['api_key']}"
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }
        
        async with session.post(url, json=payload) as response:
            data = await response.json()
            block_hex = data.get('result', '0x0')
            return int(block_hex, 16)
    
    async def _get_ethereum_transactions(
        self, 
        address: str, 
        start_block: int, 
        end_block: int
    ) -> List[TransactionInfo]:
        """获取Ethereum地址的ERC20 USDT交易"""
        session = await self._get_http_session()
        transactions = []
        
        # 使用Etherscan API获取ERC20转账
        etherscan_url = "https://api.etherscan.io/api"
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': self.ethereum_config['usdt_contract'],
            'address': address,
            'startblock': start_block,
            'endblock': end_block,
            'sort': 'desc',
            'apikey': settings.etherscan_api_key or 'YourApiKeyToken'
        }
        
        async with session.get(etherscan_url, params=params) as response:
            data = await response.json()
            
            if data.get('status') == '1':
                for tx in data.get('result', []):
                    amount = Decimal(tx.get('value', '0')) / (10 ** self.ethereum_config['decimals'])
                    block_num = int(tx.get('blockNumber', '0'))
                    
                    tx_info = TransactionInfo(
                        tx_hash=tx.get('hash', ''),
                        from_address=tx.get('from', ''),
                        to_address=tx.get('to', ''),
                        amount=amount,
                        network='ERC20',
                        block_number=block_num,
                        confirmations=int(tx.get('confirmations', '0')),
                        timestamp=datetime.fromtimestamp(int(tx.get('timeStamp', '0'))),
                        status='confirmed' if int(tx.get('confirmations', '0')) >= 12 else 'pending',
                        fee=Decimal(tx.get('gasUsed', '0')) * Decimal(tx.get('gasPrice', '0')) / (10 ** 18)
                    )
                    
                    transactions.append(tx_info)
        
        return transactions
    
    # 统一接口方法
    async def _get_latest_block_number(self, network: str) -> int:
        """获取最新区块号"""
        if network == 'TRC20':
            return await self._get_tron_latest_block()
        elif network == 'ERC20':
            return await self._get_ethereum_latest_block()
        else:
            raise ValueError(f"不支持的网络: {network}")
    
    async def _get_address_transactions(
        self, 
        address: str, 
        network: str, 
        start_block: int, 
        end_block: int
    ) -> List[TransactionInfo]:
        """获取地址交易"""
        if network == 'TRC20':
            return await self._get_tron_transactions(address, start_block, end_block)
        elif network == 'ERC20':
            return await self._get_ethereum_transactions(address, start_block, end_block)
        else:
            raise ValueError(f"不支持的网络: {network}")
    
    async def get_transaction_status(self, tx_hash: str, network: str) -> Dict[str, Any]:
        """获取交易状态"""
        session = await self._get_http_session()
        
        try:
            if network == 'TRC20':
                url = f"{self.tron_config['api_base']}/wallet/gettransactionbyid"
                data = {'value': tx_hash}
                
                headers = {}
                if self.tron_config['api_key']:
                    headers['TRON-PRO-API-KEY'] = self.tron_config['api_key']
                
                async with session.post(url, json=data, headers=headers) as response:
                    result = await response.json()
                    return {
                        'status': 'confirmed' if result.get('ret', [{}])[0].get('contractRet') == 'SUCCESS' else 'failed',
                        'confirmations': 1,
                        'block_number': result.get('blockNumber', 0)
                    }
            
            elif network == 'ERC20':
                url = f"{self.ethereum_config['api_base']}/{self.ethereum_config['api_key']}"
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionReceipt",
                    "params": [tx_hash],
                    "id": 1
                }
                
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    receipt = data.get('result')
                    
                    if receipt:
                        block_number = int(receipt.get('blockNumber', '0x0'), 16)
                        current_block = await self._get_ethereum_latest_block()
                        confirmations = max(0, current_block - block_number)
                        
                        return {
                            'status': 'confirmed' if receipt.get('status') == '0x1' else 'failed',
                            'confirmations': confirmations,
                            'block_number': block_number
                        }
            
            return {'status': 'pending', 'confirmations': 0, 'block_number': 0}
            
        except Exception as e:
            logger.error(f"获取交易状态失败 {tx_hash}: {e}")
            return {'status': 'unknown', 'confirmations': 0, 'block_number': 0}
    
    async def get_address_balance(self, address: str, network: str) -> Decimal:
        """获取地址USDT余额"""
        session = await self._get_http_session()
        
        try:
            if network == 'TRC20':
                # 获取TRC20 USDT余额
                url = f"{self.tron_config['api_base']}/v1/accounts/{address}"
                
                headers = {}
                if self.tron_config['api_key']:
                    headers['TRON-PRO-API-KEY'] = self.tron_config['api_key']
                
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    
                    for token in data.get('data', [{}])[0].get('trc20', []):
                        if token.get('contract_address') == self.tron_config['usdt_contract']:
                            balance = Decimal(token.get('balance', '0'))
                            return balance / (10 ** self.tron_config['decimals'])
                    
                    return Decimal('0')
            
            elif network == 'ERC20':
                # 获取ERC20 USDT余额
                url = f"{self.ethereum_config['api_base']}/{self.ethereum_config['api_key']}"
                
                # ERC20 balanceOf方法调用
                balance_selector = '0x70a08231'  # balanceOf(address)的函数选择器
                address_param = address[2:].zfill(64) if address.startswith('0x') else address.zfill(64)
                
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{
                        "to": self.ethereum_config['usdt_contract'],
                        "data": balance_selector + address_param
                    }, "latest"],
                    "id": 1
                }
                
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    result = data.get('result', '0x0')
                    balance = int(result, 16)
                    return Decimal(balance) / (10 ** self.ethereum_config['decimals'])
            
            return Decimal('0')
            
        except Exception as e:
            logger.error(f"获取地址余额失败 {address}: {e}")
            return Decimal('0')
    
    async def sync_wallet_balance(self, wallet_id: int):
        """同步钱包余额"""
        async with AsyncSessionLocal() as session:
            wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
            result = await session.execute(wallet_query)
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                logger.error(f"钱包 ID {wallet_id} 不存在")
                return
            
            # 从区块链获取实际余额
            actual_balance = await self.get_address_balance(wallet.address, wallet.network)
            
            # 更新钱包余额
            await usdt_wallet_service.update_wallet_balance(
                wallet_id,
                actual_balance,
                sync_source='manual_sync'
            )
            
            logger.info(f"同步钱包余额: {wallet.address} = {actual_balance} USDT")


# 全局实例
blockchain_monitor_service = BlockchainMonitorService()