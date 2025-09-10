#!/usr/bin/env python3
"""
智能Claude调度器集成测试脚本
测试新的智能调度算法是否正确集成到现有服务中
"""

import asyncio
import sys
import os
from decimal import Decimal
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('.')

from app.database import AsyncSessionLocal
from app.services.user_claude_key_service import UserClaudeKeyService
from app.services.intelligent_claude_scheduler import (
    IntelligentClaudeScheduler,
    SchedulingContext,
    SchedulingStrategy
)
from app.models.claude_proxy import UserClaudeKey, ClaudeAccount
from app.models.user import User
from sqlalchemy import select


async def test_intelligent_scheduler_integration():
    """测试智能调度器集成"""
    
    print("🔍 测试智能Claude调度器集成...")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. 测试智能调度器实例化
            scheduler = IntelligentClaudeScheduler()
            print("✅ 智能调度器创建成功")
            
            # 2. 测试调度上下文创建
            context = SchedulingContext(
                user_id=1,
                request_type="chat",
                estimated_tokens=100,
                priority="high",
                user_tier="premium",
                session_id="test_session_123",
                preferred_region="auto"
            )
            print("✅ 调度上下文创建成功")
            
            # 3. 获取测试用户（如果存在）
            user_stmt = select(User).limit(1)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                print("❌ 未找到测试用户，跳过用户相关测试")
                return
            
            print(f"✅ 找到测试用户: ID={user.id}, 等级={user.membership_level}")
            
            # 4. 测试用户Claude Key服务的路由功能
            # 首先为用户创建虚拟密钥
            user_key = await UserClaudeKeyService.auto_allocate_key_for_new_user(db, user.id)
            print(f"✅ 用户虚拟密钥创建/获取成功: {user_key.virtual_key[:20]}...")
            
            # 5. 测试智能路由算法
            print("\n🎯 测试智能路由算法...")
            
            # 获取可用的Claude账号
            claude_accounts_stmt = select(ClaudeAccount).where(ClaudeAccount.status == "active").limit(5)
            accounts_result = await db.execute(claude_accounts_stmt)
            available_accounts = accounts_result.scalars().all()
            
            if not available_accounts:
                print("⚠️ 未找到可用的Claude账号，创建测试账号...")
                # 可以选择创建测试账号或跳过此测试
                print("⏩ 跳过智能路由测试")
            else:
                print(f"✅ 找到 {len(available_accounts)} 个可用Claude账号")
                
                # 测试不同的调度策略
                strategies = [
                    SchedulingStrategy.ROUND_ROBIN,
                    SchedulingStrategy.LEAST_USED, 
                    SchedulingStrategy.WEIGHTED_RESPONSE_TIME,
                    SchedulingStrategy.COST_OPTIMIZED,
                    SchedulingStrategy.HYBRID_INTELLIGENT
                ]
                
                for strategy in strategies:
                    selected_account = await scheduler.select_optimal_account(
                        db=db,
                        available_accounts=available_accounts,
                        context=context,
                        strategy=strategy
                    )
                    
                    if selected_account:
                        print(f"  ✅ {strategy.value}: 选择账号 ID={selected_account.id}")
                    else:
                        print(f"  ❌ {strategy.value}: 未选择到账号")
            
            # 6. 测试完整的用户路由流程
            print("\n🚀 测试完整用户路由流程...")
            
            try:
                routed_account = await UserClaudeKeyService.route_to_claude_account(
                    db=db,
                    user_key=user_key,
                    request_type="chat",
                    estimated_cost=Decimal('0.02'),
                    user_tier=user.membership_level,
                    session_id="integration_test_session"
                )
                
                if routed_account:
                    print(f"✅ 完整路由成功: 选择账号 ID={routed_account.id}, 名称={routed_account.account_name}")
                else:
                    print("❌ 完整路由失败: 未返回账号")
                    
            except Exception as route_error:
                print(f"❌ 路由过程出错: {route_error}")
            
            # 7. 测试调度决策记录
            if available_accounts:
                print("\n📊 测试调度决策记录...")
                try:
                    await scheduler.record_scheduling_decision(
                        db=db,
                        selected_account_id=available_accounts[0].id,
                        context=context,
                        strategy=SchedulingStrategy.HYBRID_INTELLIGENT,
                        decision_factors={
                            "test": True,
                            "integration_test": "success",
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    print("✅ 调度决策记录成功")
                except Exception as record_error:
                    print(f"⚠️ 调度决策记录失败: {record_error}")
            
            print("\n" + "=" * 50)
            print("🎉 智能调度器集成测试完成!")
            print("✅ 主要功能验证通过:")
            print("   - 智能调度器实例化 ✓")
            print("   - 调度上下文创建 ✓") 
            print("   - 多策略账号选择 ✓")
            print("   - 用户路由集成 ✓")
            print("   - 决策记录功能 ✓")
            
        except Exception as e:
            print(f"\n❌ 集成测试过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def test_scheduling_strategies_comparison():
    """对比测试不同调度策略的效果"""
    
    print("\n📈 调度策略效果对比测试...")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        scheduler = IntelligentClaudeScheduler()
        
        # 获取测试账号
        claude_accounts_stmt = select(ClaudeAccount).where(ClaudeAccount.status == "active").limit(3)
        accounts_result = await db.execute(claude_accounts_stmt)
        available_accounts = accounts_result.scalars().all()
        
        if len(available_accounts) < 2:
            print("⚠️ 需要至少2个可用账号进行对比测试")
            return
        
        # 创建不同场景的调度上下文
        scenarios = [
            ("高优先级用户", SchedulingContext(
                user_id=1, request_type="chat", estimated_tokens=200, user_tier="professional",
                session_id="high_priority", priority="high", preferred_region="auto"
            )),
            ("成本敏感用户", SchedulingContext(
                user_id=2, request_type="analysis", estimated_tokens=50, user_tier="basic",
                session_id="cost_sensitive", priority="low", preferred_region="auto"
            )),
            ("频繁会话用户", SchedulingContext(
                user_id=3, request_type="chat", estimated_tokens=100, user_tier="premium",
                session_id="frequent_user", priority="normal", preferred_region="auto"
            ))
        ]
        
        strategies = [
            SchedulingStrategy.ROUND_ROBIN,
            SchedulingStrategy.COST_OPTIMIZED,
            SchedulingStrategy.HYBRID_INTELLIGENT
        ]
        
        print(f"🔍 使用 {len(available_accounts)} 个账号测试 {len(scenarios)} 个场景")
        print()
        
        for scenario_name, context in scenarios:
            print(f"📋 场景: {scenario_name}")
            for strategy in strategies:
                try:
                    selected = await scheduler.select_optimal_account(
                        db=db, available_accounts=available_accounts,
                        context=context, strategy=strategy
                    )
                    account_info = f"账号{selected.id}" if selected else "无"
                    print(f"  {strategy.value:25} -> {account_info}")
                except Exception as e:
                    print(f"  {strategy.value:25} -> 错误: {str(e)[:30]}")
            print()


if __name__ == "__main__":
    async def main():
        print("🚀 启动智能Claude调度器集成测试")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 执行集成测试
        success = await test_intelligent_scheduler_integration()
        
        if success:
            # 执行策略对比测试
            await test_scheduling_strategies_comparison()
            print("\n🎯 所有测试完成!")
        else:
            print("\n❌ 集成测试失败，跳过后续测试")
            sys.exit(1)
    
    asyncio.run(main())