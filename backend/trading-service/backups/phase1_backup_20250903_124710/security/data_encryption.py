"""
数据加密和脱敏系统 - Data Encryption & Masking System

功能特性:
- AES对称加密
- RSA非对称加密
- 密码哈希验证
- API密钥加密存储
- 敏感数据脱敏
- 密钥管理
- 数据完整性验证
"""

import os
import secrets
import hashlib
import hmac
import base64
import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import bcrypt
import jwt
from loguru import logger


class EncryptionError(Exception):
    """加密相关错误"""
    pass


class DataEncryption:
    """数据加密服务"""
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化数据加密服务
        
        Args:
            master_key: 主密钥，如果为None则从环境变量获取
        """
        self.logger = logger.bind(service="DataEncryption")
        
        # 获取主密钥
        self.master_key = master_key or os.getenv('ENCRYPTION_MASTER_KEY')
        if not self.master_key:
            # 生成临时主密钥（生产环境应该从安全存储获取）
            self.master_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
            self.logger.warning("使用临时生成的主密钥，生产环境请配置ENCRYPTION_MASTER_KEY")
        
        # 初始化Fernet加密器
        self.fernet = Fernet(self.master_key.encode() if len(self.master_key) == 44 else self._derive_key(self.master_key))
        
        # 初始化RSA密钥对
        self.rsa_private_key = None
        self.rsa_public_key = None
        self._generate_rsa_keys()
        
        # 加密配置
        self.config = {
            'password_rounds': 12,  # bcrypt rounds
            'key_derivation_iterations': 100000,  # PBKDF2 iterations
            'token_expiry_hours': 24,  # JWT token expiry
            'salt_length': 32,  # Salt length in bytes
        }
    
    def _derive_key(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """从密码派生密钥"""
        if salt is None:
            salt = b'stable_salt_for_master_key'  # 生产环境应该使用随机salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.config['key_derivation_iterations'],
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _generate_rsa_keys(self):
        """生成RSA密钥对"""
        try:
            self.rsa_private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            self.rsa_public_key = self.rsa_private_key.public_key()
            self.logger.info("RSA密钥对生成成功")
        except Exception as e:
            self.logger.error(f"RSA密钥对生成失败: {str(e)}")
            raise EncryptionError(f"RSA密钥生成失败: {str(e)}")
    
    # 对称加密方法
    def encrypt_data(self, data: Union[str, bytes, Dict[str, Any]]) -> str:
        """
        使用AES对称加密数据
        
        Args:
            data: 要加密的数据
            
        Returns:
            Base64编码的加密数据
        """
        try:
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False)
            elif not isinstance(data, (str, bytes)):
                data = str(data)
            
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted_data = self.fernet.encrypt(data)
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            self.logger.error(f"数据加密失败: {str(e)}")
            raise EncryptionError(f"加密失败: {str(e)}")
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        解密AES加密的数据
        
        Args:
            encrypted_data: Base64编码的加密数据
            
        Returns:
            解密后的原始数据
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"数据解密失败: {str(e)}")
            raise EncryptionError(f"解密失败: {str(e)}")
    
    # 非对称加密方法
    def encrypt_with_public_key(self, data: str) -> str:
        """
        使用RSA公钥加密数据
        
        Args:
            data: 要加密的数据
            
        Returns:
            Base64编码的加密数据
        """
        try:
            if not self.rsa_public_key:
                raise EncryptionError("RSA公钥未初始化")
            
            data_bytes = data.encode('utf-8')
            
            # RSA加密有长度限制，需要分块处理
            max_chunk_size = 190  # 2048位密钥的最大块大小
            encrypted_chunks = []
            
            for i in range(0, len(data_bytes), max_chunk_size):
                chunk = data_bytes[i:i + max_chunk_size]
                encrypted_chunk = self.rsa_public_key.encrypt(
                    chunk,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                encrypted_chunks.append(encrypted_chunk)
            
            # 合并加密块
            combined_encrypted = b''.join(encrypted_chunks)
            return base64.b64encode(combined_encrypted).decode()
            
        except Exception as e:
            self.logger.error(f"RSA加密失败: {str(e)}")
            raise EncryptionError(f"RSA加密失败: {str(e)}")
    
    def decrypt_with_private_key(self, encrypted_data: str) -> str:
        """
        使用RSA私钥解密数据
        
        Args:
            encrypted_data: Base64编码的加密数据
            
        Returns:
            解密后的原始数据
        """
        try:
            if not self.rsa_private_key:
                raise EncryptionError("RSA私钥未初始化")
            
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            
            # 分块解密
            chunk_size = 256  # 2048位密钥的加密块大小
            decrypted_chunks = []
            
            for i in range(0, len(encrypted_bytes), chunk_size):
                chunk = encrypted_bytes[i:i + chunk_size]
                decrypted_chunk = self.rsa_private_key.decrypt(
                    chunk,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                decrypted_chunks.append(decrypted_chunk)
            
            combined_decrypted = b''.join(decrypted_chunks)
            return combined_decrypted.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"RSA解密失败: {str(e)}")
            raise EncryptionError(f"RSA解密失败: {str(e)}")
    
    # 密码哈希方法
    def hash_password(self, password: str) -> str:
        """
        使用bcrypt哈希密码
        
        Args:
            password: 原始密码
            
        Returns:
            哈希后的密码
        """
        try:
            salt = bcrypt.gensalt(rounds=self.config['password_rounds'])
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"密码哈希失败: {str(e)}")
            raise EncryptionError(f"密码哈希失败: {str(e)}")
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        验证密码
        
        Args:
            password: 原始密码
            hashed_password: 哈希后的密码
            
        Returns:
            验证结果
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            self.logger.error(f"密码验证失败: {str(e)}")
            return False
    
    # API密钥管理
    def encrypt_api_key(self, api_key: str, user_salt: str = None) -> Dict[str, str]:
        """
        加密API密钥
        
        Args:
            api_key: 原始API密钥
            user_salt: 用户特定的盐值
            
        Returns:
            包含加密数据和盐值的字典
        """
        try:
            if user_salt is None:
                user_salt = base64.urlsafe_b64encode(os.urandom(self.config['salt_length'])).decode()
            
            # 使用用户特定的盐值派生密钥
            derived_key = self._derive_key(self.master_key + user_salt)
            fernet = Fernet(derived_key)
            
            encrypted_key = fernet.encrypt(api_key.encode('utf-8'))
            encrypted_b64 = base64.urlsafe_b64encode(encrypted_key).decode()
            
            return {
                'encrypted_key': encrypted_b64,
                'salt': user_salt,
                'created_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"API密钥加密失败: {str(e)}")
            raise EncryptionError(f"API密钥加密失败: {str(e)}")
    
    def decrypt_api_key(self, encrypted_data: Dict[str, str]) -> str:
        """
        解密API密钥
        
        Args:
            encrypted_data: 包含加密数据和盐值的字典
            
        Returns:
            解密后的API密钥
        """
        try:
            encrypted_key = encrypted_data['encrypted_key']
            user_salt = encrypted_data['salt']
            
            # 使用相同的盐值派生密钥
            derived_key = self._derive_key(self.master_key + user_salt)
            fernet = Fernet(derived_key)
            
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted_key = fernet.decrypt(encrypted_bytes)
            
            return decrypted_key.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"API密钥解密失败: {str(e)}")
            raise EncryptionError(f"API密钥解密失败: {str(e)}")
    
    # JWT令牌管理
    def create_jwt_token(
        self,
        payload: Dict[str, Any],
        expiry_hours: Optional[int] = None,
        secret_key: Optional[str] = None
    ) -> str:
        """
        创建JWT令牌
        
        Args:
            payload: 令牌载荷
            expiry_hours: 过期时间（小时）
            secret_key: 签名密钥
            
        Returns:
            JWT令牌
        """
        try:
            if expiry_hours is None:
                expiry_hours = self.config['token_expiry_hours']
            
            if secret_key is None:
                secret_key = self.master_key
            
            # 添加标准字段
            now = datetime.utcnow()
            payload.update({
                'iat': now,
                'exp': now + timedelta(hours=expiry_hours),
                'jti': secrets.token_urlsafe(16)  # JWT ID
            })
            
            token = jwt.encode(payload, secret_key, algorithm='HS256')
            return token
            
        except Exception as e:
            self.logger.error(f"JWT令牌创建失败: {str(e)}")
            raise EncryptionError(f"JWT令牌创建失败: {str(e)}")
    
    def verify_jwt_token(
        self,
        token: str,
        secret_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        验证JWT令牌
        
        Args:
            token: JWT令牌
            secret_key: 签名密钥
            
        Returns:
            解码后的载荷
        """
        try:
            if secret_key is None:
                secret_key = self.master_key
            
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload
            
        except jwt.ExpiredSignatureError:
            raise EncryptionError("令牌已过期")
        except jwt.InvalidTokenError as e:
            raise EncryptionError(f"无效的令牌: {str(e)}")
        except Exception as e:
            self.logger.error(f"JWT令牌验证失败: {str(e)}")
            raise EncryptionError(f"令牌验证失败: {str(e)}")
    
    # 数据完整性验证
    def create_hmac_signature(self, data: str, secret_key: Optional[str] = None) -> str:
        """
        创建HMAC签名
        
        Args:
            data: 要签名的数据
            secret_key: 签名密钥
            
        Returns:
            Base64编码的HMAC签名
        """
        try:
            if secret_key is None:
                secret_key = self.master_key
            
            signature = hmac.new(
                secret_key.encode('utf-8'),
                data.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            self.logger.error(f"HMAC签名创建失败: {str(e)}")
            raise EncryptionError(f"签名创建失败: {str(e)}")
    
    def verify_hmac_signature(
        self,
        data: str,
        signature: str,
        secret_key: Optional[str] = None
    ) -> bool:
        """
        验证HMAC签名
        
        Args:
            data: 原始数据
            signature: Base64编码的签名
            secret_key: 签名密钥
            
        Returns:
            验证结果
        """
        try:
            expected_signature = self.create_hmac_signature(data, secret_key)
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            self.logger.error(f"HMAC签名验证失败: {str(e)}")
            return False
    
    # 随机数据生成
    def generate_secure_random(self, length: int = 32) -> str:
        """
        生成安全的随机字符串
        
        Args:
            length: 字符串长度
            
        Returns:
            随机字符串
        """
        return secrets.token_urlsafe(length)
    
    def generate_api_key(self) -> str:
        """生成API密钥"""
        return f"tk_{secrets.token_urlsafe(32)}"
    
    def generate_secret_key(self) -> str:
        """生成密钥"""
        return f"sk_{secrets.token_urlsafe(48)}"
    
    # RSA密钥导出
    def export_public_key_pem(self) -> str:
        """导出RSA公钥（PEM格式）"""
        if not self.rsa_public_key:
            raise EncryptionError("RSA公钥未初始化")
        
        pem = self.rsa_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')
    
    def export_private_key_pem(self, password: Optional[str] = None) -> str:
        """导出RSA私钥（PEM格式）"""
        if not self.rsa_private_key:
            raise EncryptionError("RSA私钥未初始化")
        
        encryption_algorithm = serialization.NoEncryption()
        if password:
            encryption_algorithm = serialization.BestAvailableEncryption(password.encode('utf-8'))
        
        pem = self.rsa_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption_algorithm
        )
        return pem.decode('utf-8')


class DataMasking:
    """数据脱敏服务"""
    
    def __init__(self):
        self.logger = logger.bind(service="DataMasking")
    
    def mask_email(self, email: str) -> str:
        """脱敏邮箱地址"""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            masked_domain = domain_parts[0][0] + '*' * (len(domain_parts[0]) - 1)
            for part in domain_parts[1:]:
                masked_domain += '.' + part
        else:
            masked_domain = domain
        
        return f"{masked_local}@{masked_domain}"
    
    def mask_phone(self, phone: str) -> str:
        """脱敏电话号码"""
        if not phone:
            return phone
        
        # 移除非数字字符
        digits = ''.join(filter(str.isdigit, phone))
        
        if len(digits) < 7:
            return phone
        
        # 保留前3位和后4位
        if len(digits) <= 7:
            return digits[:3] + '*' * (len(digits) - 6) + digits[-3:]
        else:
            return digits[:3] + '*' * (len(digits) - 7) + digits[-4:]
    
    def mask_credit_card(self, card_number: str) -> str:
        """脱敏信用卡号"""
        if not card_number:
            return card_number
        
        # 移除非数字字符
        digits = ''.join(filter(str.isdigit, card_number))
        
        if len(digits) < 8:
            return card_number
        
        # 只显示后4位
        return '*' * (len(digits) - 4) + digits[-4:]
    
    def mask_id_number(self, id_number: str) -> str:
        """脱敏身份证号"""
        if not id_number or len(id_number) < 8:
            return id_number
        
        # 保留前4位和后4位
        return id_number[:4] + '*' * (len(id_number) - 8) + id_number[-4:]
    
    def mask_api_key(self, api_key: str) -> str:
        """脱敏API密钥"""
        if not api_key or len(api_key) < 8:
            return api_key
        
        # 只显示前4位和后4位
        return api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]
    
    def mask_ip_address(self, ip: str) -> str:
        """脱敏IP地址"""
        if not ip or '.' not in ip:
            return ip
        
        parts = ip.split('.')
        if len(parts) != 4:
            return ip
        
        # 只显示第一段
        return f"{parts[0]}.***.***.***"
    
    def mask_bank_account(self, account: str) -> str:
        """脱敏银行账户"""
        if not account or len(account) < 8:
            return account
        
        # 保留后4位
        return '*' * (len(account) - 4) + account[-4:]
    
    def mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        自动脱敏字典中的敏感数据
        
        Args:
            data: 包含敏感数据的字典
            
        Returns:
            脱敏后的数据字典
        """
        if not isinstance(data, dict):
            return data
        
        masked_data = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            if isinstance(value, dict):
                # 递归处理嵌套字典
                masked_data[key] = self.mask_sensitive_data(value)
            elif isinstance(value, list):
                # 处理列表
                masked_data[key] = [
                    self.mask_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, str) and value:
                # 根据字段名进行脱敏
                if any(word in key_lower for word in ['email', 'mail']):
                    masked_data[key] = self.mask_email(value)
                elif any(word in key_lower for word in ['phone', 'mobile', 'tel']):
                    masked_data[key] = self.mask_phone(value)
                elif any(word in key_lower for word in ['card', 'credit']):
                    masked_data[key] = self.mask_credit_card(value)
                elif any(word in key_lower for word in ['id_number', 'identity', 'ssn']):
                    masked_data[key] = self.mask_id_number(value)
                elif any(word in key_lower for word in ['api_key', 'secret', 'token']):
                    masked_data[key] = self.mask_api_key(value)
                elif key_lower in ['ip', 'ip_address', 'client_ip']:
                    masked_data[key] = self.mask_ip_address(value)
                elif any(word in key_lower for word in ['account', 'bank']):
                    masked_data[key] = self.mask_bank_account(value)
                elif key_lower in ['password', 'pwd']:
                    masked_data[key] = '***HIDDEN***'
                else:
                    masked_data[key] = value
            else:
                masked_data[key] = value
        
        return masked_data


# 全局实例
data_encryption = DataEncryption()
data_masking = DataMasking()