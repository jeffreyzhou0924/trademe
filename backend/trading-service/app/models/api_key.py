"""
API密钥模型 - 支持加密存储的安全API密钥管理
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.database import Base
from app.utils.secure_storage import get_api_key_manager
from app.utils.sensitive_info_masker import masker
import json
import logging

logger = logging.getLogger(__name__)


class ApiKey(Base):
    """API密钥模型 - 支持加密存储"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    exchange = Column(String(50), nullable=False)
    
    # 传统字段保留兼容性（逐步弃用）
    api_key = Column(String(255), nullable=True)  # 可为空，逐步迁移到加密存储
    secret_key = Column(String(255), nullable=True)  # 可为空，逐步迁移到加密存储  
    passphrase = Column(String(255), nullable=True)  # 可为空，逐步迁移到加密存储
    
    # 新增加密存储字段
    encrypted_credentials = Column(Text, nullable=True)  # JSON格式存储加密凭证
    credential_version = Column(String(20), default="v1")  # 加密版本标识
    key_prefix = Column(String(20), nullable=True)  # API密钥前缀（用于识别）
    credential_hash = Column(String(64), nullable=True)  # 凭证哈希（用于验证）
    
    # 状态和元数据
    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime, nullable=True)  # 最后验证时间
    verification_status = Column(String(20), default="pending")  # pending, valid, invalid, expired
    error_message = Column(Text, nullable=True)  # 验证错误信息
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    @hybrid_property
    def is_encrypted(self) -> bool:
        """检查是否使用加密存储"""
        return self.encrypted_credentials is not None
    
    def set_credentials(self, api_key: str, secret_key: str, passphrase: str = None):
        """
        设置并加密存储API凭证
        
        Args:
            api_key: API密钥
            secret_key: 密钥
            passphrase: 通行短语（可选）
        """
        try:
            # 使用API密钥管理器加密存储凭证
            manager = get_api_key_manager()
            encrypted_creds = manager.store_api_credentials(
                self.exchange, api_key, secret_key, passphrase
            )
            
            # 存储加密数据
            self.encrypted_credentials = json.dumps(encrypted_creds)
            self.credential_version = "v1"
            self.key_prefix = encrypted_creds["api_key"]["key_prefix"]
            self.credential_hash = encrypted_creds["api_key"]["key_hash"]
            
            # 清空传统字段（保证安全）
            self.api_key = None
            self.secret_key = None
            self.passphrase = None
            
            # 更新状态
            self.verification_status = "pending"
            self.error_message = None
            
            logger.info(f"API凭证加密存储成功: 交易所 {self.exchange}, 用户 {self.user_id}")
            
        except Exception as e:
            logger.error(f"API凭证加密存储失败: {e}")
            self.verification_status = "invalid"
            self.error_message = f"加密存储失败: {str(e)}"
            raise
    
    def get_credentials(self) -> dict:
        """
        获取解密后的API凭证
        
        Returns:
            解密后的凭证字典
        """
        try:
            if not self.is_encrypted:
                # 兼容传统明文存储
                logger.warning(f"使用传统明文API凭证: ID {self.id}")
                return {
                    "api_key": self.api_key,
                    "secret_key": self.secret_key,
                    "passphrase": self.passphrase
                }
            
            # 解密加密存储的凭证
            encrypted_creds = json.loads(self.encrypted_credentials)
            manager = get_api_key_manager()
            credentials = manager.retrieve_api_credentials(encrypted_creds)
            
            logger.info(f"API凭证解密成功: 交易所 {self.exchange}, 用户 {self.user_id}")
            return credentials
            
        except Exception as e:
            logger.error(f"API凭证解密失败: ID {self.id}, 错误: {e}")
            raise ValueError("API凭证解密失败")
    
    def get_display_info(self) -> dict:
        """
        获取用于安全显示的API密钥信息
        
        Returns:
            安全显示信息
        """
        try:
            if not self.is_encrypted:
                # 传统方式的安全显示
                return {
                    "api_key_masked": masker.mask_string(self.api_key or ""),
                    "secret_key_set": bool(self.secret_key),
                    "passphrase_set": bool(self.passphrase),
                    "encryption_status": "legacy"
                }
            
            # 加密存储的安全显示
            encrypted_creds = json.loads(self.encrypted_credentials)
            manager = get_api_key_manager()
            display_info = manager.generate_safe_display_info(encrypted_creds)
            display_info["encryption_status"] = "encrypted"
            
            return display_info
            
        except Exception as e:
            logger.error(f"生成显示信息失败: ID {self.id}, 错误: {e}")
            return {
                "api_key_masked": "错误",
                "secret_key_set": False,
                "passphrase_set": False,
                "encryption_status": "error"
            }
    
    def verify_credentials(self) -> bool:
        """
        验证API凭证有效性
        
        Returns:
            验证结果
        """
        try:
            # 这里应该调用具体交易所的API验证
            # 目前只是基本的格式验证
            credentials = self.get_credentials()
            
            api_key = credentials.get("api_key", "")
            secret_key = credentials.get("secret_key", "")
            
            if not api_key or not secret_key:
                self.verification_status = "invalid"
                self.error_message = "API密钥或密钥为空"
                return False
            
            # 基本格式验证
            if len(api_key) < 20 or len(secret_key) < 20:
                self.verification_status = "invalid" 
                self.error_message = "API密钥或密钥长度不足"
                return False
            
            self.verification_status = "valid"
            self.error_message = None
            self.last_verified_at = func.now()
            
            return True
            
        except Exception as e:
            logger.error(f"API凭证验证失败: ID {self.id}, 错误: {e}")
            self.verification_status = "invalid"
            self.error_message = str(e)
            return False
    
    def migrate_to_encrypted_storage(self):
        """
        将传统明文存储迁移到加密存储
        """
        try:
            if self.is_encrypted:
                logger.info(f"API凭证已使用加密存储: ID {self.id}")
                return
            
            if not self.api_key or not self.secret_key:
                logger.warning(f"API凭证数据不完整，无法迁移: ID {self.id}")
                return
            
            # 迁移到加密存储
            self.set_credentials(self.api_key, self.secret_key, self.passphrase)
            
            logger.info(f"API凭证迁移完成: ID {self.id}")
            
        except Exception as e:
            logger.error(f"API凭证迁移失败: ID {self.id}, 错误: {e}")
            raise
    
    def to_safe_dict(self) -> dict:
        """
        转换为安全的字典表示（用于API响应）
        """
        display_info = self.get_display_info()
        
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "exchange": self.exchange,
            "api_key_masked": display_info.get("api_key_masked"),
            "secret_key_set": display_info.get("secret_key_set", False),
            "passphrase_set": display_info.get("passphrase_set", False),
            "encryption_status": display_info.get("encryption_status", "unknown"),
            "is_active": self.is_active,
            "verification_status": self.verification_status,
            "last_verified_at": self.last_verified_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }