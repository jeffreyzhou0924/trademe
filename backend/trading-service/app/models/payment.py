"""
支付系统模型 - USDT支付和钱包管理
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class USDTWallet(Base):
    """USDT钱包池模型"""
    __tablename__ = "usdt_wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_name = Column(String(100), nullable=False)
    network = Column(String(20), nullable=False, index=True)  # TRC20, ERC20, BEP20
    address = Column(String(100), nullable=False, unique=True, index=True)
    private_key = Column(String(255), nullable=False)  # 加密存储
    public_key = Column(String(255), nullable=True)
    balance = Column(DECIMAL(18, 8), default=0)
    status = Column(String(20), default="available")  # available, occupied, maintenance, disabled, error
    daily_limit = Column(DECIMAL(18, 8), nullable=True)  # 日收款限额
    monthly_limit = Column(DECIMAL(18, 8), nullable=True)  # 月收款限额
    total_received = Column(DECIMAL(18, 8), default=0)  # 累计收款
    total_sent = Column(DECIMAL(18, 8), default=0)      # 累计发送
    transaction_count = Column(Integer, default=0)       # 交易次数
    current_daily_received = Column(DECIMAL(18, 8), default=0)  # 当前日收款
    current_monthly_received = Column(DECIMAL(18, 8), default=0)  # 当前月收款
    current_order_id = Column(String(50), nullable=True, index=True)  # 当前分配订单ID
    allocated_at = Column(DateTime, nullable=True)       # 分配时间
    risk_level = Column(String(20), default="LOW", index=True)  # LOW, MEDIUM, HIGH
    last_sync_at = Column(DateTime, nullable=True)       # 最后同步时间
    sync_block_height = Column(Integer, nullable=True)   # 同步区块高度
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class USDTPaymentOrder(Base):
    """USDT支付订单模型"""
    __tablename__ = "usdt_payment_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    wallet_id = Column(Integer, ForeignKey("usdt_wallets.id"), nullable=False, index=True)
    membership_plan_id = Column(Integer, ForeignKey("membership_plans.id"), nullable=True)
    
    # 订单金额
    usdt_amount = Column(DECIMAL(18, 8), nullable=False)         # 订单金额
    expected_amount = Column(DECIMAL(18, 8), nullable=False)     # 期望收到金额
    actual_amount = Column(DECIMAL(18, 8), nullable=True)        # 实际收到金额
    fee_amount = Column(DECIMAL(18, 8), default=0)               # 手续费
    
    # 区块链信息
    transaction_hash = Column(String(100), nullable=True, index=True)
    network = Column(String(20), nullable=False)
    from_address = Column(String(100), nullable=True)
    to_address = Column(String(100), nullable=False)
    block_number = Column(Integer, nullable=True)
    
    # 订单状态
    status = Column(String(20), default="pending", index=True)  # pending, confirmed, expired, failed, cancelled
    confirmations = Column(Integer, default=0)
    required_confirmations = Column(Integer, default=1)
    
    # 业务信息
    payment_type = Column(String(20), default="membership", index=True)  # membership, deposit, withdrawal, service
    description = Column(String(200), nullable=True)  # 订单描述
    callback_url = Column(String(500), nullable=True)  # 回调URL
    order_metadata = Column(Text, nullable=True)  # 扩展元数据(JSON)
    
    # 时间信息
    expires_at = Column(DateTime, nullable=False, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关联关系
    wallet = relationship("USDTWallet")


class BlockchainTransaction(Base):
    """区块链交易记录模型"""
    __tablename__ = "blockchain_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_hash = Column(String(100), nullable=False, unique=True, index=True)
    network = Column(String(20), nullable=False, index=True)
    from_address = Column(String(100), nullable=False, index=True)
    to_address = Column(String(100), nullable=False, index=True)
    amount = Column(DECIMAL(18, 8), nullable=False)
    fee = Column(DECIMAL(18, 8), default=0)
    block_number = Column(Integer, nullable=True, index=True)
    block_hash = Column(String(100), nullable=True)
    confirmations = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending, confirmed, failed
    gas_used = Column(Integer, nullable=True)
    gas_price = Column(DECIMAL(18, 8), nullable=True)
    nonce = Column(Integer, nullable=True)
    transaction_time = Column(DateTime, nullable=True, index=True)
    discovered_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaymentWebhook(Base):
    """支付Webhook记录模型"""
    __tablename__ = "payment_webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("usdt_payment_orders.id"), nullable=True, index=True)
    webhook_type = Column(String(50), nullable=False)  # payment_confirmed, payment_failed
    payload = Column(Text, nullable=False)  # JSON payload
    signature = Column(String(255), nullable=True)
    processed = Column(Boolean, default=False)
    processing_result = Column(String(20), nullable=True)  # success, failed, error
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=False, default=func.now())
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WalletBalance(Base):
    """钱包余额快照模型"""
    __tablename__ = "wallet_balances"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("usdt_wallets.id"), nullable=False, index=True)
    balance = Column(DECIMAL(18, 8), nullable=False)
    balance_change = Column(DECIMAL(18, 8), default=0)  # 余额变化
    pending_balance = Column(DECIMAL(18, 8), default=0)  # 待确认余额
    block_height = Column(Integer, nullable=True)
    change_reason = Column(String(200), nullable=True)  # 变更原因
    snapshot_time = Column(DateTime, nullable=False, default=func.now(), index=True)
    sync_source = Column(String(50), nullable=True)  # api, webhook, manual
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PaymentNotification(Base):
    """支付通知模型"""
    __tablename__ = "payment_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("usdt_payment_orders.id"), nullable=True)
    notification_type = Column(String(50), nullable=False)  # payment_success, payment_failed, payment_expired
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    send_email = Column(Boolean, default=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime, nullable=True)


class WebhookLog(Base):
    """Webhook事件日志模型"""
    __tablename__ = "webhook_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), nullable=False, unique=True, index=True)
    webhook_type = Column(String(50), nullable=False, index=True)  # tron_transaction, ethereum_transaction, etc.
    source = Column(String(100), nullable=True)  # 请求来源
    status = Column(String(20), default="received", index=True)  # received, processing, processed, failed, ignored
    message = Column(Text, nullable=True)  # 处理消息
    payload = Column(Text, nullable=False)  # 原始请求数据
    headers = Column(Text, nullable=True)  # 请求头
    signature = Column(String(255), nullable=True)  # 签名
    processing_time = Column(DECIMAL(10, 4), nullable=True)  # 处理时间(秒)
    result_data = Column(Text, nullable=True)  # 处理结果数据
    error = Column(Text, nullable=True)  # 错误信息
    retry_count = Column(Integer, default=0)  # 重试次数
    processed_at = Column(DateTime, nullable=True)  # 处理完成时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())