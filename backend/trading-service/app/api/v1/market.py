"""
Trademe Trading Service - 市场数据API

提供实时行情、K线数据、技术指标等市场数据服务
"""

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import json

from app.database import get_db
from app.services.market_service import MarketService, market_service
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/symbols")
async def get_supported_symbols(
    exchange: Optional[str] = Query(None, description="交易所筛选")
):
    """获取支持的交易对列表"""
    try:
        symbols = await MarketService.get_supported_symbols(exchange)
        return {"symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易对失败: {str(e)}")


@router.get("/exchanges")
async def get_supported_exchanges():
    """获取支持的交易所列表"""
    try:
        exchanges = await MarketService.get_supported_exchanges()
        return {"exchanges": exchanges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易所失败: {str(e)}")


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    exchange: str = Query("okx", description="交易所")
):
    """获取实时ticker数据"""
    try:
        ticker = await MarketService.get_ticker(exchange, symbol)
        return ticker
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取ticker失败: {str(e)}")


@router.get("/klines/{symbol}")
async def get_klines(
    symbol: str,
    timeframe: str = Query("1h", description="时间周期"),
    exchange: str = Query("okx", description="交易所"),
    limit: int = Query(100, ge=1, le=1000, description="K线数量"),
    since: Optional[int] = Query(None, description="开始时间戳")
):
    """获取K线数据"""
    try:
        klines = await MarketService.get_klines(
            exchange, symbol, timeframe, limit=limit, since=since
        )
        return {"klines": klines}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取K线数据失败: {str(e)}")


@router.get("/depth/{symbol}")
async def get_order_book(
    symbol: str,
    exchange: str = Query("binance", description="交易所"),
    limit: int = Query(20, ge=5, le=100, description="深度档位")
):
    """获取订单簿深度"""
    try:
        depth = await MarketService.get_order_book(exchange, symbol, limit)
        return depth
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取订单簿失败: {str(e)}")


@router.get("/indicators/{symbol}")
async def get_technical_indicators(
    symbol: str,
    timeframe: str = Query("1h", description="时间周期"),
    exchange: str = Query("binance", description="交易所"),
    indicators: str = Query("sma,ema,rsi,macd", description="指标列表,逗号分隔")
):
    """获取技术指标"""
    try:
        indicator_list = [ind.strip() for ind in indicators.split(",")]
        result = await MarketService.calculate_indicators(
            exchange, symbol, timeframe, indicator_list
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算技术指标失败: {str(e)}")


@router.websocket("/ws/{symbol}")
async def websocket_market_data(
    websocket: WebSocket,
    symbol: str,
    exchange: str = Query("okx", description="交易所")
):
    """WebSocket实时市场数据"""
    await websocket.accept()
    
    try:
        # 订阅实时数据
        async for data in market_service.subscribe_realtime_data(exchange, symbol):
            await websocket.send_text(json.dumps(data))
    except Exception as e:
        await websocket.send_text(json.dumps({"error": str(e)}))
    finally:
        await websocket.close()


@router.get("/stats/{symbol}")
async def get_market_stats(
    symbol: str,
    exchange: str = Query("binance", description="交易所"),
    period: int = Query(24, description="统计周期(小时)")
):
    """获取市场统计数据"""
    try:
        stats = await MarketService.get_market_stats(exchange, symbol, period)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取市场统计失败: {str(e)}")


@router.post("/watchlist")
async def add_to_watchlist(
    symbols: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """添加到自选列表"""
    try:
        result = await MarketService.add_to_watchlist(db, current_user.id, symbols)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加自选失败: {str(e)}")


@router.get("/watchlist")
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取自选列表"""
    try:
        watchlist = await MarketService.get_user_watchlist(db, current_user.id)
        return {"watchlist": watchlist}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取自选列表失败: {str(e)}")


@router.post("/realtime/start")
async def start_realtime_data(
    symbols: List[str],
    data_types: List[str] = Query(["kline", "tick"], description="数据类型"),
    timeframes: List[str] = Query(["1m"], description="时间周期"),
    current_user: User = Depends(get_current_user)
):
    """启动实时数据采集"""
    try:
        success = await market_service.start_real_time_data(
            symbols=symbols,
            data_types=data_types,
            timeframes=timeframes
        )
        
        if success:
            return {
                "message": "实时数据采集已启动",
                "symbols": symbols,
                "data_types": data_types,
                "timeframes": timeframes
            }
        else:
            raise HTTPException(status_code=500, detail="启动实时数据采集失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动实时数据采集失败: {str(e)}")


@router.post("/realtime/stop")
async def stop_realtime_data(
    symbols: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user)
):
    """停止实时数据采集"""
    try:
        success = await market_service.stop_real_time_data(symbols=symbols)
        
        if success:
            return {
                "message": "实时数据采集已停止",
                "symbols": symbols or "all"
            }
        else:
            raise HTTPException(status_code=500, detail="停止实时数据采集失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止实时数据采集失败: {str(e)}")


@router.get("/realtime/status")
async def get_realtime_data_status(
    current_user: User = Depends(get_current_user)
):
    """获取实时数据采集状态"""
    try:
        status = market_service.get_connection_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.get("/symbol/{symbol}/info")
async def get_symbol_info(
    symbol: str,
    exchange: str = Query("okx", description="交易所")
):
    """获取交易对详细信息"""
    try:
        info = await MarketService.get_symbol_info(symbol, exchange)
        
        if info is None:
            raise HTTPException(status_code=404, detail="交易对不存在")
        
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易对信息失败: {str(e)}")


@router.get("/historical/{symbol}")
async def get_historical_klines(
    symbol: str,
    timeframe: str = Query("1h", description="时间周期"),
    exchange: str = Query("okx", description="交易所"),
    limit: int = Query(100, ge=1, le=1000, description="数据量"),
    start_time: Optional[int] = Query(None, description="开始时间戳(毫秒)"),
    end_time: Optional[int] = Query(None, description="结束时间戳(毫秒)")
):
    """获取历史K线数据"""
    try:
        from datetime import datetime
        
        start_dt = None
        end_dt = None
        
        if start_time:
            start_dt = datetime.fromtimestamp(start_time / 1000)
        if end_time:
            end_dt = datetime.fromtimestamp(end_time / 1000)
        
        klines = await MarketService.get_historical_klines(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start_time=start_dt,
            end_time=end_dt
        )
        
        # 转换为标准格式
        result = []
        for kline in klines:
            result.append({
                "timestamp": int(kline.timestamp.timestamp() * 1000),
                "open": kline.open,
                "high": kline.high,
                "low": kline.low,
                "close": kline.close,
                "volume": kline.volume
            })
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": result,
            "count": len(result)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史数据失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_market_data(
    days_to_keep: int = Query(30, ge=1, le=365, description="保留天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清理旧的市场数据"""
    try:
        deleted_count = await MarketService.cleanup_old_data(db, days_to_keep)
        
        return {
            "message": f"清理完成，删除了{deleted_count}条旧数据",
            "deleted_count": deleted_count,
            "days_kept": days_to_keep
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理数据失败: {str(e)}")