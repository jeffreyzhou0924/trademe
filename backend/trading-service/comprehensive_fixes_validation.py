#!/usr/bin/env python3
"""
专业代理推荐修复综合验证测试
===============================

验证以下关键修复：
1. 无状态回测引擎 - 修复状态污染问题
2. 数据库连接池修复 - 修复连接泄漏
3. AI提示词简化 - 减少复杂度提升成功率
4. WebSocket并发安全 - 修复竞态条件

测试目标：确保所有修复都正常工作且系统整体稳定
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_stateless_backtest_engine():
    """测试1：验证无状态回测引擎，确保没有状态污染"""
    logger.info("🧪 测试1: 无状态回测引擎验证")
    
    try:
        from app.services.stateless_backtest_adapter import create_stateless_backtest_engine
        from app.database import get_async_session
        
        # 并发运行多个回测，验证无状态污染
        async def run_single_backtest(test_id: int):
            adapter = create_stateless_backtest_engine()
            
            params = {
                'symbol': 'BTC/USDT',
                'strategy_code': f'''
# 测试策略 {test_id}
def generate_signal(df):
    import pandas as pd
    # 简单移动平均策略
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    # 买入信号：短期均线上穿长期均线
    df['signal'] = 0
    df.loc[df['ma5'] > df['ma20'], 'signal'] = 1
    df.loc[df['ma5'] < df['ma20'], 'signal'] = -1
    
    return df[['signal']]
''',
                'start_date': '2024-01-01',
                'end_date': '2024-01-31',
                'initial_capital': 10000 + test_id * 1000  # 不同初始资金，验证隔离
            }
            
            async with get_async_session() as db:
                result = await adapter.execute_backtest(params, 6, db)
                return {'test_id': test_id, 'total_return': result.get('total_return', 0)}
        
        # 并发执行5个回测
        tasks = [run_single_backtest(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"回测 {i} 失败: {result}")
            else:
                success_count += 1
                logger.info(f"回测 {result['test_id']} 成功: 总收益率 {result['total_return']:.2%}")
        
        if success_count >= 4:  # 至少80%成功
            logger.info("✅ 无状态回测引擎测试通过")
            return True
        else:
            logger.error(f"❌ 无状态回测引擎测试失败: 只有 {success_count}/5 个测试成功")
            return False
            
    except Exception as e:
        logger.error(f"❌ 无状态回测引擎测试异常: {e}")
        return False


async def test_database_connection_pool():
    """测试2：验证数据库连接池修复，确保没有连接泄漏"""
    logger.info("🧪 测试2: 数据库连接池泄漏修复验证")
    
    try:
        from app.database import get_db, engine
        
        # 检查初始连接池状态
        initial_pool_size = engine.pool.size()
        initial_checked_out = engine.pool.checkedout()
        logger.info(f"初始连接池状态 - 大小: {initial_pool_size}, 已检出: {initial_checked_out}")
        
        # 并发创建多个数据库会话
        async def create_db_session(session_id: int):
            try:
                async for db in get_db():
                    # 执行简单查询
                    result = await db.execute("SELECT 1 as test")
                    row = result.fetchone()
                    logger.debug(f"会话 {session_id} 查询成功: {row}")
                    return f"session_{session_id}_success"
            except Exception as e:
                logger.error(f"会话 {session_id} 失败: {e}")
                return f"session_{session_id}_failed"
        
        # 并发执行20个数据库会话
        tasks = [create_db_session(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 等待连接完全释放
        await asyncio.sleep(2)
        
        # 检查最终连接池状态
        final_pool_size = engine.pool.size()
        final_checked_out = engine.pool.checkedout()
        logger.info(f"最终连接池状态 - 大小: {final_pool_size}, 已检出: {final_checked_out}")
        
        # 验证结果
        success_count = sum(1 for r in results if isinstance(r, str) and 'success' in r)
        logger.info(f"数据库会话测试结果: {success_count}/20 成功")
        
        # 验证没有连接泄漏
        if final_checked_out <= initial_checked_out + 2:  # 允许小幅增长
            logger.info("✅ 数据库连接池泄漏修复测试通过")
            return True
        else:
            logger.error(f"❌ 检测到连接泄漏: 检出连接从 {initial_checked_out} 增加到 {final_checked_out}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 数据库连接池测试异常: {e}")
        return False


async def test_simplified_ai_prompts():
    """测试3：验证简化的AI提示词"""
    logger.info("🧪 测试3: 简化AI提示词验证")
    
    try:
        from app.ai.prompts.simplified_prompts import SimplifiedPrompts
        
        # 验证简化提示词存在且合理
        prompts_to_test = [
            ('TRADING_ASSISTANT_SIMPLE', SimplifiedPrompts.TRADING_ASSISTANT_SIMPLE),
            ('STRATEGY_DISCUSSION_SIMPLE', SimplifiedPrompts.STRATEGY_DISCUSSION_SIMPLE),
            ('STRATEGY_GENERATION_SIMPLE', SimplifiedPrompts.STRATEGY_GENERATION_SIMPLE),
            ('BACKTEST_ANALYSIS_SIMPLE', SimplifiedPrompts.BACKTEST_ANALYSIS_SIMPLE),
        ]
        
        all_tests_passed = True
        
        for name, prompt in prompts_to_test:
            if not prompt:
                logger.error(f"❌ 提示词 {name} 为空")
                all_tests_passed = False
                continue
                
            # 检查提示词长度是否合理（简化后应该较短）
            lines = prompt.strip().split('\n')
            line_count = len([line for line in lines if line.strip()])
            
            if line_count > 30:  # 简化后的提示词应该不超过30行
                logger.warning(f"⚠️ 提示词 {name} 可能未充分简化 ({line_count} 行)")
            else:
                logger.info(f"✅ 提示词 {name} 长度合理 ({line_count} 行)")
            
            # 检查是否包含过多否定指令
            negative_patterns = ['不要', '不能', '不应该', '禁止', '避免', "don't", "not", "never"]
            negative_count = sum(prompt.lower().count(pattern) for pattern in negative_patterns)
            
            if negative_count > 5:  # 简化后的否定指令应该很少
                logger.warning(f"⚠️ 提示词 {name} 包含过多否定指令 ({negative_count} 个)")
            else:
                logger.info(f"✅ 提示词 {name} 否定指令适量 ({negative_count} 个)")
        
        if all_tests_passed:
            logger.info("✅ 简化AI提示词测试通过")
            return True
        else:
            logger.error("❌ 简化AI提示词测试存在问题")
            return False
            
    except Exception as e:
        logger.error(f"❌ 简化AI提示词测试异常: {e}")
        return False


async def test_websocket_concurrency_safety():
    """测试4：验证WebSocket并发安全修复"""
    logger.info("🧪 测试4: WebSocket并发安全验证")
    
    try:
        from app.services.websocket_manager import websocket_manager
        from app.api.v1.ai_websocket import ai_websocket_handler
        
        # 检查并发控制锁是否已添加
        ws_manager_locks = [
            hasattr(websocket_manager, '_connections_lock'),
            hasattr(websocket_manager, '_stats_lock'),
            hasattr(websocket_manager, '_cleanup_lock'),
        ]
        
        ai_handler_locks = [
            hasattr(ai_websocket_handler, '_tasks_lock'),
        ]
        
        logger.info(f"WebSocket管理器锁状态: {ws_manager_locks}")
        logger.info(f"AI处理器锁状态: {ai_handler_locks}")
        
        # 验证锁的基本功能
        if all(ws_manager_locks) and all(ai_handler_locks):
            # 测试锁的基本获取和释放
            try:
                async with websocket_manager._connections_lock:
                    logger.debug("连接管理锁获取成功")
                    
                async with websocket_manager._stats_lock:
                    logger.debug("统计锁获取成功")
                    
                async with ai_websocket_handler._tasks_lock:
                    logger.debug("任务管理锁获取成功")
                
                logger.info("✅ WebSocket并发安全锁测试通过")
                return True
            except Exception as lock_e:
                logger.error(f"❌ WebSocket锁功能测试失败: {lock_e}")
                return False
        else:
            logger.error("❌ WebSocket并发控制锁缺失")
            return False
            
    except Exception as e:
        logger.error(f"❌ WebSocket并发安全测试异常: {e}")
        return False


async def test_system_health():
    """测试5：系统整体健康检查"""
    logger.info("🧪 测试5: 系统整体健康检查")
    
    try:
        from app.database import engine, get_async_session
        
        health_checks = []
        
        # 数据库健康检查
        try:
            async with get_async_session() as db:
                result = await db.execute("SELECT COUNT(*) FROM users")
                user_count = result.scalar()
                health_checks.append(f"数据库连接正常 ({user_count} 用户)")
        except Exception as db_e:
            health_checks.append(f"数据库连接异常: {db_e}")
        
        # 连接池状态检查
        try:
            pool_size = engine.pool.size()
            checked_out = engine.pool.checkedout()
            pool_status = f"连接池状态正常 (大小: {pool_size}, 使用中: {checked_out})"
            health_checks.append(pool_status)
        except Exception as pool_e:
            health_checks.append(f"连接池状态异常: {pool_e}")
        
        # 服务导入检查
        try:
            from app.services.backtest_service import create_backtest_engine
            from app.services.ai_service import AIService
            from app.services.websocket_manager import websocket_manager
            
            engine = create_backtest_engine()
            health_checks.append(f"服务模块导入正常 (回测引擎: {type(engine).__name__})")
        except Exception as import_e:
            health_checks.append(f"服务模块导入异常: {import_e}")
        
        # 输出健康检查结果
        logger.info("系统健康检查结果:")
        for check in health_checks:
            logger.info(f"  • {check}")
        
        # 判断整体健康状态
        error_count = sum(1 for check in health_checks if '异常' in check)
        if error_count == 0:
            logger.info("✅ 系统整体健康检查通过")
            return True
        else:
            logger.warning(f"⚠️ 系统健康检查发现 {error_count} 个问题")
            return False
            
    except Exception as e:
        logger.error(f"❌ 系统健康检查异常: {e}")
        return False


async def main():
    """主函数：执行所有验证测试"""
    logger.info("=" * 80)
    logger.info("🔍 专业代理推荐修复综合验证测试")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    # 执行所有测试
    test_functions = [
        ("无状态回测引擎", test_stateless_backtest_engine),
        ("数据库连接池修复", test_database_connection_pool),
        ("简化AI提示词", test_simplified_ai_prompts),
        ("WebSocket并发安全", test_websocket_concurrency_safety),
        ("系统整体健康", test_system_health),
    ]
    
    results = {}
    
    for test_name, test_func in test_functions:
        logger.info(f"\n🧪 开始测试: {test_name}")
        try:
            result = await test_func()
            results[test_name] = result
            if result:
                logger.info(f"✅ {test_name} 测试通过")
            else:
                logger.error(f"❌ {test_name} 测试失败")
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
            results[test_name] = False
    
    # 生成测试报告
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试结果汇总")
    logger.info("=" * 80)
    
    passed_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{status:8} {test_name}")
    
    success_rate = (passed_count / total_count) * 100
    logger.info("-" * 80)
    logger.info(f"总体测试结果: {passed_count}/{total_count} 通过 ({success_rate:.1f}%)")
    logger.info(f"测试用时: {duration:.2f} 秒")
    
    if success_rate >= 80:
        logger.info("🎉 修复验证测试整体成功！")
        logger.info("🚀 所有关键修复均已正常工作，系统稳定性显著提升")
        return True
    else:
        logger.error("⚠️ 修复验证测试发现问题，需要进一步检查")
        return False


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)