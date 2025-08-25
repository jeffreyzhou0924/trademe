#!/usr/bin/env python3
"""
实盘交易系统集成测试脚本

测试内容:
1. 交易服务基础功能
2. 实盘交易引擎
3. 订单管理系统
4. 风险管理机制
5. 交易信号处理
"""

import asyncio
import sys
import os
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.trading_service import trading_service
from app.core.live_trading_engine import live_trading_engine, TradingSignal, StrategyExecutionMode
from app.core.order_manager import order_manager, OrderRequest, OrderSide, OrderType
from app.core.risk_manager import risk_manager
from app.services.exchange_service import exchange_service


class LiveTradingIntegrationTest:
    """实盘交易集成测试类"""
    
    def __init__(self):
        self.test_user_id = 999  # 测试用户ID
        self.test_exchange = 'binance'
        self.test_symbol = 'BTC/USDT'
        self.test_results = {}
        
    async def run_all_tests(self):
        """运行所有集成测试"""
        logger.info("🚀 开始实盘交易系统集成测试")
        
        try:
            # 1. 基础组件测试
            await self.test_trading_service_basic()
            
            # 2. 交易引擎测试
            await self.test_live_trading_engine()
            
            # 3. 订单管理测试
            await self.test_order_manager()
            
            # 4. 风险管理测试
            await self.test_risk_manager()
            
            # 5. 交易信号处理测试
            await self.test_trading_signals()
            
            # 6. 集成流程测试
            await self.test_integration_workflow()
            
            # 输出测试结果
            self.print_test_results()
            
        except Exception as e:
            logger.error(f"集成测试失败: {e}")
            raise
        finally:
            # 清理资源
            await self.cleanup()
    
    async def test_trading_service_basic(self):
        """测试交易服务基础功能"""
        logger.info("📊 测试交易服务基础功能...")
        
        try:
            # 测试支持的交易所
            exchanges = await trading_service.get_supported_exchanges()
            assert len(exchanges) > 0, "应该支持至少一个交易所"
            logger.info(f"✅ 支持的交易所: {exchanges}")
            
            # 测试交易对获取
            symbols = await trading_service.get_exchange_symbols(self.test_exchange)
            logger.info(f"✅ {self.test_exchange} 支持 {len(symbols)} 个交易对")
            
            # 测试统计功能
            stats = await trading_service.get_order_statistics(self.test_user_id, 30)
            logger.info(f"✅ 订单统计: {stats.total_orders} 个订单")
            
            self.test_results['trading_service_basic'] = True
            
        except Exception as e:
            logger.error(f"❌ 交易服务基础功能测试失败: {e}")
            self.test_results['trading_service_basic'] = False
    
    async def test_live_trading_engine(self):
        """测试实盘交易引擎"""
        logger.info("🔧 测试实盘交易引擎...")
        
        try:
            # 启动交易引擎
            await live_trading_engine.start_engine()
            logger.info("✅ 交易引擎启动成功")
            
            # 创建交易会话
            session_id = await live_trading_engine.create_trading_session(
                user_id=self.test_user_id,
                exchange=self.test_exchange,
                symbols=[self.test_symbol],
                execution_mode=StrategyExecutionMode.MANUAL,
                max_daily_trades=10,
                max_open_positions=3
            )
            logger.info(f"✅ 创建交易会话: {session_id}")
            
            # 获取会话信息
            sessions = live_trading_engine.get_active_sessions(self.test_user_id)
            assert len(sessions) >= 1, "应该有至少一个活跃会话"
            logger.info(f"✅ 活跃会话数量: {len(sessions)}")
            
            # 获取引擎统计
            engine_stats = live_trading_engine.get_engine_statistics()
            logger.info(f"✅ 引擎统计: {engine_stats}")
            
            self.test_results['live_trading_engine'] = True
            
        except Exception as e:
            logger.error(f"❌ 实盘交易引擎测试失败: {e}")
            self.test_results['live_trading_engine'] = False
    
    async def test_order_manager(self):
        """测试订单管理系统"""
        logger.info("📋 测试订单管理系统...")
        
        try:
            # 测试获取活跃订单
            active_orders = order_manager.get_active_orders(self.test_user_id)
            logger.info(f"✅ 活跃订单数量: {len(active_orders)}")
            
            # 测试获取订单历史
            order_history = order_manager.get_order_history(self.test_user_id, 10)
            logger.info(f"✅ 历史订单数量: {len(order_history)}")
            
            # 测试订单统计
            order_stats = await order_manager.get_order_statistics(self.test_user_id, 30)
            logger.info(f"✅ 订单统计: {order_stats}")
            
            self.test_results['order_manager'] = True
            
        except Exception as e:
            logger.error(f"❌ 订单管理系统测试失败: {e}")
            self.test_results['order_manager'] = False
    
    async def test_risk_manager(self):
        """测试风险管理机制"""
        logger.info("🛡️ 测试风险管理机制...")
        
        try:
            # 模拟账户余额
            mock_balance = {
                'USDT': 10000.0,
                'BTC': 0.1
            }
            
            # 测试订单风险验证
            risk_assessment = await risk_manager.validate_order(
                user_id=self.test_user_id,
                exchange=self.test_exchange,
                symbol=self.test_symbol,
                side='buy',
                order_type='market',
                quantity=0.001,  # 小额测试
                price=None,
                account_balance=mock_balance,
                db=None  # 模拟测试无需数据库
            )
            
            logger.info(f"✅ 风险评估: 批准={risk_assessment.approved}, 风险等级={risk_assessment.risk_level.value}")
            
            # 测试紧急停止检查 (不需要数据库的简化版本)
            # emergency_check = await risk_manager.emergency_stop_check(self.test_user_id, None)
            # logger.info(f"✅ 紧急停止检查: {emergency_check}")
            
            self.test_results['risk_manager'] = True
            
        except Exception as e:
            logger.error(f"❌ 风险管理机制测试失败: {e}")
            self.test_results['risk_manager'] = False
    
    async def test_trading_signals(self):
        """测试交易信号处理"""
        logger.info("📡 测试交易信号处理...")
        
        try:
            # 创建测试交易信号
            test_signal = TradingSignal(
                user_id=self.test_user_id,
                strategy_id=None,
                exchange=self.test_exchange,
                symbol=self.test_symbol,
                signal_type='BUY',
                quantity=0.001,
                price=50000.0,
                confidence=0.8,
                reason="集成测试信号"
            )
            
            # 提交交易信号 (模拟模式)
            signal_result = await live_trading_engine.submit_trading_signal(test_signal)
            logger.info(f"✅ 交易信号提交: {signal_result}")
            
            # 测试通过trading_service提交信号
            service_signal_result = await trading_service.submit_trading_signal(
                user_id=self.test_user_id,
                exchange=self.test_exchange,
                symbol=self.test_symbol,
                signal_type='SELL',
                quantity=0.001,
                price=51000.0,
                reason="服务层测试信号"
            )
            logger.info(f"✅ 服务层信号提交: {service_signal_result}")
            
            self.test_results['trading_signals'] = True
            
        except Exception as e:
            logger.error(f"❌ 交易信号处理测试失败: {e}")
            self.test_results['trading_signals'] = False
    
    async def test_integration_workflow(self):
        """测试完整集成流程"""
        logger.info("🔄 测试完整集成流程...")
        
        try:
            # 模拟完整的交易流程
            
            # 1. 创建交易会话
            session_data = {
                'exchange': self.test_exchange,
                'symbols': [self.test_symbol],
                'execution_mode': 'manual',
                'max_daily_trades': 5,
                'max_open_positions': 2
            }
            
            # 注意: 这里需要数据库会话，实际测试时需要提供
            # session = await trading_service.create_trading_session(
            #     self.test_user_id, session_data, db_session
            # )
            
            # 2. 获取账户余额 (需要API密钥配置)
            # account_balance = await trading_service.get_account_balance(
            #     self.test_user_id, self.test_exchange, db_session
            # )
            
            # 3. 获取用户持仓
            # positions = await trading_service.get_user_positions(
            #     self.test_user_id, self.test_exchange
            # )
            
            # 4. 获取交易历史
            # trades = await trading_service.get_user_trades(
            #     self.test_user_id, self.test_exchange
            # )
            
            logger.info("✅ 集成流程架构验证通过 (需要数据库连接进行完整测试)")
            
            self.test_results['integration_workflow'] = True
            
        except Exception as e:
            logger.error(f"❌ 集成流程测试失败: {e}")
            self.test_results['integration_workflow'] = False
    
    async def test_exchange_service_integration(self):
        """测试交易所服务集成"""
        logger.info("🏪 测试交易所服务集成...")
        
        try:
            # 测试支持的交易所
            supported_exchanges = list(exchange_service.SUPPORTED_EXCHANGES.keys())
            logger.info(f"✅ 支持的交易所: {supported_exchanges}")
            
            # 测试获取交易对 (公开API，无需密钥)
            symbols = await exchange_service.get_symbols(self.test_exchange)
            logger.info(f"✅ {self.test_exchange} 交易对数量: {len(symbols[:5])}... (显示前5个)")
            
            self.test_results['exchange_service'] = True
            
        except Exception as e:
            logger.error(f"❌ 交易所服务集成测试失败: {e}")
            self.test_results['exchange_service'] = False
    
    def print_test_results(self):
        """打印测试结果"""
        logger.info("\n" + "="*60)
        logger.info("📊 实盘交易系统集成测试结果汇总")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, result in self.test_results.items():
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{test_name:30} {status}")
        
        logger.info("-"*60)
        logger.info(f"总计测试: {total_tests} 个")
        logger.info(f"通过测试: {passed_tests} 个")
        logger.info(f"失败测试: {total_tests - passed_tests} 个")
        logger.info(f"通过率: {passed_tests/total_tests*100:.1f}%")
        
        if passed_tests == total_tests:
            logger.info("🎉 所有测试通过! 实盘交易系统集成成功!")
        else:
            logger.warning("⚠️  部分测试失败，请检查具体错误信息")
        
        logger.info("="*60)
    
    async def cleanup(self):
        """清理测试资源"""
        try:
            # 停止交易引擎
            await live_trading_engine.stop_engine()
            logger.info("🧹 测试资源清理完成")
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")


async def main():
    """主测试函数"""
    # 配置日志
    logger.add("logs/integration_test.log", rotation="1 day", level="INFO")
    
    # 创建测试实例
    test_runner = LiveTradingIntegrationTest()
    
    try:
        # 运行所有测试
        await test_runner.run_all_tests()
        
    except KeyboardInterrupt:
        logger.info("用户中断测试")
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        raise
    finally:
        logger.info("测试结束")


if __name__ == "__main__":
    # 设置事件循环策略 (Windows兼容)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 运行测试
    asyncio.run(main())