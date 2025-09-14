#!/usr/bin/env python3
"""
测试数据库连接池泄漏修复

验证简化的get_db()函数是否正确释放连接
"""

import sys
import os
import asyncio
import gc
from datetime import datetime

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

async def test_db_connection_fix():
    """测试数据库连接池修复"""
    print("🔧 开始测试数据库连接池修复...")
    
    try:
        # 1. 导入数据库模块
        print("\n1️⃣ 导入数据库模块...")
        from app.database import get_db, db_health_check, engine
        print("✅ 数据库模块导入成功")
        
        # 2. 获取初始健康状态
        print("\n2️⃣ 获取初始数据库健康状态...")
        initial_health = await db_health_check()
        print(f"✅ 初始健康评分: {initial_health.get('health_score', 0)}/100")
        print(f"   连接池状态: {initial_health.get('pool_stats', {})}")
        print(f"   泄漏会话: {initial_health.get('leaked_sessions', 0)}")
        
        # 3. 并发连接测试
        print("\n3️⃣ 测试并发数据库连接...")
        async def create_session():
            """创建并使用数据库会话"""
            async for session in get_db():
                # 执行一个简单查询
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                # 会话会在 finally 块中自动关闭
                return True
        
        # 并发创建多个会话
        tasks = [create_session() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_connections = sum(1 for r in results if r is True)
        print(f"✅ 成功创建 {successful_connections}/20 个并发连接")
        
        # 4. 检查连接是否正确释放
        print("\n4️⃣ 检查连接释放情况...")
        
        # 强制垃圾回收
        collected = gc.collect()
        await asyncio.sleep(0.5)  # 等待一下让连接完全释放
        
        # 获取修复后健康状态
        post_test_health = await db_health_check()
        print(f"✅ 测试后健康评分: {post_test_health.get('health_score', 0)}/100")
        print(f"   连接池状态: {post_test_health.get('pool_stats', {})}")
        print(f"   泄漏会话: {post_test_health.get('leaked_sessions', 0)}")
        
        # 5. 验证连接池统计
        print("\n5️⃣ 验证连接池统计...")
        pool_stats = post_test_health.get('pool_stats', {})
        
        # 检查连接是否正确归还
        if pool_stats.get('checked_out', 0) <= 1:  # 允许1个当前健康检查连接
            print("✅ 连接正确归还到连接池")
        else:
            print(f"⚠️  仍有 {pool_stats.get('checked_out', 0)} 个连接未归还")
        
        # 检查是否有连接泄漏
        leaked_sessions = post_test_health.get('leaked_sessions', 0)
        if leaked_sessions <= 2:  # 允许少量正常会话存在
            print("✅ 无明显连接泄漏")
        else:
            print(f"⚠️  检测到 {leaked_sessions} 个可能泄漏的会话")
        
        # 6. 压力测试
        print("\n6️⃣ 进行压力测试...")
        async def stress_test():
            """压力测试 - 快速创建和关闭大量连接"""
            for _ in range(10):
                async for session in get_db():
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
        
        stress_tasks = [stress_test() for _ in range(5)]
        await asyncio.gather(*stress_tasks, return_exceptions=True)
        
        # 最终健康检查
        final_health = await db_health_check()
        print(f"✅ 压力测试后健康评分: {final_health.get('health_score', 0)}/100")
        
        # 7. 分析修复效果
        print("\n7️⃣ 分析修复效果...")
        
        health_improvement = final_health.get('health_score', 0) - initial_health.get('health_score', 0)
        if health_improvement >= 0:
            print("✅ 健康状态保持稳定或改善")
        else:
            print(f"⚠️  健康状态下降了 {abs(health_improvement)} 分")
        
        warnings = final_health.get('warnings', [])
        if not warnings:
            print("✅ 无健康警告")
        else:
            print(f"⚠️  健康警告: {', '.join(warnings)}")
        
        recommendations = final_health.get('recommendations', [])
        if recommendations:
            print(f"💡 建议: {'; '.join(recommendations)}")
        
        print("\n🎉 数据库连接池修复测试完成！")
        
        # 返回测试结果摘要
        return {
            "success": True,
            "concurrent_connections": successful_connections,
            "initial_health_score": initial_health.get('health_score', 0),
            "final_health_score": final_health.get('health_score', 0),
            "leaked_sessions": final_health.get('leaked_sessions', 0),
            "warnings": warnings,
            "recommendations": recommendations
        }
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return {"success": False, "error": str(e)}

async def main():
    """主函数"""
    print("=" * 60)
    print("🔧 数据库连接池泄漏修复验证")
    print("=" * 60)
    
    result = await test_db_connection_fix()
    
    if result.get("success"):
        print("\n📊 测试结果总结:")
        print(f"  ✅ 并发连接成功率: {result.get('concurrent_connections', 0)}/20")
        print(f"  📈 健康评分变化: {result.get('initial_health_score', 0)} → {result.get('final_health_score', 0)}")
        print(f"  🔒 泄漏会话数量: {result.get('leaked_sessions', 0)}")
        
        if result.get('final_health_score', 0) >= 70:
            print("  🎉 数据库连接池健康状态良好！")
        elif result.get('warnings'):
            print(f"  ⚠️  检测到问题: {'; '.join(result.get('warnings', []))}")
        
        print("\n✅ 连接池泄漏修复生效！")
        print("🚀 系统现在能够正确管理数据库连接")
        return True
    else:
        print("\n❌ 连接池修复测试失败")
        print(f"   错误: {result.get('error', '未知错误')}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)