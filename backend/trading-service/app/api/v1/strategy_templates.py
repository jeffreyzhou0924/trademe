"""
策略模板管理API

提供预置策略模板的查询、获取和应用功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import json

from app.database import get_db
from app.templates.strategy_templates import (
    get_strategy_templates,
    get_strategy_template_by_id,
    get_templates_by_category,
    get_templates_by_difficulty,
    search_templates,
    STRATEGY_CATEGORIES,
    DIFFICULTY_LEVELS,
    TIMEFRAME_OPTIONS
)
from app.middleware.auth import get_current_user
from app.services.strategy_service import StrategyService
from app.models.user import User
from app.schemas.strategy import StrategyCreate

router = APIRouter()

@router.get("/", summary="获取策略模板列表")
async def get_templates(
    category: Optional[str] = Query(None, description="策略分类筛选"),
    difficulty: Optional[str] = Query(None, description="难度级别筛选"),
    search: Optional[str] = Query(None, description="关键词搜索"),
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """获取策略模板列表"""
    try:
        templates = get_strategy_templates()
        
        # 应用筛选条件
        if category:
            templates = get_templates_by_category(category)
        elif difficulty:
            templates = get_templates_by_difficulty(difficulty)
        elif search:
            templates = search_templates(search)
        
        # 限制返回数量
        templates = templates[:limit]
        
        # 简化返回信息（不包含完整代码）
        simplified_templates = []
        for template in templates:
            simplified = {
                "id": template["id"],
                "name": template["name"],
                "description": template["description"],
                "category": template["category"],
                "difficulty": template["difficulty"],
                "timeframe": template["timeframe"],
                "tags": template.get("tags", []),
                "risk_level": template.get("risk_level"),
                "expected_return": template.get("expected_return"),
                "max_drawdown": template.get("max_drawdown"),
                "author": template.get("author"),
                "created_at": template.get("created_at"),
                "parameters": template.get("parameters", {})
            }
            simplified_templates.append(simplified)
        
        return {
            "templates": simplified_templates,
            "total": len(simplified_templates),
            "categories": STRATEGY_CATEGORIES,
            "difficulties": DIFFICULTY_LEVELS,
            "timeframes": TIMEFRAME_OPTIONS
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略模板失败: {str(e)}")

@router.get("/{template_id}", summary="获取策略模板详情")
async def get_template_detail(
    template_id: str,
    include_code: bool = Query(False, description="是否包含策略代码")
):
    """获取策略模板详情"""
    try:
        template = get_strategy_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        
        # 如果不需要代码，则移除代码字段
        if not include_code:
            template = template.copy()
            template.pop("code", None)
        
        return {
            "template": template,
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模板详情失败: {str(e)}")

@router.get("/{template_id}/code", summary="获取策略模板代码")
async def get_template_code(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取策略模板的完整代码"""
    try:
        template = get_strategy_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        
        return {
            "template_id": template_id,
            "name": template["name"],
            "code": template["code"],
            "parameters": template.get("parameters", {}),
            "description": template["description"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模板代码失败: {str(e)}")

@router.post("/{template_id}/apply", summary="应用策略模板创建策略")
async def apply_template(
    template_id: str,
    custom_name: Optional[str] = None,
    custom_description: Optional[str] = None,
    custom_parameters: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """基于模板创建新策略"""
    try:
        template = get_strategy_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        
        # 合并参数
        parameters = template.get("parameters", {}).copy()
        if custom_parameters:
            parameters.update(custom_parameters)
        
        # 创建策略数据
        strategy_data = StrategyCreate(
            name=custom_name or f"{template['name']} - {current_user.username}",
            description=custom_description or template["description"],
            code=template["code"],
            parameters=json.dumps(parameters),
            is_active=True,
            is_public=False
        )
        
        # 创建策略
        strategy = await StrategyService.create_strategy(db, strategy_data, current_user.id)
        
        return {
            "strategy": strategy,
            "template_id": template_id,
            "message": "策略创建成功",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用模板失败: {str(e)}")

@router.get("/categories/list", summary="获取策略分类列表")
async def get_categories():
    """获取所有策略分类"""
    try:
        return {
            "categories": STRATEGY_CATEGORIES,
            "total": len(STRATEGY_CATEGORIES)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类失败: {str(e)}")

@router.get("/difficulties/list", summary="获取难度级别列表")
async def get_difficulties():
    """获取所有难度级别"""
    try:
        return {
            "difficulties": DIFFICULTY_LEVELS,
            "total": len(DIFFICULTY_LEVELS)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取难度级别失败: {str(e)}")

@router.get("/timeframes/list", summary="获取时间周期列表")
async def get_timeframes():
    """获取所有时间周期选项"""
    try:
        return {
            "timeframes": TIMEFRAME_OPTIONS,
            "total": len(TIMEFRAME_OPTIONS)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取时间周期失败: {str(e)}")

@router.post("/{template_id}/customize", summary="自定义策略模板参数")
async def customize_template_parameters(
    template_id: str,
    parameters: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """自定义模板参数并验证"""
    try:
        template = get_strategy_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        
        # 获取默认参数
        default_params = template.get("parameters", {})
        
        # 验证参数类型和范围
        validated_params = {}
        validation_errors = []
        
        for key, value in parameters.items():
            if key in default_params:
                default_value = default_params[key]
                
                # 类型验证
                if type(value) != type(default_value):
                    try:
                        # 尝试类型转换
                        if isinstance(default_value, float):
                            value = float(value)
                        elif isinstance(default_value, int):
                            value = int(value)
                        elif isinstance(default_value, bool):
                            value = bool(value)
                    except (ValueError, TypeError):
                        validation_errors.append(f"参数 {key} 类型不正确")
                        continue
                
                # 范围验证（简单的边界检查）
                if isinstance(value, (int, float)):
                    if value <= 0:
                        validation_errors.append(f"参数 {key} 必须大于0")
                        continue
                    if key.endswith('_threshold') and (value < 0 or value > 1):
                        validation_errors.append(f"阈值参数 {key} 必须在0-1之间")
                        continue
                
                validated_params[key] = value
            else:
                validation_errors.append(f"未知参数: {key}")
        
        # 合并默认参数
        final_params = default_params.copy()
        final_params.update(validated_params)
        
        return {
            "template_id": template_id,
            "parameters": final_params,
            "validation_errors": validation_errors,
            "is_valid": len(validation_errors) == 0,
            "estimated_performance": {
                "risk_level": template.get("risk_level"),
                "expected_return": template.get("expected_return"),
                "max_drawdown": template.get("max_drawdown")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"参数自定义失败: {str(e)}")

@router.get("/{template_id}/backtest-preview", summary="预览模板回测效果")
async def preview_template_backtest(
    template_id: str,
    parameters: Optional[str] = Query(None, description="JSON格式的参数"),
    symbol: str = Query("BTC/USDT", description="交易对"),
    timeframe: str = Query("1h", description="时间周期"),
    current_user: User = Depends(get_current_user)
):
    """预览策略模板的理论回测效果"""
    try:
        template = get_strategy_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="策略模板不存在")
        
        # 解析参数
        if parameters:
            try:
                custom_params = json.loads(parameters)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="参数格式错误")
        else:
            custom_params = {}
        
        # 合并参数
        final_params = template.get("parameters", {}).copy()
        final_params.update(custom_params)
        
        # 生成理论预览（简化版本）
        preview = {
            "template_id": template_id,
            "template_name": template["name"],
            "symbol": symbol,
            "timeframe": timeframe,
            "parameters": final_params,
            "theoretical_metrics": {
                "expected_annual_return": template.get("expected_return", "10-15%"),
                "max_drawdown": template.get("max_drawdown", "8-12%"),
                "risk_level": template.get("risk_level", "中等"),
                "win_rate": "55-65%",  # 理论胜率
                "profit_factor": "1.2-1.8",  # 理论盈亏比
                "sharpe_ratio": "0.8-1.5"  # 理论夏普比率
            },
            "suitable_market": _get_suitable_market_conditions(template),
            "warnings": _get_strategy_warnings(template, final_params),
            "recommendations": _get_parameter_recommendations(template, final_params)
        }
        
        return preview
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览回测失败: {str(e)}")

def _get_suitable_market_conditions(template: Dict[str, Any]) -> List[str]:
    """获取策略适用的市场条件"""
    category = template.get("category", "")
    
    if "均值回归" in category:
        return ["震荡市场", "低波动率", "横盘整理"]
    elif "趋势跟踪" in category or "动量" in category:
        return ["趋势市场", "高波动率", "单边行情"]
    elif "突破" in category:
        return ["突破性行情", "成交量放大", "关键价位"]
    elif "网格" in category:
        return ["震荡市场", "价格区间明确", "低趋势性"]
    elif "套利" in category:
        return ["市场中性", "相关性稳定", "价差波动"]
    else:
        return ["多种市场条件"]

def _get_strategy_warnings(template: Dict[str, Any], parameters: Dict[str, Any]) -> List[str]:
    """获取策略使用警告"""
    warnings = []
    
    # 风险级别警告
    risk_level = template.get("risk_level", "")
    if "高" in risk_level:
        warnings.append("该策略属于高风险策略，建议控制仓位大小")
    
    # 参数警告
    if "stop_loss" in parameters and parameters["stop_loss"] > 0.15:
        warnings.append("止损设置过大，可能承担过高风险")
    
    if "position_size" in parameters and parameters["position_size"] > 0.8:
        warnings.append("仓位过大，建议降低至50%以下")
    
    # 难度级别警告
    if template.get("difficulty") == "高级":
        warnings.append("该策略较为复杂，建议先在模拟环境测试")
    
    return warnings

def _get_parameter_recommendations(template: Dict[str, Any], parameters: Dict[str, Any]) -> List[str]:
    """获取参数优化建议"""
    recommendations = []
    
    # RSI策略建议
    if "rsi" in template["id"]:
        if parameters.get("oversold_threshold", 30) > 25:
            recommendations.append("可考虑将超卖阈值降低至25以下，增加交易机会")
    
    # MACD策略建议  
    if "macd" in template["id"]:
        if parameters.get("fast_period", 12) == 12 and parameters.get("slow_period", 26) == 26:
            recommendations.append("可尝试调整MACD参数，如快线10、慢线21，适应不同周期")
    
    # 布林带策略建议
    if "bollinger" in template["id"]:
        if parameters.get("bb_std", 2.0) == 2.0:
            recommendations.append("可根据市场波动率调整标准差，高波动市场可用2.5")
    
    # 通用建议
    recommendations.append("建议先进行历史回测验证策略有效性")
    recommendations.append("实盘使用前建议小仓位试运行")
    
    return recommendations