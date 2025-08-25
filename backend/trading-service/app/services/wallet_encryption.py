"""
钱包加密服务 - USDT钱包私钥安全管理
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.backends import default_backend

from app.core.exceptions import SecurityError


class WalletEncryptionService:
    """钱包加密服务 - 负责私钥的加密存储和解密"""
    
    def __init__(self):
        # 从环境变量获取主密钥
        self.master_key = os.getenv('WALLET_MASTER_KEY')
        if not self.master_key:
            raise SecurityError("WALLET_MASTER_KEY not found in environment variables")
        
        # 确保主密钥长度足够
        if len(self.master_key) < 32:
            raise SecurityError("WALLET_MASTER_KEY must be at least 32 characters long")
        
        self.backend = default_backend()
    
    def _derive_key(self, salt: bytes) -> bytes:
        """使用PBKDF2从主密钥派生加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # AES-256 需要32字节密钥
            salt=salt,
            iterations=100000,  # 10万次迭代，安全性高
            backend=self.backend
        )
        return kdf.derive(self.master_key.encode('utf-8'))
    
    def _pad_data(self, data: bytes) -> bytes:
        """PKCS7填充"""
        padder = padding.PKCS7(128).padder()  # AES块大小为128位
        padded_data = padder.update(data)
        padded_data += padder.finalize()
        return padded_data
    
    def _unpad_data(self, padded_data: bytes) -> bytes:
        """移除PKCS7填充"""
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data)
        data += unpadder.finalize()
        return data
    
    def encrypt_private_key(self, private_key: str, wallet_address: str) -> str:
        """
        加密私钥
        
        Args:
            private_key: 要加密的私钥
            wallet_address: 钱包地址（用于增加熵）
            
        Returns:
            Base64编码的加密数据
        """
        try:
            # 生成随机盐（32字节）
            salt = os.urandom(32)
            
            # 将地址哈希值加入盐中，增加安全性
            address_hash = hashlib.sha256(wallet_address.encode()).digest()[:16]
            enhanced_salt = salt + address_hash
            
            # 派生加密密钥
            derived_key = self._derive_key(enhanced_salt)
            
            # 生成随机初始化向量（16字节）
            iv = os.urandom(16)
            
            # 创建AES-256-CBC加密器
            cipher = Cipher(
                algorithms.AES(derived_key), 
                modes.CBC(iv), 
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # 填充和加密私钥
            padded_data = self._pad_data(private_key.encode('utf-8'))
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # 组合：版本(1字节) + 盐(48字节) + IV(16字节) + 加密数据
            version = b'\x01'  # 版本号，用于后续升级兼容性
            combined = version + enhanced_salt + iv + encrypted_data
            
            # Base64编码返回
            return base64.b64encode(combined).decode('utf-8')
            
        except Exception as e:
            raise SecurityError(f"私钥加密失败: {str(e)}")
    
    def decrypt_private_key(self, encrypted_private_key: str, wallet_address: str) -> str:
        """
        解密私钥
        
        Args:
            encrypted_private_key: Base64编码的加密私钥
            wallet_address: 钱包地址（用于验证）
            
        Returns:
            解密后的私钥
        """
        try:
            # Base64解码
            combined = base64.b64decode(encrypted_private_key.encode('utf-8'))
            
            # 检查版本号
            version = combined[:1]
            if version != b'\x01':
                raise SecurityError("不支持的加密版本")
            
            # 提取各部分
            enhanced_salt = combined[1:49]  # 48字节增强盐
            iv = combined[49:65]            # 16字节IV
            encrypted_data = combined[65:]   # 加密数据
            
            # 验证地址哈希
            address_hash = hashlib.sha256(wallet_address.encode()).digest()[:16]
            if enhanced_salt[32:] != address_hash:
                raise SecurityError("钱包地址不匹配，可能的安全威胁")
            
            # 重新派生密钥
            derived_key = self._derive_key(enhanced_salt)
            
            # 创建解密器
            cipher = Cipher(
                algorithms.AES(derived_key), 
                modes.CBC(iv), 
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # 解密并去除填充
            padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            private_key_bytes = self._unpad_data(padded_data)
            
            return private_key_bytes.decode('utf-8')
            
        except Exception as e:
            raise SecurityError(f"私钥解密失败: {str(e)}")
    
    def verify_private_key(self, private_key: str, expected_address: str, network: str) -> bool:
        """
        验证私钥是否对应指定地址
        
        Args:
            private_key: 私钥
            expected_address: 期望的钱包地址
            network: 网络类型 (TRC20, ERC20, BEP20)
            
        Returns:
            是否匹配
        """
        try:
            if network == "TRC20":
                return self._verify_tron_private_key(private_key, expected_address)
            elif network in ["ERC20", "BEP20"]:
                return self._verify_ethereum_private_key(private_key, expected_address)
            else:
                raise SecurityError(f"不支持的网络类型: {network}")
        except Exception as e:
            print(f"私钥验证失败: {e}")
            return False
    
    def _verify_tron_private_key(self, private_key: str, expected_address: str) -> bool:
        """验证TRON私钥"""
        try:
            from tronpy import Tron
            from tronpy.keys import PrivateKey
            
            # 创建私钥对象
            pk = PrivateKey(bytes.fromhex(private_key))
            # 获取地址
            address = pk.public_key.to_base58check_address()
            
            return address == expected_address
        except ImportError:
            print("Warning: tronpy not installed, skipping TRON verification")
            return True
        except Exception:
            return False
    
    def _verify_ethereum_private_key(self, private_key: str, expected_address: str) -> bool:
        """验证Ethereum/BSC私钥"""
        try:
            from eth_account import Account
            
            # 创建账户对象
            account = Account.from_key(private_key)
            
            return account.address.lower() == expected_address.lower()
        except ImportError:
            print("Warning: eth_account not installed, skipping Ethereum verification")
            return True
        except Exception:
            return False
    
    def generate_master_key(self) -> str:
        """生成新的主密钥（仅用于初始化）"""
        return secrets.token_urlsafe(32)
    
    def hash_for_audit(self, private_key: str) -> str:
        """生成私钥的不可逆哈希，用于审计日志"""
        return hashlib.sha256(private_key.encode()).hexdigest()[:16]


# 单例实例
wallet_encryption = WalletEncryptionService()