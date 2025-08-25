"""
简单管理员API - 用于前端Admin Dashboard
使用普通用户JWT token，检查admin@trademe.com权限后代理到高级用户管理API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.user_management_service import UserManagementService

router = APIRouter(prefix="/admin", tags=["简单管理员API"])


async def check_admin_permission(current_user=Depends(get_current_user)):
    """检查管理员权限 - 简单版本"""
    if not current_user or current_user.email != "admin@trademe.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


@router.get("/stats/system")
async def get_system_stats(
    current_user=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取系统统计信息 - 简化版本"""
    try:
        from sqlalchemy import select, func, case
        from app.models.user import User
        from datetime import datetime, timedelta
        
        # 使用单个复杂查询获取所有统计数据，避免多次数据库访问
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        query = select(
            func.count(User.id).label('total_users'),
            func.sum(case((User.is_active == True, 1), else_=0)).label('active_users'),
            func.sum(case((User.email_verified == True, 1), else_=0)).label('verified_users'),
            func.sum(case((User.membership_level == 'basic', 1), else_=0)).label('basic_users'),
            func.sum(case((User.membership_level == 'premium', 1), else_=0)).label('premium_users'),
            func.sum(case((User.membership_level == 'professional', 1), else_=0)).label('professional_users'),
            func.sum(case((User.created_at >= seven_days_ago, 1), else_=0)).label('new_users_7days')
        )
        
        result = await db.execute(query)
        stats_row = result.first()
        
        # 提取统计数据
        total_users = stats_row.total_users or 0
        active_users = stats_row.active_users or 0
        verified_users = stats_row.verified_users or 0
        basic_users = stats_row.basic_users or 0
        premium_users = stats_row.premium_users or 0
        professional_users = stats_row.professional_users or 0
        new_users_7days = stats_row.new_users_7days or 0
        
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
                "active_rate": f"{active_rate:.1f}%",
                "verification_rate": f"{verification_rate:.1f}%"
            }
        }
        
        return {
            "success": True,
            "data": system_stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统统计失败: {str(e)}"
        )


@router.get("/users")
async def get_recent_users(
    limit: int = 5,
    current_user=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取最近用户列表 - 简化版本（绕过datetime序列化问题）"""
    try:
        from sqlalchemy import select, text
        
        # 使用原始SQL查询，避免SQLAlchemy模型序列化问题
        query = text("""
            SELECT id, username, email, membership_level, is_active, email_verified, 
                   created_at, last_login_at 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT :limit
        """)
        
        result = await db.execute(query, {"limit": limit})
        user_rows = result.fetchall()
        
        # 手动转换数据，完全绕过模型序列化
        users = []
        for row in user_rows:
            try:
                # 安全的时间戳转换
                created_at_str = ""
                last_login_str = None
                
                if row.created_at:
                    try:
                        # 尝试作为时间戳处理
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
                    "id": str(row.id),
                    "username": str(row.username or ""),
                    "email": str(row.email or ""),
                    "membership_level": str(row.membership_level or "basic"),
                    "is_active": bool(row.is_active),
                    "email_verified": bool(row.email_verified),
                    "created_at": created_at_str,
                    "last_login_at": last_login_str
                })
            except Exception as row_error:
                print(f"处理用户行时出错: {row_error}")
                continue
        
        return {
            "success": True,
            "data": {
                "users": users,
                "pagination": {
                    "total": len(users),
                    "page": 1,
                    "page_size": limit,
                    "total_pages": 1
                }
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"获取用户列表失败: {str(e)}",
            "data": {"users": [], "pagination": {"total": 0, "page": 1, "page_size": limit, "total_pages": 0}}
        }


@router.get("/users/{user_id}/membership-stats")
async def get_user_membership_stats(
    user_id: str,
    current_user=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取用户详细信息和会员统计"""
    try:
        from sqlalchemy import select, text
        from datetime import datetime
        
        # 查询用户基本信息
        user_query = text("""
            SELECT id, username, email, membership_level, is_active, 
                   email_verified, created_at, last_login_at,
                   membership_expires_at
            FROM users 
            WHERE id = :user_id
        """)
        
        result = await db.execute(user_query, {"user_id": int(user_id)})
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
        
        # 查询用户的策略和API密钥统计（模拟数据）
        strategies_query = text("SELECT COUNT(*) as count FROM strategies WHERE user_id = :user_id AND is_active = 1")
        api_keys_query = text("SELECT COUNT(*) as count FROM api_keys WHERE user_id = :user_id AND is_active = 1")
        
        strategies_result = await db.execute(strategies_query, {"user_id": int(user_id)})
        api_keys_result = await db.execute(api_keys_query, {"user_id": int(user_id)})
        
        strategies_count = strategies_result.scalar() or 0
        api_keys_count = api_keys_result.scalar() or 0
        
        # 根据会员级别设置限制
        membership_level = user_row.membership_level or 'basic'
        limits = {
            'basic': {
                'name': '初级会员',
                'api_keys': 1,
                'ai_daily': 20,
                'tick_backtest': 0,
                'storage': 100,
                'indicators': 5,
                'strategies': 5,
                'live_trading': 1
            },
            'premium': {
                'name': '高级会员',
                'api_keys': 5,
                'ai_daily': 100,
                'tick_backtest': 30,
                'storage': 1000,
                'indicators': 20,
                'strategies': 20,
                'live_trading': 5
            },
            'professional': {
                'name': '专业会员',
                'api_keys': 10,
                'ai_daily': 200,
                'tick_backtest': 100,
                'storage': 5000,
                'indicators': 50,
                'strategies': 50,
                'live_trading': 10
            }
        }
        
        current_limits = limits.get(membership_level, limits['basic'])
        
        # 构建返回数据
        membership_stats = {
            "user": {
                "id": str(user_row.id),
                "username": str(user_row.username or ""),
                "email": str(user_row.email or ""),
                "membership_level": membership_level,
                "membership_name": current_limits['name'],
                "membership_expires_at": expires_at_str,
                "email_verified": bool(user_row.email_verified),
                "created_at": created_at_str
            },
            "limits": current_limits,
            "usage": {
                "api_keys_count": api_keys_count,
                "ai_usage_today": 5,  # 模拟数据
                "tick_backtest_today": 2,  # 模拟数据
                "storage_used": 50,  # 模拟数据
                "indicators_count": strategies_count,  # 使用策略数量作为指标数量
                "strategies_count": strategies_count,
                "live_trading_count": min(1, strategies_count)  # 模拟实盘数量
            }
        }
        
        return {
            "success": True,
            "data": membership_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户详情失败: {str(e)}"
        )


@router.get("/analytics/membership")
async def get_membership_analytics(
    current_user=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取会员分析数据"""
    try:
        from sqlalchemy import select, func, case, text
        from datetime import datetime, timedelta
        
        # 会员分布统计
        membership_query = select(
            func.sum(case((User.membership_level == 'basic', 1), else_=0)).label('basic_count'),
            func.sum(case((User.membership_level == 'premium', 1), else_=0)).label('premium_count'),
            func.sum(case((User.membership_level == 'professional', 1), else_=0)).label('professional_count'),
        )
        result = await db.execute(membership_query)
        stats = result.first()
        
        # 即将到期的会员（模拟数据）
        thirty_days_later = datetime.utcnow() + timedelta(days=30)
        expiring_query = text("""
            SELECT id, username, email, membership_level, membership_expires_at
            FROM users 
            WHERE membership_expires_at IS NOT NULL 
            AND membership_expires_at < :thirty_days_later
            AND membership_level != 'basic'
            ORDER BY membership_expires_at ASC 
            LIMIT 10
        """)
        
        expiring_result = await db.execute(expiring_query, {"thirty_days_later": thirty_days_later.timestamp() * 1000})
        expiring_rows = expiring_result.fetchall()
        
        expiring_users = []
        for row in expiring_rows:
            try:
                expires_timestamp = int(row.membership_expires_at) / 1000 if row.membership_expires_at > 1000000000000 else int(row.membership_expires_at)
                expires_date = datetime.fromtimestamp(expires_timestamp)
                days_remaining = (expires_date - datetime.utcnow()).days
                
                expiring_users.append({
                    "id": str(row.id),
                    "username": str(row.username or ""),
                    "email": str(row.email or ""),
                    "membership_level": str(row.membership_level or "basic"),
                    "expires_at": expires_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "days_remaining": max(0, days_remaining)
                })
            except:
                continue
        
        # 构建分析数据
        analytics_data = {
            "membership_distribution": [
                {"level": "basic", "count": stats.basic_count or 0},
                {"level": "premium", "count": stats.premium_count or 0},
                {"level": "professional", "count": stats.professional_count or 0}
            ],
            "revenue": {
                "monthly_revenue": (stats.premium_count or 0) * 99 + (stats.professional_count or 0) * 199,
                "yearly_revenue": (stats.premium_count or 0) * 99 * 12 + (stats.professional_count or 0) * 199 * 12,
                "active_subscriptions": (stats.premium_count or 0) + (stats.professional_count or 0)
            },
            "expiring_soon": expiring_users
        }
        
        return {
            "success": True,
            "data": analytics_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会员分析失败: {str(e)}"
        )


@router.post("/users/batch")
async def batch_update_users(
    request_data: dict,
    current_user=Depends(check_admin_permission),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """批量用户操作"""
    try:
        action = request_data.get('action')
        user_ids = request_data.get('user_ids', [])
        data = request_data.get('data', {})
        
        if not action or not user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少操作类型或用户ID列表"
            )
        
        from sqlalchemy import text
        
        success_count = 0
        failed_count = 0
        
        for user_id in user_ids:
            try:
                if action == 'activate':
                    query = text("UPDATE users SET is_active = 1 WHERE id = :user_id")
                    await db.execute(query, {"user_id": int(user_id)})
                elif action == 'deactivate':
                    query = text("UPDATE users SET is_active = 0 WHERE id = :user_id")
                    await db.execute(query, {"user_id": int(user_id)})
                elif action == 'upgrade_membership':
                    new_level = data.get('membership_level', 'basic')
                    query = text("UPDATE users SET membership_level = :level WHERE id = :user_id")
                    await db.execute(query, {"level": new_level, "user_id": int(user_id)})
                elif action == 'verify_email':
                    query = text("UPDATE users SET email_verified = 1 WHERE id = :user_id")
                    await db.execute(query, {"user_id": int(user_id)})
                else:
                    failed_count += 1
                    continue
                
                success_count += 1
            except:
                failed_count += 1
                continue
        
        await db.commit()
        
        return {
            "success": True,
            "data": {
                "total": len(user_ids),
                "success": success_count,
                "failed": failed_count,
                "message": f"批量操作完成：成功 {success_count} 个，失败 {failed_count} 个"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量操作失败: {str(e)}"
        )