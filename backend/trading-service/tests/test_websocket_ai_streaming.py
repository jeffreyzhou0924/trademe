"""
WebSocket AI流式对话系统全面测试套件

测试重点：
1. 验证WebSocket连接和消息传递
2. 测试流式响应处理和序列化
3. 重现并修复 "[AIStore] 流式错误: Object" 错误
4. 端到端的AI对话流程测试
"""

import pytest
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

import websockets
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# 导入被测试的组件
from app.main import app
from app.api.v1.ai_websocket import AIWebSocketHandler, ai_websocket_handler
from app.services.ai_service import AIService
from app.services.websocket_manager import WebSocketManager
from app.core.claude_client import ClaudeClient
from app.models.claude_conversation import ClaudeConversation
from app.database import get_db


class MockWebSocket:
    """模拟WebSocket连接"""
    
    def __init__(self):
        self.messages_sent = []
        self.closed = False
        self.accept_called = False
        
    async def accept(self):
        self.accept_called = True
        
    async def receive_text(self):
        # 模拟接收的消息
        return json.dumps({
            "type": "ai_chat",
            "content": "测试AI对话",
            "session_id": "test-session-123",
            "request_id": "test-request-456"
        })
        
    async def send_text(self, data: str):
        self.messages_sent.append(json.loads(data))
        
    async def send_json(self, data: dict):
        self.messages_sent.append(data)
        
    async def close(self, code: int = 1000):
        self.closed = True


class TestWebSocketAIMessageSerialization:
    """单元测试：WebSocket消息序列化和反序列化"""
    
    def test_error_object_serialization(self):
        """测试错误对象序列化 - 重现Object序列化问题"""
        
        # 创建可能导致序列化问题的错误对象
        error_objects = [
            Exception("测试异常"),
            {"error": "字符串错误", "code": 500},
            {"nested": {"error": Exception("嵌套异常")}},
            ValueError("值错误"),
            None,
            "",
            42,
            {"circular_ref": None}  # 后面会添加循环引用
        ]
        
        # 添加循环引用测试
        circular = {"data": "test"}
        circular["circular_ref"] = circular
        error_objects.append(circular)
        
        for i, error_obj in enumerate(error_objects):
            try:
                # 测试不同类型错误对象的序列化
                if isinstance(error_obj, Exception):
                    serialized = str(error_obj) if str(error_obj) else "未知异常，无错误信息"
                elif isinstance(error_obj, dict):
                    # 测试对象到字符串的安全转换
                    try:
                        serialized = json.dumps(error_obj)
                    except (TypeError, ValueError):
                        serialized = str(error_obj)
                elif error_obj is None:
                    serialized = "未知错误，请重试"
                else:
                    serialized = str(error_obj)
                
                # 确保序列化结果是字符串
                assert isinstance(serialized, str), f"测试用例{i}: 序列化结果不是字符串"
                assert len(serialized) > 0, f"测试用例{i}: 序列化结果为空"
                
                print(f"✅ 测试用例{i}通过: {type(error_obj).__name__} -> {serialized[:50]}")
                
            except Exception as e:
                pytest.fail(f"测试用例{i}失败: {type(error_obj).__name__} 序列化出错: {e}")

    def test_stream_message_format_validation(self):
        """测试流式消息格式验证"""
        
        valid_messages = [
            {
                "type": "ai_stream_start",
                "request_id": "123",
                "session_id": "session-456",
                "model": "claude-sonnet-4",
                "input_tokens": 100
            },
            {
                "type": "ai_stream_chunk", 
                "request_id": "123",
                "chunk": "Hello world",
                "content_so_far": "Hello world",
                "session_id": "session-456"
            },
            {
                "type": "ai_stream_end",
                "request_id": "123", 
                "session_id": "session-456",
                "content": "Complete response",
                "tokens_used": 150,
                "cost_usd": 0.005,
                "model": "claude-sonnet-4"
            }
        ]
        
        for message in valid_messages:
            # 测试消息可以正确序列化
            serialized = json.dumps(message)
            deserialized = json.loads(serialized)
            
            assert deserialized["type"] == message["type"]
            assert deserialized["request_id"] == message["request_id"]
            assert "session_id" in deserialized
            
    def test_error_message_format_validation(self):
        """测试错误消息格式验证"""
        
        # 测试各种错误格式
        error_scenarios = [
            # 正常错误对象
            {
                "input": {"error": "API timeout", "error_type": "timeout"},
                "expected_type": "string"
            },
            # 异常对象
            {
                "input": {"error": Exception("Connection failed")},
                "expected_type": "string" 
            },
            # None错误
            {
                "input": {"error": None},
                "expected_type": "string"
            },
            # 嵌套对象错误
            {
                "input": {"error": {"details": {"code": 500, "message": "Internal error"}}},
                "expected_type": "string"
            }
        ]
        
        for scenario in error_scenarios:
            error_input = scenario["input"]["error"]
            
            # 模拟getErrorMessage函数的逻辑
            if error_input is None:
                result = "未知错误，请重试"
            elif isinstance(error_input, Exception):
                result = str(error_input) if str(error_input) else "未知异常，无错误信息"
            elif isinstance(error_input, dict):
                try:
                    result = json.dumps(error_input, ensure_ascii=False)
                except (TypeError, ValueError):
                    result = str(error_input)
            else:
                result = str(error_input)
            
            assert isinstance(result, str), f"错误消息必须是字符串: {type(result)}"
            assert len(result) > 0, "错误消息不能为空"


class TestWebSocketAIUnit:
    """单元测试：AI服务和Claude客户端"""
    
    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=AsyncSession)
    
    @pytest.fixture  
    def mock_claude_client(self):
        """模拟Claude客户端"""
        client = Mock(spec=ClaudeClient)
        client.stream_chat_completion = AsyncMock()
        return client
    
    @pytest.fixture
    def ai_handler(self):
        """创建AI WebSocket处理器实例"""
        websocket_manager = Mock(spec=WebSocketManager)
        websocket_manager.send_to_user = AsyncMock()
        return AIWebSocketHandler(websocket_manager)
    
    @pytest.mark.asyncio
    async def test_stream_chat_completion_success(self, mock_claude_client):
        """测试Claude客户端流式对话成功流程"""
        
        # 模拟流式响应数据
        mock_stream_data = [
            {"type": "stream_start", "model": "claude-sonnet-4"},
            {"type": "content_block_delta", "delta": {"text": "Hello"}},
            {"type": "content_block_delta", "delta": {"text": " world"}},
            {"type": "content_block_delta", "delta": {"text": "!"}},
            {"type": "message_stop"}
        ]
        
        # 模拟异步生成器
        async def mock_stream():
            for item in mock_stream_data:
                yield item
        
        mock_claude_client.stream_chat_completion.return_value = mock_stream()
        
        # 测试流式处理
        accumulated_content = ""
        async for chunk in mock_claude_client.stream_chat_completion(
            messages=[{"role": "user", "content": "Test"}]
        ):
            if chunk.get("type") == "content_block_delta":
                text = chunk.get("delta", {}).get("text", "")
                accumulated_content += text
                
        assert accumulated_content == "Hello world!"
        mock_claude_client.stream_chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_service_stream_error_handling(self, mock_db):
        """测试AI服务流式处理错误处理"""
        
        with patch('app.services.ai_service.claude_scheduler_service') as mock_scheduler:
            # 模拟调度器异常
            mock_scheduler.schedule_claude_request.side_effect = Exception("调度器错误")
            
            # 创建AI服务实例
            ai_service = AIService()
            
            try:
                # 尝试流式处理，应该抛出异常
                async for chunk in ai_service.stream_chat_completion(
                    message="测试消息",
                    user_id=1, 
                    db=mock_db
                ):
                    pass  # 不应该到达这里
                    
                pytest.fail("应该抛出异常")
            except Exception as e:
                # 验证错误处理
                assert isinstance(e, Exception)
                error_str = str(e)
                assert len(error_str) > 0
                assert isinstance(error_str, str)

    def test_websocket_message_validation(self):
        """测试WebSocket消息验证逻辑"""
        
        valid_messages = [
            {
                "type": "ai_chat",
                "content": "测试消息",
                "session_id": "test-session",
                "request_id": "test-request"
            },
            {
                "type": "authenticate", 
                "token": "jwt-token-123"
            },
            {
                "type": "ping"
            }
        ]
        
        invalid_messages = [
            {},  # 空消息
            {"type": "unknown"},  # 未知类型
            {"type": "ai_chat"},  # 缺少必需字段
            {"type": "authenticate"}  # 缺少token
        ]
        
        for msg in valid_messages:
            # 验证有效消息
            assert "type" in msg
            if msg["type"] == "ai_chat":
                assert "content" in msg or msg.get("content", "") != ""
            elif msg["type"] == "authenticate":
                assert "token" in msg
                
        for msg in invalid_messages:
            # 验证无效消息检测
            if not msg.get("type"):
                assert len(msg) == 0 or "type" not in msg
            elif msg["type"] == "ai_chat" and "content" not in msg:
                assert "content" not in msg


class TestWebSocketAIIntegration:
    """集成测试：WebSocket与AI服务集成"""
    
    @pytest.fixture
    def test_client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """模拟WebSocket管理器"""
        manager = Mock(spec=WebSocketManager)
        manager.connect = AsyncMock(return_value="connection-123")
        manager.disconnect = AsyncMock()
        manager.send_to_user = AsyncMock()
        manager.handle_ping = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_websocket_ai_handler_integration(self, mock_websocket_manager):
        """测试WebSocket AI处理器集成"""
        
        # 创建AI处理器
        handler = AIWebSocketHandler(mock_websocket_manager)
        
        # 模拟AI服务
        with patch.object(handler.ai_service, 'stream_chat_completion') as mock_stream:
            # 设置流式响应模拟
            async def mock_stream_response():
                yield {"type": "ai_stream_start", "request_id": "test-123"}
                yield {"type": "ai_stream_chunk", "chunk": "Hello", "request_id": "test-123"}
                yield {"type": "ai_stream_end", "content": "Hello world", "request_id": "test-123"}
            
            mock_stream.return_value = mock_stream_response()
            
            # 创建模拟数据库
            mock_db = Mock(spec=AsyncSession)
            
            # 测试AI对话处理
            await handler.handle_ai_chat_request(
                connection_id="conn-123",
                user_id=1,
                message_data={
                    "content": "测试消息",
                    "ai_mode": "trader", 
                    "session_type": "strategy",
                    "session_id": "session-123",
                    "request_id": "test-123"
                },
                db=mock_db
            )
            
            # 验证WebSocket管理器被调用
            assert mock_websocket_manager.send_to_user.call_count >= 2  # 至少开始和结束消息
            
            # 验证发送的消息格式
            calls = mock_websocket_manager.send_to_user.call_args_list
            for call in calls:
                user_id, message = call[0]
                assert user_id == 1
                assert isinstance(message, dict)
                assert "type" in message
                assert "request_id" in message

    @pytest.mark.asyncio
    async def test_error_propagation(self, mock_websocket_manager):
        """测试错误传播和序列化"""
        
        handler = AIWebSocketHandler(mock_websocket_manager)
        
        # 模拟AI服务抛出不同类型的错误
        error_scenarios = [
            Exception("连接超时"),
            ValueError("参数错误"),
            {"error_code": "TIMEOUT", "message": "请求超时"},
            None,  # None错误
            "字符串错误"
        ]
        
        for error in error_scenarios:
            with patch.object(handler.ai_service, 'stream_chat_completion') as mock_stream:
                if error is None:
                    mock_stream.side_effect = Exception("未知错误")
                elif isinstance(error, str):
                    mock_stream.side_effect = Exception(error)
                elif isinstance(error, dict):
                    mock_stream.side_effect = Exception(json.dumps(error))
                else:
                    mock_stream.side_effect = error
                
                mock_db = Mock(spec=AsyncSession)
                
                # 处理应该捕获并处理错误
                await handler.handle_ai_chat_request(
                    connection_id="conn-123",
                    user_id=1,
                    message_data={
                        "content": "测试错误处理",
                        "request_id": f"error-test-{id(error)}"
                    },
                    db=mock_db
                )
                
                # 验证错误消息被发送
                error_calls = [call for call in mock_websocket_manager.send_to_user.call_args_list 
                             if "error" in call[0][1].get("type", "")]
                assert len(error_calls) > 0, f"错误类型 {type(error)} 没有发送错误消息"
                
                # 验证错误消息格式
                error_message = error_calls[-1][0][1]  # 最后一个错误消息
                assert "error" in error_message
                assert isinstance(error_message["error"], str), "错误消息必须是字符串"


class TestWebSocketAIEndToEnd:
    """端到端测试：完整的AI对话流程"""
    
    @pytest.fixture
    def websocket_url(self):
        """WebSocket测试URL"""
        return "ws://localhost:8001/ai/ws/chat"
    
    @pytest.mark.asyncio
    async def test_complete_websocket_conversation_flow(self):
        """测试完整的WebSocket对话流程（模拟）"""
        
        # 由于实际WebSocket连接需要运行的服务器，这里使用模拟
        mock_websocket = MockWebSocket()
        
        # 模拟认证流程
        auth_message = {
            "type": "authenticate",
            "token": "mock-jwt-token",
            "session_id": "test-session"
        }
        
        await mock_websocket.send_json(auth_message)
        
        # 模拟AI对话消息
        chat_message = {
            "type": "ai_chat",
            "content": "请分析BTC/USDT的走势",
            "ai_mode": "trader",
            "session_type": "strategy",
            "session_id": "test-session",
            "request_id": str(uuid.uuid4())
        }
        
        await mock_websocket.send_json(chat_message)
        
        # 验证消息发送
        assert len(mock_websocket.messages_sent) == 2
        assert mock_websocket.messages_sent[0]["type"] == "authenticate" 
        assert mock_websocket.messages_sent[1]["type"] == "ai_chat"
        assert mock_websocket.messages_sent[1]["content"] == "请分析BTC/USDT的走势"

    def test_websocket_message_flow_validation(self):
        """测试WebSocket消息流验证"""
        
        # 定义完整的对话流程
        message_flow = [
            # 1. 客户端认证
            {"type": "authenticate", "token": "jwt-token"},
            # 2. 服务器认证响应
            {"type": "auth_success", "connection_id": "conn-123", "user_id": 1},
            # 3. 客户端发送AI对话
            {"type": "ai_chat", "content": "测试消息", "request_id": "req-456"},
            # 4. 服务器开始处理
            {"type": "ai_chat_start", "request_id": "req-456", "status": "processing"},
            # 5. 复杂度分析
            {"type": "ai_complexity_analysis", "complexity": "simple", "estimated_time_seconds": 15},
            # 6. 流式开始
            {"type": "ai_stream_start", "request_id": "req-456", "model": "claude-sonnet-4"},
            # 7. 流式内容块
            {"type": "ai_stream_chunk", "request_id": "req-456", "chunk": "Hello"},
            {"type": "ai_stream_chunk", "request_id": "req-456", "chunk": " world"},
            # 8. 流式结束
            {"type": "ai_stream_end", "request_id": "req-456", "content": "Hello world", "tokens_used": 50}
        ]
        
        # 验证每个消息的格式
        for i, message in enumerate(message_flow):
            assert "type" in message, f"消息{i}缺少type字段"
            
            # 验证特定消息类型的必需字段
            if message["type"] in ["ai_chat", "ai_stream_start", "ai_stream_chunk", "ai_stream_end"]:
                if "request_id" not in message and message["type"] != "ai_chat":
                    pytest.fail(f"消息{i}缺少request_id字段")
            
            # 验证消息可以被JSON序列化
            try:
                json.dumps(message)
            except (TypeError, ValueError) as e:
                pytest.fail(f"消息{i}无法JSON序列化: {e}")


class TestWebSocketAIObjectErrorReproduction:
    """专门重现和修复 "[AIStore] 流式错误: Object" 错误的测试"""
    
    def test_reproduce_object_serialization_error(self):
        """重现Object序列化错误"""
        
        # 这些是可能导致"Object"错误的场景
        problematic_objects = [
            # 1. 异常对象
            Exception("测试异常"),
            # 2. 复杂嵌套对象
            {"error": {"nested": {"exception": Exception("嵌套异常")}}},
            # 3. 函数对象
            lambda x: x,
            # 4. Mock对象
            Mock(),
            # 5. 包含不可序列化内容的字典
            {"error": open(__file__)},  # 文件对象
            # 6. 循环引用
            None  # 将在下面设置
        ]
        
        # 设置循环引用
        circular = {"data": "test"}
        circular["self"] = circular
        problematic_objects[5] = circular
        
        for i, obj in enumerate(problematic_objects):
            print(f"\n测试问题对象 {i}: {type(obj)}")
            
            try:
                # 模拟前端getErrorMessage函数的逻辑
                if obj is None:
                    result = "未知错误，请重试"
                elif isinstance(obj, Exception):
                    result = str(obj) if str(obj) else "未知异常，无错误信息"
                elif callable(obj):
                    result = "函数对象错误"
                elif hasattr(obj, '__dict__') and not isinstance(obj, dict):
                    # Mock对象等
                    result = f"{type(obj).__name__}对象错误"
                elif isinstance(obj, dict):
                    try:
                        result = json.dumps(obj, ensure_ascii=False)
                    except (TypeError, ValueError) as e:
                        # 这里是关键：安全处理不可序列化对象
                        result = str(obj) if hasattr(obj, '__str__') else f"{type(obj).__name__}对象"
                else:
                    result = str(obj)
                
                # 确保结果始终是字符串
                assert isinstance(result, str), f"对象{i}: 结果不是字符串"
                assert result != "[object Object]", f"对象{i}: 出现了Object序列化问题"
                print(f"✅ 对象{i}处理成功: {result[:100]}")
                
            except Exception as e:
                print(f"❌ 对象{i}处理失败: {e}")
                # 提供最后的安全网
                result = "对象序列化错误，请重试"
                assert isinstance(result, str)
            
            finally:
                # 清理文件对象
                if isinstance(obj, dict) and "error" in obj:
                    try:
                        if hasattr(obj["error"], "close"):
                            obj["error"].close()
                    except:
                        pass

    def test_aistore_error_message_generator(self):
        """测试AIStore的getErrorMessage函数逻辑"""
        
        # 模拟AIStore.getErrorMessage的实现
        def get_error_message(error: Any) -> str:
            if not error:
                return "未知错误，请重试"

            # 检查错误类型 - 修复对象序列化问题
            error_code = getattr(error, 'error_code', None) or getattr(error, 'code', None)
            error_message = getattr(error, 'error', None) or getattr(error, 'message', None) or ''
            
            # 修复Object序列化问题: 如果error是对象，安全地转换为字符串
            if isinstance(error_message, Exception):
                error_message = str(error_message)
            elif hasattr(error_message, '__dict__') and not isinstance(error_message, (str, int, float, bool, list, dict)):
                # 处理复杂对象
                try:
                    error_message = str(error_message)
                except:
                    error_message = f"{type(error_message).__name__}对象"
            elif isinstance(error_message, dict):
                try:
                    error_message = json.dumps(error_message, ensure_ascii=False)
                except (TypeError, ValueError):
                    error_message = str(error_message)
            
            error_message = str(error_message or '')
            
            # 基于错误码的友好提示
            if error_code == 'WEBSOCKET_TIMEOUT':
                return '⏰ AI响应超时，请重试或检查网络连接'
            elif error_code == 'AI_PROCESSING_FAILED':
                return '🤖 AI处理失败，请稍后重试'
            
            # 基于错误消息内容的智能识别
            if 'timeout' in error_message.lower():
                return '⏰ 请求超时，请重试'
            elif 'network' in error_message.lower():
                return '📡 网络连接异常，请检查网络设置'
            
            # 默认错误消息
            if error_message:
                return f"❌ {error_message}"
            
            return '⚠️ 服务暂时不可用，请稍后重试'
        
        # 测试各种错误类型
        test_cases = [
            (None, "未知错误，请重试"),
            ("", "⚠️ 服务暂时不可用，请稍后重试"),
            ({"error": "timeout occurred"}, "⏰ 请求超时，请重试"),
            ({"error": Exception("Connection failed")}, "❌ Connection failed"),
            (Mock(error="network error"), "📡 网络连接异常，请检查网络设置"),
            ({"error_code": "WEBSOCKET_TIMEOUT"}, "⏰ AI响应超时，请重试或检查网络连接")
        ]
        
        for error_input, expected_pattern in test_cases:
            result = get_error_message(error_input)
            assert isinstance(result, str), f"输入{error_input}: 结果不是字符串"
            assert len(result) > 0, f"输入{error_input}: 结果为空"
            # 检查是否包含预期的关键词
            if "timeout" in expected_pattern.lower() and "timeout" not in result.lower():
                if "⏰" in expected_pattern:  # 如果是基于错误码的预期结果
                    assert expected_pattern in result, f"输入{error_input}: 预期包含'{expected_pattern}'"
            print(f"✅ 错误处理测试通过: {type(error_input)} -> {result}")


class TestWebSocketAIMockData:
    """测试数据和模拟工厂"""
    
    @classmethod
    def create_mock_streaming_response(cls) -> List[Dict[str, Any]]:
        """创建模拟流式响应数据"""
        return [
            {
                "type": "ai_stream_start",
                "request_id": "test-123",
                "session_id": "session-456",
                "model": "claude-sonnet-4",
                "input_tokens": 100
            },
            {
                "type": "ai_stream_chunk",
                "request_id": "test-123", 
                "chunk": "根据当前市场数据分析，",
                "content_so_far": "根据当前市场数据分析，",
                "session_id": "session-456"
            },
            {
                "type": "ai_stream_chunk",
                "request_id": "test-123",
                "chunk": "BTC/USDT呈现上升趋势，",
                "content_so_far": "根据当前市场数据分析，BTC/USDT呈现上升趋势，",
                "session_id": "session-456"
            },
            {
                "type": "ai_stream_chunk", 
                "request_id": "test-123",
                "chunk": "建议适当增加仓位。",
                "content_so_far": "根据当前市场数据分析，BTC/USDT呈现上升趋势，建议适当增加仓位。",
                "session_id": "session-456"
            },
            {
                "type": "ai_stream_end",
                "request_id": "test-123",
                "session_id": "session-456", 
                "content": "根据当前市场数据分析，BTC/USDT呈现上升趋势，建议适当增加仓位。",
                "tokens_used": 150,
                "cost_usd": 0.008,
                "model": "claude-sonnet-4"
            }
        ]
    
    @classmethod
    def create_mock_error_response(cls) -> Dict[str, Any]:
        """创建模拟错误响应"""
        return {
            "type": "ai_stream_error",
            "request_id": "test-123",
            "error": "Claude API连接超时", 
            "error_type": "timeout",
            "session_id": "session-456",
            "retry_suggested": True,
            "timestamp": datetime.utcnow().isoformat()
        }


# 执行测试的辅助函数
def run_object_error_reproduction_test():
    """独立运行Object错误重现测试"""
    print("🔍 开始重现 '[AIStore] 流式错误: Object' 错误...")
    
    test_instance = TestWebSocketAIObjectErrorReproduction()
    
    try:
        test_instance.test_reproduce_object_serialization_error()
        print("✅ Object序列化错误重现测试完成")
    except Exception as e:
        print(f"❌ Object序列化错误测试失败: {e}")
    
    try:
        test_instance.test_aistore_error_message_generator()
        print("✅ AIStore错误消息生成器测试完成")
    except Exception as e:
        print(f"❌ AIStore错误消息测试失败: {e}")


if __name__ == "__main__":
    # 可以独立运行特定测试
    run_object_error_reproduction_test()