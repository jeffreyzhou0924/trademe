"""
策略模板验证器

对AI生成的策略代码进行多层验证：语法检查、模板规范、安全检查、编译测试
"""

import ast
import re
import inspect
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger


class StrategyTemplateValidator:
    """策略模板验证器"""
    
    REQUIRED_IMPORTS = [
        "EnhancedBaseStrategy", "DataRequest", "DataType",
        "TradingSignal", "SignalType"
    ]
    
    REQUIRED_METHODS = [
        "get_data_requirements", "on_data_update"
    ]
    
    FORBIDDEN_FUNCTIONS = [
        "eval", "exec", "import", "__import__", "open", 
        "file", "input", "raw_input", "compile", "globals", 
        "locals", "vars", "dir", "getattr", "setattr",
        "delattr", "hasattr"
    ]
    
    FORBIDDEN_MODULES = [
        "os", "sys", "subprocess", "socket", "urllib",
        "requests", "http", "ftplib", "smtplib", "telnetlib"
    ]
    
    @classmethod
    async def validate_strategy(cls, code: str) -> Dict[str, Any]:
        """全面验证策略代码"""
        
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "syntax_check": {"passed": False},
            "template_check": {"passed": False},
            "security_check": {"passed": False},
            "compilation_test": {"passed": False}
        }
        
        try:
            # 1. 语法检查
            syntax_result = await cls._check_syntax(code)
            validation_result["syntax_check"] = syntax_result
            if not syntax_result["passed"]:
                validation_result["errors"].extend(syntax_result["errors"])
                return validation_result
            
            # 2. 模板结构检查
            template_result = await cls._check_template_structure(code)
            validation_result["template_check"] = template_result
            if not template_result["passed"]:
                validation_result["errors"].extend(template_result["errors"])
                validation_result["warnings"].extend(template_result.get("warnings", []))
            
            # 3. 安全性检查
            security_result = await cls._check_security(code)
            validation_result["security_check"] = security_result
            if not security_result["passed"]:
                validation_result["errors"].extend(security_result["errors"])
            
            # 4. 编译测试
            if len(validation_result["errors"]) == 0:
                compilation_result = await cls._test_compilation(code)
                validation_result["compilation_test"] = compilation_result
                if not compilation_result["passed"]:
                    validation_result["errors"].extend(compilation_result["errors"])
            
            # 综合判断
            validation_result["valid"] = len(validation_result["errors"]) == 0
            
            logger.info(f"策略验证完成: valid={validation_result['valid']}, errors={len(validation_result['errors'])}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"策略验证异常: {e}")
            validation_result["errors"].append(f"验证过程异常: {str(e)}")
            return validation_result
    
    @classmethod
    async def _check_syntax(cls, code: str) -> Dict[str, Any]:
        """语法检查"""
        try:
            ast.parse(code)
            return {
                "passed": True,
                "errors": []
            }
        except SyntaxError as e:
            return {
                "passed": False,
                "errors": [f"语法错误 (行{e.lineno}): {e.msg}"]
            }
        except Exception as e:
            return {
                "passed": False,
                "errors": [f"语法检查异常: {str(e)}"]
            }
    
    @classmethod
    async def _check_template_structure(cls, code: str) -> Dict[str, Any]:
        """模板结构检查"""
        errors = []
        warnings = []
        
        # 检查必需的导入
        for required_import in cls.REQUIRED_IMPORTS:
            if required_import not in code:
                errors.append(f"缺少必需的导入: {required_import}")
        
        # 检查类定义
        if not re.search(r'class\s+\w+\s*\(\s*EnhancedBaseStrategy\s*\)', code):
            errors.append("必须定义一个继承EnhancedBaseStrategy的类")
        
        # 检查必需方法
        for method in cls.REQUIRED_METHODS:
            if not re.search(rf'def\s+{method}\s*\(', code):
                errors.append(f"缺少必需方法: {method}")
        
        # 检查方法签名
        if "def get_data_requirements(self)" not in code and "def get_data_requirements(self) ->" not in code:
            warnings.append("get_data_requirements方法签名可能不正确")
        
        if "async def on_data_update(self" not in code:
            errors.append("on_data_update必须是async方法")
        
        # 检查返回类型
        if "-> List[DataRequest]" not in code:
            warnings.append("get_data_requirements应该有返回类型注解")
        
        if "-> Optional[TradingSignal]" not in code:
            warnings.append("on_data_update应该有返回类型注解")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    @classmethod
    async def _check_security(cls, code: str) -> Dict[str, Any]:
        """安全性检查"""
        errors = []
        
        # 检查禁用函数
        for forbidden in cls.FORBIDDEN_FUNCTIONS:
            if re.search(rf'\b{forbidden}\s*\(', code):
                errors.append(f"包含禁用函数: {forbidden}()")
        
        # 检查禁用模块导入
        for module in cls.FORBIDDEN_MODULES:
            if re.search(rf'import\s+{module}', code) or re.search(rf'from\s+{module}\s+import', code):
                errors.append(f"禁止导入模块: {module}")
        
        # 检查危险操作
        dangerous_patterns = [
            r'__.*__',  # 双下划线方法
            r'exec\s*\(',
            r'eval\s*\(',
            r'compile\s*\(',
            r'\.system\s*\(',
            r'\.popen\s*\(',
            r'\.call\s*\(',
        ]
        
        for pattern in dangerous_patterns:
            matches = re.findall(pattern, code)
            if matches:
                errors.append(f"包含危险操作模式: {matches[0]}")
        
        # 检查网络相关操作
        network_patterns = [
            r'urllib',
            r'requests\.',
            r'http\.',
            r'socket\.',
            r'\.get\s*\(',
            r'\.post\s*\(',
        ]
        
        for pattern in network_patterns:
            if re.search(pattern, code):
                errors.append(f"禁止网络操作: 发现模式 {pattern}")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors
        }
    
    @classmethod
    async def _test_compilation(cls, code: str) -> Dict[str, Any]:
        """编译测试"""
        try:
            # 创建安全的执行环境
            namespace = cls._create_safe_namespace()
            
            # 编译代码
            compiled_code = compile(code, '<strategy>', 'exec')
            
            # 在安全环境中执行
            exec(compiled_code, namespace)
            
            # 查找策略类
            strategy_class = cls._find_strategy_class(namespace)
            
            if strategy_class is None:
                return {
                    "passed": False,
                    "errors": ["未找到有效的策略类"]
                }
            
            # 验证方法存在
            method_errors = cls._validate_class_methods(strategy_class)
            if method_errors:
                return {
                    "passed": False,
                    "errors": method_errors
                }
            
            return {
                "passed": True,
                "errors": [],
                "strategy_class_name": strategy_class.__name__
            }
            
        except Exception as e:
            return {
                "passed": False,
                "errors": [f"编译失败: {str(e)}"]
            }
    
    @classmethod
    def _create_safe_namespace(cls) -> Dict[str, Any]:
        """创建安全的执行命名空间"""
        # 创建模拟对象避免实际导入
        class MockEnhancedBaseStrategy:
            def __init__(self, context): pass
        
        class MockDataRequest:
            def __init__(self, **kwargs): pass
        
        class MockDataType:
            KLINE = "kline"
            ORDERBOOK = "orderbook"
            FUNDING_FLOW = "funding_flow"
            NEWS_SENTIMENT = "news_sentiment"
        
        class MockTradingSignal:
            def __init__(self, **kwargs): pass
        
        class MockSignalType:
            BUY = "buy"
            SELL = "sell"
            HOLD = "hold"
        
        return {
            'EnhancedBaseStrategy': MockEnhancedBaseStrategy,
            'DataRequest': MockDataRequest,
            'DataType': MockDataType,
            'TradingSignal': MockTradingSignal,
            'SignalType': MockSignalType,
            'List': list,
            'Optional': type(None),
            'Dict': dict,
            'Any': object,
            'datetime': datetime,
            'pd': type('MockPandas', (), {}),
            'np': type('MockNumpy', (), {}),
            # 禁用危险函数
            'eval': None,
            'exec': None,
            'compile': None,
            'open': None,
            'input': None,
            '__import__': None,
        }
    
    @classmethod
    def _find_strategy_class(cls, namespace: Dict[str, Any]) -> Optional[type]:
        """查找策略类"""
        for name, obj in namespace.items():
            if (inspect.isclass(obj) and 
                name not in ['EnhancedBaseStrategy'] and
                hasattr(obj, 'get_data_requirements') and
                hasattr(obj, 'on_data_update')):
                return obj
        return None
    
    @classmethod
    def _validate_class_methods(cls, strategy_class: type) -> List[str]:
        """验证类方法"""
        errors = []
        
        # 检查必需方法
        if not hasattr(strategy_class, 'get_data_requirements'):
            errors.append("策略类缺少get_data_requirements方法")
        
        if not hasattr(strategy_class, 'on_data_update'):
            errors.append("策略类缺少on_data_update方法")
        
        # 检查方法签名
        try:
            if hasattr(strategy_class, 'get_data_requirements'):
                sig = inspect.signature(strategy_class.get_data_requirements)
                if len(sig.parameters) != 1:  # 只有self参数
                    errors.append("get_data_requirements方法参数不正确")
        except Exception:
            errors.append("get_data_requirements方法签名检查失败")
        
        try:
            if hasattr(strategy_class, 'on_data_update'):
                sig = inspect.signature(strategy_class.on_data_update)
                params = list(sig.parameters.keys())
                if len(params) != 3 or params != ['self', 'data_type', 'data']:
                    errors.append("on_data_update方法参数不正确，应为(self, data_type: str, data: Dict)")
        except Exception:
            errors.append("on_data_update方法签名检查失败")
        
        return errors
    
    @classmethod
    async def extract_strategy_metadata(cls, code: str) -> Dict[str, Any]:
        """提取策略元数据"""
        try:
            # 提取类名
            class_match = re.search(r'class\s+(\w+)\s*\(\s*EnhancedBaseStrategy\s*\)', code)
            class_name = class_match.group(1) if class_match else "UnknownStrategy"
            
            # 提取文档字符串
            docstring_match = re.search(r'"""([^"]+)"""', code)
            description = docstring_match.group(1).strip() if docstring_match else "AI生成的交易策略"
            
            # 提取数据需求
            data_requirements = []
            data_req_pattern = r'DataType\.(\w+)'
            data_matches = re.findall(data_req_pattern, code)
            data_requirements = list(set(data_matches))
            
            # 估算复杂度
            complexity_indicators = [
                len(re.findall(r'def\s+\w+', code)),  # 方法数量
                len(re.findall(r'if\s+', code)),      # 条件语句数量
                len(re.findall(r'for\s+', code)),     # 循环数量
                len(data_requirements)                # 数据源数量
            ]
            complexity_score = min(10, sum(complexity_indicators))
            
            return {
                "class_name": class_name,
                "description": description,
                "data_requirements": data_requirements,
                "complexity_score": complexity_score,
                "estimated_lines": len(code.split('\n')),
                "has_risk_controls": "stop_loss" in code.lower() or "止损" in code
            }
            
        except Exception as e:
            logger.error(f"提取策略元数据失败: {e}")
            return {
                "class_name": "UnknownStrategy",
                "description": "AI生成的交易策略",
                "data_requirements": ["kline"],
                "complexity_score": 5,
                "estimated_lines": 0,
                "has_risk_controls": False
            }