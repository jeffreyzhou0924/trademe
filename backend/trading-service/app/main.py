"""
Trademe Trading Service - 主应用入口

集成功能:
- 交易策略管理与执行
- AI对话和策略生成  
- 市场数据采集与分发
- 回测引擎和风险管理
"""

from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import time
import uvicorn
import json
import asyncio
from typing import Dict, Set

from app.config import settings
from app.database import init_db, close_db, get_db
from app.redis_client import init_redis, close_redis
from app.api.v1 import api_router
# 暂时禁用支付自动化，专注于用户管理系统整合
# from app.services.payment_automation import payment_automation
from app.middleware.auth import get_current_user, get_current_active_user, create_access_token, AuthenticationError
from app.middleware.rate_limiting import rate_limiting_middleware
from app.middleware.structured_logging import structured_logging_middleware, business_logger
from app.schemas.user import UserLogin, UserLoginResponse, UserResponse
from app.middleware.auth import verify_jwt_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    await init_db()
    await init_redis()
    
    # 暂时禁用支付自动化，专注于用户管理系统整合
    # try:
    #     async for db in get_db():
    #         await payment_automation.initialize(db)
    #         break  # 只需要初始化一次
    #     
    #     # 启动支付自动化
    #     await payment_automation.start_automation()
    #     print("💰 USDT支付自动化系统已启动")
    #     
    # except Exception as e:
    #     print(f"⚠️  支付自动化启动失败: {e}")
    
    print("🚀 Trading Service 启动成功")
    print(f"📊 环境: {settings.environment}")
    print(f"🏠 Host: {settings.host}:{settings.port}")
    
    yield
    
    # 暂时禁用支付自动化，专注于用户管理系统整合
    # try:
    #     await payment_automation.stop_automation()
    #     print("💰 USDT支付自动化系统已停止")
    # except Exception as e:
    #     print(f"⚠️  支付自动化停止失败: {e}")
    
    await close_db()
    await close_redis()
    print("👋 Trading Service 已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Trademe Trading Service",
    description="集成交易、AI、市场数据的综合服务",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可信主机中间件（开发环境允许所有主机）
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )

# 结构化日志中间件 (最外层，优先级最高)
@app.middleware("http")
async def structured_logging_middleware_handler(request: Request, call_next):
    return await structured_logging_middleware(request, call_next)

# 速率限制中间件
@app.middleware("http")
async def rate_limiting_middleware_handler(request: Request, call_next):
    return await rate_limiting_middleware(request, call_next)

# 请求时间中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "内部服务器错误",
            "error": str(exc) if settings.debug else "服务器错误",
            "path": str(request.url)
        }
    )

# 注册路由
app.include_router(api_router, prefix="/api/v1")

# 根路径健康检查
@app.get("/")
async def root():
    return {
        "service": "Trademe Trading Service",
        "version": "1.0.0",
        "status": "running",
        "features": [
            "策略管理",
            "回测引擎", 
            "实盘交易",
            "AI对话",
            "市场数据"
        ]
    }

# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "environment": settings.environment
    }

# 用户登录端点 (简化版，用于测试认证)
@app.post("/auth/login", response_model=UserLoginResponse)
async def login(user_credentials: UserLogin, request: Request):
    """用户登录 - 简化版测试实现"""
    
    # 简化的登录逻辑 (实际应该验证数据库中的用户)
    # 这里为了快速测试，接受任何邮箱/密码组合
    if "@" not in user_credentials.email or len(user_credentials.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="邮箱格式错误或密码太短"
        )
    
    # 创建模拟用户数据
    user_data = {
        "user_id": 1,
        "email": user_credentials.email,
        "username": user_credentials.email.split("@")[0],
        "membership_level": "basic"
    }
    
    # 生成访问令牌
    access_token = create_access_token(user_data)
    
    # 创建用户响应对象
    from datetime import datetime
    user_response = UserResponse(
        id=1,
        username=user_data["username"],
        email=user_credentials.email,
        membership_level="basic",
        email_verified=True,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # 记录登录成功事件
    request_id = getattr(request.state, 'request_id', None)
    business_logger.log_user_login(1, user_credentials.email, True, request_id)
    
    return UserLoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user=user_response
    )

# 获取当前用户信息 (受保护的端点)
@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_active_user)):
    """获取当前用户信息 - 需要认证"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        membership_level=current_user.membership_level,
        email_verified=current_user.email_verified,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

# 测试认证的端点
@app.get("/auth/test")
async def test_auth(current_user=Depends(get_current_user)):
    """测试认证功能"""
    return {
        "message": "认证成功！",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "membership_level": current_user.membership_level
        },
        "timestamp": time.time()
    }

# WebSocket连接管理器
class WebSocketManager:
    def __init__(self):
        # 存储活跃连接 {connection_id: {"websocket": websocket, "user_id": user_id}}
        self.active_connections: Dict[str, Dict] = {}
        # 用户订阅管理 {user_id: set of connection_ids}
        self.user_connections: Dict[int, Set[str]] = {}
        # 订阅管理 {symbol: set of connection_ids}
        self.symbol_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, connection_id: str, user_id: int):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[connection_id] = {
            "websocket": websocket,
            "user_id": user_id
        }
        
        # 添加到用户连接映射
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        print(f"✅ WebSocket连接已接受: {connection_id} (用户: {user_id})")

    def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            connection_info = self.active_connections[connection_id]
            user_id = connection_info["user_id"]
            
            # 从用户连接映射中移除
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # 从订阅中移除
            for symbol_connections in self.symbol_subscriptions.values():
                symbol_connections.discard(connection_id)
            
            # 移除连接
            del self.active_connections[connection_id]
            print(f"❌ WebSocket连接已断开: {connection_id} (用户: {user_id})")

    async def send_personal_message(self, connection_id: str, message: dict):
        """向特定连接发送消息"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]["websocket"]
            try:
                await websocket.send_text(json.dumps(message))
                return True
            except Exception as e:
                print(f"发送消息失败 {connection_id}: {e}")
                self.disconnect(connection_id)
                return False
        return False

    async def send_to_user(self, user_id: int, message: dict):
        """向特定用户的所有连接发送消息"""
        if user_id in self.user_connections:
            failed_connections = []
            for connection_id in self.user_connections[user_id].copy():
                success = await self.send_personal_message(connection_id, message)
                if not success:
                    failed_connections.append(connection_id)
            
            # 清理失败的连接
            for failed_id in failed_connections:
                self.disconnect(failed_id)

    async def broadcast_to_symbol(self, symbol: str, message: dict):
        """向订阅特定交易对的所有连接广播消息"""
        if symbol in self.symbol_subscriptions:
            failed_connections = []
            for connection_id in self.symbol_subscriptions[symbol].copy():
                success = await self.send_personal_message(connection_id, message)
                if not success:
                    failed_connections.append(connection_id)
            
            # 清理失败的连接
            for failed_id in failed_connections:
                self.disconnect(failed_id)

    def subscribe_to_symbol(self, connection_id: str, symbol: str):
        """订阅交易对"""
        if symbol not in self.symbol_subscriptions:
            self.symbol_subscriptions[symbol] = set()
        self.symbol_subscriptions[symbol].add(connection_id)
        print(f"📊 连接 {connection_id} 订阅了 {symbol}")

    def unsubscribe_from_symbol(self, connection_id: str, symbol: str):
        """取消订阅交易对"""
        if symbol in self.symbol_subscriptions:
            self.symbol_subscriptions[symbol].discard(connection_id)
            if not self.symbol_subscriptions[symbol]:
                del self.symbol_subscriptions[symbol]
            print(f"📊 连接 {connection_id} 取消订阅 {symbol}")

    def get_stats(self):
        """获取连接统计"""
        return {
            "total_connections": len(self.active_connections),
            "total_users": len(self.user_connections),
            "total_symbols": len(self.symbol_subscriptions),
            "connections_per_user": {
                user_id: len(connections) 
                for user_id, connections in self.user_connections.items()
            }
        }

# 创建全局WebSocket管理器
ws_manager = WebSocketManager()

# WebSocket认证和实时数据端点
@app.websocket("/ws/realtime")
async def websocket_realtime_endpoint(websocket: WebSocket):
    """实时数据WebSocket端点 - 支持认证和多功能"""
    connection_id = f"conn_{int(time.time() * 1000)}"
    user_id = None
    
    try:
        # 1. 建立连接（先接受，然后等待认证）
        await websocket.accept()
        print(f"🔌 WebSocket连接请求: {connection_id}")
        
        # 2. 等待客户端发送认证信息
        auth_data = await websocket.receive_text()
        auth_message = json.loads(auth_data)
        
        if auth_message.get("type") != "auth":
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "首个消息必须是认证消息"
            }))
            await websocket.close(code=4001)
            return
        
        # 3. 验证JWT Token
        token = auth_message.get("token")
        if not token:
            await websocket.send_text(json.dumps({
                "type": "error", 
                "message": "缺少认证token"
            }))
            await websocket.close(code=4001)
            return
        
        # 验证token并获取用户信息
        try:
            payload = verify_jwt_token(token)
            user_id = payload.get("user_id")
            if not user_id:
                raise ValueError("Token中缺少用户ID")
            
            # 发送认证成功消息
            await websocket.send_text(json.dumps({
                "type": "auth_success",
                "message": "认证成功",
                "user_id": user_id
            }))
            
        except Exception as auth_error:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"认证失败: {str(auth_error)}"
            }))
            await websocket.close(code=4003)
            return
        
        # 4. 注册连接到管理器
        ws_manager.active_connections[connection_id] = {
            "websocket": websocket,
            "user_id": user_id
        }
        if user_id not in ws_manager.user_connections:
            ws_manager.user_connections[user_id] = set()
        ws_manager.user_connections[user_id].add(connection_id)
        
        # 5. 开始消息循环
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理不同类型的消息
                message_type = message.get("type")
                
                if message_type == "ping":
                    # 心跳响应
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": time.time()
                    }))
                    
                elif message_type == "subscribe":
                    # 订阅交易对
                    symbol = message.get("symbol")
                    if symbol:
                        ws_manager.subscribe_to_symbol(connection_id, symbol)
                        await websocket.send_text(json.dumps({
                            "type": "subscribed",
                            "symbol": symbol
                        }))
                        
                elif message_type == "unsubscribe":
                    # 取消订阅
                    symbol = message.get("symbol")
                    if symbol:
                        ws_manager.unsubscribe_from_symbol(connection_id, symbol)
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed", 
                            "symbol": symbol
                        }))
                
                elif message_type == "get_stats":
                    # 获取连接统计
                    stats = ws_manager.get_stats()
                    await websocket.send_text(json.dumps({
                        "type": "stats",
                        "data": stats
                    }))
                    
                else:
                    # 未知消息类型
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"未知消息类型: {message_type}"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "消息格式错误，请发送有效JSON"
                }))
            except Exception as e:
                print(f"WebSocket消息处理错误: {e}")
                break
                
    except WebSocketDisconnect:
        print(f"🔌 WebSocket客户端主动断开连接: {connection_id}")
    except Exception as e:
        print(f"❌ WebSocket连接错误: {e}")
    finally:
        # 清理连接
        ws_manager.disconnect(connection_id)

# WebSocket状态查看端点 (HTTP)
@app.get("/ws/status")
async def websocket_status():
    """获取WebSocket连接状态"""
    return {
        "websocket_manager": ws_manager.get_stats(),
        "timestamp": time.time()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )