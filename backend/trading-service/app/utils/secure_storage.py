"""
安全存储工具类 - API密钥和敏感信息的加密存储解决方案
提供对称加密算法保护API密钥、私钥、token等敏感信息
"""

import os
import base64
import hashlib
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecureStorage:
    """安全存储工具类 - 提供敏感信息的加密存储功能"""
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化安全存储
        
        Args:
            master_key: 主加密密钥，如果不提供则从环境变量获取
        """
        self._fernet = None
        self._initialize_encryption_key(master_key)
    
    def _initialize_encryption_key(self, master_key: Optional[str] = None):
        """初始化加密密钥"""
        try:
            # 获取主密钥
            if master_key:
                key_string = master_key
            else:
                key_string = os.getenv('SECURE_STORAGE_KEY')
                
                if not key_string:
                    # 如果没有提供密钥，生成一个默认密钥（仅开发环境使用）
                    logger.warning("未找到SECURE_STORAGE_KEY环境变量，使用默认加密密钥")
                    key_string = "trademe_default_encryption_key_for_development_only"
            
            # 使用PBKDF2从密钥字符串生成Fernet密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'trademe_salt_v1',  # 生产环境应该使用随机盐
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(key_string.encode()))
            self._fernet = Fernet(key)
            
        except Exception as e:
            logger.error(f"加密密钥初始化失败: {e}")
            raise ValueError("加密系统初始化失败")
    
    def encrypt_value(self, plaintext: str) -> str:
        """
        加密字符串值
        
        Args:
            plaintext: 要加密的明文字符串
            
        Returns:
            base64编码的加密字符串
        """
        if not plaintext:
            return plaintext
            
        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"值加密失败: {e}")
            raise ValueError("数据加密失败")
    
    def decrypt_value(self, encrypted_text: str) -> str:
        """
        解密字符串值
        
        Args:
            encrypted_text: base64编码的加密字符串
            
        Returns:
            解密后的明文字符串
        """
        if not encrypted_text:
            return encrypted_text
            
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"值解密失败: {e}")
            raise ValueError("数据解密失败")
    
    def encrypt_api_key(self, api_key: str) -> dict:
        """
        加密API密钥并生成元数据
        
        Args:
            api_key: 要加密的API密钥
            
        Returns:
            包含加密数据和元数据的字典
        """
        if not api_key:
            return {"encrypted_value": "", "key_hash": "", "key_prefix": ""}
        
        try:
            encrypted_value = self.encrypt_value(api_key)
            
            # 生成密钥哈希用于验证（不可逆）
            key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]
            
            # 提取前缀用于识别（明文，用于日志和调试）
            key_prefix = api_key[:8] if len(api_key) > 8 else api_key[:4]
            
            return {
                "encrypted_value": encrypted_value,
                "key_hash": key_hash,
                "key_prefix": key_prefix
            }
        except Exception as e:
            logger.error(f"API密钥加密失败: {e}")
            raise ValueError("API密钥加密失败")
    
    def verify_api_key(self, api_key: str, key_hash: str) -> bool:
        """
        验证API密钥是否与存储的哈希匹配
        
        Args:
            api_key: 要验证的API密钥
            key_hash: 存储的密钥哈希
            
        Returns:
            验证结果
        """
        try:
            current_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]
            return current_hash == key_hash
        except Exception as e:
            logger.error(f"API密钥验证失败: {e}")
            return False
    
    def safe_decrypt_for_use(self, encrypted_value: str, context: str = "API调用") -> str:
        """
        安全解密用于实际使用
        
        Args:
            encrypted_value: 加密的值
            context: 使用上下文（用于日志记录）
            
        Returns:
            解密后的值
        """
        try:
            decrypted = self.decrypt_value(encrypted_value)
            logger.info(f"安全解密成功用于: {context}")
            return decrypted
        except Exception as e:
            logger.error(f"安全解密失败 - 上下文: {context}, 错误: {e}")
            raise ValueError(f"解密失败: {context}")
    
    def rotate_encryption(self, old_encrypted_value: str, new_master_key: str) -> str:
        """
        密钥轮换 - 使用新的主密钥重新加密数据
        
        Args:
            old_encrypted_value: 旧的加密值
            new_master_key: 新的主密钥
            
        Returns:
            使用新密钥加密的值
        """
        try:
            # 用当前密钥解密
            plaintext = self.decrypt_value(old_encrypted_value)
            
            # 用新密钥重新加密
            new_storage = SecureStorage(new_master_key)
            new_encrypted = new_storage.encrypt_value(plaintext)
            
            logger.info("密钥轮换完成")
            return new_encrypted
        except Exception as e:
            logger.error(f"密钥轮换失败: {e}")
            raise ValueError("密钥轮换失败")


class APIKeyManager:
    """API密钥管理器 - 提供高级API密钥管理功能"""
    
    def __init__(self, secure_storage: Optional[SecureStorage] = None):
        """
        初始化API密钥管理器
        
        Args:
            secure_storage: 安全存储实例，如果不提供则创建默认实例
        """
        self.storage = secure_storage or SecureStorage()
    
    def store_api_credentials(self, exchange: str, api_key: str, secret_key: str, 
                            passphrase: Optional[str] = None) -> dict:
        """
        存储交易所API凭证
        
        Args:
            exchange: 交易所名称
            api_key: API密钥
            secret_key: 密钥
            passphrase: 通行短语（如OKX需要）
            
        Returns:
            加密后的凭证信息
        """
        try:
            credentials = {
                "api_key": self.storage.encrypt_api_key(api_key),
                "secret_key": {
                    "encrypted_value": self.storage.encrypt_value(secret_key),
                    "key_hash": hashlib.sha256(secret_key.encode('utf-8')).hexdigest()[:16]
                }
            }
            
            if passphrase:
                credentials["passphrase"] = {
                    "encrypted_value": self.storage.encrypt_value(passphrase),
                    "key_hash": hashlib.sha256(passphrase.encode('utf-8')).hexdigest()[:16]
                }
            
            logger.info(f"交易所API凭证加密存储成功: {exchange}")
            return credentials
            
        except Exception as e:
            logger.error(f"API凭证存储失败 - 交易所: {exchange}, 错误: {e}")
            raise ValueError("API凭证加密存储失败")
    
    def retrieve_api_credentials(self, encrypted_credentials: dict) -> dict:
        """
        检索并解密交易所API凭证
        
        Args:
            encrypted_credentials: 加密的凭证信息
            
        Returns:
            解密后的凭证
        """
        try:
            credentials = {}
            
            # 解密API密钥
            if "api_key" in encrypted_credentials:
                credentials["api_key"] = self.storage.decrypt_value(
                    encrypted_credentials["api_key"]["encrypted_value"]
                )
            
            # 解密密钥
            if "secret_key" in encrypted_credentials:
                credentials["secret_key"] = self.storage.decrypt_value(
                    encrypted_credentials["secret_key"]["encrypted_value"]
                )
            
            # 解密通行短语
            if "passphrase" in encrypted_credentials:
                credentials["passphrase"] = self.storage.decrypt_value(
                    encrypted_credentials["passphrase"]["encrypted_value"]
                )
            
            return credentials
            
        except Exception as e:
            logger.error(f"API凭证检索失败: {e}")
            raise ValueError("API凭证解密失败")
    
    def generate_safe_display_info(self, encrypted_credentials: dict) -> dict:
        """
        生成用于安全显示的API密钥信息
        
        Args:
            encrypted_credentials: 加密的凭证信息
            
        Returns:
            安全显示信息
        """
        try:
            display_info = {}
            
            # API密钥显示信息
            if "api_key" in encrypted_credentials:
                api_data = encrypted_credentials["api_key"]
                key_prefix = api_data.get("key_prefix", "****")
                display_info["api_key_masked"] = f"{key_prefix}****...****{api_data.get('key_hash', '')[:4]}"
            
            # 密钥显示信息
            if "secret_key" in encrypted_credentials:
                display_info["secret_key_set"] = True
                
            # 通行短语显示信息
            if "passphrase" in encrypted_credentials:
                display_info["passphrase_set"] = True
            
            return display_info
            
        except Exception as e:
            logger.error(f"生成安全显示信息失败: {e}")
            return {"error": "无法生成显示信息"}


# 全局安全存储实例
_secure_storage = None
_api_key_manager = None


def get_secure_storage() -> SecureStorage:
    """获取全局安全存储实例"""
    global _secure_storage
    if _secure_storage is None:
        _secure_storage = SecureStorage()
    return _secure_storage


def get_api_key_manager() -> APIKeyManager:
    """获取全局API密钥管理器实例"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager(get_secure_storage())
    return _api_key_manager


# 便捷函数
def encrypt_sensitive_data(data: str) -> str:
    """便捷的敏感数据加密函数"""
    return get_secure_storage().encrypt_value(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """便捷的敏感数据解密函数"""
    return get_secure_storage().decrypt_value(encrypted_data)


def store_exchange_credentials(exchange: str, api_key: str, secret_key: str, 
                             passphrase: Optional[str] = None) -> dict:
    """便捷的交易所凭证存储函数"""
    return get_api_key_manager().store_api_credentials(exchange, api_key, secret_key, passphrase)


def retrieve_exchange_credentials(encrypted_credentials: dict) -> dict:
    """便捷的交易所凭证检索函数"""
    return get_api_key_manager().retrieve_api_credentials(encrypted_credentials)