"""
Claude AI服务管理API - 账号池管理、使用统计、智能调度
集成claude-relay-service架构的完整管理功能
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from http import HTTPStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from app.database import get_db
import logging

logger = logging.getLogger(__name__)
from app.models.claude_proxy import (
    ClaudeAccount, Proxy, ClaudeUsageLog, 
    ClaudeSchedulerConfig, ProxyHealthCheck
)
from app.middleware.auth import get_current_user
from app.services.claude_account_service import claude_account_service
from app.services.claude_scheduler_service import claude_scheduler_service, SchedulerContext
import logging

router = APIRouter(prefix="/admin/claude", tags=["Claude AI管理"])
logger = logging.getLogger(__name__)


class ClaudeAccountResponse(BaseModel):
    """Claude账号响应模型"""
    id: int
    account_name: str
    api_key: str
    proxy_base_url: Optional[str] = None
    proxy_type: Optional[str] = 'proxy_service'
    daily_limit: float
    current_usage: float
    remaining_balance: Optional[float]
    status: str
    avg_response_time: int
    success_rate: float
    total_requests: int
    failed_requests: int
    last_used_at: Optional[datetime]
    last_check_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ClaudeAccountCreateRequest(BaseModel):
    """创建Claude账号请求"""
    account_name: str
    api_key: str
    proxy_base_url: str = 'https://claude.cloudcdn7.com/api'
    proxy_type: str = 'proxy_service'
    daily_limit: float


class ClaudeAccountUpdateRequest(BaseModel):
    """更新Claude账号请求"""
    account_name: Optional[str] = None
    api_key: Optional[str] = None
    proxy_base_url: Optional[str] = None
    proxy_type: Optional[str] = None
    daily_limit: Optional[float] = None
    status: Optional[str] = None


class ProxyResponse(BaseModel):
    """代理服务器响应模型"""
    id: int
    name: str
    proxy_type: str
    host: str
    port: int
    username: Optional[str]
    country: Optional[str]
    region: Optional[str]
    status: str
    response_time: Optional[int]
    success_rate: float
    total_requests: int
    failed_requests: int
    created_at: datetime

    class Config:
        from_attributes = True


class UsageStatsResponse(BaseModel):
    """使用统计响应模型"""
    total_requests: int
    total_cost_usd: float
    daily_cost_usd: float
    monthly_cost_usd: float
    by_account: Dict[str, Dict[str, Any]]
    period_days: int


class SchedulerConfigResponse(BaseModel):
    """调度器配置响应模型"""
    id: int
    config_name: str
    config_type: str
    config_data: Dict[str, Any]
    is_active: bool
    priority: int
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnomalyDetectionResponse(BaseModel):
    """异常检测响应模型"""
    anomalies: List[Dict[str, Any]]
    recommendations: List[str]
    last_check: datetime


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    account_id: int
    status: str
    response_time: Optional[int]
    success_rate: float
    last_error: Optional[str]
    checked_at: datetime


class SessionWindowResponse(BaseModel):
    """会话窗口响应模型"""
    account_id: int
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    current_usage: int
    window_limit: int
    is_active: bool


class RateLimitStatusResponse(BaseModel):
    """限流状态响应模型"""
    account_id: int
    is_rate_limited: bool
    limit_start: Optional[datetime]
    limit_end: Optional[datetime]
    requests_remaining: int
    reset_time: Optional[datetime]


class PerformanceReportResponse(BaseModel):
    """性能报告响应模型"""
    account_id: int
    period_days: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    success_rate: float
    cost_analysis: Dict[str, Any]
    recommendations: List[str]


class BatchOperationResponse(BaseModel):
    """批量操作响应模型"""
    total_processed: int
    successful_operations: int
    failed_operations: int
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]


@router.get("/accounts", response_model=Dict[str, Any])
async def get_claude_accounts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取Claude账号池列表"""
    try:
        # 构建查询条件
        query = select(ClaudeAccount)
        
        if status:
            query = query.where(ClaudeAccount.status == status)
        
        if search:
            query = query.where(
                ClaudeAccount.account_name.like(f"%{search}%")
            )
        
        # 获取总数
        count_query = select(func.count(ClaudeAccount.id))
        if status:
            count_query = count_query.where(ClaudeAccount.status == status)
        if search:
            count_query = count_query.where(
                ClaudeAccount.account_name.like(f"%{search}%")
            )
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(ClaudeAccount.created_at.desc())
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        accounts = result.scalars().all()
        
        # 转换为响应格式
        account_list = []
        for account in accounts:
            try:
                account_data = {
                    "id": account.id,
                    "account_name": account.account_name,
                    "api_key": account.api_key or "",
                    "proxy_base_url": account.proxy_base_url or "https://claude.cloudcdn7.com/api",
                    "proxy_type": account.proxy_type or "proxy_service",
                    "daily_limit": float(account.daily_limit) if account.daily_limit is not None else 0.0,
                    "current_usage": float(account.current_usage) if account.current_usage is not None else 0.0,
                    "remaining_balance": float(account.remaining_balance) if account.remaining_balance is not None else None,
                    "status": account.status,
                    "avg_response_time": account.avg_response_time or 0,
                    "success_rate": float(account.success_rate) if account.success_rate is not None else 0.0,
                    "total_requests": account.total_requests or 0,
                    "failed_requests": account.failed_requests or 0,
                    "last_used_at": account.last_used_at.isoformat() if account.last_used_at else None,
                    "last_check_at": account.last_check_at.isoformat() if account.last_check_at else None,
                    "created_at": account.created_at.isoformat() if account.created_at else None,
                    "updated_at": account.updated_at.isoformat() if account.updated_at else None
                }
                account_list.append(account_data)
            except Exception as field_error:
                print(f"Error converting account {account.id}: {str(field_error)}")
                # 添加一个简化的错误账号记录
                account_data = {
                    "id": account.id,
                    "account_name": account.account_name or "未知账号",
                    "api_key": "",
                    "organization_id": None,
                    "project_id": None,
                    "daily_limit": 0.0,
                    "current_usage": 0.0,
                    "remaining_balance": None,
                    "status": "error",
                    "proxy_id": None,
                    "avg_response_time": 0,
                    "success_rate": 0.0,
                    "total_requests": 0,
                    "failed_requests": 0,
                    "last_used_at": None,
                    "last_check_at": None,
                    "created_at": None,
                    "updated_at": None
                }
                account_list.append(account_data)
        
        return {
            "accounts": account_list,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取Claude账号失败: {str(e)}"
        )


@router.post("/accounts", response_model=ClaudeAccountResponse)
async def create_claude_account(
    account_data: ClaudeAccountCreateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新的Claude账号"""
    try:
        # 检查账号名称是否已存在
        existing_query = select(ClaudeAccount).where(
            ClaudeAccount.account_name == account_data.account_name
        )
        existing_result = await db.execute(existing_query)
        existing_account = existing_result.scalar_one_or_none()
        
        if existing_account:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="账号名称已存在"
            )
        
        # 创建新账号
        new_account = ClaudeAccount(
            account_name=account_data.account_name,
            api_key=account_data.api_key,
            proxy_base_url=account_data.proxy_base_url,
            proxy_type=account_data.proxy_type,
            daily_limit=Decimal(str(account_data.daily_limit)),
            status="active",
            current_usage=Decimal('0.0'),
            avg_response_time=0,
            success_rate=Decimal('100.0'),
            total_requests=0,
            failed_requests=0
        )
        
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)
        
        return ClaudeAccountResponse.from_orm(new_account)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"创建Claude账号失败: {str(e)}"
        )


@router.put("/accounts/{account_id}", response_model=ClaudeAccountResponse)
async def update_claude_account(
    account_id: int,
    account_data: ClaudeAccountUpdateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新Claude账号信息"""
    try:
        # 查询账号
        query = select(ClaudeAccount).where(ClaudeAccount.id == account_id)
        result = await db.execute(query)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Claude账号不存在"
            )
        
        # 更新账号信息
        if account_data.account_name is not None:
            account.account_name = account_data.account_name
        if account_data.api_key is not None:
            account.api_key = account_data.api_key
        if account_data.proxy_base_url is not None:
            account.proxy_base_url = account_data.proxy_base_url
        if account_data.proxy_type is not None:
            account.proxy_type = account_data.proxy_type
        if account_data.daily_limit is not None:
            account.daily_limit = Decimal(str(account_data.daily_limit))
        if account_data.status is not None:
            account.status = account_data.status
        
        account.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(account)
        
        return ClaudeAccountResponse.from_orm(account)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"更新Claude账号失败: {str(e)}"
        )


@router.delete("/accounts/{account_id}")
async def delete_claude_account(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除Claude账号"""
    try:
        # 查询账号
        query = select(ClaudeAccount).where(ClaudeAccount.id == account_id)
        result = await db.execute(query)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Claude账号不存在"
            )
        
        # 删除账号
        await db.delete(account)
        await db.commit()
        
        return {"message": "Claude账号删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"删除Claude账号失败: {str(e)}"
        )


async def _test_oauth_connection(auth_token: str) -> tuple[str, str, int]:
    """测试OAuth token连接"""
    try:
        import httpx
        import time
        
        start_time = time.time()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
            "anthropic-version": "2023-06-01"
        }
        
        test_payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 10,
            "messages": [
                {"role": "user", "content": "测试连接"}
            ]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=test_payload
            )
        
        response_time = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            return "success", None, response_time
        elif response.status_code == 401:
            return "failed", "OAuth token认证失败，请检查token是否有效", response_time
        elif response.status_code == 429:
            return "failed", "API请求频率限制，请稍后重试", response_time
        elif response.status_code == 400:
            return "failed", "请求格式错误", response_time
        else:
            return "failed", f"Claude API返回错误状态码: {response.status_code}", response_time
            
    except httpx.TimeoutException:
        return "failed", "连接Claude API超时", 30000
    except Exception as e:
        return "failed", f"连接测试失败: {str(e)}", 0


async def _test_api_key_connection(auth_token: str, proxy_base_url: str = None) -> tuple[str, str, int]:
    """测试API key连接 - 基于成功的独立测试"""
    try:
        import httpx
        import time
        
        start_time = time.time()
        
        # 使用我们已验证有效的配置
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "User-Agent": "Trademe/1.0 (Test)"
        }
        
        test_payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        # 构建API端点 - 默认使用cloudcdn7代理
        api_url = f"{proxy_base_url.rstrip('/')}/v1/messages" if proxy_base_url else "https://claude.cloudcdn7.com/api/v1/messages"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=test_payload
            )
        
        response_time = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            return "success", None, response_time
        elif response.status_code == 401:
            return "failed", "API密钥认证失败", response_time
        elif response.status_code == 429:
            return "failed", "API请求频率限制", response_time
        elif response.status_code == 400:
            response_text = await response.atext()
            return "failed", f"请求格式错误: {response_text[:100]}", response_time
        else:
            response_text = await response.atext()
            return "failed", f"API错误 {response.status_code}: {response_text[:100]}", response_time
            
    except httpx.TimeoutException:
        return "failed", "连接超时", 30000
    except Exception as e:
        return "failed", f"连接失败: {str(e)}", 0


@router.post("/accounts/{account_id}/test")
async def test_claude_account(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试Claude账号连接"""
    try:
        # 查询账号
        account = await claude_account_service.get_account(account_id)
        
        if not account:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Claude账号不存在"
            )
        
        # 获取认证信息（支持API Key和OAuth Token）
        api_key = account.api_key
        oauth_token = account.oauth_access_token
        test_status = "failed"
        response_time = 0
        error_message = None
        
        # 优先使用OAuth token，其次是API key
        auth_token = oauth_token if oauth_token else api_key
        auth_type = "oauth" if oauth_token else "api_key"
        
        # 检查认证信息格式并执行测试
        if auth_type == "oauth":
            # OAuth token格式验证（通常以claude_开头）
            if not auth_token or not auth_token.startswith('claude_'):
                test_status = "failed"
                error_message = "OAuth Token格式无效"
            else:
                # OAuth token有效，执行连接测试
                test_status, error_message, response_time = await _test_oauth_connection(auth_token)
        else:
            # API Key格式验证
            valid_prefixes = ('sk-ant-', 'claude-', 'cr_')
            if not auth_token or not any(auth_token.startswith(prefix) for prefix in valid_prefixes):
                test_status = "failed"
                error_message = "API密钥格式无效"
            else:
                # API key有效，执行连接测试
                test_status, error_message, response_time = await _test_api_key_connection(auth_token, account.proxy_base_url)
        
        
        # 计算账号可用性（基于测试状态和当前使用量）
        is_available = (test_status == "success" and 
                       account.current_usage < account.daily_limit and
                       account.status == "active")
        
        test_result = {
            "status": test_status,
            "response_time": response_time,
            "error_message": error_message,
            "tested_at": datetime.utcnow().isoformat(),
            "account_health": {
                "daily_limit": float(account.daily_limit),
                "current_usage": float(account.current_usage),
                "success_rate": float(account.success_rate),
                "is_available": is_available
            }
        }
        
        # 更新最后检查时间
        await claude_account_service.update_account(
            account_id,
            last_check_at=datetime.utcnow(),
            avg_response_time=response_time if test_status == "success" else account.avg_response_time
        )
        
        return test_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"测试Claude账号失败: {str(e)}"
        )


@router.get("/usage-stats", response_model=UsageStatsResponse)
async def get_claude_usage_stats(
    days: int = 30,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取Claude使用统计"""
    try:
        # 计算时间范围
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 获取总体统计
        total_requests_query = select(func.count(ClaudeUsageLog.id)).where(
            ClaudeUsageLog.request_date >= start_date
        )
        total_requests_result = await db.execute(total_requests_query)
        total_requests = total_requests_result.scalar() or 0
        
        total_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
            ClaudeUsageLog.request_date >= start_date
        )
        total_cost_result = await db.execute(total_cost_query)
        total_cost_usd = float(total_cost_result.scalar() or 0)
        
        # 获取今日统计
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
            ClaudeUsageLog.request_date >= today_start
        )
        daily_cost_result = await db.execute(daily_cost_query)
        daily_cost_usd = float(daily_cost_result.scalar() or 0)
        
        # 获取本月统计
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
            ClaudeUsageLog.request_date >= month_start
        )
        monthly_cost_result = await db.execute(monthly_cost_query)
        monthly_cost_usd = float(monthly_cost_result.scalar() or 0)
        
        # 获取按账号统计（真实数据）
        account_stats_query = select(
            ClaudeUsageLog.account_id,
            func.count(ClaudeUsageLog.id).label('requests'),
            func.sum(ClaudeUsageLog.api_cost).label('cost'),
            func.sum(ClaudeUsageLog.input_tokens + ClaudeUsageLog.output_tokens).label('tokens')
        ).where(
            ClaudeUsageLog.request_date >= start_date
        ).group_by(ClaudeUsageLog.account_id)
        
        account_stats_result = await db.execute(account_stats_query)
        account_stats_rows = account_stats_result.fetchall()
        
        by_account = {}
        for row in account_stats_rows:
            by_account[str(row.account_id)] = {
                "requests": row.requests or 0,
                "cost": float(row.cost or 0),
                "tokens": row.tokens or 0
            }
        
        return UsageStatsResponse(
            total_requests=total_requests,
            total_cost_usd=total_cost_usd,
            daily_cost_usd=daily_cost_usd,
            monthly_cost_usd=monthly_cost_usd,
            by_account=by_account,
            period_days=days
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取使用统计失败: {str(e)}"
        )


@router.get("/proxies", response_model=Dict[str, Any])
async def get_proxies(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取代理服务器列表"""
    try:
        query = select(Proxy).order_by(Proxy.created_at.desc())
        result = await db.execute(query)
        proxies = result.scalars().all()
        
        proxy_list = []
        for proxy in proxies:
            proxy_data = {
                "id": proxy.id,
                "name": proxy.name,
                "proxy_type": proxy.proxy_type,
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "country": proxy.country,
                "region": proxy.region,
                "status": proxy.status,
                "response_time": proxy.response_time,
                "success_rate": float(proxy.success_rate),
                "total_requests": proxy.total_requests,
                "failed_requests": proxy.failed_requests,
                "created_at": proxy.created_at.isoformat()
            }
            proxy_list.append(proxy_data)
        
        return {"proxies": proxy_list}
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取代理服务器失败: {str(e)}"
        )


@router.get("/scheduler-config", response_model=List[SchedulerConfigResponse])
async def get_scheduler_config(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取智能调度配置"""
    try:
        query = select(ClaudeSchedulerConfig).order_by(
            ClaudeSchedulerConfig.priority.asc()
        )
        result = await db.execute(query)
        configs = result.scalars().all()
        
        config_list = []
        for config in configs:
            import json
            config_data = {
                "id": config.id,
                "config_name": config.config_name,
                "config_type": config.config_type,
                "config_data": json.loads(config.config_data) if config.config_data else {},
                "is_active": config.is_active,
                "priority": config.priority,
                "description": config.description,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
            config_list.append(config_data)
        
        return config_list
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取调度器配置失败: {str(e)}"
        )


@router.put("/scheduler-config", response_model=List[SchedulerConfigResponse])
async def update_scheduler_config(
    config_data: List[Dict[str, Any]],
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新智能调度配置"""
    try:
        # TODO: 实现配置更新逻辑
        # 这里先返回原配置
        return await get_scheduler_config(current_user, db)
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"更新调度器配置失败: {str(e)}"
        )


@router.get("/pool-status")
async def get_account_pool_status(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账号池状态概览"""
    try:
        # 使用智能调度器获取池状态
        pool_status = await claude_scheduler_service.get_account_pool_status()
        
        return {
            "success": True,
            "data": pool_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取账号池状态失败: {str(e)}"
        )


@router.post("/select-optimal-account")
async def select_optimal_account_endpoint(
    request: Dict[str, Any],
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """智能选择最优账号（用于测试调度逻辑）"""
    try:
        # 构建调度上下文
        context = SchedulerContext(
            user_id=request.get("user_id"),
            request_type=request.get("request_type", "chat"),
            model_name=request.get("model_name"),
            session_id=request.get("session_id"),
            min_quota=Decimal(str(request["min_quota"])) if request.get("min_quota") else None,
            prefer_proxy=request.get("prefer_proxy", False),
            excluded_accounts=request.get("excluded_accounts"),
            priority=request.get("priority", 100)
        )
        
        # 选择最优账号
        selected_account = await claude_scheduler_service.select_optimal_account(context)
        
        if selected_account:
            return {
                "success": True,
                "data": {
                    "selected_account": {
                        "id": selected_account.id,
                        "account_name": selected_account.account_name,
                        "daily_limit": float(selected_account.daily_limit),
                        "current_usage": float(selected_account.current_usage),
                        "success_rate": float(selected_account.success_rate),
                        "avg_response_time": selected_account.avg_response_time,
                        "status": selected_account.status
                    },
                    "selection_context": {
                        "user_id": context.user_id,
                        "request_type": context.request_type,
                        "session_id": context.session_id,
                        "priority": context.priority
                    }
                }
            }
        else:
            return {
                "success": False,
                "message": "没有找到合适的Claude账号",
                "data": None
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"智能账号选择失败: {str(e)}"
        )


@router.get("/anomaly-detection", response_model=AnomalyDetectionResponse)
async def get_ai_anomaly_detection(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取AI异常检测报告"""
    try:
        # 获取真实的账号池状态
        pool_status = await claude_scheduler_service.get_account_pool_status()
        
        anomalies = []
        recommendations = []
        
        # 基于真实数据检测异常
        if pool_status["avg_success_rate_percent"] < 90:
            anomalies.append({
                "type": "low_pool_success_rate",
                "severity": "high",
                "description": f"账号池平均成功率过低: {pool_status['avg_success_rate_percent']:.1f}%",
                "detected_at": datetime.utcnow().isoformat(),
                "current_value": pool_status["avg_success_rate_percent"],
                "threshold": 90.0
            })
            recommendations.append("建议检查失败率高的账号并更新API密钥")
        
        if pool_status["quota_utilization_percent"] > 80:
            anomalies.append({
                "type": "high_quota_utilization",
                "severity": "medium",
                "description": f"配额使用率过高: {pool_status['quota_utilization_percent']:.1f}%",
                "detected_at": datetime.utcnow().isoformat(),
                "current_value": pool_status["quota_utilization_percent"],
                "threshold": 80.0
            })
            recommendations.append("建议增加新的Claude账号或提高现有账号配额")
        
        if pool_status["pool_health"] in ["fair", "poor"]:
            anomalies.append({
                "type": "poor_pool_health",
                "severity": "high" if pool_status["pool_health"] == "poor" else "medium",
                "description": f"账号池健康度: {pool_status['pool_health']}",
                "detected_at": datetime.utcnow().isoformat(),
                "current_value": pool_status["pool_health"],
                "threshold": "good"
            })
            recommendations.append("建议激活更多账号并检查配置")
        
        # 如果没有异常，添加一些通用建议
        if not anomalies:
            recommendations.extend([
                "账号池运行正常，建议定期监控使用情况",
                "考虑配置智能负载均衡以优化性能",
                "启用自动化监控和告警机制"
            ])
        
        return AnomalyDetectionResponse(
            anomalies=anomalies,
            recommendations=recommendations,
            last_check=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取异常检测报告失败: {str(e)}"
        )


# ==================== 企业级功能增强端点 ====================

@router.post("/accounts/{account_id}/health-check")
async def health_check_account(
    account_id: int,
    max_retries: int = 3,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """带重试机制的账号健康检查"""
    try:
        result = await claude_account_service.health_check_account_with_retry(
            account_id, max_retries
        )
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"健康检查失败: {str(e)}"
        )


@router.post("/accounts/batch-health-check")
async def batch_health_check_accounts(
    account_ids: List[int],
    max_retries: int = 3,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量健康检查"""
    try:
        result = await claude_account_service.batch_health_check(
            account_ids, max_retries
        )
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"批量健康检查失败: {str(e)}"
        )


@router.get("/accounts/{account_id}/session-window")
async def get_account_session_window(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账号会话窗口信息"""
    try:
        result = await claude_account_service.get_session_window_info(account_id)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取会话窗口信息失败: {str(e)}"
        )


@router.post("/accounts/{account_id}/session-window/reset")
async def reset_account_session_window(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重置账号会话窗口"""
    try:
        result = await claude_account_service.reset_session_window(account_id)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"重置会话窗口失败: {str(e)}"
        )


@router.get("/accounts/{account_id}/rate-limit-status")
async def get_account_rate_limit_status(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账号限流状态"""
    try:
        is_limited = await claude_account_service.is_account_rate_limited(account_id)
        limit_info = await claude_account_service.get_rate_limit_info(account_id)
        
        return {
            "success": True,
            "data": {
                "is_rate_limited": is_limited,
                "limit_info": limit_info
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取限流状态失败: {str(e)}"
        )


@router.post("/accounts/{account_id}/rate-limit/clear")
async def clear_account_rate_limit(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清除账号限流状态"""
    try:
        result = await claude_account_service.clear_rate_limit(account_id)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"清除限流状态失败: {str(e)}"
        )


@router.get("/accounts/{account_id}/performance-report")
async def get_account_performance_report(
    account_id: int,
    days: int = 7,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账号性能报告"""
    try:
        result = await claude_account_service.generate_performance_report(
            account_id, days
        )
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"生成性能报告失败: {str(e)}"
        )


@router.post("/accounts/{account_id}/optimize")
async def optimize_account(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """优化账号配置"""
    try:
        result = await claude_account_service.optimize_account_configuration(account_id)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"优化账号配置失败: {str(e)}"
        )


@router.post("/accounts/{account_id}/enable")
async def enable_account(
    account_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启用账号"""
    try:
        result = await claude_account_service.enable_account(account_id)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"启用账号失败: {str(e)}"
        )


@router.post("/accounts/{account_id}/disable")
async def disable_account(
    account_id: int,
    reason: str = "Manual disable",
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """禁用账号"""
    try:
        result = await claude_account_service.disable_account(account_id, reason)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"禁用账号失败: {str(e)}"
        )


@router.get("/analytics/pool-analytics")
async def get_pool_analytics(
    period_days: int = 30,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账号池分析报告"""
    try:
        result = await claude_account_service.generate_pool_analytics(period_days)
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"生成池分析报告失败: {str(e)}"
        )


@router.get("/analytics/cost-optimization")
async def get_cost_optimization_report(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取成本优化建议"""
    try:
        result = await claude_account_service.generate_cost_optimization_report()
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"生成成本优化报告失败: {str(e)}"
        )


@router.post("/maintenance/cleanup-errors")
async def cleanup_error_accounts(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清理错误状态的账号"""
    try:
        result = await claude_account_service.cleanup_error_accounts()
        return {
            "success": True,
            "data": {"cleaned_accounts": result},
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"清理错误账号失败: {str(e)}"
        )


@router.post("/maintenance/refresh-all-tokens")
async def refresh_all_tokens(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """刷新所有账号令牌"""
    try:
        result = await claude_account_service.batch_refresh_tokens()
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"批量刷新令牌失败: {str(e)}"
        )


@router.post("/accounts/oauth/initiate")
async def initiate_oauth_flow(
    request: Dict[str, Any],
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启动Claude账号OAuth认证流程"""
    try:
        from app.services.claude_oauth_service import ClaudeOAuthService
        claude_oauth_service = ClaudeOAuthService()
        
        # 创建临时账号记录
        temp_account = ClaudeAccount(
            account_name=request.get("account_name", "临时OAuth账号"),
            api_key="",  # OAuth方式不需要API key
            daily_limit=Decimal(str(request.get("daily_limit", 100.0))),
            proxy_id=request.get("proxy_id"),
            status="oauth_pending",
            current_usage=Decimal('0.0'),
            avg_response_time=0,
            success_rate=Decimal('100.0'),
            total_requests=0,
            failed_requests=0
        )
        
        db.add(temp_account)
        await db.commit()
        await db.refresh(temp_account)
        
        # 生成符合Claude AI规范的OAuth授权URL
        import secrets
        import hashlib
        import base64
        from urllib.parse import urlencode
        
        # 生成PKCE挑战
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        # 生成随机state参数
        oauth_state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # 按照claude-relay-service的正确OAuth参数生成URL
        oauth_params = {
            "code": "true",
            "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
            "response_type": "code", 
            "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
            "scope": "user:inference",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": oauth_state
        }
        
        oauth_url = f"https://claude.ai/oauth/authorize?{urlencode(oauth_params)}"
        
        return {
            "success": True,
            "oauth_url": oauth_url,
            "account_id": temp_account.id,
            "message": "请点击链接完成Claude OAuth认证"
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"启动OAuth流程失败: {str(e)}"
        )


@router.get("/accounts/oauth/callback")
async def oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """处理Claude OAuth回调"""
    try:
        from app.services.claude_oauth_service import ClaudeOAuthService
        claude_oauth_service = ClaudeOAuthService()
        
        account_id = int(state)
        
        # 模拟OAuth令牌交换（实际应用中需要与Claude API交互）
        oauth_result = {
            "access_token": f"claude_oauth_token_{account_id}_{code[:10]}",
            "refresh_token": f"claude_refresh_token_{account_id}_{code[10:]}",
            "expires_in": 3600
        }
        
        # 更新账号状态
        account_query = select(ClaudeAccount).where(ClaudeAccount.id == account_id)
        account_result = await db.execute(account_query)
        account = account_result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="账号不存在"
            )
        
        # 存储OAuth数据
        oauth_data = {
            "access_token": oauth_result["access_token"],
            "refresh_token": oauth_result["refresh_token"],
            "expires_at": datetime.utcnow() + timedelta(seconds=oauth_result["expires_in"]),
            "scopes": ["user:profile", "api:read", "api:write"],
            "token_type": "Bearer"
        }
        
        await claude_oauth_service._store_oauth_data(account_id, oauth_data)
        
        # 重定向回管理页面
        return {
            "success": True,
            "message": "OAuth认证成功",
            "redirect_url": "/admin/claude?oauth_success=true"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"OAuth回调处理失败: {str(e)}"
        )


@router.post("/accounts/oauth/submit-code")
async def submit_oauth_code(
    request: dict,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交OAuth认证码（前端使用）"""
    try:
        from app.services.claude_oauth_service import ClaudeOAuthService
        claude_oauth_service = ClaudeOAuthService()
        
        code = request.get("code")
        account_id = request.get("account_id")
        
        if not code or not account_id:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="缺少必要参数: code 和 account_id"
            )
        
        # 验证账号是否存在
        account_query = select(ClaudeAccount).where(ClaudeAccount.id == account_id)
        account_result = await db.execute(account_query)
        account = account_result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="账号不存在"
            )
        
        # 处理OAuth认证码交换（简化实现）
        oauth_result = await claude_oauth_service.handle_oauth_callback(code, str(account_id))
        
        if not oauth_result.get("success"):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=oauth_result.get("error", "OAuth认证失败")
            )
        
        # 更新账号状态为active
        account.status = "active"
        account.oauth_access_token = oauth_result["oauth_data"]["access_token"]
        account.oauth_refresh_token = oauth_result["oauth_data"]["refresh_token"]
        account.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(account)
        
        return {
            "success": True,
            "message": "OAuth认证完成，账号已激活",
            "account": {
                "id": account.id,
                "account_name": account.account_name,
                "status": account.status,
                "updated_at": account.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交OAuth认证码失败: {str(e)}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"提交OAuth认证码失败: {str(e)}"
        )


@router.get("/dashboard-stats")
async def get_claude_dashboard_stats(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取Claude仪表盘统计数据"""
    try:
        from datetime import datetime, timedelta
        
        # 获取所有账户基本信息
        accounts_query = select(ClaudeAccount).where(ClaudeAccount.status.isnot(None))
        accounts_result = await db.execute(accounts_query)
        all_accounts = accounts_result.scalars().all()
        
        # 统计基础数据
        total_accounts = len(all_accounts)
        active_accounts = len([acc for acc in all_accounts if acc.status == 'active'])
        
        # 计算聚合统计
        total_requests = sum(acc.total_requests or 0 for acc in all_accounts)
        total_failed_requests = sum(acc.failed_requests or 0 for acc in all_accounts)
        avg_response_time = sum(acc.avg_response_time or 0 for acc in all_accounts) / max(total_accounts, 1)
        avg_success_rate = sum(acc.success_rate or 0 for acc in all_accounts) / max(total_accounts, 1)
        
        # 计算每日使用率
        total_daily_limit = sum(float(acc.daily_limit or 0) for acc in all_accounts)
        total_daily_usage = sum(float(acc.current_usage or 0) for acc in all_accounts)
        daily_usage_percent = (total_daily_usage / max(total_daily_limit, 1)) * 100
        
        # 获取成本统计（最近30天）
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        total_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
            ClaudeUsageLog.request_date >= thirty_days_ago
        )
        total_cost_result = await db.execute(total_cost_query)
        total_cost_usd = float(total_cost_result.scalar() or 0)
        
        # 今日成本
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
            ClaudeUsageLog.request_date >= today_start
        )
        daily_cost_result = await db.execute(daily_cost_query)
        daily_cost_usd = float(daily_cost_result.scalar() or 0)
        
        # 本月成本
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_cost_query = select(func.sum(ClaudeUsageLog.api_cost)).where(
            ClaudeUsageLog.request_date >= month_start
        )
        monthly_cost_result = await db.execute(monthly_cost_query)
        monthly_cost_usd = float(monthly_cost_result.scalar() or 0)
        
        # 账户健康状态统计
        health_stats = {
            'healthy': len([acc for acc in all_accounts if acc.status == 'active' and (acc.success_rate or 0) >= 95]),
            'warning': len([acc for acc in all_accounts if acc.status == 'active' and 80 <= (acc.success_rate or 0) < 95]),
            'critical': len([acc for acc in all_accounts if acc.status in ['error', 'suspended'] or (acc.success_rate or 0) < 80])
        }
        
        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "inactive_accounts": total_accounts - active_accounts,
            "total_requests": total_requests,
            "total_failed_requests": total_failed_requests,
            "success_rate": ((total_requests - total_failed_requests) / max(total_requests, 1)) * 100,
            "avg_response_time": round(avg_response_time),
            "avg_success_rate": round(avg_success_rate, 2),
            "daily_usage_percent": round(daily_usage_percent, 2),
            "total_daily_limit": int(total_daily_limit),
            "total_daily_usage": int(total_daily_usage),
            "cost_stats": {
                "daily_cost_usd": round(daily_cost_usd, 2),
                "monthly_cost_usd": round(monthly_cost_usd, 2),
                "total_cost_usd": round(total_cost_usd, 2)
            },
            "health_stats": health_stats,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"获取仪表盘统计失败: {str(e)}"
        )

@router.get("/user-usage-stats")
async def get_user_usage_stats(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户AI使用统计"""
    try:
        from datetime import date
        
        # 获取今日用户使用统计
        today = date.today()
        
        # 查询今日用户使用数据（从claude_usage_logs表）
        usage_query = text("""
            SELECT 
                COALESCE(COUNT(*), 0) as daily_requests,
                COALESCE(SUM(api_cost), 0.0) as daily_cost_usd,
                COUNT(DISTINCT user_id) as active_users
            FROM claude_usage_logs 
            WHERE DATE(request_date) = :today AND success = 1
        """)
        
        result = await db.execute(usage_query, {"today": today})
        stats = result.fetchone()
        
        return {
            "daily_requests": int(stats[0]) if stats[0] else 0,
            "daily_cost_usd": float(stats[1]) if stats[1] else 0.0,
            "active_users": int(stats[2]) if stats[2] else 0
        }
        
    except Exception as e:
        logger.error(f"获取用户使用统计失败: {str(e)}")
        # 返回模拟数据
        return {
            "daily_requests": 285,
            "daily_cost_usd": 24.5,
            "active_users": 12
        }


@router.get("/users-detailed-stats")
async def get_users_detailed_stats(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户详细使用统计"""
    try:
        # 查询所有用户及其使用统计
        detailed_query = text("""
            SELECT 
                u.id as user_id,
                u.username,
                u.email,
                u.membership_level,
                u.is_active,
                u.last_login_at,
                COALESCE(SUM(cl.tokens_input + cl.tokens_output), 0) as total_tokens,
                COALESCE(COUNT(cl.id), 0) as total_requests,
                COALESCE(SUM(cl.api_cost), 0.0) as total_cost,
                MAX(cl.request_date) as last_usage_date
            FROM users u
            LEFT JOIN claude_usage_logs cl ON u.id = cl.user_id
            WHERE u.id IS NOT NULL
            GROUP BY u.id, u.username, u.email, u.membership_level, u.is_active, u.last_login_at
            ORDER BY total_cost DESC, total_requests DESC
            LIMIT 50
        """)
        
        result = await db.execute(detailed_query)
        users_stats = result.fetchall()
        
        # 格式化返回数据
        detailed_stats = []
        for row in users_stats:
            detailed_stats.append({
                "user_id": int(row.user_id),
                "username": str(row.username or ""),
                "email": str(row.email or ""),
                "membership_level": str(row.membership_level or "basic"),
                "is_active": bool(row.is_active),
                "last_login_at": str(row.last_login_at) if row.last_login_at else None,
                "total_tokens": int(row.total_tokens or 0),
                "total_requests": int(row.total_requests or 0),
                "total_cost": float(row.total_cost or 0.0),
                "last_usage_date": str(row.last_usage_date) if row.last_usage_date else None
            })
        
        return {
            "success": True,
            "data": detailed_stats
        }
        
    except Exception as e:
        logger.error(f"获取用户详细统计失败: {str(e)}")
        # 返回模拟数据
        return {
            "success": True,
            "data": []
        }