"""
支付API端点单元测试
测试HTTP接口功能、参数验证、认证授权、错误处理等
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
import json

from app.main import app
from app.models.payment import USDTPaymentOrder
from app.schemas.response import SuccessResponse, ErrorResponse


class TestPaymentAPI:
    """支付API端点测试类"""
    
    def setup_method(self):
        """测试方法设置"""
        self.client = TestClient(app)
        self.test_user_token = "test_jwt_token_123456789"
        self.admin_user_token = "admin_jwt_token_123456789"
        
        # Mock认证中间件
        self.mock_user = {
            "user_id": 1,
            "email": "test@example.com",
            "membership_level": "premium",
            "is_admin": False
        }
        
        self.mock_admin = {
            "user_id": 999,
            "email": "admin@example.com", 
            "membership_level": "admin",
            "is_admin": True
        }
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.payment_order_service')
    def test_create_payment_order_endpoint(self, mock_payment_service, mock_get_user):
        """测试创建支付订单接口"""
        # Mock认证
        mock_get_user.return_value = self.mock_user
        
        # Mock服务响应
        mock_order_data = {
            "order_no": "USDT164099520012345678",
            "usdt_amount": 10.0,
            "expected_amount": 10.05,
            "network": "TRC20",
            "to_address": "TTestAPIOrderCreate123456789012345678",
            "expires_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat(),
            "status": "pending",
            "qr_code_data": "tron:TTestAPIOrderCreate123456789012345678?amount=10.05&token=USDT"
        }
        mock_payment_service.create_payment_order.return_value = mock_order_data
        
        # 请求数据
        request_data = {
            "usdt_amount": 10.0,
            "network": "TRC20",
            "add_random_suffix": True,
            "risk_level": "LOW"
        }
        
        # 发起请求
        response = self.client.post(
            "/api/v1/payments/orders",
            json=request_data,
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["message"] == "支付订单创建成功"
        assert response_data["data"]["order_no"] == mock_order_data["order_no"]
        assert response_data["data"]["usdt_amount"] == 10.0
        assert response_data["data"]["network"] == "TRC20"
        
        # 验证服务调用
        mock_payment_service.create_payment_order.assert_called_once_with(
            user_id=1,
            usdt_amount=Decimal('10.0'),
            network="TRC20",
            membership_plan_id=None,
            extra_info={'risk_level': 'LOW', 'add_random_suffix': True}
        )
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.payment_order_service')
    def test_get_payment_order_endpoint(self, mock_payment_service, mock_get_user):
        """测试获取支付订单接口"""
        # Mock认证
        mock_get_user.return_value = self.mock_user
        
        # Mock订单数据
        order_no = "USDT164099520012345678"
        mock_order_data = {
            "order_no": order_no,
            "user_id": 1,  # 与当前用户匹配
            "usdt_amount": 10.0,
            "expected_amount": 10.05,
            "actual_amount": None,
            "network": "TRC20",
            "to_address": "TTestAPIGetOrder123456789012345678",
            "status": "pending",
            "expires_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        mock_payment_service.get_payment_order.return_value = mock_order_data
        
        # 发起请求
        response = self.client.get(
            f"/api/v1/payments/orders/{order_no}",
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["data"]["order_no"] == order_no
        assert response_data["data"]["status"] == "pending"
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.payment_order_service')
    def test_get_user_payment_orders_endpoint(self, mock_payment_service, mock_get_user):
        """测试获取用户订单列表接口"""
        # Mock认证
        mock_get_user.return_value = self.mock_user
        
        # Mock订单列表
        mock_orders = [
            {
                "order_no": "USDT164099520012345679",
                "usdt_amount": 10.0,
                "network": "TRC20",
                "status": "confirmed",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "order_no": "USDT164099520012345680",
                "usdt_amount": 20.0,
                "network": "ERC20",
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }
        ]
        mock_payment_service.get_user_payment_orders.return_value = mock_orders
        
        # 发起请求（带分页参数）
        response = self.client.get(
            "/api/v1/payments/orders",
            params={"limit": 10, "offset": 0, "status": "pending"},
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert len(response_data["data"]["orders"]) == 2
        assert "pagination" in response_data["data"]
        
        # 验证服务调用参数
        mock_payment_service.get_user_payment_orders.assert_called_once_with(
            user_id=1,
            status="pending",
            limit=10,
            offset=0
        )
    
    @patch('app.api.v1.payments.admin_required')
    @patch('app.api.v1.payments.payment_order_service')
    def test_confirm_payment_order_endpoint(self, mock_payment_service, mock_admin_required):
        """测试管理员确认支付订单接口"""
        # Mock管理员认证
        mock_admin_required.return_value = self.mock_admin
        
        # Mock服务响应
        mock_payment_service.confirm_payment_order.return_value = True
        
        # 请求数据
        order_no = "USDT164099520012345681"
        request_data = {
            "transaction_hash": "tx_confirm_api_test_12345",
            "actual_amount": 10.05,
            "confirmations": 12
        }
        
        # 发起请求
        response = self.client.post(
            f"/api/v1/payments/orders/{order_no}/confirm",
            json=request_data,
            headers={"Authorization": f"Bearer {self.admin_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["message"] == "支付订单确认成功"
        assert response_data["data"]["order_no"] == order_no
        assert response_data["data"]["status"] == "confirmed"
        
        # 验证服务调用
        mock_payment_service.confirm_payment_order.assert_called_once_with(
            order_no=order_no,
            transaction_hash="tx_confirm_api_test_12345",
            actual_amount=Decimal('10.05'),
            confirmations=12
        )
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.payment_order_service')
    def test_cancel_payment_order_endpoint(self, mock_payment_service, mock_get_user):
        """测试取消支付订单接口"""
        # Mock认证
        mock_get_user.return_value = self.mock_user
        
        # Mock订单查询（验证所有权）
        order_no = "USDT164099520012345682"
        mock_order_data = {
            "order_no": order_no,
            "user_id": 1,  # 匹配当前用户
            "status": "pending"
        }
        mock_payment_service.get_payment_order.return_value = mock_order_data
        mock_payment_service.cancel_payment_order.return_value = True
        
        # 发起请求
        response = self.client.post(
            f"/api/v1/payments/orders/{order_no}/cancel",
            params={"reason": "用户主动取消"},
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["message"] == "订单取消成功"
        assert response_data["data"]["status"] == "cancelled"
        
        # 验证服务调用
        mock_payment_service.cancel_payment_order.assert_called_once_with(
            order_no, "用户主动取消"
        )
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.blockchain_monitor_service')
    def test_get_transaction_status_endpoint(self, mock_blockchain_service, mock_get_user):
        """测试查询交易状态接口"""
        # Mock认证
        mock_get_user.return_value = self.mock_user
        
        # Mock区块链服务响应
        tx_hash = "test_transaction_hash_12345"
        mock_tx_status = {
            "success": True,
            "confirmations": 15,
            "block_height": 12345,
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_blockchain_service.get_transaction_status.return_value = mock_tx_status
        
        # 发起请求
        response = self.client.get(
            f"/api/v1/payments/transactions/{tx_hash}/status",
            params={"network": "TRC20"},
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["data"]["transaction_hash"] == tx_hash
        assert response_data["data"]["network"] == "TRC20"
        assert response_data["data"]["success"] == True
        assert response_data["data"]["confirmations"] == 15
    
    @patch('app.api.v1.payments.admin_required')
    @patch('app.api.v1.payments.blockchain_monitor_service')
    def test_get_wallet_balance_endpoint(self, mock_blockchain_service, mock_admin_required):
        """测试查询钱包余额接口（管理员功能）"""
        # Mock管理员认证
        mock_admin_required.return_value = self.mock_admin
        
        # Mock区块链服务响应
        test_address = "TTestAPIBalanceQuery123456789012345678"
        mock_balance = Decimal('125.75')
        mock_blockchain_service.get_address_balance.return_value = mock_balance
        
        # 发起请求
        response = self.client.get(
            f"/api/v1/payments/wallets/{test_address}/balance",
            params={"network": "TRC20"},
            headers={"Authorization": f"Bearer {self.admin_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["data"]["address"] == test_address
        assert response_data["data"]["network"] == "TRC20"
        assert response_data["data"]["balance"] == 125.75
    
    @patch('app.api.v1.payments.admin_required')
    @patch('app.api.v1.payments.payment_order_service')
    def test_get_payment_statistics_endpoint(self, mock_payment_service, mock_admin_required):
        """测试获取支付统计接口（管理员功能）"""
        # Mock管理员认证
        mock_admin_required.return_value = self.mock_admin
        
        # Mock统计数据
        mock_stats = {
            "total_orders": 100,
            "confirmed_orders": 85,
            "pending_orders": 10,
            "expired_orders": 3,
            "cancelled_orders": 2,
            "total_amount": 1500.0,
            "confirmed_amount": 1275.0,
            "network_distribution": {"TRC20": 60, "ERC20": 25, "BEP20": 15},
            "average_confirmation_time": 4.5
        }
        mock_payment_service.get_payment_statistics.return_value = mock_stats
        
        # 发起请求
        response = self.client.get(
            "/api/v1/payments/statistics",
            params={
                "start_date": "2023-01-01T00:00:00",
                "end_date": "2023-12-31T23:59:59"
            },
            headers={"Authorization": f"Bearer {self.admin_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["data"]["total_orders"] == 100
        assert response_data["data"]["confirmed_orders"] == 85
        assert "network_distribution" in response_data["data"]
    
    @patch('app.api.v1.payments.admin_required')
    @patch('app.api.v1.payments.payment_order_service')
    def test_cleanup_expired_orders_endpoint(self, mock_payment_service, mock_admin_required):
        """测试清理过期订单接口（管理员功能）"""
        # Mock管理员认证
        mock_admin_required.return_value = self.mock_admin
        
        # Mock清理结果
        mock_payment_service.cleanup_expired_orders.return_value = 5
        
        # 发起请求
        response = self.client.post(
            "/api/v1/payments/maintenance/cleanup-expired",
            headers={"Authorization": f"Bearer {self.admin_user_token}"}
        )
        
        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["success"] == True
        assert response_data["message"] == "清理过期订单完成"
        assert response_data["data"]["cleaned_orders"] == 5
    
    def test_input_validation_create_order(self):
        """测试创建订单的输入验证"""
        # 测试无效金额
        invalid_requests = [
            {"usdt_amount": -10.0, "network": "TRC20"},  # 负数
            {"usdt_amount": 0, "network": "TRC20"},      # 零值
            {"network": "TRC20"},                        # 缺少金额
            {"usdt_amount": 10.0, "network": "INVALID"}, # 无效网络
            {"usdt_amount": 10.0},                       # 缺少网络
        ]
        
        for request_data in invalid_requests:
            response = self.client.post(
                "/api/v1/payments/orders",
                json=request_data,
                headers={"Authorization": f"Bearer {self.test_user_token}"}
            )
            
            # 应该返回400错误
            assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_authentication_required(self):
        """测试认证要求验证"""
        # 未认证请求
        response = self.client.post(
            "/api/v1/payments/orders",
            json={"usdt_amount": 10.0, "network": "TRC20"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 无效token
        response = self.client.post(
            "/api/v1/payments/orders",
            json={"usdt_amount": 10.0, "network": "TRC20"},
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.payment_order_service')
    def test_authorization_checks(self, mock_payment_service, mock_get_user):
        """测试权限检查验证"""
        # Mock普通用户
        mock_get_user.return_value = self.mock_user
        
        # Mock订单数据（属于其他用户）
        mock_order_data = {
            "order_no": "USDT164099520012345683",
            "user_id": 999,  # 不匹配当前用户ID
            "status": "pending"
        }
        mock_payment_service.get_payment_order.return_value = mock_order_data
        
        # 尝试访问他人订单
        response = self.client.get(
            "/api/v1/payments/orders/USDT164099520012345683",
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 应该返回403禁止访问
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @patch('app.api.v1.payments.get_current_user')
    @patch('app.api.v1.payments.payment_order_service')
    def test_error_handling_service_failure(self, mock_payment_service, mock_get_user):
        """测试错误处理机制"""
        # Mock认证
        mock_get_user.return_value = self.mock_user
        
        # Mock服务异常
        mock_payment_service.create_payment_order.side_effect = Exception("Database connection failed")
        
        # 发起请求
        response = self.client.post(
            "/api/v1/payments/orders",
            json={"usdt_amount": 10.0, "network": "TRC20"},
            headers={"Authorization": f"Bearer {self.test_user_token}"}
        )
        
        # 应该返回500错误
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        response_data = response.json()
        assert "创建支付订单失败" in response_data["detail"]
    
    def test_webhook_payment_confirmation(self):
        """测试支付确认Webhook"""
        # Webhook请求数据
        webhook_data = {
            "order_no": "USDT164099520012345684",
            "transaction_hash": "tx_webhook_test_12345",
            "actual_amount": 10.05
        }
        
        with patch('app.api.v1.payments.payment_order_service') as mock_payment_service:
            mock_payment_service.confirm_payment_order.return_value = True
            
            # 发起Webhook请求（无需认证）
            response = self.client.post(
                "/api/v1/payments/webhook/payment-confirmation",
                json=webhook_data
            )
            
            # 验证响应
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["status"] == "success"
            
            # 验证服务调用
            mock_payment_service.confirm_payment_order.assert_called_once_with(
                order_no=webhook_data["order_no"],
                transaction_hash=webhook_data["transaction_hash"],
                actual_amount=Decimal(str(webhook_data["actual_amount"]))
            )
    
    def test_api_response_format_consistency(self):
        """测试API响应格式一致性"""
        with patch('app.api.v1.payments.get_current_user') as mock_get_user:
            with patch('app.api.v1.payments.payment_order_service') as mock_payment_service:
                # Mock认证和服务
                mock_get_user.return_value = self.mock_user
                mock_payment_service.create_payment_order.return_value = {
                    "order_no": "TEST123",
                    "usdt_amount": 10.0,
                    "network": "TRC20",
                    "status": "pending"
                }
                
                # 发起请求
                response = self.client.post(
                    "/api/v1/payments/orders",
                    json={"usdt_amount": 10.0, "network": "TRC20"},
                    headers={"Authorization": f"Bearer {self.test_user_token}"}
                )
                
                # 验证响应格式符合SuccessResponse模式
                response_data = response.json()
                assert "success" in response_data
                assert "message" in response_data  
                assert "data" in response_data
                assert response_data["success"] == True
                assert isinstance(response_data["data"], dict)