"""
USDT钱包池管理API - 管理员钱包管理接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.wallet_pool_service import WalletPoolService, WalletInfo
from app.services.blockchain_monitor import BlockchainMonitorService
from app.models.payment import USDTWallet, USDTPaymentOrder, WalletBalance
from app.models.admin import AdminOperationLog
from app.core.exceptions import WalletError, ValidationError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/usdt-wallets", tags=["USDT钱包管理"])


# Pydantic模型
class WalletCreateRequest(BaseModel):
    """创建钱包请求"""
    network: str = Field(..., description="网络类型", pattern="^(TRC20|ERC20|BEP20)$")
    wallet_name: str = Field(..., description="钱包名称", min_length=1, max_length=100)
    private_key: str = Field(..., description="私钥")


class WalletGenerateRequest(BaseModel):
    """批量生成钱包请求"""
    network: str = Field(..., description="网络类型", pattern="^(TRC20|ERC20|BEP20)$")
    count: int = Field(..., description="生成数量", ge=1, le=1000)
    name_prefix: str = Field("wallet", description="钱包名称前缀", max_length=50)


class WalletUpdateRequest(BaseModel):
    """更新钱包请求"""
    wallet_name: Optional[str] = Field(None, description="钱包名称", max_length=100)
    status: Optional[str] = Field(None, description="钱包状态")
    daily_limit: Optional[Decimal] = Field(None, description="日限额", ge=0)


class WalletResponse(BaseModel):
    """钱包响应"""
    id: int
    wallet_name: str
    network: str
    address: str
    balance: Decimal
    status: str
    daily_limit: Optional[Decimal]
    total_received: Optional[Decimal] = Decimal('0.0')  # 允许NULL，默认值0.0
    total_sent: Optional[Decimal] = Decimal('0.0')      # 允许NULL，默认值0.0
    transaction_count: Optional[int] = 0                # 允许NULL，默认值0
    current_order_id: Optional[str]
    allocated_at: Optional[datetime]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]


class WalletListResponse(BaseModel):
    """钱包列表响应"""
    wallets: List[WalletResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WalletStatisticsResponse(BaseModel):
    """钱包统计响应"""
    total_wallets: int
    available_wallets: int
    occupied_wallets: int
    maintenance_wallets: int
    disabled_wallets: int
    total_balance: Decimal
    average_balance: Decimal
    total_received: Decimal
    utilization_rate: float
    network_distribution: Dict[str, int]


class WalletGenerateResponse(BaseModel):
    """批量生成钱包响应"""
    success: bool
    generated_count: int
    failed_count: int
    wallets: List[WalletResponse]


@router.get("/", response_model=WalletListResponse)
async def get_wallets(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    network: Optional[str] = Query(None, description="网络类型筛选"),
    wallet_status: Optional[str] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序")
):
    """获取钱包列表"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        # 构建基础查询
        query = select(USDTWallet)
        count_query = select(func.count(USDTWallet.id))
        
        # 添加筛选条件
        filters = []
        
        if network:
            filters.append(USDTWallet.network == network)
        
        if wallet_status:
            filters.append(USDTWallet.status == wallet_status)
        
        if search:
            search_filter = or_(
                USDTWallet.wallet_name.like(f"%{search}%"),
                USDTWallet.address.like(f"%{search}%")
            )
            filters.append(search_filter)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 添加排序
        if sort_by in ['created_at', 'updated_at', 'balance', 'transaction_count']:
            sort_column = getattr(USDTWallet, sort_by)
            if sort_order.lower() == 'asc':
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(USDTWallet.created_at.desc())
        
        # 添加分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # 执行查询
        result = await db.execute(query)
        wallets = result.scalars().all()
        
        # 转换为响应格式
        wallet_responses = [
            WalletResponse(
                id=wallet.id,
                wallet_name=wallet.wallet_name,
                network=wallet.network,
                address=wallet.address,
                balance=wallet.balance,
                status=wallet.status,
                daily_limit=wallet.daily_limit,
                total_received=wallet.total_received,
                total_sent=wallet.total_sent,
                transaction_count=wallet.transaction_count,
                current_order_id=wallet.current_order_id,
                allocated_at=wallet.allocated_at,
                last_sync_at=wallet.last_sync_at,
                created_at=wallet.created_at,
                updated_at=wallet.updated_at
            )
            for wallet in wallets
        ]
        
        total_pages = (total + page_size - 1) // page_size
        
        return WalletListResponse(
            wallets=wallet_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"获取钱包列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取钱包列表失败: {str(e)}"
        )


@router.post("/generate", response_model=WalletGenerateResponse)
async def generate_wallets(
    request: WalletGenerateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量生成钱包"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        wallet_service = WalletPoolService(db)
        
        # 生成钱包
        generated_wallets = await wallet_service.generate_wallets(
            network=request.network,
            count=request.count,
            name_prefix=request.name_prefix,
            admin_id=1  # 使用固定管理员ID
        )
        
        # 转换为响应格式
        wallet_responses = [
            WalletResponse(
                id=wallet.id,
                wallet_name=wallet.name,
                network=wallet.network,
                address=wallet.address,
                balance=wallet.balance,
                status=wallet.status,
                daily_limit=None,
                total_received=Decimal('0'),
                total_sent=Decimal('0'),
                transaction_count=0,
                current_order_id=None,
                allocated_at=None,
                last_sync_at=None,
                created_at=wallet.created_at,
                updated_at=None
            )
            for wallet in generated_wallets
        ]
        
        failed_count = request.count - len(generated_wallets)
        
        return WalletGenerateResponse(
            success=len(generated_wallets) > 0,
            generated_count=len(generated_wallets),
            failed_count=failed_count,
            wallets=wallet_responses
        )
        
    except Exception as e:
        logger.error(f"批量生成钱包失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"钱包生成失败: {str(e)}"
        )


@router.post("/import", response_model=WalletResponse)
async def import_wallet(
    request: WalletCreateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """导入钱包"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        wallet_service = WalletPoolService(db)
        
        # 导入钱包
        wallet_info = await wallet_service.import_wallet(
            network=request.network,
            private_key=request.private_key,
            wallet_name=request.wallet_name,
            admin_id=1  # 使用固定管理员ID
        )
        
        return WalletResponse(
            id=wallet_info.id,
            wallet_name=wallet_info.name,
            network=wallet_info.network,
            address=wallet_info.address,
            balance=wallet_info.balance,
            status=wallet_info.status,
            daily_limit=None,
            total_received=Decimal('0'),
            total_sent=Decimal('0'),
            transaction_count=0,
            current_order_id=None,
            allocated_at=None,
            last_sync_at=None,
            created_at=wallet_info.created_at,
            updated_at=None
        )
        
    except Exception as e:
        logger.error(f"导入钱包失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"钱包导入失败: {str(e)}"
        )


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取钱包详情"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        # 查询钱包信息
        wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
        result = await db.execute(wallet_query)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="钱包不存在"
            )
        
        return WalletResponse(
            id=wallet.id,
            wallet_name=wallet.wallet_name,
            network=wallet.network,
            address=wallet.address,
            balance=wallet.balance,
            status=wallet.status,
            daily_limit=wallet.daily_limit,
            total_received=wallet.total_received,
            total_sent=wallet.total_sent,
            transaction_count=wallet.transaction_count,
            current_order_id=wallet.current_order_id,
            allocated_at=wallet.allocated_at,
            last_sync_at=wallet.last_sync_at,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取钱包详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取钱包详情失败: {str(e)}"
        )


@router.put("/{wallet_id}", response_model=WalletResponse)
async def update_wallet(
    wallet_id: int,
    request: WalletUpdateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新钱包信息"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        # 检查钱包是否存在
        wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
        result = await db.execute(wallet_query)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="钱包不存在"
            )
        
        # 构建更新数据
        update_data = {}
        
        if request.wallet_name is not None:
            update_data["wallet_name"] = request.wallet_name
        
        if request.daily_limit is not None:
            update_data["daily_limit"] = request.daily_limit
        
        if request.status is not None:
            # 验证状态是否有效
            valid_statuses = ["available", "occupied", "maintenance", "disabled", "error"]
            if request.status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的状态值: {request.status}"
                )
            
            # 如果要更改状态，使用钱包服务的方法
            wallet_service = WalletPoolService(db)
            success = await wallet_service.update_wallet_status(
                wallet_id, request.status, 1  # 使用固定管理员ID
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="更新钱包状态失败"
                )
        
        # 更新其他字段
        if update_data:
            from sqlalchemy import update
            await db.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(**update_data, updated_at=func.now())
            )
            await db.commit()
        
        # 获取更新后的钱包信息
        updated_wallet_result = await db.execute(wallet_query)
        updated_wallet = updated_wallet_result.scalar_one()
        
        return WalletResponse(
            id=updated_wallet.id,
            wallet_name=updated_wallet.wallet_name,
            network=updated_wallet.network,
            address=updated_wallet.address,
            balance=updated_wallet.balance,
            status=updated_wallet.status,
            daily_limit=updated_wallet.daily_limit,
            total_received=updated_wallet.total_received,
            total_sent=updated_wallet.total_sent,
            transaction_count=updated_wallet.transaction_count,
            current_order_id=updated_wallet.current_order_id,
            allocated_at=updated_wallet.allocated_at,
            last_sync_at=updated_wallet.last_sync_at,
            created_at=updated_wallet.created_at,
            updated_at=updated_wallet.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新钱包失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"钱包更新失败: {str(e)}"
        )


@router.delete("/{wallet_id}")
async def delete_wallet(
    wallet_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除钱包"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        # 检查钱包是否存在
        wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
        result = await db.execute(wallet_query)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="钱包不存在"
            )
        
        # 检查钱包是否正在使用中
        if wallet.status == "occupied" and wallet.current_order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="钱包正在使用中，无法删除"
            )
        
        # 检查钱包是否有余额
        if wallet.balance > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="钱包有余额，请先转出后再删除"
            )
        
        # 检查是否有关联的订单
        order_check = await db.execute(
            select(func.count(USDTPaymentOrder.id))
            .where(USDTPaymentOrder.wallet_id == wallet_id)
        )
        order_count = order_check.scalar()
        
        if order_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="钱包有关联的支付订单，无法删除"
            )
        
        # 删除钱包
        await db.delete(wallet)
        await db.commit()
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=1,  # 使用固定管理员ID
            operation="DELETE_WALLET",
            resource_type="wallet",
            resource_id=wallet_id,
            details=f'{{"wallet_name": "{wallet.wallet_name}", "address": "{wallet.address}", "network": "{wallet.network}"}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {"message": "钱包删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除钱包失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"钱包删除失败: {str(e)}"
        )


@router.post("/{wallet_id}/sync-balance")
async def sync_wallet_balance(
    wallet_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """手动同步钱包余额"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        # 检查钱包是否存在
        wallet_query = select(USDTWallet).where(USDTWallet.id == wallet_id)
        result = await db.execute(wallet_query)
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="钱包不存在"
            )
        
        # 使用区块链监控服务获取余额
        blockchain_monitor = BlockchainMonitorService(db)
        try:
            balance = await blockchain_monitor.get_balance(wallet.address, wallet.network)
            
            # 更新钱包余额
            from sqlalchemy import update
            await db.execute(
                update(USDTWallet)
                .where(USDTWallet.id == wallet_id)
                .values(
                    balance=balance,
                    last_sync_at=func.now(),
                    updated_at=func.now()
                )
            )
            
            # 创建余额快照
            balance_snapshot = WalletBalance(
                wallet_id=wallet_id,
                balance=balance,
                sync_source="manual"
            )
            db.add(balance_snapshot)
            
            await db.commit()
            
            return {
                "message": "余额同步成功",
                "wallet_id": wallet_id,
                "old_balance": float(wallet.balance),
                "new_balance": float(balance),
                "sync_time": datetime.utcnow().isoformat()
            }
            
        finally:
            await blockchain_monitor.close()
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"同步钱包余额失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"余额同步失败: {str(e)}"
        )


@router.get("/statistics/overview", response_model=WalletStatisticsResponse)
async def get_wallet_statistics(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    network: Optional[str] = Query(None, description="网络类型筛选")
):
    """获取钱包池统计信息"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        wallet_service = WalletPoolService(db)
        stats = await wallet_service.get_pool_statistics(network)
        
        return WalletStatisticsResponse(
            total_wallets=stats["total_wallets"],
            available_wallets=stats["status_distribution"].get("available", 0),
            occupied_wallets=stats["status_distribution"].get("occupied", 0),
            maintenance_wallets=stats["status_distribution"].get("maintenance", 0),
            disabled_wallets=stats["status_distribution"].get("disabled", 0),
            total_balance=Decimal(str(stats["total_balance"])),
            average_balance=Decimal(str(stats["average_balance"])),
            total_received=Decimal(str(stats["total_received"])),
            utilization_rate=stats["utilization_rate"],
            network_distribution=stats["network_distribution"]
        )
        
    except Exception as e:
        logger.error(f"获取钱包统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )


@router.post("/{wallet_id}/release")
async def release_wallet(
    wallet_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """释放钱包"""
    # 简单的管理员权限检查
    if current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问此功能"
        )
    
    try:
        wallet_service = WalletPoolService(db)
        success = await wallet_service.release_wallet(wallet_id, 1)  # 使用固定管理员ID
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="钱包释放失败"
            )
        
        return {"message": "钱包释放成功", "wallet_id": wallet_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"释放钱包失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"钱包释放失败: {str(e)}"
        )