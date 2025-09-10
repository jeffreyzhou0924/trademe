"""
私钥加密存储系统 - AES-256-GCM加密保护
"""

import os
import secrets
import base64
import hashlib
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)


class CryptographyError(Exception):
    """加密相关异常"""
    pass


class KeyDerivationError(CryptographyError):
    """密钥派生异常"""
    pass


class EncryptionError(CryptographyError):
    """加密异常"""
    pass


class DecryptionError(CryptographyError):
    """解密异常"""
    pass


class CryptoManager:
    """
    密钥加密管理器
    
    使用AES-256-GCM加密算法保护私钥安全
    采用PBKDF2密钥派生函数增强安全性
    """
    
    # 加密配置常量
    AES_KEY_SIZE = 32  # AES-256需要32字节密钥
    GCM_NONCE_SIZE = 12  # GCM模式推荐12字节nonce
    PBKDF2_SALT_SIZE = 32  # PBKDF2盐值长度
    PBKDF2_ITERATIONS = 100000  # PBKDF2迭代次数 (100k次)
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化加密管理器
        
        Args:
            master_key: 主密钥 (如果不提供，将从配置获取)
        """
        if master_key:
            self.master_key = master_key
        else:
            # 先尝试从环境变量获取
            self.master_key = os.getenv('WALLET_MASTER_KEY')
            
            # 如果环境变量没有，尝试从配置文件获取
            if not self.master_key:
                try:
                    from app.config import settings
                    self.master_key = getattr(settings, 'wallet_master_key', None)
                except ImportError:
                    pass
        
        if not self.master_key:
            logger.warning("未配置主密钥，将生成临时密钥")
            self.master_key = self.generate_master_key()
        
        # 验证主密钥长度
        if len(self.master_key) < 32:
            raise KeyDerivationError("主密钥长度不足，至少需要32字符")
        
        logger.info("加密管理器初始化完成")
    
    def encrypt_private_key(self, private_key: str, additional_context: str = "") -> str:
        """
        加密私钥
        
        Args:
            private_key: 原始私钥
            additional_context: 附加上下文信息 (用于增强安全性)
            
        Returns:
            str: 加密后的私钥 (Base64编码)
            
        Raises:
            EncryptionError: 加密失败
        """
        try:
            # 生成随机盐值
            salt = secrets.token_bytes(self.PBKDF2_SALT_SIZE)
            
            # 派生加密密钥
            encryption_key = self._derive_key(self.master_key, salt, additional_context)
            
            # 生成随机nonce
            nonce = secrets.token_bytes(self.GCM_NONCE_SIZE)
            
            # 创建AESGCM对象
            aesgcm = AESGCM(encryption_key)
            
            # 加密私钥
            private_key_bytes = private_key.encode('utf-8')
            encrypted_data = aesgcm.encrypt(nonce, private_key_bytes, associated_data=None)
            
            # 组合：盐值(32) + nonce(12) + 加密数据
            combined_data = salt + nonce + encrypted_data
            
            # Base64编码
            encoded_data = base64.b64encode(combined_data).decode('utf-8')
            
            logger.debug(f"私钥加密成功，数据长度: {len(encoded_data)}")
            return encoded_data
            
        except Exception as e:
            logger.error(f"私钥加密失败: {e}")
            raise EncryptionError(f"私钥加密失败: {str(e)}")
    
    def decrypt_private_key(self, encrypted_private_key: str, additional_context: str = "") -> str:
        """
        解密私钥
        
        Args:
            encrypted_private_key: 加密的私钥 (Base64编码)
            additional_context: 附加上下文信息
            
        Returns:
            str: 解密后的私钥
            
        Raises:
            DecryptionError: 解密失败
        """
        try:
            # Base64解码
            combined_data = base64.b64decode(encrypted_private_key.encode('utf-8'))
            
            # 检查数据长度
            min_length = self.PBKDF2_SALT_SIZE + self.GCM_NONCE_SIZE + 16  # 至少包含盐值+nonce+最小加密数据
            if len(combined_data) < min_length:
                raise DecryptionError(f"加密数据长度不足: {len(combined_data)} < {min_length}")
            
            # 分离组件
            salt = combined_data[:self.PBKDF2_SALT_SIZE]
            nonce = combined_data[self.PBKDF2_SALT_SIZE:self.PBKDF2_SALT_SIZE + self.GCM_NONCE_SIZE]
            encrypted_data = combined_data[self.PBKDF2_SALT_SIZE + self.GCM_NONCE_SIZE:]
            
            # 派生解密密钥
            decryption_key = self._derive_key(self.master_key, salt, additional_context)
            
            # 创建AESGCM对象
            aesgcm = AESGCM(decryption_key)
            
            # 解密数据
            decrypted_data = aesgcm.decrypt(nonce, encrypted_data, associated_data=None)
            
            # 转换为字符串
            private_key = decrypted_data.decode('utf-8')
            
            logger.debug("私钥解密成功")
            return private_key
            
        except Exception as e:
            logger.error(f"私钥解密失败: {e}")
            raise DecryptionError(f"私钥解密失败: {str(e)}")
    
    def _derive_key(self, master_key: str, salt: bytes, context: str = "") -> bytes:
        """
        使用PBKDF2派生加密密钥
        
        Args:
            master_key: 主密钥
            salt: 盐值
            context: 上下文信息
            
        Returns:
            bytes: 派生的加密密钥
        """
        try:
            # 将主密钥和上下文合并
            key_material = (master_key + context).encode('utf-8')
            
            # 创建PBKDF2对象
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.AES_KEY_SIZE,
                salt=salt,
                iterations=self.PBKDF2_ITERATIONS,
                backend=default_backend()
            )
            
            # 派生密钥
            derived_key = kdf.derive(key_material)
            return derived_key
            
        except Exception as e:
            logger.error(f"密钥派生失败: {e}")
            raise KeyDerivationError(f"密钥派生失败: {str(e)}")
    
    def generate_master_key(self) -> str:
        """
        生成主密钥
        
        Returns:
            str: 生成的主密钥 (Base64编码)
        """
        try:
            # 生成256位随机密钥
            random_key = secrets.token_bytes(32)
            
            # Base64编码
            master_key = base64.b64encode(random_key).decode('utf-8')
            
            logger.info("新主密钥生成完成")
            return master_key
            
        except Exception as e:
            logger.error(f"主密钥生成失败: {e}")
            raise KeyDerivationError(f"主密钥生成失败: {str(e)}")
    
    def rotate_master_key(self, new_master_key: str, encrypted_private_keys: Dict[str, str], context: str = "") -> Dict[str, str]:
        """
        轮换主密钥 - 使用新密钥重新加密所有私钥
        
        Args:
            new_master_key: 新主密钥
            encrypted_private_keys: 使用旧密钥加密的私钥字典 {wallet_id: encrypted_key}
            context: 上下文信息
            
        Returns:
            Dict[str, str]: 使用新密钥重新加密的私钥字典
            
        Raises:
            CryptographyError: 密钥轮换失败
        """
        try:
            logger.info(f"开始轮换主密钥，需要重新加密{len(encrypted_private_keys)}个私钥")
            
            # 保存旧密钥
            old_master_key = self.master_key
            
            # 创建新密钥管理器
            new_crypto_manager = CryptoManager(new_master_key)
            
            re_encrypted_keys = {}
            failed_keys = []
            
            for wallet_id, encrypted_key in encrypted_private_keys.items():
                try:
                    # 使用旧密钥解密
                    private_key = self.decrypt_private_key(encrypted_key, context)
                    
                    # 使用新密钥重新加密
                    new_encrypted_key = new_crypto_manager.encrypt_private_key(private_key, context)
                    
                    re_encrypted_keys[wallet_id] = new_encrypted_key
                    
                except Exception as e:
                    logger.error(f"钱包{wallet_id}密钥轮换失败: {e}")
                    failed_keys.append(wallet_id)
                    continue
            
            # 更新主密钥
            self.master_key = new_master_key
            
            success_count = len(re_encrypted_keys)
            failure_count = len(failed_keys)
            
            logger.info(f"密钥轮换完成 - 成功: {success_count}, 失败: {failure_count}")
            
            if failed_keys:
                logger.warning(f"以下钱包密钥轮换失败: {failed_keys}")
            
            return re_encrypted_keys
            
        except Exception as e:
            logger.error(f"密钥轮换失败: {e}")
            raise CryptographyError(f"密钥轮换失败: {str(e)}")
    
    def verify_encryption_integrity(self, private_key: str, encrypted_key: str, context: str = "") -> bool:
        """
        验证加密完整性 - 检查加密/解密是否正确
        
        Args:
            private_key: 原始私钥
            encrypted_key: 加密后的私钥
            context: 上下文信息
            
        Returns:
            bool: 完整性检查结果
        """
        try:
            # 解密
            decrypted_key = self.decrypt_private_key(encrypted_key, context)
            
            # 比较
            return private_key == decrypted_key
            
        except Exception as e:
            logger.error(f"完整性验证失败: {e}")
            return False
    
    def get_encryption_info(self) -> Dict[str, Any]:
        """
        获取加密配置信息
        
        Returns:
            Dict[str, Any]: 加密配置信息
        """
        return {
            "algorithm": "AES-256-GCM",
            "key_derivation": "PBKDF2-SHA256",
            "key_size": self.AES_KEY_SIZE,
            "nonce_size": self.GCM_NONCE_SIZE,
            "salt_size": self.PBKDF2_SALT_SIZE,
            "pbkdf2_iterations": self.PBKDF2_ITERATIONS,
            "master_key_configured": bool(self.master_key)
        }
    
    def generate_secure_random(self, size: int) -> str:
        """
        生成安全随机数
        
        Args:
            size: 字节数
            
        Returns:
            str: 十六进制随机数
        """
        return secrets.token_hex(size)
    
    def hash_data(self, data: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        对数据进行哈希
        
        Args:
            data: 待哈希的数据
            salt: 盐值 (如果不提供将生成随机盐值)
            
        Returns:
            Tuple[str, str]: (哈希值, 盐值)
        """
        try:
            if salt is None:
                salt = secrets.token_hex(16)
            
            # 创建SHA-256哈希
            hash_obj = hashlib.sha256()
            hash_obj.update((data + salt).encode('utf-8'))
            hash_value = hash_obj.hexdigest()
            
            return hash_value, salt
            
        except Exception as e:
            logger.error(f"数据哈希失败: {e}")
            raise CryptographyError(f"数据哈希失败: {str(e)}")


class WalletSecurityManager:
    """
    钱包安全管理器 - 集成私钥加密和安全策略
    """
    
    def __init__(self, crypto_manager: Optional[CryptoManager] = None):
        """
        初始化安全管理器
        
        Args:
            crypto_manager: 加密管理器实例
        """
        self.crypto_manager = crypto_manager or CryptoManager()
        logger.info("钱包安全管理器初始化完成")
    
    def secure_store_private_key(self, wallet_id: str, private_key: str, network: str) -> Dict[str, Any]:
        """
        安全存储私钥
        
        Args:
            wallet_id: 钱包ID
            private_key: 私钥
            network: 网络类型
            
        Returns:
            Dict[str, Any]: 存储结果
        """
        try:
            # 创建上下文 (包含钱包ID和网络信息)
            context = f"wallet_{wallet_id}_{network}"
            
            # 加密私钥
            encrypted_key = self.crypto_manager.encrypt_private_key(private_key, context)
            
            # 生成校验哈希
            check_hash, salt = self.crypto_manager.hash_data(private_key)
            
            # 验证加密完整性
            integrity_ok = self.crypto_manager.verify_encryption_integrity(private_key, encrypted_key, context)
            
            if not integrity_ok:
                raise EncryptionError("加密完整性验证失败")
            
            return {
                "success": True,
                "encrypted_private_key": encrypted_key,
                "check_hash": check_hash,
                "check_salt": salt,
                "context": context,
                "encryption_info": self.crypto_manager.get_encryption_info()
            }
            
        except Exception as e:
            logger.error(f"私钥安全存储失败 - 钱包ID: {wallet_id}, 错误: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def secure_retrieve_private_key(self, wallet_id: str, encrypted_key: str, network: str, check_hash: Optional[str] = None, check_salt: Optional[str] = None) -> Dict[str, Any]:
        """
        安全获取私钥
        
        Args:
            wallet_id: 钱包ID
            encrypted_key: 加密的私钥
            network: 网络类型
            check_hash: 校验哈希 (可选)
            check_salt: 校验盐值 (可选)
            
        Returns:
            Dict[str, Any]: 获取结果
        """
        try:
            # 重构上下文
            context = f"wallet_{wallet_id}_{network}"
            
            # 解密私钥
            private_key = self.crypto_manager.decrypt_private_key(encrypted_key, context)
            
            # 如果提供了校验信息，进行完整性检查
            if check_hash and check_salt:
                verify_hash, _ = self.crypto_manager.hash_data(private_key, check_salt)
                if verify_hash != check_hash:
                    raise DecryptionError("私钥完整性校验失败")
            
            return {
                "success": True,
                "private_key": private_key,
                "wallet_id": wallet_id,
                "network": network
            }
            
        except Exception as e:
            logger.error(f"私钥安全获取失败 - 钱包ID: {wallet_id}, 错误: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# 全局加密管理器实例
crypto_manager = CryptoManager()
security_manager = WalletSecurityManager(crypto_manager)


def get_crypto_manager() -> CryptoManager:
    """获取加密管理器实例"""
    return crypto_manager


def get_security_manager() -> WalletSecurityManager:
    """获取安全管理器实例"""
    return security_manager


if __name__ == "__main__":
    """测试代码"""
    import asyncio
    
    async def test_crypto_manager():
        """测试加密管理器"""
        print("=== 测试加密管理器 ===")
        
        try:
            # 创建测试实例
            cm = CryptoManager()
            sm = WalletSecurityManager(cm)
            
            # 测试私钥
            test_private_key = "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
            
            print(f"\n1. 原始私钥: {test_private_key}")
            
            # 测试加密
            encrypted_result = sm.secure_store_private_key("test_wallet_001", test_private_key, "TRC20")
            print(f"2. 加密结果: {encrypted_result['success']}")
            print(f"   加密长度: {len(encrypted_result.get('encrypted_private_key', ''))}")
            
            if encrypted_result['success']:
                # 测试解密
                decrypted_result = sm.secure_retrieve_private_key(
                    "test_wallet_001", 
                    encrypted_result['encrypted_private_key'], 
                    "TRC20",
                    encrypted_result['check_hash'],
                    encrypted_result['check_salt']
                )
                print(f"3. 解密结果: {decrypted_result['success']}")
                print(f"   解密私钥: {decrypted_result.get('private_key', '')}")
                
                # 验证一致性
                is_same = decrypted_result.get('private_key') == test_private_key
                print(f"4. 一致性检查: {is_same}")
            
            # 测试加密配置
            config = cm.get_encryption_info()
            print(f"\n5. 加密配置: {config}")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    # 运行测试
    asyncio.run(test_crypto_manager())