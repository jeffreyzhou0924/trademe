"""
市场数据API
提供真实K线数据，替代前端Mock数据
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.services.okx_market_data_service import okx_market_service
from app.utils.data_validation import DataValidator
from app.middleware.auth import get_current_user
from app.models.user import User

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/klines/{symbol:path}")
async def get_klines(
    symbol: str,
    timeframe: str = Query("1h", description="时间周期 (1m,5m,15m,30m,1h,2h,4h,1d,1w)"),
    limit: int = Query(100, ge=1, le=1000, description="数据条数 (1-1000)"),
    use_cache: bool = Query(True, description="是否使用缓存"),
    current_user: User = Depends(get_current_user)
):
    """
    获取K线数据
    
    支持的交易对: BTC/USDT, ETH/USDT, SOL/USDT, ADA/USDT, DOT/USDT, LINK/USDT, MATIC/USDT, AVAX/USDT
    支持的时间周期: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w
    """
    try:
        # 验证交易对格式
        if "/" not in symbol:
            raise HTTPException(status_code=400, detail="交易对格式错误，应为 BASE/QUOTE 格式")
        
        symbol_upper = symbol.upper()
        
        # 获取K线数据
        result = await okx_market_service.get_klines(
            symbol=symbol_upper,
            timeframe=timeframe,
            limit=limit,
            use_cache=use_cache
        )
        
        logger.info(f"📊 用户 {current_user.id} 获取K线: {symbol_upper} {timeframe} ({result['count']}条)")
        
        return {
            "success": True,
            "data": result,
            "message": f"获取 {symbol_upper} {timeframe} K线数据成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取K线数据失败: {symbol} {timeframe} - {e}")
        raise HTTPException(status_code=500, detail=f"获取K线数据失败: {str(e)}")


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取实时价格数据
    
    返回指定交易对的实时价格、24小时涨跌幅、成交量等信息
    """
    try:
        symbol_upper = symbol.upper()
        
        result = await okx_market_service.get_ticker(symbol_upper)
        
        # 使用安全的价格格式化
        safe_price = DataValidator.safe_format_price(result['price'])
        logger.info(f"💰 用户 {current_user.id} 获取价格: {symbol_upper} {safe_price}")
        
        return {
            "success": True,
            "data": result,
            "message": f"获取 {symbol_upper} 价格数据成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取价格数据失败: {symbol} - {e}")
        raise HTTPException(status_code=500, detail=f"获取价格数据失败: {str(e)}")


@router.get("/tickers")
async def get_multiple_tickers(
    symbols: str = Query(..., description="交易对列表，逗号分隔 (例: BTC/USDT,ETH/USDT)"),
    current_user: User = Depends(get_current_user)
):
    """
    批量获取多个交易对的价格数据
    
    高效获取多个交易对的实时价格信息，支持并发请求
    """
    try:
        # 解析交易对列表
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
        if len(symbol_list) > 20:
            raise HTTPException(status_code=400, detail="最多支持20个交易对")
        
        # 批量获取数据
        results = await okx_market_service.get_multiple_tickers(symbol_list)
        
        logger.info(f"💰 用户 {current_user.id} 批量获取价格: {len(results)} 个交易对")
        
        return {
            "success": True,
            "data": results,
            "count": len(results),
            "message": f"批量获取 {len(results)} 个交易对价格成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 批量获取价格失败: {symbols} - {e}")
        raise HTTPException(status_code=500, detail=f"批量获取价格失败: {str(e)}")


@router.get("/symbol-info/{symbol}")
async def get_symbol_info(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取交易对详细信息
    
    包括最小交易量、价格精度、交易状态等信息
    """
    try:
        symbol_upper = symbol.upper()
        
        result = await okx_market_service.get_symbol_info(symbol_upper)
        
        logger.info(f"ℹ️ 用户 {current_user.id} 获取交易对信息: {symbol_upper}")
        
        return {
            "success": True,
            "data": result,
            "message": f"获取 {symbol_upper} 交易对信息成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取交易对信息失败: {symbol} - {e}")
        raise HTTPException(status_code=500, detail=f"获取交易对信息失败: {str(e)}")


@router.get("/supported-symbols")
async def get_supported_symbols(
    current_user: User = Depends(get_current_user)
):
    """
    获取支持的交易对列表
    
    返回当前支持的所有交易对及其基本信息
    """
    try:
        supported_symbols = okx_market_service.supported_symbols
        
        # 获取所有支持交易对的基本信息
        symbol_info_list = []
        for symbol in supported_symbols:
            try:
                info = await okx_market_service.get_symbol_info(symbol)
                symbol_info_list.append(info)
            except Exception as e:
                logger.warning(f"⚠️ 获取 {symbol} 信息失败: {e}")
                continue
        
        logger.info(f"📋 用户 {current_user.id} 获取支持的交易对列表")
        
        return {
            "success": True,
            "data": {
                "symbols": supported_symbols,
                "symbol_info": symbol_info_list,
                "count": len(supported_symbols)
            },
            "message": f"获取支持的 {len(supported_symbols)} 个交易对成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取支持的交易对列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取支持的交易对列表失败: {str(e)}")


@router.get("/health")
async def market_data_health():
    """
    市场数据服务健康检查
    
    不需要认证的公开端点，用于检查服务状态
    """
    try:
        health_info = await okx_market_service.health_check()
        
        return {
            "success": True,
            "data": health_info,
            "message": "市场数据服务健康检查完成"
        }
        
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "市场数据服务健康检查失败"
        }


@router.get("/statistics")
async def get_market_statistics(
    current_user: User = Depends(get_current_user)
):
    """
    获取市场数据统计信息
    
    包括缓存命中率、数据源状态、服务性能等
    """
    try:
        # 获取缓存统计
        cache_stats = {
            "kline_cache_size": len(okx_market_service.kline_cache),
            "ticker_cache_size": len(okx_market_service.ticker_cache),
            "cache_ttl_seconds": okx_market_service.cache_ttl
        }
        
        # 获取支持的配置
        service_config = {
            "supported_symbols_count": len(okx_market_service.supported_symbols),
            "supported_timeframes": list(okx_market_service.timeframe_map.keys()),
            "rest_api_url": okx_market_service.rest_url,
            "max_symbols_per_batch": 20
        }
        
        logger.info(f"📊 用户 {current_user.id} 获取市场数据统计")
        
        return {
            "success": True,
            "data": {
                "cache_statistics": cache_stats,
                "service_configuration": service_config,
                "timestamp": int(datetime.now().timestamp() * 1000)
            },
            "message": "获取市场数据统计信息成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取市场数据统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取市场数据统计失败: {str(e)}")


# 添加到主路由的实用端点
@router.get("/trading-pairs")
async def get_popular_trading_pairs(
    limit: int = Query(8, ge=1, le=20, description="返回数量"),
    current_user: User = Depends(get_current_user)
):
    """
    获取热门交易对及实时价格
    
    用于前端首页显示，包含价格和24小时涨跌幅
    """
    try:
        # 获取前N个支持的交易对
        popular_symbols = okx_market_service.supported_symbols[:limit]
        
        # 批量获取价格数据
        price_data = await okx_market_service.get_multiple_tickers(popular_symbols)
        
        # 格式化返回数据 - 使用安全的数据验证
        trading_pairs = []
        for symbol in popular_symbols:
            if symbol in price_data:
                ticker = price_data[symbol]
                # 使用安全的数据验证和格式化
                validated_ticker = DataValidator.validate_price_data(ticker)
                validated_ticker["symbol"] = symbol  # 确保symbol字段正确
                trading_pairs.append(validated_ticker)
        
        logger.info(f"🎯 用户 {current_user.id} 获取热门交易对: {len(trading_pairs)} 个")
        
        return {
            "success": True,
            "data": {
                "trading_pairs": trading_pairs,
                "count": len(trading_pairs),
                "last_updated": int(datetime.now().timestamp() * 1000)
            },
            "message": f"获取 {len(trading_pairs)} 个热门交易对成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取热门交易对失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取热门交易对失败: {str(e)}")