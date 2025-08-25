"""
区块链监控服务 - TRON/Ethereum/BSC网络交易监控
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Union, Any
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.models.payment import BlockchainTransaction, USDTWallet, USDTPaymentOrder
from app.core.exceptions import BlockchainError, NetworkError
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransactionStatus:
    """交易状态信息"""
    tx_hash: str
    is_confirmed: bool
    is_pending: bool
    is_failed: bool
    confirmations: int
    block_number: Optional[int]
    amount: Optional[Decimal]
    from_address: Optional[str]
    to_address: Optional[str]
    timestamp: Optional[datetime]


@dataclass
class NetworkConfig:
    """区块链网络配置"""
    name: str
    chain_id: Optional[int]
    rpc_urls: List[str]
    websocket_url: Optional[str]
    explorer_url: str
    usdt_contract: str
    required_confirmations: int
    block_time: int  # 出块时间（秒）
    native_currency: str


class BlockchainMonitorService:
    """区块链监控服务"""
    
    # 网络配置
    NETWORK_CONFIGS = {
        "TRC20": NetworkConfig(
            name="TRON",
            chain_id=None,
            rpc_urls=[
                "https://api.trongrid.io",
                "https://api.tronstack.io",
                "https://nile.trongrid.io"  # 测试网备用
            ],
            websocket_url="wss://api.trongrid.io/websocket",
            explorer_url="https://tronscan.org",
            usdt_contract="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            required_confirmations=1,
            block_time=3,
            native_currency="TRX"
        ),
        "ERC20": NetworkConfig(
            name="Ethereum",
            chain_id=1,
            rpc_urls=[
                "https://eth-mainnet.alchemyapi.io/v2/demo",
                "https://mainnet.infura.io/v3/demo",
                "https://cloudflare-eth.com"
            ],
            websocket_url="wss://eth-mainnet.alchemyapi.io/v2/demo",
            explorer_url="https://etherscan.io",
            usdt_contract="0xdAC17F958D2ee523a2206206994597C13D831ec7",
            required_confirmations=12,
            block_time=12,
            native_currency="ETH"
        ),
        "BEP20": NetworkConfig(
            name="BSC",
            chain_id=56,
            rpc_urls=[
                "https://bsc-dataseed1.binance.org",
                "https://bsc-dataseed2.binance.org",
                "https://bsc-dataseed3.binance.org"
            ],
            websocket_url="wss://bsc-websocket-node.nariox.org",
            explorer_url="https://bscscan.com",
            usdt_contract="0x55d398326f99059fF775485246999027B3197955",
            required_confirmations=3,
            block_time=3,
            native_currency="BNB"
        )
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session = aiohttp.ClientSession()
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.rpc_clients: Dict[str, int] = {}  # 当前使用的RPC索引
        
    async def close(self):
        """关闭监控服务"""
        # 取消所有监控任务
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        # 关闭HTTP会话
        if self.session:
            await self.session.close()
    
    async def start_monitoring(self, network: str) -> bool:
        """
        启动网络监控
        
        Args:
            network: 网络类型
            
        Returns:
            是否启动成功
        """
        if network not in self.NETWORK_CONFIGS:
            raise BlockchainError(f"不支持的网络: {network}")
        
        if network in self.monitoring_tasks:
            logger.info(f"{network} 监控已在运行")
            return True
        
        try:
            # 创建监控任务
            task = asyncio.create_task(self._monitor_network(network))
            self.monitoring_tasks[network] = task
            
            logger.info(f"成功启动 {network} 网络监控")
            return True
            
        except Exception as e:
            logger.error(f"启动 {network} 监控失败: {e}")
            return False
    
    async def stop_monitoring(self, network: str) -> bool:
        """
        停止网络监控
        
        Args:
            network: 网络类型
            
        Returns:
            是否停止成功
        """
        if network not in self.monitoring_tasks:
            return True
        
        try:
            task = self.monitoring_tasks[network]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            del self.monitoring_tasks[network]
            logger.info(f"已停止 {network} 网络监控")
            return True
            
        except Exception as e:
            logger.error(f"停止 {network} 监控失败: {e}")
            return False
    
    async def check_transaction(
        self, 
        tx_hash: str, 
        network: str,
        expected_address: Optional[str] = None,
        expected_amount: Optional[Decimal] = None
    ) -> TransactionStatus:
        """
        检查交易状态
        
        Args:
            tx_hash: 交易哈希
            network: 网络类型
            expected_address: 期望的收款地址
            expected_amount: 期望的金额
            
        Returns:
            交易状态信息
        """
        if network not in self.NETWORK_CONFIGS:
            raise BlockchainError(f"不支持的网络: {network}")
        
        try:
            if network == "TRC20":
                return await self._check_tron_transaction(tx_hash, expected_address, expected_amount)
            else:  # ERC20 or BEP20
                return await self._check_ethereum_transaction(tx_hash, network, expected_address, expected_amount)
                
        except Exception as e:
            logger.error(f"检查 {network} 交易 {tx_hash} 失败: {e}")
            raise BlockchainError(f"交易查询失败: {str(e)}")
    
    async def monitor_address(self, address: str, network: str) -> List[TransactionStatus]:
        """
        监控特定地址的新交易
        
        Args:
            address: 钱包地址
            network: 网络类型
            
        Returns:
            新交易列表
        """
        if network not in self.NETWORK_CONFIGS:
            raise BlockchainError(f"不支持的网络: {network}")
        
        try:
            if network == "TRC20":
                return await self._monitor_tron_address(address)
            else:  # ERC20 or BEP20
                return await self._monitor_ethereum_address(address, network)
                
        except Exception as e:
            logger.error(f"监控 {network} 地址 {address} 失败: {e}")
            return []
    
    async def get_balance(self, address: str, network: str) -> Decimal:
        """
        获取地址USDT余额
        
        Args:
            address: 钱包地址
            network: 网络类型
            
        Returns:
            USDT余额
        """
        if network not in self.NETWORK_CONFIGS:
            raise BlockchainError(f"不支持的网络: {network}")
        
        try:
            if network == "TRC20":
                return await self._get_tron_usdt_balance(address)
            else:  # ERC20 or BEP20
                return await self._get_ethereum_usdt_balance(address, network)
                
        except Exception as e:
            logger.error(f"获取 {network} 地址 {address} 余额失败: {e}")
            return Decimal('0')
    
    async def _monitor_network(self, network: str):
        """网络监控主循环"""
        config = self.NETWORK_CONFIGS[network]
        
        while True:
            try:
                # 获取需要监控的地址列表
                addresses = await self._get_monitoring_addresses(network)
                
                if not addresses:
                    await asyncio.sleep(30)  # 无地址需要监控，等待30秒
                    continue
                
                # 批量检查地址交易
                tasks = [self.monitor_address(addr, network) for addr in addresses]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理结果
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"监控地址 {addresses[i]} 失败: {result}")
                        continue
                    
                    # 处理新交易
                    for tx_status in result:
                        await self._process_new_transaction(tx_status, network)
                
                # 等待下一次检查
                await asyncio.sleep(config.block_time * 2)  # 2倍出块时间
                
            except asyncio.CancelledError:
                logger.info(f"{network} 监控任务被取消")
                break
            except Exception as e:
                logger.error(f"{network} 监控循环出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
    
    async def _check_tron_transaction(
        self, 
        tx_hash: str, 
        expected_address: Optional[str] = None,
        expected_amount: Optional[Decimal] = None
    ) -> TransactionStatus:
        """检查TRON交易"""
        config = self.NETWORK_CONFIGS["TRC20"]
        
        try:
            # 使用TronGrid API查询交易
            url = f"{config.rpc_urls[0]}/wallet/gettransactionbyid"
            data = {"value": tx_hash}
            
            async with self.session.post(url, json=data) as response:
                if response.status != 200:
                    raise NetworkError(f"TronGrid API错误: {response.status}")
                
                result = await response.json()
                
                if not result or 'txID' not in result:
                    return TransactionStatus(
                        tx_hash=tx_hash,
                        is_confirmed=False,
                        is_pending=False,
                        is_failed=True,
                        confirmations=0,
                        block_number=None,
                        amount=None,
                        from_address=None,
                        to_address=None,
                        timestamp=None
                    )
                
                # 检查交易是否确认
                is_confirmed = 'block_timestamp' in result
                confirmations = 1 if is_confirmed else 0
                
                # 解析交易详情
                amount = None
                from_address = None
                to_address = None
                
                if 'raw_data' in result and 'contract' in result['raw_data']:
                    contract = result['raw_data']['contract'][0]
                    if contract['type'] == 'TriggerSmartContract':
                        # USDT转账交易
                        parameter = contract['parameter']['value']
                        to_address = self._tron_hex_to_address(parameter.get('contract_address', ''))
                        
                        # 解析转账数据
                        data = parameter.get('data', '')
                        if len(data) >= 136:  # transfer(address,uint256)
                            to_addr_hex = data[32:72]
                            amount_hex = data[72:136]
                            
                            to_address = self._tron_hex_to_address(to_addr_hex)
                            amount = Decimal(int(amount_hex, 16)) / (10 ** 6)  # USDT 6位小数
                
                timestamp = None
                if 'block_timestamp' in result:
                    timestamp = datetime.fromtimestamp(result['block_timestamp'] / 1000)
                
                return TransactionStatus(
                    tx_hash=tx_hash,
                    is_confirmed=is_confirmed,
                    is_pending=not is_confirmed,
                    is_failed=False,
                    confirmations=confirmations,
                    block_number=result.get('blockNumber'),
                    amount=amount,
                    from_address=from_address,
                    to_address=to_address,
                    timestamp=timestamp
                )
                
        except Exception as e:
            logger.error(f"检查TRON交易失败: {e}")
            raise
    
    async def _check_ethereum_transaction(
        self, 
        tx_hash: str, 
        network: str,
        expected_address: Optional[str] = None,
        expected_amount: Optional[Decimal] = None
    ) -> TransactionStatus:
        """检查Ethereum/BSC交易"""
        config = self.NETWORK_CONFIGS[network]
        
        try:
            # 获取交易信息
            rpc_url = await self._get_rpc_url(network)
            
            # 查询交易
            tx_data = {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionByHash",
                "params": [tx_hash],
                "id": 1
            }
            
            async with self.session.post(rpc_url, json=tx_data) as response:
                result = await response.json()
                
                if 'error' in result:
                    raise NetworkError(f"RPC错误: {result['error']}")
                
                tx = result.get('result')
                if not tx:
                    return TransactionStatus(
                        tx_hash=tx_hash,
                        is_confirmed=False,
                        is_pending=False,
                        is_failed=True,
                        confirmations=0,
                        block_number=None,
                        amount=None,
                        from_address=None,
                        to_address=None,
                        timestamp=None
                    )
                
                # 获取交易收据
                receipt_data = {
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionReceipt",
                    "params": [tx_hash],
                    "id": 2
                }
                
                async with self.session.post(rpc_url, json=receipt_data) as receipt_response:
                    receipt_result = await receipt_response.json()
                    receipt = receipt_result.get('result')
                
                # 检查确认状态
                is_confirmed = receipt and receipt.get('blockNumber') is not None
                block_number = int(receipt['blockNumber'], 16) if is_confirmed else None
                
                # 计算确认数
                confirmations = 0
                if is_confirmed:
                    latest_block = await self._get_latest_block_number(network)
                    confirmations = max(0, latest_block - block_number + 1)
                
                # 解析USDT转账金额
                amount = None
                to_address = None
                
                if receipt and receipt.get('logs'):
                    for log in receipt['logs']:
                        if log.get('address', '').lower() == config.usdt_contract.lower():
                            # 解析Transfer事件
                            topics = log.get('topics', [])
                            if len(topics) >= 3 and topics[0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                                to_address = '0x' + topics[2][26:]  # 去掉前面的0
                                amount_hex = log.get('data', '0x0')
                                amount = Decimal(int(amount_hex, 16)) / (10 ** 6)  # USDT 6位小数
                
                return TransactionStatus(
                    tx_hash=tx_hash,
                    is_confirmed=is_confirmed and confirmations >= config.required_confirmations,
                    is_pending=is_confirmed and confirmations < config.required_confirmations,
                    is_failed=receipt and receipt.get('status') == '0x0',
                    confirmations=confirmations,
                    block_number=block_number,
                    amount=amount,
                    from_address=tx.get('from'),
                    to_address=to_address or tx.get('to'),
                    timestamp=None  # 需要额外查询区块时间戳
                )
                
        except Exception as e:
            logger.error(f"检查{network}交易失败: {e}")
            raise
    
    async def _get_monitoring_addresses(self, network: str) -> List[str]:
        """获取需要监控的地址列表"""
        try:
            # 查询有pending订单的钱包地址
            query = select(USDTWallet.address).join(
                USDTPaymentOrder,
                USDTWallet.id == USDTPaymentOrder.wallet_id
            ).where(
                and_(
                    USDTWallet.network == network,
                    USDTPaymentOrder.status == 'pending',
                    USDTPaymentOrder.expires_at > datetime.utcnow()
                )
            ).distinct()
            
            result = await self.db.execute(query)
            addresses = [row[0] for row in result.fetchall()]
            
            return addresses
            
        except Exception as e:
            logger.error(f"获取监控地址失败: {e}")
            return []
    
    async def _get_rpc_url(self, network: str) -> str:
        """获取当前使用的RPC URL"""
        config = self.NETWORK_CONFIGS[network]
        current_index = self.rpc_clients.get(network, 0)
        
        if current_index >= len(config.rpc_urls):
            current_index = 0
            self.rpc_clients[network] = current_index
        
        return config.rpc_urls[current_index]
    
    async def _switch_rpc_url(self, network: str):
        """切换到下一个RPC URL"""
        config = self.NETWORK_CONFIGS[network]
        current_index = self.rpc_clients.get(network, 0)
        next_index = (current_index + 1) % len(config.rpc_urls)
        self.rpc_clients[network] = next_index
        
        logger.info(f"切换{network} RPC到: {config.rpc_urls[next_index]}")
    
    async def _get_latest_block_number(self, network: str) -> int:
        """获取最新区块号"""
        if network == "TRC20":
            return await self._get_tron_latest_block()
        else:
            return await self._get_ethereum_latest_block(network)
    
    async def _get_tron_latest_block(self) -> int:
        """获取TRON最新区块"""
        config = self.NETWORK_CONFIGS["TRC20"]
        url = f"{config.rpc_urls[0]}/wallet/getnowblock"
        
        async with self.session.post(url) as response:
            result = await response.json()
            return result.get('block_header', {}).get('raw_data', {}).get('number', 0)
    
    async def _get_ethereum_latest_block(self, network: str) -> int:
        """获取Ethereum/BSC最新区块"""
        rpc_url = await self._get_rpc_url(network)
        data = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }
        
        async with self.session.post(rpc_url, json=data) as response:
            result = await response.json()
            return int(result.get('result', '0x0'), 16)
    
    async def _process_new_transaction(self, tx_status: TransactionStatus, network: str):
        """处理新发现的交易"""
        try:
            # 检查交易是否已存在
            existing_tx = await self.db.execute(
                select(BlockchainTransaction).where(
                    BlockchainTransaction.transaction_hash == tx_status.tx_hash
                )
            )
            
            if existing_tx.scalar_one_or_none():
                return  # 交易已存在
            
            # 创建新交易记录
            transaction = BlockchainTransaction(
                transaction_hash=tx_status.tx_hash,
                network=network,
                from_address=tx_status.from_address or '',
                to_address=tx_status.to_address or '',
                amount=tx_status.amount or Decimal('0'),
                block_number=tx_status.block_number,
                confirmations=tx_status.confirmations,
                status='confirmed' if tx_status.is_confirmed else 'pending',
                transaction_time=tx_status.timestamp or datetime.utcnow()
            )
            
            self.db.add(transaction)
            await self.db.commit()
            
            logger.info(f"记录新交易: {tx_status.tx_hash} ({network})")
            
            # 如果交易已确认，触发支付处理
            if tx_status.is_confirmed:
                await self._trigger_payment_confirmation(tx_status, network)
                
        except Exception as e:
            logger.error(f"处理新交易失败: {e}")
            await self.db.rollback()
    
    async def _trigger_payment_confirmation(self, tx_status: TransactionStatus, network: str):
        """触发支付确认处理"""
        # 这里会调用支付处理服务
        # 暂时只记录日志
        logger.info(f"触发支付确认: {tx_status.tx_hash} 金额: {tx_status.amount}")
    
    def _tron_hex_to_address(self, hex_str: str) -> str:
        """将TRON十六进制地址转换为Base58地址"""
        # 简化实现，实际需要完整的Base58转换
        return f"T{hex_str[-10:]}"
    
    # 其他辅助方法...
    async def _monitor_tron_address(self, address: str) -> List[TransactionStatus]:
        """监控TRON地址的简化实现"""
        return []
    
    async def _monitor_ethereum_address(self, address: str, network: str) -> List[TransactionStatus]:
        """监控Ethereum地址的简化实现"""
        return []
    
    async def _get_tron_usdt_balance(self, address: str) -> Decimal:
        """获取TRON USDT余额的简化实现"""
        return Decimal('0')
    
    async def _get_ethereum_usdt_balance(self, address: str, network: str) -> Decimal:
        """获取Ethereum USDT余额的简化实现"""
        return Decimal('0')