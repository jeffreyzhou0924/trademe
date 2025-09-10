"""
Claude API兼容端点
- 完全兼容Anthropic Claude API格式
- 支持虚拟密钥认证 (ck-格式)
- 提供标准的/v1/messages等端点
- 支持流式和非流式响应
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
import json
import time
import uuid
from decimal import Decimal
from datetime import datetime

from app.database import get_db
from app.middleware.virtual_key_auth import get_authenticated_virtual_key, security
from app.middleware.claude_proxy import ClaudeProxyMiddleware
from app.models.claude_proxy import UserClaudeKey
from app.models.user import User
from app.services.user_claude_key_service import UserClaudeKeyService

router = APIRouter()

# Claude API标准响应格式
class ClaudeMessage:
    """Claude API消息格式"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

class ClaudeUsage:
    """Claude API使用量格式"""
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class ClaudeResponse:
    """Claude API响应格式"""
    def __init__(self, 
                 id: str, 
                 content: List[Dict], 
                 model: str, 
                 role: str = "assistant",
                 stop_reason: str = "end_turn",
                 stop_sequence: str = None,
                 usage: Dict = None):
        self.id = id
        self.type = "message"
        self.role = role
        self.content = content
        self.model = model
        self.stop_reason = stop_reason
        self.stop_sequence = stop_sequence
        self.usage = usage or {}

@router.post("/v1/messages")
async def create_message(
    request: Request,
    auth: tuple[UserClaudeKey, User] = Depends(get_authenticated_virtual_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Claude API兼容的消息创建端点
    完全兼容 https://docs.anthropic.com/claude/reference/messages_post
    """
    user_key, user = auth
    
    try:
        # 解析请求体
        body = await request.json()
        
        # 验证必需字段
        if "messages" not in body or not isinstance(body["messages"], list):
            raise HTTPException(
                status_code=400, 
                detail={
                    "type": "invalid_request_error",
                    "message": "Missing required field: messages"
                }
            )
        
        if len(body["messages"]) == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "type": "invalid_request_error", 
                    "message": "Messages array cannot be empty"
                }
            )
        
        # 构建请求数据
        request_data = {
            "messages": body.get("messages", []),
            "model": body.get("model", settings.claude_model),
            "max_tokens": body.get("max_tokens", 4000),
            "temperature": body.get("temperature", 0.7),
            "system": body.get("system"),
            "stop_sequences": body.get("stop_sequences"),
            "stream": body.get("stream", False),
            "session_id": f"compat_{user.id}_{int(time.time())}",
            "ai_mode": "developer"
        }
        
        # 检查是否为流式请求
        is_stream = request_data["stream"]
        
        if is_stream:
            # 流式响应
            return StreamingResponse(
                _handle_stream_request(db, user_key, user, request_data),
                media_type="text/plain",
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Nginx不缓存流式响应
                }
            )
        else:
            # 非流式响应
            return await _handle_non_stream_request(db, user_key, user, request_data)
    
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "invalid_request_error",
                "message": "Invalid JSON in request body"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "type": "internal_server_error", 
                "message": f"Request processing failed: {str(e)}"
            }
        )

async def _handle_non_stream_request(
    db: AsyncSession,
    user_key: UserClaudeKey, 
    user: User,
    request_data: Dict[str, Any]
) -> JSONResponse:
    """处理非流式请求"""
    
    # 验证并路由请求
    proxy_middleware = ClaudeProxyMiddleware()
    validated_user_key, claude_account = await proxy_middleware.validate_and_route_request(
        db, user_key.virtual_key, request_data, "chat"
    )
    
    # 代理请求
    response = await proxy_middleware.proxy_claude_request(
        db, validated_user_key, claude_account, request_data, "chat"
    )
    
    # 转换为Claude API标准格式
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    
    # 提取响应内容
    content_text = response.get("content", response.get("text", ""))
    if isinstance(content_text, list) and len(content_text) > 0:
        # 如果已经是Claude API格式
        content = content_text
    else:
        # 转换为Claude API格式
        content = [{"type": "text", "text": str(content_text)}]
    
    # 构建标准Claude响应
    usage_info = response.get("usage", {})
    claude_response = {
        "id": message_id,
        "type": "message", 
        "role": "assistant",
        "content": content,
        "model": request_data.get("model", settings.claude_model),
        "stop_reason": response.get("stop_reason", "end_turn"),
        "stop_sequence": response.get("stop_sequence"),
        "usage": {
            "input_tokens": usage_info.get("input_tokens", 0),
            "output_tokens": usage_info.get("output_tokens", 0)
        }
    }
    
    return JSONResponse(content=claude_response)

async def _handle_stream_request(
    db: AsyncSession,
    user_key: UserClaudeKey,
    user: User, 
    request_data: Dict[str, Any]
) -> AsyncGenerator[str, None]:
    """处理流式请求"""
    
    try:
        # 验证并路由请求
        proxy_middleware = ClaudeProxyMiddleware()
        validated_user_key, claude_account = await proxy_middleware.validate_and_route_request(
            db, user_key.virtual_key, request_data, "chat"
        )
        
        # 获取流式响应生成器
        stream_generator = proxy_middleware.proxy_claude_stream_request(
            db, validated_user_key, claude_account, request_data, "chat"
        )
        
        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        
        async for chunk in stream_generator:
            # 转换为Claude API标准流式格式
            if "error" in chunk:
                # 错误事件
                error_event = {
                    "type": "error",
                    "error": chunk["error"]
                }
                yield f"data: {json.dumps(error_event)}\n\n"
            else:
                # 消息事件
                if chunk.get("choices") and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    
                    if "content" in delta or "text" in delta:
                        # 内容流式事件
                        content_delta = delta.get("content", delta.get("text", ""))
                        
                        stream_event = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "text_delta", 
                                "text": content_delta
                            }
                        }
                        yield f"data: {json.dumps(stream_event)}\n\n"
                    
                    # 检查是否结束
                    if chunk["choices"][0].get("finish_reason"):
                        # 消息结束事件
                        end_event = {
                            "type": "message_stop"
                        }
                        yield f"data: {json.dumps(end_event)}\n\n"
        
        # 流结束标识
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        # 错误事件
        error_event = {
            "type": "error",
            "error": {
                "type": "internal_server_error",
                "message": str(e)
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"

# 别名端点，兼容不同客户端
@router.post("/claude/v1/messages")
async def create_message_alias(
    request: Request,
    auth: tuple[UserClaudeKey, User] = Depends(get_authenticated_virtual_key),
    db: AsyncSession = Depends(get_db)
):
    """Claude API消息端点别名 - 兼容不同客户端"""
    return await create_message(request, auth, db)

@router.get("/v1/models") 
async def list_models(
    auth: tuple[UserClaudeKey, User] = Depends(get_authenticated_virtual_key)
):
    """列出可用的模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": settings.claude_model,
                "object": "model", 
                "created": 1677610602,
                "owned_by": "anthropic"
            },
            {
                "id": "claude-3-opus-20240229",
                "object": "model",
                "created": 1677610602, 
                "owned_by": "anthropic"
            },
            {
                "id": "claude-3-haiku-20240307",
                "object": "model",
                "created": 1677610602,
                "owned_by": "anthropic"
            }
        ]
    }

@router.get("/v1/usage")
async def get_usage_stats(
    auth: tuple[UserClaudeKey, User] = Depends(get_authenticated_virtual_key),
    db: AsyncSession = Depends(get_db)
):
    """获取API使用统计"""
    user_key, user = auth
    
    # 获取用户使用统计
    usage_stats = await UserClaudeKeyService.get_usage_statistics(db, user.id)
    
    return {
        "object": "usage",
        "total_requests": usage_stats["total_requests"],
        "successful_requests": usage_stats["successful_requests"], 
        "failed_requests": usage_stats["failed_requests"],
        "total_tokens": usage_stats["total_tokens"],
        "total_cost_usd": usage_stats["total_cost_usd"],
        "today_usage": {
            "requests": usage_stats["today_usage"]["requests"],
            "tokens": usage_stats["today_usage"]["tokens"],
            "cost_usd": usage_stats["today_usage"]["cost_usd"]
        },
        "rate_limits": {
            "daily_requests": user_key.daily_request_limit,
            "daily_tokens": user_key.daily_token_limit, 
            "daily_cost_usd": float(user_key.daily_cost_limit) if user_key.daily_cost_limit else None
        }
    }

@router.get("/v1/me")
async def get_user_info(
    auth: tuple[UserClaudeKey, User] = Depends(get_authenticated_virtual_key)
):
    """获取当前用户信息"""
    user_key, user = auth
    
    return {
        "object": "user",
        "id": f"user_{user.id}",
        "email": user.email,
        "username": user.username,
        "membership_level": user.membership_level,
        "api_key": {
            "id": user_key.id,
            "name": user_key.key_name,
            "status": user_key.status,
            "created_at": user_key.created_at.isoformat() if user_key.created_at else None
        }
    }

@router.get("/v1/key-info")
async def get_key_info(
    auth: tuple[UserClaudeKey, User] = Depends(get_authenticated_virtual_key),
    db: AsyncSession = Depends(get_db)
):
    """获取API密钥详细信息"""
    user_key, user = auth
    
    # 获取使用统计
    usage_stats = await UserClaudeKeyService.get_usage_statistics(db, user.id)
    
    return {
        "object": "api_key_info",
        "key_id": user_key.id,
        "key_name": user_key.key_name,
        "virtual_key": f"{user_key.virtual_key[:10]}...{user_key.virtual_key[-6:]}",  # 部分隐藏
        "status": user_key.status,
        "user": {
            "id": user.id,
            "username": user.username,
            "membership_level": user.membership_level
        },
        "limits": {
            "daily_requests": user_key.daily_request_limit,
            "daily_tokens": user_key.daily_token_limit,
            "daily_cost_usd": float(user_key.daily_cost_limit) if user_key.daily_cost_limit else None
        },
        "usage": usage_stats["today_usage"],
        "total_usage": {
            "requests": usage_stats["total_requests"],
            "tokens": usage_stats["total_tokens"], 
            "cost_usd": usage_stats["total_cost_usd"]
        },
        "created_at": user_key.created_at.isoformat() if user_key.created_at else None,
        "last_used_at": user_key.last_used_at.isoformat() if user_key.last_used_at else None
    }

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Trademe Claude Proxy Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "virtual_keys": True,
            "streaming": True, 
            "intelligent_routing": True,
            "cost_tracking": True
        }
    }