"""
Claude API 客户端
- 与Anthropic Claude API的核心集成
- 支持对话、分析、内容生成
- 支持流式响应和代理配置
- 企业级错误处理和重试机制
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from decimal import Decimal
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ClaudeAPIError(Exception):
    """Claude API异常基类"""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class ClaudeRateLimitError(ClaudeAPIError):
    """Claude API限流异常"""
    pass


class ClaudeQuotaExceededError(ClaudeAPIError):
    """Claude API配额超限异常"""
    pass


class ClaudeAuthenticationError(ClaudeAPIError):
    """Claude API认证异常"""
    pass


class ClaudeClient:
    """
    Claude API 客户端
    提供与 Anthropic Claude API 的完整集成
    """
    
    # Claude API 官方端点
    BASE_URL = "https://api.anthropic.com"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"  # 使用Claude Sonnet 4模型
    
    # API版本和请求头
    API_VERSION = "2023-06-01"
    
    def __init__(
        self,
        api_key: str,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        初始化Claude客户端 (优先支持外部claude-relay-service代理)
        
        Args:
            api_key: Claude API密钥 (可以是代理服务的token)
            organization_id: 组织ID (可选)
            project_id: 项目ID (可选)
            base_url: 自定义API基础URL (支持代理服务)
            timeout: 请求超时时间 (秒)
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.organization_id = organization_id
        self.project_id = project_id
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self._proxy_config: Optional[Dict] = None
        
        # 检测外部代理服务
        self.is_proxy_service = (
            base_url and (
                "claude.cloudcdn7.com" in base_url or 
                "relay" in base_url.lower() or
                "/api" in base_url
            )
        )
        
        # 配置请求头 - 优先适配外部代理服务
        if self.is_proxy_service:
            # 外部claude-relay-service格式 (优先使用)
            self._default_headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Trademe/1.0 (External Proxy)"
            }
            logger.info(f"🌐 Using external Claude proxy service: {base_url}")
        else:
            # 标准Anthropic API请求头 (备用)
            self._default_headers = {
                "x-api-key": api_key,
                "anthropic-version": self.API_VERSION,
                "content-type": "application/json"
            }
            
            if organization_id:
                self._default_headers["anthropic-org"] = organization_id
            if project_id:
                self._default_headers["anthropic-project"] = project_id
            logger.info("🔑 Using direct Anthropic API")
    
    async def __aenter__(self):
        """异步上下文管理器进入"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self.session is None or self.session.closed:
            connector_kwargs = {}
            
            # 配置代理
            if self._proxy_config:
                connector_kwargs["connector"] = aiohttp.TCPConnector()
                
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._default_headers,
                **connector_kwargs
            )
    
    async def configure_proxy(
        self,
        proxy_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        配置代理设置
        
        Args:
            proxy_url: 代理URL (如: http://proxy.example.com:8080)
            username: 代理用户名 (可选)
            password: 代理密码 (可选)
        """
        self._proxy_config = {
            "proxy_url": proxy_url,
            "username": username,
            "password": password
        }
        
        # 如果已有session，关闭并重新创建
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _calculate_request_complexity(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> str:
        """计算请求复杂度以动态调整超时时间"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        if system:
            total_chars += len(system)
        
        # 检测复杂关键词
        complex_keywords = ["策略", "代码", "分析", "算法", "回测", "交易", "指标", "MACD", "RSI", "背离"]
        content_text = " ".join(msg.get("content", "") for msg in messages)
        if system:
            content_text += " " + system
        
        complex_count = sum(1 for keyword in complex_keywords if keyword in content_text)
        
        if total_chars > 1000 or complex_count >= 2:
            return "complex"
        elif total_chars > 200 or complex_count >= 1:
            return "medium"
        else:
            return "simple"

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None,
        stream: bool = False,
        stop_sequences: Optional[List[str]] = None
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        执行对话完成请求
        
        Args:
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            model: 使用的模型名称
            max_tokens: 最大输出token数
            temperature: 温度参数 (0.0-1.0)
            system: 系统提示 (可选)
            stream: 是否使用流式响应
            stop_sequences: 停止序列列表 (可选)
            
        Returns:
            完整响应字典 或 流式响应生成器
        """
        await self._ensure_session()
        
        # 🆕 计算请求复杂度，动态调整超时和重试策略
        complexity = self._calculate_request_complexity(messages, system)
        logger.info(f"📊 请求复杂度: {complexity}")
        
        # 构建请求数据
        request_data = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            "_complexity": complexity  # 传递复杂度信息给_make_request
        }
        
        if system:
            request_data["system"] = system
        if stop_sequences:
            request_data["stop_sequences"] = stop_sequences
        
        endpoint = f"{self.base_url}/v1/messages"
        
        if stream:
            return self._stream_request(endpoint, request_data)
        else:
            return await self._make_request("POST", endpoint, request_data)
    
    async def analyze_content(
        self,
        content: str,
        analysis_type: str = "general",
        context: Optional[Dict] = None,
        model: str = None
    ) -> Dict[str, Any]:
        """
        内容分析请求
        
        Args:
            content: 要分析的内容
            analysis_type: 分析类型 (general, technical, market, etc.)
            context: 额外上下文信息
            model: 使用的模型名称
            
        Returns:
            分析结果字典
        """
        # 构建分析提示
        system_prompt = self._build_analysis_prompt(analysis_type, context)
        
        messages = [
            {"role": "user", "content": content}
        ]
        
        return await self.chat_completion(
            messages=messages,
            model=model,
            system=system_prompt,
            max_tokens=4000,
            temperature=0.3  # 分析任务使用较低温度
        )
    
    async def generate_content(
        self,
        prompt: str,
        content_type: str = "text",
        parameters: Optional[Dict] = None,
        model: str = None
    ) -> Dict[str, Any]:
        """
        内容生成请求
        
        Args:
            prompt: 生成提示
            content_type: 内容类型 (text, code, strategy, etc.)
            parameters: 生成参数
            model: 使用的模型名称
            
        Returns:
            生成结果字典
        """
        # 构建生成提示
        system_prompt = self._build_generation_prompt(content_type, parameters)
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            model=model,
            system=system_prompt,
            max_tokens=4000,
            temperature=0.8  # 生成任务使用较高温度
        )
    
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system: Optional[str] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行流式对话完成请求 (专用流式方法)
        
        这是AI服务专门调用的流式对话方法，内部调用chat_completion(stream=True)
        
        Args:
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            model: 使用的模型名称
            max_tokens: 最大输出token数
            temperature: 温度参数 (0.0-1.0)
            system: 系统提示 (可选)
            stop_sequences: 停止序列列表 (可选)
            
        Returns:
            流式响应生成器
        """
        logger.info(f"🔄 [Claude流式] 开始流式对话请求 - 模型: {model or self.DEFAULT_MODEL}")
        
        # 调用现有的chat_completion方法，设置stream=True
        async for chunk in self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            stream=True,  # 强制启用流式响应
            stop_sequences=stop_sequences
        ):
            yield chunk
        
        logger.info(f"✅ [Claude流式] 流式对话完成")
    
    async def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        执行HTTP请求 (带增强的代理504错误重试机制)
        
        Args:
            method: HTTP方法
            url: 请求URL
            data: 请求体数据
            params: URL参数
            
        Returns:
            响应数据字典
        """
        last_error = None
        
        # 🆕 基于请求复杂度动态调整重试策略
        complexity = data.get("_complexity", "medium") if data else "medium"
        
        # 根据复杂度调整超时时间
        timeout_multiplier = {
            "simple": 1.0,
            "medium": 1.5, 
            "complex": 2.5
        }.get(complexity, 1.5)
        
        # 根据复杂度调整重试次数
        retry_multiplier = {
            "simple": 1,
            "medium": 2,
            "complex": 3  # 复杂请求允许更多重试
        }.get(complexity, 2)
        
        # 针对代理服务和复杂度使用更多重试次数
        base_retries = self.max_retries * retry_multiplier
        max_retries = base_retries * 2 if self.is_proxy_service else base_retries
        
        # 动态调整session timeout
        new_timeout = int(self.timeout * timeout_multiplier)
        if hasattr(self.session, '_timeout'):
            original_timeout = self.session._timeout.total
            self.session._timeout = aiohttp.ClientTimeout(total=new_timeout)
            logger.info(f"⏱️ 动态调整超时: {original_timeout}s → {new_timeout}s (复杂度: {complexity})")
        
        # 移除内部复杂度标记，避免发送到API
        if data and "_complexity" in data:
            data = data.copy()
            del data["_complexity"]
        
        for attempt in range(max_retries + 1):
            try:
                kwargs = {}
                if data:
                    kwargs["json"] = data
                if params:
                    kwargs["params"] = params
                if self._proxy_config:
                    kwargs["proxy"] = self._proxy_config["proxy_url"]
                    if self._proxy_config.get("username"):
                        kwargs["proxy_auth"] = aiohttp.BasicAuth(
                            self._proxy_config["username"],
                            self._proxy_config["password"]
                        )
                
                async with self.session.request(method, url, **kwargs) as response:
                    response_text = await response.text()
                    
                    # 处理不同的HTTP状态码
                    if response.status == 200:
                        return json.loads(response_text)
                    elif response.status == 429:
                        # 限流错误
                        retry_after = response.headers.get("retry-after", 60)
                        if attempt < max_retries:
                            await asyncio.sleep(int(retry_after))
                            continue
                        raise ClaudeRateLimitError(
                            f"API限流，请在{retry_after}秒后重试",
                            error_code="RATE_LIMIT_EXCEEDED",
                            status_code=429
                        )
                    elif response.status == 401:
                        raise ClaudeAuthenticationError(
                            "API密钥无效或已过期",
                            error_code="INVALID_API_KEY",
                            status_code=401
                        )
                    elif response.status == 403:
                        raise ClaudeQuotaExceededError(
                            "API配额已耗尽",
                            error_code="QUOTA_EXCEEDED",
                            status_code=403
                        )
                    elif response.status == 504:
                        # 🆕 基于复杂度的智能504错误处理
                        if self.is_proxy_service and attempt < max_retries:
                            # 根据复杂度和重试次数计算等待时间
                            complexity_wait = {
                                "simple": 3,
                                "medium": 5,
                                "complex": 8  # 复杂请求需要更长等待时间
                            }.get(complexity, 5)
                            
                            # 递增等待时间：基础时间 + 重试次数递增
                            wait_time = min(complexity_wait + (attempt * 2), 45)  # 最大45秒
                            
                            logger.warning(
                                f"🔄 代理服务504超时 (复杂度: {complexity}), "
                                f"第{attempt+1}/{max_retries}次重试，等待{wait_time}秒"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        
                        # 提供更友好的错误信息
                        friendly_message = {
                            "simple": "简单请求超时，代理服务可能临时不可用",
                            "medium": "中等复杂请求超时，建议稍后重试",
                            "complex": "复杂请求超时，AI服务处理时间较长，建议简化请求或稍后重试"
                        }.get(complexity, "请求超时")
                        
                        raise ClaudeAPIError(
                            f"{friendly_message}: 已重试{attempt}次仍未成功",
                            error_code="PROXY_GATEWAY_TIMEOUT", 
                            status_code=504
                        )
                    elif response.status >= 500:
                        # 🆕 基于复杂度的其他服务器错误重试策略
                        if attempt < max_retries:
                            if not self.is_proxy_service:
                                # 标准指数退避
                                wait_time = (2 ** min(attempt, 5))
                            else:
                                # 代理服务根据复杂度调整等待时间
                                base_wait = {
                                    "simple": 2,
                                    "medium": 3,
                                    "complex": 5
                                }.get(complexity, 3)
                                wait_time = min(base_wait + attempt * 2, 20)
                            
                            logger.warning(f"🔄 服务器错误{response.status} (复杂度: {complexity}), 第{attempt+1}次重试，等待{wait_time}秒")
                            await asyncio.sleep(wait_time)
                            continue
                        raise ClaudeAPIError(
                            f"服务器错误: {response.status}",
                            error_code="SERVER_ERROR",
                            status_code=response.status
                        )
                    else:
                        # 其他客户端错误
                        try:
                            error_data = json.loads(response_text)
                            error_message = error_data.get("error", {}).get("message", response_text)
                        except:
                            error_message = response_text
                        
                        raise ClaudeAPIError(
                            f"API请求失败: {error_message}",
                            error_code="API_ERROR",
                            status_code=response.status
                        )
                        
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except json.JSONDecodeError as e:
                raise ClaudeAPIError(
                    "API响应格式错误",
                    error_code="INVALID_RESPONSE"
                )
        
        # 🆕 重试耗尽，提供基于复杂度的友好错误信息
        complexity_advice = {
            "simple": "简单请求失败，请检查网络连接",
            "medium": "中等复杂请求失败，建议稍后重试",
            "complex": "复杂请求失败，建议简化请求内容或稍后重试"
        }.get(complexity, "请求失败")
        
        raise ClaudeAPIError(
            f"{complexity_advice}，已重试{max_retries}次: {last_error}",
            error_code="MAX_RETRIES_EXCEEDED"
        )
    
    async def _stream_request(
        self,
        url: str,
        data: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行流式请求
        
        Args:
            url: 请求URL
            data: 请求数据
            
        Yields:
            流式响应数据块
        """
        await self._ensure_session()
        
        kwargs = {"json": data}
        if self._proxy_config:
            kwargs["proxy"] = self._proxy_config["proxy_url"]
            if self._proxy_config.get("username"):
                kwargs["proxy_auth"] = aiohttp.BasicAuth(
                    self._proxy_config["username"],
                    self._proxy_config["password"]
                )
        
        async with self.session.post(url, **kwargs) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ClaudeAPIError(
                    f"流式请求失败: {error_text}",
                    error_code="STREAM_ERROR",
                    status_code=response.status
                )
            
            # 处理Server-Sent Events格式
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    data_str = line[6:]  # 移除 'data: ' 前缀
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        yield chunk_data
                    except json.JSONDecodeError:
                        continue
    
    def _build_analysis_prompt(self, analysis_type: str, context: Optional[Dict]) -> str:
        """构建内容分析的系统提示"""
        base_prompt = "你是一个专业的内容分析AI助手。"
        
        if analysis_type == "technical":
            return base_prompt + "请进行技术分析，关注技术指标、图表模式和市场趋势。"
        elif analysis_type == "market":
            return base_prompt + "请进行市场分析，关注宏观经济、行业动态和投资机会。"
        elif analysis_type == "strategy":
            return base_prompt + "请分析交易策略的有效性、风险控制和优化建议。"
        else:
            return base_prompt + "请提供全面、客观的内容分析。"
    
    def _build_generation_prompt(self, content_type: str, parameters: Optional[Dict]) -> str:
        """构建内容生成的系统提示"""
        base_prompt = "你是一个专业的内容生成AI助手。"
        
        if content_type == "code":
            return base_prompt + "请生成清晰、可维护的代码，包含必要的注释和错误处理。"
        elif content_type == "strategy":
            return base_prompt + "请生成完整的交易策略代码，包含入市条件、出市条件和风险管理。"
        elif content_type == "analysis":
            return base_prompt + "请生成专业的分析报告，包含数据支撑和结论建议。"
        else:
            return base_prompt + "请生成高质量、准确的内容。"
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查 - 验证API连接和密钥有效性
        
        Returns:
            健康状态字典
        """
        try:
            # 发送简单的测试请求
            test_messages = [{"role": "user", "content": "Hello"}]
            
            start_time = time.time()
            response = await self.chat_completion(
                messages=test_messages,
                max_tokens=10,
                temperature=0.0
            )
            response_time = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "api_key_valid": True,
                "response_time_ms": response_time,
                "model": response.get("model", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except ClaudeAuthenticationError:
            return {
                "status": "unhealthy",
                "api_key_valid": False,
                "error": "API密钥无效",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "api_key_valid": None,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# 便捷函数：创建默认客户端实例
async def create_claude_client(
    api_key: str,
    organization_id: Optional[str] = None,
    project_id: Optional[str] = None
) -> ClaudeClient:
    """
    创建Claude客户端实例
    
    Args:
        api_key: API密钥
        organization_id: 组织ID (可选)
        project_id: 项目ID (可选)
        
    Returns:
        ClaudeClient实例
    """
    client = ClaudeClient(
        api_key=api_key,
        organization_id=organization_id,
        project_id=project_id
    )
    await client._ensure_session()
    return client