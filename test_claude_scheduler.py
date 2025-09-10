#!/usr/bin/env python3
"""
Claude智能调度器测试脚本
测试调度器是否能正确选择Production Claude账号
"""

import asyncio
import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.intelligent_claude_scheduler import IntelligentClaudeScheduler, SchedulingContext
from app.models.claude_proxy import ClaudeAccount
from sqlalchemy import select


async def test_claude_scheduler():
    """测试Claude智能调度器"""
    print("🚀 Claude智能调度器测试开始\n")
    
    scheduler = IntelligentClaudeScheduler()
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. 获取所有活跃的Claude账号
            print("📋 获取活跃的Claude账号...")
            result = await db.execute(
                select(ClaudeAccount).where(
                    ClaudeAccount.status == 'active'
                )
            )
            available_accounts = result.scalars().all()
            
            print(f"   找到 {len(available_accounts)} 个活跃账号:")
            for account in available_accounts:
                print(f"   - {account.account_name} (ID: {account.id})")
                print(f"     API密钥: {account.api_key[:10]}...")
                print(f"     状态: {account.status}")
            
            if not available_accounts:
                print("❌ 没有找到活跃的Claude账号")
                return False
            
            # 2. 创建调度上下文
            print(f"\n🎯 创建调度上下文...")
            context = SchedulingContext(
                user_id=9,
                membership_level="premium",
                request_type="chat",
                estimated_tokens=100,
                priority=1,
                region="global",
                model_preference="claude-3-sonnet",
                cost_budget=1.0
            )
            print(f"   用户ID: {context.user_id}")
            print(f"   会员级别: {context.membership_level}")
            print(f"   请求类型: {context.request_type}")
            
            # 3. 使用调度器选择最优账号
            print(f"\n🔍 运行智能调度算法...")
            selected_account = await scheduler.select_optimal_account(
                db=db,
                available_accounts=available_accounts,
                context=context
            )
            
            if selected_account:
                print(f"\n✅ 调度器选择结果:")
                print(f"   选中账号: {selected_account.account_name}")
                print(f"   账号ID: {selected_account.id}")
                print(f"   API密钥: {selected_account.api_key[:20]}...")
                print(f"   状态: {selected_account.status}")
                
                # 检查是否选择了Production账号
                if "Production" in selected_account.account_name:
                    print(f"   🎉 调度器成功选择了Production Claude账号!")
                else:
                    print(f"   ℹ️  调度器选择了其他账号")
                
                # 4. 测试调度决策记录
                print(f"\n📊 记录调度决策...")
                await scheduler.record_scheduling_decision(
                    db=db,
                    selected_account=selected_account,
                    context=context,
                    decision_factors={
                        "availability_score": 0.9,
                        "performance_score": 0.8,
                        "cost_score": 0.7,
                        "total_score": 0.8
                    }
                )
                print(f"   ✅ 调度决策已记录")
                
                return True
            else:
                print(f"\n❌ 调度器未能选择任何账号")
                return False
                
        except Exception as e:
            print(f"❌ 调度器测试失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


async def test_ai_chat_workflow():
    """测试完整的AI对话工作流"""
    print(f"\n" + "="*60)
    print("🤖 完整AI对话工作流测试")
    print("="*60)
    
    # 这里模拟AI对话API的调用
    from app.services.claude_account_service import ClaudeAccountService
    
    async with AsyncSessionLocal() as db:
        try:
            service = ClaudeAccountService(db)
            
            # 测试获取可用账号
            print("🔍 查询可用的Claude账号...")
            account = await service.get_available_account("premium")
            
            if account:
                print(f"✅ 找到可用账号: {account.account_name}")
                print(f"   API密钥类型: {'官方API' if account.api_key.startswith('sk-ant-api') else 'Web会话' if account.api_key.startswith('cr_') else '未知类型'}")
                
                # 这里可以添加实际的Claude API调用测试
                print(f"⚠️  注意: 实际API调用需要有效的密钥")
                
            else:
                print(f"❌ 未找到可用的Claude账号")
                
        except Exception as e:
            print(f"❌ AI对话工作流测试失败: {str(e)}")
            import traceback
            traceback.print_exc()


async def main():
    """主测试函数"""
    success1 = await test_claude_scheduler()
    await test_ai_chat_workflow()
    
    print(f"\n" + "="*60)
    print("🎯 测试结果总结")
    print("="*60)
    
    if success1:
        print("✅ Claude智能调度器: 正常工作")
        print("📋 Production账号状态: 已配置，但密钥可能需要更新")
        print("🔧 建议: 更新为有效的Claude API密钥或网站会话密钥")
    else:
        print("❌ Claude智能调度器: 存在问题")
    
    print(f"\n💡 后续建议:")
    print(f"1. 如果Production账号使用的是Claude.ai网站会话密钥(cr_开头):")
    print(f"   - 确保会话未过期")
    print(f"   - 考虑使用官方API密钥(sk-ant-api开头)")
    print(f"2. 如果使用官方API密钥:")
    print(f"   - 确保密钥有效且未过期")
    print(f"   - 检查API配额是否充足")


if __name__ == "__main__":
    asyncio.run(main())