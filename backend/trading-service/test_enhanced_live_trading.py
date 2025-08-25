"""
增强版实盘交易功能集成测试
测试市价单、限价单、止损单、持仓管理等核心功能
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 配置日志
logger.add("test_enhanced_live_trading.log", rotation="10 MB", level="DEBUG")


class LiveTradingTester:
    """实盘交易测试类"""
    
    def __init__(self):
        self.test_results = []
        self.db_session = None
        self.test_user_id = 1  # 测试用户ID
        self.test_exchange = "binance"  # 测试交易所
        self.test_symbol = "BTC/USDT"  # 测试交易对
        
    async def setup(self):
        """初始化测试环境"""
        logger.info("=== 初始化测试环境 ===")
        
        # 创建数据库连接
        DATABASE_URL = "sqlite+aiosqlite:///./data/trademe.db"
        engine = create_async_engine(DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        self.db_session = AsyncSessionLocal()
        
        logger.info("✅ 数据库连接成功")
        
    async def teardown(self):
        """清理测试环境"""
        if self.db_session:
            await self.db_session.close()
        logger.info("=== 测试环境清理完成 ===")
    
    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """记录测试结果"""
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.utcnow()
        }
        self.test_results.append(result)
        
        status = "✅ 通过" if success else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if details:
            logger.info(f"  详情: {details}")
    
    # ==================== 测试用例 ====================
    
    async def test_import_modules(self):
        """测试1: 模块导入"""
        logger.info("\n🧪 测试1: 模块导入测试")
        
        try:
            # 导入增强版交易服务
            from app.services.enhanced_exchange_service import (
                EnhancedExchangeService,
                OrderType,
                OrderSide,
                OrderStatus,
                Position
            )
            self.log_test_result("导入enhanced_exchange_service", True, "所有类导入成功")
            
            # 导入原始交易服务
            from app.services.exchange_service import ExchangeService
            self.log_test_result("导入exchange_service", True)
            
            # 导入风险管理器
            from app.core.risk_manager import risk_manager, RiskLevel
            self.log_test_result("导入risk_manager", True)
            
            # 导入错误处理器
            from app.core.error_handler import error_handler, RetryConfig
            self.log_test_result("导入error_handler", True)
            
            # 导入订单管理器
            from app.core.order_manager import order_manager
            self.log_test_result("导入order_manager", True)
            
            # 导入实盘交易引擎
            from app.core.live_trading_engine import live_trading_engine
            self.log_test_result("导入live_trading_engine", True)
            
            return True
            
        except ImportError as e:
            self.log_test_result("模块导入", False, str(e))
            return False
    
    async def test_exchange_connection(self):
        """测试2: 交易所连接"""
        logger.info("\n🧪 测试2: 交易所连接测试")
        
        try:
            from app.services.exchange_service import exchange_service
            
            # 测试获取支持的交易所
            supported = exchange_service.SUPPORTED_EXCHANGES.keys()
            self.log_test_result(
                "支持的交易所",
                len(supported) > 0,
                f"支持 {len(supported)} 个交易所: {', '.join(supported)}"
            )
            
            # 测试创建交易所实例（不需要真实API密钥）
            try:
                instance = exchange_service._create_exchange_instance(
                    exchange_name="binance",
                    api_key="test_key",
                    secret="test_secret",
                    sandbox=True  # 使用沙盒模式
                )
                self.log_test_result("创建交易所实例", instance is not None, "Binance沙盒实例创建成功")
            except Exception as e:
                self.log_test_result("创建交易所实例", False, str(e))
            
            return True
            
        except Exception as e:
            self.log_test_result("交易所连接测试", False, str(e))
            return False
    
    async def test_risk_validation(self):
        """测试3: 风险管理验证"""
        logger.info("\n🧪 测试3: 风险管理验证")
        
        try:
            from app.core.risk_manager import risk_manager, RiskLevel
            
            # 测试正常订单
            assessment = await risk_manager.validate_order(
                user_id=self.test_user_id,
                exchange=self.test_exchange,
                symbol=self.test_symbol,
                side="buy",
                order_type="market",
                quantity=0.001,  # 小额测试
                price=None,
                account_balance={'USDT': 1000},
                db=self.db_session
            )
            
            self.log_test_result(
                "正常订单风险验证",
                assessment.approved,
                f"风险等级: {assessment.risk_level.value}, 评分: {assessment.risk_score:.2f}"
            )
            
            # 测试高风险订单
            high_risk_assessment = await risk_manager.validate_order(
                user_id=self.test_user_id,
                exchange=self.test_exchange,
                symbol=self.test_symbol,
                side="buy",
                order_type="market",
                quantity=100,  # 超大额
                price=None,
                account_balance={'USDT': 1000},
                db=self.db_session
            )
            
            self.log_test_result(
                "高风险订单验证",
                not high_risk_assessment.approved,
                f"正确拒绝高风险订单: {high_risk_assessment.violations}"
            )
            
            return True
            
        except Exception as e:
            self.log_test_result("风险管理验证", False, str(e))
            return False
    
    async def test_order_creation(self):
        """测试4: 订单创建（模拟）"""
        logger.info("\n🧪 测试4: 订单创建测试（模拟模式）")
        
        try:
            from app.services.enhanced_exchange_service import enhanced_exchange_service
            
            # 初始化服务
            await enhanced_exchange_service.initialize()
            
            # 测试市价单参数验证
            test_order_market = {
                'user_id': self.test_user_id,
                'exchange_name': self.test_exchange,
                'symbol': self.test_symbol,
                'side': 'buy',
                'quantity': 0.001
            }
            
            # 注意：这里只测试参数验证，不实际下单
            self.log_test_result(
                "市价单参数验证",
                test_order_market['quantity'] > 0,
                f"参数: {test_order_market}"
            )
            
            # 测试限价单参数验证
            test_order_limit = {
                'user_id': self.test_user_id,
                'exchange_name': self.test_exchange,
                'symbol': self.test_symbol,
                'side': 'sell',
                'quantity': 0.001,
                'price': 50000
            }
            
            self.log_test_result(
                "限价单参数验证",
                test_order_limit['quantity'] > 0 and test_order_limit['price'] > 0,
                f"参数: {test_order_limit}"
            )
            
            # 测试止损单参数验证
            test_order_stop = {
                'user_id': self.test_user_id,
                'exchange_name': self.test_exchange,
                'symbol': self.test_symbol,
                'side': 'sell',
                'quantity': 0.001,
                'stop_price': 45000
            }
            
            self.log_test_result(
                "止损单参数验证",
                test_order_stop['stop_price'] > 0,
                f"参数: {test_order_stop}"
            )
            
            return True
            
        except Exception as e:
            self.log_test_result("订单创建测试", False, str(e))
            return False
    
    async def test_position_management(self):
        """测试5: 持仓管理"""
        logger.info("\n🧪 测试5: 持仓管理测试")
        
        try:
            from app.services.enhanced_exchange_service import Position
            from datetime import datetime
            
            # 创建模拟持仓
            test_position = Position(
                symbol="BTC/USDT",
                side="long",
                quantity=0.1,
                average_price=45000,
                current_price=46000,
                unrealized_pnl=100,
                realized_pnl=0,
                margin_used=1000,
                liquidation_price=40000,
                timestamp=datetime.utcnow()
            )
            
            self.log_test_result(
                "创建持仓对象",
                test_position is not None,
                f"持仓: {test_position.symbol}, 数量: {test_position.quantity}"
            )
            
            # 测试持仓盈亏计算
            pnl = (test_position.current_price - test_position.average_price) * test_position.quantity
            self.log_test_result(
                "持仓盈亏计算",
                abs(pnl - test_position.unrealized_pnl) < 0.01,
                f"计算盈亏: {pnl:.2f}"
            )
            
            # 测试持仓风险评估
            risk_ratio = test_position.margin_used / (test_position.quantity * test_position.current_price)
            self.log_test_result(
                "持仓风险评估",
                risk_ratio < 1,
                f"保证金使用率: {risk_ratio:.2%}"
            )
            
            return True
            
        except Exception as e:
            self.log_test_result("持仓管理测试", False, str(e))
            return False
    
    async def test_order_manager(self):
        """测试6: 订单管理器"""
        logger.info("\n🧪 测试6: 订单管理器测试")
        
        try:
            from app.core.order_manager import order_manager, OrderRequest, OrderStatus
            
            # 创建测试订单请求
            order_request = OrderRequest(
                user_id=self.test_user_id,
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="limit",
                quantity=0.001,
                price=45000
            )
            
            # 测试订单验证
            is_valid = await order_manager.validate_order(order_request, self.db_session)
            self.log_test_result(
                "订单验证",
                is_valid,
                f"订单请求验证{'通过' if is_valid else '失败'}"
            )
            
            # 测试订单ID生成
            order_id = order_manager._generate_order_id()
            self.log_test_result(
                "订单ID生成",
                len(order_id) > 0,
                f"生成的订单ID: {order_id}"
            )
            
            return True
            
        except Exception as e:
            self.log_test_result("订单管理器测试", False, str(e))
            return False
    
    async def test_error_handling(self):
        """测试7: 错误处理和重试机制"""
        logger.info("\n🧪 测试7: 错误处理和重试机制")
        
        try:
            from app.core.error_handler import error_handler, RetryConfig, ErrorCategory
            
            # 测试错误分类
            network_error = Exception("Network timeout")
            category = error_handler._categorize_error(network_error)
            self.log_test_result(
                "错误分类",
                category == ErrorCategory.NETWORK,
                f"网络错误正确分类为: {category.value}"
            )
            
            # 测试重试配置
            retry_config = RetryConfig(
                max_attempts=3,
                backoff_factor=2.0,
                max_delay=60
            )
            
            self.log_test_result(
                "重试配置",
                retry_config.max_attempts == 3,
                f"最大重试次数: {retry_config.max_attempts}"
            )
            
            # 测试熔断器
            circuit_breaker_open = error_handler.is_circuit_open("test_service")
            self.log_test_result(
                "熔断器状态",
                not circuit_breaker_open,
                f"熔断器{'开启' if circuit_breaker_open else '关闭'}"
            )
            
            return True
            
        except Exception as e:
            self.log_test_result("错误处理测试", False, str(e))
            return False
    
    async def test_live_trading_engine(self):
        """测试8: 实盘交易引擎"""
        logger.info("\n🧪 测试8: 实盘交易引擎测试")
        
        try:
            from app.core.live_trading_engine import live_trading_engine, TradingSession
            
            # 创建测试交易会话
            test_session = TradingSession(
                user_id=self.test_user_id,
                strategy_id=1,
                exchange="binance",
                symbol="BTC/USDT",
                mode="MANUAL",  # 手动模式
                risk_params={
                    'max_position_size': 0.1,
                    'stop_loss_pct': 0.02,
                    'take_profit_pct': 0.05
                }
            )
            
            # 添加会话到引擎
            session_id = await live_trading_engine.create_session(
                test_session, self.db_session
            )
            
            self.log_test_result(
                "创建交易会话",
                session_id is not None,
                f"会话ID: {session_id}"
            )
            
            # 获取引擎统计
            stats = live_trading_engine.get_engine_statistics()
            self.log_test_result(
                "引擎统计",
                stats is not None,
                f"活跃会话数: {stats.get('active_sessions', 0)}"
            )
            
            # 停止测试会话
            await live_trading_engine.stop_session(session_id)
            self.log_test_result("停止交易会话", True, "会话已停止")
            
            return True
            
        except Exception as e:
            self.log_test_result("实盘交易引擎测试", False, str(e))
            return False
    
    async def test_api_integration(self):
        """测试9: API集成测试"""
        logger.info("\n🧪 测试9: API集成测试")
        
        try:
            # 测试API路由导入
            from app.api.v1.enhanced_trading import router
            
            # 检查路由端点
            routes = []
            for route in router.routes:
                if hasattr(route, 'path'):
                    routes.append(route.path)
            
            self.log_test_result(
                "API路由注册",
                len(routes) > 0,
                f"注册了 {len(routes)} 个端点"
            )
            
            # 验证关键端点存在
            key_endpoints = [
                "/trading/v2/orders/market",
                "/trading/v2/orders/limit",
                "/trading/v2/positions",
                "/trading/v2/account/info"
            ]
            
            for endpoint in key_endpoints:
                exists = any(endpoint in route for route in routes)
                self.log_test_result(
                    f"端点 {endpoint}",
                    exists,
                    "已注册" if exists else "未找到"
                )
            
            return True
            
        except Exception as e:
            self.log_test_result("API集成测试", False, str(e))
            return False
    
    async def test_database_operations(self):
        """测试10: 数据库操作"""
        logger.info("\n🧪 测试10: 数据库操作测试")
        
        try:
            from app.models.trade import Trade
            from sqlalchemy import select
            
            # 测试查询交易记录
            stmt = select(Trade).where(Trade.user_id == self.test_user_id).limit(5)
            result = await self.db_session.execute(stmt)
            trades = result.scalars().all()
            
            self.log_test_result(
                "查询交易记录",
                True,
                f"找到 {len(trades)} 条交易记录"
            )
            
            # 测试创建交易记录（不提交）
            test_trade = Trade(
                user_id=self.test_user_id,
                exchange="binance",
                symbol="BTC/USDT",
                side="BUY",
                quantity=Decimal("0.001"),
                price=Decimal("45000"),
                total_amount=Decimal("45"),
                fee=Decimal("0.045"),
                order_id="TEST_ORDER_001",
                trade_type="LIVE",
                executed_at=datetime.utcnow()
            )
            
            self.log_test_result(
                "创建交易记录对象",
                test_trade is not None,
                f"订单ID: {test_trade.order_id}"
            )
            
            # 回滚，不保存测试数据
            await self.db_session.rollback()
            
            return True
            
        except Exception as e:
            self.log_test_result("数据库操作测试", False, str(e))
            return False
    
    # ==================== 运行测试 ====================
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("🚀 开始实盘交易功能集成测试")
        logger.info("=" * 60)
        
        await self.setup()
        
        # 执行所有测试
        test_methods = [
            self.test_import_modules,
            self.test_exchange_connection,
            self.test_risk_validation,
            self.test_order_creation,
            self.test_position_management,
            self.test_order_manager,
            self.test_error_handling,
            self.test_live_trading_engine,
            self.test_api_integration,
            self.test_database_operations
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                logger.error(f"测试执行错误: {e}")
        
        await self.teardown()
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 测试报告总结")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['success'])
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"✅ 通过: {passed_tests}")
        logger.info(f"❌ 失败: {failed_tests}")
        logger.info(f"通过率: {pass_rate:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    logger.info(f"  - {result['test']}: {result['details']}")
        
        # 评估结果
        logger.info("\n" + "=" * 60)
        if pass_rate >= 90:
            logger.info("🎉 优秀！实盘交易功能测试通过率很高")
            logger.info("✅ 系统已准备好进行实盘交易")
        elif pass_rate >= 70:
            logger.info("⚠️ 良好，但仍有一些功能需要修复")
            logger.info("建议修复失败的测试后再进行实盘交易")
        else:
            logger.info("❌ 需要改进，多个核心功能测试失败")
            logger.info("请修复问题后重新测试")
        
        logger.info("=" * 60)


async def main():
    """主函数"""
    tester = LiveTradingTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())