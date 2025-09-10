"""
AI策略自动修复服务

利用Claude AI自动修复策略代码中的错误，确保生成的代码符合模板规范
"""

import re
from typing import Dict, List, Any, Optional
from loguru import logger

from app.core.claude_client import ClaudeClient
from app.services.claude_account_service import claude_account_service
from app.services.strategy_template_validator import StrategyTemplateValidator


def extract_python_code(content: str) -> str:
    """提取Python代码块"""
    # 尝试从```python代码块中提取
    if "```python" in content:
        parts = content.split("```python")
        if len(parts) > 1:
            code_part = parts[1].split("```")[0]
            return code_part.strip()
    
    # 尝试从```代码块中提取
    if "```" in content:
        parts = content.split("```")
        if len(parts) >= 3:
            return parts[1].strip()
    
    # 如果没有代码块标记，返回原内容
    return content.strip()


class StrategyAutoFixService:
    """策略自动修复服务"""
    
    MAX_FIX_ATTEMPTS = 3
    
    @staticmethod
    async def _get_claude_client() -> Optional[ClaudeClient]:
        """获取Claude客户端实例"""
        try:
            account = await claude_account_service.select_best_account()
            if not account:
                logger.error("没有可用的Claude账号")
                return None
            
            decrypted_api_key = await claude_account_service.get_decrypted_api_key(account.id)
            if not decrypted_api_key:
                logger.error("无法获取解密的API密钥")
                return None
            
            return ClaudeClient(
                api_key=decrypted_api_key,
                base_url=account.proxy_base_url,
                timeout=120,
                max_retries=2
            )
        except Exception as e:
            logger.error(f"获取Claude客户端失败: {e}")
            return None
    
    @staticmethod
    async def auto_fix_strategy(
        code: str,
        validation_errors: List[str],
        original_intent: Dict[str, Any],
        attempt: int = 1
    ) -> Dict[str, Any]:
        """AI自动修复策略代码"""
        
        if attempt > StrategyAutoFixService.MAX_FIX_ATTEMPTS:
            return {
                "success": False,
                "fixed_code": code,
                "error": "超过最大修复尝试次数",
                "attempts_used": attempt - 1
            }
        
        try:
            logger.info(f"开始第{attempt}次策略代码修复")
            
            # 构建修复提示词
            fix_prompt = StrategyAutoFixService._build_fix_prompt(
                code, validation_errors, original_intent
            )
            
            # 调用Claude进行修复
            claude_client = await StrategyAutoFixService._get_claude_client()
            if not claude_client:
                return {
                    "success": False,
                    "fixed_code": code,
                    "error": "无法获取Claude客户端",
                    "attempts_used": attempt
                }
                
            response = await claude_client.create_message(
                messages=[{
                    "role": "user",
                    "content": fix_prompt
                }],
                system="你是专业的Python代码修复专家，精通量化交易策略开发，严格按照模板要求修复代码。",
                temperature=0.3
            )
            
            if not response["success"]:
                return {
                    "success": False,
                    "fixed_code": code,
                    "error": f"AI修复调用失败: {response.get('error', '未知错误')}",
                    "attempts_used": attempt
                }
            
            # 提取修复后的代码
            content = response["content"]
            if isinstance(content, list) and len(content) > 0:
                # Anthropic原始格式
                content = content[0].get("text", "")
            elif isinstance(content, str):
                # 包装格式
                pass
            else:
                content = str(content)
                
            fixed_code = extract_python_code(content)
            
            # 验证修复结果
            validation_result = await StrategyTemplateValidator.validate_strategy(fixed_code)
            
            if validation_result["valid"]:
                logger.info(f"策略代码修复成功，使用{attempt}次尝试")
                return {
                    "success": True,
                    "fixed_code": fixed_code,
                    "fix_explanation": content,
                    "validation_result": validation_result,
                    "attempts_used": attempt
                }
            else:
                # 如果还有修复机会，递归尝试
                remaining_errors = validation_result["errors"]
                if attempt < StrategyAutoFixService.MAX_FIX_ATTEMPTS and len(remaining_errors) < len(validation_errors):
                    logger.info(f"第{attempt}次修复部分成功，剩余{len(remaining_errors)}个错误，继续修复")
                    return await StrategyAutoFixService.auto_fix_strategy(
                        fixed_code, remaining_errors, original_intent, attempt + 1
                    )
                else:
                    return {
                        "success": False,
                        "fixed_code": fixed_code,
                        "error": f"修复后仍有错误: {remaining_errors}",
                        "validation_result": validation_result,
                        "attempts_used": attempt
                    }
                    
        except Exception as e:
            logger.error(f"策略自动修复异常: {e}")
            return {
                "success": False,
                "fixed_code": code,
                "error": f"修复过程异常: {str(e)}",
                "attempts_used": attempt
            }
    
    @staticmethod
    def _build_fix_prompt(
        code: str,
        validation_errors: List[str],
        original_intent: Dict[str, Any]
    ) -> str:
        """构建修复提示词"""
        
        # 分类错误类型
        syntax_errors = [e for e in validation_errors if "语法错误" in e]
        template_errors = [e for e in validation_errors if any(keyword in e for keyword in ["缺少", "必须", "方法", "导入"])]
        security_errors = [e for e in validation_errors if any(keyword in e for keyword in ["禁用", "危险", "禁止"])]
        compilation_errors = [e for e in validation_errors if "编译" in e]
        
        fix_prompt = f"""
请修复以下策略代码中的错误。

原始策略代码：
```python
{code}
```

发现的错误分类：

语法错误：
{chr(10).join(f"• {error}" for error in syntax_errors) if syntax_errors else "无"}

模板规范错误：
{chr(10).join(f"• {error}" for error in template_errors) if template_errors else "无"}

安全性错误：
{chr(10).join(f"• {error}" for error in security_errors) if security_errors else "无"}

编译错误：
{chr(10).join(f"• {error}" for error in compilation_errors) if compilation_errors else "无"}

原始策略需求：
策略类型: {original_intent.get('strategy_type', '未知')}
数据需求: {original_intent.get('data_requirements', [])}
交易逻辑: {original_intent.get('trading_logic', '未描述')}

修复要求：

1. 严格按照以下模板结构：
```python
from app.core.enhanced_strategy import EnhancedBaseStrategy, DataRequest, DataType
from app.core.strategy_engine import TradingSignal, SignalType
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

class UserStrategy(EnhancedBaseStrategy):
    \"\"\"修复后的策略\"\"\"
    
    def get_data_requirements(self) -> List[DataRequest]:
        \"\"\"定义数据需求\"\"\"
        return [
            DataRequest(
                data_type=DataType.KLINE,
                exchange="okx",
                symbol="BTC-USDT-SWAP",
                timeframe="1h",
                required=True
            )
            # 根据需求添加其他数据源...
        ]
    
    async def on_data_update(self, data_type: str, data: Dict[str, Any]) -> Optional[TradingSignal]:
        \"\"\"数据更新处理\"\"\"
        if data_type != "kline":
            return None
            
        df = self.get_kline_data()
        if df is None or len(df) < 20:
            return None
        
        # 实现策略逻辑
        # 计算技术指标
        # 生成交易信号
        
        return None  # 或返回TradingSignal
```

2. 修复原则：
   - 保持原有的业务逻辑和策略思想
   - 修复所有语法错误
   - 补充缺失的必需方法和导入
   - 移除所有禁用函数和危险操作
   - 确保方法签名正确
   - 添加适当的类型注解
   - 保持代码可读性和注释

3. 安全要求：
   - 不使用eval、exec、import、open等禁用函数
   - 不进行网络请求或文件操作
   - 不访问系统资源
   - 不使用双下划线方法

请只返回修复后的完整代码，用```python代码块包围。
"""
        return fix_prompt
    
    @staticmethod
    async def suggest_improvements(
        code: str,
        validation_warnings: List[str],
        strategy_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提供代码改进建议"""
        
        try:
            improvement_prompt = f"""
分析以下策略代码，提供改进建议：

策略代码：
```python
{code}
```

发现的警告：
{chr(10).join(f"• {warning}" for warning in validation_warnings)}

策略元数据：
- 类名: {strategy_metadata.get('class_name', 'Unknown')}
- 复杂度: {strategy_metadata.get('complexity_score', 0)}/10
- 数据需求: {strategy_metadata.get('data_requirements', [])}
- 代码行数: {strategy_metadata.get('estimated_lines', 0)}
- 风险控制: {'有' if strategy_metadata.get('has_risk_controls') else '无'}

请提供以下方面的改进建议：

1. 代码质量改进
2. 性能优化建议
3. 风险控制增强
4. 可读性提升
5. 最佳实践建议

以JSON格式返回：
{{
    "code_quality": ["具体的代码质量改进建议"],
    "performance": ["性能优化建议"],
    "risk_management": ["风险控制建议"],
    "readability": ["可读性改进建议"],
    "best_practices": ["最佳实践建议"],
    "overall_score": 8.5,
    "priority_fixes": ["高优先级修复项"]
}}
"""
            
            claude_client = await StrategyAutoFixService._get_claude_client()
            if not claude_client:
                return {
                    "success": False,
                    "error": "无法获取Claude客户端"
                }
                
            response = await claude_client.create_message(
                messages=[{"role": "user", "content": improvement_prompt}],
                system="你是资深的量化策略代码审查专家，提供专业的改进建议。",
                temperature=0.4
            )
            
            if response["success"]:
                try:
                    # 尝试解析JSON响应
                    import json
                    content = response["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # Anthropic原始格式
                        content = content[0].get("text", "")
                    elif isinstance(content, str):
                        # 包装格式
                        pass
                    else:
                        content = str(content)
                    content = content.strip()
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    suggestions = json.loads(content)
                    return {
                        "success": True,
                        "suggestions": suggestions
                    }
                except json.JSONDecodeError:
                    # JSON解析失败时返回纯文本建议
                    return {
                        "success": True,
                        "suggestions": {
                            "general_advice": content,
                            "overall_score": 7.0
                        }
                    }
            else:
                return {
                    "success": False,
                    "error": "AI建议生成失败"
                }
                
        except Exception as e:
            logger.error(f"生成改进建议失败: {e}")
            return {
                "success": False,
                "error": f"建议生成异常: {str(e)}"
            }
    
    @staticmethod
    def generate_fix_explanation(
        original_errors: List[str],
        fixed_code: str,
        attempts_used: int
    ) -> str:
        """生成修复说明"""
        
        explanation = f"✅ 策略代码修复完成！\n\n"
        explanation += f"🔧 修复统计：\n"
        explanation += f"• 解决了 {len(original_errors)} 个问题\n"
        explanation += f"• 使用了 {attempts_used} 次AI修复\n"
        explanation += f"• 代码行数: {len(fixed_code.split(chr(10)))} 行\n\n"
        
        explanation += "🛠️ 主要修复内容：\n"
        
        error_categories = {
            "语法错误": [e for e in original_errors if "语法错误" in e],
            "模板规范": [e for e in original_errors if any(kw in e for kw in ["缺少", "必须"])],
            "安全问题": [e for e in original_errors if any(kw in e for kw in ["禁用", "危险"])],
            "编译问题": [e for e in original_errors if "编译" in e]
        }
        
        for category, errors in error_categories.items():
            if errors:
                explanation += f"• {category}: 修复了 {len(errors)} 个问题\n"
        
        explanation += f"\n✨ 修复后的代码已通过全部验证检查，可以安全运行！"
        
        return explanation