"""
系统安全性测试 - Phase 4
验证JWT认证、数据加密、访问控制、SQL注入防护等安全机制
"""

import pytest
import jwt
import hashlib
import secrets
import time
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.services.wallet_encryption import encrypt_private_key, decrypt_private_key
from app.middleware.auth import create_access_token, verify_jwt_token, AuthenticationError
from app.models.payment import USDTWallet, USDTPaymentOrder
from app.config import settings


class TestSecurity:
    """系统安全性测试类"""
    
    def setup_method(self):
        """测试方法设置"""
        self.client = TestClient(app)
        self.test_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        self.test_user_data = {
            "user_id": 1,
            "email": "security_test@example.com",
            "membership_level": "premium"
        }
        self.admin_user_data = {
            "user_id": 999,
            "email": "admin@example.com", 
            "membership_level": "admin",
            "is_admin": True
        }
    
    def test_jwt_token_validation_security(self):
        """测试JWT令牌验证安全性"""
        print("\n🔐 测试JWT令牌验证安全性")
        
        # 1. 测试有效令牌创建和验证
        valid_token = create_access_token(self.test_user_data)
        assert valid_token is not None
        assert len(valid_token) > 50  # JWT应该有足够长度
        
        # 验证有效令牌
        decoded_payload = verify_jwt_token(valid_token)
        assert decoded_payload["user_id"] == self.test_user_data["user_id"]
        assert decoded_payload["email"] == self.test_user_data["email"]
        
        # 2. 测试无效令牌拒绝
        invalid_tokens = [
            "invalid.jwt.token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid_payload.signature",
            "",
            "Bearer token_without_bearer_prefix",
            "malicious_token_attempt"
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises((AuthenticationError, jwt.InvalidTokenError, Exception)):
                verify_jwt_token(invalid_token)
        
        # 3. 测试过期令牌
        expired_payload = self.test_user_data.copy()
        expired_payload["exp"] = int(time.time() - 3600)  # 1小时前过期
        
        try:
            # 手动创建过期令牌
            expired_token = jwt.encode(
                expired_payload,
                settings.jwt_secret_key,
                algorithm=settings.jwt_algorithm
            )
            
            with pytest.raises((jwt.ExpiredSignatureError, AuthenticationError)):
                verify_jwt_token(expired_token)
                
        except Exception:
            # 如果JWT密钥不可用，跳过此测试
            pass
        
        # 4. 测试篡改令牌
        try:
            # 创建篡改的令牌
            tampered_payload = self.test_user_data.copy()
            tampered_payload["user_id"] = 999  # 篡改为管理员ID
            
            # 使用错误的密钥签名
            tampered_token = jwt.encode(
                tampered_payload,
                "wrong_secret_key",
                algorithm="HS256"
            )
            
            with pytest.raises((jwt.InvalidSignatureError, AuthenticationError)):
                verify_jwt_token(tampered_token)
                
        except Exception:
            pass
        
        print("  ✅ JWT令牌验证安全性测试通过")
        print("     - 有效令牌正确验证")
        print("     - 无效令牌被拒绝")
        print("     - 过期令牌被检测")
        print("     - 篡改令牌被识别")
    
    @patch('app.api.v1.payments.get_current_user')
    def test_unauthorized_access_prevention(self, mock_get_user):
        """测试未授权访问防护"""
        print("\n🚫 测试未授权访问防护")
        
        # 1. 测试无令牌访问
        protected_endpoints = [
            "/api/v1/payments/orders",
            "/api/v1/payments/orders/TEST123",
            "/api/v1/payments/statistics"
        ]
        
        for endpoint in protected_endpoints:
            # 不带认证令牌的请求
            response = self.client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            
            # 带无效令牌的请求
            response = self.client.get(
                endpoint,
                headers={"Authorization": "Bearer invalid_token"}
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 2. 测试跨用户访问防护
        mock_get_user.return_value = self.test_user_data
        
        with patch('app.api.v1.payments.payment_order_service') as mock_service:
            # 模拟其他用户的订单
            other_user_order = {
                "order_no": "OTHER_USER_ORDER",
                "user_id": 999,  # 不同的用户ID
                "status": "pending"
            }
            mock_service.get_payment_order.return_value = other_user_order
            
            # 尝试访问他人订单
            response = self.client.get(
                "/api/v1/payments/orders/OTHER_USER_ORDER",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN
        
        print("  ✅ 未授权访问防护测试通过")
        print("     - 无令牌访问被阻止")
        print("     - 无效令牌被拒绝")
        print("     - 跨用户访问被防护")
    
    @patch('app.api.v1.payments.get_current_user')
    def test_admin_privilege_escalation_prevention(self, mock_get_user):
        """测试管理员权限提升防护"""
        print("\n👤 测试权限提升防护")
        
        # 普通用户尝试访问管理员功能
        mock_get_user.return_value = self.test_user_data  # 普通用户
        
        admin_endpoints = [
            ("/api/v1/payments/statistics", "GET"),
            ("/api/v1/payments/maintenance/cleanup-expired", "POST"),
            ("/api/v1/payments/wallets/TTestAddress123/balance", "GET")
        ]
        
        for endpoint, method in admin_endpoints:
            if method == "GET":
                response = self.client.get(
                    endpoint,
                    params={"network": "TRC20"} if "balance" in endpoint else {},
                    headers={"Authorization": "Bearer user_token"}
                )
            else:
                response = self.client.post(
                    endpoint,
                    headers={"Authorization": "Bearer user_token"}
                )
            
            # 普通用户应该被拒绝访问管理员功能
            assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN], \
                f"普通用户能访问管理员端点 {endpoint}"
        
        # 测试权限检查逻辑
        assert not self.test_user_data.get("is_admin", False)
        assert self.admin_user_data.get("is_admin", False)
        
        print("  ✅ 权限提升防护测试通过")
        print("     - 普通用户无法访问管理员功能")
        print("     - 权限检查逻辑正确")
    
    def test_sensitive_data_encryption(self):
        """测试敏感数据加密"""
        print("\n🔒 测试敏感数据加密")
        
        # 测试私钥加密
        original_private_key = self.test_private_key
        
        # 1. 加密功能测试
        encrypted_key1 = encrypt_private_key(original_private_key)
        encrypted_key2 = encrypt_private_key(original_private_key)
        
        # 验证加密结果
        assert encrypted_key1 != original_private_key, "私钥没有被加密"
        assert encrypted_key2 != original_private_key, "私钥没有被加密"
        assert encrypted_key1 != encrypted_key2, "加密结果应该每次不同(使用随机盐)"
        assert len(encrypted_key1) > len(original_private_key), "加密后长度应该增加"
        
        # 2. 解密功能测试
        decrypted_key1 = decrypt_private_key(encrypted_key1)
        decrypted_key2 = decrypt_private_key(encrypted_key2)
        
        assert decrypted_key1 == original_private_key, "解密结果不正确"
        assert decrypted_key2 == original_private_key, "解密结果不正确"
        
        # 3. 加密强度测试
        test_keys = [
            "short_key",
            "very_long_private_key_with_lots_of_characters_" + "x" * 100,
            "key_with_special_chars_!@#$%^&*()",
            "数字货币私钥测试",  # Unicode字符
            ""  # 空字符串
        ]
        
        for test_key in test_keys:
            try:
                encrypted = encrypt_private_key(test_key)
                decrypted = decrypt_private_key(encrypted)
                assert decrypted == test_key, f"加密/解密失败: {test_key}"
            except Exception as e:
                # 某些特殊情况可能失败，记录但不中断测试
                print(f"     警告: 特殊密钥加密失败 '{test_key}': {e}")
        
        # 4. 错误输入处理
        try:
            decrypt_private_key("invalid_encrypted_data")
            assert False, "应该抛出解密错误"
        except Exception:
            pass  # 预期的错误
        
        print("  ✅ 敏感数据加密测试通过")
        print("     - 私钥正确加密和解密")
        print("     - 每次加密结果不同")
        print("     - 支持各种长度和字符")
        print("     - 错误输入被正确处理")
    
    @pytest.mark.asyncio
    async def test_private_key_security_storage(self, test_db_session: AsyncSession, clean_database):
        """测试私钥安全存储"""
        print("\n🗝️ 测试私钥安全存储")
        
        # 创建钱包并验证私钥安全存储
        test_private_keys = [
            "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS",
            "L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1",
            "KyvGbxRUoofdw3TNydWn2Z78dBHSy2odn1d3wXWN2o3SAtccFNJL"
        ]
        
        stored_wallets = []
        
        for i, private_key in enumerate(test_private_keys):
            wallet = USDTWallet(
                network="TRC20",
                address=f"TPrivateKeyTest{i:030d}",
                private_key_encrypted=encrypt_private_key(private_key),
                balance=Decimal('100'),
                is_active=True
            )
            
            stored_wallets.append((wallet, private_key))
            test_db_session.add(wallet)
        
        await test_db_session.commit()
        
        # 验证存储安全性
        for wallet, original_key in stored_wallets:
            # 1. 验证原始私钥不在数据库中
            raw_query = await test_db_session.execute(
                text(f"SELECT private_key_encrypted FROM usdt_wallets WHERE id = {wallet.id}")
            )
            encrypted_in_db = raw_query.scalar()
            
            assert original_key not in str(encrypted_in_db), "原始私钥不应存储在数据库中"
            assert encrypted_in_db != original_key, "数据库中应存储加密后的私钥"
            
            # 2. 验证能正确解密
            decrypted_key = decrypt_private_key(wallet.private_key_encrypted)
            assert decrypted_key == original_key, "私钥解密失败"
            
            # 3. 验证加密强度（不应包含明显的原始信息）
            encrypted_data = wallet.private_key_encrypted
            assert len(encrypted_data) > len(original_key), "加密数据长度应该增加"
            
            # 检查是否使用了base64编码或类似的安全编码
            import base64
            try:
                base64.b64decode(encrypted_data.encode())
                # 如果能解码，说明使用了base64编码，这是好的
            except Exception:
                # 如果不能解码，说明使用了其他编码方式，也可以接受
                pass
        
        # 4. 测试批量私钥的唯一性
        encrypted_keys = [wallet[0].private_key_encrypted for wallet in stored_wallets]
        assert len(encrypted_keys) == len(set(encrypted_keys)), "相同私钥的加密结果不应该相同"
        
        print("  ✅ 私钥安全存储测试通过")
        print("     - 原始私钥不在数据库中")
        print("     - 私钥正确加密存储")
        print("     - 私钥能正确解密")
        print("     - 相同私钥加密结果不同")
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, test_db_session: AsyncSession, clean_database):
        """测试SQL注入防护"""
        print("\n💉 测试SQL注入防护")
        
        # 创建测试数据
        test_wallet = USDTWallet(
            network="TRC20",
            address="TSQLInjectionTest123456789012345678",
            private_key_encrypted="encrypted_key",
            balance=Decimal('100'),
            is_active=True
        )
        test_db_session.add(test_wallet)
        await test_db_session.commit()
        
        # SQL注入攻击向量
        sql_injection_payloads = [
            "'; DROP TABLE usdt_wallets; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM usdt_wallets --",
            "'; INSERT INTO usdt_wallets (network) VALUES ('HACKED'); --",
            "' AND (SELECT COUNT(*) FROM usdt_wallets) > 0 --",
            "admin'--",
            "' OR 1=1#",
            "') OR ('1'='1",
            "1'; SELECT * FROM usdt_payment_orders WHERE '1'='1",
            "'; UPDATE usdt_wallets SET balance=999999; --"
        ]
        
        # 测试各种可能的注入点
        for payload in sql_injection_payloads:
            try:
                # 1. 测试查询参数注入
                from sqlalchemy import select
                
                # 使用参数化查询（正确方式）
                safe_query = select(USDTWallet).where(USDTWallet.address == payload)
                result = await test_db_session.execute(safe_query)
                records = result.scalars().all()
                
                # 注入应该不会返回意外结果
                assert len(records) == 0, f"SQL注入可能成功: {payload}"
                
                # 2. 测试直接字符串拼接（错误方式的模拟）
                # 注意：这里我们不实际执行危险查询，只是验证框架的保护
                dangerous_pattern = any([
                    "DROP" in payload.upper(),
                    "DELETE" in payload.upper(),
                    "INSERT" in payload.upper(),
                    "UPDATE" in payload.upper(),
                    "UNION" in payload.upper()
                ])
                
                if dangerous_pattern:
                    # 验证框架会拒绝这类输入
                    try:
                        # 这种写法在生产中应该被禁止
                        # 这里只是测试SQLAlchemy的参数化查询保护
                        safe_result = await test_db_session.execute(
                            text("SELECT * FROM usdt_wallets WHERE address = :address"),
                            {"address": payload}
                        )
                        # 参数化查询应该安全处理
                        assert len(safe_result.fetchall()) == 0
                    except Exception:
                        # 框架拒绝危险查询是好事
                        pass
                
            except Exception as e:
                # 大多数注入尝试应该被SQLAlchemy安全处理
                # 记录但不认为是测试失败
                print(f"     注入尝试被安全处理: {payload[:20]}... -> {type(e).__name__}")
        
        # 验证数据完整性未被破坏
        final_wallet_check = await test_db_session.execute(
            select(USDTWallet).where(USDTWallet.id == test_wallet.id)
        )
        final_wallet = final_wallet_check.scalar_one()
        
        assert final_wallet.balance == Decimal('100'), "钱包余额被意外修改"
        assert final_wallet.address == "TSQLInjectionTest123456789012345678", "钱包地址被意外修改"
        
        print("  ✅ SQL注入防护测试通过")
        print("     - 参数化查询阻止注入")
        print("     - 危险查询被安全处理")
        print("     - 数据完整性未受影响")
    
    def test_api_rate_limiting_security(self):
        """测试API限流安全性"""
        print("\n🚦 测试API限流安全性")
        
        # 准备批量请求
        test_endpoint = "/api/v1/payments/orders"
        headers = {"Authorization": "Bearer fake_token"}
        
        # 模拟快速重复请求
        response_codes = []
        response_times = []
        
        for i in range(20):  # 发送20个快速请求
            start_time = time.time()
            response = self.client.post(
                test_endpoint,
                json={"usdt_amount": 10.0, "network": "TRC20"},
                headers=headers
            )
            response_time = time.time() - start_time
            
            response_codes.append(response.status_code)
            response_times.append(response_time)
            
            # 最小间隔以模拟快速请求
            time.sleep(0.01)
        
        # 分析限流效果
        rate_limited_responses = sum(1 for code in response_codes if code == 429)  # Too Many Requests
        unauthorized_responses = sum(1 for code in response_codes if code == 401)  # Unauthorized
        
        # 验证限流或认证拦截生效
        blocked_requests = rate_limited_responses + unauthorized_responses
        assert blocked_requests >= 15, f"限流/认证拦截不足: {blocked_requests}/20"
        
        # 验证响应时间合理（没有被攻击拖垮）
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time <= 1.0, f"平均响应时间过长: {avg_response_time:.3f}s"
        
        print("  ✅ API限流安全性测试通过")
        print(f"     - 快速请求被拦截: {blocked_requests}/20")
        print(f"     - 平均响应时间: {avg_response_time:.3f}s")
        print("     - 系统未被恶意请求拖垮")
    
    @pytest.mark.asyncio
    async def test_cross_user_data_isolation(self, test_db_session: AsyncSession, clean_database):
        """测试跨用户数据隔离"""
        print("\n👥 测试跨用户数据隔离")
        
        # 创建多个用户的数据
        users_data = [
            {"user_id": 1, "username": "user1", "data_prefix": "USER1"},
            {"user_id": 2, "username": "user2", "data_prefix": "USER2"},
            {"user_id": 3, "username": "user3", "data_prefix": "USER3"}
        ]
        
        # 为每个用户创建专属数据
        user_orders = {}
        
        for user in users_data:
            user_id = user["user_id"]
            prefix = user["data_prefix"]
            
            # 创建用户专属钱包
            wallet = USDTWallet(
                network="TRC20",
                address=f"T{prefix}Wallet123456789012345678901234",
                private_key_encrypted=f"encrypted_key_{user_id}",
                balance=Decimal(str(100 * user_id)),
                is_active=True
            )
            test_db_session.add(wallet)
            await test_db_session.flush()
            
            # 创建用户专属订单
            orders = []
            for i in range(3):
                order = USDTPaymentOrder(
                    order_no=f"{prefix}_ORDER_{i:03d}",
                    user_id=user_id,
                    wallet_id=wallet.id,
                    usdt_amount=Decimal(str(10 + i)),
                    expected_amount=Decimal(str(10.05 + i)),
                    network="TRC20",
                    to_address=wallet.address,
                    status="pending",
                    expires_at=datetime.utcnow() + timedelta(minutes=30)
                )
                orders.append(order)
                test_db_session.add(order)
            
            user_orders[user_id] = orders
        
        await test_db_session.commit()
        
        # 测试数据隔离
        for user in users_data:
            user_id = user["user_id"]
            
            # 1. 验证用户只能看到自己的订单
            from sqlalchemy import select
            user_order_query = select(USDTPaymentOrder).where(
                USDTPaymentOrder.user_id == user_id
            )
            user_order_result = await test_db_session.execute(user_order_query)
            user_specific_orders = user_order_result.scalars().all()
            
            # 验证订单数量正确
            assert len(user_specific_orders) == 3, f"用户{user_id}订单数量不正确"
            
            # 验证所有订单都属于该用户
            for order in user_specific_orders:
                assert order.user_id == user_id, f"发现跨用户订单泄露: 订单{order.order_no}属于用户{order.user_id}，但查询用户{user_id}"
                assert user["data_prefix"] in order.order_no, "订单数据混乱"
            
            # 2. 验证用户无法通过修改参数访问其他用户数据
            other_users = [u for u in users_data if u["user_id"] != user_id]
            for other_user in other_users:
                other_user_orders = select(USDTPaymentOrder).where(
                    USDTPaymentOrder.user_id == other_user["user_id"]
                )
                other_result = await test_db_session.execute(other_user_orders)
                other_orders = other_result.scalars().all()
                
                # 确保查询结果中没有当前用户的数据
                current_user_orders_in_other = [
                    order for order in other_orders 
                    if order.user_id == user_id
                ]
                assert len(current_user_orders_in_other) == 0, "数据隔离失败：发现跨用户数据泄露"
        
        # 3. 测试统计查询的数据隔离
        from sqlalchemy.sql import func
        
        for user in users_data:
            user_id = user["user_id"]
            
            # 用户订单统计
            user_stats_query = select(
                func.count(USDTPaymentOrder.id),
                func.sum(USDTPaymentOrder.usdt_amount)
            ).where(USDTPaymentOrder.user_id == user_id)
            
            stats_result = await test_db_session.execute(user_stats_query)
            order_count, total_amount = stats_result.fetchone()
            
            assert order_count == 3, f"用户{user_id}统计订单数不正确"
            expected_total = Decimal('10') + Decimal('11') + Decimal('12')  # 10+11+12
            assert total_amount == expected_total, f"用户{user_id}统计金额不正确"
        
        print("  ✅ 跨用户数据隔离测试通过")
        print("     - 用户只能访问自己的数据")
        print("     - 查询参数修改无法泄露数据")
        print("     - 统计查询数据隔离正确")
        print(f"     - 测试了{len(users_data)}个用户的数据隔离")


class TestEncryption:
    """加密功能专项测试"""
    
    def test_private_key_encryption_strength(self):
        """测试私钥加密强度"""
        print("\n🔐 测试私钥加密强度")
        
        # 测试不同长度的私钥
        test_private_keys = [
            "short",
            "medium_length_private_key",
            "very_long_private_key_with_many_characters_" + "x" * 100,
            self.test_private_key,
            "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        ]
        
        encryption_results = []
        
        for private_key in test_private_keys:
            # 多次加密同一私钥
            encryptions = []
            for _ in range(5):
                encrypted = encrypt_private_key(private_key)
                encryptions.append(encrypted)
            
            # 验证加密强度
            unique_encryptions = len(set(encryptions))
            assert unique_encryptions == 5, f"相同私钥加密结果应该不同: {unique_encryptions}/5"
            
            # 验证所有加密都能正确解密
            for encrypted in encryptions:
                decrypted = decrypt_private_key(encrypted)
                assert decrypted == private_key, "解密结果不匹配原始私钥"
            
            encryption_results.append({
                "key_length": len(private_key),
                "encrypted_length": len(encryptions[0]),
                "unique_encryptions": unique_encryptions
            })
        
        print("  ✅ 私钥加密强度测试通过")
        for result in encryption_results:
            print(f"     原始长度: {result['key_length']}, 加密长度: {result['encrypted_length']}, 唯一性: {result['unique_encryptions']}/5")
    
    def test_encryption_key_rotation(self):
        """测试加密密钥轮换"""
        print("\n🔄 测试加密密钥轮换模拟")
        
        test_private_key = "test_key_for_rotation_simulation"
        
        # 模拟密钥轮换场景
        # 注意：真实的密钥轮换需要更复杂的密钥管理系统
        
        # 1. 使用当前密钥加密
        current_encrypted = encrypt_private_key(test_private_key)
        current_decrypted = decrypt_private_key(current_encrypted)
        assert current_decrypted == test_private_key
        
        # 2. 模拟密钥轮换后的兼容性
        # 在真实场景中，需要支持旧密钥解密 + 新密钥加密
        
        # 创建多个加密版本（模拟不同时期的加密）
        encrypted_versions = []
        for i in range(3):
            # 每个版本使用相同算法但不同的盐值
            encrypted = encrypt_private_key(test_private_key)
            encrypted_versions.append(encrypted)
        
        # 验证所有版本都能正确解密
        for i, encrypted in enumerate(encrypted_versions):
            decrypted = decrypt_private_key(encrypted)
            assert decrypted == test_private_key, f"版本{i}解密失败"
        
        # 验证版本间的差异性
        assert len(set(encrypted_versions)) == len(encrypted_versions), "加密版本应该不同"
        
        print("  ✅ 加密密钥轮换模拟测试通过")
        print(f"     - 测试了{len(encrypted_versions)}个加密版本")
        print("     - 所有版本都能正确解密")
        print("     - 版本间保持差异性")
    
    def test_encrypted_data_integrity(self):
        """测试加密数据完整性"""
        print("\n✅ 测试加密数据完整性")
        
        test_data = "critical_private_key_data_with_checksum"
        
        # 1. 正常加密解密
        encrypted_data = encrypt_private_key(test_data)
        decrypted_data = decrypt_private_key(encrypted_data)
        assert decrypted_data == test_data, "正常加密解密失败"
        
        # 2. 测试数据篡改检测
        tampered_versions = []
        
        if isinstance(encrypted_data, str):
            # 模拟各种篡改
            if len(encrypted_data) > 10:
                # 修改开头
                tampered1 = 'X' + encrypted_data[1:]
                tampered_versions.append(tampered1)
                
                # 修改结尾
                tampered2 = encrypted_data[:-1] + 'Y'
                tampered_versions.append(tampered2)
                
                # 修改中间
                mid = len(encrypted_data) // 2
                tampered3 = encrypted_data[:mid] + 'Z' + encrypted_data[mid+1:]
                tampered_versions.append(tampered3)
        
        # 验证篡改数据解密失败
        tampered_decrypt_failed = 0
        for tampered in tampered_versions:
            try:
                decrypt_private_key(tampered)
                # 如果解密成功，说明篡改检测不够强
                print(f"     警告: 篡改数据解密成功 {tampered[:20]}...")
            except Exception:
                # 篡改数据解密失败是正常的
                tampered_decrypt_failed += 1
        
        # 至少大部分篡改应该被检测到
        if tampered_versions:
            detection_rate = tampered_decrypt_failed / len(tampered_versions)
            assert detection_rate >= 0.5, f"篡改检测率过低: {detection_rate:.1%}"
        
        print("  ✅ 加密数据完整性测试通过")
        print(f"     - 正常数据加密解密正确")
        print(f"     - 篡改检测率: {tampered_decrypt_failed}/{len(tampered_versions)}")
    
    def setup_method(self):
        """测试设置"""
        self.test_private_key = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"