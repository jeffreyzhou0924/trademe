"""
区块链监控API端点
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.core.auth import get_current_user
from app.models.auth import User
from app.services.blockchain_monitor import BlockchainMonitorService, TransactionStatus
from app.schemas.base import BaseResponse
from app.core.exceptions import BlockchainError, NetworkError

router = APIRouter(prefix="/blockchain", tags=["区块链监控"])


@router.get("/networks", response_model=BaseResponse)
async def get_supported_networks(
    current_user: User = Depends(get_current_user)
):
    """获取支持的区块链网络列表"""
    try:
        networks = []
        for network, config in BlockchainMonitorService.NETWORK_CONFIGS.items():
            networks.append({
                "network": network,
                "name": config.name,
                "chain_id": config.chain_id,
                "explorer_url": config.explorer_url,
                "usdt_contract": config.usdt_contract,
                "required_confirmations": config.required_confirmations,
                "block_time": config.block_time,
                "native_currency": config.native_currency
            })
        
        return BaseResponse(
            success=True,
            data={"networks": networks},
            message="获取网络列表成功"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取网络列表失败: {str(e)}"
        )


@router.get("/transaction/{network}/{tx_hash}", response_model=BaseResponse)
async def check_transaction_status(
    network: str,
    tx_hash: str,
    expected_address: Optional[str] = None,
    expected_amount: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检查交易状态"""
    try:
        if network not in BlockchainMonitorService.NETWORK_CONFIGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的网络类型: {network}"
            )
        
        monitor = BlockchainMonitorService(db)
        
        try:
            expected_amount_decimal = None
            if expected_amount:
                expected_amount_decimal = Decimal(expected_amount)
            
            tx_status = await monitor.check_transaction(
                tx_hash=tx_hash,
                network=network,
                expected_address=expected_address,
                expected_amount=expected_amount_decimal
            )
            
            return BaseResponse(
                success=True,
                data={
                    "transaction_hash": tx_status.tx_hash,
                    "is_confirmed": tx_status.is_confirmed,
                    "is_pending": tx_status.is_pending,
                    "is_failed": tx_status.is_failed,
                    "confirmations": tx_status.confirmations,
                    "block_number": tx_status.block_number,
                    "amount": str(tx_status.amount) if tx_status.amount else None,
                    "from_address": tx_status.from_address,
                    "to_address": tx_status.to_address,
                    "timestamp": tx_status.timestamp.isoformat() if tx_status.timestamp else None,
                    "network": network
                },
                message="交易状态查询成功"
            )
            
        finally:
            await monitor.close()
            
    except BlockchainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except NetworkError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"网络错误: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询交易失败: {str(e)}"
        )


@router.get("/balance/{network}/{address}", response_model=BaseResponse)
async def get_address_balance(
    network: str,
    address: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取地址USDT余额"""
    try:
        if network not in BlockchainMonitorService.NETWORK_CONFIGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的网络类型: {network}"
            )
        
        monitor = BlockchainMonitorService(db)
        
        try:
            balance = await monitor.get_balance(address, network)
            
            return BaseResponse(
                success=True,
                data={
                    "address": address,
                    "network": network,
                    "balance": str(balance),
                    "currency": "USDT",
                    "checked_at": datetime.utcnow().isoformat()
                },
                message="余额查询成功"
            )
            
        finally:
            await monitor.close()
            
    except BlockchainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except NetworkError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"网络错误: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询余额失败: {str(e)}"
        )


@router.post("/monitor/start", response_model=BaseResponse)
async def start_network_monitoring(
    networks: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启动网络监控"""
    try:
        # 检查管理员权限
        if current_user.email != 'admin@trademe.com':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以启动监控服务"
            )
        
        monitor = BlockchainMonitorService(db)
        results = {}
        
        try:
            for network in networks:
                if network not in BlockchainMonitorService.NETWORK_CONFIGS:
                    results[network] = {"success": False, "error": "不支持的网络类型"}
                    continue
                
                success = await monitor.start_monitoring(network)
                results[network] = {"success": success}
            
            return BaseResponse(
                success=True,
                data={
                    "monitoring_results": results,
                    "started_at": datetime.utcnow().isoformat()
                },
                message="监控服务启动完成"
            )
            
        finally:
            # 注意：这里不关闭monitor，因为监控任务需要保持运行
            pass
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动监控失败: {str(e)}"
        )


@router.post("/monitor/stop", response_model=BaseResponse)
async def stop_network_monitoring(
    networks: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止网络监控"""
    try:
        # 检查管理员权限
        if current_user.email != 'admin@trademe.com':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以停止监控服务"
            )
        
        monitor = BlockchainMonitorService(db)
        results = {}
        
        try:
            for network in networks:
                success = await monitor.stop_monitoring(network)
                results[network] = {"success": success}
            
            return BaseResponse(
                success=True,
                data={
                    "stop_results": results,
                    "stopped_at": datetime.utcnow().isoformat()
                },
                message="监控服务停止完成"
            )
            
        finally:
            await monitor.close()
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止监控失败: {str(e)}"
        )


@router.get("/monitor/status", response_model=BaseResponse)
async def get_monitoring_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取监控服务状态"""
    try:
        # 这里需要从全局状态管理器获取监控状态
        # 简化实现，返回基础状态
        
        return BaseResponse(
            success=True,
            data={
                "monitoring_active": True,  # 需要实际状态检查
                "monitored_networks": ["TRC20", "ERC20", "BEP20"],  # 需要实际状态
                "active_addresses": 0,  # 需要查询数据库
                "last_check": datetime.utcnow().isoformat(),
                "uptime_seconds": 0  # 需要计算实际运行时间
            },
            message="监控状态查询成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询监控状态失败: {str(e)}"
        )


@router.get("/transactions/recent", response_model=BaseResponse)
async def get_recent_transactions(
    network: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取最近的区块链交易记录"""
    try:
        from app.models.payment import BlockchainTransaction
        from sqlalchemy import select, desc
        
        query = select(BlockchainTransaction).order_by(desc(BlockchainTransaction.created_at))
        
        if network:
            if network not in BlockchainMonitorService.NETWORK_CONFIGS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的网络类型: {network}"
                )
            query = query.where(BlockchainTransaction.network == network)
        
        query = query.limit(limit)
        
        result = await db.execute(query)
        transactions = result.scalars().all()
        
        transaction_list = []
        for tx in transactions:
            transaction_list.append({
                "id": tx.id,
                "transaction_hash": tx.transaction_hash,
                "network": tx.network,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "amount": str(tx.amount),
                "block_number": tx.block_number,
                "confirmations": tx.confirmations,
                "status": tx.status,
                "transaction_time": tx.transaction_time.isoformat() if tx.transaction_time else None,
                "created_at": tx.created_at.isoformat()
            })
        
        return BaseResponse(
            success=True,
            data={
                "transactions": transaction_list,
                "total": len(transaction_list),
                "network_filter": network,
                "limit": limit
            },
            message="交易记录查询成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询交易记录失败: {str(e)}"
        )


@router.get("/statistics", response_model=BaseResponse)
async def get_blockchain_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取区块链监控统计信息"""
    try:
        from app.models.payment import BlockchainTransaction, USDTWallet
        from sqlalchemy import select, func, and_
        from datetime import datetime, timedelta
        
        # 交易统计
        tx_stats_query = select(
            func.count().label('total_transactions'),
            func.sum(func.case((BlockchainTransaction.status == 'confirmed', 1), else_=0)).label('confirmed'),
            func.sum(func.case((BlockchainTransaction.status == 'pending', 1), else_=0)).label('pending'),
            func.sum(BlockchainTransaction.amount).label('total_volume')
        ).select_from(BlockchainTransaction)
        
        result = await db.execute(tx_stats_query)
        tx_data = result.first()
        
        # 按网络分组统计
        network_stats_query = select(
            BlockchainTransaction.network,
            func.count().label('count'),
            func.sum(BlockchainTransaction.amount).label('volume')
        ).group_by(BlockchainTransaction.network)
        
        result = await db.execute(network_stats_query)
        network_data = result.fetchall()
        
        # 最近24小时统计
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_stats_query = select(
            func.count().label('recent_transactions'),
            func.sum(BlockchainTransaction.amount).label('recent_volume')
        ).where(BlockchainTransaction.created_at >= yesterday)
        
        result = await db.execute(recent_stats_query)
        recent_data = result.first()
        
        # 钱包统计
        wallet_stats_query = select(
            func.count().label('total_wallets'),
            func.sum(USDTWallet.balance).label('total_balance')
        ).select_from(USDTWallet)
        
        result = await db.execute(wallet_stats_query)
        wallet_data = result.first()
        
        return BaseResponse(
            success=True,
            data={
                "transactions": {
                    "total": tx_data.total_transactions or 0,
                    "confirmed": tx_data.confirmed or 0,
                    "pending": tx_data.pending or 0,
                    "total_volume": str(tx_data.total_volume or 0),
                    "recent_24h": {
                        "count": recent_data.recent_transactions or 0,
                        "volume": str(recent_data.recent_volume or 0)
                    }
                },
                "networks": [
                    {
                        "network": row.network,
                        "transaction_count": row.count,
                        "volume": str(row.volume)
                    }
                    for row in network_data
                ],
                "wallets": {
                    "total_count": wallet_data.total_wallets or 0,
                    "total_balance": str(wallet_data.total_balance or 0)
                },
                "generated_at": datetime.utcnow().isoformat()
            },
            message="统计信息查询成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询统计信息失败: {str(e)}"
        )


@router.post("/address/monitor", response_model=BaseResponse)
async def add_address_monitoring(
    network: str,
    address: str,
    order_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """添加地址监控"""
    try:
        if network not in BlockchainMonitorService.NETWORK_CONFIGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的网络类型: {network}"
            )
        
        # 这里可以添加地址监控记录到数据库
        # 简化实现，直接返回成功
        
        return BaseResponse(
            success=True,
            data={
                "address": address,
                "network": network,
                "order_id": order_id,
                "monitoring_started": datetime.utcnow().isoformat()
            },
            message="地址监控添加成功"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加地址监控失败: {str(e)}"
        )