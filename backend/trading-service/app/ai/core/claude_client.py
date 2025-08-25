"""
Claude API客户端封装

提供Claude AI的完整封装，包括：
- 异步API调用
- 错误处理和重试
- Token使用统计
- 成本控制
- 性能监控
"""

import asyncio
import os
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from decimal import Decimal

import anthropic
from anthropic import AsyncAnthropic
from loguru import logger

from app.config import settings


class ClaudeUsageStats:
    """Claude使用统计"""
    
    def __init__(self):
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = Decimal('0.00')
        self.average_response_time = 0.0
        self.error_count = 0
        
    def add_request(
        self, 
        input_tokens: int, 
        output_tokens: int, 
        response_time_ms: float,
        success: bool = True
    ):
        """添加请求统计"""
        self.total_requests += 1
        
        if success:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
            # Claude 4 Sonnet 定价 (2025年价格，与3.5相同)
            input_cost = Decimal(str(input_tokens)) * Decimal('3.0') / Decimal('1000000')  # $3/1M tokens
            output_cost = Decimal(str(output_tokens)) * Decimal('15.0') / Decimal('1000000')  # $15/1M tokens
            self.total_cost += input_cost + output_cost
            
            # 更新平均响应时间
            self.average_response_time = (
                (self.average_response_time * (self.total_requests - 1) + response_time_ms) / 
                self.total_requests
            )
        else:
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.total_requests - self.error_count,
            "error_count": self.error_count,
            "success_rate": (self.total_requests - self.error_count) / max(self.total_requests, 1),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": float(self.total_cost),
            "average_response_time_ms": self.average_response_time,
            "cost_per_request": float(self.total_cost) / max(self.total_requests - self.error_count, 1)
        }


class ClaudeClient:
    """Claude API客户端封装类"""
    
    def __init__(self):
        """初始化Claude客户端"""
        # 支持多种API key环境变量
        self.api_key = (settings.claude_auth_token or 
                       settings.claude_api_key or 
                       os.getenv("ANTHROPIC_AUTH_TOKEN") or 
                       os.getenv("CLAUDE_API_KEY"))
        
        # 支持多种base_url环境变量
        self.base_url = (settings.anthropic_base_url or 
                        settings.claude_base_url or 
                        os.getenv("ANTHROPIC_BASE_URL") or 
                        os.getenv("CLAUDE_BASE_URL"))
        
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens
        self.timeout = settings.claude_timeout
        
        # 初始化客户端 (包含错误处理)
        if self.api_key and self.api_key != "your_claude_api_key_here":
            try:
                # 根据anthropic库版本使用合适的参数
                client_kwargs = {
                    "api_key": self.api_key,
                    "timeout": self.timeout
                }
                
                # 如果有自定义base_url，则使用
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                    logger.info(f"使用自定义Claude API端点: {self.base_url}")
                
                self.client = AsyncAnthropic(**client_kwargs)
                self.enabled = True
                logger.info("Claude客户端初始化成功")
            except Exception as e:
                logger.warning(f"Claude客户端初始化失败，回退到模拟模式: {str(e)}")
                self.client = None
                self.enabled = False
        else:
            self.client = None
            self.enabled = False
            logger.warning("Claude API密钥未设置，AI功能将使用模拟模式")
        
        # 使用统计
        self.stats = ClaudeUsageStats()
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 秒
        
        logger.info(f"Claude客户端初始化完成 - 模型: {self.model}, 启用状态: {self.enabled}")
    
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        retry_count: int = 0,
        api_key: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """执行Claude API请求"""
        
        if not self.enabled:
            # 模拟模式
            return await self._mock_response(messages, system_prompt)
        
        start_time = time.time()
        request_max_tokens = max_tokens or self.max_tokens
        
        try:
            # 如果提供了动态API密钥，创建临时客户端
            if api_key and api_key != self.api_key:
                temp_client_kwargs = {
                    "api_key": api_key,
                    "timeout": self.timeout
                }
                if self.base_url:
                    temp_client_kwargs["base_url"] = self.base_url
                
                temp_client = AsyncAnthropic(**temp_client_kwargs)
                client_to_use = temp_client
            else:
                client_to_use = self.client
            
            # 构建请求参数
            request_params = {
                "model": self.model,
                "max_tokens": request_max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            if system_prompt:
                request_params["system"] = system_prompt
            
            # 发送请求
            response = await client_to_use.messages.create(**request_params)
            
            # 计算响应时间
            response_time_ms = (time.time() - start_time) * 1000
            
            # 提取响应内容
            content = ""
            if response.content and len(response.content) > 0:
                content = response.content[0].text
            
            # 统计信息
            usage_info = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                "model": response.model,
                "response_time_ms": response_time_ms
            }
            
            # 更新统计
            self.stats.add_request(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                response_time_ms=response_time_ms,
                success=True
            )
            
            logger.debug(f"Claude API请求成功 - Token使用: {usage_info['total_tokens']}, 响应时间: {response_time_ms:.2f}ms")
            
            return content, usage_info
            
        except anthropic.RateLimitError as e:
            logger.warning(f"Claude API频率限制: {str(e)}")
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay * (2 ** retry_count))  # 指数退避
                return await self._make_request(messages, system_prompt, max_tokens, temperature, retry_count + 1, api_key)
            raise
            
        except anthropic.APITimeoutError as e:
            logger.warning(f"Claude API超时: {str(e)}")
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay)
                return await self._make_request(messages, system_prompt, max_tokens, temperature, retry_count + 1, api_key)
            raise
            
        except anthropic.APIError as e:
            error_message = str(e)
            logger.error(f"Claude API错误: {error_message}")
            
            # 特殊处理网关超时错误 (504 Gateway Timeout)
            if "504" in error_message or "Gateway time-out" in error_message:
                logger.warning(f"Claude API代理服务网关超时，尝试重试 (重试次数: {retry_count}/{self.max_retries})")
                if retry_count < self.max_retries:
                    # 网关超时使用更长的重试延迟
                    await asyncio.sleep(self.retry_delay * 2)  
                    return await self._make_request(messages, system_prompt, max_tokens, temperature, retry_count + 1, api_key)
                # 超过重试次数后抛出用户友好的错误
                raise Exception("Claude AI服务繁忙，请稍后重试")
            
            # 特殊处理503服务不可用错误
            if "503" in error_message or "Service Unavailable" in error_message:
                logger.warning("Claude API服务暂时不可用")
                raise Exception("AI服务暂时维护中，请稍后重试")
            
            # 特殊处理认证错误
            if "401" in error_message or "authentication" in error_message.lower():
                logger.error("Claude API认证失败")
                raise Exception("AI服务认证失败，请联系管理员")
            
            self.stats.add_request(0, 0, 0, success=False)
            raise Exception(f"AI服务错误：{error_message}")
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Claude客户端未知错误: {error_message}")
            
            # 检查是否是网络连接错误
            if any(keyword in error_message.lower() for keyword in ["connection", "network", "timeout", "unreachable"]):
                if retry_count < self.max_retries:
                    logger.warning(f"网络连接问题，尝试重试 (重试次数: {retry_count}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay * 1.5)
                    return await self._make_request(messages, system_prompt, max_tokens, temperature, retry_count + 1, api_key)
                raise Exception("网络连接失败，请检查网络设置")
            
            self.stats.add_request(0, 0, 0, success=False)
            
            # 如果错误消息已经是用户友好的，直接使用
            if error_message.startswith(("AI服务", "Claude AI", "网络连接")):
                raise
            else:
                raise Exception("AI服务暂时不可用，请稍后再试")
    
    async def _mock_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """模拟Claude响应 (开发测试用)"""
        
        # 模拟网络延迟
        await asyncio.sleep(0.5)
        
        last_message = messages[-1]["content"] if messages else ""
        
        # 简单的模拟响应逻辑 (仅在API密钥未配置时使用)
        if "策略" in last_message or "strategy" in last_message.lower():
            mock_content = """
# 简单移动平均策略

这是一个基于移动平均线交叉的简单策略示例：

```python
class SimpleMaStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.short_period = 5
        self.long_period = 20
    
    def on_bar(self, bar):
        # 计算移动平均线
        short_ma = self.sma(self.short_period)
        long_ma = self.sma(self.long_period)
        
        # 交易信号
        if short_ma > long_ma and not self.position:
            self.buy()  # 金叉买入
        elif short_ma < long_ma and self.position:
            self.sell()  # 死叉卖出
```

这是一个基础的趋势跟随策略，适合初学者理解交易策略的基本结构。
            """
        elif "分析" in last_message or "analysis" in last_message.lower():
            mock_content = """
基于当前市场数据分析:

## 市场概况
- 趋势: 震荡上涨
- 波动率: 中等
- 成交量: 正常

## 技术指标
- RSI: 65 (略显强势)
- MACD: 金叉形态
- 支撑位: $45,000
- 阻力位: $52,000

## 建议
1. 可以考虑轻仓做多
2. 设置止损在$46,000
3. 目标价位$50,000

请注意风险管理，合理配置仓位大小。
            """
        else:
            mock_content = f"""
您好！我是Trademe的AI交易助手。

您的问题: "{last_message}"

感谢您的提问！我可以帮助您：

- 📈 生成个性化交易策略代码
- 📊 进行专业市场数据分析
- 💡 解读和优化回测结果  
- 🤖 回答各类量化交易问题
- 🔍 提供技术指标使用建议
- ⚡ 实时交易信号分析

请告诉我您具体需要什么帮助，我会为您提供详细的专业建议。
            """
        
        # 模拟使用统计
        mock_usage = {
            "input_tokens": len(last_message) // 4,  # 粗略估算
            "output_tokens": len(mock_content) // 4,
            "total_tokens": (len(last_message) + len(mock_content)) // 4,
            "model": "claude-3-5-sonnet-mock",
            "response_time_ms": 500.0
        }
        
        self.stats.add_request(
            input_tokens=mock_usage["input_tokens"],
            output_tokens=mock_usage["output_tokens"],
            response_time_ms=mock_usage["response_time_ms"],
            success=True
        )
        
        return mock_content, mock_usage
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """聊天完成API"""
        
        try:
            content, usage_info = await self._make_request(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key
            )
            
            return {
                "content": content,
                "usage": usage_info,
                "model": usage_info.get("model", self.model),
                "created_at": datetime.utcnow().isoformat(),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"聊天完成失败: {str(e)}")
            return {
                "content": f"抱歉，AI服务暂时不可用: {str(e)}",
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "model": self.model,
                "created_at": datetime.utcnow().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    async def generate_strategy_code(
        self,
        description: str,
        indicators: List[str],
        timeframe: str = "1h",
        risk_level: str = "medium"
    ) -> Dict[str, Any]:
        """生成策略代码"""
        
        system_prompt = """你是一个专业的量化交易策略开发专家。请根据用户需求生成Python交易策略代码。

要求：
1. 使用BaseStrategy类作为基础
2. 代码必须安全，不包含任何危险函数或网络请求
3. 添加详细的中文注释
4. 提供策略说明和风险提示
5. 包含合理的参数设置

输出格式：
- 策略代码 (Python)
- 策略说明
- 参数说明
- 风险提示"""
        
        user_message = f"""
请生成一个交易策略，要求如下：

策略描述: {description}
技术指标: {', '.join(indicators)}
时间周期: {timeframe}
风险级别: {risk_level}

请确保代码的安全性和实用性。
        """
        
        messages = [{"role": "user", "content": user_message}]
        
        return await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3  # 代码生成使用较低温度
        )
    
    async def analyze_market_data(
        self,
        market_data: Dict[str, Any],
        symbols: List[str],
        analysis_type: str = "technical",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析市场数据"""
        
        system_prompt = """你是一个资深的加密货币市场分析师。请基于提供的市场数据进行专业分析。

分析要求：
1. 基于技术分析提供客观判断
2. 包含风险评估和概率分析
3. 提供具体的交易建议
4. 使用中文输出专业报告
5. 避免过度乐观或悲观的表述"""
        
        user_message = f"""
请分析以下市场数据：

分析类型: {analysis_type}
关注币种: {', '.join(symbols)}
市场数据: {str(market_data)[:1000]}...

请提供专业的市场分析和建议。
        """
        
        messages = [{"role": "user", "content": user_message}]
        
        return await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.5,
            api_key=api_key
        )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return self.stats.get_stats()
    
    def reset_stats(self):
        """重置统计"""
        self.stats = ClaudeUsageStats()
        logger.info("Claude使用统计已重置")


# 全局Claude客户端实例
claude_client = ClaudeClient()