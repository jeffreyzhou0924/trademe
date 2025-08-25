"""
交易所管理API

提供交易所连接、账户信息、交易操作等功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.schemas.exchange import (
    ExchangeInfo, AccountBalance, OrderCreate, OrderResponse,
    OrderStatus, MarketDataRequest, MarketDataResponse,
    ExchangeSymbols, TradingFees
)
from app.services.exchange_service import exchange_service
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/supported", response_model=List[ExchangeInfo])
async def get_supported_exchanges():
    """获取支持的交易所列表"""
    exchanges = []
    for name in exchange_service.SUPPORTED_EXCHANGES.keys():
        exchanges.append(ExchangeInfo(
            name=name,
            display_name=name.upper(),
            supported=True,
            features={
                "spot_trading": True,
                "futures_trading": name in ['binance', 'okx', 'bybit'],
                "margin_trading": name in ['binance', 'okx'],
                "options_trading": name in ['okx']
            }
        ))
    
    return exchanges


@router.get("/{exchange_name}/symbols", response_model=ExchangeSymbols)
async def get_exchange_symbols(
    exchange_name: str,
    search: Optional[str] = Query(None, description="搜索交易对"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制")
):
    """获取交易所支持的交易对"""
    try:
        symbols = await exchange_service.get_symbols(exchange_name)
        
        # 搜索过滤
        if search:
            search_upper = search.upper()
            symbols = [s for s in symbols if search_upper in s.upper()]
        
        # 限制数量
        symbols = symbols[:limit]
        
        return ExchangeSymbols(
            exchange=exchange_name,
            symbols=symbols,
            total=len(symbols)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易对失败: {str(e)}")


@router.get("/{exchange_name}/balance", response_model=AccountBalance)
async def get_account_balance(
    exchange_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账户余额"""
    try:
        balance = await exchange_service.get_account_balance(
            current_user.id, exchange_name, db
        )
        
        if not balance:
            raise HTTPException(
                status_code=404, 
                detail=f"无法获取 {exchange_name} 账户信息，请检查API密钥配置"
            )
        
        return AccountBalance(**balance)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取账户余额失败: {str(e)}")


@router.get("/{exchange_name}/market-data", response_model=MarketDataResponse)
async def get_market_data(
    exchange_name: str,
    symbol: str = Query(..., description="交易对，如 BTC/USDT"),
    timeframe: str = Query("1h", description="时间周期"),
    limit: int = Query(100, ge=1, le=1000, description="K线数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取市场数据（K线）"""
    try:
        market_data = await exchange_service.get_market_data(
            current_user.id, exchange_name, symbol, timeframe, limit, db
        )
        
        if not market_data:
            raise HTTPException(
                status_code=404,
                detail=f"无法获取 {symbol} 的市场数据"
            )
        
        return MarketDataResponse(
            exchange=exchange_name,
            symbol=symbol,
            timeframe=timeframe,
            data=market_data,
            count=len(market_data)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取市场数据失败: {str(e)}")


@router.post("/{exchange_name}/orders", response_model=OrderResponse)
async def create_order(
    exchange_name: str,
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建订单"""
    try:
        # 基础验证
        if order_data.type.lower() == 'limit' and not order_data.price:
            raise HTTPException(status_code=422, detail="限价单必须指定价格")
        
        if order_data.amount <= 0:
            raise HTTPException(status_code=422, detail="订单数量必须大于0")
        
        order = await exchange_service.place_order(
            user_id=current_user.id,
            exchange_name=exchange_name,
            symbol=order_data.symbol,
            order_type=order_data.type,
            side=order_data.side,
            amount=order_data.amount,
            price=order_data.price,
            db=db
        )
        
        if not order:
            raise HTTPException(
                status_code=400,
                detail="订单创建失败，请检查参数和账户余额"
            )
        
        return OrderResponse(**order)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建订单失败: {str(e)}")


@router.get("/{exchange_name}/orders/{order_id}", response_model=OrderStatus)
async def get_order_status(
    exchange_name: str,
    order_id: str,
    symbol: str = Query(..., description="交易对"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询订单状态"""
    try:
        order = await exchange_service.get_order_status(
            current_user.id, exchange_name, order_id, symbol, db
        )
        
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        
        return OrderStatus(**order)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询订单失败: {str(e)}")


@router.delete("/{exchange_name}/orders/{order_id}")
async def cancel_order(
    exchange_name: str,
    order_id: str,
    symbol: str = Query(..., description="交易对"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消订单"""
    try:
        success = await exchange_service.cancel_order(
            current_user.id, exchange_name, order_id, symbol, db
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="取消订单失败")
        
        return {"message": "订单已取消", "order_id": order_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消订单失败: {str(e)}")


@router.get("/{exchange_name}/fees", response_model=TradingFees)
async def get_trading_fees(
    exchange_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取交易手续费"""
    try:
        fees = await exchange_service.get_trading_fees(
            current_user.id, exchange_name, db
        )
        
        if not fees:
            raise HTTPException(
                status_code=404,
                detail=f"无法获取 {exchange_name} 手续费信息"
            )
        
        return TradingFees(**fees)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取手续费失败: {str(e)}")


@router.post("/{exchange_name}/test-connection")
async def test_exchange_connection(
    exchange_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """测试交易所连接"""
    try:
        exchange = await exchange_service.get_exchange(
            current_user.id, exchange_name, db
        )
        
        if exchange:
            return {
                "success": True,
                "message": f"{exchange_name} 连接测试成功",
                "exchange": exchange_name
            }
        else:
            return {
                "success": False,
                "message": f"{exchange_name} 连接失败，请检查API密钥配置",
                "exchange": exchange_name
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接测试失败: {str(e)}",
            "exchange": exchange_name
        }