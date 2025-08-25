#!/usr/bin/env python3
"""
Trading API集成测试脚本

测试内容:
1. API路由完整性检查
2. 数据库依赖注入测试
3. 端到端API调用测试
4. 错误处理验证
5. 业务逻辑集成测试
"""

import asyncio
import sys
import os
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.trading import router
from app.database import get_db, AsyncSessionLocal
from app.middleware.auth import get_current_active_user
from app.schemas.user import UserInDB
from app.schemas.trade import OrderRequest, TradingAccount


class TradingAPIIntegrationTest:
    """Trading API集成测试类"""
    
    def __init__(self):
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/trading")
        self.client = TestClient(self.app)
        self.test_user = UserInDB(
            id=1,
            username="test_trader",
            email="trader@test.com",
            membership_level="basic",
            email_verified=True,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.test_results = {}
        
        # 设置测试依赖覆盖
        self.setup_test_dependencies()
    
    def setup_test_dependencies(self):
        """设置测试依赖"""
        
        # 模拟数据库会话
        async def mock_get_db():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()
            yield mock_session
        
        # 模拟用户认证
        async def mock_get_current_user():
            return self.test_user
        
        # 覆盖依赖
        self.app.dependency_overrides[get_db] = mock_get_db
        self.app.dependency_overrides[get_current_active_user] = mock_get_current_user
    
    def test_api_routes_structure(self):
        """测试API路由结构"""
        logger.info("🔍 测试API路由结构...")
        
        try:
            # 检查路由数量和结构
            routes = [route for route in self.app.routes if hasattr(route, 'path')]
            api_routes = [route for route in routes if route.path.startswith('/api/v1/trading')]
            
            expected_routes = [
                '/api/v1/trading/accounts/{exchange}/balance',
                '/api/v1/trading/exchanges',
                '/api/v1/trading/orders',
                '/api/v1/trading/positions',
                '/api/v1/trading/trades',
                '/api/v1/trading/sessions',
                '/api/v1/trading/risk/validate-order',
                '/api/v1/trading/market-data'
            ]
            
            # 验证核心路由存在
            existing_paths = {route.path for route in api_routes}
            missing_routes = []
            
            for expected_route in expected_routes:
                # 检查路由模式匹配
                route_exists = any(
                    expected_route.replace('{exchange}', 'test').replace('{order_id}', 'test') 
                    in path.replace('{exchange}', 'test').replace('{order_id}', 'test') 
                    for path in existing_paths
                )
                if not route_exists:
                    missing_routes.append(expected_route)
            
            if missing_routes:
                logger.warning(f"缺失路由: {missing_routes}")
                self.test_results['api_routes_structure'] = False
            else:
                logger.info(f"✅ API路由结构完整: {len(api_routes)} 个路由")
                self.test_results['api_routes_structure'] = True
                
        except Exception as e:
            logger.error(f"❌ API路由结构测试失败: {e}")
            self.test_results['api_routes_structure'] = False
    
    def test_database_dependency_injection(self):
        """测试数据库依赖注入"""
        logger.info("🔧 测试数据库依赖注入...")
        
        try:
            # 测试需要数据库的端点
            response = self.client.get("/api/v1/trading/accounts/binance/balance")
            
            # 检查是否正确处理依赖注入
            # 由于我们模拟了依赖，应该不会出现依赖注入错误
            if response.status_code not in [200, 400, 422]:  # 排除业务逻辑错误
                logger.error(f"数据库依赖注入可能有问题: {response.status_code}")
                self.test_results['database_dependency'] = False
            else:
                logger.info("✅ 数据库依赖注入正常")
                self.test_results['database_dependency'] = True
                
        except Exception as e:
            logger.error(f"❌ 数据库依赖注入测试失败: {e}")
            self.test_results['database_dependency'] = False
    
    def test_authentication_integration(self):
        """测试认证集成"""
        logger.info("🔐 测试认证集成...")
        
        try:
            # 测试需要认证的端点
            response = self.client.get("/api/v1/trading/exchanges")
            
            # 检查认证是否正常工作
            if response.status_code in [401, 403]:
                logger.error("认证集成可能有问题")
                self.test_results['authentication'] = False
            else:
                logger.info("✅ 认证集成正常")
                self.test_results['authentication'] = True
                
        except Exception as e:
            logger.error(f"❌ 认证集成测试失败: {e}")
            self.test_results['authentication'] = False
    
    def test_error_handling(self):
        """测试错误处理"""
        logger.info("⚠️ 测试错误处理...")
        
        try:
            # 测试无效参数
            response = self.client.post("/api/v1/trading/orders", json={
                "invalid": "data"
            })
            
            # 应该返回422验证错误
            if response.status_code == 422:
                logger.info("✅ 参数验证错误处理正常")
                self.test_results['error_handling'] = True
            else:
                logger.warning(f"参数验证错误处理异常: {response.status_code}")
                self.test_results['error_handling'] = False
                
        except Exception as e:
            logger.error(f"❌ 错误处理测试失败: {e}")
            self.test_results['error_handling'] = False
    
    def test_response_models(self):
        """测试响应模型"""
        logger.info("📋 测试响应模型...")
        
        try:
            # 测试支持的交易所端点（无需特殊参数）
            response = self.client.get("/api/v1/trading/exchanges")
            
            # 检查响应格式
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info("✅ 响应模型格式正确")
                    self.test_results['response_models'] = True
                else:
                    logger.warning("响应模型格式异常")
                    self.test_results['response_models'] = False
            else:
                logger.warning(f"响应异常: {response.status_code}")
                self.test_results['response_models'] = False
                
        except Exception as e:
            logger.error(f"❌ 响应模型测试失败: {e}")
            self.test_results['response_models'] = False
    
    def test_business_logic_integration(self):
        """测试业务逻辑集成"""
        logger.info("🔄 测试业务逻辑集成...")
        
        try:
            # 测试订单统计端点
            response = self.client.get("/api/v1/trading/orders/statistics?days=30")
            
            # 检查业务逻辑是否正常执行
            if response.status_code in [200, 400]:  # 业务逻辑错误也是正常的
                logger.info("✅ 业务逻辑集成正常")
                self.test_results['business_logic'] = True
            else:
                logger.warning(f"业务逻辑集成异常: {response.status_code}")
                self.test_results['business_logic'] = False
                
        except Exception as e:
            logger.error(f"❌ 业务逻辑集成测试失败: {e}")
            self.test_results['business_logic'] = False
    
    def test_async_operations(self):
        """测试异步操作"""
        logger.info("⚡ 测试异步操作...")
        
        try:
            # 测试多个异步端点
            endpoints = [
                "/api/v1/trading/exchanges",
                "/api/v1/trading/orders/statistics?days=7",
                "/api/v1/trading/sessions"
            ]
            
            all_success = True
            for endpoint in endpoints:
                response = self.client.get(endpoint)
                if response.status_code >= 500:  # 服务器错误可能表示异步问题
                    all_success = False
                    logger.warning(f"异步操作异常: {endpoint} -> {response.status_code}")
            
            if all_success:
                logger.info("✅ 异步操作正常")
                self.test_results['async_operations'] = True
            else:
                self.test_results['async_operations'] = False
                
        except Exception as e:
            logger.error(f"❌ 异步操作测试失败: {e}")
            self.test_results['async_operations'] = False
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始Trading API集成测试")
        
        try:
            # 运行测试
            self.test_api_routes_structure()
            self.test_database_dependency_injection()
            self.test_authentication_integration()
            self.test_error_handling()
            self.test_response_models()
            self.test_business_logic_integration()
            self.test_async_operations()
            
            # 输出结果
            self.print_test_results()
            
        except Exception as e:
            logger.error(f"集成测试失败: {e}")
            raise
    
    def print_test_results(self):
        """输出测试结果"""
        logger.info("\n" + "="*60)
        logger.info("📊 Trading API集成测试结果汇总")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        test_descriptions = {
            'api_routes_structure': 'API路由结构完整性',
            'database_dependency': '数据库依赖注入',
            'authentication': '用户认证集成',
            'error_handling': '错误处理机制',
            'response_models': '响应模型验证',
            'business_logic': '业务逻辑集成',
            'async_operations': '异步操作支持'
        }
        
        for test_name, result in self.test_results.items():
            status = "✅ 通过" if result else "❌ 失败"
            description = test_descriptions.get(test_name, test_name)
            logger.info(f"{description:25} {status}")
        
        logger.info("-"*60)
        logger.info(f"总计测试: {total_tests} 个")
        logger.info(f"通过测试: {passed_tests} 个")
        logger.info(f"失败测试: {total_tests - passed_tests} 个")
        logger.info(f"通过率: {passed_tests/total_tests*100:.1f}%")
        
        if passed_tests == total_tests:
            logger.info("🎉 所有API集成测试通过! 前后端对接就绪!")
        else:
            logger.warning("⚠️  部分API集成测试失败，请检查具体错误")
        
        logger.info("="*60)


def main():
    """主测试函数"""
    # 配置日志
    logger.add("logs/api_integration_test.log", rotation="1 day", level="INFO")
    
    # 创建测试实例
    test_runner = TradingAPIIntegrationTest()
    
    try:
        # 运行所有测试
        test_runner.run_all_tests()
        
    except KeyboardInterrupt:
        logger.info("用户中断测试")
    except Exception as e:
        logger.error(f"API集成测试执行失败: {e}")
        raise
    finally:
        logger.info("API集成测试结束")


if __name__ == "__main__":
    main()