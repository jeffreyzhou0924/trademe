"""
用户管理API - 管理员用户管理接口
提供用户CRUD、标签管理、行为分析、批量操作等全面功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator, EmailStr
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from decimal import Decimal

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.user_management_service import UserManagementService
from app.models.user import User
from app.utils.data_validation import DataValidator
from app.models.user_management import (
    TagType, ActivityType, NotificationType, NotificationChannel
)
from app.models.admin import AdminOperationLog
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["用户管理"])  # 修改prefix以支持/admin/stats/system路径


# ========== 简化权限检查 ==========

async def check_admin_permission(current_user=Depends(get_current_user)):
    """检查管理员权限 - 简化版本，兼容企业级功能"""
    if not current_user or current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


# ========== Pydantic 模型定义 ==========

class UserTagCreate(BaseModel):
    """创建用户标签请求"""
    name: str = Field(..., description="标签名称", min_length=1, max_length=50)
    display_name: str = Field(..., description="显示名称", max_length=100)
    description: Optional[str] = Field(None, description="标签描述", max_length=500)
    color: str = Field("#3B82F6", description="标签颜色(HEX)", pattern="^#[0-9A-Fa-f]{6}$")
    tag_type: str = Field("manual", description="标签类型")
    auto_assign_rule: Optional[Dict[str, Any]] = Field(None, description="自动分配规则")
    
    @validator('tag_type')
    def validate_tag_type(cls, v):
        valid_types = ['system', 'manual', 'auto']
        if v not in valid_types:
            raise ValueError(f'标签类型必须是: {valid_types}')
        return v


class UserTagUpdate(BaseModel):
    """更新用户标签请求"""
    display_name: Optional[str] = Field(None, description="显示名称", max_length=100)
    description: Optional[str] = Field(None, description="标签描述", max_length=500)
    color: Optional[str] = Field(None, description="标签颜色(HEX)", pattern="^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = Field(None, description="是否启用")
    auto_assign_rule: Optional[Dict[str, Any]] = Field(None, description="自动分配规则")


class TagAssignmentRequest(BaseModel):
    """标签分配请求"""
    user_id: int = Field(..., description="用户ID")
    tag_id: int = Field(..., description="标签ID")
    assigned_reason: Optional[str] = Field(None, description="分配原因", max_length=200)
    expires_at: Optional[datetime] = Field(None, description="过期时间")


class BatchTagAssignmentRequest(BaseModel):
    """批量标签分配请求"""
    user_ids: List[int] = Field(..., description="用户ID列表", min_items=1)
    tag_ids: List[int] = Field(..., description="标签ID列表", min_items=1)
    assigned_reason: Optional[str] = Field(None, description="分配原因", max_length=200)


class UserUpdateRequest(BaseModel):
    """用户更新请求"""
    username: Optional[str] = Field(None, description="用户名", min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="电话", max_length=20)
    membership_level: Optional[str] = Field(None, description="会员等级")
    membership_expires_at: Optional[datetime] = Field(None, description="会员到期时间")
    is_active: Optional[bool] = Field(None, description="是否激活")
    email_verified: Optional[bool] = Field(None, description="邮箱是否验证")


class BatchUserUpdateRequest(BaseModel):
    """批量用户更新请求"""
    user_ids: List[int] = Field(..., description="用户ID列表", min_items=1)
    updates: UserUpdateRequest = Field(..., description="更新字段")


class UserActivityLogRequest(BaseModel):
    """用户活动记录请求"""
    user_id: int = Field(..., description="用户ID")
    activity_type: str = Field(..., description="活动类型")
    activity_description: str = Field(..., description="活动描述", max_length=500)
    ip_address: Optional[str] = Field(None, description="IP地址")
    resource_type: Optional[str] = Field(None, description="资源类型")
    resource_id: Optional[int] = Field(None, description="资源ID")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="附加数据")


class UserSearchFilters(BaseModel):
    """用户搜索过滤条件"""
    search: Optional[str] = Field(None, description="搜索关键词")
    membership_levels: Optional[List[str]] = Field(None, description="会员等级")
    is_active: Optional[bool] = Field(None, description="是否激活")
    email_verified: Optional[bool] = Field(None, description="邮箱是否验证")
    tags: Optional[List[str]] = Field(None, description="标签名称")
    created_after: Optional[datetime] = Field(None, description="创建时间起始")
    created_before: Optional[datetime] = Field(None, description="创建时间结束")
    last_login_after: Optional[datetime] = Field(None, description="最后登录起始")
    last_login_before: Optional[datetime] = Field(None, description="最后登录结束")


# ========== 系统统计 ==========

@router.get("/stats/system", summary="获取系统统计信息")
async def get_system_stats(
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取系统统计信息 - 企业级版本"""
    try:
        from sqlalchemy import select, func, case, text
        from datetime import datetime, timedelta
        
        # 使用单个复杂查询获取所有统计数据
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        query = select(
            func.count(User.id).label('total_users'),
            func.sum(case((User.is_active == True, 1), else_=0)).label('active_users'),
            func.sum(case((User.email_verified == True, 1), else_=0)).label('verified_users'),
            func.sum(case((User.membership_level == 'basic', 1), else_=0)).label('basic_users'),
            func.sum(case((User.membership_level == 'premium', 1), else_=0)).label('premium_users'),
            func.sum(case((User.membership_level == 'professional', 1), else_=0)).label('professional_users'),
        )
        
        result = await db.execute(query)
        stats_row = result.first()
        
        # 获取最近7天新用户数量
        recent_query = text("SELECT COUNT(*) FROM users WHERE created_at >= :seven_days_ago")
        recent_result = await db.execute(recent_query, {"seven_days_ago": seven_days_ago.timestamp() * 1000})
        new_users_7days = recent_result.scalar() or 0
        
        # 提取统计数据
        total_users = stats_row.total_users or 0
        active_users = stats_row.active_users or 0
        verified_users = stats_row.verified_users or 0
        basic_users = stats_row.basic_users or 0
        premium_users = stats_row.premium_users or 0
        professional_users = stats_row.professional_users or 0
        
        # 计算比率
        active_rate = (active_users / total_users * 100) if total_users > 0 else 0
        verification_rate = (verified_users / total_users * 100) if total_users > 0 else 0
        
        # 转换为前端需要的格式
        system_stats = {
            "users": {
                "total": total_users,
                "active": active_users,
                "inactive": total_users - active_users,
                "verified": verified_users,
                "unverified": total_users - verified_users,
                "recent_7days": new_users_7days
            },
            "membership": {
                "basic": basic_users,
                "premium": premium_users,
                "professional": professional_users
            },
            "growth": {
                "weekly_new_users": new_users_7days,
                "active_rate": DataValidator.safe_format_percentage(active_rate, decimals=1),
                "verification_rate": DataValidator.safe_format_percentage(verification_rate, decimals=1)
            }
        }
        
        return {
            "success": True,
            "data": system_stats
        }
        
    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统统计失败: {str(e)}"
        )


# ========== 用户查询与管理 ==========

@router.get("/users/", summary="高级用户搜索")
async def search_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    membership_levels: Optional[str] = Query(None, description="会员等级(逗号分隔)"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    email_verified: Optional[bool] = Query(None, description="邮箱是否验证"),
    tags: Optional[str] = Query(None, description="标签名称(逗号分隔)"),
    created_after: Optional[datetime] = Query(None, description="创建时间起始"),
    created_before: Optional[datetime] = Query(None, description="创建时间结束"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """高级用户搜索和筛选"""
    
    try:
        from sqlalchemy import select, text
        
        # 构建查询条件 - 简化版本
        conditions = []
        params = {"offset": (page - 1) * page_size, "limit": page_size}
        
        if search:
            conditions.append("(username LIKE :search OR email LIKE :search)")
            params["search"] = f"%{search}%"
        
        if membership_levels:
            membership_list = membership_levels.split(',')
            membership_placeholders = ','.join([f"'{level}'" for level in membership_list])
            conditions.append(f"membership_level IN ({membership_placeholders})")
            
        if is_active is not None:
            conditions.append("is_active = :is_active")
            params["is_active"] = is_active
        
        if email_verified is not None:
            conditions.append("email_verified = :email_verified")
            params["email_verified"] = email_verified
        
        where_clause = ""
        if conditions:
            where_clause = f"WHERE {' AND '.join(conditions)}"
        
        # 获取用户列表
        query = text(f"""
            SELECT id, username, email, membership_level, is_active, email_verified, 
                   created_at, last_login_at, phone, avatar_url
            FROM users 
            {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT :limit OFFSET :offset
        """)
        
        result = await db.execute(query, params)
        user_rows = result.fetchall()
        
        # 获取总数
        count_query = text(f"SELECT COUNT(*) FROM users {where_clause}")
        count_result = await db.execute(count_query, {k: v for k, v in params.items() if k not in ['offset', 'limit']})
        total = count_result.scalar()
        
        # 转换数据格式（避免datetime序列化问题）
        users = []
        for row in user_rows:
            try:
                created_at_str = ""
                last_login_str = None
                
                if row.created_at:
                    try:
                        timestamp = int(row.created_at) / 1000 if row.created_at > 1000000000000 else int(row.created_at)
                        created_at_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    except:
                        created_at_str = str(row.created_at)
                
                if row.last_login_at:
                    try:
                        timestamp = int(row.last_login_at) / 1000 if row.last_login_at > 1000000000000 else int(row.last_login_at)
                        last_login_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    except:
                        last_login_str = str(row.last_login_at)
                
                users.append({
                    "id": row.id,
                    "username": str(row.username or ""),
                    "email": str(row.email or ""),
                    "membership_level": str(row.membership_level or "basic"),
                    "is_active": bool(row.is_active),
                    "email_verified": bool(row.email_verified),
                    "phone": str(row.phone or "") if row.phone else None,
                    "avatar_url": str(row.avatar_url or "") if row.avatar_url else None,
                    "created_at": created_at_str,
                    "last_login_at": last_login_str,
                    "updated_at": created_at_str,
                    "tags": []  # 简化版本暂不处理标签
                })
            except Exception as row_error:
                logger.error(f"处理用户行时出错: {row_error}")
                continue
        
        return {
            "success": True,
            "data": {
                "users": users,
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                    "has_next": page * page_size < total,
                    "has_prev": page > 1
                }
            }
        }
        
    except Exception as e:
        logger.error(f"用户搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


@router.get("/users/{user_id}", summary="获取用户详细信息")
async def get_user_details(
    user_id: int,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """获取用户360度全息信息"""
    
    try:
        from sqlalchemy import select, text
        
        # 查询用户基本信息
        user_query = text("""
            SELECT id, username, email, membership_level, is_active, 
                   email_verified, created_at, last_login_at,
                   membership_expires_at, phone, avatar_url
            FROM users 
            WHERE id = :user_id
        """)
        
        result = await db.execute(user_query, {"user_id": user_id})
        user_row = result.first()
        
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 转换用户基本信息
        created_at_str = ""
        last_login_str = None
        expires_at_str = None
        
        if user_row.created_at:
            try:
                timestamp = int(user_row.created_at) / 1000 if user_row.created_at > 1000000000000 else int(user_row.created_at)
                created_at_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            except:
                created_at_str = str(user_row.created_at)
        
        if user_row.last_login_at:
            try:
                timestamp = int(user_row.last_login_at) / 1000 if user_row.last_login_at > 1000000000000 else int(user_row.last_login_at)
                last_login_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            except:
                last_login_str = str(user_row.last_login_at)
                
        if user_row.membership_expires_at:
            try:
                timestamp = int(user_row.membership_expires_at) / 1000 if user_row.membership_expires_at > 1000000000000 else int(user_row.membership_expires_at)
                expires_at_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            except:
                expires_at_str = str(user_row.membership_expires_at)
        
        # 查询用户统计数据
        strategies_query = text("SELECT COUNT(*) as total, COUNT(CASE WHEN is_active = 1 THEN 1 END) as active FROM strategies WHERE user_id = :user_id")
        api_keys_query = text("SELECT COUNT(*) as total, COUNT(CASE WHEN is_active = 1 THEN 1 END) as active FROM api_keys WHERE user_id = :user_id")
        trades_query = text("SELECT COUNT(*) FROM trades WHERE user_id = :user_id")
        backtests_query = text("SELECT COUNT(*) FROM backtests WHERE user_id = :user_id")
        
        strategies_result = await db.execute(strategies_query, {"user_id": user_id})
        api_keys_result = await db.execute(api_keys_query, {"user_id": user_id})
        trades_result = await db.execute(trades_query, {"user_id": user_id})
        backtests_result = await db.execute(backtests_query, {"user_id": user_id})
        
        strategies_row = strategies_result.first()
        api_keys_row = api_keys_result.first()
        trades_count = trades_result.scalar() or 0
        backtests_count = backtests_result.scalar() or 0
        
        # 构建360度用户信息格式的响应
        user_comprehensive_info = {
            "user": {
                "id": int(user_row.id),
                "username": str(user_row.username or ""),
                "email": str(user_row.email or ""),
                "membership_level": str(user_row.membership_level or "basic"),
                "membership_expires_at": expires_at_str,
                "is_active": bool(user_row.is_active),
                "email_verified": bool(user_row.email_verified),
                "phone": str(user_row.phone or "") if user_row.phone else None,
                "avatar_url": str(user_row.avatar_url or "") if user_row.avatar_url else None,
                "created_at": created_at_str,
                "last_login_at": last_login_str,
                "updated_at": created_at_str  # 使用created_at作为fallback
            },
            "statistics": {
                "total_strategies": strategies_row.total or 0,
                "active_strategies": strategies_row.active or 0,
                "total_trades": trades_count,
                "total_backtests": backtests_count,
                "total_api_keys": api_keys_row.total or 0,
                "active_api_keys": api_keys_row.active or 0,
                "total_ai_usages": 0  # 模拟数据
            },
            "latest_snapshot": None,  # 简化版本暂不处理快照
            "tags": [],  # 空标签数组
            "recent_activity": [],  # 空活动数组
            "behavior_profile": None  # 简化版本暂不处理行为档案
        }
        
        return {
            "success": True,
            "data": user_comprehensive_info
        }
        
    except Exception as e:
        logger.error(f"获取用户详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户详情失败: {str(e)}"
        )


@router.put("/users/{user_id}", summary="更新用户信息")
async def update_user(
    user_id: int,
    user_update: UserUpdateRequest,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """更新单个用户信息"""
    
    try:
        service = UserManagementService(db)
        
        # 准备更新数据
        update_data = {}
        for field, value in user_update.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段"
            )
        
        result = await service.batch_update_users(
            user_ids=[user_id],
            updates=update_data,
            updated_by=current_admin.id
        )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="UPDATE_USER",
            resource_type="user",
            resource_id=user_id,
            details=f'{{"updated_fields": {list(update_data.keys())}}}',
            result="success" if result['successful_count'] > 0 else "failed"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "success": True,
            "message": "用户更新成功" if result['successful_count'] > 0 else "用户更新失败",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"更新用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户失败: {str(e)}"
        )


# ========== 用户标签管理 ==========

@router.get("/users/tags/", summary="获取所有用户标签")
async def get_all_tags(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    tag_type: Optional[str] = Query(None, description="标签类型"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """获取所有用户标签列表"""
    
    try:
        from sqlalchemy import select, and_
        from app.models.user_management import UserTag
        
        # 构建查询条件
        conditions = []
        if tag_type:
            conditions.append(UserTag.tag_type == tag_type)
        if is_active is not None:
            conditions.append(UserTag.is_active == is_active)
        
        # 基础查询
        query = select(UserTag)
        count_query = select(func.count(UserTag.id))
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # 排序和分页
        query = query.order_by(UserTag.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        # 执行查询
        tags_result = await db.execute(query)
        count_result = await db.execute(count_query)
        
        tags = tags_result.scalars().all()
        total_count = count_result.scalar()
        
        # 格式化结果
        tags_data = []
        for tag in tags:
            tags_data.append({
                "id": tag.id,
                "name": tag.name,
                "display_name": tag.display_name,
                "description": tag.description,
                "color": tag.color,
                "tag_type": tag.tag_type.value,
                "is_active": tag.is_active,
                "user_count": tag.user_count,
                "auto_assign_rule": tag.auto_assign_rule,
                "created_by": tag.created_by,
                "created_at": tag.created_at.isoformat(),
                "updated_at": tag.updated_at.isoformat() if tag.updated_at else None
            })
        
        return {
            "success": True,
            "data": {
                "tags": tags_data,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取标签列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标签列表失败: {str(e)}"
        )


@router.post("/users/tags/", summary="创建用户标签")
async def create_user_tag(
    tag_create: UserTagCreate,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """创建新的用户标签"""
    
    try:
        service = UserManagementService(db)
        
        # 转换标签类型
        tag_type_enum = getattr(TagType, tag_create.tag_type.upper())
        
        result = await service.create_user_tag(
            name=tag_create.name,
            display_name=tag_create.display_name,
            description=tag_create.description,
            color=tag_create.color,
            tag_type=tag_type_enum,
            auto_assign_rule=tag_create.auto_assign_rule,
            created_by=current_admin.id
        )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="CREATE_USER_TAG",
            resource_type="user_tag",
            resource_id=result['id'],
            details=f'{{"tag_name": "{tag_create.name}"}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "success": True,
            "message": "标签创建成功",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"创建用户标签失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建标签失败: {str(e)}"
        )


@router.post("/users/tags/assign", summary="分配标签给用户")
async def assign_tag_to_user(
    assignment: TagAssignmentRequest,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """为用户分配标签"""
    
    try:
        service = UserManagementService(db)
        
        success = await service.assign_tag_to_user(
            user_id=assignment.user_id,
            tag_id=assignment.tag_id,
            assigned_by=current_admin.id,
            assigned_reason=assignment.assigned_reason,
            expires_at=assignment.expires_at
        )
        
        if success:
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="ASSIGN_USER_TAG",
                resource_type="user_tag_assignment",
                details=f'{{"user_id": {assignment.user_id}, "tag_id": {assignment.tag_id}}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            return {
                "success": True,
                "message": "标签分配成功"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标签分配失败，可能用户已拥有此标签"
            )
        
    except Exception as e:
        logger.error(f"分配用户标签失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分配标签失败: {str(e)}"
        )


@router.delete("/users/tags/assign", summary="移除用户标签")
async def remove_tag_from_user(
    user_id: int = Query(..., description="用户ID"),
    tag_id: int = Query(..., description="标签ID"),
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """移除用户标签"""
    
    try:
        service = UserManagementService(db)
        
        success = await service.remove_tag_from_user(user_id, tag_id)
        
        if success:
            # 记录操作日志
            log_entry = AdminOperationLog(
                admin_id=current_admin.id,
                operation="REMOVE_USER_TAG",
                resource_type="user_tag_assignment",
                details=f'{{"user_id": {user_id}, "tag_id": {tag_id}}}',
                result="success"
            )
            db.add(log_entry)
            await db.commit()
            
            return {
                "success": True,
                "message": "标签移除成功"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="标签移除失败，可能用户没有此标签"
            )
        
    except Exception as e:
        logger.error(f"移除用户标签失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除标签失败: {str(e)}"
        )


# ========== 批量操作 ==========

@router.post("/users/batch/update", summary="批量更新用户")
async def batch_update_users(
    batch_update: BatchUserUpdateRequest,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """批量更新用户信息"""
    
    try:
        service = UserManagementService(db)
        
        # 准备更新数据
        update_data = {}
        for field, value in batch_update.updates.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段"
            )
        
        result = await service.batch_update_users(
            user_ids=batch_update.user_ids,
            updates=update_data,
            updated_by=current_admin.id
        )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="BATCH_UPDATE_USERS",
            resource_type="user",
            details=f'{{"user_count": {len(batch_update.user_ids)}, "updated_fields": {list(update_data.keys())}}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "success": True,
            "message": f"批量更新完成: 成功 {result['successful_count']}, 失败 {result['failed_count']}",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"批量更新用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量更新失败: {str(e)}"
        )


@router.post("/users/batch/assign-tags", summary="批量分配标签")
async def batch_assign_tags(
    batch_assignment: BatchTagAssignmentRequest,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """批量为用户分配标签"""
    
    try:
        service = UserManagementService(db)
        
        result = await service.batch_assign_tags(
            user_ids=batch_assignment.user_ids,
            tag_ids=batch_assignment.tag_ids,
            assigned_by=current_admin.id,
            assigned_reason=batch_assignment.assigned_reason
        )
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="BATCH_ASSIGN_TAGS",
            resource_type="user_tag_assignment",
            details=f'{{"user_count": {len(batch_assignment.user_ids)}, "tag_count": {len(batch_assignment.tag_ids)}}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "success": True,
            "message": f"批量分配完成: 成功 {result['successful_count']}, 失败 {result['failed_count']}",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"批量分配标签失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量分配失败: {str(e)}"
        )


# ========== 用户活动和统计 ==========

@router.get("/users/{user_id}/activities", summary="获取用户活动日志")
async def get_user_activities(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    activity_type: Optional[str] = Query(None, description="活动类型"),
    date_from: Optional[datetime] = Query(None, description="开始时间"),
    date_to: Optional[datetime] = Query(None, description="结束时间"),
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """获取用户活动日志"""
    
    try:
        from sqlalchemy import select, and_, desc, func
        from app.models.user_management import UserActivityLog
        
        # 构建查询条件
        conditions = [UserActivityLog.user_id == user_id]
        
        if activity_type:
            conditions.append(UserActivityLog.activity_type == activity_type)
        if date_from:
            conditions.append(UserActivityLog.created_at >= date_from)
        if date_to:
            conditions.append(UserActivityLog.created_at <= date_to)
        
        # 查询活动日志
        query = select(UserActivityLog).where(and_(*conditions)).order_by(desc(UserActivityLog.created_at))
        count_query = select(func.count(UserActivityLog.id)).where(and_(*conditions))
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        # 执行查询
        activities_result = await db.execute(query)
        count_result = await db.execute(count_query)
        
        activities = activities_result.scalars().all()
        total_count = count_result.scalar()
        
        # 格式化结果
        activities_data = []
        for activity in activities:
            activities_data.append({
                "id": activity.id,
                "activity_type": activity.activity_type.value,
                "activity_description": activity.activity_description,
                "ip_address": activity.ip_address,
                "user_agent": activity.user_agent,
                "referer": activity.referer,
                "resource_type": activity.resource_type,
                "resource_id": activity.resource_id,
                "additional_data": activity.additional_data,
                "is_successful": activity.is_successful,
                "error_message": activity.error_message,
                "created_at": activity.created_at.isoformat()
            })
        
        return {
            "success": True,
            "data": {
                "activities": activities_data,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取用户活动日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取活动日志失败: {str(e)}"
        )


@router.post("/users/{user_id}/generate-snapshot", summary="生成用户统计快照")
async def generate_user_snapshot(
    user_id: int,
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """为用户生成统计快照"""
    
    try:
        service = UserManagementService(db)
        
        result = await service.generate_user_statistics_snapshot(user_id)
        
        # 记录操作日志
        log_entry = AdminOperationLog(
            admin_id=current_admin.id,
            operation="GENERATE_USER_SNAPSHOT",
            resource_type="user_statistics_snapshot",
            resource_id=result['id'],
            details=f'{{"user_id": {user_id}}}',
            result="success"
        )
        db.add(log_entry)
        await db.commit()
        
        return {
            "success": True,
            "message": "用户统计快照生成成功",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"生成用户统计快照失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成快照失败: {str(e)}"
        )


@router.get("/users/dashboard/stats", summary="用户管理仪表板统计")
async def get_dashboard_stats(
    current_admin=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
):
    """获取用户管理仪表板统计信息"""
    
    try:
        service = UserManagementService(db)
        
        stats = await service.get_user_management_dashboard_stats()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"获取仪表板统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计失败: {str(e)}"
        )