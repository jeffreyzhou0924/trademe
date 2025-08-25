"""
区块链监控管理API - 管理员区块链监控管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from app.database import get_db
from app.middleware.admin_auth import get_current_admin, AdminUser
from app.services.blockchain_monitor import BlockchainMonitorService, TransactionStatus, NetworkConfig
from app.models.payment import BlockchainTransaction, USDTWallet
from app.models.admin import AdminOperationLog
from app.core.rbac import require_permission
from app.core.exceptions import BlockchainError, NetworkError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/blockchain", tags=["区块链监控管理"])


# Pydantic模型
class TransactionCheckRequest(BaseModel):
    """交易检查请求"""
    tx_hash: str = Field(..., description="交易哈希", min_length=32)
    network: str = Field(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$")
    expected_address: Optional[str] = Field(None, description="期望收款地址")
    expected_amount: Optional[Decimal] = Field(None, description="期望金额", gt=0)


class AddressMonitorRequest(BaseModel):
    """地址监控请求"""
    address: str = Field(..., description="监控地址", min_length=10)
    network: str = Field(..., description="网络类型", regex="^(TRC20|ERC20|BEP20)$")


class TransactionStatusResponse(BaseModel):
    """交易状态响应"""
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


class BlockchainTransactionResponse(BaseModel):
    """区块链交易响应"""
    id: int
    transaction_hash: str
    network: str
    from_address: str
    to_address: str
    amount: Decimal
    block_number: Optional[int]
    confirmations: int
    status: str
    transaction_time: datetime
    created_at: datetime
    updated_at: Optional[datetime]


class TransactionListResponse(BaseModel):
    """交易列表响应"""
    transactions: List[BlockchainTransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class NetworkStatusResponse(BaseModel):
    """网络状态响应"""
    network: str
    name: str
    is_monitoring: bool
    rpc_urls: List[str]
    current_rpc_url: str
    latest_block: Optional[int]
    usdt_contract: str
    required_confirmations: int
    block_time: int
    response_time: Optional[float]
    success_rate: Optional[float]


class BlockchainStatisticsResponse(BaseModel):
    """区块链统计响应"""
    total_transactions: int
    confirmed_transactions: int
    pending_transactions: int
    failed_transactions: int
    total_volume: Decimal
    confirmed_volume: Decimal
    network_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    hourly_activity: Dict[str, int]


@router.post("/check-transaction", response_model=TransactionStatusResponse)
@require_permission("blockchain:monitor")
async def check_transaction(
    request: TransactionCheckRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """检查交易状态"""
    try:
        blockchain_monitor = BlockchainMonitorService(db)
        
        try:
            # 检查交易状态
            tx_status = await blockchain_monitor.check_transaction(
                tx_hash=request.tx_hash,
                network=request.network,
                expected_address=request.expected_address,
                expected_amount=request.expected_amount
            )
            
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="CHECK_TRANSACTION",
                resource_type="blockchain_transaction",
                details=f'{{"tx_hash": "{request.tx_hash}", "network": "{request.network}"}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            return TransactionStatusResponse(
                tx_hash=tx_status.tx_hash,
                is_confirmed=tx_status.is_confirmed,
                is_pending=tx_status.is_pending,
                is_failed=tx_status.is_failed,
                confirmations=tx_status.confirmations,
                block_number=tx_status.block_number,
                amount=tx_status.amount,
                from_address=tx_status.from_address,
                to_address=tx_status.to_address,
                timestamp=tx_status.timestamp
            )
            
        finally:
            await blockchain_monitor.close()
        
    except BlockchainError as e:
        logger.error(f"区块链查询失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"交易查询失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"检查交易失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"系统错误: {str(e)}"
        )


@router.post("/monitor-address")
@require_permission("blockchain:monitor")
async def monitor_address(
    request: AddressMonitorRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """监控指定地址的新交易"""
    try:
        blockchain_monitor = BlockchainMonitorService(db)
        
        try:
            # 监控地址
            new_transactions = await blockchain_monitor.monitor_address(
                address=request.address,
                network=request.network
            )
            
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="MONITOR_ADDRESS",
                resource_type="blockchain_address",
                details=f'{{"address": "{request.address}", "network": "{request.network}"}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            # 转换为响应格式
            transaction_responses = [
                TransactionStatusResponse(
                    tx_hash=tx.tx_hash,
                    is_confirmed=tx.is_confirmed,
                    is_pending=tx.is_pending,
                    is_failed=tx.is_failed,
                    confirmations=tx.confirmations,
                    block_number=tx.block_number,
                    amount=tx.amount,
                    from_address=tx.from_address,
                    to_address=tx.to_address,
                    timestamp=tx.timestamp
                )
                for tx in new_transactions
            ]
            
            return {
                "message": f"地址监控完成，发现 {len(new_transactions)} 笔新交易",
                "address": request.address,
                "network": request.network,
                "new_transactions": transaction_responses
            }
            
        finally:
            await blockchain_monitor.close()
        
    except BlockchainError as e:
        logger.error(f"地址监控失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"地址监控失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"监控地址失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"系统错误: {str(e)}"
        )


@router.get("/balance/{network}/{address}")
@require_permission("blockchain:monitor")
async def get_address_balance(
    network: str,
    address: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取地址USDT余额"""
    try:
        # 验证网络类型
        if network not in ["TRC20", "ERC20", "BEP20"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的网络类型: {network}"
            )
        
        blockchain_monitor = BlockchainMonitorService(db)
        
        try:
            # 获取余额
            balance = await blockchain_monitor.get_balance(address, network)
            
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="GET_BALANCE",
                resource_type="blockchain_address",
                details=f'{{"address": "{address}", "network": "{network}", "balance": {balance}}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            return {
                "address": address,
                "network": network,
                "balance": float(balance),
                "balance_usdt": f"{balance} USDT",
                "query_time": datetime.utcnow().isoformat()
            }
            
        finally:
            await blockchain_monitor.close()
        
    except Exception as e:
        logger.error(f"获取余额失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"余额查询失败: {str(e)}"
        )


@router.get("/networks/status", response_model=List[NetworkStatusResponse])
@require_permission("blockchain:monitor")
async def get_network_status(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取各网络监控状态"""
    try:
        blockchain_monitor = BlockchainMonitorService(db)
        network_statuses = []
        
        try:
            for network_name, config in blockchain_monitor.NETWORK_CONFIGS.items():
                # 检查是否正在监控
                is_monitoring = network_name in blockchain_monitor.monitoring_tasks
                
                # 获取当前使用的RPC URL
                current_rpc_url = await blockchain_monitor._get_rpc_url(network_name)
                
                # 尝试获取最新区块号
                latest_block = None
                response_time = None
                success_rate = None
                
                try:
                    start_time = datetime.utcnow()
                    latest_block = await blockchain_monitor._get_latest_block_number(network_name)
                    end_time = datetime.utcnow()
                    response_time = (end_time - start_time).total_seconds()
                    success_rate = 100.0
                except Exception as e:
                    logger.warning(f"获取 {network_name} 网络状态失败: {e}")
                    success_rate = 0.0
                
                network_statuses.append(NetworkStatusResponse(
                    network=network_name,
                    name=config.name,
                    is_monitoring=is_monitoring,
                    rpc_urls=config.rpc_urls,
                    current_rpc_url=current_rpc_url,
                    latest_block=latest_block,
                    usdt_contract=config.usdt_contract,
                    required_confirmations=config.required_confirmations,
                    block_time=config.block_time,
                    response_time=response_time,
                    success_rate=success_rate
                ))
            
        finally:
            await blockchain_monitor.close()
        
        return network_statuses
        
    except Exception as e:
        logger.error(f"获取网络状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取网络状态失败: {str(e)}"
        )


@router.post("/networks/{network}/start-monitoring")
@require_permission("blockchain:admin")
async def start_network_monitoring(
    network: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """启动网络监控"""
    try:
        if network not in ["TRC20", "ERC20", "BEP20"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的网络类型: {network}"
            )
        
        blockchain_monitor = BlockchainMonitorService(db)
        
        try:
            success = await blockchain_monitor.start_monitoring(network)
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"启动 {network} 监控失败"
                )
            
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="START_MONITORING",
                resource_type="blockchain_network",
                details=f'{{"network": "{network}"}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            return {
                "message": f"{network} 网络监控启动成功",
                "network": network,
                "status": "monitoring"
            }
            
        finally:
            await blockchain_monitor.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动网络监控失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动监控失败: {str(e)}"
        )


@router.post("/networks/{network}/stop-monitoring")
@require_permission("blockchain:admin")
async def stop_network_monitoring(
    network: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """停止网络监控"""
    try:
        if network not in ["TRC20", "ERC20", "BEP20"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的网络类型: {network}"
            )
        
        blockchain_monitor = BlockchainMonitorService(db)
        
        try:
            success = await blockchain_monitor.stop_monitoring(network)
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"停止 {network} 监控失败"
                )
            
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="STOP_MONITORING",
                resource_type="blockchain_network",
                details=f'{{"network": "{network}"}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            return {
                "message": f"{network} 网络监控停止成功",
                "network": network,
                "status": "stopped"
            }
            
        finally:
            await blockchain_monitor.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止网络监控失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止监控失败: {str(e)}"
        )


@router.get("/transactions", response_model=TransactionListResponse)
@require_permission("blockchain:monitor")
async def get_blockchain_transactions(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    network: Optional[str] = Query(None, description="网络类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    address: Optional[str] = Query(None, description="地址筛选"),
    sort_by: str = Query("transaction_time", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序")
):
    """获取区块链交易列表"""
    try:
        # 构建基础查询
        query = select(BlockchainTransaction)
        count_query = select(func.count(BlockchainTransaction.id))
        
        # 添加筛选条件
        filters = []
        
        if network:
            filters.append(BlockchainTransaction.network == network)
        
        if status:
            filters.append(BlockchainTransaction.status == status)
        
        if address:
            address_filter = or_(
                BlockchainTransaction.from_address.like(f"%{address}%"),
                BlockchainTransaction.to_address.like(f"%{address}%")
            )
            filters.append(address_filter)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 添加排序
        if sort_by in ['transaction_time', 'created_at', 'amount', 'confirmations']:
            sort_column = getattr(BlockchainTransaction, sort_by)
            if sort_order.lower() == 'asc':
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(BlockchainTransaction.transaction_time.desc())
        
        # 添加分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # 执行查询
        result = await db.execute(query)
        transactions = result.scalars().all()
        
        # 转换为响应格式
        transaction_responses = [
            BlockchainTransactionResponse(
                id=tx.id,
                transaction_hash=tx.transaction_hash,
                network=tx.network,
                from_address=tx.from_address,
                to_address=tx.to_address,
                amount=tx.amount,
                block_number=tx.block_number,
                confirmations=tx.confirmations,
                status=tx.status,
                transaction_time=tx.transaction_time,
                created_at=tx.created_at,
                updated_at=tx.updated_at
            )
            for tx in transactions
        ]
        
        total_pages = (total + page_size - 1) // page_size
        
        return TransactionListResponse(
            transactions=transaction_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"获取交易列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取交易列表失败: {str(e)}"
        )


@router.get("/statistics/overview", response_model=BlockchainStatisticsResponse)
@require_permission("blockchain:monitor")
async def get_blockchain_statistics(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=90, description="统计天数")
):
    """获取区块链监控统计信息"""
    try:
        # 计算时间范围
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 状态分布统计
        status_query = select(
            BlockchainTransaction.status,
            func.count().label('count')
        ).where(
            BlockchainTransaction.created_at >= start_date
        ).group_by(BlockchainTransaction.status)
        
        status_result = await db.execute(status_query)
        status_stats = {row.status: row.count for row in status_result}
        
        # 网络分布统计
        network_query = select(
            BlockchainTransaction.network,
            func.count().label('count')
        ).where(
            BlockchainTransaction.created_at >= start_date
        ).group_by(BlockchainTransaction.network)
        
        network_result = await db.execute(network_query)
        network_stats = {row.network: row.count for row in network_result}
        
        # 金额和数量统计
        volume_query = select(
            func.count().label('total_transactions'),
            func.sum(BlockchainTransaction.amount).label('total_volume'),
            func.sum(
                func.case(
                    (BlockchainTransaction.status == 'confirmed', BlockchainTransaction.amount),
                    else_=0
                )
            ).label('confirmed_volume')
        ).where(BlockchainTransaction.created_at >= start_date)
        
        volume_result = await db.execute(volume_query)
        volume_row = volume_result.first()
        
        # 按小时活动统计
        hourly_query = select(
            func.date_part('hour', BlockchainTransaction.transaction_time).label('hour'),
            func.count().label('count')
        ).where(
            BlockchainTransaction.created_at >= start_date
        ).group_by(func.date_part('hour', BlockchainTransaction.transaction_time))
        
        hourly_result = await db.execute(hourly_query)
        hourly_stats = {f"{int(row.hour)}:00": row.count for row in hourly_result}
        
        return BlockchainStatisticsResponse(
            total_transactions=volume_row.total_transactions or 0,
            confirmed_transactions=status_stats.get('confirmed', 0),
            pending_transactions=status_stats.get('pending', 0),
            failed_transactions=status_stats.get('failed', 0),
            total_volume=Decimal(str(volume_row.total_volume or 0)),
            confirmed_volume=Decimal(str(volume_row.confirmed_volume or 0)),
            network_distribution=network_stats,
            status_distribution=status_stats,
            hourly_activity=hourly_stats
        )
        
    except Exception as e:
        logger.error(f"获取区块链统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )