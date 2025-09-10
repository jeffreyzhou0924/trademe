"""
多链钱包生成器 - 支持TRON和Ethereum钱包生成
"""

import os
import secrets
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
from eth_account import Account
from tronpy import Tron
from tronpy.keys import PrivateKey as TronPrivateKey
import logging

logger = logging.getLogger(__name__)


@dataclass
class WalletInfo:
    """钱包信息数据类"""
    id: Optional[int] = None
    name: str = ""
    network: str = ""
    address: str = ""
    private_key: str = ""
    public_key: str = ""
    balance: Decimal = Decimal('0')
    status: str = "available"
    created_at: Optional[datetime] = None


class NetworkConfig:
    """网络配置"""
    
    # TRON网络配置
    TRON_MAINNET = {
        "name": "TRON_MAINNET",
        "rpc_url": "https://api.trongrid.io",
        "usdt_contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT-TRON合约地址
        "confirmations_required": 1,
        "network_id": "mainnet"
    }
    
    # Ethereum网络配置  
    ETHEREUM_MAINNET = {
        "name": "ETHEREUM_MAINNET", 
        "rpc_url": f"https://mainnet.infura.io/v3/{os.getenv('INFURA_PROJECT_ID', 'demo_key')}",
        "usdt_contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT-ERC20合约地址
        "confirmations_required": 12,
        "network_id": "mainnet"
    }
    
    @classmethod
    def get_network_config(cls, network: str) -> Dict[str, Any]:
        """获取网络配置"""
        network_configs = {
            "TRC20": cls.TRON_MAINNET,
            "ERC20": cls.ETHEREUM_MAINNET,
        }
        
        config = network_configs.get(network.upper())
        if not config:
            raise ValueError(f"不支持的网络类型: {network}")
        return config


class WalletGenerationError(Exception):
    """钱包生成异常"""
    pass


class WalletValidationError(Exception):
    """钱包验证异常"""
    pass


class MultiChainWalletGenerator:
    """多链钱包生成器"""
    
    def __init__(self):
        """初始化钱包生成器"""
        self.supported_networks = ["TRC20", "ERC20"]
        logger.info("多链钱包生成器初始化完成")
    
    def generate_wallet(self, network: str, wallet_name: str = "") -> WalletInfo:
        """
        生成钱包
        
        Args:
            network: 网络类型 (TRC20, ERC20)
            wallet_name: 钱包名称
            
        Returns:
            WalletInfo: 钱包信息
            
        Raises:
            WalletGenerationError: 钱包生成失败
        """
        try:
            network = network.upper()
            if network not in self.supported_networks:
                raise WalletGenerationError(f"不支持的网络类型: {network}")
            
            if network == "TRC20":
                return self._generate_tron_wallet(wallet_name)
            elif network == "ERC20":
                return self._generate_ethereum_wallet(wallet_name)
            else:
                raise WalletGenerationError(f"未实现的网络类型: {network}")
                
        except Exception as e:
            logger.error(f"钱包生成失败 - 网络: {network}, 错误: {str(e)[:100]}...")
            raise WalletGenerationError(f"钱包生成失败: {str(e)}")
    
    def _generate_tron_wallet(self, wallet_name: str) -> WalletInfo:
        """
        生成TRON钱包
        
        Args:
            wallet_name: 钱包名称
            
        Returns:
            WalletInfo: TRON钱包信息
        """
        try:
            # 生成私钥
            private_key_obj = TronPrivateKey.random()
            private_key_hex = private_key_obj.hex()
            
            # 获取公钥
            public_key_hex = private_key_obj.public_key.hex()
            
            # 获取地址
            address = private_key_obj.public_key.to_base58check_address()
            
            logger.info(f"TRON钱包生成成功 - 地址: {address[:8]}...{address[-8:]}")
            
            return WalletInfo(
                name=wallet_name or f"TRON_Wallet_{address[:8]}",
                network="TRC20",
                address=address,
                private_key=private_key_hex,
                public_key=public_key_hex,
                balance=Decimal('0'),
                status="available",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"TRON钱包生成失败: {str(e)[:100]}...")
            raise WalletGenerationError(f"TRON钱包生成失败: {str(e)}")
    
    def _generate_ethereum_wallet(self, wallet_name: str) -> WalletInfo:
        """
        生成Ethereum钱包
        
        Args:
            wallet_name: 钱包名称
            
        Returns:
            WalletInfo: Ethereum钱包信息
        """
        try:
            # 启用不安全的非确定性随机数生成 (开发环境)
            Account.enable_unaudited_hdwallet_features()
            
            # 生成账户
            account = Account.create()
            
            # 获取私钥 (去掉0x前缀)
            private_key_hex = account.key.hex()
            
            # 获取地址
            address = account.address
            
            # 从私钥获取公钥 (这里简化处理，实际公钥需要从私钥推导)
            public_key_hex = f"04{account.key.hex()[2:]}"  # 简化的公钥格式
            
            logger.info(f"Ethereum钱包生成成功 - 地址: {address[:8]}...{address[-8:]}")
            
            return WalletInfo(
                name=wallet_name or f"ETH_Wallet_{address[:8]}",
                network="ERC20",
                address=address,
                private_key=private_key_hex,
                public_key=public_key_hex,
                balance=Decimal('0'),
                status="available",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Ethereum钱包生成失败: {str(e)[:100]}...")
            raise WalletGenerationError(f"Ethereum钱包生成失败: {str(e)}")
    
    def import_wallet(self, network: str, private_key: str, wallet_name: str = "") -> WalletInfo:
        """
        导入钱包
        
        Args:
            network: 网络类型 (TRC20, ERC20)
            private_key: 私钥
            wallet_name: 钱包名称
            
        Returns:
            WalletInfo: 钱包信息
            
        Raises:
            WalletValidationError: 钱包验证失败
        """
        try:
            network = network.upper()
            if network not in self.supported_networks:
                raise WalletValidationError(f"不支持的网络类型: {network}")
            
            # 验证私钥格式
            private_key = self._normalize_private_key(private_key)
            
            if network == "TRC20":
                return self._import_tron_wallet(private_key, wallet_name)
            elif network == "ERC20":
                return self._import_ethereum_wallet(private_key, wallet_name)
            else:
                raise WalletValidationError(f"未实现的网络类型: {network}")
                
        except Exception as e:
            logger.error(f"钱包导入失败 - 网络: {network}, 错误: {str(e)[:100]}...")
            raise WalletValidationError(f"钱包导入失败: {str(e)}")
    
    def _import_tron_wallet(self, private_key: str, wallet_name: str) -> WalletInfo:
        """
        导入TRON钱包
        
        Args:
            private_key: 私钥
            wallet_name: 钱包名称
            
        Returns:
            WalletInfo: TRON钱包信息
        """
        try:
            # 从私钥创建TronPrivateKey对象
            private_key_obj = TronPrivateKey(bytes.fromhex(private_key))
            
            # 获取公钥
            public_key_hex = private_key_obj.public_key.hex()
            
            # 获取地址
            address = private_key_obj.public_key.to_base58check_address()
            
            logger.info(f"TRON钱包导入成功 - 地址: {address[:8]}...{address[-8:]}")
            
            return WalletInfo(
                name=wallet_name or f"TRON_Imported_{address[:8]}",
                network="TRC20",
                address=address,
                private_key=private_key,
                public_key=public_key_hex,
                balance=Decimal('0'),
                status="available",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"TRON钱包导入失败: {str(e)[:100]}...")
            raise WalletValidationError(f"TRON钱包导入失败: {str(e)}")
    
    def _import_ethereum_wallet(self, private_key: str, wallet_name: str) -> WalletInfo:
        """
        导入Ethereum钱包
        
        Args:
            private_key: 私钥
            wallet_name: 钱包名称
            
        Returns:
            WalletInfo: Ethereum钱包信息
        """
        try:
            # 从私钥创建Account对象
            account = Account.from_key(private_key)
            
            # 获取地址
            address = account.address
            
            # 生成公钥 (简化处理)
            public_key_hex = f"04{private_key[2:] if private_key.startswith('0x') else private_key}"
            
            logger.info(f"Ethereum钱包导入成功 - 地址: {address[:8]}...{address[-8:]}")
            
            return WalletInfo(
                name=wallet_name or f"ETH_Imported_{address[:8]}",
                network="ERC20",
                address=address,
                private_key=private_key,
                public_key=public_key_hex,
                balance=Decimal('0'),
                status="available",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Ethereum钱包导入失败: {str(e)[:100]}...")
            raise WalletValidationError(f"Ethereum钱包导入失败: {str(e)}")
    
    def validate_address(self, address: str, network: str) -> bool:
        """
        验证地址格式
        
        Args:
            address: 钱包地址
            network: 网络类型
            
        Returns:
            bool: 是否有效
        """
        try:
            network = network.upper()
            
            if network == "TRC20":
                return self._validate_tron_address(address)
            elif network == "ERC20":
                return self._validate_ethereum_address(address)
            else:
                return False
                
        except Exception as e:
            logger.error(f"地址验证失败 - 地址: {address[:8]}...{address[-8:] if len(address) > 16 else '***'}, 网络: {network}, 错误: {str(e)[:100]}...")
            return False
    
    def _validate_tron_address(self, address: str) -> bool:
        """验证TRON地址格式"""
        try:
            # TRON地址特征：以T开头，长度34
            if not address.startswith('T'):
                return False
            if len(address) != 34:
                return False
            
            # 使用tronpy验证地址格式 (简化验证)
            from tronpy import Tron
            tron = Tron()
            # 尝试获取账户信息来验证地址 (这里简化为格式检查)
            return True
            
        except Exception:
            return False
    
    def _validate_ethereum_address(self, address: str) -> bool:
        """验证Ethereum地址格式"""
        try:
            from web3 import Web3
            return Web3.is_address(address)
        except Exception:
            return False
    
    def _normalize_private_key(self, private_key: str) -> str:
        """
        标准化私钥格式
        
        Args:
            private_key: 原始私钥
            
        Returns:
            str: 标准化的私钥 (64位hex字符串)
        """
        # 移除0x前缀
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        
        # 验证长度 (64个十六进制字符 = 32字节)
        if len(private_key) != 64:
            raise WalletValidationError(f"私钥长度无效，期望64字符，实际{len(private_key)}字符")
        
        # 验证是否为有效的十六进制
        try:
            int(private_key, 16)
        except ValueError:
            raise WalletValidationError("私钥格式无效，必须是有效的十六进制字符串")
        
        return private_key.lower()
    
    def batch_generate_wallets(self, network: str, count: int, name_prefix: str = "wallet") -> list[WalletInfo]:
        """
        批量生成钱包
        
        Args:
            network: 网络类型
            count: 生成数量
            name_prefix: 名称前缀
            
        Returns:
            list[WalletInfo]: 钱包信息列表
        """
        wallets = []
        failed_count = 0
        
        logger.info(f"开始批量生成钱包 - 网络: {network}, 数量: {count}")
        
        for i in range(count):
            try:
                wallet_name = f"{name_prefix}_{network}_{i+1:04d}"
                wallet = self.generate_wallet(network, wallet_name)
                wallets.append(wallet)
                
                if (i + 1) % 10 == 0:  # 每10个记录一次进度
                    logger.info(f"批量生成进度: {i+1}/{count}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"批量生成第{i+1}个钱包失败: {str(e)[:100]}...")
                continue
        
        success_count = len(wallets)
        logger.info(f"批量生成完成 - 成功: {success_count}, 失败: {failed_count}")
        
        return wallets
    
    def get_supported_networks(self) -> list[str]:
        """获取支持的网络列表"""
        return self.supported_networks.copy()
    
    def get_network_info(self, network: str) -> Dict[str, Any]:
        """
        获取网络信息
        
        Args:
            network: 网络类型
            
        Returns:
            dict: 网络配置信息
        """
        try:
            return NetworkConfig.get_network_config(network)
        except Exception as e:
            logger.error(f"获取网络信息失败: {str(e)[:100]}...")
            return {}


# 单例钱包生成器实例
wallet_generator = MultiChainWalletGenerator()


def create_wallet_generator() -> MultiChainWalletGenerator:
    """创建钱包生成器实例"""
    return MultiChainWalletGenerator()


if __name__ == "__main__":
    """测试代码"""
    import asyncio
    
    async def test_wallet_generation():
        """测试钱包生成功能"""
        generator = MultiChainWalletGenerator()
        
        print("=== 测试钱包生成功能 ===")
        
        try:
            # 测试TRON钱包生成
            print("\n1. 测试TRON钱包生成")
            tron_wallet = generator.generate_wallet("TRC20", "测试TRON钱包")
            print(f"TRON钱包: {tron_wallet.address[:8]}...{tron_wallet.address[-8:]}")
            
            # 测试Ethereum钱包生成
            print("\n2. 测试Ethereum钱包生成")  
            eth_wallet = generator.generate_wallet("ERC20", "测试ETH钱包")
            print(f"Ethereum钱包: {eth_wallet.address[:8]}...{eth_wallet.address[-8:]}")
            
            # 测试地址验证
            print("\n3. 测试地址验证")
            tron_valid = generator.validate_address(tron_wallet.address, "TRC20")
            eth_valid = generator.validate_address(eth_wallet.address, "ERC20")
            print(f"TRON地址验证: {tron_valid}")
            print(f"Ethereum地址验证: {eth_valid}")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    # 运行测试
    asyncio.run(test_wallet_generation())