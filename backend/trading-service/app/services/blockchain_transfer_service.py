"""
区块链转账服务 - 实现真实的USDT转账功能
支持 TRON (TRC20) 和 Ethereum (ERC20) 网络
"""

import asyncio
import logging
from typing import Optional, Dict, Tuple
from decimal import Decimal
from datetime import datetime

from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # 适配不同版本的web3.py
    try:
        from web3.middleware import construct_sign_and_send_raw_middleware
        geth_poa_middleware = None
    except ImportError:
        geth_poa_middleware = None
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.exceptions import TransactionError, ValidationError

from app.config import settings
from app.core.exceptions import BlockchainError

logger = logging.getLogger(__name__)


class BlockchainTransferService:
    """区块链转账服务 - 处理USDT转账"""
    
    def __init__(self):
        # TRON网络配置
        self.tron_network = 'mainnet' if settings.environment == 'production' else 'nile'  # testnet
        self.tron_client = Tron(network=self.tron_network)
        self.tron_usdt_contract = settings.tron_usdt_contract or 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'  # MainNet USDT
        
        # Ethereum网络配置
        self.ethereum_rpc_url = settings.ethereum_rpc_url or 'https://mainnet.infura.io/v3/YOUR_API_KEY'
        self.web3 = Web3(Web3.HTTPProvider(self.ethereum_rpc_url))
        
        # 添加POA中间件（用于BSC等POA链）
        if geth_poa_middleware:
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Ethereum USDT合约地址
        self.ethereum_usdt_contract = settings.ethereum_usdt_contract or '0xdAC17F958D2ee523a2206206994597C13D831ec7'
        
        # ERC20 USDT ABI (只包含transfer功能)
        self.usdt_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
    
    async def transfer_usdt(
        self, 
        network: str, 
        from_private_key: str, 
        to_address: str, 
        amount: Decimal,
        gas_price: Optional[int] = None
    ) -> Tuple[str, bool]:
        """
        执行USDT转账
        
        Args:
            network: 网络类型 (TRC20, ERC20)
            from_private_key: 发送方私钥
            to_address: 接收方地址
            amount: 转账金额 (USDT)
            gas_price: Gas价格 (仅ERC20需要)
            
        Returns:
            Tuple[交易哈希, 是否成功]
        """
        try:
            if network.upper() == 'TRC20':
                return await self._transfer_trc20(from_private_key, to_address, amount)
            elif network.upper() == 'ERC20':
                return await self._transfer_erc20(from_private_key, to_address, amount, gas_price)
            else:
                raise BlockchainError(f"不支持的网络类型: {network}")
                
        except Exception as e:
            logger.error(f"USDT转账失败 - {network}: {e}")
            return "", False
    
    async def _transfer_trc20(self, private_key: str, to_address: str, amount: Decimal) -> Tuple[str, bool]:
        """执行TRC20 USDT转账"""
        try:
            # 创建私钥对象
            priv_key = PrivateKey(bytes.fromhex(private_key))
            from_address = priv_key.public_key.to_base58check_address()
            
            # 获取USDT合约
            contract = self.tron_client.get_contract(self.tron_usdt_contract)
            
            # 准备转账参数 (USDT使用6位小数)
            transfer_amount = int(amount * Decimal('1000000'))  # 转换为最小单位
            
            logger.info(f"TRC20转账: {from_address} -> {to_address}, 金额: {amount} USDT")
            
            # 构建转账交易
            txn = (
                contract.functions.transfer(to_address, transfer_amount)
                .with_owner(from_address)
                .fee_limit(100_000_000)  # 100 TRX fee limit
                .build()
                .sign(priv_key)
            )
            
            # 广播交易
            result = txn.broadcast()
            
            if result.get('result'):
                tx_hash = result['txid']
                logger.info(f"TRC20转账成功: {tx_hash}")
                return tx_hash, True
            else:
                logger.error(f"TRC20转账失败: {result}")
                return "", False
                
        except TransactionError as e:
            logger.error(f"TRC20交易错误: {e}")
            return "", False
        except ValidationError as e:
            logger.error(f"TRC20验证错误: {e}")
            return "", False
        except Exception as e:
            logger.error(f"TRC20转账异常: {e}")
            return "", False
    
    async def _transfer_erc20(
        self, 
        private_key: str, 
        to_address: str, 
        amount: Decimal, 
        gas_price: Optional[int] = None
    ) -> Tuple[str, bool]:
        """执行ERC20 USDT转账"""
        try:
            # 验证网络连接
            if not self.web3.is_connected():
                raise BlockchainError("无法连接到Ethereum网络")
            
            # 创建账户对象
            account = self.web3.eth.account.from_key(private_key)
            from_address = account.address
            
            # 获取USDT合约实例
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.ethereum_usdt_contract),
                abi=self.usdt_abi
            )
            
            # USDT使用6位小数
            transfer_amount = int(amount * Decimal('1000000'))
            
            logger.info(f"ERC20转账: {from_address} -> {to_address}, 金额: {amount} USDT")
            
            # 获取nonce
            nonce = self.web3.eth.get_transaction_count(from_address)
            
            # 构建交易
            transaction = contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                transfer_amount
            ).build_transaction({
                'chainId': await self._get_chain_id(),
                'gas': 100000,  # USDT转账通常需要约60k-80k gas
                'gasPrice': gas_price or self.web3.to_wei('20', 'gwei'),
                'nonce': nonce,
            })
            
            # 签名交易
            signed_txn = self.web3.eth.account.sign_transaction(transaction, private_key)
            
            # 广播交易
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"ERC20转账已提交: {tx_hash_hex}")
            
            # 等待交易确认 (可选, 这里只是提交交易)
            # receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            # if receipt.status == 1:
            #     logger.info(f"ERC20转账确认成功: {tx_hash_hex}")
            #     return tx_hash_hex, True
            
            return tx_hash_hex, True
            
        except Exception as e:
            logger.error(f"ERC20转账异常: {e}")
            return "", False
    
    async def _get_chain_id(self) -> int:
        """获取链ID"""
        try:
            return self.web3.eth.chain_id
        except Exception:
            return 1  # 默认以太坊主网
    
    async def get_balance(self, network: str, address: str) -> Decimal:
        """获取地址的USDT余额"""
        try:
            if network.upper() == 'TRC20':
                return await self._get_trc20_balance(address)
            elif network.upper() == 'ERC20':
                return await self._get_erc20_balance(address)
            else:
                raise BlockchainError(f"不支持的网络类型: {network}")
        except Exception as e:
            logger.error(f"获取{network}余额失败: {e}")
            return Decimal('0')
    
    async def _get_trc20_balance(self, address: str) -> Decimal:
        """获取TRC20 USDT余额"""
        try:
            contract = self.tron_client.get_contract(self.tron_usdt_contract)
            balance = contract.functions.balanceOf(address)
            # USDT使用6位小数
            return Decimal(balance) / Decimal('1000000')
        except Exception as e:
            logger.error(f"获取TRC20余额异常: {e}")
            return Decimal('0')
    
    async def _get_erc20_balance(self, address: str) -> Decimal:
        """获取ERC20 USDT余额"""
        try:
            if not self.web3.is_connected():
                raise BlockchainError("无法连接到Ethereum网络")
            
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.ethereum_usdt_contract),
                abi=self.usdt_abi
            )
            
            balance = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
            # USDT使用6位小数
            return Decimal(balance) / Decimal('1000000')
            
        except Exception as e:
            logger.error(f"获取ERC20余额异常: {e}")
            return Decimal('0')
    
    async def verify_transaction(self, network: str, tx_hash: str) -> Dict:
        """验证交易状态"""
        try:
            if network.upper() == 'TRC20':
                return await self._verify_trc20_transaction(tx_hash)
            elif network.upper() == 'ERC20':
                return await self._verify_erc20_transaction(tx_hash)
            else:
                return {"status": "error", "message": f"不支持的网络类型: {network}"}
        except Exception as e:
            logger.error(f"验证{network}交易失败: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _verify_trc20_transaction(self, tx_hash: str) -> Dict:
        """验证TRC20交易"""
        try:
            tx_info = self.tron_client.get_transaction(tx_hash)
            
            return {
                "status": "confirmed" if tx_info.get('ret', [{}])[0].get('contractRet') == 'SUCCESS' else "failed",
                "block_number": tx_info.get('blockNumber'),
                "confirmations": 1,  # TRON通常1个确认即可
                "timestamp": datetime.fromtimestamp(tx_info.get('block_timestamp', 0) / 1000)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _verify_erc20_transaction(self, tx_hash: str) -> Dict:
        """验证ERC20交易"""
        try:
            if not self.web3.is_connected():
                raise BlockchainError("无法连接到Ethereum网络")
            
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            block = self.web3.eth.get_block(receipt.blockNumber)
            current_block = self.web3.eth.block_number
            
            return {
                "status": "confirmed" if receipt.status == 1 else "failed",
                "block_number": receipt.blockNumber,
                "confirmations": current_block - receipt.blockNumber + 1,
                "timestamp": datetime.fromtimestamp(block.timestamp)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# 全局实例
blockchain_transfer_service = BlockchainTransferService()