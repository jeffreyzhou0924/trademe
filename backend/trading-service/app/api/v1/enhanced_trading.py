"""
增强版实盘交易API接口
提供完整的市价单、限价单、止损单、持仓管理等功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_active_user
from app.schemas.user import UserInDB
from app.database import get_db
from app.services.enhanced_exchange_service import (
    enhanced_exchange_service,
    OrderType,
    OrderSide,
    OrderStatus,
    Position
)
from loguru import logger


router = APIRouter(prefix="/trading/v2", tags=["Enhanced Trading"])


# ==================== 请求/响应模型 ====================

class MarketOrderRequest(BaseModel):
    """市价单请求"""
    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对，如BTC/USDT")
    side: str = Field(..., description="买卖方向: buy/sell")
    quantity: float = Field(..., gt=0, description="交易数量")
    strategy_id: Optional[int] = Field(None, description="策略ID")


class LimitOrderRequest(BaseModel):
    """限价单请求"""
    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    side: str = Field(..., description="买卖方向: buy/sell")
    quantity: float = Field(..., gt=0, description="交易数量")
    price: float = Field(..., gt=0, description="限价")
    strategy_id: Optional[int] = Field(None, description="策略ID")
    time_in_force: str = Field("GTC", description="订单有效期: GTC/IOC/FOK")
    post_only: bool = Field(False, description="只做Maker")


class StopOrderRequest(BaseModel):
    """止损单请求"""
    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    side: str = Field(..., description="买卖方向: buy/sell")
    quantity: float = Field(..., gt=0, description="交易数量")
    stop_price: float = Field(..., gt=0, description="触发价格")
    limit_price: Optional[float] = Field(None, description="限价（止损限价单）")
    strategy_id: Optional[int] = Field(None, description="策略ID")


class BatchOrderRequest(BaseModel):
    """批量订单请求"""
    orders: List[Dict[str, Any]] = Field(..., description="订单列表")
    execute_parallel: bool = Field(False, description="是否并行执行")


# ==================== 订单执行API ====================

@router.post("/orders/market", summary="执行市价单")
async def place_market_order(
    request: MarketOrderRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    执行市价单
    
    - **exchange**: 交易所名称 (binance, okx, bybit等)
    - **symbol**: 交易对 (BTC/USDT, ETH/USDT等)
    - **side**: 买卖方向 (buy或sell)
    - **quantity**: 交易数量
    - **strategy_id**: 关联的策略ID（可选）
    
    返回订单执行结果，包括订单ID、成交价格、手续费等信息
    """
    try:
        logger.info(f"用户{current_user.id}执行市价单: {request.symbol} {request.side} {request.quantity}")
        
        result = await enhanced_exchange_service.place_market_order(
            user_id=current_user.id,
            exchange_name=request.exchange,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            db=db,
            strategy_id=request.strategy_id
        )
        
        if not result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=result.get('error', '市价单执行失败')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"市价单执行错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"市价单执行失败: {str(e)}")


@router.post("/orders/limit", summary="执行限价单")
async def place_limit_order(
    request: LimitOrderRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    执行限价单
    
    支持高级参数：
    - **time_in_force**: GTC(一直有效)、IOC(立即成交或取消)、FOK(全部成交或取消)
    - **post_only**: 只做Maker，避免吃单手续费
    """
    try:
        logger.info(f"用户{current_user.id}执行限价单: {request.symbol} {request.side} {request.quantity}@{request.price}")
        
        result = await enhanced_exchange_service.place_limit_order(
            user_id=current_user.id,
            exchange_name=request.exchange,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            db=db,
            strategy_id=request.strategy_id,
            time_in_force=request.time_in_force,
            post_only=request.post_only
        )
        
        if not result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=result.get('error', '限价单执行失败')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"限价单执行错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"限价单执行失败: {str(e)}")


@router.post("/orders/stop", summary="执行止损单")
async def place_stop_order(
    request: StopOrderRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    执行止损单
    
    - **stop_price**: 触发价格
    - **limit_price**: 可选，设置后变为止损限价单
    
    注意：不是所有交易所都支持止损单
    """
    try:
        logger.info(f"用户{current_user.id}执行止损单: {request.symbol} 触发价={request.stop_price}")
        
        result = await enhanced_exchange_service.place_stop_order(
            user_id=current_user.id,
            exchange_name=request.exchange,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            stop_price=request.stop_price,
            limit_price=request.limit_price,
            db=db,
            strategy_id=request.strategy_id
        )
        
        if not result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=result.get('error', '止损单执行失败')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"止损单执行错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"止损单执行失败: {str(e)}")


@router.post("/orders/batch", summary="批量下单")
async def place_batch_orders(
    request: BatchOrderRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量执行订单
    
    支持同时执行多个订单，可选择串行或并行执行
    """
    try:
        results = []
        errors = []
        
        for order_data in request.orders:
            try:
                order_type = order_data.get('type', 'market')
                
                if order_type == 'market':
                    result = await enhanced_exchange_service.place_market_order(
                        user_id=current_user.id,
                        exchange_name=order_data['exchange'],
                        symbol=order_data['symbol'],
                        side=order_data['side'],
                        quantity=order_data['quantity'],
                        db=db
                    )
                elif order_type == 'limit':
                    result = await enhanced_exchange_service.place_limit_order(
                        user_id=current_user.id,
                        exchange_name=order_data['exchange'],
                        symbol=order_data['symbol'],
                        side=order_data['side'],
                        quantity=order_data['quantity'],
                        price=order_data['price'],
                        db=db
                    )
                else:
                    result = {'success': False, 'error': f'不支持的订单类型: {order_type}'}
                
                results.append(result)
                
            except Exception as e:
                errors.append({
                    'order': order_data,
                    'error': str(e)
                })
        
        return {
            'success': len(errors) == 0,
            'total': len(request.orders),
            'successful': len(results),
            'failed': len(errors),
            'results': results,
            'errors': errors
        }
        
    except Exception as e:
        logger.error(f"批量下单错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量下单失败: {str(e)}")


# ==================== 订单管理API ====================

@router.delete("/orders/{order_id}", summary="取消订单")
async def cancel_order(
    order_id: str,
    exchange: str = Query(..., description="交易所名称"),
    symbol: str = Query(..., description="交易对"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """取消指定订单"""
    try:
        result = await enhanced_exchange_service.cancel_order(
            user_id=current_user.id,
            exchange_name=exchange,
            order_id=order_id,
            symbol=symbol,
            db=db
        )
        
        if not result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=result.get('error', '取消订单失败')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消订单错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取消订单失败: {str(e)}")


@router.delete("/orders", summary="取消所有订单")
async def cancel_all_orders(
    exchange: str = Query(..., description="交易所名称"),
    symbol: Optional[str] = Query(None, description="交易对，不填则取消所有"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """取消所有开放订单"""
    try:
        result = await enhanced_exchange_service.cancel_all_orders(
            user_id=current_user.id,
            exchange_name=exchange,
            symbol=symbol,
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"批量取消订单错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量取消订单失败: {str(e)}")


@router.get("/orders/{order_id}/status", summary="查询订单状态")
async def get_order_status(
    order_id: str,
    exchange: str = Query(..., description="交易所名称"),
    symbol: str = Query(..., description="交易对"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """查询订单当前状态"""
    try:
        result = await enhanced_exchange_service.get_order_status(
            user_id=current_user.id,
            exchange_name=exchange,
            order_id=order_id,
            symbol=symbol,
            db=db
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询订单状态错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询订单状态失败: {str(e)}")


@router.get("/orders/open", summary="获取开放订单")
async def get_open_orders(
    exchange: str = Query(..., description="交易所名称"),
    symbol: Optional[str] = Query(None, description="交易对"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有开放订单"""
    try:
        orders = await enhanced_exchange_service.get_open_orders(
            user_id=current_user.id,
            exchange_name=exchange,
            symbol=symbol,
            db=db
        )
        
        return {
            'success': True,
            'count': len(orders),
            'orders': orders
        }
        
    except Exception as e:
        logger.error(f"获取开放订单错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取开放订单失败: {str(e)}")


@router.get("/orders/history", summary="获取历史订单")
async def get_order_history(
    exchange: str = Query(..., description="交易所名称"),
    symbol: Optional[str] = Query(None, description="交易对"),
    days: int = Query(7, ge=1, le=90, description="查询天数"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取历史订单记录"""
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        orders = await enhanced_exchange_service.get_order_history(
            user_id=current_user.id,
            exchange_name=exchange,
            symbol=symbol,
            since=since,
            limit=limit,
            db=db
        )
        
        return {
            'success': True,
            'count': len(orders),
            'orders': orders,
            'period': f"最近{days}天"
        }
        
    except Exception as e:
        logger.error(f"获取历史订单错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史订单失败: {str(e)}")


# ==================== 持仓管理API ====================

@router.get("/positions", summary="获取持仓信息")
async def get_positions(
    exchange: str = Query(..., description="交易所名称"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    同步并获取最新持仓信息
    
    返回所有活跃持仓，包括：
    - 持仓数量
    - 平均成本
    - 当前价格
    - 未实现盈亏
    - 已实现盈亏
    """
    try:
        positions = await enhanced_exchange_service.sync_positions(
            user_id=current_user.id,
            exchange_name=exchange,
            db=db
        )
        
        # 转换为字典格式
        positions_data = []
        for pos in positions:
            positions_data.append({
                'symbol': pos.symbol,
                'side': pos.side,
                'quantity': pos.quantity,
                'average_price': pos.average_price,
                'current_price': pos.current_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl,
                'margin_used': pos.margin_used,
                'liquidation_price': pos.liquidation_price,
                'timestamp': pos.timestamp.isoformat()
            })
        
        return {
            'success': True,
            'exchange': exchange,
            'count': len(positions_data),
            'positions': positions_data,
            'total_unrealized_pnl': sum(p['unrealized_pnl'] for p in positions_data),
            'total_realized_pnl': sum(p['realized_pnl'] for p in positions_data)
        }
        
    except Exception as e:
        logger.error(f"获取持仓信息错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取持仓信息失败: {str(e)}")


@router.get("/positions/{symbol}", summary="获取特定持仓")
async def get_position(
    symbol: str,
    exchange: str = Query(..., description="交易所名称"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取特定交易对的持仓信息"""
    try:
        position = await enhanced_exchange_service.get_position(
            user_id=current_user.id,
            exchange_name=exchange,
            symbol=symbol,
            db=db
        )
        
        if not position:
            raise HTTPException(status_code=404, detail=f"没有找到{symbol}的持仓")
        
        return {
            'success': True,
            'position': {
                'symbol': position.symbol,
                'side': position.side,
                'quantity': position.quantity,
                'average_price': position.average_price,
                'current_price': position.current_price,
                'unrealized_pnl': position.unrealized_pnl,
                'realized_pnl': position.realized_pnl,
                'margin_used': position.margin_used,
                'liquidation_price': position.liquidation_price,
                'timestamp': position.timestamp.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取持仓信息错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取持仓信息失败: {str(e)}")


@router.post("/positions/{symbol}/close", summary="平仓")
async def close_position(
    symbol: str,
    exchange: str = Query(..., description="交易所名称"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    平掉指定持仓
    
    自动计算需要的反向订单并执行市价平仓
    """
    try:
        result = await enhanced_exchange_service.close_position(
            user_id=current_user.id,
            exchange_name=exchange,
            symbol=symbol,
            db=db
        )
        
        if not result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=result.get('error', '平仓失败')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"平仓错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"平仓失败: {str(e)}")


# ==================== 账户信息API ====================

@router.get("/account/info", summary="获取账户综合信息")
async def get_account_info(
    exchange: str = Query(..., description="交易所名称"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取账户综合信息
    
    包括：
    - 账户余额
    - 持仓信息
    - 总资产价值
    - 盈亏统计
    """
    try:
        account_info = await enhanced_exchange_service.get_account_info(
            user_id=current_user.id,
            exchange_name=exchange,
            db=db
        )
        
        if not account_info:
            raise HTTPException(status_code=404, detail="无法获取账户信息")
        
        return account_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取账户信息错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取账户信息失败: {str(e)}")


@router.get("/account/balance", summary="获取账户余额")
async def get_account_balance(
    exchange: str = Query(..., description="交易所名称"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账户余额详情"""
    try:
        from app.services.exchange_service import exchange_service
        
        balance = await exchange_service.get_account_balance(
            user_id=current_user.id,
            exchange_name=exchange,
            db=db
        )
        
        if not balance:
            raise HTTPException(status_code=404, detail="无法获取账户余额")
        
        return balance
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取账户余额错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取账户余额失败: {str(e)}")


# ==================== 风险管理API ====================

@router.post("/risk/check", summary="风险检查")
async def check_order_risk(
    order_type: str = Body(..., description="订单类型: market/limit"),
    exchange: str = Body(..., description="交易所名称"),
    symbol: str = Body(..., description="交易对"),
    side: str = Body(..., description="买卖方向"),
    quantity: float = Body(..., gt=0, description="交易数量"),
    price: Optional[float] = Body(None, description="价格（限价单）"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    订单风险预检查
    
    在下单前检查风险，返回：
    - 风险等级
    - 风险评分
    - 警告信息
    - 建议仓位
    """
    try:
        # 获取账户余额
        from app.services.exchange_service import exchange_service
        
        balance_info = await exchange_service.get_account_balance(
            user_id=current_user.id,
            exchange_name=exchange,
            db=db
        )
        
        account_balance = {}
        if balance_info:
            account_balance = {
                currency: bal.get('free', 0)
                for currency, bal in balance_info.get('balances', {}).items()
            }
        
        # 执行风险检查
        from app.core.risk_manager import risk_manager
        
        assessment = await risk_manager.validate_order(
            user_id=current_user.id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            account_balance=account_balance,
            db=db
        )
        
        return {
            'approved': assessment.approved,
            'risk_level': assessment.risk_level.value,
            'risk_score': assessment.risk_score,
            'violations': assessment.violations,
            'warnings': assessment.warnings,
            'suggested_position_size': assessment.suggested_position_size,
            'max_position_size': assessment.max_position_size
        }
        
    except Exception as e:
        logger.error(f"风险检查错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"风险检查失败: {str(e)}")


# ==================== 系统状态API ====================

@router.get("/system/status", summary="获取系统状态")
async def get_system_status(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """获取交易系统状态"""
    try:
        return {
            'status': 'operational',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0',
            'features': {
                'market_order': True,
                'limit_order': True,
                'stop_order': True,
                'position_tracking': True,
                'risk_management': True,
                'batch_orders': True
            },
            'supported_exchanges': [
                'binance', 'okx', 'bybit', 'huobi', 
                'bitget', 'coinbase', 'kucoin', 'mexc'
            ]
        }
        
    except Exception as e:
        logger.error(f"获取系统状态错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")